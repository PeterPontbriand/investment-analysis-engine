"""Display inference and recursive source evidence without inventing metadata."""

from dataclasses import replace
from datetime import UTC, datetime

from src.data.financial.provenance import ComponentLineage, ResolvedInput, SourceKind
from src.reporting.input_provenance import financial_basis, input_detail_lines, investor_input_lines, investor_value

NOW = datetime(2026, 9, 11, tzinfo=UTC)


def test_investor_evidence_deduplicates_shared_components_and_explains_zero() -> None:
    shares = ResolvedInput(
        "common_shares_outstanding",
        4_302_000_000,
        SourceKind.PROVIDER,
        NOW,
        basis="fiscal_year_end",
        units="shares",
        provider_id="sec_edgar",
    )
    preferred = ResolvedInput(
        "preferred_shares_outstanding",
        0,
        SourceKind.DERIVED,
        NOW,
        basis="fiscal_year_end",
        units="shares",
        provider_id="sec_edgar",
        provider_field="inferred:sec-company-facts:no-issued-preferred-equity",
        lineage=ComponentLineage("guard", (shares,)),
    )
    bvps = ResolvedInput(
        "bvps",
        7.477685,
        SourceKind.DERIVED,
        NOW,
        currency="USD",
        units="currency_per_share",
        lineage=ComponentLineage("division", (preferred, replace(shares, notes=("another retained source record",)))),
    )
    text = "\n".join(investor_input_lines("Book value per common share", bvps))
    assert text.count("4.302 billion shares") == 1
    assert "not an explicitly reported zero" in text
    assert "fiscal-year-end" in text
    assert "7.4777 USD" in text
    assert "provider field" not in text
    assert (
        financial_basis(replace(bvps, lineage=ComponentLineage("mixed", (shares, replace(preferred, basis=None)))))
        is None
    )
    assert investor_value(preferred) == "0 shares"


def test_missing_input_and_user_assumption_are_not_fabricated() -> None:
    assert "unavailable" in investor_input_lines("EPS", None)[0]
    assumption = ResolvedInput("expected_growth", 5, SourceKind.OVERRIDE, NOW, units="percentage_points")
    text = "\n".join(investor_input_lines("Expected growth", assumption))
    assert "5.00%" in text
    assert "user supplied" in text
    assert "not independently verified" in text


def test_inferred_zero_keeps_nested_evidence_and_assumption() -> None:
    """Guarded absence is not an observed zero, including inside derivations."""
    shares = ResolvedInput(
        "common_shares_outstanding",
        100.0,
        SourceKind.PROVIDER,
        NOW,
        units="shares",
        provider_id="sec_edgar",
        provider_field="us-gaap:CommonStockSharesOutstanding",
        notes=("same-period common-share anchor",),
    )
    inferred = ResolvedInput(
        "preferred_shares_outstanding",
        0.0,
        SourceKind.DERIVED,
        NOW,
        units="shares",
        provider_id="sec_edgar",
        provider_field="inferred:sec-company-facts:no-issued-preferred-equity",
        lineage=ComponentLineage("guarded absence", (shares,)),
        notes=("absence is an inference",),
    )
    text = "\n".join(input_detail_lines("Preferred shares", inferred))
    assert "Preferred shares: 0.000000" in text
    assert "source: inferred (SEC EDGAR)" in text
    assert "absence is an inference" in text
    assert "same-period common-share anchor" in text
    assert "units: shares" in text


def test_quote_period_is_inapplicable_and_market_time_unknown() -> None:
    """A known retrieval cannot manufacture an exchange timestamp."""
    quote = ResolvedInput(
        "current_price",
        87.83,
        SourceKind.PROVIDER,
        NOW,
        provider_id="yfinance",
        retrieved_at=NOW,
        units="currency_per_share",
        currency="USD",
    )
    text = "\n".join(input_detail_lines("Quote", quote))
    assert "period end: not applicable — point quote" in text
    assert "observed at: market observation time not supplied" in text
    assert "currency: USD" in text
