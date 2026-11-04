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
anomalies AS
(
    SELECT station_id, year, month, mean_c - avg(mean_c) OVER (PARTITION BY station_id, month) AS anomaly
    FROM months
)
SELECT
    station_id,
    substring(station_id, 1, 2) AS country,
    count() AS months_used,
    min(year) AS first_year,
    max(year) AS last_year,
    simpleLinearRegression(year + (month - 0.5) / 12, anomaly).1 * 10 AS rate_per_decade
FROM anomalies
GROUP BY station_id
HAVING months_used >= 180
   AND first_year <= 1990
   AND last_year >= 2015
   AND countIf(year < 1995) >= 24
   AND countIf(year >= 1995 AND year < 2010) >= 24
   AND countIf(year >= 2010) >= 24
ORDER BY country, station_id
FORMAT Null
