"""Regression tests for explicit display-label rendering in investor-facing output.

These tests verify that internal machine identifiers are rendered through
approved human-readable labels rather than leaking raw snake_case values
into concise or details prose.

Note: exact technical provenance identifiers (e.g. ``us-gaap:EarningsPerShareDiluted``)
may intentionally remain in Details mode for auditability; diagnostics retains
raw resolver tokens by design.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from src.analysis.graham_value.input_resolver import GrahamNumberInputAssembly
from src.analysis.graham_value.models import GrahamNumberResult
from src.analysis.momentum.momentum_analyzer import MomentumConfig, MomentumMetrics
from src.core.analysis_status import CalculationStatus
from src.core.constants import TrendStatus
from src.data.financial.provenance import ComponentLineage, ResolvedInput, SourceKind
from src.data.financial.resolution_trace import ResolutionEvent, ResolutionOutcome, ResolutionStage, ResolutionTrace
from src.data.market_data import MarketDataContext
from src.reporting.graham import (
    BASIS_DISPLAY_NAMES,
    FIELD_DISPLAY_NAMES,
    UNITS_DISPLAY_NAMES,
    GrahamNumberPresentation,
    basis_display_name,
    field_display_name,
    render_graham_number,
    units_display_name,
)
from src.reporting.momentum import MomentumPresentation, render_momentum
from src.reporting.presentation import PROVIDER_DISPLAY_NAMES, PresentationMode, provider_display_name

NOW = datetime(2026, 8, 24, 4, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Unit tests for explicit mapping functions
# ---------------------------------------------------------------------------


def test_provider_display_name_sec_edgar() -> None:
    assert provider_display_name("sec_edgar") == "SEC EDGAR"


def test_provider_display_name_yfinance() -> None:
    assert provider_display_name("yfinance") == "Yahoo Finance"


def test_provider_display_name_massive() -> None:
    assert provider_display_name("massive") == "Massive"


def test_provider_display_name_unknown_falls_through() -> None:
    assert provider_display_name("fixture_market_data") == "fixture_market_data"


def test_provider_display_name_none() -> None:
    assert provider_display_name(None) == "unavailable"


def test_basis_display_name_three_year_average() -> None:
    assert basis_display_name("three_year_average") == "3-year average"


def test_basis_display_name_ttm() -> None:
    assert basis_display_name("ttm") == "TTM"


def test_basis_display_name_fiscal_year_end() -> None:
    assert basis_display_name("fiscal_year_end") == "fiscal-year-end"


def test_basis_display_name_fiscal_year() -> None:
    assert basis_display_name("fiscal_year") == "fiscal year"


def test_basis_display_name_unknown_falls_through() -> None:
    assert basis_display_name("quarterly_rolling") == "quarterly_rolling"


def test_basis_display_name_none() -> None:
    assert basis_display_name(None) == "unavailable"


def test_field_display_name_eps() -> None:
    assert field_display_name("eps") == "EPS"


def test_field_display_name_bvps() -> None:
    assert field_display_name("bvps") == "BVPS"


def test_field_display_name_current_price() -> None:
    assert field_display_name("current_price") == "Current price"


def test_field_display_name_current_aaa_yield() -> None:
    assert field_display_name("current_aaa_yield") == "Current AAA yield"


def test_field_display_name_expected_growth() -> None:
    assert field_display_name("expected_growth") == "Expected growth"


def test_field_display_name_unknown_falls_through() -> None:
    assert field_display_name("some_unknown_field") == "some_unknown_field"


def test_units_display_name_currency_per_share() -> None:
    assert units_display_name("currency_per_share") == "currency per share"


def test_units_display_name_percentage_points() -> None:
    assert units_display_name("percentage_points") == "percentage points"


def test_units_display_name_ratio() -> None:
    assert units_display_name("ratio") == "ratio"


def test_units_display_name_none() -> None:
    assert units_display_name(None) == "unavailable"


# ---------------------------------------------------------------------------
# Integration tests: concise Graham output must not leak raw identifiers
# ---------------------------------------------------------------------------


def _graham_number_presentation() -> GrahamNumberPresentation:
    """Build a representative Graham Number presentation with sec_edgar + three_year_average."""
    eps_component = ResolvedInput(
        field_name="eps",
        value=2.47,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        basis="fiscal_year",
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        provider_field="us-gaap:EarningsPerShareDiluted",
    )
    eps = ResolvedInput(
        field_name="eps",
        value=2.66,
        source_kind=SourceKind.DERIVED,
        resolved_at=NOW,
        basis="three_year_average",
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        available_at=datetime(2026, 2, 20, tzinfo=UTC),
        retrieved_at=NOW,
        lineage=ComponentLineage(transformation="arithmetic_mean", components=(eps_component,)),
    )
    bvps = ResolvedInput(
        field_name="bvps",
        value=7.48,
        source_kind=SourceKind.PROVIDER,
        resolved_at=NOW,
        basis="fiscal_year_end",
        units="currency_per_share",
        currency="USD",
        provider_id="sec_edgar",
        provider_field="derived:stockholders_equity/common_shares_outstanding",
        available_at=datetime(2026, 2, 20, tzinfo=UTC),
        retrieved_at=NOW,
    )
    assembly = GrahamNumberInputAssembly(status=CalculationStatus.OK, eps=eps, bvps=bvps)
    return GrahamNumberPresentation(
        ticker="KO",
        assembly=assembly,
        result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=21.14),
    )


def test_concise_graham_renders_basis_through_explicit_label() -> None:
    """three_year_average must render as '3-year average', not raw snake_case."""
    rendered = render_graham_number(_graham_number_presentation())
    assert "3-year average" in rendered
    assert "three_year_average" not in rendered
    assert "three year average" not in rendered
    assert "three-year-average" not in rendered


def test_concise_graham_renders_provider_through_explicit_label() -> None:
    """sec_edgar must render as 'SEC EDGAR', not raw snake_case."""
    rendered = render_graham_number(_graham_number_presentation())
    assert "SEC EDGAR" in rendered
    assert "sec_edgar" not in rendered


def test_concise_graham_renders_field_labels_naturally() -> None:
    """Field names must render as EPS/BVPS, not eps=/bvps=."""
    rendered = render_graham_number(_graham_number_presentation())
    assert "EPS" in rendered
    assert "BVPS" in rendered
    # Raw machine identifiers must not appear in the concise output
    assert "eps=" not in rendered
    assert "bvps=" not in rendered


def test_concise_graham_source_summary_uses_explicit_labels() -> None:
    """The Sources/freshness line must use display labels for field and provider."""
    rendered = render_graham_number(_graham_number_presentation())
    lines = rendered.splitlines()
    sources_line = next(line for line in lines if line.startswith("Sources / freshness:"))
    # Should use "EPS" and "SEC EDGAR" rather than raw identifiers
    assert "EPS" in sources_line
    assert "SEC EDGAR" in sources_line
    assert "sec_edgar" not in sources_line
    assert "eps=" not in sources_line


def test_details_graham_renders_basis_through_explicit_label() -> None:
    """Details mode must also use explicit basis labels."""
    rendered = render_graham_number(_graham_number_presentation(), PresentationMode.DETAILS)
    assert "3-year average" in rendered
    assert "three_year_average" not in rendered


def test_details_graham_renders_provider_through_explicit_label() -> None:
    """Details mode must render provider through explicit label."""
    rendered = render_graham_number(_graham_number_presentation(), PresentationMode.DETAILS)
    assert "SEC EDGAR" in rendered
    assert "sec_edgar" not in rendered


def test_details_graham_preserves_exact_provider_field() -> None:
    """Details mode must retain the exact technical provider field for auditability."""
    rendered = render_graham_number(_graham_number_presentation(), PresentationMode.DETAILS)
    assert "us-gaap:EarningsPerShareDiluted" in rendered


def test_details_graham_renders_units_through_explicit_label() -> None:
    """Details mode must render units through explicit label."""
    rendered = render_graham_number(_graham_number_presentation(), PresentationMode.DETAILS)
    assert "currency per share" in rendered
    assert "currency_per_share" not in rendered


def test_diagnostics_graham_retains_raw_field_and_stage_names() -> None:
    """Diagnostics mode intentionally retains machine identifiers for precision."""
    trace = ResolutionTrace(
        events=(
            ResolutionEvent(
                field_name="bvps",
                stage=ResolutionStage.CACHE,
                outcome=ResolutionOutcome.MISS,
                message="No cached value.",
            ),
        )
    )
    assembly = _graham_number_presentation().assembly
    assembly_with_trace = GrahamNumberInputAssembly(
        status=CalculationStatus.OK,
        eps=assembly.eps,
        bvps=assembly.bvps,
        resolution_trace=trace,
    )
    presentation = GrahamNumberPresentation(
        ticker="KO",
        assembly=assembly_with_trace,
        result=GrahamNumberResult(status=CalculationStatus.OK, maximum_indicated_price=21.14),
    )
    rendered = render_graham_number(presentation, PresentationMode.DIAGNOSTICS)
    # Diagnostics intentionally uses raw identifiers
    assert "bvps" in rendered
    assert "cache" in rendered


def test_json_graham_preserves_machine_identifiers() -> None:
    """JSON output must retain raw machine identifiers as part of the schema."""
    rendered = render_graham_number(_graham_number_presentation(), PresentationMode.JSON)
    payload = json.loads(rendered)
    assert payload["inputs"]["eps"]["basis"] == "three_year_average"
    assert payload["inputs"]["eps"]["provider_id"] == "sec_edgar"
    assert payload["inputs"]["bvps"]["provider_id"] == "sec_edgar"
    assert payload["inputs"]["eps"]["field_name"] == "eps"
    assert payload["inputs"]["bvps"]["field_name"] == "bvps"


# ---------------------------------------------------------------------------
# Integration tests: concise Momentum output must not leak raw identifiers
# ---------------------------------------------------------------------------


def _momentum_presentation() -> MomentumPresentation:
    """Build a representative Momentum presentation with a typical market-data provider."""
    metrics = MomentumMetrics(
        ticker="AAPL",
        status=TrendStatus.BULLISH,
        current_price=225.0,
        short_sma_val=220.0,
        long_sma_val=210.0,
        crossover_signal=1.0,
        timestamp=NOW,
    )
    context = MarketDataContext(
        provider_id="yfinance",
        observation_interval="1d",
        data_as_of=datetime(2026, 8, 21).date(),
        currency="USD",
        observation_count=500,
        price_adjustment="adjusted",
    )
    return MomentumPresentation(
        metrics=metrics,
        config=MomentumConfig(short_window=20, long_window=50),
        market_data=context,
    )


def test_concise_momentum_renders_provider_through_explicit_label() -> None:
    """Momentum concise output must render provider through explicit label."""
    rendered = render_momentum(_momentum_presentation())
    assert "Yahoo Finance" in rendered
    assert "yfinance" not in rendered


def test_details_momentum_renders_provider_through_explicit_label() -> None:
    """Momentum details output must render provider through explicit label."""
    rendered = render_momentum(_momentum_presentation(), PresentationMode.DETAILS)
    assert "Data provider: Yahoo Finance" in rendered
    assert "yfinance" not in rendered


def test_diagnostics_momentum_retains_raw_provider_id() -> None:
    """Momentum diagnostics intentionally retains raw provider_id for precision."""
    rendered = render_momentum(_momentum_presentation(), PresentationMode.DIAGNOSTICS)
    assert "provider=yfinance" in rendered


def test_json_momentum_preserves_machine_identifiers() -> None:
    """Momentum JSON output must retain raw machine identifiers."""
    rendered = render_momentum(_momentum_presentation(), PresentationMode.JSON)
    payload = json.loads(rendered)
    assert payload["source"]["provider"] == "yfinance"


# ---------------------------------------------------------------------------
# Mapping pin tests (expected values, not dynamic completeness)
# ---------------------------------------------------------------------------


def test_provider_display_names_expected_mappings() -> None:
    """Pin the explicit provider display-label mappings."""
    assert PROVIDER_DISPLAY_NAMES["sec_edgar"] == "SEC EDGAR"
    assert PROVIDER_DISPLAY_NAMES["yfinance"] == "Yahoo Finance"
    assert PROVIDER_DISPLAY_NAMES["massive"] == "Massive"


def test_basis_display_names_expected_mappings() -> None:
    """Pin the explicit Graham basis display-label mappings."""
    assert BASIS_DISPLAY_NAMES["three_year_average"] == "3-year average"
    assert BASIS_DISPLAY_NAMES["ttm"] == "TTM"
    assert BASIS_DISPLAY_NAMES["fiscal_year_end"] == "fiscal-year-end"
    assert BASIS_DISPLAY_NAMES["fiscal_year"] == "fiscal year"


def test_field_display_names_expected_mappings() -> None:
    """Pin the explicit Graham field display-label mappings."""
    assert FIELD_DISPLAY_NAMES["eps"] == "EPS"
    assert FIELD_DISPLAY_NAMES["bvps"] == "BVPS"
    assert FIELD_DISPLAY_NAMES["current_price"] == "Current price"
    assert FIELD_DISPLAY_NAMES["current_aaa_yield"] == "Current AAA yield"
    assert FIELD_DISPLAY_NAMES["expected_growth"] == "Expected growth"


def test_units_display_names_expected_mappings() -> None:
    """Pin the explicit units display-label mappings."""
    assert UNITS_DISPLAY_NAMES["currency_per_share"] == "currency per share"
    assert UNITS_DISPLAY_NAMES["percentage_points"] == "percentage points"
    assert UNITS_DISPLAY_NAMES["ratio"] == "ratio"
