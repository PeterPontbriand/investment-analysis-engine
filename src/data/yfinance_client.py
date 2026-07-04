"""Decoupled financial market client implementing data-fetching via Yahoo Finance."""

import contextlib
import io
import logging

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

        # Suppress any low-level yfinance terminal output (like 404 prints) to stderr
        stderr_buffer = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr_buffer):
                df = yf.download(ticker, start=start_date, end=end_date, progress=False, threads=False)
        except Exception as err:
            logger.error(f"Low-level connection error during yfinance download for '{ticker}': {err}")
            # Log the captured stderr output for debug purposes
            logger.debug(f"Stderr buffer contents: {stderr_buffer.getvalue()} - Ticker: {ticker}")
            raise DataFetchError(f"Network transport fault fetching '{ticker}': {err}") from err

        # Structural sanity check
        if df is None or df.empty:
            logger.error(f"Target market ticker data resolved to empty: '{ticker}'")
            raise DataFetchError(f"Target market ticker data resolved to empty: '{ticker}'")

        # Normalize column layout (MultiIndex flattening for multi-tickers or modern yfinance packages)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return df
