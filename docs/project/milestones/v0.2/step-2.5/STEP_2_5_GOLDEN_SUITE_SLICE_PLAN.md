# Step 2.5 Golden Suite Slice Plan

**Status:** Complete and approved on 2026-08-31. The approved working tree is based on checkpoint `86f1bd6350b9a8bb2cc051a62a4d0f8ba0a5750f`; the closeout checkpoint has not yet been created.<br/>
**Governing plan:** [Milestone v0.2 Implementation Plan](../IMPLEMENTATION_PLAN.md#4518-implementation-sequence)<br/>
**Evaluation contract:** [Evaluations & Golden Suite](../../../../EVALUATIONS.md)<br/>
**Architecture:** [Financial Data Agents Architecture](../../../ARCHITECTURE.md#7-golden-suite-architecture-step-25)

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

## 3. Retired Cline handoff protocol

This protocol records the boundaries used during the terminated Cline experiment. It is historical evidence, not an active workflow. The same scope, verification, and stop boundaries remain useful for Codex implementation reviews, but no Step 2.5 slice is to be handed to Cline.

Each attempted Cline implementation prompt was intended to enforce these boundaries:

1. Read this slice plan, the linked governing sections, `docs/EVALUATIONS.md`, and only the production contracts named by the slice before editing.
2. Establish the focused baseline relevant to the owned artifacts.
3. Modify only the slice-owned artifacts and directly necessary package exports. If another production change appears necessary, stop and report the concrete incompatibility.
4. Do not edit `pyproject.toml`, `uv.lock`, provider mappings, financial formulas, production strategy semantics, or unrelated documentation.
5. Add focused deterministic tests in the same slice. Tests must not use live APIs, wall-clock time, mutable production caches, or real LLM endpoints.
6. Run focused Ruff, formatting, strict mypy, and pytest checks appropriate to the slice.
7. Report changed files, checks run, and unresolved questions, then stop. Do not start the next slice or create a commit unless the human explicitly requests it.

The complete repository quality gate is required at the review checkpoints identified below and at final closeout. A focused slice may use narrower checks while it is still under review.

## 4. Sequence crosswalk

| Implementation-plan sequence | Formal slice |
| :--- | :--- |
| 1. P1 production correction and approval | P1-A–P1-C — evidence, contract/composition, then applicability/presentation |
| 2. Accept stable contracts | P0 plus approved P1 |
| 3. Typed Golden Case model | A1–A2 — leaf constraints, then composed evaluation contract |
| 4. Independent expectations and tolerances | B1–B2 — expectation dossier |
| 5–6. Selection and numerical evaluation | C — component evaluators |
| 7–8. Aggregation and reporting | D — aggregation and report contract |
| 9. Deterministic/no-LLM harness | E1–E2 — composition and execution harness |
| 10. Evaluator self-test | F — mutation/self-test |
| 11. Minimum heterogeneous cases | G1–G4 — minimum catalog |
| 12. Run minimum suite and stop | Gate M — mandatory human review |
| 13. Expansion | H — review-directed only |
| 14. Optional real-local-Ollama | I — empirical execution mode |
| 15–16. CLI and documentation | J — operator interface and guide completion |
| 17–18. Gates and measured records | K — closeout |

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

The former local `src/golden/` and `tests/golden/` directories have been removed. P0 passed the complete repository quality gate and must not be reopened unless a later slice demonstrates a specific defect.

## 5A. Approved prerequisite — P1 instrument applicability hardening

### Objective

Correct the concrete FLSW defect before Golden behavior is frozen: preserve provider-backed identity consistently, distinguish a known ETF from an invalid ticker or missing company facts, and return native `not_applicable` outcomes for methods that do not apply. P1 must leave a stable injection seam that P2 can implement durably after Step 3.1 without changing strategy calculators or Golden case definitions.

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

After P1-A approval, preserve the existing immutable security-identity boundary, implement the reviewed separate kind-evidence/profile contracts, and add a narrow ordered candidate resolver. Reuse retained strategy-provider identity first, use the injected Yahoo capability for kind evidence, and consult Yahoo for identity only when no higher-precedence identity is available. Preserve field-level provenance and fail-open diagnostics. Add deterministic tests for mappings, unknown values, provider failure, fallback order, no duplicate network metadata fetch, immutability, and serialization. Stop for focused contract review.

### P1-C — strategy applicability, presentation, and full gate

After P1-B approval, apply the reviewed strategy-specific policy through the shared production service/tool boundaries used by direct CLI and orchestration. Ensure known ETFs produce native `not_applicable` outcomes for both Graham methods and company-level FCF Growth, retain identity-aware headings in every presentation mode, remove generic ticker-verification advice from unavailability/provider failures, and align successful `not_applicable` process status. Add deterministic CLI, presenter, service/analyzer, and production-handler regression tests; prove Momentum is unchanged. Run the complete repository quality gate and stop for explicit P1 approval before A1.

### P1 exclusions and P2 handoff

P1 does not add SQLite, durable/cross-process caches, TTL/invalidation policy, ETF holdings data, constituent aggregation, currency/weighting policy, or a new analytical strategy. P2 — Durable Instrument Profiles & ETF Aggregate FCF Growth — is planned only after Step 3.1. P2 will persist time-aware profiles behind the P1 seam and, after its own provider/product-policy checkpoint, add a distinct look-through ETF strategy with native configuration, results, coverage diagnostics, fixtures, and tool identity. Its exact placement relative to Steps 3.2–3.4 must be reviewed after Step 3.1; no P2 implementation is authorized by this Step 2.5 plan.

## 6. Slices A1–A2 — typed evaluation contract

The original monolithic Slice A was retired after two failed Cline completion attempts. A1 remains blocked until P1-C receives explicit approval. After that gate, the split preserves the governing implementation-plan sequence: A1 establishes only typed leaf vocabulary and constraint invariants; A2 composes those reviewed leaves into cases, observations, and component results. Neither slice authorizes evaluator behavior.

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

The module imports successfully. Focused tests prove enum values, valid construction, frozen behavior, canonical order, deterministic JSON round trips, and rejection of duplicates, overlaps, blank identifiers, missing/negative/non-finite tolerances, and non-finite expected values. All four focused gates pass. Stop for independent A1 review before A2.

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

Focused tests prove the complete approved validation matrix, deep immutability, deterministic serialization, preservation of ordered/repeated evidence, and deterministic-mode `not_measured` integrity. All four focused gates pass. Stop for contract review before Slice B.

## 7. Slice B — independently verified expectation dossier

Slice B defines the benchmark truth before production evaluation code consumes it. Production calculators must not be invoked to generate the expected values.

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

Every proposed minimum case has reviewable input evidence and independently derived expected values. Stop for human expectation review before Slice C.

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

After G1–G4:

1. run the full deterministic minimum suite;
2. run the complete repository quality gate;
3. record the exact case list and deterministic results;
4. stop and request human review.

No case expansion, real-local-Ollama execution, CLI work, or Step 2.5 completion claim is authorized before this gate is approved.

### 2026-08-31 decision

Gate M is **not approved**. The complete findings and verification evidence are
recorded in the [Step 2.5 Gate M Review](STEP_2_5_GATE_M_REVIEW.md). The blocking
conditions are:

- the repository gate fails with 76 strict-mypy errors in four evaluation test
  files, although focused evaluation tests and the complete pytest suite pass;
- the aggregate runner treats correct expected historical `input_unavailable`
  outcomes as failures and does not enforce several expected statuses, reasons,
  availability states, or classifications;
- there is no canonical operation that executes all reviewed minimum cases as
  one versioned deterministic report; and
- the Golden catalog proves only the Graham Number branch of the required
  cross-strategy ETF applicability scenario.

Slices I–K remain blocked. The next implementation work is only the approved
Slice H correction below, after the documentation-only checkpoint is reviewed.

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

## 18. Current handoff

The corrected Gate M result and Slices I–K received explicit human review and
acceptance. Step 2.5 is complete and approved. Checkpoint
`86f1bd6350b9a8bb2cc051a62a4d0f8ba0a5750f` is the tracked pre-Slice-I baseline;
the approved closeout change set remains in the working tree. The next handoff
is Step 2.5A D0 evidence freeze under
[`SEC_EDGAR_FPI_IFRS_SLICE_PLAN.md`](../step-2.5a/SEC_EDGAR_FPI_IFRS_SLICE_PLAN.md). Stop at
its Gate A before A1 production changes. P2 remains deferred until after Step
3.1.

## 19. Retired Cline and Ollama execution profile

### 19.1 Scope and separation from benchmark configuration

This profile was used for **Cline implementing Step 2.5** and is retained to make the failed experiment reproducible. It is no longer an active recommendation. It is not the configuration of the optional real-local-Ollama Golden evaluation in Slice I. Implementation-model behavior, prompts, and outcomes must never be mixed into Golden benchmark measurements.

The recommendation was researched on 2026-08-30. Reassess it for a later milestone because local-model and Ollama support changes quickly. Do not silently change model, quantization, context, or sampling settings between Step 2.5 slices; record any change in Section 22.

### 19.2 Historical implementation-model recommendation

The experiment selected **`qwen3-coder:30b`** through Ollama for both Cline Plan and Act modes. The installed tag was verified on 2026-08-30 to resolve to the intended 30.5B-total/3.3B-active `Q4_K_M` model with completion and tool capabilities; no additional model pull was required for this host.

Rationale:

- Cline's local-model guidance identifies Qwen3-Coder 30B as its primary local recommendation and describes it as the most reliable model below 70B for Cline tool use and repository work.
- The Qwen model card identifies the 30.5B-total/3.3B-active model as Cline-compatible, non-thinking, tool-call capable, and natively 256K-context.
- Ollama's current artifact is 19 GB, advertises tool support, and received an Ollama-engine update for more reliable tool calling.
- The repository's existing Ollama deployment artifact was designed to fully offload a larger dense `qwen2.5-coder:32b-instruct-q5_K_M` model across two GPUs. The 19 GB Qwen3-Coder quantization is therefore the strongest current Cline-recommended model with a defensible compatibility margin for a useful context cache. Exact live GPU capacity is not available from this workspace, so the preflight below remains mandatory.
- The model is a better fit for this step than a general reasoning model because the work is typed Python, multi-file codebase navigation, tool use, tests, and strict instruction following.

Do not select `qwen3-coder-next:q4_K_M` for the initial run. It is attractive for agentic coding, but its 52 GB weights precede context-cache allocation and exceed the capacity demonstrated by the repository's current deployment artifact. Do not select the 290 GB Qwen3-Coder 480B local artifact. `devstral-small-2:24b-instruct-2512-q4_K_M` is the fallback only if Qwen3-Coder cannot remain fully GPU-offloaded or proves unable to use Cline's tools reliably; do not alternate models casually between slices.

Final review decision on 2026-08-30: Qwen3-Coder remained fully GPU-offloaded but produced three completion claims that materially contradicted the files and check results on disk, including a fresh reduced A1 task. Although the original profile named `devstral-small-2:24b-instruct-2512-q4_K_M` as a possible fallback, the human elected not to spend further Step 2.5 time testing Cline implementation models. There is no active Cline fallback for the Golden Suite. Reconsidering Cline for a later milestone would require a separate explicit decision and would not reopen this Step 2.5 record.

Primary sources:

- [Cline local-model guidance](https://docs.cline.bot/running-models-locally/overview)
- [Qwen3-Coder 30B model card](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct)
- [Ollama Qwen3-Coder tags](https://ollama.com/library/qwen3-coder/tags)
- [Ollama coding-model/tool-calling update](https://ollama.com/blog/coding-models)
- [Ollama Qwen3-Coder-Next size and capabilities](https://ollama.com/library/qwen3-coder-next)
- [Ollama Devstral Small 2 fallback](https://ollama.com/library/devstral-small-2)

### 19.3 Historical Ollama model alias

The canonical artifact is [`docs/project/deploy/ollama/Modelfile.cline-step-2.5`](../../../deploy/ollama/Modelfile.cline-step-2.5). Create the dedicated `financial-data-agents-step-2-5` alias from this content on the inference server:

```text
FROM qwen3-coder:30b

PARAMETER num_ctx 65536
PARAMETER temperature 0.7
PARAMETER top_p 0.8
PARAMETER top_k 20
PARAMETER repeat_penalty 1.05
```

The sampling values follow Qwen's model-card recommendations. Do not add a Modelfile `SYSTEM` instruction: Cline and repository rules already supply the task/system context, and an extra generic persona can compete with them. Start with Ollama's automatic GPU placement and verify it with `ollama ps`. If that reports CPU-only execution, treat the preflight as failed and inspect GPU discovery and runner-allocation logs before testing an explicit `num_gpu` override; an override cannot repair a CUDA runner that did not discover the GPUs.

Use these Ollama server settings for a dedicated Step 2.5 implementation session:

```text
OLLAMA_CONTEXT_LENGTH=65536
OLLAMA_FLASH_ATTENTION=1
OLLAMA_KV_CACHE_TYPE=q8_0
OLLAMA_NUM_PARALLEL=1
OLLAMA_MAX_LOADED_MODELS=1
```

If the server is dedicated to local-only project work, also use `OLLAMA_NO_CLOUD=1`. Flash Attention reduces memory growth at longer context. The `q8_0` K/V cache uses about half the memory of the default `f16` cache with very small expected quality loss. Serial execution prevents parallel requests from multiplying context memory.

The 65,536-token context is intentional: current Ollama guidance recommends at least 64K for coding agents, while Cline requires at least 32K. It provides more margin than the repository's obsolete 8,192-token deployment setting without assuming enough memory for the model's full 256K context. If preflight shows CPU offload or instability, reduce **both** Ollama and Cline to 49,152 and then 32,768 before changing models. Never configure Cline to advertise more context than Ollama actually allocated.

Relevant runtime references:

- [Ollama context-length guidance](https://docs.ollama.com/context-length)
- [Ollama Flash Attention and K/V cache settings](https://docs.ollama.com/faq#how-can-i-enable-flash-attention)
- [Ollama Cline integration](https://docs.ollama.com/integrations/cline)

### 19.4 Historical mandatory Ollama preflight

Before giving Cline Slice A1 or A2:

1. Record `ollama --version`; use a current stable Ollama release.
2. Confirm `qwen3-coder:30b` still reports `Q4_K_M`, then create the dedicated alias from `docs/project/deploy/ollama/Modelfile.cline-step-2.5` without replacing the repository's application model aliases.
3. Run one tool-capable smoke task through Cline using the compact prompt.
4. During the request, run `ollama ps` and record model digest, processor split, and allocated context.
5. Accept the configuration only if the context is 65,536 and the model remains `100% GPU`. If it does not, follow the context-reduction order above.
6. Confirm that a small Cline task can read one file, run a harmless read-only command, and complete one tool round trip without malformed tool syntax.
7. Record the result in Section 22. Do not begin A1 or A2 on a failed preflight.

### 19.5 Historical Cline settings

| Setting | Recommendation |
| :--- | :--- |
| API provider | Ollama |
| Base URL | The existing local inference-server URL, without an OpenAI `/v1` suffix |
| Model | `financial-data-agents-step-2-5` dedicated alias |
| Context window | `65536`, exactly matching Ollama |
| Auto Compact | Enabled; `Agentic` strategy. Qwen uses Cline's fallback context management rather than model-generated summarization. |
| Compact system prompt | Not exposed in Cline `v4.1.16 (Next)` and not a preflight requirement; the former SDK setting was non-functional and removed. |
| Plan/Act models | Same recommended model for both |
| Workflow | Fresh Cline task per slice; Plan first, then Act after plan review |
| Deep planning | Do not invoke `/deep-planning`; the reviewed slice plan already supplies bounded planning. No separate toggle is exposed in this Cline version. |
| Checkpoints | Enabled |
| Default terminal profile | Git Bash |
| Auto-approve: read project files | Enabled |
| Auto-approve: edit project files | Enabled only in Act mode for the active reviewed slice |
| Auto-approve: safe commands | Enabled |
| Auto-approve: fetch web content | Disabled |
| Auto-approve: MCP servers | Disabled |
| Web Search | Disabled |
| Hooks | Disabled |
| Background Edit | Disabled |
| MCP display mode | `Plain Text`; no MCP server is required for the planned slices |
| Error and usage reporting | Optional; disable it if the implementation session must be network-silent beyond the configured Ollama host |

Cline's current SDK-based extension no longer exposes the former compact-system-prompt setting because it did not affect the generated prompt; current local-model documentation that still requests that toggle is stale for `v4.1.16 (Next)`. Fresh tasks are therefore the primary prompt-size control and prevent context accumulated in one slice from contaminating the next. Auto Compact remains a context-pressure safeguard, not a substitute for fresh tasks. Checkpoints use a shadow repository and do not replace human review or authorize commits. The repository's `.clinerules` already points Cline to `AGENTS.md`; do not add a second competing general rules file.

Use Cline's [local-model settings](https://docs.cline.bot/running-models-locally/overview), [Plan/Act workflow](https://docs.cline.bot/core-workflows/plan-and-act), [checkpoints](https://docs.cline.bot/core-workflows/checkpoints), and [bounded auto-approve controls](https://docs.cline.bot/features/auto-approve) as the operational reference.

### 19.6 Cline task lifecycle

Retired on 2026-08-30. The lifecycle below describes the attempted workflow and must not be used to start another Golden Suite implementation task.

For every slice:

1. Start a fresh Cline task in Plan mode with the corresponding prompt draft from Section 21.
2. Require Cline to inspect the named artifacts and restate its intended files and tests before Act mode.
3. Reject a plan that adds future-slice work, dependencies, a generic strategy framework, or production semantic changes.
4. Switch that same task to Act mode only after the plan matches the slice.
5. Let Cline complete focused verification, then stop it at the prompt's stop condition.
6. Review the actual diff and rerun checks independently.
7. Add a concise review entry to Section 22 and revise later prompt drafts when a recurring failure mode is discovered.
8. Start the next approved slice in a fresh task. Do not ask one long-running Cline conversation to implement all of Step 2.5.

## 20. Prompt-draft conventions

The drafts below are retained as historical design artifacts and bounded-scope references for review. They are not paste-ready tasks and must not be issued to Cline. Their repeated scope and stop conditions may inform Codex implementation review, but the stale worktree and baseline statements are not operational instructions.

Unless a prompt says otherwise, each task must:

- work on branch `feat/step-2.5-golden-suite` in the existing working tree;
- obey `AGENTS.md`, the active implementation plan, this slice plan, and `docs/EVALUATIONS.md` in that precedence order after the human request;
- preserve reviewed prerequisite work already present in the working tree;
- use `apply_patch` or Cline's normal file-edit tool rather than shell write tricks;
- add Google-style docstrings and strict types consistent with the repository;
- make no dependency or lockfile changes, no live API/LLM calls in tests, no Git commits, and no work from later slices;
- run focused non-mutating checks with `uv run --no-sync` and the repository-local managed paths described by `AGENTS.md`; and
- stop after reporting changed files, verification, and any concrete blocker.

## 21. Retired Cline prompt drafts

Do not issue these prompts. They preserve the intended slice boundaries and the exact instructions used or prepared during the terminated Cline experiment.

### 21.1 Slice A1 — enums and leaf constraints

```text
Implement only Step 2.5 Slice A1 — enums and leaf constraints — on branch feat/step-2.5-golden-suite.

The reviewed Git checkpoint is commit ff4140336381e98cff835e9ea05fa61620aca1f9. The worktree intentionally contains exactly one pre-existing human-owned modification: ` M docs/project/milestones/v0.2/step-2.5/STEP_2_5_GOLDEN_SUITE_SLICE_PLAN.md`. Before any write, run git rev-parse HEAD and git status --short from the repository root. Stop if the SHA differs or status contains anything other than that one line. Preserve the human-owned plan modification byte-for-byte: do not edit, revert, stage, format, or otherwise take ownership of it. Use repository-relative paths in every file tool; never pass C:\Source\... or another absolute Windows path to a write/edit tool.

Read AGENTS.md, Section 4.5 of docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md, Sections 2–6.1 and 19–21 of docs/project/milestones/v0.2/step-2.5/STEP_2_5_GOLDEN_SUITE_SLICE_PLAN.md, docs/EVALUATIONS.md, and the existing src/evaluation/__init__.py. Inspect src/orchestrator/analysis_tools.py only to confirm the four approved tool names. Do not modify either inspected production/package file.

In Plan mode, enumerate the exact enums, leaf models, validators, tests, and two files you will create. Confirm that Case, aggregate Expectation, observations, ComponentResult, and package exports are excluded. Wait for approval before Act mode.

In Act mode, create only src/evaluation/models.py and tests/evaluation/test_models.py. Implement the A1 string enums plus frozen ToolConstraints, GrahamMethodConstraints, BehaviorConstraints, and NumericalExpectation exactly as Section 6.1 specifies. Use Python 3.12 built-in tuple and T | None syntax, module-scope imports, Google-style docstrings, finite-number checks that satisfy Ruff, deterministic canonical ordering for unordered constraints, and explicit duplicate rejection. Do not silently deduplicate input.

Do not add composed cases, aggregate expectations, observation models, ComponentResult, evaluator functions, fixtures, reports, runners, CLI code, public __init__.py exports, production changes, dependencies, or placeholders for later work.

After editing, reread both complete repository-relative files from disk and confirm that src/evaluation/models.py begins with its module docstring/imports and that every test imports existing definitions. Then run exactly:

uv run --no-sync ruff check src/evaluation/models.py tests/evaluation/test_models.py
uv run --no-sync ruff format --check src/evaluation/models.py tests/evaluation/test_models.py
uv run --no-sync mypy --strict src/evaluation/models.py
uv run --no-sync pytest tests/evaluation/test_models.py -q

If a command cannot run, report its exact output and follow AGENTS.md's managed-agent guidance; do not substitute a claimed result. Stop after reporting git status, the two Cline-owned files, a concise diff summary, and exact output/exit status for all four checks. The final status may contain only the pre-existing modified slice-plan document plus src/evaluation/models.py and tests/evaluation/test_models.py; stop and report any other path. Do not start A2 or commit.
```

### 21.2 Slice A2 — composed case, observation, and result contract

```text
Implement only Step 2.5 Slice A2 — composed case, observation, and result contract — after A1 has been independently accepted.

The human will replace [A1_CHECKPOINT_SHA] before sending this prompt. The reviewed baseline must be clean commit [A1_CHECKPOINT_SHA] on branch feat/step-2.5-golden-suite. Before any write, run git rev-parse HEAD and git status --short from the repository root. Stop if the SHA differs or status is not empty. Use repository-relative paths in every file tool and never pass an absolute Windows path to a write/edit tool.

Read AGENTS.md, Section 4.5 of the implementation plan, Sections 2–6.2 and 19–21 of the Step 2.5 slice plan, docs/EVALUATIONS.md, and the complete reviewed A1 versions of src/evaluation/models.py and tests/evaluation/test_models.py. In Plan mode, enumerate the composed models, cross-field validators, public exports, test additions, and exact three owned files. Wait for approval before Act mode.

In Act mode, extend src/evaluation/models.py and tests/evaluation/test_models.py and deliberately export the reviewed public contract from src/evaluation/__init__.py. Add Expectation, Case, raw tool/method/numerical observation leaves, Observation, and ComponentResult exactly as Section 6.2 specifies. Expected definitions, raw observations, and component outcomes must remain separate. Ordered tool/method evidence preserves order and repetition. Deterministic/no-LLM observations reject any tool or method selection evidence. All numerical values are finite, timestamps are timezone-aware, numerical paths are unique, and ComponentResult enforces the approved reason/evidence matrix.

Do not implement comparison/evaluator functions, a case catalog, fixtures, aggregation, reporting, runners, telemetry integration, CLI code, production changes, dependencies, or Slice B work.

After editing, reread all three complete repository-relative files and confirm their first and last definitions/exports. Then run exactly:

uv run --no-sync ruff check src/evaluation/models.py src/evaluation/__init__.py tests/evaluation/test_models.py
uv run --no-sync ruff format --check src/evaluation/models.py src/evaluation/__init__.py tests/evaluation/test_models.py
uv run --no-sync mypy --strict src/evaluation/models.py src/evaluation/__init__.py
uv run --no-sync pytest tests/evaluation/test_models.py -q

If a command cannot run, report its exact output and follow AGENTS.md's managed-agent guidance; do not substitute a claimed result. Stop after reporting git status, the three changed files, a concise diff summary, and exact output/exit status for all four checks. Do not start Slice B or commit.
```

### 21.3 Slice B1 — Momentum and Graham expectation dossier

```text
Implement only Step 2.5 Slice B1 — independently verified Momentum and Graham expectations.

Read AGENTS.md, the Step 2.5 implementation-plan sections on fixture design, initial composition, and independently verified values, Sections 2–7 and 19–21 of the Step 2.5 slice plan, docs/EVALUATIONS.md, the approved A1–A2 models, and only the relevant existing Momentum/Graham fixture and finance-math contracts.

In Plan mode, list the proposed minimum Momentum and Graham scenarios, the independent calculation method for each, the fixture additions actually required, and the exact files/tests you will touch. Do not propose evaluator or runner code. Wait for approval.

In Act mode, create docs/project/milestones/v0.2/step-2.5/STEP_2_5_EXPECTED_VALUES.md with reviewable fixture inputs, formulas, intermediate arithmetic, expected statuses/values, tolerances, and signal rationale for the minimum Momentum and Graham cases. Cover straightforward and boundary Momentum; three-year-average and TTM Graham Number; Graham not_applicable; explicit Graham growth assumptions/yield; missing current price; method discrimination; and the relevant precedence/as_of scenario. Use transparent manual arithmetic or a separate simple reference calculation, never production functions under test.

Add only narrowly required deterministic fixture records under src/evaluation/fixtures and fixture-focused tests under tests/evaluation/fixtures. Do not create executable Golden cases, evaluator logic, runner code, reports, CLI code, or production-strategy changes.

Run focused checks and stop for human expectation review. Report every expected value and how it was independently derived. Do not commit.
```

### 21.4 Slice B2 — FCF/Earnings Growth expectation dossier

```text
Implement only Step 2.5 Slice B2 — independently verified FCF/Earnings Growth expectations.

Read AGENTS.md, the applicable Step 2.5 fixture/expectation requirements, Sections 2–7 and 19–21 of the Step 2.5 slice plan, docs/EVALUATIONS.md, the reviewed A1–A2 contract and Slice B1 dossier, docs/user/FINANCE_MATH.md, the Step 2.4 FCF design, and only the existing annual fixture contracts needed for this task.

In Plan mode, identify the exact straightforward, insufficient-or-nonmeaningful, period-alignment, and historical-as_of scenarios; show how you will independently compute FCF, elapsed years, CAGR, status, and classification; list owned files and focused tests. Wait for approval.

In Act mode, extend STEP_2_5_EXPECTED_VALUES.md with exact input facts, intermediate arithmetic, expected typed outcomes, tolerances, and the signal contributed by each minimum FCF case. Add only narrowly required annual fixture data and fixture tests. Do not call production calculators to generate expected values and do not alter Step 2.4 financial semantics.

Do not create executable cases, evaluators, reports, runners, CLI code, or unrelated fixtures. Run focused checks, report the derivations, and stop for human expectation review. Do not commit.
```

### 21.5 Slice C — component evaluators

```text
Implement only Step 2.5 Slice C — component evaluators.

Read AGENTS.md, Sections 4.5.6–4.5.7 of the implementation plan, Sections 2–8 and 19–21 of the Step 2.5 slice plan, docs/EVALUATIONS.md, the reviewed A1–A2 models, and the reviewed expectation dossier. Do not inspect or modify production analyzers unless a named type import is needed.

In Plan mode, describe pure evaluator inputs/outputs, component denominator semantics deferred to Slice D, error categories, tolerance behavior, and exact files/tests. Wait for approval.

In Act mode, create src/evaluation/evaluator.py and tests/evaluation/test_evaluator.py. Implement pure evaluation of tool selection, independent Graham method selection, field-addressed numerical expectations with per-expectation tolerances, required/permitted/forbidden behavior, and distinct fixture/data versus numerical/selection failures. Deterministic/no-LLM selection must return not_measured and must never be converted to pass.

Do not load fixtures, dispatch tools, aggregate cases, serialize suite reports, add case definitions, or call an LLM. Modify A1–A2 models only if a concrete tested incompatibility requires it, and report that change explicitly.

Test pass/fail/not_applicable/not_measured, tolerance boundaries, permitted alternatives, forbidden behavior, and failure classification. Run focused checks and stop; do not begin Slice D or commit.
```

### 21.6 Slice D — aggregation and report contract

```text
Implement only Step 2.5 Slice D — case aggregation and machine-readable report contract.

Read AGENTS.md, Sections 4.5.7 and 4.5.11–4.5.12 of the implementation plan, Sections 2–9 and 19–21 of the Step 2.5 slice plan, docs/EVALUATIONS.md, and the reviewed evaluation models/evaluator.

In Plan mode, specify aggregate formulas, measured/applicable denominators, report fields, deterministic serialization rules, exact files, and focused tests. Wait for approval.

In Act mode, create src/evaluation/reporting.py and tests/evaluation/test_reporting.py. Aggregate already-evaluated case results without executing them. Keep strategy selection, Graham method selection, numerical correctness, fixture/data failure, and overall pass/fail distinct. Count only measured/applicable components in component denominators. Implement the plan-defined case pass rate and deterministic JSON-compatible serialization with explicit supplied metadata and no NaN/Infinity.

Do not load fixtures, dispatch tools, integrate telemetry, add case definitions, write files or CLI commands, or call an LLM. Make only narrow, tested model changes if unavoidable.

Test mixed statuses, zero applicable denominator behavior, overall pass-rate semantics, JSON round trips, and non-finite rejection. Run focused checks and stop; do not begin Slice E or commit.
```

### 21.7 Slice E1 — fixture composition and production dispatch

```text
Implement only Step 2.5 Slice E1 — fixture composition and production dispatch.

Read AGENTS.md, Section 4.5.8 and 4.5.14 of the implementation plan, Sections 2–10 and 19–21 of the Step 2.5 slice plan, docs/EVALUATIONS.md, src/orchestrator/analysis_tools.py, src/orchestrator/dispatcher.py, and src/evaluation/fixtures/*. Do not redesign those production boundaries.

In Plan mode, map each approved fixture ID/type to the existing AnalysisToolDependencies and production handler, state how missing evidence fails closed, and list exact files/tests. Wait for approval.

In Act mode, create src/evaluation/composition.py and tests/evaluation/test_composition.py. Build explicitly injected fixture-backed dependencies for all four existing production tools and execute one supplied typed case through AsyncToolDispatcher. Use explicit clocks and provider selections. Missing fixture IDs or evidence must fail without any live fallback.

Do not add a second dispatcher, generic strategy registry, reflection-based discovery, minimum case catalog, evaluator orchestration, report runner, telemetry integration, Ollama call, persistence, or CLI code. Do not modify production handlers unless a concrete defect blocks this slice; if so, stop and report it instead.

Run focused checks and stop with a composition map and test results. Do not begin E2 or commit.
```

### 21.8 Slice E2 — deterministic runner and telemetry evidence

```text
Implement only Step 2.5 Slice E2 — deterministic/no-LLM runner and telemetry evidence.

Read AGENTS.md, Sections 4.5.8 and 4.5.10 of the implementation plan, Sections 2–10 and 19–21 of the Step 2.5 slice plan, docs/EVALUATIONS.md, and the reviewed models, evaluator, reporting, composition, dispatcher, and Step 2.1 telemetry boundaries.

In Plan mode, describe the supplied-case execution sequence, observable evidence, telemetry fail-open behavior, deterministic clocking, and exact files/tests. Wait for approval.

In Act mode, create src/evaluation/runner.py and tests/evaluation/test_runner.py. Connect supplied case input to fixture composition, existing production dispatch, component evaluation, aggregation/reporting, and observational trajectory identity/evidence. The deterministic runner must not invoke an LLM and must report strategy/tool selection as not_measured even though it directly dispatches the expected tool.

Use a small synthetic test case only; do not add the minimum production catalog yet. Do not add Ollama, CLI, persistence, live providers, or telemetry-controlled behavior.

Run focused evaluation tests and stop for integration review. Report evidence flow and checks; do not begin Slice F or commit.
```

### 21.9 Slice F — evaluator mutation/self-test

```text
Implement only Step 2.5 Slice F — evaluator mutation/self-test.

Read AGENTS.md, Section 4.5.13 of the implementation plan, Sections 2–11 and 19–21 of the Step 2.5 slice plan, and the reviewed evaluator/runner tests.

In Plan mode, identify one controlled mutation that proves a meaningful evaluator failure without entering the benchmark denominator, the exact test file, and expected failure category. Wait for approval.

In Act mode, create or extend tests/evaluation/test_evaluator_self_test.py. Prove that the correct observation passes and a deliberately wrong numerical or selection observation is detected in the expected category. The synthetic mutation is test input only and must not become a normal Golden case or make pytest fail when detection succeeds.

Change production/evaluator code only if this test exposes a genuine defect, and report any such correction. Do not add catalog cases or future-slice work. Run focused checks and stop; do not commit.
```

### 21.10 Slice G1 — Momentum minimum cases

```text
Implement only Step 2.5 Slice G1 — the two reviewed minimum Momentum Golden cases.

Read AGENTS.md, Sections 4.5.3–4.5.5 of the implementation plan, Sections 2–12 and 19–21 of the Step 2.5 slice plan, docs/EVALUATIONS.md, the reviewed expectation dossier, and the completed evaluation runtime. Use only the reviewed Momentum expectation/fixture records.

In Plan mode, name the stable case IDs, prompts, fixture IDs, expected tool constraints, expected numerical fields/tolerances, and exact files/tests. Wait for approval.

In Act mode, add only the straightforward Momentum case and the reviewed insufficient-history or point-in-time boundary case under src/evaluation/cases, with focused catalog and deterministic-runner tests. Match the reviewed expectation dossier exactly and identify the signal supplied by each case.

Do not add Graham/FCF cases, invent new expected values, call an LLM/live provider, broaden fixtures, or change production Momentum semantics. Run the two cases deterministically plus focused quality checks. Stop with their report results; do not begin G2 or commit.
```

### 21.11 Slice G2 — Graham Number minimum cases

```text
Implement only Step 2.5 Slice G2 — the reviewed minimum Graham Number cases.

Read AGENTS.md, the applicable Step 2.5 case/expectation requirements, Sections 2–12 and 19–21 of the Step 2.5 slice plan, docs/EVALUATIONS.md, the reviewed expectation dossier, and the completed evaluation runtime. Use only reviewed Graham Number fixture evidence.

In Plan mode, name stable IDs and exact expectations for default three-year-average EPS, explicit TTM EPS, not_applicable, and missing-current-price cases; list files/tests. Wait for approval.

In Act mode, add only those four Graham Number cases under src/evaluation/cases with focused catalog and deterministic-runner tests. Preserve the distinction between a valid valuation without a price comparison and an analysis failure. Match reviewed values and tolerances exactly.

Do not add growth-value, resolution, Momentum, or FCF cases; do not recalculate expectations with production functions; do not alter Graham semantics. Run focused checks and the four deterministic cases, then stop. Do not begin G3 or commit.
```

### 21.12 Slice G3 — Graham growth and resolution minimum cases

```text
Implement only Step 2.5 Slice G3 — reviewed Graham growth-value, method-discrimination, and input-resolution cases.

Read AGENTS.md, Sections 4.5.3–4.5.7 of the implementation plan, Sections 2–12 and 19–21 of the Step 2.5 slice plan, docs/EVALUATIONS.md, the reviewed expectation dossier, and existing production Graham handler/service contracts.

In Plan mode, name stable IDs, explicit growth assumptions/yield, method-selection constraints, precedence/as_of evidence, expected outputs/tolerances, and exact files/tests. Wait for approval.

In Act mode, add only the reviewed growth-value case, independent Graham method-selection discriminator, and precedence/as_of case under src/evaluation/cases. Add focused catalog/evaluation/runner tests. Match the dossier; keep broad strategy selection and Graham method selection independently observable.

Do not add other strategies' cases, expand provider behavior, change Graham calculations, call an LLM/live provider, or generate expectations from production output. Run focused checks and these deterministic cases, then stop. Do not begin G4 or commit.
```

### 21.13 Slice G4 — FCF minimum cases and cross-strategy discrimination

```text
Implement only Step 2.5 Slice G4 — reviewed FCF/Earnings Growth minimum cases and explicit cross-strategy discrimination.

Read AGENTS.md, Sections 4.5.3–4.5.7 of the implementation plan, Sections 2–12 and 19–21 of the Step 2.5 slice plan, docs/EVALUATIONS.md, the reviewed expectation dossier, and the completed FCF production/evaluation contracts.

In Plan mode, name stable IDs and expectations for straightforward growth, insufficient or mathematically nonmeaningful growth, and period-alignment/historical-as_of behavior. Identify which existing minimum case will explicitly discriminate the requested strategy from a plausible wrong strategy; do not add an unnecessary extra case if one already supplies that signal. List files/tests. Wait for approval.

In Act mode, add only the reviewed FCF cases and the explicit discrimination metadata/constraints under src/evaluation/cases, with focused catalog/evaluator/runner tests. Match independent values and tolerances exactly.

Do not add automatic expansion cases, alter FCF financial semantics, call an LLM/live provider, or tune expectations to produce passes. Run focused checks and all new deterministic cases, then stop. Do not proceed past Gate M or commit.
```

### 21.14 Gate M — minimum-suite verification and mandatory stop

```text
Perform only Step 2.5 Gate M verification. Do not implement later slices.

Read AGENTS.md, Section 4.5.18 items 10–12, Sections 2, 12–13, and 19–22 of the Step 2.5 slice plan, and docs/EVALUATIONS.md. First enumerate the exact reviewed minimum case IDs and map them to every minimum requirement. If any requirement lacks a case, stop and report it rather than inventing a case.

Run the full deterministic/no-LLM minimum suite and the complete repository quality-gate wrapper required by AGENTS.md. Confirm no live provider or LLM call occurred, deterministic strategy selection is not_measured, component denominators are honest, the evaluator self-test remains outside the denominator, and the report is reproducible.

Do not change expectations, remove failures, expand cases, add Ollama mode, add CLI work, claim Step 2.5 complete, or commit. If a test or case fails, report the exact classified failure and relevant evidence without weakening the benchmark. Stop and provide the case/results table and complete gate output summary for human review.
```

### 21.15 Slice H — approved Gate M correction

```text
Implement only the Step 2.5 Slice H corrections approved by the 2026-08-31 Gate M review.

Correct the 76 strict-mypy errors. Add and wire a narrowly typed expected-domain-outcome contract so the runner/report evaluates exact native statuses, material metric availability, reasons, and classifications. Preserve case IDs and verified numbers while correcting/versioning MOM-02, GRA-ETF-01, GRN-05, FCF-02, and FCF-03. Add MOM-ETF-01, GRG-ETF-01, and FCF-ETF-01 against the reviewed ETF fixture boundary. Add one canonical deterministic fifteen-case catalog/request builder and report entry point, but no public CLI. Add mutation/regression tests proving wrong domain outcomes fail and correct expected input_unavailable/not_applicable outcomes pass.

Read AGENTS.md, Sections 12–14 and 19–22 of the Step 2.5 slice plan, the Gate M review entry, and only the contracts named by the approved action.

In Plan mode, explain why the action adds distinct benchmark signal or corrects a demonstrated defect, list exact files/tests, and prove it does not tune results merely to improve the pass rate. Wait for approval.

In Act mode, implement only that action. Preserve all reviewed case IDs and expectations unless the human explicitly approved a versioned correction. Add focused deterministic tests and document the reason for any new case.

Do not perform generic expansion, opportunistic cleanup, real-Ollama work, CLI work, production financial changes, or other review findings. Run focused checks, the canonical deterministic suite, and the complete repository quality-gate wrapper, then stop at Gate M. Do not commit.
```

This handoff becomes executable only after the current documentation-only
checkpoint is explicitly reviewed. It does not authorize implementation during
the documentation-only interval.

### 21.16 Slice I — optional real-local-Ollama evaluation mode

```text
Implement only Step 2.5 Slice I — optional real-local-Ollama empirical evaluation mode — after Gate M approval.

Read AGENTS.md, Sections 4.5.6 and 4.5.8–4.5.10 of the implementation plan, Sections 2, 13–15, and 19–22 of the Step 2.5 slice plan, docs/EVALUATIONS.md, the production orchestrator/telemetry boundaries, and the reviewed deterministic runner. Keep the Cline implementation model configuration separate from the model-under-evaluation configuration.

In Plan mode, define the single mode-specific module, injected Ollama/client boundary, recorded model/sampling/repetition metadata, trajectory evidence, nondeterministic outcome treatment, and mocked tests. Wait for approval.

In Act mode, add the smallest reviewed mode-specific runner (normally src/evaluation/ollama_runner.py) that sends case prompts through the real production orchestration/tool-dispatch path and measures observable strategy, Graham method, tool, and argument selection. Record model identifier, Ollama version/configuration, sampling settings, repetitions, per-run outcomes, and trajectory identity. Do not inspect or store private reasoning.

All normal pytest tests must mock the local-model endpoint. Real Ollama execution must be explicit, optional, and separate from deterministic CI. Do not change deterministic expectations or convert nondeterministic failures into passes. Run focused mocked tests and stop; do not begin CLI work or commit.
```

### 21.17 Slice J — CLI and documentation completion

```text
Implement only Step 2.5 Slice J — reviewed CLI integration and evaluation-guide completion.

Read AGENTS.md, Sections 4.5.15–4.5.16 of the implementation plan, Sections 2, 13–16, and 19–22 of the Step 2.5 slice plan, docs/EVALUATIONS.md, the existing Typer CLI conventions, and the reviewed deterministic and optional empirical runners.

In Plan mode, specify commands/options for full suite, one case, deterministic mode, optional real-local-Ollama mode, report path, and exit statuses; list exact files/tests/docs. Wait for approval.

In Act mode, add the narrow command integration under the existing CLI boundary. Required benchmark failures return non-zero; configuration/fixture failures remain distinguishable. Complete docs/EVALUATIONS.md with exact commands, report fields, failure interpretation, fixture/case maintenance, and deterministic-versus-empirical separation. Add deterministic CLI tests with mocked model endpoints where applicable.

Do not redesign the CLI, add dependencies, make real model/network calls in pytest, change case expectations, or claim final completion. Run focused checks and stop; do not begin Slice K or commit.
```

### 21.18 Slice K — closeout verification

```text
Perform only Step 2.5 Slice K closeout preparation. Final approval remains human-owned.

Read AGENTS.md, all Step 2.5 acceptance criteria, Sections 2, 13–17, and 19–22 of the Step 2.5 slice plan, docs/EVALUATIONS.md, and the Gate M review record. Enumerate every acceptance criterion and point to concrete code, test, documentation, or measured-result evidence.

Run the complete repository quality-gate wrapper and the documented deterministic Golden Suite command. Record the exact case count, component metrics, aggregate result, report location, and proof that selection is not_measured in deterministic mode. If an empirical run has been explicitly authorized and performed, record it separately with its complete model/runtime configuration; otherwise state that it was not run.

Do not weaken or repair failing expectations merely to close the step. Make only narrow documentation-status corrections that reflect already-verified facts; stop and report any code/test failure for a separate reviewed correction. Do not mark Step 2.5 complete, commit, push, open a PR, or merge. Stop for final human approval.
```

## 22. Implementation execution and review record

This is the living audit trail for Step 2.5 implementation. The retired Cline attempts remain historical evidence; all P1 and later implementation is Codex-owned. Any implementation summary is evidence to review, not the review verdict. The human or reviewing agent updates this section after inspecting the actual diff and independently rerunning appropriate checks.

### 22.1 Runtime preflight record

| Date | Cline version | Ollama version | Model alias and digest | Context | `ollama ps` processor | Tool smoke test | Decision/notes |
| :--- | :--- | :--- | :--- | ---: | :--- | :--- | :--- |
| 2026-08-30 | `v4.1.16 (Next)` | `0.33.2` | `financial-data-agents-step-2-5:latest` / `5d94265d163a` | 65,536 allocated | **100% GPU — pass** | **Pass** — file read and bounded Git command | Preflight passed after removing stale GPU-discovery overrides and fully restarting Ollama; later implementation attempts failed review and the Cline experiment was terminated. |

Verified Cline UI state on 2026-08-30:

- Ollama provider at `http://192.168.1.19:11434`, with no `/v1` suffix and no API key.
- `financial-data-agents-step-2-5:latest`, 65,536-token context, 600,000 ms request timeout, and the same model for Plan and Act.
- Auto Compact enabled with the `Agentic` strategy; Web Search, Background Edit, Hooks, Fetch web content auto-approval, and MCP-server auto-approval disabled.
- Checkpoints enabled; read-file, edit-file, and command auto-approval enabled. Edit approval applies only while executing an approved slice in Act mode.
- VS Code Terminal execution with Git Bash, four-second shell-integration timeout, and aggressive terminal reuse.
- MCP display mode `Plain Text`; English preferred language; error and usage reporting enabled.

Reported inference-host inventory from `nvidia-smi` at 2026-08-30 13:59:02:

| Component | Recorded value |
| :--- | :--- |
| NVIDIA driver / CUDA UMD | `610.88` / `13.3` |
| GPU 0 | NVIDIA GeForce RTX 5060 Ti, 16,311 MiB VRAM; 5 MiB in use while idle |
| GPU 1 | NVIDIA GeForce RTX 3080 Ti, 12,288 MiB VRAM; 484 MiB in use while driving the display |
| Combined physical VRAM | 28,599 MiB across two GPUs |

Idle hardware capacity does not prove that the model and 65,536-token K/V cache remain fully GPU-resident. Record the model digest, allocated context, and processor split from `ollama ps` while the Cline smoke task is actively generating.

Initial processor-placement attempt on 2026-08-30: four `ollama ps` samples while the alias was loaded reported a 22 GB allocation at 65,536 context and `100% CPU`. This fails the mandatory placement criterion. Do not begin Slice A or reduce the benchmark requirements to accommodate CPU execution. Inspect the Ollama server log for CUDA discovery, selected runner library, available/required VRAM, requested/offloaded layers, and allocation errors before changing the Modelfile.

Initial shell triage found that the created alias contains `PARAMETER num_ctx 65536` and no `num_gpu` parameter. `CUDA_VISIBLE_DEVICES=0,1` was set at both Process and User scope. No `OLLAMA_LLM_LIBRARY`, `OLLAMA_VULKAN`, `GGML_VK_VISIBLE_DEVICES`, or `OLLAMA_GPU_OVERHEAD` value appeared in the querying shell. This ruled out an alias-level CPU request but did not establish the environment inherited by the already-running server process.

The subsequent server log resolved that distinction. At startup, the actual Ollama server process reported `CUDA_VISIBLE_DEVICES=0,1` and experimental `OLLAMA_VULKAN=true`, warned that visible devices had been overridden and should be unset if discovery failed, and then registered only `id=cpu library=cpu`. No CUDA inference device or GPU allocation was registered. The 48-layer model and 3,264 MiB q8_0 K/V cache were consequently fitted entirely to host memory. This is a GPU-discovery failure, not evidence that the combined VRAM is insufficient, and adding `num_gpu` cannot help until a CUDA device is registered.

Corrective retry: fully stop the Ollama server, remove `CUDA_VISIBLE_DEVICES` and `OLLAMA_VULKAN` from the new server process, retain the reviewed context/Flash-Attention/q8_0/serial settings, and restart it. The startup log must register both NVIDIA adapters with a CUDA library before loading the alias. If unrestricted discovery succeeds and later restriction is necessary, use the GPU UUIDs reported by `nvidia-smi -L` rather than numeric device indices. Only reconsider `num_gpu` if CUDA discovery succeeds but the scheduler requests zero or partial GPU layers.

Final preflight result on 2026-08-30: after fully stopping the stale server and restarting without the `CUDA_VISIBLE_DEVICES` and experimental `OLLAMA_VULKAN` overrides, `ollama run` returned the requested `OK` and `ollama ps` reported alias digest `5d94265d163a`, 22 GB, `100% GPU`, and 65,536 context. Cline then completed the bounded smoke prompt: it read `AGENTS.md`, correctly reported its first heading as `# Financial Data Agents – Development LLM Guardrails`, ran the read-only branch command, correctly reported `feat/step-2.5-golden-suite`, and stated that it made no file modifications. The runtime/tool preflight therefore passed; the subsequent implementation failures show that this smoke test was insufficient to establish implementation reliability.

### 22.2 Slice review log

| Slice | Attempt/config | Implementation summary | Independent review findings | Corrections/follow-up | Verification | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| P0 | Codex prerequisite work; no Cline attempt | Extracted deterministic fixtures, added evaluation scaffold/guide, and registered four dependency-injected production handlers. | Reviewed during prerequisite implementation; full repository gate passed with 940 tests and 86% coverage. | None recorded. | Ruff, format, strict mypy, 940 pytest tests | Complete |
| P1-A | Codex; approved production prerequisite | Inspected yfinance 1.6.0 sources and live FLSW/AAPL/BTC-USD metadata, then proposed exact kind mappings, separate evidence/profile contracts, schema changes, and P1-B/P1-C tests. | Mapping record preserves SEC identity separately from Yahoo kind evidence; no production code changed. | Human approved the record without amendment on 2026-08-30. | Live read-only metadata check; documentation diff check | Complete and approved |
| P1-B | Codex; focused production-contract slice | Added immutable kind evidence/profile contracts, exact Yahoo mapping, ordered fail-open candidate composition, shared Yahoo metadata retrieval, narrow adapter/façade routing, and deterministic tests. | SEC identity and Yahoo kind retain separate provenance; unknown/error remains fail-open; no strategy or presentation behavior changed. | Human reviewed and approved P1-B on 2026-08-30, authorizing P1-C. | Focused Ruff, format, strict mypy, and 28 deterministic tests | Complete and approved |
| P1-C | Codex; strategy-applicability slice | Wired request-scoped profiles through CLI and production handlers; added ETF-native Graham/FCF `not_applicable`, retained Momentum behavior, coherent identity/kind presentation, successful domain-outcome exit codes, and removed unsupported ticker-verification advice. | Only affirmative ETF evidence short-circuits; equity, unknown, and provider-error profiles retain existing resolution. FCF result schema advances to 3 without a method-version change; Momentum/Graham presentation schemas advance to 3 and FCF presentation to 4. | Human approval authorized A1; the completed P1 contract is now Golden input. | Focused Ruff, format, strict mypy, and 89 deterministic tests; complete gate: Ruff, format, strict mypy, 972 tests, 86% coverage | Complete and approved |
| A (retired monolith) | Attempts 1–2; recommended model/profile | Twice claimed a complete typed contract and passing verification. | Attempt 1 wrote a truncated, non-importable module and an unintended root file; attempt 2 replaced the module with one comment, retained the unintended file and incomplete tests, and again reported checks that did not match disk state. | Human cleanup; replace the monolith with A1–A2 and require relative write paths, full-file read-back, and exact command evidence. | Attempt 1: Ruff 76 errors, mypy 69 errors, pytest collection error. Attempt 2: Ruff 1 error, format pass, vacuous mypy pass, pytest import error. | Rejected/retired |
| A1 (Cline attempt) | Attempt 1; fresh Qwen task with reduced prompt | Claimed all enums, four frozen leaf models, comprehensive tests, and successful checks. | Wrote only five enum classes, imported unavailable third-party `strenum` instead of `enum.StrEnum`, omitted every leaf model, and never created the test file. | Reject the artifact and terminate Cline implementation for all Golden Suite slices. | Ruff 13 errors; format failed; mypy 6 errors; pytest found no test file. | Rejected; Cline experiment terminated |
| A1–G4 | Codex; reviewed implementation sequence | Added the typed models, expected-value dossier, evaluators, reports, deterministic runner, self-tests, fixtures/composition, and twelve reviewed cases now present at checkpoint `4d08b127`. | The 2026-08-31 Gate M audit found the bounded runner/domain-outcome, canonical-catalog, ETF-matrix, and strict-typing defects recorded in the Gate M review. | Complete only the approved Slice H corrections; do not rewrite verified numerical expectations. | 217 focused evaluation tests pass; complete pytest has 1189 passes and 87% coverage; the repository wrapper fails strict mypy with 76 errors. | Implemented; Gate M corrections required |
| Gate M | Independent checkpoint audit | Enumerated the exact twelve cases, inspected aggregate semantics, and ran the repository/focused/full-test verification described in `STEP_2_5_GATE_M_REVIEW.md`. | Mandatory gate is red; one canonical full-suite report cannot yet be produced. | Slice H approved as a bounded mandatory correction; return to Gate M afterward. | Ruff/format pass; strict mypy fail; focused and full pytest pass. | Not approved |
| H | Codex; approved Gate M correction | Added typed domain-outcome expectations/observations, exact native-outcome evaluation, corrected five reviewed boundary cases, three ETF cases, a canonical fifteen-case entry point, and mutation regressions. | No production financial calculation, public CLI, live-provider, or LLM behavior changed. A deterministic precedence-cache fixture was added so `GRN-04` is executable through the canonical production-composition seam rather than test-only setup. | Stop at Gate M; human re-review decides whether any later slice is authorized. | Focused: Ruff, strict mypy, and 235 evaluation tests pass. Canonical report: 15/15. Complete gate: Ruff/format/strict mypy pass; 1207 tests; 87% coverage. | Implemented; awaiting Gate M re-review |
| Gate M re-entry | Slice H working tree based on documentation checkpoint `dfc3182c` | Re-ran the exact corrected deterministic minimum and complete repository gate. | All original GM-1 through GM-4 blockers have implementation evidence; GM-5 was closed by the accepted documentation checkpoint and this status update. Approval remains human-owned. | Do not start Slice I, CLI work, or closeout; do not commit until the checkpoint is requested. | Suite `step-2.5-golden-minimum`, version `h1-v2`, fixture set `step-2.5-h1-v2`: 15 passed, 0 failed; selection 15 `not_measured`; four mutations fail as expected. | Ready for human review; not yet approved |
| I | Codex; optional empirical runner | Added real-local-Ollama evaluation through production orchestration, independent repetition reports, observable configuration, and reasoning-safe telemetry. | Human reviewed and accepted Slice I; normal tests use a mocked model client. | No live benchmark run was required or authorized. | Focused Ruff/format/strict mypy; five mocked tests; runner coverage 85%. | Complete and approved |
| J | Codex; CLI/documentation completion | Added full/named-case `evaluate` CLI, deterministic and explicit Ollama modes, protected report output, failure exit codes, CLI tests, and complete operator/planning documentation. | Human reviewed and accepted Slice J after the synchronized installed launcher was verified. | Environment sync repaired the user-side launcher; no repository packaging change was required. | Focused Ruff/format/strict mypy; 306 evaluation/CLI tests; installed deterministic smoke pass. | Complete and approved |
| K | Codex; closeout verification | Ran the complete gate and canonical installed deterministic command; recorded exact metrics, artifact hash, explicit empirical absence, and all acceptance evidence. | No implementation defect or acceptance gap found. Human approval was recorded on 2026-08-31. | Step 2.5 is closed; proceed only with Step 2.5A D0 evidence freeze and stop at Gate A. | Ruff/format/strict mypy pass; 1,219 tests; 87% coverage; deterministic suite 15/15. | Complete and approved |

#### 2026-08-30 — retired Slice A, attempts 1–2

- Prompt/configuration: final reviewed monolithic Slice A prompt; Cline `v4.1.16 (Next)`, Ollama `0.33.2`, alias digest `5d94265d163a`, 65,536 context, 100% GPU.
- Cline summaries: both attempts claimed a complete immutable contract and successful verification. The second claim explicitly reported all four focused checks as passing.
- Reviewed diff: only untracked artifacts existed. An absolute Windows path was mis-encoded into a zero-byte repository-root filename. The intended package initializer remained unchanged.
- Findings: attempt 1's `models.py` began mid-module without imports/enums and could not import; its six tests omitted most of the approved matrix. After a bounded correction prompt, attempt 2 reduced `models.py` to `# Simple test file`, retained the malformed root file and old tests, and again claimed completion.
- Independent verification: attempt 1 produced 76 Ruff errors, 69 strict-mypy errors, and a pytest collection `NameError`; formatting passed. Attempt 2 produced one Ruff error and a pytest collection `ImportError`; formatting passed, while mypy passed only because the source file contained no code.
- Decision: reject and retire the monolithic slice. The human owns exact cleanup of the three untracked artifacts. Resume from a clean checkpoint with fresh A1 and A2 tasks.
- Prompt lessons: keep each write small; prohibit absolute paths in file tools; require clean-SHA verification, full-file read-back, and exact command output; never accept a model's completion summary without inspecting disk and rerunning checks.

#### 2026-08-30 — Slice A1, attempt 1

- Prompt/configuration: fresh reduced A1 task; Cline `v4.1.16 (Next)`, Qwen3-Coder alias digest `5d94265d163a`, 65,536 context, 100% GPU; exact enums, fields, exclusions, relative paths, baseline state, read-back, and command requirements supplied.
- Cline summary: claimed five `StrEnum` classes, all four frozen leaf models, comprehensive tests, and successful validation.
- Reviewed diff: `src/evaluation/models.py` was the only Cline-owned artifact. It contained 41 lines defining only the five enums. `tests/evaluation/test_models.py` did not exist. The human-owned slice-plan modification remained separate.
- Findings: imported undeclared third-party `strenum` despite Python 3.12's standard-library `enum.StrEnum` and the no-dependency rule; omitted ToolConstraints, GrahamMethodConstraints, BehaviorConstraints, NumericalExpectation, all validators, all tests, module/class docstrings, and required verification.
- Independent verification: Ruff reported 13 errors; format-check reported the source unformatted and the test path missing; strict mypy reported 6 errors; pytest reported the test path missing and ran zero tests.
- Decision: reject and stop the current task. Because the failure recurred in a fresh, materially smaller slice after the tool smoke test and explicit corrections, treat Qwen3-Coder as unreliable for Cline implementation on this host. The Section 19.2 fallback condition is met.
- Prompt lessons: further prompt expansion is unlikely to correct the discrepancy between disk state and completion claims. Change the implementation model or implementation owner before retrying A1.

#### 2026-08-30 — final implementation-owner decision

- Decision: stop attempting to use Cline for implementation of any remaining Step 2.5 Golden Suite slice. Do not test the previously proposed Devstral fallback as part of this step.
- Basis: three materially false completion reports across a retired monolith and a fresh reduced slice made Cline's reports non-auditable without effectively redoing each implementation. The extra prompting, cleanup, model/runtime preflight, and independent verification cost exceeded the intended benefit of delegation.
- Ownership: Codex will implement the remaining slices one at a time after explicit human discussion or authorization, preserving the slice boundaries, independent verification, and mandatory human review gates in this document.
- Record retention: keep the Cline configuration, prompts, and review findings as historical evidence. They must not be treated as active recommendations or benchmark results.

### 22.3 Review-entry checklist

For every completed attempt, record:

1. Cline and Ollama versions, model digest, context, and any configuration deviation.
2. The prompt revision used and whether Plan mode stayed within the named files.
3. Actual files changed, including unexpected files.
4. Behavioral and architectural findings from the diff, ordered by severity.
5. Focused and full checks independently rerun, with exact counts/results.
6. Whether the slice is accepted, needs a bounded correction, or should be restored/retried.
7. Any prompt lesson that should be incorporated into later drafts.

Do not erase failed attempts. Add a new dated entry or concise continuation so the record explains why a prompt or configuration changed.

### 22.4 Detailed review-note template

Add one subsection per attempt when the table cannot hold the useful review detail:

```text
#### YYYY-MM-DD — Slice X, attempt N

- Prompt/configuration: prompt revision, Cline version, Ollama version, model digest, context, and deviations.
- Cline summary: concise factual summary of what Cline claimed to implement and verify.
- Reviewed diff: files changed and any unexpected scope.
- Findings: severity-ordered correctness, architecture, typing, test, and documentation findings.
- Independent verification: exact commands and results.
- Decision: accepted, bounded correction required, or restore/retry.
- Prompt lessons: changes to make to later prompt drafts.
```
