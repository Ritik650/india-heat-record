-- Q1: are heatwave days becoming more frequent?
-- One row per station and complete hot season (March-June, at least 98 of 122 days observed).
-- Starts in 1982: every value from 1973 to 1981 is a whole degree, which distorts a 40 C cut-off.
SELECT
    s.station_id AS station_id,
    s.year AS year,
    any(h.station_class) AS station_class,
    any(s.hot_tmax_days) AS observed_days,
    countIf(h.heat_level > 0) AS heatwave_days,
    countIf(h.heat_level = 2) AS severe_days,
    countIf(h.heat_level > 0 AND h.repeat_tmax = 0) AS heatwave_days_no_repeat,
    countIf(h.heat_level = 2 AND h.repeat_tmax = 0) AS severe_days_no_repeat,
    countIf(h.in_spell = 1) AS spell_days,
    countIf(h.heat_level_rounded > 0) AS heatwave_days_rounded,
    countIf(h.repeat_tmax = 1) AS repeat_days,
    countIf(h.heat_level > 0 AND h.repeat_tmax = 1) AS heatwave_days_that_repeat
FROM heat.station_season AS s
INNER JOIN heat.heatwave_days AS h ON s.station_id = h.station_id AND s.year = h.year
WHERE s.hot_ok = 1
  AND s.year BETWEEN 1982 AND 2024
  AND h.month BETWEEN 3 AND 6
GROUP BY s.station_id, s.year
ORDER BY station_id, year;
