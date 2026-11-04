"""Write dashboard/india_heat.json, the Grafana dashboard, from one readable definition.

Layout and colours follow the Stitch design in docs/design/stitch_design_tokens.md: summary first, then the
map, then one panel per question, then data quality. Colour appears only on data.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
DATASOURCE = {"type": "grafana-clickhouse-datasource", "uid": "clickhouse"}
BLUE, ORANGE, RED, GREY, AQUA = "#2a78d6", "#eb6834", "#d03b3b", "#a8a6a0", "#1baf7a"
INK = "#191c1e"


class Board:
    def __init__(self) -> None:
        self.panels: list[dict] = []
        self.next_id = 1

    def add(self, kind: str, title: str, sql: str | None, x: int, y: int, w: int, h: int, description: str = "", options: dict | None = None, field: dict | None = None, overrides: list | None = None, transformations: list | None = None, query_format: int = 1) -> None:
        panel = {
            "id": self.next_id,
            "type": kind,
            "title": title,
            "description": description,
            "gridPos": {"x": x, "y": y, "w": w, "h": h},
            "datasource": DATASOURCE,
            "options": options or {},
            "fieldConfig": {"defaults": field or {}, "overrides": overrides or []},
            "transformations": transformations or [],
            "targets": [],
        }
        if sql:
            panel["targets"] = [{"datasource": DATASOURCE, "editorType": "sql", "format": query_format, "queryType": "table", "rawSql": sql, "refId": "A"}]
        self.panels.append(panel)
        self.next_id += 1


def fixed(color: str) -> dict:
    return {"mode": "fixed", "fixedColor": color}


def stat(board: Board, title: str, metric: str, x: int, y: int, unit: str, description: str, decimals: int = 0, color: str = INK) -> None:
    board.add(
        "stat", title, f"SELECT value FROM heat.dash_summary WHERE metric = '{metric}'",
        x, y, 6, 4, description,
        options={"colorMode": "value", "graphMode": "none", "justifyMode": "auto", "textMode": "value", "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
        field={"unit": unit, "decimals": decimals, "color": fixed(color), "thresholds": {"mode": "absolute", "steps": [{"color": color, "value": None}]}},
    )


def lines(board: Board, title: str, sql: str, x: int, y: int, w: int, h: int, description: str, color: str = BLUE, axis_label: str = "", overrides: list | None = None) -> None:
    board.add(
        "timeseries", title, sql, x, y, w, h, description,
        options={"legend": {"displayMode": "list", "placement": "bottom", "showLegend": bool(overrides)}, "tooltip": {"mode": "multi", "sort": "none"}},
        field={"color": fixed(color), "custom": {"lineWidth": 2, "fillOpacity": 0, "showPoints": "never", "spanNulls": False, "axisLabel": axis_label, "axisCenteredZero": False, "drawStyle": "line"}},
        overrides=overrides or [],
        query_format=0,
    )


def bars(board: Board, title: str, sql: str, x: int, y: int, w: int, h: int, description: str, x_field: str, color: str = BLUE, orientation: str = "auto", unit: str = "", decimals: int | None = None, show_value: str = "auto", color_by: str | None = None, axis_label: str = "", min_value: float | None = None, legend: bool = False, overrides: list | None = None, field_extra: dict | None = None) -> None:
    options = {"xField": x_field, "orientation": orientation, "barWidth": 0.7, "groupWidth": 0.7, "showValue": show_value, "stacking": "none", "legend": {"displayMode": "list", "placement": "bottom", "showLegend": legend}, "tooltip": {"mode": "single"}, "xTickLabelRotation": 0, "xTickLabelSpacing": 0}
    if color_by:
        options["colorByField"] = color_by
    field = {"color": fixed(color), "unit": unit, "custom": {"axisLabel": axis_label, "fillOpacity": 90, "lineWidth": 0, "gradientMode": "none"}}
    if decimals is not None:
        field["decimals"] = decimals
    if min_value is not None:
        field["min"] = min_value
    field.update(field_extra or {})
    board.add("barchart", title, sql, x, y, w, h, description, options=options, field=field, overrides=overrides or [])


def text(board: Board, content: str, x: int, y: int, w: int, h: int) -> None:
    board.add("text", "", None, x, y, w, h, options={"mode": "markdown", "content": content})
    board.panels[-1]["transparent"] = True
    del board.panels[-1]["datasource"]


def build() -> dict:
    b = Board()
    y = 0
    text(b, "## India's Heat Record\nWeather stations with complete records, 1982 to 2024. This describes these stations, not all of India. Source: NOAA GHCN-Daily through ClickHouse, with NOAA's raw files from September 2022 on. Normals: 1991-2020.", 0, y, 24, 3)
    y += 3
    stat(b, "Rise in heatwave days, as recorded", "change_recorded_pct", 0, y, "percent", "Change from 1982-89 to the 2010s at 28 stations, each compared with itself.", color=GREY)
    stat(b, "With every repeat removed", "change_no_repeat_pct", 6, y, "percent", "The same change without readings identical to the day before. This over-corrects, because it also drops genuine hot days.", color=BLUE)
    stat(b, "At stations the artefact never touched", "change_clean_pct", 12, y, "percent", "The fairest test, from 10 stations whose records never had the problem. The interval is wide.", color=ORANGE)
    stat(b, "Stations hit by the reporting artefact", "stations_hit", 18, y, "none", "Of 79 stations with data on both sides of 2011.")
    y += 4

    b.add(
        "geomap", "Warming rate by station, °C per decade, 1982-2024",
        "SELECT name, state, lat, lon, round(mean_rate, 2) AS rate, round(tmax_rate, 2) AS days, round(tmin_rate, 2) AS nights, months, if(suspect = 1, 'Check: day and night rates differ widely', 'OK') AS flag FROM heat.dash_station_rates",
        0, y, 14, 20, "Blue to red is cool to warm.",
        options={
            "view": {"id": "coords", "lat": 22.8, "lon": 82.5, "zoom": 4.75, "allLayers": True},
            "controls": {"showZoom": False, "mouseWheelZoom": False, "showAttribution": False, "showScale": False, "showMeasure": False, "showDebug": False},
            "tooltip": {"mode": "details"},
            "basemap": {"type": "xyz", "name": "Blank", "config": {"url": "/public/maps/blank_tile.png", "attribution": ""}},
            "layers": [
                {"type": "geojson", "name": "India", "tooltip": False, "config": {"src": "public/maps/india_states.geojson", "style": {"color": {"fixed": "#a8a6a0"}, "opacity": 0.25, "symbol": {"fixed": "", "mode": "fixed"}, "size": {"fixed": 1, "max": 1, "min": 1}}, "showLegend": False}},
                {"type": "markers", "name": "Stations", "tooltip": True, "location": {"mode": "coords", "latitude": "lat", "longitude": "lon"}, "config": {"showLegend": True, "style": {"color": {"field": "rate", "fixed": BLUE}, "opacity": 1, "size": {"fixed": 9, "max": 9, "min": 9}, "symbol": {"fixed": "img/icons/marker/circle.svg", "mode": "fixed"}}}},
            ],
        },
        field={"color": {"mode": "thresholds"}, "decimals": 2, "thresholds": {"mode": "absolute", "steps": [{"color": BLUE, "value": None}, {"color": "#d9d7d0", "value": -0.1}, {"color": "#efb0a8", "value": 0.1}, {"color": "#e07a70", "value": 0.25}, {"color": RED, "value": 0.4}]}},
    )
    b.add(
        "table", "Stations ranked by warming rate",
        "SELECT name AS Station, state AS State, round(mean_rate, 2) AS `Rate`, round(ci_low, 2) AS `Low`, round(ci_high, 2) AS `High`, multiIf(repeat_group = 'jumped', 'Stepped at 2011', repeat_group = 'early', 'Stepped around 1990', repeat_group = 'clean', 'Never affected', '') AS `Repeats` FROM heat.dash_station_rates ORDER BY mean_rate DESC",
        14, y, 10, 20, "95% interval widened for month-to-month correlation. Repeats is when the reporting artefact reached the station.",
        options={"showHeader": True, "cellHeight": "sm"},
        field={"custom": {"align": "auto"}, "decimals": 2},
        overrides=[
            {"matcher": {"id": "byName", "options": "Station"}, "properties": [{"id": "custom.width", "value": 170}]},
            {"matcher": {"id": "byName", "options": "State"}, "properties": [{"id": "custom.width", "value": 118}]},
            {"matcher": {"id": "byName", "options": "Rate"}, "properties": [{"id": "custom.width", "value": 62}]},
            {"matcher": {"id": "byName", "options": "Low"}, "properties": [{"id": "custom.width", "value": 62}]},
            {"matcher": {"id": "byName", "options": "High"}, "properties": [{"id": "custom.width", "value": 62}]},
        ],
    )
    y += 20

    lines(b, "Repeated maximums switch on and off by group, while minimums never move", "SELECT toDateTime(makeDate(toUInt16(year), 1, 1)) AS time, avgIf(tmax_share, repeat_group = 'jumped') AS `Stepped at 2011`, avgIf(tmax_share, repeat_group = 'early') AS `Stepped around 1990`, avgIf(tmax_share, repeat_group = 'clean') AS `Never affected`, avgIf(tmin_share, repeat_group = 'jumped') AS `Minimums, 2011 group` FROM heat.dash_repeats WHERE tmax_days >= 500 GROUP BY year ORDER BY year", 0, y, 12, 9, "A natural repeat covers about 4% of days. 22 of the 23 stations that step at 2011 are in the area of IMD's Chennai centre.", axis_label="%", overrides=[
        {"matcher": {"id": "byName", "options": "Stepped at 2011"}, "properties": [{"id": "color", "value": fixed(ORANGE)}]},
        {"matcher": {"id": "byName", "options": "Stepped around 1990"}, "properties": [{"id": "color", "value": fixed(AQUA)}]},
        {"matcher": {"id": "byName", "options": "Never affected"}, "properties": [{"id": "color", "value": fixed(BLUE)}]},
        {"matcher": {"id": "byName", "options": "Minimums, 2011 group"}, "properties": [{"id": "color", "value": fixed(GREY)}, {"id": "custom.lineStyle", "value": {"fill": "dash", "dash": [4, 3]}}]},
    ])
    b.add(
        "barchart", "Q1. Heatwave days per station per hot season",
        "SELECT period, avg(heatwave_days) AS `As recorded`, avg(heatwave_days_no_repeat) AS `Repeats removed` FROM heat.dash_heat_periods WHERE period != '2020-24' GROUP BY period ORDER BY period = '1982-89' DESC, period",
        12, y, 12, 9, "28 stations, each compared with itself. Removing every repeat over-corrects. Few stations have complete seasons after 2015, so 2020-24 is left out.",
        options={"xField": "period", "orientation": "auto", "barWidth": 0.7, "groupWidth": 0.7, "showValue": "auto", "stacking": "none", "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True}, "tooltip": {"mode": "multi"}, "xTickLabelRotation": 0},
        field={"decimals": 2, "custom": {"fillOpacity": 90, "lineWidth": 0}, "min": 0},
        overrides=[
            {"matcher": {"id": "byName", "options": "As recorded"}, "properties": [{"id": "color", "value": fixed(GREY)}]},
            {"matcher": {"id": "byName", "options": "Repeats removed"}, "properties": [{"id": "color", "value": fixed(BLUE)}]},
        ],
    )
    y += 9

    b.add(
        "barchart", "Q2. Days against nights: warming rate at each station, °C per decade",
        "SELECT name, round(tmax_rate, 2) AS `Days (maximum)`, round(tmin_rate, 2) AS `Nights (minimum)` FROM heat.dash_station_rates ORDER BY tmin_rate - tmax_rate",
        0, y, 12, 11, "1982-2024. Stations are ordered from days furthest ahead to nights furthest ahead.",
        options={"xField": "name", "orientation": "auto", "barWidth": 0.8, "groupWidth": 0.8, "showValue": "never", "stacking": "none", "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True}, "tooltip": {"mode": "multi"}, "xTickLabelRotation": -60, "xTickLabelSpacing": 0},
        field={"custom": {"fillOpacity": 90, "lineWidth": 0}},
        overrides=[
            {"matcher": {"id": "byName", "options": "Days (maximum)"}, "properties": [{"id": "color", "value": fixed(BLUE)}]},
            {"matcher": {"id": "byName", "options": "Nights (minimum)"}, "properties": [{"id": "color", "value": fixed(ORANGE)}]},
        ],
    )
    lines(b, "Q3. First 40°C of the year, days from each station's usual date", "SELECT toDateTime(makeDate(toUInt16(year), 1, 1)) AS time, if(stations >= 5, median_shift, NULL) AS `Median across stations (days)` FROM heat.dash_first_40c ORDER BY year", 12, y, 12, 11, "Negative is earlier. The year-to-year swing dwarfs any drift.", axis_label="days")
    y += 11

    bars(b, "Q4. Rainy days per season, 1901-1970", "SELECT concat(toString(decade_start), '-', leftPad(toString((decade_start + 9) % 100), 2, '0')) AS decade, round(rainy_days, 1) AS `Rainy days` FROM heat.dash_gauge_decades ORDER BY decade_start", 0, y, 8, 9, "Station average at rain gauges with at least 56 of 70 complete seasons.", "decade", min_value=0, show_value="always", decimals=1)
    bars(b, "Heavy days (100 mm or more) per season", "SELECT concat(toString(decade_start), '-', leftPad(toString((decade_start + 9) % 100), 2, '0')) AS decade, round(heavy_days, 2) AS `Heavy days` FROM heat.dash_gauge_decades ORDER BY decade_start", 8, y, 8, 9, "Shown apart from rainy days because the scales differ.", "decade", color=ORANGE, min_value=0, show_value="always", decimals=2)
    bars(b, "Why rain after 1972 is set aside", "SELECT era AS Era, round(season_mm) AS `June-September mm as reported` FROM heat.dash_water_balance", 16, y, 8, 9, "The same 70 stations by era. A monsoon cannot fall this far and recover, so this is a change in reporting.", "Era", color=GREY, min_value=0, show_value="always")
    y += 9

    bars(
        b, "Q6. Countries by median warming rate, 1982-2021",
        "SELECT name AS Country, round(median_rate, 2) AS `°C per decade`, if(country = 'IN', 1, 0) AS is_india FROM heat.dash_countries ORDER BY median_rate DESC",
        0, y, 12, 20, "Countries with at least 5 qualifying stations. The same rule applies to every country.", "Country", orientation="horizontal", color_by="is_india", show_value="always", decimals=2,
        field_extra={"color": {"mode": "thresholds"}, "thresholds": {"mode": "absolute", "steps": [{"color": GREY, "value": None}, {"color": ORANGE, "value": 1}]}},
        overrides=[{"matcher": {"id": "byName", "options": "is_india"}, "properties": [{"id": "custom.hideFrom", "value": {"legend": True, "tooltip": True, "viz": True}}]}],
    )
    b.add(
        "table", "Benchmark: median seconds on warm runs, 4 threads, 3 GB",
        "SELECT question AS Question, nullIf(maxIf(seconds, engine = 'clickhouse_raw'), 0) AS `ClickHouse raw`, nullIf(maxIf(seconds, engine = 'clickhouse_rollup'), 0) AS `ClickHouse rollup`, nullIf(maxIf(seconds, engine = 'duckdb_parquet'), 0) AS `DuckDB Parquet` FROM heat.dash_benchmark WHERE run = 'median_warm' GROUP BY question ORDER BY question",
        12, y, 12, 8, "Same limits on every engine. A blank means the query has no version for that engine.",
        options={"showHeader": True, "cellHeight": "sm"}, field={"decimals": 2},
        overrides=[
            {"matcher": {"id": "byName", "options": "Question"}, "properties": [{"id": "custom.width", "value": 340}]},
            {"matcher": {"id": "byName", "options": "ClickHouse raw"}, "properties": [{"id": "custom.width", "value": 125}]},
            {"matcher": {"id": "byName", "options": "ClickHouse rollup"}, "properties": [{"id": "custom.width", "value": 135}]},
        ],
    )
    b.add(
        "table", "Does the result depend on the choices made?",
        "SELECT scenario AS Scenario, stations AS Stations, change_recorded_pct AS `Recorded %`, change_no_repeat_pct AS `Repeats removed %` FROM heat.dash_sensitivity",
        12, y + 8, 12, 12, "Change in heatwave days from 1982-89 to the 2010s under each assumption.",
        options={"showHeader": True, "cellHeight": "sm"}, field={"custom": {"align": "auto"}},
        overrides=[
            {"matcher": {"id": "byName", "options": "Scenario"}, "properties": [{"id": "custom.width", "value": 440}]},
            {"matcher": {"id": "byName", "options": "Stations"}, "properties": [{"id": "custom.width", "value": 70}]},
            {"matcher": {"id": "byName", "options": "Recorded %"}, "properties": [{"id": "custom.width", "value": 105}]},
        ],
    )
    y += 20

    lines(b, "Station coverage: Indian stations reporting each year", "SELECT toDateTime(makeDate(toUInt16(year), 1, 1)) AS time, stations_rain AS `Reporting rain`, stations_tmax AS `Reporting maximum temperature` FROM heat.dash_coverage WHERE year >= 1970 ORDER BY year", 0, y, 12, 15, "Rain falls from over 2,400 stations to under 100 in the early 1970s. Temperature effectively starts in 1973.", overrides=[
        {"matcher": {"id": "byName", "options": "Reporting rain"}, "properties": [{"id": "color", "value": fixed(BLUE)}]},
        {"matcher": {"id": "byName", "options": "Reporting maximum temperature"}, "properties": [{"id": "color", "value": fixed(ORANGE)}]},
    ])
    b.add(
        "table", "Data-quality log: checks by severity",
        "SELECT check AS Check, severity AS Severity, count() AS Rows, sum(count) AS Count, any(description) AS `What was checked` FROM heat.dash_issue_log GROUP BY check, severity ORDER BY check",
        12, y, 12, 15, "Every check is listed, including those that passed. The full per-station log is docs/issue_log.csv.",
        options={"showHeader": True, "cellHeight": "sm"},
        field={"custom": {"align": "auto"}},
        overrides=[
            {"matcher": {"id": "byName", "options": "Severity"}, "properties": [
                {"id": "mappings", "value": [{"type": "value", "options": {"high": {"color": "#d03b3b", "index": 0, "text": "High"}, "medium": {"color": "#ec835a", "index": 1, "text": "Medium"}, "low": {"color": "#898781", "index": 2, "text": "Low"}, "info": {"color": "#898781", "index": 3, "text": "Info"}}}]},
                {"id": "custom.cellOptions", "value": {"type": "color-text"}},
                {"id": "custom.width", "value": 90},
            ]},
            {"matcher": {"id": "byName", "options": "Check"}, "properties": [{"id": "custom.width", "value": 70}]},
            {"matcher": {"id": "byName", "options": "Rows"}, "properties": [{"id": "custom.width", "value": 60}]},
            {"matcher": {"id": "byName", "options": "Count"}, "properties": [{"id": "custom.width", "value": 100}]},
        ],
    )

    return {
        "uid": "india-heat",
        "title": "India's Heat Record",
        "tags": ["clickhouse", "ghcn", "india"],
        "timezone": "utc",
        "schemaVersion": 41,
        "version": 1,
        "editable": False,
        "graphTooltip": 0,
        "liveNow": False,
        "refresh": "",
        "time": {"from": "1970-01-01T00:00:00.000Z", "to": "2025-06-30T00:00:00.000Z"},
        "timepicker": {"hidden": True},
        "templating": {"list": []},
        "annotations": {"list": []},
        "links": [],
        "panels": b.panels,
    }


def main() -> None:
    (HERE / "india_heat.json").write_text(json.dumps(build(), indent=2), encoding="utf8")
    print("wrote dashboard/india_heat.json")


if __name__ == "__main__":
    main()
