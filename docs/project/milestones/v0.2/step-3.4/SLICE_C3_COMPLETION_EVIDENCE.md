# Slice C3 — Completion evidence

**Review disposition:** C3 reviewed and accepted by the project owner on 2026-09-18 (America/Toronto).
**Date:** 2026-09-18 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

C2 was accepted before this slice began. The project owner authorized C3
implementation directly, to be done in-session rather than handed to Cline.

## Delivered scope

- `src/data/repositories/analysis_runs.py`: `SQLiteAnalysisRunRepository`
  with `insert`, `get` and `list`, plus `AnalysisRunConflictError`. Uses the
  C1 schema's `analysis_runs` table and the existing `SQLiteDatabase`
  connection/transaction scopes.
- Focused tests: `tests/data/repositories/test_analysis_runs.py` (10 tests),
  reusing the four existing B3–B6 codec tests' private `_run()` fixture
  builders (`tests.workspace.test_momentum_codec`,
  `test_graham_number_codec`, `test_graham_growth_codec`,
  `test_fcf_growth_codec`) rather than duplicating their evidence-building
  fixtures — the same cross-test-module import pattern already used
  elsewhere in this suite (e.g. `tests/analysis/shared/test_financial_resolution.py`
  importing from `tests/analysis/test_instrument_applicability.py`).
- This completion evidence.

The full `AnalysisRun` envelope (identity, request, time, versions, outcome,
evidence, presentation inputs — all already-validated Pydantic fields,
including the B1 discriminated `AnalysisSelection` union) round-trips through
`model_dump(mode="json")` / a `TypeAdapter(AnalysisRun)` as one JSON document;
the repository does not call the B3–B6 method-specific evidence codecs
(`encode_evidence`/`decode_evidence`) itself — those operate one level down,
on the `result_evidence` field's contents, and remain a concern for the
adapter/execution (D-series) and replay (E-series) layers.

## Contract proof (§4, §5)

| Contract requirement | Evidence |
| :--- | :--- |
| Four typed round trips after reopen | One real `AnalysisRun` per method (Momentum, Graham Number, Graham Growth, FCF) is inserted, the database is closed, a second `SQLiteDatabase` is opened against the same file, and each run is read back and compared for full equality against the original. |
| Duplicate ID rejection | Inserting the same `analysis_run_id` twice raises `AnalysisRunConflictError`; storage is confirmed to still hold exactly one row. |
| Filter/tie ordering | Three runs (two sharing one completion timestamp, one earlier) are listed with no filter to verify completion-descending-then-ID-descending order, then filtered by `ticker`, `ticker`+`method_id` together (AND), `status`, and a non-matching `refresh_id`. |
| Independently durable outcomes / relational-envelope agreement | A stored envelope tampered with directly at the SQL layer — either replaced with a still-valid-but-unrelated JSON object, or left valid while its `ticker` column is changed independently — is rejected by `get` with a plain `ValueError`, while `list` (which never decodes `envelope_json`) still reports the row from its indexed summary columns. |
| Independent cache/telemetry deletion cannot erase runs | After inserting a run and a watchlist, real deletes against `trajectory_events`, `resolved_input_cache` and `market_data_cache_entries` leave the run and the watchlist both fully intact and readable — `analysis_runs` has no foreign keys, as the C1 schema already established. |
| No network calls | A dedicated test patches `socket.socket.connect`/`socket.create_connection` to raise and exercises insert/get/list successfully. |
| Naive-timestamp rejection | Inserting a run whose `completed_at` was replaced with a naive datetime (via `model_copy`, bypassing the model's own `AwareDatetime` validation) is rejected before any row is written. |

`list` bounds (`limit` default 20/range 1–100, `offset` default 0) are
enforced by `RunQuery` itself (a frozen Pydantic model with `Field` bounds),
so the repository does not re-validate them; a paging test confirms the
default page size and boundary behavior at the edge of the inserted set.

## Full managed gate

Ruff, Ruff format (365 files) and strict mypy (270 source/test files) passed
clean. The full pytest run: **2,889 passed** (10 new for this slice), combined
coverage **90%**; `src/data/repositories/analysis_runs.py` itself reaches
100% line/branch coverage on its own focused tests.

## Boundaries and review gate

No CLI, execution/adapter, watchlist-repository, or reporting code was
changed. No financial calculation, provider, dependency, or migration change
was made. Nothing was committed, pushed, or opened as a PR.
