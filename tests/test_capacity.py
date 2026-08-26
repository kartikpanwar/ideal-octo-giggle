"""capacity_summary rolls up availability, allocation and open task estimates."""

from __future__ import annotations

from app.models import (
    CapacityPeriod,
    Task,
    TeamMember,
    TeamMemberCapacity,
    Workstream,
    WorkstreamAllocation,
)
from app.services import capacity_summary, kpi_summary


def _setup(session):
    member = TeamMember(name="Sam")
    period = CapacityPeriod(name="P1")
    ws = Workstream(name="WS1")
    session.add_all([member, period, ws])
    session.flush()
    session.add_all(
        [
            TeamMemberCapacity(team_member_id=member.id, period_id=period.id, available_weeks=8.0),
            WorkstreamAllocation(workstream_id=ws.id, team_member_id=member.id, period_id=period.id, allocated_weeks=5.0),
            Task(name="Open A", assignee_id=member.id, status="in_progress", estimated_effort_weeks=3.0),
            Task(name="Open B", assignee_id=member.id, status="not_started", estimated_effort_weeks=2.0),
            Task(name="Done", assignee_id=member.id, status="done", estimated_effort_weeks=4.0),
        ]
    )
    session.flush()
    return member


def test_summary_rollup(session):
    member = _setup(session)
    row = next(r for r in capacity_summary(session) if r["member_id"] == member.id)
    assert row["available"] == 8.0
    assert row["allocated"] == 5.0
    assert row["estimated_open"] == 5.0  # 3 + 2; the done task is excluded
    assert row["remaining"] == 3.0  # 8 - 5
    assert row["over_allocated"] is False


def test_over_allocation_flag(session):
    member = TeamMember(name="Overloaded")
    period = CapacityPeriod(name="P1")
    session.add_all([member, period])
    session.flush()
    session.add_all(
        [
            TeamMemberCapacity(team_member_id=member.id, period_id=period.id, available_weeks=4.0),
            Task(name="Big", assignee_id=member.id, status="in_progress", estimated_effort_weeks=6.0),
        ]
    )
    session.flush()
    row = next(r for r in capacity_summary(session) if r["member_id"] == member.id)
    assert row["estimated_open"] == 6.0
    assert row["remaining"] == -2.0
    assert row["over_allocated"] is True


def test_kpi_summary_counts(session):
    member = TeamMember(name="Sam")
    ws_active = Workstream(name="Active WS", status="in_progress")
    ws_done = Workstream(name="Done WS", status="done")
    session.add_all([member, ws_active, ws_done])
    session.flush()
    session.add_all(
        [
            Task(name="In progress 1", assignee_id=member.id, status="in_progress"),
            Task(name="In progress 2", assignee_id=member.id, status="in_progress"),
            Task(name="Blocked 1", assignee_id=member.id, status="blocked"),
            Task(name="Done 1", assignee_id=member.id, status="done"),
        ]
    )
    session.flush()

    kpis = kpi_summary(session)
    assert kpis["tasks_in_progress"] == 2
    assert kpis["tasks_blocked"] == 1
    assert kpis["workstreams_active"] == 1


def test_kpi_summary_counts_over_allocated_people(session):
    _setup(session)  # not over-allocated
    over = TeamMember(name="Overloaded")
    period = CapacityPeriod(name="P1")
    session.add_all([over, period])
    session.flush()
    session.add_all(
        [
            TeamMemberCapacity(team_member_id=over.id, period_id=period.id, available_weeks=4.0),
            Task(name="Big", assignee_id=over.id, status="in_progress", estimated_effort_weeks=6.0),
        ]
    )
    session.flush()

    assert kpi_summary(session)["people_over_allocated"] == 1
