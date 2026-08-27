"""Shared data-access helpers used by the UI pages.

Kept UI-agnostic so they can be unit-tested directly.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    EstimateHistory,
    StrategyItem,
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


def _capacity_fraction(default_weekly_hours: float | None) -> float:
    """A member's weekly capacity as a fraction of full-time. Members without
    an hours value set are assumed full-time."""
    return (default_weekly_hours or STANDARD_WEEKLY_HOURS) / STANDARD_WEEKLY_HOURS


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


def workstream_allocation_pct(session: Session) -> list[dict]:
    """Each person's standing % allocation across workstreams (the
    `allocation_pct` rows of `workstream_allocation`, always `period_id IS
    NULL` — see docs/data-model.md). Distinct from the period-scoped
    `allocated_weeks` top-down plan used by capacity_summary().

    Returns: list of {"team_member_id", "workstream_id", "allocation_pct"}.
    """
    rows = (
        session.query(WorkstreamAllocation)
        .filter(WorkstreamAllocation.period_id.is_(None))
        .filter(WorkstreamAllocation.allocation_pct.isnot(None))
        .all()
    )
    return [
        {
            "team_member_id": r.team_member_id,
            "workstream_id": r.workstream_id,
            "allocation_pct": r.allocation_pct,
        }
        for r in rows
    ]


def set_person_allocations(session: Session, person_id: int, allocations: dict[int, float]) -> None:
    """Replace a person's standing workstream allocation_pct rows with `allocations`
    (workstream_id -> pct). A workstream missing from `allocations`, or mapped to a
    falsy pct, has its row deleted rather than kept at 0 — so a person's allocation
    rows only ever list workstreams they're actually committed to.
    """
    existing = {
        row.workstream_id: row
        for row in session.query(WorkstreamAllocation)
        .filter_by(team_member_id=person_id, period_id=None)
        .all()
    }
    for workstream_id, pct in allocations.items():
        row = existing.pop(workstream_id, None)
        if pct:
            if row:
                row.allocation_pct = pct
            else:
                session.add(
                    WorkstreamAllocation(
                        team_member_id=person_id,
                        workstream_id=workstream_id,
                        period_id=None,
                        allocation_pct=pct,
                    )
                )
        elif row:
            session.delete(row)
    for leftover in existing.values():
        session.delete(leftover)


def workstream_capacity_check(session: Session) -> list[dict]:
    """Per-workstream comparison of top-down allocated capacity against
    bottom-up required task effort, both in person-weeks:

    - allocated_weeks: each person's standing allocation_pct on this
      workstream (see workstream_allocation_pct), converted to a weekly
      capacity rate (pct/100 * their capacity fraction) and spread across the
      workstream's estimated duration.
    - required_weeks: sum of estimated_effort_weeks for this workstream's
      tasks that aren't done/cancelled — the total remaining ask, regardless
      of whether those tasks are assigned yet.
    - sufficient: allocated_weeks >= required_weeks.

    Workstreams missing an estimated_start/estimated_end are skipped — there's
    no duration to spread a standing % allocation over, so they can't be
    compared on this person-weeks basis.
    """
    capacity_fraction = {m.id: _capacity_fraction(m.default_weekly_hours) for m in session.query(TeamMember).all()}

    alloc_pct: dict[int, list[tuple[int, float]]] = {}
    for r in (
        session.query(WorkstreamAllocation)
        .filter(WorkstreamAllocation.period_id.is_(None))
        .filter(WorkstreamAllocation.allocation_pct.isnot(None))
        .all()
    ):
        alloc_pct.setdefault(r.workstream_id, []).append((r.team_member_id, r.allocation_pct))

    required = dict(
        session.query(
            Task.workstream_id,
            func.coalesce(func.sum(Task.estimated_effort_weeks), 0.0),
        )
        .filter(Task.workstream_id.isnot(None))
        .filter(Task.status.notin_(CLOSED_STATUSES))
        .group_by(Task.workstream_id)
    )

    rows = []
    for ws in session.query(Workstream).order_by(Workstream.id).all():
        if not (ws.estimated_start and ws.estimated_end):
            continue
        duration_weeks = max((ws.estimated_end - ws.estimated_start).days / 7.0, 0.0)
        allocated_weeks = sum(
            (pct / 100.0) * capacity_fraction.get(member_id, 1.0) * duration_weeks
            for member_id, pct in alloc_pct.get(ws.id, [])
        )
        required_weeks = float(required.get(ws.id, 0.0) or 0.0)
        rows.append(
            {
                "workstream_id": ws.id,
                "name": ws.name,
                "allocated_weeks": round(allocated_weeks, 2),
                "required_weeks": round(required_weeks, 2),
                "sufficient": allocated_weeks >= required_weeks,
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


def workstream_assignments(session: Session) -> list[dict]:
    """Per (workstream, person) pair: total open estimated effort and which
    tasks contribute, for the Home page's workstream x person grid.

    Only tasks with both an assignee and a workstream, and not done/cancelled
    (see CLOSED_STATUSES), are counted — this is *current* workload
    distribution, not a historical/completed record.

    Returns: list of {"workstream_id", "person_id", "effort_weeks",
    "task_count", "task_names"}.
    """
    tasks = (
        session.query(Task)
        .filter(Task.assignee_id.isnot(None))
        .filter(Task.workstream_id.isnot(None))
        .filter(Task.status.notin_(CLOSED_STATUSES))
        .all()
    )

    agg: dict[tuple[int, int], dict] = {}
    for task in tasks:
        key = (task.workstream_id, task.assignee_id)
        entry = agg.setdefault(key, {"effort_weeks": 0.0, "task_count": 0, "task_names": []})
        entry["effort_weeks"] += task.estimated_effort_weeks or 0.0
        entry["task_count"] += 1
        entry["task_names"].append(task.name)

    return [
        {
            "workstream_id": workstream_id,
            "person_id": person_id,
            "effort_weeks": round(v["effort_weeks"], 2),
            "task_count": v["task_count"],
            "task_names": v["task_names"],
        }
        for (workstream_id, person_id), v in agg.items()
    ]


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _month_end(month_start: date) -> date:
    """Last day of the calendar month `month_start` falls in."""
    if month_start.month == 12:
        return date(month_start.year + 1, 1, 1) - timedelta(days=1)
    return date(month_start.year, month_start.month + 1, 1) - timedelta(days=1)


def _next_month(month_start: date) -> date:
    if month_start.month == 12:
        return date(month_start.year + 1, 1, 1)
    return date(month_start.year, month_start.month + 1, 1)


def _days_in_month(month_start: date) -> int:
    return (_month_end(month_start) - month_start).days + 1


def _month_range(start: date, end: date) -> list[date]:
    """First-of-month date for every calendar month from start through end
    (inclusive), in order."""
    months = []
    current = _month_start(start)
    last = _month_start(end)
    while current <= last:
        months.append(current)
        current = _next_month(current)
    return months


def _days_in_month_overlap(month_start: date, span_start: date, span_end: date) -> int:
    """Days of [span_start, span_end] that fall within the calendar month
    starting at month_start (0 if there's no overlap)."""
    overlap_start = max(span_start, month_start)
    overlap_end = min(span_end, _month_end(month_start))
    return max((overlap_end - overlap_start).days + 1, 0)


def team_capacity_by_month(session: Session) -> dict:
    """Team time (person-weeks) going toward each strategy item, by calendar
    month, for the Home page's team capacity chart.

    Each dated task's estimated_effort_weeks is spread across the calendar
    months its [estimated_start, estimated_end] span touches, weighted by the
    number of days of overlap in each month — a day-weighted split, distinct
    from weekly_allocation()'s equal-per-ISO-week split, since the bucket
    here is a variable-length calendar month rather than a week.

    Unlike workstream_assignments(), this includes tasks of *every* status,
    including done/cancelled: the chart trends across past, present and
    future months, and excluding completed work would leave misleading gaps
    in past months. A task whose workstream doesn't map to a strategy item
    (or has no workstream at all) is grouped under a synthetic "Unassigned"
    bucket (strategy_item_id=None) so the stack still totals all planned
    effort rather than silently dropping it.

    Also returns each month's total team available time — the sum of active
    members' capacity fraction (default_weekly_hours / 40) times that
    month's length in weeks (days / 7) — as a reference for how allocated
    effort compares to capacity.

    Returns {
        "months": [date, ...] (first-of-month, ascending, contiguous —
            filled in even for months with no task activity),
        "strategy_items": [{"id": int|None, "name": str}, ...] (id=None is
            "Unassigned"; named items sorted alphabetically, Unassigned last),
        "effort": [{"month", "strategy_item_id", "effort_weeks"}, ...]
            (sparse — only nonzero (month, strategy_item) combinations),
        "available": [{"month", "available_weeks"}, ...] (one per month),
    }
    """
    tasks = (
        session.query(Task)
        .filter(Task.estimated_start.isnot(None))
        .filter(Task.estimated_end.isnot(None))
        .filter(Task.estimated_effort_weeks.isnot(None))
        .all()
    )
    if not tasks:
        return {"months": [], "strategy_items": [], "effort": [], "available": []}

    workstream_to_strategy = dict(session.query(Workstream.id, Workstream.strategy_item_id).all())
    strategy_names = dict(session.query(StrategyItem.id, StrategyItem.name).all())

    effort: dict[tuple[int | None, date], float] = {}
    touched_months: set[date] = set()

    for task in tasks:
        months = _month_range(task.estimated_start, task.estimated_end)
        total_days = (task.estimated_end - task.estimated_start).days + 1
        strategy_id = workstream_to_strategy.get(task.workstream_id) if task.workstream_id else None

        for month in months:
            days = _days_in_month_overlap(month, task.estimated_start, task.estimated_end)
            if days <= 0:
                continue
            share = task.estimated_effort_weeks * (days / total_days)
            key = (strategy_id, month)
            effort[key] = effort.get(key, 0.0) + share
            touched_months.add(month)

    months_sorted = _month_range(min(touched_months), max(touched_months)) if touched_months else []

    strategy_ids_present = {sid for (sid, _month) in effort}
    strategy_items = sorted(
        (
            {"id": sid, "name": strategy_names.get(sid, "Unassigned") if sid is not None else "Unassigned"}
            for sid in strategy_ids_present
        ),
        key=lambda item: (item["id"] is None, item["name"]),
    )

    active_capacity_fraction = sum(
        _capacity_fraction(m.default_weekly_hours)
        for m in session.query(TeamMember).filter(TeamMember.active.is_(True)).all()
    )
    available = [
        {
            "month": month,
            "available_weeks": round(active_capacity_fraction * (_days_in_month(month) / 7.0), 2),
        }
        for month in months_sorted
    ]

    effort_rows = [
        {"month": month, "strategy_item_id": strategy_id, "effort_weeks": round(value, 2)}
        for (strategy_id, month), value in effort.items()
    ]

    return {
        "months": months_sorted,
        "strategy_items": strategy_items,
        "effort": effort_rows,
        "available": available,
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
        m.id: _capacity_fraction(m.default_weekly_hours)
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
