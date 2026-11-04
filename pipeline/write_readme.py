"""Write README.md and the private notes from the results, so their numbers cannot drift from the analysis."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import MART, ROOT  # noqa: E402

REPOSITORY = "https://github.com/Ritik650/india-heat-record"
SITE = "https://ritik650.github.io/india-heat-record/"


def read_csv(name: str) -> list[dict]:
    path = MART / name
    return list(csv.DictReader(open(path, encoding="utf8"))) if path.exists() else []


def seconds(rows: list[dict], question: str, engine: str, run: str = "median_warm") -> str:
    for row in rows:
        if row["question"] == question and row["engine"] == engine and row["run"] == run:
            value = float(row["seconds"])
            return f"{value:.2f}" if value < 10 else f"{value:.1f}"
    return ""


def benchmark_table(rows: list[dict]) -> str:
    lines = ["| Question | ClickHouse raw | ClickHouse rollup | DuckDB on Parquet |", "|---|---:|---:|---:|"]
    seen = []
    for row in rows:
        if row["question"] not in seen:
            seen.append(row["question"])
    for question in seen:
        lines.append(f"| {question} | {seconds(rows, question, 'clickhouse_raw')} | {seconds(rows, question, 'clickhouse_rollup')} | {seconds(rows, question, 'duckdb_parquet')} |")
    return "\n".join(lines)


def sensitivity_table(rows: list[dict]) -> str:
    lines = ["| If this changes | Stations | As recorded | Repeats removed |", "|---|---:|---:|---:|"]
    for row in rows:
        lines.append(f"| {row['scenario']} | {row['stations']} | +{row['change_recorded_pct']}% | +{row['change_no_repeat_pct']}% |")
    return "\n".join(lines)


def readme(f: dict, bench: list[dict], scenarios: list[dict], storage: list[dict]) -> str:
    q1, q2, q3, q4, q5, q6, dq, scale, r = f["q1_heatwave_days"], f["q2_days_and_nights"], f["q3_first_40c"], f["q4_monsoon"], f["q5_fastest_stations"], f["q6_countries"], f["quality"], f["scale"], f["repeats"]
    recorded, clean = q1["recorded"], q1["without_repeats"]
    clean_group, clean_q2 = q1["by_repeat_group"]["clean"], q2["by_repeat_group"]["clean"]
    sizes = {row["table"]: row for row in storage}
    noaa_gb = int(sizes["noaa"]["bytes_on_disk"]) / 1e9
    raw_gb = int(sizes["noaa"]["uncompressed_bytes"]) / 1e9
    return f"""# India's Heat Record

How India's heat changed, station by station, measured in ClickHouse on **{scale['rows'] / 1e9:.2f} billion station-days** of NOAA weather records.

[![tests]({REPOSITORY}/actions/workflows/tests.yml/badge.svg)]({REPOSITORY}/actions/workflows/tests.yml)

**[Open the live site]({SITE})** | [Read the two-page brief](outputs/india_heat_record_brief.pdf) | [Where the data disagreed with the plan](docs/plan_corrections.md)

IMD confirmed 2024 as India's warmest year since 1901, and heatwave counts make headlines every summer. This project tests the common claims on the public station record, and checks that record before trusting it.

## What it found

Heatwave days did rise, by about a third to a half, in line with IMD's own count. But this public record carries an undocumented reporting artefact that switches on region by region, and it took station-by-station checks to see it.

![Heatwave days, counted three ways](outputs/charts/q1_heatwave_overall.png)

A daily maximum identical to the day before normally covers about 4% of days. At {r['groups']['jumped']} stations it jumps from {r['onset']['november_2010']:.0f}% in November 2010 to {r['onset']['december_2010']:.0f}% a month later, holds for five years, and falls away in early 2016. Minimums at the same stations never move.

![Share of days repeating the previous reading, by group](outputs/charts/repeats_by_group.png)

The stations affected follow regional lines, which weather does not: {r['chennai_region']['jumped']} of the {r['chennai_region']['stations']} in the area of IMD's Chennai centre, and none of Maharashtra's {r['maharashtra']['stations']}.

![Map of stations by when repeats affected them](outputs/charts/repeat_groups_map.png)

| Question | Answer, for these stations |
|---|---|
| Are heatwave days becoming more frequent? | Probably, by about a third to a half from 1982-89 to the 2010s. As recorded {recorded['change_pct']:+.0f}%. With every repeat removed {clean['change_pct']:+.0f}% (95% interval {clean['change_pct_ci'][0]:.0f}% to {clean['change_pct_ci'][1]:.0f}%), which over-corrects. At the {clean_group['recorded']['stations']} stations repeats never touched {clean_group['recorded']['change_pct']:+.0f}% (interval {clean_group['recorded']['change_pct_ci'][0]:.0f}% to {clean_group['recorded']['change_pct_ci'][1]:.0f}%). IMD's own count at 103 stations: {q1['imd_change_pct']:+.0f}%. |
| Are nights warming faster than days? | No. Days +{q2['median_tmax_rate']:.2f}°C a decade, nights +{q2['median_tmin_rate']:.2f}°C, and nights led at {q2['nights_faster']} of {q2['stations']} stations. At the {clean_q2['stations']} clean stations the two are level (+{clean_q2['median_tmax_rate']:.2f} and +{clean_q2['median_tmin_rate']:.2f}°C). |
| Is summer starting earlier? | Not clearly. First 40°C moved {q3['median_days_per_decade']:+.1f} days a decade (95% interval {q3['median_days_per_decade_ci'][0]:+.1f} to {q3['median_days_per_decade_ci'][1]:+.1f}), and years swing by far more than that. |
| Is monsoon rain getting more extreme? | No clear sign in either window that can be tested. Across {q4['gauge_stations']:,} gauges, 1901-1970, heavy days went from {q4['first_decade']['heavy_days']:.2f} to {q4['last_decade']['heavy_days']:.2f} a season. Across {q4['recent_window']['stations']} stations, 2006-2024, they moved {q4['recent_window']['mean_heavy_days_per_decade']:+.2f} a decade (interval {q4['recent_window']['mean_heavy_days_per_decade_ci'][0]:+.2f} to {q4['recent_window']['mean_heavy_days_per_decade_ci'][1]:+.2f}). A reporting break means the two cannot be joined. |
| Which stations are warming fastest? | {q5['fastest'][0]['name']} (+{q5['fastest'][0]['mean_rate']:.2f}°C a decade), then {q5['fastest'][1]['name']}, {q5['fastest'][2]['name']} and {q5['fastest'][3]['name']}. {q5['warming']} of {q5['stations']} stations warmed. |
| How does India compare? | Rank {q6['india_rank']} of {q6['countries_ranked']} countries at +{q6['india_median_rate']:.2f}°C a decade, against a median country of +{q6['median_of_countries']:.2f}°C, under one rule for all. Using clean stations alone: rank {q6['india_clean_stations_only']['rank']}. |

![India's stations coloured by warming rate](outputs/charts/q5_station_map.png)

These results describe the stations named, not all of India. The [brief](outputs/india_heat_record_brief.pdf) sets out the limits.

## The artefact

This is the project's main discovery, and five separate tests point the same way. They all use this one dataset, and no document found so far describes the problem, so the cause is inferred.

| Test | Result |
|---|---|
| **All or nothing** | {r['groups']['jumped']} of {r['comparable_stations']} stations jump by 10 points or more at 2011. {r['stations_jumping_5_to_15_points']} jump by 5 to 15 points. Stations either have it or do not. |
| **Sudden** | {r['onset']['november_2010']:.0f}% in November 2010, {r['onset']['december_2010']:.0f}% in December, then {r['offset']['december_2015']:.0f}% in December 2015, {r['offset']['january_2016']:.0f}% in January 2016, {r['offset']['march_2016']:.0f}% in March. |
| **Regional** | {r['chennai_region']['jumped']} of {r['chennai_region']['stations']} stations in the area of IMD's Chennai centre, plus {', '.join(r['chennai_region']['jumped_elsewhere'])}. None of Maharashtra's {r['maharashtra']['stations']}. A separate group of {r['groups']['early']} in the north-west steps up around 1990. |
| **Only maximums** | At the same stations and dates, minimums repeat at {r['jumped_median_minimum_share']['2001-10']}% before and {r['jumped_median_minimum_share']['2011-15']}% during. Maximums go from {r['jumped_median_share']['2001-10']}% to {r['jumped_median_share']['2011-15']}%. |
| **On peaks** | Repeated maximums sit on local peaks {r['peaks']['jumped']['peaks_per_trough']} times as often as on local troughs, against {r['peaks']['clean']['peaks_per_trough']} at clean stations and {r['peaks']['jumped_minimums']['peaks_per_trough']} for minimums at the same stations. A 24-hour window that catches the previous day's peak would do exactly this. |

Compared with clean stations, the day-night gap at the stations that jumped widens by {r['gap_change']['difference']}°C in 2011-15 (95% interval {r['gap_change']['difference_ci'][0]} to {r['gap_change']['difference_ci'][1]}), so it reaches mean temperatures too, not just threshold counts.

My first explanation was a peak carried forward in time, and I predicted the reading after a repeated pair would be lower more often than the reading before it. It was not: the two match. That test ruled out the simple version, and led to the local-peak test above.

## Each question's chart

The rise is uneven. {q1['biggest_rises'][0]}, {q1['biggest_rises'][1]} and {q1['biggest_rises'][2]} rose most with repeats removed, while {q1['stations_under_one_day_both_periods']} of the {q1['panel_stations']} stations average under one heatwave day a season in both 1982-89 and the 2010s.

![Heatwave days at each panel station](outputs/charts/q1_small_multiples.png)

Most stations warmed faster by day than by night, though much of that gap comes from stations with the reporting problem.

![Warming by day and by night at each station](outputs/charts/q2_days_nights.png)

Summer's first 40°C swings by weeks from year to year, with no clear drift.

![First 40°C of the year](outputs/charts/q3_first_40c.png)

Across the complete gauge record, rainy days held steady and heavy days barely moved.

![Rainy days and heavy days per season, 1901-1970](outputs/charts/q4_monsoon.png)

After 1972 the same stations appear to lose over a third of their rain and later recover, so no trend is drawn across that break.

![The same stations' monsoon rain, by era](outputs/charts/q4_water_balance.png)

India's stations warmed more slowly than most countries', under one rule for all.

![Countries ranked by median warming rate](outputs/charts/q6_countries.png)

## Why the data needed checking

The headline number was wrong before the first query ran. The widely quoted 2.68B is a count of measurements. The table has {scale['rows']:,} rows, one per station per day, and it came from a {scale['parquet_bytes'] / 1e9:.2f} GB file, not the documented 6.4 GB.

| What was found | How it was caught | What changed |
|---|---|---|
| A missing reading is stored as 0 | `tempMax = 0` appears {dq['zero_rows_india']:,} times in India, against once at +0.1°C | Zeros become NULL before any mean or threshold |
| The 1961-1990 baseline cannot be built | No Indian station has 20 complete years in it | Normals use 1991-2020, as IMD now does |
| Every maximum from 1973 to 1981 is a whole degree | Share of whole-degree values by year | Threshold questions start in 1982 |
| Repeated readings switch on by region | Share of days equal to the day before, by station and month | Heat counts are shown as recorded, with repeats removed, and at stations never affected |
| Rain halves when the source changes | The same {q4['same_stations']} stations, compared across NOAA's sources | Rain after 1972 is not compared with rain before it |
| The source changes again in 2025 | NOAA's flags, kept in its raw files | Temperature stops at December 2024 |

All {dq['checks']} checks are in the [issue log](docs/issue_log.csv), including those that passed, and [plan_corrections.md](docs/plan_corrections.md) records every departure from the original plan.

![Coverage of Indian stations by year](outputs/charts/coverage.png)

## The OLAP design

One raw table, two rollups kept current by materialized views, and small result tables for the dashboard.

```sql
CREATE TABLE heat.noaa
(
    station_id    LowCardinality(String) CODEC(ZSTD(1)),
    date          Date32 CODEC(DoubleDelta, ZSTD(1)),
    tempMax       Int32 CODEC(ZSTD(1)),
    tempMin       Int32 CODEC(ZSTD(1)),
    precipitation UInt32 CODEC(T64, ZSTD(1))
    -- and the remaining columns: sql/01_schema.sql
)
ENGINE = MergeTree
PARTITION BY intDiv(toYear(date), 10)
ORDER BY (station_id, date);
```

All {scale['rows']:,} rows take **{noaa_gb:.2f} GB**, from {raw_gb:.0f} GB uncompressed and smaller than the source Parquet. Testing on 30M rows, per-column codecs took 1.12 bytes a row, against 3.55 for ClickHouse's default.

### Benchmark

Median seconds on warm runs, with the same limits on each engine: 4 threads and 3 GB. These are the real times, including where DuckDB wins.

{benchmark_table(bench)}

![Benchmark results](outputs/charts/benchmark.png)

- **Rollups earn their place.** They answer the country scan about {float(seconds(bench, 'Every country by decade, full scan', 'clickhouse_raw')) / float(seconds(bench, 'Every country by decade, full scan', 'clickhouse_rollup')):.0f} times faster, with the same answer, and a test holds them to it.
- **DuckDB beats ClickHouse's raw table** on wide scans, reading the same data from a plain Parquet file. If the data is scanned rarely, that may be the simpler choice.
- **The first version of Q6 lost to DuckDB because of how it was written.** Its join ran the months step twice. A window function and in-order aggregation took the rollup from {seconds(bench, 'Q6, first version: a join that runs the months step twice', 'clickhouse_rollup')} s to {seconds(bench, 'Q6, rewritten: window function, in key order', 'clickhouse_rollup')} s.
- **A filter that misses the sort key costs most on its first run.** `substring(station_id, 1, 2) = 'IN'` cannot use the sort key, so a cold run reads all 1.07B rows where `LIKE 'IN%'` reads 62M, and takes {seconds(bench, "India, same result, plan's substring filter", 'clickhouse_raw', 'cold')} s against {seconds(bench, 'India, every station-year, by key prefix', 'clickhouse_raw', 'cold')} s. Warm runs nearly match, because ClickHouse's query condition cache remembers which parts of the table matched.

## How much depends on the choices made

Rise in heatwave days, 1982-89 to the 2010s, when one assumption changes. IMD's rule was implemented a second time in Python, and it agrees with ClickHouse on every station-day.

{sensitivity_table(scenarios)}

## Live site and dashboard

The [live site]({SITE}) needs no server: results are built into one page and hosted on GitHub Pages. Its station explorer shows each station's own repeat history, so you can compare Chennai with Pune yourself.

A Grafana dashboard reads the same tables live from ClickHouse, with India's station map, one panel per question, the benchmark and the quality log. It runs locally, because hosting it means hosting ClickHouse.

![The Grafana dashboard](outputs/dashboard/dashboard_full.png)

## Run it

ClickHouse has no Windows build, so on Windows it runs in WSL. A full build needs about 8 GB of disk on the Linux side, including space for merges.

```bash
# In Linux or WSL, from the repository. Run the two start scripts in their own terminals.
bash infra/install_clickhouse.sh
bash infra/start_server.sh
mkdir -p ~/heat/parquet
curl -o ~/heat/parquet/noaa_enriched.parquet https://datasets-documentation.s3.eu-west-3.amazonaws.com/noaa/noaa_enriched.parquet
~/heat/bin/clickhouse client --multiquery --queries-file sql/01_schema.sql
bash infra/load_parquet.sh
bash infra/install_duckdb.sh
bash infra/install_grafana.sh
bash infra/start_grafana.sh     # http://127.0.0.1:3000

# Then, with Python 3.11 or later:
python -m venv .venv && . .venv/bin/activate     # .venv\\Scripts\\activate on Windows
pip install -r requirements.txt
python pipeline/download_ghcn.py
python pipeline/load_reference.py
python pipeline/run_all.py --with-benchmark
pytest
```

On a 16 GB machine, run one heavy step at a time. WSL's default of half the machine's memory can exhaust Windows during the load, which grew the page file by over 5 GB in one step on the laptop this was built on. A `.wslconfig` with `memory=4500MB` under `[wsl2]` prevents that, and it needs `wsl --shutdown` to apply. It also limits Docker Desktop, so remove it afterwards. Tests that need ClickHouse skip themselves if it is not running.

## What's where

| Path | Contents |
|---|---|
| [sql/](sql/) | Schema and rollups, normals, heatwave logic, [quality checks](sql/dq_checks.sql), [the questions](sql/questions/), [benchmark queries](sql/benchmark/) |
| [pipeline/](pipeline/) | The steps from loading to the brief, run in order by `run_all.py` |
| [site/](site/) | The live site, built by `pipeline/build_site.py` and served by GitHub Pages |
| [dashboard/](dashboard/) | Grafana dashboard, generated by `build_dashboard.py` |
| [notebooks/](notebooks/) | How the data problems were found, with evidence, built by `build_notebook.py` |
| [data/mart/](data/mart/) | Aggregated results and `findings.json`, which every report reads from |
| [docs/](docs/) | [Methods](docs/methods.md), [data dictionary](docs/data_dictionary.md), [issue log](docs/issue_log.csv), [plan corrections](docs/plan_corrections.md), [sources](docs/sources.md) |
| [outputs/](outputs/) | The brief, charts and dashboard screenshot |
| [tests/](tests/) | IMD's rule at its boundaries, reconciliation, and reports against results |

## Data

NOAA GHCN-Daily, by Menne et al. (2012), through ClickHouse's Parquet and NOAA's per-station files. See [DATA_LICENSE.md](DATA_LICENSE.md). Row-level data is not committed. The code is under the [MIT licence](LICENSE).
"""


def resume_line(f: dict, bench: list[dict]) -> str:
    q1, r = f["q1_heatwave_days"], f["repeats"]
    raw = seconds(bench, "Every country by decade, full scan", "clickhouse_raw")
    rollup = seconds(bench, "Every country by decade, full scan", "clickhouse_rollup")
    return (
        f"Built a ClickHouse OLAP pipeline over {f['scale']['rows'] / 1e9:.2f}B NOAA station-days ({f['scale']['measurements_before_pivot'] / 1e9:.2f}B measurements). "
        f"Analysed heatwave trends at {q1['panel_stations']} Indian stations using IMD's heatwave definition, partitioned MergeTree tables and materialized-view rollups. "
        f"Cut a full-scan query from {raw} s to {rollup} s versus the raw table, and uncovered an undocumented reporting artefact affecting {r['groups']['jumped'] + r['groups']['early']} of {r['comparable_stations']} stations, which inflated heatwave counts.\n"
        f"Live site: {SITE}\n"
        f"Code: {REPOSITORY}\n"
    )


def interview_notes(f: dict, bench: list[dict]) -> str:
    q1, q2, q3, q4, q6, dq, r = f["q1_heatwave_days"], f["q2_days_and_nights"], f["q3_first_40c"], f["q4_monsoon"], f["q6_countries"], f["quality"], f["repeats"]
    recorded, clean_group, clean_q2 = q1["recorded"], q1["by_repeat_group"]["clean"], q2["by_repeat_group"]["clean"]
    return f"""# Interview notes

Live site: {SITE}
Code: {REPOSITORY}

Private prep, kept out of git.

## The one-minute version

I measured India's heat in ClickHouse on {f['scale']['rows'] / 1e9:.2f} billion station-days. Heatwave days rose {recorded['change_pct']:.0f}% as recorded, and I found out why that number can't be taken at face value. At {r['groups']['jumped']} stations, readings identical to the previous day jump from {r['onset']['november_2010']:.0f}% to {r['onset']['december_2010']:.0f}% in one month, December 2010, and stop in early 2016. {r['chennai_region']['jumped']} of those are in one IMD region, and minimums at the same stations never move. So I compared stations the problem never touched: up {clean_group['recorded']['change_pct']:.0f}%, close to IMD's own {q1['imd_change_pct']:.0f}%. So the rise is real, and the record overstates it where the artefact applies.

## Questions to expect

**How did you find the artefact?**
Checking the hottest readings against IMD's published records. They matched exactly, but the next day often held the identical value. So I measured how often that happens by year, then by station, and the station view split cleanly into groups, then the groups turned out to follow regional lines.

**How do you know it isn't weather?**
Five things. It is all or nothing: {r['stations_jumping_5_to_15_points']} stations jump by 5 to 15 points. It starts within a month. It follows administrative lines: none of Maharashtra's {r['maharashtra']['stations']} stations have it, next door to a region where {r['chennai_region']['jumped']} of {r['chennai_region']['stations']} do. Minimums at the same stations don't move. And repeated maximums sit on local peaks {r['peaks']['jumped']['peaks_per_trough']} times as often as troughs, against {r['peaks']['clean']['peaks_per_trough']} at clean stations.

**Do you know what caused it?**
No, and I say so. I found no document describing it. A 24-hour window that catches the previous day's peak would produce this pattern, and the regional split suggests a change in how reports were sent or processed. That is inference.

**Weren't you wrong about something along the way?**
Yes, and this is the best story to tell. My first conclusion was that about half the rise was artefact and the corrected rise couldn't be told apart from zero. Then I predicted that a carried-forward peak would leave a direction signature, and the test failed. Looking closer showed the problem was concentrated in some stations. That meant blanket removal over-corrected, and stations never affected still rose {clean_group['recorded']['change_pct']:.0f}%. I rewrote the conclusion before publishing.

**Why ClickHouse and not just DuckDB?**
DuckDB beat ClickHouse's raw table on wide scans in my benchmark, and I report that. ClickHouse earned its place through rollups: a materialized view keeps them current as rows arrive, and the country scan fell from {seconds(bench, 'Every country by decade, full scan', 'clickhouse_raw')} s to {seconds(bench, 'Every country by decade, full scan', 'clickhouse_rollup')} s with the same answer. For a one-off scan of a Parquet file I would choose DuckDB.

**What was the hardest bug?**
The plan's rollup divided by row count, but a missing reading is stored as 0, so every mean would have been too low. Then requiring whole years for trends left India with 0 stations in the global comparison. I fitted through qualifying months instead, under the same rule for every country.

**What was wrong with your first benchmark?**
Q6 lost to DuckDB, even on the rollup. The cause was my SQL: a join that ran the months step twice. A window function and in-order aggregation made it about three times faster. I kept both versions in the table. I also got the `substring` filter wrong. It nearly matched `LIKE`, and `EXPLAIN` showed it never used the index, so that made no sense. The answer was ClickHouse's query condition cache, which was making my "cold" run warm. Clearing it showed the true first-run cost, more than twice as slow, so the harness now clears it.

**What would you do with more time?**
Get IMD's own station data, which should not have the repeat problem, and test the correction directly. Ask NOAA or IMD what changed in December 2010. Separate urban stations, because this data cannot tell a warming climate from a growing city. Apply IMD's newer percentile thresholds.

**What does this not show?**
It is not a national estimate. These are {dq['stations_in_heat_panel']} stations, none in the hills, and few have complete seasons after 2015. The clean group is only {clean_group['recorded']['stations']} stations, its interval is wide, and {clean_group['recorded']['stations_falling']} of them fell. GHCN-Daily also does not correct for station moves.

**Nights are not warming faster? Isn't that the opposite of what people say?**
Overall, days +{q2['median_tmax_rate']:.2f}°C and nights +{q2['median_tmin_rate']:.2f}°C a decade. But at the {clean_q2['stations']} clean stations they are level, +{clean_q2['median_tmax_rate']:.2f} and +{clean_q2['median_tmin_rate']:.2f}°C, with nights ahead at {clean_q2['nights_faster']}. So: no evidence nights lead, and part of the apparent day lead comes from affected stations. IMD's warm nights did rise, because it counts them only on days reaching 40°C.

## Numbers to know

- {f['scale']['rows']:,} rows, from {f['scale']['measurements_before_pivot']:,} measurements.
- Station funnel: {dq['indian_stations_in_file']:,} Indian stations in the file, {dq['stations_with_any_temperature']} with any temperature, {dq['stations_with_normals']} with normals, {dq['stations_in_heat_panel']} in the heatwave panel.
- Artefact: {r['groups']['jumped']} stations stepped at 2011, {r['groups']['early']} around 1990, {r['groups']['clean']} never, out of {r['comparable_stations']} comparable.
- Rain network: {q4['network_1970']:,} stations in 1970, {q4['network_1973']} in 1973.
- India ranks {q6['india_rank']} of {q6['countries_ranked']} countries, from {q6['stations_all_countries']:,} stations.
- First 40°C: {q3['median_days_per_decade']:+.1f} days a decade.
"""


def main() -> None:
    f = json.loads((MART / "findings.json").read_text(encoding="utf8"))
    bench, scenarios, storage = read_csv("benchmark.csv"), read_csv("sensitivity.csv"), read_csv("storage.csv")
    (ROOT / "README.md").write_text(readme(f, bench, scenarios, storage), encoding="utf8", newline="\n")
    private = ROOT / "private"
    private.mkdir(exist_ok=True)
    (private / "resume_line.txt").write_text(resume_line(f, bench), encoding="utf8", newline="\n")
    (private / "interview_notes.md").write_text(interview_notes(f, bench), encoding="utf8", newline="\n")
    print("wrote README.md and private notes")


if __name__ == "__main__":
    main()
