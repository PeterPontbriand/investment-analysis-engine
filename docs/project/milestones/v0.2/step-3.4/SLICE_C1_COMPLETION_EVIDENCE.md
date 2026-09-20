# Slice C1 — Completion evidence

**Review disposition:** C1 reviewed and accepted by the project owner on 2026-09-16 (America/Toronto).
**Date:** 2026-09-16 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

B6 was accepted and committed at the starting revision. The project owner directly
authorized C1 implementation and required preservation of the uncommitted Step 3.5
planning work.

## Delivered scope and authorization

- `src/data/repositories/schema.py`: declarations for `watchlists`,
  `watchlist_members`, `watchlist_selections` and `analysis_runs`, including named
  keys, checks, foreign keys and query indexes.
- `alembic/versions/0002_research_workspace.py`: frozen successor revision with
  `down_revision = "0001_persistence"` and child-before-parent downgrade.
- Disposable schema, migration, readiness and database-maintenance tests in
  `tests/data/repositories/test_schema.py`, `test_migrations.py`,
  `test_readiness.py`, `test_maintenance_acceptance.py` and
  `tests/test_cli_database.py`.
- This completion evidence, required by the slice handoff protocol.

The schema/migration targets and disposable migration/readiness tests are the C1
edit surface expressly authorized by the direct implementation request. Adjusting
the existing structural and CLI maintenance fixtures to use the new head is part
of that proof. No prior completion evidence or planning status document was changed
as an agent judgment call. The Step 3.5 planning work was untouched.

## Schema contract

- Watchlists have immutable text IDs, unique normalized names, display names and
  checked UTC creation/update timestamps.
- Membership and selection tables use composite identity keys, unique positions
  per watchlist, nonnegative integer positions and cascading foreign keys to their
  watchlist. Selection snapshots require a positive configuration version and a
  valid JSON object.
- Analysis Runs are append-only schema records keyed by run ID. Indexed relational
  columns cover ticker, method, outcome, `(completed_at, analysis_run_id)` and
  `(refresh_id, batch_position)`. Refresh identity/position presence is paired.
- All six version columns are positive SQLite integers; outcomes use the frozen
  terminal-status set; completion timestamps use the existing canonical UTC
  storage shape; the complete run envelope must be a valid JSON object.
- Analysis Runs have no foreign key to watchlists, mutable caches or telemetry.
  Historical watchlist/profile/request snapshots remain owned by the envelope.
  No report table or duplicate rendered document was introduced.

## Migration and readiness proof

The pre-edit focused workspace baseline passed **442 tests**. The final focused
schema/migration/readiness suite passed **122 tests**.

| Contract proof | Evidence |
| :--- | :--- |
| Fresh head | Missing, zero-byte, empty and SQLite-internal-only disposable targets initialize directly at `0002_research_workspace`; reopen is `ready`. |
| Frozen migration parity | The real Alembic head has the same columns, named keys, checks, foreign keys and indexes as application metadata. The initial `0001` revision was not edited. |
| Explicit predecessor upgrade | A real disposable `0001_persistence` database is structurally verified, reported as `upgrade_required` by normal readiness, and upgraded only through the explicit maintenance path. |
| Existing data retained | A schema-metadata sentinel, telemetry event and resolved-input cache record survive the real `0001` → `0002` upgrade. |
| Rollback | A forced failure after creation of the first workspace table rolls back that table and retains the `0001` revision stamp and predecessor sentinel. |
| Downgrade | `0002` → `0001` removes only workspace tables, retains predecessor data, and can be upgraded to head again. Full `head` → `base` → `head` lifecycle also passes. |
| Schema signatures | Normal readiness recognizes both the valid predecessor signature and exact current-head signature; drift in tables, columns, constraints, indexes, views, triggers or required metadata remains incompatible. |
| SQL constraints | Tests reject blank identities, duplicate names/positions, invalid/negative/noninteger versions and positions, invalid outcomes/timestamps, malformed/non-object JSON and unpaired refresh metadata; child cascade and all Analysis Run indexes are verified. |
| No operational migration | All upgrade/downgrade/mutation tests use disposable SQLite files. The repository's real default `0001` database was left unchanged and continues to report upgrade required. |

## Complete managed gate

The first full gate correctly exposed that the repository's real default database
remains on the predecessor revision: direct CLI tests received the expected
upgrade-required preflight. It was not upgraded. The affected CLI tests passed
**72/72** against a disposable C1 database. Database-maintenance expectations were
then aligned with the new head.

The final full wrapper ran with a unique disposable `DATABASE_URL` and passed Ruff,
formatting (**359 files**), strict mypy (**264 source/test files**) and **2,842 tests
in 97.82 seconds**. Combined coverage is **90%** (11,595 statements, 863 missed).

Artifacts:
`.tmp/quality-runs/20260916160923911-10800-95ff378dfc144299a7ba3e8e0c2996f4/`.

Verification used the existing interpreter through automatically approved
`require_escalated` access because the managed sandbox could not query it. Commands
used `uv run --no-sync`; caches, test databases and full-gate temporary files were
repository-local. No dependency installation or synchronization occurred.

## Boundaries and review gate

No repository/service implementation, provider or LLM call, financial behavior,
CLI product behavior, operational database migration, dependency change, commit,
push or PR was introduced. C2 and C3 have not started.

C1 acceptance is recorded under the direct user instruction to record that fact.
C2 has not been started in this task.
