"""Build the Indian analysis tables: base readings, completeness, normals, heatwave days."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import SQL, client, run_sql_file  # noqa: E402

STEPS = ["03_india_base.sql", "04_normals.sql", "05_heatwave_days.sql"]


def main() -> None:
    ch = client()
    for step in STEPS:
        started = time.time()
        run_sql_file(ch, SQL / step)
        print(f"{step}: {time.time() - started:.1f}s")
    for table in ["india_temp", "india_days", "station_season", "station_normals", "heatwave_days"]:
        print(f"{table}: {ch.command(f'SELECT count() FROM heat.{table}'):,} rows")


if __name__ == "__main__":
    main()
