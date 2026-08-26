"""build_workstream_person_grid_options() turns workstream_assignments() rows
into a dense workstream x person ECharts heatmap grid."""

from __future__ import annotations

from app.pages.home import build_workstream_person_grid_options


def _row(workstream_id, person_id, effort_weeks, task_count=1, task_names=None):
    return {
        "workstream_id": workstream_id,
        "person_id": person_id,
        "effort_weeks": effort_weeks,
        "task_count": task_count,
        "task_names": task_names or ["Task"],
    }


def test_no_rows_returns_none():
    workstreams = [{"id": 1, "name": "WS1"}]
    members = [{"id": 1, "name": "Alice"}]
    assert build_workstream_person_grid_options(workstreams, members, []) is None


def test_no_workstreams_or_members_returns_none():
    rows = [_row(1, 1, 2.0)]
    assert build_workstream_person_grid_options([], [{"id": 1, "name": "Alice"}], rows) is None
    assert build_workstream_person_grid_options([{"id": 1, "name": "WS1"}], [], rows) is None


def test_grid_is_dense_missing_combos_default_to_zero():
    workstreams = [{"id": 1, "name": "WS1"}, {"id": 2, "name": "WS2"}]
    members = [{"id": 1, "name": "Alice"}]
    rows = [_row(1, 1, 3.0)]
    options = build_workstream_person_grid_options(workstreams, members, rows)
    data = options["series"][0]["data"]
    assert len(data) == 2  # 2 workstreams x 1 member, dense

    ws2_cell = next(d for d in data if d["value"][1] == 1)  # workstream index 1 (WS2)
    assert ws2_cell["value"][2] == 0.0
    assert "0 wks open" in ws2_cell["name"]


def test_axis_orientation_people_columns_workstreams_rows():
    workstreams = [{"id": 1, "name": "Setup"}, {"id": 2, "name": "Ingestion"}]
    members = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Ben"}]
    rows = [_row(1, 1, 2.0)]
    options = build_workstream_person_grid_options(workstreams, members, rows)
    assert options["xAxis"]["data"] == ["Alice", "Ben"]  # people = columns
    assert options["yAxis"]["data"] == ["Setup", "Ingestion"]  # workstreams = rows


def test_heat_max_scales_to_largest_cell():
    workstreams = [{"id": 1, "name": "WS1"}]
    members = [{"id": 1, "name": "Alice"}]
    rows = [_row(1, 1, 4.2)]
    options = build_workstream_person_grid_options(workstreams, members, rows)
    assert options["visualMap"]["max"] == 5  # ceil(4.2)


def test_heat_max_has_a_floor_of_one():
    workstreams = [{"id": 1, "name": "WS1"}]
    members = [{"id": 1, "name": "Alice"}]
    rows = [_row(1, 1, 0.0)]
    options = build_workstream_person_grid_options(workstreams, members, rows)
    assert options["visualMap"]["max"] == 1


def test_tooltip_lists_task_names_and_truncates():
    workstreams = [{"id": 1, "name": "WS1"}]
    members = [{"id": 1, "name": "Alice"}]
    names = [f"Task {i}" for i in range(6)]
    rows = [_row(1, 1, 4.0, task_count=6, task_names=names)]
    options = build_workstream_person_grid_options(workstreams, members, rows)
    tooltip = options["series"][0]["data"][0]["name"]
    assert "Task 0" in tooltip
    assert "Task 3" in tooltip
    assert "Task 4" not in tooltip  # only first 4 shown
    assert "+ 2 more" in tooltip
