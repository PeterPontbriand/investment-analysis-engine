"""File-name roles of a strategy package, shared by the layering and boundary tests."""

from __future__ import annotations

from typing import Final

ANALYZER_ROLES: Final = frozenset(
    {"analyzer", "calculation", "calculators", "config", "input_resolver", "models", "service"}
)
"""Analyzer-level files: calculation code that may import one another but nothing above them."""

ROLE_RANK: Final = {
    "vocabulary": -1,
    **dict.fromkeys(ANALYZER_ROLES, 0),
    "envelope": 0,
    "selection": 1,
    "codec": 1,
    "tool": 2,
    "execution": 2,
    "presenter": 3,
    "replay": 4,
    "cli": 5,
    "evaluation": 5,
}
"""Rank of each recognized role; a file may import only a lower-ranked role of its own package."""
