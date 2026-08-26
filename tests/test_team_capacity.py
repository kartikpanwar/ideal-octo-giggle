"""team_capacity_by_month() spreads task effort across months by day-overlap,
grouped by strategy item, plus a per-month team-available-time reference."""

from __future__ import annotations

from datetime import date

from app.models import StrategyItem, Task, TeamMember, Workstream
from app.services import (
    _days_in_month,
    _days_in_month_overlap,
    _month_range,
    team_capacity_by_month,
)


def _member(session, **kwargs) -> TeamMember:
    m = TeamMember(name=kwargs.pop("name", "Sam"), **kwargs)
    session.add(m)
    session.flush()
    return m


def _strategy(session, name="S1") -> StrategyItem:
    s = StrategyItem(name=name)
    session.add(s)
    session.flush()
    return s


def _workstream(session, strategy=None, name="WS") -> Workstream:
    w = Workstream(name=name, strategy_item_id=strategy.id if strategy else None)
    session.add(w)
    session.flush()
    return w


def _task(session, **kwargs) -> Task:
    t = Task(name=kwargs.pop("name", "Task"), **kwargs)
    session.add(t)
    session.flush()
    return t


def _effort_for(result, month, strategy_item_id):
    return next(
        (
            r["effort_weeks"]
            for r in result["effort"]
            if r["month"] == month and r["strategy_item_id"] == strategy_item_id
        ),
        0.0,
    )


# --- date helpers ---

def test_days_in_month_handles_28_30_31():
    assert _days_in_month(date(2026, 2, 1)) == 28
    assert _days_in_month(date(2026, 4, 1)) == 30
    assert _days_in_month(date(2026, 9, 1)) == 30
    assert _days_in_month(date(2026, 1, 1)) == 31


def test_days_in_month_handles_leap_year():
    assert _days_in_month(date(2028, 2, 1)) == 29


def test_month_range_spans_year_boundary():
    months = _month_range(date(2026, 11, 15), date(2027, 1, 5))
    assert months == [date(2026, 11, 1), date(2026, 12, 1), date(2027, 1, 1)]


def test_days_in_month_overlap_partial_at_boundaries():
    # Task spans Sep 25 - Oct 5; Sep gets 6 days (25-30), Oct gets 5 days (1-5).
    assert _days_in_month_overlap(date(2026, 9, 1), date(2026, 9, 25), date(2026, 10, 5)) == 6
    assert _days_in_month_overlap(date(2026, 10, 1), date(2026, 9, 25), date(2026, 10, 5)) == 5


def test_days_in_month_overlap_zero_when_no_overlap():
    assert _days_in_month_overlap(date(2026, 12, 1), date(2026, 9, 1), date(2026, 9, 30)) == 0


# --- team_capacity_by_month ---

def test_no_tasks_returns_empty_shape(session):
    result = team_capacity_by_month(session)
    assert result == {"months": [], "strategy_items": [], "effort": [], "available": []}


def test_single_month_task_fully_attributed(session):
    strategy = _strategy(session, "Onboarding")
    ws = _workstream(session, strategy)
    _task(session, workstream_id=ws.id, status="in_progress",
          estimated_start=date(2026, 9, 5), estimated_end=date(2026, 9, 20),
          estimated_effort_weeks=2.0)

    result = team_capacity_by_month(session)
    assert result["months"] == [date(2026, 9, 1)]
    assert _effort_for(result, date(2026, 9, 1), strategy.id) == 2.0


def test_task_spanning_two_months_splits_by_day_count(session):
    strategy = _strategy(session)
    ws = _workstream(session, strategy)
    # 10-day task: Sep 26-30 (5 days) + Oct 1-5 (5 days) -> even 50/50 split.
    _task(session, workstream_id=ws.id, status="in_progress",
          estimated_start=date(2026, 9, 26), estimated_end=date(2026, 10, 5),
          estimated_effort_weeks=2.0)

    result = team_capacity_by_month(session)
    assert _effort_for(result, date(2026, 9, 1), strategy.id) == 1.0
    assert _effort_for(result, date(2026, 10, 1), strategy.id) == 1.0


def test_includes_done_and_cancelled_tasks(session):
    # Unlike workstream_assignments(), closed tasks still count here.
    strategy = _strategy(session)
    ws = _workstream(session, strategy)
    _task(session, workstream_id=ws.id, status="done",
          estimated_start=date(2026, 9, 1), estimated_end=date(2026, 9, 10),
          estimated_effort_weeks=3.0)

    result = team_capacity_by_month(session)
    assert _effort_for(result, date(2026, 9, 1), strategy.id) == 3.0


def test_task_without_workstream_goes_to_unassigned_bucket(session):
    _task(session, status="in_progress", estimated_start=date(2026, 9, 1),
          estimated_end=date(2026, 9, 10), estimated_effort_weeks=1.5)

    result = team_capacity_by_month(session)
    assert {"id": None, "name": "Unassigned"} in result["strategy_items"]
    assert _effort_for(result, date(2026, 9, 1), None) == 1.5


def test_workstream_without_strategy_item_goes_to_unassigned_bucket(session):
    ws = _workstream(session, strategy=None)  # no strategy item link
    _task(session, workstream_id=ws.id, status="in_progress",
          estimated_start=date(2026, 9, 1), estimated_end=date(2026, 9, 10),
          estimated_effort_weeks=1.5)

    result = team_capacity_by_month(session)
    assert _effort_for(result, date(2026, 9, 1), None) == 1.5


def test_unassigned_bucket_sorted_last(session):
    # "Zebra" sorts after "Unassigned" alphabetically, but Unassigned (id=None)
    # should still land last regardless of name.
    strategy = _strategy(session, "Zebra Project")
    ws = _workstream(session, strategy)
    _task(session, workstream_id=ws.id, status="in_progress",
          estimated_start=date(2026, 9, 1), estimated_end=date(2026, 9, 5),
          estimated_effort_weeks=1.0)
    _task(session, status="in_progress",  # no workstream -> Unassigned
          estimated_start=date(2026, 9, 1), estimated_end=date(2026, 9, 5),
          estimated_effort_weeks=1.0)

    result = team_capacity_by_month(session)
    names = [item["name"] for item in result["strategy_items"]]
    assert names[-1] == "Unassigned"


def test_months_filled_contiguously_even_with_a_gap(session):
    strategy = _strategy(session)
    ws = _workstream(session, strategy)
    _task(session, workstream_id=ws.id, status="in_progress",
          estimated_start=date(2026, 9, 1), estimated_end=date(2026, 9, 5),
          estimated_effort_weeks=1.0)
    _task(session, workstream_id=ws.id, status="in_progress",
          estimated_start=date(2026, 11, 1), estimated_end=date(2026, 11, 5),
          estimated_effort_weeks=1.0)

    result = team_capacity_by_month(session)
    # October has no task activity but should still appear in the range.
    assert result["months"] == [date(2026, 9, 1), date(2026, 10, 1), date(2026, 11, 1)]


def test_available_only_counts_active_members(session):
    _member(session, name="Active", default_weekly_hours=40, active=True)
    _member(session, name="Inactive", default_weekly_hours=40, active=False)
    strategy = _strategy(session)
    ws = _workstream(session, strategy)
    _task(session, workstream_id=ws.id, status="in_progress",
          estimated_start=date(2026, 9, 1), estimated_end=date(2026, 9, 30),
          estimated_effort_weeks=1.0)

    result = team_capacity_by_month(session)
    sept = next(r for r in result["available"] if r["month"] == date(2026, 9, 1))
    # Only the active member (fraction 1.0) counts: 1.0 * (30 days / 7).
    assert sept["available_weeks"] == round(30 / 7, 2)
