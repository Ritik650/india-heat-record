"""Reports against results, and the published checks. Most of this needs no ClickHouse, so it runs in a fresh clone."""
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))


@pytest.fixture(scope="module")
def findings():
    return json.loads((ROOT / "data/mart/findings.json").read_text(encoding="utf8"))


@pytest.fixture(scope="module")
def brief_text():
    from pypdf import PdfReader

    reader = PdfReader(str(ROOT / "outputs/india_heat_record_brief.pdf"))
    return " ".join(" ".join(page.extract_text().split()) for page in reader.pages)


@pytest.fixture(scope="module")
def readme():
    return (ROOT / "README.md").read_text(encoding="utf8")


def test_brief_is_two_pages():
    from pypdf import PdfReader

    assert len(PdfReader(str(ROOT / "outputs/india_heat_record_brief.pdf")).pages) == 2


def test_brief_quotes_the_headline_figures(findings, brief_text):
    q1 = findings["q1_heatwave_days"]
    clean = q1["by_repeat_group"]["clean"]["recorded"]
    assert f"rose {q1['recorded']['change_pct']:.0f}%" in brief_text
    assert f"gives {q1['without_repeats']['change_pct']:.0f}%" in brief_text
    assert f"up {clean['change_pct']:.0f}%" in brief_text
    assert f"{findings['repeats']['onset']['december_2010']:.0f}% a month later" in brief_text
    assert f"ranks {findings['q6_countries']['india_rank']} of {findings['q6_countries']['countries_ranked']}" in brief_text


def test_readme_quotes_the_headline_figures(findings, readme):
    q1 = findings["q1_heatwave_days"]
    assert f"As recorded {q1['recorded']['change_pct']:+.0f}%" in readme
    assert f"With every repeat removed {q1['without_repeats']['change_pct']:+.0f}%" in readme
    assert f"{q1['by_repeat_group']['clean']['recorded']['change_pct']:+.0f}%" in readme
    assert f"{findings['scale']['rows']:,} rows" in readme


def test_no_report_repeats_the_wrong_row_count(readme, brief_text):
    assert "2.68 billion rows" not in readme
    assert "2.68B rows" not in readme
    assert "2.68B rows" not in brief_text


def test_every_readme_link_resolves(readme):
    import re

    for target in re.findall(r"\]\(([^)#]+)\)", readme):
        if not target.startswith("http"):
            assert (ROOT / target).exists(), target


def test_every_chart_exists():
    for name in ["q1_heatwave_overall", "q1_small_multiples", "repeats_by_group", "repeat_groups_map", "q2_days_nights", "q3_first_40c", "q4_monsoon", "q4_water_balance", "q5_station_map", "q6_countries", "coverage", "benchmark"]:
        assert (ROOT / f"outputs/charts/{name}.png").stat().st_size > 5000, name


def test_quality_catalogue_parses():
    from quality import parse_checks

    checks = parse_checks(ROOT / "sql/dq_checks.sql")
    assert len(checks) == 15
    assert len({c["id"] for c in checks}) == 15
    assert all(c["severity"] in {"high", "medium", "low", "info"} and c["action"] and c["description"] and c["sql"] for c in checks)


def test_issue_log_lists_every_check():
    with open(ROOT / "docs/issue_log.csv", encoding="utf8") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["check"] for row in rows} == {f"DQ{i:02d}" for i in range(1, 16)}
    assert all(row["action_taken"] for row in rows)


def test_quoted_imd_range_is_true(findings):
    q1 = findings["q1_heatwave_days"]
    low, high = q1["without_repeats"]["change_pct"], q1["recorded"]["change_pct"]
    imd = 100 * (q1["imd_103_stations"]["2011-20"] / q1["imd_103_stations"]["1981-90"] - 1)
    assert low <= imd <= high
    assert q1["imd_inside_our_range"] is True


def test_sensitivity_baseline_matches_findings(findings):
    with open(ROOT / "data/mart/sensitivity.csv", encoding="utf8") as handle:
        base = next(csv.DictReader(handle))
    q1 = findings["q1_heatwave_days"]
    assert float(base["before_recorded"]) == q1["recorded"]["before"]
    assert float(base["after_recorded"]) == q1["recorded"]["after"]
    assert float(base["after_no_repeat"]) == q1["without_repeats"]["after"]


def test_every_benchmark_question_has_all_runs():
    with open(ROOT / "data/mart/benchmark.csv", encoding="utf8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows and all(float(row["seconds"]) > 0 for row in rows)
    assert {row["engine"] for row in rows} == {"clickhouse_raw", "clickhouse_rollup", "duckdb_parquet"}
    assert {row["run"] for row in rows} == {"cold", "median_warm"}


def test_dashboard_definition_is_current():
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_dashboard", ROOT / "dashboard/build_dashboard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build() == json.loads((ROOT / "dashboard/india_heat.json").read_text(encoding="utf8"))


def test_dashboard_uses_no_online_basemap():
    dashboard = json.loads((ROOT / "dashboard/india_heat.json").read_text(encoding="utf8"))
    geomap = next(panel for panel in dashboard["panels"] if panel["type"] == "geomap")
    assert geomap["options"]["basemap"]["config"]["url"].startswith("/public/maps/")


def test_repeat_groups_are_a_clean_split(findings):
    """The grouping is defensible only because stations do not spread across the boundary."""
    repeats = findings["repeats"]
    assert repeats["stations_jumping_5_to_15_points"] == 0
    assert sum(repeats["groups"].values()) == repeats["comparable_stations"]
    assert repeats["jumped_median_share"]["2011-15"] > 20 > repeats["jumped_median_share"]["2001-10"]
    assert abs(repeats["jumped_median_minimum_share"]["2011-15"] - repeats["jumped_median_minimum_share"]["2001-10"]) < 1


def test_removing_repeats_barely_moves_clean_stations(findings):
    """If never-affected stations really are clean, removing repeats should change their result very little."""
    clean = findings["q1_heatwave_days"]["by_repeat_group"]["clean"]
    assert abs(clean["recorded"]["change_pct"] - clean["without_repeats"]["change_pct"]) <= 10


def test_group_panel_adds_up(findings):
    q1 = findings["q1_heatwave_days"]
    in_groups = sum(len(g["names"]) for g in q1["by_repeat_group"].values())
    assert in_groups <= q1["panel_stations"]
    assert q1["by_repeat_group"]["clean"]["recorded"]["stations"] == len(q1["by_repeat_group"]["clean"]["names"])


def test_imd_documented_records_are_in_the_data(ch, findings):
    """IMD's own figures for Churu are the outside check that the source matches reality."""
    for record in findings["imd_records"]:
        value = ch.command(f"SELECT tmax FROM heat.india_days WHERE station_id = '{record['station']}' AND date = '{record['date']}'")
        assert int(value) / 10 == record["celsius"], record


def test_every_dashboard_query_runs(ch):
    dashboard = json.loads((ROOT / "dashboard/india_heat.json").read_text(encoding="utf8"))
    queries = [target["rawSql"] for panel in dashboard["panels"] for target in panel.get("targets", [])]
    assert len(queries) >= 15
    for query in queries:
        assert ch.query(query).row_count > 0, query
