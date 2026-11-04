-- Do repeated readings sit on local peaks? A pair of equal readings is a local peak if the days on either side are
-- both lower, and a local trough if both are higher. Natural pairs fall about evenly. If a day's peak is being copied
-- into the next day's value, pairs of maximums pile up on peaks. Minimums are the control, because the same stations
-- report them on the same dates. Only pairs with readings on all four consecutive days count.
WITH maximums AS
(
    SELECT
        station_id, date, year, tmax AS value, repeat_tmax AS is_repeat,
        lagInFrame(toNullable(date), 2) OVER w AS date_before,
        lagInFrame(tmax, 2) OVER w AS value_before,
        leadInFrame(toNullable(date), 1) OVER w AS date_after,
        leadInFrame(tmax, 1) OVER w AS value_after
    FROM heat.india_days
    WHERE tmax IS NOT NULL
    WINDOW w AS (PARTITION BY station_id ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
),
minimums AS
(
    SELECT
        station_id, date, year, tmin AS value, repeat_tmin AS is_repeat,
        lagInFrame(toNullable(date), 2) OVER w AS date_before,
        lagInFrame(tmin, 2) OVER w AS value_before,
        leadInFrame(toNullable(date), 1) OVER w AS date_after,
        leadInFrame(tmin, 1) OVER w AS value_after
    FROM heat.india_days
    WHERE tmin IS NOT NULL
    WINDOW w AS (PARTITION BY station_id ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
)
SELECT
    station_id, year, 'maximum' AS reading, count() AS pairs,
    countIf(value_before < value AND value_after < value) AS local_peaks,
    countIf(value_before > value AND value_after > value) AS local_troughs
FROM maximums
WHERE is_repeat = 1 AND year BETWEEN 1982 AND 2024 AND date_before = date - 2 AND date_after = date + 1
GROUP BY station_id, year
UNION ALL
SELECT
    station_id, year, 'minimum' AS reading, count() AS pairs,
    countIf(value_before < value AND value_after < value) AS local_peaks,
    countIf(value_before > value AND value_after > value) AS local_troughs
FROM minimums
WHERE is_repeat = 1 AND year BETWEEN 1982 AND 2024 AND date_before = date - 2 AND date_after = date + 1
GROUP BY station_id, year
ORDER BY station_id, year, reading;
