"""build_person_timeline_options() renders estimated + actual bars per task."""

from __future__ import annotations

from datetime import date

from app.pages.people import build_person_timeline_options


def _task(name, est_start=None, est_end=None, act_start=None, act_end=None,
          status="not_started", effort=2.0, workstream="Setup"):
    return {
        "name": name,
        "status": status,
        "workstream": workstream,
        "estimated_start": est_start,
        "estimated_end": est_end,
        "actual_start": act_start,
        "actual_end": act_end,
        "estimated_effort_weeks": effort,
    }


def test_no_dated_tasks_returns_none():
    assert build_person_timeline_options([_task("A")]) is None


def test_estimated_only_task_has_no_actual_bar():
    tasks = [_task("A", date(2026, 9, 1), date(2026, 9, 8))]
    options = build_person_timeline_options(tasks)
    est_series, act_series = options["series"][1], options["series"][3]
    assert est_series["data"][0] is not None
    assert act_series["data"][0] is None


def test_actual_only_task_has_no_estimated_bar():
    tasks = [_task("A", act_start=date(2026, 9, 3), act_end=date(2026, 9, 10))]
    options = build_person_timeline_options(tasks)
    est_series, act_series = options["series"][1], options["series"][3]
    assert est_series["data"][0] is None
    assert act_series["data"][0] is not None


def test_timeline_start_uses_earliest_of_either_kind():
    # Actual start (Sep 1) is earlier than the estimated start (Sep 5).
    tasks = [_task("A", date(2026, 9, 5), date(2026, 9, 12), date(2026, 9, 1), date(2026, 9, 10))]
    options = build_person_timeline_options(tasks)
    assert "Days from 2026-09-01" in options["xAxis"]["name"]
    est_offset = options["series"][0]["data"][0]
    act_offset = options["series"][2]["data"][0]
    assert est_offset == 4  # Sep 5 - Sep 1
    assert act_offset == 0  # Sep 1 - Sep 1


def test_both_bars_present_when_both_date_pairs_exist():
    tasks = [_task("Slipped", date(2026, 9, 1), date(2026, 9, 8), date(2026, 9, 1), date(2026, 9, 15))]
    options = build_person_timeline_options(tasks)
    est_duration = options["series"][1]["data"][0]["value"]
    act_duration = options["series"][3]["data"][0]["value"]
    assert est_duration == 7
    assert act_duration == 14  # actual ran longer than estimated


def test_actual_bar_uses_fixed_colour_not_status():
    tasks = [_task("A", date(2026, 9, 1), date(2026, 9, 5), date(2026, 9, 1), date(2026, 9, 5), status="blocked")]
    options = build_person_timeline_options(tasks)
    est_color = options["series"][1]["data"][0]["itemStyle"]["color"]
    act_color = options["series"][3]["data"][0]["itemStyle"]["color"]
    assert est_color == "#e53935"  # blocked
    assert act_color != est_color


def test_tooltip_labels_estimated_vs_actual():
    tasks = [_task("Task X", date(2026, 9, 1), date(2026, 9, 5), date(2026, 9, 1), date(2026, 9, 5))]
    options = build_person_timeline_options(tasks)
    est_name = options["series"][1]["data"][0]["name"]
    act_name = options["series"][3]["data"][0]["name"]
    assert "Estimated" in est_name
    assert "Actual" in act_name
