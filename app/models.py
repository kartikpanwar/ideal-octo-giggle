"""SQLAlchemy ORM models for the capacity estimation app.

Mirrors docs/data-model.md. The v1 UI touches TeamMember, StrategyItem, Workstream,
Task and EstimateHistory. The capacity/allocation tables are defined so the schema is
complete, but have no UI or seed data yet.

Effort and capacity are measured in person-weeks. Estimated start/end are calendar dates.
"""

from __future__ import annotations

from datetime import date, datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# --- Status vocabularies (kept as plain strings for CSV friendliness) ---

TASK_STATUSES = ["not_started", "in_progress", "blocked", "done", "cancelled"]
WORKSTREAM_STATUSES = TASK_STATUSES
STRATEGY_STATUSES = ["proposed", "active", "on_hold", "done", "cancelled"]
TASK_PRIORITIES = ["low", "medium", "high"]


class TeamMember(Base):
    __tablename__ = "team_member"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str | None] = mapped_column(String)
    default_weekly_hours: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    active_from: Mapped[date | None] = mapped_column(Date)

    tasks: Mapped[list[Task]] = relationship(back_populates="assignee")


class StrategyItem(Base):
    __tablename__ = "strategy_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="proposed")
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("team_member.id"))
    target_start: Mapped[date | None] = mapped_column(Date)
    target_end: Mapped[date | None] = mapped_column(Date)

    workstreams: Mapped[list[Workstream]] = relationship(back_populates="strategy_item")


class Workstream(Base):
    __tablename__ = "workstream"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    strategy_item_id: Mapped[int | None] = mapped_column(ForeignKey("strategy_item.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="not_started")
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("team_member.id"))
    estimated_start: Mapped[date | None] = mapped_column(Date)
    estimated_end: Mapped[date | None] = mapped_column(Date)

    strategy_item: Mapped[StrategyItem | None] = relationship(back_populates="workstreams")
    tasks: Mapped[list[Task]] = relationship(back_populates="workstream")


class Task(Base):
    __tablename__ = "task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workstream_id: Mapped[int | None] = mapped_column(ForeignKey("workstream.id"))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("team_member.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="not_started")
    priority: Mapped[str | None] = mapped_column(String, default="medium")
    estimated_effort_weeks: Mapped[float | None] = mapped_column(Float)
    estimated_start: Mapped[date | None] = mapped_column(Date)
    estimated_end: Mapped[date | None] = mapped_column(Date)
    actual_start: Mapped[date | None] = mapped_column(Date)
    actual_end: Mapped[date | None] = mapped_column(Date)

    workstream: Mapped[Workstream | None] = relationship(back_populates="tasks")
    assignee: Mapped[TeamMember | None] = relationship(back_populates="tasks")


class EstimateHistory(Base):
    """Append-only log written on status/estimate changes (see docs/data-model.md)."""

    __tablename__ = "estimate_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)  # task|workstream|strategy_item
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    estimated_start: Mapped[date | None] = mapped_column(Date)
    estimated_end: Mapped[date | None] = mapped_column(Date)
    status_update: Mapped[str | None] = mapped_column(Text)
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("team_member.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    note: Mapped[str | None] = mapped_column(Text)


# --- Capacity / allocation tables: defined for schema completeness, no UI in v1 ---

class CapacityPeriod(Base):
    __tablename__ = "capacity_period"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)


class TeamMemberCapacity(Base):
    __tablename__ = "team_member_capacity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_member_id: Mapped[int] = mapped_column(ForeignKey("team_member.id"))
    period_id: Mapped[int] = mapped_column(ForeignKey("capacity_period.id"))
    available_weeks: Mapped[float | None] = mapped_column(Float)


class WorkstreamAllocation(Base):
    __tablename__ = "workstream_allocation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workstream_id: Mapped[int] = mapped_column(ForeignKey("workstream.id"))
    team_member_id: Mapped[int] = mapped_column(ForeignKey("team_member.id"))
    period_id: Mapped[int | None] = mapped_column(ForeignKey("capacity_period.id"))
    allocated_weeks: Mapped[float | None] = mapped_column(Float)
