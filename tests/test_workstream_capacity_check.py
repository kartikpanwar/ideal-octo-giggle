"""workstream_capacity_check() compares top-down allocated capacity (from
standing allocation_pct rows, spread over a workstream's estimated duration)
against bottom-up required task effort."""

from __future__ import annotations

from datetime import date

from app.models import TeamMember, Task, Workstream, WorkstreamAllocation
from app.services import workstream_capacity_check


def _member(session, name="Sam", default_weekly_hours=None) -> TeamMember:
    m = TeamMember(name=name, default_weekly_hours=default_weekly_hours)
    session.add(m)
    session.flush()
    return m


def _workstream(session, name="WS", start=None, end=None) -> Workstream:
    w = Workstream(name=name, estimated_start=start, estimated_end=end)
    session.add(w)
    session.flush()
    return w


def _entry(rows, workstream_id):
    return next((r for r in rows if r["workstream_id"] == workstream_id), None)


def test_sufficient_when_allocated_capacity_covers_required_effort(session):
    member = _member(session)
    ws = _workstream(session, start=date(2026, 1, 1), end=date(2026, 1, 29))  # 4-week span
    session.add_all(
        [
            WorkstreamAllocation(workstream_id=ws.id, team_member_id=member.id, period_id=None, allocation_pct=100.0),
            Task(name="A", workstream_id=ws.id, status="in_progress", estimated_effort_weeks=3.0),
        ]
    )
    session.flush()

    row = _entry(workstream_capacity_check(session), ws.id)
    assert row["allocated_weeks"] == 4.0  # 100% * 1.0 fraction * 4 weeks
    assert row["required_weeks"] == 3.0
    assert row["sufficient"] is True


def test_insufficient_when_required_effort_exceeds_allocated_capacity(session):
    member = _member(session)
    ws = _workstream(session, start=date(2026, 1, 1), end=date(2026, 1, 8))  # 1-week span
    session.add_all(
        [
            WorkstreamAllocation(workstream_id=ws.id, team_member_id=member.id, period_id=None, allocation_pct=50.0),
            Task(name="A", workstream_id=ws.id, status="in_progress", estimated_effort_weeks=5.0),
        ]
    )
    session.flush()

    row = _entry(workstream_capacity_check(session), ws.id)
    assert row["allocated_weeks"] == 0.5  # 50% * 1.0 * 1 week
    assert row["required_weeks"] == 5.0
    assert row["sufficient"] is False


def test_workstream_without_dates_is_skipped(session):
    ws = _workstream(session)  # no estimated_start/end
    session.flush()
    assert workstream_capacity_check(session) == []


def test_only_open_tasks_count_toward_required(session):
    ws = _workstream(session, start=date(2026, 1, 1), end=date(2026, 1, 8))
    session.add_all(
        [
            Task(name="Open", workstream_id=ws.id, status="in_progress", estimated_effort_weeks=2.0),
            Task(name="Done", workstream_id=ws.id, status="done", estimated_effort_weeks=10.0),
            Task(name="Cancelled", workstream_id=ws.id, status="cancelled", estimated_effort_weeks=10.0),
        ]
    )
    session.flush()

    row = _entry(workstream_capacity_check(session), ws.id)
    assert row["required_weeks"] == 2.0


def test_allocation_to_other_workstream_not_counted(session):
    member = _member(session)
    ws1 = _workstream(session, "WS1", start=date(2026, 1, 1), end=date(2026, 1, 8))
    ws2 = _workstream(session, "WS2", start=date(2026, 1, 1), end=date(2026, 1, 8))
    session.add(
        WorkstreamAllocation(workstream_id=ws1.id, team_member_id=member.id, period_id=None, allocation_pct=100.0)
    )
    session.flush()

    rows = workstream_capacity_check(session)
    assert _entry(rows, ws1.id)["allocated_weeks"] == 1.0
    assert _entry(rows, ws2.id)["allocated_weeks"] == 0.0


def test_part_time_member_capacity_fraction_applied(session):
    member = _member(session, default_weekly_hours=20)  # 0.5 FTE
    ws = _workstream(session, start=date(2026, 1, 1), end=date(2026, 1, 8))
    session.add(
        WorkstreamAllocation(workstream_id=ws.id, team_member_id=member.id, period_id=None, allocation_pct=100.0)
    )
    session.flush()

    row = _entry(workstream_capacity_check(session), ws.id)
    assert row["allocated_weeks"] == 0.5  # 100% * 0.5 fraction * 1 week


def test_no_allocation_and_no_tasks_is_sufficient_by_default(session):
    ws = _workstream(session, start=date(2026, 1, 1), end=date(2026, 1, 8))
    session.flush()

    row = _entry(workstream_capacity_check(session), ws.id)
    assert row["allocated_weeks"] == 0.0
    assert row["required_weeks"] == 0.0
    assert row["sufficient"] is True
