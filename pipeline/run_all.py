"""Rebuild everything after the Parquet is loaded. Steps run one at a time, because a second heavy query
during a build is what ran the VM out of memory on the 16 GB laptop this was written on.

Usage: python pipeline/run_all.py [--with-benchmark]
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
STEPS = ["classify_stations", "build_india", "quality", "questions", "findings", "sensitivity", "dashboard_tables", "charts", "brief", "write_readme", "build_site"]


def main() -> None:
    steps = STEPS[:]
    if "--with-benchmark" in sys.argv:
        steps.insert(steps.index("sensitivity"), "benchmark")
    for step in steps:
        path = HERE / f"{step}.py"
        if not path.exists():
            print(f"skipped {step}: not written yet")
            continue
        started = time.time()
        subprocess.run([sys.executable, str(path)], check=True)
        print(f"== {step} done in {time.time() - started:.0f}s", flush=True)


if __name__ == "__main__":
    main()
