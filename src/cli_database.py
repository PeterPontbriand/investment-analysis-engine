"""Hidden technical commands for inspecting and migrating configured storage."""

import json
from dataclasses import asdict, dataclass
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

app = typer.Typer(help="Inspect or explicitly migrate application storage.", add_completion=False)


@dataclass(frozen=True)
class DatabaseMaintenanceReport:
    """Versioned maintenance evidence independent of analysis-result documents."""

    command: str
    status: Literal["success", "error"]
    database_path: str | None
    state: str | None
    current_revision: str | None
    expected_revision: str | None
    reason: str | None
    message: str
    schema_version: int = 1


def _run(*, upgrade: bool, database_url: str | None, json_output: bool) -> None:
    try:
        if database_url is None:
            selected = settings
        else:
            selected = ProjectSettings(**(settings.model_dump() | {"database_url": database_url}))
        database = SQLiteDatabase(selected)
    except (ValidationError, ValueError) as exc:
        raise typer.BadParameter("Select a valid local SQLite database URL.") from exc
    report: DatabaseMaintenanceReport
    code = 0
    try:
        path = database.database_path
        if path is None:
            raise typer.BadParameter(
                "Database maintenance requires a file-backed target; private memory is not supported."
            )
        command = "db upgrade" if upgrade else "db status"
        try:
            if upgrade:
                outcome, revision = upgrade_database(database)
                report = DatabaseMaintenanceReport(
                    command,
                    "success",
                    str(path),
                    outcome.value,
                    revision,
                    revision,
                    None,
                    "Database is ready.",
                )
            else:
                inspection = inspect_database(database)
                state = inspection.state
                reason = {
                    DatabaseState.UPGRADE_REQUIRED: ReadinessReason.UPGRADE_REQUIRED,
                    DatabaseState.INCOMPATIBLE: ReadinessReason.INCOMPATIBLE_SCHEMA,
                }.get(state)
                message = (
                    str(DatabaseReadinessError(reason, path, inspection.expected_revision))
                    if reason is not None
                    else "Database is ready."
                    if state is DatabaseState.READY
                    else (
                        "Database is not initialized. Run financial-agents db upgrade with "
                        "this same target to initialize it."
                    )
                )
                report = DatabaseMaintenanceReport(
                    command,
                    "success",
                    str(path),
                    state.value,
                    inspection.current_revision,
                    inspection.expected_revision,
                    reason.value if reason else None,
                    message,
                )
                code = 0 if state is DatabaseState.READY else 1
        except DatabaseReadinessError as exc:
            report = DatabaseMaintenanceReport(
                command,
                "error",
                str(path),
                None,
                None,
                exc.expected_revision,
                exc.reason.value,
                str(exc),
            )
            code = 1
        if json_output:
            typer.echo(json.dumps(asdict(report), ensure_ascii=True, allow_nan=False))
        else:
            typer.echo(
                f"Database: {json.dumps(report.database_path, ensure_ascii=True)}\n"
                f"State: {report.state or 'unavailable'}\n"
                f"Revision: {report.current_revision or 'unknown'}; expected: {report.expected_revision or 'unknown'}\n"
                f"{report.message}",
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
