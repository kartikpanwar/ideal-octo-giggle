"""Home / landing page.

Hosts the capacity-vs-estimate overview as its first widget. More visualisations
will be added here later.
"""

from __future__ import annotations

from nicegui import ui

from app.db import get_session
from app.pages.layout import header
from app.services import capacity_summary

COLUMNS = [
    {"name": "name", "label": "Team member", "field": "name", "align": "left"},
    {"name": "available", "label": "Available (wks)", "field": "available"},
    {"name": "allocated", "label": "Allocated to workstreams (wks)", "field": "allocated"},
    {"name": "estimated_open", "label": "Estimated open tasks (wks)", "field": "estimated_open"},
    {"name": "remaining", "label": "Remaining (wks)", "field": "remaining"},
    {"name": "flag", "label": "Status", "field": "flag", "align": "left"},
]


def build() -> None:
    header("Home")

    with get_session() as session:
        summary = capacity_summary(session)

    rows = [
        {
            **row,
            "flag": "Over-allocated" if row["over_allocated"] else "OK",
        }
        for row in summary
    ]

    with ui.column().classes("w-full p-4 gap-4"):
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
