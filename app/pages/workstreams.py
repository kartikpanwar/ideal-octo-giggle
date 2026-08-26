"""Workstream CRUD page (child of strategy item), plus a per-workstream
task timeline rendered with ECharts (see docs/standards.md)."""

from __future__ import annotations

from nicegui import ui
from sqlalchemy.orm import joinedload

from app.db import get_session
from app.models import TASK_STATUSES, WORKSTREAM_STATUSES, Task, Workstream
from app.pages.common import (
    STATUS_COLORS,
    fmt_date,
    member_options,
    month_year_axis_label,
    parse_date,
    strategy_options,
)
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


def _load_timeline_tasks(workstream_id: int) -> list[dict]:
    """Tasks in a workstream, dated ones first (ascending start), for the timeline chart."""
    with get_session() as session:
        tasks = (
            session.query(Task)
            .options(joinedload(Task.assignee))
            .filter(Task.workstream_id == workstream_id)
            .order_by(Task.estimated_start.is_(None), Task.estimated_start)
            .all()
        )
        return [
            {
                "name": t.name,
                "status": t.status,
                "estimated_start": t.estimated_start,
                "estimated_end": t.estimated_end,
                "estimated_effort_weeks": t.estimated_effort_weeks,
                "assignee": t.assignee.name if t.assignee else "",
            }
            for t in tasks
        ]


def build_timeline_options(tasks: list[dict]) -> dict | None:
    """Stacked horizontal bar chart of each task's estimated span (ECharts options).

    ECharts has no native Gantt series, so this uses the standard workaround: an
    invisible 'offset' bar (days from the workstream's earliest start) stacked
    under a visible 'duration' bar. Tasks missing either date can't be placed
    and are excluded here; the caller lists them separately. Returns None when
    no task has both dates.
    """
    dated = [t for t in tasks if t["estimated_start"] and t["estimated_end"]]
    if not dated:
        return None

    timeline_start = min(t["estimated_start"] for t in dated)
    names, offsets, bars = [], [], []
    for t in dated:
        offset_days = (t["estimated_start"] - timeline_start).days
        duration_days = max((t["estimated_end"] - t["estimated_start"]).days, 1)
        effort = t["estimated_effort_weeks"]
        effort_txt = f"{effort:g} wks" if effort is not None else "— wks"
        # Plain text with \n, not HTML: ECharts escapes the {b} template
        # substitution before inserting it, so embedded tags like <br/> would
        # render as literal text. extraCssText (below) turns \n into line
        # breaks instead.
        tooltip = (
            f"{t['name']}\n"
            f"{t['status']} · {t['assignee'] or 'Unassigned'}\n"
            f"{fmt_date(t['estimated_start'])} → {fmt_date(t['estimated_end'])} · {effort_txt}"
        )
        names.append(t["name"])
        offsets.append(offset_days)
        bars.append(
            {
                "value": duration_days,
                "name": tooltip,
                "itemStyle": {"color": STATUS_COLORS.get(t["status"], "#9e9e9e")},
            }
        )

    return {
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}",
            "extraCssText": "text-align:left; white-space:pre-line; max-width:260px;",
        },
        "grid": {"left": "22%", "right": "6%", "top": "6%", "bottom": "14%", "containLabel": True},
        "xAxis": {
            "type": "value",
            **month_year_axis_label(timeline_start),
        },
        "yAxis": {"type": "category", "inverse": True, "data": names},
        "series": [
            {
                "name": "offset",
                "type": "bar",
                "stack": "timeline",
                "silent": True,
                "itemStyle": {"color": "transparent"},
                "data": offsets,
            },
            {
                "name": "duration",
                "type": "bar",
                "stack": "timeline",
                "barWidth": "55%",
                "data": bars,
            },
        ],
    }


def _present_statuses(tasks: list[dict]) -> list[str]:
    """Statuses actually used in `tasks`, in canonical order (for the legend)."""
    return [s for s in TASK_STATUSES if any(t["status"] == s for t in tasks)]


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
                '<q-td :props="props">'
                '<q-btn dense flat icon="edit" @click="() => $parent.$emit(\'edit\', props.row)"/>'
                '<q-btn dense flat icon="timeline" @click="() => $parent.$emit(\'timeline\', props.row)"/>'
                "</q-td>",
            )
            table.on("edit", lambda e: open_form(e.args))
            table.on("timeline", lambda e: show_timeline(e.args))

    def show_timeline(row: dict) -> None:
        tasks = _load_timeline_tasks(row["id"])
        options = build_timeline_options(tasks)
        undated = [t["name"] for t in tasks if not (t["estimated_start"] and t["estimated_end"])]

        with ui.dialog() as dialog, ui.card().classes("w-[48rem] max-w-full"):
            ui.label(f"Timeline — {row['name']}").classes("text-lg font-bold")
            if not tasks:
                ui.label("No tasks in this workstream yet.").classes("text-sm text-gray-500")
            elif options is None:
                ui.label(
                    "No tasks have both an estimated start and end date yet."
                ).classes("text-sm text-gray-500")
            else:
                with ui.row().classes("items-center gap-4"):
                    for status in _present_statuses(tasks):
                        with ui.row().classes("items-center gap-1"):
                            ui.element("div").classes("w-3 h-3 rounded-full").style(
                                f"background-color: {STATUS_COLORS.get(status, '#9e9e9e')}"
                            )
                            ui.label(status).classes("text-xs text-gray-600")
                chart_height = max(240, 42 * len(options["yAxis"]["data"]) + 90)
                ui.echart(options).classes("w-full").style(f"height: {chart_height}px")
                if undated:
                    ui.label(
                        "No estimated dates yet, not shown: " + ", ".join(undated)
                    ).classes("text-xs text-gray-500")
            with ui.row().classes("justify-end w-full"):
                ui.button("Close", on_click=dialog.close).props("flat")
        dialog.open()

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
