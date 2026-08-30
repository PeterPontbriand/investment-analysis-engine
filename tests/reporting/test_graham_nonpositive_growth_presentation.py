"""Regression coverage for non-positive Graham Growth Value presentation."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from src.analysis.graham_value.input_resolver import GrowthValueInputAssembly
from src.analysis.graham_value.models import GrahamGrowthValueResult
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import ResolvedInput, SourceKind
from src.reporting.graham import GrahamGrowthPresentation, render_graham_growth
from src.reporting.presentation import PresentationMode

NOW = datetime(2026, 8, 25, 3, 0, tzinfo=UTC)
WARNING = "The Graham growth value is non-positive; percentage price comparison is omitted."


def _presentation() -> GrahamGrowthPresentation:
    eps = ResolvedInput(
        field_name="eps",
        value=-1.4366666666666668,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        basis="three_year_average",
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        provider_field="us-gaap:EarningsPerShareDiluted",
        available_at=NOW,
        retrieved_at=NOW,
    )
    growth = ResolvedInput(
        field_name="expected_growth",
        value=12.5,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=NOW,
        units="percentage_points",
    )
    aaa_yield = ResolvedInput(
        field_name="current_aaa_yield",
        value=6.73,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=NOW,
        units="percentage_points",
    )
    current_price = ResolvedInput(
        field_name="current_price",
        value=2.15,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        units="currency_per_share",
        currency="USD",
        provider_id="yfinance",
        provider_field="fast_info.last_price",
        observed_at=NOW,
        available_at=NOW,
        retrieved_at=NOW,
    )
    assembly = GrowthValueInputAssembly(
        status=CalculationStatus.OK,
        eps=eps,
        expected_growth=growth,
        current_aaa_yield=aaa_yield,
        current_price=current_price,
    )
    return GrahamGrowthPresentation(
        ticker="HURA",
        assembly=assembly,
        result=GrahamGrowthValueResult(
            status=CalculationStatus.OK,
            growth_value=-31.465775136206044,
        ),
        base_pe=8.5,
        growth_multiplier=2.0,
        baseline_aaa_yield=4.4,
    )


def test_non_positive_growth_value_explains_omitted_price_comparison() -> None:
    rendered = render_graham_growth(_presentation())

    assert "HURA — Graham Growth Value: -31.47 USD" in rendered
    assert "Current price: 2.15 USD" in rendered
    assert "Price comparison: unavailable (Graham growth value is non-positive)" in rendered
    assert f"Warning: {WARNING}" in rendered


def test_non_positive_growth_value_warning_is_preserved_in_json() -> None:
    payload = json.loads(render_graham_growth(_presentation(), PresentationMode.JSON))

    assert payload["schema_version"] == 2
    assert payload["status"] == "ok"
    assert payload["result"]["growth_value"] == pytest.approx(-31.465775136206044)
    assert payload["result"]["margin_of_safety_percent"] is None
    assert WARNING in payload["warnings"]
