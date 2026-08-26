"""Capacity page: tabbed CRUD for periods, per-member availability, and
workstream allocations (the three capacity/allocation tables)."""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from app.db import get_session
from app.models import CapacityPeriod, TeamMemberCapacity, WorkstreamAllocation
from app.pages.common import (
    fmt_date,
    member_options,
    parse_date,
    period_options,
    workstream_options,
)
from app.pages.layout import header

_EDIT_SLOT = (
    '<q-td :props="props"><q-btn dense flat icon="edit" '
    "@click=\"() => $parent.$emit('edit', props.row)\"/></q-td>"
)


def _crud_panel(add_label: str, columns: list[dict], load_rows: Callable,
                open_form: Callable) -> None:
    """Render a table + Add button; wire per-row edit. `open_form(row, on_done)`
    builds the dialog and calls on_done() after a successful save."""
    container = ui.column().classes("w-full")

    def refresh() -> None:
        container.clear()
        with container:
            table = ui.table(columns=columns, rows=load_rows(), row_key="id").classes("w-full")
            table.add_slot("body-cell-actions", _EDIT_SLOT)
            table.on("edit", lambda e: open_form(e.args, refresh))

    with ui.row().classes("items-center gap-4 py-2"):
        ui.button(add_label, icon="add", on_click=lambda: open_form(None, refresh))
    refresh()


def _dialog_buttons(dialog, save: Callable) -> None:
    with ui.row().classes("justify-end w-full"):
        ui.button("Cancel", on_click=dialog.close).props("flat")
        ui.button("Save", on_click=save)


# --- Periods ---------------------------------------------------------------

_PERIOD_COLUMNS = [
    {"name": "id", "label": "ID", "field": "id", "align": "left"},
    {"name": "name", "label": "Name", "field": "name", "align": "left"},
    {"name": "start_date", "label": "Start", "field": "start_date"},
    {"name": "end_date", "label": "End", "field": "end_date"},
    {"name": "actions", "label": "", "field": "actions"},
]


def _load_periods() -> list[dict]:
    with get_session() as session:
        return [
            {"id": p.id, "name": p.name, "start_date": fmt_date(p.start_date),
             "end_date": fmt_date(p.end_date)}
            for p in session.query(CapacityPeriod).order_by(CapacityPeriod.id).all()
        ]


def _period_form(row: dict | None, on_done: Callable) -> None:
    row = row or {}
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("Edit period" if row else "Add period").classes("text-lg font-bold")
        name = ui.input("Name", value=row.get("name", "")).classes("w-full")
        start = ui.input("Start (YYYY-MM-DD)", value=row.get("start_date", "")).classes("w-full")
        end = ui.input("End (YYYY-MM-DD)", value=row.get("end_date", "")).classes("w-full")

        def save() -> None:
            if not name.value.strip():
                ui.notify("Name is required", type="negative")
                return
            with get_session() as session:
                obj = session.get(CapacityPeriod, row["id"]) if row else CapacityPeriod()
                obj.name = name.value.strip()
                obj.start_date = parse_date(start.value)
                obj.end_date = parse_date(end.value)
                if not row:
                    session.add(obj)
            dialog.close()
            on_done()
            ui.notify("Saved", type="positive")

        _dialog_buttons(dialog, save)
    dialog.open()


# --- Availability (team_member_capacity) -----------------------------------

_AVAIL_COLUMNS = [
    {"name": "id", "label": "ID", "field": "id", "align": "left"},
    {"name": "member", "label": "Team member", "field": "member", "align": "left"},
    {"name": "period", "label": "Period", "field": "period", "align": "left"},
    {"name": "available_weeks", "label": "Available (wks)", "field": "available_weeks"},
    {"name": "actions", "label": "", "field": "actions"},
]


def _load_availability() -> list[dict]:
    members = member_options()
    periods = period_options()
    with get_session() as session:
        return [
            {
                "id": c.id,
                "team_member_id": c.team_member_id,
                "member": members.get(c.team_member_id, ""),
                "period_id": c.period_id,
                "period": periods.get(c.period_id, ""),
                "available_weeks": c.available_weeks,
            }
            for c in session.query(TeamMemberCapacity).order_by(TeamMemberCapacity.id).all()
        ]


def _availability_form(row: dict | None, on_done: Callable) -> None:
    row = row or {}
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("Edit availability" if row else "Add availability").classes("text-lg font-bold")
        member = ui.select(member_options(), label="Team member", value=row.get("team_member_id"), with_input=True).classes("w-full")
        period = ui.select(period_options(), label="Period", value=row.get("period_id")).classes("w-full")
        weeks = ui.number("Available (weeks)", value=row.get("available_weeks"), step=0.5)

        def save() -> None:
            if member.value is None or period.value is None:
                ui.notify("Team member and period are required", type="negative")
                return
            with get_session() as session:
                obj = session.get(TeamMemberCapacity, row["id"]) if row else TeamMemberCapacity()
                obj.team_member_id = member.value
                obj.period_id = period.value
                obj.available_weeks = weeks.value
                if not row:
                    session.add(obj)
            dialog.close()
            on_done()
            ui.notify("Saved", type="positive")

        _dialog_buttons(dialog, save)
    dialog.open()


# --- Allocations (workstream_allocation) -----------------------------------

_ALLOC_COLUMNS = [
    {"name": "id", "label": "ID", "field": "id", "align": "left"},
    {"name": "workstream", "label": "Workstream", "field": "workstream", "align": "left"},
    {"name": "member", "label": "Team member", "field": "member", "align": "left"},
    {"name": "period", "label": "Period", "field": "period", "align": "left"},
    {"name": "allocated_weeks", "label": "Allocated (wks)", "field": "allocated_weeks"},
    {"name": "actions", "label": "", "field": "actions"},
]


def _load_allocations() -> list[dict]:
    members = member_options()
    periods = period_options()
    workstreams = workstream_options()
    with get_session() as session:
        return [
            {
                "id": a.id,
                "workstream_id": a.workstream_id,
                "workstream": workstreams.get(a.workstream_id, ""),
                "team_member_id": a.team_member_id,
                "member": members.get(a.team_member_id, ""),
                "period_id": a.period_id,
                "period": periods.get(a.period_id, ""),
                "allocated_weeks": a.allocated_weeks,
            }
            for a in session.query(WorkstreamAllocation).order_by(WorkstreamAllocation.id).all()
        ]


def _allocation_form(row: dict | None, on_done: Callable) -> None:
    row = row or {}
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label("Edit allocation" if row else "Add allocation").classes("text-lg font-bold")
        workstream = ui.select(workstream_options(), label="Workstream", value=row.get("workstream_id"), with_input=True).classes("w-full")
        member = ui.select(member_options(), label="Team member", value=row.get("team_member_id"), with_input=True).classes("w-full")
        period = ui.select(period_options(), label="Period", value=row.get("period_id")).classes("w-full")
        weeks = ui.number("Allocated (weeks)", value=row.get("allocated_weeks"), step=0.5)

        def save() -> None:
            if workstream.value is None or member.value is None:
                ui.notify("Workstream and team member are required", type="negative")
                return
            with get_session() as session:
                obj = session.get(WorkstreamAllocation, row["id"]) if row else WorkstreamAllocation()
                obj.workstream_id = workstream.value
                obj.team_member_id = member.value
                obj.period_id = period.value
                obj.allocated_weeks = weeks.value
                if not row:
                    session.add(obj)
            dialog.close()
            on_done()
            ui.notify("Saved", type="positive")

        _dialog_buttons(dialog, save)
    dialog.open()


def build() -> None:
    header("Capacity")
    with ui.column().classes("w-full p-4 gap-2"):
        ui.label("Capacity planning").classes("text-xl font-bold")
        with ui.tabs() as tabs:
            ui.tab("periods", "Periods")
            ui.tab("availability", "Availability")
            ui.tab("allocations", "Allocations")
        with ui.tab_panels(tabs, value="periods").classes("w-full"):
            with ui.tab_panel("periods"):
                _crud_panel("Add period", _PERIOD_COLUMNS, _load_periods, _period_form)
            with ui.tab_panel("availability"):
                _crud_panel("Add availability", _AVAIL_COLUMNS, _load_availability, _availability_form)
            with ui.tab_panel("allocations"):
                _crud_panel("Add allocation", _ALLOC_COLUMNS, _load_allocations, _allocation_form)
