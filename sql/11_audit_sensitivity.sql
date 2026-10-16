-- Проверки состава и альтернативные спецификации после независимого аудита.
-- Дополнение к 04: прежние итоговые показатели сохраняются для сопоставления.
CREATE OR REPLACE VIEW research.selection_flow AS
SELECT l.university, l.major_group, l.scope, m.metric, b.base_year,
       s.university IS NOT NULL AS complete_history,
       COALESCE(c.control_universities, 0) AS control_universities,
       CASE WHEN s.university IS NULL THEN 'incomplete_focal_history'
            WHEN c.major_group IS NULL THEN 'no_complete_controls'
            WHEN c.admitted = 0 THEN 'zero_control_baseline'
            ELSE 'included' END AS status
FROM research.scope_links l
JOIN research.pilot_universities p USING (university)
CROSS JOIN (VALUES ('score'), ('bvi'), ('intake')) m(metric)
CROSS JOIN (VALUES (2021), (2022)) b(base_year)
LEFT JOIN research.stable_group_metric s
  ON s.university=l.university AND s.major_group=l.major_group AND s.metric=m.metric
LEFT JOIN research.subject_background c
  ON c.major_group=l.major_group AND c.metric=m.metric AND c.year=b.base_year
WHERE p.in_primary_cohort;

-- Фактический состав всех панелей после присоединения фона.
CREATE OR REPLACE VIEW research.final_panel_members AS
SELECT g.*, b.base_year
FROM research.group_membership g
CROSS JOIN (VALUES (2021), (2022)) b(base_year)
JOIN research.subject_background c
  ON c.major_group=g.major_group AND c.metric=g.metric AND c.year=b.base_year
WHERE c.admitted > 0;

-- Охват приёма: знаменатель — весь ИЗВЕСТНЫЙ N в данном году, не все студенты.
CREATE OR REPLACE VIEW research.panel_coverage AS
SELECT f.university, f.scope, f.side, f.metric, f.base_year, a.year,
       COUNT(*) AS groups_used, SUM(a.admitted) AS panel_admitted,
       (SELECT SUM(z.admitted) FROM research.mkp_annual z
        WHERE z.university=f.university AND z.year=a.year AND z.admitted>=0)
           AS all_known_admitted,
       100*SUM(a.admitted)/NULLIF((SELECT SUM(z.admitted)
         FROM research.mkp_annual z WHERE z.university=f.university
           AND z.year=a.year AND z.admitted>=0),0) AS known_intake_covered_pct
FROM research.final_panel_members f
JOIN research.mkp_annual a USING (university, major_group)
GROUP BY f.university, f.scope, f.side, f.metric, f.base_year, a.year;

-- Вторая ступень фиксации: веса вузов-контролей внутри каждой группы.
CREATE OR REPLACE VIEW research.control_score_fixed AS
SELECT s.major_group, b.year AS base_year, a.year,
       SUM(b.admitted*a.ege)/SUM(b.admitted) AS ege
FROM research.stable_group_metric s
JOIN research.mkp_annual a USING (university, major_group)
JOIN research.mkp_annual b
  ON b.university=s.university AND b.major_group=s.major_group AND b.year IN (2021,2022)
WHERE s.metric='score' AND NOT EXISTS
  (SELECT FROM research.pilot_universities p WHERE p.university=s.university)
GROUP BY s.major_group, b.year, a.year;

CREATE OR REPLACE VIEW research.double_fixed_score_annual AS
SELECT f.university, f.scope, f.side, f.base_year, a.year,
       COUNT(*) AS groups_used,
       SUM(b.admitted*a.ege)/SUM(b.admitted) AS university_ege,
       SUM(b.admitted*c.ege)/SUM(b.admitted) AS reference_ege
FROM research.final_panel_members f
JOIN research.mkp_annual a USING (university, major_group)
JOIN research.mkp_annual b
  ON b.university=f.university AND b.major_group=f.major_group AND b.year=f.base_year
JOIN research.control_score_fixed c
  ON c.major_group=f.major_group AND c.base_year=f.base_year AND c.year=a.year
WHERE f.metric='score'
GROUP BY f.university, f.scope, f.side, f.base_year, a.year;

CREATE OR REPLACE VIEW research.double_fixed_score_changes AS
SELECT a.university, a.scope, a.side, a.base_year, a.year AS end_year, a.groups_used,
       (a.university_ege-b.university_ege)-(a.reference_ege-b.reference_ege) AS score_gap
FROM research.double_fixed_score_annual a
JOIN research.double_fixed_score_annual b
  ON b.university=a.university AND b.scope=a.scope AND b.side=a.side
 AND b.base_year=a.base_year AND b.year=a.base_year
WHERE a.year>a.base_year;

-- Порог применяется к БВИ каждой связки в базовом году. После исключения
-- пересчитываются N, B, веса групп и обе доли соответствующего фона.
CREATE OR REPLACE VIEW research.bvi_threshold_annual AS
SELECT f.university, f.scope, f.base_year, t.min_bvi, a.year,
       COUNT(*) AS groups_used, SUM(a.admitted) AS admitted, SUM(a.bvi) AS bvi,
       SUM(b.admitted*c.admitted/c0.admitted) AS reference_admitted,
       SUM(b.admitted*c.bvi/c0.admitted) AS reference_bvi
FROM research.final_panel_members f
CROSS JOIN (VALUES (0), (5), (10), (20)) t(min_bvi)
JOIN research.mkp_annual a USING (university, major_group)
JOIN research.mkp_annual b
  ON b.university=f.university AND b.major_group=f.major_group AND b.year=f.base_year
JOIN research.subject_background c
  ON c.major_group=f.major_group AND c.metric='bvi' AND c.year=a.year
JOIN research.subject_background c0
  ON c0.major_group=f.major_group AND c0.metric='bvi' AND c0.year=f.base_year
WHERE f.metric='bvi' AND f.side='linked' AND b.bvi>=t.min_bvi
GROUP BY f.university, f.scope, f.base_year, t.min_bvi, a.year;

CREATE OR REPLACE VIEW research.bvi_threshold_changes AS
SELECT a.university, a.scope, a.base_year, a.year AS end_year, a.min_bvi,
       a.groups_used, b.bvi AS bvi0, a.bvi AS bvi1,
       b.admitted AS n0, a.admitted AS n1,
       100*b.bvi/b.admitted AS share0, 100*a.bvi/a.admitted AS share1,
       100*((a.bvi/a.admitted-b.bvi/b.admitted)
        -(a.reference_bvi/a.reference_admitted-b.reference_bvi/b.reference_admitted))
          AS share_gap_pp
FROM research.bvi_threshold_annual a
JOIN research.bvi_threshold_annual b
 ON b.university=a.university AND b.scope=a.scope AND b.base_year=a.base_year
 AND b.min_bvi=a.min_bvi AND b.year=a.base_year
WHERE a.year>a.base_year;

SELECT scope, metric, base_year, COUNT(*) AS registered,
       COUNT(*) FILTER (WHERE complete_history) AS complete_history,
       COUNT(*) FILTER (WHERE status='included') AS final_groups,
       COUNT(DISTINCT university) FILTER (WHERE status='included') AS final_universities
FROM research.selection_flow GROUP BY scope,metric,base_year ORDER BY scope,metric,base_year;
SELECT * FROM research.selection_flow WHERE status<>'included'
ORDER BY scope, metric, base_year, university, major_group;
