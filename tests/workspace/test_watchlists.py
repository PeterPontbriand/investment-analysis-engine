"""Focused tests for the watchlist creation spec and selection JSON codec."""

import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.workspace.watchlists import (
    StoredSelectionError,
    WatchlistId,
    WatchlistName,
    WatchlistSpec,
    decode_selection,
    encode_selection,
    not_found_message,
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


@pytest.mark.parametrize(
    "selection",
    [
        MomentumSelection(short_window=2, long_window=5, rsi_period=14),
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
        decode_selection("graham_number", 1, encoded)


def test_decode_selection_rejects_a_stored_momentum_selection_from_before_as_of_and_no_cache() -> None:
    """An entry saved with the retired version 1 shape is rejected, never read as version 2."""
    payload = json.loads(encode_selection(MomentumSelection(short_window=2, long_window=5, rsi_period=14)))
    payload["config_schema_version"] = 1
    del payload["as_of"], payload["use_cache"]
    with pytest.raises(StoredSelectionError, match=r"saved by an earlier version \(selection version 1\)"):
        decode_selection("sma_crossover", 1, json.dumps(payload, ensure_ascii=False))


def test_decode_selection_rejects_a_momentum_version_column_that_disagrees() -> None:
    encoded = encode_selection(MomentumSelection(short_window=2, long_window=5, rsi_period=14))
    with pytest.raises(ValueError, match="does not match"):
        decode_selection("sma_crossover", 1, encoded)


def test_decode_selection_rejects_malformed_json() -> None:
    with pytest.raises(ValueError, match="JSON"):
        decode_selection("graham_number", 1, "{not json")


def test_decode_selection_rejects_unknown_method_id() -> None:
    with pytest.raises(ValueError, match="not in a shape this version can read"):
        decode_selection("unknown_method", 1, '{"method_id": "unknown_method"}')


def test_a_stored_selection_error_names_an_entry_by_all_five_fields_or_by_none() -> None:
    clause_only = StoredSelectionError("its stored selection is not valid JSON")
    named = StoredSelectionError(
        "its stored selection is not valid JSON",
        watchlist_name="Core",
        entry_number=2,
        ticker="KO",
        method="momentum",
        method_id="momentum_sma_crossover",
    )

    assert str(clause_only) == "its stored selection is not valid JSON"
    assert clause_only.watchlist_name is None
    assert str(named) == "Watchlist 'Core', entry 2 (KO, momentum): its stored selection is not valid JSON."
    assert (named.watchlist_name, named.entry_number, named.ticker, named.method, named.method_id) == (
        "Core",
        2,
        "KO",
        "momentum",
        "momentum_sma_crossover",
    )
    with pytest.raises(ValueError, match="all of its five fields or by none"):
        StoredSelectionError("clause", watchlist_name="Core")


def test_the_not_found_message_names_the_watchlist_as_it_was_addressed() -> None:
    watchlist_id = UUID(int=3)

    assert not_found_message(WatchlistName("Core")) == "No watchlist named 'Core' exists."
    assert not_found_message(WatchlistId(watchlist_id)) == f"No watchlist with ID {watchlist_id} exists."
