"""CSV -> DB -> CSV round-trip: exporting then reloading yields identical rows."""

from __future__ import annotations

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
from app.seed import export_csvs, load_csvs


def _counts(session):
    return {
        "people": session.query(TeamMember).count(),
        "strategy": session.query(StrategyItem).count(),
        "workstreams": session.query(Workstream).count(),
        "tasks": session.query(Task).count(),
        "periods": session.query(CapacityPeriod).count(),
        "availability": session.query(TeamMemberCapacity).count(),
        "allocations": session.query(WorkstreamAllocation).count(),
        "history": session.query(EstimateHistory).count(),
    }


def _clear_all(session):
    # Delete child tables before parents (reverse of metadata create order).
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.flush()


def test_load_seed_data(session):
    load_csvs(session)  # from the real data/ dir
    counts = _counts(session)
    assert counts["people"] >= 1
    assert counts["tasks"] >= 1
    assert counts["periods"] >= 1
    assert counts["allocations"] >= 1
    assert counts["history"] >= 1


def test_roundtrip(session, tmp_path):
    load_csvs(session)  # load real seed data
    before = _counts(session)

    # Export to a temp dir, then reload into a cleared DB.
    export_csvs(session, data_dir=tmp_path)
    _clear_all(session)

    load_csvs(session, data_dir=tmp_path)
    assert _counts(session) == before


def test_task_fields_preserved(session, tmp_path):
    load_csvs(session)
    original = {
        t.id: (t.name, t.status, t.estimated_effort_weeks, t.estimated_start)
        for t in session.query(Task).all()
    }
    export_csvs(session, data_dir=tmp_path)
    _clear_all(session)
    load_csvs(session, data_dir=tmp_path)
    reloaded = {
        t.id: (t.name, t.status, t.estimated_effort_weeks, t.estimated_start)
        for t in session.query(Task).all()
    }
    assert reloaded == original
