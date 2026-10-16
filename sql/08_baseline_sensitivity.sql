-- Изменение базы не должно выбираться по удобству знака результата.
-- При смене базы пересчитываются и исходные веса приёма.
SELECT p.short_name, c.base_year, c.end_year, c.groups_used,
       ROUND(c.ege_fixed_gap, 2) AS score_gap
FROM research.comparison_changes c
JOIN research.pilot_universities p USING (university)
WHERE c.scope = 'whole' AND c.metric = 'score' AND c.end_year = 2025
ORDER BY p.short_name, c.base_year;

-- Единственный допилотный интервал. Это диагностика, не тест
-- параллельных трендов и не доказательство причинного эффекта.
SELECT p.short_name, c.groups_used,
       ROUND(c.growth_gap_pp, 2) AS preperiod_intake_gap_pp,
       ROUND(c.ege_current_gap, 2) AS preperiod_score_gap
FROM research.comparison_changes c
JOIN research.pilot_universities p USING (university)
WHERE c.scope = 'cohort2023' AND c.side = 'linked' AND c.metric = 'score'
  AND c.base_year = 2021 AND c.end_year = 2022
ORDER BY p.short_name;
