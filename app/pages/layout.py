"""Shared page chrome: header with navigation and the CSV export action."""

from __future__ import annotations

from nicegui import ui

from app.db import get_session
from app.pages.theme import apply_theme
from app.seed import export_csvs

APP_NAME = "On My Plate"
APP_ICON = "restaurant"  # a literal plate + utensils, matching the app name pun

NAV = [
    ("Home", "/"),
    ("People", "/people"),
    ("Workstreams", "/workstreams"),
    ("Tasks", "/tasks"),
]


def _do_export() -> None:
    with get_session() as session:
        export_csvs(session)
    ui.notify("Exported current data to data/*.csv", type="positive")


def header(active: str) -> None:
    """Render the top navigation bar. `active` is the label to highlight."""
    apply_theme()
    with ui.header().classes("items-center justify-between px-4"):
        with ui.row().classes("items-center gap-4"):
            with ui.row().classes("items-center gap-2"):
                ui.icon(APP_ICON).classes("text-2xl")
                ui.label(APP_NAME).classes("text-lg font-bold")
            for label, target in NAV:
                link = ui.link(label, target).classes("text-white no-underline")
                if label == active:
                    link.classes("font-bold underline")
        ui.button("Export to CSV", icon="download", on_click=_do_export).props("flat color=white")
