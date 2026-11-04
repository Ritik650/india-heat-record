# Data dictionary

Temperatures are in tenths of a degree C and rain in tenths of a mm in `heat.noaa`, `heat.india_raw` and `heat.india_days`. Everything in `data/mart` is in degrees C and mm unless the column says otherwise.

## ClickHouse tables

| Table | One row per | Rows | Notes |
|---|---|---|---|
| `heat.noaa` | Station-day | 1,074,089,837 | Raw table. A missing reading is 0, not NULL |
| `heat.station_year` | Station-year | 3,267,574 | Rollup kept current by `mv_station_year`. Read every column through `sum()` |
| `heat.station_month` | Station-month | 15,335,837 | Rollup kept current by `mv_station_month`. Read every column through `sum()` |
| `heat.stations`, `heat.countries` | Station, country | 133,041, 219 | NOAA's metadata files |
| `heat.station_class` | Indian station | 3,807 | Plains, coastal or hills, coast distance, state |
| `heat.india_raw` | Station-day-element | 6,681,570 | NOAA's readings with flags, for temperature stations |
| `heat.india_days` | Station-day | 1,437,122 | Analysis base. Missing is NULL. Flags repeated values |
| `heat.station_season` | Station-year | 4,999 | Days observed, and whether the year or season counts |
| `heat.station_normals` | Station, day of year | 21,228 | 1991-2020 normals for 58 stations |
| `heat.heatwave_days` | Station-day | 823,654 | IMD heat and warm-night levels for stations with normals |
| `heat.passing_stations` | Station | 175 | Which stations pass which bar |
| `heat.coverage_by_year` | Year | 120 | Indian stations reporting |
| `heat.dash_*` | Various | Small | Result tables for Grafana |

## Key columns in `heat.heatwave_days`

| Column | Meaning |
|---|---|
| `tmax_departure`, `tmin_departure` | Reading minus the station's normal for that day, in tenths |
| `heat_level` | 0 none, 1 heatwave, 2 severe, by IMD's rule |
| `night_level` | 0 none, 1 warm night, 2 very warm night, by IMD's rule |
| `heat_level_rounded` | `heat_level` with the maximum rounded to a whole degree, to test the 1973-81 rounding |
| `repeat_tmax`, `repeat_tmin` | 1 if identical to the previous calendar day |
| `in_spell` | 1 if part of a run of 2 or more heatwave days |
| `origin` | `parquet`, or `noaa_raw` after 7 September 2022 |

## Files in `data/mart`

| File | Contents |
|---|---|
| `findings.json` | Every figure used in the brief and README |
| `passing_stations.csv` | Stations with temperature data and which bars they pass |
| `coverage_by_year.csv` | Indian stations reporting each year |
| `station_season.csv` | Completeness for each Indian station-year |
| `q1_heatwave_seasons.csv`, `q1_station_periods.csv` | Heatwave days per station-season, and averaged per period |
| `repeats_by_year.csv` | Share of hot-season days repeating the previous maximum, at stations with normals |
| `q2_monthly_anomalies.csv`, `q2_warm_nights.csv` | Monthly anomalies per station, and warm nights per season |
| `station_rates.csv` | Warming rate per station: days, nights, both, interval, suspect flag |
| `q3_first_40c.csv`, `q3_station_trends.csv`, `q3_yearly.csv` | First 40 C by station-year, trend per station, and median by year |
| `q4_monsoon_seasons.csv`, `q4_gauge_decades.csv` | Monsoon totals per station-season, and per decade at complete gauges |
| `q4_rain_sources.csv`, `q4_water_balance.csv` | Rain by NOAA's source flag, and the same stations by era |
| `q6_country_rates_rollup.csv`, `q6_country_summary.csv` | Warming rate per station worldwide, and median per country |
| `q7_repeat_years.csv`, `q7_repeat_months.csv`, `q7_repeat_pairs.csv` | Repeated readings per station by year and by month, and how many sit on local peaks or troughs |
| `station_repeat_groups.csv`, `repeat_groups_by_state.csv` | Which group each station falls in, and the groups by state |
| `repeat_years_by_group.csv`, `repeat_months_jumped.csv`, `repeat_peak_ratios.csv` | Repeat share by group and year, month by month for the 2011 group, and peaks against troughs |
| `q1_group_periods.csv` | Heatwave days per period for each repeat group |
| `station_names.csv` | Display details for Indian temperature stations |
| `sensitivity.csv` | Heatwave result under each alternative assumption |
| `benchmark.csv`, `benchmark_reads.csv`, `storage.csv` | Query times, rows read by each query, and sizes on disk |

## Issue log, `docs/issue_log.csv`

| Column | Meaning |
|---|---|
| `check` | Check ID, matching `sql/dq_checks.sql` |
| `station` | Station, or blank for a check on the whole dataset |
| `count` | Rows or days affected |
| `severity` | High, medium, low or info |
| `description` | What was checked |
| `action_taken` | What was done about it |
| `detail` | The evidence |

A check with a count of 0 and the detail `passed` ran and found nothing.
