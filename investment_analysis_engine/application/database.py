"""The one opener of a readiness-checked database connection for an application operation."""

from collections.abc import Iterator
from contextlib import contextmanager

from investment_analysis_engine.application.context import ApplicationContext
from investment_analysis_engine.data.repositories.readiness import ensure_database_ready
from investment_analysis_engine.data.repositories.sqlite import SQLiteDatabase


@contextmanager
def open_database(context: ApplicationContext) -> Iterator[SQLiteDatabase]:
    """Open the context's database, check that it is ready, yield it and close it.

    Raises:
        DatabaseReadinessError: If the database is missing, busy or not at the expected revision; the error
            passes through unchanged.
    """
    database = SQLiteDatabase(context.settings)
    try:
        ensure_database_ready(database)
        yield database
    finally:
        database.close()


__all__ = ["open_database"]
