"""Small helpers shared across CRUD pages: date parsing, FK option lists, and
the task-status colour map used by the timeline charts (workstreams + people)."""

from __future__ import annotations

from datetime import date

from app.db import get_session
from app.models import CapacityPeriod, StrategyItem, TeamMember, Workstream

# Status -> colour, shared by every timeline/status visualisation.
STATUS_COLORS = {
    "not_started": "#9e9e9e",
    "in_progress": "#1976d2",
    "blocked": "#e53935",
    "done": "#43a047",
    "cancelled": "#bdbdbd",
}


def parse_date(value: str | None) -> date | None:
    value = (value or "").strip()
    return date.fromisoformat(value) if value else None


def fmt_date(value: date | None) -> str:
    return value.isoformat() if value else ""


def member_options() -> dict[int, str]:
    with get_session() as session:
        return {m.id: m.name for m in session.query(TeamMember).order_by(TeamMember.name).all()}


def strategy_options() -> dict[int, str]:
    with get_session() as session:
        return {s.id: s.name for s in session.query(StrategyItem).order_by(StrategyItem.name).all()}


def workstream_options() -> dict[int, str]:
    with get_session() as session:
        return {w.id: w.name for w in session.query(Workstream).order_by(Workstream.name).all()}


def period_options() -> dict[int, str]:
    with get_session() as session:
        return {p.id: p.name for p in session.query(CapacityPeriod).order_by(CapacityPeriod.id).all()}
