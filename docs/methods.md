# Methods

Each step is one SQL file or one Python module, and `pipeline/run_all.py` runs them in order. This page explains the decisions, and [plan_corrections.md](plan_corrections.md) explains why they differ from the original plan.

## Data

- **`heat.noaa`** holds ClickHouse's Parquet copy of GHCN-Daily, loaded whole. The row count is checked against the file's footer.
- **`heat.india_raw`** holds NOAA's own per-station files for the 211 Indian stations that ever reported temperature. A missing reading is absent there, and NOAA's flags are kept. It settles what the zeros mean, supplies the source flags, and extends the series after the Parquet ends.
- **`heat.india_days`** is the analysis base for Indian temperature. It takes the Parquet to 7 September 2022, then NOAA's raw files through 31 December 2024, using only readings that passed NOAA's checks and came from source S. Zeros become NULL. In the period both cover, 99.92% of 1.09M Parquet maximums are identical to the raw files.

## Completeness

| Unit | It counts when |
|---|---|
| Hot season, March-June | At least 98 of 122 days have a maximum |
| Month | At least 24 days have both a maximum and a minimum |
| First half of a year, January-June | At least 145 days have a maximum |
| Monsoon season, June-September, 1901-1970 | At least 98 of 122 days reported, on a rain-only record |

Heat counts are scaled to a full 122-day season, so a station with some missing days is not undercounted relative to its own better years.

## Heatwave days

IMD's rule, from its own [definition](https://internal.imd.gov.in/section/nhac/dynamic/Definition.pdf), is the SQL function `imd_heat_level`. Temperatures are in tenths of a degree.

| Station type | Floor | Heatwave | Severe |
|---|---|---|---|
| Plains | 40 C | 4.5 to 6.4 C above normal, or 45 C outright | More than 6.4 C above normal, or 47 C outright |
| Hills, 1,000 m and above | 30 C | 4.5 to 6.4 C above normal | More than 6.4 C above normal |
| Coast, within 50 km | 37 C | 4.5 C or more above normal | IMD defines none |

IMD gives no numeric boundary for hills or coast, so those two cut-offs are this project's assumptions, and both are tested. IMD's warm night, `imd_warm_night`, counts only on days reaching 40 C, by how far the minimum sits above its normal.

**Normals** are per station and calendar day, from 1991-2020, averaged over the 15 days centred on each day, because one calendar day has only about 25 readings. A station needs 15 complete hot seasons in the window. Calendar days use a leap-year numbering, so 1 March is always day 61.

**What this does not reproduce.** IMD declares a heatwave when two stations in a sub-division meet the rule on two consecutive days. This project counts station-days, because it has no sub-division mapping, and tests the two-day condition separately. So the counts here cannot be compared with IMD's national totals.

## Repeated readings

A day is a repeat if its maximum equals the previous calendar day's, to the tenth. The natural level is about 4% of days, and minimums stay there throughout, at every station.

**Grouping stations.** Each station's repeat share is measured in fixed windows, and `pipeline/repeat_groups.py` sorts it by rule:

| Group | Rule |
|---|---|
| Stepped at 2011 | Share rises by 10 points or more between 2001-10 and 2011-15 |
| Stepped around 1990 | Already at 15% or more in 2001-10 |
| Never affected | Below 12% in every window from 1982 to 2019 |
| Other | Anything else, one station |
| Too little data | Lacks 200 days in 2001-10 or 2011-15 |

The rule rests on a clean split: no station rises by 5 to 15 points. Results for the never-affected group do not change between ceilings of 10% and 20%.

**What points to reporting, not weather.** The share jumps within a month, from 14% to 31% in December 2010, and falls back by March 2016. The groups follow regional lines. Minimums at the same stations do not move. Repeated maximums sit on local peaks about 6 times as often as on local troughs, against about 1.3 at clean stations and about 1.2 for minimums. A window that catches the previous day's peak would produce exactly that. NOAA says this source is derived from hourly reports and "may differ significantly" from true daily data. No document found so far describes the change, so the cause is inferred.

**A test that failed.** The first hypothesis was a peak carried strictly forward in time, which predicted that the reading after a repeated pair would be lower more often than the reading before it. The two rates match, at 61.2% and 61.5% in 2011-24. A rolling maximum is symmetric, and fits that result. The failed prediction is what prompted the station-level look.

**Three estimates of the heatwave trend.** Results are reported as recorded, with every repeat removed, and at never-affected stations only. Removing every repeat over-corrects, because it also removes genuine hot days and natural repeats, so it is a low estimate. As recorded is a high one. The never-affected stations avoid the problem, but they are few and mostly in the centre and east, so they cannot stand in for the south or north-west.

**Effect on mean temperature.** A copied peak lifts only the maximum, so the day-night gap is compared between groups, which removes most regional weather. From 2006-10 to 2011-15 the gap at stations that jumped widens by about 0.3 C more than at clean stations.

## Comparing periods

Stations are compared with themselves. The heatwave panel needs normals and at least 3 complete hot seasons in each of 1982-89, the 1990s, the 2000s and the 2010s. Each station's seasons are averaged within a period, then stations are averaged, so a station with more seasons does not count for more. 1973-1981 is left out because every value is a whole degree. 2020-24 is reported but not used for the headline, because few stations have complete seasons.

## Warming rates

Each month is compared with that station's own usual month, which removes the seasons, and a straight line is fitted through all qualifying months. A station needs 180 such months, starting by 1990, reaching 2015, with at least 24 in each of three eras. Whole-year rules left India with no stations, because minimum temperatures are sparse before 2000.

A station's interval is widened for month-to-month correlation. Stations whose day and night rates differ by 0.5 C a decade or more are marked as suspect, since this usually means a change of site or instrument, which GHCN-Daily does not adjust for.

**Q6** applies the same rule to every country, over 1982-2021 because the Parquet stops in 2022, and ranks countries with at least 5 qualifying stations by their median station. Country codes are NOAA's FIPS codes. A real reading of exactly 0.0 C is lost to the zero rule in cold countries. It removes the same small share across years, so it should barely affect slopes, but this was not measured.

## First 40 C

A year counts if January-June is at least 80% complete and at least 6 of the 7 days before the crossing have readings, because a gap can hide the real first crossing. A station needs 15 usable years, starting by 1995, reaching 2015, and must reach 40 C in at least 80% of its complete years.

## Monsoon rain

The main test uses rain-only records from 1901 to 1970, at stations with at least 56 of 70 complete seasons. A second covers 2006-2024, within one source with steady reporting, at stations with at least 15 of 19 seasons. A rainy day is 2.5 mm or more, as IMD defines it. A heavy day is 100 mm or more, as the plan asked. IMD's own "heavy" category starts lower, at 64.5 mm.

Rain after 1972 is not compared with rain before it. Coverage collapses, and the same stations appear to lose over a third of their rain and later recover. Since a zero on a temperature station can mean "not reported", post-1972 rain would need a station-by-station audit before it could carry a trend.

## Uncertainty

Intervals resample stations 10,000 times with a fixed seed, because the question is whether a pattern holds across stations. Stations are not independent, so these intervals are if anything too narrow. Sign tests treat each station as a coin flip, with the same caveat.

## Checks

| Check | What it guards against |
|---|---|
| Row count against the Parquet footer | A partial load |
| Rollups against a direct scan, and Q6 from rollup against Q6 from raw | Materialized views drifting from the data |
| IMD's rule at every boundary | An off-by-a-tenth error, which no reconciliation would show |
| IMD's rule implemented again in Python, compared on every station-day | A shared misreading of the SQL |
| Readings counted on both sides of the normals join | An inner join quietly dropping rows |
| Churu's documented records against the data | The source not matching reality |
| IMD's own 103-station count against this project's range | The answer being wrong in direction or scale |
| Never-affected stations against the full panel | An artefact driving the conclusion |
| README and brief against `findings.json` | Reports drifting from results |

## Benchmark

Each query runs once cold, after clearing the OS page cache and ClickHouse's mark and query condition caches, then three times warm, reporting the median. An early version of this harness left the condition cache in place, which made a filter that misses the sort key look nearly free. Both engines get 4 threads and 3 GB, inside WSL on a 16 GB laptop, with DuckDB reading the same Parquet from the Linux filesystem. Times include starting each engine's command-line client, which matters only for the fastest queries. Run-to-run variation on the longest scans was about 15%, so small gaps are not meaningful.
