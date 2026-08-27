"""build_workstream_capacity_check_options() turns workstream_capacity_check()
rows into a bar (allocated) + line (required) chart, coloured per bar by
sufficiency."""

from __future__ import annotations

from app.pages.home import (
    INSUFFICIENT_COLOR,
    SUFFICIENT_COLOR,
    build_workstream_capacity_check_options,
)


def _row(workstream_id, name, allocated_weeks, required_weeks):
    return {
        "workstream_id": workstream_id,
        "name": name,
        "allocated_weeks": allocated_weeks,
        "required_weeks": required_weeks,
        "sufficient": allocated_weeks >= required_weeks,
    }


def test_no_rows_returns_none():
    assert build_workstream_capacity_check_options([]) is None


def test_categories_and_series_values():
    rows = [_row(1, "WS1", 4.0, 3.0), _row(2, "WS2", 1.0, 5.0)]
    options = build_workstream_capacity_check_options(rows)
    assert options["xAxis"]["data"] == ["WS1", "WS2"]
    allocated_series = next(s for s in options["series"] if s["name"] == "Allocated capacity")
    required_series = next(s for s in options["series"] if s["name"] == "Required effort")
    assert [d["value"] for d in allocated_series["data"]] == [4.0, 1.0]
    assert required_series["data"] == [3.0, 5.0]


def test_sufficient_bar_is_green_insufficient_is_red():
    rows = [_row(1, "WS1", 4.0, 3.0), _row(2, "WS2", 1.0, 5.0)]
    options = build_workstream_capacity_check_options(rows)
    allocated_series = next(s for s in options["series"] if s["name"] == "Allocated capacity")
    assert allocated_series["data"][0]["itemStyle"]["color"] == SUFFICIENT_COLOR
    assert allocated_series["data"][1]["itemStyle"]["color"] == INSUFFICIENT_COLOR


def test_exactly_equal_counts_as_sufficient():
    rows = [_row(1, "WS1", 3.0, 3.0)]
    options = build_workstream_capacity_check_options(rows)
    allocated_series = next(s for s in options["series"] if s["name"] == "Allocated capacity")
    assert allocated_series["data"][0]["itemStyle"]["color"] == SUFFICIENT_COLOR
