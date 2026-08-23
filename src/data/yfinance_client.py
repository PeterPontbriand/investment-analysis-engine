"""Decoupled financial market client implementing data-fetching via Yahoo Finance."""

import contextlib
import io
import logging
import math
from typing import cast

import pandas as pd
import yfinance as yf

from src.data.base_client import BaseDataClient, DataFetchError

logger = logging.getLogger(__name__)


class YFinanceClient(BaseDataClient):
    """Concrete data client for acquiring market vectors from yfinance."""

    def fetch_data(self, ticker: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
        """Download and sanitize historical datasets from yfinance.

        Suppresses stderr console pollution during download execution, flattens
        multi-indexed frames, and enforces strict validation checks.
        """
        logger.info(f"Downloading market data for tool execution: {ticker} from {start_date}")

        stderr_buffer = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr_buffer):
                df = yf.download(ticker, start=start_date, end=end_date, progress=False, threads=False)
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

    def fetch_current_price(self, ticker: str) -> float:
        """Resolve the latest tradable quote for a ticker via the yfinance quote interface.

        Uses the dedicated quote boundary (``Ticker.fast_info``) rather than a
        one-day historical download, per the project's historical/quote split.
        """
        logger.info(f"Resolving current quote for '{ticker}' via yfinance")

        stderr_buffer = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr_buffer):
                quote = float(yf.Ticker(ticker).fast_info["last_price"])
        except Exception as err:
            logger.debug("Quote provider lookup failed for %r: %s", ticker, err)
            logger.debug(f"Stderr buffer contents: {stderr_buffer.getvalue()} - Ticker: {ticker}")
            raise DataFetchError(f"Unable to resolve a current quote for '{ticker}' via yfinance.") from err

        if not math.isfinite(quote) or quote <= 0:
            logger.error(f"Resolved non-finite or non-positive quote {quote!r} for '{ticker}'")
            raise DataFetchError(f"Current quote for '{ticker}' must be finite and positive (received {quote!r}).")

        logger.info(f"Current quote for '{ticker}': ${quote:,.2f}")
        return quote
