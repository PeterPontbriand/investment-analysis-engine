# SQLite migrations

Run commands from the repository root in the synchronized project environment:

```powershell
uv run --no-sync alembic upgrade head
uv run --no-sync alembic current
```

These commands use `ProjectSettings.database_url`, including the existing
case-sensitive `database_url` environment override. Relative SQLite paths resolve
against `base_dir`. `alembic.ini` resolves script/import paths from its own location.
No logging configuration is installed or replaced by the migration environment.

For an isolated bootstrap check, use a new ignored temporary directory:

```powershell
$migrationCheck = Join-Path (Get-Location) ('.tmp/migration-checks/' + [guid]::NewGuid().ToString('N'))
$migrationUrl = 'sqlite:///' + (Join-Path $migrationCheck 'check.sqlite3').Replace('\', '/')
uv run --no-sync alembic -x "database_url=$migrationUrl" upgrade head
uv run --no-sync alembic -x "database_url=$migrationUrl" upgrade head
uv run --no-sync alembic -x "database_url=$migrationUrl" downgrade base
uv run --no-sync alembic -x "database_url=$migrationUrl" upgrade head
```

URL precedence: `-x database_url=...`, programmatic Alembic
`Config.set_main_option("sqlalchemy.url", ...)`, then application settings.
Programmatic Config values containing `%` require `%%` escaping for ConfigParser;
CLI `-x` values do not. Unknown `-x` names and invalid/empty overrides are errors.

The shared B1 boundary supplies WAL, foreign keys, bounded busy waiting, atomic
transactions, and cleanup. Failure rolls back the migration transaction and is
reported to the caller. Do not enable autocommit blocks or manually commit inside
revisions: the shared outer transaction owns commit/rollback.

The B3 revision `0001_persistence` creates `schema_metadata`, `trajectory_events`,
`resolved_input_cache`, `market_data_cache_entries`, and `market_price_observations`.
It seeds `persistence_encoding_version = 1`; `current` then reports the revision.
Repeated upgrade is a no-op. Downgrade to base removes all five application tables
and their contents, leaving only Alembic's empty revision table. Re-upgrade creates
a fresh schema. B3 awaits Gate B review; adapter implementation has not started.
Use downgrade checks only on disposable test databases; migrations against user
data require explicit approval.

Offline `--sql` mode is explicitly unsupported because it cannot establish or
verify the connection policy. Core metadata is available for schema comparison;
historical revision scripts independently freeze the schema they introduce.
The Mako file remains a revision-generation template, not a migration itself.
