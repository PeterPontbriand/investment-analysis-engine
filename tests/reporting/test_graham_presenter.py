"""Semantic tests for investor-facing Graham presentation."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from src.analysis.graham_value.models import (
    CalculationStatus,
    GrahamGrowthValueResult,
    GrahamNumberResult,
)
from src.analysis.graham_value.provenance import ComponentLineage, ResolvedInput, SourceKind
from src.analysis.graham_value.resolution_trace import (
    ResolutionEvent,
    ResolutionOutcome,
    ResolutionStage,
    ResolutionTrace,
)
from src.analysis.graham_value.resolver import (
    GrahamNumberInputAssembly,
    GrowthValueInputAssembly,
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

    assert "Maximum indicated price" in rendered
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

    assert "USER ASSUMPTION — expected growth" in rendered
    assert "user override, not provider-verified data" in rendered
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

    assert f"As of: {historical_as_of.isoformat()}" in render_graham_growth(presentation)


def test_graham_presentation_rejects_naive_as_of() -> None:
    assembly = GrahamNumberInputAssembly(status=CalculationStatus.OK, eps=_eps(), bvps=_derived_bvps())

    with pytest.raises(ValueError, match="timezone-aware"):
        GrahamNumberPresentation(
            ticker="NDAQ",
            assembly=assembly,
            result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=33.8004677786747),
            as_of=datetime(2026, 8, 22),
        )
