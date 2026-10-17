"""Command Line Interface routing for the Investment Analysis Engine execution suite."""

from __future__ import annotations

import asyncio
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from investment_analysis_engine.cli_composition import load_all_strategy_settings
from investment_analysis_engine.cli_database import app as database_app
from investment_analysis_engine.cli_health import build_provider_clients
from investment_analysis_engine.cli_health import register as register_health_command
from investment_analysis_engine.cli_run_support import get_cli_run_context
from investment_analysis_engine.cli_strategy_wiring import add_strategy_commands
from investment_analysis_engine.cli_support import parameter_failures
from investment_analysis_engine.cli_workspace import register as register_workspace_commands
from investment_analysis_engine.config import paths, settings
from investment_analysis_engine.core.clock import utc_now
from investment_analysis_engine.core.operator_errors import InvalidParameterError
from investment_analysis_engine.data.provider_probe import ProviderProbe
from investment_analysis_engine.evaluation.catalog import (
    DETERMINISTIC_FIXTURE_SET_VERSION,
    DETERMINISTIC_SUITE_ID,
    DETERMINISTIC_SUITE_VERSION,
    build_deterministic_requests,
)
from investment_analysis_engine.evaluation.ollama_runner import (
    OllamaEvaluationConfig,
    OllamaEvaluationResult,
    run_real_local_ollama_suite,
)
from investment_analysis_engine.evaluation.reporting import EvaluationReport
from investment_analysis_engine.evaluation.runner import DeterministicCaseRequest, run_deterministic_suite
from investment_analysis_engine.llm.client import LLMClient
from investment_analysis_engine.telemetry.recorder import TrajectoryRecorder
from investment_analysis_engine.telemetry.run_context import (
    RunContext,
    get_current_run_context,
    set_current_run_context,
)

load_all_strategy_settings()

app = typer.Typer(
    help="Analyze financial data with transparent calculations and supporting evidence.", add_completion=False
)
app.add_typer(database_app, name="db", hidden=True)
register_workspace_commands(app)
register_health_command(app)
add_strategy_commands(app)


class EvaluationCliMode(StrEnum):
    """User-facing Golden-Suite execution choices."""

    DETERMINISTIC = "deterministic"
    OLLAMA = "ollama"


type EvaluationCommandResult = EvaluationReport | OllamaEvaluationResult


def build_provider_probe() -> ProviderProbe:
    """Build the one automatic provider check of this process from the settings.

    This is the only place the probe is built; the commands that report a provider failure receive it through the
    Typer context. It contacts no provider until a command reports a provider failure.
    """
    return ProviderProbe(
        enabled=settings.provider_check,
        timeout_seconds=settings.provider_check_timeout_seconds,
        clients=build_provider_clients,
    )


@app.callback()
def main_entry_point(context: typer.Context) -> None:
    """Initialize one RunContext for this CLI invocation if main.py did not, and hand the commands the probe."""
    if get_current_run_context() is None:
        set_current_run_context(RunContext.new())
    if context.obj is None:
        context.obj = build_provider_probe()


@app.command(name="evaluate")
def evaluate(  # noqa: PLR0913
    *,
    mode: Annotated[
        EvaluationCliMode,
        typer.Option("--mode", help="Execution mode: deterministic (default) or ollama"),
    ] = EvaluationCliMode.DETERMINISTIC,
    case_id: str | None = typer.Option(None, "--case", help="Run one stable Golden case ID instead of the full suite"),
    report_path: Annotated[Path, typer.Option("--report", help="Explicit JSON report destination")],
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace an existing report file"),
    ollama_endpoint: str | None = typer.Option(
        None,
        "--ollama-endpoint",
        help="Ollama endpoint; defaults to the configured application endpoint",
    ),
    model_id: str | None = typer.Option(
        None,
        "--model",
        help="Local model identifier; defaults to the configured application model",
    ),
    temperature: float | None = typer.Option(None, "--temperature", help="Empirical sampling temperature"),
    repetitions: int | None = typer.Option(
        None,
        "--repetitions",
        min=1,
        max=100,
        help="Independent empirical repetitions (1-100)",
    ),
    max_steps: int | None = typer.Option(
        None,
        "--max-steps",
        min=1,
        max=50,
        help="Maximum orchestration steps per case (1-50)",
    ),
) -> None:
    """Run the versioned Golden Suite and write one machine-readable report."""
    with parameter_failures(json_output=False):
        try:
            paths.require_anchored_path(report_path.as_posix(), name="--report", windows=paths.is_windows())
        except ValueError as exc:
            raise InvalidParameterError(str(exc), parameters=("--report",)) from exc
        requests = _select_evaluation_requests(case_id)
        _validate_evaluation_mode_options(
            mode,
            ollama_endpoint=ollama_endpoint,
            model_id=model_id,
            temperature=temperature,
            repetitions=repetitions,
            max_steps=max_steps,
        )
        target = report_path.expanduser().resolve()
        if target.exists() and not overwrite:
            raise InvalidParameterError(
                f"--report target already exists: {target}. Use --overwrite to replace it.", parameters=("--report",)
            )

    try:
        result = asyncio.run(
            _run_evaluation_command(
                requests,
                mode=mode,
                executed_at=utc_now(),
                ollama_endpoint=ollama_endpoint,
                model_id=model_id,
                temperature=temperature,
                repetitions=repetitions,
                max_steps=max_steps,
            )
        )
        _write_evaluation_report(result, target=target, overwrite=overwrite)
    except (OSError, ValueError) as err:
        typer.echo(f"Evaluation failed: {err}", err=True)
        raise typer.Exit(code=1) from err
    except Exception as err:
        typer.echo(f"Evaluation failed unexpectedly: {err}", err=True)
        raise typer.Exit(code=1) from err

    passed, failed, skipped = _evaluation_case_counts(result)
    typer.echo(f"Evaluation report written to {target} ({passed} passed, {failed} failed, {skipped} skipped).")
    if failed or skipped:
        for diagnostic in _evaluation_failure_diagnostics(result):
            typer.echo(diagnostic, err=True)
        raise typer.Exit(code=1)


def _select_evaluation_requests(case_id: str | None) -> tuple[DeterministicCaseRequest, ...]:
    """Return the full canonical catalog or one exact stable case."""
    requests = build_deterministic_requests()
    if case_id is None:
        return requests
    normalized = case_id.strip().upper()
    selected = tuple(request for request in requests if request.case.case_id == normalized)
    if selected:
        return selected
    available = ", ".join(request.case.case_id for request in requests)
    raise InvalidParameterError(
        f"Unknown Golden case ID {case_id!r} for --case. Available IDs: {available}.", parameters=("--case",)
    )


def _validate_evaluation_mode_options(  # noqa: PLR0913
    mode: EvaluationCliMode,
    *,
    ollama_endpoint: str | None,
    model_id: str | None,
    temperature: float | None,
    repetitions: int | None,
    max_steps: int | None,
) -> None:
    """Reject empirical-only controls when deterministic execution is selected."""
    empirical_options = (ollama_endpoint, model_id, temperature, repetitions, max_steps)
    if mode is EvaluationCliMode.DETERMINISTIC and any(value is not None for value in empirical_options):
        raise InvalidParameterError("Ollama options require --mode ollama.", parameters=("--mode",))


async def _run_evaluation_command(  # noqa: PLR0913
    requests: tuple[DeterministicCaseRequest, ...],
    *,
    mode: EvaluationCliMode,
    executed_at: datetime,
    ollama_endpoint: str | None,
    model_id: str | None,
    temperature: float | None,
    repetitions: int | None,
    max_steps: int | None,
) -> EvaluationCommandResult:
    """Route one CLI request through the reviewed deterministic or empirical runner."""
    if mode is EvaluationCliMode.DETERMINISTIC:
        recorder = TrajectoryRecorder.from_settings(get_cli_run_context())
        return await run_deterministic_suite(
            requests,
            suite_id=DETERMINISTIC_SUITE_ID,
            suite_version=DETERMINISTIC_SUITE_VERSION,
            fixture_set_version=DETERMINISTIC_FIXTURE_SET_VERSION,
            executed_at=executed_at,
            recorder=recorder,
        )

    endpoint = ollama_endpoint or settings.ollama_base_url
    selected_model = model_id or settings.model_selection
    config = OllamaEvaluationConfig(
        endpoint=endpoint,
        model_id=selected_model,
        temperature=0.0 if temperature is None else temperature,
        repetitions=1 if repetitions is None else repetitions,
        max_steps=10 if max_steps is None else max_steps,
        schema_config=settings.schema_config,
    )
    client = LLMClient(config.endpoint, default_model=config.model_id)
    try:
        return await run_real_local_ollama_suite(
            requests,
            suite_id=DETERMINISTIC_SUITE_ID,
            suite_version=DETERMINISTIC_SUITE_VERSION,
            fixture_set_version=DETERMINISTIC_FIXTURE_SET_VERSION,
            llm_client=client,
            config=config,
            executed_at=executed_at,
        )
    finally:
        await client.close()


def _write_evaluation_report(
    result: EvaluationCommandResult,
    *,
    target: Path,
    overwrite: bool,
) -> None:
    """Serialize a complete report without replacing an existing file implicitly."""
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with target.open(mode, encoding="utf-8", newline="\n") as report_file:
        report_file.write(result.model_dump_json(indent=2))
        report_file.write("\n")


def _evaluation_case_counts(result: EvaluationCommandResult) -> tuple[int, int, int]:
    """Return aggregate passed, failed, and skipped case-execution counts."""
    if isinstance(result, EvaluationReport):
        return result.passed_cases, result.failed_cases, result.skipped_cases
    reports = tuple(item.report for item in result.repetition_reports)
    return (
        sum(report.passed_cases for report in reports),
        sum(report.failed_cases for report in reports),
        sum(report.skipped_cases for report in reports),
    )


def _evaluation_failure_diagnostics(result: EvaluationCommandResult) -> tuple[str, ...]:
    """Render concise case diagnostics, including typed reliability reasons and run IDs."""
    reports = (
        (result,) if isinstance(result, EvaluationReport) else tuple(item.report for item in result.repetition_reports)
    )
    diagnostics: list[str] = []
    for repetition, report in enumerate(reports, start=1):
        for case in getattr(report, "case_results", ()):
            prefix = f"{case.case_id}"
            if len(reports) > 1:
                prefix += f" repetition {repetition}"
            if case.failure_reasons:
                diagnostics.extend(f"{prefix}: {reason}" for reason in case.failure_reasons)
            elif case.skip_reason is not None:
                diagnostics.append(f"{prefix}: skipped: {case.skip_reason}")
    return tuple(diagnostics)


if __name__ == "__main__":
    app()
