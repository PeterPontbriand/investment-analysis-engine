"""Live checks that Yahoo and SEC EDGAR still answer in the shape the adapters read.

These tests call the real services, so they are marked ``live_network``: the default run and the managed quality
gate never collect them, and ``--live`` selects only them. Each calls the shared check body the ``health``
command uses, makes at most the request budget of that check, and asserts shape, never a value. A failure prints
the check's own detail as the assertion message.
"""

import pytest

from src.cli_health import build_provider_clients
from src.data.provider_checks import PROVIDER_CHECKS, ProviderCheckEntry
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from src.data.yfinance.client import YFINANCE_PROVIDER_ID

pytestmark = pytest.mark.live_network


def _entry(provider_id: str) -> ProviderCheckEntry:
    return next(entry for entry in PROVIDER_CHECKS if entry.provider_id == provider_id)


def _assert_passes(provider_id: str) -> None:
    result = _entry(provider_id).run(build_provider_clients())
    assert result.passed, (
        f"{provider_id} check failed ({result.probe}, {result.elapsed_seconds:.2f} s): {result.detail}"
    )


def test_yahoo_response_shape() -> None:
    _assert_passes(YFINANCE_PROVIDER_ID)


def test_sec_edgar_response_shape() -> None:
    _assert_passes(SEC_PROVIDER_ID)
