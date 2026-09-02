"""Deterministic in-memory market-data client for evaluation and tests.

Implements the full `BaseDataClient` contract with synthetic data so
Golden evaluation and analyzer tests never touch external market-data providers.
"""

from datetime import date
from typing import Final

import pandas as pd

from src.data.base_client import BaseDataClient, DataFetchError
from src.data.market_data import HistoricalMarketData, MarketDataContext

MOMENTUM_SHORT_WINDOW: Final = 2
MOMENTUM_LONG_WINDOW: Final = 3
MOMENTUM_RSI_PERIOD: Final = 3
MOMENTUM_SUCCESS_CLOSES: Final = (100.0, 101.0, 102.0, 103.0, 104.0)
MOMENTUM_BOUNDARY_CLOSES: Final = MOMENTUM_SUCCESS_CLOSES[:2]


def momentum_success_frame() -> pd.DataFrame:
    """Return the five-observation rising series used by the success case."""
    return _momentum_frame(MOMENTUM_SUCCESS_CLOSES)


def momentum_boundary_frame() -> pd.DataFrame:
    """Return the two-observation series that is one row short of the long SMA."""
    return _momentum_frame(MOMENTUM_BOUNDARY_CLOSES)


def _momentum_frame(closes: tuple[float, ...]) -> pd.DataFrame:
    """Build a fresh UTC-indexed close-price frame from immutable fixture values."""
    index = pd.date_range("2026-01-02", periods=len(closes), freq="D", tz="UTC", name="Timestamp")
    return pd.DataFrame({"Close": closes}, index=index)


class FixtureMarketDataProvider:
    """Deterministic provider for point-in-time Momentum evaluation."""

    provider_id = "fixture_market"

    def __init__(self, frame: pd.DataFrame) -> None:
        """Retain the deterministic historical frame."""
        self._frame = frame

    def fetch_historical_data(self, ticker: str, start_date: str, end_date: str | None = None) -> HistoricalMarketData:
        """Return the complete fixture series so the resolver must truncate it."""
        del ticker, start_date, end_date
        return HistoricalMarketData(
            frame=self._frame,
            context=MarketDataContext(
                provider_id=self.provider_id,
                observation_interval="1d",
                data_as_of=date(2026, 1, 6),
                currency="USD",
                observation_count=len(self._frame),
                price_adjustment="adjusted",
            ),
        )


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
