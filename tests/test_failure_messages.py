"""One failure message rule: the same exception gives the same code and message from a direct command and from refresh.

``ROWS`` is the failure table of the SWC plan (B.17) written out as literals: each row names the exception, the step
that raises it, and the code and message the rule gives it. Every refresh path that reaches a row and every direct
command that has a counterpart are run through the real command line against a disposable database; nothing reaches a
service. The detail of a fixed message is in the log with its traceback.
"""

import json
import logging
import re
from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest
from alembic.config import Config
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import OperationalError
from typer.testing import CliRunner, Result

import investment_analysis_engine.cli_workspace
from alembic import command
from investment_analysis_engine.cli import app
from investment_analysis_engine.cli_strategy_wiring import CLI_BUILDERS
from investment_analysis_engine.cli_support import (
    InternalDefectError,
    describe_failure,
    require_job_ticker,
    stored_configuration,
)
from investment_analysis_engine.cli_watchlist_flags import WatchlistFlags
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.config import settings as real_settings
from investment_analysis_engine.core.failure_classification import classify_failure
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.core.operator_errors import AnalysisConfigurationError
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind
from investment_analysis_engine.core.repository_root import PACKAGE_ROOT, REPOSITORY_ROOT
from investment_analysis_engine.core.strategy_errors import undeclared
from investment_analysis_engine.data.base_client import DataFetchError
from investment_analysis_engine.data.financial.facts import FinancialProviderError
from investment_analysis_engine.data.market_data import NoEligibleObservationsError
from investment_analysis_engine.data.repositories.readiness import DatabaseReadinessError, ReadinessReason
from investment_analysis_engine.workspace.codecs import InvalidStoredRunError
from investment_analysis_engine.workspace.repositories.analysis_runs import (
    AnalysisRunConflictError,
    SQLiteAnalysisRunRepository,
)
from tests._cli_helpers import isolated_cli_database, normalize_cli_output, stub_yahoo_identity_metadata  # noqa: F401
from tests._direct_command_output import _COMMANDS, enter_fixture_providers
from tests._failure_code_table import _historical_quality_error
from tests.test_cli_refresh import _create_momentum_only, _mock_momentum_run

runner = CliRunner()

RAISED = "as raised"
SAVE = "{t} was analyzed, but the result could not be saved."
INVALID = "Unable to analyze {t}: invalid analysis inputs or provider data."
UNEXPECTED = "Unable to analyze {t}: the analysis failed unexpectedly."
Step = Literal["executor", "spec", "save"]


class _Model(BaseModel):
    number: int


def _validation_error() -> ValidationError:
    try:
        _Model(number="not a number")  # type: ignore[arg-type]
    except ValidationError as exc:
        return exc
    raise AssertionError("the model accepted a bad value")


@dataclass(frozen=True)
class Row:
    """One row of the failure table: the exception, where it is raised and what the rule gives it."""

    number: str
    build: Callable[[], BaseException]
    step: Step
    code: str
    message: str
    direct: bool = True

    def expected(self, exception: BaseException, ticker: str) -> str:
        """Return the message the rule gives, with the ticker filled in."""
        return str(exception) if self.message == RAISED else self.message.format(t=ticker)


ROWS = (
    Row(
        "1",
        lambda: DataFetchError("raw yahoo text", kind=ProviderFailureKind.UNREACHABLE, provider_id="yfinance"),
        "executor",
        "provider_unreachable",
        "Unable to analyze {t}: yfinance did not serve the request.",
    ),
    Row(
        "2",
        lambda: DataFetchError("raw yahoo text"),
        "executor",
        "provider_error",
        "Unable to analyze {t}: a data provider failed; the failure was not classified.",
    ),
    Row(
        "3",
        lambda: FinancialProviderError("raw sec text", kind=ProviderFailureKind.RATE_LIMITED, provider_id="sec_edgar"),
        "executor",
        "provider_rate_limited",
        "Unable to analyze {t}: sec_edgar is limiting requests.",
    ),
    Row(
        "4",
        lambda: FinancialProviderError("raw sec text"),
        "executor",
        "provider_error",
        "Unable to analyze {t}: a data provider failed; the failure was not classified.",
    ),
    Row("5", _historical_quality_error, "executor", "historical_quality", RAISED),
    Row(
        "6",
        lambda: NoEligibleObservationsError("No eligible observations."),
        "executor",
        "no_eligible_observations",
        RAISED,
    ),
    Row(
        "7",
        lambda: AnalysisConfigurationError("SEC EDGAR access is not configured. Set SEC_USER_AGENT."),
        "executor",
        "configuration_error",
        RAISED,
    ),
    Row(
        "8",
        lambda: DatabaseReadinessError(ReadinessReason.BUSY, Path("x.sqlite3")),
        "executor",
        "database_busy",
        RAISED,
    ),
    Row(
        "9",
        lambda: InternalDefectError("A stored selection no longer converts to a configuration."),
        "executor",
        "execution_error",
        UNEXPECTED,
        direct=False,
    ),
    Row(
        "10",
        lambda: InternalDefectError("A refresh job has a blank ticker."),
        "executor",
        "execution_error",
        UNEXPECTED,
        direct=False,
    ),
    Row("11", lambda: ValueError("raw library text"), "executor", "invalid_input", INVALID),
    Row("11-save", _validation_error, "save", "invalid_input", SAVE),
    Row("12", lambda: RuntimeError("raw runtime text"), "executor", "execution_error", UNEXPECTED),
    Row(
        "13",
        lambda: undeclared("refresh executor", ("a", "b")),
        "executor",
        "execution_error",
        UNEXPECTED,
        direct=False,
    ),
    Row(
        "14",
        lambda: undeclared("run spec", ("a", "b")),
        "spec",
        "execution_error",
        UNEXPECTED,
        direct=False,
    ),
    Row("15", lambda: InvalidStoredRunError("Invalid Momentum evidence."), "save", "invalid_stored_run", SAVE),
    Row(
        "16",
        lambda: AnalysisRunConflictError("Analysis run X already exists."),
        "save",
        "execution_error",
        SAVE,
    ),
    Row(
        "17",
        lambda: OperationalError("INSERT INTO analysis_runs", {}, Exception("raw driver text")),
        "save",
        "execution_error",
        SAVE,
    ),
)
DIRECT_ROWS = tuple(row for row in ROWS if row.direct)
_LEAKS = re.compile(
    r"momentum|graham|fcf|input_value|validation error for|errors\.pydantic\.dev|insert into|select ", re.IGNORECASE
)


def _assert_clean(row: Row, message: str) -> None:
    """A fixed message names no strategy and carries no library or SQL text; an as-raised one is the application's."""
    if row.message != RAISED:
        assert not _LEAKS.search(message), message
    assert "raw " not in message


def _logged(caplog: pytest.LogCaptureFixture, exception: BaseException) -> bool:
    return any(
        record.exc_info is not None and record.exc_info[1] is exception and record.levelno >= logging.ERROR
        for record in caplog.records
    )


def _refresh(settings: ProjectSettings, row: Row, flags: list[str]) -> tuple[BaseException, dict[str, str | None], int]:
    """Run ``refresh`` once with the row's exception raised at its step; return the exception and the one job."""
    exception = row.build()
    _create_momentum_only(settings, "W", ["AAPL"])
    with ExitStack() as stack:
        if row.step == "executor" and row.number == "13":
            stack.enter_context(
                patch("investment_analysis_engine.cli_workspace.refresh_executor_for", side_effect=exception)
            )
        elif row.step == "executor":
            stack.enter_context(
                patch("investment_analysis_engine.cli_workspace._refresh_executor", side_effect=exception)
            )
        else:
            run = stack.enter_context(
                patch("investment_analysis_engine.strategies.momentum.execution.MomentumAnalyzer.run_analysis")
            )
            run.side_effect = lambda **kw: _mock_momentum_run(kw["ticker"])
            if row.step == "spec":
                stack.enter_context(patch.object(investment_analysis_engine.cli_workspace, "RUN_SPECS_BY_KEY", {}))
            else:
                stack.enter_context(patch.object(SQLiteAnalysisRunRepository, "insert", side_effect=exception))
        result = runner.invoke(app, ["refresh", "W", *flags, "--json", "--no-provider-check"])
    jobs = json.loads(result.stdout)["results"]
    assert len(jobs) == 1
    return exception, jobs[0], result.exit_code


_PATHS = {
    "no-save": ["--workers", "1", "--no-save"],
    "saved": ["--workers", "1"],
    "concurrent": ["--workers", "2"],
}


def _paths(row: Row) -> list[str]:
    return ["no-save", "saved", "concurrent"] if row.step == "executor" else ["saved", "concurrent"]


@pytest.mark.parametrize("row", ROWS, ids=[row.number for row in ROWS])
def test_refresh_gives_every_row_its_code_and_message(
    row: Row,
    caplog: pytest.LogCaptureFixture,
    isolated_cli_settings: ProjectSettings,
) -> None:
    for path in _paths(row):
        caplog.clear()
        exception, job, exit_code = _refresh(isolated_cli_settings, row, _PATHS[path])
        message = row.expected(exception, "AAPL")
        assert (job["reason_code"], job["error"]) == (row.code, message), path
        assert exit_code == 1
        _assert_clean(row, str(job["error"]))
        if row.step == "spec":  # the real lookup raises its own exception, of the row's type
            assert any(isinstance(record.exc_info and record.exc_info[1], type(exception)) for record in caplog.records)
        else:
            assert _logged(caplog, exception) is (row.message != RAISED), path
        runner.invoke(app, ["watchlist", "delete", "W", "--yes"])


_ANALYSIS_PATCHES: dict[str, Callable[[BaseException], AbstractContextManager[MagicMock]]] = {
    "momentum": lambda exc: patch("investment_analysis_engine.strategies.momentum.cli.run_momentum", side_effect=exc),
    "graham-number": lambda exc: patch(
        "investment_analysis_engine.strategies.graham_number.cli.execute_graham_number", side_effect=exc
    ),
    "graham-growth": lambda exc: patch(
        "investment_analysis_engine.strategies.graham_growth.cli.execute_graham_growth", side_effect=exc
    ),
    "fcf-growth": lambda exc: patch(
        "investment_analysis_engine.strategies.fcf_growth.cli.execute_fcf_growth", side_effect=exc
    ),
}


def _migrated(directory: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    url = f"sqlite:///{(directory / 'direct.sqlite3').as_posix()}"
    config = Config(str(REPOSITORY_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
    isolated = ProjectSettings(**(real_settings.model_dump() | {"database_url": url}))
    monkeypatch.setattr("investment_analysis_engine.cli_run_support.settings", isolated)
    monkeypatch.setattr("investment_analysis_engine.cli_support.settings", isolated)


def _direct(
    row: Row, alias: str, mode: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[BaseException, Result]:
    """Run one direct command with the row's exception raised at its step; return the exception and the result."""
    exception = row.build()
    with ExitStack() as stack:
        enter_fixture_providers(stack, alias)
        if row.step == "save":
            _migrated(tmp_path, monkeypatch)
            stack.enter_context(patch.object(SQLiteAnalysisRunRepository, "insert", side_effect=exception))
            arguments = [*_COMMANDS[alias], "--save-run"]
        else:
            stack.enter_context(_ANALYSIS_PATCHES[alias](exception))
            arguments = list(_COMMANDS[alias])
        result = runner.invoke(app, [*arguments, *mode, "--no-provider-check"])
    return exception, result


@pytest.mark.parametrize("alias", list(_COMMANDS))
@pytest.mark.parametrize("row", DIRECT_ROWS, ids=[row.number for row in DIRECT_ROWS])
def test_every_direct_command_gives_every_counterpart_row_its_code_and_message(
    row: Row, alias: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    ticker = _COMMANDS[alias][1]
    (tmp_path / "json").mkdir()
    (tmp_path / "text").mkdir()
    exception, as_json = _direct(row, alias, ["--json"], tmp_path / "json", monkeypatch)
    message = row.expected(exception, ticker)
    document = json.loads(as_json.stdout)
    assert as_json.exit_code == 1
    assert (document["reason_code"], document["reason"]) == (row.code, message)
    assert _logged(caplog, exception) is (row.message != RAISED)
    _assert_clean(row, document["reason"])
    caplog.clear()
    exception, as_text = _direct(row, alias, [], tmp_path / "text", monkeypatch)
    assert as_text.exit_code == 1
    assert normalize_cli_output(as_text.stderr).endswith(normalize_cli_output(message))


@pytest.mark.parametrize("alias", ["graham-number", "graham-growth"])
@pytest.mark.parametrize(
    ("build", "code", "message"),
    [
        (
            lambda: AnalysisConfigurationError("SEC EDGAR access is not configured. Set SEC_USER_AGENT."),
            "configuration_error",
            RAISED,
        ),
        (lambda: ValueError("raw library text"), "invalid_input", INVALID),
    ],
    ids=["configuration", "value"],
)
def test_the_graham_resolver_build_gives_the_same_code_and_message(
    alias: str, build: Callable[[], BaseException], code: str, message: str
) -> None:
    module = alias.replace("-", "_")
    exception = build()
    with ExitStack() as stack:
        enter_fixture_providers(stack, alias)
        stack.enter_context(
            patch(f"investment_analysis_engine.strategies.{module}.cli.build_graham_resolver", side_effect=exception)
        )
        result = runner.invoke(app, [*_COMMANDS[alias], "--json", "--no-provider-check"])
    document = json.loads(result.stdout)
    expected = str(exception) if message == RAISED else message.format(t=_COMMANDS[alias][1])
    assert (document["reason_code"], document["reason"]) == (code, expected)


@pytest.mark.parametrize("row", [row for row in DIRECT_ROWS if row.step != "save"], ids=lambda row: row.number)
def test_the_same_exception_gives_the_same_code_and_message_from_a_direct_command_and_a_refresh_job(
    row: Row,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    isolated_cli_settings: ProjectSettings,
) -> None:
    exception, job, _ = _refresh(isolated_cli_settings, row, _PATHS["saved"])
    direct_exception, result = _direct(row, "momentum", ["--json"], tmp_path, monkeypatch)
    document = json.loads(result.stdout)
    assert (document["reason_code"], document["reason"].replace("AAPL", "BTC-USD")) == (
        job["reason_code"],
        str(job["error"]).replace("AAPL", "BTC-USD"),
    )
    assert type(exception) is type(direct_exception)


@pytest.mark.parametrize("row", ROWS, ids=[row.number for row in ROWS])
def test_describe_failure_gives_every_row_its_code_and_message_without_raising(
    row: Row, caplog: pytest.LogCaptureFixture
) -> None:
    exception = row.build()
    saving = row.step == "save"
    description = describe_failure(exception, "KO", saving=saving)
    assert (description.code.value, description.message) == (row.code, row.expected(exception, "KO"))
    assert _logged(caplog, exception) is (row.message != RAISED)
    _assert_clean(row, description.message)


def test_a_missing_ticker_is_spelled_as_the_requested_instrument() -> None:
    assert describe_failure(RuntimeError("x"), None, saving=False).message == (
        "Unable to analyze the requested instrument: the analysis failed unexpectedly."
    )
    assert describe_failure(RuntimeError("x"), None, saving=True).message == (
        "The requested instrument was analyzed, but the result could not be saved."
    )


def test_a_code_without_a_message_is_reported_as_an_unexpected_failure() -> None:
    description = describe_failure(InvalidStoredRunError("x"), "KO", saving=False)
    assert (description.code, description.message) == (FailureReasonCode.EXECUTION_ERROR, UNEXPECTED.format(t="KO"))


def test_the_defects_declare_their_code_and_the_classifier_names_no_exception_type() -> None:
    assert classify_failure(InternalDefectError("x")).reason_code is FailureReasonCode.EXECUTION_ERROR
    assert classify_failure(AnalysisRunConflictError("x")).reason_code is FailureReasonCode.EXECUTION_ERROR
    source = (PACKAGE_ROOT / "core" / "failure_classification.py").read_text(encoding="utf-8")
    for name in ("InternalDefectError", "AnalysisRunConflictError", "ValidationError"):
        assert name not in source


def test_a_stored_selection_that_does_not_convert_and_a_blank_ticker_are_defects() -> None:
    with pytest.raises(InternalDefectError) as converted:
        stored_configuration(_raise_validation_error)
    assert isinstance(converted.value.__cause__, ValidationError)
    with pytest.raises(InternalDefectError):
        require_job_ticker("  ")
    assert require_job_ticker("KO") == "KO"
    assert stored_configuration(lambda: 3) == 3


def _raise_validation_error() -> int:
    raise _validation_error()


@pytest.mark.parametrize(
    ("alias", "patch_conversion"),
    [
        (
            "graham-number",
            lambda exc: patch(
                "investment_analysis_engine.strategies.graham_number.selection.GrahamNumberSelection.to_graham_number_config",
                side_effect=exc,
            ),
        ),
        (
            "graham-growth",
            lambda exc: patch(
                "investment_analysis_engine.strategies.graham_growth.selection.GrahamGrowthSelection.to_graham_growth_config",
                side_effect=exc,
            ),
        ),
        (
            "fcf-growth",
            lambda exc: patch(
                "investment_analysis_engine.strategies.fcf_growth.selection.FCFGrowthSelection.to_fcf_config",
                side_effect=exc,
            ),
        ),
    ],
)
def test_a_stored_selection_that_does_not_convert_is_an_execution_error_from_the_real_executor(
    alias: str, patch_conversion: Callable[[BaseException], AbstractContextManager[MagicMock]]
) -> None:
    flags = WatchlistFlags(
        short_window=20,
        long_window=50,
        rsi_period=14,
        as_of=None,
        data_provider=None,
        no_cache=True,
        eps=None,
        eps_basis=None,
        bvps=None,
        current_price=None,
        expected_growth=5.0,
        aaa_yield=4.5,
        growth_years=None,
        forward_policy="display-only",
        classification_basis="total-fcf",
        currency="USD",
    )
    selection = CLI_BUILDERS[alias](flags)
    with patch_conversion(_validation_error()), pytest.raises(InternalDefectError) as caught:
        investment_analysis_engine.cli_workspace._refresh_executor("KO", selection, profile_cache=MagicMock())
    assert classify_failure(caught.value).reason_code is FailureReasonCode.EXECUTION_ERROR
