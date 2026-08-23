"""Massive adapter for current TTM diluted EPS and latest-trade price facts."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, time
from urllib.parse import urlencode

from src.analysis.graham_value.facts import (
    ProviderFact,
    ValuationFactRequest,
    ValuationField,
    ValuationProviderError,
    ValuationUnit,
)
from src.analysis.graham_value.provenance import ValuationSubjectKind
from src.analysis.graham_value.providers.http_json import JsonFetcher, fetch_json

MASSIVE_PROVIDER_ID = "massive"
MASSIVE_TTM_EPS_FIELD = "diluted_earnings_per_share"
MASSIVE_LAST_TRADE_FIELD = "results.p"
_BASE_URL = "https://api.massive.com"


class MassiveValuationAdapter:
    """Provide the E1-approved current Massive valuation capabilities.

    Supported:
        - current TTM diluted EPS;
        - current price from the latest stock trade.

    Historical ``as_of`` requests, BVPS, annual EPS, and AAA yield are
    intentionally unavailable.  This prevents current snapshots or inadequately
    evidenced fields from masquerading as historical/verified facts.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        json_fetcher: JsonFetcher = fetch_json,
        clock: Callable[[], datetime] | None = None,
        base_url: str = _BASE_URL,
    ) -> None:
        """Initialize the adapter with injectable credentials, transport, and clock."""
        self._api_key = api_key if api_key is not None else os.getenv("MASSIVE_API_KEY")
        self._fetch_json = json_fetcher
        self._clock = clock or (lambda: datetime.now(UTC))
        self._base_url = base_url.rstrip("/")
        self._currency_by_ticker: dict[str, str] = {}

    def fetch_facts(self, request: ValuationFactRequest) -> tuple[ProviderFact, ...]:  # noqa: PLR0911
        """Return supported current facts, or explicit unavailability."""
        if request.provider_id != MASSIVE_PROVIDER_ID:
            return ()
        if request.subject_kind is not ValuationSubjectKind.SECURITY:
            return ()
        if request.as_of is not None:
            return ()
        if not self._api_key:
            return ()

        try:
            if request.field_name is ValuationField.EPS and request.basis == "ttm" and request.observation_count == 1:
                fact = self._fetch_ttm_eps(request)
                return () if fact is None else (fact,)
            if (
                request.field_name is ValuationField.CURRENT_PRICE
                and request.basis is None
                and request.observation_count == 1
            ):
                fact = self._fetch_current_price(request)
                return () if fact is None else (fact,)
            return ()
        except ValuationProviderError:
            raise
        except (KeyError, TypeError, ValueError, OSError) as exc:
            msg = f"Massive valuation retrieval failed for {request.subject_id}: {exc}"
            raise ValuationProviderError(msg) from exc

    def _fetch_ttm_eps(self, request: ValuationFactRequest) -> ProviderFact | None:
        currency = self._currency_for_ticker(request.subject_id)
        params = urlencode(
            {
                "tickers": request.subject_id,
                "timeframe": "trailing_twelve_months",
                "limit": 1,
                "sort": "period_end.desc",
            }
        )
        payload = self._get(f"/stocks/financials/v1/income-statements?{params}")
        result = _first_result(payload)
        if result is None:
            return None

        timeframe = result.get("timeframe")
        value = result.get(MASSIVE_TTM_EPS_FIELD)
        period_end_text = result.get("period_end")
        filing_date_text = result.get("filing_date")
        tickers = result.get("tickers")
        if (
            timeframe != "trailing_twelve_months"
            or not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not isinstance(period_end_text, str)
            or not isinstance(filing_date_text, str)
            or not _contains_ticker(tickers, request.subject_id)
        ):
            return None

        period_end = _parse_date_end(period_end_text)
        filing_eod = _parse_date_end(filing_date_text)
        if period_end is None or filing_eod is None:
            return None

        notes: tuple[str, ...] = (
            "Massive TTM EPS uses diluted_earnings_per_share",
            "TTM EPS is recalculated from TTM net income and average diluted shares over four quarters",
            "available_at conservatively uses end of provider-reported filing_date",
            "Massive filing_date may be the most recent filing containing the period, "
            "not its original publication date",
        )
        cik = result.get("cik")
        if isinstance(cik, str) and cik.strip():
            notes += (f"cik={cik.strip()}",)

        return ProviderFact(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=request.subject_id,
            field_name=ValuationField.EPS,
            value=float(value),
            units=ValuationUnit.CURRENCY_PER_SHARE,
            provider_id=MASSIVE_PROVIDER_ID,
            provider_field=MASSIVE_TTM_EPS_FIELD,
            retrieved_at=self._clock(),
            basis="ttm",
            currency=currency,
            observation_period_end=period_end,
            available_at=filing_eod,
            notes=notes,
        )

    def _fetch_current_price(self, request: ValuationFactRequest) -> ProviderFact | None:
        currency = self._currency_for_ticker(request.subject_id)
        payload = self._get(f"/v2/last/trade/{request.subject_id}")
        result = _result_object(payload)
        if result is None:
            return None

        value = result.get("p")
        ticker = result.get("T")
        sip_timestamp = result.get("t")
        if ticker != request.subject_id:
            return None
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None
        observed_at = _timestamp_ns(sip_timestamp)
        if observed_at is None:
            return None

        notes = ["price is Massive latest-trade field results.p"]
        trade_id = result.get("i")
        exchange_id = result.get("x")
        participant_timestamp = _timestamp_ns(result.get("y"))
        if isinstance(trade_id, str):
            notes.append(f"trade_id={trade_id}")
        if isinstance(exchange_id, int) and not isinstance(exchange_id, bool):
            notes.append(f"exchange_id={exchange_id}")
        if participant_timestamp is not None:
            notes.append(f"participant_timestamp={participant_timestamp.isoformat()}")

        return ProviderFact(
            subject_kind=ValuationSubjectKind.SECURITY,
            subject_id=request.subject_id,
            field_name=ValuationField.CURRENT_PRICE,
            value=float(value),
            units=ValuationUnit.CURRENCY_PER_SHARE,
            provider_id=MASSIVE_PROVIDER_ID,
            provider_field=MASSIVE_LAST_TRADE_FIELD,
            retrieved_at=self._clock(),
            currency=currency,
            observed_at=observed_at,
            available_at=observed_at,
            notes=tuple(notes),
        )

    def _currency_for_ticker(self, ticker: str) -> str:
        cached = self._currency_by_ticker.get(ticker)
        if cached is not None:
            return cached

        params = urlencode(
            {
                "ticker": ticker,
                "market": "stocks",
                "active": "true",
                "limit": 10,
            }
        )
        payload = self._get(f"/v3/reference/tickers?{params}")
        results = _results(payload)
        for result in results:
            candidate_ticker = result.get("ticker")
            currency_name = result.get("currency_name")
            if candidate_ticker != ticker or not isinstance(currency_name, str):
                continue
            currency = currency_name.strip().upper()
            if len(currency) != 3 or not currency.isalpha():
                continue
            self._currency_by_ticker[ticker] = currency
            return currency

        msg = f"Massive returned no verified currency metadata for {ticker!r}."
        raise ValuationProviderError(msg)

    def _get(self, path: str) -> object:
        assert self._api_key is not None
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        payload = self._fetch_json(f"{self._base_url}{path}", headers=headers)
        _require_ok(payload)
        return payload


def _require_ok(payload: object) -> None:
    if not isinstance(payload, Mapping):
        msg = "Massive response is not an object."
        raise ValueError(msg)
    status = payload.get("status")
    if status is not None and status != "OK":
        msg = f"Massive returned non-OK status {status!r}."
        raise ValuationProviderError(msg)


def _results(payload: object) -> tuple[Mapping[object, object], ...]:
    if not isinstance(payload, Mapping):
        return ()
    values = payload.get("results")
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return ()
    return tuple(item for item in values if isinstance(item, Mapping))


def _first_result(payload: object) -> Mapping[object, object] | None:
    values = _results(payload)
    return values[0] if values else None


def _result_object(payload: object) -> Mapping[object, object] | None:
    if not isinstance(payload, Mapping):
        return None
    result = payload.get("results")
    return result if isinstance(result, Mapping) else None


def _contains_ticker(value: object, ticker: str) -> bool:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return False
    return any(item == ticker for item in value)


def _parse_date_end(value: str) -> datetime | None:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
    return datetime.combine(parsed, time.max, tzinfo=UTC)


def _timestamp_ns(value: object) -> datetime | None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return None
    return datetime.fromtimestamp(value / 1_000_000_000, tz=UTC)
