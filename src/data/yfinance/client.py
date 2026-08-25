"""Decoupled financial market client implementing data-fetching via Yahoo Finance."""

import contextlib
import io
import logging
import math
from dataclasses import dataclass
from typing import cast

import pandas as pd
import yfinance as yf

from src.data.base_client import BaseDataClient, DataFetchError
from src.data.market_data import HistoricalMarketData, MarketDataContext, latest_observation_date

logger = logging.getLogger(__name__)

YFINANCE_PROVIDER_ID = "yfinance"
YFINANCE_HISTORICAL_INTERVAL = "1d"
YFINANCE_PRICE_ADJUSTMENT = "adjusted"


@dataclass(frozen=True)
class YFinanceQuote:
    """Current Yahoo quote value plus the currency exposed by ``fast_info``."""

    price: float
    currency: str | None


class YFinanceClient(BaseDataClient):
    """Concrete data client for acquiring market vectors from yfinance."""

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
        try:
            with contextlib.redirect_stderr(stderr_buffer):
                df = yf.download(
                    ticker,
                    start=start_date,
                    end=end_date,
                    interval=YFINANCE_HISTORICAL_INTERVAL,
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                )
        except Exception as err:
            logger.error(f"Low-level connection error during yfinance download for '{ticker}': {err}")
            logger.debug(f"Stderr buffer contents: {stderr_buffer.getvalue()} - Ticker: {ticker}")
            raise DataFetchError(f"Network transport fault fetching '{ticker}': {err}") from err

        if df is None or df.empty:
            logger.debug("No market data returned for ticker '%s'.", ticker)
            raise DataFetchError(f"No market data was returned for ticker '{ticker}'.")

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return cast(pd.DataFrame, df)

    def fetch_data_with_context(
        self,
        ticker: str,
        start_date: str,
        end_date: str | None = None,
    ) -> HistoricalMarketData:
        """Return explicitly adjusted daily historical prices with retained yfinance metadata."""
        frame = self.fetch_data(ticker, start_date, end_date)
        context = MarketDataContext(
            provider_id=self.provider_id,
            observation_interval=YFINANCE_HISTORICAL_INTERVAL,
            data_as_of=latest_observation_date(frame),
            currency=self._fetch_currency(ticker),
            observation_count=len(frame),
            price_adjustment=YFINANCE_PRICE_ADJUSTMENT,
        )
        return HistoricalMarketData(frame=frame, context=context)

    def fetch_current_quote(self, ticker: str) -> YFinanceQuote:
        """Resolve the latest tradable quote and best-effort currency via ``fast_info``."""
        logger.info(f"Resolving current quote for '{ticker}' via yfinance")

        stderr_buffer = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr_buffer):
                fast_info = yf.Ticker(ticker).fast_info
                quote = float(fast_info["last_price"])
                try:
                    raw_currency = fast_info["currency"]
                except (KeyError, TypeError):
                    raw_currency = None
        except Exception as err:
            logger.debug("Quote provider lookup failed for %r: %s", ticker, err)
            logger.debug(f"Stderr buffer contents: {stderr_buffer.getvalue()} - Ticker: {ticker}")
            raise DataFetchError(f"Unable to resolve a current quote for '{ticker}' via yfinance.") from err

        if not math.isfinite(quote) or quote <= 0:
            logger.error(f"Resolved non-finite or non-positive quote {quote!r} for '{ticker}'")
            raise DataFetchError(f"Current quote for '{ticker}' must be finite and positive (received {quote!r}).")

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

    def _fetch_currency(self, ticker: str) -> str | None:
        """Best-effort currency enrichment that never invalidates usable price history."""
        stderr_buffer = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr_buffer):
                raw_currency = yf.Ticker(ticker).fast_info["currency"]
        except Exception as err:
            logger.debug("Optional currency metadata unavailable for %r: %s", ticker, err)
            logger.debug(f"Stderr buffer contents: {stderr_buffer.getvalue()} - Ticker: {ticker}")
            return None

        if not isinstance(raw_currency, str):
            return None
        currency = raw_currency.strip().upper()
        return currency or None
