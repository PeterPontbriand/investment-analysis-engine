"""SEC EDGAR adapter for annual diluted EPS and BVPS derivation components."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from types import MappingProxyType
from typing import cast
from zoneinfo import ZoneInfo

from investment_analysis_engine.core.clock import utc_now
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import (
    ANNUAL_PERIOD_FIELDS,
    COVER_PAGE_BASIS,
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    InstantAbsence,
    InstantAbsenceReason,
    InstantSeriesFacts,
    InstantSeriesRequest,
    ProviderFact,
    ProviderShareSource,
)
from investment_analysis_engine.data.financial.provenance import (
    AccountingScope,
    CapitalExpenditureSign,
    FinancialSubjectKind,
    PeriodKind,
)
from investment_analysis_engine.data.http_json import JsonFetcher, fetch_json
from investment_analysis_engine.data.provider_failure import failure_record
from investment_analysis_engine.data.sec_edgar.annual_series import annual_concepts, select_annual_period_facts
from investment_analysis_engine.data.sec_edgar.cover_listing import (
    CoverFetcher,
    CoverListingRequest,
    CoverReaderPolicy,
    CoverUnavailableReason,
    ListingResolution,
    cover_url,
    fetch_anchor_cover,
    fetch_cover,
    read_cover_listing,
)
from investment_analysis_engine.data.sec_edgar.filing_document import (
    FilingFetcher,
    FilingHeaderFetcher,
    FilingHeaderPolicy,
    FilingReaderPolicy,
    fetch_filing,
    fetch_filing_header,
    filing_header_url,
    filing_url,
)
from investment_analysis_engine.data.sec_edgar.filing_header import (
    AsFiledSicResolution,
    SicUnavailableReason,
    parse_filing_header,
)
from investment_analysis_engine.data.sec_edgar.instant_series import InstantSource, select_instant_series
from investment_analysis_engine.data.sec_edgar.security_unit import (
    MAPPING_ID,
    UnitMappingError,
    parse_unit_document,
    source_accession,
    source_leaves,
)
from investment_analysis_engine.data.security_identity import SecurityIdentity, SecurityIdentityRequest
from investment_analysis_engine.data.security_unit import (
    SecurityUnitDocument,
    SecurityUnitEvidence,
    SecurityUnitKind,
    SecurityUnitProvenance,
    SecurityUnitRequest,
    SecurityUnitResolution,
    SecurityUnitResolutionReason,
)

SEC_PROVIDER_ID = "sec_edgar"
SEC_EPS_FIELD = "us-gaap:EarningsPerShareDiluted"
SEC_WEIGHTED_AVERAGE_DILUTED_SHARES_FIELD = "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding"
SEC_OPERATING_CASH_FLOW_FIELD = "us-gaap:NetCashProvidedByUsedInOperatingActivities"
SEC_CAPITAL_EXPENDITURES_FIELD = "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment"
SEC_IFRS_EPS_FIELD = "ifrs-full:DilutedEarningsLossPerShare"
SEC_IFRS_WEIGHTED_AVERAGE_DILUTED_SHARES_FIELD = "ifrs-full:AdjustedWeightedAverageShares"
SEC_IFRS_OPERATING_CASH_FLOW_FIELD = "ifrs-full:CashFlowsFromUsedInOperatingActivities"
SEC_IFRS_CAPITAL_EXPENDITURES_FIELD = "ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"
SEC_STOCKHOLDERS_EQUITY_FIELD = "us-gaap:StockholdersEquity"
_SEC_DERIVED_COMMON_SHARES_FIELD = "derived:us-gaap:CommonStockSharesIssued-us-gaap:TreasuryStockCommonShares"
SEC_COVER_PAGE_SHARES_FIELD = "dei:EntityCommonStockSharesOutstanding"
_IFRS_FULL = "ifrs-full"
_US_GAAP = "us-gaap"
_SEC_INFERRED_PREFERRED_ABSENCE_FIELD = "inferred:sec-company-facts:no-issued-preferred-equity"
_PREFERRED_NEUTRAL_CONCEPTS = frozenset({"PreferredStockSharesAuthorized", "PreferredStockParOrStatedValuePerShare"})
_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_SUBMISSION_PAGE_URL = "https://data.sec.gov/submissions/{name}"
# An extra page names one stretch of an issuer's filings (about a month for the most frequent filers). A balance-sheet
# series reads at most this many of them, so the cost of an issuer that files constantly stays bounded.
_MAX_SUBMISSION_PAGES = 12
_SUBMISSION_PAGE_NAME = re.compile(r"^CIK(\d{10})-submissions-\d{3}\.json$")


class _MissingCikError(FinancialProviderError):
    """SEC's ticker map has no entry for the ticker: a ticker without a CIK, not a failure to read the map."""


_COMPLETED_ANNUAL_FORMS = frozenset({"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"})
_SEC_EASTERN = ZoneInfo("America/New_York")
# A completed fiscal year can vary around 365 days, including 52/53-week years.
# The approved mapping excludes quarterly, YTD, and TTM durations; this bounded
# tolerance admits ordinary issuer calendar variation without guessing at them.
_MIN_ANNUAL_DURATION_DAYS = 335
_MAX_ANNUAL_DURATION_DAYS = 395
_BALANCE_SHEET_FORMS = frozenset({"10-K", "10-K/A"})
_BALANCE_SHEET_FIELDS: Mapping[FinancialField, tuple[str, FinancialUnit]] = {
    FinancialField.STOCKHOLDERS_EQUITY: ("StockholdersEquity", FinancialUnit.CURRENCY),
    FinancialField.COMMON_SHARES_OUTSTANDING: ("CommonStockSharesOutstanding", FinancialUnit.SHARES),
    FinancialField.PREFERRED_SHARES_OUTSTANDING: ("PreferredStockSharesOutstanding", FinancialUnit.SHARES),
}

# The approved D0 SEC mapping treats these entity-wide annual cash-flow facts
# as unavailable when ticker-to-CIK identity cannot be established. Legacy SEC
# valuation fields retain their existing provider-error behavior until their
# separately reviewed compatibility boundary is reconciled.
_SEC_FIELDS_WITH_UNAVAILABLE_MISSING_IDENTITY = (
    frozenset(
        {
            FinancialField.EPS,
            FinancialField.OPERATING_CASH_FLOW,
            FinancialField.CAPITAL_EXPENDITURES,
            FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
        }
    )
    | ANNUAL_PERIOD_FIELDS
)

# SEC Company Facts monetary cash-flow fields describe the issuer, so an exact
# ticker-to-CIK match is sufficient even when the same CIK has other ticker
# rows. Per-share fields describe an issuer share unit; until affirmative unit
# evidence is implemented, multiple ticker rows cannot prove that the requested
# listed security uses that same unit and therefore remain fail-closed.
_SEC_ISSUER_LEVEL_COMPLETED_ANNUAL_FIELDS = (
    frozenset(
        {
            FinancialField.OPERATING_CASH_FLOW,
            FinancialField.CAPITAL_EXPENDITURES,
        }
    )
    | ANNUAL_PERIOD_FIELDS
)
_SEC_SECURITY_UNIT_SENSITIVE_COMPLETED_ANNUAL_FIELDS = frozenset(
    {
        FinancialField.EPS,
        FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
    }
)

# These SEC capabilities return completed fiscal-year duration series and use
# the shared annual-candidate eligibility boundary.
_SEC_COMPLETED_ANNUAL_FIELDS = (
    _SEC_ISSUER_LEVEL_COMPLETED_ANNUAL_FIELDS | _SEC_SECURITY_UNIT_SENSITIVE_COMPLETED_ANNUAL_FIELDS
)


@dataclass(frozen=True)
class _BalanceSheetParseContext:
    """Context shared while converting one SEC balance-sheet observation."""

    request: FinancialFactRequest
    provider_field: str
    unit: FinancialUnit
    currency: str | None
    acceptance_by_accession: Mapping[str, datetime]
    retrieved_at: datetime
    forms: frozenset[str] = _BALANCE_SHEET_FORMS


@dataclass(frozen=True)
class _AnnualCashFlowParseContext:
    """Context shared while converting one SEC annual cash-flow observation."""

    request: FinancialFactRequest
    cik: str
    currency: str
    acceptance_by_accession: Mapping[str, datetime]
    retrieved_at: datetime
    provider_field: str


@dataclass(frozen=True)
class _AnnualEpsParseContext:
    """Context shared while converting one SEC annual diluted-EPS observation."""

    request: FinancialFactRequest
    cik: str
    currency: str
    acceptance_by_accession: Mapping[str, datetime]
    retrieved_at: datetime
    provider_field: str


@dataclass(frozen=True)
class SubmissionPage:
    """One extra page of an issuer's submissions history, as the `filings.files` list names it."""

    name: str
    filing_from: date
    filing_to: date


@dataclass(frozen=True)
class _SecShareObservation:
    """One raw SEC share-count observation used for provider-specific derivation."""

    value: float
    provider_field: str
    accession: str
    retrieved_at: datetime
    observation_period_end: datetime
    available_at: datetime


@dataclass(frozen=True)
class SecEdgarAnalysisSnapshot:
    """Immutable Company Facts and filing-regime evidence for one analysis."""

    subject_id: str
    cik: str | None
    as_of: datetime
    retrieved_at: datetime
    company_facts: object
    acceptance_by_accession: Mapping[str, datetime]
    accession_taxonomies: Mapping[str, frozenset[str]]
    latest_annual_accession: str | None
    eligible_annual_accessions: tuple[str, ...]
    taxonomy: str | None
    primary_documents: Mapping[str, str] = field(default_factory=dict)
    filing_forms: Mapping[str, str] = field(default_factory=dict)
    filing_dates: Mapping[str, date] = field(default_factory=dict)
    current_tickers: tuple[str, ...] = ()
    submission_pages: tuple[SubmissionPage, ...] = ()


_ACTIVE_SNAPSHOT: ContextVar[SecEdgarAnalysisSnapshot | None] = ContextVar("sec_edgar_analysis_snapshot", default=None)


class SecEdgarFinancialFactsAdapter:
    """Provide verified SEC observations for deterministic valuation analysis.

    Supported facts are fiscal-year diluted EPS plus fiscal-year-end balance-sheet
    components used by ``InputResolver`` to derive BVPS conservatively. SEC-specific
    fallbacks stay inside this adapter. Common shares may be derived as issued minus
    treasury shares when the direct outstanding-share concept is absent. A zero
    preferred-share guard may be inferred only for narrowly verified Company Facts
    evidence shapes; a merely missing preferred-share tag is still unavailable.
    Direct BVPS remains unsupported by SEC Company Facts here.

    ``available_at`` uses EDGAR ``acceptanceDateTime`` when the accession is
    present in the company's submissions metadata.  When acceptance time is
    absent, the adapter falls back conservatively to the end of the SEC
    ``filed`` date rather than pretending the fact was knowable at midnight.
    """

    def __init__(  # noqa: PLR0913
        self,
        *,
        json_fetcher: JsonFetcher = fetch_json,
        clock: Callable[[], datetime] | None = None,
        user_agent: str,
        filing_fetcher: FilingFetcher = fetch_filing,
        filing_policy: FilingReaderPolicy | None = None,
        header_fetcher: FilingHeaderFetcher = fetch_filing_header,
        header_policy: FilingHeaderPolicy | None = None,
        cover_fetcher: CoverFetcher = fetch_cover,
        cover_policy: CoverReaderPolicy | None = None,
    ) -> None:
        """Initialize the adapter with injectable transport, clock, and SEC identity.

        The caller supplies the declared ``user_agent`` (the composition root takes it from the application
        settings); the adapter never reads the environment. A non-empty identity is required before any SEC
        request can be made.
        """
        resolved_user_agent = _resolve_sec_user_agent(user_agent)
        self._fetch_json = json_fetcher
        self._filing_fetcher = filing_fetcher
        self._filing_policy = filing_policy or FilingReaderPolicy()
        self._header_fetcher = header_fetcher
        self._header_policy = header_policy or FilingHeaderPolicy()
        self._header_texts: dict[tuple[str, str], tuple[str, datetime]] = {}
        self._cover_fetcher = cover_fetcher
        self._cover_policy = cover_policy or CoverReaderPolicy()
        self._cover_texts: dict[tuple[str, str], tuple[str, str, datetime]] = {}
        self._submission_page_documents: dict[tuple[str, str], object] = {}
        self._clock = clock or utc_now
        self._headers = {"User-Agent": resolved_user_agent, "Accept": "application/json"}
        self._ticker_to_cik: dict[str, str] | None = None
        self._cik_to_tickers: dict[str, frozenset[str]] | None = None
        self._security_identities: dict[str, SecurityIdentity] | None = None

    def create_analysis_snapshot(self, *, subject_id: str, as_of: datetime | None) -> SecEdgarAnalysisSnapshot:
        """Fetch and freeze one SEC payload pair and its effective taxonomy regime."""
        ticker = subject_id.strip().upper()
        retrieved_at = self._clock()
        effective_as_of = as_of or retrieved_at
        try:
            cik = self._resolve_cik(ticker)
        except _MissingCikError:
            return SecEdgarAnalysisSnapshot(
                subject_id=ticker,
                cik=None,
                as_of=effective_as_of,
                retrieved_at=retrieved_at,
                company_facts=MappingProxyType({}),
                acceptance_by_accession=MappingProxyType({}),
                accession_taxonomies=MappingProxyType({}),
                latest_annual_accession=None,
                eligible_annual_accessions=(),
                taxonomy=None,
            )
        company_facts_raw = self._fetch_company_document(_COMPANY_FACTS_URL.format(cik=cik))
        submissions_raw = self._fetch_company_document(_SUBMISSIONS_URL.format(cik=cik))
        acceptance_by_accession = _acceptance_times(submissions_raw)
        accession_taxonomies = _accession_taxonomies(company_facts_raw)
        eligible_accessions = _eligible_annual_accessions(
            submissions_raw,
            acceptance_by_accession=acceptance_by_accession,
            as_of=effective_as_of,
        )
        latest_accession = eligible_accessions[0] if eligible_accessions else None
        namespaces = accession_taxonomies.get(latest_accession, frozenset()) if latest_accession else frozenset()
        taxonomy = next(iter(namespaces)) if len(namespaces) == 1 else None
        return SecEdgarAnalysisSnapshot(
            subject_id=ticker,
            cik=cik,
            as_of=effective_as_of,
            retrieved_at=retrieved_at,
            company_facts=_freeze_json(company_facts_raw),
            acceptance_by_accession=MappingProxyType(dict(acceptance_by_accession)),
            accession_taxonomies=MappingProxyType(dict(accession_taxonomies)),
            latest_annual_accession=latest_accession,
            eligible_annual_accessions=eligible_accessions,
            taxonomy=taxonomy,
            primary_documents=MappingProxyType(_submission_strings(submissions_raw, "primaryDocument")),
            filing_forms=MappingProxyType(_submission_strings(submissions_raw, "form")),
            filing_dates=MappingProxyType(_submission_filing_dates(submissions_raw)),
            current_tickers=_submission_tickers(submissions_raw),
            submission_pages=_submission_pages(submissions_raw, cik),
        )

    def resolve_as_filed_sic(self, snapshot: SecEdgarAnalysisSnapshot) -> AsFiledSicResolution:
        """Resolve the SIC code the anchor filing's SEC header assigns to the issuer.

        One header request is made for the anchor filing, outside the filing-document limit, and its text is kept for
        the life of the adapter because a filed header never changes; the boundary check is made on every call. A
        header that is missing or unreadable, or that fails a check, gives the reason the class is unknown. A
        transport fault raises the classified ``FinancialProviderError``.
        """
        accession = snapshot.latest_annual_accession
        if snapshot.cik is None or accession is None:
            return AsFiledSicResolution(reason=SicUnavailableReason.NO_ANCHOR_FILING)
        try:
            url = filing_header_url(snapshot.cik, accession)
        except ValueError as exc:
            msg = f"SEC listed a filing that cannot be addressed: {exc}"
            raise FinancialProviderError(
                msg, kind=ProviderFailureKind.UNEXPECTED_RESPONSE, provider_id=SEC_PROVIDER_ID
            ) from exc
        cached = self._header_texts.get((snapshot.cik, accession))
        if cached is None:
            try:
                text = self._header_fetcher(
                    url,
                    headers=self._headers,
                    policy=self._header_policy,
                    not_found=ProviderFailureKind.NO_DATA,
                    provider_id=SEC_PROVIDER_ID,
                )
            except FinancialProviderError as exc:
                if exc.kind is ProviderFailureKind.NO_DATA:
                    return AsFiledSicResolution(reason=SicUnavailableReason.HEADER_MISSING)
                raise
            cached = (text, self._clock())
            self._header_texts[(snapshot.cik, accession)] = cached
        text, retrieved_at = cached
        return parse_filing_header(
            text,
            cik=snapshot.cik,
            accession=accession,
            filing_date=snapshot.filing_dates.get(accession),
            boundary=snapshot.as_of,
            source_url=url,
            retrieved_at=retrieved_at,
        )

    def resolve_cover_listing(self, request: CoverListingRequest) -> ListingResolution:  # noqa: PLR0911
        """Resolve what the anchor filing's cover registers for the requested ticker.

        One cover request is made for the anchor filing, outside the filing-document limit, and its text is kept for
        the life of the adapter because a filed cover never changes; the boundary check is made on every call. The
        read works with ``as_of``: the cover of a filing accepted at or before the boundary is historical evidence.
        A cover that is missing or unreadable, or that fails a check, gives the reason none could be read. A
        transport fault raises the classified ``FinancialProviderError``.
        """
        snapshot = _ACTIVE_SNAPSHOT.get()
        if request.provider_id != SEC_PROVIDER_ID or snapshot is None:
            return ListingResolution(reason=CoverUnavailableReason.NO_ANALYSIS_SCOPE)
        if snapshot.subject_id != request.ticker:
            return ListingResolution(reason=CoverUnavailableReason.SUBJECT_MISMATCH)
        accession = snapshot.latest_annual_accession
        if snapshot.cik is None or accession is None:
            return ListingResolution(reason=CoverUnavailableReason.NO_ANCHOR_FILING)
        form = snapshot.filing_forms.get(accession)
        if not form:
            return ListingResolution(reason=CoverUnavailableReason.FORM_UNAVAILABLE)
        accepted_at = snapshot.acceptance_by_accession.get(accession)
        if accepted_at is None:
            return ListingResolution(reason=CoverUnavailableReason.ACCEPTANCE_UNAVAILABLE)
        if accepted_at > snapshot.as_of:
            return ListingResolution(reason=CoverUnavailableReason.ACCEPTED_AFTER_BOUNDARY)
        try:
            cover_url(snapshot.cik, accession)
        except ValueError as exc:
            msg = f"SEC listed a filing that cannot be addressed: {exc}"
            raise FinancialProviderError(
                msg, kind=ProviderFailureKind.UNEXPECTED_RESPONSE, provider_id=SEC_PROVIDER_ID
            ) from exc
        cached = self._cover_texts.get((snapshot.cik, accession))
        if cached is None:
            try:
                text, url = fetch_anchor_cover(
                    snapshot.cik,
                    accession,
                    fetcher=self._cover_fetcher,
                    headers=self._headers,
                    policy=self._cover_policy,
                    not_found=ProviderFailureKind.NO_DATA,
                    provider_id=SEC_PROVIDER_ID,
                )
            except FinancialProviderError as exc:
                if exc.kind is ProviderFailureKind.NO_DATA:
                    return ListingResolution(reason=CoverUnavailableReason.COVER_MISSING)
                raise
            cached = (text, url, self._clock())
            self._cover_texts[(snapshot.cik, accession)] = cached
        text, url, retrieved_at = cached
        return read_cover_listing(
            text,
            ticker=request.ticker,
            cik=snapshot.cik,
            accession=accession,
            form=form,
            accepted_at=accepted_at,
            boundary=snapshot.as_of,
            source_url=url,
            retrieved_at=retrieved_at,
        )

    def resolve_security_unit(self, request: SecurityUnitRequest) -> SecurityUnitResolution:  # noqa: PLR0911
        """Verify the exact source filings inside the current financial snapshot."""
        if request.as_of is not None:
            return SecurityUnitResolution(SecurityUnitResolutionReason.UNSUPPORTED_TEMPORAL_EVIDENCE)
        snapshot = _ACTIVE_SNAPSHOT.get()
        if request.provider_id != SEC_PROVIDER_ID or snapshot is None or snapshot.taxonomy != "us-gaap":
            return SecurityUnitResolution(SecurityUnitResolutionReason.PROVIDER_UNSUPPORTED)
        if (
            snapshot.subject_id != request.ticker
            or snapshot.cik is None
            or request.ticker not in snapshot.current_tickers
        ):
            return SecurityUnitResolution(SecurityUnitResolutionReason.SOURCE_MISMATCH)
        if request.quote.provider_id != "yfinance" and request.quote.source_kind.value != "override":
            return SecurityUnitResolution(SecurityUnitResolutionReason.PROVIDER_UNSUPPORTED)
        try:
            return self._verify_security_unit(request, snapshot)
        except UnitMappingError:
            return SecurityUnitResolution(SecurityUnitResolutionReason.UNSUPPORTED_EVIDENCE)
        except (FinancialProviderError, DataFetchError) as exc:
            return SecurityUnitResolution(
                SecurityUnitResolutionReason.PROVIDER_ERROR, provider_failure=failure_record(exc)
            )

    def _verify_security_unit(  # noqa: PLR0911
        self, request: SecurityUnitRequest, snapshot: SecEdgarAnalysisSnapshot
    ) -> SecurityUnitResolution:
        assert snapshot.cik is not None
        leaves = source_leaves(request.inputs)
        if any(not item.provider_fact_id for item in leaves):
            return SecurityUnitResolution(SecurityUnitResolutionReason.MISSING_EVIDENCE)
        by_accession = {source_accession(item) for item in leaves}
        if snapshot.latest_annual_accession is None:
            return SecurityUnitResolution(SecurityUnitResolutionReason.MISSING_EVIDENCE)
        by_accession.add(snapshot.latest_annual_accession)
        if len(by_accession) > self._filing_policy.max_documents:
            return SecurityUnitResolution(SecurityUnitResolutionReason.UNSUPPORTED_EVIDENCE)
        documents = []
        titles = set()
        for accession in sorted(by_accession):
            accepted = snapshot.acceptance_by_accession.get(accession)
            primary = snapshot.primary_documents.get(accession)
            if (
                accepted is None
                or accepted > snapshot.as_of
                or not primary
                or snapshot.filing_forms.get(accession) != "10-K"
            ):
                return SecurityUnitResolution(SecurityUnitResolutionReason.UNSUPPORTED_EVIDENCE)
            try:
                url = filing_url(snapshot.cik, accession, primary)
            except ValueError as exc:
                msg = f"SEC listed a filing that cannot be addressed: {exc}"
                raise FinancialProviderError(
                    msg, kind=ProviderFailureKind.UNEXPECTED_RESPONSE, provider_id=SEC_PROVIDER_ID
                ) from exc
            markup = self._filing_fetcher(
                url,
                headers=self._headers,
                policy=self._filing_policy,
                not_found=ProviderFailureKind.NO_DATA,
                provider_id=SEC_PROVIDER_ID,
            )
            if len(markup.encode("utf-8")) > self._filing_policy.max_document_bytes:
                return SecurityUnitResolution(SecurityUnitResolutionReason.UNSUPPORTED_EVIDENCE)
            parsed = parse_unit_document(markup, cik=snapshot.cik, ticker=request.ticker)
            context_ids = set(parsed.class_contexts)
            for leaf in leaves:
                if source_accession(leaf) == accession:
                    context_ids.update(parsed.verify(leaf))
            titles.add(parsed.class_title)
            documents.append(
                SecurityUnitDocument(
                    accession, url, tuple(sorted(context_ids)), accepted, self._clock(), parsed.listing_venue
                )
            )
        if len(titles) != 1:
            return SecurityUnitResolution(SecurityUnitResolutionReason.AMBIGUOUS_CLASS)
        return SecurityUnitResolution(
            SecurityUnitResolutionReason.RESOLVED,
            SecurityUnitEvidence(
                request.ticker,
                SecurityUnitKind.ORDINARY_SHARE,
                SecurityUnitKind.ORDINARY_SHARE,
                1.0,
                SEC_PROVIDER_ID,
                MAPPING_ID,
            ),
            SecurityUnitProvenance(MAPPING_ID, snapshot.cik, titles.pop(), tuple(documents)),
        )

    @contextmanager
    def analysis_scope(
        self,
        *,
        subject_id: str,
        provider_id: str,
        as_of: datetime | None,
    ) -> Iterator[None]:
        """Reuse one immutable SEC snapshot throughout an analysis request."""
        if provider_id.strip().lower() != SEC_PROVIDER_ID:
            yield
            return
        snapshot = self.create_analysis_snapshot(subject_id=subject_id, as_of=as_of)
        token = _ACTIVE_SNAPSHOT.set(snapshot)
        try:
            yield
        finally:
            _ACTIVE_SNAPSHOT.reset(token)

    def fetch_instant_series(self, request: InstantSeriesRequest, *, effective_as_of: datetime) -> InstantSeriesFacts:
        """Return the balance-sheet value the eligible annual filings report at each requested year-end.

        The anchor filing is the newest annual filing accepted at or before the boundary, and the taxonomy is the one
        it tags. A year-end it does not report may come from an earlier eligible filing on the same taxonomy; see
        ``select_instant_series`` for the selection rules.

        Args:
            request: The exact-date series request.
            effective_as_of: The resolved point-in-time boundary when the request names none.

        Raises:
            FinancialProviderError: On an operational provider failure.
        """
        boundary = request.as_of or effective_as_of
        if request.provider_id != SEC_PROVIDER_ID:
            return _all_absent(request, InstantAbsenceReason.UNSUPPORTED, "SEC EDGAR does not serve this provider.")
        try:
            try:
                cik = self._resolve_cik(request.subject_id)
            except _MissingCikError:
                return _all_absent(
                    request, InstantAbsenceReason.NO_ANCHOR_FILING, "SEC EDGAR has no CIK for the ticker."
                )
            snapshot = _ACTIVE_SNAPSHOT.get()
            if snapshot is None or snapshot.subject_id != request.subject_id:
                snapshot = self.create_analysis_snapshot(subject_id=request.subject_id, as_of=boundary)
            if snapshot.cik != cik:
                return _all_absent(
                    request, InstantAbsenceReason.UNSUPPORTED, "The analysis snapshot is for another issuer."
                )
            acceptance, forms = self._filings_reaching_back(snapshot, request.period_ends[0], boundary)
            eligible = {
                accession: accepted
                for accession, accepted in acceptance.items()
                if forms.get(accession) in _COMPLETED_ANNUAL_FORMS and accepted <= boundary
            }
            anchor = max(eligible, key=lambda accession: eligible[accession], default=None)
            namespaces = snapshot.accession_taxonomies.get(anchor, frozenset()) if anchor is not None else frozenset()
            company_facts = snapshot.company_facts if isinstance(snapshot.company_facts, Mapping) else {}
            return select_instant_series(
                request,
                InstantSource(
                    company_facts=company_facts,
                    cik_matches=_company_facts_matches_cik(company_facts, cik),
                    taxonomy=next(iter(namespaces)) if len(namespaces) == 1 else None,
                    acceptance_by_accession=eligible,
                    accession_taxonomies=snapshot.accession_taxonomies,
                    retrieved_at=snapshot.retrieved_at,
                    boundary=boundary,
                ),
            )
        except FinancialProviderError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            msg = f"SEC EDGAR balance-sheet series retrieval failed for {request.subject_id}: {exc}"
            raise FinancialProviderError(
                msg, kind=ProviderFailureKind.UNEXPECTED_RESPONSE, provider_id=SEC_PROVIDER_ID
            ) from exc

    def _filings_reaching_back(
        self, snapshot: SecEdgarAnalysisSnapshot, oldest: date, boundary: datetime
    ) -> tuple[dict[str, datetime], dict[str, str]]:
        """Return the acceptance times and forms of the recent filings, with older pages added when they are needed.

        A year-end is reported by the annual filing made after it and by the next year's filing, which repeats it as a
        comparative. The recent block is enough when an annual filing accepted at the boundary or before was filed
        after ``oldest`` and within two years of it. Otherwise the extra pages the submissions data lists are read,
        nearest to that window first, until one is enough or ``_MAX_SUBMISSION_PAGES`` have been read. Nothing else
        reads these pages, so no other resolution changes.
        """
        acceptance = dict(snapshot.acceptance_by_accession)
        forms = dict(snapshot.filing_forms)
        dates = dict(snapshot.filing_dates)
        window_end = oldest + timedelta(days=2 * 365)

        def enough() -> bool:
            return any(
                forms.get(accession) in _COMPLETED_ANNUAL_FORMS
                and accepted <= boundary
                and oldest < dates.get(accession, accepted.date()) <= window_end
                for accession, accepted in acceptance.items()
            )

        if enough() or snapshot.cik is None:
            return acceptance, forms
        pages = sorted(
            (page for page in snapshot.submission_pages if page.filing_to > oldest and page.filing_from <= window_end),
            key=lambda page: page.filing_from,
            reverse=True,
        )
        for page in pages[:_MAX_SUBMISSION_PAGES]:
            wrapped = {"filings": {"recent": self._submission_page(snapshot.cik, page)}}
            acceptance.update(_acceptance_times(wrapped))
            forms.update(_submission_strings(wrapped, "form"))
            dates.update(_submission_filing_dates(wrapped))
            if enough():
                break
        return acceptance, forms

    def _with_older_acceptance_times(  # noqa: PLR0913
        self,
        *,
        cik: str,
        pages: tuple[SubmissionPage, ...],
        acceptance: Mapping[str, datetime],
        company_facts: object,
        request: FinancialFactRequest,
        taxonomy: str,
        boundary: datetime,
    ) -> Mapping[str, datetime]:
        """Add the acceptance times of the older annual filings the series needs, from the extra submissions pages.

        A frequent filer's older filings are not in the recent block, so their facts would carry only the end of the
        filing date as their availability. The Company Facts name each annual filing and its filing date; the extra
        page that holds that date is read, for at most the ``observation_count`` newest filings with no acceptance time
        and at most ``_MAX_SUBMISSION_PAGES`` pages, each once per adapter. Nothing is read when every annual filing of
        the series is in the recent block.
        """
        filed = _annual_filing_dates(company_facts, _annual_concept_names(request.field_name, taxonomy))
        newest = sorted(((day, accession) for accession, day in filed.items() if day <= boundary.date()), reverse=True)
        missing = [
            (day, accession) for day, accession in newest[: request.observation_count] if accession not in acceptance
        ]
        needed: list[SubmissionPage] = []
        for day, _accession in missing:
            page = next((item for item in pages if item.filing_from <= day <= item.filing_to), None)
            if page is not None and page not in needed:
                needed.append(page)
        if not needed:
            return acceptance
        merged = dict(acceptance)
        for page in needed[:_MAX_SUBMISSION_PAGES]:
            merged.update(_acceptance_times({"filings": {"recent": self._submission_page(cik, page)}}))
        return merged

    def _submission_page(self, cik: str, page: SubmissionPage) -> object:
        """Fetch one extra submissions page once per adapter; its history never changes except by appending."""
        key = (cik, page.name)
        if key not in self._submission_page_documents:
            self._submission_page_documents[key] = self._fetch_company_document(
                _SUBMISSION_PAGE_URL.format(name=page.name)
            )
        return self._submission_page_documents[key]

    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity | None:
        """Return current SEC ticker-title and CIK evidence when available."""
        if request.provider_id != SEC_PROVIDER_ID:
            return None
        self._load_ticker_metadata()
        identities = self._security_identities
        if identities is None:
            return None
        return identities.get(request.ticker)

    def fetch_facts(  # noqa: PLR0911, PLR0912, PLR0915
        self, request: FinancialFactRequest, *, effective_as_of: datetime
    ) -> tuple[ProviderFact, ...]:
        """Return supported SEC facts, or explicit unavailability.

        Args:
            request: The provider-neutral fact request.
            effective_as_of: The resolved point-in-time eligibility boundary for
                annual-candidate and balance-sheet-fact filtering. Independent of
                this adapter's own retrieval clock (used only to stamp ``retrieved_at``).
        """
        if not self._supports(request):
            return ()

        try:
            try:
                cik = self._resolve_cik(request.subject_id)
            except _MissingCikError:
                if request.field_name in _SEC_FIELDS_WITH_UNAVAILABLE_MISSING_IDENTITY:
                    return ()
                raise
            if (
                request.field_name in _SEC_SECURITY_UNIT_SENSITIVE_COMPLETED_ANNUAL_FIELDS
                and not self._has_single_ticker_identity(cik)
            ):
                return ()
            snapshot = _ACTIVE_SNAPSHOT.get()
            if snapshot is not None and snapshot.subject_id == request.subject_id.strip().upper():
                if snapshot.cik != cik:
                    return ()
                if request.field_name in _SEC_COMPLETED_ANNUAL_FIELDS and snapshot.taxonomy not in {
                    "us-gaap",
                    "ifrs-full",
                }:
                    return ()
                company_facts = snapshot.company_facts
                acceptance_by_accession = snapshot.acceptance_by_accession
                provider_now = snapshot.retrieved_at
                anchor_accession = snapshot.latest_annual_accession
                pages = snapshot.submission_pages
            else:
                company_facts = self._fetch_company_document(_COMPANY_FACTS_URL.format(cik=cik))
                submissions = self._fetch_company_document(_SUBMISSIONS_URL.format(cik=cik))
                acceptance_by_accession = _acceptance_times(submissions)
                provider_now = self._clock()
                eligible_accessions = _eligible_annual_accessions(
                    submissions,
                    acceptance_by_accession=acceptance_by_accession,
                    as_of=request.as_of or effective_as_of,
                )
                anchor_accession = eligible_accessions[0] if eligible_accessions else None
                pages = _submission_pages(submissions, cik)
            taxonomy = snapshot.taxonomy if snapshot is not None and snapshot.taxonomy is not None else "us-gaap"
            if request.field_name in _SEC_COMPLETED_ANNUAL_FIELDS:
                acceptance_by_accession = self._with_older_acceptance_times(
                    cik=cik,
                    pages=pages,
                    acceptance=acceptance_by_accession,
                    company_facts=company_facts,
                    request=request,
                    taxonomy=taxonomy,
                    boundary=request.as_of or effective_as_of,
                )
            if request.field_name in ANNUAL_PERIOD_FIELDS:
                facts = select_annual_period_facts(
                    company_facts,
                    request=request,
                    cik=cik,
                    acceptance_by_accession=acceptance_by_accession,
                    retrieved_at=provider_now,
                    taxonomy=taxonomy,
                    boundary=request.as_of or effective_as_of,
                )
                return _enforce_snapshot_regime(facts, request=request, snapshot=snapshot)
            if request.field_name is FinancialField.OPERATING_CASH_FLOW:
                candidates = _annual_operating_cash_flow_candidates(
                    company_facts,
                    request=request,
                    cik=cik,
                    acceptance_by_accession=acceptance_by_accession,
                    retrieved_at=provider_now,
                    taxonomy=taxonomy,
                )
                facts = _eligible_annual_candidates(candidates, request=request, now=effective_as_of)
                return _enforce_snapshot_regime(facts, request=request, snapshot=snapshot)
            if request.field_name is FinancialField.CAPITAL_EXPENDITURES:
                candidates = _annual_capital_expenditure_candidates(
                    company_facts,
                    request=request,
                    cik=cik,
                    acceptance_by_accession=acceptance_by_accession,
                    retrieved_at=provider_now,
                    taxonomy=taxonomy,
                )
                facts = _eligible_annual_candidates(candidates, request=request, now=effective_as_of)
                return _enforce_snapshot_regime(facts, request=request, snapshot=snapshot)
            if request.field_name is FinancialField.EPS:
                candidates = _annual_eps_candidates(
                    company_facts,
                    request=request,
                    cik=cik,
                    acceptance_by_accession=acceptance_by_accession,
                    retrieved_at=provider_now,
                    taxonomy=taxonomy,
                )
                facts = _reconcile_annual_eps(candidates, request=request, now=effective_as_of)
                return _enforce_snapshot_regime(facts, request=request, snapshot=snapshot)
            if request.field_name is FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES:
                candidates = _annual_diluted_share_candidates(
                    company_facts,
                    request=request,
                    cik=cik,
                    acceptance_by_accession=acceptance_by_accession,
                    retrieved_at=provider_now,
                    taxonomy=taxonomy,
                )
                facts = _reconcile_annual_eps(candidates, request=request, now=effective_as_of)
                return _enforce_snapshot_regime(facts, request=request, snapshot=snapshot)

            if request.field_name is FinancialField.COMMON_SHARES_OUTSTANDING:
                if request.basis == COVER_PAGE_BASIS:
                    return _cover_page_shares_facts(
                        company_facts,
                        request=request,
                        anchor_accession=anchor_accession,
                        acceptance_by_accession=acceptance_by_accession,
                        retrieved_at=provider_now,
                        now=effective_as_of,
                    )
                return _common_shares_facts(
                    company_facts,
                    request=request,
                    acceptance_by_accession=acceptance_by_accession,
                    retrieved_at=provider_now,
                    now=effective_as_of,
                )
            if request.field_name is FinancialField.PREFERRED_SHARES_OUTSTANDING:
                return _preferred_shares_facts(
                    company_facts,
                    request=request,
                    acceptance_by_accession=acceptance_by_accession,
                    retrieved_at=provider_now,
                    now=effective_as_of,
                )

            candidates = _balance_sheet_fact_candidates(
                company_facts,
                request=request,
                acceptance_by_accession=acceptance_by_accession,
                retrieved_at=provider_now,
            )
            return _select_latest_balance_sheet_fact(candidates, request=request, now=effective_as_of)
        except FinancialProviderError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            msg = f"SEC EDGAR valuation retrieval failed for {request.subject_id}: {exc}"
            raise FinancialProviderError(
                msg, kind=ProviderFailureKind.UNEXPECTED_RESPONSE, provider_id=SEC_PROVIDER_ID
            ) from exc

    def _supports(self, request: FinancialFactRequest) -> bool:
        if request.provider_id != SEC_PROVIDER_ID or request.subject_kind is not FinancialSubjectKind.SECURITY:
            return False
        if request.field_name in _SEC_COMPLETED_ANNUAL_FIELDS:
            return request.basis == "fiscal_year" and request.observation_count >= 1
        if request.field_name is FinancialField.COMMON_SHARES_OUTSTANDING and request.basis == COVER_PAGE_BASIS:
            return request.observation_count == 1
        return (
            request.field_name in _BALANCE_SHEET_FIELDS
            and request.basis == "fiscal_year_end"
            and request.observation_count == 1
        )

    def _resolve_cik(self, ticker: str) -> str:
        self._load_ticker_metadata()
        ticker_to_cik = self._ticker_to_cik
        assert ticker_to_cik is not None
        try:
            return ticker_to_cik[ticker]
        except KeyError as exc:
            msg = f"SEC EDGAR has no CIK mapping for ticker {ticker!r}."
            raise _MissingCikError(msg, kind=ProviderFailureKind.NO_DATA, provider_id=SEC_PROVIDER_ID) from exc

    def _fetch_company_document(self, url: str) -> object:
        """Fetch one per-company SEC document, whose HTTP 404 means SEC has nothing for the company."""
        document = self._fetch_json(
            url, headers=self._headers, not_found=ProviderFailureKind.NO_DATA, provider_id=SEC_PROVIDER_ID
        )
        _require_mapping(document, "company")
        return document

    def _load_ticker_metadata(self) -> None:
        """Load SEC ticker mappings and descriptive identities only once per adapter."""
        if self._ticker_to_cik is not None:
            return
        payload = self._fetch_json(
            _COMPANY_TICKERS_URL,
            headers=self._headers,
            not_found=ProviderFailureKind.UNEXPECTED_RESPONSE,
            provider_id=SEC_PROVIDER_ID,
        )
        _require_mapping(payload, "company-ticker")
        resolved_at = self._clock()
        self._ticker_to_cik = _ticker_cik_map(payload)
        self._cik_to_tickers = _cik_tickers_map(payload)
        self._security_identities = _ticker_identity_map(payload, resolved_at=resolved_at)

    def _has_single_ticker_identity(self, cik: str) -> bool:
        """Return whether the resolved CIK has exactly one listed SEC ticker."""
        cik_to_tickers = self._cik_to_tickers
        if cik_to_tickers is None:
            return False
        return len(cik_to_tickers.get(cik, ())) == 1


def _require_mapping(payload: object, name: str) -> None:
    """Reject an SEC document that is not a JSON object, which is not the form the adapter reads."""
    if not isinstance(payload, Mapping):
        msg = f"SEC {name} document is not a JSON object."
        raise FinancialProviderError(msg, kind=ProviderFailureKind.UNEXPECTED_RESPONSE, provider_id=SEC_PROVIDER_ID)


def _resolve_sec_user_agent(user_agent: str) -> str:
    """Return the declared SEC identity, rejecting an empty one."""
    if not user_agent.strip():
        msg = "SEC EDGAR requires a declared User-Agent; pass a non-empty user_agent."
        raise ValueError(msg)
    return user_agent.strip()


def _ticker_cik_map(payload: object) -> dict[str, str]:
    """Parse SEC ``company_tickers.json`` into ticker -> zero-padded CIK."""
    if not isinstance(payload, Mapping):
        msg = "SEC company-ticker payload is not an object."
        raise ValueError(msg)

    result: dict[str, str] = {}
    for item in payload.values():
        if not isinstance(item, Mapping):
            continue
        ticker = item.get("ticker")
        cik = item.get("cik_str")
        if not isinstance(ticker, str) or not isinstance(cik, (int, str)):
            continue
        cik_text = str(cik).strip()
        if not cik_text.isdigit():
            continue
        result[ticker.strip().upper()] = cik_text.zfill(10)
    return result


def _cik_tickers_map(payload: object) -> dict[str, frozenset[str]]:
    """Parse SEC ticker data into zero-padded CIK -> distinct listed tickers."""
    if not isinstance(payload, Mapping):
        return {}

    mutable: dict[str, set[str]] = {}
    for item in payload.values():
        if not isinstance(item, Mapping):
            continue
        ticker = item.get("ticker")
        cik = item.get("cik_str")
        if not isinstance(ticker, str) or not isinstance(cik, (int, str)):
            continue
        cik_text = str(cik).strip()
        ticker_text = ticker.strip().upper()
        if not cik_text.isdigit() or not ticker_text:
            continue
        mutable.setdefault(cik_text.zfill(10), set()).add(ticker_text)
    return {cik: frozenset(tickers) for cik, tickers in mutable.items()}


def _ticker_identity_map(payload: object, *, resolved_at: datetime) -> dict[str, SecurityIdentity]:
    """Parse current SEC ticker-title/CIK evidence into identity snapshots."""
    if not isinstance(payload, Mapping):
        return {}

    result: dict[str, SecurityIdentity] = {}
    for item in payload.values():
        if not isinstance(item, Mapping):
            continue
        ticker = item.get("ticker")
        title = item.get("title")
        cik = item.get("cik_str")
        if not isinstance(ticker, str) or not isinstance(title, str) or not isinstance(cik, (int, str)):
            continue
        ticker_text = ticker.strip().upper()
        cik_text = str(cik).strip()
        if not ticker_text or not title.strip() or not cik_text.isdigit():
            continue
        result[ticker_text] = SecurityIdentity(
            ticker=ticker_text,
            instrument_name=title,
            issuer_identifier=cik_text.zfill(10),
            provider_id=SEC_PROVIDER_ID,
            resolved_at=resolved_at,
        )
    return result


def _submission_strings(payload: object, field_name: str) -> dict[str, str]:
    """Retain exact recent-filing fields without guessing historical filenames."""
    if not isinstance(payload, Mapping):
        return {}
    filings = payload.get("filings")
    if not isinstance(filings, Mapping):
        return {}
    recent = filings.get("recent")
    if not isinstance(recent, Mapping):
        return {}
    accessions, values = recent.get("accessionNumber"), recent.get(field_name)
    if not isinstance(accessions, (list, tuple)) or not isinstance(values, (list, tuple)):
        return {}
    return {
        accession: value
        for accession, value in zip(accessions, values, strict=False)
        if isinstance(accession, str) and isinstance(value, str)
    }


def _submission_filing_dates(payload: object) -> dict[str, date]:
    """Return accession -> SEC filing date for recent submissions, skipping any value that is not a date."""
    result: dict[str, date] = {}
    for accession, value in _submission_strings(payload, "filingDate").items():
        try:
            result[accession] = date.fromisoformat(value)
        except ValueError:
            continue
    return result


# The concepts each completed-annual field reads, per taxonomy, so that the filings that report them can be listed.
_ANNUAL_CONCEPT_NAMES: Mapping[FinancialField, Mapping[str, tuple[str, ...]]] = {
    FinancialField.OPERATING_CASH_FLOW: {
        "us-gaap": ("NetCashProvidedByUsedInOperatingActivities",),
        "ifrs-full": ("CashFlowsFromUsedInOperatingActivities",),
    },
    FinancialField.CAPITAL_EXPENDITURES: {
        "us-gaap": ("PaymentsToAcquirePropertyPlantAndEquipment",),
        "ifrs-full": ("PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",),
    },
    FinancialField.EPS: {"us-gaap": ("EarningsPerShareDiluted",), "ifrs-full": ("DilutedEarningsLossPerShare",)},
    FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES: {
        "us-gaap": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
        "ifrs-full": ("AdjustedWeightedAverageShares",),
    },
}


def _annual_concept_names(field_name: FinancialField, taxonomy: str) -> tuple[str, ...]:
    """Return the concepts a completed-annual field reads under a taxonomy."""
    return _ANNUAL_CONCEPT_NAMES.get(field_name, {}).get(taxonomy, ()) or annual_concepts(field_name, taxonomy)


def _annual_filing_dates(payload: object, concepts: tuple[str, ...]) -> dict[str, date]:
    """Return accession -> filing date for the annual filings that report any of ``concepts`` in Company Facts."""
    found: dict[str, date] = {}
    if not isinstance(payload, Mapping):
        return found
    facts = payload.get("facts")
    if not isinstance(facts, Mapping):
        return found
    for namespace in facts.values():
        if not isinstance(namespace, Mapping):
            continue
        for name in concepts:
            units = namespace.get(name)
            units = units.get("units") if isinstance(units, Mapping) else None
            for observations in units.values() if isinstance(units, Mapping) else ():
                for observation in observations if isinstance(observations, Sequence) else ():
                    if not isinstance(observation, Mapping) or observation.get("form") not in _COMPLETED_ANNUAL_FORMS:
                        continue
                    accession, filed = observation.get("accn"), observation.get("filed")
                    if isinstance(accession, str) and isinstance(filed, str):
                        try:
                            found[accession] = date.fromisoformat(filed)
                        except ValueError:
                            continue
    return found


def _submission_pages(payload: object, cik: str) -> tuple[SubmissionPage, ...]:
    """Return the extra submissions pages the issuer's own document lists, skipping any entry that is not usable.

    A page is usable when its name is the issuer's own `CIK<cik>-submissions-NNN.json` and its filing range is valid.
    """
    filings = payload.get("filings") if isinstance(payload, Mapping) else None
    listed = filings.get("files") if isinstance(filings, Mapping) else None
    if not isinstance(listed, Sequence) or isinstance(listed, (str, bytes)):
        return ()
    pages: list[SubmissionPage] = []
    for entry in listed:
        if not isinstance(entry, Mapping):
            continue
        name, first, last = entry.get("name"), entry.get("filingFrom"), entry.get("filingTo")
        if not isinstance(name, str) or not isinstance(first, str) or not isinstance(last, str):
            continue
        matched = _SUBMISSION_PAGE_NAME.match(name)
        try:
            filing_from, filing_to = date.fromisoformat(first), date.fromisoformat(last)
        except ValueError:
            continue
        if matched is None or matched.group(1) != cik or filing_from > filing_to:
            continue
        pages.append(SubmissionPage(name, filing_from, filing_to))
    return tuple(pages)


def _submission_tickers(payload: object) -> tuple[str, ...]:
    """Retain current issuer symbols for positive request identity confirmation."""
    tickers = payload.get("tickers") if isinstance(payload, Mapping) else None
    return tuple(value for value in tickers if isinstance(value, str)) if isinstance(tickers, (list, tuple)) else ()


def _acceptance_times(payload: object) -> dict[str, datetime]:
    """Return accession -> EDGAR acceptance timestamp for recent submissions."""
    if not isinstance(payload, Mapping):
        return {}
    filings = payload.get("filings")
    if not isinstance(filings, Mapping):
        return {}
    recent = filings.get("recent")
    if not isinstance(recent, Mapping):
        return {}

    accessions = recent.get("accessionNumber")
    accepted = recent.get("acceptanceDateTime")
    if not isinstance(accessions, Sequence) or isinstance(accessions, (str, bytes)):
        return {}
    if not isinstance(accepted, Sequence) or isinstance(accepted, (str, bytes)):
        return {}

    result: dict[str, datetime] = {}
    for accession, timestamp in zip(accessions, accepted, strict=False):
        if not isinstance(accession, str) or not isinstance(timestamp, str):
            continue
        parsed = _parse_sec_acceptance_datetime(timestamp)
        if parsed is not None:
            result[accession] = parsed
    return result


def _freeze_json(value: object) -> object:
    """Recursively freeze a JSON-compatible payload without changing values."""
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _accession_taxonomies(payload: object) -> dict[str, frozenset[str]]:
    """Return exact SEC taxonomy namespaces observed for each accession."""
    if not isinstance(payload, Mapping):
        return {}
    facts = payload.get("facts")
    if not isinstance(facts, Mapping):
        return {}
    mutable: dict[str, set[str]] = {}
    for namespace in ("us-gaap", "ifrs-full"):
        concepts = facts.get(namespace)
        if not isinstance(concepts, Mapping):
            continue
        for concept in concepts.values():
            if not isinstance(concept, Mapping):
                continue
            units = concept.get("units")
            if not isinstance(units, Mapping):
                continue
            for observations in units.values():
                if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
                    continue
                for observation in observations:
                    if not isinstance(observation, Mapping):
                        continue
                    accession = observation.get("accn")
                    if isinstance(accession, str) and accession:
                        mutable.setdefault(accession, set()).add(namespace)
    return {accession: frozenset(namespaces) for accession, namespaces in mutable.items()}


def _eligible_annual_accessions(
    payload: object,
    *,
    acceptance_by_accession: Mapping[str, datetime],
    as_of: datetime,
) -> tuple[str, ...]:
    """Return annual accessions publicly available at ``as_of``, latest first."""
    if not isinstance(payload, Mapping):
        return ()
    filings = payload.get("filings")
    if not isinstance(filings, Mapping):
        return ()
    recent = filings.get("recent")
    if not isinstance(recent, Mapping):
        return ()
    accessions = recent.get("accessionNumber")
    forms = recent.get("form")
    if not isinstance(accessions, Sequence) or isinstance(accessions, (str, bytes)):
        return ()
    if not isinstance(forms, Sequence) or isinstance(forms, (str, bytes)):
        return ()
    eligible: list[tuple[datetime, str]] = []
    for accession, form in zip(accessions, forms, strict=False):
        if not isinstance(accession, str) or form not in _COMPLETED_ANNUAL_FORMS:
            continue
        accepted_at = acceptance_by_accession.get(accession)
        if accepted_at is not None and accepted_at <= as_of:
            eligible.append((accepted_at, accession))
    return tuple(accession for _, accession in sorted(eligible, reverse=True))


def _enforce_snapshot_regime(
    facts: tuple[ProviderFact, ...],
    *,
    request: FinancialFactRequest,
    snapshot: SecEdgarAnalysisSnapshot | None,
) -> tuple[ProviderFact, ...]:
    """Reject facts or requested spans not proven homogeneous in the locked taxonomy."""
    if snapshot is None:
        return facts
    if snapshot.taxonomy not in {"us-gaap", "ifrs-full"}:
        return ()
    expected_taxonomy = frozenset({snapshot.taxonomy})
    accessions = {accession for fact in facts if (accession := _note_value(fact.notes, "accession")) is not None}
    if any(snapshot.accession_taxonomies.get(accession, frozenset()) != expected_taxonomy for accession in accessions):
        return ()
    if len(facts) < request.observation_count:
        relevant = snapshot.eligible_annual_accessions[: request.observation_count]
        if any(
            snapshot.accession_taxonomies.get(accession, frozenset()) != expected_taxonomy for accession in relevant
        ):
            return ()
    return facts


def _note_value(notes: Sequence[str], key: str) -> str | None:
    """Read one exact ``key=value`` provenance note."""
    prefix = f"{key}="
    return next((note.removeprefix(prefix) for note in notes if note.startswith(prefix)), None)


def _annual_eps_candidates(  # noqa: PLR0913
    payload: object,
    *,
    request: FinancialFactRequest,
    cik: str,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
    taxonomy: str = "us-gaap",
) -> tuple[ProviderFact, ...]:
    """Parse annual ``EarningsPerShareDiluted`` Company Facts observations."""
    if not isinstance(payload, Mapping):
        msg = "SEC Company Facts payload is not an object."
        raise ValueError(msg)
    if not _company_facts_matches_cik(payload, cik):
        return ()

    facts = payload.get("facts")
    if not isinstance(facts, Mapping):
        return ()
    namespace = facts.get(taxonomy)
    if not isinstance(namespace, Mapping):
        return ()
    concept_name = "DilutedEarningsLossPerShare" if taxonomy == "ifrs-full" else "EarningsPerShareDiluted"
    provider_field = SEC_IFRS_EPS_FIELD if taxonomy == "ifrs-full" else SEC_EPS_FIELD
    eps = namespace.get(concept_name)
    if not isinstance(eps, Mapping):
        return ()
    units = eps.get("units")
    if not isinstance(units, Mapping):
        return ()

    result: list[ProviderFact] = []
    for unit_name, observations in units.items():
        currency = _currency_from_sec_unit(unit_name)
        if currency is None:
            continue
        if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
            continue
        context = _AnnualEpsParseContext(
            request=request,
            cik=cik,
            currency=currency,
            acceptance_by_accession=acceptance_by_accession,
            retrieved_at=retrieved_at,
            provider_field=provider_field,
        )
        for observation in observations:
            if not isinstance(observation, Mapping):
                continue
            fact = _parse_eps_observation(
                observation,
                context=context,
            )
            if fact is not None:
                result.append(fact)
    return tuple(result)


def _annual_diluted_share_candidates(  # noqa: PLR0913
    payload: object,
    *,
    request: FinancialFactRequest,
    cik: str,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
    taxonomy: str = "us-gaap",
) -> tuple[ProviderFact, ...]:
    """Parse exact-concept annual weighted-average diluted-share facts."""
    if not isinstance(payload, Mapping) or not _company_facts_matches_cik(payload, cik):
        return ()
    facts = payload.get("facts")
    namespace = facts.get(taxonomy) if isinstance(facts, Mapping) else None
    concept_name = (
        "AdjustedWeightedAverageShares"
        if taxonomy == "ifrs-full"
        else "WeightedAverageNumberOfDilutedSharesOutstanding"
    )
    provider_field = (
        SEC_IFRS_WEIGHTED_AVERAGE_DILUTED_SHARES_FIELD
        if taxonomy == "ifrs-full"
        else SEC_WEIGHTED_AVERAGE_DILUTED_SHARES_FIELD
    )
    concept = namespace.get(concept_name) if isinstance(namespace, Mapping) else None
    units = concept.get("units") if isinstance(concept, Mapping) else None
    observations = units.get("shares") if isinstance(units, Mapping) else None
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        return ()
    result: list[ProviderFact] = []
    for observation in observations:
        if not isinstance(observation, Mapping):
            continue
        fact = _parse_diluted_share_observation(
            observation,
            request=request,
            cik=cik,
            acceptance_by_accession=acceptance_by_accession,
            retrieved_at=retrieved_at,
            provider_field=provider_field,
        )
        if fact is not None:
            result.append(fact)
    return tuple(result)


def _annual_operating_cash_flow_candidates(  # noqa: PLR0913
    payload: object,
    *,
    request: FinancialFactRequest,
    cik: str,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
    taxonomy: str = "us-gaap",
) -> tuple[ProviderFact, ...]:
    """Parse exact-concept completed-annual operating-cash-flow observations."""
    if not isinstance(payload, Mapping):
        msg = "SEC Company Facts payload is not an object."
        raise ValueError(msg)
    if not _company_facts_matches_cik(payload, cik):
        return ()

    facts = payload.get("facts")
    if not isinstance(facts, Mapping):
        return ()
    namespace = facts.get(taxonomy)
    if not isinstance(namespace, Mapping):
        return ()
    concept_name = (
        "CashFlowsFromUsedInOperatingActivities"
        if taxonomy == "ifrs-full"
        else "NetCashProvidedByUsedInOperatingActivities"
    )
    provider_field = SEC_IFRS_OPERATING_CASH_FLOW_FIELD if taxonomy == "ifrs-full" else SEC_OPERATING_CASH_FLOW_FIELD
    concept = namespace.get(concept_name)
    if not isinstance(concept, Mapping):
        return ()
    units = concept.get("units")
    if not isinstance(units, Mapping):
        return ()

    result: list[ProviderFact] = []
    for unit_name, observations in units.items():
        currency = _currency_from_sec_monetary_unit(unit_name)
        if currency is None:
            continue
        if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
            continue
        context = _AnnualCashFlowParseContext(
            request=request,
            cik=cik,
            currency=currency,
            acceptance_by_accession=acceptance_by_accession,
            retrieved_at=retrieved_at,
            provider_field=provider_field,
        )
        for observation in observations:
            if not isinstance(observation, Mapping):
                continue
            fact = _parse_operating_cash_flow_observation(
                observation,
                context=context,
            )
            if fact is not None:
                result.append(fact)
    return tuple(result)


def _annual_capital_expenditure_candidates(  # noqa: PLR0913
    payload: object,
    *,
    request: FinancialFactRequest,
    cik: str,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
    taxonomy: str = "us-gaap",
) -> tuple[ProviderFact, ...]:
    """Parse exact-concept completed-annual PP&E acquisition payments."""
    if not isinstance(payload, Mapping):
        msg = "SEC Company Facts payload is not an object."
        raise ValueError(msg)
    if not _company_facts_matches_cik(payload, cik):
        return ()

    facts = payload.get("facts")
    if not isinstance(facts, Mapping):
        return ()
    namespace = facts.get(taxonomy)
    if not isinstance(namespace, Mapping):
        return ()
    concept_name = (
        "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"
        if taxonomy == "ifrs-full"
        else "PaymentsToAcquirePropertyPlantAndEquipment"
    )
    provider_field = SEC_IFRS_CAPITAL_EXPENDITURES_FIELD if taxonomy == "ifrs-full" else SEC_CAPITAL_EXPENDITURES_FIELD
    concept = namespace.get(concept_name)
    if not isinstance(concept, Mapping):
        return ()
    units = concept.get("units")
    if not isinstance(units, Mapping):
        return ()

    result: list[ProviderFact] = []
    for unit_name, observations in units.items():
        currency = _currency_from_sec_monetary_unit(unit_name)
        if currency is None:
            continue
        if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
            continue
        context = _AnnualCashFlowParseContext(
            request=request,
            cik=cik,
            currency=currency,
            acceptance_by_accession=acceptance_by_accession,
            retrieved_at=retrieved_at,
            provider_field=provider_field,
        )
        for observation in observations:
            if not isinstance(observation, Mapping):
                continue
            fact = _parse_capital_expenditure_observation(observation, context=context)
            if fact is not None:
                result.append(fact)
    return tuple(result)


def _company_facts_matches_cik(payload: Mapping[object, object], expected_cik: str) -> bool:
    """Return whether Company Facts declares the exact resolved CIK and an entity."""
    payload_cik = payload.get("cik")
    entity_name = payload.get("entityName")
    if not isinstance(payload_cik, (int, str)) or not isinstance(entity_name, str) or not entity_name.strip():
        return False
    cik_text = str(payload_cik).strip()
    return cik_text.isdigit() and cik_text.zfill(10) == expected_cik


def _parse_operating_cash_flow_observation(  # noqa: PLR0911
    observation: Mapping[object, object],
    *,
    context: _AnnualCashFlowParseContext,
) -> ProviderFact | None:
    """Parse one exact-concept annual operating-cash-flow observation."""
    form = observation.get("form")
    if form not in _COMPLETED_ANNUAL_FORMS or observation.get("fp") != "FY":
        return None

    value = observation.get("val")
    start = observation.get("start")
    end = observation.get("end")
    accession = observation.get("accn")
    filed = observation.get("filed")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return None
    if not all(isinstance(item, str) for item in (start, end, accession, filed)):
        return None

    start_text = cast(str, start)
    end_text = cast(str, end)
    accession_text = cast(str, accession)
    filed_text = cast(str, filed)
    period_start = _parse_date_start(start_text)
    period_end = _parse_date_end(end_text)
    if period_start is None or period_end is None or not _is_completed_annual_period(period_start, period_end):
        return None

    available_at = context.acceptance_by_accession.get(accession_text)
    if available_at is None:
        available_at = _parse_sec_filed_date_end(filed_text)
        if available_at is None:
            return None
        availability_note = (
            "availability_source=SEC filed date end in America/New_York, converted to UTC; "
            "acceptanceDateTime unavailable"
        )
    else:
        availability_note = "availability_source=SEC submissions acceptanceDateTime, normalized to UTC"

    provider_fy = observation.get("fy")
    fiscal_year = period_end.year
    provider_fact_id = f"{accession_text}:{context.provider_field}:{context.currency}:{start_text}:{end_text}"
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=context.request.subject_id,
        field_name=FinancialField.OPERATING_CASH_FLOW,
        value=numeric_value,
        units=FinancialUnit.CURRENCY,
        provider_id=SEC_PROVIDER_ID,
        provider_field=context.provider_field,
        retrieved_at=context.retrieved_at,
        basis="fiscal_year",
        currency=context.currency,
        observation_period_start=period_start,
        observation_period_end=period_end,
        available_at=available_at,
        notes=(
            f"cik={context.cik}",
            f"accession={accession_text}",
            f"form={form}",
            f"provider_fiscal_year={provider_fy}"
            if isinstance(provider_fy, (int, str))
            else "provider_fiscal_year=unknown",
            "fiscal_year_source=calendar year containing exact SEC period end",
            "definition=net cash provided by or used in all operating activities; signed raw value preserved",
            availability_note,
        ),
        fiscal_year=fiscal_year,
        period_kind=PeriodKind.COMPLETED_ANNUAL,
        accounting_scope=AccountingScope.CONSOLIDATED,
        provider_fact_id=provider_fact_id,
    )


def _parse_capital_expenditure_observation(  # noqa: PLR0911
    observation: Mapping[object, object],
    *,
    context: _AnnualCashFlowParseContext,
) -> ProviderFact | None:
    """Parse one non-negative exact-concept annual PP&E payment observation."""
    form = observation.get("form")
    if form not in _COMPLETED_ANNUAL_FORMS or observation.get("fp") != "FY":
        return None

    value = observation.get("val")
    start = observation.get("start")
    end = observation.get("end")
    accession = observation.get("accn")
    filed = observation.get("filed")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    numeric_value = float(value)
    if not math.isfinite(numeric_value) or numeric_value < 0:
        return None
    if not all(isinstance(item, str) for item in (start, end, accession, filed)):
        return None

    start_text = cast(str, start)
    end_text = cast(str, end)
    accession_text = cast(str, accession)
    filed_text = cast(str, filed)
    period_start = _parse_date_start(start_text)
    period_end = _parse_date_end(end_text)
    if period_start is None or period_end is None or not _is_completed_annual_period(period_start, period_end):
        return None

    available_at = context.acceptance_by_accession.get(accession_text)
    if available_at is None:
        available_at = _parse_sec_filed_date_end(filed_text)
        if available_at is None:
            return None
        availability_note = (
            "availability_source=SEC filed date end in America/New_York, converted to UTC; "
            "acceptanceDateTime unavailable"
        )
    else:
        availability_note = "availability_source=SEC submissions acceptanceDateTime, normalized to UTC"

    provider_fy = observation.get("fy")
    provider_fact_id = f"{accession_text}:{context.provider_field}:{context.currency}:{start_text}:{end_text}"
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=context.request.subject_id,
        field_name=FinancialField.CAPITAL_EXPENDITURES,
        value=numeric_value,
        units=FinancialUnit.CURRENCY,
        provider_id=SEC_PROVIDER_ID,
        provider_field=context.provider_field,
        retrieved_at=context.retrieved_at,
        basis="fiscal_year",
        currency=context.currency,
        observation_period_start=period_start,
        observation_period_end=period_end,
        available_at=available_at,
        notes=(
            f"cik={context.cik}",
            f"accession={accession_text}",
            f"form={form}",
            f"provider_fiscal_year={provider_fy}"
            if isinstance(provider_fy, (int, str))
            else "provider_fiscal_year=unknown",
            "fiscal_year_source=calendar year containing exact SEC period end",
            "definition=cash paid to acquire property, plant, and equipment; non-negative raw value preserved",
            availability_note,
        ),
        fiscal_year=period_end.year,
        period_kind=PeriodKind.COMPLETED_ANNUAL,
        accounting_scope=AccountingScope.CONSOLIDATED,
        capital_expenditure_sign=CapitalExpenditureSign.POSITIVE_EXPENDITURE,
        provider_fact_id=provider_fact_id,
    )


def _is_completed_annual_period(period_start: datetime, period_end: datetime) -> bool:
    """Return whether exact dates have a plausible completed fiscal-year duration."""
    inclusive_days = (period_end.date() - period_start.date()).days + 1
    return _MIN_ANNUAL_DURATION_DAYS <= inclusive_days <= _MAX_ANNUAL_DURATION_DAYS


def _eligible_annual_candidates(
    facts: tuple[ProviderFact, ...],
    *,
    request: FinancialFactRequest,
    now: datetime,
) -> tuple[ProviderFact, ...]:
    """Retain annual candidates knowable at the boundary in stable evidence order.

    Restatements and equal-rank duplicates deliberately remain present. The C2
    annual-series resolver owns evidence-aware grouping, latest-version
    selection, deterministic identical-duplicate handling, and ambiguity.
    """
    boundary = request.as_of or now
    eligible = (
        fact
        for fact in facts
        if fact.observation_period_end is not None
        and fact.available_at is not None
        and fact.observation_period_end <= boundary
        and fact.available_at <= boundary
    )
    return tuple(
        sorted(
            eligible,
            key=lambda fact: (
                cast(datetime, fact.observation_period_end),
                cast(datetime, fact.observation_period_start),
                cast(datetime, fact.available_at),
                fact.provider_fact_id or "",
            ),
        )
    )


def _balance_sheet_concept_units(
    payload: Mapping[object, object],
    concept_name: str,
    namespace: str = _US_GAAP,
) -> Mapping[object, object] | None:
    """Return the SEC units mapping for one balance-sheet concept of a taxonomy (US-GAAP unless stated)."""
    facts = payload.get("facts")
    if not isinstance(facts, Mapping):
        return None
    us_gaap = facts.get(namespace)
    if not isinstance(us_gaap, Mapping):
        return None
    concept = us_gaap.get(concept_name)
    if not isinstance(concept, Mapping):
        return None
    units = concept.get("units")
    if not isinstance(units, Mapping):
        return None
    return units


def _balance_sheet_fact_candidates(  # noqa: PLR0912, PLR0913
    payload: object,
    *,
    request: FinancialFactRequest,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
    namespace: str = _US_GAAP,
    concept_override: str | None = None,
) -> tuple[ProviderFact, ...]:
    """Parse fiscal-year-end SEC facts used by the conservative BVPS derivation.

    An IFRS concept (``concept_override`` with ``namespace="ifrs-full"``) is read from the annual forms of a foreign
    private issuer as well; the US-GAAP concepts keep the 10-K forms.
    """
    if not isinstance(payload, Mapping):
        msg = "SEC Company Facts payload is not an object."
        raise ValueError(msg)

    mapping = _BALANCE_SHEET_FIELDS.get(request.field_name)
    if mapping is None:
        return ()
    concept_name, expected_unit = mapping
    if concept_override is not None:
        concept_name = concept_override

    units = _balance_sheet_concept_units(payload, concept_name, namespace)
    if units is None:
        return ()

    result: list[ProviderFact] = []
    for unit_name, observations in units.items():
        currency: str | None
        if expected_unit is FinancialUnit.CURRENCY:
            currency = _currency_from_sec_monetary_unit(unit_name)
            if currency is None:
                continue
        else:
            if unit_name != "shares":
                continue
            currency = None

        if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
            continue
        context = _BalanceSheetParseContext(
            request=request,
            provider_field=f"{namespace}:{concept_name}",
            unit=expected_unit,
            currency=currency,
            acceptance_by_accession=acceptance_by_accession,
            retrieved_at=retrieved_at,
            forms=_COMPLETED_ANNUAL_FORMS if namespace == _IFRS_FULL else _BALANCE_SHEET_FORMS,
        )
        for observation in observations:
            if not isinstance(observation, Mapping):
                continue
            fact = _parse_balance_sheet_observation(
                observation,
                context=context,
            )
            if fact is not None:
                result.append(fact)
    return tuple(result)


def _share_concept_observations(
    payload: Mapping[object, object],
    *,
    concept_name: str,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
) -> tuple[_SecShareObservation, ...]:
    """Parse raw share observations without imposing semantic-field invariants."""
    units = _balance_sheet_concept_units(payload, concept_name)
    if units is None:
        return ()
    observations = units.get("shares")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        return ()

    result: list[_SecShareObservation] = []
    provider_field = f"us-gaap:{concept_name}"
    for observation in observations:
        if not isinstance(observation, Mapping):
            continue
        parsed = _parse_share_observation(
            observation,
            provider_field=provider_field,
            acceptance_by_accession=acceptance_by_accession,
            retrieved_at=retrieved_at,
        )
        if parsed is not None:
            result.append(parsed)
    return tuple(result)


def _parse_share_observation(  # noqa: PLR0911
    observation: Mapping[object, object],
    *,
    provider_field: str,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
) -> _SecShareObservation | None:
    """Parse one raw fiscal-year-end share observation."""
    if observation.get("form") not in _BALANCE_SHEET_FORMS:
        return None

    value = observation.get("val")
    end = observation.get("end")
    accession = observation.get("accn")
    filed = observation.get("filed")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return None
    if not all(isinstance(item, str) for item in (end, accession, filed)):
        return None

    period_end = _parse_date_end(cast(str, end))
    if period_end is None:
        return None
    accession_text = cast(str, accession)
    available_at = acceptance_by_accession.get(accession_text)
    if available_at is None:
        available_at = _parse_date_end(cast(str, filed))
    if available_at is None:
        return None

    return _SecShareObservation(
        value=numeric_value,
        provider_field=provider_field,
        accession=accession_text,
        retrieved_at=retrieved_at,
        observation_period_end=period_end,
        available_at=available_at,
    )


def _select_latest_share_observation(
    observations: tuple[_SecShareObservation, ...],
    *,
    request: FinancialFactRequest,
    now: datetime,
) -> tuple[_SecShareObservation, ...]:
    """Select one unambiguous latest raw share observation at the boundary."""
    boundary = request.as_of or now
    eligible = tuple(
        observation
        for observation in observations
        if observation.observation_period_end <= boundary and observation.available_at <= boundary
    )
    if not eligible:
        return ()

    latest_period = max(observation.observation_period_end for observation in eligible)
    period_observations = tuple(
        observation for observation in eligible if observation.observation_period_end == latest_period
    )
    latest_available = max(observation.available_at for observation in period_observations)
    latest_version = tuple(
        observation for observation in period_observations if observation.available_at == latest_available
    )
    if len({observation.value for observation in latest_version}) != 1:
        return ()
    return (latest_version[0],)


def _common_shares_facts(
    payload: object,
    *,
    request: FinancialFactRequest,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
    now: datetime,
) -> tuple[ProviderFact, ...]:
    """Resolve period-end common shares directly or as issued minus treasury shares."""
    if not isinstance(payload, Mapping):
        msg = "SEC Company Facts payload is not an object."
        raise ValueError(msg)

    direct = _balance_sheet_fact_candidates(
        payload,
        request=request,
        acceptance_by_accession=acceptance_by_accession,
        retrieved_at=retrieved_at,
    ) + _balance_sheet_fact_candidates(
        payload,
        request=request,
        acceptance_by_accession=acceptance_by_accession,
        retrieved_at=retrieved_at,
        namespace=_IFRS_FULL,
        concept_override="NumberOfSharesOutstanding",
    )
    selected_direct = _select_latest_balance_sheet_fact(direct, request=request, now=now)
    if selected_direct:
        return selected_direct

    issued = _select_latest_share_observation(
        _share_concept_observations(
            payload,
            concept_name="CommonStockSharesIssued",
            acceptance_by_accession=acceptance_by_accession,
            retrieved_at=retrieved_at,
        ),
        request=request,
        now=now,
    )
    treasury = _select_latest_share_observation(
        _share_concept_observations(
            payload,
            concept_name="TreasuryStockCommonShares",
            acceptance_by_accession=acceptance_by_accession,
            retrieved_at=retrieved_at,
        ),
        request=request,
        now=now,
    )
    if len(issued) != 1 or len(treasury) != 1:
        return ()

    issued_fact = issued[0]
    treasury_fact = treasury[0]
    if issued_fact.observation_period_end != treasury_fact.observation_period_end:
        return ()
    if issued_fact.value <= 0 or treasury_fact.value < 0:
        return ()

    derived_value = issued_fact.value - treasury_fact.value
    if derived_value <= 0:
        return ()

    return (
        ProviderFact(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id=request.subject_id,
            field_name=FinancialField.COMMON_SHARES_OUTSTANDING,
            value=derived_value,
            units=FinancialUnit.SHARES,
            provider_id=SEC_PROVIDER_ID,
            provider_field=_SEC_DERIVED_COMMON_SHARES_FIELD,
            retrieved_at=max(issued_fact.retrieved_at, treasury_fact.retrieved_at),
            basis="fiscal_year_end",
            observation_period_end=issued_fact.observation_period_end,
            available_at=max(issued_fact.available_at, treasury_fact.available_at),
            source_facts=tuple(_share_source_fact(item, request) for item in (issued_fact, treasury_fact)),
            source_transformation="common shares issued - treasury common shares",
            notes=(
                "derivation=common shares outstanding = common shares issued - treasury common shares",
                f"issued_source={issued_fact.provider_field}; accession={issued_fact.accession}; "
                f"value={issued_fact.value}",
                f"treasury_source={treasury_fact.provider_field}; accession={treasury_fact.accession}; "
                f"value={treasury_fact.value}",
                "same-period source observations required; no cover-date DEI share substitution applied",
            ),
        ),
    )


def _cover_page_shares_facts(  # noqa: PLR0913
    payload: object,
    *,
    request: FinancialFactRequest,
    anchor_accession: str | None,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
    now: datetime,
) -> tuple[ProviderFact, ...]:
    """Return the cover-page share count of the anchor annual filing, or nothing.

    The count is used only where the filing tags exactly one non-dimensional total (Company Facts holds no dimensional
    value, so a filer that reports its classes separately has none here). Its own date, the date of the cover page, is
    the share-count date; it is not a balance-sheet fact and the year-end path never returns it.
    """
    if not isinstance(payload, Mapping):
        msg = "SEC Company Facts payload is not an object."
        raise ValueError(msg)
    if anchor_accession is None:
        return ()
    boundary = request.as_of or now
    available_at = acceptance_by_accession.get(anchor_accession)
    if available_at is None or available_at > boundary:
        return ()
    units = _balance_sheet_concept_units(payload, "EntityCommonStockSharesOutstanding", "dei")
    observations = units.get("shares") if units is not None else None
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
        return ()
    found: set[tuple[str, float]] = set()
    for observation in observations:
        if not isinstance(observation, Mapping) or observation.get("accn") != anchor_accession:
            continue
        value, end = observation.get("val"), observation.get("end")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isinstance(end, str):
            continue
        found.add((end, float(value)))
    if len(found) != 1:
        return ()
    end_text, value_number = next(iter(found))
    period_end = _parse_date_end(end_text)
    if period_end is None or period_end > boundary or not math.isfinite(value_number) or value_number <= 0:
        return ()
    return (
        ProviderFact(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id=request.subject_id,
            field_name=FinancialField.COMMON_SHARES_OUTSTANDING,
            value=value_number,
            units=FinancialUnit.SHARES,
            provider_id=SEC_PROVIDER_ID,
            provider_field=SEC_COVER_PAGE_SHARES_FIELD,
            retrieved_at=retrieved_at,
            basis=COVER_PAGE_BASIS,
            observation_period_end=period_end,
            available_at=available_at,
            notes=(
                f"accession={anchor_accession}",
                "definition=cover-page common shares outstanding of the anchor annual filing "
                "as one non-dimensional total",
                "not a balance-sheet fact; for market capitalization only; its own date is the share-count date",
            ),
            provider_fact_id=f"{anchor_accession}:{SEC_COVER_PAGE_SHARES_FIELD}:shares:{end_text}",
        ),
    )


def _all_absent(request: InstantSeriesRequest, reason: InstantAbsenceReason, detail: str) -> InstantSeriesFacts:
    """Report every requested year-end as absent for one reason."""
    return InstantSeriesFacts(
        absences=tuple(InstantAbsence(period_end=day, reason=reason, detail=detail) for day in request.period_ends)
    )


def _share_source_fact(item: _SecShareObservation, request: FinancialFactRequest) -> ProviderShareSource:
    """Preserve exact raw share observations behind the adapter derivation."""
    return ProviderShareSource(
        subject_id=request.subject_id,
        value=item.value,
        provider_id=SEC_PROVIDER_ID,
        provider_field=item.provider_field,
        retrieved_at=item.retrieved_at,
        observation_period_end=item.observation_period_end,
        available_at=item.available_at,
        provider_fact_id=f"{item.accession}:{item.provider_field}:shares:{item.observation_period_end.date()}",
    )


def _preferred_shares_facts(  # noqa: PLR0911
    payload: object,
    *,
    request: FinancialFactRequest,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
    now: datetime,
) -> tuple[ProviderFact, ...]:
    """Resolve explicit preferred shares or one of the verified zero-preferred evidence shapes."""
    if not isinstance(payload, Mapping):
        msg = "SEC Company Facts payload is not an object."
        raise ValueError(msg)

    direct = _balance_sheet_fact_candidates(
        payload,
        request=request,
        acceptance_by_accession=acceptance_by_accession,
        retrieved_at=retrieved_at,
    )
    selected_direct = _select_latest_balance_sheet_fact(direct, request=request, now=now)
    if selected_direct:
        return selected_direct

    equity_request = FinancialFactRequest(
        subject_kind=request.subject_kind,
        subject_id=request.subject_id,
        field_name=FinancialField.STOCKHOLDERS_EQUITY,
        provider_id=request.provider_id,
        basis=request.basis,
        as_of=request.as_of,
    )
    equity_candidates = _balance_sheet_fact_candidates(
        payload,
        request=equity_request,
        acceptance_by_accession=acceptance_by_accession,
        retrieved_at=retrieved_at,
    )
    selected_equity = _select_latest_balance_sheet_fact(equity_candidates, request=equity_request, now=now)
    common = _common_shares_facts(
        payload,
        request=FinancialFactRequest(
            subject_kind=request.subject_kind,
            subject_id=request.subject_id,
            field_name=FinancialField.COMMON_SHARES_OUTSTANDING,
            provider_id=request.provider_id,
            basis=request.basis,
            as_of=request.as_of,
        ),
        acceptance_by_accession=acceptance_by_accession,
        retrieved_at=retrieved_at,
        now=now,
    )
    if len(selected_equity) != 1 or len(common) != 1:
        return ()
    anchor = selected_equity[0]
    common_fact = common[0]
    if anchor.observation_period_end != common_fact.observation_period_end:
        return ()
    if anchor.observation_period_end is None or anchor.available_at is None:
        return ()

    boundary = request.as_of or now
    anchor_period = anchor.observation_period_end
    neutral_concepts, blocked, neutral_available = _classify_preferred_concepts(
        payload,
        boundary=boundary,
        anchor_period=anchor_period,
        acceptance_by_accession=acceptance_by_accession,
    )
    if blocked:
        return ()

    if not neutral_concepts:
        if common_fact.provider_field != _SEC_DERIVED_COMMON_SHARES_FIELD:
            return ()
        evidence_pattern = "no preferred/preference concepts plus same-period issued-minus-treasury common shares"
    else:
        if "PreferredStockSharesAuthorized" not in neutral_concepts:
            return ()
        evidence_pattern = "preferred concepts limited to shares-authorized/par-value-per-share disclosures"

    common_available = cast(datetime, common_fact.available_at)
    inferred_available_at = max(anchor.available_at, common_available)
    if neutral_available is not None:
        inferred_available_at = max(inferred_available_at, neutral_available)

    return (
        ProviderFact(
            subject_kind=FinancialSubjectKind.SECURITY,
            subject_id=request.subject_id,
            field_name=FinancialField.PREFERRED_SHARES_OUTSTANDING,
            value=0.0,
            units=FinancialUnit.SHARES,
            provider_id=SEC_PROVIDER_ID,
            provider_field=_SEC_INFERRED_PREFERRED_ABSENCE_FIELD,
            retrieved_at=anchor.retrieved_at,
            basis="fiscal_year_end",
            observation_period_end=anchor.observation_period_end,
            available_at=inferred_available_at,
            source_facts=(anchor, common_fact),
            source_transformation="zero preferred-share guard verified against SEC Company Facts",
            notes=(
                "evidence=inferred zero preferred-share guard; not an explicit PreferredStockSharesOutstanding fact",
                f"evidence_pattern={evidence_pattern}",
                f"reporting_period_anchor={SEC_STOCKHOLDERS_EQUITY_FIELD}",
                f"inferred_available_at={inferred_available_at.isoformat()}",
                "generic missing preferred-share data remains unavailable outside the verified evidence patterns",
            ),
        ),
    )


def _classify_preferred_concepts(
    payload: Mapping[object, object],
    *,
    boundary: datetime,
    anchor_period: datetime,
    acceptance_by_accession: Mapping[str, datetime],
) -> tuple[frozenset[str], bool, datetime | None]:
    """Classify all preferred/preference concepts as neutral or blocking.

    Returns a tuple of (neutral_concept_names, blocked, neutral_evidence_available_at).
    ``blocked`` is True when any non-neutral preferred-equity concept has an
    eligible observation known at the boundary.
    ``neutral_evidence_available_at`` is the latest ``available_at`` across all
    qualifying neutral observations (or None when no neutral concepts qualify).
    """
    facts = payload.get("facts")
    if not isinstance(facts, Mapping):
        return frozenset(), False, None

    neutral: set[str] = set()
    neutral_available: datetime | None = None
    for namespace_name, namespace in facts.items():
        if not isinstance(namespace_name, str) or not isinstance(namespace, Mapping):
            continue
        for concept_name, metadata in namespace.items():
            if not isinstance(concept_name, str) or not isinstance(metadata, Mapping):
                continue
            if not _concept_is_preferred_equity(concept_name):
                continue
            available = _concept_eligible_annual_observation_available_at(
                metadata,
                boundary=boundary,
                anchor_period=anchor_period,
                acceptance_by_accession=acceptance_by_accession,
            )
            if available is None:
                continue
            if concept_name in _PREFERRED_NEUTRAL_CONCEPTS and namespace_name == "us-gaap":
                neutral.add(concept_name)
                if neutral_available is None or available > neutral_available:
                    neutral_available = available
            else:
                return frozenset(), True, None
    return frozenset(neutral), False, neutral_available


def _concept_is_preferred_equity(concept_name: str) -> bool:
    """Return True when a concept name indicates preferred/preference equity."""
    lower = concept_name.lower()
    return "preferred" in lower or "preference" in lower


def _concept_eligible_annual_observation_available_at(
    metadata: Mapping[object, object],
    *,
    boundary: datetime,
    anchor_period: datetime,
    acceptance_by_accession: Mapping[str, datetime],
) -> datetime | None:
    """Return the available_at of a 10-K observation at the anchor period, or None."""
    units = metadata.get("units")
    if not isinstance(units, Mapping):
        return None

    for observations in units.values():
        if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
            continue
        for observation in observations:
            if not isinstance(observation, Mapping) or observation.get("form") not in _BALANCE_SHEET_FORMS:
                continue
            end = observation.get("end")
            accession = observation.get("accn")
            filed = observation.get("filed")
            if not all(isinstance(item, str) for item in (end, accession, filed)):
                continue
            period_end = _parse_date_end(cast(str, end))
            if period_end is None or period_end != anchor_period:
                continue
            if period_end > boundary:
                continue
            accession_text = cast(str, accession)
            available_at = acceptance_by_accession.get(accession_text)
            if available_at is None:
                available_at = _parse_date_end(cast(str, filed))
            if available_at is not None and available_at <= boundary:
                return available_at
    return None


def _parse_balance_sheet_observation(  # noqa: PLR0911
    observation: Mapping[object, object],
    *,
    context: _BalanceSheetParseContext,
) -> ProviderFact | None:
    request = context.request
    form = observation.get("form")
    if form not in context.forms:
        return None

    value = observation.get("val")
    end = observation.get("end")
    accession = observation.get("accn")
    filed = observation.get("filed")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    if not all(isinstance(item, str) for item in (end, accession, filed)):
        return None

    end_text = cast(str, end)
    accession_text = cast(str, accession)
    filed_text = cast(str, filed)
    period_end = _parse_date_end(end_text)
    if period_end is None:
        return None

    available_at = context.acceptance_by_accession.get(accession_text)
    if available_at is None:
        available_at = _parse_date_end(filed_text)
        if available_at is None:
            return None
        availability_note = "available_at conservatively uses end of SEC filed date; EDGAR acceptance time unavailable"
    else:
        availability_note = "available_at uses EDGAR acceptanceDateTime"

    fy = observation.get("fy")
    fp = observation.get("fp")
    notes = (
        f"accession={accession_text}",
        f"form={form}",
        f"fiscal_year={fy}" if isinstance(fy, (int, str)) else "fiscal_year=unknown",
        f"fiscal_period={fp}" if isinstance(fp, str) else "fiscal_period=unknown",
        _balance_sheet_definition_note(request.field_name),
        availability_note,
    )
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=request.subject_id,
        field_name=request.field_name,
        value=float(value),
        units=context.unit,
        provider_id=SEC_PROVIDER_ID,
        provider_field=context.provider_field,
        retrieved_at=context.retrieved_at,
        basis="fiscal_year_end",
        currency=context.currency,
        observation_period_end=period_end,
        available_at=available_at,
        notes=notes,
        provider_fact_id=f"{accession_text}:{context.provider_field}:{context.currency or 'shares'}:{end_text}",
    )


def _parse_diluted_share_observation(  # noqa: PLR0911, PLR0913
    observation: Mapping[object, object],
    *,
    request: FinancialFactRequest,
    cik: str,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
    provider_field: str,
) -> ProviderFact | None:
    """Parse one completed-annual diluted-share denominator observation."""
    if observation.get("form") not in _COMPLETED_ANNUAL_FORMS or observation.get("fp") != "FY":
        return None
    value = observation.get("val")
    start = observation.get("start")
    end = observation.get("end")
    accession = observation.get("accn")
    filed = observation.get("filed")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    numeric_value = float(value)
    if not math.isfinite(numeric_value) or numeric_value <= 0:
        return None
    if not all(isinstance(item, str) for item in (start, end, accession, filed)):
        return None
    start_text, end_text, accession_text, filed_text = cast(tuple[str, str, str, str], (start, end, accession, filed))
    period_start = _parse_date_start(start_text)
    period_end = _parse_date_end(end_text)
    if period_start is None or period_end is None or not _is_completed_annual_period(period_start, period_end):
        return None
    available_at = acceptance_by_accession.get(accession_text) or _parse_sec_filed_date_end(filed_text)
    if available_at is None:
        return None
    provider_fact_id = f"{accession_text}:{provider_field}:shares:{start_text}:{end_text}"
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=request.subject_id,
        field_name=FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
        value=numeric_value,
        units=FinancialUnit.SHARES,
        provider_id=SEC_PROVIDER_ID,
        provider_field=provider_field,
        retrieved_at=retrieved_at,
        basis="fiscal_year",
        currency=None,
        observation_period_start=period_start,
        observation_period_end=period_end,
        available_at=available_at,
        notes=(f"cik={cik}", f"accession={accession_text}", "definition=weighted-average diluted shares"),
        fiscal_year=period_end.year,
        period_kind=PeriodKind.COMPLETED_ANNUAL,
        accounting_scope=AccountingScope.CONSOLIDATED,
        provider_fact_id=provider_fact_id,
    )


def _parse_eps_observation(  # noqa: PLR0911
    observation: Mapping[object, object],
    *,
    context: _AnnualEpsParseContext,
) -> ProviderFact | None:
    """Parse one exact-concept completed-annual diluted-EPS observation."""
    form = observation.get("form")
    fp = observation.get("fp")
    if form not in _COMPLETED_ANNUAL_FORMS or fp != "FY":
        return None

    value = observation.get("val")
    start = observation.get("start")
    end = observation.get("end")
    accession = observation.get("accn")
    filed = observation.get("filed")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    numeric_value = float(value)
    if not math.isfinite(numeric_value):
        return None
    if not all(isinstance(item, str) for item in (start, end, accession, filed)):
        return None

    start_text = cast(str, start)
    end_text = cast(str, end)
    accession_text = cast(str, accession)
    filed_text = cast(str, filed)
    period_start = _parse_date_start(start_text)
    period_end = _parse_date_end(end_text)
    if period_start is None or period_end is None or not _is_completed_annual_period(period_start, period_end):
        return None

    available_at = context.acceptance_by_accession.get(accession_text)
    availability_note: str
    if available_at is None:
        available_at = _parse_sec_filed_date_end(filed_text)
        if available_at is None:
            return None
        availability_note = (
            "availability_source=SEC filed date end in America/New_York, converted to UTC; "
            "acceptanceDateTime unavailable"
        )
    else:
        availability_note = "availability_source=SEC submissions acceptanceDateTime, normalized to UTC"

    provider_fy = observation.get("fy")
    provider_fact_id = f"{accession_text}:{context.provider_field}:{context.currency}:{start_text}:{end_text}"
    notes = (
        f"cik={context.cik}",
        f"accession={accession_text}",
        f"form={form}",
        f"provider_fiscal_year={provider_fy}"
        if isinstance(provider_fy, (int, str))
        else "provider_fiscal_year=unknown",
        "fiscal_year_source=calendar year containing exact SEC period end",
        "definition=diluted earnings per common share; signed raw value preserved",
        availability_note,
    )
    return ProviderFact(
        subject_kind=FinancialSubjectKind.SECURITY,
        subject_id=context.request.subject_id,
        field_name=FinancialField.EPS,
        value=numeric_value,
        units=FinancialUnit.CURRENCY_PER_SHARE,
        provider_id=SEC_PROVIDER_ID,
        provider_field=context.provider_field,
        retrieved_at=context.retrieved_at,
        basis="fiscal_year",
        currency=context.currency,
        observation_period_start=period_start,
        observation_period_end=period_end,
        available_at=available_at,
        notes=notes,
        fiscal_year=period_end.year,
        period_kind=PeriodKind.COMPLETED_ANNUAL,
        accounting_scope=AccountingScope.CONSOLIDATED,
        provider_fact_id=provider_fact_id,
    )


def _reconcile_annual_eps(
    facts: tuple[ProviderFact, ...],
    *,
    request: FinancialFactRequest,
    now: datetime,
) -> tuple[ProviderFact, ...]:
    """Return the newest requested EPS periods only when they share one basis.

    A changed value for an exact period is evidence of a remeasurement event,
    such as a split-adjusted comparative amount. The latest event in the
    requested span establishes the earliest acceptable filing boundary for
    every period. This deliberately returns no series when an older endpoint
    was not re-presented on that basis.
    """
    eligible = _eligible_annual_candidates(facts, request=request, now=now)
    by_period: dict[tuple[datetime, datetime], list[ProviderFact]] = {}
    for fact in eligible:
        assert fact.observation_period_start is not None
        assert fact.observation_period_end is not None
        by_period.setdefault((fact.observation_period_start, fact.observation_period_end), []).append(fact)

    selected_periods = sorted(by_period, key=lambda period: (period[1], period[0]))[-request.observation_count :]
    if not selected_periods:
        return ()

    common_basis_boundary: datetime | None = None
    for period in selected_periods:
        ordered = sorted(
            by_period[period],
            key=lambda fact: (cast(datetime, fact.available_at), fact.provider_fact_id or ""),
        )
        prior_value = ordered[0].value
        for fact in ordered[1:]:
            if fact.value != prior_value:
                event_time = cast(datetime, fact.available_at)
                common_basis_boundary = (
                    event_time if common_basis_boundary is None else max(common_basis_boundary, event_time)
                )
            prior_value = fact.value

    selected: list[ProviderFact] = []
    for period in selected_periods:
        candidates = by_period[period]
        if common_basis_boundary is not None:
            candidates = [fact for fact in candidates if cast(datetime, fact.available_at) >= common_basis_boundary]
        if not candidates:
            return ()
        latest_time = max(cast(datetime, fact.available_at) for fact in candidates)
        latest = [fact for fact in candidates if fact.available_at == latest_time]
        if len({fact.value for fact in latest}) != 1:
            return ()
        selected.append(min(latest, key=lambda fact: fact.provider_fact_id or ""))
    return tuple(selected)


def _select_latest_balance_sheet_fact(
    facts: tuple[ProviderFact, ...],
    *,
    request: FinancialFactRequest,
    now: datetime,
) -> tuple[ProviderFact, ...]:
    """Select one unambiguous latest fiscal-year-end fact knowable at the boundary.

    Company Facts can contain dimensional observations for multiple share
    classes. If the latest filing exposes differing values for the same
    concept/reporting period end, returning empty is safer than guessing or
    silently summing dimensions.
    """
    boundary = request.as_of or now
    eligible = tuple(
        fact
        for fact in facts
        if fact.observation_period_end is not None
        and fact.available_at is not None
        and fact.observation_period_end <= boundary
        and fact.available_at <= boundary
    )
    if not eligible:
        return ()

    latest_period = max(cast(datetime, fact.observation_period_end) for fact in eligible)
    period_facts = tuple(fact for fact in eligible if fact.observation_period_end == latest_period)
    latest_available = max(cast(datetime, fact.available_at) for fact in period_facts)
    latest_version = tuple(fact for fact in period_facts if fact.available_at == latest_available)
    signatures = {(fact.value, fact.currency) for fact in latest_version}
    if len(signatures) != 1:
        return ()
    return (latest_version[0],)


def _balance_sheet_definition_note(field_name: FinancialField) -> str:
    """Describe the accounting/share semantics retained for a balance-sheet concept."""
    if field_name is FinancialField.STOCKHOLDERS_EQUITY:
        return "definition=stockholders equity attributable to parent; preferred-stock guard required for BVPS"
    if field_name is FinancialField.COMMON_SHARES_OUTSTANDING:
        return "definition=period-end common stock shares outstanding; ambiguous class values are rejected"
    return "definition=nonredeemable preferred stock shares outstanding as reported by us-gaap taxonomy"


def _currency_from_sec_unit(unit_name: object) -> str | None:
    if not isinstance(unit_name, str) or not unit_name.endswith("/shares"):
        return None
    currency = unit_name.removesuffix("/shares")
    if len(currency) != 3 or not currency.isalpha():
        return None
    return currency.upper()


def _currency_from_sec_monetary_unit(unit_name: object) -> str | None:
    """Return an ISO-like three-letter currency code for a monetary SEC unit."""
    if not isinstance(unit_name, str):
        return None
    currency = unit_name.strip()
    if len(currency) != 3 or not currency.isalpha():
        return None
    return currency.upper()


def _parse_sec_acceptance_datetime(value: str) -> datetime | None:
    """Parse SEC acceptance time, treating only legacy naive values as Eastern."""
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        parsed = parsed.replace(tzinfo=_SEC_EASTERN)
    return parsed.astimezone(UTC)


def _parse_date_start(value: str) -> datetime | None:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
    return datetime.combine(parsed, time.min, tzinfo=UTC)


def _parse_date_end(value: str) -> datetime | None:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
    return datetime.combine(parsed, time.max, tzinfo=UTC)


def _parse_sec_filed_date_end(value: str) -> datetime | None:
    """Return end of the SEC filed date in Eastern time, normalized to UTC."""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
    return datetime.combine(parsed, time.max, tzinfo=_SEC_EASTERN).astimezone(UTC)
