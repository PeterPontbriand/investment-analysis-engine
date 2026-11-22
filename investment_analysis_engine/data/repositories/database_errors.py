"""The typed database error, its stable reasons and the rule that classifies a storage error.

:class:`DatabaseError` is raised by the readiness check for every failure it reports, and by
:class:`~investment_analysis_engine.data.repositories.sqlite.SQLiteDatabase` for a storage error raised while it opens a
connection or inside one of its scopes, so a failure after readiness has passed carries the same precise code.
"""

import errno
import sqlite3
from enum import StrEnum
from pathlib import Path

from sqlalchemy.exc import DBAPIError

from investment_analysis_engine.core.failure_codes import FailureReasonCode
from investment_analysis_engine.data.repositories.readiness_lock import ReadinessLockTimeoutError


class DatabaseReason(StrEnum):
    """Stable failure categories independent of driver exception wording."""

    UPGRADE_REQUIRED = "database_upgrade_required"
    INCOMPATIBLE_SCHEMA = "database_incompatible_schema"
    BUSY = "database_busy"
    PERMISSION_DENIED = "database_permission_denied"
    INVALID_FILE = "database_invalid_file"
    IO_ERROR = "database_io_error"
    RESOURCES_UNAVAILABLE = "database_resources_unavailable"
    INITIALIZATION_FAILED = "database_initialization_failed"
    MIGRATION_FAILED = "database_migration_failed"


_MESSAGES = {
    DatabaseReason.MIGRATION_FAILED: (
        "Database schema migration did not complete. Preserve this database and inspect application diagnostics; "
        "the migration transaction was rolled back."
    ),
    DatabaseReason.UPGRADE_REQUIRED: (
        "Database schema upgrade required to revision {expected_revision}. This is a one-time upgrade of your "
        "existing local database, not new setup — your data is not lost. Back up the database file before "
        "upgrading it, and let any other process using it finish first."
    ),
    DatabaseReason.INCOMPATIBLE_SCHEMA: (
        "Database schema is incompatible or incomplete. Preserve this database and inspect it with the matching "
        "application version; automatic initialization was not performed."
    ),
    DatabaseReason.BUSY: (
        "The database is in use by another operation and did not become free within the configured wait. "
        "Close other database operations and retry."
    ),
    DatabaseReason.PERMISSION_DENIED: (
        "Database access was denied. Check permissions for the database file and its parent directory."
    ),
    DatabaseReason.INVALID_FILE: (
        "The database file is not a readable SQLite database or is corrupt. "
        "Preserve it and inspect or restore it before retrying."
    ),
    DatabaseReason.IO_ERROR: (
        "Database storage could not be accessed. Check the database location, available storage and filesystem health."
    ),
    DatabaseReason.RESOURCES_UNAVAILABLE: (
        "Database migration resources are unavailable or inconsistent. Use a complete matching source installation; "
        "the database was not initialized."
    ),
    DatabaseReason.INITIALIZATION_FAILED: (
        "Database fresh initialization did not complete. "
        "Preserve this file and inspect application diagnostics before retrying; "
        "no partial schema was accepted."
    ),
}
"""The message of each category: only the state of the database, with no command, option, variable or path.

A caller that can name a remedy or the target, as the command line does, adds them to this message itself; the target
is :attr:`DatabaseError.database_path`.
"""


class DatabaseError(RuntimeError):
    """Sanitized database error with read-only safe evidence and a chained cause."""

    def __init__(
        self, reason: DatabaseReason, database_path: Path | None, expected_revision: str | None = None
    ) -> None:
        """Retain the category/target without incorporating raw driver messages."""
        self._reason = reason
        self._database_path = database_path
        self._expected_revision = expected_revision
        message = _MESSAGES[reason]
        if reason is DatabaseReason.UPGRADE_REQUIRED:
            message = message.format(expected_revision=expected_revision or "the required revision")
        super().__init__(message)

    @property
    def reason(self) -> DatabaseReason:
        """Return the stable error category."""
        return self._reason

    @property
    def reason_code(self) -> FailureReasonCode:
        """Return the stable failure code of the category."""
        return FailureReasonCode(self._reason.value)

    @property
    def database_path(self) -> Path | None:
        """Return the configured target, never a fallback database."""
        return self._database_path

    @property
    def expected_revision(self) -> str | None:
        """Return the verified bundled revision, when readiness discovered it; null for a storage error."""
        return self._expected_revision


_REASON_BY_PRIMARY_CODE = {
    sqlite3.SQLITE_BUSY: DatabaseReason.BUSY,
    sqlite3.SQLITE_LOCKED: DatabaseReason.BUSY,
    sqlite3.SQLITE_READONLY: DatabaseReason.PERMISSION_DENIED,
    sqlite3.SQLITE_PERM: DatabaseReason.PERMISSION_DENIED,
    sqlite3.SQLITE_AUTH: DatabaseReason.PERMISSION_DENIED,
    sqlite3.SQLITE_NOTADB: DatabaseReason.INVALID_FILE,
    sqlite3.SQLITE_CORRUPT: DatabaseReason.INVALID_FILE,
    sqlite3.SQLITE_IOERR: DatabaseReason.IO_ERROR,
    sqlite3.SQLITE_FULL: DatabaseReason.IO_ERROR,
    sqlite3.SQLITE_CANTOPEN: DatabaseReason.IO_ERROR,
}
"""The category of each SQLite primary result code that is a storage error; any other code is not one."""


def storage_reason(error: Exception) -> DatabaseReason | None:
    """Return the category of a storage error, or ``None`` when the error is not one.

    A SQLite error is a storage error when its primary result code is busy or locked (``database_busy``); read-only,
    permission or auth (``database_permission_denied``); not a database or corrupt (``database_invalid_file``); or I/O
    error, full or can't-open (``database_io_error``). Any other SQLite error, such as a constraint violation or a
    programming error, is a defect and not a database state, so it has no category. A raw ``OSError`` is
    ``database_permission_denied`` for ``EACCES`` and ``EPERM`` and ``database_io_error`` otherwise, and the readiness
    lock's timeout is ``database_busy``.
    """
    if isinstance(error, ReadinessLockTimeoutError):
        return DatabaseReason.BUSY
    original = error.orig if isinstance(error, DBAPIError) else error
    code = getattr(original, "sqlite_errorcode", None)
    if isinstance(code, int):
        return _REASON_BY_PRIMARY_CODE.get(code & 0xFF)
    if isinstance(original, OSError):
        return (
            DatabaseReason.PERMISSION_DENIED
            if original.errno in (errno.EACCES, errno.EPERM)
            else DatabaseReason.IO_ERROR
        )
    return None
