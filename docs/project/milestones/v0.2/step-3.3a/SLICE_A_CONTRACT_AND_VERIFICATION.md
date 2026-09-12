# Step 3.3A Slice A — Concrete readiness contract and verification

**Status:** Gate A approved and Slice B implementation explicitly authorized by the project owner on 2026-09-12: “Gate A is approved and Slice B implementation is authorized. Proceed.” The approved contract was checkpointed at `d912d4d`. Implementation proceeds on `codex/step-3.3a-readiness`; Slice B was approved and Slice C authorized on 2026-09-12, including the [hidden maintenance amendment](SLICE_C_MAINTENANCE_AMENDMENT.md). No production source, permanent tests, dependencies or migration revisions changed during Slice A.

**Authority:** [Step 3.3A contract and gates](STEP_3_3A_CONTRACT_AND_SLICE_PLAN.md). ESC-C is accepted. The project owner created `docs/step-3.3a-contract-planning` and explicitly authorized Slice A planning and verification. Source examined: `634164b` (merged PR #34), with a clean initial working tree. This document freezes the proposed implementation choices for review; it does not approve itself.

## 1. Source reconciliation and caller inventory

| Boundary | Current behavior | Required change / disposition |
| :--- | :--- | :--- |
| `src/cli_support.py::_production_financial_cache` | Constructs a lazy database and yields a cache without checking its schema. Used by Number, Growth and FCF. `enabled=False` returns an in-memory cache before constructing SQLite. | Call readiness inside the existing `try/finally`, before yielding the durable cache. Keep the disabled branch ahead of all database/resource/lock work. |
| `src/cli_support.py::_production_historical_client` | Owns SQLite market storage and wraps the supplied Yahoo client. | Ensure readiness before yielding the wrapper. Provider construction is permitted, but no network fetch may precede readiness. |
| `src/cli.py` | All four commands already wrap those context managers in `execution_errors`; Number/Growth construct financial providers afterward, FCF composes its provider/profile afterward, Momentum fetches after entering its context. | Existing context order is sufficient. Add no strategy-specific readiness calls or provider changes. CLI integration tests must prove zero provider calls on readiness failure. |
| `src/data/repositories/sqlite.py::SQLiteDatabase` | Constructor is lazy. First connection creates parent directories, enables WAL/foreign keys/busy timeout, then uses Python modern transaction control. | Preserve normal read/transaction behavior. Expose read-only resolved path and timeout properties for readiness. Readiness must inspect existing storage before using this connection factory, because setting WAL changes file state. |
| `src/data/repositories/migrations.py::run_migrations` / `alembic/env.py` | Always constructs and owns a new database, including for programmatic Alembic calls. Uses transactional DDL and an explicit transaction. | Add the borrowed-connection branch below and shared migration-resource helper. Manual invocation retains URL precedence and ownership. |
| `src/core/telemetry/recorder.py::from_settings`, SQLite sink/repository | Optional SQLite telemetry opens lazily and recorder failures are swallowed. It does not own business cache readiness. | No automatic initialization or new readiness dependency. Preserve fail-open behavior. Telemetry may still attempt its existing writes; an absent schema must never initiate migration through telemetry. |
| `src/orchestrator/analysis_tools.py` | Handlers receive analyzers/resolvers through `AnalysisToolDependencies`; they do not construct SQLite. | Dependency owners remain responsible for readiness. No handler-side database lookup or implicit constructor migration. |
| `src/evaluation/composition.py` | Builds fixture/in-memory dependencies. | No readiness calls; evaluation must remain storage-independent except its existing optional telemetry. |
| `src/main.py` | Sets up logging and dispatches CLI; no required database construction. | No global initialization. Help/import and storage-free commands remain free of cache readiness work. Existing unrelated logging/bootstrap code is outside scope. |

Repository constructors remain side-effect free with respect to schema creation. Direct repository users explicitly call readiness or manually prepare their schema. There is no second production runtime persistence factory in this revision; the source inventory found the two CLI owners, manual migration owner and optional telemetry owner above.

## 2. Typed boundary and exact file scope

The proposed public additions are deliberately narrow:

```python
# src/data/repositories/readiness.py
class ReadinessOutcome(StrEnum):
    READY = "ready"
    INITIALIZED = "initialized"


class ReadinessReason(StrEnum):
    UPGRADE_REQUIRED = "database_upgrade_required"
    INCOMPATIBLE_SCHEMA = "database_incompatible_schema"
    BUSY = "database_busy"
    PERMISSION_DENIED = "database_permission_denied"
    INVALID_FILE = "database_invalid_file"
    IO_ERROR = "database_io_error"
    RESOURCES_UNAVAILABLE = "database_resources_unavailable"
    INITIALIZATION_FAILED = "database_initialization_failed"


def ensure_database_ready(database: SQLiteDatabase) -> ReadinessOutcome: ...


class DatabaseReadinessError(RuntimeError):
    # Read-only, typed attributes; constructor sets a sanitized message.
    reason: ReadinessReason
    database_path: Path | None
    expected_revision: str | None


# SQLiteDatabase: no setters; values come from the already resolved instance.
@property
def database_path(self) -> Path | None: ...
@property
def busy_timeout_ms(self) -> int: ...
```

`None` path means the same instance's private in-memory database, never a default disk fallback. No readiness-success cache survives a call: check each newly composed database owner. Return an outcome rather than logging a success preamble. Error causes are chained internally; raw exception messages are not public fields.

| Slice | File allowlist and bounded purpose |
| :--- | :--- |
| B | New `src/data/repositories/readiness.py`: classification, schema signature, typed outcomes/errors and orchestration. New `src/data/repositories/readiness_lock.py`: private cross-process ownership helper and typed polling policy. `sqlite.py`: two read-only properties only, unless a demonstrated memory-scope defect requires a reviewed expansion. `migrations.py`: resource discovery, programmatic fresh upgrade and borrowed/manual branches. `__init__.py`: export the readiness API. |
| B tests | New `tests/data/repositories/test_readiness.py` and `test_readiness_concurrency.py`; extend `test_migrations.py`, `test_sqlite.py`, `test_schema.py` only for the new seams. Synthetic migration graphs/failure hooks stay in tests. |
| C | Extended by the [authorized maintenance amendment](SLICE_C_MAINTENANCE_AMENDMENT.md), which adds hidden commands and inspection/explicit-upgrade seams. `src/cli_support.py`: two composition calls and typed exception translation. New `tests/test_cli_database_readiness.py`; adjust existing financial/historical-cache, CLI-support and failure-output tests where their setup/expectations require it. Add fail-open assertions to `tests/core/telemetry/test_sqlite_sink.py` only as needed. |
| D | README, `docs/user/INSTALLATION.md`, `QUICKSTART.md`, `DATABASE.md`, `SMOKE_TESTING.md`, `docs/project/ARCHITECTURE.md`, and these milestone records. Update applicable ownership docstrings in files already in scope. |

Except for the subsequently authorized `src/cli.py` registration and repository seams in the [Slice C amendment](SLICE_C_MAINTENANCE_AMENDMENT.md), reporting serializers, financial algorithms, provider adapters, schema metadata definitions, frozen migration `0001_persistence.py`, `alembic/env.py`, `alembic.ini`, configuration defaults, `pyproject.toml` and `uv.lock` need no production edits under this contract. The existing Alembic environment delegates to the module being changed. No table, schema version, dependency or standalone packaging change is proposed. Any necessary expansion must be explained before its dependent edits.

## 3. State classification and schema invariants

Resolve the target exactly once through `ProjectSettings` and retain the same `SQLiteDatabase` through checking, initialization and repository use. Its current normalization anchors relative paths to `base_dir`, rejects URL credentials/host/query parameters and rejects SQLite URI configuration. Do not reconstruct settings inside automatic initialization.

For file storage, acquire ownership before inspection. If the path exists, open a short-lived `sqlite3` read-only URI connection (`Path.as_uri()` plus `mode=ro`, `uri=True`) with the configured busy timeout. This URI is an internal safe access mechanism, not newly accepted user URI configuration. Inspect in one explicit read transaction; close it before opening the normal application connection. Do not enable WAL, create schema, write pragmas or run repair against rejected storage. A missing path is a candidate for fresh creation, not authorization until the locked recheck. Zero-byte and valid-empty SQLite files are inspected, never classified from size.

Read `sqlite_schema` for all table/view/index/trigger objects. Ignore only SQLite-owned names beginning `sqlite_`; SQLite reserves that namespace. Everything else counts as user/application state. An `alembic_version` table with no rows is **not fresh**, including after manual downgrade to base. `sqlite_sequence` alone or planner statistics alone do not prove application state; absent non-internal objects means fresh. Tests must cover internal objects and non-table user objects explicitly.

Current expected revision is the unique bundled head, `0001_persistence`. Required non-internal tables are `alembic_version`, `schema_metadata`, `trajectory_events`, `resolved_input_cache`, `market_data_cache_entries`, and `market_price_observations`.

- **Fresh:** no non-internal objects. Initialize only this state.
- **Ready:** exactly one expected revision row; the five application tables match their canonical structural signatures; the version table has its expected column and primary key; metadata includes exactly the required `persistence_encoding_version=1` entry. Additional metadata keys may coexist, but duplicate/invalid required values may not.
- **Upgrade required:** exactly one revision known to be a proper ancestor of the bundled head, with recognizable application tables and version metadata. There is no older deployed revision in the current one-revision graph. Test this branch with a synthetic two-revision graph, not a new production migration. Missing version metadata or obviously partial storage is incompatible, not a prompt to blindly upgrade.
- **Incompatible:** unrelated/partial schema, unknown or newer revision, multiple/empty version rows, divergent heads, current revision with schema drift or unsupported metadata encoding. Preserve all contents.

For the expected revision, compare reflected names/order/types/nullability/defaults, primary keys, unique constraints, foreign keys, indexes and check constraints with `schema.py` metadata using the same signature categories as `test_schema.py::schema_signature`. Normalize SQL whitespace and dialect representation only; do not weaken constraints to make mismatches pass. No `create_all` or scratch reference schema is used at production runtime. Extra non-internal tables/views/triggers or unexpected application-table columns/indexes are incompatible at this frozen schema revision. Unknown metadata keys alone remain permissible as above. No full integrity scan or cache-row traversal occurs during startup; existing payload validation owns row quality.

After fresh migration, run the same revision/signature/metadata check inside the still-open migration transaction. A failure rolls back and becomes `database_initialization_failed`. Schema inspection is bounded by schema size, not stored financial or trajectory row counts.

## 4. Ownership, transaction and recovery algorithm

Use a persistent sibling file `<database filename>.readiness.lock`. Acquire it with standard-library OS locks: on Windows, nonblocking `msvcrt.locking` for byte 0, length 1; on POSIX, `fcntl.flock(LOCK_EX | LOCK_NB)`. Imports are platform-conditional at module scope. Open without truncation; lock contents/PIDs are not evidence of ownership. Locks may cover byte zero of an empty file. **Never unlink the sidecar on release or remove it as stale**: the OS releases the lock when its handle/process closes, and a persistent pathname prevents two processes locking different replacement files.

Reuse `database_busy_timeout_ms` (default 5,000 ms) as the ownership wait limit. A private frozen `ReadinessLockPolicy` names/documents a 0.05-second polling interval; clamp each wait to the monotonic deadline. Retry only OS codes meaning lock contention; permission and other errors are terminal. No unbounded blocking lock call, PID polling, recursive initialization retry or new setting/dependency. SQLite's existing busy timeout separately bounds database lock waits; document that these are separate bounded phases, not a promised five-second total command runtime.

Classify errors at the operation that raised them: `EACCES`/`EAGAIN` from the nonblocking lock primitive indicate contention, whereas `EACCES`/`EPERM` opening the sidecar indicate denied access. The lock helper translates contention into the typed busy outcome at deadline; it must not pass an ambiguous acquisition error to the general permission mapper. Invalid handles and unexpected lock errors are terminal I/O failures.

File algorithm:

1. Discover/validate migration resources without touching the database. Resolve the existing instance's normalized path; create only its parent directory and lock sidecar as needed.
2. Acquire ownership and inspect existing storage read-only. Reject invalid/incompatible/older states before using `_connect` and therefore before changing journal mode. The only possible new artifact for a rejected file is the empty ownership sidecar; database contents/schema are unchanged.
3. For ready storage, release ownership and return `READY`. Normal repository connection policy applies when actual work begins.
4. For fresh storage, open the same instance's normal `transaction()`. WAL setup now occurs **under ownership**, before the migration transaction; foreign keys, busy timeout and modern transaction control remain unchanged. Reinspect schema on this exact connection. If another writer changed it, classify the actual state; never migrate a now-nonfresh schema.
5. Pass that connection to Alembic. Apply the unique head, verify schema and encoding before commit, commit once through the outer `SQLiteDatabase.transaction`, then release ownership and return `INITIALIZED`.
6. On any exception, let the outer transaction roll back, close all scopes and release ownership in `finally`. Do not delete/recreate the database or lock file. WAL/file existence may remain after a failed fresh attempt; next invocation must inspect its actual schema again.

Manual online Alembic migrations acquire the same sidecar before opening their owned SQLite connection, but do **not** call automatic readiness/classification: explicitly requested upgrades/downgrades retain Alembic semantics. A borrowed connection does not reacquire the lock. Concurrent automatic initializers and manual migrations therefore serialize before WAL setup. Ordinary repository writes still use SQLite's locks; an unrelated/noncooperating writer can cause a classified busy failure and rollback, never a stale-snapshot initialization retry. External file replacement, hard-link aliases and network filesystem locking are not supported coordination mechanisms; use the same normalized local path. Symlink resolution follows existing `Path.resolve` settings behavior.

In-memory behavior: support only the existing instance's sequential `StaticPool` connection. Skip sidecar and read-only URI inspection. Inspect, initialize and verify inside that instance's transaction; injected Alembic must use that exact connection. Close/recreate produces a distinct empty database. Existing overlapping-scope rejection remains in force. Do not open a second `SQLiteDatabase` for memory readiness or silently turn memory into a file.

## 5. Alembic connection and resource contract

Add `upgrade_fresh_database(connection: Connection) -> None` to `migrations.py`. It requires an active caller-owned transaction and runs `command.upgrade(config, "head")` with `config.attributes["connection"] = connection`. It creates no engine and never commits, rolls back or closes the borrowed connection. Readiness owns freshness checks, locking and the outer transaction.

`run_migrations()` gains two explicit paths:

- Borrowed connection: validate `Connection` type and active transaction, reject offline mode or conflicting URL/`-x` overrides, configure the existing metadata with `transactional_ddl=True`, and run migration operations. Do not construct settings, reacquire ownership or dispose resources owned by the caller.
- Manual owned connection: preserve `-x database_url` → configured `sqlalchemy.url` → `ProjectSettings` precedence, unsupported-option rejection, percent escaping and offline rejection. Resolve once, acquire ownership, run the existing transaction and dispose the owned instance.

Resource discovery is anchored to `Path(__file__).resolve()` at the installed source checkout root, never the current directory or configured database `base_dir`. Verify `alembic/env.py` and the revision directory before touching storage; load `ScriptDirectory` and require one head. Build programmatic `Config` with absolute `script_location` and a captured text output sink; preserve normal manual `alembic.ini` use. Do not call `fileConfig`, reset application logging or emit initialization progress to stdout.

Supported deployment here is the documented source checkout with `uv sync` (editable installation), including invocation from another working directory with its installed executable/interpreter. `pyproject.toml` includes only `src*` packages; standalone wheel relocation is not verified to contain top-level Alembic resources. If resources are absent, fail with `database_resources_unavailable` before database creation. Do not search arbitrary parent/current directories for another checkout. Adding wheel-bundled resources would require a separate packaging contract and explicit permission to change build configuration; it is not silently included in B.

## 6. Error, JSON and logging contract

Catch `DatabaseReadinessError` before generic `ValueError`/unexpected-error handling in `execution_errors`. Use the existing `analysis_failure_document` unchanged: exit 1, `status="error"`, the stable readiness reason code, `result=null`, and existing analysis presentation versions (Momentum 4, others 5). JSON stdout contains exactly one document; initialization adds no stdout/stderr chatter. Parser/option failures retain exit 2.

Concise/details/diagnostics share the same actionable stderr message and empty stdout. Diagnostics append only authored `rule`/`reason` records. JSON retains those same safe records under `diagnostics`; do not add top-level schema fields or bump versions. Include the normalized target in the message, escaped as one line (including control characters), or the literal `in-memory database`. Do not echo arbitrary version rows, SQL, parameters, payloads, URLs with credentials, or exception strings.

| Code | Authored message after `Database <target>:` |
| :--- | :--- |
| `database_upgrade_required` | `schema upgrade required. Stop application processes and back up this database, then run uv run --no-sync alembic upgrade head from the installation folder with DATABASE_URL set to this target.` |
| `database_incompatible_schema` | `schema is incompatible or incomplete. Preserve this database and inspect it with the matching application version; automatic initialization was not performed.` |
| `database_busy` | `readiness could not acquire storage access within the configured wait. Close other database operations and retry.` |
| `database_permission_denied` | `access was denied. Check permissions for this file and its parent directory.` |
| `database_invalid_file` | `the file is not a readable SQLite database or is corrupt. Preserve it and inspect or restore it before retrying.` |
| `database_io_error` | `storage could not be accessed. Check the path, available storage and filesystem health.` |
| `database_resources_unavailable` | `migration resources are unavailable or inconsistent. Use a complete matching source installation; the database was not initialized.` |
| `database_initialization_failed` | `fresh initialization did not complete. Preserve this file and inspect application diagnostics before retrying; no partial schema was accepted.` |

Do not automatically execute the upgrade instruction, fabricate a shell-escaped command from a path, or suggest upgrading unknown/newer storage. Document how to select `DATABASE_URL` in the operator guide. An older-schema error must identify the inspected target; an unqualified default-path migration is insufficient guidance.

Classify SQLite/SQLAlchemy wrapped errors using `sqlite_errorcode` (mask extended codes to primary codes) and `OSError.errno`: BUSY/LOCKED → busy; READONLY/PERM/AUTH or EACCES/EPERM → permission; NOTADB/CORRUPT → invalid file; IOERR/FULL/CANTOPEN and otherwise unclassified OS storage failures → I/O. CANTOPEN alone does not prove permission failure. Missing optional error codes remain I/O, never evidence of freshness. An unexpected exception during the migration phase becomes initialization failed; resource discovery failure is separate. Preserve the original exception as the cause for internal debugging. Existing logging remains in place; no raw-exception logger or new framework is added. Diagnostic rendering/logging failure must not change the primary failure category or exit behavior.

## 7. Deterministic verification matrix for implementation

| Test group | New required proof and existing anchors |
| :--- | :--- |
| `test_readiness.py` lifecycle | Missing file, zero-byte file and valid empty schema initialize; repeat call returns ready without upgrade; saved rows survive reopen. Empty version table, unrelated table/view/trigger, unknown/multiple revisions, missing columns/indexes/checks/FKs, altered encoding, current stamp on partial schema all reject without changing database bytes where no SQLite recovery is involved, and without schema/row changes in all cases. |
| Version/resources | Synthetic older revision gives upgrade-required; invalid topology/resources fail before file creation. Foreign cwd, custom `base_dir`, spaces/percent/Unicode paths and missing packaged resources. Existing `test_migrations.py` override precedence and percent/cwd tests remain green. |
| Schema | Reuse signature categories from `test_schema.py`; verify required metadata, extra-key allowance, internal-object exclusion and no table-content scan. Do not treat matching table names alone as readiness. |
| Memory | Same instance initializes and persists between sequential scopes; distinct instance is empty; no lock file; overlapping scopes still reject. Existing `test_sqlite.py` memory cases remain green. |
| Concurrency | Two spawned processes synchronized with IPC barriers: only one migration, both observe ready after commit. Hold ownership to verify bounded busy; terminate owner to verify OS release. No timing sleeps to establish process ordering. Exercise Windows and POSIX paths in existing CI OS matrix. |
| Rollback/recovery | Inject failure after DDL and after version writes; force a process to exit during an uncommitted migration; reopening sees fresh or ready, never accepted partial schema. Post-migration signature failure also rolls back. Existing migration rollback/connection policy tests remain green. |
| Errors | Inject stable SQLite primary/extended codes and OS errors; distinguish lock, permission, corruption, I/O and migration failure. No text parsing, automatic repair, stale PID cleanup or fallback target. |
| CLI composition | Real cache/database/readiness/resolver paths with mocked transports for all four commands. First invocation initializes, next reuses; missing/incompatible storage fails before provider calls. Assert stderr/text and parseable JSON per mode, consistent target and safe next action, no raw secret/error leakage. |
| Independence | Help/import/evaluate fixtures and financial `--no-cache` never call readiness or create cache/sidecar; optional telemetry failure stays fail-open and never migrates. Do not assert that existing telemetry itself cannot touch its configured file. |
| Regression | All repository, migration, four-analysis, cache, orchestrator and evaluation tests plus complete managed gate; ≥85% coverage. The gate covers the accepted financial semantics unchanged. |

## 8. Slice A evidence and limits

Fresh complete baseline on `634164b`, 2026-09-11 (Toronto): **2,054 tests passed, 89% coverage**, Ruff check clean, 315 files formatted, strict mypy clean (240 source/test files). Command:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

Artifacts: `.tmp/quality-runs/20260911211225380-35712-ad631207d66c407c866aab9d3c651637/`.

Disposable offline experiments used `.tmp/readiness_contract_probe.py` and recorded `.tmp/readiness-contract-probe-result.json`:

1. Independent spawned process could not acquire an owned sidecar; acquired it after release; a new owner acquired it after the holding process terminated. This verifies the Windows primitive, not the future full initialization algorithm or POSIX implementation.
2. A temporary borrowed-database shim passed an outer connection through the existing Alembic runner. The real `0001_persistence` revision, including its version row, rolled back after an injected exception, then committed on the next attempt. A conflicting unused target was not opened. This proves feasibility of transaction injection, not that the new production branch already exists.
3. A provider-construction sentinel in the actual Graham CLI was reached without a prior readiness check and translated to generic `execution_error`. This proves composition currently lacks readiness; it is not a fabricated live provider result or a complete replay of the original missing-table report.
4. Schema inspection confirmed the six expected tables after migration. Existing schema tests separately verify constraints, indexes and the encoding seed.

Only disposable local databases were used. No operational database was read or migrated, no live provider/LLM was called, and no dependencies were installed. The temporary probes are not permanent acceptance tests; B/C must implement the matrix above. POSIX locks, full startup races, interrupted migration processes, schema-drift classification and final CLI wording remain implementation acceptance work, not completed claims.

## 9. Gate A decision

Gate A approval and Slice B authorization were granted on 2026-09-12 for the ownership sidecar, state/signature rules, same-instance memory support, Alembic injection, source-installation resource boundary, typed failures and exact file scope. Slice B subsequently passed its full gate and was explicitly approved on 2026-09-12; Slice C is authorized with the linked amendment. After C, stop for review before D documentation/acceptance. No commit, push, PR, dependency change or migration against user data is authorized by this handoff.
