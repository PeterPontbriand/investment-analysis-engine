"""Versioned deterministic SEC FPI fixtures for the Step 2.5A Golden Suite."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from src.data.instrument_profile import InstrumentKind, InstrumentKindEvidence, InstrumentProfile
from src.data.sec_edgar.financial_facts import SecEdgarFinancialFactsAdapter
from src.data.security_identity import SecurityIdentity
from src.data.security_unit import SecurityUnitEvidence, SecurityUnitKind

SEC_FPI_ASML_FIXTURE_ID: Final = "sec_fpi_asml_us_gaap_20f"
SEC_FPI_NTR_FIXTURE_ID: Final = "sec_fpi_ntr_ifrs"
SEC_FPI_SAP_FIXTURE_ID: Final = "sec_fpi_sap_exact_capex_absent"
SEC_FPI_NVO_FIXTURE_ID: Final = "sec_fpi_nvo_security_unit_negative"
SEC_FPI_FIXTURE_IDS: Final = frozenset(
    {SEC_FPI_ASML_FIXTURE_ID, SEC_FPI_NTR_FIXTURE_ID, SEC_FPI_SAP_FIXTURE_ID, SEC_FPI_NVO_FIXTURE_ID}
)

_ISSUER_BY_FIXTURE_ID = {
    SEC_FPI_ASML_FIXTURE_ID: "asml",
    SEC_FPI_NTR_FIXTURE_ID: "ntr",
    SEC_FPI_SAP_FIXTURE_ID: "sap",
    SEC_FPI_NVO_FIXTURE_ID: "nvo",
}
_FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "sec_edgar" / "step_2_5a_d0"
_USER_AGENT = "Step 2.5A Golden fixture tests@example.invalid"


def _load(name: str) -> Any:
    """Load one checked-in D0 evidence fragment."""
    return json.loads((_FIXTURE_ROOT / name).read_text(encoding="utf-8"))


class _FrozenSecFetcher:
    """Serve one issuer's minimized SEC payloads without network access."""

    def __init__(self, issuer: str) -> None:
        self._issuer = issuer

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
        if headers["User-Agent"] != _USER_AGENT:
            raise AssertionError("Unexpected deterministic SEC user agent.")
        if "company_tickers.json" in url:
            rows: dict[str, dict[str, object]] = _load("company_tickers.json")
            ticker = self._issuer.upper()
            return {key: row for key, row in rows.items() if row["ticker"] == ticker}
        if "/companyfacts/" in url:
            return _load(f"{self._issuer}_companyfacts.json")
        if "/submissions/" in url:
            return _load(f"{self._issuer}_submissions.json")
        raise AssertionError(f"Unexpected deterministic SEC URL: {url}")


def fixture_sec_fpi_adapter(fixture_id: str, *, clock_at: datetime) -> SecEdgarFinancialFactsAdapter:
    """Build the exact frozen SEC adapter selected by a versioned fixture ID."""
    issuer = _ISSUER_BY_FIXTURE_ID[fixture_id]
    return SecEdgarFinancialFactsAdapter(
        json_fetcher=_FrozenSecFetcher(issuer),
        clock=lambda: clock_at,
        user_agent=_USER_AGENT,
    )


def fixture_nvo_security_unit_profile(*, resolved_at: datetime) -> InstrumentProfile:
    """Build NVO's frozen ADR evidence without performing any conversion."""
    payload: dict[str, object] = _load("nvo_security_unit_evidence.json")
    ticker = str(payload["quoted_ticker"])
    identity = SecurityIdentity(ticker=ticker, provider_id="sec_edgar", resolved_at=resolved_at)
    kind = InstrumentKindEvidence(
        ticker=ticker,
        kind=InstrumentKind.EQUITY,
        provider_value="EQUITY",
        provider_id="yfinance",
        resolved_at=resolved_at,
    )
    ratio = payload["deposited_shares_per_adr"]
    if not isinstance(ratio, int | float):
        raise ValueError("Frozen NVO ADR ratio must be numeric.")
    unit = SecurityUnitEvidence(
        ticker=ticker,
        filing_unit_kind=SecurityUnitKind.ORDINARY_SHARE,
        quoted_unit_kind=SecurityUnitKind.ADR,
        underlying_shares_per_quoted_unit=float(ratio),
        provider_id="sec_edgar",
        source=str(payload["filing_security_title"]),
    )
    return InstrumentProfile(
        ticker=ticker,
        identity=identity,
        kind_evidence=kind,
        diagnostics=(),
        security_unit_evidence=unit,
    )
