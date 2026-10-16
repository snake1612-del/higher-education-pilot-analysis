-- Дополнительные воспроизводимые проверки слайдов 6–9.
-- Число вузов фона — отдельный критерий, не порог исходного числа БВИ.
CREATE OR REPLACE VIEW research.bvi_donor_members AS
SELECT f.university, f.major_group, t.min_controls, c.control_universities
FROM research.final_panel_members f
CROSS JOIN (VALUES (1),(2),(3),(5)) t(min_controls)
JOIN research.subject_background c ON c.major_group=f.major_group
 AND c.metric='bvi' AND c.year=f.base_year
WHERE f.scope='cohort2023' AND f.side='linked' AND f.metric='bvi'
 AND f.base_year=2022 AND c.control_universities>=t.min_controls;

CREATE OR REPLACE VIEW research.bvi_donor_annual AS
SELECT f.university,f.min_controls,a.year,COUNT(*) AS groups_used,
 SUM(a.admitted) AS admitted,SUM(a.bvi) AS bvi,
 SUM(b.admitted*c.admitted/c0.admitted) AS reference_admitted,
 SUM(b.admitted*c.bvi/c0.admitted) AS reference_bvi
FROM research.bvi_donor_members f
JOIN research.mkp_annual a USING(university,major_group)
JOIN research.mkp_annual b ON b.university=f.university
 AND b.major_group=f.major_group AND b.year=2022
JOIN research.subject_background c ON c.major_group=f.major_group
 AND c.metric='bvi' AND c.year=a.year
JOIN research.subject_background c0 ON c0.major_group=f.major_group
 AND c0.metric='bvi' AND c0.year=2022
GROUP BY f.university,f.min_controls,a.year;

CREATE OR REPLACE VIEW research.bvi_donor_changes AS
SELECT a.university,a.min_controls,a.groups_used,b.admitted AS n0,a.admitted AS n1,
 b.bvi AS bvi0,a.bvi AS bvi1,100*b.bvi/b.admitted AS share0,
 100*a.bvi/a.admitted AS share1,
 100*((a.bvi/a.admitted-b.bvi/b.admitted)
 -(a.reference_bvi/a.reference_admitted-b.reference_bvi/b.reference_admitted)) AS share_gap_pp
FROM research.bvi_donor_annual a JOIN research.bvi_donor_annual b
 ON b.university=a.university AND b.min_controls=a.min_controls AND b.year=2022
WHERE a.year=2025;

CREATE OR REPLACE VIEW research.internal_score_contrasts AS
SELECT l.university,'current_controls'::text AS weights,
 l.groups_used AS linked_groups,o.groups_used AS other_groups,
 l.ege_fixed_gap AS linked_gap,o.ege_fixed_gap AS other_gap,
 l.ege_fixed_gap-o.ege_fixed_gap AS internal_gap
FROM research.comparison_changes l JOIN research.comparison_changes o
 ON o.university=l.university AND o.scope=l.scope AND o.metric=l.metric
 AND o.base_year=l.base_year AND o.end_year=l.end_year AND o.side='other_observed'
WHERE l.scope='cohort2023' AND l.metric='score' AND l.side='linked'
 AND l.base_year=2022 AND l.end_year=2025
UNION ALL
SELECT l.university,'fixed_controls',l.groups_used,o.groups_used,
 l.score_gap,o.score_gap,l.score_gap-o.score_gap
FROM research.double_fixed_score_changes l JOIN research.double_fixed_score_changes o
 ON o.university=l.university AND o.scope=l.scope AND o.base_year=l.base_year
 AND o.end_year=l.end_year AND o.side='other_observed'
WHERE l.scope='cohort2023' AND l.side='linked' AND l.base_year=2022 AND l.end_year=2025;

-- Проверка утверждения о вложенности именно опубликованной когорты.
DO $$
BEGIN
 IF EXISTS (
  SELECT FROM research.final_panel_members b
  WHERE b.scope='cohort2023' AND b.side='linked' AND b.metric='bvi' AND b.base_year=2022
   AND NOT EXISTS (SELECT FROM research.final_panel_members q
    WHERE q.university=b.university AND q.major_group=b.major_group
     AND q.scope=b.scope AND q.side='linked' AND q.metric='score' AND q.base_year=2022)
 ) THEN RAISE EXCEPTION 'BVI cohort is not nested in the score cohort'; END IF;
END $$;
