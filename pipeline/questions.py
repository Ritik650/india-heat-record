"""Answer the six questions in SQL and save each result to data/mart.

Each file in sql/questions becomes one CSV of the same name. Interpreting them is findings.py's job.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import MART, SQL, client  # noqa: E402

# The raw variant of Q6 repeats the rollup's answer at far higher cost, so it runs only in the tests and the benchmark.
SKIP = {"q6_country_rates_raw"}


def main() -> None:
    ch = client()
    MART.mkdir(parents=True, exist_ok=True)
    for path in sorted((SQL / "questions").glob("*.sql")):
        if path.stem in SKIP:
            continue
        started = time.time()
        frame = ch.query_df(path.read_text(encoding="utf8").strip().rstrip(";"))
        frame.to_csv(MART / f"{path.stem}.csv", index=False)
        print(f"{path.stem}: {len(frame):,} rows, {time.time() - started:.1f}s")


if __name__ == "__main__":
    main()
