"""IMD's rules at their exact boundaries, run inside ClickHouse so the tested code is the code that counts.

A rule that is off by a tenth of a degree would change every heatwave count, and no reconciliation would show it.
"""
import pytest

PLAINS, HILLS, COAST = "plains", "hills", "coastal"

# tmax and departure are in tenths of a degree C, as stored.
HEAT_CASES = [
    # Below the 40 C floor nothing counts on the plains, however far above normal.
    (399, 90, PLAINS, 0),
    # At the floor, the departure decides: 4.5 to 6.4 is a heatwave, above 6.4 is severe.
    (400, 44, PLAINS, 0),
    (400, 45, PLAINS, 1),
    (400, 64, PLAINS, 1),
    (400, 65, PLAINS, 2),
    # From 45 C outright, a heatwave whatever the departure; from 47 C, severe.
    (449, 10, PLAINS, 0),
    (450, 10, PLAINS, 1),
    (469, 10, PLAINS, 1),
    (470, 10, PLAINS, 2),
    # Hills use a 30 C floor and the same departures.
    (299, 90, HILLS, 0),
    (300, 45, HILLS, 1),
    (300, 65, HILLS, 2),
    # The outright rule is for the plains only.
    (450, 10, HILLS, 0),
    # Coastal stations use 37 C and 4.5, and IMD defines no severe level for them.
    (369, 90, COAST, 0),
    (370, 44, COAST, 0),
    (370, 45, COAST, 1),
    (370, 90, COAST, 1),
    (480, 10, COAST, 0),
]

NIGHT_CASES = [
    # Only counts when the maximum reached 40 C.
    (399, 90, 0),
    (400, 44, 0),
    (400, 45, 1),
    (400, 64, 1),
    (400, 65, 2),
]


@pytest.mark.parametrize("tmax, departure, station_class, expected", HEAT_CASES)
def test_heat_level(ch, tmax, departure, station_class, expected):
    got = ch.command(f"SELECT imd_heat_level(toInt32({tmax}), toInt32({departure}), '{station_class}')")
    assert int(got) == expected


@pytest.mark.parametrize("tmax, departure, expected", NIGHT_CASES)
def test_warm_night(ch, tmax, departure, expected):
    assert int(ch.command(f"SELECT imd_warm_night(toInt32({tmax}), toInt32({departure}))")) == expected


def test_missing_reading_is_never_a_heatwave(ch):
    assert int(ch.command("SELECT imd_heat_level(CAST(NULL AS Nullable(Int32)), toInt32(90), 'plains')")) == 0
    assert int(ch.command("SELECT imd_warm_night(toInt32(450), CAST(NULL AS Nullable(Int32)))")) == 0


def test_every_heat_level_in_the_table_agrees_with_the_rule(ch):
    """The stored levels must be what the function returns for the stored values."""
    bad = ch.command(
        """
        SELECT count() FROM heat.heatwave_days
        WHERE heat_level != imd_heat_level(tmax, tmax_departure, station_class)
        """
    )
    assert int(bad) == 0


def test_no_heatwave_below_the_floor(ch):
    bad = ch.command(
        """
        SELECT count() FROM heat.heatwave_days
        WHERE heat_level > 0 AND tmax < multiIf(station_class = 'plains', 400, station_class = 'coastal', 370, 300)
        """
    )
    assert int(bad) == 0
