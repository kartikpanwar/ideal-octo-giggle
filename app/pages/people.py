"""People (team member) CRUD page."""

from __future__ import annotations

from nicegui import ui

from app.db import get_session
from app.models import TeamMember
from app.pages.layout import header

COLUMNS = [
    {"name": "id", "label": "ID", "field": "id", "align": "left"},
    {"name": "name", "label": "Name", "field": "name", "align": "left"},
    {"name": "email", "label": "Email", "field": "email", "align": "left"},
    {"name": "role", "label": "Role", "field": "role", "align": "left"},
    {"name": "default_weekly_hours", "label": "Weekly hrs", "field": "default_weekly_hours"},
    {"name": "active", "label": "Active", "field": "active"},
    {"name": "actions", "label": "", "field": "actions"},
]


def _load_rows() -> list[dict]:
    with get_session() as session:
        return [
            {
                "id": p.id,
                "name": p.name,
                "email": p.email,
                "role": p.role,
                "default_weekly_hours": p.default_weekly_hours,
                "active": p.active,
            }
            for p in session.query(TeamMember).order_by(TeamMember.id).all()
        ]


def _save(row_id: int | None, name, email, role, hours, active) -> None:
    with get_session() as session:
        person = session.get(TeamMember, row_id) if row_id else TeamMember()
        person.name = name
        person.email = email or None
        person.role = role or None
        person.default_weekly_hours = hours
        person.active = active
        if row_id is None:
            session.add(person)


def build() -> None:
    header("People")

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
            ui.label("Edit person" if row else "Add person").classes("text-lg font-bold")
            name = ui.input("Name", value=row.get("name", "")).classes("w-full")
            email = ui.input("Email", value=row.get("email") or "").classes("w-full")
            role = ui.input("Role", value=row.get("role") or "").classes("w-full")
            hours = ui.number("Default weekly hours", value=row.get("default_weekly_hours") or 40)
            active = ui.switch("Active", value=row.get("active", True))

            def save() -> None:
                if not name.value.strip():
                    ui.notify("Name is required", type="negative")
                    return
                _save(row.get("id"), name.value.strip(), email.value, role.value,
                      hours.value, active.value)
                dialog.close()
                refresh()
                ui.notify("Saved", type="positive")

            with ui.row().classes("justify-end w-full"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Save", on_click=save)
        dialog.open()

    with ui.row().classes("items-center gap-4 p-4"):
        ui.label("People").classes("text-xl font-bold")
        ui.button("Add person", icon="add", on_click=lambda: open_form())

    refresh()
