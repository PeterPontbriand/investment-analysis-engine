"""The automatic provider check in the text modes: the first line after a provider failure.

The finding in the ``--json`` documents is tested in ``tests/test_provider_check_element.py``.

The suite switches the check off through ``IAN_PROVIDER_CHECK`` (tests/conftest.py). A test of the check injects a
probe built over fake check bodies through the Typer context, so no test reaches a provider.
"""

# ruff: noqa: F811 - a test takes the imported autouse fixture by name to use its value.
import itertools
import json
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from typer.main import get_command
from typer.testing import CliRunner, Result

from src.cli import app
from src.cli_provider_check import ProviderCheckChoice, provider_check_findings
from src.config import ProjectSettings
from src.core.failure_classification import provider_failure_of
from src.core.provider_failure_element import ProviderFailure
from src.core.provider_failure_kind import ProviderFailureKind, ProviderFailureRecord
from src.data.base_client import DataFetchError
from src.data.provider_checks import CheckVerdict, ProviderCheckEntry, ProviderCheckResult, ProviderClients
from src.data.provider_probe import ProbeFinding, ProbeVerdict, ProviderProbe
from tests._cli_helpers import isolated_cli_database, normalize_cli_output, stub_yahoo_identity_metadata  # noqa: F401
from tests._strategy_document_output import CASES, _enter_providers

runner = CliRunner()


def _no_clients() -> ProviderClients:
    """Stand in for the provider clients; the fake check bodies never use them."""
    return cast(ProviderClients, object())


_FINDING_LINES = {
    CheckVerdict.UNREACHABLE: "Yahoo Finance is not answering: a test request also failed.",
    CheckVerdict.RATE_LIMITED: "Yahoo Finance is limiting requests: a test request was also refused.",
    CheckVerdict.UNEXPECTED_RESPONSE: "Yahoo Finance answered a test request in a form this application does not read.",
    CheckVerdict.NO_DATA: "Yahoo Finance returned no data for a known test ticker. It may be limiting requests.",
    CheckVerdict.OK: "Yahoo Finance answered a test request normally. The failure may be specific to this request.",
}
_SWITCHED_OFF = "Yahoo Finance was not checked (the provider check is turned off)."
_COULD_NOT_CHECK = "Yahoo Finance could not be checked."


def _result(provider_id: str, verdict: CheckVerdict) -> ProviderCheckResult:
    passed = verdict is CheckVerdict.OK
    kind = (
        None
        if verdict in (CheckVerdict.OK, CheckVerdict.NOT_CONFIGURED, CheckVerdict.FAILED)
        else ProviderFailureKind(verdict.value)
    )
    return ProviderCheckResult(
        provider_id, "a test probe", passed, 0.01, None if passed else "detail", kind,
        not_configured=verdict is CheckVerdict.NOT_CONFIGURED,
    )  # fmt: skip


@dataclass
class _Probe:
    """A real probe over fake check bodies that count their calls; nothing reaches a provider."""

    probe: ProviderProbe
    calls: list[str]


def _probe(verdicts: dict[str, CheckVerdict] | None = None, *, enabled: bool = True) -> _Probe:
    """Build a probe whose checks return the given verdicts; the default makes Yahoo and SEC healthy."""
    chosen = {"yfinance": CheckVerdict.OK, "sec_edgar": CheckVerdict.OK}
    chosen.update(verdicts or {})
    calls: list[str] = []

    def entry(provider_id: str) -> ProviderCheckEntry:
        def run(clients: ProviderClients, *, timeout_seconds: float | None = None) -> ProviderCheckResult:
            del clients, timeout_seconds
            calls.append(provider_id)
            return _result(provider_id, chosen[provider_id])

        return ProviderCheckEntry(provider_id=provider_id, probe="a test probe", run=run)

    probe = ProviderProbe(
        enabled=enabled,
        timeout_seconds=10.0,
        clients=_no_clients,
        checks=tuple(entry(provider_id) for provider_id in chosen),
    )
    return _Probe(probe, calls)


@dataclass(frozen=True)
class _Scenario:
    """One command made to fail on a provider, and the provider and stream its failure text uses."""

    command: str
    arguments: tuple[str, ...]
    provider_id: str


_SCENARIOS = {
    "momentum": _Scenario("momentum", ("momentum", "FCIM"), "yfinance"),
    "graham-number": _Scenario("graham-number", (), "sec_edgar"),
    "graham-growth": _Scenario("graham-growth", (), "sec_edgar"),
    "fcf-growth": _Scenario("fcf-growth", (), "sec_edgar"),
}
_CASE_OF = {
    "graham-number": "graham-number-provider-error",
    "graham-growth": "graham-growth-provider-error",
    "fcf-growth": "fcf-growth-provider-error",
}


@contextmanager
def _failing(
    command: str, *, kind: ProviderFailureKind | None = ProviderFailureKind.UNREACHABLE
) -> Iterator[list[str]]:
    """Make *command* fail on a provider with *kind* and yield its arguments.

    With no kind the failure is unclassified (it names no provider); only Momentum and Graham Number have such a
    case.
    """
    with ExitStack() as stack:
        if command == "momentum":
            stack.enter_context(
                patch(
                    "src.strategies.momentum.execution.MomentumAnalyzer.run_analysis",
                    side_effect=DataFetchError("library detail", kind=kind, provider_id="yfinance" if kind else None),
                )
            )
            yield ["momentum", "FCIM"]
            return
        name = _CASE_OF[command] if kind is not None else "graham-number-provider-error-unclassified"
        case = next(item for item in CASES if item.name == name)
        _enter_providers(stack, case)
        yield list(case.arguments)


def _invoke(arguments: list[str], probe: object | None, *extra: str) -> Result:
    return runner.invoke(app, [*arguments, *extra], obj=probe)


def _first_line_and_failure_stream(command: str, mode: str) -> str:
    """Return the stream (``stdout`` or ``stderr``) the command writes its failure text to in *mode*."""
    if command == "momentum":
        return "stderr"
    return "stderr" if mode in ("", "--details") else "stdout"


_MODES = ("", "--details", "--diagnostics")


@pytest.mark.parametrize("mode", _MODES, ids=["concise", "details", "diagnostics"])
@pytest.mark.parametrize("command", list(_SCENARIOS))
def test_the_first_line_is_written_to_the_stream_of_the_failure_text_immediately_before_it(
    command: str, mode: str
) -> None:
    scenario = _SCENARIOS[command]
    fake = _probe({scenario.provider_id: CheckVerdict.UNREACHABLE})
    display = {"yfinance": "Yahoo Finance", "sec_edgar": "SEC EDGAR"}[scenario.provider_id]

    with _failing(command) as arguments:
        result = _invoke(arguments, fake.probe, *([mode] if mode else []))

    assert result.exit_code == 1
    stream = _first_line_and_failure_stream(command, mode)
    written, other = (result.stderr, result.stdout) if stream == "stderr" else (result.stdout, result.stderr)
    assert written.startswith(f"{display} is not answering: a test request also failed.\n")
    failure_text = written.split("\n", 1)[1]
    assert failure_text.strip() != ""
    assert "not answering" not in failure_text
    assert other == ""
    assert fake.calls == [scenario.provider_id]


@pytest.mark.parametrize("verdict", list(_FINDING_LINES), ids=lambda verdict: verdict.value)
def test_each_verdict_has_its_first_line(verdict: CheckVerdict) -> None:
    fake = _probe({"yfinance": verdict})

    with _failing("momentum") as arguments:
        result = _invoke(arguments, fake.probe)

    assert result.exit_code == 1
    assert result.stderr.splitlines()[0] == _FINDING_LINES[verdict]
    assert result.stderr.splitlines()[1] == "Unable to analyze FCIM: yfinance did not serve the request."


@pytest.mark.parametrize(
    "verdict", [CheckVerdict.NOT_CONFIGURED, CheckVerdict.FAILED], ids=lambda verdict: verdict.value
)
def test_a_check_that_could_not_run_says_the_provider_could_not_be_checked(verdict: CheckVerdict) -> None:
    fake = _probe({"yfinance": verdict})

    with _failing("momentum") as arguments:
        result = _invoke(arguments, fake.probe)

    assert result.exit_code == 1
    assert result.stderr.splitlines()[0] == _COULD_NOT_CHECK


def test_a_timed_out_check_is_the_not_answering_line() -> None:
    """A timeout is an unreachable provider; the line makes no claim about a timeout."""

    def run(clients: ProviderClients, *, timeout_seconds: float | None = None) -> ProviderCheckResult:
        del clients
        assert timeout_seconds == 10.0
        return ProviderCheckResult(
            "yfinance", "a test probe", False, 10.0, "timed out after 10 s", ProviderFailureKind.UNREACHABLE
        )

    probe = ProviderProbe(
        enabled=True,
        timeout_seconds=10.0,
        clients=_no_clients,
        checks=(ProviderCheckEntry(provider_id="yfinance", probe="p", run=run),),
    )

    with _failing("momentum") as arguments:
        result = _invoke(arguments, probe)

    assert result.stderr.splitlines()[0] == _FINDING_LINES[CheckVerdict.UNREACHABLE]
    assert "timed out" not in result.stderr


def test_a_provider_with_no_health_check_could_not_be_checked_and_no_request_is_made() -> None:
    probe = ProviderProbe(
        enabled=True,
        timeout_seconds=10.0,
        clients=_no_clients,
        checks=(),
    )

    with _failing("graham-number") as arguments:
        result = _invoke(arguments, probe)

    assert result.exit_code == 1
    assert result.stderr.splitlines()[0] == "SEC EDGAR could not be checked."


@pytest.mark.parametrize("command", list(_SCENARIOS))
def test_the_option_turns_the_check_off_for_the_invocation(command: str) -> None:
    fake = _probe()
    display = {"yfinance": "Yahoo Finance", "sec_edgar": "SEC EDGAR"}[_SCENARIOS[command].provider_id]

    with _failing(command) as arguments:
        result = _invoke(arguments, fake.probe, "--no-provider-check")

    assert result.exit_code == 1
    text = result.stderr if command == "momentum" or "--diagnostics" not in arguments else result.stdout
    assert text.splitlines()[0] == f"{display} was not checked (the provider check is turned off)."
    assert fake.calls == []


def test_the_setting_turns_the_check_off() -> None:
    fake = _probe(enabled=False)

    with _failing("momentum") as arguments:
        result = _invoke(arguments, fake.probe)

    assert result.exit_code == 1
    assert result.stderr.splitlines()[0] == _SWITCHED_OFF
    assert fake.calls == []


@pytest.mark.parametrize("command", list(_SCENARIOS))
def test_json_output_prints_nothing_extra_and_carries_the_finding_in_the_document(command: str) -> None:
    scenario = _SCENARIOS[command]
    fake = _probe({scenario.provider_id: CheckVerdict.UNREACHABLE})

    with _failing(command) as arguments:
        result = _invoke(arguments, fake.probe, "--json")

    assert result.exit_code == 1
    document = json.loads(result.stdout)
    assert document["provider_failure"]["inputs"][0]["kind"] == "unreachable"
    assert document["provider_check"] == [{"provider_id": scenario.provider_id, "verdict": "unreachable"}]
    assert result.stderr == ""
    assert fake.calls == [scenario.provider_id]


def test_the_command_is_given_the_probe_built_from_the_settings_when_none_is_injected() -> None:
    with patch("src.cli.build_provider_probe") as build:
        build.return_value = _probe({"yfinance": CheckVerdict.NO_DATA}).probe
        with _failing("momentum") as arguments:
            result = runner.invoke(app, arguments)

    assert result.stderr.splitlines()[0] == _FINDING_LINES[CheckVerdict.NO_DATA]
    build.assert_called_once_with()


def test_the_probe_is_built_from_the_two_settings() -> None:
    from src.cli import build_provider_probe  # noqa: PLC0415 - the root's own builder

    with patch("src.cli.settings") as fake_settings:
        fake_settings.provider_check = False
        fake_settings.provider_check_timeout_seconds = 3.5
        probe = build_provider_probe()

    assert isinstance(probe, ProviderProbe)
    assert probe.check("yfinance").switched_off is True


def test_the_failed_call_is_never_retried() -> None:
    fake = _probe({"yfinance": CheckVerdict.UNREACHABLE})

    with (
        patch(
            "src.strategies.momentum.execution.MomentumAnalyzer.run_analysis",
            side_effect=DataFetchError("detail", kind=ProviderFailureKind.UNREACHABLE, provider_id="yfinance"),
        ) as analysis,
    ):
        result = _invoke(["momentum", "FCIM"], fake.probe)

    assert result.exit_code == 1
    assert analysis.call_count == 1


@pytest.mark.parametrize("command", ["momentum", "graham-number"])
def test_a_failure_that_names_no_provider_runs_no_probe_and_prints_no_line(command: str) -> None:
    fake = _probe()

    with _failing(command, kind=None) as arguments:
        result = _invoke(arguments, fake.probe)

    assert result.exit_code == 1
    text = result.stderr
    assert "was not checked" not in text
    assert "could not be checked" not in text
    assert "test request" not in text
    assert fake.calls == []


@pytest.mark.parametrize("command", ["graham-number", "graham-growth"])
def test_a_failed_optional_quote_on_a_successful_analysis_does_not_trigger_the_check(command: str) -> None:
    fake = _probe()
    case = next(item for item in CASES if item.name == f"{command}-quote-provider-failure")

    with ExitStack() as stack:
        _enter_providers(stack, case)
        result = _invoke(list(case.arguments), fake.probe)

    assert result.exit_code == 0
    assert fake.calls == []
    assert "test request" not in result.output
    assert "was not checked" not in result.output


class _RaisingProbe:
    def check(self, provider_id: str, *, requested: bool = True) -> ProbeFinding:
        del provider_id, requested
        raise RuntimeError("defect in the probe")


class _WrongValueProbe:
    def check(self, provider_id: str, *, requested: bool = True) -> object:
        del provider_id, requested
        return "healthy"


@pytest.mark.parametrize("probe", [_RaisingProbe(), _WrongValueProbe()], ids=["raises", "wrong-value"])
@pytest.mark.parametrize("command", list(_SCENARIOS))
def test_the_check_fails_open_and_never_changes_the_failure_or_its_exit_code(command: str, probe: object) -> None:
    scenario = _SCENARIOS[command]
    display = {"yfinance": "Yahoo Finance", "sec_edgar": "SEC EDGAR"}[scenario.provider_id]

    with _failing(command) as arguments:
        result = _invoke(arguments, probe)
        baseline = _invoke(arguments, _probe(enabled=False).probe)

    assert result.exit_code == baseline.exit_code == 1
    assert result.stderr.splitlines()[0] == f"{display} could not be checked."
    assert result.stderr.splitlines()[1:] == baseline.stderr.splitlines()[1:]
    assert result.stdout == baseline.stdout


# ---------------------------------------------------------------------------
# The shared function: several providers, the implicated one only, the order.
# ---------------------------------------------------------------------------


def _element(*records: tuple[ProviderFailureKind, str]) -> ProviderFailure:
    element = provider_failure_of(tuple(ProviderFailureRecord(kind, provider) for kind, provider in records))
    assert element is not None
    return element


def test_several_providers_follow_the_kind_order_and_each_appears_once() -> None:
    fake = _probe()
    choice = ProviderCheckChoice(fake.probe, requested=True)
    failures = [
        _element((ProviderFailureKind.NO_DATA, "yfinance")),
        _element((ProviderFailureKind.UNREACHABLE, "sec_edgar"), (ProviderFailureKind.RATE_LIMITED, "yfinance")),
        _element((ProviderFailureKind.UNEXPECTED_RESPONSE, "yfinance")),
        None,
    ]

    lines = provider_check_findings(failures, choice).lines()

    assert lines == (
        "SEC EDGAR answered a test request normally. The failure may be specific to this request.",
        "Yahoo Finance answered a test request normally. The failure may be specific to this request.",
    )
    assert sorted(fake.calls) == ["sec_edgar", "yfinance"]


def test_only_the_implicated_provider_is_probed() -> None:
    fake = _probe()

    provider_check_findings(
        [_element((ProviderFailureKind.NO_DATA, "sec_edgar"))], ProviderCheckChoice(fake.probe, True)
    )

    assert fake.calls == ["sec_edgar"]


def test_no_failure_and_no_probe_give_no_lines() -> None:
    fake = _probe()

    one = [_element((ProviderFailureKind.NO_DATA, "yfinance"))]
    for findings in (
        provider_check_findings([None, None], ProviderCheckChoice(fake.probe, True)),
        provider_check_findings(one, None),
        provider_check_findings(one, ProviderCheckChoice(None, True)),
    ):
        assert findings.lines() == ()
        assert findings.element() is None
    assert fake.calls == []


# ---------------------------------------------------------------------------
# The option is on exactly five commands.
# ---------------------------------------------------------------------------


def _commands_with_option(option: str) -> set[str]:
    found: set[str] = set()

    def walk(command: object, path: tuple[str, ...]) -> None:
        if any(option in getattr(parameter, "opts", ()) for parameter in getattr(command, "params", ())):
            found.add(" ".join(path))
        for name, child in getattr(command, "commands", {}).items():
            walk(child, (*path, name))

    walk(get_command(app), ())
    return found


def test_the_option_is_on_exactly_the_five_commands() -> None:
    assert _commands_with_option("--no-provider-check") == {
        "momentum",
        "graham-number",
        "graham-growth",
        "fcf-growth",
        "refresh",
    }


def test_the_option_help_names_no_planning_label_and_not_the_word_canary() -> None:
    for command in ("momentum", "graham-number", "graham-growth", "fcf-growth", "refresh"):
        text = normalize_cli_output(runner.invoke(app, [command, "--help"]).output).lower()
        assert "--no-provider-check" in text
        assert "canary" not in text


# ---------------------------------------------------------------------------
# The refresh command.
# ---------------------------------------------------------------------------

_WATCHLIST_NUMBER = itertools.count(1)


def _seed_momentum(settings: ProjectSettings, name: str, tickers: list[str]) -> None:
    from tests.test_cli_refresh import _create_momentum_only  # noqa: PLC0415 - shares that module's seeding

    _create_momentum_only(settings, name, tickers)


def _refresh_failing(
    settings: ProjectSettings,
    probe: object | None,
    *extra: str,
    tickers: tuple[str, ...] = ("AAPL", "MSFT", "KO"),
    kind: ProviderFailureKind | None = ProviderFailureKind.UNREACHABLE,
) -> Result:
    name = f"Watch {next(_WATCHLIST_NUMBER)}"
    _seed_momentum(settings, name, list(tickers))
    with patch(
        "src.strategies.momentum.execution.MomentumAnalyzer.run_analysis",
        side_effect=DataFetchError("library detail", kind=kind, provider_id="yfinance" if kind else None),
    ):
        return runner.invoke(app, ["refresh", name, "--workers", "1", *extra], obj=probe)


def test_refresh_prints_the_line_before_the_summary_on_the_summary_stream_and_probes_once(
    isolated_cli_database: ProjectSettings,
) -> None:
    fake = _probe({"yfinance": CheckVerdict.UNREACHABLE})

    result = _refresh_failing(isolated_cli_database, fake.probe)

    assert result.exit_code == 1
    lines = result.stdout.splitlines()
    assert lines[0] == _FINDING_LINES[CheckVerdict.UNREACHABLE]
    assert lines[1].startswith("Refresh ")
    assert result.stderr == ""
    assert fake.calls == ["yfinance"]  # three failed tickers, one test request


def test_refresh_runs_the_check_after_the_batch_never_inside_the_job_loop(
    isolated_cli_database: ProjectSettings,
) -> None:
    events: list[str] = []
    probe = MagicMock()

    def check(provider_id: str, *, requested: bool = True) -> ProbeFinding:
        del requested
        events.append("probe")
        return ProbeFinding(provider_id, ProbeVerdict.HEALTHY)

    probe.check = check
    _seed_momentum(isolated_cli_database, "My Watch", ["AAPL", "MSFT"])

    def failing(**_kwargs: object) -> None:
        events.append("job")
        raise DataFetchError("detail", kind=ProviderFailureKind.UNREACHABLE, provider_id="yfinance")

    with patch("src.strategies.momentum.execution.MomentumAnalyzer.run_analysis", side_effect=failing):
        result = runner.invoke(app, ["refresh", "My Watch", "--workers", "1"], obj=probe)

    assert result.exit_code == 1
    assert events == ["job", "job", "probe"]


def test_refresh_json_prints_nothing_extra_and_carries_one_finding_in_the_summary(
    isolated_cli_database: ProjectSettings,
) -> None:
    fake = _probe({"yfinance": CheckVerdict.RATE_LIMITED})

    result = _refresh_failing(isolated_cli_database, fake.probe, "--json")

    assert result.exit_code == 1
    document = json.loads(result.stdout)
    assert document["counts"] == {"error": 3}
    assert document["provider_check"] == [{"provider_id": "yfinance", "verdict": "rate_limited"}]
    assert result.stderr == ""
    assert fake.calls == ["yfinance"]  # three failed tickers, one test request


def test_refresh_option_turns_the_check_off_without_changing_the_summary(
    isolated_cli_database: ProjectSettings,
) -> None:
    fake = _probe()
    checked = _refresh_failing(isolated_cli_database, _probe().probe)

    result = _refresh_failing(isolated_cli_database, fake.probe, "--no-provider-check")

    assert result.exit_code == checked.exit_code == 1
    assert result.stdout.splitlines()[0] == _SWITCHED_OFF
    # Only the identities differ between two refreshes: the same job lines and counts follow the one first line.
    assert len(result.stdout.splitlines()) == len(checked.stdout.splitlines())
    assert result.stdout.splitlines()[-1] == checked.stdout.splitlines()[-1] == "Counts: error=3"
    assert fake.calls == []


def test_refresh_without_a_provider_failure_prints_no_line_and_runs_no_probe(
    isolated_cli_database: ProjectSettings,
) -> None:
    fake = _probe()

    result = _refresh_failing(isolated_cli_database, fake.probe, kind=None)

    assert result.exit_code == 1
    assert result.stdout.startswith("Refresh ")
    assert fake.calls == []


def test_refresh_fails_open_when_the_probe_raises(isolated_cli_database: ProjectSettings) -> None:
    result = _refresh_failing(isolated_cli_database, _RaisingProbe())

    assert result.exit_code == 1
    assert result.stdout.splitlines()[0] == _COULD_NOT_CHECK
    assert result.stdout.splitlines()[1].startswith("Refresh ")


@pytest.mark.parametrize("flag", [None, "--no-provider-check"], ids=["checked", "declined"])
def test_refresh_exit_code_is_the_same_with_and_without_the_check(
    flag: str | None, isolated_cli_database: ProjectSettings
) -> None:
    extra = (flag,) if flag else ()
    assert (
        _refresh_failing(isolated_cli_database, _probe().probe, *extra).exit_code
        == _refresh_failing(isolated_cli_database, None).exit_code
        == 1
    )
