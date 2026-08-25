"""SEC EDGAR adapter for annual diluted EPS and BVPS derivation components."""

from __future__ import annotations

import math
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import cast

from src.data.http_json import JsonFetcher, fetch_json
from src.data.valuation.facts import (
    ProviderFact,
    ValuationFactRequest,
    ValuationField,
    ValuationProviderError,
    ValuationUnit,
)
from src.data.valuation.provenance import ValuationSubjectKind

SEC_PROVIDER_ID = "sec_edgar"
SEC_EPS_FIELD = "us-gaap:EarningsPerShareDiluted"
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
_ACCEPTED_FORMS = frozenset({"10-K", "10-K/A"})
_BALANCE_SHEET_FORMS = _ACCEPTED_FORMS
_BALANCE_SHEET_FIELDS: Mapping[ValuationField, tuple[str, ValuationUnit]] = {
    ValuationField.STOCKHOLDERS_EQUITY: ("StockholdersEquity", ValuationUnit.CURRENCY),
    ValuationField.COMMON_SHARES_OUTSTANDING: ("CommonStockSharesOutstanding", ValuationUnit.SHARES),
    ValuationField.PREFERRED_SHARES_OUTSTANDING: ("PreferredStockSharesOutstanding", ValuationUnit.SHARES),
}


@dataclass(frozen=True)
class _BalanceSheetParseContext:
    """Context shared while converting one SEC balance-sheet observation."""

    request: ValuationFactRequest
    provider_field: str
    unit: ValuationUnit
    currency: str | None
    acceptance_by_accession: Mapping[str, datetime]
    retrieved_at: datetime


@dataclass(frozen=True)
class _SecShareObservation:
    """One raw SEC share-count observation used for provider-specific derivation."""

    value: float
    provider_field: str
    accession: str
    retrieved_at: datetime
    observation_period_end: datetime
    available_at: datetime


class SecEdgarValuationAdapter:
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

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:
        """Return supported SEC facts, or explicit unavailability."""
        if not self._supports(request):
            return ()

        try:
            cik = self._resolve_cik(request.subject_id)
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
            if request.field_name is ValuationField.EPS:
                candidates = _annual_eps_candidates(
                    company_facts,
                    request=request,
                    acceptance_by_accession=acceptance_by_accession,
                    retrieved_at=provider_now,
                )
                return _select_one_fact_per_period(candidates, request=request, now=provider_now)

            if request.field_name is ValuationField.COMMON_SHARES_OUTSTANDING:
                return _common_shares_facts(
                    company_facts,
                    request=request,
                    acceptance_by_accession=acceptance_by_accession,
                    retrieved_at=provider_now,
                    now=provider_now,
                )
            if request.field_name is ValuationField.PREFERRED_SHARES_OUTSTANDING:
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
        except ValuationProviderError:
            raise
        except (KeyError, TypeError, ValueError, OSError) as exc:
            msg = f"SEC EDGAR valuation retrieval failed for {request.subject_id}: {exc}"
            raise ValuationProviderError(msg) from exc

    def _supports(self, request: ValuationFactRequest) -> bool:
        if request.provider_id != SEC_PROVIDER_ID or request.subject_kind is not ValuationSubjectKind.SECURITY:
            return False
        if request.field_name is ValuationField.EPS:
            return request.basis == "fiscal_year" and request.observation_count >= 1
        return (
            request.field_name in _BALANCE_SHEET_FIELDS
            and request.basis == "fiscal_year_end"
            and request.observation_count == 1
        )

    def _resolve_cik(self, ticker: str) -> str:
        ticker_to_cik = self._ticker_to_cik
        if ticker_to_cik is None:
            payload = self._fetch_json(_COMPANY_TICKERS_URL, headers=self._headers)
            ticker_to_cik = _ticker_cik_map(payload)
            self._ticker_to_cik = ticker_to_cik
        try:
            return ticker_to_cik[ticker]
        except KeyError as exc:
            msg = f"SEC EDGAR has no CIK mapping for ticker {ticker!r}."
            raise ValuationProviderError(msg) from exc


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
        parsed = _parse_datetime(timestamp)
        if parsed is not None:
            result[accession] = parsed
    return result


def _annual_eps_candidates(
    payload: object,
    *,
    request: ValuationFactRequest,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
) -> tuple[ProviderFact, ...]:
    """Parse annual ``EarningsPerShareDiluted`` Company Facts observations."""
    if not isinstance(payload, Mapping):
        msg = "SEC Company Facts payload is not an object."
        raise ValueError(msg)

    facts = payload.get("facts")
    if not isinstance(facts, Mapping):
        return ()
    us_gaap = facts.get("us-gaap")
    if not isinstance(us_gaap, Mapping):
        return ()
    eps = us_gaap.get("EarningsPerShareDiluted")
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
        for observation in observations:
            if not isinstance(observation, Mapping):
                continue
            fact = _parse_eps_observation(
                observation,
                request=request,
                currency=currency,
                acceptance_by_accession=acceptance_by_accession,
                retrieved_at=retrieved_at,
            )
            if fact is not None:
                result.append(fact)
    return tuple(result)


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
    request: ValuationFactRequest,
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
        if expected_unit is ValuationUnit.CURRENCY:
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
    request: ValuationFactRequest,
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
    request: ValuationFactRequest,
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
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=request.subject_id,
            field_name=ValuationField.COMMON_SHARES_OUTSTANDING,
            value=derived_value,
            units=ValuationUnit.SHARES,
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
    request: ValuationFactRequest,
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

    equity_request = ValuationFactRequest(
        subject_kind=request.subject_kind,
        subject_id=request.subject_id,
        field_name=ValuationField.STOCKHOLDERS_EQUITY,
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
        request=ValuationFactRequest(
            subject_kind=request.subject_kind,
            subject_id=request.subject_id,
            field_name=ValuationField.COMMON_SHARES_OUTSTANDING,
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
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=request.subject_id,
            field_name=ValuationField.PREFERRED_SHARES_OUTSTANDING,
            value=0.0,
            units=ValuationUnit.SHARES,
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
        subject_kind=ValuationSubjectKind.SECURITY,
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


def _parse_eps_observation(  # noqa: PLR0911
    observation: Mapping[object, object],
    *,
    request: ValuationFactRequest,
    currency: str,
    acceptance_by_accession: Mapping[str, datetime],
    retrieved_at: datetime,
) -> ProviderFact | None:
    form = observation.get("form")
    fp = observation.get("fp")
    if form not in _ACCEPTED_FORMS or fp != "FY":
        return None

    value = observation.get("val")
    start = observation.get("start")
    end = observation.get("end")
    accession = observation.get("accn")
    filed = observation.get("filed")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    if not all(isinstance(item, str) for item in (start, end, accession, filed)):
        return None

    start_text = cast(str, start)
    end_text = cast(str, end)
    accession_text = cast(str, accession)
    filed_text = cast(str, filed)
    period_start = _parse_date_start(start_text)
    period_end = _parse_date_end(end_text)
    if period_start is None or period_end is None:
        return None

    available_at = acceptance_by_accession.get(accession_text)
    availability_note: str
    if available_at is None:
        available_at = _parse_date_end(filed_text)
        if available_at is None:
            return None
        availability_note = "available_at conservatively uses end of SEC filed date; EDGAR acceptance time unavailable"
    else:
        availability_note = "available_at uses EDGAR acceptanceDateTime"

    fy = observation.get("fy")
    notes = (
        f"accession={accession_text}",
        f"form={form}",
        f"fiscal_year={fy}" if isinstance(fy, (int, str)) else "fiscal_year=unknown",
        availability_note,
    )
    return ProviderFact(
        subject_kind=ValuationSubjectKind.SECURITY,
        subject_id=request.subject_id,
        field_name=ValuationField.EPS,
        value=float(value),
        units=ValuationUnit.CURRENCY_PER_SHARE,
        provider_id=SEC_PROVIDER_ID,
        provider_field=SEC_EPS_FIELD,
        retrieved_at=retrieved_at,
        basis="fiscal_year",
        currency=currency,
        observation_period_start=period_start,
        observation_period_end=period_end,
        available_at=available_at,
        notes=notes,
    )


def _select_one_fact_per_period(
    facts: tuple[ProviderFact, ...],
    *,
    request: ValuationFactRequest,
    now: datetime,
) -> tuple[ProviderFact, ...]:
    """Select the latest restatement knowable at the request boundary per period."""
    boundary = request.as_of or now
    by_period: dict[datetime, ProviderFact] = {}
    for fact in facts:
        period_end = fact.observation_period_end
        available_at = fact.available_at
        if period_end is None or available_at is None:
            continue
        if period_end > boundary or available_at > boundary:
            continue
        prior = by_period.get(period_end)
        if prior is None or cast(datetime, prior.available_at) < available_at:
            by_period[period_end] = fact
    return tuple(by_period[end] for end in sorted(by_period))


def _select_latest_balance_sheet_fact(
    facts: tuple[ProviderFact, ...],
    *,
    request: ValuationFactRequest,
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


def _balance_sheet_definition_note(field_name: ValuationField) -> str:
    """Describe the accounting/share semantics retained for a balance-sheet concept."""
    if field_name is ValuationField.STOCKHOLDERS_EQUITY:
        return "definition=stockholders equity attributable to parent; preferred-stock guard required for BVPS"
    if field_name is ValuationField.COMMON_SHARES_OUTSTANDING:
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


def _parse_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
        return None
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
