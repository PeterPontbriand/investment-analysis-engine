# Slice D5 — Completion evidence

**Review disposition:** D5 reviewed and accepted by the project owner on 2026-09-18 (America/Toronto).
**Date:** 2026-09-18 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

D4 was accepted before this slice began. The project owner authorized D5
implementation directly, to be done in-session rather than handed to Cline.
D5 completes the D-series: all four method adapters (D1–D4) now have a
common way to become a persisted `AnalysisRun`.

## Design decisions requiring judgment (documented per the handoff protocol)

The contract's own language for D5 is intentionally terse — "`workspace/execution.py`;
inject capture, ID, clock and repository" — leaving several concrete choices
unresolved. None of them contradicted the frozen interface enough to justify
stopping for an amendment; each is recorded here for review rather than left
implicit.

1. **"Capture" is an injected zero-argument callable, not a finished value.**
   §6 states "the service owns IDs/timing and capture." Read literally, the
   service must be the one to *invoke* the method adapter, not merely receive
   its already-finished result — otherwise it could not time the attempt
   itself. `execute()` therefore takes `capture: Callable[[], ExecutionCapture]`
   and calls it once, timing `started_at`/`completed_at` around that one call.

2. **A normalized `ExecutionCapture` type, with one small converter function per
   method.** D1–D4 return four differently-shaped dataclasses
   (`MomentumCapture.run`, `GrahamNumberCapture.analysis`,
   `GrahamGrowthCapture.analysis`, `FCFGrowthCapture.result` — different field
   names, and Momentum's has no `outcome` field at all since Momentum has no
   native applicability/validity status). Rather than have `execute()` know
   about all four shapes (a `isinstance`/`match` ladder that would grow with
   every future method) or retrofitting D1–D4's already-accepted dataclasses
   with a common field name, this slice adds one explicit converter per method
   (`from_momentum_capture`, `from_graham_number_capture`,
   `from_graham_growth_capture`, `from_fcf_growth_capture`) that each do a
   trivial field rename into one shared `ExecutionCapture(native_evidence,
   profile, outcome, presentation_inputs)`. This is explicit dispatch by
   name, not a registry or plugin mechanism, matching the contract's
   repeated instruction against inventing a generic strategy hierarchy.
   Momentum's outcome is always `RunOutcome.COMPLETED` when `capture()`
   returns without raising, since Momentum has no native failure/
   not-applicable status distinct from an exception.

3. **A capture-time exception is not caught here; a persistence-time
   exception is never converted into a stored record.** The contract
   explicitly forbids turning a storage exception into "a successfully
   stored failed-analysis record," and separately notes that "a killed
   process may leave no record for in-flight/unstarted jobs" is an accepted
   limitation. Reading these together: `execute()` catches nothing. If
   `capture()` raises, nothing is stored and the exception propagates
   unchanged (matching the existing CLI's own `execution_errors` boundary,
   which already classifies analyzer/provider failures safely — duplicating
   that classification inside `execute()` would create a second, divergent
   place doing the same job). If `repository.insert()` raises, that also
   propagates unchanged; `execute()` never falls back to inserting a
   different, simplified failure record instead.

4. **No separate readiness check inside `execute()`.** D5's injected
   dependencies are exactly "capture, ID, clock and repository" — no
   readiness callable is listed. `repository` is documented as received
   already composed and ready, matching the existing pattern where
   readiness is checked once at composition (for example
   `_production_historical_client`), not per operation. "Ready before work,
   never a false success" is satisfied at this layer by the ordering
   guarantee in point 3, not by a redundant readiness probe; composing an
   already-ready repository remains the caller's job (F3).

5. **`failure_reason_code` is one stable, method-agnostic string
   (`"execution_failed"`) rather than a per-method detailed code.** The
   detailed reason (Graham's `assembly.reason`/`result.reason`, FCF's
   `classification_reason`, etc.) is already preserved unmodified inside
   `result_evidence`, satisfying "retained available evidence." Deriving a
   more granular top-level code would require `execute()` to know each
   method's native reason shape, reintroducing the per-method coupling
   point 2 avoids.

6. **Temporal-boundary fidelity (`effective_boundary`, `source_observation_dates`,
   `source_retrieval_at`) is left at its default (unset).** These are
   optional fields on `AnalysisRun`; deriving them precisely per method
   (Momentum's `market_data.data_as_of`, FCF's `period_start`/`period_end`,
   etc.) is real fidelity work with its own proof obligations, not
   mentioned in D5's stated scope ("Readiness before work; insert-before-
   success; persistence error visible; telemetry independent"). Leaving
   them unset keeps this slice bounded to save-service mechanics; a future
   slice can populate them once specifically authorized.

## Delivered scope

- `src/workspace/execution.py`: `ExecutionCapture` (the normalized shape),
  `AnalysisRunSink` (a minimal `Protocol` needing only `insert`, so this
  module never imports from `src.data.repositories`), the four `from_*_capture`
  converters, and `execute(request, *, capture, repository, id_factory, clock)`.
- `tests/workspace/test_execution.py` (14 tests): orchestration/ordering
  tests with fake capture callables and a fake sink, all four converter
  functions, a stable-failure-reason-code test, a capture-raises-nothing-
  inserted test, a persistence-error-propagates test, a
  capture-called-exactly-once test, a no-network guard, and one true
  end-to-end test against a real `SQLiteAnalysisRunRepository` (C3),
  reopened, confirming the persisted run round-trips exactly.
- This completion evidence.

## Contract proof (§4, §6, §9)

| Contract requirement | Evidence |
| :--- | :--- |
| Readiness before work / insert-before-success | The real-repository end-to-end test inserts through an actually-migrated database and reads it back after reopening; `repository.insert` is always the last statement in `execute`, confirmed never called when `capture()` raises. |
| Persistence error visible | A fake sink raising `AnalysisRunConflictError` on `insert` causes `execute()` to raise that exact exception uncaught — no substitute success or substitute failure record is produced. |
| Telemetry independent | `execution.py` imports nothing from `src.core.telemetry`; there is no telemetry dependency in `execute()`'s signature for a caller to even wire in at this layer. |
| Method version / result schema version correctness | The completed-run assembly test asserts `method_version=1`/`result_schema_version=1` for Momentum and confirms the resulting envelope round-trips through the existing `codecs.decode_evidence`; the version table also encodes FCF's distinct `(2, 3)` pair used by all three Graham/Momentum entries' `(1, 1)`. |
| Outcome-dependent fields | `failure_reason_code` is set only when `status is FAILED`, verified for `NOT_APPLICABLE`, `UNAVAILABLE`, and `COMPLETED` all leaving it `None`. |

## Full managed gate

Ruff, Ruff format (382 files) and strict mypy (282 source/test files) passed
clean. The full pytest run: **2,941 passed** (14 new for this slice), combined
coverage **90%**; `execution.py` reaches 100% line/branch coverage on its
own focused tests.

## Boundaries and review gate

No CLI wiring (`--save-run`), replay/reporting, or refresh code was
introduced — those remain E-series, F-series and G-series. No financial
calculation changed. `execute()` is not called from anywhere in production
code yet; F3 is the slice that will compose real dependencies (a live,
ready repository; real adapter closures) and call it from the four direct
commands. Nothing was committed, pushed, or opened as a PR.
