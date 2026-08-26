"""build_allocation_heatmap_options() turns weekly_allocation() rows into a
dense week x person ECharts heatmap grid."""

from __future__ import annotations

from datetime import date

from app.pages.people import HEATMAP_MAX, build_allocation_heatmap_options


def test_no_rows_returns_none():
    assert build_allocation_heatmap_options([{"id": 1, "name": "Sam"}], []) is None


def test_no_members_returns_none():
    rows = [{"member_id": 1, "week_start": date(2026, 9, 7), "pct": 50.0}]
    assert build_allocation_heatmap_options([], rows) is None


def test_grid_is_dense_missing_combos_default_to_zero():
    # Two members, but only one has a row for the single week present.
    members = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Ben"}]
    rows = [{"member_id": 1, "week_start": date(2026, 9, 7), "pct": 60.0}]
    options = build_allocation_heatmap_options(members, rows)
    series_data = options["series"][0]["data"]
    assert len(series_data) == 2  # 2 members x 1 week, dense

    # Ben (index 1) has no row -> his single cell should be 0%.
    ben_cell = next(d for d in series_data if d["value"][1] == 1)
    assert ben_cell["value"][2] == 0.0
    assert "0% allocated" in ben_cell["name"]


def test_axis_data_matches_members_and_sorted_weeks():
    members = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Ben"}]
    rows = [
        {"member_id": 1, "week_start": date(2026, 9, 14), "pct": 10.0},
        {"member_id": 1, "week_start": date(2026, 8, 31), "pct": 20.0},
    ]
    options = build_allocation_heatmap_options(members, rows)
    assert options["yAxis"]["data"] == ["Alice", "Ben"]
    assert options["xAxis"]["data"] == ["Aug 31", "Sep 14"]  # sorted ascending


def test_cell_value_clamped_but_tooltip_shows_true_pct():
    members = [{"id": 1, "name": "Alice"}]
    rows = [{"member_id": 1, "week_start": date(2026, 9, 7), "pct": 180.0}]
    options = build_allocation_heatmap_options(members, rows)
    cell = options["series"][0]["data"][0]
    assert cell["value"][2] == HEATMAP_MAX  # colour clamped
    assert "180% allocated" in cell["name"]  # tooltip uncapped


def test_visual_map_range_matches_heatmap_max():
    members = [{"id": 1, "name": "Alice"}]
    rows = [{"member_id": 1, "week_start": date(2026, 9, 7), "pct": 50.0}]
    options = build_allocation_heatmap_options(members, rows)
    assert options["visualMap"]["min"] == 0
    assert options["visualMap"]["max"] == HEATMAP_MAX
