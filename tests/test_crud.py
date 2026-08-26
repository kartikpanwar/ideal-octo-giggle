"""Creating/amending a task appends estimate_history rows via the shared helper."""

from __future__ import annotations

from datetime import date

from app.models import EstimateHistory, Task, TeamMember
from app.services import record_task_change, task_history


def _make_task(session, status="not_started"):
    member = TeamMember(name="Test Person")
    session.add(member)
    session.flush()
    task = Task(
        name="Sample task",
        assignee_id=member.id,
        status=status,
        estimated_start=date(2026, 9, 1),
        estimated_end=date(2026, 9, 30),
    )
    session.add(task)
    session.flush()
    return task


def test_status_change_logs_history(session):
    task = _make_task(session)
    # initial creation snapshot
    record_task_change(session, task, previous_status=None, status_update="Created")

    # amend the status
    prev = task.status
    task.status = "in_progress"
    session.flush()
    record_task_change(session, task, previous_status=prev, status_update="Kicked off")
    session.flush()

    history = task_history(session, task.id)
    assert len(history) == 2
    # newest first
    assert history[0].status == "in_progress"
    assert history[0].previous_status == "not_started"
    assert history[0].status_update == "Kicked off"
    assert history[1].status == "not_started"


def test_history_snapshots_dates(session):
    task = _make_task(session)
    task.estimated_end = date(2026, 10, 15)
    session.flush()
    record_task_change(session, task, previous_status=task.status, status_update="Pushed end date")
    session.flush()

    entry = task_history(session, task.id)[0]
    assert entry.estimated_end == date(2026, 10, 15)
    assert entry.entity_type == "task"


def test_history_isolated_per_task(session):
    t1 = _make_task(session)
    t2 = _make_task(session)
    record_task_change(session, t1, previous_status=None, status_update="t1")
    session.flush()

    assert len(task_history(session, t1.id)) == 1
    assert len(task_history(session, t2.id)) == 0
    assert session.query(EstimateHistory).count() == 1
