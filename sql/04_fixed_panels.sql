-- Единый расчётный слой для итоговых сравнений.
-- Каждая метрика имеет собственное правило полноты за все пять лет.
BEGIN;
CREATE MATERIALIZED VIEW IF NOT EXISTS research.stable_group_metric AS
SELECT a.university, a.major_group, m.metric
FROM research.mkp_annual a
CROSS JOIN LATERAL (VALUES
    ('score', a.admitted > 0 AND a.ege IS NOT NULL),
    ('bvi', a.admitted > 0 AND a.bvi IS NOT NULL
            AND a.bvi BETWEEN 0 AND a.admitted),
    ('coverage', a.admitted >= 0)
) m(metric, valid)
GROUP BY a.university, a.major_group, m.metric
HAVING COUNT(*) = 5 AND BOOL_AND(COALESCE(m.valid, false))
WITH NO DATA;
REFRESH MATERIALIZED VIEW research.stable_group_metric;
CREATE UNIQUE INDEX IF NOT EXISTS stable_group_metric_key
    ON research.stable_group_metric (university, major_group, metric);
ANALYZE research.stable_group_metric;

-- Постоянный набор вузов фона внутри каждой группы и метрики.
-- Первоначальная шестёрка полностью исключена из внешнего фона.
CREATE MATERIALIZED VIEW IF NOT EXISTS research.subject_background AS
SELECT s.major_group, s.metric, a.year,
       COUNT(*) AS control_universities,
       SUM(a.admitted) AS admitted,
       SUM(a.admitted * a.ege) AS score_numerator,
       CASE WHEN s.metric = 'bvi' THEN SUM(a.bvi) END AS bvi
FROM research.stable_group_metric s
JOIN research.mkp_annual a USING (university, major_group)
WHERE s.metric IN ('score', 'bvi')
  AND NOT EXISTS (SELECT FROM research.pilot_universities p
                  WHERE p.university = s.university)
GROUP BY s.major_group, s.metric, a.year
WITH NO DATA;
REFRESH MATERIALIZED VIEW research.subject_background;
CREATE UNIQUE INDEX IF NOT EXISTS subject_background_key
    ON research.subject_background (major_group, metric, year);
ANALYZE research.subject_background;

CREATE OR REPLACE VIEW research.group_membership AS
SELECT s.university, s.major_group, s.metric,
       'whole'::text AS scope, 'all'::text AS side
FROM research.stable_group_metric s
JOIN research.pilot_universities p USING (university)
WHERE s.metric IN ('score', 'bvi')
UNION ALL
SELECT s.university, s.major_group, s.metric, scopes.scope,
       CASE WHEN EXISTS (
           SELECT FROM research.scope_links l
           WHERE l.university = s.university AND l.major_group = s.major_group
             AND l.scope = scopes.scope
       ) THEN 'linked' ELSE 'other_observed' END AS side
FROM research.stable_group_metric s
JOIN research.pilot_universities p USING (university)
CROSS JOIN (VALUES ('cohort2023'), ('confirmed_eventual')) scopes(scope)
WHERE s.metric IN ('score', 'bvi')
  AND p.in_primary_cohort
  AND EXISTS (SELECT FROM research.scope_links l
              WHERE l.university = s.university AND l.scope = scopes.scope);

-- Внешние количества масштабируются к структуре фокального вуза в базе.
-- Такие количества — расчётный фон, а не фактические люди одного вуза.
CREATE MATERIALIZED VIEW IF NOT EXISTS research.comparison_annual AS
SELECT g.university, g.scope, g.side, g.metric, base.base_year, a.year,
       COUNT(*) AS groups_used,
       SUM(b.admitted) AS baseline_admitted,
       SUM(a.admitted) AS admitted,
       CASE WHEN g.metric = 'score' THEN
           SUM(a.admitted * a.ege) / SUM(a.admitted) END AS ege_current,
       CASE WHEN g.metric = 'score' THEN
           SUM(b.admitted * a.ege) / SUM(b.admitted) END AS ege_fixed,
       CASE WHEN g.metric = 'bvi' THEN SUM(a.bvi) END AS bvi,
       SUM(b.admitted * c.admitted / c0.admitted) AS reference_scaled_admitted,
       CASE WHEN g.metric = 'score' THEN
           SUM(b.admitted * c.score_numerator / c0.admitted)
           / SUM(b.admitted * c.admitted / c0.admitted) END AS reference_ege_current,
       CASE WHEN g.metric = 'score' THEN
           SUM(b.admitted * c.score_numerator / c.admitted)
           / SUM(b.admitted) END AS reference_ege_fixed,
       CASE WHEN g.metric = 'bvi' THEN
           SUM(b.admitted * c.bvi / c0.admitted) END AS reference_scaled_bvi
FROM research.group_membership g
CROSS JOIN (VALUES (2021), (2022)) base(base_year)
JOIN research.mkp_annual a USING (university, major_group)
JOIN research.mkp_annual b
  ON b.university = g.university AND b.major_group = g.major_group
 AND b.year = base.base_year
JOIN research.subject_background c
  ON c.major_group = g.major_group AND c.metric = g.metric AND c.year = a.year
JOIN research.subject_background c0
  ON c0.major_group = g.major_group AND c0.metric = g.metric
 AND c0.year = base.base_year
GROUP BY g.university, g.scope, g.side, g.metric, base.base_year, a.year
WITH NO DATA;
REFRESH MATERIALIZED VIEW research.comparison_annual;
CREATE UNIQUE INDEX IF NOT EXISTS comparison_annual_key
    ON research.comparison_annual (university, scope, side, metric, base_year, year);
ANALYZE research.comparison_annual;

CREATE OR REPLACE VIEW research.comparison_changes AS
SELECT a.university, a.scope, a.side, a.metric, a.base_year, a.year AS end_year,
       a.groups_used, b.admitted AS n0, a.admitted AS n1,
       a.admitted - b.admitted AS delta_n,
       100 * (a.admitted / b.admitted - 1) AS growth_pct,
       100 * (a.reference_scaled_admitted / b.reference_scaled_admitted - 1)
           AS reference_growth_pct,
       100 * (a.admitted / b.admitted
              - a.reference_scaled_admitted / b.reference_scaled_admitted)
           AS growth_gap_pp,
       a.ege_fixed - b.ege_fixed AS ege_fixed_change,
       a.reference_ege_fixed - b.reference_ege_fixed AS reference_ege_fixed_change,
       (a.ege_fixed - b.ege_fixed)
         - (a.reference_ege_fixed - b.reference_ege_fixed) AS ege_fixed_gap,
       (a.ege_current - b.ege_current)
         - (a.reference_ege_current - b.reference_ege_current) AS ege_current_gap,
       b.bvi AS bvi0, a.bvi AS bvi1,
       100 * b.bvi / b.admitted AS bvi_share0,
       100 * a.bvi / a.admitted AS bvi_share1,
       100 * (a.bvi / a.admitted - b.bvi / b.admitted) AS bvi_share_change_pp,
       100 * ((a.bvi / a.admitted - b.bvi / b.admitted)
         - (a.reference_scaled_bvi / a.reference_scaled_admitted
            - b.reference_scaled_bvi / b.reference_scaled_admitted)) AS bvi_share_gap_pp
FROM research.comparison_annual a
JOIN research.comparison_annual b
  ON b.university = a.university AND b.scope = a.scope AND b.side = a.side
 AND b.metric = a.metric AND b.base_year = a.base_year AND b.year = a.base_year
WHERE a.year > a.base_year;
COMMIT;
