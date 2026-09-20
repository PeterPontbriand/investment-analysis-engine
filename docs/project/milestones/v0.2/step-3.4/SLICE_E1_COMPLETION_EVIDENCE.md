# Slice E1 — Completion evidence

**Review disposition:** accepted by the project owner on 2026-09-19 (America/Toronto).
**Date:** 2026-09-19 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

D5 was accepted before this slice began. The project owner authorized E1
implementation directly, to be done in-session rather than handed to Cline,
specifically so E1 establishes a correct pattern before Cline attempts E2
(Number replay) against it.

## The audit required by §7

Contract §7 requires auditing "every method's concise/details/diagnostics/JSON
path for similar hidden computations before sharing render helpers." Reading
all of `src/reporting/momentum.py`'s four render paths line by line, exactly
one function produces a new financial number from raw stored values: the SMA
spread and its percentage (`_sma_spread`/`_sma_spread_percent`) — already
captured into `presentation_inputs` by D1. Every other computed helper
(`_trend_relationship`, `_trend_interpretation`, `_crossover_interpretation`,
`_crossover_state`, `_warnings`, `_data_summary`, and the various label/format
functions) turns already-known values into categorical labels or formatted
text — no new financial quantity, so no future formula could silently change
a rendered number. Only the spread substitution point needed a replay-safe
alternative; everything else is reused unmodified.

## A gap found in D5, fixed as an authorized amendment

Building the replay path required reconstructing a full `MomentumPresentation`,
which surfaced that `AnalysisRun` had no field for the composed
`InstrumentProfile` at all — `ExecutionCapture.profile` (correctly captured by
every D1–D4 adapter) was never threaded into anything `execute()` persisted.
Investigation narrowed this to a Momentum-specific gap, not a general D5
defect: Graham Number, Graham Growth, and FCF's native evidence types each
carry their own `instrument_profile` field natively (their analyzers receive
the profile as an input), so `encode_evidence()` already preserves it for
those three methods. Momentum's analyzer deliberately never sets
`MomentumRun.instrument_profile` (the profile is composed outside the
calculator, per the retained-without-recomputation contract requirement),
which is exactly why D1 kept `capture.profile` separate from `capture.run` —
correct then, but with nothing downstream to persist that separate value.

The project owner authorized fixing this as an amendment to already-accepted
B2/D5 files (plus this slice's own pre-acceptance E1 work) rather than
carrying it forward as a permanent limitation. The fix adds one field,
`AnalysisRun.instrument_profile: InstrumentProfile | None`, populated
uniformly by `execute()` from `ExecutionCapture.profile` for all four
methods (redundant with the native evidence for three of them, but giving
every future replay implementation one consistent field to read instead of
per-method fallback logic). This required no schema or migration change:
C3's repository already serializes the full `AnalysisRun` as one JSON
envelope column, and `InstrumentProfile` already round-trips through
pydantic JSON validation today, proven by B3's existing
`_MomentumEvidence(BaseModel): run: MomentumRun` wrapper (`MomentumRun`
itself carries an `instrument_profile` field). `_project_momentum_v1` now
reads `run.instrument_profile` instead of the native evidence's
always-null-for-Momentum copy.

## Design decision: an additive, opt-in field on the existing presenter

Rather than duplicating ~250 lines of `_concise_lines`/`_payload` assembly
logic to substitute one value, `MomentumPresentation` gained three new
fields — `use_captured_spread: bool = False`, `captured_sma_spread`,
`captured_sma_spread_percent` — defaulting to fully backward-compatible
behavior (every existing call site is unaffected; confirmed by two new tests
plus the entire unmodified existing presenter test suite passing unchanged).
Replay is the only caller that sets `use_captured_spread=True`. This keeps
one rendering implementation instead of two, while still guaranteeing replay
never calls `_sma_spread`/`_sma_spread_percent` on live metrics — a dedicated
test proves this by storing a deliberately wrong captured value and
confirming the rendered output shows the wrong (stored) number, not the
mathematically correct (recomputed) one.

## Delivered scope

- `src/reporting/analysis_runs.py`: `ReplayOptions`, `UnsupportedProjectionError`,
  `project_run(run, options) -> str`, dispatching by `(analysis_id, method_id)`
  with exactly one branch implemented (`_project_momentum_v1`). Internal
  invariants already guaranteed elsewhere (decoded-evidence type,
  requested/effective config type) are asserted, not re-validated, per the
  project's existing `assert config.eps_basis is not None`-style convention;
  `presentation_inputs`' lack of any per-key schema is treated as a genuine
  system boundary and is validated for real.
- `src/reporting/momentum.py`: the three additive `MomentumPresentation`
  fields and the `_effective_spread` substitution point described above.
- `src/workspace/runs.py` (D5-amendment, authorized): one additive field,
  `AnalysisRun.instrument_profile: InstrumentProfile | None`, plus a
  cross-field check that its ticker matches the run's own ticker.
- `src/workspace/execution.py` (D5-amendment, authorized): `execute()` now
  passes `instrument_profile=result.profile` through to the assembled
  `AnalysisRun`, uniformly for all four methods.
- `tests/reporting/test_momentum_presenter.py`: 3 new tests (backward
  compatibility, override wins over a matching real value, a captured null
  is preserved).
- `tests/reporting/test_analysis_run_replay.py`: the checked-in
  deterministic replay fixture (built through the real D5 `execute()` and a
  real Momentum adapter run against `FixtureDataClient`, so it is genuine
  captured evidence, not hand-built) with a deliberately mismatched stored
  spread; all four modes; JSON payload fidelity; unsupported projection
  version; unimplemented method; two malformed-`presentation_inputs` cases;
  a test patching the live analyzer and settings loader to raise, confirming
  replay never reaches them; and a new test proving replay renders the
  envelope's own captured profile rather than the native evidence's
  always-null-for-Momentum copy.
- `tests/workspace/test_runs.py`: default-None, JSON round-trip, and
  ticker-mismatch-rejection tests for the new field.
- `tests/workspace/test_execution.py`: the assembly test now asserts
  `run.instrument_profile` matches the captured profile; the real-repository
  round-trip test asserts it survives a reopen.
- `tests/data/repositories/test_analysis_runs.py`: a focused round-trip test
  inserting and reopening a run with a real captured profile.

## Contract proof (§7, §9)

| Contract requirement | Evidence |
| :--- | :--- |
| All modes from a reopened run | `test_project_run_all_modes_render_from_the_reopened_run` iterates every `PresentationMode` against one persisted-shape run. |
| Calculators/providers/settings/clock forbidden | A dedicated test patches `MomentumAnalyzer.run_with_context`/`run_analysis` and `ProjectSettings.get_momentum_analysis` to raise; replay still succeeds. `analysis_runs.py` has no `datetime.now()`/provider/cache import at all. |
| No recalculation | The strongest test stores a spread value the real fixture SMAs do **not** imply, and confirms the rendered text shows the stored (wrong) value — proof of consumption, not coincidental agreement. |
| Use the run's own projection version; no automatic fallback | `project_run` checks `run.projection_version` against the one implemented constant and raises `UnsupportedProjectionError` otherwise; tested directly. |
| Reject unsupported options/versions | Both an unsupported projection version and an unimplemented `(analysis_id, method_id)` pair raise the same typed error, tested separately. |
| Dedicated v1 path, checked-in deterministic fixtures | `_project_momentum_v1` is a separate function from the live `render_momentum` call path used by `src.cli`; the replay test fixture is a real, reproducible `AnalysisRun` built once and reused across all assertions. |

## Full managed gate

Ruff, Ruff format and strict mypy passed clean. The full pytest run:
**2,958 passed** (17 new in total: 3 in the presenter tests, 10 in the
replay tests, 3 in the run-envelope model tests, and 1 each in the
execution-service and repository tests for the D5-amendment field),
combined coverage **91%**; `reporting/analysis_runs.py`, `workspace/runs.py`
and `workspace/execution.py` each reach 100% line/branch coverage.

## Boundaries and review gate

No Number/Growth/FCF replay was implemented — those are E2–E4. No CLI wiring
(`runs show`) was introduced — that is F2. Nothing was committed, pushed, or
opened as a PR.
