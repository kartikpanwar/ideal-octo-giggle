"""Home / landing page.

Leads with a KPI row, then a team capacity chart (team time by strategy item
over months) and a workstream x person grid of who's working on what. More
visualisations will be added here later.
"""

from __future__ import annotations

from datetime import date
from math import ceil

from nicegui import ui

from app.db import get_session
from app.models import TeamMember, Workstream
from app.pages.layout import header
from app.services import kpi_summary, team_capacity_by_month, workstream_assignments

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

# Categorical palette for the team capacity chart's strategy-item stack,
# cycled by index. "Unassigned" always gets UNASSIGNED_COLOR instead, since
# it's a neutral fallback bucket, not one more strategy item to distinguish.
STRATEGY_STACK_COLORS = [
    "#1976d2", "#43a047", "#fb8c00", "#8e24aa", "#00838f", "#c62828", "#6d4c41", "#3949ab",
]
UNASSIGNED_COLOR = "#9e9e9e"
AVAILABLE_LINE_COLOR = "#212121"


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


def _month_label(m: date) -> str:
    return f"{m.strftime('%b')}-{str(m.year)[-2:]}"  # e.g. "Sep-26", matching the Gantt charts' style


def build_team_capacity_chart_options(capacity: dict) -> dict | None:
    """Stacked bar chart of team time (person-weeks) by strategy item, one
    bar per calendar month, from app.services.team_capacity_by_month. A
    dashed line overlays each month's total team available time, so the
    stacked bars' total height can be read against actual team capacity.

    A plain axis-trigger tooltip is used here (not the Gantt/heatmap charts'
    manually-built `{b}` tooltip) — this is an ordinary stacked bar + line
    combo, so ECharts' default multi-series tooltip already shows every
    series' name and value at the hovered month with no custom formatting
    needed.

    Returns None when there's no dated, estimated task to plot.
    """
    months = capacity["months"]
    strategy_items = capacity["strategy_items"]
    if not months or not strategy_items:
        return None

    by_key = {(r["strategy_item_id"], r["month"]): r["effort_weeks"] for r in capacity["effort"]}
    available_by_month = {r["month"]: r["available_weeks"] for r in capacity["available"]}

    bar_series = []
    color_i = 0
    for item in strategy_items:
        if item["id"] is None:
            color = UNASSIGNED_COLOR
        else:
            color = STRATEGY_STACK_COLORS[color_i % len(STRATEGY_STACK_COLORS)]
            color_i += 1
        bar_series.append(
            {
                "name": item["name"],
                "type": "bar",
                "stack": "capacity",
                "itemStyle": {"color": color},
                "data": [by_key.get((item["id"], m), 0.0) for m in months],
            }
        )

    line_series = {
        "name": "Total available",
        "type": "line",
        "itemStyle": {"color": AVAILABLE_LINE_COLOR},
        "lineStyle": {"type": "dashed", "width": 2},
        "symbol": "circle",
        "symbolSize": 6,
        "data": [available_by_month.get(m, 0.0) for m in months],
    }

    return {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"top": 0, "type": "scroll"},
        "grid": {"left": "6%", "right": "4%", "top": 60, "bottom": "8%", "containLabel": True},
        "xAxis": {"type": "category", "data": [_month_label(m) for m in months]},
        "yAxis": {"type": "value", "name": "Person-weeks", "nameLocation": "middle", "nameGap": 40},
        "series": [*bar_series, line_series],
    }


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
        # top is a fixed pixel offset, not a %: the visualMap legend's own
        # rendered height doesn't scale with the chart's (data-driven) total
        # height, so a percentage margin shrinks below the legend's actual
        # height at low row counts and the legend overlaps the first row.
        "grid": {"left": "16%", "right": "4%", "top": 55, "bottom": "12%", "containLabel": True},
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
            "calculable": False,
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

        ui.label("Team capacity").classes("text-2xl font-bold")
        ui.label(
            "Team time (person-weeks) going toward each strategy item, by month, against "
            "total team available time. Includes tasks of every status, so past months "
            "reflect what was actually planned then, not just what's still open."
        ).classes("text-sm text-gray-500")

        with get_session() as session:
            capacity = team_capacity_by_month(session)
        capacity_options = build_team_capacity_chart_options(capacity)
        if capacity_options is None:
            ui.label("No dated, estimated tasks yet.").classes("text-sm text-gray-500")
        else:
            ui.echart(capacity_options).classes("w-full h-96")

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
