-- Raw table and rollups. Run before loading: a materialized view sees only rows inserted after it exists.
-- Codecs were chosen by loading the same 30M rows three ways: default LZ4 took 3.55 bytes a row,
-- ZSTD 1.67, and these per-column codecs 1.12. Delta encoding gave temperatures nothing, so they use plain ZSTD.
CREATE DATABASE IF NOT EXISTS heat;

-- One row per station per day. Every column is non-nullable in the source Parquet, so a reading
-- that was never taken is stored as 0. Queries must treat 0 in tempMax and tempMin as missing.
CREATE TABLE IF NOT EXISTS heat.noaa
(
    station_id       LowCardinality(String) CODEC(ZSTD(1)),
    date             Date32 CODEC(DoubleDelta, ZSTD(1)),
    tempAvg          Int32  COMMENT 'tenths of a degree C, 0 when missing' CODEC(ZSTD(1)),
    tempMax          Int32  COMMENT 'tenths of a degree C, 0 when missing' CODEC(ZSTD(1)),
    tempMin          Int32  COMMENT 'tenths of a degree C, 0 when missing' CODEC(ZSTD(1)),
    precipitation    UInt32 COMMENT 'tenths of a mm, 0 when dry or missing' CODEC(T64, ZSTD(1)),
    snowfall         UInt32 COMMENT 'mm' CODEC(T64, ZSTD(1)),
    snowDepth        UInt32 COMMENT 'mm' CODEC(T64, ZSTD(1)),
    percentDailySun  UInt8 CODEC(ZSTD(1)),
    averageWindSpeed UInt32 COMMENT 'tenths of a metre per second' CODEC(T64, ZSTD(1)),
    maxWindSpeed     UInt32 COMMENT 'tenths of a metre per second' CODEC(T64, ZSTD(1)),
    weatherType      Enum8('Normal' = 0, 'Fog' = 1, 'Heavy Fog' = 2, 'Thunder' = 3, 'Small Hail' = 4, 'Hail' = 5,
                           'Glaze' = 6, 'Dust/Ash' = 7, 'Smoke/Haze' = 8, 'Blowing/Drifting Snow' = 9, 'Tornado' = 10,
                           'High Winds' = 11, 'Blowing Spray' = 12, 'Mist' = 13, 'Drizzle' = 14, 'Freezing Drizzle' = 15,
                           'Rain' = 16, 'Freezing Rain' = 17, 'Snow' = 18, 'Unknown Precipitation' = 19,
                           'Ground Fog' = 21, 'Freezing Fog' = 22) CODEC(ZSTD(1)),
    location         Point CODEC(ZSTD(1)),
    elevation        Float32 COMMENT 'metres, -999.9 when missing' CODEC(ZSTD(1)),
    name             LowCardinality(String) CODEC(ZSTD(1))
)
ENGINE = MergeTree
PARTITION BY intDiv(toYear(date), 10)
ORDER BY (station_id, date);

-- SummingMergeTree adds rows up in the background, so reads must still wrap every column in sum().
CREATE TABLE IF NOT EXISTS heat.station_year
(
    station_id      LowCardinality(String),
    year            UInt16,
    days_obs        UInt32,
    tmax_days       UInt32,
    tmin_days       UInt32,
    days_40c        UInt32,
    rainy_days      UInt32,
    heavy_rain_days UInt32,
    sum_tmax        Int64,
    sum_tmin        Int64,
    sum_precip      UInt64
)
ENGINE = SummingMergeTree
ORDER BY (station_id, year);

CREATE MATERIALIZED VIEW IF NOT EXISTS heat.mv_station_year TO heat.station_year AS
SELECT
    station_id,
    toUInt16(toYear(date))          AS year,
    toUInt32(count())               AS days_obs,
    toUInt32(countIf(tempMax != 0)) AS tmax_days,
    toUInt32(countIf(tempMin != 0)) AS tmin_days,
    toUInt32(countIf(tempMax >= 400)) AS days_40c,
    toUInt32(countIf(precipitation >= 25))   AS rainy_days,
    toUInt32(countIf(precipitation >= 1000)) AS heavy_rain_days,
    toInt64(sum(tempMax))           AS sum_tmax,
    toInt64(sum(tempMin))           AS sum_tmin,
    toUInt64(sum(precipitation))    AS sum_precip
FROM heat.noaa
GROUP BY station_id, year;

-- Monthly grain. A yearly mean shifts when a station's missing days fall in one season, so
-- warming rates are built from months, each compared with that station's own usual month.
CREATE TABLE IF NOT EXISTS heat.station_month
(
    station_id LowCardinality(String),
    year       UInt16,
    month      UInt8,
    tmax_days  UInt32,
    tmin_days  UInt32,
    sum_tmax   Int64,
    sum_tmin   Int64
)
ENGINE = SummingMergeTree
ORDER BY (station_id, year, month);

CREATE MATERIALIZED VIEW IF NOT EXISTS heat.mv_station_month TO heat.station_month AS
SELECT
    station_id,
    toUInt16(toYear(date))          AS year,
    toUInt8(toMonth(date))          AS month,
    toUInt32(countIf(tempMax != 0)) AS tmax_days,
    toUInt32(countIf(tempMin != 0)) AS tmin_days,
    toInt64(sum(tempMax))           AS sum_tmax,
    toInt64(sum(tempMin))           AS sum_tmin
FROM heat.noaa
GROUP BY station_id, year, month;
