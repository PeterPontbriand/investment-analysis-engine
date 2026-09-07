"""Deterministic strategy regressions for provider-backed instrument applicability."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.analysis.strategy.fcf_earnings_growth import FCFEarningsGrowthAnalyzer, FCFEarningsGrowthPolicy
from src.analysis.strategy.graham_growth.calculation import GrahamGrowthCalculationPolicy
from src.analysis.strategy.graham_growth.service import run_graham_growth_analysis
from src.analysis.strategy.graham_number.calculation import GrahamNumberInputAssembly
from src.analysis.strategy.graham_number.service import run_graham_number_analysis
from src.core.analysis_status import CalculationStatus
from src.core.metric_result import MetricStatus, ReasonCode
from src.data.instrument_profile import (
    InstrumentKind,
    InstrumentKindEvidence,
    InstrumentProfile,
    InstrumentProfileCapability,
    InstrumentProfileDiagnostic,
    InstrumentProfileResolutionStatus,
)
from src.data.security_identity import SecurityIdentity

NOW = datetime(2026, 8, 30, 18, 0, tzinfo=UTC)


def _profile(kind: InstrumentKind | None, provider_value: str) -> InstrumentProfile:
    """Build one deterministic profile with independent identity/kind provenance."""
    identity = SecurityIdentity(
        ticker="FLSW",
        provider_id="sec_edgar",
        resolved_at=NOW,
        instrument_name="Franklin FTSE Switzerland ETF",
    )
    evidence = InstrumentKindEvidence(
        ticker="FLSW",
        kind=kind,
        provider_value=provider_value,
        provider_id="yfinance",
        resolved_at=NOW,
    )
    return InstrumentProfile(
        ticker="FLSW",
        identity=identity,
        kind_evidence=evidence,
        diagnostics=(
            InstrumentProfileDiagnostic(
                InstrumentProfileCapability.SECURITY_IDENTITY,
                "sec_edgar",
                InstrumentProfileResolutionStatus.RESOLVED,
                "Resolved fixture identity.",
            ),
            InstrumentProfileDiagnostic(
                InstrumentProfileCapability.INSTRUMENT_KIND,
                "yfinance",
                InstrumentProfileResolutionStatus.RESOLVED,
                "Resolved fixture kind.",
            ),
        ),
    )


def _profile_without_kind(status: InstrumentProfileResolutionStatus) -> InstrumentProfile:
    """Build a profile whose optional kind lookup did not produce evidence."""
    return InstrumentProfile(
        ticker="FLSW",
        identity=SecurityIdentity(
            ticker="FLSW",
            provider_id="sec_edgar",
            resolved_at=NOW,
            instrument_name="Franklin FTSE Switzerland ETF",
        ),
        kind_evidence=None,
        diagnostics=(
            InstrumentProfileDiagnostic(
                InstrumentProfileCapability.INSTRUMENT_KIND,
                "yfinance",
                status,
                "Fixture kind metadata was not resolved.",
            ),
        ),
    )


def test_known_etf_short_circuits_both_graham_methods_before_input_or_quote_resolution() -> None:
    resolver = MagicMock()
    profile = _profile(InstrumentKind.ETF, "ETF")

    number = run_graham_number_analysis(
        resolver=resolver,
        ticker="FLSW",
        security_provider_id="sec_edgar",
        quote_provider_id="yfinance",
        eps_basis="three_year_average",
        eps_override=None,
        bvps_override=None,
        quote_override=None,
        as_of=None,
        use_cache=True,
        instrument_profile=profile,
    )
    growth = run_graham_growth_analysis(
        resolver=resolver,
        ticker="FLSW",
        security_provider_id="sec_edgar",
        quote_provider_id="yfinance",
        eps_basis="three_year_average",
        eps_override=None,
        expected_growth=5.0,
        aaa_yield_override=4.4,
        quote_override=None,
        as_of=None,
        use_cache=True,
        policy=GrahamGrowthCalculationPolicy(8.5, 2.0, 4.4),
        instrument_profile=profile,
    )

    assert number.result.status is CalculationStatus.NOT_APPLICABLE
    assert growth.result.status is CalculationStatus.NOT_APPLICABLE
    assert number.assembly.current_price is None
    assert growth.assembly.current_price is None
    assert "company-level" in (number.result.reason or "")
    assert "aggregate ETF valuation" in (growth.result.reason or "")
    resolver.assemble_graham_number.assert_not_called()
    resolver.assemble_growth_value.assert_not_called()


def test_known_etf_short_circuits_company_fcf_before_annual_fact_resolution() -> None:
    resolver = MagicMock()
    profile = _profile(InstrumentKind.ETF, "ETF")

    result = FCFEarningsGrowthAnalyzer(resolver).run_analysis(
        ticker="FLSW",
        policy=FCFEarningsGrowthPolicy(),
        currency="USD",
        as_of=None,
        provider_id="sec_edgar",
        effective_as_of=NOW,
        instrument_profile=profile,
    )

    assert result.execution_status is CalculationStatus.NOT_APPLICABLE
    assert result.classification.value == "indeterminate"
    assert result.classification_reason_code is ReasonCode.INSTRUMENT_KIND_NOT_APPLICABLE
    assert result.annual_observations == ()
    assert result.fcf_cagr.status is MetricStatus.NOT_APPLICABLE
    assert result.fcf_per_share_cagr.status is MetricStatus.NOT_APPLICABLE
    assert result.eps_cagr.status is MetricStatus.NOT_APPLICABLE
    assert result.schema_version == 3
    resolver.resolve.assert_not_called()


def test_unreviewed_kind_fails_open_to_existing_graham_resolution() -> None:
    resolver = MagicMock()
    resolver.assemble_graham_number.return_value = GrahamNumberInputAssembly(
        status=CalculationStatus.INPUT_UNAVAILABLE,
        reason="Fixture facts are unavailable.",
    )
    profile = _profile(None, "MUTUALFUND")

    result = run_graham_number_analysis(
        resolver=resolver,
        ticker="FLSW",
        security_provider_id="sec_edgar",
        quote_provider_id="yfinance",
        eps_basis="three_year_average",
        eps_override=None,
        bvps_override=None,
        quote_override=None,
        as_of=None,
        use_cache=True,
        instrument_profile=profile,
    )

    assert result.result.status is CalculationStatus.INPUT_UNAVAILABLE
    resolver.assemble_graham_number.assert_called_once()


def test_known_equity_continues_existing_graham_resolution() -> None:
    resolver = MagicMock()
    resolver.assemble_graham_number.return_value = GrahamNumberInputAssembly(
        status=CalculationStatus.INPUT_UNAVAILABLE,
        reason="Fixture facts are unavailable.",
    )

    result = run_graham_number_analysis(
        resolver=resolver,
        ticker="FLSW",
        security_provider_id="sec_edgar",
        quote_provider_id="yfinance",
        eps_basis="three_year_average",
        eps_override=None,
        bvps_override=None,
        quote_override=None,
        as_of=None,
        use_cache=True,
        instrument_profile=_profile(InstrumentKind.EQUITY, "EQUITY"),
    )

    assert result.result.status is CalculationStatus.INPUT_UNAVAILABLE
    resolver.assemble_graham_number.assert_called_once()


def test_kind_provider_error_fails_open_to_existing_graham_resolution() -> None:
    resolver = MagicMock()
    resolver.assemble_graham_number.return_value = GrahamNumberInputAssembly(
        status=CalculationStatus.INPUT_UNAVAILABLE,
        reason="Fixture facts are unavailable.",
    )

    result = run_graham_number_analysis(
        resolver=resolver,
        ticker="FLSW",
        security_provider_id="sec_edgar",
        quote_provider_id="yfinance",
        eps_basis="three_year_average",
        eps_override=None,
        bvps_override=None,
        quote_override=None,
        as_of=None,
        use_cache=True,
        instrument_profile=_profile_without_kind(InstrumentProfileResolutionStatus.PROVIDER_ERROR),
    )

    assert result.result.status is CalculationStatus.INPUT_UNAVAILABLE
    resolver.assemble_graham_number.assert_called_once()


@pytest.mark.parametrize("known_etf", [False, True])
def test_fcf_profile_mismatch_precedes_applicability_and_resolution(known_etf: bool) -> None:
    resolver = MagicMock()
    profile = _profile(InstrumentKind.ETF, "ETF") if known_etf else _profile(None, "MUTUALFUND")
    with pytest.raises(ValueError, match="Instrument profile ticker does not match") as error:
        FCFEarningsGrowthAnalyzer(resolver).run_analysis(
            ticker="OTHER",
            policy=FCFEarningsGrowthPolicy(),
            currency="USD",
            as_of=NOW,
            provider_id="sec_edgar",
            effective_as_of=NOW,
            instrument_profile=profile,
        )
    assert str(error.value) == "Instrument profile ticker does not match the FCF & Earnings Growth analysis ticker."
    resolver.resolve.assert_not_called()


@pytest.mark.parametrize("include_yield", [False, True])
def test_fcf_etf_result_retains_caller_owned_messages_and_boundaries(include_yield: bool) -> None:
    resolver = MagicMock()
    profile = _profile(InstrumentKind.ETF, "ETF")
    result = FCFEarningsGrowthAnalyzer(resolver).run_analysis(
        ticker=" flsw ",
        policy=FCFEarningsGrowthPolicy(include_fcf_yield=include_yield),
        currency="USD",
        as_of=NOW,
        provider_id="sec_edgar",
        effective_as_of=NOW,
        instrument_profile=profile,
    )
    reason = (
        "Reported company free-cash-flow and diluted-EPS growth analysis does not apply directly to an ETF. "
        "No holdings-level or aggregate ETF analysis was performed."
    )
    assert result.classification_reason == reason
    assert result.instrument_profile is profile
    assert result.ticker == "FLSW"
    assert result.requested_as_of == result.effective_as_of == NOW
    assert result.market_capitalization is None
    assert result.warnings == ()
    assert result.forward_evidence.actual_to_fy1_growth.reason == reason
    assert result.fcf_yield.reason == (reason if include_yield else "FCF yield was not requested.")
    assert result.fcf_yield.status is MetricStatus.NOT_APPLICABLE
    resolver.resolve.assert_not_called()
