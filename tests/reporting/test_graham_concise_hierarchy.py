"""Investor-hierarchy tests for concise Graham reports."""

from __future__ import annotations

from datetime import UTC, datetime

from src.analysis.graham_value.input_resolver import GrahamNumberInputAssembly, GrowthValueInputAssembly
from src.analysis.graham_value.models import GrahamGrowthValueResult, GrahamNumberResult
from src.core.analysis_status import CalculationStatus
from src.data.valuation.provenance import ResolvedInput, SourceKind
from src.reporting.graham import (
    GrahamGrowthPresentation,
    GrahamNumberPresentation,
    render_graham_growth,
    render_graham_number,
)

NOW = datetime(2026, 8, 24, 4, 30, tzinfo=UTC)
HISTORICAL = datetime(2025, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)


def _provider_input(  # noqa: PLR0913
    field_name: str,
    value: float,
    *,
    basis: str | None,
    units: str,
    currency: str | None,
    provider_id: str,
    provider_field: str,
    as_of: datetime | None = None,
) -> ResolvedInput:
    return ResolvedInput(
        field_name=field_name,
        value=value,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        basis=basis,
        units=units,
        currency=currency,
        provider_id=provider_id,
        provider_field=provider_field,
        as_of=as_of,
    )


def _override_input(
    field_name: str,
    value: float,
    *,
    as_of: datetime | None = None,
) -> ResolvedInput:
    return ResolvedInput(
        field_name=field_name,
        value=value,
        source_kind=SourceKind.OVERRIDE,
        resolved_at=NOW,
        units="percentage_points",
        as_of=as_of,
    )


def _number_presentation(*, as_of: datetime | None = None) -> GrahamNumberPresentation:
    eps = _provider_input(
        "eps",
        2.656667,
        basis="three_year_average",
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        provider_field="us-gaap:EarningsPerShareDiluted",
        as_of=as_of,
    )
    bvps = _provider_input(
        "bvps",
        7.477685,
        basis="fiscal_year_end",
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        provider_field="derived:stockholders_equity/common_shares_outstanding",
        as_of=as_of,
    )
    price = _provider_input(
        "current_price",
        91.10,
        basis=None,
        units="currency_per_share",
        currency="USD",
        provider_id="yfinance",
        provider_field="fast_info.last_price",
        as_of=as_of,
    )
    return GrahamNumberPresentation(
        ticker="KO",
        assembly=GrahamNumberInputAssembly(
            status=CalculationStatus.OK,
            eps=eps,
            bvps=bvps,
            current_price=price,
        ),
        result=GrahamNumberResult(
            status=CalculationStatus.OK,
            maximum_indicated_price=21.14,
        ),
        as_of=as_of,
        margin_of_safety_percent=-330.90,
    )


def test_number_success_leads_with_result_and_omits_success_metadata() -> None:
    rendered = render_graham_number(_number_presentation())
    lines = rendered.splitlines()

    assert lines[0] == "KO — Graham Number (maximum indicated price): 21.14 USD"
    assert lines[1] == "Current price: 91.10 USD"
    assert lines[2] == "Price relationship: 330.90% above the Graham Number"
    assert "Status: ok" not in rendered
    assert "As of: current" not in rendered
    assert "Basis: 3-year average diluted EPS + latest eligible fiscal-year-end BVPS" in rendered


def test_number_historical_boundary_is_material_in_result_heading() -> None:
    rendered = render_graham_number(_number_presentation(as_of=HISTORICAL))

    assert rendered.splitlines()[0] == ("KO — Graham Number (maximum indicated price) as of 2025-12-31: 21.14 USD")
    assert "As of:" not in rendered


def test_number_not_applicable_keeps_status_and_reason_prominent() -> None:
    eps = _provider_input(
        "eps",
        2.04,
        basis="three_year_average",
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        provider_field="us-gaap:EarningsPerShareDiluted",
    )
    bvps = _provider_input(
        "bvps",
        -4.986447,
        basis="fiscal_year_end",
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        provider_field="derived:stockholders_equity/common_shares_outstanding",
    )
    presentation = GrahamNumberPresentation(
        ticker="HLF",
        assembly=GrahamNumberInputAssembly(status=CalculationStatus.OK, eps=eps, bvps=bvps),
        result=GrahamNumberResult(
            status=CalculationStatus.NOT_APPLICABLE,
            reason="BVPS must be positive for Graham Number.",
        ),
    )

    lines = render_graham_number(presentation).splitlines()

    assert lines[0] == "HLF — Graham Number"
    assert lines[1] == "Status: not applicable"
    assert lines[2] == (
        "Reason: Book value per common share is negative (-4.99 USD), so the Graham Number does not apply."
    )


def test_growth_success_leads_with_value_then_forecast_assumption() -> None:
    eps = _provider_input(
        "eps",
        2.656667,
        basis="three_year_average",
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        provider_field="us-gaap:EarningsPerShareDiluted",
    )
    growth = _override_input("expected_growth", 5.0)
    aaa = _override_input("current_aaa_yield", 4.5)
    price = _provider_input(
        "current_price",
        91.10,
        basis=None,
        units="currency_per_share",
        currency="USD",
        provider_id="yfinance",
        provider_field="fast_info.last_price",
    )
    presentation = GrahamGrowthPresentation(
        ticker="KO",
        assembly=GrowthValueInputAssembly(
            status=CalculationStatus.OK,
            eps=eps,
            expected_growth=growth,
            current_aaa_yield=aaa,
            current_price=price,
        ),
        result=GrahamGrowthValueResult(status=CalculationStatus.OK, growth_value=48.06),
        base_pe=8.5,
        growth_multiplier=2.0,
        baseline_aaa_yield=4.4,
        margin_of_safety_percent=-89.55,
    )

    rendered = render_graham_growth(presentation)
    lines = rendered.splitlines()

    assert lines[0] == "KO — Graham Growth Value: 48.06 USD"
    assert lines[1] == "Expected growth assumption: 5.00 percentage points"
    assert lines[2] == "Current price: 91.10 USD"
    assert lines[3] == "Price relationship: 89.55% above the Graham growth value"
    assert "Status: ok" not in rendered
    assert "As of: current" not in rendered
    assert "Warning: AAA yield is user-supplied rather than provider-verified." in rendered
    assert "expected_growth is a user override" not in rendered
