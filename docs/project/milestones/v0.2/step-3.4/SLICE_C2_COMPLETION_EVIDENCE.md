# Slice C2 — Completion evidence

**Review disposition:** C2 reviewed and accepted by the project owner on 2026-09-18 (America/Toronto).
**Date:** 2026-09-18 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

C1 was accepted before this slice began. The project owner authorized C2
implementation directly (see contract §11) after the standalone env-var
casing defect fix was completed.

## Delivered scope

- `src/workspace/watchlists.py`: `WatchlistSpec` (the creation input — a
  display name only), `normalize_ticker`, and the `encode_selection` /
  `decode_selection` JSON codec pair for the existing B1 `AnalysisSelection`
  union. Pure types and validation; no SQL.
- `src/data/repositories/watchlists.py`: `SQLiteWatchlistRepository` with
  `create`, `get`, `list`, `add_members`, `remove_members`, `set_selection`
  and `disable_selection`, plus `WatchlistConflictError` and
  `WatchlistNotFoundError`. Uses the C1 schema tables and the existing
  `SQLiteDatabase` connection/transaction scopes; injected clock and ID
  factory.
- Focused tests: `tests/workspace/test_watchlists.py` (codec/spec unit
  tests) and `tests/data/repositories/test_watchlist_repository.py`
  (repository integration tests against real migrated SQLite storage). The
  repository test file is named `test_watchlist_repository.py`, not
  `test_watchlists.py`, because the latter basename collides with the
  workspace-layer test module under pytest's default (non-`importlib`)
  collection; renaming the test avoided a broader, out-of-scope change to
  the test suite's import-mode configuration.
- This completion evidence.

`Watchlist` and `WatchlistSummary` themselves already existed in
`src/workspace/runs.py` from Slice B2; C2 did not modify that module.

## Contract proof

| Contract requirement (§5) | Evidence |
| :--- | :--- |
| Create / edit | `create` materializes no members and the frozen version-1 default selections (Momentum, Graham Number, historical FCF/Earnings Growth) via the existing `default_selections()`; `add_members`, `remove_members`, `set_selection`, `disable_selection` each round-trip through a fresh `get`. |
| Idempotence | Repeated `add_members`/`remove_members` with already-present/absent tickers, and `disable_selection` on an absent method, are no-ops that leave `updated_at` unchanged; verified explicitly. |
| Atomic conflict | Duplicate `create` (including a case/whitespace variant of an existing name) raises `WatchlistConflictError` and leaves storage at exactly one row across all three tables; a batch `add_members` call is validated (ticker normalization) before any row is written, so an invalid ticker leaves the member table untouched. |
| Order | Member and selection insertion order is preserved via monotonically assigned positions; a batch add follows the caller's argument order; a replaced selection keeps its original position, a new one is appended after the current highest. |
| Reopen | A dedicated test creates, edits and closes one `SQLiteDatabase`, then opens a second `SQLiteDatabase` against the same file and confirms the full `Watchlist` (members, selections, timestamps) round-trips unchanged. |
| No network calls | A dedicated test patches `socket.socket.connect`/`socket.create_connection` to raise and exercises the full create/edit/list/get lifecycle successfully. |
| Missing watchlist is an error | `add_members`, `remove_members`, `set_selection`, `disable_selection` each raise `WatchlistNotFoundError` for an unknown name. |

Selection JSON is stored and re-validated through the existing B1
discriminated `AnalysisSelection` union (via a `pydantic.TypeAdapter`), so a
stored selection's method/version identity is cross-checked against its own
`method_id`/`config_schema_version` columns on every read.

## Focused and full-gate results

The new modules reach 99% (`src/data/repositories/watchlists.py`, one
unreachable defensive branch) and 100% (`src/workspace/watchlists.py`) branch
coverage on their own 37 focused tests.

The full managed wrapper ran clean on Ruff, Ruff format (362 files) and
strict mypy (268 source/test files). The full pytest run collected 2,879
tests: 2,848 passed (including all 37 new C2 tests) and 31 failed, with
combined coverage at 90%.

**The 31 failures are a pre-existing baseline defect, not a C2 regression.**
They are confined to `tests/test_cli.py`, `tests/test_cli_graham_nonpositive_growth.py`,
`tests/data/test_massive_cli_configuration.py` and
`tests/test_graham_growth_default_policy.py` — files C2 does not touch, in
the Momentum/Graham CLI path that C2's edit surface (`workspace/watchlists.py`,
`repositories/watchlists.py`) has no import relationship with. Reverting the
working tree to the pre-C2 committed state and rerunning one representative
failing test (`test_cli_momentum_with_options`) reproduced the identical
failure, confirming it predates this slice. Root-causing and fixing it is
out of C2's bounded edit surface and is not addressed here.

## Boundaries and review gate

No CLI, execution/adapter, run-repository (C3), or reporting code was
introduced. No financial calculation, provider, dependency, or migration
change was made. Nothing was committed, pushed, or opened as a PR; C3 has
not been started.
