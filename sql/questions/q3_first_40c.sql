-- Q3: is summer starting earlier? First date each year a station reaches 40 C.
-- A gap can hide the real first crossing, so a year counts only if at least 80% of January-June is
-- observed. observed_prior_7 lets the Python step also require readings on the 7 days before the crossing.
-- Years that never reach 40 C stay in the output with days_40c 0, so stations can be required to reach it reliably.
WITH crossings AS
(
    SELECT
        station_id,
        year,
        minIf(date, tmax >= 400) AS first_date,
        countIf(tmax >= 400) AS days_40c
    FROM heat.india_days
    WHERE year BETWEEN 1982 AND 2024
      AND month BETWEEN 1 AND 6
    GROUP BY station_id, year
)
SELECT
    c.station_id AS station_id,
    c.year AS year,
    any(c.days_40c) AS days_40c,
    if(any(c.days_40c) > 0, toDayOfYear(makeDate(2020, toMonth(any(c.first_date)), toDayOfMonth(any(c.first_date)))), 0) AS first_doy,
    countIf(d.tmax IS NOT NULL AND d.date >= c.first_date - 7 AND d.date < c.first_date) AS observed_prior_7
FROM crossings AS c
INNER JOIN heat.station_season AS s ON c.station_id = s.station_id AND c.year = s.year
INNER JOIN heat.india_days AS d ON c.station_id = d.station_id AND c.year = d.year
WHERE s.firsthalf_ok = 1
GROUP BY c.station_id, c.year
ORDER BY station_id, year;
