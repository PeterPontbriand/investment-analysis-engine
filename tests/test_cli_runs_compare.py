"""``ian runs compare``: the stored runs of one refresh as one table, rebuilt from storage only.

Every test refreshes a real watchlist offline (``tests/_runs_compare_refresh.py``) and then compares the stored refresh
with the provider, cache and clock unreachable.
"""

import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from typer.testing import CliRunner

from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.workspace_documents.runs_compare import RunsCompareDocument
from tests._runs_compare_refresh import (
    ENTRIES,
    GROWTH,
    LONG_AVERAGE,
    MOMENTUM,
    PER_SHARE,
    alter_row,
    refresh,
    refresh_document,
    run_ids,
)

pytestmark = pytest.mark.usefixtures("isolated_cli_settings", "stub_yahoo_identity_metadata")

runner = CliRunner()

_FETCH = "investment_analysis_engine.data.yfinance.client.YFinanceClient.fetch_data_with_context"


def _compare(refresh_id: UUID | str, *extra: str) -> tuple[int, str, str]:
    result = runner.invoke(app, ["runs", "compare", str(refresh_id), *extra])
    return result.exit_code, result.stdout, result.stderr


def _document(refresh_id: UUID) -> RunsCompareDocument:
    code, out, _err = _compare(refresh_id, "--json")
    assert code == 0, out
    return RunsCompareDocument.model_validate_json(out)


def test_the_table_of_a_stored_refresh_equals_the_reviewed_layout(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(isolated_cli_settings)
    ids = run_ids(isolated_cli_settings, refresh_id)
    momentum, number, growth, fcf = "sma_crossover", "graham_number", "graham_growth_value", "reported_fcf_eps_cagr"

    code, out, err = _compare(refresh_id)

    assert (code, err) == (0, "")
    assert out.splitlines() == [
        f'Refresh {refresh_id} · watchlist "Core" · 3 tickers · 4 strategies',
        "",
        "         Momentum                      Graham Number                       Graham Growth",
        "Ticker   Trend     RSI    Outcome      Max price      Margin  Outcome      Value          Margin  Outcome",
        "SYNTH    Bullish   100.0  completed    36.69 USD      —       completed    66.28 USD      —       completed",
        "MISSING  —         100.0  unavailable  —              —       unavailable  no stored run  —       —",
        "ERROR    —         —      failed       —              —       failed       —              —       failed",
        "",
        "         FCF Growth",
        "Ticker   FCF CAGR / FCF/share CAGR  EPS CAGR  Class          Outcome",
        "SYNTH    10.2%                      17.6%     PASS           completed",
        "MISSING  —                          —         INDETERMINATE  unavailable",
        "ERROR    10.2%†                     17.6%     PASS           completed",
        "",
        "† marks a value labelled FCF/share CAGR, not the first label of its column header",
        "",
        "Period ends",
        "  SYNTH    Graham Number: earnings input period end 2024-06-30 · Graham Growth: earnings input period end"
        " 2024-06-30",
        "           FCF Growth: selected span end 2025-01-01",
        "  MISSING  Graham Number: earnings input period end not recorded · FCF Growth: selected span end not recorded",
        "  ERROR    Graham Number: earnings input period end not recorded · Graham Growth: earnings input period end"
        " not recorded",
        "           FCF Growth: selected span end 2025-01-01",
        "",
        "Runs (open one with: ian runs show <run-id>)",
        f"  SYNTH    momentum       {ids[('SYNTH', momentum)]}",
        f"  SYNTH    graham-number  {ids[('SYNTH', number)]}",
        f"  SYNTH    graham-growth  {ids[('SYNTH', growth)]}",
        f"  SYNTH    fcf-growth     {ids[('SYNTH', fcf)]}",
        f"  MISSING  momentum       {ids[('MISSING', momentum)]}",
        f"  MISSING  graham-number  {ids[('MISSING', number)]}",
        f"  MISSING  fcf-growth     {ids[('MISSING', fcf)]}",
        f"  ERROR    momentum       {ids[('ERROR', momentum)]}",
        f"  ERROR    graham-number  {ids[('ERROR', number)]}",
        f"  ERROR    graham-growth  {ids[('ERROR', growth)]}",
        f"  ERROR    fcf-growth     {ids[('ERROR', fcf)]}",
    ]


def test_the_json_document_validates_and_carries_the_same_content_as_the_text(
    isolated_cli_settings: ProjectSettings,
) -> None:
    refresh_id = refresh(isolated_cli_settings)
    _code, out, _err = _compare(refresh_id, "--json")

    assert list(json.loads(out))[0] == "schema_version"
    document = RunsCompareDocument.model_validate_json(out)

    assert document.schema_version == 1
    assert (document.refresh_id, document.watchlist_name) == (refresh_id, "Core")
    assert [item.alias for item in document.strategies] == ["momentum", "graham-number", "graham-growth", "fcf-growth"]
    assert [row.ticker for row in document.rows] == ["SYNTH", "MISSING", "ERROR"]
    missing_growth = document.rows[1].entries[2]
    assert (missing_growth.method_id, missing_growth.run) == ("graham_growth_value", None)
    synth_run = document.rows[0].entries[1].run
    assert synth_run is not None
    assert synth_run.headline is not None
    price = synth_run.headline.cells[0]
    assert (price.key, price.label, price.kind.value, price.unit, price.status) == (
        "maximum_indicated_price",
        "Max price",
        "number",
        "USD per share",
        "ok",
    )
    assert price.value == pytest.approx(36.686169055926236)
    assert synth_run.headline.period_end_label == "earnings input period end"
    assert synth_run.headline.taxonomy is None
    failed = document.rows[2].entries[0].run
    assert failed is not None
    assert failed.headline is not None
    assert failed.outcome.value == "failed"
    rsi = failed.headline.cells[1]
    assert (rsi.value, rsi.status, rsi.reason_code) == (None, "provider_error", "provider_error")
    trend = failed.headline.cells[0]
    assert (trend.kind.value, trend.value, trend.status, trend.unit) == ("text", None, None, None)


def test_the_table_is_built_from_storage_alone(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(isolated_cli_settings)
    before = _compare(refresh_id)

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("The table must not reach a provider, a cache or the clock.")

    with (
        patch(_FETCH, side_effect=refuse),
        patch("investment_analysis_engine.core.clock.utc_now", side_effect=refuse),
        patch("investment_analysis_engine.cli_workspace.utc_now", side_effect=refuse),
    ):
        assert _compare(refresh_id) == before


def test_a_watchlist_deleted_after_the_refresh_changes_nothing(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(isolated_cli_settings)
    before = _compare(refresh_id)

    deleted = runner.invoke(app, ["watchlist", "delete", "Core", "--yes"])

    assert deleted.exit_code == 0, deleted.output
    assert _compare(refresh_id) == before


def test_a_refresh_holding_one_strategy_has_one_column_group(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(isolated_cli_settings, entries=[("SYNTH", MOMENTUM), ("ERROR", MOMENTUM)])

    document = _document(refresh_id)
    _code, out, _err = _compare(refresh_id)

    assert [item.alias for item in document.strategies] == ["momentum"]
    assert out.split("\n")[2].strip() == "Momentum"
    assert out.split("\n")[3].split() == ["Ticker", "Trend", "RSI", "Outcome"]


def test_a_refresh_larger_than_the_query_limit_shows_every_row(isolated_cli_settings: ProjectSettings) -> None:
    tickers = [f"T{number:03d}" for number in range(101)]
    refresh_id = refresh(isolated_cli_settings, entries=[(ticker, MOMENTUM) for ticker in tickers])

    document = _document(refresh_id)

    assert [row.ticker for row in document.rows] == tickers, "Rows follow the watchlist, past the 100-run limit."


def test_a_failed_run_keeps_its_row_and_the_exit_code_is_zero(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(isolated_cli_settings, entries=[("ERROR", MOMENTUM), ("ERROR", GrahamNumberSelection())])

    code, out, err = _compare(refresh_id)

    assert (code, err) == (0, "")
    assert out.split("\n")[4].split() == ["ERROR", "—", "—", "failed", "—", "—", "failed"]


def test_a_per_share_refresh_names_its_basis_in_the_header(isolated_cli_settings: ProjectSettings) -> None:
    total = refresh(isolated_cli_settings, "Total", [("SYNTH", FCFGrowthSelection())])
    per_share = refresh(isolated_cli_settings, "Share", [("SYNTH", PER_SHARE)])

    total_header = _compare(total)[1].splitlines()[3]
    assert "FCF CAGR" in total_header
    assert "FCF/share" not in total_header
    assert "FCF/share CAGR" in _compare(per_share)[1].splitlines()[3]


def test_a_missing_pair_says_no_stored_run_once_per_strategy(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(isolated_cli_settings)

    _code, out, _err = _compare(refresh_id)

    assert out.count("no stored run") == 1


def test_requested_as_of_dates_are_listed_only_when_more_than_one(isolated_cli_settings: ProjectSettings) -> None:
    same = refresh(isolated_cli_settings, "Same", [("SYNTH", MOMENTUM)])
    mixed = refresh(
        isolated_cli_settings,
        "Mixed",
        [("SYNTH", MOMENTUM), ("ERROR", MomentumSelection(short_window=2, long_window=3, rsi_period=3, as_of=_AS_OF))],
    )

    assert "Requested as-of" not in _compare(same)[1]
    assert "Requested as-of: now, 2026-02-01" in _compare(mixed)[1]
    document = _document(mixed)
    requested = [entry.run.requested_as_of for row in document.rows for entry in row.entries if entry.run is not None]
    assert requested == [None, _AS_OF]


_AS_OF = datetime(2026, 2, 1, tzinfo=UTC)


def test_a_column_whose_runs_give_different_labels_is_headed_by_all_and_marks_the_later_ones(
    isolated_cli_settings: ProjectSettings,
) -> None:
    refresh_id = refresh(
        isolated_cli_settings, entries=[("SYNTH", FCFGrowthSelection()), ("ERROR", PER_SHARE), ("MISSING", PER_SHARE)]
    )

    code, out, err = _compare(refresh_id)

    assert (code, err) == (0, "")
    lines = out.splitlines()
    assert "FCF CAGR / FCF/share CAGR  EPS CAGR" in lines[3]
    assert lines[4].split()[1] == "10.2%", "The first label's value carries no marker."
    assert lines[5].split()[1] == "10.2%†"
    assert lines[6].split()[1] == "—†", "A value that is absent still says which label it would have had."
    assert lines[7] == ""
    assert lines[8] == "† marks a value labelled FCF/share CAGR, not the first label of its column header"
    assert out.count("marks a value labelled") == 1
    document = _document(refresh_id)
    labels = [row.entries[0].run.headline.cells[0].label for row in document.rows if row.entries[0].run]  # type: ignore[union-attr]
    assert labels == ["FCF CAGR", "FCF/share CAGR", "FCF/share CAGR"], "--json keeps each run's own label."


def test_no_legend_is_shown_when_every_run_of_a_column_has_the_same_label(
    isolated_cli_settings: ProjectSettings,
) -> None:
    refresh_id = refresh(
        isolated_cli_settings, entries=[("SYNTH", FCFGrowthSelection()), ("ERROR", FCFGrowthSelection())]
    )

    _code, out, _err = _compare(refresh_id)

    assert "†" not in out
    assert "marks a value" not in out


def test_a_strategy_with_a_fiscal_period_shows_not_recorded_and_momentum_is_left_out(
    isolated_cli_settings: ProjectSettings,
) -> None:
    refresh_id = refresh(
        isolated_cli_settings,
        entries=[
            ("SYNTH", MOMENTUM),
            ("SYNTH", GrahamNumberSelection(eps_override=5.0, bvps_override=10.0)),
            ("ERROR", FCFGrowthSelection()),
            ("ERROR", GrahamNumberSelection()),
        ],
    )

    _code, out, _err = _compare(refresh_id)

    block = out.split("Period ends\n", 1)[1].split("\n\n", 1)[0].splitlines()
    assert block == [
        "  SYNTH  Graham Number: earnings input period end not recorded",
        "  ERROR  Graham Number: earnings input period end not recorded · FCF Growth: selected span end 2025-01-01",
    ]
    assert "Momentum:" not in "\n".join(block)


# The currency of a per-share value ------------------------------------------------------------------------------


def test_overridden_earnings_and_book_value_show_the_value_without_a_currency(
    isolated_cli_settings: ProjectSettings,
) -> None:
    refresh_id = refresh(
        isolated_cli_settings, entries=[("SYNTH", GrahamNumberSelection(eps_override=5.0, bvps_override=10.0))]
    )

    _code, out, _err = _compare(refresh_id)
    document = _document(refresh_id)

    assert "(currency unspecified)" in out
    run = document.rows[0].entries[0].run
    assert run is not None
    assert run.headline is not None
    assert run.headline.cells[0].unit == "currency unspecified per share"
    assert run.headline.period_end is None, "An override has no period."
    assert "earnings input period end not recorded" in out


def test_overridden_earnings_show_the_growth_value_without_a_currency(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(
        isolated_cli_settings,
        entries=[("SYNTH", GrahamGrowthSelection(eps_override=5.0, expected_growth=6.0, aaa_yield_override=4.4))],
    )

    _code, out, _err = _compare(refresh_id)
    document = _document(refresh_id)

    assert "(currency unspecified)" in out
    run = document.rows[0].entries[0].run
    assert run is not None
    assert run.headline is not None
    assert run.headline.cells[0].unit == "currency unspecified per share"


def test_a_reported_currency_follows_the_number(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(isolated_cli_settings, entries=[("SYNTH", GrahamNumberSelection())])

    assert "36.69 USD" in _compare(refresh_id)[1]


# A refresh that cannot be shown ---------------------------------------------------------------------------------

_NOT_FOUND = "No runs are stored for refresh {id}. The ID is unknown, or the refresh was run with --no-save."


def test_an_unknown_refresh_and_a_no_save_refresh_give_the_same_message_and_code(
    isolated_cli_settings: ProjectSettings,
) -> None:
    unsaved = refresh_document(isolated_cli_settings, "Unsaved", [("SYNTH", MOMENTUM)], "--no-save")
    unsaved_id = unsaved["refresh_id"]
    unknown_id = str(uuid4())

    for identifier in (unsaved_id, unknown_id):
        code, out, err = _compare(identifier)
        assert (code, out) == (1, "")
        assert err.strip() == _NOT_FOUND.format(id=identifier)
        code, out, err = _compare(identifier, "--json")
        envelope = json.loads(out)
        assert (code, err) == (1, "")
        assert (envelope["status"], envelope["reason_code"]) == ("error", "analysis_run_not_found")
        assert envelope["reason"] == _NOT_FOUND.format(id=identifier)


def test_two_runs_of_one_ticker_and_strategy_refuse_the_table_and_name_the_duplicates(
    isolated_cli_settings: ProjectSettings,
) -> None:
    refresh_id = refresh(
        isolated_cli_settings,
        entries=[("SYNTH", MOMENTUM), ("SYNTH", LONG_AVERAGE), ("ERROR", GROWTH), ("ERROR", GROWTH)],
    )

    code, out, err = _compare(refresh_id)

    assert (code, out) == (1, "")
    assert "SYNTH momentum" in err
    assert "ERROR graham-growth" in err
    code, out, _err = _compare(refresh_id, "--json")
    envelope = json.loads(out)
    assert (code, envelope["reason_code"]) == (1, "invalid_input")
    assert "SYNTH momentum" in envelope["reason"]


def test_a_malformed_refresh_id_is_an_invalid_parameter() -> None:
    code, out, _err = _compare("not-a-uuid", "--json")

    assert code == 1
    assert json.loads(out)["reason_code"] == "invalid_parameter"


# Runs the table cannot read -------------------------------------------------------------------------------------


def _age(settings: ProjectSettings, run_id: str) -> None:
    """Store a run as the version before the Momentum result status: result schema 4 and evidence codec 3."""

    def envelope(document: dict[str, object]) -> None:
        document["result_schema_version"] = 4
        document["evidence_codec_version"] = 3

    alter_row(settings, run_id, {"result_schema_version": 4, "evidence_codec_version": 3}, envelope)


def test_a_momentum_run_stored_before_the_result_status_shows_its_outcome_and_a_note(
    isolated_cli_settings: ProjectSettings,
) -> None:
    refresh_id = refresh(isolated_cli_settings, entries=[("SYNTH", MOMENTUM), ("ERROR", MOMENTUM)])
    old_id = run_ids(isolated_cli_settings, refresh_id)[("ERROR", "sma_crossover")]
    _age(isolated_cli_settings, old_id)

    code, out, err = _compare(refresh_id)

    assert (code, err) == (0, "")
    lines = out.split("\n")
    assert lines[3].split() == ["Ticker", "Trend", "RSI", "Outcome"]
    assert lines[4].split() == ["SYNTH", "Bullish", "100.0", "completed"]
    assert lines[5].split() == ["ERROR", "—", "—", "failed"], "The outcome is read from the stored envelope status."
    assert (
        f"Could not be read (stored under an older version, or for a strategy no longer declared):\n  {old_id}\n" in out
    )
    document = _document(refresh_id)
    run = document.rows[1].entries[0].run
    assert run is not None
    assert (run.headline, run.headline_unavailable, run.outcome.value) == (None, "unsupported_version", "failed")


def test_a_run_for_a_strategy_no_longer_declared_follows_the_declared_columns(
    isolated_cli_settings: ProjectSettings,
) -> None:
    refresh_id = refresh(isolated_cli_settings, entries=[("SYNTH", MOMENTUM), ("SYNTH", GrahamNumberSelection())])
    gone_id = run_ids(isolated_cli_settings, refresh_id)[("SYNTH", "graham_number")]
    alter_row(
        isolated_cli_settings,
        gone_id,
        {"analysis_id": "retired", "method_id": "retired_method"},
        lambda document: document.update(analysis_id="retired", method_id="retired_method"),
    )

    code, out, _err = _compare(refresh_id)

    assert code == 0
    assert out.split("\n")[2].split() == ["Momentum", "retired_method"]
    assert out.split("\n")[4].split() == ["SYNTH", "Bullish", "100.0", "completed", "completed"]
    assert f"or for a strategy no longer declared):\n  {gone_id}\n" in out
    document = _document(refresh_id)
    assert [(item.method_id, item.declared, item.alias) for item in document.strategies] == [
        ("sma_crossover", True, "momentum"),
        ("retired_method", False, None),
    ]
    run = document.rows[0].entries[1].run
    assert run is not None
    assert (run.headline, run.headline_unavailable) == (None, "strategy_not_declared")


def test_a_run_with_invalid_evidence_refuses_the_table_and_names_the_run(
    isolated_cli_settings: ProjectSettings,
) -> None:
    refresh_id = refresh(isolated_cli_settings, entries=[("SYNTH", MOMENTUM), ("ERROR", MOMENTUM)])
    bad_id = run_ids(isolated_cli_settings, refresh_id)[("SYNTH", "sma_crossover")]

    def corrupt(document: dict[str, object]) -> None:
        evidence = document["result_evidence"]
        assert isinstance(evidence, dict)
        evidence["run"]["metrics"]["current_price"] = "not a number"

    alter_row(isolated_cli_settings, bad_id, {}, corrupt)

    code, out, err = _compare(refresh_id)
    assert (code, out) == (1, "")
    assert f"Analysis Run {bad_id} could not be read" in err
    code, out, err = _compare(refresh_id, "--json")
    envelope = json.loads(out)
    assert (code, err, envelope["reason_code"]) == (1, "", "invalid_stored_run")
    assert bad_id in envelope["reason"]


def test_a_malformed_envelope_refuses_the_table_as_runs_show_does(isolated_cli_settings: ProjectSettings) -> None:
    refresh_id = refresh(isolated_cli_settings, entries=[("SYNTH", MOMENTUM)])
    bad_id = run_ids(isolated_cli_settings, refresh_id)[("SYNTH", "sma_crossover")]
    path = isolated_cli_settings.database_url.removeprefix("sqlite:///")
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("UPDATE analysis_runs SET envelope_json = '{}' WHERE analysis_run_id = ?", (bad_id,))
        connection.commit()

    code, out, err = _compare(refresh_id, "--json")

    envelope = json.loads(out)
    assert (code, err, envelope["reason_code"]) == (1, "", "invalid_stored_run")
    assert bad_id in envelope["reason"]


def test_the_entries_fixture_covers_every_strategy() -> None:
    assert {type(selection) for _ticker, selection in ENTRIES} == {
        MomentumSelection,
        GrahamNumberSelection,
        GrahamGrowthSelection,
        FCFGrowthSelection,
    }
