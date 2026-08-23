"""Tests for the deterministic fixture data client contract."""

import pandas as pd
import pytest

from src.data.base_client import BaseDataClient, DataFetchError
from tests.data.fixture_client import FixtureDataClient


class TestFixtureDataClientContract:
    """Verify the fixture satisfies the BaseDataClient interface."""

    def test_implements_base_data_client(self) -> None:
        assert isinstance(FixtureDataClient(), BaseDataClient)

    def test_fetch_data_returns_full_ohlc_frame(self) -> None:
        df = FixtureDataClient().fetch_data("TEST", start_date="2026-01-01")
        assert isinstance(df, pd.DataFrame)
        for column in ("Open", "High", "Low", "Close", "Volume"):
            assert column in df.columns
        assert not df.empty

    def test_fetch_data_rejects_empty_ticker(self) -> None:
        with pytest.raises(ValueError, match="Invalid ticker"):
            FixtureDataClient().fetch_data("   ", start_date="2026-01-01")

    def test_fetch_data_simulated_failure(self) -> None:
        with pytest.raises(DataFetchError):
            FixtureDataClient().fetch_data("TEST", start_date="raise")

    def test_fetch_current_price_returns_last_close(self) -> None:
        client = FixtureDataClient()
        expected = float(client.fetch_data("TEST", start_date="2026-01-01").iloc[-1]["Close"])
        assert client.fetch_current_price("TEST") == pytest.approx(expected)

    def test_fetch_current_price_rejects_empty_ticker(self) -> None:
        with pytest.raises(ValueError, match="Invalid ticker"):
            FixtureDataClient().fetch_current_price("")

    def test_fetch_current_price_simulated_failure(self) -> None:
        with pytest.raises(DataFetchError):
            FixtureDataClient().fetch_current_price("FAIL")
