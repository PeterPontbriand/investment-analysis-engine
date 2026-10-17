# Local Database Operations

The CLI stores historical market-data snapshots and resolved financial inputs
in SQLite through shared persistence interfaces. Trajectory telemetry defaults to JSONL; SQLite telemetry is
optional. When required persistence is first used, the application initializes
a missing or verified empty database through the Alembic migrations that ship inside the package. Ready
storage is reused without migration. Existing schemas are never upgraded
automatically; incompatible or incomplete storage is preserved and rejected.

## First use and explicit upgrades

No database preparation command is required for a fresh installation. Configure
the location before the first analysis. Freshness is checked from schema objects,
not file size: an empty revision table, partial schema or unrelated tables/views
are not fresh. A revision stamp alone does not prove readiness.

Maintenance commands are hidden from top-level help but available explicitly:

```powershell
ian db --help
ian db status
ian db status --json
```

`db status` inspects without initializing, upgrading, enabling WAL or creating
the target, parent directory or readiness lock. It reports `missing`, `fresh`,
`ready`, `upgrade_required` or `incompatible`. Inspection is a consistent snapshot,
not a reservation; SQLite may still need normal journal/shared-memory access.

To initialize in advance or explicitly upgrade supported existing storage, stop
application processes and back up existing data, then run:

```powershell
ian db upgrade
```

The command initializes fresh storage, upgrades a structurally valid recognized
ancestor, or succeeds without changes when already ready. It does not prompt for
confirmation. Unknown/newer revisions, unversioned nonempty storage and schema
drift require inspection with matching application code, not a blind upgrade.
The bundle holds five revisions, `0001_persistence` to `0005_remove_cancelled_outcome`,
and a database at any earlier one upgrades in place. The last revision rebuilds the
run table without the `cancelled` outcome that no run ever had; it stops and changes
nothing if a stored run somehow holds that outcome. Upgrade behavior is tested with
synthetic migration history.

Both maintenance commands accept `--database-url` and `--json`. An override is
for that invocation only; it does not redirect later analyses:

```powershell
ian db status --database-url "sqlite:///E:/FinancialData/trial.sqlite3" --json
ian db upgrade --database-url "sqlite:///E:/FinancialData/trial.sqlite3"
```

A relative path in `--database-url` is resolved against the folder the command runs in. A Windows path that is only
partly anchored is rejected, as described under [Choose the database location](#choose-the-database-location).

Exit 0 means ready or successfully initialized/upgraded; exit 1 means not ready
or an operational failure, including a rejected `--database-url`; exit 2 means the parser rejected the command line. A completed
inspection of non-ready storage has report `status=success` but exit 1. JSON
reports have `schema_version=2`, `command`, `status`, `database_path`, `state`,
`current_revision`, `expected_revision`, `reason_code` (the stable code) and `reason`
(a sentence for people); unavailable fields are null. Version 1 named the code
`reason` and the sentence `message`, so a reader written for version 1 must check
`schema_version` first: `reason` now holds the sentence. The report shares the failure
envelope's names and its code vocabulary; the published schema is
`schemas/database-maintenance-report.schema.json`. Upgrade success states are `initialized`, `upgraded` and `ready`.
Untrusted revision strings are not exposed. JSON operational reports use stdout
only, without migration chatter. Text reports use stdout, operational failures
stderr; parser-level usage errors retain normal CLI behavior (exit 2). A `--database-url` the command rejects, or a private-memory target, is not a maintenance report: it is the failure document (`reason_code` `invalid_parameter` with `parameters` `["--database-url"]`; a private-memory target that came from the settings is `configuration_error`), so `--json` can write a maintenance report or a failure document, told apart by the `command` key, which only the report has.

Current financial quotes use `IAN_QUOTE_CACHE_TTL_SECONDS` (default 300 seconds), measured from the original provider response retrieval. Zero disables quote reuse. Unknown, future or expired response timing triggers refresh without stale fallback. This policy is separate from annual financial-input and historical-snapshot cache settings. Legacy quote keys refresh automatically without a schema migration; retrieval time does not establish an exchange trade timestamp.

## Choose the database location

The default file is `investment-analysis-engine.sqlite3` in your per-user data folder:

| System | Data folder |
| :--- | :--- |
| Windows | `%LOCALAPPDATA%\investment-analysis-engine` |
| macOS | `~/Library/Application Support/investment-analysis-engine` |
| Linux | `$XDG_DATA_HOME/investment-analysis-engine` (usually `~/.local/share/investment-analysis-engine`) |

The folder is created when the database is first needed. Three settings change the location, highest first:

1. `--database-url` on an `ian db` command, for that command only;
2. `IAN_DATABASE_URL`, the full SQLite URL;
3. `IAN_DATA_DIR`, a folder that holds the default file name.

`IAN_DATA_DIR` and the file path in `IAN_DATABASE_URL` must be absolute paths; a relative path stops the application at
startup with a message that names the variable. Set the same URL for `ian db upgrade` and for every analysis command.

PowerShell example:

```powershell
$env:IAN_DATABASE_URL = "sqlite:///E:/FinancialData/investment-analysis-engine.sqlite3"
ian db upgrade
ian db status
```

Linux or macOS example:

```bash
export IAN_DATABASE_URL="sqlite:////srv/financial-data/investment-analysis-engine.sqlite3"
ian db upgrade
```

Git Bash on Windows example:

```bash
export IAN_DATABASE_URL="sqlite:///E:/FinancialData/investment-analysis-engine.sqlite3"
ian db upgrade
```

On Windows, a path that has a root but no drive letter (such as `/e/FinancialData/...`,
which is how Git Bash writes paths) is rejected, because Windows would place it under
the root of the current drive. The message suggests the full path; `cygpath -m <path>`
converts a Git Bash path to the form to use. A path with a drive letter but no root
(`E:data`) is rejected for the same reason.

The environment setting lasts for the terminal session. Add `IAN_DATABASE_URL` to the
`.env` file in your settings folder to retain it (see [Installation](INSTALLATION.md#where-the-application-keeps-its-files)).
The folder must be writable. Synchronous local SQLite URLs are supported; remote database URLs and SQLite
URI query parameters are not.

## Cache and telemetry behavior

- Historical reuse requires the same ticker, provider, request dates, and daily
  adjusted-price configuration. Other ranges refetch in full. The default
  `IAN_HISTORICAL_CACHE_TTL_SECONDS` is 3600; zero permits no positive cache age.
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
- `IAN_TELEMETRY_SINK=sqlite` selects SQLite trajectory storage where the runtime
  creates a recorder. `IAN_TELEMETRY_SINK=jsonl` is the default;
  `IAN_TELEMETRY_LEVEL=OFF` disables recording. Telemetry failures remain fail-open;
  they do not initialize storage or control analysis readiness. If SQLite is used
  only for telemetry, explicitly prepare its target with `db upgrade` first.

`IAN_DATABASE_BUSY_TIMEOUT_MS` defaults to 5000. Connections enable foreign keys and
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
analysis failures retain their versioned failure envelope (`schema_version=7`) with
`status=error`, `result=null` and a stable `reason_code`, without initialization
chatter. A `database_*` code also carries `database`, holding `database_path` and
`expected_revision` as separate fields, so a caller need not read them from the
sentence. The envelope reports the condition and never upgrades the database; the
published schema is `schemas/failure.schema.json`.

| Reason | Next action |
| :--- | :--- |
| `database_upgrade_required` | Stop processes, back up, and explicitly upgrade the same configured target. |
| `database_incompatible_schema` | Preserve contents and inspect with matching application code; do not stamp or blindly upgrade. |
| `database_busy` | Close competing database operations and retry after the bounded wait. Do not delete lock or WAL sidecars. |
| `database_permission_denied` | Check file and parent-directory permissions. |
| `database_invalid_file` | Preserve the unreadable/corrupt file; inspect or restore a consistent backup. |
| `database_io_error` | Check the path, free space and filesystem health. |
| `database_resources_unavailable` | Reinstall the application; the migrations ship inside the package. |
| `database_initialization_failed` | Preserve the file and inspect diagnostics; no partial schema was accepted. |
| `database_migration_failed` | Preserve the database and inspect diagnostics; the migration transaction was rolled back. |

There is no fallback database, automatic repair, downgrade, deletion or existing-data
upgrade. Retry interrupted initialization only after resolving the cause; the next
inspection must prove fresh or ready storage before analysis can proceed.

Maintenance requires file-backed storage and rejects private in-memory URLs.
Programmatic readiness supports memory only on the same `SQLiteDatabase` instance.
The migrations ship inside the installed package, so an installed wheel and a source checkout
both migrate. Local verification covers Windows locking, not POSIX execution,
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
point `IAN_DATABASE_URL` there. Do not mix sidecars from different backups. Check
`ian db status`, review the needed migrations, and upgrade with compatible
application code before resuming analysis. Database files and operational logs
are local artifacts and must not be committed to Git.

## Failed migrations

A failed migration is rolled back through the shared SQLite transaction scope.
Stop competing processes, preserve the error and database file set, and check
permissions, free space, the selected URL, and `ian db status`. Correct the
cause and rerun `ian db upgrade`. Never edit the revision table by hand or mark a
failed database as current. If the database's integrity is in
doubt, retain it for diagnosis and restore a consistent backup into a separate
location before retrying. Use `ian db status` to inspect readiness after an update.

## For developers: Alembic from a checkout

The migration scripts are in `investment_analysis_engine/data/repositories/migration_scripts/`, and the `alembic.ini` at the
repository root points at them. Run these commands from a repository checkout, in the synchronized project
environment, after stopping application processes and backing up an existing database:

```powershell
uv sync --locked
uv run --no-sync alembic upgrade head
uv run --no-sync alembic current
uv run --no-sync alembic history
```

They use the same database as the application: `IAN_DATABASE_URL`, else the default file in `IAN_DATA_DIR`. A one-command
override affects only Alembic and does not redirect later analysis commands. The path in it must be absolute:

```powershell
uv run --no-sync alembic -x "database_url=sqlite:///E:/FinancialData/trial.sqlite3" upgrade head
```

Migration URL precedence is `-x database_url`, an explicit Alembic `sqlalchemy.url`, then application settings.

Downgrading to `base` removes the persistence tables and their data. Use the following only for an explicitly
disposable database or after approving data loss and retaining a verified backup:

```powershell
uv run --no-sync alembic -x "database_url=sqlite:///E:/FinancialData/disposable.sqlite3" downgrade base
uv run --no-sync alembic -x "database_url=sqlite:///E:/FinancialData/disposable.sqlite3" upgrade head
```

Do not use `alembic stamp head` to conceal a failure.

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
