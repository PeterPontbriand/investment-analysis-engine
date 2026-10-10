"""Compare each strategy's ``--json`` document, direct and replayed, byte for byte with stored output.

The stored files under ``tests/expected_output/strategy_documents/`` were captured from the hand-written document
builders before any builder changed, one per reachable shape: every document status of every strategy, the optional
evidence that is present or absent, and the same run replayed through ``runs show --json``. This is the check that
the typed documents write the same bytes. See ``tests/_strategy_document_output.py`` for the cases and for how to
regenerate the files deliberately; only the normalization of ``tests/test_direct_command_output.py`` applies.
"""

from __future__ import annotations

import json

import pytest

from tests._strategy_document_output import EXPECTED_DIRECTORY, cases, expected_exit_code, expected_path, produce


@pytest.mark.parametrize("stem", list(cases()))
def test_the_document_matches_the_stored_output(stem: str) -> None:
    """Each case prints exactly the stored bytes with the exit code its status requires."""
    output = produce(stem)
    assert output.exit_code == expected_exit_code(stem)
    assert output.stdout == expected_path(stem).read_bytes()


def test_every_stored_file_belongs_to_a_case() -> None:
    """No stored file is left behind by a removed case, and no case lacks its file."""
    stored = {path.name.removesuffix(".json") for path in EXPECTED_DIRECTORY.glob("*.json")}
    assert stored == set(cases())


def test_every_strategy_has_a_document_for_each_status_it_can_report() -> None:
    """The captured set spans each strategy's statuses, so a status cannot lose its byte check unnoticed."""
    statuses: dict[str, set[str]] = {}
    trends: set[str] = set()
    for stem in cases():
        document = json.loads(expected_path(stem).read_bytes())
        statuses.setdefault(document["analysis"], set()).add(document["status"])
        if document["analysis"] == "momentum":
            trends.add(document["result"]["trend"])
    assert statuses["momentum"] == {"ok"}
    assert trends >= {"BULLISH", "UNKNOWN"}
    for graham in ("graham_number", "graham_growth_value"):
        assert statuses[graham] == {"ok", "not_applicable", "input_unavailable", "provider_error", "invalid_input"}
    assert statuses["fcf_earnings_growth"] == {
        "ok",
        "not_applicable",
        "input_unavailable",
        "provider_error",
        "invalid_input",
    }
