# Step 3.3A — Fresh Database Initialization and Schema Readiness

Defines safe fresh-database initialization, explicit upgrades and readiness errors.

Work-package order and status: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## Sequence and status

| Order | Scope | Local gate |
| :--- | :--- | :--- |
| A | Concrete interfaces, locking and verification contract | Accepted |
| B | Readiness and fresh initialization | Accepted |
| C | Composition, errors and hidden maintenance | Accepted |
| D | Documentation and final evidence | Accepted |

## 1. Problem and decision

A missing-table failure on first use exposed an onboarding gap. Initialize only
verified fresh storage when required persistence is used; preserve saved records
and require explicit upgrades of existing schemas. Alembic remains the sole schema
authority. Report actionable storage errors before provider work wherever composition permits.

## 2. Readiness contract

| Observed state | Required behavior |
| :--- | :--- |
| Database file absent | Create and initialize through bundled Alembic migrations after exclusive ownership and an authoritative recheck. |
| Valid SQLite file with no user/application schema objects | Treat as fresh, including an empty file left by a prior connection; initialize as above. File size alone is never evidence. |
| Expected application revision and required schema structure | Proceed without migration or data changes. |
| Recognized older application revision | Fail with an upgrade-required error, resolved target location, and the explicit operator upgrade command; do not upgrade automatically. |
| Unknown/newer revision, unexpected revision topology, existing objects without trusted revision history, or incomplete/inconsistent schema | Fail with an incompatible/incomplete-schema error; preserve contents and request inspection. Missing one table or a revision row never proves freshness. |
| Lock timeout, permission failure, invalid SQLite file/corruption, or other storage I/O failure | Fail with the correct bounded storage category and useful next action; never reinterpret it as fresh storage or automatically repair it. |

Freshness inspection must enumerate relevant tables, views, indexes, and triggers, with an explicit reviewed policy for SQLite-owned internal objects. An empty Alembic version table or partially created application schema is not fresh. Revision checking includes the required structure and application schema metadata compatibility; a head stamp alone does not establish readiness. Do not perform an expensive full integrity scan on every invocation.

Resolve the database target once from application settings and use that exact target for inspection, initialization, and repository use. Preserve existing URL validation and base-directory-relative semantics. A caller-supplied/custom location is subject to the same strict empty-storage rule. No fallback to a second database, ephemeral cache, or alternate path on readiness failure.

## 3. Ownership and lifecycle

- Add the smallest shared readiness boundary under `src/data/repositories/`, invoked by application composition before required persistence is used. Keep constructors lazy and calculators/repositories free of implicit migration side effects.
- Audit every required production persistence entry point, including financial and historical CLI helpers and runtime composition. Do not initialize only for Graham. Optional SQLite telemetry must not trigger initialization or become a prerequisite for business execution; preserve fail-open telemetry.
- Preserve `--no-cache` financial-cache bypass, imports, help, and genuinely storage-free operations without creating/opening the cache database. Do not promise that a flag bypasses unrelated persistence.
- Invoke bundled Alembic programmatically in the running interpreter. Do not spawn `uv`, depend on the current working directory, synchronize dependencies, or download migration resources. Keep manual Alembic commands functional and preserve their documented override precedence.
- Reuse `SQLiteDatabase` transaction, foreign-key, WAL, and timeout policy. The current migration runner owns a new database/connection; design the smallest connection-injection seam required to keep locking, recheck, DDL, and revision verification in one coordinated lifecycle without recursively invoking readiness.
- Serialize simultaneous first launches across processes, not just threads. After ownership is acquired, recheck state before deciding to migrate; waiting peers observe the committed ready schema. Use a bounded timeout and release ownership on success, failure, or process termination. Account for WAL setup and inspection races before acquiring the migration lock. Freeze the exact mechanism in Slice A; a new locking dependency is not authorized.
- Keep migration DDL and revision updates atomic under the established transaction policy. Verify final revision and required structure before allowing analysis to proceed. Never use `create_all`, `stamp head`, database replacement/deletion, or automatic retries that mask partial state. An interrupted run may be retried automatically only if the next inspection proves storage is fresh or already ready.
- Initialization must have no provider or LLM dependency. Keep progress/log messages off JSON stdout.

## 4. Error and diagnostic contract

Use typed readiness failures with stable reason categories at the persistence boundary. CLI translation produces concise sanitized errors and nonzero exit status; ordinary users must receive an actionable explanation even without `--diagnostics`. Do not parse arbitrary `OperationalError` text to decide to migrate.

For recognized older schemas, include `uv run --no-sync alembic upgrade head` as the repository-installation operator action, identify the selected database, and explain backup/process-stop prerequisites. Ensure instructions target the same configured database. For unknown/newer or inconsistent schemas, recommend inspection with compatible application code rather than blindly upgrading.

Preserve analysis-focused diagnostic rendering. Provide sanitized operational evidence for unexpected infrastructure failures through existing logging conventions, with original causes retained internally. Do not expose SQL parameters, financial payloads, secrets, configuration dumps, or raw exception text indiscriminately. Avoid a new logging framework or a broad diagnostics redesign.

Slice A freezes the exact error types, safe fields, stderr wording, exit codes, and JSON failure behavior in the concrete contract. The selected contract preserves the accepted failure serializer: exactly one versioned JSON document on stdout, `status=error`, a stable readiness reason code, `result=null`, and exit 1; empty JSON stdout is not an acceptable readiness failure. No migration chatter may contaminate it. Tests must prove diagnostics do not obscure readiness errors. Logging failures must not alter the underlying failure or business outcome.

## 5. Scope and source inventory

Known implementation seams: `src/data/repositories/sqlite.py`, `migrations.py`, `schema.py`, repository exports, `src/cli_support.py`, `src/cli.py`, application runtime persistence composition, `alembic/env.py`, and `alembic.ini`. Review `src/config.py` only if a typed setting is required; reuse existing bounds where sufficient. Exact file/function allowlist and existing test mappings are Slice A deliverables, not permission to refactor every listed module.

Documentation delivery belongs in README and `docs/user/INSTALLATION.md`, `QUICKSTART.md`, and `DATABASE.md`, plus relevant CLI/runtime docstrings and project architecture. Describe automatic initialization, explicit existing-database upgrades, error remediation, database selection, bypass behavior, and operational recovery consistently. Keep those user guides accurate for the current implementation until the behavioral change ships; no milestone labels belong in them.

Out of scope: existing-data auto-upgrades, automatic repair/downgrade/backup/restore, user-database migrations during agent verification, new schema/business tables, workspace design, financial math/provider changes, generic infrastructure frameworks, new dependencies, and changes to `pyproject.toml` or `uv.lock`. Explicit operator upgrades remain separately authorized actions.

## 7. Deterministic acceptance matrix

| Area | Required proof |
| :--- | :--- |
| Fresh lifecycle | Missing file and valid empty file initialize; required schema/revision checks pass; first mocked default Graham invocation succeeds; second invocation and close/reopen preserve stored records and do not rerun migrations. |
| Existing storage protection | Older known revision, unknown/newer revision, empty revision table, missing required table, inconsistent schema metadata, partial schema, and unrelated tables/views are rejected with no application/schema data mutation. |
| Configuration/resources | Default/custom/relative paths resolve consistently across working directories; migration resources work for supported installation modes; manual Alembic override behavior remains valid. Explicitly decide and test in-memory support without accidentally migrating a different connection. |
| Concurrency | Two independent processes start against the same fresh target using deterministic synchronization rather than timing sleeps; one initialization commits, both observe readiness, and bounded contention failure is classified. |
| Failure recovery | Inject migration failure and test interrupted-process recovery; no partial committed schema/revision is accepted; lock ownership is released and a subsequent run handles the observed state safely. |
| Storage errors | Deterministic lock, permission, malformed-file, and I/O failures remain distinct from upgrade-required; no automatic destructive recovery or fallback. |
| Presentation | Concise, details, diagnostics, and JSON failures have the agreed status/streams and safe next action; no SQL parameters/secrets or initialization chatter leak; successful analysis output remains compatible. |
| Independence | Help/import/storage-free commands and financial `--no-cache` avoid cache creation; optional telemetry failure never controls analysis readiness; provider/LLM calls are blocked in tests. |
| Regression | Existing repository round trips, explicit migration lifecycle, heterogeneous CLI commands, financial semantics, and cache behavior pass. |

Use synthetic data and unique temporary databases only. Never read or migrate the operational database or import diagnostic captures as fixtures. Tests use no live network or LLM endpoints. Run the complete non-mutating managed quality wrapper for each implementation gate:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

```bash
bash "$(git rev-parse --show-toplevel)/scripts/run-quality-gates.sh"
```

Record revision, verification date, Ruff/format/strict-mypy results, pytest totals,
coverage (at least 85%) and isolated artifact location. The [final evidence record](SLICE_D_FINAL_ACCEPTANCE.md)
links the lifecycle, composition and documentation verification.
