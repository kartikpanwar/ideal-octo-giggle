"""Shared data-access helpers used by the UI pages.

Kept UI-agnostic so they can be unit-tested directly.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    EstimateHistory,
    Task,
    TeamMember,
    TeamMemberCapacity,
    Workstream,
    WorkstreamAllocation,
    _utcnow,
)

# Task statuses that no longer consume remaining capacity.
CLOSED_STATUSES = ("done", "cancelled")

# Hours/week treated as "full-time" (1.0) when converting a member's
# default_weekly_hours into a capacity fraction. Members without a value set
# are assumed full-time.
STANDARD_WEEKLY_HOURS = 40.0


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


def kpi_summary(session: Session) -> dict:
    """Small headline counts for the Home page's KPI row."""
    return {
        "tasks_in_progress": session.query(Task).filter(Task.status == "in_progress").count(),
        "tasks_blocked": session.query(Task).filter(Task.status == "blocked").count(),
        "workstreams_active": session.query(Workstream).filter(Workstream.status == "in_progress").count(),
        "people_over_allocated": sum(1 for row in capacity_summary(session) if row["over_allocated"]),
    }


def _iso_weeks_between(start: date, end: date) -> list[date]:
    """Monday date of every distinct ISO calendar week between start and end
    (inclusive), in order. Order is swapped if end < start."""
    if end < start:
        start, end = end, start
    weeks: list[date] = []
    seen: set[tuple[int, int]] = set()
    current = start
    while current <= end:
        iso_year, iso_week, _ = current.isocalendar()
        key = (iso_year, iso_week)
        if key not in seen:
            seen.add(key)
            weeks.append(date.fromisocalendar(iso_year, iso_week, 1))
        current += timedelta(days=1)
    return weeks


def weekly_allocation(session: Session) -> list[dict]:
    """Weekly % capacity allocation per team member, for the People page's
    allocation heatmap.

    Each dated task's estimated_effort_weeks (a single total, not phased per
    period — see docs/architecture.md's known constraints) is spread evenly
    across the ISO calendar weeks between its estimated_start and
    estimated_end, then summed per member per week. Dividing by the member's
    weekly capacity fraction (default_weekly_hours / 40, defaulting to
    full-time when unset) converts that into a percentage — a week where a
    member's tasks sum to exactly their weekly capacity is 100%.

    Tasks missing an assignee, a full date pair, or an effort estimate are
    skipped (their load can't be placed). Only (member, week) combinations
    with at least one contributing task are returned — the caller is
    responsible for filling in the full member x week grid if it wants a
    dense heatmap.

    Returns: list of {"member_id", "week_start" (that week's Monday), "pct"}.
    """
    tasks = (
        session.query(Task)
        .filter(Task.assignee_id.isnot(None))
        .filter(Task.estimated_start.isnot(None))
        .filter(Task.estimated_end.isnot(None))
        .filter(Task.estimated_effort_weeks.isnot(None))
        .all()
    )

    load: dict[tuple[int, date], float] = {}
    for task in tasks:
        weeks = _iso_weeks_between(task.estimated_start, task.estimated_end)
        if not weeks:
            continue
        share = task.estimated_effort_weeks / len(weeks)
        for week_start in weeks:
            key = (task.assignee_id, week_start)
            load[key] = load.get(key, 0.0) + share

    capacity_fraction = {
        m.id: (m.default_weekly_hours or STANDARD_WEEKLY_HOURS) / STANDARD_WEEKLY_HOURS
        for m in session.query(TeamMember).all()
    }

    return [
        {
            "member_id": member_id,
            "week_start": week_start,
            "pct": round((weekly_load / capacity_fraction.get(member_id, 1.0)) * 100, 1),
        }
        for (member_id, week_start), weekly_load in load.items()
    ]


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
