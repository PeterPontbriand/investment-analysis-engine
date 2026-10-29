"""What an investor sees of the FCF yield's market capitalization: concise, details, JSON, schema and stored replay."""

import json
from dataclasses import replace

import pytest

from investment_analysis_engine.analysis.shared.market_cap import ListingCheck
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode
from investment_analysis_engine.data.sec_edgar.cover_listing import ListingRename
from investment_analysis_engine.evaluation.fixtures.fcf_earnings_growth import (
    FCF_GROWTH_ACCESSION,
    FCF_GROWTH_PRICE,
    FCF_GROWTH_SHARE_COUNT,
)
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.strategies.fcf_growth.analyzer import FCFEarningsGrowthAnalyzer
from investment_analysis_engine.strategies.fcf_growth.codec import decode_fcf_growth, encode_fcf_growth
from investment_analysis_engine.strategies.fcf_growth.models import FCFEarningsGrowthResult
from investment_analysis_engine.strategies.fcf_growth.presenter import render_fcf_earnings_growth
from investment_analysis_engine.strategies.fcf_growth.replay import headline_fcf_growth
from scripts.repository_root import REPOSITORY_ROOT
from tests._fcf_market_data import CLOCK, fcf_market_data, fcf_result

RENAME = ListingRename(
    anchor_accession="0001326801-21-000014",
    anchor_form="10-K",
    anchor_symbol="FB",
    latest_accession="0001628280-26-003942",
    latest_form="10-K",
    latest_symbol="META",
)
SCHEMA = REPOSITORY_ROOT / "schemas" / "fcf-growth.schema.json"


def _renamed() -> FCFEarningsGrowthResult:
    result = fcf_result()
    assert result.market_capitalization is not None
    check = ListingCheck(affirmed=True, accession=RENAME.anchor_accession, rename=RENAME)
    return replace(result, market_capitalization=replace(result.market_capitalization, listing_check=check))


def test_the_concise_view_shows_the_yield_line_and_none_of_the_evidence() -> None:
    text = render_fcf_earnings_growth(fcf_result(), PresentationMode.CONCISE)

    assert "FCF yield: +10.00%" in text
    assert "Market capitalization" not in text
    assert "Listing check" not in text
    assert "Warning: FCF yield" not in text


def test_the_details_view_shows_the_whole_evidence() -> None:
    lines = render_fcf_earnings_growth(fcf_result(), PresentationMode.DETAILS).splitlines()

    assert "Market capitalization: 1,300.00 USD" in lines
    assert (
        f"  Share count: {FCF_GROWTH_SHARE_COUNT:,.0f} (year end, dated 2025-01-01; source filed 2025-02-01)" in lines
    )
    assert "  Share count on the price's basis: 400" in lines
    assert "  Provider split adjustments applied:" in lines
    assert "    2025-03-03 ×2 (between the share count and the price)" in lines
    assert f"  Price: {FCF_GROWTH_PRICE:,.2f} USD (split-adjusted close, {CLOCK.date().isoformat()})" in lines
    assert "  Currencies: filing USD, quote USD" in lines
    assert f"  Listing check: affirmed on {FCF_GROWTH_ACCESSION}" in lines


def test_the_details_view_names_both_accessions_of_a_renamed_ticker() -> None:
    text = render_fcf_earnings_growth(_renamed(), PresentationMode.DETAILS)

    assert (
        "  Listing check: affirmed; FB on 10-K 0001326801-21-000014, renamed META on 10-K 0001628280-26-003942" in text
    )


def test_the_diagnostics_view_also_shows_the_evidence() -> None:
    assert "  Listing check: affirmed on" in render_fcf_earnings_growth(fcf_result(), PresentationMode.DIAGNOSTICS)


def test_the_details_view_of_a_refused_market_cap_shows_what_is_known_and_why() -> None:
    result = fcf_result()
    assert result.market_capitalization is not None
    refusal = MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.INCOMPATIBLE_UNITS, "A depositary share.")
    check = ListingCheck(
        affirmed=False,
        accession=FCF_GROWTH_ACCESSION,
        reason_code=ReasonCode.INCOMPATIBLE_UNITS,
        reason="A depositary share.",
    )
    refused = replace(result.market_capitalization, result=refusal, listing_check=check)
    text = render_fcf_earnings_growth(
        replace(result, market_capitalization=refused, fcf_yield=refusal, warnings=()), PresentationMode.DETAILS
    )

    assert "Market capitalization: unavailable — A depositary share." in text
    assert "  Listing check: refused — A depositary share." in text
    assert "FCF yield: +" not in text


def test_the_json_document_holds_the_whole_evidence() -> None:
    document = json.loads(render_fcf_earnings_growth(fcf_result(), PresentationMode.JSON))
    part = document["market_capitalization"]

    assert set(part) == {
        "result",
        "share_count",
        "share_count_basis",
        "share_count_date",
        "share_count_filing_date",
        "scaled_share_count",
        "provider_adjustments",
        "price",
        "price_date",
        "form",
        "filing_currency",
        "quote_currency",
        "listing_check",
    }
    assert part["result"] == {"status": "ok", "value": 1300.0, "reason_code": None, "reason": None}
    assert part["share_count"]["value"] == FCF_GROWTH_SHARE_COUNT
    assert part["share_count"]["field_name"] == "common_shares_outstanding"
    assert part["share_count_basis"] == "year_end"
    assert (part["share_count_date"], part["share_count_filing_date"]) == ("2025-01-01", "2025-02-01")
    assert part["scaled_share_count"] == 400.0
    assert part["provider_adjustments"] == [{"ex_date": "2025-03-03", "ratio": 2.0, "window": "count_to_price"}]
    assert (part["price"], part["price_date"]) == (FCF_GROWTH_PRICE, CLOCK.date().isoformat())
    assert (part["form"], part["filing_currency"], part["quote_currency"]) == ("10-K", "USD", "USD")
    assert part["listing_check"] == {
        "affirmed": True,
        "accession": FCF_GROWTH_ACCESSION,
        "reason_code": None,
        "reason": None,
        "rename": None,
    }
    assert document["fcf_yield"]["value"] == pytest.approx(10.0)
    assert (document["schema_version"], document["result_schema_version"]) == (10, 6)


def test_the_json_document_holds_both_accessions_of_a_renamed_ticker() -> None:
    document = json.loads(render_fcf_earnings_growth(_renamed(), PresentationMode.JSON))

    assert document["market_capitalization"]["listing_check"]["rename"] == {
        "anchor_accession": "0001326801-21-000014",
        "anchor_form": "10-K",
        "anchor_symbol": "FB",
        "latest_accession": "0001628280-26-003942",
        "latest_form": "10-K",
        "latest_symbol": "META",
    }


def test_a_result_without_market_data_writes_null() -> None:
    document = json.loads(render_fcf_earnings_growth(fcf_result(fcf_market_data()), PresentationMode.JSON))

    assert document["market_capitalization"] is None
    assert document["fcf_yield"]["status"] == "unavailable"


def test_the_checked_in_schema_describes_the_market_cap_part() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert schema["properties"]["market_capitalization"]["anyOf"][0] == {"$ref": "#/$defs/FCFMarketCapPart"}
    assert {"FCFMarketCapPart", "FCFListingCheckPart", "FCFListingRenamePart", "FCFProviderAdjustmentPart"} <= set(
        schema["$defs"]
    )


@pytest.mark.parametrize("mode", list(PresentationMode))
def test_a_stored_run_replays_the_evidence_with_provider_cache_clock_and_calculator_disabled(
    mode: PresentationMode, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _renamed()
    live = render_fcf_earnings_growth(result, mode)
    stored = encode_fcf_growth(result)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("A replay must not resolve, compute or read the clock.")

    monkeypatch.setattr(FCFEarningsGrowthAnalyzer, "run_analysis", forbidden)
    for target in (
        "investment_analysis_engine.analysis.shared.cash_flow.compute_fcf_yield",
        "investment_analysis_engine.analysis.shared.market_cap.compute_market_cap",
        "investment_analysis_engine.analysis.shared.metric_inputs.resolve_market_cap_inputs",
        "investment_analysis_engine.analysis.shared.metric_inputs.anchor_year_end_scope",
        "investment_analysis_engine.core.clock.utc_now",
    ):
        monkeypatch.setattr(target, forbidden)

    assert render_fcf_earnings_growth(decode_fcf_growth(stored), mode) == live


def test_the_side_by_side_headline_is_the_same_with_and_without_a_market_cap() -> None:
    with_data = headline_fcf_growth(fcf_result())
    without = headline_fcf_growth(fcf_result(fcf_market_data()))

    assert [cell.key for cell in with_data.cells] == ["fcf_cagr", "eps_cagr", "classification"]
    assert with_data == without
