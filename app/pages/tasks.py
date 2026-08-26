"""Task CRUD page. Amending status/estimate appends an estimate_history snapshot."""

from __future__ import annotations

from nicegui import ui

from app.db import get_session
from app.models import TASK_STATUSES, Task
from app.pages.common import (
    STATUS_BADGE_SLOT,
    STATUS_COLOR_FALLBACK,
    STATUS_COLORS,
    fmt_date,
    member_options,
    parse_date,
    workstream_options,
)
from app.pages.layout import header
from app.services import CLOSED_STATUSES, record_task_change, task_history

_ALL = "__all__"  # sentinel option value meaning "no filter" (workstream/person filters)

COLUMNS = [
    {"name": "id", "label": "ID", "field": "id", "align": "left"},
    {"name": "name", "label": "Task", "field": "name", "align": "left"},
    {"name": "assignee", "label": "Assignee", "field": "assignee", "align": "left"},
    {"name": "workstream", "label": "Workstream", "field": "workstream", "align": "left"},
    {"name": "status", "label": "Status", "field": "status", "align": "left"},
    {"name": "estimated_effort_weeks", "label": "Effort (wks)", "field": "estimated_effort_weeks"},
    {"name": "estimated_start", "label": "Est. start", "field": "estimated_start"},
    {"name": "estimated_end", "label": "Est. end", "field": "estimated_end"},
    {"name": "actual_start", "label": "Actual start", "field": "actual_start"},
    {"name": "actual_end", "label": "Actual end", "field": "actual_end"},
    {"name": "actions", "label": "", "field": "actions"},
]


def _load_rows() -> list[dict]:
    members = member_options()
    workstreams = workstream_options()
    with get_session() as session:
        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "assignee_id": t.assignee_id,
                "assignee": members.get(t.assignee_id, ""),
                "workstream_id": t.workstream_id,
                "workstream": workstreams.get(t.workstream_id, ""),
                "status": t.status,
                "status_color": STATUS_COLORS.get(t.status, STATUS_COLOR_FALLBACK),
                "estimated_effort_weeks": t.estimated_effort_weeks,
                "estimated_start": fmt_date(t.estimated_start),
                "estimated_end": fmt_date(t.estimated_end),
                "actual_start": fmt_date(t.actual_start),
                "actual_end": fmt_date(t.actual_end),
            }
            for t in session.query(Task).order_by(Task.id).all()
        ]


def _save(row_id, name, description, workstream_id, assignee_id, status, effort, start, end,
          actual_start, actual_end, status_update) -> None:
    with get_session() as session:
        is_new = row_id is None
        task = Task() if is_new else session.get(Task, row_id)
        prev_status = None if is_new else task.status
        prev_start = None if is_new else task.estimated_start
        prev_end = None if is_new else task.estimated_end

        task.name = name
        task.description = description or None
        task.workstream_id = workstream_id
        task.assignee_id = assignee_id
        task.status = status
        task.estimated_effort_weeks = effort
        task.estimated_start = parse_date(start)
        task.estimated_end = parse_date(end)
        task.actual_start = parse_date(actual_start)
        task.actual_end = parse_date(actual_end)
        if is_new:
            session.add(task)
        session.flush()  # ensure task.id for the history row

        changed = (
            is_new
            or task.status != prev_status
            or task.estimated_start != prev_start
            or task.estimated_end != prev_end
        )
        if changed:
            record_task_change(session, task, previous_status=prev_status, status_update=status_update)


def build() -> None:
    header("Tasks")

    # Filter state, driven by the selects below. Status is multi-select (a
    # list, not the _ALL-sentinel pattern the other two use) and defaults to
    # excluding closed statuses so the table opens showing active work.
    default_statuses = [s for s in TASK_STATUSES if s not in CLOSED_STATUSES]
    filters = {"workstream_id": _ALL, "assignee_id": _ALL, "status": default_statuses}

    def _apply_filters(rows: list[dict]) -> list[dict]:
        return [
            r
            for r in rows
            if (filters["workstream_id"] == _ALL or r["workstream_id"] == filters["workstream_id"])
            and (filters["assignee_id"] == _ALL or r["assignee_id"] == filters["assignee_id"])
            and r["status"] in filters["status"]
        ]

    def refresh() -> None:
        table_holder.clear()
        with table_holder:
            rows = _apply_filters(_load_rows())
            table = ui.table(columns=COLUMNS, rows=rows, row_key="id").classes("w-full")
            table.add_slot("body-cell-status", STATUS_BADGE_SLOT)
            table.add_slot(
                "body-cell-actions",
                '<q-td :props="props">'
                '<q-btn dense flat icon="edit" @click="() => $parent.$emit(\'edit\', props.row)"/>'
                '<q-btn dense flat icon="history" @click="() => $parent.$emit(\'history\', props.row)"/>'
                "</q-td>",
            )
            table.on("edit", lambda e: open_form(e.args))
            table.on("history", lambda e: show_history(e.args))

    def show_history(row: dict) -> None:
        with get_session() as session:
            entries = [
                {
                    "changed_at": h.changed_at.strftime("%Y-%m-%d %H:%M"),
                    "transition": f"{h.previous_status or '—'} → {h.status or '—'}",
                    "dates": f"{fmt_date(h.estimated_start)} → {fmt_date(h.estimated_end)}",
                    "status_update": h.status_update or "",
                }
                for h in task_history(session, row["id"])
            ]
        with ui.dialog() as dialog, ui.card().classes("w-[36rem]"):
            ui.label(f"History — {row['name']}").classes("text-lg font-bold")
            if not entries:
                ui.label("No history yet.")
            for e in entries:
                with ui.card().classes("w-full"):
                    ui.label(f"{e['changed_at']}  ·  {e['transition']}").classes("font-medium")
                    ui.label(f"Est. dates: {e['dates']}").classes("text-sm text-gray-500")
                    if e["status_update"]:
                        ui.label(e["status_update"]).classes("text-sm")
            ui.button("Close", on_click=dialog.close).props("flat")
        dialog.open()

    def open_form(row: dict | None = None) -> None:
        row = row or {}
        with ui.dialog() as dialog, ui.card().classes("w-[32rem]"):
            ui.label("Edit task" if row else "Add task").classes("text-lg font-bold")
            name = ui.input("Name", value=row.get("name", "")).classes("w-full")
            description = ui.textarea("Description", value=row.get("description") or "").classes("w-full")
            workstream = ui.select(workstream_options(), label="Workstream", value=row.get("workstream_id"), with_input=True).classes("w-full")
            assignee = ui.select(member_options(), label="Assignee", value=row.get("assignee_id"), with_input=True).classes("w-full")
            status = ui.select(TASK_STATUSES, label="Status", value=row.get("status", "not_started")).classes("w-full")
            effort = ui.number("Estimated effort (weeks)", value=row.get("estimated_effort_weeks"), step=0.5)
            start = ui.input("Est. start (YYYY-MM-DD)", value=row.get("estimated_start", "")).classes("w-full")
            end = ui.input("Est. end (YYYY-MM-DD)", value=row.get("estimated_end", "")).classes("w-full")
            actual_start = ui.input(
                "Actual start (YYYY-MM-DD)", value=row.get("actual_start", "")
            ).classes("w-full")
            actual_end = ui.input(
                "Actual end (YYYY-MM-DD)", value=row.get("actual_end", "")
            ).classes("w-full")
            status_update = ui.textarea("Status update (logged on status/date change)").classes("w-full")

            def save() -> None:
                if not name.value.strip():
                    ui.notify("Name is required", type="negative")
                    return
                _save(row.get("id"), name.value.strip(), description.value, workstream.value,
                      assignee.value, status.value, effort.value, start.value, end.value,
                      actual_start.value, actual_end.value, status_update.value)
                dialog.close()
                refresh()
                ui.notify("Saved", type="positive")

            with ui.row().classes("justify-end w-full"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Save", on_click=save)
        dialog.open()

    def _set(key: str, value) -> None:
        filters[key] = _ALL if value is None else value
        refresh()

    def _set_status(value) -> None:
        filters["status"] = value or []
        refresh()

    ws_opts = {_ALL: "All workstreams", **workstream_options()}
    who_opts = {_ALL: "All people", **member_options()}

    # Visual order: title/add, filters, then the table.
    with ui.row().classes("items-center gap-4 p-4"):
        ui.label("Tasks").classes("text-xl font-bold")
        ui.button("Add task", icon="add", on_click=lambda: open_form())

    with ui.row().classes("items-center gap-4 px-4 pb-2"):
        ui.label("Filter:").classes("text-sm text-gray-500")
        ui.select(ws_opts, value=_ALL, label="Workstream",
                  on_change=lambda e: _set("workstream_id", e.value)).classes("w-52")
        ui.select(who_opts, value=_ALL, label="Person",
                  on_change=lambda e: _set("assignee_id", e.value)).classes("w-52")
        ui.select(TASK_STATUSES, label="Status", multiple=True, value=default_statuses,
                  on_change=lambda e: _set_status(e.value)).classes("w-64")

    table_holder = ui.column().classes("w-full px-4")
    refresh()
