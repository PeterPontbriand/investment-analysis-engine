"""The one rule that normalizes a ticker."""

import pytest

from investment_analysis_engine.core.tickers import is_normalized_ticker, normalize_ticker


@pytest.mark.parametrize(("raw", "expected"), [("ko", "KO"), (" pfe.to ", "PFE.TO"), ("BRK.B", "BRK.B")])
def test_normalize_ticker_trims_and_uppercases_preserving_suffix(raw: str, expected: str) -> None:
    assert normalize_ticker(raw) == expected


@pytest.mark.parametrize("raw", ["", "   "])
def test_normalize_ticker_rejects_blank(raw: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        normalize_ticker(raw)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("AAPL", True), ("BRK.B", True), ("aapl", False), (" AAPL", False), ("", False), ("  ", False)],
)
def test_is_normalized_ticker(value: str, expected: bool) -> None:
    assert is_normalized_ticker(value) is expected
