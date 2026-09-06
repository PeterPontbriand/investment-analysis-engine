"""Online Alembic bootstrap using the shared SQLite transaction policy."""

from alembic import context
from src.config import ProjectSettings
from src.data.repositories.schema import metadata
from src.data.repositories.sqlite import SQLiteDatabase


def run_migrations() -> None:
    """Execute Alembic online with settings, optional URL override, and cleanup.

    URL precedence is CLI ``-x database_url=...``, Alembic's ``sqlalchemy.url``
    config option, then ProjectSettings (including its environment overrides).
    Offline SQL generation cannot verify connection policy and is unsupported.
    """
    if context.is_offline_mode():
        raise ValueError("Offline migrations are not supported; run against an explicit SQLite database.")
    arguments = context.get_x_argument(as_dictionary=True)
    unsupported = set(arguments) - {"database_url"}
    if unsupported:
        raise ValueError("Unsupported Alembic -x option; only database_url is accepted.")
    override = arguments.get("database_url", context.config.get_main_option("sqlalchemy.url"))
    settings = ProjectSettings() if override is None else ProjectSettings(database_url=override)
    database = SQLiteDatabase(settings)
    try:
        with database.transaction() as connection:
            context.configure(connection=connection, target_metadata=metadata, transactional_ddl=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        database.close()
