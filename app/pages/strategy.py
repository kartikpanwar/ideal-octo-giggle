"""Strategy item CRUD page."""

from __future__ import annotations

from nicegui import ui

from app.db import get_session
from app.models import STRATEGY_STATUSES, StrategyItem
from app.pages.common import fmt_date, member_options, parse_date
from app.pages.layout import header

COLUMNS = [
    {"name": "id", "label": "ID", "field": "id", "align": "left"},
    {"name": "name", "label": "Name", "field": "name", "align": "left"},
    {"name": "status", "label": "Status", "field": "status", "align": "left"},
    {"name": "priority", "label": "Priority", "field": "priority"},
    {"name": "owner", "label": "Owner", "field": "owner", "align": "left"},
    {"name": "target_start", "label": "Target start", "field": "target_start"},
    {"name": "target_end", "label": "Target end", "field": "target_end"},
    {"name": "actions", "label": "", "field": "actions"},
]


def _load_rows() -> list[dict]:
    owners = member_options()
    with get_session() as session:
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "status": s.status,
                "priority": s.priority,
                "owner_id": s.owner_id,
                "owner": owners.get(s.owner_id, ""),
                "target_start": fmt_date(s.target_start),
                "target_end": fmt_date(s.target_end),
            }
            for s in session.query(StrategyItem).order_by(StrategyItem.id).all()
        ]


def _save(row_id, name, description, status, priority, owner_id, start, end) -> None:
    with get_session() as session:
        item = session.get(StrategyItem, row_id) if row_id else StrategyItem()
        item.name = name
        item.description = description or None
        item.status = status
        item.priority = int(priority) if priority is not None else None
        item.owner_id = owner_id
        item.target_start = parse_date(start)
        item.target_end = parse_date(end)
        if row_id is None:
            session.add(item)


def build() -> None:
    header("Strategy")
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
            ui.label("Edit strategy item" if row else "Add strategy item").classes("text-lg font-bold")
            name = ui.input("Name", value=row.get("name", "")).classes("w-full")
            description = ui.textarea("Description", value=row.get("description") or "").classes("w-full")
            status = ui.select(STRATEGY_STATUSES, label="Status", value=row.get("status", "proposed")).classes("w-full")
            priority = ui.number("Priority", value=row.get("priority"))
            owner = ui.select(member_options(), label="Owner", value=row.get("owner_id"), with_input=True).classes("w-full")
            start = ui.input("Target start (YYYY-MM-DD)", value=row.get("target_start", "")).classes("w-full")
            end = ui.input("Target end (YYYY-MM-DD)", value=row.get("target_end", "")).classes("w-full")

            def save() -> None:
                if not name.value.strip():
                    ui.notify("Name is required", type="negative")
                    return
                _save(row.get("id"), name.value.strip(), description.value, status.value,
                      priority.value, owner.value, start.value, end.value)
                dialog.close()
                refresh()
                ui.notify("Saved", type="positive")

            with ui.row().classes("justify-end w-full"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Save", on_click=save)
        dialog.open()

    with ui.row().classes("items-center gap-4 p-4"):
        ui.label("Strategy items").classes("text-xl font-bold")
        ui.button("Add strategy item", icon="add", on_click=lambda: open_form())

    refresh()
