-- Ранний этап исследования. Состав и веса могут меняться по годам.
-- Это не итоговое сравнение с предметным фоном.
-- COUNT(*) — число групп; SUM(admitted) — число зачисленных.
WITH university_year AS (
    SELECT university, region, year,
           SUM(ege * admitted) / NULLIF(SUM(admitted), 0) AS university_ege,
           COUNT(*) AS groups_used, SUM(admitted) AS admitted_used
    FROM research.mkp_annual
    WHERE admitted > 0 AND ege IS NOT NULL
    GROUP BY university, region, year
), nonpilot AS (
    SELECT u.* FROM university_year u
    WHERE NOT EXISTS (SELECT FROM research.pilot_universities p
                      WHERE p.university = u.university)
), regional AS (
    SELECT region, year, AVG(university_ege) AS ege,
           COUNT(*) AS universities
    FROM nonpilot GROUP BY region, year
), national AS (
    SELECT year, AVG(university_ege) AS ege, COUNT(*) AS universities
    FROM nonpilot GROUP BY year
)
SELECT p.short_name, u.region, u.year,
       ROUND(u.university_ege, 2) AS university_ege,
       ROUND(r.ege, 2) AS region_ege, ROUND(n.ege, 2) AS country_ege,
       ROUND(u.university_ege - r.ege, 2) AS gap_to_region,
       ROUND(u.university_ege - n.ege, 2) AS gap_to_country,
       r.universities AS regional_universities,
       n.universities AS national_universities,
       u.groups_used, u.admitted_used
FROM university_year u
JOIN research.pilot_universities p USING (university)
LEFT JOIN regional r USING (region, year)
JOIN national n USING (year)
ORDER BY p.short_name, u.year;

-- Внешние вузы имеют равные веса в региональном / страновом среднем.
-- Внутри вуза баллы групп взвешены численностью бюджетного зачисления.
-- Это приближение: индивидуальный знаменатель официального балла неизвестен.
