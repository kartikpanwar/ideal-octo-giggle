"""workstream_assignments() aggregates open task effort per (workstream, person)."""

from __future__ import annotations

from app.models import Task, TeamMember, Workstream
from app.services import workstream_assignments


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


def _task(session, member, workstream, **kwargs) -> Task:
    t = Task(name=kwargs.pop("name", "Task"), assignee_id=member.id,
              workstream_id=workstream.id, **kwargs)
    session.add(t)
    session.flush()
    return t


def _entry(rows, workstream_id, person_id):
    return next(
        (r for r in rows if r["workstream_id"] == workstream_id and r["person_id"] == person_id),
        None,
    )


def test_sums_effort_across_multiple_tasks(session):
    member = _member(session)
    ws = _workstream(session)
    _task(session, member, ws, name="A", status="in_progress", estimated_effort_weeks=2.0)
    _task(session, member, ws, name="B", status="not_started", estimated_effort_weeks=1.5)

    entry = _entry(workstream_assignments(session), ws.id, member.id)
    assert entry["effort_weeks"] == 3.5
    assert entry["task_count"] == 2
    assert sorted(entry["task_names"]) == ["A", "B"]


def test_excludes_done_and_cancelled_tasks(session):
    member = _member(session)
    ws = _workstream(session)
    _task(session, member, ws, status="in_progress", estimated_effort_weeks=2.0)
    _task(session, member, ws, status="done", estimated_effort_weeks=5.0)
    _task(session, member, ws, status="cancelled", estimated_effort_weeks=5.0)

    entry = _entry(workstream_assignments(session), ws.id, member.id)
    assert entry["effort_weeks"] == 2.0
    assert entry["task_count"] == 1


def test_missing_effort_treated_as_zero_but_still_counted(session):
    member = _member(session)
    ws = _workstream(session)
    _task(session, member, ws, status="not_started", estimated_effort_weeks=None)

    entry = _entry(workstream_assignments(session), ws.id, member.id)
    assert entry["effort_weeks"] == 0.0
    assert entry["task_count"] == 1


def test_separates_by_workstream_and_person(session):
    alice = _member(session, "Alice")
    ben = _member(session, "Ben")
    ws1 = _workstream(session, "WS1")
    ws2 = _workstream(session, "WS2")
    _task(session, alice, ws1, status="in_progress", estimated_effort_weeks=1.0)
    _task(session, ben, ws1, status="in_progress", estimated_effort_weeks=2.0)
    _task(session, alice, ws2, status="in_progress", estimated_effort_weeks=3.0)

    rows = workstream_assignments(session)
    assert _entry(rows, ws1.id, alice.id)["effort_weeks"] == 1.0
    assert _entry(rows, ws1.id, ben.id)["effort_weeks"] == 2.0
    assert _entry(rows, ws2.id, alice.id)["effort_weeks"] == 3.0
    assert _entry(rows, ws2.id, ben.id) is None


def test_task_missing_assignee_or_workstream_is_skipped(session):
    member = _member(session)
    ws = _workstream(session)
    # No workstream.
    session.add(Task(name="Unassigned WS", assignee_id=member.id, status="in_progress",
                      estimated_effort_weeks=1.0))
    # No assignee.
    session.add(Task(name="Unassigned person", workstream_id=ws.id, status="in_progress",
                      estimated_effort_weeks=1.0))
    session.flush()

    assert workstream_assignments(session) == []
