"""Home / landing page.

Leads with a KPI row, then the capacity-vs-estimate overview. More
visualisations will be added here later.
"""

from __future__ import annotations

from nicegui import ui

from app.db import get_session
from app.pages.layout import header
from app.services import capacity_summary, kpi_summary

# (label, kpi_summary key, icon, colour) for the KPI row, in display order.
KPI_TILES = [
    ("Tasks in progress", "tasks_in_progress", "play_circle", "#1976d2"),
    ("Tasks blocked", "tasks_blocked", "block", "#e53935"),
    ("Active workstreams", "workstreams_active", "timeline", "#43a047"),
    ("People over-allocated", "people_over_allocated", "warning", "#fb8c00"),
]

COLUMNS = [
    {"name": "name", "label": "Team member", "field": "name", "align": "left"},
    {"name": "available", "label": "Available (wks)", "field": "available"},
    {"name": "allocated", "label": "Allocated to workstreams (wks)", "field": "allocated"},
    {"name": "estimated_open", "label": "Estimated open tasks (wks)", "field": "estimated_open"},
    {"name": "remaining", "label": "Remaining (wks)", "field": "remaining"},
    {"name": "flag", "label": "Status", "field": "flag", "align": "left"},
]


def _kpi_tile(label: str, value: int, icon: str, color: str) -> None:
    with ui.card().classes("flex-1 min-w-[180px]"):
        with ui.row().classes("items-center gap-3"):
            with ui.element("div").classes("rounded-full flex items-center justify-center").style(
                f"background-color:{color}1a; width:44px; height:44px; flex-shrink:0;"
            ):
                ui.icon(icon).style(f"color:{color}; font-size:24px;")
            with ui.column().classes("gap-0"):
                ui.label(str(value)).classes("text-2xl font-bold")
                ui.label(label).classes("text-xs text-gray-500")


def build() -> None:
    header("Home")

    with get_session() as session:
        kpis = kpi_summary(session)
        summary = capacity_summary(session)

    rows = [
        {
            **row,
            "flag": "Over-allocated" if row["over_allocated"] else "OK",
        }
        for row in summary
    ]

    with ui.column().classes("w-full p-4 gap-4"):
        with ui.row().classes("w-full gap-4 flex-wrap"):
            for label, key, icon, color in KPI_TILES:
                _kpi_tile(label, kpis[key], icon, color)

        ui.label("Capacity overview").classes("text-2xl font-bold")
        ui.label(
            "Available capacity vs. workstream allocation vs. open task estimates, "
            "per person (person-weeks, summed across all periods)."
        ).classes("text-sm text-gray-500")

        table = ui.table(columns=COLUMNS, rows=rows, row_key="name").classes("w-full")
        # Colour the status cell red when over-allocated.
        table.add_slot(
            "body-cell-flag",
            '<q-td :props="props">'
            '<q-badge :color="props.value === \'Over-allocated\' ? \'red\' : \'green\'">'
            "{{ props.value }}</q-badge></q-td>",
        )

        ui.separator()
        with ui.card().classes("w-full bg-blue-50"):
            ui.label("More visualisations coming soon").classes("text-base font-medium")
            ui.label(
                "This home page will grow charts for capacity trends, workstream burn-down, "
                "and estimate history over time."
            ).classes("text-sm text-gray-600")
