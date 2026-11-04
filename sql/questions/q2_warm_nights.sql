-- Q2: warm nights by IMD's definition, per station and complete hot season.
-- IMD counts a warm night only when the day's maximum reached 40 C, so hill and coastal stations rarely qualify.
SELECT
    s.station_id AS station_id,
    s.year AS year,
    any(s.hot_tmax_days) AS observed_days,
    countIf(h.night_level > 0) AS warm_nights,
    countIf(h.night_level = 2) AS very_warm_nights,
    countIf(h.night_level > 0 AND h.repeat_tmin = 0 AND h.repeat_tmax = 0) AS warm_nights_no_repeat
FROM heat.station_season AS s
INNER JOIN heat.heatwave_days AS h ON s.station_id = h.station_id AND s.year = h.year
WHERE s.hot_ok = 1
  AND s.year BETWEEN 1982 AND 2024
  AND h.month BETWEEN 3 AND 6
GROUP BY s.station_id, s.year
ORDER BY station_id, year;
