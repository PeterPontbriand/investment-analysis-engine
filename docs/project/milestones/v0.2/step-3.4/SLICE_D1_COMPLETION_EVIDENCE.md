# Slice D1 — Completion evidence

**Review disposition:** D1 reviewed and accepted by the project owner on 2026-09-18 (America/Toronto).
**Date:** 2026-09-18 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

C3 was accepted before this slice began. The project owner authorized D1
implementation directly, to be done in-session rather than handed to Cline.

## Delivered scope

- `src/workspace/momentum_execution.py`: `run_momentum` (borrows a
  `BaseDataClient` and calls the existing `MomentumAnalyzer` exactly as the
  CLI did) and `capture_momentum` (bundles the resulting `MomentumRun` with
  a caller-composed `InstrumentProfile` and captured display-derived
  values — the SMA spread and its percentage, using the same formulas
  `src/reporting/momentum.py` already computes at render time), plus the
  `MomentumCapture` result type. No provider, cache, or database lifecycle is
  owned here.
- `src/cli.py`: the `momentum` command's inline analyzer construction and
  invocation is replaced with a call to `run_momentum`; profile composition
  is unchanged and still happens after the historical-client context
  manager exits, in the same order as before. `MomentumAnalyzer` is no
  longer imported directly by `cli.py`.
- `tests/test_cli.py`: the ten `@patch("src.cli.MomentumAnalyzer.run_with_context")`
  decorators now target `src.workspace.momentum_execution.MomentumAnalyzer.run_with_context`,
  the module that actually constructs and calls the analyzer now. This is
  the same underlying class object either way; only the patch path changed
  to match where the call now happens.
- `tests/workspace/test_momentum_execution.py`: 7 focused tests using only
  fake dependencies (`FixtureDataClient`/a small provider-ID-bearing
  subclass of it, and the existing `fixture_instrument_profile` helper —
  no real network, provider, or database access anywhere).
- This completion evidence.

## Design note: why `run_momentum` and `capture_momentum` are separate

The existing CLI command composes the instrument profile strictly *after*
the historical-client context manager has exited (so the SQLite-backed
cache connection is closed before profile composition, which does not need
it). An initial single-function design would have forced profile
composition to happen *inside* that scope instead, which is not a
functional bug (`compose_instrument_profile` never touches the historical
cache) but is an avoidable, unrequested change to existing resource-lifetime
ordering. Splitting the adapter into `run_momentum` (the analyzer call,
called inside the borrowed client's scope) and `capture_momentum` (pure
bundling plus derived-value capture, called after) lets `src/cli.py`
preserve its exact original ordering while still sharing real code with the
adapter, rather than duplicating the analyzer-invocation logic to preserve
that ordering.

## Contract proof (§6, §9)

| Contract requirement | Evidence |
| :--- | :--- |
| Same direct output/math | All pre-existing Momentum CLI tests in `tests/test_cli.py` pass unchanged (assertions untouched) after the extraction; only their mock patch target moved to follow the analyzer call to its new location. |
| Captured price inputs/profile | `MomentumCapture.run` retains the native `MomentumRun` (metrics, market data, price inputs, resolution trace, data resolution) untouched; `MomentumCapture.profile` is exactly the profile object the caller composed, identity-checked in tests (`capture.profile is profile`). |
| Captured display derivations | `capture_momentum` computes `sma_spread`/`sma_spread_percent` using the same formulas as `src/reporting/momentum.py`'s private `_sma_spread`/`_sma_spread_percent`, verified equal in a dedicated test; None/zero-long-SMA guard cases are covered directly. |
| Fake dependencies only | Every adapter test uses `FixtureDataClient` (or a minimal provider-ID-bearing subclass of it) and the existing `fixture_instrument_profile` fixture; a dedicated test patches `socket.socket.connect`/`socket.create_connection` to confirm no real network path is reachable. |
| Minimal CLI execution extraction | Only the `MomentumAnalyzer` construction and `run_with_context` call moved out of `src/cli.py`; presentation, error handling, option parsing, and profile composition in the CLI are unchanged. |

## Full managed gate

Ruff, Ruff format (368 files) and strict mypy (272 source/test files) passed
clean. The full pytest run: **2,896 passed** (7 new for this slice), combined
coverage **90%**; `src/workspace/momentum_execution.py` reaches 100%
line/branch coverage on its own focused tests.

## Boundaries and review gate

No Graham or FCF adapter, execution service, run persistence, `--save-run`
CLI flag, replay/reporting, or refresh code was introduced — those remain
D2–D5, E-series, F-series and G-series. No financial calculation changed;
Momentum's math and CLI output are identical to before this slice. Nothing
was committed, pushed, or opened as a PR.
