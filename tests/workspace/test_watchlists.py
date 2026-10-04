"""Focused tests for the watchlist creation spec and selection JSON codec."""

import json

import pytest
from pydantic import ValidationError

from src.strategies.fcf_growth.selection import FCFGrowthSelection
from src.strategies.graham_growth.selection import GrahamGrowthSelection
from src.strategies.graham_number.selection import GrahamNumberSelection
from src.strategies.momentum.selection import MomentumSelection
from src.workspace.watchlists import (
    StoredSelectionError,
    WatchlistSpec,
    decode_selection,
    encode_selection,
    normalize_ticker,
)


def test_watchlist_spec_accepts_only_display_name() -> None:
    spec = WatchlistSpec(display_name="  Dividend Growth  ")
    assert spec.display_name == "  Dividend Growth  "
    with pytest.raises(ValidationError, match="Extra inputs"):
        WatchlistSpec(display_name="X", members=("KO",))  # type: ignore[call-arg]


def test_watchlist_spec_is_frozen() -> None:
    spec = WatchlistSpec(display_name="X")
    with pytest.raises(ValidationError, match="frozen_instance"):
        spec.display_name = "Y"


@pytest.mark.parametrize(("raw", "expected"), [("ko", "KO"), (" pfe.to ", "PFE.TO"), ("BRK.B", "BRK.B")])
def test_normalize_ticker_trims_and_uppercases_preserving_suffix(raw: str, expected: str) -> None:
    assert normalize_ticker(raw) == expected


@pytest.mark.parametrize("raw", ["", "   "])
def test_normalize_ticker_rejects_blank(raw: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        normalize_ticker(raw)


@pytest.mark.parametrize(
    "selection",
    [
        MomentumSelection(short_window=2, long_window=5),
        GrahamNumberSelection(),
        GrahamGrowthSelection(expected_growth=5.0, aaa_yield_override=4.5),
        FCFGrowthSelection(),
    ],
)
def test_selection_json_round_trips_exactly(selection: object) -> None:
    encoded = encode_selection(selection)  # type: ignore[arg-type]
    decoded = decode_selection(selection.method_id, selection.config_schema_version, encoded)  # type: ignore[attr-defined]
    assert decoded == selection


def test_encode_selection_is_canonical_and_sorted() -> None:
    first = encode_selection(GrahamNumberSelection())
    second = encode_selection(GrahamNumberSelection())
    assert first == second
    assert '"analysis_id"' in first
    assert "\n" not in first


def test_decode_selection_rejects_method_id_mismatch() -> None:
    encoded = encode_selection(GrahamNumberSelection())
    with pytest.raises(ValueError, match="does not match"):
        decode_selection("graham_growth_value", 1, encoded)


def test_decode_selection_rejects_version_mismatch() -> None:
    encoded = encode_selection(GrahamNumberSelection())
    with pytest.raises(ValueError, match="does not match"):
        decode_selection("graham_number", 2, encoded)


def test_decode_selection_rejects_a_stored_momentum_selection_from_before_as_of_and_no_cache() -> None:
    """An entry saved with the retired version 1 shape is rejected, never read as version 2."""
    payload = json.loads(encode_selection(MomentumSelection(short_window=2, long_window=5)))
    payload["config_schema_version"] = 1
    del payload["as_of"], payload["use_cache"]
    with pytest.raises(StoredSelectionError, match=r"saved by an earlier version \(selection version 1\)"):
        decode_selection("sma_crossover", 1, json.dumps(payload))


def test_decode_selection_rejects_a_momentum_version_column_that_disagrees() -> None:
    encoded = encode_selection(MomentumSelection(short_window=2, long_window=5))
    with pytest.raises(ValueError, match="does not match"):
        decode_selection("sma_crossover", 1, encoded)


def test_decode_selection_rejects_malformed_json() -> None:
    with pytest.raises(ValueError, match="JSON"):
        decode_selection("graham_number", 1, "{not json")


def test_decode_selection_rejects_unknown_method_id() -> None:
    with pytest.raises(ValueError, match="not in a shape this version can read"):
        decode_selection("unknown_method", 1, '{"method_id": "unknown_method"}')
