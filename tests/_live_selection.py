"""Opt-in selection of tests that deliberately call a live provider.

A test marked ``live_network`` is the only kind that may reach a real service (see ``tests/_network_guard.py``).
The default run deselects every such test; ``--live`` selects only those tests. The hook lives in conftest rather
than in ``addopts`` because the managed quality-gate wrappers run with ``-o addopts=``, which would drop an
``addopts`` exclusion and let a live test into the gate.
"""

from __future__ import annotations

import pytest

from tests._network_guard import LIVE_NETWORK_MARKER

LIVE_OPTION = "--live"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add the opt-in switch that runs only the live provider tests."""
    parser.addoption(
        LIVE_OPTION,
        action="store_true",
        default=False,
        help="Run only the tests marked live_network, which call the real providers.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register the live-provider marker."""
    config.addinivalue_line(
        "markers",
        f"{LIVE_NETWORK_MARKER}: calls a real provider; excluded from the default run, selected alone by {LIVE_OPTION}",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Deselect live tests by default, or everything else when ``--live`` is given."""
    live_requested = bool(config.getoption(LIVE_OPTION))
    kept: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        is_live = item.get_closest_marker(LIVE_NETWORK_MARKER) is not None
        (kept if is_live == live_requested else deselected).append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = kept
