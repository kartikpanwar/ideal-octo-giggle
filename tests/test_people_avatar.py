"""_initials() / _avatar_color() drive the People table's avatar chips."""

from __future__ import annotations

from app.pages.people import AVATAR_PALETTE, _avatar_color, _initials


def test_initials_two_word_name():
    assert _initials("Alice Nguyen") == "AN"


def test_initials_three_word_name_uses_first_and_last():
    assert _initials("Mary Jane Watson") == "MW"


def test_initials_single_word_name():
    assert _initials("Cher") == "CH"


def test_initials_empty_name():
    assert _initials("") == "?"


def test_avatar_color_stable_per_id():
    assert _avatar_color(3) == _avatar_color(3)


def test_avatar_color_cycles_through_palette():
    n = len(AVATAR_PALETTE)
    assert _avatar_color(0) == _avatar_color(n)  # wraps around
    assert _avatar_color(1) != _avatar_color(2) or n == 1
