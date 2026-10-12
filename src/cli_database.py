"""Hidden technical commands for inspecting and migrating configured storage."""

import json
from typing import Literal

import typer
from pydantic import ValidationError

from src.cli_support import parameter_failures, report_failure
from src.config import ProjectSettings, settings
from src.core.failure_codes import FailureReasonCode
from src.core.operator_errors import InvalidParameterError
from src.data.repositories.readiness import (
    DatabaseReadinessError,
    DatabaseState,
    ReadinessReason,
    inspect_database,
    upgrade_database,
)
from src.data.repositories.sqlite import SQLiteDatabase
from src.reporting.documents.database import DatabaseMaintenanceReport
from src.reporting.failure_envelope import failure_envelope

app = typer.Typer(help="Inspect or explicitly migrate application storage.", add_completion=False)


def _first_reason(error: ValidationError) -> str:
    """Return the validator's own message for the first failure, without pydantic's prefix."""
    message = str(error.errors()[0]["msg"])
    return message.removeprefix("Value error, ")


_MEMORY_TARGET_SENTENCE = "Database maintenance requires a file-backed target; private memory is not supported."


def _open_database(database_url: str | None, *, json_output: bool) -> SQLiteDatabase:
    """Open the selected target, which must be a validated file-backed SQLite database.

    A supplied ``--database-url`` the settings reject, or one that selects private memory, is an
    ``invalid_parameter`` failure. A private-memory target that came from the settings is a
    ``configuration_error``: no parameter is at fault.
    """
    with parameter_failures(json_output=json_output):
        try:
            selected = (
                settings
                if database_url is None
                else ProjectSettings(**(settings.model_dump() | {"database_url": database_url}))
            )
        except ValidationError as exc:
            raise InvalidParameterError(
                f"Select a valid local SQLite database URL for --database-url: {_first_reason(exc)}",
                parameters=("--database-url",),
            ) from exc
        database = SQLiteDatabase(selected)
        if database.database_path is None:
            database.close()
            if database_url is None:
                report_failure(
                    failure_envelope(FailureReasonCode.CONFIGURATION_ERROR, _MEMORY_TARGET_SENTENCE),
                    json_output=json_output,
                )
            raise InvalidParameterError(
                "Database maintenance requires a file-backed target for --database-url; "
                "private memory is not supported.",
                parameters=("--database-url",),
            )
        return database


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
                    str(DatabaseReadinessError(reason, path, inspection.expected_revision))
                    if reason is not None
                    else "Database is ready."
                    if state is DatabaseState.READY
                    else ("Database is not initialized. Run ian db upgrade with this same target to initialize it.")
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
                reason=str(exc),
            )
            code = 1
        if json_output:
            typer.echo(json.dumps(report.model_dump(mode="json"), ensure_ascii=True, allow_nan=False))
        else:
            typer.echo(
                f"Database: {json.dumps(report.database_path, ensure_ascii=True)}\n"
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
