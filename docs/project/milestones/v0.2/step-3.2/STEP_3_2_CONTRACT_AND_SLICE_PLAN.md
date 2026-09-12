# Step 3.2 Contract and Slice Plan — DAO & Repository Layer

**Status:** Step 3.2 complete and approved on 2026-09-07. All Gates 3.2-A/B/C/D are closed. [PR #30](https://github.com/PeterPontbriand/financial-data-agents/pull/30) merged implementation head `d07a709` as `f3ef25701cac3fbee3a2caa295f102f4d389d51b` on 2026-09-08 at 00:11 UTC (2026-09-07 in America/Toronto), closing the implementation commit/PR workflow. Earlier workflow statements below remain the historical gate record.

**Authority:** [Implementation Plan, Step 3.2](../IMPLEMENTATION_PLAN.md#48-step-32--dao--repository-layer) owns scope, sequencing, and acceptance criteria. This companion supplies the concrete handoff. If they conflict, amend this handoff to match the Implementation Plan before execution.

**Predecessors:** Step 3.1, R1, and R2 are complete and approved. [PR #29](https://github.com/PeterPontbriand/financial-data-agents/pull/29) merged R1/R2 into `main` on 2026-09-07 at 17:55:41 UTC, merge commit `ca914b73281aaf5e618684098bb4f115c90972c5`. Its tree is identical to reviewed R2 tip `c4316425c52488c6574c93027235b9ac980e0803`.

**Authorization:** On 2026-09-07 the project owner confirmed that the documents were reviewed and approved and explicitly authorized Slice 3.2-B. This closes Gate 3.2-A and accepts the inventory, gap dispositions, implementation contract, file scope, and verification requirements below. The requested documents-only checkpoint was committed and pushed as `ee4db024bb10c061b2b17ccad41e35544ccd94e3`; the project owner then instructed execution of B. No additional planning approval is required for B within this contract; C and D retain their separate review and authorization gates.

## 1. Scope and preservation

Complete only demonstrated gaps in typed access for cache inspection, audit logging, and later analytics. The existing storage and public financial representations remain authoritative. Step 3.2 precedes Step 3.3, P2-Profiles, Step 3.4, and Step 3.6 in the selected sequence.

- Preserve dataclasses, Pydantic models, DataFrames, all cache identities, timestamps, provenance, temporal eligibility, TTL behavior, and existing public methods/imports.
- Keep application persistence SQL in `src/data/repositories/`; the existing telemetry adapter's SQL is a demonstrated gap to move behind that boundary. Migration DDL and test setup/assertion SQL retain their existing owners. No raw SQL belongs in orchestrators, tools, or CLI code.
- Reuse `SQLiteDatabase`, approved tables, and migration-owned encoding metadata. No schema, migration, dependency, connection-policy, or data-format change is proposed.
- Repository errors remain explicit. The telemetry recorder retains sanitization and fail-open behavior; the sink retains its lifecycle and ownership semantics. Storage does not become business control flow.
- No generic DAO base class, registry, ORM rewrite, duplicate cache protocol, provider/model calls, financial recalculation, or user-data migration.
- Step 3.3 owns new data-quality/refresh/invalidation policy. P2-Profiles owns durable instrument profiles. Step 3.4 owns watchlists, Analysis Runs, run browsing, and report projection. No new CLI commands, investor records, aggregate analytics, or telemetry retention/deletion policy are implied here.

## 2. Slice 3.2-A — Source reconciliation and contract review

The inventory below preserves the pre-implementation source snapshot reviewed at Gate 3.2-A, not the final repository state. Sections 7–9 record implementation and disposition of its gaps. It was prepared from source and tests, not inferred solely from Step 3.1 completion. Paths are repository-relative. The [Step 3.1 contract](../step-3.1/STEP_3_1_SQLITE_SLICE_PLAN.md) and [approved persistence mapping](../step-3.1/STEP_3_1_D0_PERSISTENCE_MAPPING.md) remain the storage authority.

### Existing public surface

| Module | Existing typed boundary | Preservation / limitation |
| :--- | :--- | :--- |
| `src/data/repositories/sqlite.py` | `SQLiteDatabase.transaction()`, `read()`, `close()` | Borrowed scopes; commit/rollback; query-only snapshots; lazy construction; no implicit migration. |
| `src/data/repositories/market_data.py` | `MarketDataCacheKey`, `MarketDataCacheEntry`, `SQLiteMarketDataRepository.put()`, `get()` | Exact historical request snapshots with complete frame/context reconstruction; no enumeration API. |
| `src/data/repositories/resolved_input_cache.py` | `SQLiteResolvedInputCache.put()`, `get()`, `get_series()`, `ttl` | Complete scalar/series provenance; reads apply eligibility and configured TTL, so absent and ineligible entries both appear unavailable. |
| `src/data/financial/cache.py` | `ResolvedInputCacheProtocol`, `ResolvedInputSeriesCacheProtocol`, keys, entries, series query, in-memory implementation | Approved provider-resolution seams; do not expand these protocols for administrative SQLite inspection. |
| `src/core/telemetry/sinks/sqlite.py` | `SQLiteTrajectorySink.record()`, `flush()`, `close()`; `read_trajectory(database, run_id)` | Typed immutable event storage/readback exists, but SQL and row encoding reside outside the repository package. |
| `src/core/telemetry/sinks/__init__.py` | Re-exports `SQLiteTrajectorySink` and `read_trajectory` | Preserve public import paths and call signatures when delegating to a repository. |
| `src/data/repositories/schema.py`, `migrations.py`, `alembic/` | Core table metadata and migration lifecycle | Existing tables/encoding suffice; no replacement infrastructure. |
| `src/data/cached_client.py`, `src/cli_support.py` | Historical cache/provider composition and shared resource scopes | Fetch, fallback, TTL selection, and resource ownership stay with existing callers. |

### Requirement and gap matrix

| ID | Requirement | Finding and evidence | Smallest disposition |
| :--- | :--- | :--- | :--- |
| G1 | Fully typed access for core cached entities | **Satisfied.** Historical `put/get`, scalar `put/get`, and period `get_series` already exist. `tests/data/repositories/test_market_data.py`, `test_resolved_input_cache.py`, and `test_series_cache.py` cover identities, replacement, reopen, precision, lineage, ordering, eligibility, and corrupt storage. | Retain these interfaces and tests; no universal Pydantic conversion or additional cache abstraction. |
| G2 | Cache inspection | **Partially satisfied.** Exact historical lookup is available; financial `get/get_series` expose only eligible entries. Neither concrete repository enumerates stored keys. Storage can contain stale entries that cannot be distinguished from misses through the normal cache interface. | Add approved bounded key enumeration and explicit stored-entry inspection on the concrete SQLite classes, as specified in section 3. No freshness-policy change or CLI. |
| G3 | Audit logging and typed readback | **Satisfied behavior; partial architectural placement.** `SQLiteTrajectorySink` commits immutable events; `read_trajectory` reconstructs ordered typed events. `tests/core/telemetry/test_sqlite_sink.py` covers duplicates/conflicts, concurrency, sanitization, missing/corrupt data, encoding, ownership, and fail-open composition. | Extract existing SQL/serialization into a narrow trajectory repository; retain sink/readback entry points as delegates. No second audit log or new run model. |
| G4 | SQL confined to the repository layer | **Partially satisfied.** Market/fact SQL is in repositories. Telemetry sink/readback directly execute SQLAlchemy statements. | Move only that trajectory persistence responsibility under `src/data/repositories/`; keep schema management and test SQL in their established locations. |
| G5 | Consistent WAL / single-writer connection management | **Satisfied.** `SQLiteDatabase` verifies WAL, foreign keys, busy timeout, query-only reads, and scoped disposal; SQLite serializes competing writers. `tests/data/repositories/test_sqlite.py` exercises reader snapshots, writer timeout, rollback, close guards, and sequential memory scopes. | Reuse unchanged. Do not invent a writer queue or claim the Python lock globally serializes all file writes. Use file-backed tests for WAL/concurrency. |
| G6 | Round trips for core entities | **Satisfied baseline; extend with changes.** Above suites plus `test_persistence_smoke.py`, `test_schema.py`, and `test_migrations.py` verify the persisted lifecycle. | Add focused tests alongside implementation; retain the existing suite and full managed gate. |
| G7 | Support later analytics | **Satisfied foundation, later product work deferred.** Historical frames/context, financial facts/lineage, and ordered trajectory events are reconstructable through typed access. | No speculative analytics query language, joins, watchlists, or Analysis Run repository. Later requirements belong to their owning steps. |

Gate 3.2-A approval on 2026-09-07 accepts G2 as the bounded cache-inspection scope specified in section 3. G3/G4 describe one extraction, not two implementations. No completely missing storage subsystem was found.

### Fresh baseline evidence

On 2026-09-07 the managed wrapper passed Ruff, formatting (283 files), strict mypy (222 source files), and **1,811 tests in 26.87 seconds**. Coverage: **89% reported combined coverage**, 9,376 statements, 776 missing, 2,964 branches, 497 partial branches; statement coverage is approximately 91.7%.

Command: `& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')`.

Artifacts: `.tmp/quality-runs/20260907143230324-6084-fb6f134eada84485bb6fbef5972eafe2/` (ignored; do not commit).

The run started on `c4316425c52488c6574c93027235b9ac980e0803` with documentation-only changes. The fetched PR merge has the identical tracked tree; the handoff now resides on `docs/step-3.2-repositories` based on that merge. No source or test edits were made. The initial sandboxed attempt could not query the existing Python interpreter; the approved retry used the same non-mutating wrapper and existing environment without dependency synchronization.

### Gate 3.2-A

Approved by the project owner on 2026-09-07 following document review. Approval covers the inventory, G2 inspection interpretation, G3/G4 extraction, section 3's interface/behavior contract, file scope, and recorded green baseline. Slice 3.2-B was explicitly authorized in the same instruction. The documents-only checkpoint requirement was subsequently satisfied by pushed commit `ee4db024bb10c061b2b17ccad41e35544ccd94e3`; no second planning-only slice was needed.

## 3. Slice 3.2-B — Demonstrated gaps with focused tests

**Status:** Implemented, verified, and approved at Gate 3.2-B on 2026-09-07. Evidence is recorded in section 7; approval and C execution are recorded in section 8.

### Bounded implementation contract

1. Add `src/data/repositories/trajectory.py` with `SQLiteTrajectoryRepository(database)`, `record(event: TrajectoryEvent) -> None`, and `read_trajectory(run_id: UUID) -> list[TrajectoryEvent]`. It borrows an already-migrated database and neither closes nor migrates it. Move the existing row encoding, JSON/finite-value validation, insert/conflict comparison, and ordered readback without altering semantics. Preserve identical-event idempotency, event/run-sequence conflicts, atomic rollback, missing-run empty lists, sequence gaps, nullable fields, and explicit corrupt/unsupported-encoding errors. Preserve current encoding-check behavior rather than introducing new validation policy during extraction.
2. Keep the existing `SQLiteTrajectorySink(database, *, close_database=False)` and module/package `read_trajectory(database, run_id)` signatures. Delegate persistence to the repository; retain sink locking, flush/close behavior, and database ownership in the adapter. The recorder continues to sanitize and handle sink failures. Repository imports may use `TrajectoryEvent` from its model module, but must not import the sink or recorder and create a dependency cycle.
3. Add `list_keys(*, limit: int, offset: int = 0) -> tuple[MarketDataCacheKey, ...]` to `SQLiteMarketDataRepository`, and the equivalent returning `tuple[ResolvedInputCacheKey, ...]` to `SQLiteResolvedInputCache`. Require positive integer `limit` and nonnegative integer `offset`, rejecting booleans; no unbounded/default-limit path. Order by the existing canonical `entry_key` / `cache_key` text in ascending order. Each call is one read snapshot; pagination across concurrent writes is not a frozen database snapshot. Return an empty tuple for an empty page. Validate key representations and encoding versions; malformed selected keys raise explicitly. No dynamic SQL, arbitrary filters, or payload loading merely to enumerate keys.
4. Add `SQLiteResolvedInputCache.inspect(key: ResolvedInputCacheKey) -> ResolvedInputCacheEntry | None`: return the complete validated stored entry irrespective of TTL or analysis eligibility, or `None` only when the exact key is absent. Preserve stored provenance and timestamps; do not relabel it as a current cache hit. Invalid input/storage/version raises as in existing retrieval. The existing historical `get` already provides stored-entry inspection and needs no duplicate method. Share decoding where useful without changing `get/get_series` eligibility semantics. Inspection must never refresh, delete, call providers, or supply facts to normal resolver paths.
5. Keep `ResolvedInputCacheProtocol` and `ResolvedInputSeriesCacheProtocol` unchanged. These concrete administrative methods do not need in-memory-provider equivalents. Expose only the new trajectory repository through the repository package where appropriate; preserve every existing export.

**File scope:** `src/data/repositories/trajectory.py` (new), `__init__.py`, `market_data.py`, `resolved_input_cache.py`; `src/core/telemetry/sinks/sqlite.py`; focused tests under `tests/data/repositories/` and `tests/core/telemetry/test_sqlite_sink.py`; this planning record. Schema, migrations, dependencies, analyzers, provider clients, CLI behavior, and telemetry recorder policy are outside the implementation scope. A demonstrated need beyond this scope requires a contract amendment and review, not an opportunistic rewrite.

**Tests belong in this slice:** Establish/confirm the baseline before refactoring. Add focused failing tests for new inspection behavior and direct repository access, then implement. Cover stable key ordering/pagination, empty pages, invalid bounds, stale/historically ineligible entries visible only to inspection, unchanged normal reads, corruption, unsupported encoding, and no write/provider side effects. Preserve full trajectory equivalence, conflict/rollback, lock/ownership, and recorder fail-open coverage. Use migrated temporary-file databases for durability and concurrency; memory databases only for sequential cases.

**Gate 3.2-B:** Review the bounded diff, full typed API, focused regression evidence, preserved public behavior, and complete managed gate. No known failing or untested implementation is handed to 3.2-C. Record explicit authorization before C begins.

## 4. Slice 3.2-C — Integration and acceptance verification

**Status:** Verified and approved at Gate 3.2-C on 2026-09-07. Acceptance evidence is recorded in section 8; the project owner explicitly authorized D.

Verify the combined repository/sink/cache lifecycle against a fresh migrated temporary database and a reopened database. Extend integration tests only for demonstrated coverage gaps; do not duplicate B's tests. Demonstrate exact typed round trips, original provenance/timestamps, unchanged cache eligibility, and preserved telemetry failure handling. Audit production SQL placement, public imports, connection ownership, and the three Step 3.2 acceptance criteria. A defect receives a bounded fix and regression test within the approved contract; wider changes return to review.

Run the complete managed gate and record count/coverage changes relative to A/B, explaining any removed test or changed denominator. Deterministic tests must not call real providers or LLMs. Real user databases and live-model smoke tests are not required.

**Gate 3.2-C:** Review acceptance evidence and authorize D explicitly. Verification success does not mark Step 3.2 complete.

## 5. Slice 3.2-D — Documentation and closeout

**Status:** Documentation reconciliation and final managed verification completed on 2026-09-07 after explicit authorization. Evidence is in section 9; final Gate 3.2-D approval was granted on 2026-09-07, as recorded in section 10.

Synchronize this record, the Implementation Plan, Master Plan, and affected durable architecture guidance with actual implemented contracts. Reconcile Discovery Workbook references only where affected; preserve historical design and approval snapshots. Record the final full managed gate, whitespace/link checks, and documents/source scope review. Mark Step 3.2 complete only after explicit Gate 3.2-D approval. Step 3.3 and later work retain their own authorization and planning gates.

## 6. Checkpoint and decision record

| Item | Current state |
| :--- | :--- |
| R1/R2 approvals and merge | Complete; PR #29 merged on 2026-09-07. Historical pending entries in predecessor records are superseded by their final approvals and merge closeout. |
| 3.2-A inventory, gap matrix, approved contract, baseline | Reviewed and approved on 2026-09-07. |
| Gate 3.2-A / authorization for B | Explicitly approved / authorized by the project owner on 2026-09-07. |
| Documents-only checkpoint | Committed and pushed as `ee4db024bb10c061b2b17ccad41e35544ccd94e3`; local HEAD and its remote-tracking ref matched at execution start. |
| B / C / D | All approved on 2026-09-07; final Gate 3.2-D approval completes Step 3.2. |

Gate 3.2-A approval, B authorization, and the pushed documentation checkpoint are recorded. B execution is complete and approved. The project owner subsequently approved C and explicitly authorized D. Final Gate 3.2-D approval was granted on 2026-09-07, completing Step 3.2.

## 7. Slice 3.2-B implementation and verification — 2026-09-07

Execution started from clean pushed checkpoint
`ee4db024bb10c061b2b17ccad41e35544ccd94e3` on
`docs/step-3.2-repositories`, after the project owner explicitly instructed
3.2-B implementation. The local HEAD and remote-tracking ref both matched that
checkpoint. No further planning decision or scope amendment was needed.

### Delivered scope

- Added and exported `SQLiteTrajectoryRepository`. Moved the existing event
  codec, immutable insertion/conflict comparison, and ordered readback into
  `src/data/repositories/trajectory.py`. The existing sink and public readback
  function delegate to it; sink locking, flush/close behavior, database
  ownership, recorder sanitization, and fail-open handling remain intact.
- Added bounded `list_keys(limit=..., offset=...)` methods to the two concrete
  SQLite cache repositories. They select only key columns, order by canonical
  stored identity, validate bounds/encoding/selected keys, and return typed
  tuples. They do not load financial/frame payloads or apply freshness policy.
- Added `SQLiteResolvedInputCache.inspect(key)` for validated stored entries,
  including stale and historically ineligible facts. Existing `get` shares
  that decoding path and still applies its original eligibility policy;
  `get_series` and both cache protocols are unchanged.
- Added 42 deterministic cases: 14 historical key-inspection cases, 19
  financial-cache inspection cases, 5 direct trajectory-repository cases,
  and 4 fresh-process import-order cases. All 49 pre-existing test functions
  in the three modified test modules retain identical ASTs, including their
  decorators and assertions; no existing cases were removed or weakened.

The sink imports the trajectory module rather than eagerly importing its class,
so the existing package-level telemetry exports can finish initialization before
repository construction. Fresh-process checks cover repository package/module
and telemetry package/sink entry points. No telemetry package/recorder redesign
or delayed function-local import was introduced.

### Verification evidence

| Check | Result |
| :--- | :--- |
| Fresh pre-refactor managed gate | Ruff clean; 283 files formatted; strict mypy clean (222 source files); 1,811 tests passed in 26.54 seconds; 89% reported coverage. |
| Initial focused test run | All 33 new cache-inspection cases failed because the new public methods were absent, before production edits. |
| Focused post-implementation suite | All 272 persistence and telemetry cases passed in 19.17 seconds, including fresh-process imports. |
| Final managed gate | Ruff clean; 285 files formatted; strict mypy clean (224 source files); 1,853 tests passed in 31.80 seconds; 89% reported coverage. |
| Preservation audit | Event codec and immutable-write ASTs unchanged; executable readback AST unchanged apart from using the borrowed instance database. Existing test functions unchanged. |
| Scope / whitespace | `git --no-pager diff --check` passed; only the approved five production files, four test files, and this handoff changed. No SQL remains in the trajectory adapter. |

Baseline artifacts:
`.tmp/quality-runs/20260907144856403-37660-01e75ea911064b20aafeffbf9378de61/`.
Final artifacts:
`.tmp/quality-runs/20260907145451159-31164-6b796ff39ee64bbbb3012c2ff7ff4edf/`.
Both runs used the complete non-mutating managed PowerShell wrapper against the
existing environment. Artifacts remain ignored and must not be committed.

Coverage reconciliation: baseline 9,376 statements / 776 missing and 2,964
branches / 497 partial; final 9,422 statements / 776 missing and 2,980 branches /
497 partial. The test count increased by exactly 42 (1,811 → 1,853). Final
statement coverage is approximately 91.8%; combined reported coverage remains
89%. No removed test or reduced statement denominator explains the result.

The first lint pass identified parameterization style and overly broad exception
assertions in the new tests; these were corrected before the final gate. An
auxiliary AST comparison initially included changed docstring indentation from
moving readback into a class; comparing the executable body confirmed that its
logic is preserved. No production defect or widened contract resulted from
these verification corrections.

Gate 3.2-B is ready for stakeholder review, not yet approved. Step 3.2 remains
in progress; C/D and later milestone implementation have not started. No commit,
push, PR, dependency/schema change, real provider/model call, or user-data
migration was performed during this implementation task.

## 8. Gate 3.2-B approval and Slice 3.2-C acceptance — 2026-09-07

The project owner reviewed and approved the delivered B implementation and
instructed proceeding. In the context of the pending Gate 3.2-B review, this
closes Gate 3.2-B and authorizes the next slice, 3.2-C. It does not declare the
whole step complete or approve unreviewed D closeout work. Section 7's pending
approval statement is retained as the historical pre-review snapshot.

C started from the approved, uncommitted B working tree over checkpoint
`ee4db024bb10c061b2b17ccad41e35544ccd94e3`. B's final managed gate is the accepted
baseline: 1,853 passing tests and 89% reported coverage. No production refactor
or defect correction was necessary in C.

### Integration coverage and scope

Extended `tests/data/repositories/test_persistence_smoke.py` because the existing
combined lifecycle test did not yet exercise the new inspection interfaces
across close/reopen. It now verifies direct trajectory readback and both key
listings in the fresh migrated database; after reopening, it checks stored-fact
inspection, pagination exhaustion, original timestamps/provenance, and continued
ineligibility through normal TTL-aware reads. It also verifies empty inspection
results after the existing disposable-database downgrade/recreation lifecycle.
Existing frame equality, event equality, database integrity, foreign-key checks,
and network prohibition remain in place.

The expanded assertions exceeded Ruff's statement limit in the existing test,
so reopened-store assertions were moved into a narrowly typed helper without
weakening them. No new test case was needed: this extends the existing lifecycle
case rather than duplicating B's focused tests. Only that test module and this
handoff changed during C; all B production changes remain as approved.

### Acceptance reconciliation

| Step 3.2 criterion / boundary | Verified evidence |
| :--- | :--- |
| Public repository methods fully typed and mypy-clean | Complete strict mypy passed across `src` and `tests` (224 source files). Public APIs retain explicit annotations and domain return types. |
| Core entity round trips | Full cache/trajectory suites and expanded offline lifecycle test pass against migrated temporary files and reopened databases; frame precision/context, facts/provenance/timestamps, and event ordering are retained. |
| WAL / single-writer connection policy | `SQLiteDatabase` remains unchanged. Existing policy tests pass for WAL/foreign keys/timeout on new connections, reader snapshots, competing writers, rollback, query-only reads, sequential in-memory scopes, and close guards. |
| SQL placement | Production source audit found application database execution confined to `src/data/repositories/`. Remaining SQLAlchemy references in `src/config.py` are URL parsing/validation, not SQL execution. Migration DDL and test assertion/setup SQL retain their established owners. |
| Public imports and ownership | Fresh-process import-order tests and existing sink ownership tests pass. Original sink/readback exports remain; repositories borrow the migrated database; default sink close does not close the shared database. |
| Cache eligibility and telemetry failure handling | Inspection exposes stored facts without changing normal `get/get_series` eligibility. Existing sanitization, recorder fail-open, missing-schema, and locked-database recovery tests pass unchanged. |

### Final verification and handoff

The complete managed PowerShell wrapper passed on 2026-09-07:
Ruff clean, formatting clean (285 files), strict mypy clean (224 source files),
and **1,853 tests in 31.67 seconds**. Coverage remains **89% reported**:
9,422 statements, 776 missing, 2,980 branches, 497 partial branches.
Counts and coverage denominators are identical to B; no cases were removed.
Relative to A, the suite still contains B's 42 additional cases.

Artifacts:
`.tmp/quality-runs/20260907151840521-36700-f15ebceb4f544d4abc7518b9303d88a2/`.
The artifacts remain ignored. Final whitespace and scope review passed.
No real provider/model calls, dependency changes, schema changes, or user-data
migrations were needed; the lifecycle migration operates only on a temporary
test database. No commit, push, or PR was performed.

Gate 3.2-C is ready for stakeholder review. D requires Gate 3.2-C approval and
explicit authorization; Step 3.2 is not yet marked complete. Final cross-document
synchronization and closeout remain D work.

## 9. Gate 3.2-C approval and Slice 3.2-D closeout — 2026-09-07

The project owner explicitly approved Gate 3.2-C and authorized Slice 3.2-D.
This accepts section 8's integration/acceptance evidence and supersedes its
historical pending-review status. D began from the approved B/C working tree
over pushed checkpoint `ee4db024bb10c061b2b17ccad41e35544ccd94e3`.
No source or test change was made during D.

### Documentation reconciliation and final dispositions

| Artifact / requirement | Final disposition |
| :--- | :--- |
| Master Plan | Records implemented repository scope and approved A/B/C gates; checkpoint prerequisite satisfied; final D approval remains pending and later work remains separately authorized. |
| Implementation Plan | Synchronizes status, selected sequence, decision record, technical acceptance checklist, and immediate actions. The three technical criteria are satisfied; Step 3.2 is not declared complete before final review. |
| Architecture | Documents current repository APIs, bounded key enumeration, stored-input inspection versus eligible cache reads, trajectory delegation, explicit errors, and borrowed connection ownership. Repository package layout and formerly planned persistence references now reflect implementation. |
| Discovery Workbook | Updates the repository layout/ownership statements and links to the durable architecture contract; historical decisions and unrelated research remain intact. |
| This handoff | Preserves the approved pre-implementation inventory as a labeled historical snapshot and records actual implementation, approval, verification, and gap dispositions. |
| G2 inspection | Satisfied by both bounded key-listing methods and financial `inspect`; no refresh or eligibility policy change. |
| G3/G4 audit storage and SQL placement | Satisfied by the trajectory repository and retained public sink/readback delegates; no second audit system or changed event contract. |
| G1/G5/G6/G7 existing foundations | Retained typed representations, round trips, connection policy, and analytical evidence access; no duplicate infrastructure or deferred product feature was added. |

### Final managed gate

The complete managed PowerShell wrapper passed on 2026-09-07: Ruff clean,
formatting clean (285 files), strict mypy clean (224 source files), and
**1,853 tests passed in 33.96 seconds**. Coverage remains **89% reported**:
9,422 statements, 776 missing, 2,980 branches, 497 partial branches.
Counts and coverage denominators are unchanged from approved C and B; the
42-case increase from A remains fully explained by B's regression additions.

Artifacts:
`.tmp/quality-runs/20260907152641011-37860-9f5323ced488480e8ed02f8ec3580468/`.
These local verification artifacts remain ignored and are not commit content.

All 23 relative Markdown link targets across the five changed documents resolve.
The new architecture section anchor matches the Discovery Workbook link.
Final whitespace and documentation scope checks passed. Active repository
status no longer describes storage as merely planned or B as awaiting its
already-pushed checkpoint. Earlier milestone design and per-slice execution
snapshots retain their original historical meaning.

D changed only the five documentation files listed above. All source and test
changes in the working tree belong to approved B/C. No commit, push, PR,
dependency/schema change, live provider/model call, or user-data migration was
performed in D.

**Final review:** Gate 3.2-D is ready for stakeholder approval. That approval is
required to mark Step 3.2 complete; no later milestone implementation is
implicitly authorized. Implementation checkpoint/PR work remains subject to
explicit authorization.

## 10. Final approval and Step 3.2 completion — 2026-09-07

The project owner granted final Gate 3.2-D approval and instructed recording
Step 3.2 as complete. All A–D gates are closed. The repository implementation,
integration acceptance evidence, and documentation reconciliation are accepted,
including the final managed gate in section 9: 1,853 passing tests, 89% reported
coverage, clean Ruff/formatting, and strict mypy.

Earlier pending-review statements in sections 7–9 remain historical execution
snapshots superseded by their subsequent approvals and this final decision.
The Master Plan and Implementation Plan now record Step 3.2 as complete and
approved. Step 3.3 and later implementation remain separately authorized.

The project owner requested commit, PR, and PR-comment drafts. This record does
not claim that the implementation has been committed, pushed, or merged, or
that a PR/comment has been published. Those workflow actions remain outstanding.
Approval recording changes documentation only; the accepted source/test state
and verification evidence are unchanged.
