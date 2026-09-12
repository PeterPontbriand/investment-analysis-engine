# Step 3.3A — Slice B Readiness Review

**Status:** Slice B approved and Slice C explicitly authorized on 2026-09-12 (Toronto). Implementation and Windows verification are complete. Gate A was approved on 2026-09-12 (Toronto): “Gate A is approved and Slice B implementation is authorized. Proceed.”

**Authority:** [Contract and Slice Plan](STEP_3_3A_CONTRACT_AND_SLICE_PLAN.md#6-slices-and-review-gates) and [approved concrete contract](SLICE_A_CONTRACT_AND_VERIFICATION.md). Implementation branch: `codex/step-3.3a-readiness`, based on contract checkpoint `d912d4d`. Changes are uncommitted; no push or PR was performed.

## Implemented behavior

`ensure_database_ready(SQLiteDatabase)` returns typed ready/initialized outcomes or a sanitized `DatabaseReadinessError`. It resolves migration resources before touching storage and inspects existing files read-only before application connection policy can enable WAL. Only verified empty storage is initialized through the real Alembic migration, inside the caller-owned transaction; final schema verification precedes commit.

Existing storage must match the unique bundled revision, encoding metadata and canonical schema. Validation covers tables, columns, types, nullability, defaults, primary/foreign/unique/check constraints, indexes and unexpected objects. Canonical SQLite DDL comparison also catches reflection omissions such as collations and descending/expression indexes. This deliberately accepts the supported Alembic-created schema rather than inferring compatibility from a head stamp. SQLite-owned internal objects do not alone disqualify otherwise empty storage.

A persistent sibling `.readiness.lock` coordinates initialization and explicit manual migrations before normal connection setup. OS ownership is bounded by the existing database busy timeout and released on scope exit or process termination; the sidecar is never unlinked or truncated. Waiting initializers recheck committed state. In-memory readiness uses the same `SQLiteDatabase` instance and its existing sequential transaction policy without a sidecar.

The Alembic runner accepts an active borrowed connection without committing, closing or replacing it, rejects conflicting target overrides, and preserves existing manual URL precedence. Resources are located from the source installation, independently of the working directory and configured data directory. Missing or invalid resources fail before storage creation.

## Change inventory

| Files | Responsibility |
| :--- | :--- |
| `src/data/repositories/readiness.py` | Classification, strict schema checks, atomic initialization and authored error categories. |
| `src/data/repositories/readiness_lock.py` | Windows/POSIX OS ownership and bounded acquisition. |
| `src/data/repositories/migrations.py` | Resource discovery, borrowed transaction seam and manual migration coordination. |
| `src/data/repositories/sqlite.py`, `__init__.py` | Read-only resolved-path/timeout properties and readiness exports. |
| `tests/data/repositories/test_readiness.py` | Lifecycle, preservation, drift, resource, memory, rollback and error cases. |
| `tests/data/repositories/test_readiness_concurrency.py` | Independent spawned-process ownership, manual coordination, timeout and crash recovery. |
| `tests/data/repositories/test_migrations.py` | Borrowed ownership, conflicting targets and revision-resource graphs, alongside existing manual migration regressions. |
| Milestone planning documents | Record Gate A approval, Slice B evidence and the next review boundary. |

No schema revision, dependencies, financial calculations, providers, CLI composition or telemetry behavior changed.

## Verification evidence

The full non-mutating managed wrapper passed on **2026-09-12 (Toronto)** against the uncommitted Slice B implementation based on `d912d4d`:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

| Check | Result |
| :--- | :--- |
| Ruff check | Passed. |
| Ruff format check | 320 files already formatted. |
| Strict mypy | Passed, 244 source/test files. |
| Pytest | **2,119 passed**, 47.58 seconds. |
| Overall coverage | **90%**, above the 85% requirement. |
| Environment | Windows, Python 3.14.7, pytest 9.1.1. |
| Reconciliation | Approved fresh baseline: 2,054 tests / 89%; 65 added cases, no removed tests. |

Isolated artifacts: `.tmp/quality-runs/20260912090421456-29664-994a5d23151b4795a660c8c4c8155c3c/`. Captured gate output: `.tmp/slice-b-final-gate.txt`. These ignored local artifacts are not commit content.

Deterministic tests prove fresh missing/empty storage, preserved records on reopen without remigration, refusal of incompatible files before journal-policy changes, schema drift and malformed-file classification, synthetic known ancestors, same-instance memory ownership, rollback at DDL/revision/post-verification failures, and missing-resource failure before directory creation. Process tests synchronize through IPC, proving one automatic initialization, a waiting automatic or manual peer, bounded timeout, and reacquisition plus safe retry after a migration owner exits abruptly.

All database tests use disposable local storage. No operational database was accessed or migrated, no live provider or LLM was called, and no dependencies were installed. The full regression suite includes the existing four analysis strategies and repository/cache behavior.

## Limits and next gate

Windows runtime evidence covers `msvcrt` ownership. The conditional POSIX `flock` implementation and portable process tests are present, but Linux/macOS execution was not performed locally and is not claimed. The production revision graph currently has one revision; known-ancestor classification is verified with a synthetic graph. Source-checkout/editable installation resources remain the supported boundary; standalone wheel migration packaging is not added.

CLI callers do not yet invoke readiness. Default first-use analysis behavior, safe CLI error serialization, bypass/help independence and telemetry composition therefore remain Slice C work. Durable user-facing behavior documentation and final acceptance remain Slice D work; the full Step 3.3A acceptance matrix is not yet complete.

**Review decision:** On 2026-09-12, the project owner instructed: “As well, record my approval Slice B and my authorization to proceed with Slice C.” Slice B is accepted. Slice C is authorized with the [hidden database maintenance amendment](SLICE_C_MAINTENANCE_AMENDMENT.md); implementation evidence for C remains pending. Stop for Slice C review before D. Step 3.4 remains deferred until Step 3.3A final acceptance.
