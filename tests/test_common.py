"""app.pages.common helpers shared across pages."""

from __future__ import annotations

from datetime import date

from app.models import STRATEGY_STATUSES, TASK_PRIORITIES, TASK_STATUSES, WORKSTREAM_STATUSES
from app.pages.common import (
    PRIORITY_BADGE_SLOT,
    PRIORITY_COLORS,
    STATUS_BADGE_SLOT,
    STATUS_COLORS,
    dot_badge_slot,
    month_year_axis_label,
)


def _formatter(timeline_start: date) -> str:
    return month_year_axis_label(timeline_start)["axisLabel"][":formatter"]


def test_embeds_utc_midnight_epoch_for_reference_date():
    # 2000-01-01T00:00:00Z, independently known epoch (946684800000 ms).
    assert "946684800000" in _formatter(date(2000, 1, 1))


def test_embeds_correct_epoch_for_a_leap_year_date():
    # 2026-01-01T00:00:00Z, independently known epoch (1767225600000 ms).
    assert "1767225600000" in _formatter(date(2026, 1, 1))


def test_formatter_is_a_bare_function_expression():
    # NiceGUI's dynamic-property conversion does `new Function("return (" + v + ")")()`,
    # so this must be a plain function expression, not a statement or an IIFE.
    formatter = _formatter(date(2026, 9, 1))
    assert formatter.strip().startswith("function(")
    assert not formatter.strip().endswith("})()")  # not self-invoked


def test_uses_only_utc_date_methods():
    # Using local (non-UTC) Date methods here would make the rendered label
    # depend on the viewer's browser timezone.
    formatter = _formatter(date(2026, 9, 1))
    assert "getUTCMonth" in formatter
    assert "getUTCFullYear" in formatter
    assert "setUTCDate" in formatter
    assert "getMonth()" not in formatter
    assert "getFullYear()" not in formatter


def test_min_interval_guarantees_a_distinct_month_per_tick():
    # No month has more than 31 days, so a step of >=31 days from any
    # starting day-of-month always lands in a different calendar month —
    # otherwise consecutive ticks could repeat e.g. "Sep-26" back to back.
    assert month_year_axis_label(date(2026, 9, 1))["minInterval"] >= 31


# --- dot_badge_slot / STATUS_BADGE_SLOT / PRIORITY_BADGE_SLOT ---

def test_dot_badge_slot_binds_the_given_field_names():
    slot = dot_badge_slot("foo_color", "foo")
    assert "props.row.foo_color" in slot
    assert "props.row.foo" in slot
    assert "{{ props.row.foo }}" in slot


def test_status_badge_slot_matches_hand_written_original():
    # Locks in the exact markup the earlier hardcoded STATUS_BADGE_SLOT used,
    # so refactoring it through dot_badge_slot can't silently change the
    # rendered HTML (e.g. losing the flex-shrink:0 or the gap).
    expected = (
        '<q-td :props="props">'
        '<div class="row items-center no-wrap" style="gap:6px">'
        "<div :style=\"'background-color:' + props.row.status_color + "
        "'; width:10px; height:10px; border-radius:50%; flex-shrink:0;'\"></div>"
        "<span>{{ props.row.status }}</span>"
        "</div></q-td>"
    )
    assert STATUS_BADGE_SLOT == expected


def test_priority_badge_slot_uses_priority_fields():
    assert "props.row.priority_color" in PRIORITY_BADGE_SLOT
    assert "{{ props.row.priority }}" in PRIORITY_BADGE_SLOT
    assert "props.row.status" not in PRIORITY_BADGE_SLOT


# --- Colour map coverage ---
# Every value pages actually put in a "status"/"priority" field should have
# an explicit colour, so pages fall back to STATUS_COLOR_FALLBACK /
# PRIORITY_COLOR_FALLBACK only for genuinely unexpected data, not routine values.

def test_status_colors_cover_every_task_and_workstream_status():
    for status in TASK_STATUSES:
        assert status in STATUS_COLORS
    for status in WORKSTREAM_STATUSES:
        assert status in STATUS_COLORS


def test_status_colors_cover_every_strategy_status():
    for status in STRATEGY_STATUSES:
        assert status in STATUS_COLORS


def test_priority_colors_cover_every_task_priority():
    for priority in TASK_PRIORITIES:
        assert priority in PRIORITY_COLORS


def test_priority_colors_are_distinct_from_status_colors():
    # Not a strict requirement, but the two palettes are deliberately chosen
    # not to overlap (see the comment on PRIORITY_COLORS) so a status dot and
    # a priority dot in the same row never accidentally look identical.
    assert set(PRIORITY_COLORS.values()).isdisjoint(STATUS_COLORS.values())
