# Local Database Operations

The CLI stores historical market-data snapshots and resolved financial inputs
in SQLite through shared persistence interfaces. Trajectory telemetry defaults to JSONL; SQLite telemetry is
optional. When required persistence is first used, the application initializes
a missing or verified empty database through bundled Alembic migrations. Ready
storage is reused without migration. Existing schemas are never upgraded
automatically; incompatible or incomplete storage is preserved and rejected.

## First use and explicit upgrades

No database preparation command is required for a fresh installation. Configure
the location before the first analysis. Freshness is checked from schema objects,
not file size: an empty revision table, partial schema or unrelated tables/views
are not fresh. A revision stamp alone does not prove readiness.

Maintenance commands are hidden from top-level help but available explicitly:

```powershell
uv run --no-sync ian db --help
uv run --no-sync ian db status
uv run --no-sync ian db status --json
```

`db status` inspects without initializing, upgrading, enabling WAL or creating
the target, parent directory or readiness lock. It reports `missing`, `fresh`,
`ready`, `upgrade_required` or `incompatible`. Inspection is a consistent snapshot,
not a reservation; SQLite may still need normal journal/shared-memory access.

To initialize in advance or explicitly upgrade supported existing storage, stop
application processes and back up existing data, then run:

```powershell
uv run --no-sync ian db upgrade
```

The command initializes fresh storage, upgrades a structurally valid recognized
ancestor, or succeeds without changes when already ready. It does not prompt for
confirmation. Unknown/newer revisions, unversioned nonempty storage and schema
drift require inspection with matching application code, not a blind upgrade.
The current bundle contains only `0001_persistence`; older-production-revision
upgrades are not presently available. Upgrade behavior is tested with synthetic
migration history.

Both maintenance commands accept `--database-url` and `--json`. An override is
for that invocation only; it does not redirect later analyses:

```powershell
uv run --no-sync ian db status --database-url "sqlite:///E:/FinancialData/trial.sqlite3" --json
uv run --no-sync ian db upgrade --database-url "sqlite:///E:/FinancialData/trial.sqlite3"
```

Exit 0 means ready or successfully initialized/upgraded; exit 1 means not ready
or an operational failure; exit 2 means invalid usage/configuration. A completed
inspection of non-ready storage has report `status=success` but exit 1. JSON
reports have `schema_version=1`, `command`, `status`, `database_path`, `state`,
`current_revision`, `expected_revision`, `reason` and `message`; unavailable fields
are null. Upgrade success states are `initialized`, `upgraded` and `ready`.
Untrusted revision strings are not exposed. JSON operational reports use stdout
only, without migration chatter. Text reports use stdout, operational failures
stderr; parser-level usage errors retain normal CLI behavior.

Direct Alembic commands remain available for explicit operator maintenance.

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

The default file is `data/investment-analysis-engine.sqlite3` under the installation
folder (or the configured `DATA_DIR`). A relative `database_url` resolves against
the configured application base directory, not the terminal's current folder.
Set the same URL for migrations and subsequent analysis commands.

PowerShell example:

```powershell
$env:database_url = "sqlite:///E:/FinancialData/investment-analysis-engine.sqlite3"
uv run --no-sync alembic upgrade head
uv run --no-sync alembic current
```

Bash example:

```bash
export database_url="sqlite:////srv/financial-data/investment-analysis-engine.sqlite3"
uv run --no-sync alembic upgrade head
```

The environment setting lasts for the terminal session. Add `database_url` to
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
- `telemetry_sink=sqlite` selects SQLite trajectory storage where the runtime
  creates a recorder. `telemetry_sink=jsonl` is the default;
  `telemetry_level=OFF` disables recording. Telemetry failures remain fail-open;
  they do not initialize storage or control analysis readiness. If SQLite is used
  only for telemetry, explicitly prepare its target with `db upgrade` first.

`DATABASE_BUSY_TIMEOUT_MS` defaults to 5000. Connections enable foreign keys and
WAL journaling. Transactions keep related rows atomic; caches do not import
benchmark fixtures as production data.

Help, imports and storage-free operations do not initialize the database.
Financial `--no-cache` bypasses that cache only, not unrelated persistence.
Concurrent initialization and maintenance coordinate through the persistent
`<database>.readiness.lock` sidecar, recheck storage after ownership, and verify
revision and structure before committing. Closing the handle or terminating the
owner releases its operating-system lock. **Do not delete the sidecar as stale**;
its stable pathname is part of coordination. Keep it out of Git.

## Readiness errors and recovery

Analysis readiness failures exit 1 with an actionable sanitized target and reason,
including in ordinary output; `--diagnostics` remains analysis-focused. JSON
analysis failures retain their versioned analysis envelope with `status=error`,
`result=null` and a stable reason code, without initialization chatter.

| Reason | Next action |
| :--- | :--- |
| `database_upgrade_required` | Stop processes, back up, and explicitly upgrade the same configured target. |
| `database_incompatible_schema` | Preserve contents and inspect with matching application code; do not stamp or blindly upgrade. |
| `database_busy` | Close competing database operations and retry after the bounded wait. Do not delete lock or WAL sidecars. |
| `database_permission_denied` | Check file and parent-directory permissions. |
| `database_invalid_file` | Preserve the unreadable/corrupt file; inspect or restore a consistent backup. |
| `database_io_error` | Check the path, free space and filesystem health. |
| `database_resources_unavailable` | Use a complete matching source installation with bundled migrations. |
| `database_initialization_failed` | Preserve the file and inspect diagnostics; no partial schema was accepted. |
| `database_migration_failed` | Preserve the database and inspect diagnostics; the migration transaction was rolled back. |

There is no fallback database, automatic repair, downgrade, deletion or existing-data
upgrade. Retry interrupted initialization only after resolving the cause; the next
inspection must prove fresh or ready storage before analysis can proceed.

Maintenance requires file-backed storage and rejects private in-memory URLs.
Programmatic readiness supports memory only on the same `SQLiteDatabase` instance.
Source-checkout/editable installations with bundled migration resources are the
verified installation boundary; standalone wheel migration packaging is not
provided. Local verification covers Windows locking, not POSIX execution,
network filesystems, hard-link aliases or external file replacement.

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
point `database_url` there. Do not mix sidecars from different backups. Check
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
location before retrying. Use `db status` to inspect readiness after an update.

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
checks in [Smoke Testing Commands](SMOKE_TESTING.md) are separate user-run
checks and are not part of this offline verification.
