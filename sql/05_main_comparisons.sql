-- 1. Баллы шести вузов. База и состав фиксированы, фон согласован по группам.
SELECT p.short_name, c.groups_used,
       ROUND(c.ege_fixed_change, 2) AS university_change,
       ROUND(c.reference_ege_fixed_change, 2) AS background_change,
       ROUND(c.ege_fixed_gap, 2) AS difference_in_changes
FROM research.comparison_changes c
JOIN research.pilot_universities p USING (university)
WHERE c.scope = 'whole' AND c.metric = 'score'
  AND c.base_year = 2022 AND c.end_year = 2025
ORDER BY p.short_name;

-- Полная траектория приёма основной когорты и годовые темпы через LAG.
WITH trajectory AS (
    SELECT university, year, admitted,
           LAG(admitted) OVER (PARTITION BY university ORDER BY year) AS prior_n
    FROM research.comparison_annual
    WHERE scope = 'cohort2023' AND side = 'linked' AND metric = 'score'
      AND base_year = 2022
)
SELECT p.short_name, t.year, t.admitted,
       ROUND(100 * (t.admitted / NULLIF(t.prior_n, 0) - 1), 2) AS annual_growth_pct
FROM trajectory t
JOIN research.pilot_universities p USING (university)
ORDER BY p.short_name, t.year;

-- 2. Приём основной когорты. Здесь фон соответствует проверенной панели
-- с известным баллом и положительным N во все пять лет (metric = 'score').
SELECT p.short_name, c.groups_used, c.n0, c.n1,
       ROUND(c.growth_pct, 2) AS growth_pct,
       ROUND(c.reference_growth_pct, 2) AS reference_growth_pct,
       ROUND(c.growth_gap_pp, 2) AS growth_gap_pp
FROM research.comparison_changes c
JOIN research.pilot_universities p USING (university)
WHERE c.scope = 'cohort2023' AND c.side = 'linked' AND c.metric = 'score'
  AND c.base_year = 2022 AND c.end_year = 2025
ORDER BY p.short_name;

-- Средний контраст вузов и совокупный рост панели — разные показатели.
SELECT COUNT(*) AS universities, SUM(groups_used) AS university_group_pairs,
       SUM(n0) AS n0, SUM(n1) AS n1, SUM(delta_n) AS delta_n,
       ROUND(100 * (SUM(n1) / SUM(n0) - 1), 2) AS pooled_growth_pct,
       ROUND(AVG(growth_gap_pp), 2) AS equal_university_growth_gap_pp
FROM research.comparison_changes
WHERE scope = 'cohort2023' AND side = 'linked' AND metric = 'score'
  AND base_year = 2022 AND end_year = 2025;

-- 3. Связанные против остальных групп одного вуза, с предметной поправкой.
-- Остальные наблюдаемые группы не обязательно полностью непилотные.
SELECT p.short_name, l.groups_used AS linked_groups,
       r.groups_used AS other_groups,
       ROUND(l.ege_fixed_gap - r.ege_fixed_gap, 2) AS adjusted_within_gap
FROM research.comparison_changes l
JOIN research.comparison_changes r
  ON r.university = l.university AND r.scope = l.scope AND r.metric = l.metric
 AND r.base_year = l.base_year AND r.end_year = l.end_year
 AND r.side = 'other_observed'
JOIN research.pilot_universities p ON p.university = l.university
WHERE l.scope = 'cohort2023' AND l.side = 'linked' AND l.metric = 'score'
  AND l.base_year = 2022 AND l.end_year = 2025
ORDER BY p.short_name;
