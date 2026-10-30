"""The inputs the shared metrics need, assembled once for an issuer and a boundary.

Four functions, one per input family: the anchor fiscal year-end *t*; the market-cap inputs at *t*; balance-sheet
values at *t*; annual values at *t*. Each takes the dependencies a consumer's analyzer received at construction (the
``InputResolver``, the split-history client and the cover-listing capability) and holds no state. Every input is the
evidence of the registrant the ticker names, as filed or priced at the boundary.

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
from typing import Final

from investment_analysis_engine.analysis.shared.financial_resolution import resolve_optional_quote
from investment_analysis_engine.analysis.shared.market_cap import (
    ANCHOR_FILING_FORMS,
    ListingCheck,
    MarketCapEvidence,
    ShareCountBasis,
    compute_market_cap,
    listing_check_from_resolution,
)
from investment_analysis_engine.analysis.shared.metric_evidence import AnnualValue, BalanceSheetValue, InputUnavailable
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.metric_result import ReasonCode
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureRecord
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import (
    ANNUAL_PERIOD_FIELDS,
    COVER_PAGE_BASIS,
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
    InputResolutionResult,
    InputResolver,
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


def _source_filing_date(count: ResolvedInput, anchor: AnchorYearEnd) -> date | None:
    """Return the filing date of the one filing a year-end count was taken from, or ``None`` when it is not dated."""
    accessions = {
        piece.split("=", 1)[1].strip()
        for note in count.notes
        for piece in note.split(";")
        if piece.strip().startswith("accession=")
    }
    if len(accessions) != 1:
        return None
    return anchor.filing_dates.get(next(iter(accessions)))


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


def resolve_balance_sheet_values(
    resolver: InputResolver,
    *,
    anchor: AnchorYearEnd,
    ticker: str,
    fields: Sequence[FinancialField],
    as_of: datetime | None,
) -> Mapping[FinancialField, BalanceSheetValue] | InputUnavailable | MetricInputsFailure:
    """Return each named balance-sheet field at the anchor year-end: its resolved input or its absence.

    A field the provider cannot serve is an ``InstantAbsence`` of reason ``unsupported``, and a field the filings do
    not report is the absence the provider gives. An absence because the year-end is after the boundary is the
    registrant whose annual filings all came after it: the function returns it once, as ``not_available_as_of`` with
    the provider's message, and requests no further field.
    """
    values: dict[FinancialField, BalanceSheetValue] = {}
    for name in fields:
        request = InstantSeriesRequest(ticker, name, SEC_PROVIDER_ID, (anchor.year_end,), as_of=as_of)
        resolution = resolver.resolve_instant_series(request)
        if resolution.status is CalculationStatus.OK:
            values[name] = resolution.inputs[0]
            continue
        if resolution.status is not CalculationStatus.INPUT_UNAVAILABLE:
            record = resolution.provider_failure
            return MetricInputsFailure(
                name.value,
                resolution.reason or "The provider's answer was rejected.",
                None if record is None else record.for_input(name.value),
            )
        absence = (
            resolution.absences[0]
            if resolution.absences
            else InstantAbsence(
                anchor.year_end, InstantAbsenceReason.UNSUPPORTED, resolution.reason or "The provider serves no series."
            )
        )
        if absence.reason is InstantAbsenceReason.AFTER_BOUNDARY:
            return InputUnavailable(ReasonCode.NOT_AVAILABLE_AS_OF, absence.detail)
        values[name] = absence
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

    A field is its resolved input; ``None`` where the filings report none for the year, which includes an observation
    whose period does not end at *t* (it is never returned as *t*'s); or an ``InputUnavailable`` where the latest
    versions of the year's value conflict. The completed-annual fields are a series: the resolver gives every
    observation that passed its provider-response checks (``InputResolver.resolve_annual_series``), and this function
    takes the ones that end at *t* and, as FCF-Growth does, keeps the latest-available version of the period. That
    selection stays here because it is the shared metrics' rule for *t* and for ``ambiguous_fact``, and the resolver
    stays provider-neutral. A registrant whose annual filings all came after the boundary is returned once, as
    ``not_available_as_of`` with the provider's message, and no further field is requested.

    Raises:
        ValueError: If a field is not a completed-annual period field.
    """
    values: dict[FinancialField, AnnualValue | InputUnavailable] = {}
    for name in fields:
        if name not in ANNUAL_PERIOD_FIELDS:
            raise ValueError(f"{name.value} is not a completed-annual period field.")
        request = FinancialFactRequest(
            FinancialSubjectKind.SECURITY, ticker, name, SEC_PROVIDER_ID, basis=_ANNUAL_BASIS, as_of=as_of
        )
        resolution = resolver.resolve_annual_series(request)
        if resolution.not_available_as_of:
            return InputUnavailable(ReasonCode.NOT_AVAILABLE_AS_OF, resolution.reason or "")
        if resolution.status in (CalculationStatus.OK, CalculationStatus.INPUT_UNAVAILABLE):
            value = _annual_value(resolution.inputs, name, anchor.year_end)
            values[name] = value if value is not None else _left_out_at(resolution.left_out, anchor.year_end)
        else:
            record = resolution.provider_failure
            return MetricInputsFailure(
                name.value,
                resolution.reason or "The provider's answer was rejected.",
                None if record is None else record.for_input(name.value),
            )
    return MappingProxyType(values)


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
