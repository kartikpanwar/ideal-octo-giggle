"""Home / landing page.

Leads with a KPI row, then a workstream x person grid of who's working on
what. More visualisations will be added here later.
"""

from __future__ import annotations

from math import ceil

from nicegui import ui

from app.db import get_session
from app.models import TeamMember, Workstream
from app.pages.layout import header
from app.services import kpi_summary, workstream_assignments

# (label, kpi_summary key, icon, colour) for the KPI row, in display order.
KPI_TILES = [
    ("Tasks in progress", "tasks_in_progress", "play_circle", "#1976d2"),
    ("Tasks blocked", "tasks_blocked", "block", "#e53935"),
    ("Active workstreams", "workstreams_active", "timeline", "#43a047"),
    ("People over-allocated", "people_over_allocated", "warning", "#fb8c00"),
]

# Sequential blue scale for effort volume — deliberately distinct from the
# People page's green->red allocation heatmap, since this isn't a danger
# signal, just "how much".
GRID_COLORS = ["#e3f2fd", "#90caf9", "#42a5f5", "#1976d2", "#0d47a1"]
MAX_TOOLTIP_TASKS = 4


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


def _load_workstream_person_grid_data() -> tuple[list[dict], list[dict], list[dict]]:
    with get_session() as session:
        workstreams = [
            {"id": w.id, "name": w.name}
            for w in session.query(Workstream).order_by(Workstream.id).all()
        ]
        members = [
            {"id": m.id, "name": m.name}
            for m in session.query(TeamMember).order_by(TeamMember.name).all()
        ]
        rows = workstream_assignments(session)
    return workstreams, members, rows


def build_workstream_person_grid_options(
    workstreams: list[dict], members: list[dict], rows: list[dict]
) -> dict | None:
    """People x workstream heatmap: cell = total *open* (not done/cancelled)
    estimated effort (person-weeks) each person has on tasks in that
    workstream — see app.services.workstream_assignments.

    People are columns, workstreams are rows (yAxis inverse=True keeps the
    first workstream at the top, matching the Workstreams table's order).
    Builds a dense grid like the People page's allocation heatmap: every
    workstream x every person gets a cell, defaulting to 0 where nobody has
    an open assigned task there. The colour scale's max is the largest single
    cell value actually present (rounded up), not a fixed cap, since effort
    volume — unlike the % allocation heatmap — has no natural ceiling to clamp
    against. Returns None when there's nothing to place.
    """
    if not rows or not workstreams or not members:
        return None

    ws_index = {w["id"]: i for i, w in enumerate(workstreams)}
    member_index = {m["id"]: i for i, m in enumerate(members)}
    by_key = {(r["workstream_id"], r["person_id"]): r for r in rows}

    heat_max = max(1, ceil(max((r["effort_weeks"] for r in rows), default=0.0)))

    data = []
    for ws in workstreams:
        for member in members:
            entry = by_key.get((ws["id"], member["id"]))
            effort = entry["effort_weeks"] if entry else 0.0
            task_count = entry["task_count"] if entry else 0
            names = entry["task_names"] if entry else []

            tooltip = f"{member['name']}\n{ws['name']}\n{effort:g} wks open · {task_count} task(s)"
            if names:
                shown = names[:MAX_TOOLTIP_TASKS]
                extra = len(names) - len(shown)
                task_lines = "\n".join(f"- {n}" for n in shown)
                if extra > 0:
                    task_lines += f"\n+ {extra} more"
                tooltip += f"\n{task_lines}"

            data.append(
                {
                    "value": [member_index[member["id"]], ws_index[ws["id"]], min(effort, heat_max)],
                    "name": tooltip,
                }
            )

    return {
        "tooltip": {
            "trigger": "item",
            "formatter": "{b}",
            "extraCssText": "text-align:left; white-space:pre-line; max-width:260px;",
        },
        "grid": {"left": "16%", "right": "4%", "top": "10%", "bottom": "12%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": [m["name"] for m in members],
            "splitArea": {"show": True},
        },
        "yAxis": {
            "type": "category",
            "inverse": True,
            "data": [w["name"] for w in workstreams],
            "splitArea": {"show": True},
        },
        "visualMap": {
            "min": 0,
            "max": heat_max,
            "calculable": True,
            "orient": "horizontal",
            "left": "center",
            "top": "0",
            "inRange": {"color": GRID_COLORS},
        },
        "series": [
            {
                "type": "heatmap",
                "data": data,
                "label": {"show": False},
                "emphasis": {"itemStyle": {"borderColor": "#333", "borderWidth": 1}},
            }
        ],
    }


def build() -> None:
    header("Home")

    with get_session() as session:
        kpis = kpi_summary(session)

    with ui.column().classes("w-full p-4 gap-4"):
        with ui.row().classes("w-full gap-4 flex-wrap"):
            for label, key, icon, color in KPI_TILES:
                _kpi_tile(label, kpis[key], icon, color)

        ui.label("Who's working on what").classes("text-2xl font-bold")
        ui.label(
            "Open task effort (person-weeks) each person has per workstream — "
            "done and cancelled tasks aren't counted."
        ).classes("text-sm text-gray-500")

        workstreams, members, assignment_rows = _load_workstream_person_grid_data()
        grid_options = build_workstream_person_grid_options(workstreams, members, assignment_rows)
        if grid_options is None:
            ui.label("No open, assigned tasks yet.").classes("text-sm text-gray-500")
        else:
            chart_height = max(280, 45 * len(workstreams) + 140)
            ui.echart(grid_options).classes("w-full").style(f"height: {chart_height}px")

        ui.separator()
        with ui.card().classes("w-full bg-blue-50"):
            ui.label("More visualisations coming soon").classes("text-base font-medium")
            ui.label(
                "This home page will grow charts for capacity trends, workstream burn-down, "
                "and estimate history over time."
            ).classes("text-sm text-gray-600")
