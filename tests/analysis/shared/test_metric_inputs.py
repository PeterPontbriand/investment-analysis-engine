"""The shared input assembly: the anchor year-end, the market-cap inputs, and the balance-sheet and annual values."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from investment_analysis_engine.analysis.shared.enterprise_value import compute_enterprise_value, compute_total_debt
from investment_analysis_engine.analysis.shared.market_cap import ListingCheck, MarketCapEvidence, ShareCountBasis
from investment_analysis_engine.analysis.shared.metric_evidence import InputUnavailable
from investment_analysis_engine.analysis.shared.metric_inputs import (
    SPLIT_HISTORY_MARGIN_DAYS,
    MarketCapInputs,
    MetricInputsFailure,
    anchor_year_end_scope,
    resolve_annual_values,
    resolve_balance_sheet_values,
    resolve_market_cap_inputs,
)
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.financial.facts import (
    COVER_PAGE_BASIS,
    FactsNotAvailableAsOf,
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    InstantAbsence,
    InstantAbsenceReason,
    InstantSeriesFacts,
    InstantSeriesRequest,
)
from investment_analysis_engine.data.financial.production import ProductionFinancialFactsProvider
from investment_analysis_engine.data.financial.provenance import FinancialSubjectKind, ResolvedInput
from investment_analysis_engine.data.financial.resolver import InputResolver
from investment_analysis_engine.data.market_data import SplitEvent
from investment_analysis_engine.data.sec_edgar.cover_listing import ListingEvidence, ListingResolution, SecurityKind
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    SEC_PROVIDER_ID,
    AnchorYearEnd,
    SecEdgarFinancialFactsAdapter,
)
from tests._sec_instants import ANNUAL_FIXTURES, REGRESSION_SET, FixtureFetcher, load
from tests.analysis.shared._metric_input_rig import (
    LIVE_NOW,
    FactsStub,
    Rig,
    SplitStub,
    captured_history,
    fetch_error,
    read_cover,
    rig,
    synthetic_history,
    unreachable,
)

F = FinancialField
_YEAR_END_BASIS = "fiscal_year_end"
_QUOTE = (130.0, "USD", LIVE_NOW)


def _anchor(rig_: Rig, ticker: str, as_of: datetime | None = None) -> AnchorYearEnd:
    """Return the anchor year-end of a scope that is closed again, for tests that only read the date."""
    with anchor_year_end_scope(rig_.resolver, ticker=ticker, as_of=as_of) as anchor:
        assert isinstance(anchor, AnchorYearEnd)
        return anchor


@contextmanager
def _scoped(rig_: Rig, ticker: str, as_of: datetime | None = None) -> Iterator[AnchorYearEnd]:
    """Open the analysis scope and yield its anchor; the inputs are read inside, as a consumer's analyzer does."""
    with anchor_year_end_scope(rig_.resolver, ticker=ticker, as_of=as_of) as anchor:
        assert isinstance(anchor, AnchorYearEnd)
        yield anchor


def _inputs(  # noqa: PLR0913
    ticker: str,
    *,
    as_of: datetime | None = None,
    history: SplitStub | None = None,
    quotes: FactsStub | None = None,
    filing_currency: str | None = "USD",
    rig_: Rig | None = None,
) -> tuple[MarketCapInputs, Rig, SplitStub]:
    """Return the market-cap inputs of an issuer through the real adapter and the stubs of the market-data side."""
    chosen = rig_ or rig(ticker, quotes=quotes or FactsStub(quote=_QUOTE))
    splits = history or SplitStub(captured_history("wmt"))
    with anchor_year_end_scope(chosen.resolver, ticker=ticker, as_of=as_of) as anchor:
        assert isinstance(anchor, AnchorYearEnd)
        result = resolve_market_cap_inputs(
            chosen.resolver,
            splits,
            chosen.production,
            anchor=anchor,
            ticker=ticker,
            filing_currency=filing_currency,
            quote_provider_id="yfinance",
            as_of=as_of,
            use_cache=False,
        )
    assert isinstance(result, MarketCapInputs)
    return result, chosen, splits


def _count_bases(chosen: Rig) -> list[str | None]:
    """Return the basis of every share-count request the production provider routed."""
    return [
        request.basis
        for request in chosen.production.fact_requests
        if request.field_name is F.COMMON_SHARES_OUTSTANDING
    ]


def _count(inputs: MarketCapInputs) -> ResolvedInput:
    assert isinstance(inputs.share_count, ResolvedInput)
    return inputs.share_count


def _unavailable(value: object) -> InputUnavailable:
    assert isinstance(value, InputUnavailable)
    return value


# --- year-end t (K4) ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("ticker", sorted(REGRESSION_SET))
def test_the_anchor_year_end_of_every_regression_issuer_is_its_latest_fiscal_year_end(ticker: str) -> None:
    anchor = _anchor(rig(ticker), ticker)
    assert anchor.year_end == REGRESSION_SET[ticker]
    assert anchor.accession == load(ticker)["anchor_accession"]


def test_the_year_end_is_found_once_per_scope_and_every_input_is_taken_at_it() -> None:
    chosen = rig("WMT", quotes=FactsStub(quote=_QUOTE))
    splits = SplitStub(captured_history("wmt"))
    with anchor_year_end_scope(chosen.resolver, ticker="WMT", as_of=None) as anchor:
        assert isinstance(anchor, AnchorYearEnd)
        opened = len(chosen.fetcher.calls)
        inputs = resolve_market_cap_inputs(
            chosen.resolver,
            splits,
            chosen.production,
            anchor=anchor,
            ticker="WMT",
            filing_currency="USD",
            quote_provider_id="yfinance",
            as_of=None,
            use_cache=False,
        )
        balance = resolve_balance_sheet_values(
            chosen.resolver, anchor=anchor, ticker="WMT", fields=[F.TOTAL_ASSETS, F.CASH_AND_EQUIVALENTS], as_of=None
        )
    assert isinstance(inputs, MarketCapInputs)
    assert not isinstance(balance, (InputUnavailable, MetricInputsFailure))
    assert anchor.year_end == date(2026, 1, 31)
    assert len(chosen.fetcher.calls) == opened == 3  # the ticker file, the Company Facts and the submissions
    assert sum("/submissions/" in url for url in chosen.fetcher.calls) == 1
    assert sum("/companyfacts/" in url for url in chosen.fetcher.calls) == 1
    for value in balance.values():
        assert isinstance(value, ResolvedInput)
        assert value.observation_period_end is not None
        assert value.observation_period_end.date() == anchor.year_end


def test_annual_values_of_an_issuer_end_at_the_year_end_in_the_same_scope() -> None:
    chosen = rig("WMT", fetcher=FixtureFetcher("WMT", folder=ANNUAL_FIXTURES))
    with anchor_year_end_scope(chosen.resolver, ticker="WMT", as_of=None) as anchor:
        assert isinstance(anchor, AnchorYearEnd)
        annual = resolve_annual_values(
            chosen.resolver,
            anchor=anchor,
            ticker="WMT",
            fields=[
                F.SALES,
                F.COST_OF_REVENUE,
                F.OPERATING_INCOME,
                F.DEPRECIATION_AND_AMORTIZATION,
                F.INTEREST_EXPENSE,
            ],
            as_of=None,
        )
    assert not isinstance(annual, (InputUnavailable, MetricInputsFailure))
    assert len(chosen.fetcher.calls) == 3
    held = {name: value for name, value in annual.items() if isinstance(value, ResolvedInput)}
    assert set(held) == {F.SALES, F.COST_OF_REVENUE, F.OPERATING_INCOME, F.DEPRECIATION_AND_AMORTIZATION}
    for observation in held.values():
        assert observation.observation_period_end is not None
        assert observation.observation_period_end.date() == date(2026, 1, 31)
    assert annual[F.INTEREST_EXPENSE] is None  # Walmart tags none for the year


_ANCHOR = AnchorYearEnd(date(2026, 1, 31), "0000000001-26-000001", "10-K", date(2026, 3, 13), {})
_EARLIER = datetime(2026, 3, 1, tzinfo=UTC)
_LATER = datetime(2026, 3, 13, tzinfo=UTC)


def _annual(stub: FactsStub, *fields: F, boundary: datetime | None = None) -> Any:
    return resolve_annual_values(
        InputResolver(stub, clock=lambda: LIVE_NOW),
        anchor=_ANCHOR,
        ticker="WMT",
        fields=fields,
        as_of=boundary,
    )


def test_an_annual_observation_that_does_not_end_at_the_year_end_is_never_returned_as_the_year_ends() -> None:
    stub = FactsStub(
        annual={
            F.SALES: [(100.0, date(2025, 1, 31), _EARLIER)],
            F.OPERATING_INCOME: [(5.0, date(2026, 1, 31), _EARLIER), (4.0, date(2025, 1, 31), _EARLIER)],
        }
    )
    values = _annual(stub, F.SALES, F.OPERATING_INCOME, F.NET_INCOME)
    assert not isinstance(values, (InputUnavailable, MetricInputsFailure))
    assert values[F.SALES] is None  # the answer ends a year earlier
    assert values[F.NET_INCOME] is None  # the provider reports none
    held = values[F.OPERATING_INCOME]
    assert isinstance(held, ResolvedInput)
    assert held.value == 5.0


def test_the_latest_available_version_of_the_years_value_is_the_one_returned() -> None:
    stub = FactsStub(annual={F.SALES: [(100.0, date(2026, 1, 31), _EARLIER), (101.0, date(2026, 1, 31), _LATER)]})
    values = _annual(stub, F.SALES)
    assert not isinstance(values, (InputUnavailable, MetricInputsFailure))
    held = values[F.SALES]
    assert isinstance(held, ResolvedInput)
    assert held.value == 101.0


def test_a_version_available_after_the_boundary_is_not_used() -> None:
    stub = FactsStub(annual={F.SALES: [(100.0, date(2026, 1, 31), _EARLIER), (101.0, date(2026, 1, 31), _LATER)]})
    values = _annual(stub, F.SALES, boundary=datetime(2026, 3, 5, tzinfo=UTC))
    assert not isinstance(values, (InputUnavailable, MetricInputsFailure))
    held = values[F.SALES]
    assert isinstance(held, ResolvedInput)
    assert held.value == 100.0
    assert held.as_of == datetime(2026, 3, 5, tzinfo=UTC)


def test_conflicting_latest_versions_are_unavailable_not_chosen() -> None:
    stub = FactsStub(annual={F.SALES: [(100.0, date(2026, 1, 31), _LATER), (101.0, date(2026, 1, 31), _LATER)]})
    values = _annual(stub, F.SALES)
    assert not isinstance(values, (InputUnavailable, MetricInputsFailure))
    conflict = _unavailable(values[F.SALES])
    assert conflict.reason_code is ReasonCode.AMBIGUOUS_FACT


def test_case_b_from_a_fact_path_is_returned_once_and_no_further_field_is_requested() -> None:
    stub = FactsStub(not_available_as_of="The registrant filed its first annual report after the boundary.")
    outcome = _annual(stub, F.SALES, F.OPERATING_INCOME)
    unavailable = _unavailable(outcome)
    assert unavailable.reason_code is ReasonCode.NOT_AVAILABLE_AS_OF
    assert unavailable.reason == "The registrant filed its first annual report after the boundary."
    assert len(stub.requests) == 1


def test_a_field_that_is_not_a_completed_annual_period_field_is_a_caller_error() -> None:
    with pytest.raises(ValueError, match="not a completed-annual period field"):
        _annual(FactsStub(), F.TOTAL_ASSETS)


def test_an_unsigned_field_is_a_caller_error_not_a_provider_failure() -> None:
    chosen = rig("WMT")
    anchor = _anchor(chosen, "WMT")
    with pytest.raises(ValueError, match="not a balance-sheet field"):
        resolve_balance_sheet_values(chosen.resolver, anchor=anchor, ticker="WMT", fields=[F.SALES], as_of=None)


def test_a_provider_without_the_year_end_capability_has_no_year_end() -> None:
    resolver = InputResolver(FactsStub(), clock=lambda: LIVE_NOW)
    with anchor_year_end_scope(resolver, ticker="WMT", as_of=None) as anchor:
        unavailable = _unavailable(anchor)
    assert unavailable.reason_code is ReasonCode.MISSING_FACT


# --- the share count (S4) ----------------------------------------------------------------------------------------


def test_a_year_end_count_dated_the_year_end_is_used_and_the_cover_count_is_not_requested() -> None:
    inputs, chosen, _ = _inputs("JPM")
    count = _count(inputs)
    assert (inputs.share_count_basis, count.value) == (ShareCountBasis.YEAR_END, 2_696_200_000.0)
    assert count.observation_period_end is not None
    assert count.observation_period_end.date() == date(2025, 12, 31)
    assert inputs.share_count_filing_date == date(2026, 2, 13)
    assert _count_bases(chosen) == [_YEAR_END_BASIS]


@pytest.mark.parametrize(
    ("ticker", "value", "count_date"),
    [("WMT", 7_972_402_501.0, date(2026, 3, 11)), ("SAP", 1_228_504_232.0, date(2025, 12, 31))],
)
def test_walmart_and_sap_use_the_cover_page_count(ticker: str, value: float, count_date: date) -> None:
    inputs, chosen, _ = _inputs(ticker)
    count = _count(inputs)
    assert (inputs.share_count_basis, count.value) == (ShareCountBasis.COVER_PAGE, value)
    assert count.observation_period_end is not None
    assert count.observation_period_end.date() == count_date
    assert _count_bases(chosen) == [_YEAR_END_BASIS, COVER_PAGE_BASIS]


def test_alphabet_uses_its_combined_year_end_count() -> None:
    inputs, _, _ = _inputs("GOOGL")
    assert (inputs.share_count_basis, _count(inputs).value) == (ShareCountBasis.YEAR_END, 12_088_000_000.0)
    assert inputs.listing_check.affirmed


def test_per_class_cover_counts_with_no_total_give_none() -> None:
    document = load("GOOGL")
    del document["companyfacts"]["facts"]["us-gaap"]["CommonStockSharesOutstanding"]
    chosen = rig(
        "GOOGL", quotes=FactsStub(quote=_QUOTE), fetcher=FixtureFetcher("GOOGL", companyfacts=document["companyfacts"])
    )
    inputs, _, _ = _inputs("GOOGL", rig_=chosen)
    missing = _unavailable(inputs.share_count)
    assert missing.reason_code is ReasonCode.MISSING_FACT
    assert "No share count" in missing.reason
    assert inputs.market_cap().result.status is MetricStatus.UNAVAILABLE


def test_nutriens_count_for_the_year_before_is_not_used_and_with_no_cover_count_it_is_unavailable() -> None:
    inputs, _, _ = _inputs("NTR")
    count = _count(inputs)
    assert count.observation_period_end is not None
    assert count.observation_period_end.date() == date(2024, 12, 31)  # the year before t = 2025-12-31
    # NTR files a 40-F, which market cap refuses first; as a 10-K the count's own date would refuse it.
    as_a_domestic_filer = replace(
        inputs, form="10-K", filing_currency="USD", listing_check=ListingCheck(affirmed=True, accession="a")
    )
    refused = as_a_domestic_filer.market_cap().result
    assert (refused.status, refused.reason_code) == (MetricStatus.UNAVAILABLE, ReasonCode.INCOMPATIBLE_PERIOD)
    assert inputs.market_cap().result.reason_code is ReasonCode.INCOMPATIBLE_SCOPE


def test_a_count_whose_source_filing_is_not_dated_is_unavailable() -> None:
    chosen = rig("JPM", quotes=FactsStub(quote=_QUOTE))
    with _scoped(chosen, "JPM") as anchor:
        result = resolve_market_cap_inputs(
            chosen.resolver,
            SplitStub(captured_history("wmt")),
            chosen.production,
            anchor=replace(anchor, filing_dates={}),
            ticker="JPM",
            filing_currency="USD",
            quote_provider_id="yfinance",
            as_of=None,
            use_cache=False,
        )
    assert isinstance(result, MarketCapInputs)
    assert "not in the submissions data" in _unavailable(result.share_count).reason


# --- the price (K15), the quote and the split history (S2, N7) ---------------------------------------------------


def _nvidia(as_of: datetime, history: SplitStub | None = None) -> tuple[MarketCapInputs, SplitStub]:
    """Return NVIDIA's inputs through the assembly: no SEC fixture exists, so the facts are the table of a stub."""
    stub = FactsStub(counts={_YEAR_END_BASIS: (2_464_000_000.0, date(2024, 1, 28), "0001045810-24-000029")})
    resolver = InputResolver(stub, clock=lambda: LIVE_NOW)
    anchor = AnchorYearEnd(
        date(2024, 1, 28),
        "0001045810-24-000029",
        "10-K",
        date(2024, 2, 21),
        {"0001045810-24-000029": date(2024, 2, 21)},
    )
    splits = history or SplitStub(captured_history("nvda"))
    result = resolve_market_cap_inputs(
        resolver,
        splits,
        _Affirming(),
        anchor=anchor,
        ticker="NVDA",
        filing_currency="USD",
        quote_provider_id="yfinance",
        as_of=as_of,
        use_cache=False,
    )
    assert isinstance(result, MarketCapInputs)
    return result, splits


class _Affirming:
    """A cover-listing capability that affirms every ticker as a share."""

    def resolve_cover_listing(self, request: Any) -> Any:
        return ListingResolution(
            evidence=ListingEvidence(
                ticker=request.ticker,
                kind=SecurityKind.SHARE,
                title="Common Stock, $0.001 par value per share",
                cik="0001045810",
                accession="0001045810-24-000029",
                form="10-K",
                accepted_at=datetime(2024, 2, 21, 21, 0, tzinfo=UTC),
                source_url="https://www.sec.gov/Archives/edgar/data/1045810/000104581024000029/R1.htm",
                retrieved_at=LIVE_NOW,
            )
        )


def test_with_as_of_the_price_is_the_split_adjusted_close_of_the_last_session_on_or_before_it() -> None:
    inputs, splits = _nvidia(datetime(2024, 4, 30, 15, 0, tzinfo=UTC))
    assert inputs.price == pytest.approx(86.402)
    assert inputs.price_date == date(2024, 4, 30)
    assert inputs.quote_currency == "USD"
    assert splits.calls == [
        {
            "ticker": "NVDA",
            "start": "2024-02-11",  # the filing date of the count, 2024-02-21, less the margin of 10 days
            "use_cache": False,
            "adjusted_on": None,
            "as_of": date(2024, 4, 30),
        }
    ]


@pytest.mark.parametrize(
    ("as_of", "session", "close"),
    [
        (datetime(2024, 5, 2, tzinfo=UTC), date(2024, 5, 2), 85.817),  # a date-only boundary includes that day's close
        (datetime(2024, 5, 2, 23, 59, 59, tzinfo=UTC), date(2024, 5, 2), 85.817),
        (datetime(2024, 5, 4, 12, tzinfo=UTC), date(2024, 5, 2), 85.817),  # a Saturday: the last session before it
        (datetime(2024, 6, 7, tzinfo=UTC), date(2024, 6, 7), 120.888),
    ],
)
def test_a_date_only_boundary_includes_that_days_close_and_a_closed_day_takes_the_last_session(
    as_of: datetime, session: date, close: float
) -> None:
    inputs, _ = _nvidia(as_of)
    assert inputs.price == pytest.approx(close)
    assert inputs.price_date == session


def test_nvidias_split_after_the_count_scales_it_to_the_price_basis() -> None:
    inputs, _ = _nvidia(datetime(2024, 4, 30, tzinfo=UTC))
    evidence = inputs.market_cap()
    assert evidence.result.status is MetricStatus.OK
    assert evidence.scaled_share_count == 24_640_000_000.0  # the 10-for-1 split of 2024-06-10 follows the filing
    assert evidence.splits_applied == (SplitEvent(date(2024, 6, 10), 10.0),)
    assert evidence.result.value == pytest.approx(86.402 * 24_640_000_000.0)
    assert evidence.result.value == pytest.approx(864.02 * 2_464_000_000.0)  # the unadjusted close of the day


def test_a_response_that_ends_before_as_of_is_refused() -> None:
    history = SplitStub(synthetic_history({date(2024, 4, 29): 87.0}, adjustment_date=date(2024, 4, 30)))
    inputs, _ = _nvidia(datetime(2024, 5, 3, tzinfo=UTC), history)
    refused = _unavailable(inputs.price)
    assert refused.reason_code is ReasonCode.NOT_AVAILABLE_AS_OF
    assert "ends at its adjustment date" in refused.reason
    assert inputs.market_cap().result.reason_code is ReasonCode.NOT_AVAILABLE_AS_OF


def test_no_session_on_or_before_as_of_is_unavailable_as_of() -> None:
    history = SplitStub(synthetic_history({date(2024, 5, 6): 87.0}, adjustment_date=date(2026, 10, 26)))
    inputs, _ = _nvidia(datetime(2024, 5, 3, tzinfo=UTC), history)
    assert _unavailable(inputs.price).reason_code is ReasonCode.NOT_AVAILABLE_AS_OF


def test_the_margin_keeps_the_last_session_before_a_weekend_filing_date_in_range() -> None:
    saturday = date(2024, 3, 16)
    stub = FactsStub(counts={_YEAR_END_BASIS: (1_000.0, date(2024, 1, 31), "0000000001-24-000001")})
    anchor = AnchorYearEnd(
        date(2024, 1, 31), "0000000001-24-000001", "10-K", saturday, {"0000000001-24-000001": saturday}
    )
    splits = SplitStub(captured_history("wmt"))
    result = resolve_market_cap_inputs(
        InputResolver(stub, clock=lambda: LIVE_NOW),
        splits,
        _Affirming(),
        anchor=anchor,
        ticker="WMT",
        filing_currency="USD",
        quote_provider_id="yfinance",
        as_of=datetime(2024, 3, 16, 20, tzinfo=UTC),
        use_cache=False,
    )
    assert isinstance(result, MarketCapInputs)
    assert SPLIT_HISTORY_MARGIN_DAYS == 10
    assert splits.calls[0]["start"] == (saturday - timedelta(days=10)).isoformat() == "2024-03-06"
    assert result.price == pytest.approx(60.68)  # Friday's close
    assert result.price_date == date(2024, 3, 15)


def test_without_as_of_the_price_is_the_current_quote_and_the_history_is_adjusted_on_its_date() -> None:
    inputs, chosen, splits = _inputs("WMT")
    assert (inputs.price, inputs.price_date, inputs.quote_currency) == (130.0, date(2026, 10, 26), "USD")
    assert splits.calls == [
        {
            "ticker": "WMT",
            "start": "2026-03-01",  # the cover-page count is dated 2026-03-11; its splits are counted from there
            "use_cache": False,
            "adjusted_on": date(2026, 10, 26),
            "as_of": None,
        }
    ]
    assert inputs.adjustment_date == date(2026, 10, 26)
    quotes = [request for request in chosen.quotes.requests if request.field_name is F.CURRENT_PRICE]
    assert len(quotes) == 1
    assert (quotes[0].provider_id, quotes[0].as_of) == ("yfinance", None)


def test_a_one_day_download_is_never_a_quote() -> None:
    history = SplitStub(synthetic_history({date(2026, 10, 26): 99.0}, adjustment_date=date(2026, 10, 26)))
    quote_less, _, _ = _inputs("WMT", history=history, quotes=FactsStub(quote=None))
    missing = _unavailable(quote_less.price)
    assert missing.reason_code is ReasonCode.MISSING_FACT
    assert quote_less.quote_currency is None
    assert history.calls == []  # no quote, so no history is read for a price either
    with_quote, _, _ = _inputs("WMT", history=history)
    assert with_quote.price == 130.0  # the quote, not the history's 99.0 close of the same day


def test_a_split_history_adjusted_on_another_day_than_the_quote_is_refused() -> None:
    history = SplitStub(replace(captured_history("wmt"), adjustment_date=date(2026, 10, 25)))
    inputs, _, _ = _inputs("WMT", history=history)
    refused = _unavailable(inputs.price)
    assert refused.reason_code is ReasonCode.INCOMPATIBLE_PERIOD
    assert "2026-10-25" in refused.reason
    assert "2026-10-26" in refused.reason


def test_the_quote_currency_with_as_of_is_the_split_history_responses() -> None:
    history = SplitStub(
        replace(captured_history("nvda"), context=replace(captured_history("nvda").context, currency="EUR"))
    )
    inputs, _ = _nvidia(datetime(2024, 4, 30, tzinfo=UTC), history)
    assert inputs.quote_currency == "EUR"
    assert inputs.market_cap().result.reason_code is ReasonCode.INCOMPATIBLE_CURRENCY


# --- end to end through compute_market_cap -----------------------------------------------------------------------


def test_walmarts_count_taken_after_its_split_is_not_scaled_again() -> None:
    inputs, _, _ = _inputs("WMT")
    evidence = inputs.market_cap()
    assert evidence.result.status is MetricStatus.OK
    assert evidence.share_count_basis is ShareCountBasis.COVER_PAGE
    assert evidence.splits_applied == ()  # the 3-for-1 split of 2024-02-26 precedes the count of 2026-03-11
    assert evidence.scaled_share_count == 7_972_402_501.0
    assert evidence.result.value == pytest.approx(7_972_402_501.0 * 130.0)
    assert evidence.listing_check is not None
    assert evidence.listing_check.affirmed
    # Scaling from the fiscal year-end instead would count the split again: three times the market cap.
    wrong = 7_972_402_501.0 * 3 * 130.0
    assert evidence.result.value != pytest.approx(wrong)


def test_sap_is_refused_by_its_form_before_its_cover_is_read() -> None:
    inputs, chosen, _ = _inputs("SAP", filing_currency="EUR")
    evidence = inputs.market_cap()
    assert (evidence.result.status, evidence.result.reason_code) == (
        MetricStatus.UNAVAILABLE,
        ReasonCode.INCOMPATIBLE_SCOPE,
    )
    assert inputs.form == "20-F"
    assert chosen.cover_urls == []  # a form market cap refuses by itself is not worth a request
    assert inputs.listing_check.reason is not None
    assert "was not read" in inputs.listing_check.reason


def test_a_quote_in_another_currency_than_the_filing_is_refused() -> None:
    inputs, _, _ = _inputs("WMT", quotes=FactsStub(quote=(100.0, "EUR", LIVE_NOW)))
    assert inputs.quote_currency == "EUR"
    assert inputs.market_cap().result.reason_code is ReasonCode.INCOMPATIBLE_CURRENCY
    unknown, _, _ = _inputs("WMT", filing_currency=None)
    assert unknown.market_cap().result.reason_code is ReasonCode.INCOMPATIBLE_CURRENCY


def test_the_requested_tickers_own_row_decides_the_listing_check_whatever_else_the_cover_registers() -> None:
    inputs, _, _ = _inputs("JPM")
    assert inputs.listing_check.affirmed  # JPM's common stock is affirmed beside the depositary shares of its preferred
    assert inputs.listing_check.accession == load("JPM")["anchor_accession"]


def test_a_listing_check_is_read_once_for_the_scope() -> None:
    inputs, chosen, _ = _inputs("WMT")
    assert inputs.listing_check.affirmed
    assert len(chosen.cover_urls) == 1


def test_the_inputs_are_the_arguments_of_compute_market_cap() -> None:
    inputs, _, _ = _inputs("WMT")
    evidence = inputs.market_cap()
    assert isinstance(evidence, MarketCapEvidence)
    assert evidence.form == "10-K"
    assert evidence.price_date == date(2026, 10, 26)
    assert evidence.filing_currency == evidence.quote_currency == "USD"


# --- balance-sheet values and the metrics that read them ---------------------------------------------------------

_DEBT_FIELDS = [
    F.SHORT_TERM_BORROWINGS,
    F.CURRENT_PORTION_OF_LONG_TERM_DEBT,
    F.NONCURRENT_LONG_TERM_DEBT,
    F.LEASE_LIABILITIES_AS_DEBT,
    F.LONG_TERM_DEBT_TOTAL,
]


def _debt_and_ev(ticker: str) -> tuple[Any, Any]:
    chosen = rig(ticker)
    with anchor_year_end_scope(chosen.resolver, ticker=ticker, as_of=None) as anchor:
        assert isinstance(anchor, AnchorYearEnd)
        balance = resolve_balance_sheet_values(
            chosen.resolver,
            anchor=anchor,
            ticker=ticker,
            fields=[
                *_DEBT_FIELDS,
                F.PREFERRED_STOCK,
                F.NONCONTROLLING_INTEREST,
                F.CASH_AND_EQUIVALENTS,
                F.SHORT_TERM_INVESTMENTS,
                F.CURRENT_ASSETS,
            ],
            as_of=None,
        )
    income = rig(ticker, fetcher=FixtureFetcher(ticker, folder=ANNUAL_FIXTURES))
    with anchor_year_end_scope(income.resolver, ticker=ticker, as_of=None) as anchor:
        assert isinstance(anchor, AnchorYearEnd)
        annual = resolve_annual_values(
            income.resolver,
            anchor=anchor,
            ticker=ticker,
            fields=[F.INTEREST_EXPENSE],
            as_of=None,
        )
    assert not isinstance(balance, (InputUnavailable, MetricInputsFailure))
    assert not isinstance(annual, (InputUnavailable, MetricInputsFailure))
    interest = annual[F.INTEREST_EXPENSE]
    assert not isinstance(interest, InputUnavailable)
    debt = compute_total_debt(
        short_term_borrowings=balance[F.SHORT_TERM_BORROWINGS],
        current_portion_of_long_term_debt=balance[F.CURRENT_PORTION_OF_LONG_TERM_DEBT],
        noncurrent_long_term_debt=balance[F.NONCURRENT_LONG_TERM_DEBT],
        lease_liabilities_as_debt=balance[F.LEASE_LIABILITIES_AS_DEBT],
        long_term_debt_total=balance[F.LONG_TERM_DEBT_TOTAL],
        interest_expense=interest,
    )
    market_cap = MarketCapEvidence(result=MetricResult.ok(600_000e6))
    enterprise_value = compute_enterprise_value(
        market_cap=market_cap,
        total_debt=debt,
        preferred_stock=balance[F.PREFERRED_STOCK],
        noncontrolling_interest=balance[F.NONCONTROLLING_INTEREST],
        cash_and_equivalents=balance[F.CASH_AND_EQUIVALENTS],
        short_term_investments=balance[F.SHORT_TERM_INVESTMENTS],
        current_assets=balance[F.CURRENT_ASSETS],
    )
    return debt, enterprise_value


def test_monsters_empty_debt_reaches_total_debt_as_zero_through_the_balance_sheet_function() -> None:
    debt, _ = _debt_and_ev("MNST")
    assert debt.result.status is MetricStatus.OK
    assert debt.result.value == 0.0
    assert len(debt.zero_components) == 4


def test_deeres_unclassified_balance_sheet_reaches_enterprise_value_as_unavailable() -> None:
    debt, enterprise_value = _debt_and_ev("DE")
    assert debt.result.reason_code is ReasonCode.DEBT_NOT_VISIBLE
    assert enterprise_value.result.status is MetricStatus.UNAVAILABLE
    assert enterprise_value.total_debt.result.reason_code is ReasonCode.DEBT_NOT_VISIBLE


def test_walmarts_balance_sheet_values_carry_the_year_end_and_walmarts_debt_is_summed() -> None:
    debt, _ = _debt_and_ev("WMT")
    assert debt.result.value == 51_523_000_000.0


def test_a_field_the_filings_do_not_tag_is_an_absence_not_zero() -> None:
    chosen = rig("MNST")
    anchor = _anchor(chosen, "MNST")
    with anchor_year_end_scope(chosen.resolver, ticker="MNST", as_of=None) as scoped:
        assert isinstance(scoped, AnchorYearEnd)
        values = resolve_balance_sheet_values(
            chosen.resolver, anchor=anchor, ticker="MNST", fields=[F.SHORT_TERM_BORROWINGS], as_of=None
        )
    assert not isinstance(values, (InputUnavailable, MetricInputsFailure))
    absence = values[F.SHORT_TERM_BORROWINGS]
    assert isinstance(absence, InstantAbsence)
    assert absence.reason is InstantAbsenceReason.NOT_TAGGED


class _FactsOnly:
    """A financial-facts provider with no balance-sheet series."""

    def fetch_facts(self, request: Any, *, effective_as_of: datetime) -> tuple[()]:  # noqa: ARG002
        return ()


def test_a_provider_that_serves_no_series_gives_an_unsupported_absence() -> None:
    resolver = InputResolver(_FactsOnly(), clock=lambda: LIVE_NOW)
    anchor = AnchorYearEnd(date(2026, 1, 31), "0000000001-26-000001", "10-K", date(2026, 3, 13), {})
    values = resolve_balance_sheet_values(resolver, anchor=anchor, ticker="WMT", fields=[F.TOTAL_ASSETS], as_of=None)
    assert not isinstance(values, (InputUnavailable, MetricInputsFailure))
    absence = values[F.TOTAL_ASSETS]
    assert isinstance(absence, InstantAbsence)
    assert absence.reason is InstantAbsenceReason.UNSUPPORTED


# --- the registrant with no annual report, or none by the boundary (S6) ------------------------------------------


def _after_boundary_message() -> str:
    """Return the adapter's own message for Walmart at a boundary before its first annual report."""
    chosen = rig("WMT")
    with anchor_year_end_scope(chosen.resolver, ticker="WMT", as_of=datetime(2023, 1, 1, tzinfo=UTC)) as outcome:
        return _unavailable(outcome).reason


def test_case_b_is_returned_once_as_unavailable_as_of_with_the_adapters_message_and_nothing_more_is_requested() -> None:
    chosen = rig("WMT", quotes=FactsStub(quote=_QUOTE))
    with anchor_year_end_scope(chosen.resolver, ticker="WMT", as_of=datetime(2023, 1, 1, tzinfo=UTC)) as outcome:
        unavailable = _unavailable(outcome)
    assert unavailable.reason_code is ReasonCode.NOT_AVAILABLE_AS_OF
    assert "filed its first annual report on 2024-03-15" in unavailable.reason
    assert len(chosen.fetcher.calls) == 3  # the scope's own documents, and nothing after it
    assert chosen.production.fact_requests == []
    assert chosen.production.series_requests == []
    assert chosen.cover_urls == []
    assert chosen.quotes.requests == []


def test_case_b_has_the_same_message_on_the_fact_path_the_balance_sheet_path_and_the_year_end() -> None:
    boundary = datetime(2023, 1, 1, tzinfo=UTC)
    chosen = rig("WMT")
    adapter_message = _after_boundary_message()
    with chosen.production.analysis_scope(subject_id="WMT", provider_id=SEC_PROVIDER_ID, as_of=boundary):
        with pytest.raises(FactsNotAvailableAsOf) as raised:
            chosen.production.fetch_facts(
                FinancialFactRequest(
                    FinancialSubjectKind.SECURITY,
                    "WMT",
                    F.COMMON_SHARES_OUTSTANDING,
                    SEC_PROVIDER_ID,
                    basis="fiscal_year_end",
                    as_of=boundary,
                ),
                effective_as_of=boundary,
            )
        series = chosen.production.fetch_instant_series(
            InstantSeriesRequest("WMT", F.TOTAL_ASSETS, SEC_PROVIDER_ID, (date(2023, 1, 31),), as_of=boundary),
            effective_as_of=boundary,
        )
    assert str(raised.value) == adapter_message
    assert [absence.detail for absence in series.absences] == [adapter_message]
    assert [absence.reason for absence in series.absences] == [InstantAbsenceReason.AFTER_BOUNDARY]


def test_an_after_boundary_balance_sheet_answer_is_returned_once_and_no_further_field_is_requested() -> None:
    class AfterBoundary(FactsStub):
        def fetch_instant_series(self, request: Any, *, effective_as_of: datetime) -> InstantSeriesFacts:  # noqa: ARG002
            self.series_requests.append(request)
            return InstantSeriesFacts(
                absences=(
                    InstantAbsence(request.period_ends[0], InstantAbsenceReason.AFTER_BOUNDARY, "after the boundary."),
                )
            )

    stub = AfterBoundary()
    anchor = AnchorYearEnd(date(2026, 1, 31), "0000000001-26-000001", "10-K", date(2026, 3, 13), {})
    outcome = resolve_balance_sheet_values(
        InputResolver(stub, clock=lambda: LIVE_NOW),
        anchor=anchor,
        ticker="WMT",
        fields=[F.TOTAL_ASSETS, F.CASH_AND_EQUIVALENTS, F.CURRENT_ASSETS],
        as_of=None,
    )
    unavailable = _unavailable(outcome)
    assert (unavailable.reason_code, unavailable.reason) == (ReasonCode.NOT_AVAILABLE_AS_OF, "after the boundary.")
    assert len(stub.series_requests) == 1


def test_case_a_a_registrant_with_no_annual_report_is_the_typed_failure_with_its_provider_failure_record() -> None:
    document = load("WMT")
    document["submissions"]["filings"]["recent"]["form"] = ["8-K", "8-K", "8-K"]
    companyfacts = {"cik": document["cik"], "entityName": "X", "facts": {"us-gaap": {}}}
    chosen = rig("WMT", fetcher=FixtureFetcher("WMT", submissions=document["submissions"], companyfacts=companyfacts))
    with anchor_year_end_scope(chosen.resolver, ticker="WMT", as_of=None) as outcome:
        assert isinstance(outcome, MetricInputsFailure)
    assert outcome.input_name == "anchor_year_end"
    assert outcome.provider_failure == ProviderFailureRecord(
        ProviderFailureKind.NO_DATA, SEC_PROVIDER_ID, "anchor_year_end"
    )
    assert "has filed no annual report" in outcome.reason
    assert outcome.reason_code is ReasonCode.PROVIDER_ERROR
    assert chosen.production.fact_requests == []


# --- a provider failure is returned typed on every input family, never raised (N5) --------------------------------


def _run(chosen: Rig, splits: SplitStub, *, as_of: datetime | None) -> Any:
    with _scoped(chosen, "JPM", as_of) as anchor:
        return resolve_market_cap_inputs(
            chosen.resolver,
            splits,
            chosen.production,
            anchor=anchor,
            ticker="JPM",
            filing_currency="USD",
            quote_provider_id="yfinance",
            as_of=as_of,
            use_cache=False,
        )


def _failure(value: object, input_name: str, kind: ProviderFailureKind, provider: str) -> None:
    assert isinstance(value, MetricInputsFailure)
    assert value.input_name == input_name
    assert value.provider_failure == ProviderFailureRecord(kind, provider, input_name)
    assert value.reason_code is ReasonCode.PROVIDER_ERROR


def test_a_share_count_failure_is_returned_not_raised() -> None:
    stub = FactsStub(error=unreachable("sec_edgar"))
    resolver = InputResolver(stub, clock=lambda: LIVE_NOW)
    anchor = AnchorYearEnd(date(2025, 12, 31), "0000000001-26-000001", "10-K", date(2026, 2, 13), {})
    outcome = resolve_market_cap_inputs(
        resolver,
        SplitStub(captured_history("wmt")),
        _Affirming(),
        anchor=anchor,
        ticker="JPM",
        filing_currency="USD",
        quote_provider_id="yfinance",
        as_of=None,
        use_cache=False,
    )
    _failure(outcome, "common_shares_outstanding", ProviderFailureKind.UNREACHABLE, "sec_edgar")


def test_a_listing_check_failure_is_returned_not_raised() -> None:
    chosen = rig("JPM", quotes=FactsStub(quote=_QUOTE), cover=unreachable())
    outcome = _run(chosen, SplitStub(captured_history("wmt")), as_of=None)
    _failure(outcome, "listing_check", ProviderFailureKind.UNREACHABLE, "sec_edgar")


def test_a_quote_failure_is_returned_not_raised() -> None:
    chosen = rig("JPM", quotes=FactsStub(error=unreachable("yfinance")))
    outcome = _run(chosen, SplitStub(captured_history("wmt")), as_of=None)
    _failure(outcome, "price", ProviderFailureKind.UNREACHABLE, "yfinance")


@pytest.mark.parametrize("as_of", [None, datetime(2026, 6, 30, tzinfo=UTC)])
def test_a_split_history_failure_is_returned_not_raised(as_of: datetime | None) -> None:
    chosen = rig("JPM", quotes=FactsStub(quote=_QUOTE))
    outcome = _run(chosen, SplitStub(error=fetch_error()), as_of=as_of)
    _failure(outcome, "price", ProviderFailureKind.RATE_LIMITED, "yfinance")


def test_an_unclassified_failure_is_returned_with_no_record() -> None:
    values = _annual(FactsStub(error=FinancialProviderError("odd")), F.SALES)
    assert isinstance(values, MetricInputsFailure)
    assert values.provider_failure is None


def test_a_balance_sheet_failure_is_returned_not_raised() -> None:
    stub = FactsStub(error=unreachable())
    anchor = AnchorYearEnd(date(2025, 12, 31), "0000000001-26-000001", "10-K", date(2026, 2, 13), {})
    outcome = resolve_balance_sheet_values(
        InputResolver(stub, clock=lambda: LIVE_NOW),
        anchor=anchor,
        ticker="JPM",
        fields=[F.TOTAL_ASSETS, F.CURRENT_ASSETS],
        as_of=None,
    )
    _failure(outcome, "total_assets", ProviderFailureKind.UNREACHABLE, "sec_edgar")
    assert len(stub.series_requests) == 1  # no later field is requested after a failure


def test_an_annual_failure_is_returned_not_raised() -> None:
    _failure(_annual(FactsStub(error=unreachable()), F.SALES), "sales", ProviderFailureKind.UNREACHABLE, "sec_edgar")


def test_a_transport_failure_when_the_scope_opens_is_returned_typed() -> None:
    class Failing(FixtureFetcher):
        def __call__(self, url: str, **kwargs: Any) -> object:
            if "/submissions/" in url:
                raise unreachable()
            return super().__call__(url, **kwargs)

    chosen = rig("WMT", fetcher=Failing("WMT"))
    with anchor_year_end_scope(chosen.resolver, ticker="WMT", as_of=None) as outcome:
        _failure(outcome, "anchor_year_end", ProviderFailureKind.UNREACHABLE, "sec_edgar")


# --- point in time -----------------------------------------------------------------------------------------------


def test_nothing_after_the_boundary_is_used_apart_from_the_splits_that_undo_the_adjustment() -> None:
    boundary = datetime(2025, 6, 30, tzinfo=UTC)
    chosen = rig("WMT")
    prices = synthetic_history(
        {date(2025, 6, 27): 90.0, date(2025, 7, 1): 95.0},
        events=(SplitEvent(date(2025, 9, 1), 2.0),),
        adjustment_date=date(2026, 10, 26),
    )
    with anchor_year_end_scope(chosen.resolver, ticker="WMT", as_of=boundary) as anchor:
        assert isinstance(anchor, AnchorYearEnd)
        balance = resolve_balance_sheet_values(
            chosen.resolver, anchor=anchor, ticker="WMT", fields=[F.TOTAL_ASSETS], as_of=boundary
        )
        inputs = resolve_market_cap_inputs(
            chosen.resolver,
            SplitStub(prices),
            chosen.production,
            anchor=anchor,
            ticker="WMT",
            filing_currency="USD",
            quote_provider_id="yfinance",
            as_of=boundary,
            use_cache=False,
        )
    assert (anchor.accession, anchor.year_end) == ("0000104169-25-000021", date(2025, 1, 31))
    assert not isinstance(balance, (InputUnavailable, MetricInputsFailure))
    held = balance[F.TOTAL_ASSETS]
    assert isinstance(held, ResolvedInput)
    assert held.available_at is not None
    assert held.available_at <= boundary
    assert isinstance(inputs, MarketCapInputs)
    assert (inputs.price, inputs.price_date) == (90.0, date(2025, 6, 27))  # the 2025-07-01 close is after the boundary
    assert all(request.as_of == boundary for request in chosen.production.fact_requests)
    assert inputs.split_events == (SplitEvent(date(2025, 9, 1), 2.0),)  # a later split only restates the basis
    assert inputs.adjustment_date == date(2026, 10, 26)


def test_the_listing_check_of_a_filing_accepted_after_the_boundary_is_not_used() -> None:
    boundary = datetime(2025, 6, 30, tzinfo=UTC)
    chosen = rig("WMT", quotes=FactsStub(quote=_QUOTE))
    with anchor_year_end_scope(chosen.resolver, ticker="WMT", as_of=boundary) as anchor:
        assert isinstance(anchor, AnchorYearEnd)
        inputs = resolve_market_cap_inputs(
            chosen.resolver,
            SplitStub(synthetic_history({date(2025, 6, 27): 90.0})),
            chosen.production,
            anchor=anchor,
            ticker="WMT",
            filing_currency="USD",
            quote_provider_id="yfinance",
            as_of=boundary,
            use_cache=False,
        )
    assert isinstance(inputs, MarketCapInputs)
    # The cover read is the anchor filing's of 2025-03-14, which was accepted by the boundary; the 2026 cover is not.
    assert all("000010416926000055" not in url for url in chosen.cover_urls)


def test_the_failure_and_the_inputs_validate_themselves() -> None:
    with pytest.raises(ValueError, match="requires an input name"):
        MetricInputsFailure(" ", "x")
    with pytest.raises(ValueError, match="requires an input name"):
        MetricInputsFailure("price", " ")


# --- a renamed ticker reaches the listing check through the assembly (P22) -------------------------------------------

_META_FY2020, _META_FY2025 = "0001326801-21-000014", "0001628280-26-003942"
_META_URL = "https://www.sec.gov/Archives/edgar/data/1326801/{folder}/R1.htm"


class _MetaSec:
    """Meta Platforms' submissions and two captured covers, served as the SEC would; the ticker is the current one."""

    def __init__(self) -> None:
        self.cover_urls: list[str] = []

    def json(self, url: str, **_kwargs: object) -> object:
        if url.endswith("company_tickers.json"):
            return {"0": {"cik_str": 1326801, "ticker": "META", "title": "Meta Platforms, Inc."}}
        if "/companyfacts/" in url:
            return {"cik": 1326801, "entityName": "Meta", "facts": {"us-gaap": {}}}
        return {
            "tickers": ["META"],
            "filings": {
                "recent": {
                    "accessionNumber": [_META_FY2025, _META_FY2020],
                    "form": ["10-K", "10-K"],
                    "filingDate": ["2026-01-29", "2021-01-28"],
                    "reportDate": ["2025-12-31", "2020-12-31"],
                    "acceptanceDateTime": ["2026-01-29T00:13:46.000Z", "2021-01-28T02:13:48.000Z"],
                    "primaryDocument": ["a.htm", "b.htm"],
                }
            },
        }

    def cover(self, url: str, **_kwargs: object) -> str:
        self.cover_urls.append(url)
        for accession, name in ((_META_FY2020, "meta_fy2020"), (_META_FY2025, "meta_fy2025")):
            if url == _META_URL.format(folder=accession.replace("-", "")):
                return read_cover(name)
        raise AssertionError(f"unexpected cover {url}")


def test_a_renamed_ticker_is_affirmed_through_the_assembly_by_the_rename_rule() -> None:
    sec = _MetaSec()
    adapter = SecEdgarFinancialFactsAdapter(
        json_fetcher=sec.json, cover_fetcher=sec.cover, clock=lambda: LIVE_NOW, user_agent="Synthetic test"
    )
    production = ProductionFinancialFactsProvider(sec_edgar=adapter, yfinance=FactsStub())
    resolver = InputResolver(production, clock=lambda: LIVE_NOW)
    boundary = datetime(2021, 6, 1, tzinfo=UTC)
    prices = synthetic_history({date(2021, 5, 28): 330.0}, adjustment_date=date(2026, 10, 26))
    with anchor_year_end_scope(resolver, ticker="META", as_of=boundary) as anchor:
        assert isinstance(anchor, AnchorYearEnd)
        inputs = resolve_market_cap_inputs(
            resolver,
            SplitStub(prices),
            production,
            anchor=anchor,
            ticker="META",
            filing_currency="USD",
            quote_provider_id="yfinance",
            as_of=boundary,
            use_cache=False,
        )
    assert (anchor.accession, anchor.year_end) == (_META_FY2020, date(2020, 12, 31))
    assert isinstance(inputs, MarketCapInputs)
    assert inputs.listing_check.affirmed
    rename = inputs.listing_check.rename
    assert rename is not None
    assert (rename.anchor_symbol, rename.latest_symbol) == ("FB", "META")
    assert (rename.anchor_accession, rename.latest_accession) == (_META_FY2020, _META_FY2025)
    assert len(sec.cover_urls) == 2  # the anchor cover, then the latest annual cover, each once


# --- the remaining branches of the assembly -------------------------------------------------------------------


def test_a_year_end_capability_that_fails_is_returned_typed() -> None:
    class Failing(FactsStub):
        def resolve_anchor_year_end(self, request: Any) -> Any:  # noqa: ARG002
            raise unreachable()

    resolver = InputResolver(Failing(), clock=lambda: LIVE_NOW)
    with anchor_year_end_scope(resolver, ticker="WMT", as_of=None) as outcome:
        _failure(outcome, "anchor_year_end", ProviderFailureKind.UNREACHABLE, "sec_edgar")


def test_a_year_end_count_with_no_accession_in_its_provenance_is_unavailable() -> None:
    stub = FactsStub(counts={_YEAR_END_BASIS: (1_000.0, date(2025, 12, 31), None)})
    anchor = AnchorYearEnd(
        date(2025, 12, 31), "0000000001-26-000001", "10-K", date(2026, 2, 13), {"x": date(2026, 2, 13)}
    )
    outcome = resolve_market_cap_inputs(
        InputResolver(stub, clock=lambda: LIVE_NOW),
        SplitStub(captured_history("wmt")),
        _Affirming(),
        anchor=anchor,
        ticker="JPM",
        filing_currency="USD",
        quote_provider_id="yfinance",
        as_of=None,
        use_cache=False,
    )
    assert isinstance(outcome, MarketCapInputs)
    assert "not in the submissions data" in _unavailable(outcome.share_count).reason


def test_a_cover_page_count_failure_is_returned_not_raised() -> None:
    stub = FactsStub(error_basis=COVER_PAGE_BASIS)
    anchor = AnchorYearEnd(date(2025, 12, 31), "0000000001-26-000001", "10-K", date(2026, 2, 13), {})
    outcome = resolve_market_cap_inputs(
        InputResolver(stub, clock=lambda: LIVE_NOW),
        SplitStub(captured_history("wmt")),
        _Affirming(),
        anchor=anchor,
        ticker="JPM",
        filing_currency="USD",
        quote_provider_id="yfinance",
        as_of=None,
        use_cache=False,
    )
    _failure(outcome, "common_shares_outstanding", ProviderFailureKind.UNREACHABLE, "sec_edgar")


# --- an anchor found on the extra submissions pages ----------------------------------------------------------------


def test_a_boundary_before_the_newest_annual_filing_uses_the_anchor_found_on_the_pages() -> None:
    boundary = datetime(2025, 6, 30, tzinfo=UTC)
    prices = synthetic_history({date(2025, 6, 27): 290.0}, adjustment_date=date(2026, 10, 26))
    inputs, chosen, _ = _inputs("JPM", as_of=boundary, history=SplitStub(prices))
    prior = "0000019617-25-000270"
    assert (inputs.year_end, inputs.form) == (date(2024, 12, 31), "10-K")
    assert inputs.listing_check.affirmed
    assert any(prior.replace("-", "") in url for url in chosen.cover_urls)
    count = _count(inputs)
    assert count.observation_period_end is not None
    assert count.observation_period_end.date() == date(2024, 12, 31)
    # The filing date of the count's source filing is looked up on the page, so the count is scaled from it.
    assert inputs.share_count_filing_date == date(2025, 2, 14)
    assert inputs.share_count_basis is ShareCountBasis.YEAR_END
