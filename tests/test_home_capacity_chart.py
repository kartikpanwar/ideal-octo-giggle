"""build_team_capacity_chart_options() turns team_capacity_by_month() output
into a stacked bar (by strategy item) + available-time line chart."""

from __future__ import annotations

from datetime import date

from app.pages.home import (
    AVAILABLE_LINE_COLOR,
    UNASSIGNED_COLOR,
    build_team_capacity_chart_options,
)


def _capacity(months=None, strategy_items=None, effort=None, available=None):
    return {
        "months": months or [],
        "strategy_items": strategy_items or [],
        "effort": effort or [],
        "available": available or [],
    }


def test_no_months_returns_none():
    assert build_team_capacity_chart_options(_capacity()) is None


def test_no_strategy_items_returns_none():
    capacity = _capacity(months=[date(2026, 9, 1)])
    assert build_team_capacity_chart_options(capacity) is None


def test_bar_series_one_per_strategy_item_plus_available_line():
    capacity = _capacity(
        months=[date(2026, 9, 1)],
        strategy_items=[{"id": 1, "name": "Onboarding"}, {"id": 2, "name": "Platform"}],
        effort=[
            {"month": date(2026, 9, 1), "strategy_item_id": 1, "effort_weeks": 3.0},
            {"month": date(2026, 9, 1), "strategy_item_id": 2, "effort_weeks": 2.0},
        ],
        available=[{"month": date(2026, 9, 1), "available_weeks": 8.0}],
    )
    options = build_team_capacity_chart_options(capacity)
    series_names = [s["name"] for s in options["series"]]
    assert series_names == ["Onboarding", "Platform", "Total available"]


def test_bar_series_are_stacked_line_is_not():
    capacity = _capacity(
        months=[date(2026, 9, 1)],
        strategy_items=[{"id": 1, "name": "Onboarding"}],
        effort=[{"month": date(2026, 9, 1), "strategy_item_id": 1, "effort_weeks": 3.0}],
        available=[{"month": date(2026, 9, 1), "available_weeks": 8.0}],
    )
    options = build_team_capacity_chart_options(capacity)
    bar, line = options["series"]
    assert bar["type"] == "bar" and bar["stack"] == "capacity"
    assert line["type"] == "line" and "stack" not in line


def test_missing_month_defaults_to_zero_effort():
    capacity = _capacity(
        months=[date(2026, 9, 1), date(2026, 10, 1)],
        strategy_items=[{"id": 1, "name": "Onboarding"}],
        effort=[{"month": date(2026, 9, 1), "strategy_item_id": 1, "effort_weeks": 3.0}],
        available=[
            {"month": date(2026, 9, 1), "available_weeks": 8.0},
            {"month": date(2026, 10, 1), "available_weeks": 8.0},
        ],
    )
    options = build_team_capacity_chart_options(capacity)
    assert options["series"][0]["data"] == [3.0, 0.0]  # Sep has data, Oct doesn't


def test_unassigned_gets_fixed_neutral_colour():
    capacity = _capacity(
        months=[date(2026, 9, 1)],
        strategy_items=[{"id": 1, "name": "Onboarding"}, {"id": None, "name": "Unassigned"}],
        effort=[
            {"month": date(2026, 9, 1), "strategy_item_id": 1, "effort_weeks": 3.0},
            {"month": date(2026, 9, 1), "strategy_item_id": None, "effort_weeks": 1.0},
        ],
        available=[{"month": date(2026, 9, 1), "available_weeks": 8.0}],
    )
    options = build_team_capacity_chart_options(capacity)
    unassigned_series = next(s for s in options["series"] if s["name"] == "Unassigned")
    assert unassigned_series["itemStyle"]["color"] == UNASSIGNED_COLOR


def test_month_labels_formatted_mmm_yy():
    capacity = _capacity(
        months=[date(2026, 9, 1), date(2027, 1, 1)],
        strategy_items=[{"id": 1, "name": "Onboarding"}],
        effort=[{"month": date(2026, 9, 1), "strategy_item_id": 1, "effort_weeks": 1.0}],
        available=[
            {"month": date(2026, 9, 1), "available_weeks": 8.0},
            {"month": date(2027, 1, 1), "available_weeks": 8.0},
        ],
    )
    options = build_team_capacity_chart_options(capacity)
    assert options["xAxis"]["data"] == ["Sep-26", "Jan-27"]


def test_available_line_uses_fixed_colour():
    capacity = _capacity(
        months=[date(2026, 9, 1)],
        strategy_items=[{"id": 1, "name": "Onboarding"}],
        effort=[{"month": date(2026, 9, 1), "strategy_item_id": 1, "effort_weeks": 1.0}],
        available=[{"month": date(2026, 9, 1), "available_weeks": 8.0}],
    )
    options = build_team_capacity_chart_options(capacity)
    line = next(s for s in options["series"] if s["name"] == "Total available")
    assert line["itemStyle"]["color"] == AVAILABLE_LINE_COLOR
    assert line["data"] == [8.0]
