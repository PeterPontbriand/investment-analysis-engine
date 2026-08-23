"""Deterministic in-memory data client for unit tests.

Implements the full `BaseDataClient` contract with synthetic data so
analyzer and pipeline tests never touch external market-data providers.
"""

import pandas as pd

from src.data.base_client import BaseDataClient, DataFetchError


class FixtureDataClient(BaseDataClient):
    """BaseDataClient implementation backed by deterministic test data."""

    def fetch_data(self, ticker: str, start_date: str, _end_date: str | None = None) -> pd.DataFrame:
        """Return a small deterministic close-price series.

        The series starts at 100.0 and grows 1 % per period, producing a
        stable rising trend for analyzer calculations. The date arguments are
        accepted for interface compatibility; the fixture always returns 5 rows.

        Args:
            ticker: Symbol under test.
            start_date: Query start date (accepted for interface compatibility).
                The reserved token "raise" simulates a provider failure.
            _end_date: Optional query end date (accepted for interface
                compatibility only; intentionally unused by the fixture).

        Returns:
            pd.DataFrame: Columns Open, High, Low, Close and Volume (5 rows).

        Raises:
            ValueError: If `ticker` is empty or whitespace.
            DataFetchError: If `start_date` is the reserved token "raise".
        """
        if not ticker or not ticker.strip():
            raise ValueError(f"Invalid ticker supplied to fixture: {ticker!r}")
        if start_date == "raise":
            raise DataFetchError("fixture simulated provider failure")

        closes = [100.0 * (1.01**i) for i in range(5)]
        return pd.DataFrame(
            {
                "Open": closes,
                "High": [close * 1.005 for close in closes],
                "Low": [close * 0.995 for close in closes],
                "Close": closes,
                "Volume": [1_000_000] * len(closes),
            }
        )

    def fetch_current_price(self, ticker: str) -> float:
        """Return the deterministic last close of the fixture series.

        Args:
            ticker: Symbol under test. The reserved ticker "FAIL" simulates
                a quote-provider failure.

        Returns:
            float: Last fixture close for the requested ticker.

        Raises:
            ValueError: If `ticker` is empty or whitespace.
            DataFetchError: If `ticker` is the reserved "FAIL" symbol.
        """
        if not ticker or not ticker.strip():
            raise ValueError(f"Invalid ticker supplied to fixture: {ticker!r}")
        if ticker == "FAIL":
            raise DataFetchError("fixture simulated quote failure")
        return float(self.fetch_data(ticker, "2026-01-01").iloc[-1]["Close"])
