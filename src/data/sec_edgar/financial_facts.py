"""SEC EDGAR adapter for annual diluted EPS and BVPS derivation components."""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, time
from types import MappingProxyType
from typing import cast
from zoneinfo import ZoneInfo

from src.data.financial.facts import (
    FinancialFactRequest,
    FinancialField,
    FinancialProviderError,
    FinancialUnit,
    ProviderFact,
)
from src.data.financial.provenance import AccountingScope, CapitalExpenditureSign, FinancialSubjectKind, PeriodKind
from src.data.http_json import JsonFetcher, fetch_json
from src.data.security_identity import SecurityIdentity, SecurityIdentityRequest

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
SEC_COMMON_SHARES_FIELD = "us-gaap:CommonStockSharesOutstanding"
SEC_PREFERRED_SHARES_FIELD = "us-gaap:PreferredStockSharesOutstanding"
_SEC_DERIVED_COMMON_SHARES_FIELD = "derived:us-gaap:CommonStockSharesIssued-us-gaap:TreasuryStockCommonShares"
_SEC_INFERRED_PREFERRED_ABSENCE_FIELD = "inferred:sec-company-facts:no-issued-preferred-equity"
_PREFERRED_NEUTRAL_CONCEPTS = frozenset({"PreferredStockSharesAuthorized", "PreferredStockParOrStatedValuePerShare"})
_SEC_USER_AGENT_ENV = "SEC_USER_AGENT"
_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
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
_SEC_FIELDS_WITH_UNAVAILABLE_MISSING_IDENTITY = frozenset(
    {
        FinancialField.EPS,
        FinancialField.OPERATING_CASH_FLOW,
        FinancialField.CAPITAL_EXPENDITURES,
        FinancialField.WEIGHTED_AVERAGE_DILUTED_SHARES,
    }
)

# SEC Company Facts monetary cash-flow fields describe the issuer, so an exact
# ticker-to-CIK match is sufficient even when the same CIK has other ticker
# rows. Per-share fields describe an issuer share unit; until affirmative unit
# evidence is implemented, multiple ticker rows cannot prove that the requested
# listed security uses that same unit and therefore remain fail-closed.
_SEC_ISSUER_LEVEL_COMPLETED_ANNUAL_FIELDS = frozenset(
    {
        FinancialField.OPERATING_CASH_FLOW,
        FinancialField.CAPITAL_EXPENDITURES,
    }
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
    company_facts_sha256: str
    submissions_sha256: str


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

    def __init__(
        self,
        *,
        json_fetcher: JsonFetcher = fetch_json,
        clock: Callable[[], datetime] | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Initialize the adapter with injectable transport, clock, and SEC identity.

        An explicit ``user_agent`` takes precedence. When it is omitted, the
        adapter reads ``SEC_USER_AGENT`` from the environment. A non-empty
        declared identity is required before any SEC request can be made.
        """
        resolved_user_agent = _resolve_sec_user_agent(user_agent)
        self._fetch_json = json_fetcher
        self._clock = clock or (lambda: datetime.now(UTC))
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
        except FinancialProviderError:
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
                company_facts_sha256=_payload_sha256({}),
                submissions_sha256=_payload_sha256({}),
            )
        company_facts_raw = self._fetch_json(_COMPANY_FACTS_URL.format(cik=cik), headers=self._headers)
        submissions_raw = self._fetch_json(_SUBMISSIONS_URL.format(cik=cik), headers=self._headers)
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
            company_facts_sha256=_payload_sha256(company_facts_raw),
            submissions_sha256=_payload_sha256(submissions_raw),
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

    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity | None:
        """Return current SEC ticker-title and CIK evidence when available."""
        if request.provider_id != SEC_PROVIDER_ID:
            return None
        self._load_ticker_metadata()
        identities = self._security_identities
        if identities is None:
            return None
        return identities.get(request.ticker)

    def fetch_facts(self, request: FinancialFactRequest) -> tuple[ProviderFact, ...]:  # noqa: PLR0911, PLR0912
        """Return supported SEC facts, or explicit unavailability."""
        if not self._supports(request):
            return ()

        try:
            try:
                cik = self._resolve_cik(request.subject_id)
            except FinancialProviderError:
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
            else:
                company_facts = self._fetch_json(
                    _COMPANY_FACTS_URL.format(cik=cik),
                    headers=self._headers,
                )
                submissions = self._fetch_json(
                    _SUBMISSIONS_URL.format(cik=cik),
                    headers=self._headers,
                )
                acceptance_by_accession = _acceptance_times(submissions)
                provider_now = self._clock()
            taxonomy = snapshot.taxonomy if snapshot is not None and snapshot.taxonomy is not None else "us-gaap"
            if request.field_name is FinancialField.OPERATING_CASH_FLOW:
                candidates = _annual_operating_cash_flow_candidates(
                    company_facts,
                    request=request,
                    cik=cik,
                    acceptance_by_accession=acceptance_by_accession,
                    retrieved_at=provider_now,
                    taxonomy=taxonomy,
                )
                facts = _eligible_annual_candidates(candidates, request=request, now=provider_now)
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
                facts = _eligible_annual_candidates(candidates, request=request, now=provider_now)
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
                facts = _reconcile_annual_eps(candidates, request=request, now=provider_now)
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
                facts = _reconcile_annual_eps(candidates, request=request, now=provider_now)
                return _enforce_snapshot_regime(facts, request=request, snapshot=snapshot)

            if request.field_name is FinancialField.COMMON_SHARES_OUTSTANDING:
                return _common_shares_facts(
                    company_facts,
                    request=request,
                    acceptance_by_accession=acceptance_by_accession,
                    retrieved_at=provider_now,
                    now=provider_now,
                )
            if request.field_name is FinancialField.PREFERRED_SHARES_OUTSTANDING:
                return _preferred_shares_facts(
                    company_facts,
                    request=request,
                    acceptance_by_accession=acceptance_by_accession,
                    retrieved_at=provider_now,
                    now=provider_now,
                )

            candidates = _balance_sheet_fact_candidates(
                company_facts,
                request=request,
                acceptance_by_accession=acceptance_by_accession,
                retrieved_at=provider_now,
            )
            return _select_latest_balance_sheet_fact(candidates, request=request, now=provider_now)
        except FinancialProviderError:
            raise
        except (KeyError, TypeError, ValueError, OSError) as exc:
            msg = f"SEC EDGAR valuation retrieval failed for {request.subject_id}: {exc}"
            raise FinancialProviderError(msg) from exc

    def _supports(self, request: FinancialFactRequest) -> bool:
        if request.provider_id != SEC_PROVIDER_ID or request.subject_kind is not FinancialSubjectKind.SECURITY:
            return False
        if request.field_name in _SEC_COMPLETED_ANNUAL_FIELDS:
            return request.basis == "fiscal_year" and request.observation_count >= 1
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
            raise FinancialProviderError(msg) from exc

    def _load_ticker_metadata(self) -> None:
        """Load SEC ticker mappings and descriptive identities only once per adapter."""
        if self._ticker_to_cik is not None:
            return
        payload = self._fetch_json(_COMPANY_TICKERS_URL, headers=self._headers)
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


def _resolve_sec_user_agent(explicit_user_agent: str | None) -> str:
    """Resolve the declared SEC identity from constructor input or environment."""
    candidate = explicit_user_agent if explicit_user_agent is not None else os.getenv(_SEC_USER_AGENT_ENV)
    if candidate is None or not candidate.strip():
        msg = (
            "SEC EDGAR requires a declared User-Agent. "
            "Pass user_agent=... or set the SEC_USER_AGENT environment variable."
        )
        raise ValueError(msg)
    return candidate.strip()


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


def _payload_sha256(payload: object) -> str:
    """Return a stable checksum for one JSON-compatible SEC payload."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
) -> Mapping[object, object] | None:
    """Return the SEC units mapping for one US-GAAP balance-sheet concept."""
    facts = payload.get("facts")
    if not isinstance(facts, Mapping):
        return None
    us_gaap = facts.get("us-gaap")
    if not isinstance(us_gaap, Mapping):
        return None
    concept = us_gaap.get(concept_name)
    if not isinstance(concept, Mapping):
        return None
    units = concept.get("units")
    if not isinstance(units, Mapping):
        return None
    return units


def _balance_sheet_fact_candidates(
    payload: object,
    *,
    request: FinancialFactRequest,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
) -> tuple[ProviderFact, ...]:
    """Parse fiscal-year-end SEC facts used by the conservative BVPS derivation."""
    if not isinstance(payload, Mapping):
        msg = "SEC Company Facts payload is not an object."
        raise ValueError(msg)

    mapping = _BALANCE_SHEET_FIELDS.get(request.field_name)
    if mapping is None:
        return ()
    concept_name, expected_unit = mapping

    units = _balance_sheet_concept_units(payload, concept_name)
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
            provider_field=f"us-gaap:{concept_name}",
            unit=expected_unit,
            currency=currency,
            acceptance_by_accession=acceptance_by_accession,
            retrieved_at=retrieved_at,
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
    if form not in _BALANCE_SHEET_FORMS:
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
