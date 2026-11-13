"""Hidden technical commands for inspecting and migrating configured storage."""

import json
from typing import Literal

import typer

from investment_analysis_engine.cli_database_target import file_backed_settings
from investment_analysis_engine.cli_support import database_message, parameter_failures, report_failure
from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.core.operator_errors import AnalysisConfigurationError
from investment_analysis_engine.data.repositories.readiness import (
    DatabaseReadinessError,
    DatabaseState,
    ReadinessReason,
    inspect_database,
    upgrade_database,
)
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase
from investment_analysis_engine.reporting.documents.database import DatabaseMaintenanceReport
from investment_analysis_engine.reporting.failure_envelope import failure_envelope

app = typer.Typer(help="Inspect or explicitly migrate application storage.", add_completion=False)


def _open_database(database_url: str | None, *, json_output: bool) -> SQLiteDatabase:
    """Open the selected target, which must be a validated file-backed SQLite database.

    A supplied ``--database-url`` the settings reject, or one that selects private memory, is an
    ``invalid_parameter`` failure. A private-memory target that came from the settings is a
    ``configuration_error``: no parameter is at fault.
    """
    with parameter_failures(json_output=json_output):
        try:
            selected = file_backed_settings(database_url)
        except AnalysisConfigurationError as exc:
            report_failure(
                failure_envelope(FailureReasonCode.CONFIGURATION_ERROR, str(exc)),
                json_output=json_output,
            )
        return SQLiteDatabase(selected)


def _run(*, upgrade: bool, database_url: str | None, json_output: bool) -> None:
    database = _open_database(database_url, json_output=json_output)
    report: DatabaseMaintenanceReport
    code = 0
    try:
        path = database.database_path
        assert path is not None  # _open_database refuses private memory
        command: Literal["db upgrade", "db status"] = "db upgrade" if upgrade else "db status"
        try:
            if upgrade:
                outcome, revision = upgrade_database(database)
                report = DatabaseMaintenanceReport(
                    command=command,
                    status="success",
                    database_path=str(path),
                    state=outcome.value,
                    current_revision=revision,
                    expected_revision=revision,
                    reason_code=None,
                    reason="Database is ready.",
                )
            else:
                inspection = inspect_database(database)
                state = inspection.state
                reason = {
                    DatabaseState.UPGRADE_REQUIRED: ReadinessReason.UPGRADE_REQUIRED,
                    DatabaseState.INCOMPATIBLE: ReadinessReason.INCOMPATIBLE_SCHEMA,
                }.get(state)
                reason_text = (
                    database_message(DatabaseReadinessError(reason, path, inspection.expected_revision))
                    if reason is not None
                    else "Database is ready."
                    if state is DatabaseState.READY
                    else (
                        "Database is not initialized yet. The first command that needs it creates it; "
                        "to create it now, run ian db upgrade with this same target."
                    )
                )
                report = DatabaseMaintenanceReport(
                    command=command,
                    status="success",
                    database_path=str(path),
                    state=state.value,
                    current_revision=inspection.current_revision,
                    expected_revision=inspection.expected_revision,
                    reason_code=FailureReasonCode(reason.value) if reason else None,
                    reason=reason_text,
                )
                code = 0 if state is DatabaseState.READY else 1
        except DatabaseReadinessError as exc:
            report = DatabaseMaintenanceReport(
                command=command,
                status="error",
                database_path=str(path),
                state=None,
                current_revision=None,
                expected_revision=exc.expected_revision,
                reason_code=FailureReasonCode(exc.reason.value),
                reason=database_message(exc),
            )
            code = 1
        if json_output:
            typer.echo(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, allow_nan=False))
        else:
            typer.echo(
                f"Database: {json.dumps(report.database_path, ensure_ascii=False)}\n"
                f"State: {report.state or 'unavailable'}\n"
                f"Revision: {report.current_revision or 'unknown'}; expected: {report.expected_revision or 'unknown'}\n"
                f"{report.reason}",
                err=report.status == "error",
            )
    finally:
        database.close()
    raise typer.Exit(code)


@app.command()
def status(
    database_url: str | None = typer.Option(None, help="Override the configured SQLite target."),
    json_output: bool = typer.Option(False, "--json", help="Emit one versioned maintenance report."),
) -> None:
    """Inspect readiness without initializing or upgrading storage."""
    _run(upgrade=False, database_url=database_url, json_output=json_output)


@app.command()
def upgrade(
    database_url: str | None = typer.Option(None, help="Override the configured SQLite target."),
    json_output: bool = typer.Option(False, "--json", help="Emit one versioned maintenance report."),
) -> None:
    """Migrate supported storage. Stop application processes and back up existing data first."""
    _run(upgrade=True, database_url=database_url, json_output=json_output)
