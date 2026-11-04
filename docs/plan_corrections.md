# Where the data disagreed with the plan

The project began from a written plan, and each of its claims about the data was checked before use. Where the plan and the data disagree, the data won, and this page records the change. The plan's questions, method and deliverables otherwise stand.

| # | The plan said | What was found | What changed |
|---|---|---|---|
| 1 | 2,679,264,563 rows, one per station per day | The Parquet's footer says 1,074,089,837 rows. The larger number counts individual measurements before they were pivoted into rows | The project says 1.07B station-days, from 2.68B measurements |
| 2 | The Parquet is about 6.4 GB | It is 2,284,954,281 bytes, by the server's `Content-Length`. ClickHouse's documentation also says 6.4 GB | Disk was planned around the real size |
| 3 | The data covers 1900-2022 | It ends on 7 September 2022, and Indian temperature effectively starts in 1973 | Heat questions cover 1982-2024. 2022 is completed from NOAA's raw files |
| 4 | Use 1961-1990 as "normal" | No Indian station has 20 complete years in that window, and at most 3 have 15. It cannot be built | Normals use 1991-2020, which IMD now uses too. 1981-2010 is a sensitivity test |
| 5 | Check whether temperature is in tenths | Confirmed: tenths of a degree C, and rain in tenths of a mm | Applied as planned |
| 6 | Heatwave: 40 C and 4.5 C above normal; severe from 6.5 C | That is IMD's rule for the plains, in part. IMD also has 45 C and 47 C triggers, a 30 C floor for hills and a 37 C floor for the coast, and defines warm nights only on days reaching 40 C | The full rule is implemented and tested. The plan's simpler version is a sensitivity test |
| 7 | A rollup with `days_obs = count()` and `sum(tempMax)` | Every column is non-nullable, so a missing reading is stored as 0. `tempMax = 0` appears 60.2M times in India, against once at +0.1 C. Dividing by `count()` would drag every mean toward zero | The rollup counts readings separately from rows |
| 8 | Filter with `substring(station_id, 1, 2) = 'IN'` | Correct rows, but it cannot use the table's sort key, so a first run reads all 1.07B rows where `LIKE 'IN%'` reads 62M, and takes more than twice as long. Repeat runs nearly match, because ClickHouse's query condition cache remembers which parts matched | `LIKE 'IN%'` is used, and both are in the benchmark |
| 9 | Check for negative rainfall | The source has no negative rain, and the column cannot hold any. The real problem is the opposite: half the zeros on temperature stations were never reported | The check stays and passes. Rain results use only complete reports |
| 10 | Values outside -10 to 52 C are implausible | That bound suits the plains. Readings below -10 C are real in the hills | Only non-hill stations are flagged, and none fail |
| 11 | Rollups by station and year | A station needs every year nearly complete, and minimum temperatures are too sparse before 2000 for that. India had 0 stations under a full-year rule | A monthly rollup was added, and trends use qualifying months, for every country alike |
| 12 | Use a station-year bar of about 80% | The heat questions depend on March-June, so the bar applies to that season. Rates are scaled to a full season | 98 of 122 days in the season |
| 13 | One chart per question | Rain needed a second chart to show why rain after 1972 cannot be compared with rain before it | Added |

## Findings the plan did not anticipate

| Finding | Evidence | Treatment |
|---|---|---|
| Repeated readings | A maximum identical to the previous day's normally covers about 4% of days. At 23 stations it jumps to about 31% from December 2010 to early 2016, and 22 of them are in the area of IMD's Chennai centre. Another 14 in the north-west step up around 1990. Minimums never move | Stations are grouped by when it reached them. Heat results are reported as recorded, with repeats removed, and at stations never affected |
| Rounding to whole degrees | 100% of maximums from 1973 to 1981 are whole degrees, against 15.6% afterwards | Threshold questions start in 1982 |
| Rain reporting break | The same 70 stations seem to lose over a third of their monsoon rain between 1901-72 and 1982-98, then recover | Rain after 1972 is not compared with rain before it |
| Source break in 2025 | NOAA moved Indian stations to a different source, and values shift | Temperature stops at December 2024 |
| Warm-weather record is one source | Every Indian maximum through 2024 comes from NOAA's source S, which its readme says to use with caution | Stated as a limitation. Two of IMD's documented records were checked and match |

## Citations

The plan cited five sources. Their claims are correct but needed framing, as [sources.md](sources.md) sets out:

- **536 heatwave days** adds up meteorological sub-divisions, and covers summer only. One day across five sub-divisions counts as five.
- **143 deaths and 41,789 cases** is a count to 20 June 2024, not a final total.
- **India Weekly** could not be found. The figures were traced to Business Today, citing NCDC surveillance.
- **IMD has since added percentile thresholds**, according to its chief in 2026. The older rule is used here because it can be applied to all years alike.
