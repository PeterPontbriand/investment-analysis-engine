"""Focused tests for the concise Graham Number input-basis explanation."""

from datetime import UTC, datetime

from src.analysis.graham_value.input_resolver import GrahamNumberInputAssembly
from src.analysis.graham_value.models import GrahamNumberResult
from src.core.analysis_status import CalculationStatus
from src.data.financial.provenance import ComponentLineage, ResolvedInput, SourceKind
from src.reporting.graham import GrahamNumberPresentation, render_graham_number

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)


def _provider_input(field_name: str, value: float, *, basis: str, provider_field: str) -> ResolvedInput:
    return ResolvedInput(
        field_name=field_name,
        value=value,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        basis=basis,
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        provider_field=provider_field,
    )


def test_number_concise_explains_normalized_eps_and_period_end_bvps_basis() -> None:
    eps_component = _provider_input(
        "eps",
        2.47,
        basis="fiscal_year",
        provider_field="us-gaap:EarningsPerShareDiluted",
    )
    eps = ResolvedInput(
        field_name="eps",
        value=2.656667,
        source_kind=SourceKind.DERIVED,
        resolved_at=NOW,
        basis="three_year_average",
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        lineage=ComponentLineage(transformation="arithmetic_mean", components=(eps_component,)),
    )
    bvps_component = _provider_input(
        "book_value_component",
        7.477685,
        basis="fiscal_year_end",
        provider_field="derived:book_value_component",
    )
    bvps = ResolvedInput(
        field_name="bvps",
        value=7.477685,
        source_kind=SourceKind.DERIVED,
        resolved_at=NOW,
        basis="fiscal_year_end",
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        lineage=ComponentLineage(transformation="book_value_per_common_share", components=(bvps_component,)),
    )
    presentation = GrahamNumberPresentation(
        ticker="KO",
        assembly=GrahamNumberInputAssembly(status=CalculationStatus.OK, eps=eps, bvps=bvps),
        result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=21.14),
    )

    rendered = render_graham_number(presentation)

    assert "Basis: 3-year average diluted EPS + latest eligible fiscal-year-end BVPS" in rendered
