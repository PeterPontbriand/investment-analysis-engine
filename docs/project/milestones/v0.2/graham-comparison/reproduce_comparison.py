"""Executable successor to the original failed-comparison characterization.

Runs the deterministic production-composition success regression for both methods.
The pre-repair characterization remains available in Git history.
"""

import pytest

from tests.test_graham_comparison_composition import (
    test_verified_comparison_reaches_cli_and_cache as verify_comparison,
)


@pytest.mark.parametrize("command", ["graham-number", "graham-growth"])
def test_repaired_composition(command: str) -> None:
    """Verify the real evidence path rather than requiring the former defect."""
    verify_comparison(command, "--json", False)
