"""Deterministic regression tests for SEC BVPS production-path hardening."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from src.analysis.graham_value.input_resolver import GrahamInputResolver
from src.core.analysis_status import CalculationStatus
from src.data.financial.facts import FinancialFactRequest, FinancialField
from src.data.financial.provenance import FinancialSubjectKind
from src.data.financial.resolver import InputResolutionResult
from src.data.sec_edgar.financial_facts import SEC_PROVIDER_ID, SecEdgarFinancialFactsAdapter

NOW = datetime(2026, 8, 23, 16, 0, tzinfo=UTC)
PERIOD_END = "2025-12-31"
ACCESSION = "0001-26"
FILED = "2026-02-20"
ACCEPTED = "2026-02-20T14:46:32Z"


class FakeJsonFetcher:
    """Return deterministic SEC payloads and record requested URLs."""

    def __init__(self, *, ticker: str, payload: object) -> None:
        """Initialize with a ticker and a payload to return for company facts."""
        self._ticker = ticker
        self._payload = payload
        self.calls: list[str] = []

    def __call__(self, url: str, *, headers: Mapping[str, str]) -> object:
        del headers
        self.calls.append(url)
        if "company_tickers.json" in url:
            return {"0": {"cik_str": 123456, "ticker": self._ticker, "title": "Fixture Corp"}}
        if "/companyfacts/" in url:
            return self._payload
        if "/submissions/" in url:
            return {
                "filings": {
                    "recent": {
                        "accessionNumber": [ACCESSION],
                        "acceptanceDateTime": [ACCEPTED],
                    }
                }
            }
        msg = f"Unexpected URL: {url}"
        raise AssertionError(msg)


def _annual_observation(value: float) -> dict[str, Any]:
    return {
        "end": PERIOD_END,
        "val": value,
        "accn": ACCESSION,
        "fy": 2025,
        "fp": "FY",
        "form": "10-K",
        "filed": FILED,
    }


def _base_payload() -> dict[str, Any]:
    return {"facts": {"us-gaap": {"StockholdersEquity": {"units": {"USD": [_annual_observation(75_000_000_000.0)]}}}}}


def _us_gaap(payload: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], payload["facts"]["us-gaap"])


def _add_common_direct(payload: dict[str, Any], shares: float) -> None:
    _us_gaap(payload)["CommonStockSharesOutstanding"] = {"units": {"shares": [_annual_observation(shares)]}}


def _add_common_issued_treasury(
    payload: dict[str, Any],
    *,
    issued: float,
    treasury: float,
) -> None:
    us_gaap = _us_gaap(payload)
    us_gaap["CommonStockSharesIssued"] = {"units": {"shares": [_annual_observation(issued)]}}
    us_gaap["TreasuryStockCommonShares"] = {"units": {"shares": [_annual_observation(treasury)]}}


def _add_hlf_neutral_preferred_concepts(payload: dict[str, Any]) -> None:
    us_gaap = _us_gaap(payload)
    us_gaap["PreferredStockSharesAuthorized"] = {"units": {"shares": [_annual_observation(7_500_000.0)]}}
    us_gaap["PreferredStockParOrStatedValuePerShare"] = {"units": {"USD/shares": [_annual_observation(0.002)]}}


def _adapter(ticker: str, payload: object) -> SecEdgarFinancialFactsAdapter:
    return SecEdgarFinancialFactsAdapter(
        json_fetcher=FakeJsonFetcher(ticker=ticker, payload=payload),
        clock=lambda: NOW,
        user_agent="Fixture Tester fixture@example.com",
    )


def _component_request(ticker: str, field: FinancialField) -> FinancialFactRequest:
    return FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=ticker,
        field_name=field,
        provider_id=SEC_PROVIDER_ID,
        basis="fiscal_year_end",
    )


def _resolve_bvps(ticker: str, payload: object) -> InputResolutionResult:
    adapter = _adapter(ticker, payload)
    resolver = GrahamInputResolver(provider=adapter, clock=lambda: NOW)
    request = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=ticker,
        field_name=FinancialField.BVPS,
        provider_id=SEC_PROVIDER_ID,
    )
    return resolver.resolve_bvps(request)


def test_ko_shape_derives_common_shares_and_infers_zero_preferred_guard() -> None:
    """KO-shaped Company Facts support the validated BVPS fallback path."""
    payload = _base_payload()
    _add_common_issued_treasury(payload, issued=7_040_000_000.0, treasury=2_738_000_000.0)

    result = _resolve_bvps("KO", payload)

    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.value == pytest.approx(75_000_000_000.0 / 4_302_000_000.0)
    assert result.resolved_input.lineage is not None
    provider_fields = {component.provider_field for component in result.resolved_input.lineage.components}
    assert "derived:us-gaap:CommonStockSharesIssued-us-gaap:TreasuryStockCommonShares" in provider_fields
    assert "inferred:sec-company-facts:no-issued-preferred-equity" in provider_fields


def test_hlf_shape_authorized_and_par_only_preferred_concepts_infer_zero_guard() -> None:
    """HLF-shaped authorized/par disclosures do not imply issued preferred equity."""
    payload = _base_payload()
    _add_common_direct(payload, 103_300_000.0)
    _add_hlf_neutral_preferred_concepts(payload)

    result = _resolve_bvps("HLF", payload)

    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.lineage is not None
    preferred = next(
        component
        for component in result.resolved_input.lineage.components
        if component.field_name == FinancialField.PREFERRED_SHARES_OUTSTANDING.value
    )
    assert preferred.value == pytest.approx(0.0)
    assert preferred.provider_field == "inferred:sec-company-facts:no-issued-preferred-equity"
    assert any("shares-authorized/par-value" in note for note in preferred.notes)


def test_ko_direct_adapter_infers_zero_preferred_from_derived_common_shares() -> None:
    """KO-shaped: derived common shares (issued - treasury) with no preferred concepts."""
    payload = _base_payload()
    # Replace the base payload equity with the real KO figure
    _us_gaap(payload)["StockholdersEquity"] = {"units": {"USD": [_annual_observation(32_169_000_000.0)]}}
    _add_common_issued_treasury(payload, issued=7_040_000_000.0, treasury=2_738_000_000.0)
    adapter = _adapter("KO", payload)

    common = adapter.fetch_facts(
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="KO",
            field_name=FinancialField.COMMON_SHARES_OUTSTANDING,
            provider_id=SEC_PROVIDER_ID,
            basis="fiscal_year_end",
            as_of=NOW,
        )
    )
    assert len(common) == 1
    assert common[0].value == 4_302_000_000
    assert common[0].provider_field == "derived:us-gaap:CommonStockSharesIssued-us-gaap:TreasuryStockCommonShares"

    preferred = adapter.fetch_facts(
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="KO",
            field_name=FinancialField.PREFERRED_SHARES_OUTSTANDING,
            provider_id=SEC_PROVIDER_ID,
            basis="fiscal_year_end",
            as_of=NOW,
        )
    )
    assert len(preferred) == 1
    assert preferred[0].value == 0
    assert preferred[0].provider_field == "inferred:sec-company-facts:no-issued-preferred-equity"
    assert preferred[0].observation_period_end is not None
    assert preferred[0].observation_period_end.isoformat().startswith("2025-12-31")
    notes = preferred[0].notes
    assert any("not an explicit PreferredStockSharesOutstanding fact" in n for n in notes)
    assert any("evidence_pattern=" in n and "issued-minus-treasury" in n for n in notes)


def test_hlf_direct_adapter_infers_zero_preferred_from_authorized_par_only() -> None:
    """HLF-shaped: authorized + par-value only, direct common shares outstanding."""
    payload = _base_payload()
    # Replace equity with the real HLF figure
    _us_gaap(payload)["StockholdersEquity"] = {"units": {"USD": [_annual_observation(-515_100_000.0)]}}
    _add_common_direct(payload, 103_300_000.0)
    _add_hlf_neutral_preferred_concepts(payload)
    adapter = _adapter("HLF", payload)

    preferred = adapter.fetch_facts(
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="HLF",
            field_name=FinancialField.PREFERRED_SHARES_OUTSTANDING,
            provider_id=SEC_PROVIDER_ID,
            basis="fiscal_year_end",
            as_of=NOW,
        )
    )
    assert len(preferred) == 1
    assert preferred[0].value == 0
    assert preferred[0].provider_field == "inferred:sec-company-facts:no-issued-preferred-equity"
    assert preferred[0].observation_period_end is not None
    assert preferred[0].observation_period_end.isoformat().startswith("2025-12-31")
    notes = preferred[0].notes
    assert any("not an explicit PreferredStockSharesOutstanding fact" in n for n in notes)
    assert any("evidence_pattern=" in n and "shares-authorized" in n for n in notes)


def test_generic_missing_preferred_tag_with_direct_common_shares_remains_unavailable() -> None:
    """A merely absent preferred tag is not promoted to zero outside verified shapes."""
    payload = _base_payload()
    _add_common_direct(payload, 100_000_000.0)

    result = _resolve_bvps("MISS", payload)

    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.resolved_input is None
    assert result.reason is not None
    assert "preferred_shares_outstanding" in result.reason


def test_non_neutral_preferred_equity_concept_blocks_inferred_zero() -> None:
    """WFC-like positive preferred-equity evidence blocks the inferred-zero path."""
    payload = _base_payload()
    _add_common_direct(payload, 3_092_600_000.0)
    _us_gaap(payload)["PreferredStockValue"] = {"units": {"USD": [_annual_observation(16_608_000_000.0)]}}

    result = _resolve_bvps("WFCX", payload)

    assert result.status is CalculationStatus.INPUT_UNAVAILABLE
    assert result.resolved_input is None


def test_issued_minus_treasury_common_share_fallback_accepts_zero_treasury() -> None:
    """Zero treasury shares remain a valid component of the common-share derivation."""
    payload = _base_payload()
    _add_common_issued_treasury(payload, issued=15_000_000_000.0, treasury=0.0)
    adapter = _adapter("ZERO", payload)

    facts = adapter.fetch_facts(_component_request("ZERO", FinancialField.COMMON_SHARES_OUTSTANDING))

    assert len(facts) == 1
    assert facts[0].value == pytest.approx(15_000_000_000.0)
    assert facts[0].provider_field == ("derived:us-gaap:CommonStockSharesIssued-us-gaap:TreasuryStockCommonShares")


def test_future_preferred_equity_fact_does_not_create_historical_lookahead() -> None:
    """Preferred evidence filed after as_of cannot contaminate an earlier KO-shaped resolution."""
    payload = _base_payload()
    _add_common_issued_treasury(payload, issued=7_040_000_000.0, treasury=2_738_000_000.0)
    future = _annual_observation(10_000_000_000.0)
    future.update(
        {
            "end": "2026-12-31",
            "accn": "0001-27",
            "fy": 2026,
            "filed": "2027-02-20",
        }
    )
    _us_gaap(payload)["PreferredStockValue"] = {"units": {"USD": [future]}}
    adapter = _adapter("KOH", payload)
    resolver = GrahamInputResolver(provider=adapter, clock=lambda: NOW)
    as_of = datetime(2026, 3, 1, tzinfo=UTC)
    request = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="KOH",
        field_name=FinancialField.BVPS,
        provider_id=SEC_PROVIDER_ID,
        as_of=as_of,
    )

    result = resolver.resolve_bvps(request)

    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
    assert result.resolved_input.as_of == as_of


def test_inferred_preferred_available_at_reflects_latest_neutral_evidence() -> None:
    """The inferred zero fact's available_at must be at least as late as the latest neutral evidence."""
    payload = _base_payload()
    _add_common_direct(payload, 103_300_000.0)
    # PreferredStockSharesAuthorized filed later than the main filing
    late_obs = _annual_observation(7_500_000.0)
    late_obs["filed"] = "2026-03-15"
    late_obs["accn"] = "0001-26-LATE"
    us_gaap = _us_gaap(payload)
    us_gaap["PreferredStockSharesAuthorized"] = {"units": {"shares": [late_obs]}}
    us_gaap["PreferredStockParOrStatedValuePerShare"] = {"units": {"USD/shares": [_annual_observation(0.002)]}}

    adapter = _adapter("HLF2", payload)
    preferred = adapter.fetch_facts(
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="HLF2",
            field_name=FinancialField.PREFERRED_SHARES_OUTSTANDING,
            provider_id=SEC_PROVIDER_ID,
            basis="fiscal_year_end",
            as_of=NOW,
        )
    )
    assert len(preferred) == 1
    # The inferred fact's available_at must be >= the late neutral observation's filed date
    # 2026-03-15T23:59:59 is the end of the filed date
    expected_late = datetime(2026, 3, 15, 23, 59, 59, tzinfo=UTC)
    assert preferred[0].available_at is not None
    assert preferred[0].available_at >= expected_late


def test_mismatched_equity_and_common_periods_cannot_infer_preferred() -> None:
    """When equity and common shares are from different reporting periods, no inference is made."""
    payload = _base_payload()
    # Common shares from a different period (2024-12-31)
    common_2024 = _annual_observation(103_300_000.0)
    common_2024["end"] = "2024-12-31"
    common_2024["fy"] = 2024
    _us_gaap(payload)["CommonStockSharesOutstanding"] = {"units": {"shares": [common_2024]}}

    adapter = _adapter("MIS", payload)
    preferred = adapter.fetch_facts(
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="MIS",
            field_name=FinancialField.PREFERRED_SHARES_OUTSTANDING,
            provider_id=SEC_PROVIDER_ID,
            basis="fiscal_year_end",
            as_of=NOW,
        )
    )
    assert len(preferred) == 0


def test_unrelated_concept_with_preferred_in_description_does_not_block_inference() -> None:
    """Descriptive text on an unrelated XBRL concept must not be mistaken for preferred-equity evidence.

    The concept NAME is 'RevenueFromContractWithCustomer' (no 'preferred'/'preference'),
    but its label/description metadata contains the word 'preferred'. The classifier
    must inspect only the concept name, not descriptive metadata.
    """
    payload = _base_payload()
    _us_gaap(payload)["StockholdersEquity"] = {"units": {"USD": [_annual_observation(32_169_000_000.0)]}}
    _add_common_issued_treasury(payload, issued=7_040_000_000.0, treasury=2_738_000_000.0)
    # Unrelated concept: name has NO "preferred"/"preference" substring,
    # but description/label metadata DOES.
    us_gaap = _us_gaap(payload)
    us_gaap["RevenueFromContractWithCustomer"] = {
        "label": "Revenue from contracts with customer, net of amounts billed to preferred customers",
        "description": "Represents revenue recognized under the preferred customer revenue program",
        "units": {"USD": [_annual_observation(1_000_000_000.0)]},
    }

    adapter = _adapter("KO", payload)

    # Common shares still resolve correctly
    common = adapter.fetch_facts(
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="KO",
            field_name=FinancialField.COMMON_SHARES_OUTSTANDING,
            provider_id=SEC_PROVIDER_ID,
            basis="fiscal_year_end",
            as_of=NOW,
        )
    )
    assert len(common) == 1
    assert common[0].value == 4_302_000_000

    # Preferred still infers zero (unrelated concept with "preferred" in description is ignored)
    preferred = adapter.fetch_facts(
        FinancialFactRequest(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id="KO",
            field_name=FinancialField.PREFERRED_SHARES_OUTSTANDING,
            provider_id=SEC_PROVIDER_ID,
            basis="fiscal_year_end",
            as_of=NOW,
        )
    )
    assert len(preferred) == 1
    assert preferred[0].value == 0
    assert preferred[0].provider_field == "inferred:sec-company-facts:no-issued-preferred-equity"

    # BVPS still resolves successfully end-to-end
    resolver = GrahamInputResolver(provider=adapter, clock=lambda: NOW)
    request = FinancialFactRequest(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id="KO",
        field_name=FinancialField.BVPS,
        provider_id=SEC_PROVIDER_ID,
    )
    result = resolver.resolve_bvps(request)
    assert result.status is CalculationStatus.OK
    assert result.resolved_input is not None
