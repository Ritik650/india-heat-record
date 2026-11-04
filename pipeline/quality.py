"""Run the data-quality checks and write the issue log, coverage tables and passing-station list.

Coverage is measured before any finding is reported. A check that finds nothing still gets a row in
the log, so a reader can tell it ran.
"""
from __future__ import annotations

import csv
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import DOCS, MART, SQL, client, run_sql_file  # noqa: E402

HEADER = re.compile(r"^-- check: (\w+) \| (\w+) \| (.+)$")


def parse_checks(path: Path) -> list[dict]:
    """Split the catalogue into checks: id, severity, action, description and query."""
    checks: list[dict] = []
    current: dict | None = None
    for line in path.read_text(encoding="utf8").splitlines():
        match = HEADER.match(line)
        if match:
            current = {"id": match[1], "severity": match[2], "action": match[3], "description": "", "sql": []}
            checks.append(current)
        elif current is not None:
            if line.startswith("--"):
                if not current["description"]:
                    current["description"] = line.removeprefix("-- ").strip()
            elif line.strip():
                current["sql"].append(line)
    for check in checks:
        check["sql"] = "\n".join(check["sql"]).rstrip().rstrip(";")
    return checks


def run_checks(ch) -> list[dict]:
    rows = []
    for check in parse_checks(SQL / "dq_checks.sql"):
        started = time.time()
        result = ch.query(check["sql"]).result_rows
        found = [r for r in result if r[1]]
        print(f"{check['id']} {check['severity']:<6} {len(found):>4} rows, {time.time() - started:6.1f}s  {check['description'][:70]}")
        if not found:
            found = [("", 0, "passed")]
        for station, count, detail in found:
            rows.append({
                "check": check["id"],
                "station": station,
                "count": count,
                "severity": check["severity"],
                "description": check["description"],
                "action_taken": check["action"],
                "detail": detail,
            })
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ch = client()
    run_sql_file(ch, SQL / "06_panels.sql")
    write_csv(DOCS / "issue_log.csv", run_checks(ch))

    ch.query_df("SELECT * FROM heat.coverage_by_year ORDER BY year").to_csv(MART / "coverage_by_year.csv", index=False)
    ch.query_df("SELECT * FROM heat.passing_stations ORDER BY station_id").to_csv(MART / "passing_stations.csv", index=False)
    ch.query_df("SELECT station_id, name, state, station_class, lat, lon, elevation, coast_km, inside_india FROM heat.station_class WHERE station_id IN (SELECT DISTINCT station_id FROM heat.india_days) ORDER BY station_id").to_csv(MART / "station_names.csv", index=False)
    ch.query_df("SELECT * FROM heat.station_season ORDER BY station_id, year").to_csv(MART / "station_season.csv", index=False)
    print("wrote docs/issue_log.csv and the coverage tables")


if __name__ == "__main__":
    main()
