"""build_person_allocation_chart_options() turns workstream_allocation_pct()
rows into a stacked per-person % allocation bar chart, with an over-allocation
mark and a 100%-reference markLine."""

from __future__ import annotations

from app.pages.home import OVER_ALLOCATED_MARK, build_person_allocation_chart_options


def _row(team_member_id, workstream_id, pct):
    return {"team_member_id": team_member_id, "workstream_id": workstream_id, "allocation_pct": pct}


MEMBERS = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Ben"}]
WORKSTREAMS = [{"id": 1, "name": "WS1"}, {"id": 2, "name": "WS2"}]


def test_no_rows_returns_none():
    assert build_person_allocation_chart_options(MEMBERS, WORKSTREAMS, []) is None


def test_no_members_or_workstreams_returns_none():
    rows = [_row(1, 1, 50.0)]
    assert build_person_allocation_chart_options([], WORKSTREAMS, rows) is None
    assert build_person_allocation_chart_options(MEMBERS, [], rows) is None


def test_only_workstreams_with_an_allocation_get_a_series():
    rows = [_row(1, 1, 50.0)]
    options = build_person_allocation_chart_options(MEMBERS, WORKSTREAMS, rows)
    series_names = [s["name"] for s in options["series"]]
    assert "WS1" in series_names
    assert "WS2" not in series_names


def test_every_member_included_even_with_no_allocation():
    rows = [_row(1, 1, 50.0)]
    options = build_person_allocation_chart_options(MEMBERS, WORKSTREAMS, rows)
    assert options["yAxis"]["data"] == ["Alice", "Ben"]
    ws1_series = next(s for s in options["series"] if s["name"] == "WS1")
    assert ws1_series["data"] == [50.0, 0.0]


def test_unallocated_segment_fills_gap_to_100():
    rows = [_row(1, 1, 40.0)]
    options = build_person_allocation_chart_options(MEMBERS, WORKSTREAMS, rows)
    unalloc = next(s for s in options["series"] if s["name"] == "Unallocated")
    assert unalloc["data"] == [60.0, 100.0]  # Alice: 100-40, Ben: 100-0


def test_over_allocated_member_has_zero_unallocated_and_is_marked():
    rows = [_row(1, 1, 60.0), _row(1, 2, 60.0)]
    options = build_person_allocation_chart_options(MEMBERS, WORKSTREAMS, rows)
    unalloc = next(s for s in options["series"] if s["name"] == "Unallocated")
    assert unalloc["data"] == [0.0, 100.0]
    assert options["yAxis"]["data"][0] == f"Alice{OVER_ALLOCATED_MARK}"
    assert options["yAxis"]["data"][1] == "Ben"


def test_exactly_100_pct_is_not_marked_over_allocated():
    rows = [_row(1, 1, 50.0), _row(1, 2, 50.0)]
    options = build_person_allocation_chart_options(MEMBERS, WORKSTREAMS, rows)
    assert options["yAxis"]["data"][0] == "Alice"


def test_reference_line_marks_100_pct():
    rows = [_row(1, 1, 50.0)]
    options = build_person_allocation_chart_options(MEMBERS, WORKSTREAMS, rows)
    unalloc = next(s for s in options["series"] if s["name"] == "Unallocated")
    assert unalloc["markLine"]["data"] == [{"xAxis": 100}]
