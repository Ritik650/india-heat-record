-- Q6: how does India compare? Warming rate per station for every country, read from the monthly rollup.
-- The window is 1982-2021 because the Parquet stops in September 2022. Every country gets the same rule:
-- a month qualifies with 24 days of both readings, and a station needs 180 such months, starting by 1990,
-- reaching 2015, with at least 24 in each of 1982-94, 1995-2009 and 2010-21.
-- A window function and in-order aggregation took this from 7.8 s to about 2 s with the same answer: a join
-- against the usual month runs the months step twice, and the rollup is already sorted by these keys.
WITH months AS
(
    SELECT
        station_id,
        year,
        month,
        (sum(sum_tmax) / sum(tmax_days) + sum(sum_tmin) / sum(tmin_days)) / 20 AS mean_c
    FROM heat.station_month
    WHERE year BETWEEN 1982 AND 2021
    GROUP BY station_id, year, month
    HAVING sum(tmax_days) >= 24 AND sum(tmin_days) >= 24
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
SETTINGS optimize_aggregation_in_order = 1;
