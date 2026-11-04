"""The one validation of a ``--database-url`` option, shared by every command that accepts it."""

from pathlib import Path

from pydantic import ValidationError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from investment_analysis_engine.config import ProjectSettings, settings
from investment_analysis_engine.config.paths import is_windows, require_anchored_path
from investment_analysis_engine.core.operator_errors import AnalysisConfigurationError, InvalidParameterError
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase

MEMORY_TARGET_MESSAGE = "Database maintenance requires a file-backed target; private memory is not supported."
"""The message of a configured target that selects private memory."""


def _first_reason(error: ValidationError) -> str:
    """Return the validator's own message for the first failure, without pydantic's prefix."""
    message = str(error.errors()[0]["msg"])
    return message.removeprefix("Value error, ")


def _anchor_database_url(database_url: str) -> str:
    """Resolve a relative SQLite file path in ``--database-url`` against the current folder.

    A URL the settings will reject anyway, memory and URI targets, and a path that is not a file path are returned
    unchanged, so the settings give their usual message. A Windows path that is only partly anchored is rejected.
    """
    try:
        url = make_url(database_url)
    except ArgumentError:
        return database_url
    if url.database in (None, "", ":memory:") or url.database.startswith("file:"):
        return database_url
    try:
        require_anchored_path(url.database, name="--database-url", windows=is_windows())
    except ValueError as exc:
        raise InvalidParameterError(
            f"Select a valid local SQLite database URL for --database-url: {exc}", parameters=("--database-url",)
        ) from exc
    return url.set(database=(Path.cwd() / url.database).resolve().as_posix()).render_as_string(hide_password=False)


def file_backed_settings(database_url: str | None) -> ProjectSettings:
    """Return the settings a command uses: the configured ones, or those with ``--database-url`` applied.

    The target must be a file-backed SQLite database.

    Raises:
        InvalidParameterError: If a supplied ``--database-url`` is rejected by the settings or selects private
            memory.
        AnalysisConfigurationError: If the configured target, with no ``--database-url``, selects private memory.
    """
    try:
        selected = (
            settings
            if database_url is None
            else ProjectSettings(**(settings.model_dump() | {"database_url": _anchor_database_url(database_url)}))
        )
    except ValidationError as exc:
        raise InvalidParameterError(
            f"Select a valid local SQLite database URL for --database-url: {_first_reason(exc)}",
            parameters=("--database-url",),
        ) from exc
    probe = SQLiteDatabase(selected)
    try:
        file_backed = probe.database_path is not None
    finally:
        probe.close()
    if not file_backed:
        if database_url is None:
            raise AnalysisConfigurationError(MEMORY_TARGET_MESSAGE)
        raise InvalidParameterError(
            "Database maintenance requires a file-backed target for --database-url; private memory is not supported.",
            parameters=("--database-url",),
        )
    return selected


__all__ = ["MEMORY_TARGET_MESSAGE", "file_backed_settings"]
