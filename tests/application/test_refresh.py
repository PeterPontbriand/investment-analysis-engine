"""The refresh operations: preparing (the checks, the snapshot, the ID) and running (the outcome and progress)."""

import threading
from pathlib import Path

import pytest
from pydantic import JsonValue

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.application.refresh import (
    PreparedRefresh,
    RefreshEntries,
    RefreshEntry,
    RefreshOutcome,
    RefreshTarget,
    prepare_refresh,
    run_refresh,
)
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.application.watchlists import (
    add_watchlist_entries,
    create_watchlist,
    get_watchlist_summary,
)
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.data.repositories.readiness import DatabaseReadinessError
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategy_wiring import MOMENTUM
from investment_analysis_engine.workspace.refresh import (
    DEFAULT_WORKERS,
    EmptyRefreshTargetError,
    RefreshJobFinished,
    RefreshJobStarted,
    RefreshProgress,
)
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.watchlists import WatchlistId, WatchlistName, WatchlistNotFoundError
from tests.application._refresh_fakes import FakeRuns, Probe, fakes
from tests.application._unready_database import unready_database_url

_MOMENTUM = MomentumSelection(short_window=2, long_window=3, rsi_period=14)
_FIELDS: dict[str, JsonValue] = {"short_window": 2, "long_window": 3, "rsi_period": 14}


def _refresh(  # noqa: PLR0913
    context: ApplicationContext,
    target: RefreshTarget,
    *,
    workers: int = DEFAULT_WORKERS,
    save: bool = False,
    provider_check: bool = True,
    cancellation: threading.Event | None = None,
    on_progress: "object | None" = None,
) -> RefreshOutcome:
    """Prepare and run a refresh, as the command line does."""
    prepared = prepare_refresh(context, target, workers=workers, save=save, provider_check=provider_check)
    return run_refresh(context, prepared, cancellation=cancellation, on_progress=on_progress)  # type: ignore[arg-type]


def _entry(ticker: str, **fields: JsonValue) -> RefreshEntry:
    return RefreshEntry(ticker, MOMENTUM.method_id, {**_FIELDS, **fields})


def _seed(settings: ProjectSettings, tickers: tuple[str, ...] = ("AAPL", "MSFT")) -> ApplicationContext:
    context = ApplicationContext(settings=settings)
    create_watchlist(context, "Core")
    if tickers:
        add_watchlist_entries(context, WatchlistName("Core"), [(ticker, _MOMENTUM) for ticker in tickers])
    return context


def test_a_watchlist_is_refreshed_by_name_and_by_id(isolated_cli_settings: ProjectSettings) -> None:
    context = _seed(isolated_cli_settings)
    watchlist_id = get_watchlist_summary(context, WatchlistName("Core")).watchlist_id

    with fakes(Probe()):
        by_name = _refresh(context, WatchlistName("core"), workers=1)
        by_id = _refresh(context, WatchlistId(watchlist_id), workers=1)

    assert by_name.document.watchlist_id == by_id.document.watchlist_id == watchlist_id
    assert [result.ticker for result in by_id.document.results] == ["AAPL", "MSFT"]


def test_a_missing_watchlist_and_an_empty_one_are_reported_with_the_cli_messages(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = _seed(isolated_cli_settings, ())
    runs = FakeRuns()
    with fakes(Probe(), runs):
        with pytest.raises(WatchlistNotFoundError) as missing:
            prepare_refresh(context, WatchlistName("Nope"), workers=2, save=False, provider_check=True)
        with pytest.raises(EmptyRefreshTargetError) as empty:
            prepare_refresh(context, WatchlistName("Core"), workers=2, save=False, provider_check=True)
        watchlist_id = get_watchlist_summary(context, WatchlistName("Core")).watchlist_id
        with pytest.raises(EmptyRefreshTargetError) as empty_by_id:
            prepare_refresh(context, WatchlistId(watchlist_id), workers=2, save=False, provider_check=True)
        with pytest.raises(WatchlistNotFoundError) as missing_by_id:
            prepare_refresh(
                context,
                WatchlistId(type(watchlist_id)(int=watchlist_id.int ^ 1)),
                workers=2,
                save=False,
                provider_check=True,
            )

    assert str(missing.value) == "No watchlist named 'Nope' exists."
    assert str(empty.value) == "Watchlist 'Core' has no entries; there is nothing to refresh."
    assert str(empty_by_id.value) == "Watchlist 'Core' has no entries; there is nothing to refresh."
    assert str(missing_by_id.value).startswith("No watchlist with ID ")
    assert runs.calls == []


@pytest.mark.parametrize("workers", [0, 5, -1])
@pytest.mark.parametrize("by_entries", [False, True])
def test_a_worker_count_out_of_range_names_its_rule_and_values(
    isolated_cli_settings: ProjectSettings, workers: int, by_entries: bool
) -> None:
    context = _seed(isolated_cli_settings)
    target: RefreshTarget = RefreshEntries((_entry("AAPL"),)) if by_entries else WatchlistName("Core")

    with pytest.raises(ActionParameterError) as caught:
        prepare_refresh(context, target, workers=workers, save=False, provider_check=True)

    error = caught.value
    assert error.rule == "refresh.workers_range"
    assert error.template == "{workers} must be between {minimum} and {maximum}."
    assert error.arguments == {"value": workers, "minimum": 1, "maximum": 4}
    assert error.action_parameters == ("workers",)
    assert str(error) == "workers must be between 1 and 4."
    cli = error.named({"workers": "--workers"})
    assert str(cli) == "--workers must be between 1 and 4."
    assert cli.parameters == ("--workers",)


@pytest.mark.parametrize("by_entries", [False, True])
def test_the_arguments_are_checked_before_the_database_opens_and_the_database_before_any_job(
    tmp_path: Path, by_entries: bool
) -> None:
    unready = ApplicationContext(settings=ProjectSettings(database_url=unready_database_url(tmp_path)))
    target: RefreshTarget = RefreshEntries((_entry("AAPL"),)) if by_entries else WatchlistName("Core")
    runs = FakeRuns()

    with fakes(Probe(), runs):
        with pytest.raises(ActionParameterError):
            prepare_refresh(unready, target, workers=9, save=False, provider_check=True)
        with pytest.raises(DatabaseReadinessError):
            prepare_refresh(unready, target, workers=1, save=False, provider_check=True)

    assert runs.calls == []


def test_the_default_worker_count_is_two() -> None:
    assert DEFAULT_WORKERS == 2


def test_each_prepared_refresh_has_its_own_id_which_the_run_reports(isolated_cli_settings: ProjectSettings) -> None:
    context = _seed(isolated_cli_settings)
    with fakes(Probe()):
        first = prepare_refresh(context, WatchlistName("Core"), workers=1, save=False, provider_check=True)
        second = prepare_refresh(context, WatchlistName("Core"), workers=1, save=False, provider_check=True)
        outcome = run_refresh(context, first)

    assert isinstance(first, PreparedRefresh)
    assert first.snapshot.refresh_id != second.snapshot.refresh_id
    assert outcome.document.refresh_id == first.snapshot.refresh_id
    assert (first.workers, first.save, first.provider_check) == (1, False, True)


def test_a_refresh_without_a_failure_has_no_provider_check_and_text_is_the_summary(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = _seed(isolated_cli_settings)
    probe = Probe()

    with fakes(probe):
        outcome = _refresh(context, WatchlistName("Core"), workers=1, save=True)

    assert outcome.failed is False
    assert outcome.document.provider_check is None
    assert probe.calls == []
    lines = outcome.render_text().splitlines()
    assert lines[0] == f"Refresh {outcome.document.refresh_id} for 'Core':"
    assert lines[-1] == "Counts: completed=2"
    assert all(result.saved for result in outcome.document.results)


def test_a_refresh_with_a_provider_failure_fails_and_carries_the_check_first_in_text(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = _seed(isolated_cli_settings)
    probe = Probe()

    with fakes(probe, FakeRuns(failing=frozenset({"MSFT"}))):
        outcome = _refresh(context, WatchlistName("Core"), workers=1, save=True)

    assert outcome.failed is True
    assert probe.calls == [("yfinance", True)]
    assert outcome.document.provider_check is not None
    assert [(item.provider_id, item.verdict.value) for item in outcome.document.provider_check] == [
        ("yfinance", "unreachable")
    ]
    text = outcome.render_text().splitlines()
    assert text[0] == "Yahoo Finance is not answering: a test request also failed."
    assert text[1].startswith("Refresh ")


def test_the_provider_check_option_off_is_reported_and_sends_no_request(isolated_cli_settings: ProjectSettings) -> None:
    context = _seed(isolated_cli_settings)
    probe = Probe()

    with fakes(probe, FakeRuns(failing=frozenset({"MSFT"}))):
        _refresh(context, WatchlistName("Core"), workers=1, provider_check=False)

    assert probe.calls == [("yfinance", False)]


def test_progress_reaches_the_callback_on_the_calling_thread_and_a_finished_event_carries_its_run(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = _seed(isolated_cli_settings)
    events: list[RefreshProgress[StrategyRun]] = []
    threads: set[int] = set()

    def observe(event: RefreshProgress[StrategyRun]) -> None:
        events.append(event)
        threads.add(threading.get_ident())

    with fakes(Probe(), FakeRuns(raising=frozenset({"MSFT"}))):
        outcome = _refresh(context, WatchlistName("Core"), workers=2, save=True, on_progress=observe)

    assert threads == {threading.get_ident()}
    assert sum(isinstance(event, RefreshJobStarted) for event in events) == 2
    finished = [event for event in events if isinstance(event, RefreshJobFinished)]
    assert len(finished) == 2
    assert {event.refresh_id for event in events} == {outcome.document.refresh_id}
    by_ticker = {event.result.ticker: event for event in finished}
    assert isinstance(by_ticker["AAPL"].produced, StrategyRun)
    assert by_ticker["MSFT"].produced is None  # the job raised
    assert by_ticker["MSFT"].result.error is not None


def test_each_job_reads_its_own_clock(isolated_cli_settings: ProjectSettings) -> None:
    context = _seed(isolated_cli_settings)
    runs = FakeRuns()

    with fakes(Probe(), runs):
        _refresh(context, WatchlistName("Core"), workers=1)

    assert [ticker for ticker, _ in runs.calls] == ["AAPL", "MSFT"]
    assert all(executed_at.tzinfo is not None for _ticker, executed_at in runs.calls)
    assert runs.calls[0][1] <= runs.calls[1][1]


# --- a list of entries ---------------------------------------------------------------------------------------------


def test_entries_are_refreshed_and_belong_to_no_watchlist(isolated_cli_settings: ProjectSettings) -> None:
    context = ApplicationContext(settings=isolated_cli_settings)
    entries = RefreshEntries((_entry(" aapl "), _entry("MSFT", short_window=1)))

    with fakes(Probe()):
        prepared = prepare_refresh(context, entries, workers=1, save=True, provider_check=True)
        outcome = run_refresh(context, prepared)

    document = outcome.document
    assert (document.watchlist_id, document.watchlist_name) == (None, None)
    assert document.schema_version == 4
    assert [result.ticker for result in document.results] == ["AAPL", "MSFT"]
    assert outcome.render_text().splitlines()[0] == f"Refresh {document.refresh_id}:"
    database = SQLiteDatabase(isolated_cli_settings)
    try:
        stored = SQLiteAnalysisRunRepository(database).list_refresh_runs(document.refresh_id)
    finally:
        database.close()
    runs = [item.envelope() for item in stored]
    assert [(run.batch_position, run.ticker) for run in runs] == [(0, "AAPL"), (1, "MSFT")]
    assert all(run.refresh_id == document.refresh_id for run in runs)
    assert all(run.watchlist_id is None and run.watchlist_name is None for run in runs)
    assert runs[1].requested_config.model_dump()["short_window"] == 1


def test_the_stored_runs_of_an_entries_refresh_match_those_of_a_watchlist_refresh(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = _seed(isolated_cli_settings)

    with fakes(Probe()):
        from_watchlist = _refresh(context, WatchlistName("Core"), workers=1, save=True)
        from_entries = _refresh(context, RefreshEntries((_entry("AAPL"), _entry("MSFT"))), workers=1, save=True)

    database = SQLiteDatabase(isolated_cli_settings)
    try:
        repository = SQLiteAnalysisRunRepository(database)
        first = [item.envelope() for item in repository.list_refresh_runs(from_watchlist.document.refresh_id)]
        second = [item.envelope() for item in repository.list_refresh_runs(from_entries.document.refresh_id)]
    finally:
        database.close()

    kept = {"ticker", "analysis_id", "method_id", "batch_position", "status", "requested_config", "method_version"}
    assert [run.model_dump(include=kept) for run in first] == [run.model_dump(include=kept) for run in second]
    assert all(run.watchlist_name == "Core" for run in first)
    assert all(run.watchlist_name is None for run in second)


def _entry_error(entries: tuple[RefreshEntry, ...], context: ApplicationContext) -> InvalidParameterError:
    with pytest.raises(InvalidParameterError) as caught:
        prepare_refresh(context, RefreshEntries(entries), workers=1, save=False, provider_check=True)
    return caught.value


def test_an_entry_error_is_named_by_its_index_and_every_error_is_listed(
    isolated_cli_settings: ProjectSettings,
) -> None:
    context = ApplicationContext(settings=isolated_cli_settings)
    entries = (
        _entry("AAPL"),
        _entry("MSFT"),
        _entry("KO", short_window=5),  # short_window must be below long_window
        RefreshEntry("PG", "no_such_method", {}),
        _entry("  "),
        _entry("T", rsi_period="x"),
    )

    error = _entry_error(entries, context)

    names = [violation.parameters for violation in error.violations]
    assert names == [
        ("entries[2].selection.short_window", "entries[2].selection.long_window"),
        ("entries[3].method_id",),
        ("entries[4].ticker",),
        ("entries[5].selection.rsi_period",),
    ]
    assert error.parameters == ("entries[2].selection.short_window", "entries[2].selection.long_window")
    assert str(error) == error.violations[0].message
    assert error.violations[2].rule == "refresh.blank_ticker"
    assert error.violations[2].message == "entries[4].ticker must be a non-empty symbol."


def test_a_repeated_entry_is_a_duplicate_but_another_selection_is_not(isolated_cli_settings: ProjectSettings) -> None:
    context = ApplicationContext(settings=isolated_cli_settings)

    error = _entry_error((_entry("AAPL"), _entry("MSFT"), _entry(" aapl "), _entry("MSFT")), context)

    assert [violation.parameters for violation in error.violations] == [("entries[2]",), ("entries[3]",)]
    assert {violation.rule for violation in error.violations} == {"entries.duplicate"}
    assert error.violations[0].message == (
        f"entries[2] must not duplicate an entry: AAPL is already listed for {MOMENTUM.method_id} with an equal "
        "selection earlier in this request."
    )
    assert dict(error.violations[0].arguments) == {
        "ticker": "AAPL",
        "method_id": MOMENTUM.method_id,
        "where": "earlier in this request",
    }
    with fakes(Probe()):  # the same ticker and method under a different selection is allowed
        prepared = prepare_refresh(
            context,
            RefreshEntries((_entry("AAPL"), _entry("AAPL", short_window=1))),
            workers=1,
            save=False,
            provider_check=True,
        )
    assert len(prepared.snapshot.entries) == 2


def test_an_empty_list_of_entries_names_its_rule(isolated_cli_settings: ProjectSettings) -> None:
    context = ApplicationContext(settings=isolated_cli_settings)

    with pytest.raises(ActionParameterError) as caught:
        prepare_refresh(context, RefreshEntries(()), workers=1, save=False, provider_check=True)

    assert caught.value.rule == "refresh.entries_empty"
    assert str(caught.value) == "entries must hold at least one entry."
    assert caught.value.parameters == ("entries",)


def test_no_entry_runs_when_any_entry_is_rejected(isolated_cli_settings: ProjectSettings) -> None:
    context = ApplicationContext(settings=isolated_cli_settings)
    runs = FakeRuns()

    with fakes(Probe(), runs), pytest.raises(InvalidParameterError):
        prepare_refresh(
            context,
            RefreshEntries((_entry("AAPL"), _entry("KO", short_window=9))),
            workers=1,
            save=True,
            provider_check=True,
        )

    assert runs.calls == []
