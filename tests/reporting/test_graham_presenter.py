"""Semantic tests for investor-facing Graham presentation."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from src.analysis.graham_value.input_resolver import GrahamNumberInputAssembly, GrowthValueInputAssembly
from src.analysis.graham_value.models import GrahamGrowthValueResult, GrahamNumberResult
from src.core.analysis_status import CalculationStatus
from src.data.valuation.provenance import ComponentLineage, ResolvedInput, SourceKind
from src.data.valuation.resolution_trace import (
    ResolutionEvent,
    ResolutionOutcome,
    ResolutionStage,
    ResolutionTrace,
)
from src.reporting.graham import (
    GrahamGrowthPresentation,
    GrahamNumberPresentation,
    render_graham_growth,
    render_graham_number,
)
from src.reporting.presentation import PresentationMode

NOW = datetime(2026, 8, 22, 4, 0, tzinfo=UTC)
AVAILABLE = datetime(2026, 2, 12, 21, 29, 7, tzinfo=UTC)


def _provider_input(
    field_name: str,
    value: float,
    *,
    units: str,
    currency: str | None,
    provider_field: str,
) -> ResolvedInput:
    return ResolvedInput(
        field_name=field_name,
        value=value,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        basis="fiscal_year_end",
        units=units,
        currency=currency,
        provider_id="sec_edgar",
        provider_field=provider_field,
        observation_period_end=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC),
        available_at=AVAILABLE,
        retrieved_at=NOW,
    )


def _derived_bvps() -> ResolvedInput:
    equity = _provider_input(
        "stockholders_equity",
        12_227_000_000.0,
        units="currency",
        currency="USD",
        provider_field="us-gaap:StockholdersEquity",
    )
    preferred = _provider_input(
        "preferred_shares_outstanding",
        0.0,
        units="shares",
        currency=None,
        provider_field="us-gaap:PreferredStockSharesOutstanding",
    )
    common = _provider_input(
        "common_shares_outstanding",
        569_894_024.0,
        units="shares",
        currency=None,
        provider_field="us-gaap:CommonStockSharesOutstanding",
    )
    return ResolvedInput(
        field_name="bvps",
        value=21.454866141919748,
        source_kind=SourceKind.DERIVED,
        resolved_at=NOW,
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        observation_period_end=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC),
        available_at=AVAILABLE,
        retrieved_at=NOW,
        lineage=ComponentLineage(
            transformation=("stockholders_equity / common_shares_outstanding; preferred_shares_outstanding == 0 guard"),
            components=(equity, preferred, common),
        ),
    )


def _eps() -> ResolvedInput:
    component = ResolvedInput(
        field_name="eps",
        value=2.08,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        basis="fiscal_year",
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        provider_field="us-gaap:EarningsPerShareDiluted",
        observation_period_end=datetime(2023, 12, 31, 23, 59, 59, tzinfo=UTC),
        available_at=AVAILABLE,
        retrieved_at=NOW,
    )
    return ResolvedInput(
        field_name="eps",
        value=2.3666666666666667,
        source_kind=SourceKind.DERIVED,
        resolved_at=NOW,
        basis="three_year_average",
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        available_at=AVAILABLE,
        retrieved_at=NOW,
        lineage=ComponentLineage(
            transformation="arithmetic_mean",
            components=(component,),
        ),
    )


def test_number_concise_uses_screening_ceiling_language_and_not_intrinsic_value() -> None:
    assembly = GrahamNumberInputAssembly(
        status=CalculationStatus.OK,
        eps=_eps(),
        bvps=_derived_bvps(),
        quote_status=CalculationStatus.INPUT_UNAVAILABLE,
        quote_reason="Provider returned no data for the requested field.",
    )
    presentation = GrahamNumberPresentation(
        ticker="NDAQ",
        assembly=assembly,
        result=GrahamNumberResult(
            status=CalculationStatus.OK,
            maximum_indicated_price=33.8004677786747,
        ),
    )

    rendered = render_graham_number(presentation)

    assert "NDAQ — Graham Number (maximum indicated price): 33.80 USD" in rendered
    assert "screening ceiling" in rendered
    assert "Intrinsic Value" not in rendered
    assert "Current price: unavailable" in rendered
    assert "quote unavailable" in rendered.lower()


def test_number_details_expose_provider_fields_and_derivation_lineage() -> None:
    assembly = GrahamNumberInputAssembly(
        status=CalculationStatus.OK,
        eps=_eps(),
        bvps=_derived_bvps(),
    )
    presentation = GrahamNumberPresentation(
        ticker="NDAQ",
        assembly=assembly,
        result=GrahamNumberResult(
            status=CalculationStatus.OK,
            maximum_indicated_price=33.8004677786747,
        ),
    )

    rendered = render_graham_number(presentation, PresentationMode.DETAILS)

    assert "provider field: us-gaap:StockholdersEquity" in rendered
    assert "preferred_shares_outstanding == 0 guard" in rendered
    assert "available at:" in rendered


def test_number_json_preserves_typed_provenance() -> None:
    assembly = GrahamNumberInputAssembly(
        status=CalculationStatus.OK,
        eps=_eps(),
        bvps=_derived_bvps(),
    )
    presentation = GrahamNumberPresentation(
        ticker="NDAQ",
        assembly=assembly,
        result=GrahamNumberResult(
            status=CalculationStatus.OK,
            maximum_indicated_price=33.8004677786747,
        ),
    )

    payload = json.loads(render_graham_number(presentation, PresentationMode.JSON))

    assert payload["schema_version"] == 1
    assert payload["method"] == "graham_number"
    assert payload["result"]["maximum_indicated_price"] == pytest.approx(33.8004677786747)
    assert payload["inputs"]["bvps"]["source_kind"] == "derived"
    components = payload["inputs"]["bvps"]["lineage"]["components"]
    assert components[1]["provider_field"] == "us-gaap:PreferredStockSharesOutstanding"


def test_growth_concise_makes_user_growth_assumption_conspicuous() -> None:
    growth = ResolvedInput(
        field_name="expected_growth",
        value=6.5,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=NOW,
        units="percentage_points",
    )
    aaa = ResolvedInput(
        field_name="current_aaa_yield",
        value=5.25,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        units="percentage_points",
        provider_id="fixture_macro",
        provider_field="AAA",
        available_at=NOW,
        retrieved_at=NOW,
    )
    assembly = GrowthValueInputAssembly(
        status=CalculationStatus.OK,
        eps=_eps(),
        expected_growth=growth,
        current_aaa_yield=aaa,
    )
    presentation = GrahamGrowthPresentation(
        ticker="NDAQ",
        assembly=assembly,
        result=GrahamGrowthValueResult(
            status=CalculationStatus.OK,
            growth_value=40.0,
        ),
        base_pe=8.5,
        growth_multiplier=2.0,
        baseline_aaa_yield=4.4,
    )

    rendered = render_graham_growth(presentation)

    assert "Expected growth assumption: 6.50 percentage points" in rendered
    assert "expected_growth is a user override" not in rendered
    assert "Warning:" not in rendered
    assert "forecast-dependent" in rendered.lower()


def test_diagnostics_do_not_invent_unretained_cache_or_provider_attempts() -> None:
    assembly = GrahamNumberInputAssembly(
        status=CalculationStatus.INPUT_UNAVAILABLE,
        reason="bvps: provider returned no data",
        eps=_eps(),
    )
    presentation = GrahamNumberPresentation(
        ticker="AAPL",
        assembly=assembly,
        result=None,
    )

    rendered = render_graham_number(presentation, PresentationMode.DIAGNOSTICS)

    assert "will not infer cache or provider behavior" in rendered
    assert "cache -> miss" not in rendered.lower()


def test_diagnostics_render_recorded_resolver_trace_without_reconstruction() -> None:
    trace = ResolutionTrace(
        events=(
            ResolutionEvent(
                field_name="bvps",
                stage=ResolutionStage.OVERRIDE,
                outcome=ResolutionOutcome.NOT_USED,
                message="No explicit override was supplied.",
            ),
            ResolutionEvent(
                field_name="bvps",
                stage=ResolutionStage.CACHE,
                outcome=ResolutionOutcome.MISS,
                message="Cache returned no usable entry.",
            ),
            ResolutionEvent(
                field_name="bvps",
                stage=ResolutionStage.PROVIDER,
                outcome=ResolutionOutcome.UNAVAILABLE,
                message="Provider returned no data for the requested field.",
            ),
            ResolutionEvent(
                field_name="bvps",
                stage=ResolutionStage.DERIVATION,
                outcome=ResolutionOutcome.SUCCESS,
                message="Derived BVPS from compatible components.",
            ),
        )
    )
    assembly = GrahamNumberInputAssembly(
        status=CalculationStatus.OK,
        eps=_eps(),
        bvps=_derived_bvps(),
        resolution_trace=trace,
    )
    presentation = GrahamNumberPresentation(
        ticker="NDAQ",
        assembly=assembly,
        result=GrahamNumberResult(
            status=CalculationStatus.OK,
            maximum_indicated_price=33.8004677786747,
        ),
    )

    rendered = render_graham_number(presentation, PresentationMode.DIAGNOSTICS)

    assert "bvps: cache -> miss — Cache returned no usable entry." in rendered
    assert "bvps: provider -> unavailable" in rendered
    assert "bvps: derivation -> success" in rendered


def test_number_presentation_rejects_as_of_mismatch_with_resolved_input() -> None:
    historical_as_of = datetime(2025, 12, 31, tzinfo=UTC)
    eps = ResolvedInput(
        field_name="eps",
        value=2.0,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=NOW,
        basis="ttm",
        units="currency_per_share",
        as_of=historical_as_of,
    )
    bvps = ResolvedInput(
        field_name="bvps",
        value=10.0,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=NOW,
        units="currency_per_share",
        as_of=historical_as_of,
    )
    assembly = GrahamNumberInputAssembly(status=CalculationStatus.OK, eps=eps, bvps=bvps)

    with pytest.raises(ValueError, match="Presentation as_of"):
        GrahamNumberPresentation(
            ticker="SYNTH",
            assembly=assembly,
            result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=21.213203435596427),
            as_of=None,
        )


def test_growth_presentation_accepts_matching_historical_as_of() -> None:
    historical_as_of = datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)
    eps = ResolvedInput(
        field_name="eps",
        value=2.0,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=NOW,
        basis="ttm",
        units="currency_per_share",
        as_of=historical_as_of,
    )
    growth = ResolvedInput(
        field_name="expected_growth",
        value=5.0,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=NOW,
        units="percentage_points",
        as_of=historical_as_of,
    )
    aaa = ResolvedInput(
        field_name="current_aaa_yield",
        value=5.25,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=NOW,
        units="percentage_points",
        as_of=historical_as_of,
    )
    assembly = GrowthValueInputAssembly(
        status=CalculationStatus.OK,
        eps=eps,
        expected_growth=growth,
        current_aaa_yield=aaa,
    )
    presentation = GrahamGrowthPresentation(
        ticker="SYNTH",
        assembly=assembly,
        result=GrahamGrowthValueResult(status=CalculationStatus.OK, growth_value=31.00952380952381),
        base_pe=8.5,
        growth_multiplier=2.0,
        baseline_aaa_yield=4.4,
        as_of=historical_as_of,
    )

    rendered = render_graham_growth(presentation)
    assert "SYNTH — Graham Growth Value as of 2025-12-31: 31.01 (currency unspecified)" in rendered
    assert "As of:" not in rendered


def test_graham_presentation_rejects_naive_as_of() -> None:
    assembly = GrahamNumberInputAssembly(status=CalculationStatus.OK, eps=_eps(), bvps=_derived_bvps())

    with pytest.raises(ValueError, match="timezone-aware"):
        GrahamNumberPresentation(
            ticker="NDAQ",
            assembly=assembly,
            result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=33.8004677786747),
            as_of=datetime(2026, 8, 22),
        )


def test_number_not_applicable_is_humanized_and_suppresses_quote_noise() -> None:
    bvps = replace(
        _derived_bvps(),
        value=-4.986447241045498,
        observation_period_end=datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=UTC),
    )
    assembly = GrahamNumberInputAssembly(
        status=CalculationStatus.OK,
        eps=_eps(),
        bvps=bvps,
        quote_status=CalculationStatus.INPUT_UNAVAILABLE,
        quote_reason="technical quote reason",
    )
    presentation = GrahamNumberPresentation(
        ticker="HLF",
        assembly=assembly,
        result=GrahamNumberResult(
            status=CalculationStatus.NOT_APPLICABLE,
            reason="BVPS must be positive for Graham Number (received -4.986447241045498).",
        ),
    )
    rendered = render_graham_number(presentation)
    assert "Status: not applicable" in rendered
    assert "Book value per common share is negative (-4.99 USD), so the Graham Number does not apply." in rendered
    assert "-4.986447241045498" not in rendered
    assert "Current quote unavailable" not in rendered


def test_number_details_use_human_dates_and_omit_operational_timestamps() -> None:
    presentation = GrahamNumberPresentation(
        ticker="NDAQ",
        assembly=GrahamNumberInputAssembly(status=CalculationStatus.OK, eps=_eps(), bvps=_derived_bvps()),
        result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=33.8),
    )
    rendered = render_graham_number(presentation, PresentationMode.DETAILS)
    assert "basis: fiscal-year-end" in rendered
    assert "period end: 2025-12-31" in rendered
    assert "available at: 2026-02-12 21:29 UTC" in rendered
    assert "retrieved at:" not in rendered
    assert "resolved at:" not in rendered
    assert "T23:59:59" not in rendered
    assert ".999999" not in rendered


def test_provider_side_inference_and_derivation_have_explicit_source_labels() -> None:
    preferred = _provider_input(
        "preferred_shares_outstanding",
        0.0,
        units="shares",
        currency=None,
        provider_field="inferred:sec-company-facts:no-issued-preferred-equity",
    )
    common = _provider_input(
        "common_shares_outstanding",
        4_302_000_000.0,
        units="shares",
        currency=None,
        provider_field="derived:us-gaap:CommonStockSharesIssued-us-gaap:TreasuryStockCommonShares",
    )
    bvps = ResolvedInput(
        field_name="bvps",
        value=7.48,
        source_kind=SourceKind.DERIVED,
        resolved_at=NOW,
        basis="fiscal_year_end",
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        available_at=AVAILABLE,
        retrieved_at=NOW,
        lineage=ComponentLineage(transformation="test", components=(preferred, common)),
    )
    presentation = GrahamNumberPresentation(
        ticker="KO",
        assembly=GrahamNumberInputAssembly(status=CalculationStatus.OK, eps=_eps(), bvps=bvps),
        result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=21.14),
    )
    rendered = render_graham_number(presentation, PresentationMode.DETAILS)
    assert "source: inferred (SEC EDGAR)" in rendered
    assert "source: provider-derived (SEC EDGAR)" in rendered


def test_concise_freshness_uses_semantic_dates() -> None:
    presentation = GrahamNumberPresentation(
        ticker="KO",
        assembly=GrahamNumberInputAssembly(status=CalculationStatus.OK, eps=_eps(), bvps=_derived_bvps()),
        result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=21.14),
    )
    rendered = render_graham_number(presentation)
    assert "(available 2026-02-12)" in rendered
    assert "2026-02-12T21:29:07" not in rendered


def test_cross_currency_quote_is_shown_without_price_relationship() -> None:
    quote = ResolvedInput(
        field_name="current_price",
        value=50.0,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        units="currency_per_share",
        currency="CAD",
        provider_id="yfinance",
        provider_field="fast_info.last_price",
        observed_at=NOW,
        available_at=NOW,
        retrieved_at=NOW,
    )
    presentation = GrahamNumberPresentation(
        ticker="TEST",
        assembly=GrahamNumberInputAssembly(
            status=CalculationStatus.OK,
            eps=_eps(),
            bvps=_derived_bvps(),
            current_price=quote,
        ),
        result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=33.8),
        margin_of_safety_percent=None,
    )
    rendered = render_graham_number(presentation)
    assert "Current price: 50.00 CAD" in rendered
    assert "Price comparison: unavailable (valuation and quote currencies differ)" in rendered
    assert "Price relationship:" not in rendered


def test_not_applicable_json_preserves_raw_status_value_and_precision() -> None:
    bvps_value = -4.986447241045498
    available = datetime(2026, 2, 18, 21, 23, 3, 123456, tzinfo=UTC)
    bvps = replace(
        _derived_bvps(),
        value=bvps_value,
        available_at=available,
    )
    presentation = GrahamNumberPresentation(
        ticker="HLF",
        assembly=GrahamNumberInputAssembly(status=CalculationStatus.OK, eps=_eps(), bvps=bvps),
        result=GrahamNumberResult(
            status=CalculationStatus.NOT_APPLICABLE,
            reason=f"BVPS must be positive for Graham Number (received {bvps_value}).",
        ),
    )
    payload = json.loads(render_graham_number(presentation, PresentationMode.JSON))
    assert payload["status"] == "not_applicable"
    assert payload["inputs"]["bvps"]["value"] == pytest.approx(bvps_value)
    assert payload["inputs"]["bvps"]["available_at"] == available.isoformat()
