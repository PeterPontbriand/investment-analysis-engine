# Step 2.5 Gate M Review

**Review date:** 2026-08-31<br/>
**Checkpoint:** `4d08b1273fe3e226f69b3a47e9680e9e70d001eb` on `feat/step-2.5-golden-suite`<br/>
**Repository state at review start:** clean; checkpoint already pushed<br/>
**Original decision:** **Gate M not approved; mandatory bounded Slice H correction required**<br/>
**Re-entry decision:** The corrected Gate M result was subsequently accepted; Slices I–J were also explicitly reviewed and accepted<br/>
**Current status:** Historical Gate M record; current work is at the final approval gate documented in the [Step 2.5 Closeout Verification Record](STEP_2_5_CLOSEOUT_RECORD.md)

## 1. Purpose and review boundary

Gate M is the mandatory stop after the minimum deterministic Golden Suite. This
review inspected the checkpoint rather than accepting implementation summaries
at face value. It covered:

- the typed case, expectation, observation, component-result, report, evaluator,
  runner, fixture-composition, and case-catalog implementation;
- the exact minimum case set and its coverage of the governing Step 2.5
  requirements;
- whether expected successful and non-success domain outcomes are enforced by
  the aggregate benchmark, not merely asserted in adjacent unit tests;
- whether one canonical operation can execute and report the full minimum suite;
  and
- the complete repository quality gate.

This review does not authorize code changes, case-expectation changes, CLI work,
real-local-Ollama work, or Step 2.5 completion.

## 2. Verification evidence

| Check | Result | Evidence / consequence |
| :--- | :--- | :--- |
| Checkpoint identity | Pass | `HEAD` exactly matched the pushed checkpoint SHA above. |
| Initial worktree state | Pass | `git status --short` returned no changes. |
| Ruff check | Pass | The repository quality-gate wrapper reported `All checks passed!`. |
| Ruff format check | Pass | The wrapper reported `211 files already formatted`. |
| Strict mypy | **Fail** | `76` errors in `4` files; the mandatory wrapper stopped here. |
| Focused evaluation tests | Pass | `217 passed` in `5.21s`. |
| Complete pytest suite | Pass | `1189 passed` in `13.60s`; overall line coverage was `87%`. |
| Canonical 12-case report | **Unavailable** | No catalog/request-builder entry point executes all reviewed cases as one suite. |

The strict-typing failures are concentrated in:

- `tests/evaluation/test_models.py` and
  `tests/evaluation/test_evaluator.py`: list literals are passed to model fields
  whose strict static types are tuples;
- `tests/evaluation/test_reporting.py`: one missing return annotation and one
  unsafe union attribute access; and
- `tests/evaluation/fixtures/test_momentum_graham_expectations.py`: timezone
  access through a pandas `Index[Any]` type that does not guarantee `.tz`.

Passing pytest does not override the failed project gate. The Gate M evidence is
therefore red even before the semantic benchmark defects below are considered.

## 3. Minimum case inventory and requirement fit

The checkpoint contains exactly twelve stable case IDs.

| Case | Intended signal | Aggregate-contract assessment |
| :--- | :--- | :--- |
| `MOM-01` | Straightforward Momentum arithmetic | Adequately represented numerically. |
| `MOM-02` | Insufficient long-window boundary | **Incomplete:** unavailable long-SMA/crossover statuses are not first-class expectations. |
| `GRN-01` | Default three-year-average Graham Number | Adequately represented numerically and by method constraint. |
| `GRN-02` | Explicit TTM Graham Number | Adequately represented numerically and by method constraint. |
| `GRA-ETF-01` | Known ETF is not applicable to Graham Number | **Incomplete:** report can pass without asserting the native `not_applicable` outcome or reason. |
| `GRN-03` | Missing quote preserves valid Graham Number | Numerically useful; optional-price status is tested outside the case expectation. |
| `GRG-01` | Explicit Graham growth-value method | Adequately discriminates the Graham method and verifies arithmetic. |
| `GRN-04` | Override/cache/provider precedence | Useful numerical consequence; direct tests carry most lineage assertions. |
| `GRN-05` | Historical `as_of` look-ahead rejection | **Incorrect aggregate semantics:** expected input unavailability is not encoded as a passing outcome. |
| `FCF-01` | Straightforward aligned FCF/EPS growth | Adequately represented numerically. |
| `FCF-02` | Interior sign change makes compound growth nonmeaningful | **Incomplete:** status, reason, and classification are not first-class expectations. |
| `FCF-03` | Period alignment and historical `as_of` rejection | **Incorrect aggregate semantics:** the correct expected `input_unavailable` result is reported as a fixture failure. |

The minimum set covers the named strategy families and principal numerical
paths, but it does not yet satisfy the full cross-strategy ETF requirement. The
governing plan requires one provider-confirmed ETF scenario to prove all four
strategy outcomes: Momentum applicable; Graham Number, Graham growth value, and
company-level FCF Growth `not_applicable`. The Golden catalog currently exercises
only Graham Number for that scenario. Separate production tests are valuable but
do not make the missing Golden cases appear in the benchmark report.

## 4. Blocking findings

### GM-1 — Mandatory quality gate fails

Severity: blocking.

The project requires Ruff, format, strict mypy, and pytest to pass. Strict mypy
reports 76 errors, so the checkpoint cannot pass Gate M or Step 2.5 closeout.
These are bounded test-typing corrections; they do not justify changing
production financial behavior.

### GM-2 — Correct expected domain outcomes are treated as failures or go unproved

Severity: blocking.

The runner currently classifies any observed `input_unavailable` or
`provider_error` status as a fixture failure. That rule is invalid for cases
whose purpose is to prove a deliberate historical boundary. `FCF-03` therefore
correctly reaches `input_unavailable` but is expected by its own test to fail the
Golden report. `GRN-05` has the same contract risk.

The inverse problem also exists: `not_applicable`, metric availability, reason,
and classification fields can go unasserted. `BehaviorConstraints` and a
behavior evaluator exist, but the deterministic runner does not integrate them,
and the reviewed cases do not encode the necessary observable outcomes. A case
must pass only when its expected domain outcome is observed; an expected
non-success domain result is not an infrastructure failure.

### GM-3 — No canonical full-minimum-suite execution exists

Severity: blocking.

Case tuples and request construction are distributed across modules and tests.
There is no reviewed `ALL_CASES`-style catalog plus deterministic request builder
that executes the exact twelve cases and emits one report with stable suite and
fixture-set versions. Per-strategy test invocations do not satisfy Gate M's
requirement to run and record the full minimum suite.

This is an internal deterministic harness boundary, not the user-facing CLI
owned by Slice J.

### GM-4 — The cross-strategy ETF contract is absent from the Golden denominator

Severity: blocking against the governing minimum composition.

`GRA-ETF-01` proves only the Graham Number route. The benchmark needs three
additional stable cases using the same reviewed ETF profile evidence:

- `MOM-ETF-01`: Momentum remains applicable and executes with deterministic
  price evidence;
- `GRG-ETF-01`: Graham growth value returns its native `not_applicable` outcome;
  and
- `FCF-ETF-01`: company-level FCF Growth returns its native `not_applicable`
  outcome.

Together with `GRA-ETF-01`, these cases form one cross-strategy scenario without
creating a multi-tool generic case shape. Fifteen cases remain within the
approved 10–18 initial range.

### GM-5 — Current planning and evaluation documentation is stale

Severity: blocking for a trustworthy handoff.

The evaluation guide still describes typed models, evaluators, reports, runners,
and cases as unimplemented. The slice plan still stops before A1 and records
A1–G4 as pending. The implementation plan says to expand automatically after
Gate M even though its detailed slice plan correctly requires review-directed
changes. These discrepancies could send the next implementer to the wrong work.

## 5. Approved Slice H corrective scope

Slice H is now mandatory and limited to the following work after the current
documentation-only checkpoint is reviewed:

1. Correct the 76 strict-mypy failures without changing benchmark criteria or
   production calculations.
2. Add a narrowly typed way for a case to expect observable native domain
   outcomes, including result/calculation status, metric availability where
   material, reason code, and classification where material. Do not create a
   generic production strategy-result hierarchy.
3. Integrate those expectations into deterministic evaluation and reporting.
   An expected `input_unavailable` or `not_applicable` outcome passes when its
   exact contract is observed; an unexpected one remains a classified failure.
4. Version and correct expectations for `MOM-02`, `GRA-ETF-01`, `GRN-05`,
   `FCF-02`, and `FCF-03`. Preserve all case IDs and independently verified
   numerical values.
5. Add `MOM-ETF-01`, `GRG-ETF-01`, and `FCF-ETF-01` using the existing reviewed
   profile/fixture boundaries. Do not add an ETF aggregate strategy.
6. Add one canonical deterministic minimum-suite catalog and request-building
   entry point that produces a single report for all fifteen cases. Do not add
   the public CLI in Slice H.
7. Add mutation/regression tests proving that wrong statuses, reasons,
   classifications, and ETF applicability outcomes are detected and that the
   expected historical-boundary outcomes pass.
8. Run focused checks, the canonical deterministic suite, and the complete
   repository quality-gate wrapper; then stop again at Gate M.

Slice H must not weaken tolerances, remove useful cases, convert deterministic
execution into a strategy-selection measurement, add live provider/model calls,
perform unrelated cleanup, or start Slices I–K.

## 6. Gate M re-entry criteria

Gate M may be reconsidered only when all of the following evidence is available:

- the complete repository wrapper passes Ruff, formatting, strict mypy, and
  pytest;
- one canonical deterministic report contains the exact reviewed fifteen-case
  catalog and stable suite/fixture versions;
- deterministic strategy selection remains honestly `not_measured`;
- every correct expected domain outcome passes, and mutation tests demonstrate
  that an incorrect outcome fails with the proper component classification;
- the four-case ETF scenario proves the complete P1 applicability matrix;
- aggregate and component denominators are explicit and honest; and
- no live provider or LLM call occurred.

The next decision is another human Gate M review. Gate M approval would authorize
the next selected slice; it would not by itself mark Step 2.5 complete.

## 7. Slice H re-entry evidence

Slice H was explicitly authorized after the documentation checkpoint was
accepted. The correction stayed within the approved boundary: no production
financial formulas, public CLI, real-local-Ollama path, live-provider behavior,
or dependency metadata changed.

| Re-entry criterion | Result | Evidence |
| :--- | :--- | :--- |
| Strict typing and complete repository gate | Pass | Repository wrapper: Ruff check pass; 216 files formatted; strict mypy pass across 176 source files; 1,207 pytest tests pass; 87% line coverage. |
| Canonical deterministic report | Pass | Suite `step-2.5-golden-minimum`, suite version `h1-v2`, fixture-set version `step-2.5-h1-v2`; 15 executed, 15 passed, 0 failed; overall pass rate 100%. |
| Honest strategy-selection measurement | Pass | All 15 strategy-selection observations are `not_measured`; measured/applicable denominator is 0 and pass rate is null. |
| Exact native domain outcomes | Pass | Execution-status component: 15/15; fixture-status component: 15/15. Correct expected `input_unavailable` and `not_applicable` results pass only when their exact typed status/reason/classification contracts match. |
| Mutation sensitivity | Pass | Four regressions mutate execution status, applicability reason, classification, and ETF execution status; each produces a case failure classified under `execution_status`. |
| ETF applicability matrix | Pass | `MOM-ETF-01`, `GRA-ETF-01`, `GRG-ETF-01`, and `FCF-ETF-01` exercise the four approved routes against the reviewed ETF profile boundary. |
| Honest component denominators | Pass | Numerical correctness: 10 measured passes and 5 not applicable; Graham method selection: 7 not applicable and 8 not measured; no unobserved component is counted as a pass. |
| Network/model isolation | Pass | Canonical execution used only injected deterministic fixtures and direct registered tool dispatch; no live provider or LLM call occurred. |

One additional canonical-execution defect was corrected inside the approved
harness scope: `GRN-04` previously depended on cache evidence created only by an
individual test. Slice H moved that deterministic evidence into an explicit
fixture-composition input so the canonical request builder can reproduce the
reviewed precedence outcome without mutable or production cache state.

The domain-path extractor also distinguishes an explicitly expected terminal
null from a missing nested field below a null parent; an integration regression
prevents those two outcomes from collapsing into the same observation.

The re-entry evidence closes the demonstrated Slice H defects, but it is not a
self-approval. Work remains stopped at Gate M pending human review.
