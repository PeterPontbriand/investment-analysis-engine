"""Market capitalization at a boundary: a filed share count on the basis of a split-adjusted price.

The function is pure. Market cap = common shares outstanding x price, with the count put on the basis of the price
by the provider's split adjustments of two windows (``scale_share_count``). It is available only when all of these
hold, and each refusal has its code:

- the anchor annual filing is a 10-K or a 10-K/A (``incompatible_scope``): a 20-F or 40-F filer, or their amendments,
  may list a depositary receipt at a ratio the structured data cannot show;
- the quote currency equals the filing currency, both known (``incompatible_currency``);
- a listing check of the anchor filing's cover affirms the requested ticker as a share of the issuer (the check's own
  reason code); a ticker renamed since the anchor filing is affirmed when the anchor cover's one share line is the
  renamed line of the registrant's latest annual cover, and the check records both accessions and symbols;
- a share count and a price are present (the input's own reason code). A year-end count must be dated at the fiscal
  year-end *t* (``incompatible_period``); several classes are valued as one combined count at the requested ticker's
  price, and per-class counts with no total arrive as an unavailable count;
- an adjustment between the count's date and the price date has a recognizable split ratio (``ambiguous_fact``
  otherwise): it may be a spin-off, which does not change the share count.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from enum import StrEnum

from investment_analysis_engine.analysis.shared.metric_evidence import InputUnavailable
from investment_analysis_engine.analysis.shared.split_adjustment import AppliedAdjustment, scale_share_count
from investment_analysis_engine.core.metric_result import MetricResult, MetricStatus, ReasonCode
from investment_analysis_engine.data.financial.provenance import ResolvedInput
from investment_analysis_engine.data.market_data import SplitEvent
from investment_analysis_engine.data.sec_edgar.cover_listing import (
    CoverUnavailableReason,
    ListingEvidence,
    ListingRename,
    ListingResolution,
    SecurityKind,
)

ANCHOR_FILING_FORMS = frozenset({"10-K", "10-K/A"})


class ShareCountBasis(StrEnum):
    """Where a share count was taken from."""

    YEAR_END = "year_end"
    COVER_PAGE = "cover_page"


@dataclass(frozen=True)
class ListingCheck:
    """The outcome of reading the anchor 10-K's cover for the requested ticker.

    Attributes:
        affirmed: Whether the cover lists the ticker, under this CIK, on a registered title that is a share of the
            issuer.
        accession: The accession of the anchor filing whose cover was read; ``None`` only when no cover could be read.
        reason_code: For a refusal, ``incompatible_units`` (a depositary share, unit, warrant or preferred security) or
            ``missing_fact`` (a missing or unreadable cover); ``None`` when affirmed.
        reason: For a refusal, a non-empty explanation; ``None`` when affirmed.
        rename: Set when the ticker is not on the anchor cover but is the renamed one share line of the registrant's
            latest annual cover; it records both accessions and both symbols as filed.
    """

    affirmed: bool
    accession: str | None = None
    reason_code: ReasonCode | None = None
    reason: str | None = None
    rename: ListingRename | None = None

    def __post_init__(self) -> None:
        """Require an accession when affirmed, and a code and a reason when refused."""
        if self.affirmed:
            if self.accession is None or not self.accession.strip():
                raise ValueError("An affirmed listing check requires the accession it read.")
            if self.reason_code is not None or self.reason is not None:
                raise ValueError("An affirmed listing check carries no reason.")
        elif self.reason_code is None or self.reason is None or not self.reason.strip():
            raise ValueError("A refused listing check requires a reason code and a non-empty reason.")
        if self.rename is not None and not self.affirmed:
            raise ValueError("Only an affirmed listing check records a rename.")


_REFUSED_KINDS = {
    SecurityKind.DEPOSITARY_SHARE: "a depositary share",
    SecurityKind.UNIT: "a unit",
    SecurityKind.WARRANT: "a warrant",
    SecurityKind.PREFERRED: "a preferred security",
}
_UNAVAILABLE_REASONS = {
    CoverUnavailableReason.PROVIDER_UNSUPPORTED: "the provider does not read filing covers",
    CoverUnavailableReason.NO_ANALYSIS_SCOPE: "no analysis scope is active for the provider",
    CoverUnavailableReason.SUBJECT_MISMATCH: "the active analysis scope is for another ticker",
    CoverUnavailableReason.NO_ANCHOR_FILING: "SEC EDGAR has no CIK for the ticker",
    CoverUnavailableReason.FORM_UNAVAILABLE: "the anchor filing's form is unknown",
    CoverUnavailableReason.ACCEPTANCE_UNAVAILABLE: "the anchor filing's acceptance time is unknown",
    CoverUnavailableReason.ACCEPTED_AFTER_BOUNDARY: "the registrant's annual filings were accepted after the boundary",
    CoverUnavailableReason.COVER_MISSING: "the filing has no rendered cover",
    CoverUnavailableReason.COVER_UNREADABLE: "the cover cannot be read without guessing",
    CoverUnavailableReason.NO_REGISTRATION_TABLE: "the cover has no table of registered securities",
    CoverUnavailableReason.FORM_MISMATCH: "the cover names a different form than the anchor filing",
    CoverUnavailableReason.CIK_MISMATCH: "the cover does not name the issuer's CIK",
    CoverUnavailableReason.AMBIGUOUS_LISTING: "the cover lists the ticker under different titles",
}


def listing_check_from_resolution(resolution: ListingResolution) -> ListingCheck:
    """Return the listing check a cover resolution gives.

    A share of the issuer is affirmed. A depositary share, unit, warrant or preferred security is refused with
    ``incompatible_units``. A ticker the cover does not list, a title outside the vocabulary and a cover that could
    not be read are refused with ``missing_fact``.
    """
    evidence = resolution.evidence
    if evidence is None:
        assert resolution.reason is not None  # the resolution type guarantees one of the two
        return ListingCheck(
            affirmed=False,
            reason_code=ReasonCode.MISSING_FACT,
            reason=f"No cover could be read for the listing check: {_UNAVAILABLE_REASONS[resolution.reason]}.",
        )
    return _check_listed_security(evidence)


def _check_listed_security(evidence: ListingEvidence) -> ListingCheck:
    """Return the listing check for a cover that was read."""
    if evidence.kind is SecurityKind.SHARE and evidence.rename is not None:
        return ListingCheck(affirmed=True, accession=evidence.rename.anchor_accession, rename=evidence.rename)
    if evidence.kind is SecurityKind.SHARE:
        return ListingCheck(affirmed=True, accession=evidence.accession)
    if evidence.kind in _REFUSED_KINDS:
        return ListingCheck(
            affirmed=False,
            accession=evidence.accession,
            reason_code=ReasonCode.INCOMPATIBLE_UNITS,
            reason=f"{evidence.ticker} is registered as {_REFUSED_KINDS[evidence.kind]} ({evidence.title!r}), "
            "not as a share of the issuer.",
        )
    if evidence.kind is SecurityKind.NOT_LISTED:
        reason = f"The cover of {evidence.accession} does not list {evidence.ticker} under this CIK."
    else:
        reason = f"{evidence.ticker} is registered under a title outside the share vocabulary ({evidence.title!r})."
    return ListingCheck(
        affirmed=False, accession=evidence.accession, reason_code=ReasonCode.MISSING_FACT, reason=reason
    )


@dataclass(frozen=True)
class MarketCapEvidence:
    """Market capitalization with the share count, price and splits behind it.

    Fields other than ``result`` hold what was known when the metric was decided, so a refusal still shows the inputs
    it was given.

    Attributes:
        result: The metric's status, finite value, reason code and reason.
        share_count: The resolved count as filed.
        share_count_basis: Whether the count is a year-end or a cover-page count.
        share_count_date: The date of the count: the fiscal year-end, or the date of the cover page.
        share_count_filing_date: The filing date of the count's source.
        scaled_share_count: The count on the basis of the price, after the splits applied.
        provider_adjustments: The provider's split-history events that scaled the count, each with the window it fell
            in: between the count and the price (a recognizable split ratio) or after the price (undoing the provider's
            adjustment of the close). The provider reports splits and other adjustments, such as a spin-off, alike.
        price: The split-adjusted close, without dividend adjustment.
        price_date: The date of the price.
        form: The anchor filing's form.
        filing_currency: The currency of the filing.
        quote_currency: The currency of the price.
        listing_check: The listing check's outcome.
    """

    result: MetricResult
    share_count: ResolvedInput | None = None
    share_count_basis: ShareCountBasis | None = None
    share_count_date: date | None = None
    share_count_filing_date: date | None = None
    scaled_share_count: float | None = None
    provider_adjustments: tuple[AppliedAdjustment, ...] = field(default=())
    price: float | None = None
    price_date: date | None = None
    form: str | None = None
    filing_currency: str | None = None
    quote_currency: str | None = None
    listing_check: ListingCheck | None = None


_UNDECIDED = MetricResult.failure(MetricStatus.UNAVAILABLE, ReasonCode.MISSING_FACT, "Market cap is not decided.")


def _refuse(
    base: MarketCapEvidence, reason_code: ReasonCode, reason: str, status: MetricStatus = MetricStatus.UNAVAILABLE
) -> MarketCapEvidence:
    """Return ``base`` with a non-``ok`` result, keeping the inputs known so far."""
    return replace(base, result=MetricResult.failure(status, reason_code, reason))


def compute_market_cap(  # noqa: PLR0911, PLR0913
    *,
    year_end: date,
    form: str,
    filing_currency: str | None,
    quote_currency: str | None,
    listing_check: ListingCheck,
    share_count: ResolvedInput | InputUnavailable,
    share_count_basis: ShareCountBasis,
    share_count_filing_date: date,
    price: float | InputUnavailable,
    price_date: date | None,
    split_events: Sequence[SplitEvent],
    adjustment_date: date,
) -> MarketCapEvidence:
    """Return market capitalization at the boundary, or why it is ``unavailable``.

    Args:
        year_end: The anchor fiscal year-end *t*.
        form: The anchor filing's form; only ``10-K`` and ``10-K/A`` qualify.
        filing_currency: The filing's currency, ``None`` when unknown.
        quote_currency: The price's currency, ``None`` when unknown.
        listing_check: The outcome of the cover listing check.
        share_count: The resolved count, or why there is none.
        share_count_basis: Whether ``share_count`` is a year-end or a cover-page count.
        share_count_filing_date: The filing date of the count's source. It scales a year-end count; a cover-page count
            is scaled from its own date.
        price: The split-adjusted close without dividend adjustment, or why there is none.
        price_date: The date of the price.
        split_events: The provider's split history.
        adjustment_date: The date up to which the provider adjusted the price.

    Raises:
        ValueError: If a price is given without its ``price_date``.
    """
    if not isinstance(price, InputUnavailable) and price_date is None:
        raise ValueError("A price requires its price_date, which stays visible with the market cap.")
    base = MarketCapEvidence(
        result=_UNDECIDED,
        share_count_basis=share_count_basis,
        share_count_filing_date=share_count_filing_date,
        price_date=price_date,
        form=form,
        filing_currency=filing_currency,
        quote_currency=quote_currency,
        listing_check=listing_check,
    )
    if form.strip().upper() not in ANCHOR_FILING_FORMS:
        return _refuse(
            base,
            ReasonCode.INCOMPATIBLE_SCOPE,
            f"The anchor filing is a {form}, not one of {sorted(ANCHOR_FILING_FORMS)}: the listing may be a depositary "
            "receipt at a ratio the structured data cannot show.",
        )
    if not filing_currency or not quote_currency or filing_currency.strip().upper() != quote_currency.strip().upper():
        return _refuse(
            base,
            ReasonCode.INCOMPATIBLE_CURRENCY,
            f"The filing currency {filing_currency!r} and the quote currency {quote_currency!r} are not the same "
            "known currency.",
        )
    if not listing_check.affirmed:
        return _refuse(
            base,
            listing_check.reason_code or ReasonCode.MISSING_FACT,
            listing_check.reason or "The listing check refused the ticker.",
        )
    if isinstance(share_count, InputUnavailable):
        return _refuse(base, share_count.reason_code, share_count.reason)
    base = replace(base, share_count=share_count)
    if isinstance(price, InputUnavailable):
        return _refuse(base, price.reason_code, price.reason)
    base = replace(base, price=price)
    if share_count.observation_period_end is None:
        return _refuse(base, ReasonCode.INCOMPATIBLE_PERIOD, "The share count carries no date.")
    count_date = share_count.observation_period_end.date()
    base = replace(base, share_count_date=count_date)
    if share_count_basis is ShareCountBasis.YEAR_END and count_date != year_end:
        return _refuse(
            base,
            ReasonCode.INCOMPATIBLE_PERIOD,
            f"The year-end share count is dated {count_date}, not the fiscal year-end {year_end}; "
            "an older year's count is never substituted.",
        )
    if not math.isfinite(price) or price <= 0 or share_count.value <= 0:
        return _refuse(
            base,
            ReasonCode.INVALID_REQUEST,
            "The share count and the price must be finite and positive.",
            MetricStatus.NOT_APPLICABLE,
        )
    after = share_count_filing_date if share_count_basis is ShareCountBasis.YEAR_END else count_date
    assert price_date is not None  # a price is given only with its date
    scaling = scale_share_count(share_count.value, after, price_date, adjustment_date, split_events)
    if scaling.unrecognized is not None:
        return _refuse(
            base,
            ReasonCode.AMBIGUOUS_FACT,
            f"The provider reports an adjustment with ex-date {scaling.unrecognized.ex_date} and ratio "
            f"{scaling.unrecognized.ratio:g} between the share count ({after}) and the price ({price_date}) that is "
            "not a recognizable split ratio; it may be a spin-off or a stock dividend, which would not change the "
            "share count the way a split does, so the share count on the price's basis is undetermined.",
        )
    base = replace(base, scaled_share_count=scaling.count, provider_adjustments=scaling.applied)
    market_cap = scaling.count * price
    if not math.isfinite(market_cap):
        return _refuse(
            base,
            ReasonCode.INVALID_REQUEST,
            "Market cap overflows the finite double range for the supplied inputs.",
            MetricStatus.NOT_APPLICABLE,
        )
    return replace(base, result=MetricResult.ok(market_cap))
