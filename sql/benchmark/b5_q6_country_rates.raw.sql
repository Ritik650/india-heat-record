WITH months AS
(
    SELECT
        station_id,
        toYear(date) AS year,
        toMonth(date) AS month,
        (sum(tempMax) / countIf(tempMax != 0) + sum(tempMin) / countIf(tempMin != 0)) / 20 AS mean_c
    FROM heat.noaa
    WHERE date >= '1982-01-01' AND date <= '2021-12-31'
    GROUP BY station_id, year, month
    HAVING countIf(tempMax != 0) >= 24 AND countIf(tempMin != 0) >= 24
),
usual AS
(
    SELECT station_id, month, avg(mean_c) AS mean_usual
    FROM months
    GROUP BY station_id, month
)
SELECT
    m.station_id AS station_id,
    substring(m.station_id, 1, 2) AS country,
    count() AS months_used,
    min(m.year) AS first_year,
    max(m.year) AS last_year,
    simpleLinearRegression(m.year + (m.month - 0.5) / 12, m.mean_c - u.mean_usual).1 * 10 AS rate_per_decade
FROM months AS m
INNER JOIN usual AS u ON m.station_id = u.station_id AND m.month = u.month
GROUP BY m.station_id
HAVING months_used >= 180
   AND first_year <= 1990
   AND last_year >= 2015
   AND countIf(m.year < 1995) >= 24
   AND countIf(m.year >= 1995 AND m.year < 2010) >= 24
   AND countIf(m.year >= 2010) >= 24
ORDER BY country, station_id
FORMAT Null
