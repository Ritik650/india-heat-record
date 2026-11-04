-- Q2 and Q5: how fast are days and nights warming at each station?
-- Each month is compared with that station's own usual month, which removes the seasons, so a trend can
-- be fitted through every qualifying month. Requiring whole years instead left no Indian station at all,
-- because minimum temperatures are sparse before 2000. A month qualifies with 24 days of both readings.
WITH months AS
(
    SELECT
        station_id,
        year,
        month,
        avg(tmax) / 10 AS tmax_c,
        avg(tmin) / 10 AS tmin_c,
        avgIf(tmax, repeat_tmax = 0) / 10 AS tmax_norepeat_c,
        avgIf(tmin, repeat_tmin = 0) / 10 AS tmin_norepeat_c,
        count(tmax) AS tmax_n,
        count(tmin) AS tmin_n
    FROM heat.india_days
    WHERE year BETWEEN 1982 AND 2024
    GROUP BY station_id, year, month
    HAVING tmax_n >= 24 AND tmin_n >= 24
),
usual AS
(
    SELECT
        station_id,
        month,
        avg(tmax_c) AS tmax_usual,
        avg(tmin_c) AS tmin_usual,
        avg(tmax_norepeat_c) AS tmax_norepeat_usual,
        avg(tmin_norepeat_c) AS tmin_norepeat_usual
    FROM months
    GROUP BY station_id, month
)
SELECT
    m.station_id AS station_id,
    m.year AS year,
    m.month AS month,
    m.tmax_c - u.tmax_usual AS tmax_anomaly,
    m.tmin_c - u.tmin_usual AS tmin_anomaly,
    m.tmax_norepeat_c - u.tmax_norepeat_usual AS tmax_anomaly_no_repeat,
    m.tmin_norepeat_c - u.tmin_norepeat_usual AS tmin_anomaly_no_repeat
FROM months AS m
INNER JOIN usual AS u ON m.station_id = u.station_id AND m.month = u.month
ORDER BY station_id, year, month;
