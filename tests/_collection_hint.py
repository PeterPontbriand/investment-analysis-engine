"""A line for a collection error in a conformance test module, pointing at the status command.

When a strategy file or a wiring entry is removed, the package cannot be imported and a conformance test module fails
at collection with the Python error alone, which names no edit site. The status command attributes the same error to a
site, so the report of such a collection error ends with a line that says to run it.
"""

from collections.abc import Generator
from typing import Any, Final

import pytest

CONFORMANCE_MODULES: Final = frozenset(
    {
        "tests/scripts/test_strategy_status.py",
        "tests/test_cli_strategy_wiring.py",
        "tests/test_failure_messages.py",
        "tests/test_save_run_every_direct_command.py",
        "tests/test_specimen_strategy.py",
        "tests/test_strategy_wiring_conformance.py",
    }
)
"""The test modules, by path from the repository root, that fail at collection when the strategy wiring is broken."""

HINT: Final = (
    "Run the status command to see which site: uv run python -m scripts.strategy_status <module_name> [--alias <alias>]"
)
SECTION: Final = "Edit site"


def add_hint(report: pytest.CollectReport) -> None:
    """Append the hint to the report of a failed collection of a conformance test module; any other report is left.

    pytest reports an exception raised while a module runs as a traceback representation that takes a named section,
    and an import error of the module itself as a representation that holds the message text.
    """
    if not report.failed or report.nodeid.replace("\\", "/") not in CONFORMANCE_MODULES:
        return
    longrepr = report.longrepr
    add_section = getattr(longrepr, "addsection", None)
    if add_section is not None:
        add_section(SECTION, HINT, "-")
    elif isinstance(getattr(longrepr, "longrepr", None), str):
        longrepr.longrepr = longrepr.longrepr + "\n" + HINT  # type: ignore[union-attr]
    elif isinstance(longrepr, str):
        report.longrepr = longrepr + "\n" + HINT


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector: pytest.Collector) -> Generator[None, Any, None]:  # noqa: ARG001 - fixed hook signature
    """Add the status-command hint to a collection error in a conformance test module."""
    outcome = yield
    add_hint(outcome.get_result())
