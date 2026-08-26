"""Shared data-access helpers used by the UI pages.

Kept UI-agnostic so they can be unit-tested directly.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    EstimateHistory,
    Task,
    TeamMember,
    TeamMemberCapacity,
    WorkstreamAllocation,
    _utcnow,
)

# Task statuses that no longer consume remaining capacity.
CLOSED_STATUSES = ("done", "cancelled")


def record_status_change(
    session: Session,
    *,
    entity_type: str,
    entity_id: int,
    previous_status: str | None,
    status: str | None,
    estimated_start: date | None,
    estimated_end: date | None,
    status_update: str | None = None,
    changed_by_id: int | None = None,
) -> EstimateHistory:
    """Append an estimate_history snapshot. Centralises history logging so tasks,
    workstreams and strategy items all record changes the same way."""
    entry = EstimateHistory(
        entity_type=entity_type,
        entity_id=entity_id,
        previous_status=previous_status,
        status=status,
        estimated_start=estimated_start,
        estimated_end=estimated_end,
        status_update=status_update,
        changed_by_id=changed_by_id,
        changed_at=_utcnow(),
    )
    session.add(entry)
    return entry


def task_history(session: Session, task_id: int) -> list[EstimateHistory]:
    """History rows for one task, newest first."""
    return (
        session.query(EstimateHistory)
        .filter_by(entity_type="task", entity_id=task_id)
        .order_by(EstimateHistory.changed_at.desc())
        .all()
    )


def capacity_summary(session: Session) -> list[dict]:
    """Per-member comparison of available capacity vs. workstream allocation vs.
    task estimates (all in person-weeks). Totals are summed across all periods.

    - available: sum of team_member_capacity.available_weeks
    - allocated: sum of workstream_allocation.allocated_weeks (top-down plan)
    - estimated_open: sum of estimated_effort_weeks for tasks not done/cancelled
    - remaining: available - estimated_open
    - over_allocated: estimated or allocated work exceeds available capacity
    """
    avail = dict(
        session.query(
            TeamMemberCapacity.team_member_id,
            func.coalesce(func.sum(TeamMemberCapacity.available_weeks), 0.0),
        ).group_by(TeamMemberCapacity.team_member_id)
    )
    alloc = dict(
        session.query(
            WorkstreamAllocation.team_member_id,
            func.coalesce(func.sum(WorkstreamAllocation.allocated_weeks), 0.0),
        ).group_by(WorkstreamAllocation.team_member_id)
    )
    est_open = dict(
        session.query(
            Task.assignee_id,
            func.coalesce(func.sum(Task.estimated_effort_weeks), 0.0),
        )
        .filter(Task.status.notin_(CLOSED_STATUSES))
        .group_by(Task.assignee_id)
    )

    rows = []
    for member in session.query(TeamMember).order_by(TeamMember.name).all():
        available = float(avail.get(member.id, 0.0) or 0.0)
        allocated = float(alloc.get(member.id, 0.0) or 0.0)
        estimated = float(est_open.get(member.id, 0.0) or 0.0)
        rows.append(
            {
                "member_id": member.id,
                "name": member.name,
                "available": round(available, 2),
                "allocated": round(allocated, 2),
                "estimated_open": round(estimated, 2),
                "remaining": round(available - estimated, 2),
                "over_allocated": estimated > available or allocated > available,
            }
        )
    return rows


def record_task_change(
    session: Session,
    task: Task,
    *,
    previous_status: str | None,
    status_update: str | None,
) -> None:
    """Convenience wrapper: snapshot a task's current status/estimate into history."""
    record_status_change(
        session,
        entity_type="task",
        entity_id=task.id,
        previous_status=previous_status,
        status=task.status,
        estimated_start=task.estimated_start,
        estimated_end=task.estimated_end,
        status_update=status_update,
        changed_by_id=task.assignee_id,
    )
