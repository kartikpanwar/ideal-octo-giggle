"""Workstream CRUD page (child of strategy item)."""

from __future__ import annotations

from nicegui import ui

from app.db import get_session
from app.models import WORKSTREAM_STATUSES, Workstream
from app.pages.common import fmt_date, member_options, parse_date, strategy_options
from app.pages.layout import header

COLUMNS = [
    {"name": "id", "label": "ID", "field": "id", "align": "left"},
    {"name": "name", "label": "Name", "field": "name", "align": "left"},
    {"name": "strategy", "label": "Strategy item", "field": "strategy", "align": "left"},
    {"name": "status", "label": "Status", "field": "status", "align": "left"},
    {"name": "lead", "label": "Lead", "field": "lead", "align": "left"},
    {"name": "estimated_start", "label": "Est. start", "field": "estimated_start"},
    {"name": "estimated_end", "label": "Est. end", "field": "estimated_end"},
    {"name": "actions", "label": "", "field": "actions"},
]


def _load_rows() -> list[dict]:
    strategies = strategy_options()
    leads = member_options()
    with get_session() as session:
        return [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "strategy_item_id": w.strategy_item_id,
                "strategy": strategies.get(w.strategy_item_id, ""),
                "status": w.status,
                "lead_id": w.lead_id,
                "lead": leads.get(w.lead_id, ""),
                "estimated_start": fmt_date(w.estimated_start),
                "estimated_end": fmt_date(w.estimated_end),
            }
            for w in session.query(Workstream).order_by(Workstream.id).all()
        ]


def _save(row_id, name, description, strategy_id, status, lead_id, start, end) -> None:
    with get_session() as session:
        ws = session.get(Workstream, row_id) if row_id else Workstream()
        ws.name = name
        ws.description = description or None
        ws.strategy_item_id = strategy_id
        ws.status = status
        ws.lead_id = lead_id
        ws.estimated_start = parse_date(start)
        ws.estimated_end = parse_date(end)
        if row_id is None:
            session.add(ws)


def build() -> None:
    header("Workstreams")
    table_holder = ui.column().classes("w-full")

    def refresh() -> None:
        table_holder.clear()
        with table_holder:
            table = ui.table(columns=COLUMNS, rows=_load_rows(), row_key="id").classes("w-full")
            table.add_slot(
                "body-cell-actions",
                '<q-td :props="props"><q-btn dense flat icon="edit" '
                "@click=\"() => $parent.$emit('edit', props.row)\"/></q-td>",
            )
            table.on("edit", lambda e: open_form(e.args))

    def open_form(row: dict | None = None) -> None:
        row = row or {}
        with ui.dialog() as dialog, ui.card().classes("w-96"):
            ui.label("Edit workstream" if row else "Add workstream").classes("text-lg font-bold")
            name = ui.input("Name", value=row.get("name", "")).classes("w-full")
            description = ui.textarea("Description", value=row.get("description") or "").classes("w-full")
            strategy = ui.select(strategy_options(), label="Strategy item", value=row.get("strategy_item_id"), with_input=True).classes("w-full")
            status = ui.select(WORKSTREAM_STATUSES, label="Status", value=row.get("status", "not_started")).classes("w-full")
            lead = ui.select(member_options(), label="Lead", value=row.get("lead_id"), with_input=True).classes("w-full")
            start = ui.input("Est. start (YYYY-MM-DD)", value=row.get("estimated_start", "")).classes("w-full")
            end = ui.input("Est. end (YYYY-MM-DD)", value=row.get("estimated_end", "")).classes("w-full")

            def save() -> None:
                if not name.value.strip():
                    ui.notify("Name is required", type="negative")
                    return
                _save(row.get("id"), name.value.strip(), description.value, strategy.value,
                      status.value, lead.value, start.value, end.value)
                dialog.close()
                refresh()
                ui.notify("Saved", type="positive")

            with ui.row().classes("justify-end w-full"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Save", on_click=save)
        dialog.open()

    with ui.row().classes("items-center gap-4 p-4"):
        ui.label("Workstreams").classes("text-xl font-bold")
        ui.button("Add workstream", icon="add", on_click=lambda: open_form())

    refresh()
