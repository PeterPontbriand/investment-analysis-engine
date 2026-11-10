"""Direct analysis: the one operation every direct command calls, over each declared strategy.

Each test runs the operation against the deterministic fixtures of the direct-command tests, so no test reaches a
provider. The expected text of every mode was recorded from the direct commands before the operation existed
(``tests/expected_output/analysis_text/`` for the three text modes and ``tests/expected_output/direct_commands/`` for
``--json``), so the operation is compared with what the commands printed, not with itself.
"""

import ast
import dataclasses
import inspect
import json
import re
from contextlib import ExitStack
from datetime import UTC, datetime
from typing import Literal, get_args, get_type_hints
from unittest.mock import patch
from uuid import UUID

import pytest
from pydantic import BaseModel
from typer.testing import CliRunner

from investment_analysis_engine.analysis.run_models import RunOutcome
from investment_analysis_engine.application.analysis import AnalysisOutcome, analyze, exit_code_of
from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.application.parameters import ActionParameterError
from investment_analysis_engine.application.runs import replay_run_document
from investment_analysis_engine.application.strategy_run import StrategyRun
from investment_analysis_engine.cli import app
from investment_analysis_engine.config import ProjectSettings
from investment_analysis_engine.core.analysis_status import CalculationStatus
from investment_analysis_engine.core.failure_classification import provider_failure_of
from investment_analysis_engine.core.package_root import PACKAGE_ROOT
from investment_analysis_engine.core.provider_check_element import ProviderCheckVerdict
from investment_analysis_engine.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from investment_analysis_engine.data.provider_probe import ProbeFinding, ProbeVerdict
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.evaluation.fixtures.graham import SECURITY_ID
from investment_analysis_engine.reporting.documents.strategy_document import strategy_document_json
from investment_analysis_engine.reporting.presentation import PresentationMode
from investment_analysis_engine.reporting.replay_inputs import TextPresentationMode
from investment_analysis_engine.strategies.fcf_growth.selection import FCFGrowthSelection
from investment_analysis_engine.strategies.graham_growth.selection import GrahamGrowthSelection
from investment_analysis_engine.strategies.graham_number.selection import GrahamNumberSelection
from investment_analysis_engine.strategies.momentum.selection import MomentumSelection
from investment_analysis_engine.strategies.piotroski.selection import PiotroskiSelection
from investment_analysis_engine.strategy_wiring import STRATEGIES
from investment_analysis_engine.workspace.capture import ExecutionCapture
from investment_analysis_engine.workspace.repositories.analysis_runs import SQLiteAnalysisRunRepository
from investment_analysis_engine.workspace.runs import RunQuery
from investment_analysis_engine.workspace.strategy_types import SelectionMember
from scripts.repository_root import REPOSITORY_ROOT
from tests._direct_command_output import _COMMANDS, enter_fixture_providers, normalize
from tests._probe_injection import injected_probe
from tests._strategy_document_output import CASES, Case, _enter_providers, without_excluded_keys
from tests.workspace.test_execution import _momentum_native_evidence

pytestmark = pytest.mark.usefixtures("stub_yahoo_identity_metadata")

_EXPECTED_TEXT = REPOSITORY_ROOT / "tests" / "expected_output" / "analysis_text"
_EXPECTED_DIRECT = REPOSITORY_ROOT / "tests" / "expected_output" / "direct_commands"
_TEXT_MODES: tuple[TextPresentationMode, ...] = get_args(TextPresentationMode.__value__)
_MODE_NAMES = {
    PresentationMode.CONCISE: "concise",
    PresentationMode.DETAILS: "details",
    PresentationMode.DIAGNOSTICS: "diagnostics",
}

_TICKERS = {"momentum": "BTC-USD", "graham-number": SECURITY_ID, "graham-growth": SECURITY_ID}
_GRAHAM_AS_OF = datetime(2025, 7, 1, 23, 59, 59, 999999, tzinfo=UTC)
"""The run date the Graham commands are pinned to, as the direct-command harness does with ``--as-of``."""
_SELECTIONS: dict[str, SelectionMember] = {
    "momentum": MomentumSelection(short_window=2, long_window=3, rsi_period=3, use_cache=False),
    "graham-number": GrahamNumberSelection(use_cache=False, as_of=_GRAHAM_AS_OF),
    "graham-growth": GrahamGrowthSelection(
        expected_growth=5.0, aaa_yield_override=4.5, use_cache=False, as_of=_GRAHAM_AS_OF
    ),
    "fcf-growth": FCFGrowthSelection(use_cache=False),
    "piotroski": PiotroskiSelection(use_cache=False, as_of=datetime(2025, 1, 15, 23, 59, 59, 999999, tzinfo=UTC)),
}


def _ticker(alias: str) -> str:
    """Return the ticker the direct command of ``alias`` is recorded with."""
    return _TICKERS.get(alias) or _COMMANDS[alias][1]


def _strategy_ids() -> list[str]:
    return [item.alias for item in STRATEGIES]


class _Probe:
    """A probe that finds every provider unreachable and records what it was asked."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def check(self, provider_id: str, *, requested: bool = True) -> ProbeFinding:
        self.calls.append((provider_id, requested))
        if not requested:
            return ProbeFinding(provider_id, ProbeVerdict.NOT_CHECKED, switched_off=True)
        return ProbeFinding(provider_id, ProbeVerdict.UNREACHABLE)


@pytest.fixture
def context(isolated_cli_settings: ProjectSettings) -> ApplicationContext:
    return ApplicationContext(settings=isolated_cli_settings)


def _stored_run_count(settings: ProjectSettings) -> int:
    database = SQLiteDatabase(settings)
    try:
        return len(SQLiteAnalysisRunRepository(database).list(RunQuery()).summaries)
    finally:
        database.close()


def _run(
    context: ApplicationContext, alias: str, *, save: bool = False, provider_check: bool = True
) -> AnalysisOutcome:
    with ExitStack() as stack:
        enter_fixture_providers(stack, alias)
        return analyze(context, _ticker(alias), _SELECTIONS[alias], save=save, provider_check=provider_check)


# The only text lines that hold the run's own reading of now: Momentum's details and diagnostics print the moment the
# analysis ran and, with no cache, the moment the data was retrieved. Every other time in the text, the as-of and the
# effective times among them, is compared exactly.
_WALL_CLOCK_LINES = re.compile(rb"^(Analysis timestamp|Originally retrieved): .*$", re.MULTILINE)


def _as_written(text: str) -> bytes:
    """Return text as a command writes it to a file: the text, a newline, and the suite's line-ending normalization."""
    return normalize(f"{text}\n".encode())


def _without_wall_clock(written: bytes) -> bytes:
    """Replace the value on each labelled wall-clock line with a marker; nothing else is masked."""
    return _WALL_CLOCK_LINES.sub(rb"\1: <wall-clock>", written)


@pytest.mark.parametrize("alias", _strategy_ids())
def test_an_unsaved_analysis_has_no_run_id_and_stores_no_run(alias: str, context: ApplicationContext) -> None:
    outcome = _run(context, alias)

    assert outcome.analysis_run_id is None
    assert outcome.outcome is RunOutcome.COMPLETED
    assert _stored_run_count(context.settings) == 0


@pytest.mark.parametrize("alias", _strategy_ids())
def test_a_saved_analysis_returns_the_run_id_and_the_stored_run_replays_to_the_same_document(
    alias: str, context: ApplicationContext
) -> None:
    outcome = _run(context, alias, save=True)

    assert isinstance(outcome.analysis_run_id, UUID)
    assert _stored_run_count(context.settings) == 1
    replayed = replay_run_document(context, outcome.analysis_run_id)
    direct = strategy_document_json(outcome.document).encode()
    assert without_excluded_keys(normalize(strategy_document_json(replayed).encode())) == without_excluded_keys(
        normalize(direct)
    )


@pytest.mark.parametrize("mode", _TEXT_MODES, ids=lambda mode: _MODE_NAMES[mode])
@pytest.mark.parametrize("alias", _strategy_ids())
def test_each_text_mode_is_byte_for_byte_what_the_direct_command_printed_before(
    alias: str, mode: TextPresentationMode, context: ApplicationContext
) -> None:
    outcome = _run(context, alias)

    recorded = (_EXPECTED_TEXT / f"{alias}.{_MODE_NAMES[mode]}.txt").read_bytes()
    assert _without_wall_clock(_as_written(outcome.render_text(mode))) == _without_wall_clock(recorded)


@pytest.mark.parametrize("alias", _strategy_ids())
def test_the_document_is_what_json_wrote_before(alias: str, context: ApplicationContext) -> None:
    outcome = _run(context, alias)

    expected = (_EXPECTED_DIRECT / f"{alias}.json").read_bytes()
    assert _as_written(strategy_document_json(outcome.document)) == expected


@pytest.mark.parametrize("alias", _strategy_ids())
def test_the_outcome_gives_the_exit_code_the_command_gives(alias: str, context: ApplicationContext) -> None:
    outcome = _run(context, alias)

    with ExitStack() as stack:
        enter_fixture_providers(stack, alias)
        result = CliRunner().invoke(app, _COMMANDS[alias])
    assert exit_code_of(outcome.outcome) == result.exit_code == 0


@pytest.mark.parametrize("alias", _strategy_ids())
def test_the_as_of_reaches_the_document(alias: str, context: ApplicationContext) -> None:
    boundary = _SELECTIONS[alias].model_copy(update={"as_of": _as_of()})

    with ExitStack() as stack:
        enter_fixture_providers(stack, alias)
        outcome = analyze(context, _ticker(alias), boundary, save=False, provider_check=False)

    document = json.loads(strategy_document_json(outcome.document))
    assert document["requested_as_of"].startswith("2026-01-15T23:59:59.999999")
    assert "effective_as_of" in document


def _as_of() -> datetime:
    return datetime(2026, 1, 15, 23, 59, 59, 999999, tzinfo=UTC)


_FAILURE_CASES = {
    "momentum": "momentum-provider-error",
    "graham-number": "graham-number-provider-error",
    "graham-growth": "graham-growth-provider-error",
    "fcf-growth": "fcf-growth-provider-error",
}


def _failure_case(alias: str) -> Case:
    return next(case for case in CASES if case.name == _FAILURE_CASES[alias])


@pytest.fixture(params=sorted(_FAILURE_CASES))
def failing(request: pytest.FixtureRequest) -> tuple[str, Case]:
    return request.param, _failure_case(request.param)


def _analyze_failing(
    context: ApplicationContext, alias: str, case: Case, *, provider_check: bool, probe: _Probe
) -> AnalysisOutcome:
    selection = _SELECTIONS[alias]
    ticker = _failure_ticker(case, alias)
    with ExitStack() as stack:
        _enter_providers(stack, case)
        stack.enter_context(injected_probe(probe))
        return analyze(context, ticker, selection, save=False, provider_check=provider_check)


def _failure_ticker(case: Case, alias: str) -> str:
    """Return the ticker of the failing case's command line: its first argument after the command name."""
    return case.arguments[1] if alias != "momentum" else _ticker(alias)


def test_a_provider_failure_carries_the_check_in_the_document_and_the_text(
    failing: tuple[str, Case], context: ApplicationContext
) -> None:
    alias, case = failing
    probe = _Probe()

    outcome = _analyze_failing(context, alias, case, provider_check=True, probe=probe)

    assert exit_code_of(outcome.outcome) == 1
    assert [call[1] for call in probe.calls] == [True]
    element = json.loads(strategy_document_json(outcome.document))["provider_check"]
    assert [item["verdict"] for item in element] == [ProviderCheckVerdict.UNREACHABLE.value]
    first_line = outcome.render_text(PresentationMode.CONCISE).splitlines()[0]
    assert "is not answering: a test request also failed." in first_line


def test_a_provider_failure_with_the_check_turned_off_says_it_was_not_checked(
    failing: tuple[str, Case], context: ApplicationContext
) -> None:
    alias, case = failing
    probe = _Probe()

    outcome = _analyze_failing(context, alias, case, provider_check=False, probe=probe)

    assert [call[1] for call in probe.calls] == [False]
    element = json.loads(strategy_document_json(outcome.document))["provider_check"]
    assert [item["verdict"] for item in element] == [ProviderCheckVerdict.NOT_CHECKED.value]
    assert "(the provider check is turned off)" in outcome.render_text(PresentationMode.DETAILS).splitlines()[0]


def test_a_failure_with_the_check_switched_off_in_the_settings_says_so(
    failing: tuple[str, Case], context: ApplicationContext
) -> None:
    """The probe the operation builds from the settings contacts no provider when the setting is off."""
    alias, case = failing

    with ExitStack() as stack:
        _enter_providers(stack, case)
        outcome = analyze(context, _failure_ticker(case, alias), _SELECTIONS[alias], save=False, provider_check=True)

    element = json.loads(strategy_document_json(outcome.document))["provider_check"]
    assert [item["verdict"] for item in element] == [ProviderCheckVerdict.NOT_CHECKED.value]
    assert "(the provider check is turned off)" in outcome.render_text(PresentationMode.CONCISE).splitlines()[0]


def test_each_call_builds_its_own_probe_so_no_finding_carries_over(
    failing: tuple[str, Case], context: ApplicationContext
) -> None:
    alias, case = failing
    probes = [_Probe(), _Probe()]

    with ExitStack() as stack:
        _enter_providers(stack, case)
        build = stack.enter_context(
            patch("investment_analysis_engine.application.analysis.build_provider_probe", side_effect=probes)
        )
        for _ in range(2):
            analyze(context, _failure_ticker(case, alias), _SELECTIONS[alias], save=False, provider_check=True)

    assert build.call_count == 2
    assert [len(probe.calls) for probe in probes] == [1, 1]


def test_no_application_module_holds_a_module_level_probe() -> None:
    """A probe remembers its findings, so one that lived in a module would carry them from one operation to the next."""
    for path in sorted((PACKAGE_ROOT / "application").glob("*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign | ast.AnnAssign) and node.value is not None:
                called = {
                    call.func.id
                    for call in ast.walk(node.value)
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                }
                assert not called & {"ProviderProbe", "build_provider_probe"}, (path.name, node.lineno)


def test_a_completed_analysis_never_runs_the_check(context: ApplicationContext) -> None:
    probe = _Probe()

    with ExitStack() as stack:
        enter_fixture_providers(stack, "momentum")
        stack.enter_context(injected_probe(probe))
        outcome = analyze(context, _ticker("momentum"), _SELECTIONS["momentum"], save=False, provider_check=True)

    assert probe.calls == []
    assert json.loads(strategy_document_json(outcome.document))["provider_check"] is None


# ---------------------------------------------------------------------------
# The outcome carries no raw execution and no strategy-specific type.
# ---------------------------------------------------------------------------


def test_the_outcome_holds_only_a_model_a_run_id_an_outcome_and_a_renderer() -> None:
    """A field holding a raw execution or a strategy's type fails this test."""
    hints = get_type_hints(AnalysisOutcome)
    fields = {field.name for field in dataclasses.fields(AnalysisOutcome)}

    assert fields == {"document", "analysis_run_id", "outcome", "text_renderer"}
    assert hints["document"] is BaseModel
    assert hints["analysis_run_id"] == UUID | None
    assert hints["outcome"] is RunOutcome
    renderer = hints["text_renderer"]
    assert str(renderer).startswith("collections.abc.Callable[[")
    assert renderer.__args__[-1] is str
    forbidden = {ExecutionCapture, StrategyRun}
    assert not {hint for hint in hints.values() if hint in forbidden}
    for hint in hints.values():
        module = getattr(hint, "__module__", "")
        assert ".strategies." not in module, hint


def test_the_render_method_takes_a_text_mode_and_returns_text() -> None:
    signature = inspect.signature(AnalysisOutcome.render_text)

    assert list(signature.parameters) == ["self", "mode"]
    assert get_type_hints(AnalysisOutcome.render_text) == {"mode": TextPresentationMode, "return": str}


def test_no_direct_command_imports_a_strategy_presenter() -> None:
    """The commands call the operation; the presentation stays inside each strategy's application file."""
    commands = sorted((PACKAGE_ROOT / "strategies").glob("*/cli.py"))
    assert len(commands) >= len(STRATEGIES)
    for path in commands:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.endswith(".presenter"), (path.name, node.module)
            if isinstance(node, ast.Import):
                assert not any(alias.name.endswith(".presenter") for alias in node.names), path.name


# ---------------------------------------------------------------------------
# The operation's own rules, with a stand-in strategy.
# ---------------------------------------------------------------------------


class _Document(BaseModel):
    value: int = 1


def _stand_in(status: CalculationStatus, calls: list[object]) -> StrategyRun:
    failure = provider_failure_of((ProviderFailureRecord(ProviderFailureKind.UNREACHABLE, "yfinance"),))
    execution = ExecutionCapture(
        native_evidence=_momentum_native_evidence(), profile=None, native_status=status, provider_failure=failure
    )

    def document(element: object) -> BaseModel:
        calls.append(element)
        return _Document()

    return StrategyRun(execution=execution, document=document, render_text=lambda _element, _mode: "result")


@pytest.mark.parametrize(
    ("status", "exit_code", "check_runs"),
    [(CalculationStatus.OK, 0, False), (CalculationStatus.PROVIDER_ERROR, 1, True)],
)
def test_the_check_runs_only_after_a_failure(
    status: CalculationStatus, exit_code: int, check_runs: bool, context: ApplicationContext
) -> None:
    probe = _Probe()
    elements: list[object] = []

    def runner(*_arguments: object, **_keywords: object) -> StrategyRun:
        return _stand_in(status, elements)

    with (
        patch("investment_analysis_engine.application.analysis.analysis_runner_for", return_value=runner),
        injected_probe(probe),
    ):
        outcome = analyze(context, "KO", _SELECTIONS["piotroski"], save=False, provider_check=True)

    assert exit_code_of(outcome.outcome) == exit_code
    assert bool(probe.calls) is check_runs
    assert (elements[0] is not None) is check_runs
    assert (outcome.render_text(PresentationMode.CONCISE).splitlines()[-1]) == "result"
    assert len(outcome.render_text(PresentationMode.CONCISE).splitlines()) == (2 if check_runs else 1)


def test_the_literal_text_modes_are_the_three_text_modes() -> None:
    assert get_args(Literal[PresentationMode.CONCISE, PresentationMode.DETAILS, PresentationMode.DIAGNOSTICS]) == (
        _TEXT_MODES
    )


def test_an_analysis_failure_before_the_save_passes_through_unchanged(context: ApplicationContext) -> None:
    def runner(*_arguments: object, **_keywords: object) -> StrategyRun:
        raise ValueError("analysis failed")

    with (
        patch("investment_analysis_engine.application.analysis.analysis_runner_for", return_value=runner),
        pytest.raises(ValueError, match="analysis failed"),
    ):
        analyze(context, "KO", _SELECTIONS["piotroski"], save=False, provider_check=True)


def test_a_blank_ticker_is_rejected_before_any_database_or_provider_work(context: ApplicationContext) -> None:
    selection = _SELECTIONS["momentum"]
    with (
        patch("investment_analysis_engine.application.analysis.SQLiteDatabase") as database,
        patch("investment_analysis_engine.application.analysis.analysis_runner_for") as runner,
        pytest.raises(ActionParameterError) as caught,
    ):
        analyze(context, "  ", selection, save=True, provider_check=True)

    assert (str(caught.value), caught.value.parameters, caught.value.rule) == (
        "ticker must be a non-empty symbol.",
        ("ticker",),
        "analysis.blank_ticker",
    )
    database.assert_not_called()
    runner.assert_not_called()


def test_a_padded_lower_case_ticker_is_analyzed_as_its_normalized_form(context: ApplicationContext) -> None:
    ticker = _ticker("momentum")
    with ExitStack() as stack:
        enter_fixture_providers(stack, "momentum")
        outcome = analyze(context, f"  {ticker.lower()} ", _SELECTIONS["momentum"], save=False, provider_check=False)

    assert outcome.document.model_dump(mode="json")["ticker"] == ticker
