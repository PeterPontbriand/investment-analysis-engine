# Slice D2 — Completion evidence

**Review disposition:** D2 reviewed and accepted by the project owner on 2026-09-18 (America/Toronto).
**Date:** 2026-09-18 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

D1 was accepted before this slice began. The project owner authorized D2
implementation directly, to be done in-session rather than handed to Cline.

## Delivered scope

- `src/workspace/graham_number_execution.py`: `execute_graham_number`
  (composes the profile and calls the existing `GrahamNumberAnalyzer`
  exactly as `_run_graham_number` did) and `classify_graham_number_outcome`
  (the frozen native-status → `RunOutcome` mapping), plus the
  `GrahamNumberCapture` result type.
- `src/workspace/graham_shared.py`: `compose_graham_profile`, relocated
  unchanged from `src.cli`'s private `_compose_analysis_profile`. This
  helper is genuinely method-agnostic — Graham Number, Graham Growth, and
  FCF all use it identically — and had to move to the workspace layer
  rather than stay in `cli.py`: the Number adapter needs it, and importing
  it from `src.cli` into a workspace module would be a circular import
  (`src.cli` imports the Number adapter at module load time). `src/cli.py`
  now imports it back for Graham Growth's and FCF's still-inline usage.
- `src/cli.py`: `_run_graham_number`'s inline profile composition and
  analyzer invocation is replaced with a call to `execute_graham_number`;
  presentation, exit-code selection, and failure rendering are unchanged.
  `GrahamNumberAnalyzer` is no longer imported directly.
- `tests/test_cli.py`, `tests/test_cli_fcf_earnings_growth.py`,
  `tests/test_cli_financial_cache.py`: patch targets for the relocated
  profile-composition helper updated to follow it to its new module (or, for
  the two tests parametrized across all three methods, patched in both the
  new Number-adapter location and the still-inline `src.cli` location, since
  each parametrization exercises a different call site now).
- `tests/workspace/test_graham_shared.py` (2 tests) and
  `tests/workspace/test_graham_number_execution.py` (9 tests): focused,
  fake-dependency-only tests for the relocated helper and the new adapter,
  including all six native-status combinations for the outcome mapping.
- This completion evidence.

## Contract proof (§4, §6, §9)

| Contract requirement | Evidence |
| :--- | :--- |
| Existing Number CLI/output/comparison regressions | Every pre-existing Graham Number (and, where shared helpers are touched, Graham Growth and FCF) CLI test in `tests/test_cli.py`, `tests/test_cli_fcf_earnings_growth.py`, and `tests/test_cli_financial_cache.py` passes unchanged; only patch targets moved to follow relocated code. |
| Exact capture/status mapping | `classify_graham_number_outcome` is tested against all six native `(assembly.status, result.status)` combinations that can occur: OK/OK → completed, OK/invalid_input → failed, not_applicable → not_applicable, input_unavailable → unavailable, invalid_input → failed, provider_error → failed — matching §4's frozen mapping directly. |
| Capture the exact profile supplied to each analyzer | `execute_graham_number` reproduces the CLI's own fallback (`analysis.instrument_profile or composed_profile`) exactly; both branches (analyzer returns its own profile vs. falls back to the composed one) are tested explicitly. |
| Fake dependencies only | Every adapter test uses a fixture-backed `GrahamNumberInputResolver` (`FixtureFinancialFactsProvider`), the existing `fixture_instrument_profile` helper, and mocked/patched analyzer calls — no real provider or network path; a dedicated test patches `socket.socket.connect`/`socket.create_connection` to confirm none is reachable. |
| Bounded `_run_graham_number` extraction | Only the profile-composition-then-analyzer-invocation seam moved out; the assembly-status branching, presentation construction, and exit-code selection remain in `src.cli` untouched. |

## Full managed gate

Ruff, Ruff format (373 files) and strict mypy (276 source/test files) passed
clean. The full pytest run: **2,907 passed** (11 new for this slice), combined
coverage **90%**; both new modules (`graham_number_execution.py`,
`graham_shared.py`) reach 100% line/branch coverage on their own focused
tests.

## Boundaries and review gate

No Graham Growth or FCF adapter, execution service, run persistence,
`--save-run` CLI flag, replay/reporting, or refresh code was introduced —
those remain D3–D5, E-series, F-series and G-series. No financial
calculation changed; Graham Number's math and CLI output are identical to
before this slice. Nothing was committed, pushed, or opened as a PR.
