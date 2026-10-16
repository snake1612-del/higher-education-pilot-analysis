-- Чистим представления, не переписывая исходные значения.
BEGIN;
CREATE OR REPLACE FUNCTION research.normalized_text(value text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT NULLIF(BTRIM(REGEXP_REPLACE(
        TRANSLATE(value, CHR(160) || CHR(8239), '  '), '\s+', ' ', 'g'
    )), '');
$$;

CREATE OR REPLACE FUNCTION research.parse_number(value text)
RETURNS numeric LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE AS $$
DECLARE cleaned text;
BEGIN
    cleaned := REPLACE(REGEXP_REPLACE(
        TRANSLATE(value, CHR(160) || CHR(8239), '  '), '\s+', '', 'g'
    ), ',', '.');
    IF cleaned IS NULL OR LOWER(cleaned) IN ('', '-', '—', 'н/д', 'na', 'n/a') THEN
        RETURN NULL;
    END IF;
    -- Неизвестный маркер должен вызвать ошибку, а не исчезнуть как пропуск.
    IF cleaned !~ '^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)$' THEN
        RAISE EXCEPTION 'Некорректное числовое значение: %', value;
    END IF;
    RETURN cleaned::numeric;
END;
$$;

-- Материализуем очистку один раз, чтобы не разбирать текст заново
-- при каждом соединении. После нового импорта повторить этот файл.
CREATE MATERIALIZED VIEW IF NOT EXISTS research.mkp_annual AS
SELECT research.normalized_text(t.major_group) AS major_group,
       research.normalized_text(t.region) AS region,
       research.normalized_text(t.university) AS university,
       research.normalized_text(t.profile) AS profile,
       y.year,
       research.parse_number(y.admitted) AS admitted,
       research.parse_number(y.bvi) AS bvi,
       research.parse_number(y.ege) AS ege
FROM research_raw.mkp_budget t
CROSS JOIN LATERAL (VALUES
    (2021, t.admitted_2021, t.bvi_2021, t.ege_2021),
    (2022, t.admitted_2022, t.bvi_2022, t.ege_2022),
    (2023, t.admitted_2023, t.bvi_2023, t.ege_2023),
    (2024, t.admitted_2024, t.bvi_2024, t.ege_2024),
    (2025, t.admitted_2025, t.bvi_2025, t.ege_2025)
) y(year, admitted, bvi, ege)
WITH NO DATA;
REFRESH MATERIALIZED VIEW research.mkp_annual;
CREATE INDEX IF NOT EXISTS mkp_annual_key
    ON research.mkp_annual (university, major_group, year);
ANALYZE research.mkp_annual;
COMMIT;
