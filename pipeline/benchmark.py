"""Run each benchmark question three ways and save the real times, including any query DuckDB wins.

Each run gets the same limits: 4 threads and 3 GB of memory. The first run follows a cleared OS page cache
and cleared ClickHouse mark and query condition caches, and the later runs are warm. Queries run inside Linux,
next to the data.

Usage: python pipeline/benchmark.py [runs]
"""
from __future__ import annotations

import csv
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import MART, ROOT, SQL, client  # noqa: E402

DISTRO = "Ubuntu-20.04"
QUESTIONS = {
    "b1_india_station_years": "India, every station-year, by key prefix",
    "b2_india_filter_no_index": "India, same result, plan's substring filter",
    "b3_one_station_history": "One station's whole history",
    "b4_country_decade_scan": "Every country by decade, full scan",
    "b5_q6_country_rates": "Q6, first version: a join that runs the months step twice",
    "b6_q6_rewritten": "Q6, rewritten: window function, in key order",
}
ENGINES = {"raw": ("clickhouse", "clickhouse_raw"), "rollup": ("clickhouse", "clickhouse_rollup"), "duckdb": ("duckdb", "duckdb_parquet")}


def linux_path(path: Path) -> str:
    drive, rest = str(path.resolve()).split(":", 1)
    return f"/mnt/{drive.lower()}{rest.replace(chr(92), '/')}"


def timed(engine: str, query: Path, mode: str) -> float:
    command = ["wsl", "-d", DISTRO, "--", "bash", linux_path(ROOT / "infra" / "timed_query.sh"), engine, linux_path(query), mode]
    for attempt in range(3):
        result = subprocess.run(command, capture_output=True, text=True, timeout=1800, check=False)
        if result.returncode == 0:
            return float(result.stdout.strip().splitlines()[-1])
        print(f"{query.name} attempt {attempt + 1} failed: {result.stderr[:300]}", flush=True)
    raise RuntimeError(f"{query.name} failed three times")


def storage() -> None:
    ch = client()
    rows = ch.query(
        """
        SELECT table, sum(rows) AS row_count, sum(bytes_on_disk) AS bytes_on_disk, sum(data_uncompressed_bytes) AS uncompressed_bytes, count() AS parts
        FROM system.parts
        WHERE database = 'heat' AND active AND table IN ('noaa', 'station_year', 'station_month')
        GROUP BY table
        """
    ).result_rows
    with open(MART / "storage.csv", "w", newline="", encoding="utf8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["table", "rows", "bytes_on_disk", "uncompressed_bytes", "parts"])
        writer.writerows(rows)


def reads() -> None:
    """The most each ClickHouse query read, which is its cold run: the condition cache cuts later reads."""
    ch = client()
    ch.command("SYSTEM FLUSH LOGS")
    rows = ch.query(
        """
        SELECT log_comment, max(read_rows), max(read_bytes), max(memory_usage)
        FROM system.query_log
        WHERE type = 'QueryFinish' AND log_comment LIKE 'b%.sql' AND event_time > now() - INTERVAL 2 HOUR
        GROUP BY log_comment
        ORDER BY log_comment
        """
    ).result_rows
    with open(MART / "benchmark_reads.csv", "w", newline="", encoding="utf8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["query", "read_rows", "read_bytes", "peak_memory_bytes"])
        writer.writerows(rows)


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    storage()
    results = []
    for stem, label in QUESTIONS.items():
        for suffix, (engine, name) in ENGINES.items():
            query = SQL / "benchmark" / f"{stem}.{suffix}.sql"
            if not query.exists():
                continue
            cold = timed(engine, query, "cold")
            warm = [timed(engine, query, "warm") for _ in range(runs - 1)]
            median = statistics.median(warm)
            print(f"{label:<48} {name:<18} cold {cold:8.3f}s  warm {median:8.3f}s", flush=True)
            results.append({"question": label, "engine": name, "run": "cold", "seconds": round(cold, 3)})
            results.append({"question": label, "engine": name, "run": "median_warm", "seconds": round(median, 3)})
    with open(MART / "benchmark.csv", "w", newline="", encoding="utf8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["question", "engine", "run", "seconds"])
        writer.writeheader()
        writer.writerows(results)
    reads()


if __name__ == "__main__":
    main()
