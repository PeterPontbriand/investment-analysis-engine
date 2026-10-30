"""The inputs the shared metrics need, assembled once for an issuer and a boundary.

Functions, one per input family: the anchor fiscal year-end *t*; the market-cap inputs at *t*; balance-sheet values
and annual values at one or several named year-ends; the industry class. Each takes the dependencies a consumer's
analyzer received at construction (the ``InputResolver``, the split-history client, the cover-listing capability and the
as-filed SIC source) and holds no state. Every input is the evidence of the registrant the ticker names, as filed or
priced at the boundary.

A provider failure is never raised out of these functions. It is returned as a ``MetricInputsFailure`` carrying the
provider-failure record, and a consumer calls no metric after one. An input that is merely unavailable is returned as
its reason, so a metric can report it. The registrant whose annual filings all came after the boundary is returned once
by ``anchor_year_end_scope`` as unavailable with ``not_available_as_of`` and the adapter's message; no function that
needs the year-end can be called after it. A registrant with no annual report at all is a provider failure raised when
the analysis scope opens, and the same function returns it as a ``MetricInputsFailure``.
"""

from collections.abc import Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Protocol

from investment_analysis_engine.analysis.shared.applicability import IndustryClass, industry_class_of_sic
from investment_analysis_engine.analysis.shared.financial_resolution import resolve_optional_quote
from investment_analysis_engine.analysis.shared.market_cap import (
    ANCHOR_FILING_FORMS,
    ListingCheck,
    MarketCapEvidence,
    ShareCountBasis,
    compute_market_cap,
    listing_check_from_resolution,
)
from investment_analysis_engine.analysis.shared.metric_evidence import (
    AnnualValue,
    BalanceSheetValue,
    InputUnavailable,
    absence_reason_code,
)
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureRecord
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import (
    ANNUAL_PERIOD_FIELDS,
    COVER_PAGE_BASIS,
    SHARE_COUNT_SERIES_FIELD,
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    InstantAbsence,
    InstantAbsenceReason,
    InstantSeriesRequest,
    financial_facts_analysis_scope,
)
from investment_analysis_engine.data.financial.provenance import (
    FinancialSubjectKind,
    ResolvedInput,
)
from investment_analysis_engine.data.financial.resolver import (
    AnnualSeriesResolution,
    InputResolutionResult,
    InputResolver,
    InstantSeriesResolution,
    LeftOutObservation,
    LeftOutReason,
)
from investment_analysis_engine.data.market_data import (
    DatedSplitAdjustedHistoryProvider,
    NoEligibleObservationsError,
    SplitAdjustedHistory,
    SplitEvent,
    SplitHistoryEndsBeforeRequestError,
    split_adjusted_close_on_or_before,
)
from investment_analysis_engine.data.provider_failure import failure_record
from investment_analysis_engine.data.sec_edgar.cover_listing import CoverListingProvider, CoverListingRequest
from investment_analysis_engine.data.sec_edgar.filing_header import AsFiledSicResolution
from investment_analysis_engine.data.sec_edgar.financial_facts import (
    SEC_PROVIDER_ID,
    AnchorYearEnd,
    AnchorYearEndProvider,
    AnchorYearEndRequest,
    AnchorYearEndUnavailableReason,
)

SPLIT_HISTORY_MARGIN_DAYS: Final = 10
"""Calendar days the split-history request starts before the date the share count is scaled from.

A count is scaled by the splits after its source date, and the price is the close of the last session on or before the
boundary. The margin keeps the last session before a source date that falls on a weekend or a holiday inside the
requested range.
"""

_YEAR_END_BASIS = "fiscal_year_end"
_ANNUAL_BASIS = "fiscal_year"
_ASSEMBLED_ANNUAL_FIELDS = ANNUAL_PERIOD_FIELDS | {FinancialField.OPERATING_CASH_FLOW}

YEAR_END_START_FIELDS: Final = (
    FinancialField.NET_INCOME,
    FinancialField.SALES,
    FinancialField.OPERATING_CASH_FLOW,
)
"""The completed-annual fields whose period start dates give the year-ends before the anchor, in priority order.

Every listed field that reports a year must give the same start date for it. Two fields are the least that lets a
disagreement be seen, and three keep a year-end available when one is not tagged (Monster tags no net income). All
three agreed on every year of every captured issuer (``STEP_3_5_3_INPUT_EVIDENCE.md``).
"""

YEAR_LENGTH_DAYS: Final = (335, 395)
"""The least and most days between a derived year-end and the later year-end for the year to count as a fiscal year.

These are the bounds of the completed-annual duration tolerance, the same ones consecutive year-ends must meet.
"""


@dataclass(frozen=True)
class MetricInputsFailure:
    """A provider failure while assembling one input, returned instead of raised.

    Attributes:
        input_name: The input that failed.
        reason: A non-empty explanation.
        provider_failure: The kind and provider of the failure, with ``input`` set to ``input_name``; ``None`` for a
            failure the adapter did not classify or a provider answer the resolver rejected.
    """

    input_name: str
    reason: str
    provider_failure: ProviderFailureRecord | None = None

    def __post_init__(self) -> None:
        """Require an input name and an explanation."""
        if not self.input_name.strip() or not self.reason.strip():
            raise ValueError("A metric-inputs failure requires an input name and a reason.")

    @property
    def reason_code(self) -> ReasonCode:
        """Return the code a dependent metric reports: always ``provider_error``."""
        return ReasonCode.PROVIDER_ERROR


class ShareCountPath(StrEnum):
    """How a year-end common share count was obtained."""

    DIRECT = "direct"
    ISSUED_LESS_TREASURY = "issued_less_treasury"


@dataclass(frozen=True)
class YearEndShareCount:
    """A common share count at a fiscal year-end with the filing and the path it came from.

    Attributes:
        count: The resolved count, with its provenance.
        accession: The accession of the one filing the count was taken from.
        path: Whether the count is reported directly or is issued shares less treasury shares.
    """

    count: ResolvedInput
    accession: str
    path: ShareCountPath

    def __post_init__(self) -> None:
        """Require an accession."""
        if not self.accession.strip():
            raise ValueError("A share count requires the accession of the filing it came from.")


@dataclass(frozen=True)
class MarketCapInputs:
    """Everything ``compute_market_cap`` takes, each input or the reason it is unavailable.

    When the anchor form refuses market cap the cover is not read, and the listing check says so; the pure function
    refuses by form first and does not read it. When no price is available the adjustment date is not used by the
    pure function.
    """

    year_end: date
    form: str
    filing_currency: str | None
    quote_currency: str | None
    listing_check: ListingCheck
    share_count: ResolvedInput | InputUnavailable
    share_count_basis: ShareCountBasis
    share_count_filing_date: date
    price: float | InputUnavailable
    price_date: date | None
    split_events: tuple[SplitEvent, ...]
    adjustment_date: date

    def market_cap(self) -> MarketCapEvidence:
        """Return market capitalization at the boundary, or why it is ``unavailable``."""
        return compute_market_cap(
            year_end=self.year_end,
            form=self.form,
            filing_currency=self.filing_currency,
            quote_currency=self.quote_currency,
            listing_check=self.listing_check,
            share_count=self.share_count,
            share_count_basis=self.share_count_basis,
            share_count_filing_date=self.share_count_filing_date,
            price=self.price,
            price_date=self.price_date,
            split_events=self.split_events,
            adjustment_date=self.adjustment_date,
        )


@dataclass(frozen=True)
class _ShareCount:
    """The share count the assembly chose, the basis it is on and the date its splits are counted from."""

    count: ResolvedInput | InputUnavailable
    basis: ShareCountBasis
    filing_date: date
    scaled_from: date | None


@dataclass(frozen=True)
class _Price:
    """The price with its date, currency and the split history it is on the basis of."""

    price: float | InputUnavailable
    price_date: date | None
    quote_currency: str | None
    events: tuple[SplitEvent, ...]
    adjustment_date: date


def _failure(input_name: str, error: DataFetchError | FinancialProviderError) -> MetricInputsFailure:
    """Return the typed failure of a classified provider error."""
    record = failure_record(error)
    return MetricInputsFailure(
        input_name, f"Provider error: {error}", None if record is None else record.for_input(input_name)
    )


def _resolution_failure(input_name: str, result: InputResolutionResult) -> MetricInputsFailure:
    """Return the typed failure of a resolution that is neither ``OK`` nor ``INPUT_UNAVAILABLE``."""
    record = result.provider_failure
    return MetricInputsFailure(
        input_name,
        result.reason or "The provider's answer was rejected.",
        None if record is None else record.for_input(input_name),
    )


def _unavailable_year_end(reason: AnchorYearEndUnavailableReason, message: str) -> InputUnavailable:
    """Return the unavailable year-end: ``not_available_as_of`` when every annual filing came after the boundary."""
    code = (
        ReasonCode.NOT_AVAILABLE_AS_OF
        if reason is AnchorYearEndUnavailableReason.ACCEPTED_AFTER_BOUNDARY
        else ReasonCode.MISSING_FACT
    )
    return InputUnavailable(code, message)


@contextmanager
def anchor_year_end_scope(
    resolver: InputResolver, *, ticker: str, as_of: datetime | None
) -> Iterator[AnchorYearEnd | InputUnavailable | MetricInputsFailure]:
    """Open the SEC analysis scope for ``ticker`` and yield the anchor fiscal year-end *t*, found once for the scope.

    Every other function of this module is called inside the ``with`` block with the yielded ``AnchorYearEnd``, so
    every input is taken at the same *t* from one snapshot of the provider's data.

    Yields:
        The ``AnchorYearEnd``; an ``InputUnavailable`` when there is none (``not_available_as_of`` with the adapter's
        message for a registrant whose annual filings all came after the boundary, otherwise ``missing_fact``); or a
        ``MetricInputsFailure`` when the registrant has no annual report at all or the provider failed. After the last
        two the block must not call another function of this module.
    """
    subject = ticker.strip().upper()
    scope = financial_facts_analysis_scope(
        resolver.provider, subject_id=subject, provider_id=SEC_PROVIDER_ID, as_of=as_of
    )
    with ExitStack() as stack:
        try:
            stack.enter_context(scope)
        except FinancialProviderError as exc:
            yield _failure("anchor_year_end", exc)
            return
        yield _anchor_in_scope(resolver, subject)


def _anchor_in_scope(resolver: InputResolver, ticker: str) -> AnchorYearEnd | InputUnavailable | MetricInputsFailure:
    """Return the anchor year-end of the open scope, or why there is none."""
    provider = resolver.provider
    if not isinstance(provider, AnchorYearEndProvider):
        return InputUnavailable(ReasonCode.MISSING_FACT, "The provider does not give the anchor filing's year-end.")
    try:
        resolution = provider.resolve_anchor_year_end(AnchorYearEndRequest(ticker, SEC_PROVIDER_ID))
    except FinancialProviderError as exc:
        return _failure("anchor_year_end", exc)
    if resolution.anchor is not None:
        return resolution.anchor
    assert resolution.reason is not None
    assert resolution.message is not None  # the resolution type guarantees both
    return _unavailable_year_end(resolution.reason, resolution.message)


def _accessions(count: ResolvedInput) -> frozenset[str]:
    """Return the accessions the notes of ``count`` name."""
    return frozenset(
        piece.split("=", 1)[1].strip()
        for note in count.notes
        for piece in note.split(";")
        if piece.strip().startswith("accession=")
    )


def _single_accession(count: ResolvedInput) -> str | None:
    """Return the one accession the notes of ``count`` name, or ``None`` when they name none or several."""
    accessions = _accessions(count)
    return next(iter(accessions)) if len(accessions) == 1 else None


def _source_filing_date(count: ResolvedInput, anchor: AnchorYearEnd) -> date | None:
    """Return the filing date of the one filing a year-end count was taken from, or ``None`` when it is not dated."""
    accession = _single_accession(count)
    return None if accession is None else anchor.filing_dates.get(accession)


def _count_request(ticker: str, basis: str, as_of: datetime | None) -> FinancialFactRequest:
    """Return the request for the common shares outstanding on ``basis``."""
    return FinancialFactRequest(
        FinancialSubjectKind.SECURITY,
        ticker,
        FinancialField.COMMON_SHARES_OUTSTANDING,
        SEC_PROVIDER_ID,
        basis=basis,
        as_of=as_of,
    )


def _resolve_share_count(  # noqa: PLR0911
    resolver: InputResolver, anchor: AnchorYearEnd, *, ticker: str, as_of: datetime | None, use_cache: bool
) -> _ShareCount | MetricInputsFailure:
    """Return the year-end count when it is dated *t*, else the cover-page count, else why there is none.

    The cover-page count is requested only when the year-end count is missing or dated another day. A year-end count
    dated another day with no cover-page count is passed on as it is, so the market-cap function refuses it as
    ``incompatible_period`` and an older year's count is never substituted.
    """
    default_filing_date = anchor.filing_date or anchor.year_end
    year_end = resolver.resolve(_count_request(ticker, _YEAR_END_BASIS, as_of), use_cache=use_cache)
    if year_end.status not in (CalculationStatus.OK, CalculationStatus.INPUT_UNAVAILABLE):
        return _resolution_failure("common_shares_outstanding", year_end)
    held = year_end.resolved_input
    if (
        held is not None
        and held.observation_period_end is not None
        and held.observation_period_end.date() == anchor.year_end
    ):
        filing_date = _source_filing_date(held, anchor)
        if filing_date is None:
            reason = InputUnavailable(
                ReasonCode.MISSING_FACT,
                "The filing date of the filing the year-end share count was taken from is not in the submissions data.",
            )
            return _ShareCount(reason, ShareCountBasis.YEAR_END, default_filing_date, None)
        return _ShareCount(held, ShareCountBasis.YEAR_END, filing_date, filing_date)
    cover = resolver.resolve(_count_request(ticker, COVER_PAGE_BASIS, as_of), use_cache=use_cache)
    if cover.status not in (CalculationStatus.OK, CalculationStatus.INPUT_UNAVAILABLE):
        return _resolution_failure("common_shares_outstanding", cover)
    counted = cover.resolved_input
    if counted is not None:
        cover_date = counted.observation_period_end.date() if counted.observation_period_end is not None else None
        return _ShareCount(counted, ShareCountBasis.COVER_PAGE, default_filing_date, cover_date)
    if held is not None:
        held_date = held.observation_period_end.date() if held.observation_period_end is not None else None
        return _ShareCount(held, ShareCountBasis.YEAR_END, default_filing_date, held_date)
    reason = InputUnavailable(
        ReasonCode.MISSING_FACT,
        f"No share count: the year-end count is unavailable ({year_end.reason}); "
        f"the cover-page count is unavailable ({cover.reason}).",
    )
    return _ShareCount(reason, ShareCountBasis.COVER_PAGE, default_filing_date, None)


def _split_history(  # noqa: PLR0913
    history: DatedSplitAdjustedHistoryProvider,
    ticker: str,
    start: date,
    *,
    use_cache: bool,
    adjusted_on: date | None,
    as_of: date | None,
) -> SplitAdjustedHistory | MetricInputsFailure:
    """Request the split-adjusted history from ``start``, or return its typed failure."""
    try:
        return history.fetch_split_adjusted_history(
            ticker, start.isoformat(), use_cache=use_cache, adjusted_on=adjusted_on, as_of=as_of
        )
    except DataFetchError as exc:
        return _failure("price", exc)


def _price_at_boundary(
    history: DatedSplitAdjustedHistoryProvider, ticker: str, start: date, as_of: datetime, *, use_cache: bool
) -> _Price | MetricInputsFailure:
    """Return the split-adjusted close of the last session on or before ``as_of``, by Momentum's rule (K15).

    A date-only ``--as-of`` includes that day's close: the session is compared with the boundary's UTC calendar date,
    and a session is read by its exchange-local date. The currency is the split-history response's.
    """
    boundary_day = as_of.astimezone(UTC).date()
    response = _split_history(history, ticker, start, use_cache=use_cache, adjusted_on=None, as_of=boundary_day)
    if isinstance(response, MetricInputsFailure):
        return response
    currency = response.context.currency
    try:
        session, close = split_adjusted_close_on_or_before(response, boundary_day)
    except (SplitHistoryEndsBeforeRequestError, NoEligibleObservationsError) as exc:
        unavailable = InputUnavailable(ReasonCode.NOT_AVAILABLE_AS_OF, str(exc))
        return _Price(unavailable, None, currency, response.events, response.adjustment_date)
    return _Price(close, session, currency, response.events, response.adjustment_date)


def _price_now(  # noqa: PLR0913
    resolver: InputResolver,
    history: DatedSplitAdjustedHistoryProvider,
    ticker: str,
    start: date,
    *,
    quote_provider_id: str,
    use_cache: bool,
) -> _Price | MetricInputsFailure:
    """Return the current quote with a split history adjusted on the quote's date (S2).

    The quote is the price: a one-day historical download is never a quote. Its date is its retrieval date, because
    the quote carries no market time, and the currency is the quote's.
    """
    quote = resolve_optional_quote(
        resolver,
        security_subject_id=ticker,
        security_provider_id=quote_provider_id,
        quote_override=None,
        as_of=None,
        use_cache=use_cache,
    )
    if quote.status not in (CalculationStatus.OK, CalculationStatus.INPUT_UNAVAILABLE):
        return _resolution_failure("price", quote)
    held = quote.resolved_input
    if held is None or held.retrieved_at is None:
        reason = InputUnavailable(
            ReasonCode.MISSING_FACT, quote.reason or "The current quote carries no retrieval time."
        )
        return _Price(reason, None, None if held is None else held.currency, (), start)
    quote_day = held.retrieved_at.astimezone(UTC).date()
    response = _split_history(history, ticker, start, use_cache=use_cache, adjusted_on=quote_day, as_of=None)
    if isinstance(response, MetricInputsFailure):
        return response
    if response.adjustment_date != quote_day:
        mismatch = InputUnavailable(
            ReasonCode.INCOMPATIBLE_PERIOD,
            f"The split history was adjusted on {response.adjustment_date}, not on the quote's date {quote_day}.",
        )
        return _Price(mismatch, quote_day, held.currency, response.events, quote_day)
    return _Price(held.value, quote_day, held.currency, response.events, quote_day)


def resolve_market_cap_inputs(  # noqa: PLR0913
    resolver: InputResolver,
    split_history: DatedSplitAdjustedHistoryProvider,
    listing: CoverListingProvider,
    *,
    anchor: AnchorYearEnd,
    ticker: str,
    filing_currency: str | None,
    quote_provider_id: str,
    as_of: datetime | None,
    use_cache: bool,
) -> MarketCapInputs | MetricInputsFailure:
    """Return every input of ``compute_market_cap`` at the anchor year-end, or the provider failure that stopped it.

    The share count is the year-end count when it is dated *t*, else the cover-page count (Shared definitions §4). The
    price is the split-adjusted close of the last session on or before ``as_of`` (K15), or without ``as_of`` the current
    quote, and the split history starts ``SPLIT_HISTORY_MARGIN_DAYS`` before the date the count is scaled from (N7).
    Without ``as_of`` the history is adjusted on the quote's date (S2). The quote currency is the quote's, or with
    ``as_of`` the split-history response's, and the filing currency is the one the consumer found in the monetary facts
    it resolved at *t* (N6).

    Args:
        resolver: Resolves the share counts and the quote.
        split_history: Gives the split-adjusted close and the split history.
        listing: Reads the anchor cover for the listing check of the requested ticker.
        anchor: The anchor year-end of the open scope.
        ticker: The requested ticker.
        filing_currency: The currency of the monetary facts at *t*, ``None`` when unknown.
        quote_provider_id: The provider that gives the current quote.
        as_of: The point-in-time boundary, ``None`` for a current run.
        use_cache: Whether stored responses may be reused.
    """
    subject = ticker.strip().upper()
    check = _listing_check(listing, anchor, subject)
    if isinstance(check, MetricInputsFailure):
        return check
    count = _resolve_share_count(resolver, anchor, ticker=subject, as_of=as_of, use_cache=use_cache)
    if isinstance(count, MetricInputsFailure):
        return count
    start = (count.scaled_from or anchor.year_end) - timedelta(days=SPLIT_HISTORY_MARGIN_DAYS)
    if as_of is None:
        price = _price_now(
            resolver, split_history, subject, start, quote_provider_id=quote_provider_id, use_cache=use_cache
        )
    else:
        price = _price_at_boundary(split_history, subject, start, as_of, use_cache=use_cache)
    if isinstance(price, MetricInputsFailure):
        return price
    return MarketCapInputs(
        year_end=anchor.year_end,
        form=anchor.form,
        filing_currency=filing_currency,
        quote_currency=price.quote_currency,
        listing_check=check,
        share_count=count.count,
        share_count_basis=count.basis,
        share_count_filing_date=count.filing_date,
        price=price.price,
        price_date=price.price_date,
        split_events=price.events,
        adjustment_date=price.adjustment_date,
    )


def _listing_check(
    listing: CoverListingProvider, anchor: AnchorYearEnd, ticker: str
) -> ListingCheck | MetricInputsFailure:
    """Return the listing check of the anchor cover; a form market cap refuses by itself is not worth a request."""
    if anchor.form.strip().upper() not in ANCHOR_FILING_FORMS:
        return ListingCheck(
            affirmed=False,
            reason_code=ReasonCode.INCOMPATIBLE_SCOPE,
            reason=f"The cover was not read: the anchor filing is a {anchor.form}, which market cap refuses by form.",
        )
    try:
        return listing_check_from_resolution(
            listing.resolve_cover_listing(CoverListingRequest(ticker, SEC_PROVIDER_ID))
        )
    except FinancialProviderError as exc:
        return _failure("listing_check", exc)


def _requested_dates(year_ends: Sequence[date]) -> tuple[date, ...]:
    """Return the requested year-ends once each, oldest first, so the request never depends on the caller's order."""
    dates = tuple(sorted(set(year_ends)))
    if not dates:
        raise ValueError("At least one year-end is required.")
    return dates


def _requested_fields(fields: Sequence[FinancialField]) -> tuple[FinancialField, ...]:
    """Return the requested fields once each, in the caller's order.

    The order decides only which failure is reported first when several fields fail, and so which later fields are
    not requested; the values of a successful answer are keyed by field and do not depend on it.
    """
    return tuple(dict.fromkeys(fields))


def _instant_values(resolution: InstantSeriesResolution, dates: tuple[date, ...]) -> dict[date, BalanceSheetValue]:
    """Return each requested date's resolved input or absence from one series resolution.

    A date the answer neither resolves nor lists as absent (or every date, when the provider serves no series) is an
    ``unsupported`` absence carrying the resolution's reason, so a date is never left without a value or a reason.
    """
    resolved = {
        item.observation_period_end.date(): item
        for item in resolution.inputs
        if item.observation_period_end is not None
    }
    absent = {item.period_end: item for item in resolution.absences}
    detail = resolution.reason or "The provider's answer did not cover the year-end."
    return {
        day: resolved.get(day) or absent.get(day) or InstantAbsence(day, InstantAbsenceReason.UNSUPPORTED, detail)
        for day in dates
    }


def resolve_balance_sheet_values_at(
    resolver: InputResolver,
    *,
    ticker: str,
    fields: Sequence[FinancialField],
    year_ends: Sequence[date],
    as_of: datetime | None,
) -> Mapping[FinancialField, Mapping[date, BalanceSheetValue]] | InputUnavailable | MetricInputsFailure:
    """Return each named balance-sheet field at each named year-end: its resolved input or its absence.

    One series request is made per field, for all the year-ends. A field the provider cannot serve is an
    ``InstantAbsence`` of reason ``unsupported`` at every date, and a field the filings do not report at a date is the
    absence the provider gives. An absence because the year-end is after the boundary stays that date's absence, so a
    year filed late does not remove the others; when every requested year-end of a field is after the boundary it is
    the registrant whose annual filings all came after it, and the function returns it once, as
    ``not_available_as_of`` with the provider's message, and requests no further field. The year-ends must be
    consecutive fiscal year-ends within the annual-duration tolerance (``InstantSeriesRequest`` refuses others). A
    year-end is never filled from another, and the values never depend on the order of ``fields`` or ``year_ends``.

    Raises:
        ValueError: If no year-end is requested, a field is not a balance-sheet field, or a field is the share count,
            which is a count of shares and not an amount (``resolve_share_count_series`` serves it).
    """
    dates = _requested_dates(year_ends)
    if SHARE_COUNT_SERIES_FIELD in fields:
        raise ValueError(f"{SHARE_COUNT_SERIES_FIELD.value} is a share count, not a balance-sheet amount.")
    values: dict[FinancialField, Mapping[date, BalanceSheetValue]] = {}
    for name in _requested_fields(fields):
        by_date = _instant_series_by_date(resolver, ticker=ticker, name=name, dates=dates, as_of=as_of)
        if isinstance(by_date, (InputUnavailable, MetricInputsFailure)):
            return by_date
        values[name] = MappingProxyType(by_date)
    return MappingProxyType(values)


def _instant_series_by_date(
    resolver: InputResolver, *, ticker: str, name: FinancialField, dates: tuple[date, ...], as_of: datetime | None
) -> dict[date, BalanceSheetValue] | InputUnavailable | MetricInputsFailure:
    """Return one instant-series field at each date, or the failure, or ``not_available_as_of`` once for every date.

    An absence because a year-end is after the boundary stays that date's absence; when every date is after it, the
    registrant's annual filings all came after the boundary and the provider's message is returned once.
    """
    resolution = resolver.resolve_instant_series(
        InstantSeriesRequest(ticker, name, SEC_PROVIDER_ID, dates, as_of=as_of)
    )
    if resolution.status not in (CalculationStatus.OK, CalculationStatus.INPUT_UNAVAILABLE):
        record = resolution.provider_failure
        return MetricInputsFailure(
            name.value,
            resolution.reason or "The provider's answer was rejected.",
            None if record is None else record.for_input(name.value),
        )
    by_date = _instant_values(resolution, dates)
    late = [
        item
        for item in by_date.values()
        if isinstance(item, InstantAbsence) and item.reason is InstantAbsenceReason.AFTER_BOUNDARY
    ]
    if len(late) == len(dates):
        return InputUnavailable(ReasonCode.NOT_AVAILABLE_AS_OF, late[0].detail)
    return by_date


def resolve_balance_sheet_values(
    resolver: InputResolver,
    *,
    anchor: AnchorYearEnd,
    ticker: str,
    fields: Sequence[FinancialField],
    as_of: datetime | None,
) -> Mapping[FinancialField, BalanceSheetValue] | InputUnavailable | MetricInputsFailure:
    """Return each named balance-sheet field at the anchor year-end: its resolved input or its absence.

    This is ``resolve_balance_sheet_values_at`` for the one year-end *t*; its rules and its raised errors are those
    of that function.
    """
    outcome = resolve_balance_sheet_values_at(
        resolver, ticker=ticker, fields=fields, year_ends=(anchor.year_end,), as_of=as_of
    )
    if isinstance(outcome, (InputUnavailable, MetricInputsFailure)):
        return outcome
    return MappingProxyType({name: outcome[name][anchor.year_end] for name in dict.fromkeys(fields)})


def resolve_annual_values_at(
    resolver: InputResolver,
    *,
    ticker: str,
    fields: Sequence[FinancialField],
    year_ends: Sequence[date],
    as_of: datetime | None,
) -> Mapping[FinancialField, Mapping[date, AnnualValue | InputUnavailable]] | InputUnavailable | MetricInputsFailure:
    """Return each named annual field for the year ending at each named year-end.

    A value is its resolved input; ``None`` where the filings report none for the year, which includes an observation
    whose period does not end at that year-end (it is never returned as that year's); or an ``InputUnavailable`` where
    the latest versions of the year's value conflict (``ambiguous_fact``) or the year was filed only after the
    boundary (``not_available_as_of``), each decided per year. The completed-annual fields and
    ``OPERATING_CASH_FLOW`` are a series: the resolver gives every observation that passed its provider-response
    checks (``InputResolver.resolve_annual_series``) in one resolution per field, and this function takes the ones that
    end at each year-end and, as FCF-Growth does, keeps the latest-available version of the period. That selection
    stays here because it is the shared metrics' rule for a year-end and for ``ambiguous_fact``, and the resolver stays
    provider-neutral. A registrant whose annual filings all came after the boundary is returned once, as
    ``not_available_as_of`` with the provider's message, and no further field is requested. The values never depend
    on the order of ``fields`` or ``year_ends``, or on the order of the provider's answer.

    Raises:
        ValueError: If no year-end is requested, or a field is neither a completed-annual period field nor
            ``OPERATING_CASH_FLOW``.
    """
    dates = _requested_dates(year_ends)
    names = _requested_fields(fields)
    for name in names:
        if name not in _ASSEMBLED_ANNUAL_FIELDS:
            raise ValueError(f"{name.value} is not a completed-annual period field.")
    values: dict[FinancialField, Mapping[date, AnnualValue | InputUnavailable]] = {}
    for name in names:
        request = FinancialFactRequest(
            FinancialSubjectKind.SECURITY, ticker, name, SEC_PROVIDER_ID, basis=_ANNUAL_BASIS, as_of=as_of
        )
        resolution = resolver.resolve_annual_series(request)
        if resolution.not_available_as_of:
            return InputUnavailable(ReasonCode.NOT_AVAILABLE_AS_OF, resolution.reason or "")
        if resolution.status not in (CalculationStatus.OK, CalculationStatus.INPUT_UNAVAILABLE):
            record = resolution.provider_failure
            return MetricInputsFailure(
                name.value,
                resolution.reason or "The provider's answer was rejected.",
                None if record is None else record.for_input(name.value),
            )
        by_date: dict[date, AnnualValue | InputUnavailable] = {}
        for day in dates:
            value = _annual_value(resolution.inputs, name, day)
            by_date[day] = value if value is not None else _left_out_at(resolution.left_out, day)
        values[name] = MappingProxyType(by_date)
    return MappingProxyType(values)


def resolve_annual_values(
    resolver: InputResolver,
    *,
    anchor: AnchorYearEnd,
    ticker: str,
    fields: Sequence[FinancialField],
    as_of: datetime | None,
) -> Mapping[FinancialField, AnnualValue | InputUnavailable] | InputUnavailable | MetricInputsFailure:
    """Return each named annual field for the year ending at the anchor year-end.

    This is ``resolve_annual_values_at`` for the one year-end *t*; its rules and its raised errors are those of that
    function.
    """
    outcome = resolve_annual_values_at(
        resolver, ticker=ticker, fields=fields, year_ends=(anchor.year_end,), as_of=as_of
    )
    if isinstance(outcome, (InputUnavailable, MetricInputsFailure)):
        return outcome
    return MappingProxyType({name: outcome[name][anchor.year_end] for name in dict.fromkeys(fields)})


@dataclass(frozen=True)
class YearEnds:
    """The fiscal year-ends of the three years a multi-year consumer reads.

    Attributes:
        year_end: *t*, the anchor year-end.
        prior: *t-1*, or why it is unavailable.
        second_prior: *t-2*, or why it is unavailable; unavailable whenever ``prior`` is.
    """

    year_end: date
    prior: date | InputUnavailable
    second_prior: date | InputUnavailable

    def __post_init__(self) -> None:
        """Refuse a *t-2* when *t-1* is unavailable, since *t-2* is derived from *t-1*."""
        if isinstance(self.prior, InputUnavailable) and not isinstance(self.second_prior, InputUnavailable):
            raise ValueError("A second prior year-end cannot be known when the prior year-end is unavailable.")

    def available_dates(self) -> tuple[date, ...]:
        """Return the year-ends that are dates, newest first."""
        return tuple(item for item in (self.year_end, self.prior, self.second_prior) if isinstance(item, date))


def resolve_year_ends(
    resolver: InputResolver, *, anchor: AnchorYearEnd, ticker: str, as_of: datetime | None
) -> YearEnds | InputUnavailable | MetricInputsFailure:
    """Return the anchor year-end *t* with *t-1* and *t-2*, each a date or the reason it is unavailable.

    *t-1* is the day before the start of the completed annual period that ends at *t*; *t-2* is derived the same way
    from the period that ends at *t-1*. The start date is read from the latest-available version of each field of
    ``YEAR_END_START_FIELDS`` that reports the year: they must all give the same start (``ambiguous_fact`` if not), at
    least one must report the year (``missing_fact`` if none does), and the derived year-end must lie
    ``YEAR_LENGTH_DAYS`` before the later one (``incompatible_period`` if not). A period that is not a completed
    annual period, such as a transition period, is not in the series, so it breaks the chain: the year-end before it is
    unavailable for ``missing_fact`` and so is every earlier one. A year-end is never taken from the submissions'
    report dates.

    A registrant whose annual filings all came after the boundary is returned once, as ``not_available_as_of`` with the
    provider's message.
    """
    series: dict[FinancialField, AnnualSeriesResolution] = {}
    for name in YEAR_END_START_FIELDS:
        request = FinancialFactRequest(
            FinancialSubjectKind.SECURITY, ticker, name, SEC_PROVIDER_ID, basis=_ANNUAL_BASIS, as_of=as_of
        )
        resolution = resolver.resolve_annual_series(request)
        if resolution.not_available_as_of:
            return InputUnavailable(ReasonCode.NOT_AVAILABLE_AS_OF, resolution.reason or "")
        if resolution.status not in (CalculationStatus.OK, CalculationStatus.INPUT_UNAVAILABLE):
            record = resolution.provider_failure
            return MetricInputsFailure(
                name.value,
                resolution.reason or "The provider's answer was rejected.",
                None if record is None else record.for_input(name.value),
            )
        series[name] = resolution
    prior = _prior_year_end(series, anchor.year_end)
    second_prior = prior if isinstance(prior, InputUnavailable) else _prior_year_end(series, prior)
    return YearEnds(anchor.year_end, prior, second_prior)


def _prior_year_end(series: Mapping[FinancialField, AnnualSeriesResolution], year_end: date) -> date | InputUnavailable:
    """Return the year-end before ``year_end`` from the start dates the listed fields give for the year ending then."""
    starts: set[date] = set()
    after_boundary: InputUnavailable | None = None
    for name, resolution in series.items():
        candidates = [
            item
            for item in resolution.inputs
            if item.observation_period_end is not None
            and item.observation_period_end.date() == year_end
            and item.observation_period_start is not None
            and item.available_at is not None
        ]
        if not candidates:
            after_boundary = after_boundary or _left_out_at(resolution.left_out, year_end)
            continue
        newest = max(item.available_at for item in candidates if item.available_at is not None)
        latest = {
            item.observation_period_start.date()
            for item in candidates
            if item.available_at == newest and item.observation_period_start is not None
        }
        if len(latest) != 1:
            return InputUnavailable(
                ReasonCode.AMBIGUOUS_FACT,
                f"The latest versions of {name.value} for the year ending {year_end} give different start dates.",
            )
        starts |= latest
    names = ", ".join(name.value for name in series)
    if len(starts) > 1:
        return InputUnavailable(
            ReasonCode.AMBIGUOUS_FACT,
            f"The fields {names} give different start dates "
            f"({', '.join(sorted(day.isoformat() for day in starts))}) for the year ending {year_end}.",
        )
    if not starts:
        return after_boundary or InputUnavailable(
            ReasonCode.MISSING_FACT, f"None of {names} reports a completed annual period ending {year_end}."
        )
    derived = next(iter(starts)) - timedelta(days=1)
    gap = (year_end - derived).days
    least, most = YEAR_LENGTH_DAYS
    if not least <= gap <= most:
        return InputUnavailable(
            ReasonCode.INCOMPATIBLE_PERIOD,
            f"The year ending {year_end} began after {derived}, {gap} days earlier; "
            f"a fiscal year is {least} to {most} days.",
        )
    return derived


def resolve_share_count_series(
    resolver: InputResolver, *, ticker: str, year_ends: Sequence[date], as_of: datetime | None
) -> Mapping[date, YearEndShareCount | InputUnavailable] | InputUnavailable | MetricInputsFailure:
    """Return the common share count at each named year-end with its filing and path, or why there is none.

    The count is the balance-sheet count at that year-end, by the direct path or issued less treasury shares from one
    filing (Shared definitions §4); the cover-page count is never used. Each count carries the one accession its
    provenance names, and a count whose provenance names none or several is unavailable. A year-end is never filled from
    another, and the result does not depend on the order of ``year_ends`` or of the provider's answer. A registrant
    whose annual filings all came after the boundary is returned once, as ``not_available_as_of``.

    Raises:
        ValueError: If no year-end is requested.
    """
    dates = _requested_dates(year_ends)
    by_date = _instant_series_by_date(resolver, ticker=ticker, name=SHARE_COUNT_SERIES_FIELD, dates=dates, as_of=as_of)
    if isinstance(by_date, (InputUnavailable, MetricInputsFailure)):
        return by_date
    return MappingProxyType({day: _year_end_share_count(item) for day, item in by_date.items()})


def _year_end_share_count(item: BalanceSheetValue) -> YearEndShareCount | InputUnavailable:
    """Return the count as a ``YearEndShareCount``, or the reason it is unavailable."""
    if isinstance(item, InstantAbsence):
        return InputUnavailable(absence_reason_code(item.reason), item.detail)
    accessions = _accessions(item)
    if len(accessions) != 1:
        return InputUnavailable(
            ReasonCode.AMBIGUOUS_FACT if accessions else ReasonCode.MISSING_FACT,
            "The share count does not name exactly one filing it was taken from.",
        )
    derived = item.provider_field is not None and item.provider_field.startswith("derived:")
    path = ShareCountPath.ISSUED_LESS_TREASURY if derived else ShareCountPath.DIRECT
    return YearEndShareCount(item, next(iter(accessions)), path)


class AsFiledSicSource(Protocol):
    """The capability that gives the as-filed SIC code of the anchor filing of the active analysis scope."""

    def resolve_as_filed_sic_at_anchor(self, ticker: str, as_of: datetime | None) -> AsFiledSicResolution:
        """Return the SIC code the anchor filing's header assigns, or the reason it is unavailable.

        Raises:
            FinancialProviderError: On an operational provider failure.
        """
        ...


@dataclass(frozen=True)
class IndustryClassResolution:
    """The industry class of an issuer, or the reason it is unknown.

    Attributes:
        industry_class: The class of the as-filed SIC code, ``None`` when it is unknown.
        unknown: Why the class is unknown (``industry_class_unknown`` with a message naming the reason); set exactly
            when ``industry_class`` is ``None``.
    """

    industry_class: IndustryClass | None
    unknown: InputUnavailable | None

    def __post_init__(self) -> None:
        """Require exactly one of the class and the reason it is unknown."""
        if (self.industry_class is None) == (self.unknown is None):
            raise ValueError("An industry-class resolution holds exactly one of the class and the unknown reason.")


def resolve_industry_class(
    source: AsFiledSicSource, *, ticker: str, as_of: datetime | None
) -> IndustryClassResolution | MetricInputsFailure:
    """Return the industry class of the SIC code the anchor annual filing assigns, or why it is unknown.

    The class comes from the SIC code as filed, never from the issuer's current code. Every reason the code is
    unavailable gives an unknown class with ``industry_class_unknown`` and a message naming the reason, so a strategy
    runs and says so. A provider failure is returned as a ``MetricInputsFailure`` for the input ``industry_class``.
    """
    try:
        resolution = source.resolve_as_filed_sic_at_anchor(ticker.strip().upper(), as_of)
    except FinancialProviderError as exc:
        return _failure("industry_class", exc)
    if resolution.sic is None:
        assert resolution.reason is not None  # the resolution type guarantees one of the two
        return IndustryClassResolution(
            None,
            InputUnavailable(
                ReasonCode.INDUSTRY_CLASS_UNKNOWN,
                f"The industry class is unknown: the as-filed SIC code is unavailable ({resolution.reason.value}).",
            ),
        )
    return IndustryClassResolution(industry_class_of_sic(resolution.sic.code), None)


def _left_out_at(left_out: Sequence[LeftOutObservation], year_end: date) -> InputUnavailable | None:
    """Return ``not_available_as_of`` when the observation that ends at ``year_end`` was filed after the boundary."""
    for item in left_out:
        if (
            item.why is LeftOutReason.NOT_AVAILABLE_AT_BOUNDARY
            and item.observation_period_end is not None
            and item.observation_period_end.date() == year_end
        ):
            return InputUnavailable(ReasonCode.NOT_AVAILABLE_AS_OF, item.reason)
    return None


def _annual_value(
    inputs: Sequence[ResolvedInput], name: FinancialField, year_end: date
) -> AnnualValue | InputUnavailable:
    """Return the latest-available version of the observation that ends at ``year_end``, ``None`` if there is none."""
    candidates = [
        item
        for item in inputs
        if item.observation_period_end is not None
        and item.observation_period_end.date() == year_end
        and item.available_at is not None
    ]
    if not candidates:
        return None
    latest_time = max(item.available_at for item in candidates if item.available_at is not None)
    latest = [item for item in candidates if item.available_at == latest_time]
    if len({item.value for item in latest}) != 1:
        return InputUnavailable(
            ReasonCode.AMBIGUOUS_FACT,
            f"The latest versions of {name.value} for the year ending {year_end} have conflicting values.",
        )
    return min(
        latest, key=lambda item: (item.provider_fact_id or "", item.provider_id or "", item.provider_field or "")
    )
