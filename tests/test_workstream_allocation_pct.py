"""workstream_allocation_pct() reads standing % allocation rows; set_person_allocations()
upserts/deletes them for one person."""

from __future__ import annotations

from app.models import TeamMember, Workstream, WorkstreamAllocation
from app.services import set_person_allocations, workstream_allocation_pct


def _member(session, name="Sam") -> TeamMember:
    m = TeamMember(name=name)
    session.add(m)
    session.flush()
    return m


def _workstream(session, name="WS") -> Workstream:
    w = Workstream(name=name)
    session.add(w)
    session.flush()
    return w


def test_reads_only_period_scoped_null_pct_rows(session):
    member = _member(session)
    ws = _workstream(session)
    period_row = WorkstreamAllocation(
        workstream_id=ws.id, team_member_id=member.id, period_id=1, allocated_weeks=5.0
    )
    pct_row = WorkstreamAllocation(
        workstream_id=ws.id, team_member_id=member.id, period_id=None, allocation_pct=50.0
    )
    session.add_all([period_row, pct_row])
    session.flush()

    rows = workstream_allocation_pct(session)
    assert len(rows) == 1
    assert rows[0] == {
        "team_member_id": member.id,
        "workstream_id": ws.id,
        "allocation_pct": 50.0,
    }


def test_set_person_allocations_creates_rows(session):
    member = _member(session)
    ws1 = _workstream(session, "WS1")
    ws2 = _workstream(session, "WS2")

    set_person_allocations(session, member.id, {ws1.id: 50.0, ws2.id: 50.0})
    session.flush()

    rows = {r["workstream_id"]: r["allocation_pct"] for r in workstream_allocation_pct(session)}
    assert rows == {ws1.id: 50.0, ws2.id: 50.0}


def test_set_person_allocations_updates_existing_row(session):
    member = _member(session)
    ws = _workstream(session)
    session.add(
        WorkstreamAllocation(workstream_id=ws.id, team_member_id=member.id, period_id=None, allocation_pct=30.0)
    )
    session.flush()

    set_person_allocations(session, member.id, {ws.id: 75.0})
    session.flush()

    rows = workstream_allocation_pct(session)
    assert len(rows) == 1
    assert rows[0]["allocation_pct"] == 75.0


def test_set_person_allocations_deletes_zeroed_or_omitted_rows(session):
    member = _member(session)
    ws1 = _workstream(session, "WS1")
    ws2 = _workstream(session, "WS2")
    session.add_all(
        [
            WorkstreamAllocation(workstream_id=ws1.id, team_member_id=member.id, period_id=None, allocation_pct=40.0),
            WorkstreamAllocation(workstream_id=ws2.id, team_member_id=member.id, period_id=None, allocation_pct=40.0),
        ]
    )
    session.flush()

    # ws1 explicitly zeroed, ws2 simply omitted -> both should be removed.
    set_person_allocations(session, member.id, {ws1.id: 0.0})
    session.flush()

    assert workstream_allocation_pct(session) == []


def test_set_person_allocations_does_not_touch_other_people(session):
    alice = _member(session, "Alice")
    ben = _member(session, "Ben")
    ws = _workstream(session)
    session.add(
        WorkstreamAllocation(workstream_id=ws.id, team_member_id=ben.id, period_id=None, allocation_pct=60.0)
    )
    session.flush()

    set_person_allocations(session, alice.id, {ws.id: 40.0})
    session.flush()

    rows = {r["team_member_id"]: r["allocation_pct"] for r in workstream_allocation_pct(session)}
    assert rows == {alice.id: 40.0, ben.id: 60.0}
