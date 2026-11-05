"""Hand a test's fake probe to the operations that build their own.

Each operation that reports a provider failure builds its probe from the application context's settings. A test that
needs a probe with chosen findings patches the two builders the commands reach: the direct-analysis operation and
the refresh command.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch


@contextmanager
def injected_probe(probe: object) -> Iterator[None]:
    """Make every operation use ``probe`` for the life of the block."""
    with (
        patch("investment_analysis_engine.application.analysis.build_provider_probe", return_value=probe),
        patch("investment_analysis_engine.cli_workspace.build_provider_probe", return_value=probe),
    ):
        yield
