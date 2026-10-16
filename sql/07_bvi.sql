-- Для БВИ требуется собственная полная история. Известный EГЭ не обязателен.
SELECT p.short_name, c.groups_used, c.bvi0, c.bvi1, c.n0, c.n1,
       ROUND(c.bvi_share0, 2) AS share2022,
       ROUND(c.bvi_share1, 2) AS share2025,
       ROUND(c.bvi_share_gap_pp, 2) AS difference_to_background_pp
FROM research.comparison_changes c
JOIN research.pilot_universities p USING (university)
WHERE c.scope = 'cohort2023' AND c.side = 'linked' AND c.metric = 'bvi'
  AND c.base_year = 2022 AND c.end_year = 2025
ORDER BY p.short_name;

SELECT SUM(groups_used) AS university_group_pairs,
       SUM(bvi0) AS bvi0, SUM(bvi1) AS bvi1,
       SUM(n0) AS denominator0, SUM(n1) AS denominator1,
       ROUND(100 * SUM(bvi0) / SUM(n0), 2) AS pooled_share2022,
       ROUND(100 * SUM(bvi1) / SUM(n1), 2) AS pooled_share2025,
       ROUND(AVG(bvi_share_gap_pp), 2) AS equal_university_share_gap_pp
FROM research.comparison_changes
WHERE scope = 'cohort2023' AND side = 'linked' AND metric = 'bvi'
  AND base_year = 2022 AND end_year = 2025;

-- Диагностика малых баз: сколько связок остаётся при каждом пороге БВИ.
-- Порог применяется к исходному числу людей, а не к процентному росту.
WITH thresholds(min_bvi) AS (VALUES (0), (5), (10), (20))
SELECT t.min_bvi, COUNT(g.university) AS groups_remaining,
       COUNT(DISTINCT g.university) AS universities_remaining
FROM thresholds t
LEFT JOIN (
    SELECT g.university, g.major_group, a.bvi
    FROM research.group_membership g
    JOIN research.mkp_annual a USING (university, major_group)
    WHERE g.scope = 'cohort2023' AND g.side = 'linked' AND g.metric = 'bvi'
      AND a.year = 2022
      AND EXISTS (SELECT FROM research.subject_background c
                  WHERE c.major_group = g.major_group AND c.metric = 'bvi'
                    AND c.year = 2022)
) g ON g.bvi >= t.min_bvi
GROUP BY t.min_bvi ORDER BY t.min_bvi;

-- БВИ в методике МКП получают 100 баллов. EГЭ и доля БВИ не независимы.
