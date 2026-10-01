"""The Massive placeholder client treats ``end_date`` as exclusive, like the Yahoo client."""

import pandas as pd
import pytest

from src.data.base_client import DataFetchError
from src.data.massive.client import MassiveClient


def test_the_end_date_is_exclusive() -> None:
    frame = MassiveClient().fetch_data("ACME", "2026-01-05", "2026-01-09")

    assert list(frame.index) == [pd.Timestamp(day) for day in ("2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08")]


def test_an_end_date_that_is_a_weekend_day_keeps_the_prior_business_days() -> None:
    frame = MassiveClient().fetch_data("ACME", "2026-01-05", "2026-01-10")

    assert frame.index[-1] == pd.Timestamp("2026-01-09")


def test_without_an_end_date_the_default_range_is_unchanged() -> None:
    frame = MassiveClient().fetch_data("ACME", "2026-06-29")

    assert frame.index[-1] == pd.Timestamp("2026-07-01")


def test_a_window_holding_no_business_day_is_a_fetch_error() -> None:
    with pytest.raises(DataFetchError):
        MassiveClient().fetch_data("ACME", "2026-01-05", "2026-01-05")
