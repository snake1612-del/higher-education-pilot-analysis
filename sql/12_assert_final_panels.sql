-- Ожидания относятся к опубликованному исследованию, а не к любым данным.
-- Новая выборка требует явного пересмотра ожидаемого состава, а не отключения ошибок.
DO $$
DECLARE metric_name text; expected_groups integer; actual_groups integer;
        actual_universities integer;
BEGIN
  FOR metric_name, expected_groups IN VALUES ('score',16), ('bvi',8) LOOP
    SELECT COUNT(*), COUNT(DISTINCT university)
      INTO actual_groups,actual_universities
    FROM research.final_panel_members
    WHERE scope='cohort2023' AND side='linked' AND metric=metric_name AND base_year=2022;
    IF actual_groups<>expected_groups OR actual_universities<>4 THEN
      RAISE EXCEPTION 'Панель %: % групп, % вузов; ожидалось % и 4. Проверьте selection_flow',
        metric_name,actual_groups,actual_universities,expected_groups;
    END IF;
  END LOOP;
  IF (SELECT COUNT(*) FROM research.comparison_changes
      WHERE scope='whole' AND metric='score' AND base_year=2022 AND end_year=2025)<>6 THEN
    RAISE EXCEPTION 'Панель баллов не содержит шесть вузов';
  END IF;
END $$;
