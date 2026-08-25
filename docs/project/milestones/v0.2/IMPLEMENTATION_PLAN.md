# Milestone v0.2 Implementation Plan
## Reliability, Observability, Data Persistence, Investor Workflow & Strategy-General Evaluation

**Project:** Financial Data Agents<br/>
**Repository:** [https://github.com/PeterPontbriand/financial-data-agents](https://github.com/PeterPontbriand/financial-data-agents)<br/>
**Source of truth:** Current `docs/project/MASTER_PLAN.md` (Milestone v0.2 section)<br/>
**Companion rationale:** Current `docs/project/DISCOVERY_WORKBOOK.md`<br/>
**Prepared:** 2026-08-15<br/>
**Revised:** 2026-08-25 — Recorded Step 2.3 completion; inserted Step 2.4 Free Cash Flow & Earnings Growth ahead of evaluation; renumbered the Golden Suite to Step 2.5 and reliability limits to Step 2.6; synchronized downstream sequencing and acceptance criteria.<br/>
**Status:** Step 2.2 → Implementation complete; Step 2.3 → complete and approved; Step 2.4 → design drafted / implementation not started; Step 2.5 → Golden Suite not started
↳ Follow-up validation: empirically verify native schema support for the actual Light Mode model configuration.

---

## 1. Purpose & Scope

This plan turns the high-level Master Plan steps for Milestone v0.2 into an actionable, sequenced work package that the development team can organize around **before** writing production code.

**In scope**
- Step 2 – Agent Reliability, Strategy Generalization, Evaluation & Observability Foundation (2.1 → 2.6)
- Step 3 – Relational Data Persistence, Data Quality & Local Research Workspace (3.1 → 3.4)
- Step 3.5 – Light Mode Support (required before the v0.2.5 checkpoint)

**Out of scope (explicit)**
- Milestone v0.2.5 real-user validation activities (recruitment, feedback sessions)
- Milestone v0.3 analytics expansion or localization
- Unattended scheduling, proactive monitoring/notifications, autonomous multi-step research, and executive reporting (Milestone v1.0)
- Graphical UI/dashboard and full-screen TUI work. Rich terminal presentation, CLI workspace commands, and persistent run browsing are in scope where required for v0.2.5 validation.

**Success definition for the milestone**<br/>
A clean, Light-Mode-capable analysis workflow exists that:
1. Logs full trajectories (prompts, tool calls, latency, tokens).
2. Enforces native Ollama JSON schema constraints + Pydantic validation.
3. Passes a golden-test suite at the ≥ 90 % target.
4. Has hard circuit-breaker and timeout limits.
5. Persists data, execution logs, and later investor-facing Analysis Run history in SQLite (WAL) with typed repositories and basic data-quality checks.
6. Presents Momentum, Graham, and Free Cash Flow & Earnings Growth analysis through a coherent terminal experience with concise defaults, detailed provenance, explicit overrides/warnings or assumptions, resolution diagnostics, and machine-readable output.
7. Can be used end-to-end by a new user following only Light Mode instructions to analyze or add a ticker, refresh supported analyses, revisit completed runs, and inspect the evidence behind a result.

---

## 2. Guiding Constraints

The following core principles govern all technical decisions across Milestone v0.2.

| Constraint | Description & Architectural Principle | Primary Impacted Packages |
| :--- | :--- | :--- |
| **Python Determinism** | Deterministic math stays in Python; LLM is used only for planning, tool selection, and narrative synthesis. | Step 2.2, Step 2.3, Step 2.4, Step 2.5 |
| **Typed Tool Interfaces** | All tool arguments and return structures must be strictly defined via Pydantic models. | Step 2.1, Step 2.2, Step 2.3, Step 2.4, Step 3.2 |
| **Native Schema Formatting** | Native Ollama `format=Schema` (or provider equivalent) is preferred over post-hoc string/regex parsing. | Step 2.2 |
| **Light-Mode Default** | Light Mode is the recommended adoption and execution mode; Full Dual-Tier remains optional. | Step 3.5 |
| **Strict Quality Gates** | Strict typing (`mypy --strict`), Ruff, and pytest coverage are non-negotiable CI gates. | All Work Packages |
| **Guarded Egress** | Outbound network access is strictly guarded (cache-first, rate-limited, domain-whitelisted). | Step 2.3, Step 2.4, Step 3.1, Step 3.3 |
| **Classified Diagnostics** | Failures are categorized (transient vs. non-recoverable) and surface structured diagnostics. | Step 2.1, Step 2.6 |
| **Decoupled Contracts** | Decoupled, swappable implementations behind narrow interfaces are preferred over direct library dependencies. | Step 2.1, Step 2.3, Step 2.4, Step 3.1 |
| **Heterogeneous Strategy Independence** | Financial-analysis strategies must be independently selectable, deterministic, typed, and swappable. The runtime and data layer must not assume that all financial analysis follows a single analytical pattern. | Step 2.3, Step 2.4, Step 2.5, Step 3.1, Step 4 |
| **Method-Explicit Financial Semantics** | Every financial result identifies the exact method, input convention, output meaning, assumptions, and applicability; related formulas are never silently conflated. | Step 2.3, Step 2.4 |
| **Traceable, Time-Bounded Inputs** | Resolved values retain provenance, reporting/observation and availability dates, retrieval time, transformations, override/cache state, and the requested analysis `as_of`. | Step 2.3, Step 2.4, Step 3.1, Step 3.3 |
| **Progressive Investor Disclosure** | Default terminal output is concise and financial; provenance, derivations, resolution diagnostics, and JSON are explicit deeper views. Operational logs are not the presentation surface. | Step 2.3, Step 2.4, Step 3.4, Step 3.5 |
| **Analysis Run as Canonical Product Record** | Persist the requested analysis/configuration, typed result, provenance, warnings, and timestamps; render reports/views from that record rather than generating a competing canonical artifact. | Step 3.4, Step 7 |
| **Bounded Agentic Workflow** | v0.2 may concurrently execute user-requested work and synthesize completed typed results; unattended scheduling/proactive monitoring remains v1.0 work. | Step 3.4, Step 3.5, Step 6 |

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
| Step 2.3 Graham/data foundation | `feat/step-2.3-graham-data-contracts` | Adds two explicit Graham methods plus method-aware input resolution and shared data contracts |
| Step 2.4 FCF/earnings-growth strategy | `feat/step-2.4-fcf-earnings-growth` | Adds the third deterministic strategy and minimally extends financial-fact resolution |
| Step 2.5 Golden runner | `feat/step-2.5-golden-suite` | Implements heterogeneous benchmark cases and evaluation harness after the v0.2 strategy set is stable |
| Step 2.6 reliability limits | `feat/step-2.6-circuit-breakers` | Isolates hard execution limits |
| Step 3.1 persistence foundation | `feat/step-3.1-sqlite-foundation` | Alembic, schema, SQLite telemetry sink, production data access |
| Step 3.2 repositories | `feat/step-3.2-repositories` | Typed DAO/repository layer |
| Step 3.3 data quality | `feat/step-3.3-data-quality` | Validation, staleness, invalidation |
| Step 3.4 research workspace | `feat/step-3.4-research-workspace` | Watchlists, user-initiated concurrent refresh, durable Analysis Runs, run browsing |
| Step 3.5 Light Mode | `feat/step-3.5-light-mode` | Adoption workflow and smoke validation |

**Working agreement**
- Prefer small, reviewable PRs that each leave `main` green.
- Every PR must pass the CI quality gates.
- Branch names should identify the Master Plan step they implement.
- Temporary scaffolding must be documented and have an explicit removal point.
- Documentation-only changes may use `docs/...` branches where that is clearer.
- A reviewed intermediate checkpoint may be committed and pushed after the human explicitly approves it and the agreed quality gates are green. Such a checkpoint does not declare the owning step complete and does not authorize beginning a later Master Plan step.
- Cline must never commit automatically; every commit/push remains an explicit human action or authorization.

---

## 4. Detailed Work Packages

### 4.1 Step 2.1 – Trajectory Logging & Telemetry

**Goal**<br/>
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

**Sequencing decision**<br/>
Step 2.1 defines a narrow `TrajectorySink` abstraction and implements JSONL first. Step 3.1 later adds a SQLite sink satisfying the same abstraction. The orchestrator and telemetry recorder remain decoupled from the specific underlying storage choice.

**Telemetry semantics & Concrete Event Types**<br/>
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
* `RECOVERY_ATTEMPT`: Triggered when a transient failure initiates a retry or fallback flow.

Every telemetry event envelope captures standard metadata fields including `event_id`, `trajectory_id`, `sequence`, `timestamp`, `event_type`, `component`, `schema_version`, latency, parent/correlation identifiers, and payload metadata according to configurable retention rules.

**Observability & Data Boundaries**<br/>
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
11. Update `docs/project/ARCHITECTURE.md` with sink contracts and logging boundaries.

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
  repair/retry flow runs, record a `RECOVERY_ATTEMPTED` event on each attempt
  (component, step_index, span linkage, sanitized error context). If recovery
  is still minimal, wire this when Step 2.6 circuit-breakers / repair policy
  lands.
- **Always set `payload_hash` when a payload is retained:** Confirm
  `TrajectoryRecorder` sets `payload_hash` for every event that keeps a
  non-null payload (integrity without storing full bodies). Leave hash null
  only when payload is omitted.
<br/>
---

### 4.2 Step 2.2 – Native Schema Enforcement

**Goal**<br/>
Prevent unstructured / drifting LLM output by using Ollama's native JSON-schema constraint (`format=Schema` or equivalent) wherever the model is expected to emit structured tool calls or final synthesis objects.

**Implementation outline**
1. Inventory every place the orchestrator currently asks the model for structured output.
2. Convert existing Pydantic tool / response models into the JSON Schema form expected by the Ollama client.
3. Pass the schema on every constrained generation call.
4. Keep a Pydantic validation step as a second line of defense; treat schema violation as a recoverable error that can feed the circuit-breaker / retry flow.
5. Add focused unit/integration tests that mock an Ollama response and assert both successful constrained generation and graceful handling of schema violations.

**Acceptance criteria**
- [x] All tool-call extraction flows use native schema constraints when the underlying Ollama version supports them.
- [x] Schema violations are classified as transient and do not crash the process.
- [ ] Golden-test or smoke tests demonstrate reduced output-drift failures compared with the pre-constraint baseline.

> **Status:** Implementation complete and ready for PR/merge. The remaining unchecked item is deferred to Step 2.5/3.5 validation because it requires empirical evaluation rather than further Step 2.2 implementation.

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
<br/>
---

### 4.3 Step 2.3 – Graham Methods, Input Resolution & Data Contracts

**Status:** Complete and approved on 2026-08-25. Detailed historical implementation status is retained in `STEP_2_3_GRAHAM_SLICE_PLAN.md`.

**Goal**<br/>
Add Benjamin Graham analysis as the second materially different deterministic strategy family and establish the minimum input-resolution and market-data contracts required to support Momentum and Graham without introducing speculative architecture.

Step 2.3 is an **architectural foundation step**, not the Golden Suite itself. Its purpose is to make heterogeneous deterministic strategies and their data requirements work cleanly through the existing analysis/tool/orchestration architecture.

The initial strategy set entering Step 2.3 was:

1. **Momentum analysis** — the existing historical-price/SMA strategy.
2. **Benjamin Graham analysis** — a fundamentally different valuation family with two explicitly identified methods:
   - `graham_number` — the default, a conservative price ceiling derived from Graham's combined P/E and P/B defensive-investor limits;
   - `graham_growth_value` — the forecast-dependent growth-stock formula, retained as a separate secondary method.

Step 2.4 adds Free Cash Flow & Earnings Growth on these same strategy/data foundations. The subsequent Step 2.5 Golden Suite will benchmark Momentum, both Graham methods, and the Step 2.4 cash-flow/growth strategy. Step 2.3 remains stable; later work may extend its provider-neutral contracts only where concrete new data requirements prove that extension necessary.

#### 4.3.1 Strategy boundary

Each analytical strategy owns:

- its Pydantic configuration model;
- its deterministic mathematical implementation;
- its typed result/metrics model;
- only the data capabilities it actually requires.

Both strategy families and both Graham methods must be invocable through the **existing** analysis/tool/orchestration mechanisms without adding strategy-specific branches to the orchestrator. Reuse `BaseAnalyzer`, existing tool registration/dispatch, and existing dependency-injection patterns wherever they are sufficient.

Do **not** introduce a new generic `Strategy`, plugin, registry, factory hierarchy, or parallel orchestration framework merely because Momentum and Graham differ. A small Graham-specific method discriminator, typed input resolver, or discriminated union is acceptable where it prevents ambiguous optional fields. Introduce a broader abstraction only if inspection proves that the existing architecture cannot express the required boundary cleanly.

The fact that Graham and Momentum have different inputs and outputs is intentional:

```text
                         Analysis Runtime
                                │
                     existing generic runtime flow
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
        Momentum analysis                Graham analysis
                 │                             │
       historical prices             resolved typed inputs
                 │                      ┌──────┴─────┐
             SMA/trend                  ▼            ▼
                                 Graham Number   Growth value
                                        │            │
                                        └─────┬──────┘
                                              ▼
                                     typed method result
```

Do not make Graham "Momentum-shaped" merely for implementation consistency.

#### 4.3.2 Graham method definitions and output semantics

The approved implementation contains both Graham methods, provenance/cache/resolution contracts, deterministic fixtures, verified production adapters, the E3 SEC-backed BVPS derivation, and the F1/F2 investor-facing CLI/presentation work. The semantics below remain authoritative for Step 2.3 behavior.

##### Method A — `graham_number` (default)

```text
maximum_indicated_price = sqrt(22.5 × EPS × BVPS)
```

The factor `22.5` is the product of a maximum P/E ratio of `15` and maximum P/B ratio of `1.5`. This method is a conservative screening ceiling derived from two of Graham's defensive-investor criteria. It is **not** a complete test of all defensive-investor criteria and must not be described as a comprehensive intrinsic-value determination.

Required conventions:

- default `eps_basis` is `three_year_average`, calculated transparently from three completed fiscal-year EPS observations;
- `ttm` is a supported modern alternative only when explicitly selected and labeled;
- the output records the selected EPS basis and every reporting period used;
- BVPS uses the latest available common-shareholders' equity and period-end common shares outstanding, or a provider-reported equivalent whose definition is recorded;
- tangible book value must not be silently substituted for ordinary book value;
- EPS and BVPS must be aligned for splits and the applicable common share class;
- non-positive EPS or BVPS makes the method `not_applicable`; it must not produce a complex number, zero valuation, or fabricated fallback;
- the primary output is named and described as `maximum_indicated_price` or `screening_value`, not unqualified `intrinsic_value`.

##### Method B — `graham_growth_value` (secondary)

```text
growth_value = normalized_eps
    × (base_pe + growth_multiplier × g)
    × baseline_aaa_yield / current_aaa_yield
```

The configurable constants preserve `base_pe = 8.5`, `growth_multiplier = 2.0`, and `baseline_aaa_yield = 4.4`. `g`, `baseline_aaa_yield`, and `current_aaa_yield` are expressed in percentage points; for example, `6.5` means 6.5%.

This method is described as a forecast-dependent, simplified growth-stock estimate. It must not be represented as equivalent to the Graham Number or as a precise, generally applicable intrinsic value. Its output is named `growth_value` or `growth_formula_estimate`.

##### Shared result semantics

Each result includes:

- a stable method identifier and calculation-version identifier;
- an applicability status such as `applicable`, `not_applicable`, or `input_unavailable` with structured reason codes;
- the method-specific reference value (`maximum_indicated_price` or `growth_value`);
- `current_price: float | None`;
- `margin_of_safety_percent: float | None` calculated against the selected method's reference value;
- all resolved inputs with provenance and timestamps;
- warnings identifying material assumptions, mixed reporting dates, stale data, and method limitations.

The project retains the existing margin-of-safety convention:

```text
(reference_value - current_price) / reference_value × 100
```

Positive means the current price is below the method's reference value; negative means it is above it. This percentage is a valuation discount/premium calculation and must not imply that business or investment risk has been eliminated. If the reference value or current price is unavailable, margin of safety is `None`, never numeric zero.

#### 4.3.3 Method-aware input-resolution layer

Step 2.3 added a typed input-resolution layer between CLI/tool requests and deterministic calculation. The calculator receives resolved values; it does not know how to call providers, inspect caches, or interpret CLI precedence.

Resolution occurs **field by field** in this order:

1. explicit user/CLI override;
2. valid cache entry satisfying the requested `as_of` and freshness policy;
3. configured provider retrieval;
4. explicit `input_unavailable` result or typed error when no permitted source can supply the field.

There is no silent numeric default, cross-method substitution, or live-network fallback from deterministic fixture mode.

Every resolved field preserves at least:

- canonical field name and value;
- units and currency where applicable;
- source kind (`override`, `cache`, `provider`, `fixture`, or `derived`);
- provider and provider field/series identifier when applicable;
- source observation/reporting period;
- `as_of` timestamp/date describing the observation or reporting boundary;
- publication, filing, or `available_at` timestamp where the source supplies one;
- `retrieved_at` timestamp describing when the application obtained it;
- transformation details, including averaging, share adjustment, or unit conversion;
- cache freshness/staleness state;
- override flag and, where useful, the value/source it superseded.

The resolver accepts an optional requested analysis `as_of`. It may use only information actually available on or before that boundary. For company financial facts, a fiscal period end alone does not prove the value was known then; use a filing/publication/availability timestamp when available to prevent look-ahead bias. A current quote means the latest permitted market observation at or before `as_of`, not necessarily the wall-clock price at execution time. If no analysis `as_of` is supplied, the execution time becomes the boundary and is recorded.

Input timestamps are allowed to differ naturally—for example, a quote may be newer than the latest financial statement—but the difference must be visible. Materially inconsistent or stale inputs produce structured warnings or unavailability according to documented policy; they must not be silently blended.

Step 2.3 defines the resolver and a narrow cache-access seam plus deterministic cache-hit/miss/stale fixtures. Step 3.1 remains responsible for the durable SQLite cache implementation, and Step 3.3 remains responsible for broader production data-quality and invalidation policy.

#### 4.3.4 EPS, BVPS, and growth-estimation policy

##### EPS policy

The project distinguishes these earnings bases rather than exposing one ambiguous `eps` value:

- `three_year_average` — arithmetic mean of three completed fiscal-year per-share earnings observations; default for `graham_number`;
- `ttm` — trailing-twelve-month EPS; supported as an explicitly labeled modern variation;
- `normalized` — an explicitly documented transformation used by `graham_growth_value`, if the implementation adjusts reported earnings.

The calculation records whether EPS is basic or diluted, the fiscal periods used, and any split adjustment. It does not average provider values whose bases or share classes are incompatible.

##### BVPS policy

BVPS means book value attributable to common shareholders divided by period-end common shares outstanding. Prefer a transparent derivation from provider-neutral financial facts when reliable. If a provider-reported BVPS field is used, preserve its definition and provenance. Tangible BVPS is a separate metric and may be supported only as an explicitly selected future variation.

##### Growth policy

`graham_growth_value` never invents, silently defaults, or asks an LLM to improvise `g`. The implemented production policy is `explicit_override`: the user supplies the expected annual growth rate. A future deterministic historical proxy or provider/analyst estimate policy requires separately approved semantics and provenance.

Do not clip, cap, or floor growth without a documented policy, rationale, and tests. Growth is expressed in percentage points in the formula and its intended horizon must be displayed.

No production AAA-yield series is approved in Step 2.3. The historical `4.4` baseline is a configurable formula constant, not a current market observation. Both yields must be strictly positive for the growth method.

#### 4.3.5 Typed request, configuration, CLI, and presentation contract

The direct Graham CLI is method-explicit:

```text
financial-agents graham TICKER [--method number|growth] [options]
```

Requirements:

- omitted `--method` selects `number` and reports that choice prominently;
- ticker-only Graham Number execution resolves EPS, BVPS, and current price through overrides/cache/provider policy for representative supported production securities;
- `--eps`, `--bvps`, and `--current-price`/quote remain field-level overrides and are visibly marked as overrides;
- `--eps-basis three_year_average|ttm` controls the Graham Number earnings convention;
- growth-specific options are accepted only for `--method growth`;
- the growth method requires an explicit expected-growth assumption and explicit AAA-yield input under the Step 2.3 production policy;
- `--as-of` provides a reproducible temporal boundary; and
- incompatible options fail with a clear usage error rather than being ignored.

Investor-facing presentation uses progressive disclosure:

1. **Default concise view** — ticker, method/analysis, `as_of`, status, headline metrics, plain-language comparison, high-level source/freshness summary, material warnings, and a short method limitation.
2. **`--details`** — financial audit trail: resolved inputs, bases, periods/observation dates, provider/source identity, availability dates, derivations/component lineage, and visible assumptions.
3. **`--diagnostics`** — software resolution trace: override supplied/not supplied, cache hit/miss/staleness, provider attempted, and classified failure/unavailability. A cache hit continues to identify the original financial source rather than pretending “cache” is the economic data source.
4. **`--json`** — stable machine-readable result/provenance output suitable for later persistence and tooling.

User overrides are conspicuous in the default view when material to interpretation, especially expected growth. Unqualified `Intrinsic Value` wording is prohibited for the Graham Number. Operational logger output is not the primary investor-facing renderer.

Momentum and Graham use the same visual grammar without forcing their internal result models into one generic shape. Strategy-specific presenters or equivalent narrow presentation adapters are preferred to a giant generic `AnalysisResult`.

The general `financial-agents analyze TICKER` research-assistant entry point is not required by Step 2.3; it is validated as part of the later Light Mode workflow in Step 3.5.

#### 4.3.6 Market-data contract

Step 2.3 defined the **minimum** typed market/financial-data contracts required by Momentum and the two Graham methods.

The contracts distinguish at least:

- **historical market data** — required by Momentum;
- **current market quote/price** — required for margin-of-safety comparison;
- **company financial facts** — annual/TTM EPS, common shareholders' equity, and period-end common shares or a clearly defined BVPS equivalent;
- **macro/benchmark series** — a provider-neutral observation capability, without implying that a production AAA series was approved;
- **cache access** — a narrow provider-neutral lookup/write seam that Step 3.1 can implement durably.

`BaseDataClient` remains historical-price focused. Materially different company-fundamental and macro capabilities use narrow typed protocols/models rather than being forced into a historical-price-shaped method.

The contracts:

- are fully typed;
- avoid exposing provider-specific response types to consumers where a provider-neutral boundary is appropriate;
- make missing data explicit;
- support deterministic fixture execution without network access;
- are narrow enough that Step 3.1 can later supply a SQLite/cache-backed implementation;
- preserve provider field definitions, units, currencies, reporting periods, and timestamps;
- support split/share-class alignment of per-share inputs;
- distinguish provider observations from derived values;
- avoid speculative operations not required by the strategies.

Step 2.4 may minimally extend this boundary for operating cash flow and capital expenditures if reconnaissance proves the existing surface needs extension; it must not create a parallel fact/provenance architecture merely because the new strategy is not Graham.

#### 4.3.7 Fixture adapter for contract and resolution validation

Step 2.3 includes the **minimal fixture-backed adapter/data needed to prove the shared market-data contract**. It is foundation for Step 2.4 strategy extension and Step 2.5 Golden evaluation; it is not itself the Golden Suite.

The fixture system:

- satisfies the same typed market-data contract as provider-backed clients;
- supports historical data required by Momentum;
- supports quote, EPS history/TTM EPS, BVPS components, and AAA-yield observations required by the Graham methods;
- exercises override, valid-cache, stale-cache, cache-miss, provider, derived-value, and unavailable-input branches deterministically;
- preserves realistic source, reporting-period, `as_of`, and `retrieved_at` metadata;
- fails explicitly when requested data is absent;
- performs no live network fallback;
- remains deterministic across repeated runs.

Golden Case schemas, scoring, reports, and benchmark composition belong to Step 2.5.

#### 4.3.8 Required deterministic tests

Step 2.3 tests cover:

- exact/reference Graham Number calculation;
- derivation using both `three_year_average` and explicitly selected `ttm` EPS;
- exact/reference growth-formula calculation;
- method-specific configuration and rejection of incompatible CLI options;
- non-positive EPS/BVPS → `not_applicable` for the Graham Number;
- invalid/non-positive yield or mathematically invalid growth configuration;
- field-level precedence: override → valid cache → provider → unavailable;
- provenance and timestamp preservation for every resolution branch;
- requested `as_of` boundaries, filing/publication availability where applicable, and no use of information that was not yet available;
- cache hit, miss, and stale-entry behavior;
- explicit supplied and resolved current price;
- unavailable current price → `current_price is None` and `margin_of_safety_percent is None`;
- positive and negative margin-of-safety semantics;
- fixture mode performing no live network calls;
- CLI defaulting to the Graham Number while reporting the selected method.

#### 4.3.9 Documentation requirements

Step 2.3 documentation was synchronized with implementation across:

- `docs/user/FINANCE_MATH.md`;
- `docs/project/ARCHITECTURE.md`;
- `docs/user/GLOSSARY.md`;
- README and CLI examples;
- configuration documentation and code docstrings;
- `STEP_2_3_GRAHAM_DESIGN.md`; and
- `STEP_2_3_GRAHAM_SLICE_PLAN.md`.

Documentation does not claim that the Graham Number is a complete intrinsic-value calculation or that either Graham method is sufficient by itself for an investment decision.

#### 4.3.10 Implementation guardrails for later reuse

- Prefer existing abstractions (`BaseAnalyzer`, `BaseDataClient`, current tool registration/dispatch, telemetry, financial-fact/provenance seams) over parallel frameworks.
- Do not create a strategy/plugin registry unless a concrete later-step incompatibility proves it is required.
- Do not refactor unrelated production code.
- Treat the approved Step 2.3 implementation as a stable foundation; do not reopen it without a concrete incompatibility or review finding.
- Keep deterministic calculations separate from provider/cache/input-resolution I/O.
- Use strategy/method-specific typed models; do not create ambiguous bags of optional inputs.
- Do not weaken `as_of`, provenance, subject-validation, or investor-presentation semantics when extending the financial-fact surface.
- Coding agents never commit automatically.

#### 4.3.11 Implementation sequence

Step 2.3 was implemented and reviewed in bounded slices. The authoritative historical handoff is `STEP_2_3_GRAHAM_SLICE_PLAN.md`.

1. **A — reconnaissance**
2. **B — pure methods/results**
3. **C1/C2 — provenance/cache/provider-neutral resolution**
4. **D — deterministic valuation fixtures**
5. **E1 — provider evidence**
6. **E2 — verified production adapters**
7. **Checkpoint — human-approved provider/resolver durability boundary**
8. **E3 — user-viable standard Graham data configuration**
9. **F1 — investor-facing result presentation**
10. **F2 — unified direct-analysis CLI**
11. **G — documentation/final gate and explicit human approval**

#### 4.3.12 Non-goals

Step 2.3 does **not** include:

- Free Cash Flow & Earnings Growth strategy implementation;
- Golden Suite runner/evaluator architecture;
- Golden Case schema;
- benchmark scoring/reporting;
- empirical Ollama model-performance measurement;
- SQLite persistence or Alembic;
- production cache implementation;
- broad provider abstraction beyond the minimum shared contract;
- provider/analyst consensus-growth ingestion unless its semantics and provenance are separately approved;
- tangible-book-value or sector-specific Graham variants;
- implementation of all seven historical defensive-investor criteria;
- additional financial algorithms beyond the two approved Graham methods;
- autonomous planning changes;
- model fine-tuning;
- private chain-of-thought capture;
- cloud LLM evaluation;
- unrelated production refactoring.

#### 4.3.13 Acceptance criteria

- [x] Graham is implemented as a second deterministic analytical strategy family without making it Momentum-shaped.
- [x] `graham_number` and `graham_growth_value` are distinct, stable method identifiers with method-specific typed configuration and results.
- [x] The CLI defaults to `graham_number`; it never silently selects or substitutes the growth method.
- [x] Ticker-only Graham Number execution resolves EPS, BVPS, and current price without requiring growth or AAA-yield arguments.
- [x] The Graham Number is documented and emitted as a screening ceiling/maximum indicated price, not a complete intrinsic-value determination.
- [x] `three_year_average` is the documented default EPS basis for the Graham Number; `ttm` is explicit and labeled.
- [x] BVPS definition, share basis, reporting period, and any derivation are explicit.
- [x] Non-positive EPS or BVPS produces a structured `not_applicable` result.
- [x] The growth method is explicitly forecast-dependent and records its growth policy, horizon, constants, and AAA-yield input convention.
- [x] No LLM-generated or silent default growth assumption is used.
- [x] Field-level resolution follows override → valid cache → provider → unavailable precedence.
- [x] Every resolved input carries source, provider/field where applicable, observation/reporting period, availability timestamp where supplied, `as_of`, `retrieved_at`, units, transformation, and override/cache status.
- [x] A requested `as_of` boundary prevents use of later observations or financial facts that had not yet been filed/published.
- [x] Invalid mathematical configuration values are rejected deterministically; arbitrary financial-domain limits are not introduced without rationale.
- [x] `current_price` and `margin_of_safety_percent` are nullable; unavailable data produces `None`, not numeric zero.
- [x] Positive and negative margin-of-safety semantics are documented against the selected method's reference value.
- [x] Narrow typed contracts support historical prices, current quotes, required company financial facts, provider-neutral macro observations, and cache access.
- [x] Provider-specific response details do not leak across the intended abstraction boundary.
- [x] Deterministic fixtures cover both Graham methods plus override/cache/provider precedence and timestamp behavior.
- [x] Fixture execution requires no live external market-data calls.
- [x] Step 3.1 can replace the fixture cache with production persistence without changing calculator APIs.
- [x] Momentum and both Graham methods are invocable through the existing generic analysis/tool/orchestration interface.
- [x] No orchestrator special case or speculative generic strategy/plugin/registry framework has been introduced.
- [x] `docs/user/FINANCE_MATH.md`, `docs/project/ARCHITECTURE.md`, `docs/user/GLOSSARY.md`, README/CLI examples, and relevant docstrings/configuration documentation agree with implemented behavior.
- [x] Existing application behavior is unchanged outside intended Step 2.3 additions.
- [x] Ruff, formatting, `mypy --strict`, and pytest pass.
- [x] The remaining Step 2.3 diff since the last approved checkpoint was reviewed and approved before Step 2.4 work.

**Definition of done:** Satisfied on 2026-08-25. Momentum and both explicitly named Graham methods coexist cleanly through the existing analysis architecture; the representative standard production Graham Number configuration is user-viable; Graham inputs resolve reproducibly through typed override/cache/provider resolution with provenance and `as_of` semantics; deterministic fixtures prove the contracts without network access; investor-facing concise/details/diagnostics/JSON presentation matches the approved semantics; documentation matches behavior; and the remaining diff passed human review before Step 2.4 work.

---

### 4.4 Step 2.4 – Free Cash Flow & Earnings Growth Analysis

**Goal**<br/>
Add a third materially different deterministic investor analysis before the Golden Suite, driven by prospective Real-User demand and designed to exercise the Step 2.3 financial-fact, resolver, provenance, fixture, CLI, and presentation boundaries.

The governing design is:

`docs/project/milestones/v0.2/STEP_2_4_FCF_EARNINGS_GROWTH_DESIGN.md`

Step 2.4 is a bounded strategy addition, not a reopening of Step 2.3 and not a reason to introduce speculative strategy/plugin architecture.

#### 4.4.1 Product-policy checkpoint

The phrase “FCF (free cash flow) and earnings growth” is sufficient to select the strategy direction but does not yet lock every investor-facing metric.

Implementation begins with reconnaissance only. Before production coding proceeds, explicitly resolve or approve the baseline for:

- historical actuals versus forward/analyst estimates;
- FCF amount/trend versus P/FCF or FCF yield;
- preferred historical horizon;
- whether the user wants a pass/fail rule or transparent metrics/trends; and
- whether TTM support is required initially.

Unless separately changed at that checkpoint, the approved baseline is:

- completed fiscal-year actuals;
- project-defined `FCF = operating cash flow - capital expenditures`;
- latest annual FCF and diluted EPS;
- year-over-year FCF/EPS change where mathematically meaningful;
- 3-year FCF CAGR and diluted-EPS CAGR using four compatible completed fiscal-year observations;
- a small descriptive trend classification;
- no forecast/consensus growth;
- no P/FCF or FCF yield in the required core;
- no DCF;
- no composite score or investment recommendation.

#### 4.4.2 Canonical financial semantics

For the initial implementation:

```text
free_cash_flow = operating_cash_flow - capital_expenditures
```

`capital_expenditures` is normalized at the provider/resolution boundary to a positive expenditure amount before subtraction. Derived FCF must retain complete component lineage.

The baseline earnings measure is completed fiscal-year diluted EPS.

Annual FCF is valid only when operating cash flow and capital expenditures refer to the same compatible fiscal period and currency. Do not combine cumulative/interim and full-year periods, different fiscal years, incompatible scopes, or facts that were not yet available by the requested `as_of`.

Provider/company precomputed “free cash flow” fields are not silently substituted unless their definitions are proven compatible with the project definition.

#### 4.4.3 Growth semantics

Year-over-year percentage growth is:

```text
(current - prior) / prior × 100
```

It is numeric only when the prior-period denominator is strictly positive. A zero/negative prior value remains visible financial data but produces an unavailable percentage-growth metric with a structured reason.

CAGR is:

```text
((ending / beginning) ** (1 / years) - 1) × 100
```

The default 3-year CAGR requires four compatible completed fiscal-year observations. Beginning and ending values must be strictly positive; sign changes or non-positive endpoints make CAGR unavailable rather than producing NaN, infinity, complex values, absolute-value reinterpretation, or a fabricated fallback.

Negative latest FCF or EPS is not a software error. The latest raw values remain reportable even when one or more growth metrics are mathematically unavailable.

#### 4.4.4 Strategy/data boundary

Reuse the existing Step 2.3 provider-neutral financial-fact, resolver, cache, provenance, fixture, subject-validation, and presentation patterns.

Do **not** create:

- a parallel FCF-only provider framework;
- a second provenance model;
- a second cache hierarchy;
- a second presentation framework;
- a speculative strategy registry/plugin system.

The minimum new semantic financial facts are:

- operating cash flow / net cash provided by operating activities;
- capital expenditures.

Annual diluted EPS should reuse the Step 2.3 capability wherever semantically compatible.

A Step 2.3 type or class may be renamed/generalized only if reconnaissance demonstrates a concrete new-strategy incompatibility; do not refactor merely because an old name now feels narrow.

#### 4.4.5 Point-in-time and provenance rules

Step 2.3's no-look-ahead policy remains authoritative.

Every accepted annual fact must preserve:

- exact provider concept/field;
- fiscal period start/end;
- filing/publication/availability timestamp where supplied;
- units/currency;
- retrieval/resolution time;
- requested `as_of`;
- selection/restatement rule;
- transformation details.

Each derived FCF observation must preserve lineage sufficient to reconstruct the operating-cash-flow and normalized-CapEx components.

A later filing/restatement is not eligible for an earlier historical `as_of` unless it was already available by that boundary.

#### 4.4.6 Provider evidence gate

SEC EDGAR is the natural first production candidate because Step 2.3 already established SEC financial-fact infrastructure, but no cash-flow mapping is approved merely by this plan.

Before coding production mappings, document evidence for:

- operating-cash-flow concept(s) and annual cash-flow-statement semantics;
- capital-expenditure concept(s), included/excluded expenditures, and provider-native sign convention;
- units/currency;
- fiscal-period pairing;
- amended/restated filing selection;
- publication/availability timestamp;
- historical `as_of`;
- reuse of annual diluted EPS.

If multiple plausible CapEx concepts exist, do not guess. Establish and test a conservative selection rule or stop for review.

#### 4.4.7 Deterministic fixtures and pure calculations

Fixtures must provide at least four compatible completed fiscal years and cover:

- annual operating cash flow;
- annual CapEx;
- annual diluted EPS;
- availability timestamps and provider concepts;
- CapEx sign normalization;
- duplicate/restatement behavior;
- future-published exclusion;
- missing CapEx;
- period mismatch;
- zero/negative prior values;
- negative FCF or EPS;
- provider failure.

Pure calculation code owns arithmetic only. Candidate functions may include:

```text
compute_free_cash_flow(...)
compute_growth_percent(...)
compute_cagr(...)
classify_fcf_earnings_growth(...)
```

Exact names follow repository conventions. Pure functions perform no provider/cache/filesystem/settings/clock I/O and never infer periods or missing values.

#### 4.4.8 Direct CLI and presentation

Proposed direct command:

```text
financial-agents fcf-growth TICKER [options]
```

Initial options:

```text
--growth-years INTEGER
--as-of DATE_OR_TIMESTAMP
--data-provider PROVIDER_ID
--no-cache
--details
--diagnostics
--json
```

Default `--growth-years` is 3.

Do not add ambiguous unperiodized repeated-value override flags merely to imitate Graham. If series overrides later prove necessary, use an explicit period-tagged representation.

Reuse the Step 2.3 progressive-disclosure grammar:

1. **Default concise:** latest completed period, latest FCF, diluted-EPS growth, FCF growth, descriptive trend, source/freshness, warnings, method limitation.
2. **`--details`:** annual CFO, normalized CapEx, FCF, diluted-EPS series, periods, provider concepts, availability, derivation lineage, growth endpoints.
3. **`--diagnostics`:** cache/provider/selection/derivation behavior and classified unavailable/error outcomes.
4. **`--json`:** stable machine-readable strategy result/provenance; unavailable growth metrics are JSON `null`, never `NaN`.

#### 4.4.9 Implementation sequence

Implement and review Step 2.4 in bounded slices:

1. **A — reconnaissance and product-policy lock:** inspect post-Step-2.3 reuse seams, provider evidence candidates, likely files, and resolve the product-policy checkpoint. Make no production changes. Stop for human review.
2. **B — pure FCF/growth math and typed result semantics:** implement deterministic arithmetic/results and focused tests only.
3. **C — financial-fact extension, resolution, and fixtures:** minimally extend the provider-neutral fact/resolution system and add period-aligned FCF derivation plus deterministic multi-year fixtures.
4. **D — provider evidence and production integration:** evidence and implement the minimum safe production path; unsupported evidence shapes remain unavailable.
5. **E — investor CLI and presentation:** add direct execution plus concise/details/diagnostics/JSON rendering and representative live validation after deterministic gates are green.
6. **F — documentation and full gate:** synchronize docs, run the complete repository gate, review the full Step 2.4 diff, and obtain explicit human completion approval before Step 2.5.

#### 4.4.10 Non-goals

Step 2.4 does **not** include:

- discounted-cash-flow valuation;
- terminal-value modeling;
- cost-of-capital estimation;
- analyst-consensus or LLM-generated growth forecasts;
- P/FCF or P/CF as required core metrics unless separately approved after the product-policy checkpoint;
- a broad named-investor methodology;
- arbitrary composite scoring/ranking;
- investment recommendations;
- Golden Suite/evaluator implementation;
- durable SQLite persistence/migrations;
- watchlists or Analysis Run persistence;
- a generic strategy/plugin registry;
- unrelated refactoring.

#### 4.4.11 Acceptance criteria

- [ ] The prospective-user policy question has been explicitly resolved or the historical baseline has been explicitly approved.
- [ ] The strategy is named and typed independently from Momentum and Graham.
- [ ] The canonical initial FCF definition is explicit and tested.
- [ ] CapEx provider sign conventions are normalized transparently.
- [ ] Annual CFO and CapEx are paired only across compatible fiscal periods.
- [ ] Annual diluted-EPS growth uses an explicit documented basis.
- [ ] 3-year CAGR uses four completed annual observations and rejects mathematically nonmeaningful endpoints.
- [ ] Negative/zero values are represented truthfully without NaN/infinity or fabricated fallbacks.
- [ ] Strict `as_of` prevents look-ahead.
- [ ] Derived FCF retains full component lineage.
- [ ] The Step 2.3 provider/cache/resolver/provenance architecture is reused or minimally extended rather than duplicated.
- [ ] Deterministic fixtures cover success, missing data, period mismatch, negative/zero growth, restatement, and historical-boundary cases.
- [ ] A representative supported production ticker can run the analysis without manual financial-statement arithmetic.
- [ ] Concise/details/diagnostics/JSON output follows the established investor-facing grammar.
- [ ] Automated tests make no live network or LLM calls.
- [ ] Full repository quality gates pass.
- [ ] Documentation matches implemented semantics.
- [ ] The final Step 2.4 diff receives explicit human approval.

**Definition of done:** Step 2.4 is complete when one useful, auditable Free Cash Flow & Earnings Growth strategy runs through the existing architecture with explicit historical financial semantics, reproducible provenance/`as_of` behavior, deterministic fixture coverage, a viable production path, coherent investor presentation, green repository gates, and explicit human approval.

---

### 4.5 Step 2.5 – Golden-Test Suite & Strategy Evaluation

**Goal**<br/>
Establish a deterministic, fixture-backed benchmark that exercises the approved v0.2 set of materially different analytical strategies and separates strategy/tool-selection correctness from deterministic numerical correctness.

Step 2.5 consumes the stable strategy and data foundations established in Steps 2.3–2.4. It must not redesign those foundations unless implementation evidence reveals a concrete defect.

The initial benchmark targets:

1. **Momentum analysis** — the existing historical-price/SMA strategy.
2. **Graham Number analysis** — the default defensive screening-ceiling method.
3. **Graham growth-value analysis** — the explicit forecast-dependent secondary method.
4. **Free Cash Flow & Earnings Growth analysis** — the Step 2.4 historical cash-flow/growth strategy.

This is the empirical test of the architectural objective established in Steps 2.3–2.4: financial analysis must not be implicitly synonymous with one analytical pattern.

#### 4.5.1 Implementation guardrails for Cline

- Reuse the Steps 2.3–2.4 strategy and market/financial-data contracts; do not create parallel abstractions.
- Reuse existing production orchestration/tool-dispatch wherever it already supports deterministic fixture injection.
- Introduce only the minimum test seams necessary for fixtures and evaluation evidence.
- Deterministic/no-LLM tests validate fixtures, contracts, analytics, expected values, and evaluator mechanics; **they cannot validate LLM strategy selection**.
- Real-local-Ollama evaluation measures empirical strategy/tool-selection behaviour and must remain separate from deterministic regression tests.
- Do not optimize or weaken benchmark criteria to achieve the ≥90% target. The suite measures model/system performance; it is not a mechanism for making the model pass.
- The ≥90% aggregate target does **not** imply that strategy-selection accuracy itself must equal or exceed 90%. Report component metrics honestly.
- Do not refactor unrelated production code.
- Stop for review after the minimum heterogeneous suite works before expanding benchmark sophistication.

#### 4.5.2 Fixture design and determinism

Golden fixtures are deterministic, reviewable test evidence. They use the shared fixture-backed data implementations established by Steps 2.3–2.4 and contain only the data required by their cases.

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

#### 4.5.3 Golden case schema

Represent each benchmark case with a typed case definition containing at minimum:

- unique case identifier;
- human-readable description;
- task/prompt supplied to the orchestrator;
- fixture identifier(s);
- expected analysis strategy/tool selection;
- expected deterministic outputs;
- numerical tolerances;
- expected strategy/tool-selection constraints;
- pass/fail evaluation rules;
- optional tags.

Define required, permitted, and forbidden behaviour. Forbidden behaviour includes live network access, unrelated strategy/tool substitution, fabricated numerical inputs, bypassing the market-data abstraction, malformed tool arguments, and missing required analytical output.

#### 4.5.4 Initial benchmark composition

The eventual initial suite should contain approximately **10–18 high-signal cases**, but implementation must begin with a smaller minimum heterogeneous set before expansion.

Minimum set:

- straightforward Momentum case;
- Momentum boundary/edge case;
- straightforward Graham Number case using the default three-year-average EPS basis;
- Graham Number case using the explicitly selected TTM variation;
- Graham Number `not_applicable` case;
- growth-value case with an explicit growth policy and documented yield fixture;
- Graham missing-current-price case;
- input-resolution case proving override/cache/provider precedence and `as_of` behavior;
- straightforward Free Cash Flow & Earnings Growth case;
- FCF/earnings-growth case with insufficient or mathematically nonmeaningful growth history;
- FCF/earnings-growth case proving period alignment and historical `as_of` rejection;
- at least one case where selecting a materially different strategy would produce a materially different analytical result.

After that minimum works, expand toward the target range with additional coverage such as:

- multiple deterministic tool calls;
- missing/insufficient fixture data;
- tool-argument sensitivity;
- malformed/unstructured-output regression;
- provider/fact-selection edge cases;
- known or plausible failure modes.

Document why each case provides useful signal.

#### 4.5.5 Independently verified expected values

Expected numerical values are part of the benchmark contract and must be independently verified before being committed.

Prefer, in order:

1. simple transparent reference calculations;
2. a separate reference implementation;
3. manual verification for sufficiently simple cases.

Do not generate expected values by invoking the production function under test.

Use case-appropriate absolute/relative tolerances rather than one universal tolerance.

#### 4.5.6 Strategy/tool-selection evaluation

Evaluate strategy/tool-selection correctness separately from numerical correctness.

Use observable Step 2.1 trajectory evidence where useful. Verify the expected strategy/tool, valid arguments, case-corresponding arguments, relevant prohibited/unnecessary-tool constraints, and actual fixture-backed data use.

Selecting Momentum when Graham or FCF/earnings-growth analysis is required is a **strategy-selection failure**, even if the final prose appears plausible. Selecting the growth-value method when a Graham Number was requested, or vice versa, is a **method-selection failure** and must be reported separately or as a clearly identified subtype.

Selecting the correct strategy but obtaining an incorrect deterministic result is a **numerical/implementation failure**, not a strategy-selection failure.

Where multiple tool sequences are legitimately equivalent, define an acceptable set or predicate.

#### 4.5.7 Numerical and case-level evaluation

Compare deterministic analytics/tool outputs against independently verified expected values. LLM prose is not authoritative when structured deterministic output exists.

Report separately:

- strategy/tool-selection score;
- Graham method-selection score where applicable;
- numerical-correctness score;
- overall case pass/fail.

A case fails overall when a required case-level criterion fails even if another component passes.

#### 4.5.8 End-to-end execution

Reuse the real production orchestration/tool-dispatch flow as far as practical. Introduce only the minimum injection seams required for deterministic fixtures and evaluation evidence.

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

#### 4.5.9 LLM nondeterminism

Real-model evaluation may use the configured local Ollama server. Document model identifier, Ollama configuration, sampling settings where applicable, repetitions, and treatment of nondeterministic outcomes.

Do not make model-generated behaviour a prerequisite for deterministic fixture/analytics tests.

#### 4.5.10 Telemetry integration

Every end-to-end Golden Suite execution should produce a Step 2.1 trajectory. Use telemetry as observable evidence of selected strategy/tools, arguments, results, errors/recovery, step boundaries, and run identity.

Do not depend on private model reasoning or `<think>` content. Telemetry is execution evidence, not the benchmark expectation.

#### 4.5.11 Machine-readable evaluation report

Emit a machine-readable report containing at minimum:

- suite identifier/version;
- execution timestamp;
- model/provider configuration when applicable;
- fixture-set version;
- total/passed/failed/skipped cases;
- overall pass rate;
- strategy/tool-selection score;
- Graham method-selection score where applicable;
- numerical-correctness score;
- end-to-end case score;
- per-case result;
- failure category/reason;
- run/trajectory identifier where available.

The report must distinguish strategy-selection, Graham method-selection, deterministic numerical, fixture/data, and other execution failures.

#### 4.5.12 Pass-rate definition

```text
aggregate pass rate =
    cases satisfying all required case-level acceptance criteria
    ------------------------------------------------------------
    total executed benchmark cases
```

Report both case-level pass/fail and component-level metrics.

The ≥90% target is an evaluation target, not a reason to modify expectations, remove failing cases, or otherwise tune the instrument until the model passes.

#### 4.5.13 Evaluator regression/self-test

Include at least one evaluator self-test proving that an intentionally incorrect result is detected as a failure. Keep it separate from the normal benchmark denominator so CI remains green when the evaluator correctly detects the synthetic failure.

#### 4.5.14 Network isolation

Normal deterministic Golden Suite execution requires no external market-data access. Fixture-backed adapters fail closed when requested data is absent and never silently fall back to live providers.

#### 4.5.15 CLI / execution interface

Provide a documented command through the project's normal `uv run` workflow supporting:

- full suite;
- individual case;
- deterministic/no-LLM evaluation;
- optional real-local-Ollama evaluation;
- output report location.

Return a non-zero process exit status when required benchmark criteria fail. Real-model/network-dependent evaluation is not mandatory CI unless explicitly configured.

#### 4.5.16 Documentation

Update `docs/EVALUATIONS.md` to document Golden Suite purpose, architecture, fixture provenance, expected-value verification, tolerance policy, scoring, deterministic mode, real-Ollama mode, execution command, report format, failure interpretation, and case/fixture maintenance.

Update `docs/project/ARCHITECTURE.md` if Step 2.5 introduces any evaluation-specific seams not already documented in Steps 2.3–2.4.

#### 4.5.17 Relationship to Step 3.1

Step 3.1 introduces SQLite-backed production persistence and market/financial-data access. Step 2.5 must not couple Golden cases directly to SQLite, Alembic, provider-specific APIs, or production cache internals.

```text
Step 2.5 Golden Case
        │
        ▼
Shared Data Contracts
      │       │
      ▼       ▼
Fixture     SQLite
Adapters    Adapters
2.3/2.4    Step 3.1
```

Golden case definitions should remain unchanged when the production persistence adapter arrives.

#### 4.5.18 Implementation sequence

1. Inspect and accept the stable Steps 2.3–2.4 strategy/data contracts; do not redesign them speculatively.
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
12. Expand toward the approved initial target range.
13. Add optional real-local-Ollama evaluation.
14. Add the documented CLI.
15. Update evaluation documentation.
16. Run Ruff, formatting checks, `mypy --strict`, and pytest.
17. Record deterministic and, when available, empirical model results separately.

#### 4.5.19 Non-goals

Step 2.5 does **not** include:

- SQLite persistence or Alembic;
- production cache implementation;
- analytical strategies beyond the approved v0.2 set;
- broad provider abstraction;
- UI/dashboard work;
- autonomous planning changes;
- model fine-tuning;
- private chain-of-thought capture;
- cloud LLM evaluation;
- unrelated production refactoring.

#### 4.5.20 Acceptance criteria

- [ ] A reproducible fixture-backed Golden Suite exercises Momentum, the Graham Number, the Graham growth-value method, and Free Cash Flow & Earnings Growth.
- [ ] No live market-data access is required for deterministic suite execution.
- [ ] Existing production orchestration/tool-dispatch is reused as far as practical.
- [ ] Expected numerical values are independently verified.
- [ ] Strategy/tool-selection correctness is evaluated separately from numerical correctness.
- [ ] Deterministic numerical evaluation does not depend on LLM prose.
- [ ] A minimum heterogeneous case set works before expansion.
- [ ] The default three-year-average EPS basis, explicit TTM variation, `not_applicable` behavior, and missing-current-price behavior are covered by Graham cases.
- [ ] At least one case verifies Graham method-selection correctness independently of broad strategy selection.
- [ ] Straightforward, insufficient/nonmeaningful-growth, and period/`as_of` FCF-growth cases are covered.
- [ ] At least one case materially discriminates correct strategy selection from a plausible wrong strategy.
- [ ] Machine-readable reporting distinguishes component and overall failures.
- [ ] The ≥90% target is defined and reported without weakening criteria.
- [ ] Strategy-selection accuracy is reported independently and is not artificially forced to ≥90%.
- [ ] An evaluator self-test detects an intentionally incorrect result.
- [ ] Deterministic/no-LLM mode is documented.
- [ ] Optional real-local-Ollama evaluation is documented separately.
- [ ] CLI execution and non-zero failure status work.
- [ ] `docs/EVALUATIONS.md` is updated.
- [ ] Step 3.1 can replace fixture-backed data sources with production persistence without changing Golden case definitions.
- [ ] Ruff, formatting, `mypy --strict`, and pytest pass.
- [ ] Actual measured benchmark results are recorded honestly.

**Definition of done:** Step 2.5 is complete when the repository contains a reproducible fixture-backed benchmark that exercises the approved heterogeneous v0.2 strategy set, distinguishes strategy/method-selection failures from deterministic numerical failures, produces an auditable machine-readable report, and remains decoupled from production persistence.

---

### 4.6 Step 2.6 – Circuit Breakers & Timeout Limits

**Goal**<br/>
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

### 4.7 Step 3.1 – SQLite DB & Migration Infrastructure

**Goal**
Establish the production SQLite persistence foundation while implementing the SQLite telemetry sink and durable production data/cache access behind the contracts established in Steps 2.3–2.4.

**Implementation outline**
1. Add Alembic and establish the migration environment using the existing application database configuration.
2. Create the initial production schema for market prices/OHLCV, instrument/source metadata, required company financial facts, macro-series observations, cache metadata, and trajectory telemetry storage.
3. Enforce SQLite WAL mode and appropriate busy-timeout/connection settings.
4. Implement `SQLiteTrajectorySink` against the exact `TrajectorySink` contract established in Step 2.1.
5. Implement durable historical-series, financial-fact, and cache retrieval behind the Steps 2.3–2.4 provider/resolver contracts.
6. Place repository implementation under `src/data/repositories/`.
7. Preserve provider identity, observation/availability timestamps, requested `as_of`, retrieval time, and cache freshness/schema metadata when persisted.
8. Provide a documented migration command and fresh-database smoke test.
9. Verify trajectories can be persisted/reconstructed identically through JSONL or SQLite sinks.

**Acceptance criteria**
- [ ] `alembic upgrade head` succeeds on a clean environment.
- [ ] WAL mode is verified.
- [ ] Schema is migration-controlled.
- [ ] `SQLiteTrajectorySink` conforms to the Step 2.1 sink contract.
- [ ] A representative trajectory can be written to and reconstructed from SQLite.
- [ ] Production data/cache implementations satisfy the historical-price and financial-fact contracts used by the approved strategies.
- [ ] Valid cached inputs can be reused without unnecessary external refetch and without losing provenance or temporal semantics.

### 4.8 Step 3.2 – DAO & Repository Layer

**Goal**<br/>
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

### 4.9 Step 3.3 – Data Quality & Cache Invalidation Pipeline

**Goal**<br/>
Validate incoming financial data (FX adjustments, corporate actions, staleness) and invalidate or refresh cache entries when quality rules fail.

**Implementation outline**
1. Define core quality rules: price series continuity/missing-bar detection, currency consistency (CAD vs USD), financial-period compatibility, and maximum age of cached observations before forced refresh.
2. Run rules on every fetch operation before writing to the cache.
3. On failure: reject the write, mark the entry stale, or trigger a controlled re-fetch (with circuit-breaker awareness).
4. Log quality decisions into the execution trajectory for auditability.
5. Unit tests with synthetic valid and invalid data series/facts.

**Acceptance criteria**
- [ ] Documented quality rules with clear pass/fail behaviour.
- [ ] Stale or invalid data cannot silently become the source of truth for downstream analytics.
- [ ] Quality failures appear transparently in the trajectory log.

---

### 4.10 Step 3.4 – Local Research Workspace & Analysis Run Library

**Goal**
Turn the command-line program into a small local research workbench before real-user validation: users maintain ticker/analysis lists, initiate a refresh, and revisit durable completed results without requiring a GUI or unattended service.

**Product model**
- A **watchlist** is a named local collection of tickers plus supported requested analysis types/configuration.
- An **Analysis Run** is the durable investor-domain record of one requested analysis: `analysis_run_id`, ticker, analysis/method, requested `as_of`, configuration snapshot, status, typed result payload, resolved-input provenance, warnings, start/completion times, and calculation/version identifiers. It may reference execution/telemetry identity, but does not overload `RunContext`.
- A **report/view** is a rendering of an Analysis Run. v0.2 does not persist a competing canonical report document.
- A **refresh** is a user-initiated batch that may execute multiple ticker/analysis jobs concurrently and persist each completed Analysis Run immediately.

**Initial CLI workflow**
```text
financial-agents watchlist create core
financial-agents watchlist add core KO MSFT CNR.TO
financial-agents watchlist remove core MSFT
financial-agents watchlist show core
financial-agents refresh core
financial-agents runs list
financial-agents runs show ANALYSIS_RUN_ID [--details|--diagnostics|--json]
```

Exact command spelling may be refined during implementation, but the user capability must remain equivalent. The initial default watchlist profile uses analyses that require no invented forward-growth assumption: Momentum, Graham Number, and the historical FCF/Earnings Growth strategy once Step 2.4 is complete. `graham_growth_value` may be enabled only when an explicit persisted/user-supplied growth configuration is attached and shown as an assumption.

**Concurrency boundary**
`refresh` may run independent jobs concurrently within the user-started process and write completed runs as they finish; a second CLI invocation may read already-persisted completed results under SQLite/WAL. Step 3.4 does **not** install a daemon/service, schedule unattended work, monitor markets proactively, or send notifications.

**Implementation outline**
1. Add migration-controlled persistence for watchlists, memberships/configuration, refresh batches if useful, and Analysis Runs.
2. Add narrow typed repositories/services for watchlist management and Analysis Run storage/query.
3. Reuse strategy presenters for `runs show`; do not regenerate financial calculations merely to view a completed run.
4. Add user-initiated concurrent refresh with bounded worker/concurrency limits and per-job classified status.
5. Persist each completed/failed/unavailable run independently so one ticker/provider failure does not discard other completed work.
6. Preserve reproducibility: `as_of`, config, method version, result, provenance, warnings, and source timestamps travel with the Analysis Run.
7. Add deterministic tests for create/add/remove/show, refresh fan-out, partial failures, persistence/reload, run-list ordering/filtering, and view rendering.

**Acceptance criteria**
- [ ] Named watchlists can add/remove tickers and show configured supported analyses.
- [ ] A refresh over multiple ticker/analysis combinations executes with bounded concurrency and independently persisted outcomes.
- [ ] `runs list` exposes completed/unavailable/failed work without requiring recomputation.
- [ ] `runs show` renders the same concise/details/diagnostic/JSON information from the stored Analysis Run.
- [ ] Analysis Run identity is distinct from, but linkable to, execution telemetry identity.
- [ ] No daemon, unattended scheduler, proactive monitoring, notifications, full-screen TUI, or executive report generator is introduced.

### 4.11 Step 3.5 – Light Mode Support

**Goal**
The complete investor workflow—data fetch/cache → deterministic analytics → durable Analysis Run → concise/detailed inspection → bounded local-model synthesis—runs cleanly under Light Mode with a 14B-class (or smaller) model.

**Implementation outline**
1. Make Light Mode the configuration default (model tag, single-tier behaviour).
2. Ensure README and `docs/user/HARDWARE.md` give a new user a complete workflow to first analysis/watchlist refresh and stored-run inspection.
3. Add a minimal smoke test covering direct analysis or watchlist refresh, result persistence, concise rendering, and provenance inspection under Light Mode resource assumptions.
4. Confirm dual-tier functionality remains available as opt-in features.
5. Complete the Step 2.2 empirical schema/model compatibility check for the supported Light Mode configuration.
6. Add or validate a simple `financial-agents analyze TICKER` entry point that can request the default deterministic analyses and optionally ask the local LLM to synthesize only their completed typed results.
7. Ensure synthesis failure, timeout, or schema failure never discards valid deterministic Analysis Runs.

**Synthesis boundary**
The model may summarize, compare, flag tensions, and suggest what the investor may wish to inspect next. It may not invent financial facts, perform the deterministic arithmetic, silently select a growth assumption, or turn a screening result into an investment recommendation.

**Acceptance criteria (exit criterion for Step 3.5)**
- [ ] A new user following only Light Mode instructions can analyze/add a real ticker, refresh supported analyses, and revisit stored results.
- [ ] The user can see a concise result and inspect detailed provenance without developer assistance.
- [ ] Bounded local-model synthesis works on the supported Light Mode configuration and is clearly downstream of deterministic results.
- [ ] Synthesis failure leaves deterministic results usable.
- [ ] Configuration defaults favor Light Mode and dual-tier remains optional.
- [ ] Documentation is consistent across README, `docs/user/HARDWARE.md`, Master Plan, and Discovery Workbook.

## 5. Suggested Sequencing & Parallelism

```text
Phase A — Step 2.1 foundation
  └─ telemetry model, sinks, runtime instrumentation

Phase B — Step 2.2 structured-output foundation
  └─ native schema enforcement + fallback

Phase C — Step 2.3 strategy/data/presentation foundation
  ├─ Graham methods, provenance, resolver, fixtures
  ├─ verified production adapters + standard BVPS path
  ├─ investor-facing presentation + unified direct CLI
  └─ complete gate + human approval
        │
        ▼
Phase D — Step 2.4 FCF & earnings growth
  ├─ reconnaissance + product-policy lock
  ├─ pure historical FCF/growth semantics
  ├─ financial-fact extension + fixtures + provider evidence
  └─ investor CLI/presentation + complete gate
        │
        ▼
Phase E — Step 2.5 Golden Suite
  └─ heterogeneous selection + deterministic numeric evaluation

Phase F — Step 2.6 reliability limits
  └─ circuit breakers & timeout limits

Phase G — Step 3 production persistence/data quality
  ├─ 3.1 SQLite + durable cache/data/telemetry
  ├─ 3.2 typed repositories
  └─ 3.3 data quality / invalidation
        │
        ▼
Phase H — Step 3.4 local research workspace
  └─ watchlists + user-initiated concurrent refresh + Analysis Run library
        │
        ▼
Phase I — Step 3.5 adoption gate
  └─ Light Mode workflow + bounded typed-result synthesis
       → unlocks Milestone v0.2.5 real-user validation
```

## 6. Quality Gates

The following quality checks must pass on every pull request within this milestone:

* `ruff check . && ruff format --check .`
* `mypy --strict src tests`
* `pytest` (unit and integration) with monitored coverage trends
* Zero untyped public interfaces
* Zero secret or API key leaks in trajectory outputs
* Verified Light Mode workflow functionality once Step 3.5 lands

---

## 7. Exit Criteria for Milestone v0.2

All of the following must be true before declaring the milestone complete and opening the v0.2.5 validation window:

1. Steps 2.1–2.6 and 3.1–3.5, including the new Step 3.4 research workspace, are fully implemented and merged.
2. Step 2.5 Golden-test suite exists, runs headlessly, exercises Momentum, both Graham methods, and Free Cash Flow & Earnings Growth, and reports strategy-selection, Graham method-selection, numerical-correctness, and overall pass rates against the ≥ 90 % target.
3. A fresh repository clone running Light Mode setup instructions completes the investor workflow: direct/watchlist analysis, refresh, persisted Analysis Run, concise view, detailed provenance, and bounded synthesis.
4. CI pipeline is green on `main`.
5. Master Plan and Discovery Workbook cross-references remain consistent.
6. Temporary scaffolding and blocking TODOs are cleaned up or documented.

---

## 8. Decisions & Deferred Questions

### Resolved before implementation
1. **Trajectory storage sequencing** — JSONL first in Step 2.1; SQLite sink in Step 3.1 behind the same sink abstraction.
2. **Golden Suite data determinism** — Step 2.3 establishes the first shared historical-price, quote, financial-fact, macro-observation, cache, input-resolution, and deterministic fixture contracts; Step 2.4 minimally extends the financial-fact/fixture surface for FCF and earnings growth; Step 2.5 consumes the stable combined foundation; Step 3.1 supplies durable production SQLite/cache-backed access.
3. **Telemetry retention** — Configurable via `ProjectSettings`, adhering to existing `logger_util.py` options.
4. **Branch granularity** — Fine-grained branches mapped to coherent implementation units.
5. **Telemetry boundaries** — Telemetry captures observable provider output; missing metrics are stored explicitly as `None` rather than estimated.
6. **Heterogeneous strategy validation** — Momentum and Benjamin Graham are established in Step 2.3; Free Cash Flow & Earnings Growth is added in Step 2.4; Step 2.5 evaluates broad strategy selection, Graham method selection, and deterministic numerical correctness across the approved v0.2 set.
7. **Current quote abstraction** — Current market-price retrieval is a first-class valuation-input capability rather than an implicit one-day historical-data workaround.
8. **Graham result semantics** — The Graham Number is a screening ceiling/maximum indicated price, while the growth formula is a separate forecast-dependent estimate. An unavailable current price produces an unavailable (`None`) margin of safety rather than numeric zero. Positive margin of safety means price is below the selected method's reference value; negative means it exceeds that value.
9. **Strategy-specific determinism** — Each analytical strategy owns its deterministic mathematical implementation and typed configuration/result models. The LLM selects and orchestrates strategies but does not perform the underlying financial calculations.
10. **Step 2.2 enforcement fallback** — Native schema enforcement is preferred when capability is confirmed; prompt-based schema instructions with Pydantic validation/retry provide the configured fallback when native capability is unavailable or unknown; legacy parsing remains the final compatibility fallback.
11. **Graham default method** — `graham_number` is the default CLI method; `graham_growth_value` is explicit and secondary.
12. **Graham Number EPS basis** — Three-year-average fiscal EPS is the default; TTM EPS is an explicitly selected and labeled modern variation.
13. **Graham growth policy** — The growth method requires an explicit expected-growth override. No LLM or silent default supplies growth.
14. **Input resolution** — Inputs resolve field by field using override → valid cache → provider → unavailable precedence, with provenance and `as_of` semantics preserved.
15. **Checkpoint policy** — Reviewed, coherent intermediate checkpoints may be committed/pushed after explicit human approval and a green agreed gate. A checkpoint does not mark the parent step complete or authorize the next step.
16. **Investor-facing presentation** — Default terminal output is concise; `--details`, `--diagnostics`, and `--json` provide progressive disclosure. Strategies share presentation grammar, not a forced internal result model.
17. **Durable product record** — Step 3.4 stores Analysis Runs as the canonical investor-domain history; report formats are views of those runs.
18. **Bounded v0.2 agentic behavior** — User-initiated refresh may fan out concurrently and Light Mode may synthesize completed typed results. Unattended scheduling, proactive monitoring, notifications, and autonomous multi-step research remain v1.0 work.
19. **Step 2.4 roadmap placement** — Free Cash Flow & Earnings Growth is implemented before the Golden Suite to address concrete prospective Real-User demand and to exercise the Step 2.3 strategy/data/provenance architecture before evaluation infrastructure is frozen.
20. **Step 2.4 baseline interpretation** — Unless the pre-implementation product-policy checkpoint changes it, the first version is a historical actuals screen using project-defined FCF, diluted-EPS growth, and FCF growth; DCF, analyst forecasts, P/FCF, broad named-investor methodology, and composite recommendation scoring are not implied.

### Explicitly deferred
1. **Ollama schema/model support matrix** — Empirical validation remains outstanding for the actual Light Mode model configuration. Record the tested Ollama version, model identifier, schema-constrained request, observed response behaviour, and pass/fail result when completed. This is non-blocking for the Step 2.2 implementation/merge.
2. **Provider/analyst consensus-growth policy** — Do not ingest a provider forecast until its field meaning, time horizon, provenance, update behavior, and licensing are verified.
3. **Tangible-book and sector-specific variants** — Defer these until the base Graham methods and their limitations are validated.
4. **Step 2.4 product refinements** — P/FCF/FCF yield, forward earnings growth, alternate growth horizons, and explicit screen thresholds remain pending the prospective Real-User product-policy checkpoint.

---

## 9. Next Immediate Actions

Step 2.3 is complete and approved. The immediate work is to close its PR with the agreed roadmap recorded, then begin Step 2.4 as a separate implementation step.

1. Apply and review the planning/documentation amendment that inserts Step 2.4 Free Cash Flow & Earnings Growth and renumbers Golden evaluation/reliability work.
2. Add `docs/project/milestones/v0.2/STEP_2_4_FCF_EARNINGS_GROWTH_DESIGN.md` as the Step 2.4 design document.
3. Complete the Step 2.3 closeout PR without including Step 2.4 production code.
4. Gather the focused prospective Real-User clarification on historical versus forward growth, FCF trend versus valuation multiple, preferred horizon, and desired screening behavior.
5. Start Step 2.4 on `feat/step-2.4-fcf-earnings-growth` with **Slice A reconnaissance only**; reconcile the product-policy checkpoint before Slice B.
6. Implement and review Step 2.4 in bounded slices through its full documentation/gate approval.
7. Begin Step 2.5 Golden Suite only after Step 2.4 is complete and approved.
8. Implement Step 2.6 reliability limits, then Step 3.1–3.3 persistence/repositories/data quality and Step 3.4 research workspace.
9. Complete Step 3.5 Light Mode workflow, including empirical schema/model compatibility validation, before opening v0.2.5 real-user validation.
