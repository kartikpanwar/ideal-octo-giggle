"""app.pages.theme's palette registry: configurable, with a faithful
"classic" snapshot to revert to."""

from __future__ import annotations

import re

from app.pages.theme import ACTIVE_PALETTE, PALETTES

HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def test_active_palette_is_a_registered_key():
    assert ACTIVE_PALETTE in PALETTES


def test_every_palette_role_is_a_valid_hex_colour():
    for name, palette in PALETTES.items():
        for role in ("primary", "secondary", "accent", "negative"):
            value = getattr(palette, role)
            assert HEX_COLOR.match(value), f"{name}.{role} = {value!r} is not #RRGGBB"
        if palette.background is not None:
            assert HEX_COLOR.match(palette.background), (
                f"{name}.background = {palette.background!r} is not #RRGGBB"
            )


def test_classic_matches_quasar_stock_defaults():
    # Locked in so a future edit can't accidentally drift "classic" away from
    # being a faithful snapshot of how the app looked before any custom
    # theme existed -- the whole point of keeping it is a genuine revert path.
    classic = PALETTES["classic"]
    assert classic.primary == "#1976D2"
    assert classic.secondary == "#26A69A"
    assert classic.accent == "#9C27B0"
    assert classic.negative == "#C10015"
    assert classic.background is None


def test_deep_space_matches_supplied_brand_colours():
    deep_space = PALETTES["deep_space"]
    assert deep_space.primary == "#273043"  # deep-space-blue
    assert deep_space.secondary == "#9197AE"  # lavender-grey
    assert deep_space.accent == "#DD0426"  # primary-scarlet
    assert deep_space.negative == "#F02D3A"  # strawberry-red
    assert deep_space.background == "#EFF6EE"  # mint-cream


def test_palettes_are_registered_under_distinct_names_with_distinct_colours():
    # Sanity check against a copy-paste palette that doesn't actually change anything.
    names = list(PALETTES)
    assert len(names) == len(set(names))
    assert PALETTES["classic"] != PALETTES["deep_space"]
