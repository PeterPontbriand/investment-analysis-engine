# Step 3.3A — Fresh Database Initialization and Schema Readiness

**Status:** The [existing-strategy correctness audit](../existing-strategy-correctness/ESC_C_FINAL_ACCEPTANCE.md) received ESC-C final acceptance on 2026-09-11 (Toronto), releasing the readiness planning deferral. Planning was requested on 2026-09-09 and may now resume at Slice A. The contract and implementation slices remain proposed; production implementation requires Gate A approval. No readiness baseline or implementation acceptance is claimed.

**Authority:** [Milestone implementation plan](../IMPLEMENTATION_PLAN.md#49a-step-33a--fresh-database-initialization--schema-readiness). This bounded prerequisite precedes Step 3.4 contract design and implementation. Step 3.4's 2026-09-08 start authorization is retained but deferred until this work receives final acceptance; its own contract/review gates still apply. Subsequent sequence remains Step 3.4 → P2-Profiles → ESC-D renewed acceptance → Step 3.5 → Step 3.6, following the active milestone's latest ordering.

**Branch history:** Renamed locally to `codex/step-3.3a-database-readiness` on 2026-09-09 for this planning/implementation work. The starting local branch was `feat/step-3.4-research-workspace`, at `b6a84e0`, with two documentation commits after Step 3.3 and no configured upstream. Renaming preserves those commits and working-tree content. No commit, push, or PR is authorized by this plan.

**Current sequencing:** ESC-C is accepted. Resume contract planning and verification at Slice A; retain its explicit review gate before production edits. Readiness implementation belongs on a separate descriptive branch such as `feat/database-readiness`; no branch creation is requested here. Its acceptance must rerun the four-analysis regressions and relevant fresh/current/cache lifecycle cases. ESC-D renewal remains mandatory before Step 3.5.

## 1. Problem and decision

The project owner reported that the README's `graham-number KO` example and its `--diagnostics` variant both returned only a generic unexpected-failure message. The supplied Cline diagnosis attributed this to an empty SQLite database with no applied Alembic revision; bypassing the financial cache succeeded, and an operator migration restored the default command. This is reported diagnostic evidence, not a live reproduction performed for this planning change.

Source inspection confirms that `src/cli_support.py` explicitly leaves migrations to the operator, `execution_errors` hides unclassified exceptions behind a generic message, and the diagnostics flag selects analysis presentation. The current operational documentation is consistent with that implementation. The new target deliberately changes first-use policy while preserving explicit upgrades of existing schemas.

Initialize verified fresh storage automatically when an application operation first needs persistence. Keep Alembic as the only schema authority. Detect incompatible or unavailable storage before provider work whenever composition permits, and report an actionable, sanitized failure. Do not treat a database containing saved user records as disposable cache storage.

This work precedes the research workspace because watchlists and Analysis Runs will increase both persistence usage and the cost of misclassifying an existing database. It adds no workspace tables and does not renumber Step 3.4 or later steps.

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

Slice A must freeze the exact error types, safe fields, stderr wording, exit codes, and JSON failure behavior after inspecting existing command contracts. JSON stdout must remain parseable or empty according to the selected existing-compatible contract; no migration chatter may contaminate it. Tests must prove diagnostics do not obscure readiness errors. Logging failures must not alter the underlying failure or business outcome.

## 5. Scope and source inventory

Known implementation seams: `src/data/repositories/sqlite.py`, `migrations.py`, `schema.py`, repository exports, `src/cli_support.py`, `src/cli.py`, application runtime persistence composition, `alembic/env.py`, and `alembic.ini`. Review `src/config.py` only if a typed setting is required; reuse existing bounds where sufficient. Exact file/function allowlist and existing test mappings are Slice A deliverables, not permission to refactor every listed module.

Documentation delivery belongs in README and `docs/user/INSTALLATION.md`, `QUICKSTART.md`, and `DATABASE.md`, plus relevant CLI/runtime docstrings and project architecture. Describe automatic initialization, explicit existing-database upgrades, error remediation, database selection, bypass behavior, and operational recovery consistently. Keep those user guides accurate for the current implementation until the behavioral change ships; no milestone labels belong in them.

Out of scope: existing-data auto-upgrades, automatic repair/downgrade/backup/restore, user-database migrations during agent verification, new schema/business tables, workspace design, financial math/provider changes, generic infrastructure frameworks, new dependencies, and changes to `pyproject.toml` or `uv.lock`. Explicit operator upgrades remain separately authorized actions.

## 6. Slices and review gates

| Slice | Work and evidence | Exit gate |
| :--- | :--- | :--- |
| 3.3A-A — Reconciliation and concrete design | Inventory callers/tests and schema invariants; freeze typed interfaces, exact file scope, locking/transaction strategy, Alembic resource discovery, error/JSON/logging contract, and in-memory behavior. Establish a fresh full managed baseline before refactoring. | Explicit contract approval and implementation authorization before B. This planning request does not close Gate A. |
| 3.3A-B — Readiness and initialization | Implement state classification, coordinated fresh initialization, manual migration compatibility, and focused lifecycle/concurrency/rollback tests. | Full managed gate and explicit review before C. |
| 3.3A-C — Composition and errors | Wire required persistence callers, actionable typed CLI failures and sanitized evidence; prove bypass/help/telemetry behavior and mocked CLI success. | Full managed gate and explicit review before D. |
| 3.3A-D — Documentation and acceptance | Update durable behavior docs, reconcile all acceptance evidence, and record limitations and final verification. | Explicit final acceptance closes this prerequisite; then resume Step 3.4 contract preparation under its retained start authorization. |

Do not infer approval from elapsed time, a passing test suite, or this document's existence. Preserve unrelated work. Document any required scope expansion before implementation.

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

Record commit/revision, date, Ruff/format/strict-mypy results, pytest totals, coverage (at least 85% overall), and isolated artifact location. Existing predecessor test totals are historical evidence only. For this documentation checkpoint, validate links, sequencing, approval wording, and diff whitespace; production quality evidence is deferred to Slice A onward.
