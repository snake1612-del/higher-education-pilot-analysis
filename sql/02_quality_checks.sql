-- Ошибки ключей не агрегируем молча: это могло бы удвоить приём.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM research.mkp_annual) THEN
        RAISE EXCEPTION 'Сначала загрузите исходный CSV';
    END IF;
    IF EXISTS (SELECT FROM research.mkp_annual
               WHERE university IS NULL OR major_group IS NULL) THEN
        RAISE EXCEPTION 'Пустое название вуза или группы';
    END IF;
    IF EXISTS (SELECT FROM research.mkp_annual
               GROUP BY university, major_group, year HAVING COUNT(*) > 1) THEN
        RAISE EXCEPTION 'Неуникальный ключ вуз / группа / год';
    END IF;
    IF EXISTS (SELECT FROM research.mkp_annual
               WHERE admitted < 0 OR bvi < 0 OR bvi > admitted
                  OR admitted <> TRUNC(admitted) OR bvi <> TRUNC(bvi)
                  OR ege < 0 OR ege > 100) THEN
        RAISE EXCEPTION 'Проверьте диапазоны и целочисленность численностей';
    END IF;
    IF EXISTS (SELECT FROM research.pilot_universities p
               WHERE NOT EXISTS (SELECT FROM research.mkp_annual a
                                 WHERE a.university = p.university)) THEN
        RAISE EXCEPTION 'Не все первоначальные участники найдены по точному имени';
    END IF;
    IF EXISTS (SELECT FROM research.scope_links l
               WHERE NOT EXISTS (SELECT FROM research.mkp_annual a
                                 WHERE a.university = l.university
                                   AND a.major_group = l.major_group)) THEN
        RAISE EXCEPTION 'Связь реестра не найдена в МКП';
    END IF;
    IF EXISTS (
        SELECT FROM research.pilot_universities p
        CROSS JOIN (VALUES ('cohort2023'), ('confirmed_eventual')) s(scope)
        WHERE p.in_primary_cohort
          AND NOT EXISTS (SELECT FROM research.scope_links l
                          WHERE l.university = p.university AND l.scope = s.scope)
    ) THEN
        RAISE EXCEPTION 'Для основной когорты не заполнен проверенный реестр связей';
    END IF;
END;
$$;

SELECT year, COUNT(*) AS university_group_rows,
       COUNT(DISTINCT university) AS universities,
       COUNT(*) FILTER (WHERE admitted IS NULL) AS missing_admitted,
       COUNT(*) FILTER (WHERE ege IS NULL) AS missing_ege,
       COUNT(*) FILTER (WHERE bvi IS NULL) AS missing_bvi
FROM research.mkp_annual
GROUP BY year ORDER BY year;
