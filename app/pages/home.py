"""Home / landing page.

Leads with a KPI row, then a team capacity chart (team time by strategy item
over months), a workstream x person grid of who's working on what, a
per-person workstream allocation chart (standing % allocation vs. 100%
capacity), and a per-workstream capacity check (allocated capacity vs.
required task effort). More visualisations will be added here later.
"""

from __future__ import annotations

from datetime import date
from math import ceil

from nicegui import ui

from app.db import get_session
from app.models import TeamMember, Workstream
from app.pages.layout import header
from app.services import (
    kpi_summary,
    team_capacity_by_month,
    workstream_allocation_pct,
    workstream_assignments,
    workstream_capacity_check,
)

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

# Categorical palette shared by the team capacity chart's strategy-item stack
# and the person-allocation chart's workstream stack, cycled by index in each.
# "Unassigned"/"Unallocated" always get UNASSIGNED_COLOR instead, since it's a
# neutral fallback bucket, not one more category to distinguish.
STRATEGY_STACK_COLORS = [
    "#1976d2", "#43a047", "#fb8c00", "#8e24aa", "#00838f", "#c62828", "#6d4c41", "#3949ab",
]
UNASSIGNED_COLOR = "#9e9e9e"
AVAILABLE_LINE_COLOR = "#212121"

# Appended to a person's axis label when their allocation totals over 100% —
# a bar that only just pokes past the 100% reference line can be easy to miss.
OVER_ALLOCATED_MARK = " ⚠"

# Sufficient/insufficient bar colours for the workstream capacity check chart —
# reuses the same green/red as the "Active workstreams"/"Tasks blocked" KPI
# tiles above, for the same good/bad semantic.
SUFFICIENT_COLOR = "#43a047"
INSUFFICIENT_COLOR = "#e53935"


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
        # left/right are equal so containLabel expands symmetrically and the
        # heatmap stays centred instead of drifting toward one side.
        "grid": {"left": "4%", "right": "4%", "top": 55, "bottom": "12%", "containLabel": True},
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


def _load_person_allocation_data() -> tuple[list[dict], list[dict], list[dict]]:
    with get_session() as session:
        members = [
            {"id": m.id, "name": m.name}
            for m in session.query(TeamMember).order_by(TeamMember.name).all()
        ]
        workstreams = [
            {"id": w.id, "name": w.name}
            for w in session.query(Workstream).order_by(Workstream.id).all()
        ]
        rows = workstream_allocation_pct(session)
    return members, workstreams, rows


def build_person_allocation_chart_options(
    members: list[dict], workstreams: list[dict], rows: list[dict]
) -> dict | None:
    """Stacked horizontal bar chart of each person's standing % allocation
    across workstreams, from app.services.workstream_allocation_pct — one bar
    per person, one stacked segment per workstream they're allocated to, plus
    a neutral "Unallocated" segment filling the gap up to 100% for anyone
    under capacity.

    A dashed reference line at 100% makes over/under-allocation directly
    readable: a bar extending past the line is over capacity (that person's
    workstreams are, collectively, over-allocating them); a bar that doesn't
    reach it, with a visible gray remainder, is under capacity. Members over
    100% also get OVER_ALLOCATED_MARK appended to their axis label.

    Every person is included (even with an all-gray, 0%-allocated bar) so
    spare capacity is visible too — this only returns None when nobody has
    any standing allocation at all yet.
    """
    if not rows or not members or not workstreams:
        return None

    by_member: dict[int, dict[int, float]] = {}
    for r in rows:
        by_member.setdefault(r["team_member_id"], {})[r["workstream_id"]] = r["allocation_pct"]

    totals = {m["id"]: sum(by_member.get(m["id"], {}).values()) for m in members}

    ws_ids_present = {ws_id for allocs in by_member.values() for ws_id in allocs}
    workstreams_present = [w for w in workstreams if w["id"] in ws_ids_present]
    if not workstreams_present:
        return None

    names = [
        f"{m['name']}{OVER_ALLOCATED_MARK}" if totals[m["id"]] > 100 else m["name"]
        for m in members
    ]

    bar_series = [
        {
            "name": ws["name"],
            "type": "bar",
            "stack": "alloc",
            "itemStyle": {"color": STRATEGY_STACK_COLORS[i % len(STRATEGY_STACK_COLORS)]},
            "data": [by_member.get(m["id"], {}).get(ws["id"], 0.0) for m in members],
        }
        for i, ws in enumerate(workstreams_present)
    ]

    unallocated_series = {
        "name": "Unallocated",
        "type": "bar",
        "stack": "alloc",
        "itemStyle": {"color": UNASSIGNED_COLOR},
        "data": [max(0.0, 100.0 - totals[m["id"]]) for m in members],
        "markLine": {
            "silent": True,
            "symbol": "none",
            "lineStyle": {"type": "dashed", "color": AVAILABLE_LINE_COLOR},
            "label": {"formatter": "100%"},
            "data": [{"xAxis": 100}],
        },
    }

    return {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"top": 0, "type": "scroll"},
        # left/right equal (see build_workstream_person_grid_options's comment on the same
        # convention) so the plot area — not just the outer chart box — sits centred instead
        # of drifting toward the narrower-margin side.
        "grid": {"left": "18%", "right": "18%", "top": 50, "bottom": "10%", "containLabel": True},
        "xAxis": {
            "type": "value",
            "name": "% allocated",
            "nameLocation": "middle",
            "nameGap": 30,
            "axisLabel": {"formatter": "{value}%"},
        },
        "yAxis": {"type": "category", "inverse": True, "data": names},
        "series": [*bar_series, unallocated_series],
    }


def _load_workstream_capacity_check_data() -> list[dict]:
    with get_session() as session:
        return workstream_capacity_check(session)


def build_workstream_capacity_check_options(rows: list[dict]) -> dict | None:
    """Bar + line chart of each workstream's top-down allocated capacity
    (bar, coloured green/red for sufficient/insufficient) against its
    bottom-up required task effort (dashed line), both in person-weeks — from
    app.services.workstream_capacity_check. Same bar+line shape as
    build_team_capacity_chart_options, just per workstream instead of per
    month, so it gets the same plain axis-trigger tooltip for free.

    Returns None when no workstream has both an estimated duration and either
    a standing allocation or an open task — see
    workstream_capacity_check's docstring for what's excluded and why.
    """
    if not rows:
        return None

    return {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"top": 0},
        "grid": {"left": "6%", "right": "4%", "top": 50, "bottom": "10%", "containLabel": True},
        "xAxis": {"type": "category", "data": [r["name"] for r in rows], "axisLabel": {"interval": 0}},
        "yAxis": {"type": "value", "name": "Person-weeks", "nameLocation": "middle", "nameGap": 40},
        "series": [
            {
                "name": "Allocated capacity",
                "type": "bar",
                "data": [
                    {
                        "value": r["allocated_weeks"],
                        "itemStyle": {"color": SUFFICIENT_COLOR if r["sufficient"] else INSUFFICIENT_COLOR},
                    }
                    for r in rows
                ],
            },
            {
                "name": "Required effort",
                "type": "line",
                "itemStyle": {"color": AVAILABLE_LINE_COLOR},
                "lineStyle": {"type": "dashed", "width": 2},
                "symbol": "circle",
                "symbolSize": 8,
                "data": [r["required_weeks"] for r in rows],
            },
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

        ui.label("Workstream allocation").classes("text-2xl font-bold")
        ui.label(
            "Each person's standing % allocation across workstreams (set from the People "
            "page's allocation action). The dashed line marks 100% capacity — a bar "
            "extending past it is over-allocated; the gray remainder is spare capacity."
        ).classes("text-sm text-gray-500")

        alloc_members, alloc_workstreams, alloc_rows = _load_person_allocation_data()
        alloc_options = build_person_allocation_chart_options(alloc_members, alloc_workstreams, alloc_rows)
        if alloc_options is None:
            ui.label("No standing workstream allocation set yet.").classes("text-sm text-gray-500")
        else:
            chart_height = max(280, 40 * len(alloc_members) + 120)
            ui.echart(alloc_options).classes("w-full").style(f"height: {chart_height}px")

        ui.label("Workstream capacity check").classes("text-2xl font-bold")
        ui.label(
            "Capacity allocated to each workstream (standing % allocation, spread over its "
            "estimated duration) against the open task effort it requires. A red bar means "
            "the workstream doesn't have enough people committed to it yet."
        ).classes("text-sm text-gray-500")

        capacity_check_rows = _load_workstream_capacity_check_data()
        capacity_check_options = build_workstream_capacity_check_options(capacity_check_rows)
        if capacity_check_options is None:
            ui.label(
                "No workstream has both an estimated duration and allocation/task data to compare yet."
            ).classes("text-sm text-gray-500")
        else:
            ui.echart(capacity_check_options).classes("w-full h-96")
