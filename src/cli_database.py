"""Hidden technical commands for inspecting and migrating configured storage."""

import json
from typing import Literal

import typer
from pydantic import ValidationError

from src.config import ProjectSettings, settings
from src.data.repositories.readiness import (
    DatabaseReadinessError,
    DatabaseState,
    ReadinessReason,
    inspect_database,
    upgrade_database,
)
from src.data.repositories.sqlite import SQLiteDatabase
from src.reporting.documents.database import DatabaseMaintenanceReport
from src.reporting.documents.failure import FailureReasonCode

app = typer.Typer(help="Inspect or explicitly migrate application storage.", add_completion=False)


def _first_reason(error: ValidationError) -> str:
    """Return the validator's own message for the first failure, without pydantic's prefix."""
    message = str(error.errors()[0]["msg"])
    return message.removeprefix("Value error, ")


def _run(*, upgrade: bool, database_url: str | None, json_output: bool) -> None:
    try:
        if database_url is None:
            selected = settings
        else:
            selected = ProjectSettings(**(settings.model_dump() | {"database_url": database_url}))
        database = SQLiteDatabase(selected)
    except ValidationError as exc:
        raise typer.BadParameter(f"Select a valid local SQLite database URL: {_first_reason(exc)}") from exc
    except ValueError as exc:
        raise typer.BadParameter(f"Select a valid local SQLite database URL: {exc}") from exc
    report: DatabaseMaintenanceReport
    code = 0
    try:
        path = database.database_path
        if path is None:
            raise typer.BadParameter(
                "Database maintenance requires a file-backed target; private memory is not supported."
            )
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
