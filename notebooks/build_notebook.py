"""Build and execute the walkthrough notebook. The notebook itself reads only data/mart and docs.

Usage: python notebooks/build_notebook.py
"""
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

root = Path(__file__).resolve().parent.parent
md = new_markdown_cell
code = new_code_cell

cells = [
    md("""# How the data problems were found

This walks through each problem in the order it turned up, using the saved results in `data/mart`, so it runs without ClickHouse. The queries that produced them are in `sql/`.

The habit throughout: before believing a number, ask what it would look like if the data were wrong, then look for that."""),
    code("""from pathlib import Path
import json
import pandas as pd

ROOT = Path.cwd() if (Path.cwd() / "data").exists() else Path.cwd().parent
MART = ROOT / "data" / "mart"
findings = json.loads((MART / "findings.json").read_text(encoding="utf8"))
issues = pd.read_csv(ROOT / "docs" / "issue_log.csv", keep_default_na=False)
overall = issues[issues.station == ""].set_index("check")
pd.set_option("display.max_colwidth", 120, "display.width", 160)"""),
    md("""## 1. The row count

The plan said 2,679,264,563 rows, one per station per day. A Parquet file records its row count in its footer, which can be read over HTTP without downloading the file. It says 1,074,089,837. ClickHouse's documentation gives the larger figure as the measurement count before pivoting into rows, so 2.68B is measurements and 1.07B is station-days."""),
    code("""scale = findings["scale"]
print(f"Rows in the file:          {scale['rows']:>13,}")
print(f"Measurements before pivot: {scale['measurements_before_pivot']:>13,}")
print(f"Measurements per row:      {scale['measurements_before_pivot'] / scale['rows']:>13.1f}")
print(f"Last date in the file:     {scale['last_date']:>13}")"""),
    md("""## 2. Zero means missing

The footer also says every column is required, so nothing can be NULL. Then what does a station with no thermometer store? If missing readings are 0, exactly 0.0 C should be far more common than its neighbours, -0.1 C and +0.1 C."""),
    code("""print(overall.loc["DQ01", "detail"])"""),
    md("""That settles it. A rollup that divides `sum(tempMax)` by `count()`, as the plan's did, would drag every mean toward zero, so the rollup counts readings separately from rows.

Rain has the same problem in a harder form, because a real dry day is also 0. NOAA's raw files omit readings that were never taken, so they show how many zeros are false."""),
    code("""print(overall.loc["DQ02", "detail"])"""),
    md("""## 3. Temperature starts in 1973, and rain nearly stops

A file described as 1900-2022 suggests 122 years of everything. Counting stations each year shows something else."""),
    code("""coverage = pd.read_csv(MART / "coverage_by_year.csv").set_index("year")
coverage.loc[[1901, 1950, 1960, 1970, 1973, 1980, 1990, 2000, 2010, 2020], ["stations_rain", "stations_tmax", "stations_full_year", "stations_full_hot_season"]]"""),
    md("""The plan's 1961-1990 baseline therefore cannot be built. It was replaced with 1991-2020, which IMD itself now uses, and where the most stations have complete seasons."""),
    code("""passing = pd.read_csv(MART / "passing_stations.csv", keep_default_na=False)
pd.Series({
    "Indian stations in the file": findings["quality"]["indian_stations_in_file"],
    "with any temperature": len(passing),
    "with normals (15 complete hot seasons in 1991-2020)": int(passing.has_normals.sum()),
    "in the heatwave panel (also complete in every period)": int(passing.in_heat_panel.sum()),
})"""),
    md("""## 4. Readings that repeat

While checking the hottest readings against published records, the values matched exactly: Churu's 50.8 C on 1 June 2019 and 50.5 C on 28 May 2024 are both documented by IMD. But the next day held the identical value both times. Is that common? A maximum identical to the day before, to a tenth of a degree, should be rare and steady over time."""),
    code("""repeats = pd.read_csv(MART / "repeats_by_year.csv").set_index("year")
repeats.loc[[1985, 1990, 1995, 2000, 2005, 2008, 2009, 2010, 2011, 2012, 2013, 2015], ["stations", "repeat_pct"]].round(1)"""),
    md("""It more than doubles between 2010 and 2011, which weather cannot do. My first conclusion was that about half the rise in heatwave days was artefact, because removing every repeat cuts the rise from 64% to 31%, with an interval that includes zero. That conclusion was too strong, and the next two steps show why.

**A prediction that failed.** If a day's peak were carried forward in time, the reading after a repeated pair should be lower more often than the reading before it. It is not: the two rates match. That ruled out the simple version, and prompted a look at individual stations.

**The problem is not spread evenly.** Each station's repeat share either stays near a natural level or jumps by 20 points or more."""),
    code("""groups = pd.read_csv(MART / "station_repeat_groups.csv")
comparable = groups[groups.repeat_group != "unknown"]
jump = comparable["share_2011-15"] - comparable["share_2001-10"]
print("Stations by size of jump, 2001-10 to 2011-15, in points")
print(pd.cut(jump, [-40, 0, 5, 15, 30, 50]).value_counts().sort_index().to_string())
print()
print(comparable.group_label.value_counts().to_string())"""),
    md("""**And it follows regional lines.** Weather does not stop at a state border."""),
    code("""pd.read_csv(MART / "repeat_groups_by_state.csv", keep_default_na=False).set_index("state")"""),
    md("""**It starts and stops within weeks,** and minimums at the same stations and dates never move."""),
    code("""months = pd.read_csv(MART / "repeat_months_jumped.csv")
window = months[((months.year == 2010) & (months.month >= 8)) | ((months.year == 2011) & (months.month <= 2)) | ((months.year == 2015) & (months.month >= 11)) | ((months.year == 2016) & (months.month <= 4))]
window[["year", "month", "tmax_days", "tmax_share", "tmin_share"]].round(1)"""),
    md("""**Repeats sit on peaks.** A pair of equal readings is a local peak if the days on either side are both lower. Natural pairs fall about evenly between peaks and troughs. A window that catches the previous day's peak piles them up on peaks."""),
    code("""pd.read_csv(MART / "repeat_peak_ratios.csv")[["reading", "repeat_group", "pairs", "peak_pct", "trough_pct", "peaks_per_trough"]].round(1)"""),
    md("""**So the fairest test is the stations it never touched.** Removing every repeat over-corrects, because it also drops genuine hot days. Comparing groups avoids that."""),
    code("""q1 = findings["q1_heatwave_days"]
rows = {"All stations, as recorded": q1["recorded"], "All stations, repeats removed": q1["without_repeats"]}
for key, label in (("clean", "Never affected"), ("jumped", "Stepped at 2011"), ("early", "Stepped around 1990")):
    rows[label + ", as recorded"] = q1["by_repeat_group"][key]["recorded"]
    rows[label + ", repeats removed"] = q1["by_repeat_group"][key]["without_repeats"]
pd.DataFrame(rows).T[["stations", "before", "after", "change_pct", "change_pct_ci", "stations_rising", "stations_falling"]]"""),
    md("""At never-affected stations, removing repeats changes almost nothing, as it should. They rose about 55%, and IMD's own count at 103 stations rose 45%. So heatwave days probably did rise, by about a third to a half, and the record overstates it where the artefact applies.

It also changes another answer. At never-affected stations, days and nights warm at the same pace."""),
    code("""pd.DataFrame(findings["q2_days_and_nights"]["by_repeat_group"]).T"""),
    code("""sensitivity = pd.read_csv(MART / "sensitivity.csv")
sensitivity[["scenario", "stations", "change_recorded_pct", "change_no_repeat_pct"]]"""),
    md("""## 5. Whole degrees before 1982

Every maximum from 1973 to 1981 is a whole degree, and then the share drops to about 15%. Rounding does not bias a mean, but it does move values across a cut-off: a true 39.6 C becomes 40 C. So the threshold questions start in 1982."""),
    code("""print(overall.loc["DQ11", "detail"])"""),
    md("""## 6. Rain that halves and recovers

Comparing the same stations across NOAA's sources is a simple water-balance test. A monsoon does not fall by over a third and then return, so this is a change in reporting."""),
    code("""pd.read_csv(MART / "q4_water_balance.csv")[["era", "stations", "season_mm", "rainy_days", "heavy_days", "reports"]].round(1)"""),
    md("""A naive trend across these eras would show extreme rain rising sharply from the 1990s. That is the finding this project chose not to report. The only long comparison it trusts is 1901-1970, on complete gauges."""),
    code("""pd.read_csv(MART / "q4_gauge_decades.csv").round(2)"""),
    md("""## 7. A rule that left India out

Warming rates first required whole years. That left India with no stations at all in the global comparison, because minimum temperatures are sparse before 2000. Each month is already compared with that station's own usual month, so the seasons are removed and a line can go through every qualifying month. The same rule applies to every country."""),
    code("""countries = pd.read_csv(MART / "q6_country_summary.csv", keep_default_na=False)
countries[countries.country.isin(["IN", "US", "CH", "RS", "AS"]) | (countries["rank"] <= 3)][["rank", "name", "stations", "median_rate"]].round(3)"""),
    md("""## 8. Where I was wrong in the benchmark

Two more of this project's expectations failed, and both are worth keeping.

- **The plan's `substring` filter seemed to cost almost nothing, and that was wrong.** It nearly matched `LIKE 'IN%'` in the first benchmark, but `EXPLAIN` showed it never used the sort key. ClickHouse's query condition cache was remembering which parts of the table matched, so the "cold" run was not cold. With that cache cleared, it reads all 1.07B rows and takes more than twice as long. The harness now clears it.
- **The first version of Q6 lost to DuckDB, even on the rollup.** The fault was in the SQL: its join ran the months step twice. A window function and in-order aggregation made it about three times faster."""),
    code("""bench = pd.read_csv(MART / "benchmark.csv")
bench.pivot_table(index="question", columns=["run", "engine"], values="seconds")"""),
    code("""reads = pd.read_csv(MART / "benchmark_reads.csv")
reads.assign(million_rows=(reads.read_rows / 1e6).round(1), gb_read=(reads.read_bytes / 1e9).round(2))[["query", "million_rows", "gb_read"]]"""),
    md("""## What the checks add up to

Every check is in `docs/issue_log.csv`, and the departures from the original plan are in `docs/plan_corrections.md`."""),
    code("""issues.groupby(["check", "severity"]).agg(rows=("count", "size"), total=("count", "sum"), what=("description", "first")).reset_index()"""),
]

nb = new_notebook(cells=cells, metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}})
NotebookClient(nb, timeout=120, kernel_name="python3", resources={"metadata": {"path": str(root / "notebooks")}}).execute()
for cell in nb.cells:
    if cell.cell_type == "code":
        cell.metadata.pop("execution", None)
path = root / "notebooks" / "how_the_problems_were_found.ipynb"
nbformat.write(nb, str(path))
print("wrote", path.name, path.stat().st_size // 1024, "KB")
errors = [o for c in nb.cells if c.cell_type == "code" for o in c.outputs if o.output_type == "error"]
print("errors:", len(errors))
