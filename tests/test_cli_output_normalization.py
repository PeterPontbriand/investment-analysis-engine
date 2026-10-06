"""``normalize_cli_output`` makes Rich panel output the same on every platform and terminal."""

from __future__ import annotations

from tests._cli_helpers import normalize_cli_output

_SQUARE = "┌─ Commands ─────────┐\n│ momentum  Run it.  │\n└────────────────────┘\n"
_ROUNDED = "╭─ Commands ─────────╮\n│ momentum  Run it.  │\n╰────────────────────╯\n"
_STYLED = "\x1b[1m┌─ Commands ─────────┐\x1b[0m\n│ \x1b[36mmomentum\x1b[0m  Run it.  │\n└────────────────────┘\n"


def test_square_and_rounded_corners_normalize_to_the_same_text() -> None:
    """A panel drawn with square corners (Windows console) equals the same panel drawn with rounded ones."""
    assert normalize_cli_output(_SQUARE) == normalize_cli_output(_ROUNDED)
    assert normalize_cli_output(_SQUARE) == "Commands momentum Run it."


def test_ansi_styling_does_not_change_the_normalized_text() -> None:
    """Colour and weight codes are removed, whichever corner style the panel uses."""
    assert normalize_cli_output(_STYLED) == normalize_cli_output(_SQUARE)


def test_a_different_word_still_differs() -> None:
    """The normalization removes layout only: changed text is still a difference."""
    assert normalize_cli_output(_SQUARE.replace("Run it.", "Run that.")) != normalize_cli_output(_ROUNDED)
