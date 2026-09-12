"""Online Alembic bootstrap using the shared SQLite transaction policy."""

from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection

from alembic import command, context
from src.config import ProjectSettings
from src.data.repositories.readiness_lock import readiness_lock
from src.data.repositories.schema import metadata
from src.data.repositories.sqlite import SQLiteDatabase


@dataclass(frozen=True)
class MigrationResources:
    """Validated source-installation migration location and revision graph."""

    directory: Path
    head: str
    ancestors: frozenset[str]


def migration_resources() -> MigrationResources:
    """Find the unique bundled head independently of cwd and database settings."""
    directory = Path(__file__).resolve().parents[3] / "alembic"
    if not (directory / "env.py").is_file() or not (directory / "versions").is_dir():
        raise ValueError("Bundled migration resources are missing.")
    script = ScriptDirectory(str(directory))
    heads = script.get_heads()
    if len(heads) != 1:
        raise ValueError("Bundled migrations must have exactly one head.")
    head = heads[0]
    ancestors = frozenset(item.revision for item in script.walk_revisions() if item.revision != head)
    return MigrationResources(directory, head, ancestors)


def upgrade_fresh_database(connection: Connection) -> None:
    """Upgrade using a caller-owned transaction without creating another engine."""
    if not connection.in_transaction():
        raise ValueError("Fresh initialization requires an active transaction.")
    resources = migration_resources()
    upgrade_database_revision(connection, resources, resources.head)


def upgrade_database_revision(connection: Connection, resources: MigrationResources, revision: str) -> None:
    """Run a bundled revision in an active transaction owned by the caller."""
    if not connection.in_transaction():
        raise ValueError("Migration requires an active transaction.")
    config = Config(stdout=StringIO())
    config.set_main_option("script_location", str(resources.directory).replace("%", "%%"))
    config.attributes["connection"] = connection
    command.upgrade(config, revision)


def _run_on_connection(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=metadata, transactional_ddl=True)
    with context.begin_transaction():
        context.run_migrations()


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
    if "connection" in context.config.attributes:
        borrowed = context.config.attributes["connection"]
        if not isinstance(borrowed, Connection) or not borrowed.in_transaction():
            raise ValueError("Borrowed migrations require an active SQLAlchemy connection.")
        if override is not None:
            raise ValueError("URL overrides cannot accompany a borrowed migration connection.")
        _run_on_connection(borrowed)
        return
    settings = ProjectSettings() if override is None else ProjectSettings(database_url=override)
    database = SQLiteDatabase(settings)
    try:
        with readiness_lock(database.database_path, database.busy_timeout_ms), database.transaction() as connection:
            _run_on_connection(connection)
    finally:
        database.close()
