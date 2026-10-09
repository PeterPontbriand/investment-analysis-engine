"""Decoupled financial market client implementing data-fetching via Yahoo Finance."""

import contextlib
import io
import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import curl_cffi.requests.exceptions as curl_exceptions
import pandas as pd
import requests.exceptions as requests_exceptions
import yfinance as yf
from yfinance.exceptions import (
    YFDataException,
    YFException,
    YFInvalidPeriodError,
    YFNotImplementedError,
    YFRateLimitError,
    YFTickerMissingError,
)

from src.core.clock import utc_now
from src.core.provider_failure_kind import ProviderFailureKind
from src.data.base_client import BaseDataClient, DataFetchError
from src.data.financial.provenance import SourceKind
from src.data.instrument_profile import (
    InstrumentKindEvidence,
    InstrumentKindRequest,
    reviewed_instrument_kind,
)
from src.data.market_data import (
    HistoricalDataResolution,
    HistoricalMarketData,
    MarketDataContext,
    latest_observation_date,
)
from src.data.provider_failure import DEFECT, FailureRule, call_library
from src.data.security_identity import SecurityIdentity, SecurityIdentityRequest

logger = logging.getLogger(__name__)

YFINANCE_PROVIDER_ID = "yfinance"
YFINANCE_HISTORICAL_INTERVAL = "1d"
YFINANCE_PRICE_ADJUSTMENT = "adjusted"
YFINANCE_HISTORY_COLUMNS = ("Open", "High", "Low", "Close", "Volume")
"""The columns of a daily history frame that the adapter requires from ``yf.download``."""

# How an exception raised inside a yfinance call is classified, checked in this order. The more specific types
# come first because both HTTP backends derive their request errors from ``OSError`` (including the JSON-decoding,
# content-decoding and invalid-URL errors), and a bare ``YFException`` is a library defect, not a service fault.
_YFINANCE_FAILURE_RULES = (
    FailureRule(
        (
            curl_exceptions.JSONDecodeError,
            curl_exceptions.ContentDecodingError,
            requests_exceptions.JSONDecodeError,
            requests_exceptions.ContentDecodingError,
            YFDataException,
        ),
        ProviderFailureKind.UNEXPECTED_RESPONSE,
    ),
    FailureRule((YFTickerMissingError,), ProviderFailureKind.NO_DATA),
    FailureRule(
        (YFInvalidPeriodError, YFNotImplementedError, curl_exceptions.InvalidURL, requests_exceptions.InvalidURL),
        DEFECT,
    ),
    FailureRule((YFException,), DEFECT, when=lambda error: type(error) is YFException),
    FailureRule((OSError, YFRateLimitError), ProviderFailureKind.UNREACHABLE),
)


@dataclass(frozen=True)
class YFinanceQuote:
    """Current Yahoo quote value plus the currency exposed by ``fast_info``."""

    price: float
    currency: str | None


@dataclass(frozen=True)
class _YFinanceMetadataSnapshot:
    """One lazily retrieved Yahoo metadata mapping and its retrieval time."""

    metadata: Mapping[object, object] | None
    resolved_at: datetime


class YFinanceClient(BaseDataClient):
    """Concrete data client for acquiring market vectors from yfinance."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        """Initialize with an injectable metadata-resolution clock."""
        self._clock = clock or utc_now
        self._metadata_by_ticker: dict[str, _YFinanceMetadataSnapshot | DataFetchError] = {}

    @property
    def provider_id(self) -> str:
        """Return the stable provider identity owned by this adapter."""
        return YFINANCE_PROVIDER_ID

    def fetch_data(self, ticker: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
        """Download and sanitize historical datasets from yfinance.

        Suppresses stderr console pollution during download execution, flattens
        multi-indexed frames, and enforces strict validation checks.
        """
        logger.info(f"Downloading market data for tool execution: {ticker} from {start_date}")

        stderr_buffer = io.StringIO()

        def download() -> object:
            with contextlib.redirect_stderr(stderr_buffer):
                return yf.download(
                    ticker,
                    start=start_date,
                    end=end_date,
                    interval=YFINANCE_HISTORICAL_INTERVAL,
                    ignore_tz=True,
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                )

        try:
            result = call_library(
                download,
                rules=_YFINANCE_FAILURE_RULES,
                provider_id=YFINANCE_PROVIDER_ID,
                message=f"yfinance history download failed for '{ticker}'",
                error_type=DataFetchError,
            )
        except DataFetchError as failure:
            logger.error(f"yfinance download for '{ticker}' failed ({failure.kind}): {failure}")
            logger.debug(f"Stderr buffer contents: {stderr_buffer.getvalue()} - Ticker: {ticker}")
            raise

        if result is None or (isinstance(result, pd.DataFrame) and result.empty):
            logger.debug("No market data returned for ticker '%s'.", ticker)
            raise DataFetchError(
                f"No market data was returned for ticker '{ticker}'.",
                kind=ProviderFailureKind.NO_DATA,
                provider_id=YFINANCE_PROVIDER_ID,
            )
        if not isinstance(result, pd.DataFrame):
            raise DataFetchError(
                f"yfinance returned {type(result).__name__} instead of a data frame for '{ticker}'.",
                kind=ProviderFailureKind.UNEXPECTED_RESPONSE,
                provider_id=YFINANCE_PROVIDER_ID,
            )
        df = result

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        missing = [column for column in YFINANCE_HISTORY_COLUMNS if column not in df.columns]
        if missing:
            raise DataFetchError(
                f"yfinance history for '{ticker}' is missing columns: {', '.join(missing)}.",
                kind=ProviderFailureKind.UNEXPECTED_RESPONSE,
                provider_id=YFINANCE_PROVIDER_ID,
            )

        return df

    def fetch_data_with_context(
        self,
        ticker: str,
        start_date: str,
        end_date: str | None = None,
        *,
        use_cache: bool = True,  # noqa: ARG002
    ) -> HistoricalMarketData:
        """Return explicitly adjusted daily historical prices with retained yfinance metadata.

        ``use_cache`` is accepted for interface uniformity and ignored: this raw provider has no
        cache of its own to skip.
        """
        frame = self.fetch_data(ticker, start_date, end_date)
        context = MarketDataContext(
            provider_id=self.provider_id,
            observation_interval=YFINANCE_HISTORICAL_INTERVAL,
            data_as_of=latest_observation_date(frame),
            currency=self._fetch_currency(ticker),
            observation_count=len(frame),
            price_adjustment=YFINANCE_PRICE_ADJUSTMENT,
        )
        retrieved = utc_now()
        return HistoricalMarketData(
            frame=frame,
            context=context,
            resolution=HistoricalDataResolution(SourceKind.PROVIDER, retrieved, None, retrieved),
        )

    def fetch_current_quote(self, ticker: str) -> YFinanceQuote:
        """Resolve the latest tradable quote and best-effort currency via ``fast_info``."""
        logger.info(f"Resolving current quote for '{ticker}' via yfinance")

        stderr_buffer = io.StringIO()

        def read_quote() -> tuple[Any, object]:
            with contextlib.redirect_stderr(stderr_buffer):
                fast_info = yf.Ticker(ticker).fast_info
                raw_price = fast_info["last_price"]
                try:
                    return raw_price, fast_info["currency"]
                except (KeyError, TypeError):
                    return raw_price, None

        try:
            raw_price, raw_currency = call_library(
                read_quote,
                rules=_YFINANCE_FAILURE_RULES,
                provider_id=YFINANCE_PROVIDER_ID,
                message=f"Unable to resolve a current quote for '{ticker}' via yfinance",
                error_type=DataFetchError,
            )
        except DataFetchError as failure:
            logger.debug("Quote provider lookup failed for %r: %s", ticker, failure)
            logger.debug(f"Stderr buffer contents: {stderr_buffer.getvalue()} - Ticker: {ticker}")
            raise

        try:
            quote = float(raw_price)
        except (TypeError, ValueError) as err:
            raise DataFetchError(
                f"Current quote for '{ticker}' is not numeric (received {raw_price!r}).",
                kind=ProviderFailureKind.UNEXPECTED_RESPONSE,
                provider_id=YFINANCE_PROVIDER_ID,
            ) from err

        if not math.isfinite(quote) or quote <= 0:
            logger.error(f"Resolved non-finite or non-positive quote {quote!r} for '{ticker}'")
            raise DataFetchError(
                f"Current quote for '{ticker}' must be finite and positive (received {quote!r}).",
                kind=ProviderFailureKind.UNEXPECTED_RESPONSE,
                provider_id=YFINANCE_PROVIDER_ID,
            )

        currency: str | None = None
        if isinstance(raw_currency, str):
            normalized_currency = raw_currency.strip().upper()
            currency = normalized_currency or None

        logger.info(f"Current quote for '{ticker}': ${quote:,.2f}")
        return YFinanceQuote(price=quote, currency=currency)

    def fetch_current_price(self, ticker: str) -> float:
        """Resolve the latest tradable quote for a ticker via the yfinance quote interface.

        Uses the dedicated quote boundary (``Ticker.fast_info``) rather than a
        one-day historical download, per the project's historical/quote split.
        """
        return self.fetch_current_quote(ticker).price

    def resolve_security_identity(self, request: SecurityIdentityRequest) -> SecurityIdentity | None:
        """Return best-effort current Yahoo descriptive metadata for one instrument."""
        if request.provider_id != YFINANCE_PROVIDER_ID:
            return None

        snapshot = self._fetch_metadata_snapshot(request.ticker)
        if snapshot.metadata is None:
            return None
        instrument_name = _first_metadata_text(snapshot.metadata, "longName", "shortName", "displayName")
        listing_venue = _first_metadata_text(snapshot.metadata, "fullExchangeName", "exchange")
        instrument_identifier = _first_metadata_text(snapshot.metadata, "uuid")
        if instrument_name is None and listing_venue is None and instrument_identifier is None:
            return None
        return SecurityIdentity(
            ticker=request.ticker,
            instrument_name=instrument_name,
            listing_venue=listing_venue,
            instrument_identifier=instrument_identifier,
            provider_id=YFINANCE_PROVIDER_ID,
            resolved_at=snapshot.resolved_at,
        )

    def resolve_instrument_kind(self, request: InstrumentKindRequest) -> InstrumentKindEvidence | None:
        """Return reviewed Yahoo ``quoteType`` evidence without inferring kind."""
        if request.provider_id != YFINANCE_PROVIDER_ID:
            return None

        snapshot = self._fetch_metadata_snapshot(request.ticker)
        if snapshot.metadata is None:
            return None
        raw_provider_value = snapshot.metadata.get("quoteType")
        if not isinstance(raw_provider_value, str) or not raw_provider_value.strip():
            return None
        provider_value = " ".join(raw_provider_value.split())
        return InstrumentKindEvidence(
            ticker=request.ticker,
            kind=reviewed_instrument_kind(YFINANCE_PROVIDER_ID, provider_value),
            provider_value=provider_value,
            provider_id=YFINANCE_PROVIDER_ID,
            resolved_at=snapshot.resolved_at,
        )

    def _fetch_metadata_snapshot(self, ticker: str) -> _YFinanceMetadataSnapshot:
        """Fetch and retain one metadata result per client/ticker, including failure."""
        cached = self._metadata_by_ticker.get(ticker)
        if isinstance(cached, DataFetchError):
            raise cached
        if cached is not None:
            return cached

        stderr_buffer = io.StringIO()

        def read_info() -> object:
            with contextlib.redirect_stderr(stderr_buffer):
                return yf.Ticker(ticker).info

        try:
            raw_metadata = call_library(
                read_info,
                rules=_YFINANCE_FAILURE_RULES,
                provider_id=YFINANCE_PROVIDER_ID,
                message=f"Unable to resolve instrument metadata for '{ticker}' via yfinance",
                error_type=DataFetchError,
            )
        except DataFetchError as failure:
            logger.debug("Optional instrument metadata unavailable for %r: %s", ticker, failure)
            logger.debug(f"Stderr buffer contents: {stderr_buffer.getvalue()} - Ticker: {ticker}")
            self._metadata_by_ticker[ticker] = failure
            raise

        metadata = dict(raw_metadata) if isinstance(raw_metadata, Mapping) else None
        snapshot = _YFinanceMetadataSnapshot(metadata=metadata, resolved_at=self._clock())
        self._metadata_by_ticker[ticker] = snapshot
        return snapshot

    def _fetch_currency(self, ticker: str) -> str | None:
        """Best-effort currency enrichment that never invalidates usable price history.

        A typed provider failure, or the ``KeyError`` that a connection fault surfaces as here, returns no currency;
        any other exception is a defect and propagates.
        """
        stderr_buffer = io.StringIO()

        def read_currency() -> object:
            with contextlib.redirect_stderr(stderr_buffer):
                try:
                    return yf.Ticker(ticker).fast_info["currency"]
                except KeyError:
                    return None

        try:
            raw_currency = call_library(
                read_currency,
                rules=_YFINANCE_FAILURE_RULES,
                provider_id=YFINANCE_PROVIDER_ID,
                message=f"Optional currency metadata unavailable for '{ticker}'",
                error_type=DataFetchError,
            )
        except DataFetchError as failure:
            logger.debug("Optional currency metadata unavailable for %r (%s): %s", ticker, failure.kind, failure)
            logger.debug(f"Stderr buffer contents: {stderr_buffer.getvalue()} - Ticker: {ticker}")
            return None

        if not isinstance(raw_currency, str):
            return None
        currency = raw_currency.strip().upper()
        return currency or None


def _first_metadata_text(metadata: Mapping[object, object], *keys: str) -> str | None:
    """Return the first non-empty Yahoo metadata string without changing its case."""
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None
