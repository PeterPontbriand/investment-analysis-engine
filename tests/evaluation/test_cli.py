"""CLI coverage for deterministic and opt-in empirical Golden-Suite execution."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from src.cli import app
from src.core.telemetry import RunContext, TrajectoryEvent, TrajectoryRecorder
from src.evaluation.models import ComponentKind, ComponentOutcome, ComponentResult, ExecutionMode
from src.evaluation.reporting import EvaluationReport, build_case_result, build_evaluation_report
from src.evaluation.runner import DETERMINISTIC_REQUIRED_COMPONENT_KINDS
from tests._cli_helpers import normalize_cli_output

runner = CliRunner()


class NullSink:
    """Accept deterministic evaluation telemetry without persistence."""

    def record(self, event: TrajectoryEvent) -> None:
        """Accept one trajectory event."""
        del event

    def flush(self) -> None:
        """Accept a flush request."""

    def close(self) -> None:
        """Accept recorder closure."""


def _recorder() -> TrajectoryRecorder:
    """Return a fresh in-memory recorder for one CLI invocation."""
    return TrajectoryRecorder(RunContext.new(), NullSink())


def _empirical_result(*, passed: int, failed: int = 0, skipped: int = 0) -> MagicMock:
    """Build the minimal report-shaped empirical result needed at the CLI boundary."""
    result = MagicMock()
    result.model_dump_json.return_value = '{"execution_mode":"real_local_ollama"}'
    report = SimpleNamespace(passed_cases=passed, failed_cases=failed, skipped_cases=skipped)
    result.repetition_reports = (SimpleNamespace(report=report),)
    return result


def _failed_deterministic_report() -> EvaluationReport:
    """Build one valid deterministic report containing a required execution failure."""
    diagnostic = "max_steps_exceeded: reliability limit reached (run_id=12345678-1234-5678-1234-567812345678)."
    components = (
        ComponentResult(kind=ComponentKind.FIXTURE_STATUS, outcome=ComponentOutcome.PASS),
        ComponentResult(
            kind=ComponentKind.EXECUTION_STATUS,
            outcome=ComponentOutcome.FAIL,
            failure_reason=diagnostic,
        ),
        ComponentResult(kind=ComponentKind.NUMERICAL_CORRECTNESS, outcome=ComponentOutcome.PASS),
    )
    case = build_case_result(
        case_id="GRN-01",
        components=components,
        required_component_kinds=DETERMINISTIC_REQUIRED_COMPONENT_KINDS,
    )
    return build_evaluation_report(
        suite_id="cli-failure-test",
        suite_version="test-v1",
        fixture_set_version="fixtures-v1",
        execution_mode=ExecutionMode.DETERMINISTIC_NO_LLM,
        executed_at=datetime(2026, 8, 31, 22, 0, tzinfo=UTC),
        required_component_kinds=DETERMINISTIC_REQUIRED_COMPONENT_KINDS,
        case_results=(case,),
    )


def test_evaluate_cli_runs_full_deterministic_suite_and_writes_report(tmp_path: Path) -> None:
    """The default command executes all reviewed cases without a model or live provider."""
    target = tmp_path / "reports" / "golden.json"

    with patch("src.cli.TrajectoryRecorder.from_settings", side_effect=lambda *_args, **_kwargs: _recorder()):
        result = runner.invoke(app, ["evaluate", "--report", str(target)])

    assert result.exit_code == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["execution_mode"] == "deterministic_no_llm"
    assert payload["total_cases"] == 19
    assert payload["passed_cases"] == 19
    assert payload["failed_cases"] == 0
    assert "19 passed, 0 failed, 0 skipped" in result.output


def test_evaluate_cli_selects_one_named_case_case_insensitively(tmp_path: Path) -> None:
    """A stable case ID narrows both execution and the serialized report."""
    target = tmp_path / "one-case.json"

    with patch("src.cli.TrajectoryRecorder.from_settings", side_effect=lambda *_args, **_kwargs: _recorder()):
        result = runner.invoke(app, ["evaluate", "--case", "grn-01", "--report", str(target)])

    assert result.exit_code == 0
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["total_cases"] == 1
    assert payload["case_results"][0]["case_id"] == "GRN-01"


def test_evaluate_cli_rejects_unknown_case_and_does_not_create_report(tmp_path: Path) -> None:
    """Unknown identities fail as usage errors before execution or file creation."""
    target = tmp_path / "unknown.json"

    result = runner.invoke(app, ["evaluate", "--case", "NOT-A-CASE", "--report", str(target)])

    assert result.exit_code == 2
    assert "Unknown Golden case ID" in result.output
    assert not target.exists()


def test_evaluate_cli_protects_existing_report_unless_overwrite_is_explicit(tmp_path: Path) -> None:
    """The report boundary never replaces prior evidence implicitly."""
    target = tmp_path / "existing.json"
    target.write_text("preserve me", encoding="utf-8")

    blocked = runner.invoke(
        app,
        ["evaluate", "--case", "GRN-01", "--report", str(target)],
        terminal_width=80,
    )

    assert blocked.exit_code == 2
    assert "Use --overwrite" in normalize_cli_output(blocked.output)
    assert target.read_text(encoding="utf-8") == "preserve me"

    with patch("src.cli.TrajectoryRecorder.from_settings", side_effect=lambda *_args, **_kwargs: _recorder()):
        replaced = runner.invoke(
            app,
            ["evaluate", "--case", "GRN-01", "--report", str(target), "--overwrite"],
        )

    assert replaced.exit_code == 0
    assert json.loads(target.read_text(encoding="utf-8"))["total_cases"] == 1


def test_evaluate_cli_routes_explicit_ollama_mode_and_fails_on_required_case_failure(tmp_path: Path) -> None:
    """Empirical execution is opt-in, closes its client, writes evidence, and returns status 1 on failure."""
    target = tmp_path / "empirical.json"
    client = MagicMock()
    client.close = AsyncMock()
    empirical = _empirical_result(passed=0, failed=1)
    run_empirical = AsyncMock(return_value=empirical)

    with (
        patch("src.cli.LLMClient", return_value=client) as client_type,
        patch("src.cli.run_real_local_ollama_suite", run_empirical),
    ):
        result = runner.invoke(
            app,
            [
                "evaluate",
                "--mode",
                "ollama",
                "--case",
                "GRN-01",
                "--report",
                str(target),
                "--ollama-endpoint",
                "http://local-ollama.test",
                "--model",
                "golden-model:test",
                "--temperature",
                "0.2",
                "--repetitions",
                "2",
                "--max-steps",
                "4",
            ],
        )

    assert result.exit_code == 1
    assert json.loads(target.read_text(encoding="utf-8"))["execution_mode"] == "real_local_ollama"
    client_type.assert_called_once_with("http://local-ollama.test", default_model="golden-model:test")
    client.close.assert_awaited_once()
    call = run_empirical.await_args
    assert call is not None
    assert tuple(request.case.case_id for request in call.args[0]) == ("GRN-01",)
    config = call.kwargs["config"]
    assert config.endpoint == "http://local-ollama.test"
    assert config.model_id == "golden-model:test"
    assert config.temperature == 0.2
    assert config.repetitions == 2
    assert config.max_steps == 4
    assert "0 passed, 1 failed, 0 skipped" in result.output


def test_evaluate_cli_writes_deterministic_failure_report_before_returning_status_one(tmp_path: Path) -> None:
    """A deterministic benchmark failure remains inspectable and fails the process."""
    target = tmp_path / "failed-deterministic.json"
    failed_report = _failed_deterministic_report()

    with patch("src.cli._run_evaluation_command", AsyncMock(return_value=failed_report)):
        result = runner.invoke(app, ["evaluate", "--case", "GRN-01", "--report", str(target)])

    assert result.exit_code == 1
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["failed_cases"] == 1
    expected = (
        "execution_status: max_steps_exceeded: reliability limit reached (run_id=12345678-1234-5678-1234-567812345678)."
    )
    assert payload["case_results"][0]["failure_reasons"] == [expected]
    assert f"GRN-01: {expected}" in result.output


def test_evaluate_cli_rejects_ollama_options_in_default_mode(tmp_path: Path) -> None:
    """Supplying model controls cannot silently change deterministic semantics."""
    target = tmp_path / "unused.json"

    result = runner.invoke(
        app,
        ["evaluate", "--report", str(target), "--model", "unexpected-model"],
        terminal_width=80,
    )

    assert result.exit_code == 2
    assert "Ollama options require --mode ollama" in normalize_cli_output(result.output)
    assert not target.exists()
