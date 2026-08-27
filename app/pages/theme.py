"""App-wide visual theme: header/nav bar colour, page background, and the
primary/secondary/accent/negative colours Quasar buttons and other
components pick up automatically via `ui.colors()`.

Deliberately separate from app.pages.common's STATUS_COLORS / PRIORITY_COLORS
— those carry meaning (e.g. red = blocked) and shouldn't shift just because
the app's branding does. This module only covers non-semantic UI chrome.
Card backgrounds are left at Quasar's default white on purpose too: the
"deep_space" palette's background colour (mint-cream) is meant as a subtle
page wash, and giving cards that same tone would erase the contrast that
makes them read as distinct surfaces.

Palettes are a plain, swappable registry (`PALETTES`) selected by
`ACTIVE_PALETTE`. To switch — including back to how this app looked before
any custom theme existed — change `ACTIVE_PALETTE` to another key in
`PALETTES` and restart the app; no other code needs to change. `"classic"`
is the exact Quasar/NiceGUI default colours this app rendered with
(unstyled) before this module was introduced, captured verbatim so
reverting is a faithful, one-line change rather than a guess.
"""

from __future__ import annotations

from dataclasses import dataclass

from nicegui import ui


@dataclass(frozen=True)
class Palette:
    """The Quasar theme roles this app actually uses, plus the page
    background (which Quasar's colour roles don't cover — see apply_theme)."""

    primary: str  # header/nav bar background, primary buttons ("Add task", etc.)
    secondary: str  # secondary Quasar-themed elements
    accent: str  # accent highlights
    negative: str  # Quasar's "negative" role: ui.notify(type="negative"), validation errors
    background: str | None  # page background; None = Quasar/NiceGUI's own default (no override)


PALETTES: dict[str, Palette] = {
    # The exact Quasar defaults this app ran on before any custom theme
    # existed (https://quasar.dev/style/theme-builder's stock colours).
    # Kept as real hex values, not "leave everything unset", so switching
    # back to this is a genuine revert rather than "whatever Quasar ships
    # in some future version".
    "classic": Palette(
        primary="#1976D2",
        secondary="#26A69A",
        accent="#9C27B0",
        negative="#C10015",
        background=None,
    ),
    # "On My Plate" brand palette supplied 2026-08-27: deep-space-blue,
    # lavender-grey, mint-cream, strawberry-red, primary-scarlet. The two
    # reds get different roles since they're subtly different shades:
    # primary-scarlet as a deliberate accent highlight, strawberry-red as
    # Quasar's "negative" (error/validation) role, which is literally red
    # already by convention.
    "deep_space": Palette(
        primary="#273043",  # deep-space-blue
        secondary="#9197AE",  # lavender-grey
        accent="#DD0426",  # primary-scarlet
        negative="#F02D3A",  # strawberry-red
        background="#EFF6EE",  # mint-cream
    ),
}

ACTIVE_PALETTE = "deep_space"  # change this one line (+ restart) to switch palettes


def apply_theme() -> None:
    """Call once per page load (from layout.header()) to apply the active
    palette: Quasar theme roles via ui.colors(), plus the page background
    (a plain CSS override, since Quasar's colour roles don't include one)."""
    palette = PALETTES[ACTIVE_PALETTE]
    ui.colors(
        primary=palette.primary,
        secondary=palette.secondary,
        accent=palette.accent,
        negative=palette.negative,
    )
    if palette.background:
        # No `!important`: NiceGUI's ui.query().style() applies this via the
        # browser's 2-argument CSSStyleDeclaration.setProperty(key, value) —
        # embedding "!important" in that value string (rather than passing it
        # as setProperty's separate 3rd argument) is invalid and the browser
        # silently drops the whole declaration. Plain inline style already
        # out-specifies body's default (unset) background, so it isn't needed.
        ui.query("body").style(f"background-color: {palette.background};")
