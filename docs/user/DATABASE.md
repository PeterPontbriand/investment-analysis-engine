# Local Database Operations

The CLI stores historical market-data snapshots and resolved financial inputs
in SQLite through shared persistence interfaces. Trajectory telemetry defaults to JSONL; SQLite telemetry is
optional. Database schemas are prepared explicitly with Alembic. Analysis
commands do not create tables or run migrations automatically.

## Prepare or update an installation

Current financial quotes use `quote_cache_ttl_seconds` (default 300 seconds), measured from the original provider response retrieval. Zero disables quote reuse. Unknown, future or expired response timing triggers refresh without stale fallback. This policy is separate from annual financial-input and historical-snapshot cache settings. Legacy quote keys refresh automatically without a schema migration; retrieval time does not establish an exchange trade timestamp.

Run these commands from the installation folder, after stopping application
processes. Back up an existing database before upgrading it.

```powershell
uv sync --locked
uv run --no-sync alembic upgrade head
uv run --no-sync alembic current
```

Dependency synchronization installs the versions in the existing lockfile.
`upgrade head` creates a fresh schema or applies pending migrations; repeating
it on an up-to-date database is safe. The initial revision is
`0001_persistence`. `current` reports the installed revision. Help commands alone
do not verify that the database is prepared.

Managed verification uses the already synchronized environment and does not
install dependencies. Dependency installation and migrations against a user's
existing data are separate operator actions.

## Choose the database location

The default file is `data/financial-data-agents.sqlite3` under the installation
folder (or the configured `DATA_DIR`). A relative `DATABASE_URL` resolves against
the configured application base directory, not the terminal's current folder.
Set the same URL for migrations and subsequent analysis commands.

PowerShell example:

```powershell
$env:DATABASE_URL = "sqlite:///E:/FinancialData/financial-data-agents.sqlite3"
uv run --no-sync alembic upgrade head
uv run --no-sync alembic current
```

Bash example:

```bash
export DATABASE_URL="sqlite:////srv/financial-data/financial-data-agents.sqlite3"
uv run --no-sync alembic upgrade head
```

The environment setting lasts for the terminal session. Add `DATABASE_URL` to
local `.env` configuration to retain it. The directory must be writable.
Synchronous local SQLite URLs are supported; remote database URLs and SQLite
URI query parameters are not.

A one-command migration override is also available:

```powershell
uv run --no-sync alembic -x "database_url=sqlite:///E:/FinancialData/trial.sqlite3" upgrade head
```

That override affects only Alembic. It does not redirect later analysis commands.
Migration URL precedence is `-x database_url`, an explicit Alembic
`sqlalchemy.url`, then application settings.

## Cache and telemetry behavior

- Historical reuse requires the same ticker, provider, request dates, and daily
  adjusted-price configuration. Other ranges refetch in full. The default
  `HISTORICAL_CACHE_TTL_SECONDS` is 3600; zero permits no positive cache age.
  Programmatic `ProjectSettings(..., historical_cache_ttl_seconds=None)` disables
  expiry. Failed fetches never substitute a stale snapshot. Empty or invalid
  observations are not persisted; valid unsupported frame shapes bypass caching.
- Financial caches retain the existing no-TTL policy and resolver temporal
  eligibility checks. Commands that support `--no-cache` bypass resolved-input
  cache reads and writes without opening that cache's SQLite database. Check
  the command's `--help` for availability; use this option when refreshed
  financial facts are required. Cache reuse preserves provider provenance and reports cache resolution.
- Historical prices do not become live quotes. Quote requests and optional
  instrument-profile enrichment retain their provider boundaries.
- `TELEMETRY_SINK=sqlite` selects SQLite trajectory storage where the runtime
  creates a recorder. `TELEMETRY_SINK=jsonl` is the default;
  `TELEMETRY_LEVEL=OFF` disables recording. Telemetry failures remain fail-open;
  they do not make a missing database schema acceptable for financial caches.

`DATABASE_BUSY_TIMEOUT_MS` defaults to 5000. Connections enable foreign keys and
WAL journaling. Transactions keep related rows atomic; caches do not import
benchmark fixtures as production data.

## Back up and restore

Stop all processes using the database before a filesystem backup or restore.
SQLite WAL files can contain committed changes that have not reached the main
file. Do not copy just the main file while writers are active, and do not delete
`-wal` or `-shm` files to fix a lock error.

After every connection has closed, copy the database and any remaining matching
`-wal` and `-shm` sidecars together into a new backup directory. Keep their names
and record the application revision and Alembic revision with the backup. If
shutdown was interrupted and sidecars remain, preserve the complete set before
attempting recovery. A backup made while the application is running instead
requires a SQLite-aware consistent backup mechanism, not sequential file copies.

Restore only with all application processes stopped. Preserve the current file
set first, then restore the matching backup set into a clean destination and
point `DATABASE_URL` there. Do not mix sidecars from different backups. Check
`alembic current`, review the needed migrations, and upgrade with compatible
application code before resuming analysis. Database files and operational logs
are local artifacts and must not be committed to Git.

## Downgrade and failed migrations

Inspect history before changing revisions:

```powershell
uv run --no-sync alembic history
uv run --no-sync alembic current
```

Downgrading to `base` removes the persistence tables and their data. Use the
following only for an explicitly disposable database or after approving data
loss and retaining a verified backup:

```powershell
uv run --no-sync alembic -x "database_url=sqlite:///data/disposable.sqlite3" downgrade base
uv run --no-sync alembic -x "database_url=sqlite:///data/disposable.sqlite3" upgrade head
```

A failed migration is rolled back through the shared SQLite transaction scope.
Stop competing processes, preserve the error and database file set, and check
permissions, free space, the selected URL, and `alembic current`. Correct the
cause and rerun the same upgrade. Do not use `alembic stamp head` to conceal a
failure or manually edit the revision table. If the database's integrity is in
doubt, retain it for diagnosis and restore a consistent backup into a separate
location before retrying. An unexpected analysis failure after an update may
indicate an unmigrated database; compare its revision with `alembic history`.

## Offline persistence verification

The integrated test creates and migrates a temporary database, writes telemetry,
a resolved financial input and historical observations, closes/reopens storage,
checks exact readback and database integrity, and verifies downgrade/re-upgrade.
It blocks socket connections and uses synthetic data. It never targets the
configured operational database or contacts a provider or local LLM.

The complete managed gate includes this test and the migration lifecycle,
rollback, cache, and CLI composition suites:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

Git Bash:

```bash
bash "$(git rev-parse --show-toplevel)/scripts/run-quality-gates.sh"
```

Each invocation writes isolated ignored artifacts below `.tmp/quality-runs/`.
The suite reports its test count, coverage, and artifact path. Live-provider
checks in [Smoke Testing Commands](SMOKE_TESTING.md) are separate human-run
checks and are not part of this offline verification.
