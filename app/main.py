"""NiceGUI entrypoint: initialise the in-memory DB, seed from CSV, register pages."""

from __future__ import annotations

from nicegui import ui

from app.db import get_session, init_db
from app.pages import capacity, home, people, strategy, tasks, workstreams
from app.seed import load_csvs


def bootstrap() -> None:
    """Create tables and seed from CSV. In-memory DB, so this runs every start."""
    init_db()
    with get_session() as session:
        load_csvs(session)


@ui.page("/")
def index() -> None:
    home.build()


@ui.page("/people")
def people_page() -> None:
    people.build()


@ui.page("/strategy")
def strategy_page() -> None:
    strategy.build()


@ui.page("/workstreams")
def workstreams_page() -> None:
    workstreams.build()


@ui.page("/tasks")
def tasks_page() -> None:
    tasks.build()


@ui.page("/capacity")
def capacity_page() -> None:
    capacity.build()


bootstrap()

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="Capacity Estimation", reload=False, port=8080)
