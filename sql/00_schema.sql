-- PostgreSQL. Выполнять в отдельной базе проекта.
-- Схемы проекта не изменяют существующую public.mkp_budget_raw.
BEGIN;
CREATE SCHEMA IF NOT EXISTS research_raw;
CREATE SCHEMA IF NOT EXISTS research;

CREATE TABLE IF NOT EXISTS research_raw.mkp_budget (
    major_group text, region text, university text, profile text,
    admitted_2021 text, admitted_2022 text, admitted_2023 text,
    admitted_2024 text, admitted_2025 text,
    bvi_2021 text, bvi_2022 text, bvi_2023 text, bvi_2024 text, bvi_2025 text,
    ege_2021 text, ege_2022 text, ege_2023 text, ege_2024 text, ege_2025 text
);

-- Точные названия вместо ILIKE: ТГУ не должен смешиваться с ТУСУР или ТПУ.
-- Участие в справочнике относится к вузу, а не ко всем его программам.
CREATE TABLE IF NOT EXISTS research.pilot_universities (
    university text PRIMARY KEY,
    short_name text UNIQUE NOT NULL,
    in_primary_cohort boolean NOT NULL
);
INSERT INTO research.pilot_universities VALUES
('Балтийский федеральный университет им. И. Канта', 'БФУ', false),
('Московский авиационный институт (национальный исследовательский университет)', 'МАИ', true),
('Национальный исследовательский технологический университет "МИСиС", г. Москва', 'МИСИС', true),
('Московский педагогический государственный университет', 'МПГУ', true),
('Национальный исследовательский Томский государственный университет', 'ТГУ', true),
('Санкт-Петербургский горный университет', 'Горный', false)
ON CONFLICT (university) DO UPDATE SET
    short_name = EXCLUDED.short_name,
    in_primary_cohort = EXCLUDED.in_primary_cohort;

-- Заполняется отдельно из проверенного реестра, не по значению результата.
-- cohort2023: документированные связи когорты 2023.
-- confirmed_eventual: фиксированный подтверждённый перечень к 2025 году.
-- Внутри связанной группы могут оставаться другие программы.
CREATE TABLE IF NOT EXISTS research.scope_links (
    university text NOT NULL REFERENCES research.pilot_universities,
    major_group text NOT NULL,
    scope text NOT NULL CHECK (scope IN ('cohort2023', 'confirmed_eventual')),
    evidence_note text NOT NULL,
    PRIMARY KEY (university, major_group, scope)
);
COMMIT;
