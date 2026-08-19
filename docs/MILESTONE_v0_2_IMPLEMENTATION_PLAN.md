# Milestone v0.2 Implementation Plan
## Reliability, Observability, Data Persistence & Strategy-General Evaluation

**Project:** Financial Data Agents  
**Repository:** [https://github.com/PeterPontbriand/financial-data-agents](https://github.com/PeterPontbriand/financial-data-agents)  
**Source of truth:** Current `docs/MASTER_PLAN.md` (Milestone v0.2 section)  
**Companion rationale:** Current `docs/DISCOVERY_WORKBOOK.md`  
**Prepared:** 2026-08-15  
**Revised:** 2026-08-19 — Separated the Graham strategy/data-contract foundation from the Golden Suite, bumped subsequent Step 2 work accordingly, added staged implementation guardrails for Cline, and clarified deterministic versus empirical evaluation boundaries.  
**Status:** Step 2.2 → Implementation complete / merge-ready; Step 2.3 → Ready to resume
↳ Follow-up validation: empirically verify native schema support for the actual Light Mode model configuration.

---

## 1. Purpose & Scope

This plan turns the high-level Master Plan steps for Milestone v0.2 into an actionable, sequenced work package that the development team can organize around **before** writing production code.

**In scope**
- Step 2 – Agent Reliability, Evaluation & Observability Foundation (2.1 → 2.5)
- Step 3 – Relational Data Persistence Layer & Data Quality (3.1 → 3.3)
- Step 3.5 – Light Mode Support (required before the v0.2.5 checkpoint)

**Out of scope (explicit)**
- Milestone v0.2.5 real-user validation activities (recruitment, feedback sessions)
- Milestone v0.3 analytics expansion or localization
- Multi-step autonomy / executive reporting (Milestone v1.0)
- Any UI / dashboard work

**Success definition for the milestone**  
A clean, Light-Mode-capable analysis path exists that:
1. Logs full trajectories (prompts, tool calls, latency, tokens).
2. Enforces native Ollama JSON schema constraints + Pydantic validation.
3. Passes a golden-test suite at the ≥ 90 % target.
4. Has hard circuit-breaker and timeout limits.
5. Persists data and execution logs in SQLite (WAL) with typed DAOs and basic data-quality checks.
6. Can be run end-to-end by a new user following only the Light Mode instructions in `docs/HARDWARE.md` and the README.

---

## 2. Guiding Constraints

The following core principles govern all technical decisions across Milestone v0.2.

| Constraint | Description & Architectural Principle | Primary Impacted Packages |
| :--- | :--- | :--- |
| **Python Determinism** | Deterministic math stays in Python; LLM is used only for planning, tool selection, and narrative synthesis. | Step 2.2, Step 2.3, Step 2.4 |
| **Typed Tool Interfaces** | All tool arguments and return structures must be strictly defined via Pydantic models. | Step 2.1, Step 2.2, Step 3.2 |
| **Native Schema Formatting** | Native Ollama `format=Schema` (or provider equivalent) is preferred over post-hoc string/regex parsing. | Step 2.2 |
| **Light-Mode Default** | Light Mode is the default adoption and execution path; Full Dual-Tier remains optional. | Step 3.5 |
| **Strict Quality Gates** | Strict typing (`mypy --strict`), Ruff, and pytest coverage are non-negotiable CI gates. | All Work Packages |
| **Guarded Egress** | Outbound network access is strictly guarded (cache-first, rate-limited, domain-whitelisted). | Step 3.1, Step 3.3 |
| **Classified Diagnostics** | Failures are categorized (transient vs. non-recoverable) and surface structured diagnostics. | Step 2.1, Step 2.5 |
| **Decoupled Contracts** | Decoupled, swappable implementations behind narrow interfaces are preferred over direct library dependencies. | Step 2.1, Step 2.3, Step 3.1 |
| **Heterogeneous Strategy Independence** | Financial-analysis strategies must be independently selectable, deterministic, typed, and swappable. The runtime and data layer must not assume that all financial analysis follows a single analytical pattern. | Step 2.3, Step 2.4, Step 3.1, Step 4 |

---

## 3. Recommended Branch & PR Strategy

Use **fine-grained branches aligned with coherent implementation units within a Master Plan step**. Do not use one branch spanning the entire milestone, and do not create trivial one-change branches merely for mechanical edits.

| Work unit | Suggested branch | Rationale |
| :--- | :--- | :--- |
| Step 2.1 telemetry model | `feat/step-2.1-telemetry-model` | Establishes the stable event contract |
| Step 2.1 sinks | `feat/step-2.1-telemetry-sinks` | Adds sink abstraction + JSONL persistence |
| Step 2.1 runtime instrumentation | `feat/step-2.1-runtime-instrumentation` | Wires telemetry into orchestrator/LLM/tool boundaries |
| Step 2.1 integration tests/docs | `feat/step-2.1-telemetry-integration` | Demonstrates complete trajectory reconstruction |
| Step 2.2 schema enforcement | `feat/step-2.2-schema-enforcement` | Isolates native structured-output work |
| Step 2.3 Graham/data foundation | `feat/step-2.3-graham-data-contracts` | Adds the second heterogeneous strategy and the shared market-data contract |
| Step 2.4 Golden runner | `feat/step-2.4-golden-suite` | Implements heterogeneous benchmark cases and evaluation harness |
| Step 2.5 reliability limits | `feat/step-2.5-circuit-breakers` | Isolates hard execution limits |
| Step 3.1 persistence foundation | `feat/step-3.1-sqlite-foundation` | Alembic, schema, SQLite telemetry sink, production data access |
| Step 3.2 repositories | `feat/step-3.2-repositories` | Typed DAO/repository layer |
| Step 3.3 data quality | `feat/step-3.3-data-quality` | Validation, staleness, invalidation |
| Step 3.5 Light Mode | `feat/step-3.5-light-mode` | Adoption path and smoke validation |

**Working agreement**
- Prefer small, reviewable PRs that each leave `main` green.
- Every PR must pass the CI quality gates.
- Branch names should identify the Master Plan step they implement.
- Temporary scaffolding must be documented and have an explicit removal point.
- Documentation-only changes may use `docs/...` branches where that is clearer.

---

## 4. Detailed Work Packages

### 4.1 Step 2.1 – Trajectory Logging & Telemetry

**Goal**  
Establish the project's machine-readable observability foundation without duplicating the existing human-oriented operational logger or blocking on the production SQLite layer.

**Architectural boundary**

```text
                         Agent Runtime
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
       Operational logging             Trajectory telemetry
       (`logger_util.py`)              (typed event model)
              │                               │
       human-readable                    machine-readable
       diagnostics                       execution history
                                              │
                                      ┌───────┴───────┐
                                      ▼               ▼
                                    JSONL           SQLite
                                  (Step 2.1)      (Step 3.1)
```

The existing `src/utils/logger_util.py` provides asynchronous queue-based logging, dual console/file routing, rotation, compression, and graceful shutdown. Step 2.1 will **reuse its configuration conventions** rather than replace it.

**Sequencing decision**  
Step 2.1 defines a narrow `TrajectorySink` abstraction and implements JSONL first. Step 3.1 later adds a SQLite sink satisfying the same abstraction. The orchestrator and telemetry recorder remain decoupled from the specific underlying storage choice.

**Telemetry semantics & Concrete Event Types**  
To ensure clarity during implementation, the initial system will emit a closed set of concrete, strongly-typed event types:

* `RUN_START`: Triggered when an overall analysis session or trajectory begins.
* `RUN_END`: Triggered when a session completes (successfully or with terminal error).
* `STEP_START`: Emitted at the start of an orchestrator planning cycle.
* `STEP_END`: Emitted at the completion of an orchestrator planning cycle.
* `LLM_REQUEST`: Logged prior to sending prompts to the underlying model provider.
* `LLM_RESPONSE`: Logged upon receiving completion outputs from the model.
* `TOOL_CALL_START`: Emitted when an internal Python tool invocation begins.
* `TOOL_CALL_END`: Emitted upon successful tool execution, capturing validated results.
* `TOOL_CALL_FAILED`: Logged when a tool throws an unhandled exception or validation failure.
* `RECOVERY_ATTEMPT`: Triggered when a transient failure initiates a retry or fallback path.

Every telemetry event envelope captures standard metadata fields including `event_id`, `trajectory_id`, `sequence`, `timestamp`, `event_type`, `component`, `schema_version`, latency, parent/correlation identifiers, and payload metadata according to configurable retention rules.

**Observability & Data Boundaries**  
The telemetry recorder will capture and store observable data explicitly exposed by the model or provider during execution. This includes prompts, returned completions, tool inputs/outputs, wall-clock timing, and provider token metrics. If specific metrics (such as token counts or extended latency breakdown) are omitted by a local model/provider, the event will explicitly capture these as `null` or missing fields rather than estimating or fabricating metrics.

**Implementation outline**
1. Define typed telemetry event schemas (including the concrete `event_type` enumeration) and envelope models under `src/core/telemetry/`.
2. Define the `TrajectorySink` Protocol interface.
3. Implement `JSONLTrajectorySink` as the initial persistence sink.
4. Implement `TrajectoryRecorder` to manage monotonic sequence assignment and `trajectory_id` tracking.
5. Instrument trajectory, step, LLM, tool, and failure boundaries without altering core execution semantics.
6. Capture token usage when available; render missing provider metrics explicitly as `None`.
7. Add payload sanitization/redaction at the telemetry boundary to guard secrets.
8. Integrate telemetry configuration into `ProjectSettings`, mirroring `logger_util.py` retention options.
9. Add unit tests for serialization, redaction, sequencing, and sink behavior.
10. Add integration tests verifying complete trajectory reconstruction from logged JSONL files.
11. Update `docs/ARCHITECTURE.md` with sink contracts and logging boundaries.

**Acceptance criteria**
- [x] A complete representative analysis produces a coherent ordered trajectory using the defined event types.
- [x] LLM requests/responses, tool calls/results, failures, latency, and exposed token metrics are fully recorded.
- [x] Provider limitations (e.g., missing token counts) are logged explicitly as missing data without execution failure.
- [x] Telemetry persistence is independent of the orchestrator through the sink abstraction.
- [x] JSONL readback cleanly reconstructs the exact recorded event sequence.
- [x] Telemetry retention and storage controls are fully configurable via settings.
- [x] Telemetry failures fail-open and do not disrupt business execution semantics.
- [x] Secrets, API keys, and sensitive tokens are automatically redacted prior to persistence.
- [x] Quality gates pass (`mypy --strict`, Ruff, pytest).

**Follow-ups (non-blocking for Step 2.1 merge)**

- **Emit `RECOVERY_ATTEMPTED`:** The event type is defined. When the orchestrator
  repair/retry path runs, record a `RECOVERY_ATTEMPTED` event on each attempt
  (component, step_index, span linkage, sanitized error context). If recovery
  is still minimal, wire this when Step 2.5 circuit-breakers / repair policy
  lands.
- **Always set `payload_hash` when a payload is retained:** Confirm
  `TrajectoryRecorder` sets `payload_hash` for every event that keeps a
  non-null payload (integrity without storing full bodies). Leave hash null
  only when payload is omitted.
  
---

### 4.2 Step 2.2 – Native Schema Enforcement

**Goal**  
Prevent unstructured / drifting LLM output by using Ollama's native JSON-schema constraint (`format=Schema` or equivalent) wherever the model is expected to emit structured tool calls or final synthesis objects.

**Implementation outline**
1. Inventory every place the orchestrator currently asks the model for structured output.
2. Convert existing Pydantic tool / response models into the JSON Schema form expected by the Ollama client.
3. Pass the schema on every constrained generation call.
4. Keep a Pydantic validation step as a second line of defense; treat schema violation as a recoverable error that can feed the circuit-breaker / retry path.
5. Add focused unit/integration tests that mock an Ollama response and assert both successful constrained generation and graceful handling of schema violations.

**Acceptance criteria**
- [x] All tool-call extraction paths use native schema constraints when the underlying Ollama version supports them.
- [x] Schema violations are classified as transient and do not crash the process.
- [ ] Golden-test or smoke tests demonstrate reduced output-drift failures compared with the pre-constraint baseline.

> **Status:** Implementation complete and ready for PR/merge. The remaining unchecked item is deferred to Step 2.4/3.5 validation because it requires empirical evaluation rather than further Step 2.2 implementation.

**Dependencies / risks**
- The detailed Ollama/model support matrix is deferred to empirical validation against the actual Light Mode model configuration.
- Verify the actual installed Ollama version and supported Light Mode model configurations.
- Define a documented fallback for model/provider configurations that do not reliably honour native schema constraints.
- Retain Pydantic validation as the application-level defense even when native schema enforcement is active.

#### 4.2.1 Step 2.2 Follow-up Validation

- **Empirical Light Mode model compatibility:** The runtime currently
  determines native schema capability from Ollama server-version information
  and falls back conservatively when capability is unknown. A model-by-model
  empirical verification of native JSON-schema enforcement against the
  supported Light Mode model configuration remains to be performed.

  This validation is intentionally non-blocking for the Step 2.2 merge.
  Record the tested Ollama version, model identifier, schema-constrained
  request, observed response behavior, and pass/fail result when completed.
  
---

### 4.3 Step 2.3 – Graham Strategy & Market-Data Contract

**Goal**  
Add the Benjamin Graham intrinsic-value strategy as the second materially different deterministic analytical strategy and establish the minimum shared market-data contract required to support both Momentum and Graham without introducing speculative architecture.

Step 2.3 is an **architectural foundation step**, not the Golden Suite itself. Its purpose is to make heterogeneous deterministic strategies and their data requirements work cleanly through the existing analysis/tool/orchestration architecture.

The initial strategy set is:

1. **Momentum analysis** — the existing historical-price/SMA strategy.
2. **Benjamin Graham intrinsic-value analysis** — a fundamentally different valuation strategy.

The subsequent Step 2.4 Golden Suite will use these two strategies as its first heterogeneous benchmark targets.

#### 4.3.1 Strategy boundary

Each analytical strategy owns:

- its Pydantic configuration model;
- its deterministic mathematical implementation;
- its typed result/metrics model;
- only the data capabilities it actually requires.

Both strategies must be invocable through the **existing** analysis/tool/orchestration mechanisms without adding strategy-specific branches to the orchestrator. Reuse `BaseAnalyzer`, existing tool registration/dispatch, and existing dependency-injection patterns wherever they are sufficient.

Do **not** introduce a new generic `Strategy`, plugin, registry, factory hierarchy, or parallel orchestration framework merely because Momentum and Graham differ. Introduce a new abstraction only if inspection proves that the existing architecture cannot express the required boundary cleanly.

The fact that Graham and Momentum have different inputs and outputs is intentional:

```text
                         Analysis Runtime
                                │
                     existing generic path
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
        MomentumAnalyzer                GrahamValueAnalyzer
                 │                             │
       historical prices             EPS / growth / yields
                 │                             │
             SMA/trend                 intrinsic value
                 │                             │
                 └──────────────┬──────────────┘
                                ▼
                       typed analysis results
```

Do not make Graham "Momentum-shaped" merely for implementation consistency.

#### 4.3.2 Benjamin Graham strategy requirements

Treat the supplied Graham implementation as a **starting point**, not an immutable patch. The following corrections are intentional requirements.

The implementation must:

- expose parameters through `GrahamValueConfig`;
- expose deterministic results through `GrahamValueMetrics`;
- preserve dependency injection through `BaseDataClient`;
- document the exact Graham formula convention implemented;
- obtain current market price through the shared market-data abstraction rather than a one-day historical-data workaround;
- include `current_price: float | None` in the typed metrics;
- use `margin_of_safety_percent: float | None`;
- represent unavailable current price / margin of safety as `None`, never as a false numeric zero;
- document that positive margin of safety means price is below estimated intrinsic value, while negative margin means price exceeds estimated intrinsic value;
- reject mathematically invalid configuration values;
- avoid arbitrary financial-domain bounds unless they have explicit rationale and tests;
- avoid broad `except Exception` handling where the data-client contract provides narrower failure types;
- remain independent of Momentum-specific models and orchestration.

The selected formula convention is:

```text
V = EPS × (base_pe + growth_multiplier × g)
    × baseline_aaa_yield / current_aaa_yield
```

where `g`, `baseline_aaa_yield`, and `current_aaa_yield` are expressed in percentage points (for example, `6.5` means 6.5%).

The implementation must state that this is the project's selected revised Graham-formula convention rather than implying that all published/restated versions use identical constants.

**Required deterministic tests**

- exact/reference formula calculation;
- invalid/non-positive EPS;
- mathematically invalid yield/configuration values;
- explicit supplied `current_price`;
- injected data-client current-price retrieval;
- unavailable current price → `current_price is None` and `margin_of_safety_percent is None`;
- positive and negative margin-of-safety semantics.

#### 4.3.3 Market-data contract

Inspect the existing data clients and define the **minimum** typed market-data contract required by Momentum and Graham.

The contract must distinguish at least:

- **historical market data** — required by Momentum;
- **current market quote/price** — required by Graham.

The existing `BaseDataClient` remains the provider boundary. Extend it only as necessary to expose a narrow current-price/quote operation alongside historical-data access.

Do not make Graham obtain a quote by downloading a one-day historical DataFrame merely because that operation already exists.

Conceptually:

```text
BaseDataClient
    │
    ├── historical market data
    │       └── Momentum
    │
    └── current market quote
            └── Graham
```

The contract must:

- be fully typed;
- avoid exposing `yfinance`-specific types to consumers where a provider-neutral boundary is appropriate;
- make missing data explicit;
- support deterministic fixture execution without network access;
- be narrow enough that Step 3.1 can later supply a SQLite/cache-backed implementation;
- avoid speculative operations that are not required by the initial strategies.

The exact method/model names should follow existing project conventions. Prefer the smallest clean change consistent with the current codebase.

#### 4.3.4 Fixture adapter for contract validation

Step 2.3 should include only the **minimal fixture-backed adapter/data needed to prove the shared market-data contract**. This adapter is foundation for Step 2.4; it is not yet the Golden Suite.

The fixture adapter must:

- satisfy the same typed market-data contract as provider-backed clients;
- support historical data required by Momentum;
- support current-price data required by Graham;
- fail explicitly when requested data is absent;
- perform no live network fallback;
- remain deterministic across repeated runs.

Do not build Golden Case schemas, scoring, reports, or benchmark composition in this step.

#### 4.3.5 Implementation guardrails for Cline

- Prefer existing abstractions (`BaseAnalyzer`, `BaseDataClient`, current tool registration/dispatch, telemetry) over parallel frameworks.
- Do not create a strategy/plugin registry unless inspection proves it is required.
- Do not refactor unrelated production code.
- Treat the supplied Graham code as a starting point subject to the explicit corrections above.
- Implement the smallest change that allows Momentum and Graham to coexist through the existing runtime.
- Do not begin Golden Suite evaluator/reporting work during Step 2.3.
- If an architectural choice is ambiguous, inspect existing code and choose the smallest solution consistent with current conventions.
- Stop for human review at the Step 2.3 boundary before beginning Step 2.4.

#### 4.3.6 Implementation sequence

1. Inspect `BaseAnalyzer`, `BaseDataClient`, provider adapters, Momentum, tool registration/dispatch, orchestrator, telemetry, configuration, CLI, and relevant tests.
2. Add/refine `GrahamValueAnalyzer`, `GrahamValueConfig`, and `GrahamValueMetrics` according to this plan.
3. Add deterministic Graham unit tests.
4. Confirm Momentum and Graham can coexist through the existing analysis/tool/orchestration path without strategy-specific orchestrator branches.
5. Define/extend the minimum shared market-data contract for historical data and current quotes.
6. Update provider adapter(s) and add deterministic contract tests.
7. Implement the minimal fixture-backed adapter and focused fixture data needed to exercise both strategies.
8. Update `docs/ARCHITECTURE.md` with the resulting strategy/data boundaries.
9. Run Ruff, formatting checks, `mypy --strict`, and the complete pytest suite.
10. **Stop for review before Step 2.4 begins.**

#### 4.3.7 Non-goals

Step 2.3 does **not** include:

- Golden Suite runner/evaluator architecture;
- Golden Case schema;
- benchmark scoring/reporting;
- 8–15 case benchmark composition;
- empirical Ollama model-performance measurement;
- SQLite persistence or Alembic;
- production cache implementation;
- broad provider abstraction beyond the minimum shared contract;
- additional financial algorithms beyond Graham;
- autonomous planning changes;
- model fine-tuning;
- private chain-of-thought capture;
- cloud LLM evaluation;
- unrelated production refactoring.

#### 4.3.8 Acceptance criteria

- [ ] Graham is implemented as a second deterministic analytical strategy without making it Momentum-shaped.
- [ ] Momentum and Graham are invocable through the existing generic analysis/tool/orchestration path.
- [ ] No orchestrator special case is required merely because Graham differs from Momentum.
- [ ] No speculative generic strategy/plugin/registry framework has been introduced.
- [ ] `GrahamValueConfig`, `GrahamValueMetrics`, and `GrahamValueAnalyzer` are covered by deterministic tests.
- [ ] The Graham formula convention is explicitly documented.
- [ ] Invalid mathematical configuration values are rejected deterministically; arbitrary financial-domain limits are not introduced without rationale.
- [ ] `current_price` is present in the typed result and nullable.
- [ ] `margin_of_safety_percent` is nullable.
- [ ] Missing current-price data produces `None`, not numeric zero.
- [ ] A narrow typed market-data contract supports both historical data and current quote/price retrieval.
- [ ] Provider-specific response details do not leak across the intended abstraction boundary.
- [ ] A deterministic fixture-backed implementation satisfies the contract.
- [ ] Fixture execution requires no live external market-data calls.
- [ ] The fixture adapter can later be replaced by Step 3.1 production persistence without changing strategy APIs.
- [ ] Existing application behaviour is unchanged outside intended Step 2.3 additions.
- [ ] Ruff, formatting, `mypy --strict`, and pytest pass.
- [ ] Step 2.3 is reviewed and stable before Step 2.4 begins.

**Definition of done:** Step 2.3 is complete when Graham and Momentum coexist cleanly through the existing analysis architecture, the shared market-data contract is typed and fixture-testable, and the repository is ready for the separate Step 2.4 Golden Suite.

---

### 4.4 Step 2.4 – Golden-Test Suite & Strategy Evaluation

**Goal**  
Establish a deterministic, fixture-backed benchmark that exercises materially different analytical strategies and separates strategy/tool-selection correctness from deterministic numerical correctness.

Step 2.4 consumes the stable strategy and market-data foundations established in Step 2.3. It must not redesign those foundations unless implementation evidence reveals a concrete defect.

The initial benchmark targets:

1. **Momentum analysis** — the existing historical-price/SMA strategy.
2. **Benjamin Graham intrinsic-value analysis** — the new fundamentally different valuation strategy.

This is the empirical test of the architectural objective established in Step 2.3: financial analysis must not be implicitly synonymous with Momentum.

#### 4.4.1 Implementation guardrails for Cline

- Reuse the Step 2.3 strategy and market-data contracts; do not create parallel abstractions.
- Reuse existing production orchestration/tool-dispatch wherever it already supports deterministic fixture injection.
- Introduce only the minimum test seams necessary for fixtures and evaluation evidence.
- Deterministic/no-LLM tests validate fixtures, contracts, analytics, expected values, and evaluator mechanics; **they cannot validate LLM strategy selection**.
- Real-local-Ollama evaluation measures empirical strategy/tool-selection behaviour and must remain separate from deterministic regression tests.
- Do not optimize or weaken benchmark criteria to achieve the ≥90% target. The suite measures model/system performance; it is not a mechanism for making the model pass.
- The ≥90% aggregate target does **not** imply that strategy-selection accuracy itself must equal or exceed 90%. Report component metrics honestly.
- Do not refactor unrelated production code.
- Stop for review after the minimum heterogeneous suite works before expanding benchmark sophistication.

#### 4.4.2 Fixture design and determinism

Golden fixtures are deterministic, reviewable test evidence. They use the Step 2.3 fixture-backed market-data implementation and contain only the data required by their cases.

Fixture metadata should establish provenance and reproducibility, including where practical:

- fixture identifier;
- instrument/ticker;
- source/provider;
- source retrieval date;
- historical date range where applicable;
- currency;
- timezone/date convention where relevant;
- schema/version identifier;
- optional source/provider reference;
- transformations applied;
- checksum/content hash where useful.

The suite must never silently fetch missing fixture data from the network. Missing fixture data must fail explicitly.

Repeated execution with the same fixture set must produce the same deterministic analytical inputs and expected numerical results. The deterministic suite must not depend on current market prices, current dates, live APIs, network availability, provider ordering, local timezone, or mutable cache contents.

Where a reference date matters analytically, make it explicit in the case definition.

#### 4.4.3 Golden case schema

Represent each benchmark case with a typed case definition containing at minimum:

- unique case identifier;
- human-readable description;
- task/prompt supplied to the orchestrator;
- fixture identifier(s);
- expected analysis strategy/tool path;
- expected deterministic outputs;
- numerical tolerances;
- expected strategy/tool-selection constraints;
- pass/fail evaluation rules;
- optional tags.

Define required, permitted, and forbidden behaviour. Forbidden behaviour includes live network access, unrelated strategy/tool substitution, fabricated numerical inputs, bypassing the market-data abstraction, malformed tool arguments, and missing required analytical output.

#### 4.4.4 Initial benchmark composition

The eventual initial suite should contain approximately **8–15 high-signal cases**, but implementation must begin with a smaller minimum heterogeneous set before expansion.

Minimum set:

- straightforward Momentum case;
- Momentum boundary/edge case;
- straightforward Graham valuation case;
- Graham case with different growth/yield configuration;
- Graham missing-current-price case;
- at least one case where selecting Momentum instead of Graham produces a materially different analytical result.

After that minimum works, expand toward 8–15 cases with additional coverage such as:

- multiple deterministic tool calls;
- missing/insufficient fixture data;
- tool-argument sensitivity;
- malformed/unstructured-output regression;
- known or plausible failure modes.

Document why each case provides useful signal.

#### 4.4.5 Independently verified expected values

Expected numerical values are part of the benchmark contract and must be independently verified before being committed.

Prefer, in order:

1. simple transparent reference calculations;
2. a separate reference implementation;
3. manual verification for sufficiently simple cases.

Do not generate expected values by invoking the production function under test.

Use case-appropriate absolute/relative tolerances rather than one universal tolerance.

#### 4.4.6 Strategy/tool-selection evaluation

Evaluate strategy/tool-selection correctness separately from numerical correctness.

Use observable Step 2.1 trajectory evidence where useful. Verify the expected strategy/tool, valid arguments, case-corresponding arguments, relevant prohibited/unnecessary-tool constraints, and actual fixture-backed data use.

Selecting Momentum when Graham is required is a **strategy-selection failure**, even if the final prose appears plausible.

Selecting Graham correctly but obtaining an incorrect deterministic result is a **numerical/implementation failure**, not a strategy-selection failure.

Where multiple tool sequences are legitimately equivalent, define an acceptable set or predicate.

#### 4.4.7 Numerical and case-level evaluation

Compare deterministic analytics/tool outputs against independently verified expected values. LLM prose is not authoritative when structured deterministic output exists.

Report separately:

- strategy/tool-selection score;
- numerical-correctness score;
- overall case pass/fail.

A case fails overall when a required case-level criterion fails even if another component passes.

#### 4.4.8 End-to-end execution

Reuse the real production orchestration/tool-dispatch path as far as practical. Introduce only the minimum injection seams required for deterministic fixtures and evaluation evidence.

The runner should:

1. load a named case;
2. construct fixture-backed data access;
3. configure deterministic test execution;
4. execute the case;
5. capture Step 2.1 trajectory data;
6. extract structured strategy/tool and deterministic-result evidence;
7. evaluate the case;
8. emit a machine-readable result.

Support two explicitly separate modes:

- **deterministic/no-LLM mode** — fixture, contract, analytics, expected-value, evaluator, and report testing;
- **real-local-Ollama mode** — empirical model strategy/tool-selection evaluation.

#### 4.4.9 LLM nondeterminism

Real-model evaluation may use the configured local Ollama server. Document model identifier, Ollama configuration, sampling settings where applicable, repetitions, and treatment of nondeterministic outcomes.

Do not make model-generated behaviour a prerequisite for deterministic fixture/analytics tests.

#### 4.4.10 Telemetry integration

Every end-to-end Golden Suite execution should produce a Step 2.1 trajectory. Use telemetry as observable evidence of selected strategy/tools, arguments, results, errors/recovery, step boundaries, and run identity.

Do not depend on private model reasoning or `<think>` content. Telemetry is execution evidence, not the benchmark expectation.

#### 4.4.11 Machine-readable evaluation report

Emit a machine-readable report containing at minimum:

- suite identifier/version;
- execution timestamp;
- model/provider configuration when applicable;
- fixture-set version;
- total/passed/failed/skipped cases;
- overall pass rate;
- strategy/tool-selection score;
- numerical-correctness score;
- end-to-end case score;
- per-case result;
- failure category/reason;
- run/trajectory identifier where available.

The report must distinguish strategy-selection, deterministic numerical, fixture/data, and other execution failures.

#### 4.4.12 Pass-rate definition

```text
aggregate pass rate =
    cases satisfying all required case-level acceptance criteria
    ------------------------------------------------------------
    total executed benchmark cases
```

Report both case-level pass/fail and component-level metrics.

The ≥90% target is an evaluation target, not a reason to modify expectations, remove failing cases, or otherwise tune the instrument until the model passes.

#### 4.4.13 Evaluator regression/self-test

Include at least one evaluator self-test proving that an intentionally incorrect result is detected as a failure. Keep it separate from the normal benchmark denominator so CI remains green when the evaluator correctly detects the synthetic failure.

#### 4.4.14 Network isolation

Normal deterministic Golden Suite execution requires no external market-data access. The fixture-backed adapter fails closed when requested data is absent and never silently falls back to `yfinance` or another live provider.

#### 4.4.15 CLI / execution interface

Provide a documented command through the project's normal `uv run` workflow supporting:

- full suite;
- individual case;
- deterministic/no-LLM evaluation;
- optional real-local-Ollama evaluation;
- output report location.

Return a non-zero process exit status when required benchmark criteria fail. Real-model/network-dependent evaluation is not mandatory CI unless explicitly configured.

#### 4.4.16 Documentation

Update `docs/EVALUATIONS.md` to document Golden Suite purpose, architecture, fixture provenance, expected-value verification, tolerance policy, scoring, deterministic mode, real-Ollama mode, execution command, report format, failure interpretation, and case/fixture maintenance.

Update `docs/ARCHITECTURE.md` if Step 2.4 introduces any evaluation-specific seams not already documented in Step 2.3.

#### 4.4.17 Relationship to Step 3.1

Step 3.1 introduces SQLite-backed production persistence and market-data access. Step 2.4 must not couple Golden cases directly to SQLite, Alembic, provider-specific APIs, or production cache internals.

```text
Step 2.4 Golden Case
        │
        ▼
Shared Market-Data Contract
      │       │
      ▼       ▼
Fixture     SQLite
Adapter     Adapter
Step 2.3    Step 3.1
```

Golden case definitions should remain unchanged when the production adapter arrives.

#### 4.4.18 Implementation sequence

1. Inspect and accept the stable Step 2.3 strategy/data contracts; do not redesign them speculatively.
2. Define the typed Golden Case model.
3. Define independently verified expected values and tolerance rules.
4. Implement strategy/tool-selection evaluation.
5. Implement numerical evaluation.
6. Implement case-level aggregation and pass-rate calculation.
7. Implement machine-readable reporting.
8. Implement deterministic/no-LLM harness tests.
9. Add the evaluator regression/self-test.
10. Add the minimum heterogeneous case set.
11. Run the minimum deterministic suite and **stop for review**.
12. Expand toward 8–15 cases.
13. Add optional real-local-Ollama evaluation.
14. Add the documented CLI.
15. Update evaluation documentation.
16. Run Ruff, formatting checks, `mypy --strict`, and pytest.
17. Record deterministic and, when available, empirical model results separately.

#### 4.4.19 Non-goals

Step 2.4 does **not** include:

- SQLite persistence or Alembic;
- production cache implementation;
- new analytical strategies beyond Momentum and Graham;
- broad provider abstraction;
- UI/dashboard work;
- autonomous planning changes;
- model fine-tuning;
- private chain-of-thought capture;
- cloud LLM evaluation;
- unrelated production refactoring.

#### 4.4.20 Acceptance criteria

- [ ] A reproducible fixture-backed Golden Suite exercises both Momentum and Graham.
- [ ] No live market-data access is required for deterministic suite execution.
- [ ] Existing production orchestration/tool-dispatch is reused as far as practical.
- [ ] Expected numerical values are independently verified.
- [ ] Strategy/tool-selection correctness is evaluated separately from numerical correctness.
- [ ] Deterministic numerical evaluation does not depend on LLM prose.
- [ ] A minimum heterogeneous case set works before expansion toward 8–15 cases.
- [ ] Missing-current-price behaviour is covered by a Graham case.
- [ ] At least one case materially discriminates correct Graham selection from incorrect Momentum selection.
- [ ] Machine-readable reporting distinguishes component and overall failures.
- [ ] The ≥90% target is defined and reported without weakening criteria.
- [ ] Strategy-selection accuracy is reported independently and is not artificially forced to ≥90%.
- [ ] An evaluator self-test detects an intentionally incorrect result.
- [ ] Deterministic/no-LLM mode is documented.
- [ ] Optional real-local-Ollama evaluation is documented separately.
- [ ] CLI execution and non-zero failure status work.
- [ ] `docs/EVALUATIONS.md` is updated.
- [ ] Step 3.1 can replace the fixture-backed data source with production persistence without changing Golden case definitions.
- [ ] Ruff, formatting, `mypy --strict`, and pytest pass.
- [ ] Actual measured benchmark results are recorded honestly.

**Definition of done:** Step 2.4 is complete when the repository contains a reproducible fixture-backed benchmark that exercises materially different analytical strategies, distinguishes strategy-selection failures from deterministic numerical failures, produces an auditable machine-readable report, and remains decoupled from production persistence.

---

### 4.5 Step 2.5 – Circuit Breakers & Timeout Limits

**Goal**  
Hard execution caps, wall-clock bounds, and error thresholds that prevent unbounded loops or runaway token spend.

**Implementation outline**
1. Centralise limits in the existing Settings / config model (max steps, max transient retries, per-step and overall wall-clock timeouts, max consecutive schema violations, etc.).
2. Implement a small `CircuitBreaker` (or equivalent) that the orchestrator consults before each planning step and after each tool/LLM call.
3. On threshold breach: halt cleanly, emit a human-readable diagnostic that includes the `run_id` and last few trajectory events, and return a structured failure result to the CLI. Also emit RECOVERY_ATTEMPTED if not already done in 2.1.
4. Unit tests covering: normal completion, max-steps hit, timeout hit, repeated schema-violation trip.

**Acceptance criteria**
- [ ] Defaults are documented and match Master Plan intent (e.g. max steps ≈ 10, max retries ≈ 3).
- [ ] Breach always produces a clear diagnostic; never an unhandled exception.
- [ ] Limits are configurable without code changes.

---

### 4.6 Step 3.1 – SQLite DB & Migration Infrastructure

**Goal**  
Establish the production SQLite persistence foundation while implementing the SQLite telemetry sink and production market-data access behind the shared market-data contracts established in Step 2.3.

**Implementation outline**
1. Add Alembic and establish the migration environment using the existing application database configuration.
2. Create the initial production schema for market prices/OHLCV, instrument/source metadata, and trajectory telemetry storage.
3. Enforce SQLite WAL mode and appropriate busy-timeout/connection settings.
4. Implement `SQLiteTrajectorySink` against the exact `TrajectorySink` contract established in Step 2.1.
5. Implement production historical-series and current-quote retrieval against the shared market-data contracts consumed by the Golden Suite.
6. Place implementation under `src/data/repositories/`.
7. Ensure cache-first retrieval reuses previously fetched historical market data rather than repeatedly querying external providers.
8. Provide a documented migration command and fresh-database smoke test.
9. Verify that trajectories can be persisted and reconstructed identically through either JSONL or SQLite sinks.

**Acceptance criteria**
- [ ] `alembic upgrade head` succeeds on a clean environment.
- [ ] WAL mode is verified.
- [ ] Schema is migration-controlled.
- [ ] `SQLiteTrajectorySink` conforms to the Step 2.1 sink contract.
- [ ] A representative trajectory can be written to and reconstructed from SQLite.
- [ ] Production market-data implementation satisfies the shared historical-data and current-quote contracts consumed by the Golden Suite.
- [ ] Previously fetched historical data can be reused without an unnecessary external refetch.

---

### 4.7 Step 3.2 – DAO & Repository Layer

**Goal**  
Strongly-typed Python data-access objects for cache inspection, audit logging, and later analytics.

**Implementation outline**
1. Define narrow repository interfaces (e.g. `PriceRepository`, `TrajectoryRepository`, `MetadataRepository`).
2. Implement SQLite-backed concrete classes that accept/return Pydantic models only under `src/data/repositories/`.
3. Keep all SQL inside the repository layer; no raw SQL in the orchestrator or tools.
4. Unit tests with an in-memory or temporary-file SQLite DB.

**Acceptance criteria**
- [ ] Public repository methods are fully typed and mypy-clean.
- [ ] Round-trip tests pass for core entities.
- [ ] Connection management is consistent with WAL / single-writer guidance.

---

### 4.8 Step 3.3 – Data Quality & Cache Invalidation Pipeline

**Goal**  
Validate incoming financial data (FX adjustments, corporate actions, staleness) and invalidate or refresh cache entries when quality rules fail.

**Implementation outline**
1. Define core quality rules: price series continuity/missing-bar detection, currency consistency (CAD vs USD), and maximum age of cached bars before forced refresh.
2. Run rules on every fetch path before writing to the cache.
3. On failure: reject the write, mark the entry stale, or trigger a controlled re-fetch (with circuit-breaker awareness).
4. Log quality decisions into the execution trajectory for auditability.
5. Unit tests with synthetic valid and invalid data series.

**Acceptance criteria**
- [ ] Documented quality rules with clear pass/fail behaviour.
- [ ] Stale or invalid data cannot silently become the source of truth for downstream analytics.
- [ ] Quality failures appear transparently in the trajectory log.

---

### 4.9 Step 3.5 – Light Mode Support

**Goal**  
The full single-step analysis path (data fetch → deterministic analytics → basic synthesis/report) runs cleanly under Light Mode configuration with a 14B-class (or smaller) model.

**Implementation outline**
1. Make Light Mode the configuration default (model tag, single-tier behaviour).
2. Ensure README and `docs/HARDWARE.md` give a new user a complete, copy-pasteable path to a first successful analysis under Light Mode.
3. Add a minimal smoke-test expected to pass under Light Mode resource constraints.
4. Confirm dual-tier code paths remain available as opt-in features.
5. Verify trajectory logging, schema enforcement, and circuit breakers function cleanly under the Light Mode model.

**Acceptance criteria (exit criterion for Step 3.5)**
- [ ] A user following only Light Mode instructions can complete an end-to-end analysis.
- [ ] Configuration defaults favour Light Mode.
- [ ] Basic smoke tests pass under Light Mode constraints.
- [ ] Documentation is consistent across README, `HARDWARE.md`, Master Plan, and Discovery Workbook.

---

## 5. Suggested Sequencing & Parallelism

```text
Phase A — Step 2.1 foundation
  ├─ 2.1 telemetry model & event types
  ├─ 2.1 sink abstraction + JSONL sink
  └─ 2.1 runtime instrumentation

Phase B — Structured-output foundation
  └─ 2.2 native schema enforcement

Phase C — Strategy/data foundation
  ├─ 2.3 Graham strategy + deterministic tests
  ├─ 2.3 historical/current-quote data contract
  └─ 2.3 minimal fixture adapter
        │
        ▼
     review gate
        │
        ▼
Phase D — Golden Suite
  ├─ 2.4 heterogeneous benchmark cases
  ├─ 2.4 strategy-selection evaluation
  └─ 2.4 numerical evaluation/reporting
        │
        ▼
     ≥90% target measured honestly

Phase E — Reliability limits
  └─ 2.5 circuit breakers & timeout limits

Phase F — Production persistence
  ├─ 3.1 Alembic + SQLite schema
  ├─ 3.1 SQLite telemetry sink
  └─ 3.1 production market-data/cache implementation
        │
        ▼
   3.2 repositories
        │
        ▼
   3.3 data quality / cache invalidation

Phase G — Adoption gate
  └─ 3.5 Light Mode defaults, docs, smoke tests
       → unlocks Milestone v0.2.5 real-user validation
```

---

## 6. Quality Gates

The following quality checks must pass on every pull request within this milestone:

* `ruff check . && ruff format --check .`
* `mypy --strict src/`
* `pytest` (unit and integration) with monitored coverage trends
* Zero untyped public interfaces
* Zero secret or API key leaks in trajectory outputs
* Verified Light Mode path functionality once Step 3.5 lands

---

## 7. Exit Criteria for Milestone v0.2

All of the following must be true before declaring the milestone complete and opening the v0.2.5 validation window:

1. Steps 2.1–2.5, 3.1–3.3, and 3.5 are fully implemented and merged.
2. Step 2.4 Golden-test suite exists, runs headlessly, exercises both Momentum and Graham, and reports strategy-selection, numerical-correctness, and overall pass rates against the ≥ 90 % target.
3. A fresh repository clone running Light Mode setup instructions completes an end-to-end analysis successfully.
4. CI pipeline is green on `main`.
5. Master Plan and Discovery Workbook cross-references remain consistent.
6. Temporary scaffolding and blocking TODOs are cleaned up or documented.

---

## 8. Decisions & Deferred Questions

### Resolved before implementation
1. **Trajectory storage sequencing** — JSONL first in Step 2.1; SQLite sink in Step 3.1 behind the same sink abstraction.
2. **Golden Suite market-data determinism** — Step 2.3 establishes the shared historical-series/current-quote contract and deterministic fixture adapter; Step 2.4 consumes that foundation for the Golden Suite; Step 3.1 supplies production SQLite/cache-backed access.
3. **Telemetry retention** — Configurable via `ProjectSettings`, adhering to existing `logger_util.py` options.
4. **Branch granularity** — Fine-grained branches mapped to coherent implementation units.
5. **Telemetry boundaries** — Telemetry captures observable provider output; missing metrics are stored explicitly as `None` rather than estimated.
6. **Heterogeneous strategy validation** — Momentum and Benjamin Graham are established in Step 2.3 as the initial materially different analytical strategies; Step 2.4 evaluates whether the runtime/model selects and executes them appropriately.
7. **Current quote abstraction** — Current market-price retrieval is a first-class capability of the market-data abstraction rather than an implicit one-day historical-data workaround.
8. **Graham result semantics** — An unavailable current price produces an unavailable (`None`) margin of safety rather than a numeric zero. Positive margin of safety means the current price is below estimated intrinsic value; negative margin means the current price exceeds estimated intrinsic value.
9. **Strategy-specific determinism** — Each analytical strategy owns its deterministic mathematical implementation and typed configuration/result models. The LLM selects and orchestrates strategies but does not perform the underlying financial calculations.
10. **Step 2.2 enforcement fallback** — Native schema enforcement is preferred when capability is confirmed; prompt-based schema instructions with Pydantic validation/retry provide the configured fallback when native capability is unavailable or unknown; legacy parsing remains the final compatibility fallback.

### Explicitly deferred
1. **Ollama schema/model support matrix** — Empirical validation remains outstanding for the actual Light Mode model configuration. Record the tested Ollama version, model identifier, schema-constrained request, observed response behaviour, and pass/fail result when completed. This is non-blocking for the Step 2.2 implementation/merge.

---

## 9. Next Immediate Actions

Before implementation resumes, remove temporary exploratory implementation changes from the local worktree so that the working baseline contains only the committed Step 2.2 state plus intentionally retained milestone-plan/documentation edits. The Graham implementation should then be introduced as a deliberate Step 2.3 change rather than carried forward as unreviewed exploratory work.

1. Preserve the committed Step 2.2 implementation and approved planning/documentation changes as the clean baseline.
2. Record the outstanding empirical Light Mode model/schema compatibility validation as a non-blocking follow-up.
3. Add the proposed Graham implementation to the local repo as the Step 2.3 starting point.
4. Have Cline complete Step 2.3 only: refine Graham, establish the current-quote/historical-data contract, add the minimal fixture adapter, and pass quality gates.
5. **Stop and review Step 2.3 before allowing Cline to begin Step 2.4.**
6. Have Cline implement Step 2.4 Golden Suite from the now-stable Step 2.3 contracts, beginning with the minimum heterogeneous case set.
7. Review the minimum Golden Suite before expansion toward 8–15 cases and optional real-Ollama evaluation.
8. Complete the empirical Light Mode schema/model compatibility validation before the Step 3.5 exit criterion.


---
