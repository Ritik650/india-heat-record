"""Checks that nothing was lost or double-counted between the Parquet, the raw table and the rollups."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PARQUET_ROWS = 1_074_089_837


def scalar(ch, sql):
    return ch.command(sql)


def test_every_parquet_row_loaded(ch):
    assert int(scalar(ch, "SELECT count() FROM heat.noaa")) == PARQUET_ROWS


def test_date_range_is_the_one_documented(ch):
    assert str(scalar(ch, "SELECT min(date) FROM heat.noaa")) == "1900-01-01"
    assert str(scalar(ch, "SELECT max(date) FROM heat.noaa")) == "2022-09-07"


@pytest.mark.parametrize("rollup", ["station_year"])
def test_rollup_rows_add_up_to_the_raw_table(ch, rollup):
    assert int(scalar(ch, f"SELECT sum(days_obs) FROM heat.{rollup}")) == PARQUET_ROWS


def test_yearly_rollup_matches_a_direct_aggregate(ch):
    """Materialized views saw the rows in blocks, so compare them with one direct scan."""
    raw = ch.query(
        """
        SELECT countIf(tempMax != 0), countIf(tempMin != 0), countIf(tempMax >= 400), countIf(precipitation >= 1000), sum(tempMax), sum(tempMin), sum(precipitation)
        FROM heat.noaa
        """
    ).result_rows[0]
    rollup = ch.query(
        "SELECT sum(tmax_days), sum(tmin_days), sum(days_40c), sum(heavy_rain_days), sum(sum_tmax), sum(sum_tmin), sum(sum_precip) FROM heat.station_year"
    ).result_rows[0]
    assert tuple(raw) == tuple(rollup)


def test_monthly_rollup_matches_the_yearly_rollup(ch):
    monthly = ch.query("SELECT sum(tmax_days), sum(tmin_days), sum(sum_tmax), sum(sum_tmin) FROM heat.station_month").result_rows[0]
    yearly = ch.query("SELECT sum(tmax_days), sum(tmin_days), sum(sum_tmax), sum(sum_tmin) FROM heat.station_year").result_rows[0]
    assert tuple(monthly) == tuple(yearly)


def test_rollup_answers_q6_exactly_as_the_raw_table_does(ch):
    """The rollup's whole point is the same answer for less work, so hold it to the same answer."""
    rollup = ch.query_df((ROOT / "sql/questions/q6_country_rates_rollup.sql").read_text(encoding="utf8").strip().rstrip(";"))
    raw = ch.query_df((ROOT / "sql/questions/q6_country_rates_raw.sql").read_text(encoding="utf8").strip().rstrip(";"))
    assert len(rollup) == len(raw) > 0
    merged = rollup.merge(raw, on="station_id", suffixes=("_rollup", "_raw"), validate="one_to_one")
    assert len(merged) == len(rollup)
    assert (merged.rate_per_decade_rollup - merged.rate_per_decade_raw).abs().max() < 1e-6


def test_every_indian_parquet_reading_reached_the_analysis_table(ch):
    parquet = int(scalar(ch, "SELECT countIf(tempMax != 0) FROM heat.noaa WHERE station_id LIKE 'IN%'"))
    analysis = int(scalar(ch, "SELECT count(tmax) FROM heat.india_days WHERE origin = 'parquet'"))
    assert parquet == analysis


def test_analysis_table_has_one_row_per_station_day(ch):
    assert int(scalar(ch, "SELECT count() - uniqExact(station_id, date) FROM heat.india_days")) == 0


def test_like_and_substring_select_the_same_rows(ch):
    """The benchmark compares these two filters, so they must select the same rows."""
    like = int(scalar(ch, "SELECT count() FROM heat.noaa WHERE station_id LIKE 'IN%'"))
    substring = int(scalar(ch, "SELECT count() FROM heat.noaa WHERE substring(station_id, 1, 2) = 'IN'"))
    assert like == substring > 0


def test_normals_cover_every_day_of_the_year(ch):
    """A station short of days would silently lose them in the inner join with its readings."""
    short = ch.query("SELECT station_id, count() AS days FROM heat.station_normals GROUP BY station_id HAVING days != 366").result_rows
    assert short == []


def test_no_normal_is_implausible(ch):
    assert int(scalar(ch, "SELECT count() FROM heat.station_normals WHERE normal_tmax < -200 OR normal_tmax > 480")) == 0


def test_heatwave_join_keeps_every_reading_at_stations_with_normals(ch):
    """An inner join keeps its row count looking healthy while losing matches, so count readings on both sides."""
    readings = int(scalar(ch, "SELECT count(tmax) FROM heat.india_days WHERE station_id IN (SELECT DISTINCT station_id FROM heat.station_normals)"))
    joined = int(scalar(ch, "SELECT count() FROM heat.heatwave_days"))
    assert readings == joined
