"""Market capitalization: the refusals, the share-count rule and the split scaling."""

import json
import math
from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from investment_analysis_engine.analysis.shared.market_cap import (
    ListingCheck,
    MarketCapEvidence,
    ShareCountBasis,
    compute_market_cap,
)
from investment_analysis_engine.analysis.shared.metric_evidence import InputUnavailable
from investment_analysis_engine.core.metric_result import MetricStatus, ReasonCode
from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.data.market_data import SplitEvent
from tests.analysis.shared._issuer_inputs import share_count, synthetic, year_end

_FIXTURES = PACKAGE_ROOT / "evaluation" / "fixtures" / "sec_edgar" / "split_history"
_ADJUSTED = date(2026, 10, 26)
_AFFIRMED = ListingCheck(affirmed=True, accession="0000000000-26-000001")
_NVIDIA_YEAR_END = date(2024, 1, 28)


def _events(name: str) -> tuple[SplitEvent, ...]:
    document: dict[str, Any] = json.loads((_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return tuple(SplitEvent(date.fromisoformat(day), ratio) for day, ratio in document["events"])


def _close(name: str, day: str) -> float:
    document: dict[str, Any] = json.loads((_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return float(dict(document["close"])[day])


def _cap(**changes: Any) -> MarketCapEvidence:
    arguments: dict[str, Any] = {
        "year_end": date(2025, 12, 31),
        "form": "10-K",
        "filing_currency": "USD",
        "quote_currency": "USD",
        "listing_check": _AFFIRMED,
        "share_count": synthetic("common_shares_outstanding", 1_000.0),
        "share_count_basis": ShareCountBasis.YEAR_END,
        "share_count_filing_date": date(2026, 2, 10),
        "price": 20.0,
        "price_date": date(2025, 12, 31),
        "split_events": (),
        "adjustment_date": _ADJUSTED,
    }
    arguments.update(changes)
    return compute_market_cap(**arguments)


def _ok(evidence: MarketCapEvidence) -> float:
    assert evidence.result.status is MetricStatus.OK
    assert evidence.result.value is not None
    assert math.isfinite(evidence.result.value)
    assert evidence.result.reason_code is None
    assert evidence.result.reason is None
    return evidence.result.value


def _refused(evidence: MarketCapEvidence, code: ReasonCode, status: MetricStatus = MetricStatus.UNAVAILABLE) -> None:
    assert evidence.result.status is status
    assert evidence.result.value is None
    assert evidence.result.reason_code is code
    assert evidence.result.reason is not None
    assert evidence.result.reason.strip()


def test_market_cap_is_the_count_times_the_price_and_records_what_it_used() -> None:
    count = synthetic("common_shares_outstanding", 1_000.0)
    evidence = _cap(share_count=count)
    assert _ok(evidence) == 20_000.0
    assert evidence.share_count is count
    assert evidence.share_count_basis is ShareCountBasis.YEAR_END
    assert evidence.share_count_date == date(2025, 12, 31)
    assert evidence.share_count_filing_date == date(2026, 2, 10)
    assert (evidence.scaled_share_count, evidence.splits_applied) == (1_000.0, ())
    assert (evidence.price, evidence.price_date) == (20.0, date(2025, 12, 31))
    assert (evidence.form, evidence.filing_currency, evidence.quote_currency) == ("10-K", "USD", "USD")
    assert evidence.listing_check is _AFFIRMED


# --- the refusals of the fail-closed rule -------------------------------------------------------------------------


@pytest.mark.parametrize("form", ["20-F", "40-F", "10-K/A", "10-Q"])
def test_a_filing_other_than_a_10k_is_incompatible_scope(form: str) -> None:
    _refused(_cap(form=form), ReasonCode.INCOMPATIBLE_SCOPE)


def test_sap_a_20f_filer_in_euro_with_a_dollar_adr_is_incompatible_scope_through_its_form() -> None:
    sap = share_count("SAP", "cover_page")
    assert sap is not None
    evidence = _cap(
        year_end=year_end("SAP"),
        form="20-F",
        filing_currency="EUR",
        quote_currency="USD",
        share_count=sap,
        share_count_basis=ShareCountBasis.COVER_PAGE,
    )
    _refused(evidence, ReasonCode.INCOMPATIBLE_SCOPE)


@pytest.mark.parametrize(("filing", "quote"), [("EUR", "USD"), (None, "USD"), ("USD", None), (None, None), ("", "USD")])
def test_a_currency_mismatch_or_an_unknown_currency_is_incompatible_currency(
    filing: str | None, quote: str | None
) -> None:
    _refused(_cap(filing_currency=filing, quote_currency=quote), ReasonCode.INCOMPATIBLE_CURRENCY)


def test_currencies_are_compared_without_regard_to_case() -> None:
    assert _ok(_cap(filing_currency="usd", quote_currency=" USD ")) == 20_000.0


@pytest.mark.parametrize(
    ("code", "reason"),
    [
        (ReasonCode.INCOMPATIBLE_UNITS, "The ticker is listed on depositary shares."),
        (ReasonCode.MISSING_FACT, "The cover could not be read."),
    ],
)
def test_a_refused_listing_check_gives_the_checks_own_code_and_reason(code: ReasonCode, reason: str) -> None:
    check = ListingCheck(affirmed=False, accession=None, reason_code=code, reason=reason)
    evidence = _cap(listing_check=check)
    _refused(evidence, code)
    assert evidence.result.reason == reason
    assert evidence.listing_check is check


def test_the_listing_check_validates_its_own_fields() -> None:
    with pytest.raises(ValueError, match="accession"):
        ListingCheck(affirmed=True)
    with pytest.raises(ValueError, match="no reason"):
        ListingCheck(affirmed=True, accession="a", reason="why")
    with pytest.raises(ValueError, match="reason code"):
        ListingCheck(affirmed=False, reason="why")
    with pytest.raises(ValueError, match="reason code"):
        ListingCheck(affirmed=False, reason_code=ReasonCode.MISSING_FACT, reason=" ")


def test_the_form_is_checked_before_the_currency_and_the_currency_before_the_listing() -> None:
    refused = ListingCheck(affirmed=False, reason_code=ReasonCode.INCOMPATIBLE_UNITS, reason="depositary share")
    _refused(_cap(form="20-F", filing_currency="EUR", listing_check=refused), ReasonCode.INCOMPATIBLE_SCOPE)
    _refused(_cap(filing_currency="EUR", listing_check=refused), ReasonCode.INCOMPATIBLE_CURRENCY)


# --- the inputs that are absent -----------------------------------------------------------------------------------


@pytest.mark.parametrize("code", [ReasonCode.MISSING_FACT, ReasonCode.AMBIGUOUS_FACT])
def test_no_share_count_takes_the_inputs_own_code(code: ReasonCode) -> None:
    unavailable = InputUnavailable(code, "no unambiguous count")
    evidence = _cap(share_count=unavailable)
    _refused(evidence, code)
    assert evidence.result.reason == "no unambiguous count"
    assert evidence.share_count is None


def test_no_price_takes_the_inputs_own_code_and_keeps_the_count() -> None:
    count = synthetic("common_shares_outstanding", 1_000.0)
    evidence = _cap(share_count=count, price=InputUnavailable(ReasonCode.PROVIDER_ERROR, "quote failed"))
    _refused(evidence, ReasonCode.PROVIDER_ERROR)
    assert evidence.share_count is count


def test_a_price_or_count_that_is_not_positive_is_an_invalid_request() -> None:
    for changes in ({"price": 0.0}, {"price": -1.0}, {"price": float("nan")}, {"price": float("inf")}):
        _refused(_cap(**changes), ReasonCode.INVALID_REQUEST, MetricStatus.NOT_APPLICABLE)
    _refused(
        _cap(share_count=synthetic("common_shares_outstanding", -5.0)),
        ReasonCode.INVALID_REQUEST,
        MetricStatus.NOT_APPLICABLE,
    )


def test_an_overflowing_market_cap_is_not_a_number() -> None:
    evidence = _cap(share_count=synthetic("common_shares_outstanding", 1.7e308), price=10.0)
    _refused(evidence, ReasonCode.INVALID_REQUEST, MetricStatus.NOT_APPLICABLE)


# --- the share-count rule -----------------------------------------------------------------------------------------


def test_nutriens_ifrs_count_is_for_the_year_before_the_year_end_so_it_is_incompatible_period() -> None:
    count = share_count("NTR", "fiscal_year_end")
    assert count is not None
    assert count.observation_period_end is not None
    assert count.observation_period_end.date() == date(2024, 12, 31)
    evidence = _cap(year_end=year_end("NTR"), form="40-F", share_count=count)
    # The form refuses first; with a 10-K filer the date is what refuses.
    _refused(evidence, ReasonCode.INCOMPATIBLE_SCOPE)
    _refused(_cap(year_end=year_end("NTR"), share_count=count), ReasonCode.INCOMPATIBLE_PERIOD)


def test_a_year_end_count_dated_after_the_year_end_is_incompatible_period_too() -> None:
    _refused(_cap(year_end=date(2025, 6, 30)), ReasonCode.INCOMPATIBLE_PERIOD)


def test_a_count_without_a_date_is_incompatible_period() -> None:
    undated = replace(synthetic("common_shares_outstanding", 1_000.0), observation_period_end=None)
    _refused(_cap(share_count=undated), ReasonCode.INCOMPATIBLE_PERIOD)


def test_alphabets_one_combined_count_is_valued_at_the_requested_tickers_price() -> None:
    combined = share_count("GOOGL", "fiscal_year_end")
    assert combined is not None
    evidence = _cap(year_end=year_end("GOOGL"), share_count=combined, price=200.0)
    # 12,088 million shares x 200.
    assert _ok(evidence) == 2_417_600_000_000.0
    assert evidence.share_count_date == date(2025, 12, 31)


def test_per_class_counts_with_no_total_arrive_as_an_unavailable_count() -> None:
    unavailable = InputUnavailable(ReasonCode.MISSING_FACT, "Only per-class counts are reported.")
    _refused(_cap(share_count=unavailable), ReasonCode.MISSING_FACT)


def test_walmart_uses_its_cover_page_count_dated_after_the_year_end() -> None:
    count = share_count("WMT", "cover_page")
    assert count is not None
    evidence = _cap(
        year_end=year_end("WMT"),
        share_count=count,
        share_count_basis=ShareCountBasis.COVER_PAGE,
        share_count_filing_date=date(2026, 3, 13),
        price=100.0,
    )
    assert _ok(evidence) == 7_972_402_501.0 * 100.0
    assert evidence.share_count_basis is ShareCountBasis.COVER_PAGE
    assert evidence.share_count_date == date(2026, 3, 11)


# --- the split scaling --------------------------------------------------------------------------------------------


def test_nvidia_the_count_scaled_by_the_june_split_gives_the_market_cap_of_the_unadjusted_figures() -> None:
    events = _events("nvda")
    adjusted_close = _close("nvda", "2024-04-30")
    count = synthetic("common_shares_outstanding", 2_464_000_000.0, day=_NVIDIA_YEAR_END)
    evidence = _cap(
        year_end=_NVIDIA_YEAR_END,
        share_count=count,
        share_count_filing_date=date(2024, 2, 21),
        price=adjusted_close,
        price_date=date(2024, 4, 30),
        split_events=events,
    )
    assert evidence.scaled_share_count == 24_640_000_000.0
    assert evidence.splits_applied == (SplitEvent(date(2024, 6, 10), 10.0),)
    assert adjusted_close == pytest.approx(86.402, abs=1e-3)
    # 86.402 x 24,640,000,000 equals 864.02 x 2,464,000,000.
    assert _ok(evidence) == pytest.approx(864.02 * 2_464_000_000, rel=1e-6)
    assert _ok(evidence) == pytest.approx(2_128_945_280_000, rel=1e-6)


def test_walmart_fiscal_2024_a_count_from_a_filing_after_its_split_is_not_scaled_again() -> None:
    events = _events("wmt")
    restated = synthetic("common_shares_outstanding", 2_690_000_000.0 * 3, day=date(2024, 1, 31))
    common: dict[str, Any] = {
        "year_end": date(2024, 1, 31),
        "share_count": restated,
        "price": 60.0,
        "price_date": date(2024, 3, 15),
        "split_events": events,
    }
    after_the_split = _cap(share_count_filing_date=date(2024, 3, 15), **common)
    assert _ok(after_the_split) == 2_690_000_000.0 * 3 * 60.0
    assert after_the_split.splits_applied == ()
    # Negative case: scaling from the year-end counts the split twice and gives three times the value.
    from_the_year_end = _cap(share_count_filing_date=date(2024, 1, 31), **common)
    assert _ok(from_the_year_end) == 3 * _ok(after_the_split)
    assert from_the_year_end.splits_applied == events


def test_a_cover_page_count_dated_after_the_filings_split_date_is_scaled_and_one_before_is_not() -> None:
    split = SplitEvent(date(2024, 6, 10), 10.0)
    common: dict[str, Any] = {
        "share_count_basis": ShareCountBasis.COVER_PAGE,
        "share_count_filing_date": date(2024, 2, 21),
        "split_events": (split,),
        "year_end": date(2024, 1, 28),
    }
    before = _cap(share_count=synthetic("shares", 100.0, day=date(2024, 6, 9)), **common)
    after = _cap(share_count=synthetic("shares", 100.0, day=date(2024, 6, 10)), **common)
    # A cover dated on the ex-date already reflects the split; one a day earlier does not.
    assert (_ok(before), before.splits_applied) == (100.0 * 10.0 * 20.0, (split,))
    assert (_ok(after), after.splits_applied) == (100.0 * 20.0, ())


def test_a_cover_count_is_scaled_from_its_own_date_not_the_filing_date() -> None:
    split = SplitEvent(date(2024, 3, 1), 2.0)
    evidence = _cap(
        share_count=synthetic("shares", 100.0, day=date(2024, 3, 5)),
        share_count_basis=ShareCountBasis.COVER_PAGE,
        share_count_filing_date=date(2024, 2, 1),
        split_events=(split,),
        year_end=date(2023, 12, 31),
    )
    assert _ok(evidence) == 100.0 * 20.0
    assert evidence.splits_applied == ()


def test_a_split_after_the_price_date_still_scales_the_count_up_to_the_adjustment_date() -> None:
    split = SplitEvent(date(2026, 3, 5), 2.0)
    evidence = _cap(split_events=(split,), price=10.0)
    assert _ok(evidence) == 1_000.0 * 2.0 * 10.0
    assert _ok(_cap(split_events=(split,), adjustment_date=date(2026, 3, 4))) == 20_000.0
