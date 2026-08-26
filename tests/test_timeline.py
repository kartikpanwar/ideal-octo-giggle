"""build_timeline_options() turns task rows into an ECharts stacked-bar Gantt."""

from __future__ import annotations

from datetime import date

from app.pages.strategy import build_timeline_options


def _task(name, start=None, end=None, status="not_started", effort=2.0, assignee="Sam"):
    return {
        "name": name,
        "status": status,
        "estimated_start": start,
        "estimated_end": end,
        "estimated_effort_weeks": effort,
        "assignee": assignee,
    }


def test_no_dated_tasks_returns_none():
    tasks = [_task("A"), _task("B")]
    assert build_timeline_options(tasks) is None


def test_offsets_relative_to_earliest_start():
    tasks = [
        _task("Second", date(2026, 9, 8), date(2026, 9, 15)),
        _task("First", date(2026, 9, 1), date(2026, 9, 8)),
    ]
    options = build_timeline_options(tasks)
    names = options["yAxis"]["data"]
    offsets = options["series"][0]["data"]
    durations = [d["value"] for d in options["series"][1]["data"]]

    assert names == ["Second", "First"]
    assert offsets == [7, 0]  # Second starts 7 days after the earliest (First)
    assert durations == [7, 7]


def test_undated_tasks_excluded_from_series():
    tasks = [
        _task("Dated", date(2026, 9, 1), date(2026, 9, 8)),
        _task("No dates"),
    ]
    options = build_timeline_options(tasks)
    assert options["yAxis"]["data"] == ["Dated"]


def test_zero_length_task_gets_minimum_visible_duration():
    tasks = [_task("SameDay", date(2026, 9, 1), date(2026, 9, 1))]
    options = build_timeline_options(tasks)
    assert options["series"][1]["data"][0]["value"] == 1


def test_bar_colour_follows_status():
    tasks = [_task("Blocked task", date(2026, 9, 1), date(2026, 9, 5), status="blocked")]
    options = build_timeline_options(tasks)
    assert options["series"][1]["data"][0]["itemStyle"]["color"] == "#e53935"


def test_offset_series_is_invisible_and_silent():
    tasks = [_task("A", date(2026, 9, 1), date(2026, 9, 5))]
    options = build_timeline_options(tasks)
    offset_series = options["series"][0]
    assert offset_series["silent"] is True
    assert offset_series["itemStyle"]["color"] == "transparent"


def test_tooltip_is_plain_text_not_html():
    # ECharts escapes the {b} template substitution before inserting it, so
    # embedding HTML tags (e.g. <br/>) would render as literal text. Line
    # breaks come from \n + the tooltip's white-space:pre-line CSS instead.
    tasks = [_task("Some task", date(2026, 9, 1), date(2026, 9, 5))]
    options = build_timeline_options(tasks)
    tooltip_name = options["series"][1]["data"][0]["name"]
    assert "<" not in tooltip_name
    assert "\n" in tooltip_name
    assert options["tooltip"]["extraCssText"].find("white-space:pre-line") != -1
