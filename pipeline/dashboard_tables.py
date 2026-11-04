"""Publish the small result tables to ClickHouse, so Grafana reads them live over SQL.

Grafana queries these and the rollups, never the raw table, which is what keeps every panel instant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from common import DOCS, MART, client  # noqa: E402

TABLES = {
    "dash_station_rates": MART / "station_rates.csv",
    "dash_heat_periods": MART / "q1_station_periods.csv",
    "dash_repeats": MART / "repeat_years_by_group.csv",
    "dash_repeat_groups": MART / "station_repeat_groups.csv",
    "dash_first_40c": MART / "q3_yearly.csv",
    "dash_gauge_decades": MART / "q4_gauge_decades.csv",
    "dash_water_balance": MART / "q4_water_balance.csv",
    "dash_countries": MART / "q6_country_summary.csv",
    "dash_coverage": MART / "coverage_by_year.csv",
    "dash_sensitivity": MART / "sensitivity.csv",
    "dash_benchmark": MART / "benchmark.csv",
    "dash_issue_log": DOCS / "issue_log.csv",
}
CLICKHOUSE_TYPES = {"int64": "Int64", "float64": "Float64", "bool": "UInt8", "object": "String"}


def publish(ch, name: str, frame: pd.DataFrame) -> None:
    frame = frame.copy()
    for column in frame.columns:
        if frame[column].dtype == bool:
            frame[column] = frame[column].astype(int)
        elif frame[column].dtype == object:
            frame[column] = frame[column].fillna("").astype(str)
    frame = frame.fillna(0)
    columns = ", ".join(f"`{c}` {CLICKHOUSE_TYPES[str(frame[c].dtype)]}" for c in frame.columns)
    ch.command(f"DROP TABLE IF EXISTS heat.{name}")
    ch.command(f"CREATE TABLE heat.{name} ({columns}) ENGINE = MergeTree ORDER BY tuple()")
    ch.insert_df(name, frame)
    print(f"{name}: {len(frame):,} rows")


def summary(findings: dict) -> pd.DataFrame:
    q1, q2, q5, q6 = findings["q1_heatwave_days"], findings["q2_days_and_nights"], findings["q5_fastest_stations"], findings["q6_countries"]
    rows = [
        ("stations_panel", q1["panel_stations"]),
        ("stations_trend", q5["stations"]),
        ("change_recorded_pct", q1["recorded"]["change_pct"]),
        ("change_no_repeat_pct", q1["without_repeats"]["change_pct"]),
        ("change_clean_pct", q1["by_repeat_group"]["clean"]["recorded"]["change_pct"]),
        ("stations_hit", findings["repeats"]["groups"]["jumped"] + findings["repeats"]["groups"]["early"]),
        ("median_warming_rate", q5["median_rate"]),
        ("nights_faster", q2["nights_faster"]),
        ("india_rank", q6["india_rank"]),
        ("countries_ranked", q6["countries_ranked"]),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"]).astype({"value": float})


def main() -> None:
    ch = client()
    for name, path in TABLES.items():
        if path.exists():
            publish(ch, name, pd.read_csv(path, keep_default_na=False, na_values=[""]))
    findings = json.loads((MART / "findings.json").read_text(encoding="utf8"))
    publish(ch, "dash_summary", summary(findings))


if __name__ == "__main__":
    main()
