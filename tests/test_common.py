"""app.pages.common helpers shared across pages."""

from __future__ import annotations

from datetime import date

from app.pages.common import month_year_axis_label


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
