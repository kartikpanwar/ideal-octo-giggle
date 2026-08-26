"""Small helpers shared across CRUD pages: date parsing, FK option lists, and
the status colour map + table badge slot used on every status column."""

from __future__ import annotations

from datetime import date, datetime, timezone

from app.db import get_session
from app.models import CapacityPeriod, StrategyItem, TeamMember, Workstream

# Status -> colour, covering both the task/workstream vocabulary
# (not_started, in_progress, blocked, done, cancelled) and the strategy item
# one (proposed, active, on_hold, done, cancelled) — shared by the timeline
# charts and every status table column.
STATUS_COLORS = {
    "not_started": "#9e9e9e",
    "in_progress": "#1976d2",
    "blocked": "#e53935",
    "done": "#43a047",
    "cancelled": "#bdbdbd",
    "proposed": "#90a4ae",
    "active": "#1976d2",
    "on_hold": "#fb8c00",
}
STATUS_COLOR_FALLBACK = "#9e9e9e"

# body-cell-status slot for a ui.table: a coloured dot + the status text.
# Requires each row dict to carry a "status_color" field (e.g.
# STATUS_COLORS.get(row["status"], STATUS_COLOR_FALLBACK)) alongside "status".
STATUS_BADGE_SLOT = (
    '<q-td :props="props">'
    '<div class="row items-center no-wrap" style="gap:6px">'
    "<div :style=\"'background-color:' + props.row.status_color + "
    "'; width:10px; height:10px; border-radius:50%; flex-shrink:0;'\"></div>"
    "<span>{{ props.row.status }}</span>"
    "</div></q-td>"
)


def parse_date(value: str | None) -> date | None:
    value = (value or "").strip()
    return date.fromisoformat(value) if value else None


def month_year_axis_label(timeline_start: date) -> dict:
    """xAxis config (spread into the xAxis dict) that renders a numeric 'days
    from timeline_start' tick as a calendar month/year (e.g. "Sep-26"), for
    the timeline (Gantt-style) charts' xAxis.

    A plain ECharts 'value' axis has no date-aware tick formatting (only a
    'time' axis does, and switching axis types would mean rebuilding the
    offset/duration stacking math around absolute epoch timestamps, which
    drags in browser-timezone-dependent date formatting we can't control from
    here). Instead this embeds a small JS formatter — via NiceGUI's ':'
    dynamic-property convention, see nicegui/elements/echart's use of
    convertDynamicProperties — that adds the tick's day offset to
    `timeline_start` and formats it. It uses only UTC-suffixed Date methods,
    so the result is identical regardless of the viewer's browser timezone.

    `minInterval: 31` stops ECharts' auto tick placement from landing two
    ticks in the same calendar month (which would repeat e.g. "Sep-26" back
    to back) — no month has more than 31 days, so a >=31-day step from any
    starting day-of-month always crosses into the next month.
    """
    epoch_ms = int(
        datetime(timeline_start.year, timeline_start.month, timeline_start.day, tzinfo=timezone.utc)
        .timestamp()
        * 1000
    )
    formatter = (
        "function(v){"
        "var m=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];"
        f"var d=new Date({epoch_ms});"
        "d.setUTCDate(d.getUTCDate()+v);"
        "return m[d.getUTCMonth()]+'-'+String(d.getUTCFullYear()).slice(-2);"
        "}"
    )
    return {"axisLabel": {":formatter": formatter}, "minInterval": 31}


def fmt_date(value: date | None) -> str:
    return value.isoformat() if value else ""


def member_options() -> dict[int, str]:
    with get_session() as session:
        return {m.id: m.name for m in session.query(TeamMember).order_by(TeamMember.name).all()}


def strategy_options() -> dict[int, str]:
    with get_session() as session:
        return {s.id: s.name for s in session.query(StrategyItem).order_by(StrategyItem.name).all()}


def workstream_options() -> dict[int, str]:
    with get_session() as session:
        return {w.id: w.name for w in session.query(Workstream).order_by(Workstream.name).all()}


def period_options() -> dict[int, str]:
    with get_session() as session:
        return {p.id: p.name for p in session.query(CapacityPeriod).order_by(CapacityPeriod.id).all()}
