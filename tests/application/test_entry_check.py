"""Adding entries checks each distinct ticker once, warns of each unconfirmed one and never refuses or fails."""

import logging
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from investment_analysis_engine.application import entry_check
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.entry_check import AddedEntries, add_watchlist_entries_checked
from investment_analysis_engine.application.instrument_profiles import lookup_instrument_profile
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.application.watchlists import create_watchlist, get_watchlist_by_name
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.entry_warnings import EntryWarningCode, join_labels
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.core.operator_errors import AnalysisConfigurationError
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.repositories.database_errors import DatabaseError, DatabaseReason
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategies.piotroski.selection import PiotroskiSelection
from investment_analysis_engine.workspace.strategy_types import AnalysisSelection
from investment_analysis_engine.workspace.watchlists import WatchlistName
from tests._instrument_profile_fakes import (
    FakeSec,
    FakeYahoo,
    profile_context,
    store_profile,
    use_providers,
    use_yahoo_only,
)
from tests.application._unready_database import unready_database_url

_SELECTION = MomentumSelection(short_window=2, long_window=3, rsi_period=14)
_REF = WatchlistName("Core")

_NOT_RECOGNIZED = "No data provider recognizes {ticker}. Check the ticker, and remove the entry if it is wrong."
_UNREACHABLE = "{ticker} could not be checked, because the data providers could not be reached."
_RATE_LIMITED = "{ticker} could not be checked, because a data provider asked the engine to wait before asking again."
_UNEXPECTED = "{ticker} could not be checked, because a data provider gave an unexpected answer."
_DATABASE = "{ticker} could not be checked, because the engine's database was not available."


def _seeded(settings: ProjectSettings) -> ApplicationContext:
    context = ApplicationContext(settings=settings)
    create_watchlist(context, "Core")
    return context


def _add(context: ApplicationContext, *tickers: str) -> AddedEntries:
    return add_watchlist_entries_checked(context, _REF, [(ticker, _SELECTION) for ticker in tickers])


def _answers(monkeypatch: pytest.MonkeyPatch, outcomes: dict[str, BaseException | None]) -> list[str]:
    """Make the lookup answer each ticker as ``outcomes`` says (``None`` is a resolved profile); return its calls."""
    asked: list[str] = []

    def lookup(_context: ApplicationContext, ticker: str) -> None:
        asked.append(ticker)
        outcome = outcomes[ticker]
        if outcome is not None:
            raise outcome

    monkeypatch.setattr(entry_check, "lookup_instrument_profile", lookup)
    return asked


def _fetch(kind: ProviderFailureKind | None) -> DataFetchError:
    return DataFetchError("failed", kind=kind, provider_id="yfinance")


def _tickers(context: ApplicationContext) -> list[str]:
    return [entry.ticker for entry in get_watchlist_by_name(context, "Core").entries]


def test_a_mix_of_recognized_unrecognized_and_unchecked_tickers_adds_every_entry_and_warns_of_two(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _seeded(isolated_cli_settings)
    asked = _answers(
        monkeypatch,
        {
            "KO": None,
            "KOO": _fetch(ProviderFailureKind.NO_DATA),
            "MSFT": _fetch(ProviderFailureKind.UNEXPECTED_RESPONSE),
        },
    )

    added = _add(context, "ko", "KOO", "MSFT")

    assert [entry.ticker for entry in added.watchlist.entries] == ["KO", "KOO", "MSFT"]
    assert _tickers(context) == ["KO", "KOO", "MSFT"]
    assert asked == ["KO", "KOO", "MSFT"]
    assert [(item.ticker, item.code, item.reason_code, item.message) for item in added.warnings] == [
        ("KOO", EntryWarningCode.TICKER_NOT_RECOGNIZED, None, _NOT_RECOGNIZED.format(ticker="KOO")),
        (
            "MSFT",
            EntryWarningCode.TICKER_NOT_CHECKED,
            FailureReasonCode.PROVIDER_UNEXPECTED_RESPONSE,
            _UNEXPECTED.format(ticker="MSFT"),
        ),
    ]
    warning = added.warnings[0]
    assert warning.arguments == {"ticker": "KOO"}
    assert warning.template.replace("{ticker}", "KOO") == warning.message


def test_every_ticker_confirmed_gives_no_warning(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _seeded(isolated_cli_settings)
    _answers(monkeypatch, {"KO": None})

    assert _add(context, "KO").warnings == ()


def test_a_ticker_repeated_across_entries_is_looked_up_once_in_order_of_first_appearance(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _seeded(isolated_cli_settings)
    asked = _answers(monkeypatch, {"MSFT": None, "KO": None})
    other = MomentumSelection(short_window=2, long_window=4, rsi_period=14)

    add_watchlist_entries_checked(context, _REF, [("msft", _SELECTION), ("KO", _SELECTION), ("MSFT", other)])

    assert asked == ["MSFT", "KO"]


@pytest.mark.parametrize(
    ("kind", "code", "template"),
    [
        (ProviderFailureKind.UNREACHABLE, FailureReasonCode.PROVIDER_UNREACHABLE, _UNREACHABLE),
        (ProviderFailureKind.RATE_LIMITED, FailureReasonCode.PROVIDER_RATE_LIMITED, _RATE_LIMITED),
    ],
)
def test_no_provider_is_asked_after_the_first_network_failure_and_every_ticker_gets_its_message(
    isolated_cli_settings: ProjectSettings,
    monkeypatch: pytest.MonkeyPatch,
    kind: ProviderFailureKind,
    code: FailureReasonCode,
    template: str,
) -> None:
    context = _seeded(isolated_cli_settings)
    asked = _answers(monkeypatch, {"KO": None, "MSFT": _fetch(kind), "AAPL": None, "PG": None})

    added = _add(context, "KO", "MSFT", "AAPL", "PG")

    assert asked == ["KO", "MSFT"]
    assert [(item.ticker, item.code, item.reason_code, item.message) for item in added.warnings] == [
        (ticker, EntryWarningCode.TICKER_NOT_CHECKED, code, template.format(ticker=ticker))
        for ticker in ("MSFT", "AAPL", "PG")
    ]
    assert _tickers(context) == ["KO", "MSFT", "AAPL", "PG"]


@pytest.mark.parametrize("kind", [ProviderFailureKind.UNEXPECTED_RESPONSE, None])
def test_an_unexpected_answer_or_an_unclassified_failure_does_not_stop_the_check(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch, kind: ProviderFailureKind | None
) -> None:
    context = _seeded(isolated_cli_settings)
    asked = _answers(monkeypatch, {"KO": _fetch(kind), "MSFT": _fetch(ProviderFailureKind.NO_DATA), "PG": None})

    added = _add(context, "KO", "MSFT", "PG")

    expected = FailureReasonCode.PROVIDER_ERROR if kind is None else FailureReasonCode.PROVIDER_UNEXPECTED_RESPONSE
    assert asked == ["KO", "MSFT", "PG"]
    assert [(item.ticker, item.code, item.reason_code) for item in added.warnings] == [
        ("KO", EntryWarningCode.TICKER_NOT_CHECKED, expected),
        ("MSFT", EntryWarningCode.TICKER_NOT_RECOGNIZED, None),
    ]
    assert added.warnings[0].message == _UNEXPECTED.format(ticker="KO")


def _readiness(reason: DatabaseReason) -> BaseException:
    return DatabaseError(reason, None)


@pytest.mark.parametrize(
    ("raised", "code"),
    [
        (lambda: _readiness(DatabaseReason.BUSY), FailureReasonCode.DATABASE_BUSY),
        (lambda: _readiness(DatabaseReason.UPGRADE_REQUIRED), FailureReasonCode.DATABASE_UPGRADE_REQUIRED),
    ],
    ids=["readiness-busy", "readiness-upgrade"],
)
def test_a_database_error_on_the_first_lookup_stops_the_check_and_the_add_still_succeeds(
    isolated_cli_settings: ProjectSettings,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    raised: Callable[[], BaseException],
    code: FailureReasonCode,
) -> None:
    context = _seeded(isolated_cli_settings)
    asked = _answers(monkeypatch, {"KO": raised(), "MSFT": None, "PG": None})

    with caplog.at_level(logging.ERROR):
        added = _add(context, "KO", "MSFT", "PG")

    assert asked == ["KO"]
    assert [(item.ticker, item.code, item.reason_code, item.message) for item in added.warnings] == [
        (ticker, EntryWarningCode.TICKER_NOT_CHECKED, code, _DATABASE.format(ticker=ticker))
        for ticker in ("KO", "MSFT", "PG")
    ]
    assert _tickers(context) == ["KO", "MSFT", "PG"]
    assert [entry.ticker for entry in added.watchlist.entries] == ["KO", "MSFT", "PG"]
    assert any(record.exc_info is not None for record in caplog.records)


def test_any_other_exception_propagates(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _seeded(isolated_cli_settings)
    _answers(monkeypatch, {"KO": RuntimeError("defect")})

    with pytest.raises(RuntimeError, match="defect"):
        _add(context, "KO")


def test_a_sqlite_error_that_is_not_a_storage_error_propagates(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _seeded(isolated_cli_settings)
    defect = sqlite3.OperationalError("near SELEKT: syntax error")
    defect.sqlite_errorcode = sqlite3.SQLITE_ERROR
    _answers(monkeypatch, {"KO": defect})

    with pytest.raises(sqlite3.OperationalError, match="syntax"):
        _add(context, "KO")


def test_a_fresh_stored_profile_answers_with_no_provider_call(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = profile_context(isolated_cli_settings)
    create_watchlist(context, "Core")
    store_profile(context, refreshed_at=datetime.now(UTC))
    sec = FakeSec(failure=ProviderFailureKind.UNREACHABLE)
    use_providers(monkeypatch, sec, FakeYahoo(failure=ProviderFailureKind.UNREACHABLE))
    monkeypatch.setattr(entry_check, "lookup_instrument_profile", lookup_instrument_profile)

    added = _add(context, "KO")

    assert (added.warnings, sec.calls) == ((), 0)


def test_with_no_sec_identity_yahoo_alone_is_asked(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = profile_context(isolated_cli_settings, sec_identity=False)
    create_watchlist(context, "Core")
    yahoo = FakeYahoo(identity=False)
    use_yahoo_only(monkeypatch, yahoo)
    monkeypatch.setattr(entry_check, "lookup_instrument_profile", lookup_instrument_profile)

    added = _add(context, "ZZZZ")

    assert yahoo.calls > 0
    assert [(item.ticker, item.code) for item in added.warnings] == [("ZZZZ", EntryWarningCode.TICKER_NOT_RECOGNIZED)]
    assert _tickers(context) == ["ZZZZ"]


def test_a_provider_that_identifies_nothing_through_the_real_lookup_is_not_recognized(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = profile_context(isolated_cli_settings)
    create_watchlist(context, "Core")
    use_providers(monkeypatch, FakeSec(identity=False), FakeYahoo(identity=False))
    monkeypatch.setattr(entry_check, "lookup_instrument_profile", lookup_instrument_profile)

    added = _add(context, "ZZZZ")

    assert [(item.code, item.reason_code) for item in added.warnings] == [
        (EntryWarningCode.TICKER_NOT_RECOGNIZED, None)
    ]


def test_refusals_happen_before_any_lookup(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _seeded(isolated_cli_settings)
    asked = _answers(monkeypatch, {"KO": None, "MSFT": None})
    _add(context, "KO")
    asked.clear()

    with pytest.raises(ActionParameterError):  # a repeat of a stored entry
        _add(context, "MSFT", "ko")
    with pytest.raises(ActionParameterError):  # a repeat within the request
        _add(context, "MSFT", "msft")
    with pytest.raises(ActionParameterError):  # a blank ticker
        _add(context, "MSFT", " ")
    with pytest.raises(ActionParameterError):  # no entries
        add_watchlist_entries_checked(context, _REF, [])

    assert asked == []
    assert _tickers(context) == ["KO"]


def test_an_unknown_watchlist_and_an_unready_database_are_refused_before_any_lookup(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    from investment_analysis_engine.workspace.watchlists import WatchlistNotFoundError  # noqa: PLC0415

    context = _seeded(isolated_cli_settings)
    asked = _answers(monkeypatch, {"KO": None})

    with pytest.raises(WatchlistNotFoundError):
        add_watchlist_entries_checked(context, WatchlistName("Nowhere"), [("KO", _SELECTION)])
    unready = ApplicationContext(
        settings=ProjectSettings(database_url=unready_database_url(tmp_path_factory.mktemp("unready")))
    )
    with pytest.raises(DatabaseError):
        add_watchlist_entries_checked(unready, _REF, [("KO", _SELECTION)])

    assert asked == []


def test_a_raw_storage_error_is_no_longer_classified_here_and_propagates(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _seeded(isolated_cli_settings)
    _answers(monkeypatch, {"KO": OSError("raw")})

    with pytest.raises(OSError, match="raw"):
        _add(context, "KO")


_SEC_MESSAGE = (
    "{ticker} is not in SEC EDGAR's ticker list, so {strategies} will be unavailable for it: they read the company's "
    "financial statements from SEC filings. SEC EDGAR lists a company only under its US ticker symbol, so a ticker on "
    "an exchange outside the United States is not in the list even when the company files with the SEC."
)
_GRAHAM = GrahamNumberSelection()
_GRAHAM_OVERRIDDEN = GrahamNumberSelection(eps_override=5.0, bvps_override=30.0)
_PIOTROSKI = PiotroskiSelection()


class _FakeSecList:
    """Stands in for the SEC adapter: it lists the given tickers, or fails when asked about one in ``failing``."""

    def __init__(self, listed: set[str], failing: set[str] | None = None) -> None:
        self.listed = listed
        self.failing = failing or set()
        self.asked: list[str] = []

    def lists_ticker(self, ticker: str) -> bool:
        self.asked.append(ticker)
        if ticker in self.failing:
            raise FinancialProviderError("down", kind=ProviderFailureKind.UNREACHABLE, provider_id="sec_edgar")
        return ticker in self.listed


def _with_sec(monkeypatch: pytest.MonkeyPatch, sec: _FakeSecList | None) -> None:
    def build(_context: ApplicationContext) -> _FakeSecList:
        if sec is None:
            raise AnalysisConfigurationError("SEC EDGAR access is not configured.")
        return sec

    monkeypatch.setattr(entry_check, "build_sec_edgar_adapter", build)


def _add_selections(context: ApplicationContext, *entries: tuple[str, AnalysisSelection]) -> AddedEntries:
    return add_watchlist_entries_checked(context, _REF, list(entries))


def test_an_unlisted_ticker_with_one_sec_strategy_gets_the_warning_and_the_entry_is_added(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _seeded(isolated_cli_settings)
    _answers(monkeypatch, {"NTR.TO": None})
    _with_sec(monkeypatch, _FakeSecList(set()))

    added = _add_selections(context, ("ntr.to", _GRAHAM))

    assert _tickers(context) == ["NTR.TO"]
    (warning,) = added.warnings
    assert (warning.ticker, warning.code, warning.reason_code) == (
        "NTR.TO",
        EntryWarningCode.TICKER_NOT_IN_SEC_LIST,
        None,
    )
    assert warning.arguments == {"ticker": "NTR.TO", "strategies": "Graham Number"}
    assert warning.message == _SEC_MESSAGE.format(ticker="NTR.TO", strategies="Graham Number")
    assert warning.template.replace("{ticker}", "NTR.TO").replace("{strategies}", "Graham Number") == warning.message


def test_several_sec_strategies_are_named_once_each_in_order_of_first_appearance(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _seeded(isolated_cli_settings)
    _answers(monkeypatch, {"NTR.TO": None})
    sec = _FakeSecList(set())
    _with_sec(monkeypatch, sec)

    added = _add_selections(context, ("NTR.TO", _PIOTROSKI), ("NTR.TO", _SELECTION), ("NTR.TO", _GRAHAM))

    (warning,) = added.warnings
    assert warning.arguments["strategies"] == "Piotroski F-Score and Graham Number"
    assert sec.asked == ["NTR.TO"]


def test_three_strategies_are_joined_with_commas_and_and() -> None:
    assert join_labels(["A"]) == "A"
    assert join_labels(["A", "B"]) == "A and B"
    assert join_labels(["A", "B", "C"]) == "A, B and C"


@pytest.mark.parametrize(
    "selection", [_SELECTION, _GRAHAM_OVERRIDDEN], ids=["momentum-only", "graham-with-every-filing-input-overridden"]
)
def test_an_entry_that_reads_no_sec_filing_gives_no_warning_and_does_not_ask_sec(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch, selection: AnalysisSelection
) -> None:
    context = _seeded(isolated_cli_settings)
    _answers(monkeypatch, {"NTR.TO": None})
    sec = _FakeSecList(set())
    _with_sec(monkeypatch, sec)

    assert _add_selections(context, ("NTR.TO", selection)).warnings == ()
    assert sec.asked == []


def test_a_listed_or_overridden_ticker_gives_no_warning(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _seeded(isolated_cli_settings)
    _answers(monkeypatch, {"MSFT": None, "BRK.B": None})
    _with_sec(monkeypatch, _FakeSecList({"MSFT", "BRK.B"}))

    assert _add_selections(context, ("MSFT", _GRAHAM), ("BRK.B", _PIOTROSKI)).warnings == ()


def test_without_an_sec_identity_there_is_no_new_warning(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _seeded(isolated_cli_settings)
    _answers(monkeypatch, {"NTR.TO": None})
    _with_sec(monkeypatch, None)

    assert _add_selections(context, ("NTR.TO", _GRAHAM)).warnings == ()


def test_a_failure_asking_sec_gives_no_warning_logs_the_traceback_and_does_not_stop_the_check(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    context = _seeded(isolated_cli_settings)
    _answers(monkeypatch, {"A": None, "NTR.TO": None})
    _with_sec(monkeypatch, _FakeSecList(set(), failing={"A"}))

    with caplog.at_level(logging.WARNING, logger=entry_check.logger.name):
        added = _add_selections(context, ("A", _GRAHAM), ("NTR.TO", _GRAHAM))

    assert [item.ticker for item in added.warnings] == ["NTR.TO"]
    assert any(record.exc_info is not None and "A" in record.getMessage() for record in caplog.records)


def test_an_unrecognized_ticker_gets_only_its_own_warning(
    isolated_cli_settings: ProjectSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _seeded(isolated_cli_settings)
    _answers(monkeypatch, {"KOO": _fetch(ProviderFailureKind.NO_DATA)})
    sec = _FakeSecList(set())
    _with_sec(monkeypatch, sec)

    added = _add_selections(context, ("KOO", _GRAHAM))

    assert [item.code for item in added.warnings] == [EntryWarningCode.TICKER_NOT_RECOGNIZED]
    assert sec.asked == []
