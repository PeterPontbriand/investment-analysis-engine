"""Live checks that Yahoo and SEC EDGAR still answer in the shape the adapters read.

These tests call the real services, so they are marked ``live_network``: the default run and the managed quality
gate never collect them, and ``--live`` selects only them. Each calls the shared check body the ``health``
command uses, makes at most the request budget of that check, and asserts shape, never a value. A failure prints
the check's own detail as the assertion message.
"""

import math
import re
from datetime import UTC, datetime

import pytest

from investment_analysis_engine.cli_health import build_provider_clients
from investment_analysis_engine.config import settings
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.provider_checks import PROVIDER_CHECKS, ProviderCheckEntry
from investment_analysis_engine.data.sec_edgar.cover_listing import (
    CoverReaderPolicy,
    cover_url,
    fetch_cover,
    read_cover_listing,
)
from investment_analysis_engine.data.sec_edgar.filing_document import (
    FilingHeaderPolicy,
    fetch_filing_header,
    filing_header_url,
)
from investment_analysis_engine.data.sec_edgar.financial_facts import SEC_PROVIDER_ID
from investment_analysis_engine.data.yfinance.client import YFINANCE_PROVIDER_ID, YFinanceClient

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


def test_sec_edgar_filing_header_response_shape() -> None:
    """Request one filing header, the anchor-filing request of a run, and check its shape, never a value."""
    identity = (settings.sec_user_agent or "").strip()
    assert identity, "SEC access is not configured: set SEC_USER_AGENT."
    accession = "0001628280-26-008131"
    text = fetch_filing_header(
        filing_header_url("19617", accession),
        headers={"User-Agent": identity},
        policy=FilingHeaderPolicy(),
        not_found=ProviderFailureKind.NO_DATA,
        provider_id=SEC_PROVIDER_ID,
    )
    assert re.search(rf"^<ACCESSION-NUMBER>{accession}$", text, re.MULTILINE)
    assert re.search(r"^<ACCEPTANCE-DATETIME>[0-9]{14}$", text, re.MULTILINE)
    assert re.search(r"^<FILING-DATE>[0-9]{8}$", text, re.MULTILINE)
    filer = re.search(r"<FILER>(.*?)</FILER>", text, re.DOTALL)
    assert filer is not None, "the header has no <FILER> block"
    assert re.search(r"^<CIK>[0-9]{10}$", filer.group(1), re.MULTILINE)
    assert re.search(r"^<ASSIGNED-SIC>[0-9]{4}$", filer.group(1), re.MULTILINE)


def test_sec_edgar_cover_response_shape() -> None:
    """Request one rendered cover, the listing check's one request, and check its shape, never a value."""
    identity = (settings.sec_user_agent or "").strip()
    assert identity, "SEC access is not configured: set SEC_USER_AGENT."
    accession = "0001628280-26-008131"
    url = cover_url("19617", accession)
    text = fetch_cover(
        url,
        headers={"User-Agent": identity},
        policy=CoverReaderPolicy(),
        not_found=ProviderFailureKind.NO_DATA,
        provider_id=SEC_PROVIDER_ID,
    )
    for concept in (
        "DocumentType",
        "EntityCentralIndexKey",
        "Security12bTitle",
        "TradingSymbol",
        "SecurityExchangeName",
    ):
        assert f"defref_dei_{concept}'" in text, f"the cover has no {concept} row"
    resolution = read_cover_listing(
        text,
        ticker="JPM",
        cik="19617",
        accession=accession,
        form="10-K",
        accepted_at=datetime(2026, 2, 13, tzinfo=UTC),
        boundary=datetime.now(UTC),
        source_url=url,
        retrieved_at=datetime.now(UTC),
    )
    assert resolution.reason is None, f"the live cover could not be read: {resolution.reason}"
    assert resolution.evidence is not None
    assert resolution.evidence.title, "the requested ticker's row has no title"


def test_yahoo_split_adjusted_history_response_shape() -> None:
    """Request the split-adjusted history of an issuer that has split, and check its shape, never a value."""
    history = YFinanceClient().fetch_split_adjusted_history("AAPL", "2020-08-01")
    assert list(history.close.columns) == ["Close"]
    assert len(history.close) > 100
    assert (history.close["Close"] > 0).all()
    assert history.events, "an issuer that has split returned no split event"
    assert all(math.isfinite(event.ratio) and event.ratio > 0 for event in history.events)
    assert history.context.data_as_of is not None
    assert history.adjustment_date >= history.context.data_as_of
    assert history.context.price_adjustment == "split_adjusted"
