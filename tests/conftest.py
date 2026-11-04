"""Tests that talk to ClickHouse are skipped when it is not running, so the rest still run in a fresh clone."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))


@pytest.fixture(scope="session")
def ch():
    from common import client

    try:
        connection = client()
        connection.command("SELECT 1 FROM heat.heatwave_days LIMIT 1")
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"ClickHouse with the built tables is not available: {error}")
    return connection
