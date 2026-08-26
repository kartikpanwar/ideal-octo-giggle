"""People (team member) CRUD page, plus a per-person task timeline (ECharts)
comparing estimated vs. actual dates — see docs/standards.md."""

from __future__ import annotations

from nicegui import ui
from sqlalchemy.orm import joinedload

from app.db import get_session
from app.models import TASK_STATUSES, Task, TeamMember
from app.pages.common import STATUS_COLORS, fmt_date
from app.pages.layout import header

# Fixed styling for the "actual" bar, distinct from the status-coloured
# "estimated" bar so the two read as different series, not different statuses.
ACTUAL_BAR_COLOR = "#37474f"

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


def _load_timeline_tasks(person_id: int) -> list[dict]:
    """Tasks assigned to a person, dated ones first (ascending start), for the timeline."""
    with get_session() as session:
        tasks = (
            session.query(Task)
            .options(joinedload(Task.workstream))
            .filter(Task.assignee_id == person_id)
            .order_by(Task.estimated_start.is_(None), Task.estimated_start)
            .all()
        )
        return [
            {
                "name": t.name,
                "status": t.status,
                "workstream": t.workstream.name if t.workstream else "",
                "estimated_start": t.estimated_start,
                "estimated_end": t.estimated_end,
                "actual_start": t.actual_start,
                "actual_end": t.actual_end,
                "estimated_effort_weeks": t.estimated_effort_weeks,
            }
            for t in tasks
        ]


def build_person_timeline_options(tasks: list[dict]) -> dict | None:
    """Grouped horizontal bar chart: each task gets an 'estimated' bar (coloured
    by status) and, when present, a thinner 'actual' bar alongside it, so
    planned vs. actual dates are directly comparable on one row.

    Uses the same invisible-offset + visible-duration stacked-bar workaround as
    the workstream timeline (see app/pages/workstreams.py), doubled: the
    estimated pair uses stack "est", the actual pair uses stack "act" — two
    distinct stacks on the same category axis render as grouped bars.
    Tasks with neither a complete estimated nor actual date pair are excluded
    (the caller lists them separately). Returns None when nothing can be placed.
    """
    dated = [
        t
        for t in tasks
        if (t["estimated_start"] and t["estimated_end"]) or (t["actual_start"] and t["actual_end"])
    ]
    if not dated:
        return None

    starts = [
        d
        for t in dated
        for d in (
            t["estimated_start"] if t["estimated_start"] and t["estimated_end"] else None,
            t["actual_start"] if t["actual_start"] and t["actual_end"] else None,
        )
        if d is not None
    ]
    timeline_start = min(starts)

    names, est_offsets, est_bars, act_offsets, act_bars = [], [], [], [], []
    for t in dated:
        names.append(t["name"])
        where = f" · {t['workstream']}" if t["workstream"] else ""

        if t["estimated_start"] and t["estimated_end"]:
            effort = t["estimated_effort_weeks"]
            effort_txt = f"{effort:g} wks" if effort is not None else "— wks"
            est_offsets.append((t["estimated_start"] - timeline_start).days)
            est_bars.append(
                {
                    "value": max((t["estimated_end"] - t["estimated_start"]).days, 1),
                    "name": (
                        f"{t['name']}\nEstimated — {t['status']}{where}\n"
                        f"{fmt_date(t['estimated_start'])} → {fmt_date(t['estimated_end'])} · {effort_txt}"
                    ),
                    "itemStyle": {"color": STATUS_COLORS.get(t["status"], "#9e9e9e")},
                }
            )
        else:
            est_offsets.append(None)
            est_bars.append(None)

        if t["actual_start"] and t["actual_end"]:
            act_offsets.append((t["actual_start"] - timeline_start).days)
            act_bars.append(
                {
                    "value": max((t["actual_end"] - t["actual_start"]).days, 1),
                    "name": (
                        f"{t['name']}\nActual{where}\n"
                        f"{fmt_date(t['actual_start'])} → {fmt_date(t['actual_end'])}"
                    ),
                    "itemStyle": {"color": ACTUAL_BAR_COLOR},
                }
            )
        else:
            act_offsets.append(None)
            act_bars.append(None)

    return {
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}",
            "extraCssText": "text-align:left; white-space:pre-line; max-width:260px;",
        },
        "grid": {"left": "22%", "right": "6%", "top": "6%", "bottom": "14%", "containLabel": True},
        "xAxis": {
            "type": "value",
            "name": f"Days from {fmt_date(timeline_start)}",
            "nameLocation": "middle",
            "nameGap": 28,
            "axisLabel": {"formatter": "{value}d"},
        },
        "yAxis": {"type": "category", "inverse": True, "data": names},
        "series": [
            {
                "name": "estOffset", "type": "bar", "stack": "est",
                "silent": True, "itemStyle": {"color": "transparent"},
                "data": est_offsets,
            },
            {
                "name": "estDuration", "type": "bar", "stack": "est",
                "barWidth": "45%", "data": est_bars,
            },
            {
                "name": "actOffset", "type": "bar", "stack": "act",
                "silent": True, "itemStyle": {"color": "transparent"},
                "data": act_offsets,
            },
            {
                "name": "actDuration", "type": "bar", "stack": "act",
                "barWidth": "18%", "barGap": "30%", "data": act_bars,
            },
        ],
    }


def _present_statuses(tasks: list[dict]) -> list[str]:
    """Statuses actually used in `tasks`, in canonical order (for the legend)."""
    return [s for s in TASK_STATUSES if any(t["status"] == s for t in tasks)]


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
                '<q-td :props="props">'
                '<q-btn dense flat icon="edit" @click="() => $parent.$emit(\'edit\', props.row)"/>'
                '<q-btn dense flat icon="timeline" @click="() => $parent.$emit(\'timeline\', props.row)"/>'
                "</q-td>",
            )
            table.on("edit", lambda e: open_form(e.args))
            table.on("timeline", lambda e: show_timeline(e.args))

    def show_timeline(row: dict) -> None:
        tasks = _load_timeline_tasks(row["id"])
        options = build_person_timeline_options(tasks)
        undated = [
            t["name"]
            for t in tasks
            if not (t["estimated_start"] and t["estimated_end"])
            and not (t["actual_start"] and t["actual_end"])
        ]

        with ui.dialog() as dialog, ui.card().classes("w-[48rem] max-w-full"):
            ui.label(f"Timeline — {row['name']}").classes("text-lg font-bold")
            if not tasks:
                ui.label("No tasks assigned yet.").classes("text-sm text-gray-500")
            elif options is None:
                ui.label(
                    "No tasks have estimated or actual dates yet."
                ).classes("text-sm text-gray-500")
            else:
                with ui.row().classes("items-center gap-4"):
                    for status in _present_statuses(tasks):
                        with ui.row().classes("items-center gap-1"):
                            ui.element("div").classes("w-3 h-3 rounded-full").style(
                                f"background-color: {STATUS_COLORS.get(status, '#9e9e9e')}"
                            )
                            ui.label(status).classes("text-xs text-gray-600")
                with ui.row().classes("items-center gap-4"):
                    with ui.row().classes("items-center gap-1"):
                        ui.element("div").classes("w-4 h-3").style(
                            "background-color: #90a4ae"
                        )
                        ui.label("Estimated (coloured by status)").classes("text-xs text-gray-600")
                    with ui.row().classes("items-center gap-1"):
                        ui.element("div").classes("w-2 h-3").style(
                            f"background-color: {ACTUAL_BAR_COLOR}"
                        )
                        ui.label("Actual").classes("text-xs text-gray-600")
                chart_height = max(240, 46 * len(options["yAxis"]["data"]) + 90)
                ui.echart(options).classes("w-full").style(f"height: {chart_height}px")
                if undated:
                    ui.label(
                        "No estimated or actual dates yet, not shown: " + ", ".join(undated)
                    ).classes("text-xs text-gray-500")
            with ui.row().classes("justify-end w-full"):
                ui.button("Close", on_click=dialog.close).props("flat")
        dialog.open()

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
