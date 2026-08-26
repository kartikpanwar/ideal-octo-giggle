"""weekly_allocation() spreads task effort across ISO weeks and converts to %."""

from __future__ import annotations

from datetime import date

from app.models import Task, TeamMember
from app.services import _iso_weeks_between, weekly_allocation


def _member(session, **kwargs) -> TeamMember:
    m = TeamMember(name=kwargs.pop("name", "Sam"), **kwargs)
    session.add(m)
    session.flush()
    return m


def _task(session, member, **kwargs) -> Task:
    t = Task(name=kwargs.pop("name", "Task"), assignee_id=member.id, **kwargs)
    session.add(t)
    session.flush()
    return t


def _pct_for(rows, member_id, week_start):
    return next(
        (r["pct"] for r in rows if r["member_id"] == member_id and r["week_start"] == week_start),
        None,
    )


# --- _iso_weeks_between ---

def test_iso_weeks_between_single_week():
    # Both dates fall within ISO week 2026-W36 (Aug 31 - Sep 6).
    weeks = _iso_weeks_between(date(2026, 9, 1), date(2026, 9, 3))
    assert weeks == [date(2026, 8, 31)]


def test_iso_weeks_between_multiple_weeks():
    weeks = _iso_weeks_between(date(2026, 9, 1), date(2026, 9, 15))
    assert weeks == [date(2026, 8, 31), date(2026, 9, 7), date(2026, 9, 14)]


def test_iso_weeks_between_handles_reversed_dates():
    assert _iso_weeks_between(date(2026, 9, 15), date(2026, 9, 1)) == _iso_weeks_between(
        date(2026, 9, 1), date(2026, 9, 15)
    )


# --- weekly_allocation ---

def test_full_time_member_single_week_task_is_100_pct(session):
    member = _member(session, default_weekly_hours=40)
    _task(session, member, estimated_start=date(2026, 9, 1), estimated_end=date(2026, 9, 3),
          estimated_effort_weeks=1.0)
    rows = weekly_allocation(session)
    assert _pct_for(rows, member.id, date(2026, 8, 31)) == 100.0


def test_effort_spread_evenly_across_multiple_weeks(session):
    member = _member(session, default_weekly_hours=40)
    # Sep 1 (ISO week 36) - Sep 8 (ISO week 37) spans exactly 2 ISO weeks;
    # 1.0 total effort -> 0.5/week -> 50% each week.
    _task(session, member, estimated_start=date(2026, 9, 1), estimated_end=date(2026, 9, 8),
          estimated_effort_weeks=1.0)
    rows = weekly_allocation(session)
    assert _pct_for(rows, member.id, date(2026, 8, 31)) == 50.0
    assert _pct_for(rows, member.id, date(2026, 9, 7)) == 50.0


def test_part_time_member_scales_pct_up(session):
    # 32/40 hrs = 0.8 capacity fraction, so the same load reads as a higher %.
    member = _member(session, default_weekly_hours=32)
    _task(session, member, estimated_start=date(2026, 9, 1), estimated_end=date(2026, 9, 3),
          estimated_effort_weeks=0.8)
    rows = weekly_allocation(session)
    assert _pct_for(rows, member.id, date(2026, 8, 31)) == 100.0  # 0.8 / 0.8 = 1.0 -> 100%


def test_missing_default_hours_treated_as_full_time(session):
    member = _member(session, default_weekly_hours=None)
    _task(session, member, estimated_start=date(2026, 9, 1), estimated_end=date(2026, 9, 3),
          estimated_effort_weeks=1.0)
    rows = weekly_allocation(session)
    assert _pct_for(rows, member.id, date(2026, 8, 31)) == 100.0


def test_multiple_tasks_same_week_sum(session):
    member = _member(session, default_weekly_hours=40)
    _task(session, member, name="A", estimated_start=date(2026, 9, 1), estimated_end=date(2026, 9, 3),
          estimated_effort_weeks=0.5)
    _task(session, member, name="B", estimated_start=date(2026, 9, 2), estimated_end=date(2026, 9, 4),
          estimated_effort_weeks=0.3)
    rows = weekly_allocation(session)
    assert _pct_for(rows, member.id, date(2026, 8, 31)) == 80.0


def test_task_missing_effort_is_skipped(session):
    member = _member(session, default_weekly_hours=40)
    _task(session, member, estimated_start=date(2026, 9, 1), estimated_end=date(2026, 9, 3),
          estimated_effort_weeks=None)
    assert weekly_allocation(session) == []


def test_task_missing_dates_is_skipped(session):
    member = _member(session, default_weekly_hours=40)
    _task(session, member, estimated_effort_weeks=1.0)
    assert weekly_allocation(session) == []


def test_unassigned_task_is_skipped(session):
    t = Task(name="Orphan", assignee_id=None, estimated_start=date(2026, 9, 1),
              estimated_end=date(2026, 9, 3), estimated_effort_weeks=1.0)
    session.add(t)
    session.flush()
    assert weekly_allocation(session) == []
