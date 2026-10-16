-- Дополнительный модуль. Использует локальный выбранный CSV МЭВ,
-- подготовленный из исходного массива, и явную таблицу соответствий ID.
-- Выполнить блок создания таблиц, загрузить CSV и crosswalk, затем SELECT.
CREATE TABLE IF NOT EXISTS research_raw.mev_selected (
    id text, monitor_year text, id_parent text, inn text,
    region text, university text,
    humanities_students text, medical_students text, engineering_students text,
    arts_students text, natural_sciences_students text, social_sciences_students text,
    education_students text, agriculture_students text, total_students text,
    full_time_share text, bachelor_share text, master_share text
);
CREATE TABLE IF NOT EXISTS research.mev_crosswalk (
    university text PRIMARY KEY REFERENCES research.pilot_universities,
    mev_id text UNIQUE NOT NULL
);

CREATE OR REPLACE VIEW research.mev_context AS
SELECT research.normalized_text(id) AS id,
       research.parse_number(monitor_year)::integer AS monitor_year,
       research.parse_number(monitor_year)::integer - 1 AS report_year,
       research.normalized_text(id_parent) AS id_parent,
       research.normalized_text(university) AS university,
       research.normalized_text(region) AS region,
       research.parse_number(total_students) AS total_students,
       research.parse_number(engineering_students) AS engineering_students,
       research.parse_number(full_time_share) AS full_time_share,
       research.parse_number(bachelor_share) AS bachelor_share,
       research.parse_number(master_share) AS master_share,
       research.parse_number(humanities_students)+research.parse_number(medical_students)
        +research.parse_number(engineering_students)+research.parse_number(arts_students)
        +research.parse_number(natural_sciences_students)+research.parse_number(social_sciences_students)
        +research.parse_number(education_students)+research.parse_number(agriculture_students)
           AS equivalent_students
FROM research_raw.mev_selected;

-- Отличаем год мониторинга от отчётного года и головной вуз от филиала.
SELECT monitor_year, report_year, COUNT(*) AS observations,
       COUNT(*) FILTER (WHERE id_parent IS NULL) AS head_universities
FROM research.mev_context
GROUP BY monitor_year, report_year ORDER BY monitor_year;

-- Только допилотные отчётные 2021–2022. Пропущенный ID виден как NULL.
-- Доли bachelor/master/full_time уже представлены в процентах в selected CSV.
-- Это описание фокальных вузов, не автоматический подбор аналогов.
-- Численности областей знаний — приведённый контингент. Его доли считаются
-- в сумме восьми областей, а не в общей физической численности студентов.
SELECT p.short_name, m.report_year, m.total_students,
       ROUND(100 * m.engineering_students / NULLIF(m.equivalent_students, 0), 1)
           AS engineering_pct,
       m.full_time_share, m.bachelor_share, m.master_share
FROM research.pilot_universities p
LEFT JOIN research.mev_crosswalk x ON x.university = p.university
LEFT JOIN research.mev_context m
  ON m.id = x.mev_id AND m.id_parent IS NULL AND m.report_year IN (2021, 2022)
ORDER BY p.short_name, m.report_year;
