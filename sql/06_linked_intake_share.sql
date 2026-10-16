-- Доля связанных групп в постоянном составе наблюдений своего вуза.
-- Здесь нулевой известный приём допустим; пропуск недопустим.
-- Перечень confirmed_eventual фиксирован для всех лет, включая допилотные.
CREATE OR REPLACE VIEW research.linked_intake_share AS
SELECT a.university, a.year, COUNT(*) AS total_groups,
       COUNT(*) FILTER (WHERE l.major_group IS NOT NULL) AS linked_groups,
       SUM(a.admitted) AS total_admitted,
       SUM(a.admitted) FILTER (WHERE l.major_group IS NOT NULL) AS linked_admitted,
       100 * SUM(a.admitted) FILTER (WHERE l.major_group IS NOT NULL)
           / NULLIF(SUM(a.admitted), 0) AS linked_share_pct
FROM research.stable_group_metric s
JOIN research.mkp_annual a USING (university, major_group)
JOIN research.pilot_universities p USING (university)
LEFT JOIN research.scope_links l
  ON l.university = a.university AND l.major_group = a.major_group
 AND l.scope = 'confirmed_eventual'
WHERE s.metric = 'coverage' AND p.in_primary_cohort
GROUP BY a.university, a.year;

SELECT p.short_name, b.linked_groups, b.total_groups,
       ROUND(b.linked_share_pct, 2) AS share2022,
       ROUND(e.linked_share_pct, 2) AS share2025,
       ROUND(e.linked_share_pct - b.linked_share_pct, 2) AS change_pp
FROM research.linked_intake_share b
JOIN research.linked_intake_share e
  ON e.university = b.university AND e.year = 2025
JOIN research.pilot_universities p ON p.university = b.university
WHERE b.year = 2022 ORDER BY p.short_name;

-- Это НЕ доля непосредственно пилотных студентов и НЕ гарантированно
-- полный приём университета: знаменатель ограничен стабильной панелью.
