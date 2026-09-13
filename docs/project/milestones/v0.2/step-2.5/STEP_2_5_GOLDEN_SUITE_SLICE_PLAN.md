# Step 2.5 Golden Suite Slice Plan

Defines the evaluation components, fixture contracts and local review gates.

Work-package order and status: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## Sequence and status

| Order | Scope | Local gate |
| :--- | :--- | :--- |
| P0 → P1-A/B/C | Production fixture seams; instrument applicability | Accepted |
| A1 → A2 → B1/B2 | Typed contracts; independent expected values | Accepted |
| C → D → E1/E2 → F | Evaluation; aggregation; execution; self-tests | Accepted |
| G1–G4 → M → H | Minimum catalog; review-directed corrections | Accepted |
| I → J → K | Optional model mode; CLI/docs; final verification | Accepted; empirical-run absence recorded separately |

## 1. Purpose

This document turns Section 4.5.18 of the implementation plan into bounded implementation handoffs. It is subordinate to that plan and does not change Step 2.5 scope, ordering, acceptance criteria, or the mandatory review gate.

The slices are intentionally small enough to give one implementation agent one coherent contract at a time. Each implementation handoff should name exactly one slice, its owned artifacts, its required tests, and its stop condition. Later-slice requirements are context, not authorization to implement ahead.

## 2. Decisions fixed before Slice A

The following decisions are already reviewed and are not open design questions in later slices:

- Deterministic fixture providers live under `src/evaluation/fixtures/`; production or evaluation code must not import fixtures from `tests/`.
- The approved production tools are explicitly registered in `src/orchestrator/analysis_tools.py` as `analyze_momentum`, `analyze_graham_number`, `analyze_graham_growth_value`, and `analyze_fcf_earnings_growth`.
- Step 2.5 must reuse `AsyncToolDispatcher` and those production handlers rather than introduce an evaluation-only dispatcher or strategy framework.
- Production tool availability remains an explicit allowlist. Reflection-based analysis discovery and generic strategy/plugin registration are set aside until Step 4 at the earliest and only if concrete expansion pressure justifies them.
- Deterministic/no-LLM execution reports strategy/tool selection as `not_measured`. Direct or scripted invocation must not manufacture a passing selection result.
- Each strategy retains its native typed production result. Evaluation-specific result and report models may aggregate observations, but must not replace production results with a generic strategy result.
- Expected numerical values must be established independently of the production functions under test.
- The minimum heterogeneous suite must stop for human review when it works. Expansion beyond that reviewed minimum is human-directed, not automatic.
- No slice may add live network or LLM calls to deterministic tests, production persistence, SQLite, or new analytical strategies.
- Effective 2026-08-30, no further Step 2.5 Golden Suite implementation work will be assigned to Cline. Codex is the implementation owner; the prompts and runtime profile below are retained only as an audit record and must not be issued as active implementation instructions.
- A provider-confirmed ETF is applicable to Momentum but `not_applicable` to both Graham methods and the existing company-level FCF Growth strategy. Unknown instrument kind remains fail-open and must not be guessed.
- P1 owns only the pre-Golden contract/applicability correction. Durable instrument-profile caching and a distinct ETF aggregate FCF-growth strategy are P2 after Step 3.1 and are not authorized during Step 2.5.

## 5. Completed prerequisite — P0

### Objective

Remove repository-structure work from Cline's evaluation prompts and expose one production execution boundary for every approved strategy.

### Completed artifacts

- `src/evaluation/__init__.py`
- `src/evaluation/fixtures/__init__.py`
- `src/evaluation/fixtures/market_data.py`
- `src/evaluation/fixtures/graham.py`
- `src/evaluation/fixtures/fcf_earnings_growth.py`
- `src/orchestrator/analysis_tools.py`
- `src/analysis/graham_value/service.py`
- `docs/EVALUATIONS.md`
- focused production-handler and fixture tests

The former local `src/golden/` and `tests/golden/` directories have been removed.

## 5A. Approved prerequisite — P1 instrument applicability hardening

### Objective

Correct the concrete FLSW defect before Golden behavior is frozen: preserve provider-backed identity consistently, distinguish a known ETF from an invalid ticker or missing company facts, and return native `not_applicable` outcomes for methods that do not apply.

### Fixed invariants

- Instrument kind is provider-backed evidence. Never infer it from a ticker, instrument name, absence of SEC facts, or the success of another strategy.
- The composed profile preserves the existing one-provider identity separately from optional normalized/raw kind evidence; each retains its own provider and timezone-aware resolution time.
- Missing or failed kind resolution remains unknown and fail-open. Only affirmative ETF evidence changes applicability.
- Momentum remains ETF-applicable. Both Graham methods and the existing company-level FCF Growth strategy return `not_applicable` for a known ETF.
- `not_applicable` is a completed domain outcome with successful direct-CLI process status. It is not input unavailability, provider error, ticker invalidity, or implicit selection of another tool.
- Identity/profile candidates are ordered and explicitly injected. Each candidate is consulted at most once per run; deterministic execution has no live fallback.
- Graham/FCF formulas, provider fact mappings, and native result types remain strategy-specific and unchanged except for the minimum typed applicability/status accommodation.
- The future ETF aggregate method is a separate strategy/tool and must never be hidden inside or silently substituted for company-level FCF Growth.

### P1-A — provider evidence and contract checkpoint

Inspect authoritative provider documentation and representative payload shapes for instrument classification, especially Yahoo's ETF/equity discriminator and retained raw value. Propose the minimum normalized vocabulary, exact mappings, unknown/unsupported behavior, and identity/profile schema-version consequences in [`STEP_2_5_P1_INSTRUMENT_APPLICABILITY_MAPPING_RECORD.md`](STEP_2_5_P1_INSTRUMENT_APPLICABILITY_MAPPING_RECORD.md). Update the relevant historical mapping/design cross-references and architecture text, then stop for human approval before production code changes.

### P1-B — identity/profile contract and request-scoped composition

Preserve the existing immutable security-identity boundary, implement the reviewed separate kind-evidence/profile contracts, and add a narrow ordered candidate resolver. Reuse retained strategy-provider identity first, use the injected Yahoo capability for kind evidence, and consult Yahoo for identity only when no higher-precedence identity is available. Preserve field-level provenance and fail-open diagnostics. Add deterministic tests for mappings, unknown values, provider failure, fallback order, no duplicate network metadata fetch, immutability, and serialization.

### P1-C — strategy applicability, presentation, and full gate

Apply the reviewed strategy-specific policy through the shared production service/tool boundaries used by direct CLI and orchestration. Ensure known ETFs produce native `not_applicable` outcomes for both Graham methods and company-level FCF Growth, retain identity-aware headings in every presentation mode, remove generic ticker-verification advice from unavailability/provider failures, and align successful `not_applicable` process status. Add deterministic CLI, presenter, service/analyzer, and production-handler regression tests; prove Momentum is unchanged. Run the complete repository quality gate and stop for explicit P1 approval before A1.

### P1 exclusions and P2 handoff

P1 does not add SQLite, durable/cross-process caches, TTL/invalidation policy, ETF holdings data, constituent aggregation, currency/weighting policy, or a new analytical strategy.   Durable profiles and ETF aggregation are outside this contract.

## 6. Slices A1–A2 — typed evaluation contract

  After that gate, the split preserves the governing implementation-plan sequence: A1 establishes only typed leaf vocabulary and constraint invariants; A2 composes those reviewed leaves into cases, observations, and component results. Neither slice authorizes evaluator behavior.

### 6.1 Slice A1 — enums and leaf constraints

#### Objective

Create one importable, strictly typed foundation containing only the stable discriminators and immutable expectation constraints that later case models require.

#### Owned artifacts

- create `src/evaluation/models.py`;
- create `tests/evaluation/test_models.py`;
- do not modify `src/evaluation/__init__.py` yet.

#### Required contract

- String enums for execution mode, the four approved production tool names, the two Graham methods, component kind, and component outcome.
- Frozen `ToolConstraints` and `GrahamMethodConstraints` with canonical, duplicate-free permitted/required/forbidden collections. Required values are permitted; forbidden values are disjoint from permitted and required values.
- Frozen `BehaviorConstraints` with the same set relationships for nonblank behavior identifiers.
- Frozen `NumericalExpectation` containing one nonblank field path, one finite expected value, and at least one finite non-negative absolute or relative tolerance. Zero is an intentional exact-match tolerance.
- Deeply immutable built-in tuples, deterministic serialization order for semantically unordered collections, Python 3.12 typing, and fail-closed rejection rather than silent duplicate removal.

#### Exclusions

Do not add `Case`, aggregate `Expectation`, observation models, `ComponentResult`, public package exports, evaluator functions, fixtures, runners, reports, or later-slice placeholders.

#### Acceptance and stop condition

The module imports successfully. Focused tests prove enum values, valid construction, frozen behavior, canonical order, deterministic JSON round trips, and rejection of duplicates, overlaps, blank identifiers, missing/negative/non-finite tolerances, and non-finite expected values. All four focused gates pass.

### 6.2 Slice A2 — composed case, observation, and result contract

#### Objective

Compose the reviewed A1 leaves into the immutable Golden Case, raw observation, and component-result vocabulary without implementing evaluation logic.

#### Owned artifacts

- extend `src/evaluation/models.py`;
- extend `tests/evaluation/test_models.py`;
- update `src/evaluation/__init__.py` only for deliberate public exports.

#### Required contract

- Frozen `Expectation` and `Case` models with stable nonblank case and fixture identifiers, description, prompt/task text, canonical tags, constraint leaves, and field-addressed numerical expectations with unique paths.
- Frozen raw evidence models for ordered tool calls, ordered Graham-method observations, and finite numerical observations. Ordered tool/method evidence preserves order and repetition; it is never sorted, deduplicated, or pre-evaluated.
- A frozen `Observation` whose execution mode is separate from the mode-neutral case definition, whose timestamp is timezone-aware, and whose numerical field paths are unique. Deterministic/no-LLM observations reject tool-selection and Graham-method-selection evidence so direct dispatch cannot masquerade as measured LLM selection.
- A frozen `ComponentResult` as the only layer containing `pass`, `fail`, `not_applicable`, or `not_measured`. `fail` requires a nonblank failure reason; other outcomes forbid one; `not_applicable` and `not_measured` require nonblank explanatory evidence.
- Explicit separation between expected definitions, raw observed evidence, and evaluated component results; deterministic JSON round trips; finite-number rejection throughout.

#### Exclusions

Do not add a case catalog, fixture composition, comparison/evaluator functions, runner, report writer, CLI, telemetry integration, production changes, or Slice B work.

#### Acceptance and stop condition

Focused tests prove the complete approved validation matrix, deep immutability, deterministic serialization, preservation of ordered/repeated evidence, and deterministic-mode `not_measured` integrity. All four focused gates pass.

## 7. Slice B — independently verified expectation dossier

 Production calculators must not be invoked to generate the expected values.

### Slice B1 — Momentum and Graham expectations

#### Owned artifacts

- create `docs/project/milestones/v0.2/step-2.5/STEP_2_5_EXPECTED_VALUES.md`;
- add only narrowly required deterministic fixture data under `src/evaluation/fixtures/`;
- add fixture-focused tests under `tests/evaluation/fixtures/`.

#### Required work

Document the proposed minimum Momentum and Graham cases, exact fixture inputs, transparent reference calculations, expected statuses/values, tolerances, and why each case is useful. Cover both Graham methods, default and TTM EPS bases, `not_applicable`, missing current price, and relevant `as_of` or precedence behavior.

### Slice B2 — FCF/Earnings Growth expectations

#### Owned artifacts

- extend `STEP_2_5_EXPECTED_VALUES.md`;
- add only narrowly required annual facts under `src/evaluation/fixtures/`;
- extend fixture-focused tests under `tests/evaluation/fixtures/`.

#### Required work

Document the straightforward, insufficient or mathematically nonmeaningful, period-alignment, and historical-`as_of` scenarios. Show the independent FCF, EPS, elapsed-year, CAGR, classification, and tolerance reasoning.

### Exclusions

Do not create executable Golden cases, call production calculators to populate expectations, implement evaluators, or broaden production fixture/provider behavior.

### Acceptance and stop condition

Every proposed minimum case has reviewable input evidence and independently derived expected values.

## 8. Slice C — component evaluators

### Objective

Evaluate observed evidence without executing strategies or aggregating a suite.

### Owned artifacts

- create `src/evaluation/evaluator.py`;
- create `tests/evaluation/test_evaluator.py`;
- modify `src/evaluation/models.py` only when a reviewed Slice A contract proves insufficient.

### Required behavior

- Evaluate expected versus observed tool selection.
- Evaluate Graham method selection independently from broad strategy selection.
- Compare typed numerical observations using each expectation's tolerances.
- Classify fixture/data failures separately from numerical and selection failures.
- Return `not_measured` for selection in deterministic/no-LLM mode and exclude it from measured selection denominators.
- Accept legitimate permitted alternatives and reject explicitly forbidden behavior.

### Exclusions

Do not load fixtures, dispatch tools, aggregate multiple cases, serialize suite reports, or add real-model execution.

### Acceptance and stop condition

Focused tests cover pass, fail, not-applicable, and not-measured behavior plus boundary tolerances and failure classification. Stop after focused verification.

## 9. Slice D — case aggregation and machine-readable report contract

### Objective

Aggregate already-evaluated cases and serialize an auditable report without running them.

### Owned artifacts

- create `src/evaluation/reporting.py`;
- create `tests/evaluation/test_reporting.py`;
- modify evaluation models only as narrowly required by the report contract.

### Required behavior

- Case totals and aggregate pass rate use the denominator defined in the implementation plan.
- Component denominators count only measured and applicable observations.
- Strategy selection, Graham method selection, numerical correctness, fixture/data failure, and overall results remain distinct.
- Reports contain suite/fixture versions, mode, execution timestamp, applicable model configuration, case results, failure reasons, and optional trajectory identity.
- Machine-readable serialization rejects NaN and Infinity and is deterministic apart from explicitly supplied execution metadata.

### Exclusions

Do not execute cases, select fixtures, invoke telemetry, or implement a CLI.

### Acceptance and stop condition

Focused tests prove denominator semantics, mixed component states, JSON round trips, and non-finite rejection. Stop after focused verification.

## 10. Slice E — deterministic execution harness

### Slice E1 — fixture composition and production dispatch

#### Objective

Build fixture-backed dependencies for the four existing production handlers and execute one supplied case through `AsyncToolDispatcher` without an LLM.

#### Owned artifacts

- create `src/evaluation/composition.py`;
- create `tests/evaluation/test_composition.py`.

#### Required behavior

Use only `src/evaluation/fixtures/`, `AnalysisToolDependencies`, `register_analysis_tools(...)`, and explicit injected clocks/provider selections. Missing fixture IDs or facts fail closed. No fixture composition may fall back to a live provider.

### Slice E2 — deterministic runner and telemetry evidence

#### Objective

Connect case loading, E1 composition, production dispatch, component evaluation, aggregation/reporting, and Step 2.1 trajectory observation.

#### Owned artifacts

- create `src/evaluation/runner.py`;
- create `tests/evaluation/test_runner.py`.

#### Required behavior

The deterministic runner executes supplied cases without an LLM, records tool and calculation evidence, reports strategy selection as `not_measured`, and produces the machine-readable in-memory report contract. Telemetry remains observational and fail-open.

### Exclusions

Do not add the minimum production case catalog yet, invoke Ollama, write a CLI, persist reports to SQLite, or manufacture LLM-selection evidence.

### Acceptance and stop condition

A small synthetic test case proves the end-to-end deterministic pipeline through the production dispatcher. Run the focused evaluation suite and stop for integration review.

## 11. Slice F — evaluator mutation/self-test

### Objective

Prove the evaluator detects a deliberately incorrect observed result without adding that mutation to the benchmark denominator.

### Owned artifacts

- create or extend `tests/evaluation/test_evaluator_self_test.py`;
- change evaluator code only if the test exposes a genuine defect.

### Acceptance and stop condition

The correct observation passes, a controlled numerical or selection mutation fails for the expected category, and the synthetic mutation is not counted as a normal Golden case. Stop after focused verification.

## 12. Slice G — minimum heterogeneous catalog

Executable case definitions belong in `src/evaluation/cases/`; keep one stable case ID per reviewed scenario. Each subslice may add only its named cases, directly required fixture records, and focused tests.

### Slice G1 — Momentum cases

- straightforward Momentum result;
- insufficient-history or point-in-time boundary behavior.

### Slice G2 — Graham Number cases

- default three-year-average EPS;
- explicit TTM EPS;
- `not_applicable`;
- missing current price where comparison is unavailable but valuation remains explicit.

### Slice G3 — Graham growth and resolution cases

- explicit growth-value assumptions and AAA yield;
- Graham method-selection discrimination;
- override/cache/provider precedence and historical `as_of` behavior.

### Slice G4 — FCF/Earnings Growth and cross-strategy discrimination

- straightforward historical growth;
- insufficient or mathematically nonmeaningful growth;
- period alignment and historical `as_of` rejection;
- one known-ETF applicability case proving Momentum remains applicable while both Graham methods and company-level FCF Growth are `not_applicable`, with no invalid-ticker claim or automatic aggregate-strategy substitution;
- at least one existing case explicitly identified as discriminating the requested strategy from a plausible wrong strategy.

### Shared acceptance

- Case data matches the reviewed Slice B expectation dossier.
- Stable IDs, fixture IDs, prompts, tool constraints, numerical expectations, and tolerances are explicit.
- Deterministic execution never touches live providers or an LLM.
- Each subslice passes focused tests and does not broaden another strategy's cases.

## 13. Gate M — mandatory minimum-suite review

Minimum-catalog verification:

1. run the full deterministic minimum suite;
2. run the complete repository quality gate;
3. record the exact case list and deterministic results;
4. stop and request human review.

Catalog expansion must be justified by demonstrated coverage gaps.

## 14. Slice H — review-directed case changes or expansion

Slice H is mandatory because Gate M identified demonstrated evaluator and
coverage defects. It is limited to the following approved actions:

1. correct the 76 strict-mypy failures without changing production financial
   behavior;
2. represent and evaluate exact expected native domain outcomes, including
   status, metric availability, reason, and classification where material;
3. correct/version the expectations for `MOM-02`, `GRA-ETF-01`, `GRN-05`,
   `FCF-02`, and `FCF-03` while preserving IDs and verified numerical values;
4. add `MOM-ETF-01`, `GRG-ETF-01`, and `FCF-ETF-01` so the existing
   `GRA-ETF-01` scenario proves the complete four-strategy P1 applicability
   matrix; these bring the suite to fifteen cases, within the approved range;
5. add one canonical deterministic catalog/request-builder entry point that
   produces a single versioned report without adding the public CLI; and
6. add mutation/regression evidence, run focused checks, the canonical suite,
   and the complete repository wrapper, then stop again at Gate M.

Every added case must state the distinct failure mode or signal it contributes. Do not add cases mechanically to reach a number, remove a useful failure, or alter expectations to improve measured performance.

## 15. Slice I — optional real-local-Ollama mode

### Objective

Measure empirical strategy, method, tool, and argument selection through the real orchestration boundary while keeping deterministic execution independent.

### Owned artifacts

- create `src/evaluation/ollama_runner.py` or another single reviewed mode-specific module;
- create deterministic tests with mocked local-model responses;
- add empirical execution tests only as explicitly invoked, non-CI tests.

### Required behavior

Record model identifier, configuration, sampling settings where applicable, repetition policy, trajectories, and nondeterministic outcomes. Do not inspect private reasoning or make a real model call during normal pytest.

## 16. Slice J — CLI and documentation completion

### Objective

Expose the reviewed runner through the normal `uv run` workflow and complete operator documentation.

### Owned artifacts

- a narrowly reviewed command integration under the existing CLI boundary;
- CLI-focused tests;
- `docs/EVALUATIONS.md`;
- directly affected documentation links.

### Required behavior

Support the full suite, one named case, deterministic/no-LLM mode, optional real-local-Ollama mode, and an explicit report location. Required benchmark failure returns a non-zero status. Documentation must explain report fields, failure interpretation, fixture maintenance, and the separation of deterministic and empirical results.

## 17. Slice K — Step 2.5 closeout

### Required work

- Run Ruff, formatting checks, `mypy --strict`, and the complete pytest suite through the repository quality-gate wrapper.
- Run and record the deterministic suite result.
- Record empirical local-model results separately when they are available; absence of an optional empirical run must remain explicit.
- Reconcile all Step 2.5 acceptance criteria and documentation status.
- Stop for final human approval before representing Step 2.5 as complete.
