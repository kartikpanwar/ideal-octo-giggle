"""Seed the in-memory DB from CSV files and export it back to CSV.

CSV headers match model column names. Parents are loaded before children so foreign
keys resolve. Type coercion is driven by each column's SQLAlchemy type, so the same
logic round-trips every table.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import Boolean, Date, DateTime, Float, Integer
from sqlalchemy.orm import Session

from app.models import (
    Base,
    CapacityPeriod,
    EstimateHistory,
    StrategyItem,
    Task,
    TeamMember,
    TeamMemberCapacity,
    Workstream,
    WorkstreamAllocation,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Order matters: parents before children (FK resolution on load).
CSV_TABLES: list[tuple[type[Base], str]] = [
    (TeamMember, "people.csv"),
    (StrategyItem, "strategy_items.csv"),
    (Workstream, "workstreams.csv"),
    (Task, "tasks.csv"),
    (CapacityPeriod, "capacity_period.csv"),
    (TeamMemberCapacity, "team_member_capacity.csv"),
    (WorkstreamAllocation, "workstream_allocation.csv"),
    (EstimateHistory, "estimate_history.csv"),
]


def _coerce(value: str, column) -> object:
    """Convert a CSV string into the Python type for a SQLAlchemy column."""
    if value is None or value == "":
        return None
    col_type = column.type
    if isinstance(col_type, Boolean):
        return value.strip().lower() in {"1", "true", "yes", "t"}
    if isinstance(col_type, Integer):
        return int(value)
    if isinstance(col_type, Float):
        return float(value)
    if isinstance(col_type, DateTime):
        return datetime.fromisoformat(value)
    if isinstance(col_type, Date):
        return date.fromisoformat(value)
    return value


def _serialize(value: object) -> str:
    """Convert a Python value into a CSV cell."""
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def load_csvs(session: Session, data_dir: Path = DATA_DIR) -> None:
    """Load every CSV into its table. Missing files are skipped."""
    for model, filename in CSV_TABLES:
        path = data_dir / filename
        if not path.exists():
            continue
        columns = model.__table__.columns
        with path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                kwargs = {
                    name: _coerce(row[name], columns[name])
                    for name in row
                    if name in columns
                }
                session.add(model(**kwargs))
    session.flush()


def export_csvs(session: Session, data_dir: Path = DATA_DIR) -> None:
    """Write every table back to its CSV, preserving column order."""
    data_dir.mkdir(parents=True, exist_ok=True)
    for model, filename in CSV_TABLES:
        columns = [c.name for c in model.__table__.columns]
        rows = session.query(model).order_by(model.id).all()
        with (data_dir / filename).open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(columns)
            for obj in rows:
                writer.writerow([_serialize(getattr(obj, name)) for name in columns])
