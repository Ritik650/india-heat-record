"""The live site against the results. It needs no ClickHouse, so this runs in a fresh clone and in CI."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "site" / "index.html"


@pytest.fixture(scope="module")
def page():
    return PAGE.read_text(encoding="utf8")


@pytest.fixture(scope="module")
def data(page):
    return json.loads(re.search(r"const D = (\{.*?\});\nconst NS", page, re.S).group(1))


@pytest.fixture(scope="module")
def findings():
    return json.loads((ROOT / "data/mart/findings.json").read_text(encoding="utf8"))


def test_every_token_was_filled(page):
    assert "{{" not in page.split("const D =")[0]


def test_stitch_placeholders_did_not_survive(page):
    """Stitch's design came with invented numbers and branding. Only its layout and colours belong here."""
    for placeholder in ("ClimateAnalytics", "Climate Analytics Institute", "lh3.googleusercontent", "cdn.tailwindcss", "Nagpur Sonegaon</td>", "IN009021100"):
        assert placeholder not in page


def test_headline_figures_match_the_results(page, findings):
    q1 = findings["q1_heatwave_days"]
    assert f"{q1['recorded']['change_pct']:+.0f}%" in page
    assert f"{q1['by_repeat_group']['clean']['recorded']['change_pct']:+.0f}%" in page
    assert f"{q1['imd_change_pct']:+.0f}%" in page
    assert f"{findings['scale']['rows']:,}" in page


def test_only_fonts_load_from_elsewhere(page):
    sources = re.findall(r'(?:src|href)="(https?://[^"]+)"', page.split("<body>")[0])
    assert all(url.startswith(("https://fonts.googleapis.com", "https://fonts.gstatic.com")) for url in sources), sources
    assert "<script src=" not in page


def test_every_comparable_station_is_on_the_map(data, findings):
    groups = [s["group"] for s in data["stations"]]
    for key, count in findings["repeats"]["groups"].items():
        assert groups.count(key) == count, key
    assert sum(s["rate"] is not None for s in data["stations"]) == findings["q5_fastest_stations"]["stations"]


def test_stations_sit_inside_the_map(data):
    for station in data["stations"]:
        assert 0 <= station["x"] <= data["map"]["w"] and 0 <= station["y"] <= data["map"]["h"], station["name"]


def test_default_stations_exist(data):
    ids = {s["id"]: s for s in data["stations"]}
    assert ids[data["defaultStation"]]["group"] == "jumped"
    assert ids[data["defaultRateStation"]]["rate"] is not None


def test_every_quality_check_is_shown(data):
    assert [row["check"] for row in data["dq"]] == [f"DQ{i:02d}" for i in range(1, 16)]


def test_site_files_are_in_place():
    """The brief and the sharing image are copied in at deploy, so check what that step copies from."""
    for path in ("site/index.html", "site/.nojekyll", "outputs/india_heat_record_brief.pdf", "outputs/charts/repeat_groups_map.png"):
        assert (ROOT / path).exists(), path
