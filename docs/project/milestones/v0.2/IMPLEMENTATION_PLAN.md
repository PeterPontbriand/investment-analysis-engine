# Milestone v0.2 Implementation Plan
## Reliability, Observability, Data Persistence, Investor Workflow & Strategy-General Evaluation

**Project:** Financial Data Agents<br/>
**Repository:** [https://github.com/PeterPontbriand/financial-data-agents](https://github.com/PeterPontbriand/financial-data-agents)<br/>
**Source of truth:** Current `docs/project/MASTER_PLAN.md` (Milestone v0.2 section)<br/>
**Companion rationale:** Current `docs/project/DISCOVERY_WORKBOOK.md`<br/>
**Prepared:** 2026-08-15<br/>
**Revised:** 2026-09-02 — Recorded Step 2.6 Slice B implementation and Gate B review stop.<br/>
**Status:** Step 2.2 → implementation complete; Steps 2.3, 2.4, 2.5, and 2.5A → complete and approved; Step 2.6 → Slice B implemented, pending Gate B review
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
| **Deterministic Versioned Report Projection** | Project investor reports from persisted Analysis Runs without provider/LLM calls, financial recalculation, or mutable current-state enrichment. Version the projection contract independently from calculation methods and result schemas. | Step 3.4, Step 7 |
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
| Step 2.4 pre-Golden shared-contract hardening | `fix/step-2.4-pre-golden-contract-hardening` | Corrects bounded Graham result, presentation, quote, and compatibility seams before benchmark fixtures freeze them |
| Step 2.5 Golden runner | `feat/step-2.5-golden-suite` | Implements heterogeneous benchmark cases and evaluation harness after the v0.2 strategy set is stable |
| Step 2.5A SEC FPI/IFRS coverage | `feat/step-2.5a-sec-fpi-ifrs` | Adds foreign annual forms, exact IFRS duration mappings, snapshot consistency, and security-unit gates after Golden closeout |
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

Step 2.4 adds Free Cash Flow & Earnings Growth on these same strategy/data foundations. Its closeout includes the Graham/shared-contract corrections in Section 4.4.10 and bounded shared security-identity work in Section 4.4.11 without changing Step 2.3's historical completion status. The subsequent Step 2.5 Golden Suite will benchmark Momentum, both Graham methods, and the Step 2.4 cash-flow/growth strategy only after those corrections are approved. Later work may otherwise extend the provider-neutral contracts only where concrete new data requirements or review findings prove that extension necessary.

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

Graham is not forced to be "Momentum-shaped" merely for some notional implementation consistency, and future implement strategies will have their own shapes that will be invocable through the **existing** analysis/tool/orchestration mechanisms as well.

#### 4.3.2 Graham method definitions and output semantics

The approved implementation contains both Graham methods, provenance/cache/resolution contracts, deterministic fixtures, verified production adapters, the E3 SEC-backed BVPS derivation, and the F1/F2 investor-facing CLI/presentation work. The Graham design document describes the completed behavior exactly. This section is a historical planning summary; where its originally intended contract was not fully enforced, Section 4.4.10 records the required correction before the Golden Suite.

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
- the selected EPS observations must share provider field, units, currency, and accounting basis; the current implementation retains provider restatement semantics but does not independently prove share-class compatibility or normalize splits;
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

Each pure calculation result includes a stable method identifier, a shared `CalculationStatus`, a nullable reason string, and the method-specific reference value (`maximum_indicated_price` or `growth_value`). The command presentation combines that result with the resolved-input assembly, optional current price and margin-of-safety percentage, provenance, diagnostics, warnings, limitation, and JSON schema version. The current result models require a method value on success and a null value plus reason on failure, but do not yet reject a non-null reason on success; Section 4.4.10 closes that invariant.

The project retains the existing margin-of-safety convention:

```text
(reference_value - current_price) / reference_value × 100
```

Positive means the current price is below the method's reference value; negative means it is above it. This percentage is a valuation discount/premium calculation and must not imply that business or investment risk has been eliminated. If the reference value or current price is unavailable, margin of safety is `None`, never numeric zero.

#### 4.3.3 Method-aware input-resolution layer

Step 2.3 added a typed input-resolution layer between CLI/tool requests and deterministic calculation. The calculator receives resolved values; it does not know how to call providers, inspect caches, or interpret CLI precedence.

Provider-resolvable fields use this order:

1. explicit user/CLI override;
2. valid cache entry satisfying the requested `as_of` and freshness policy;
3. configured provider retrieval;
4. explicit `input_unavailable` result or typed error when no permitted source can supply the field.

Expected growth is instead override-only. There is no silent numeric default, cross-method substitution, or live-network fallback from deterministic fixture mode.

Every resolved field preserves at least:

- canonical field name and value;
- units and currency where applicable;
- source kind (`override`, `cache`, `provider`, or `derived`); fixture-backed facts use the provider source kind and retain their fixture provider identity;
- provider and provider field/series identifier when applicable;
- source observation/reporting period;
- `as_of` timestamp/date describing the observation or reporting boundary;
- publication, filing, or `available_at` timestamp where the source supplies one;
- `retrieved_at` timestamp describing when the application obtained it;
- transformation details actually applied, including averaging or derivation lineage;
- cache schema/version metadata when a cache entry is used; and
- override status through the explicit source kind.

The resolver accepts an optional requested analysis `as_of`. It may use only information actually available on or before that boundary. For company financial facts, a fiscal period end alone does not prove the value was known then; use a filing/publication/availability timestamp when available to prevent look-ahead bias. The production quote adapters are current-only and therefore return no historical quote for a requested historical `as_of`. If no analysis `as_of` is supplied, current-resolution timestamps and provenance identify when the inputs were resolved or retrieved.

Input timestamps are allowed to differ naturally—for example, a quote may be newer than the latest financial statement—and retained provenance makes the difference visible. Cache time-to-live and historical eligibility are enforced by injected cache policy; the current presenter adds no separate cross-input age rule.

Step 2.3 defines the resolver and a narrow cache-access seam plus deterministic cache-hit/miss/stale fixtures. Step 3.1 remains responsible for the durable SQLite cache implementation, and Step 3.3 remains responsible for broader production data-quality and invalidation policy.

#### 4.3.4 EPS, BVPS, and growth-estimation policy

##### EPS policy

The project distinguishes these earnings bases rather than exposing one ambiguous `eps` value:

- `three_year_average` — arithmetic mean of three completed fiscal-year per-share earnings observations; default for `graham_number`;
- `ttm` — trailing-twelve-month EPS; supported as an explicitly labeled modern variation;
- `normalized` — an explicitly documented transformation used by `graham_growth_value`, if the implementation adjusts reported earnings.

The SEC mapping uses diluted EPS and retains the exact provider field and fiscal periods used. Three-year averaging requires identical provider field, units, currency, and accounting basis across observations. The implementation does not independently inspect share-class dimensions or record/apply a separate split adjustment; Section 4.4.10 requires an explicit compatibility policy before the Golden Suite.

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
- `--eps`, `--bvps`, and `--current-price` remain field-level overrides and retain override provenance; earnings-per-share and book-value-per-share overrides produce concise warnings, while a current-price override is visible in details/JSON but does not currently produce its own warning;
- `--eps-basis three_year_average|ttm` controls the Graham Number earnings convention;
- growth-specific options are accepted only for `--method growth`;
- the growth method requires an explicit expected-growth assumption and explicit AAA-yield input under the Step 2.3 production policy;
- `--as-of` provides a reproducible temporal boundary; and
- incompatible options fail with a clear usage error rather than being ignored.

Investor-facing presentation uses progressive disclosure:

1. **Default concise view** — ticker, method/analysis, historical `as_of` when requested, headline metrics, plain-language comparison, high-level source/freshness summary, material warnings, and a short method limitation. Successful output omits `Status: ok`; calculation failures rendered by the presenter include status and reason, while required-input and similar assembly failures currently use a one-line friendly path.
2. **`--details`** — financial audit trail: resolved inputs, bases, periods/observation dates, provider/source identity, availability dates, derivations/component lineage, and visible assumptions.
3. **`--diagnostics`** — software resolution trace: override supplied/not supplied, cache hit/miss/staleness, provider attempted, and classified failure/unavailability. A cache hit continues to identify the original financial source rather than pretending “cache” is the economic data source.
4. **`--json`** — stable machine-readable result/provenance output suitable for later persistence and tooling.

Expected growth is always displayed as an assumption. Earnings-per-share and book-value-per-share overrides are warned in the applicable concise view, and the user-supplied AAA yield has its own warning; current price and expected growth do not produce generic override warnings. Unqualified `Intrinsic Value` wording is prohibited for the Graham Number. Operational logger output is not the primary investor-facing renderer.

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
- retain exact per-share provider concepts and period evidence; independent split/share-class compatibility enforcement is scheduled in Section 4.4.10;
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
- [x] Provider-resolvable fields follow override → valid cache → provider → unavailable precedence; expected growth is override-only.
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

**Definition of done:** Satisfied on 2026-08-25. Momentum and both explicitly named Graham methods coexist cleanly through the existing analysis architecture; the representative standard production Graham Number configuration is user-viable; Graham inputs resolve reproducibly through typed override/cache/provider resolution, or the explicit growth override path, with provenance and `as_of` semantics; deterministic fixtures prove the principal contracts without network access; the investor-facing concise/details/diagnostics/JSON modes were approved; and the remaining diff passed human review before Step 2.4 work. The later design-to-implementation audit did not revoke that completion, but its bounded hardening findings must be closed under Section 4.4.10 before Step 2.5.

---

### 4.4 Step 2.4 – Free Cash Flow & Earnings Growth Analysis

**Goal**<br/>
Add a third materially different deterministic investor analysis before the Golden Suite, addressing documented stakeholder requirements and exercising the Step 2.3 financial-fact, resolver, provenance, fixture, CLI, and presentation boundaries.

The governing design is:

`docs/project/milestones/v0.2/step-2.4/STEP_2_4_FCF_EARNINGS_GROWTH_DESIGN.md`

Step 2.4 is a bounded strategy addition, not a reopening of Step 2.3 and not a reason to introduce speculative strategy/plugin architecture. Its closeout also owns the bounded shared-contract hardening identified while reconciling the completed Graham implementation with its design record. That work does not change Step 2.3's historical completion status, but it must finish before Step 2.5 freezes the strategy contracts into Golden fixtures.

#### 4.4.1 Product-policy checkpoint

The phrase “FCF (free cash flow) and earnings growth” is sufficient to select the strategy direction but does not yet lock every investor-facing metric.

Implementation begins with reconnaissance only. Before production coding proceeds, explicitly resolve or approve the baseline for:

- historical actuals versus forward/analyst estimates;
- FCF amount/trend versus P/FCF or FCF yield;
- preferred historical horizon;
- whether the user wants a pass/fail rule or transparent metrics/trends; and
- whether TTM support is required initially.

The product-policy checkpoint is resolved by the reviewed governing design. The approved baseline is:

- completed annual actuals with project-defined `FCF = operating cash flow - normalized capital expenditures`;
- annual diluted EPS and FCF CAGR over one common contiguous span;
- automatic longest-available selection that prefers five elapsed years, then four, then three, while an explicitly requested horizon is strict;
- an explicit `PASS`, `FAIL`, or `INDETERMINATE` historical screen plus a descriptive relationship classification;
- optional FCF yield as supporting information only, with no yield threshold and no effect on classification;
- optional FY1/FY2 analyst-consensus EPS context under `display_only`, `confirmation`, or explicit `hard_gate` policy, subject to an approved provider mapping;
- no TTM substitution for the required annual historical series;
- no P/FCF threshold, DCF, peer ranking, composite score, or investment recommendation.

The exact financial, typed-result, versioning, and presentation semantics are normative in the governing Step 2.4 design. Unsupported optional provider capabilities remain explicitly unavailable; they are not guessed or silently substituted.

The focused product-policy follow-up is resolved: the stand-alone Free Cash Flow & Earnings Growth analysis shows both total-company-FCF CAGR and FCF-per-diluted-share CAGR. Total-company-FCF CAGR controls `PASS`/`FAIL` by default; an explicit typed policy and CLI switch may select FCF/share CAGR instead. Because FCF/share incorporates dilution and repurchases, this is a versioned strategy-contract extension requiring weighted-average diluted-share evidence, split/share-class compatibility, provenance, fixtures, and schema evolution. It is not a presentation-only toggle and does not introduce the later composite screener.

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

An elapsed period of three, four, or five years requires four, five, or six compatible completed fiscal-year observations respectively. Automatic selection prefers five elapsed years and falls back to four and then three; an explicitly requested period never falls back. Beginning and ending values must be strictly positive, and a sign change within the selected span makes CAGR unavailable rather than producing NaN, infinity, complex values, absolute-value reinterpretation, or a fabricated fallback.

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

Slice C1 demonstrated a concrete new-strategy incompatibility in the shared vocabulary: operating cash flow and capital expenditures are general financial-statement facts, while the shared cache accepts provider- or derived-origin `ResolvedInput` objects and does not enforce a valuation-only domain. C1R therefore performs one deliberate naming migration before C2 adds another consumer. Provider-facing `Valuation*` fact contracts become `Financial*` fact contracts, and cache-facing `ValuationCache*` contracts become `ResolvedInputCache*` contracts. Numeric `value` fields retain that name because they denote a fact's numeric payload, not a company valuation.

The migration changes vocabulary, imports, and documentation without changing provider, resolution, cache, or financial semantics. Competing permanent aliases are never retained unless review identifies a concrete external compatibility requirement. Pass focused Graham and FCF regressions and the complete repository quality gate, then stop for human review before C2.

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

Fixtures must provide at least six compatible completed fiscal years and cover:

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
--forward-policy POLICY
--as-of DATE_OR_TIMESTAMP
--data-provider PROVIDER_ID
--no-cache
--details
--diagnostics
--json
--chart
```

Omitting `--growth-years` selects the approved longest-available 5 → 4 → 3 policy. An explicit 3, 4, or 5 is strict. `--forward-policy` defaults to `display-only`; `--chart`, if implemented, follows the presentation-mode compatibility rules in the governing design.

Do not add ambiguous unperiodized repeated-value override flags merely to imitate Graham. If series overrides later prove necessary, use an explicit period-tagged representation.

Reuse the Step 2.3 progressive-disclosure grammar:

1. **Default concise:** latest completed period, latest FCF, diluted-EPS growth, FCF growth, descriptive trend, source/freshness, warnings, method limitation.
2. **`--details`:** annual CFO, normalized CapEx, FCF, diluted-EPS series, periods, provider concepts, availability, derivation lineage, growth endpoints.
3. **`--diagnostics`:** cache/provider/selection/derivation behavior and classified unavailable/error outcomes.
4. **`--json`:** stable machine-readable strategy result/provenance; unavailable growth metrics are JSON `null`, never `NaN`.

#### 4.4.9 Implementation sequence

Implement and review Step 2.4 in bounded slices:

1. **A — reconnaissance and initial product-policy lock:** inspect post-Step-2.3 reuse seams, provider evidence candidates, likely files, and resolve the initial product-policy checkpoint. Make no production changes. Stop for human review. The later FCF/share amendment is implemented in E1–E3 rather than rewriting the completed Slice A/B history.
2. **B — pure FCF/growth math and typed result semantics:** implement deterministic arithmetic/results and focused tests only.
3. **C1 — financial-fact contracts and period-aware cache:** minimally extend the shared fact/provenance contracts for annual operating cash flow, capital expenditures, and period-scoped cache entries. Stop for human review.
4. **C1R — deliberate shared-boundary naming migration:** before another strategy couples to the Step 2.3 names, rename the provider-facing `Valuation*` fact vocabulary to `Financial*` and the cache-facing `ValuationCache*` vocabulary to `ResolvedInputCache*`. Reconcile production code, tests, type annotations, documentation, and imports in one bounded migration; preserve behavior and stop for human review after the complete gate passes.
5. **C2 — annual-series resolution and fixtures:** add period-aligned FCF derivation plus deterministic multi-year fixtures on the renamed shared contracts.
6. **D0 — provider-evidence checkpoint:** inspect authoritative provider documentation and representative payloads for exact concepts, financial meaning, signs, units, periods, availability timestamps, restatements, duplicates, and security identity. Record each supported mapping and each explicitly unsupported shape. Make no production changes and stop for human approval.
7. **D1 — operating-cash-flow adapter:** implement and test only the approved operating-cash-flow mapping from D0. Stop for human review.
8. **D2 — capital-expenditure adapter:** implement and test only the approved capital-expenditure mapping and sign normalization from D0. Stop for human review.
9. **D3 — annual diluted-EPS reconciliation:** implement and test only the approved annual diluted-EPS compatibility and selection rules from D0. Stop for human review.
10. **D4 — production composition:** compose the approved provider capabilities through the C2 annual-series resolver, preserving typed unavailability and provenance. Stop for human review.
11. **D5 — integration closeout:** add bounded provider regressions, run the complete repository gate, and reconcile the provider mapping record with the implemented behavior. Unsupported evidence shapes remain explicitly unavailable.
12. **E — initial investor CLI and presentation:** add direct execution plus concise/details/diagnostics/JSON rendering and representative live validation after deterministic gates are green. The initial total-FCF implementation is complete and approved.
13. **E1 — FCF/share evidence and contract checkpoint:** inspect authoritative provider evidence for annual weighted-average diluted shares, split/share-class treatment, restatements, units, periods, availability, and compatibility with the FCF observation. Freeze the versioned policy/result contract and supported mappings; make no production changes and stop for human approval. Complete and approved.
14. **E2 — FCF/share calculation and data implementation:** add period-compatible diluted-share resolution, deterministic FCF/share derivation, both CAGRs, the typed classification-basis policy, method/schema-version evolution, and focused fixtures/tests. Default classification remains total-company FCF; selecting FCF/share makes missing or nonmeaningful FCF/share evidence `INDETERMINATE`. Complete and approved.
15. **E3 — FCF/share CLI and presentation amendment:** add the explicit classification-basis CLI switch and render both FCF growth measures in concise/details/diagnostics/JSON output. Presenters consume the typed result and never reclassify it. Add representative live validation after deterministic gates are green. Complete and approved.
16. **F — pre-Golden shared-contract hardening:** complete the bounded work in Section 4.4.10 across Graham and any shared seams used by the new strategy, and execute the Momentum strategy modernization: strict point-in-time filtering, `MetricResult` refactoring, `MarketDataProvider` provenance, `MomentumPolicy`, and diagnostic traces. Complete and approved. F does not own the strategy-specific FCF/share extension in E1–E3 or the later F-1 identity slice.
17. **F-1 — shared security identity and investor display:** complete and approved on 2026-08-30. The bounded work in Section 4.4.11 makes Momentum, both Graham methods, and FCF & Earnings Growth retain and display best-effort security identity without treating a ticker as permanent identity.
18. **G — documentation and full gate:** complete and approved on 2026-08-30. Documentation was synchronized, the complete repository gate passed, and the full Step 2.4/hardening/identity diff received explicit human completion approval before Step 2.5.

#### 4.4.10 Pre-Golden shared-contract hardening

A post-implementation audit found several places where the completed Graham behavior is safe but less explicit or uniform than the contracts should be before benchmark cases are frozen. Implement these as a bounded correction work unit during Step 2.4 closeout; do not create another Graham design document or reopen the completed Step 2.3 work record.

Required work:

1. **Result invariants:** enforce in the public method-result models that `status = ok` requires a non-null method value and a null failure reason, while every non-success status requires a null method value and a non-empty reason. Verify calculators, presenters, JSON, and runtime consumers against the same invariant.
2. **Investor-facing status language:** provide an exhaustive mapping from every calculation status to plain English in concise and detailed output. Machine enum spellings remain appropriate for JSON and diagnostics but must not leak accidentally into investor-facing prose.
3. **One typed failure boundary:** route required-input, provider, and ticker-verification failures through the same typed result/presentation boundary used by successful analyses. Preserve concise friendly error wording as a rendering decision, not as an untyped alternate execution path.
4. **Quote semantics:** preserve the distinction between an invalid explicit quote override, which is a fatal input error, and an unavailable optional provider quote, which suppresses only comparison fields. Normalize a provider quote lacking required currency as `input_unavailable` across production adapters, document that an explicit quote override may omit currency, and keep cross-currency quotes visible while suppressing the price relationship.
5. **Earnings compatibility:** define an explicit, evidence-based compatibility predicate for annual earnings observations, including provider concept, diluted/basic basis, share class when the source exposes it, currency, units, fiscal periods, restatements, and split treatment. Retain the required evidence in provenance. If compatibility cannot be established, return unavailable rather than guessing or silently normalizing.
6. **Supported routing:** make the explicit Massive Graham Number combination deliberate and tested: trailing-twelve-month Massive earnings plus a book-value-per-share override may use a Massive quote. Continue to reject unsupported provider/basis combinations before provider work begins.
7. **Presentation contract:** lock the required concise line order, status/reason behavior, exact method limitations, and deliberate warning selection and order. Explicitly cover the current treatment of expected-growth and current-price overrides rather than relying on incidental presenter implementation.
8. **Regression evidence:** add focused tests for every item above, including successful-result reason validation, all status labels, concise and detailed failure paths, quote currency omitted from an override, missing-currency provider quotes, Massive Graham Number routing, exact limitation strings, and warning order.

##### Momentum Strategy Modernization

The same pre-Golden gate also remediates the outstanding technical-debt and design-gap items in the existing Momentum strategy so its contracts are as explicit and uniform as the Graham and Free Cash Flow & Earnings Growth contracts before Step 2.5 freezes them into Golden fixtures.

Required work:

1. **Strict Point-in-Time Truncation:** enforce historical `bar_timestamp <= effective_as_of` filtering inside `MomentumInputResolver` before invoking any pure calculation function, preventing look-ahead leakage in backtests.
2. **Standard `MetricResult` Migration:** refactor `sma_50`, `sma_200`, and `rsi_14` from raw `float | None` values into standard `MetricResult` structures. On insufficient history, populate `status = unavailable` and `reason_code = insufficient_history` rather than returning silent nulls.
3. **Provider & Provenance Standardization:** migrate data fetching from the legacy `BaseDataClient` to `MarketDataProvider`, wrapping price observations in `ResolvedInput` containers that preserve provider identity, retrieval timestamps, and currency attributes.
4. **Configurable `MomentumPolicy`:** introduce a typed `MomentumPolicy` dataclass as the home for momentum window/period defaults and support the CLI parameters `--short-window`, `--long-window`, and `--rsi-period`.
5. **Diagnostic Trace Coverage:** integrate `ResolutionTrace` logging across data fetch, series filtering, and calculation execution so Momentum resolutions are as observable as the other strategies.

This work may minimally revise shared types or presenter seams used by Free Cash Flow & Earnings Growth when necessary for one coherent contract. It must not introduce a generic all-strategy result object, broaden provider scope without evidence, or change either Graham formula.

The hardening gate is complete only when the Graham design describes the resulting implementation exactly, relevant shared documentation agrees, focused regression tests and the full repository gate pass, and the correction diff receives explicit human approval. Step 2.5 must not begin before that approval.

#### 4.4.11 Slice F-1 — Shared security identity and investor display

Ticker symbols are venue-scoped, time-sensitive display identifiers and may be reused after delisting. They must not be treated as permanent issuer or instrument identity. Before Golden fixtures freeze the three strategy presentation contracts, implement one bounded cross-strategy identity slice with these requirements:

1. **Narrow identity contract:** define a provider-neutral immutable security-identity value with normalized ticker, optional instrument name, optional listing venue, optional issuer identifier, optional instrument/listing identifier, provider identity, and timezone-aware resolution time. Use `instrument_name` or `security_name`, not `company_name`, because Momentum supports non-company instruments such as cryptocurrency pairs. Do not introduce a generic strategy-result hierarchy.
2. **Best-effort provider capability:** obtain identity only from retained provider evidence or a narrow injected identity-provider capability. Preserve usable SEC ticker-title or Company Facts entity-name evidence and supported Yahoo/provider metadata where available. Do not infer a name from a ticker, make duplicate lookups within one run, or broaden numeric `ProviderFact` merely to carry display metadata.
3. **Fail-open semantics:** identity absence or lookup failure must never invalidate, downgrade, or reclassify an otherwise valid analysis. Retain the ticker and render it alone when the name is unavailable. Identity resolution failure may appear in diagnostics but is not an investor-facing financial warning.
4. **All-strategy presentation:** Momentum, Graham Number, Graham Growth Value, and FCF & Earnings Growth use the same heading grammar when a name is available: `Instrument Name (TICKER) — Analysis`; otherwise use `TICKER — Analysis`. Preserve official name capitalization and punctuation after whitespace normalization.
5. **Machine-readable output:** expose the resolved identity consistently in each strategy's JSON presentation contract, using explicit nulls for unavailable optional fields. Review and deliberately record any schema-version increment rather than assuming that an added field is invisible to consumers.
6. **Time semantics:** treat a presently resolved name as current descriptive metadata unless provider evidence establishes an historical effective interval. Never imply that a current lookup proves the name or listing identity at a historical analysis `as_of`.
7. **Persistence handoff:** define the Step 3.4 `AnalysisRun` handoff now: persist the identity snapshot used by the completed run, including `resolved_at`, rather than re-resolving its ticker when historical output is viewed. Later persistence may enrich stable issuer/instrument identifiers but must not silently relabel an old run after ticker reuse.
8. **Regression evidence:** add deterministic tests for available and unavailable names, non-company instruments, lookup failure, whitespace normalization, all presentation modes and all three strategies, JSON null/version behavior, no duplicate lookup per run, and preservation of otherwise successful analysis semantics. Deterministic tests make no live provider calls.

F-1 is presentation and identity-provenance work, not financial calculation work. It must not change formulas, classifications, data eligibility, or existing ticker-verification behavior. Stop for focused human review after focused tests and the complete repository quality gate pass.

**Planning approval:** Approved on 2026-08-29.<br/>
**Implementation approval:** The completed F-1 implementation and focused gate were approved on 2026-08-30. Slice G owns final documentation synchronization, the complete repository gate, and Step 2.4 completion review.

**Post-closeout P1 refinement:** The concrete FLSW defect recorded in Section 4.5.0 supersedes only F-1's preservation of existing ticker-verification behavior and its assumption that identity metadata can never participate in applicability. Lookup absence/failure remains fail-open and display-only; affirmative provider-backed instrument-kind evidence may establish strategy-specific `not_applicable` without changing financial formulas.

#### 4.4.12 Non-goals

Step 2.4 does **not** include:

- discounted-cash-flow valuation;
- terminal-value modeling;
- cost-of-capital estimation;
- LLM-generated growth forecasts or unapproved provider-consensus mappings;
- P/FCF or P/CF as required core metrics unless separately approved after the product-policy checkpoint;
- a broad named-investor methodology;
- arbitrary composite scoring/ranking;
- ROIC, incremental ROIC, WACC, reinvestment-opportunity analysis, estimate-revision history, management-guidance analysis, historical valuation bands, growth-adjusted cash-flow valuation, leverage/earnings-stability scoring, or universe normalization;
- investment recommendations;
- Golden Suite/evaluator implementation;
- durable SQLite persistence/migrations;
- watchlists or Analysis Run persistence;
- a generic strategy/plugin registry;
- unrelated refactoring.

#### 4.4.13 Acceptance criteria

- [x] The product-policy checkpoint resolved in the governing design has been explicitly approved before Slice B begins.
- [x] The strategy is named and typed independently from Momentum and Graham.
- [x] The canonical initial FCF definition is explicit and tested.
- [x] CapEx provider sign conventions are normalized transparently.
- [x] Annual CFO and CapEx are paired only across compatible fiscal periods.
- [x] Annual diluted-EPS growth uses an explicit documented basis.
- [x] Both total-company-FCF CAGR and FCF-per-diluted-share CAGR are returned and shown; weighted-average diluted shares are period-compatible and retain provenance.
- [x] Total-company-FCF CAGR controls classification by default, while the explicit FCF/share policy/CLI selection controls classification deterministically and produces `INDETERMINATE` when its required evidence is unavailable or nonmeaningful.
- [x] Three-, four-, and five-year CAGR use four, five, and six completed annual observations respectively; automatic selection and strict explicit-horizon behavior are tested.
- [x] `PASS`, `FAIL`, and `INDETERMINATE` classification follows the governing design and remains distinct from software execution status.
- [x] Optional FCF yield cannot alter classification, and optional forward evidence follows the selected policy without guessed provider data.
- [x] Negative/zero values are represented truthfully without NaN/infinity or fabricated fallbacks.
- [x] Strict `as_of` prevents look-ahead.
- [x] Derived FCF retains full component lineage.
- [x] The Step 2.3 provider/cache/resolver/provenance architecture is reused or minimally extended rather than duplicated.
- [x] Deterministic fixtures cover success, missing data, period mismatch, negative/zero growth, restatement, and historical-boundary cases.
- [x] A representative supported production ticker can run the analysis without manual financial-statement arithmetic.
- [x] Concise/details/diagnostics/JSON output follows the established investor-facing grammar.
- [x] Momentum, both Graham methods, and FCF & Earnings Growth retain and display best-effort security identity under Section 4.4.11, fall back cleanly to ticker-only output, and do not allow identity lookup failure to alter analysis semantics.
- [x] Machine-readable outputs expose explicit nullable identity metadata with deliberate schema-version handling, and the Step 3.4 handoff requires persistence of the run-time identity snapshot rather than later ticker re-resolution.
- [x] Automated tests make no live network or LLM calls.
- [x] Full repository quality gates pass.
- [x] Documentation matches implemented semantics.
- [x] The pre-Golden shared-contract hardening in Section 4.4.10 is implemented, tested, documented, and explicitly approved.
- [x] Momentum strict point-in-time filtering enforces `bar_timestamp <= effective_as_of` inside `MomentumInputResolver` before calculation and is covered by deterministic look-ahead tests.
- [x] `sma_50`, `sma_200`, and `rsi_14` are returned as standard `MetricResult` structures, reporting `status = unavailable` and `reason_code = insufficient_history` on insufficient history.
- [x] Momentum data fetching runs through `MarketDataProvider` with price observations wrapped in `ResolvedInput` containers retaining provider identity, retrieval timestamps, and currency attributes.
- [x] `MomentumPolicy` is a typed dataclass and the `--short-window`, `--long-window`, and `--rsi-period` CLI parameters are implemented and tested.
- [x] Momentum resolution, series filtering, and calculation execution are covered by `ResolutionTrace` diagnostic logging.
- [x] The final Step 2.4 diff receives explicit human approval.

**Definition of done:** Satisfied on 2026-08-30. One useful, auditable Free Cash Flow & Earnings Growth strategy runs through the existing architecture with explicit historical financial semantics, reproducible provenance/`as_of` behavior, deterministic fixture coverage, a viable production path, coherent investor presentation, green repository gates, and explicit human approval. The pre-Golden shared-contract hardening, F-1 identity work, and Slice G closeout are complete and approved. Step 2.5 may proceed.

---

### 4.5 Step 2.5 – Golden-Test Suite & Strategy Evaluation

**Status:** Complete and approved on 2026-08-31. Verification and the final decision are recorded in the [Step 2.5 Closeout Verification Record](step-2.5/STEP_2_5_CLOSEOUT_RECORD.md).<br/>
**Goal**<br/>
Establish a deterministic, fixture-backed benchmark that exercises the approved v0.2 set of materially different analytical strategies and separates strategy/tool-selection correctness from deterministic numerical correctness.

Step 2.5 consumes the stable strategy and data foundations established in Steps 2.3–2.4, including the approved pre-Golden shared-contract hardening gate. It must not begin before that gate or redesign those foundations unless implementation evidence reveals a concrete defect.

The live FLSW review on 2026-08-30 revealed one such defect: Momentum identified the valid ETF, while Graham conflated unavailable company facts with a possibly invalid ticker and FCF Growth could not retain the resolved instrument name. The approved P1 correction below must close this bounded contract/applicability gap before Golden Suite model work begins.

The initial benchmark targets:

1. **Momentum analysis** — the existing historical-price/SMA strategy.
2. **Graham Number analysis** — the default defensive screening-ceiling method.
3. **Graham growth-value analysis** — the explicit forecast-dependent secondary method.
4. **Free Cash Flow & Earnings Growth analysis** — the Step 2.4 historical cash-flow/growth strategy.

This is the empirical test of the architectural objective established in Steps 2.3–2.4: financial analysis must not be implicitly synonymous with one analytical pattern.


#### 4.5.0 P1 — Pre-Golden instrument applicability hardening

**Status:** Complete and approved. P1-A through P1-C were accepted before the typed Golden Case implementation began.

**Goal:** Make the Step 2.4 identity, status, provider-composition, and presentation seams an adequate long-lived basis for known non-company instruments without adding persistence or an ETF aggregate strategy.

P1 is a concrete-defect correction, not a reopening of the approved financial formulas. Implement it as one bounded production slice with these requirements:

1. **Provider-evidence checkpoint:** inspect authoritative provider documentation and representative deterministic payloads before mapping provider instrument classifications. Record the initial normalized vocabulary and exact supported mappings. The minimum approved capability must distinguish a provider-confirmed ETF from an instrument that is not confirmed to be an ETF; do not infer kind from a ticker or instrument name.
2. **Identity/profile evidence:** preserve the immutable one-provider `SecurityIdentity`, add separate immutable normalized/raw instrument-kind evidence with its own provider and timezone-aware resolution time, and compose both without rewriting field-level provenance. Do not broaden numeric `ProviderFact` to carry descriptive metadata. The exact P1-A proposal is recorded in [`STEP_2_5_P1_INSTRUMENT_APPLICABILITY_MAPPING_RECORD.md`](step-2.5/STEP_2_5_P1_INSTRUMENT_APPLICABILITY_MAPPING_RECORD.md).
3. **Fail-open classification:** missing, unsupported, or failed identity/kind resolution remains unknown and must not invalidate or downgrade an otherwise usable analysis. Only affirmative provider-backed kind evidence may control strategy applicability. Unknown kind must continue through the existing data-resolution path.
4. **Narrow fallback composition:** permit one analysis run to consult an ordered, explicitly injected identity/profile candidate list, using retained strategy-provider evidence first and Yahoo only when the required name or kind remains unresolved. Query each candidate at most once per run, retain the winning provider provenance, and do not introduce a broad provider registry or hidden live fallback in deterministic execution.
5. **Strategy-specific applicability:** Momentum continues to support ETFs. A provider-confirmed ETF is `not_applicable` to both Graham methods and to the existing company-level Free Cash Flow & Earnings Growth strategy. This is a valid completed applicability result, not `input_unavailable`, `provider_error`, an invalid ticker, or an automatic request to run a future aggregate strategy.
6. **Typed-result preservation:** represent `not_applicable` through each strategy's existing native typed status/result boundary. Do not add a generic strategy-result hierarchy. Keep calculation formulas unchanged and do not manufacture company facts for an ETF.
7. **Investor presentation:** every concise/details/diagnostics/JSON path retains the shared `Instrument Name (TICKER) — Analysis` heading when identity is available, including unsuccessful and `not_applicable` Graham paths. Ordinary input unavailability or provider failure must not tell the user to verify the ticker unless affirmative evidence establishes an invalid symbol. A known ETF explanation must name the selected company-level method and why it does not apply.
8. **Process status:** a successfully determined `not_applicable` analysis is a normal domain outcome and returns a successful direct-CLI process status. Invalid arguments, unresolved required inputs, and provider/execution failures retain non-zero process behavior.
9. **Deterministic regression evidence:** add fixture-backed tests for a known ETF, known supported instrument, unknown kind, provider failure, ordered fallback, winning provenance, no duplicate candidate lookup, all affected presentation modes, native typed/JSON status, unchanged Momentum behavior, and CLI/tool-handler consistency. Deterministic tests make no live provider calls.
10. **Review gate:** run focused Ruff, formatting, strict mypy, and tests, then the complete repository quality gate. Stop for human review before Slice A1 or any Golden case implementation begins.

**P1 exclusions:** durable or cross-process metadata caching, SQLite/Alembic, TTL/invalidation policy, ETF holdings ingestion, constituent aggregation, automatic substitution of another strategy, changes to Graham/FCF mathematics, and unrelated provider expansion. Those deferred concerns belong to P2 after Step 3.1.

#### 4.5.1 Implementation guardrails

These guardrails apply to every Step 2.5 implementer. The earlier Cline experiment was terminated after repeated completion claims contradicted repository state; Codex owns P1 and the remaining implementation, with the human review gates unchanged.

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
- known-ETF applicability case proving Momentum remains applicable while both Graham methods and company-level FCF Growth report `not_applicable` without treating the ticker as invalid;
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

The formal bounded handoff boundaries, owned artifacts, intermediate review points, and current handoff are recorded in the [Step 2.5 Golden Suite Slice Plan](step-2.5/STEP_2_5_GOLDEN_SUITE_SLICE_PLAN.md). That document decomposes this governing sequence without changing its order or acceptance criteria.

1. Implement P1, run the complete repository gate, and stop for explicit human approval of the corrected production contracts.
2. Inspect and accept the stable Steps 2.3–2.4 plus P1 strategy/data/applicability contracts; do not redesign them speculatively.
3. Define the typed Golden Case model.
4. Define independently verified expected values and tolerance rules.
5. Implement strategy/tool-selection evaluation.
6. Implement numerical evaluation.
7. Implement case-level aggregation and pass-rate calculation.
8. Implement machine-readable reporting.
9. Implement deterministic/no-LLM harness tests.
10. Add the evaluator regression/self-test.
11. Add the minimum heterogeneous case set.
12. Run the minimum deterministic suite and **stop for review**.
13. Perform only Gate M-directed correction or expansion, then rerun Gate M; skip this item only when Gate M approves the minimum unchanged.
14. Add optional real-local-Ollama evaluation.
15. Add the documented CLI.
16. Update evaluation documentation.
17. Run Ruff, formatting checks, `mypy --strict`, and pytest.
18. Record deterministic and, when available, empirical model results separately.

#### 4.5.19 Non-goals

Step 2.5 does **not** include:

- SQLite persistence or Alembic;
- production cache implementation;
- analytical strategies beyond the approved v0.2 set;
- durable instrument-profile caching or ETF constituent aggregation (deferred to P2 after Step 3.1);
- broad provider abstraction;
- UI/dashboard work;
- autonomous planning changes;
- model fine-tuning;
- private chain-of-thought capture;
- cloud LLM evaluation;
- unrelated production refactoring.

#### 4.5.20 Acceptance criteria

Checked items below are evidenced by the reviewed implementation and Slice K
closeout record. The human approved Step 2.5 on 2026-08-31.

- [x] A reproducible fixture-backed Golden Suite exercises Momentum, the Graham Number, the Graham growth-value method, and Free Cash Flow & Earnings Growth.
- [x] P1 is approved before Golden models/cases are implemented; a provider-confirmed ETF is `not_applicable` to both Graham methods and company-level FCF Growth, remains applicable to Momentum, retains its identity when available, and is not described as an invalid ticker.
- [x] No live market-data access is required for deterministic suite execution.
- [x] Existing production orchestration/tool-dispatch is reused as far as practical.
- [x] Expected numerical values are independently verified.
- [x] Strategy/tool-selection correctness is evaluated separately from numerical correctness.
- [x] Deterministic numerical evaluation does not depend on LLM prose.
- [x] A minimum heterogeneous case set works before expansion.
- [x] The default three-year-average EPS basis, explicit TTM variation, `not_applicable` behavior, and missing-current-price behavior are covered by Graham cases.
- [x] At least one case verifies Graham method-selection correctness independently of broad strategy selection.
- [x] Straightforward, insufficient/nonmeaningful-growth, and period/`as_of` FCF-growth cases are covered.
- [x] At least one case materially discriminates correct strategy selection from a plausible wrong strategy.
- [x] Machine-readable reporting distinguishes component and overall failures.
- [x] The ≥90% target is defined and reported without weakening criteria.
- [x] Strategy-selection accuracy is reported independently and is not artificially forced to ≥90%.
- [x] An evaluator self-test detects an intentionally incorrect result.
- [x] Deterministic/no-LLM mode is documented.
- [x] Optional real-local-Ollama evaluation is documented separately.
- [x] CLI execution and non-zero failure status work.
- [x] `docs/EVALUATIONS.md` documents the implemented Slice J operator interface, report contract, failure interpretation, and maintenance workflow.
- [x] Step 3.1 can replace fixture-backed data sources with production persistence without changing Golden case definitions.
- [x] Ruff, formatting, `mypy --strict`, and pytest pass.
- [x] Actual measured deterministic benchmark results are recorded honestly; empirical model selection remains unmeasured.

**Definition of done:** Step 2.5 is complete when the repository contains a reproducible fixture-backed benchmark that exercises the approved heterogeneous v0.2 strategy set, distinguishes strategy/method-selection failures from deterministic numerical failures, produces an auditable machine-readable report, and remains decoupled from production persistence.

---

### 4.5A Step 2.5A – SEC EDGAR Foreign-Private-Issuer Annual-Filing Coverage

**Status:** complete and approved on 2026-09-01.<br/>
**Governing records:** [SEC EDGAR FPI / IFRS D0 Mapping Record](step-2.5a/SEC_EDGAR_FPI_IFRS_D0_MAPPING_RECORD.md), [SEC EDGAR FPI / IFRS Slice Plan](step-2.5a/SEC_EDGAR_FPI_IFRS_SLICE_PLAN.md), [Step 2.5A D0 Evidence Freeze and Implementation Handoff](step-2.5a/STEP_2_5A_D0_EVIDENCE_FREEZE.md), and [Step 2.5A A0 Identity/Security-Unit Boundary Review](step-2.5a/STEP_2_5A_A0_REVIEW.md)<br/>
**Goal**<br/>
Extend the existing SEC annual financial-fact adapter to a narrow, evidence-backed foreign-private-issuer surface without weakening exact-concept, annual-period, `as_of`, currency, restatement, provenance, or security-unit requirements.

The approved first implementation has two provider increments:

1. accept `20-F`, `20-F/A`, `40-F`, and `40-F/A` for already-approved US-GAAP annual **duration** concepts while leaving balance-sheet/instant forms unchanged; and
2. map exact IFRS annual duration concepts for diluted EPS, adjusted weighted-average shares, operating cash flow, and physical-PP&E capital expenditure.

One immutable analysis-scoped SEC snapshot must supply all selected facts and accession availability evidence. Accounting taxonomy is selected from the latest eligible annual accession at effective `as_of`, not from any namespace that happened to occur in the issuer's lifetime history. Requested spans that cross an unproved taxonomy/accounting transition are unavailable.

Foreign security units are an independent compatibility boundary. Issuer-level FCF facts may resolve when supported, but per-share or quote comparisons require affirmative ordinary-share / quoted-unit compatibility. The first implementation is limited to proven 1:1 shapes. ADR/ADS ratio conversion and currency conversion are not approved.

IFRS book value per common/ordinary share is deferred. Missing preferred-share evidence is never zero, generic outstanding-share facts do not prove an ordinary-share denominator, and Company Facts' entity-level surface does not supply the dimensional share-class evidence required for a safe IFRS BVPS derivation.

**Implementation order**

1. freeze minimal deterministic evidence and confirm the exact owned files;
2. correct the identity/security-unit boundary so multi-ticker CIKs do not erase
   issuer-level facts while per-share use remains fail-closed, then stop for
   review;
3. add US-GAAP foreign annual forms for duration fields only and stop for review;
4. add request-scoped snapshot and latest-accession taxonomy selection and stop for review;
5. add the four exact IFRS duration mappings and negative boundaries and stop for review;
6. complete the narrow security-unit compatibility predicate and stop for review;
7. version and extend the Golden Suite only after the provider/resolver behavior is approved;
8. update support documentation, run the complete repository and Golden gates, and stop for final approval.

D0 found that the existing multi-ticker guard blocks the planned ASML, SAP, and
NVO cases and erases issuer-level fields contrary to the approved unit boundary.
It also confirmed that snapshot reuse spans both analysis resolvers. Gate A
approved bounded A0 and the exact B1-A ownership on 2026-08-31. A0 must stop for
review before A1.

A0 is implemented and verified at that stop. Exact ticker-to-CIK resolution and
payload-CIK validation are unchanged; OCF and CapEx no longer fail merely
because the resolved CIK has multiple ticker rows, while EPS and diluted
weighted-average shares remain fail-closed. The complete repository gate passed
1,225 tests at 87% reported coverage. A1 is not started.

**Acceptance criteria**

- [x] Step 2.5 is complete and approved before implementation begins.
- [x] D0 evidence fragments are minimized, sourced, dated, checksummed, and
  covered by an exact deterministic test matrix and focused baseline.
- [x] Existing US-GAAP duration concepts accept the approved foreign annual forms without broadening balance-sheet/instant forms.
- [x] Exact IFRS EPS, diluted-share, OCF, and physical-PP&E CapEx mappings preserve units, sign, period, availability, currency, and provenance.
- [x] One immutable SEC snapshot supplies all fields in one analysis.
- [x] Latest-eligible-accession taxonomy selection and cross-regime rejection are deterministic and `as_of` safe.
- [x] Missing exact concepts, ambiguous evidence, and unknown security-unit compatibility remain explicitly unavailable.
- [x] IFRS BVPS, preferred-zero inference, ADR/ADS conversion, currency conversion, and custom extensions remain unsupported.
- [x] Existing case IDs and historical Golden fixtures are preserved; additions are deliberately versioned.
- [x] Focused checks, the complete repository gate, and the canonical Golden Suite pass without live provider or LLM calls.
- [x] The final diff receives explicit human approval before Step 2.6.

---

### 4.6 Step 2.6 – Circuit Breakers & Timeout Limits

**Status:** The [Step 2.6 Reliability Limits Slice Plan](step-2.6/STEP_2_6_RELIABILITY_SLICE_PLAN.md)
was approved on 2026-09-02. Slices A and B, the Gate C native Ollama
remediation, deterministic verification, and repeat optional LAN smoke were
approved on 2026-09-03. Step 2.6 is complete.

**Goal**<br/>
Hard execution caps, wall-clock bounds, and error thresholds that prevent unbounded loops or runaway token spend.

**Implementation outline**
1. Centralise limits in the existing Settings / config model (max steps, max transient retries, per-step and overall wall-clock timeouts, max consecutive schema violations, etc.).
2. Implement a small `CircuitBreaker` (or equivalent) that the orchestrator consults before each planning step and after each tool/LLM call.
3. On threshold breach: halt cleanly, emit a human-readable diagnostic that includes the `run_id` and last few trajectory events, and return a structured failure result to the CLI. Also emit RECOVERY_ATTEMPTED if not already done in 2.1.
4. Unit tests covering: normal completion, max-steps hit, timeout hit, repeated schema-violation trip.

**Acceptance criteria**
- [x] Defaults are documented and match Master Plan intent (e.g. max steps ≈ 10, max retries ≈ 3).
- [x] Breach always produces a clear diagnostic; never an unhandled exception.
- [x] Limits are configurable without code changes.

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

### 4.7A P2 – Durable Instrument Profiles & ETF Aggregate FCF Growth (Post–Step 3.1)

**Status:** Planned and explicitly deferred until Step 3.1 is implemented and approved. Its exact placement relative to Steps 3.2–3.4 must be reviewed after the Step 3.1 schema/repository boundary is concrete; this section does not authorize implementation during Step 2.5 or Step 3.1.

**Goal:** Replace repeated live descriptive/classification lookups with durable, time-aware instrument profiles and add a distinct look-through FCF-growth strategy for ETFs without changing the meaning of the existing company-level strategy.

**Required planning and implementation work:**

1. Persist normalized instrument kind, raw provider classification, name, venue, stable identifiers where available, provider provenance, retrieval/resolution time, and explicit freshness/expiry metadata behind a narrow repository/cache contract. Ticker alone is not a permanent identity or sufficient cache key.
2. Define cache precedence, TTL/invalidation, refresh, provider disagreement, ticker-reuse, and historical-snapshot rules. Step 3.4 Analysis Runs retain the exact identity/profile snapshot used at execution and never relabel a historical run from mutable current metadata.
3. Complete a separate provider-evidence and product-policy checkpoint for ETF holdings: provider/licensing constraints, holdings effective dates, weights, cash/derivatives, duplicate exposure, constituent identifiers, currency conversion, missing/stale constituents, coverage thresholds, rebalancing, and `as_of` semantics.
4. Implement ETF aggregate FCF Growth as a separate strategy/tool with its own typed configuration, result, method/version identifiers, coverage diagnostics, aggregation semantics, fixtures, and investor limitations. It may reuse approved company-level calculations per constituent, but it must not add ETF branches to or redefine `analyze_fcf_earnings_growth`.
5. Keep selection explicit and auditable. A company-level FCF request for a known ETF remains `not_applicable`; it must not silently invoke the aggregate strategy. Any later convenience routing belongs at the orchestration layer and requires its own reviewed selection behavior.
6. Add deterministic holdings/profile fixtures and independently verified aggregate expectations. Live providers and mutable caches remain excluded from deterministic tests and Golden fixture truth.
7. Revisit Golden coverage only after the strategy's contracts and production behavior pass their own review gate. Add cases through the existing review-directed expansion process rather than changing the original benchmark retrospectively.

**P2 non-goals:** treating an ETF as an operating company, deriving holdings from an instrument name, hiding incomplete constituent coverage, using an LLM for aggregation mathematics, silently substituting the ETF strategy, or coupling strategy calculators directly to SQLite.

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
- An **Analysis Run** is the durable investor-domain record of one requested analysis: `analysis_run_id`, ticker, analysis/method, requested `as_of`, configuration snapshot, status, typed result payload, resolved-input provenance, the security identity/instrument-profile snapshot used by the run, warnings, start/completion times, and calculation/version identifiers. It may reference execution/telemetry identity, but does not overload `RunContext`.
- A **report/view** is a deterministic, explicitly versioned projection of an Analysis Run. v0.2 does not persist a competing canonical report document.
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
3. Add a narrow investor-report projector that consumes only the persisted Analysis Run plus explicit presentation mode/locale/format options. Reuse strategy presentation semantics where practical, but do not regenerate financial calculations merely to view a completed run.
4. Add user-initiated concurrent refresh with bounded worker/concurrency limits and per-job classified status.
5. Persist each completed/failed/unavailable run independently so one ticker/provider failure does not discard other completed work.
6. Preserve reproducibility: `as_of`, config, method version, result, provenance, warnings, and source timestamps travel with the Analysis Run.
7. Give the report projection contract its own explicit version, independent of method and typed result-schema versions. Persist or emit the selected projection version so rendered history is auditable; breaking structural or semantic changes require a new projection version.
8. Keep projection replay pure with respect to external and mutable state: no provider or LLM calls, financial recalculation, current identity lookup, mutable cache reads, or implicit current-clock enrichment. The same stored run, projection version, mode, and explicit locale/format options produce the same semantic output.
9. Retain historical projection implementations or provide an explicit, auditable migration. Never silently reinterpret an old run under a breaking projection contract.
10. Add deterministic tests for create/add/remove/show, refresh fan-out, partial failures, persistence/reload, run-list ordering/filtering, projection-version dispatch, historical projection replay, and view rendering.

**Acceptance criteria**
- [ ] Named watchlists can add/remove tickers and show configured supported analyses.
- [ ] A refresh over multiple ticker/analysis combinations executes with bounded concurrency and independently persisted outcomes.
- [ ] `runs list` exposes completed/unavailable/failed work without requiring recomputation.
- [ ] `runs show` renders the same concise/details/diagnostic/JSON information from the stored Analysis Run.
- [ ] Investor reports expose an explicit projection version that evolves independently from calculation method and typed result-schema versions.
- [ ] Replaying the same stored Analysis Run under the same projection version and explicit rendering options produces the same semantic report without provider/LLM access, financial recalculation, mutable cache reads, identity re-resolution, or current-clock enrichment.
- [ ] Breaking report changes create a new projection version; historical versions remain reproducible or use an explicit audited migration.
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
  ├─ FCF/share evidence + versioned calculation/classification policy
  ├─ investor CLI/presentation
  ├─ pre-Golden Graham/shared-contract hardening
  └─ complete gate + human approval
        │
        ▼
Phase E — Step 2.5 Golden Suite
  ├─ P1 instrument-kind/applicability hardening + review
  └─ heterogeneous selection + deterministic numeric evaluation

Phase F — Step 2.6 reliability limits
  └─ circuit breakers & timeout limits

Phase G — Step 3 production persistence/data quality
  ├─ 3.1 SQLite + durable cache/data/telemetry
  ├─ 3.2 typed repositories
  ├─ 3.3 data quality / invalidation
  └─ P2 durable instrument profiles + separate ETF aggregate FCF strategy
       (exact placement reviewed after 3.1; may depend on 3.2/3.3)
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
2. **Golden Suite data determinism** — Step 2.3 establishes the first shared historical-price, quote, financial-fact, macro-observation, cache, input-resolution, and deterministic fixture contracts; Step 2.4 minimally extends the financial-fact/fixture surface for FCF and earnings growth and closes the bounded shared-contract hardening gate; Step 2.5 consumes the stable approved foundation; Step 3.1 supplies durable production SQLite/cache-backed access.
3. **Telemetry retention** — Configurable via `ProjectSettings`, adhering to existing `logger_util.py` options.
4. **Branch granularity** — Fine-grained branches mapped to coherent implementation units.
5. **Telemetry boundaries** — Telemetry captures observable provider output; missing metrics are stored explicitly as `None` rather than estimated.
6. **Heterogeneous strategy validation** — Momentum and Benjamin Graham are established in Step 2.3; Free Cash Flow & Earnings Growth is added in Step 2.4; Step 2.5 evaluates broad strategy selection, Graham method selection, and deterministic numerical correctness across the approved v0.2 set.
7. **Current quote abstraction** — Current market-price retrieval is a first-class financial-fact capability rather than an implicit one-day historical-data workaround.
8. **Graham result semantics** — The Graham Number is a screening ceiling/maximum indicated price, while the growth formula is a separate forecast-dependent estimate. An unavailable current price produces an unavailable (`None`) margin of safety rather than numeric zero. Positive margin of safety means price is below the selected method's reference value; negative means it exceeds that value.
9. **Strategy-specific determinism** — Each analytical strategy owns its deterministic mathematical implementation and typed configuration/result models. The LLM selects and orchestrates strategies but does not perform the underlying financial calculations.
10. **Step 2.2 enforcement fallback** — Native schema enforcement is preferred when capability is confirmed; prompt-based schema instructions with Pydantic validation/retry provide the configured fallback when native capability is unavailable or unknown; legacy parsing remains the final compatibility fallback.
11. **Graham default method** — `graham_number` is the default CLI method; `graham_growth_value` is explicit and secondary.
12. **Graham Number EPS basis** — Three-year-average fiscal EPS is the default; TTM EPS is an explicitly selected and labeled modern variation.
13. **Graham growth policy** — The growth method requires an explicit expected-growth override. No LLM or silent default supplies growth.
14. **Input resolution** — Provider-resolvable inputs resolve field by field using override → valid cache → provider → unavailable precedence, with provenance and `as_of` semantics preserved. Expected growth is deliberately override-only.
15. **Checkpoint policy** — Reviewed, coherent intermediate checkpoints may be committed/pushed after explicit human approval and a green agreed gate. A checkpoint does not mark the parent step complete or authorize the next step.
16. **Investor-facing presentation** — Default terminal output is concise; `--details`, `--diagnostics`, and `--json` provide progressive disclosure. Strategies share presentation grammar, not a forced internal result model.
17. **Durable product record** — Step 3.4 stores Analysis Runs as the canonical investor-domain history; report formats are views of those runs.
18. **Bounded v0.2 agentic behavior** — User-initiated refresh may fan out concurrently and Light Mode may synthesize completed typed results. Unattended scheduling, proactive monitoring, notifications, and autonomous multi-step research remain v1.0 work.
19. **Step 2.4 roadmap placement** — Free Cash Flow & Earnings Growth is implemented before the Golden Suite to address documented stakeholder requirements and to exercise the Step 2.3 strategy/data/provenance architecture before evaluation infrastructure is frozen.
20. **Step 2.4 baseline interpretation** — The reviewed governing design resolves the product-policy checkpoint: the first version is a historical actuals screen using project-defined FCF, diluted-EPS CAGR, longest-available 5 → 4 → 3-year selection, and explicit `PASS` / `FAIL` / `INDETERMINATE` semantics. FCF yield and FY1/FY2 consensus EPS are optional evidence-gated context under the documented policies; DCF, P/FCF thresholds, peer ranking, broad named-investor methodology, and composite recommendation scoring are not implied.
21. **Pre-Golden hardening placement** — The Graham design-to-implementation reconciliation does not reopen completed Step 2.3. Its bounded result, presentation, quote, compatibility, routing, and regression corrections are a mandatory Step 2.4 closeout gate before Step 2.5 begins.
22. **Shared financial-fact naming** — Slice C1 proved that the Step 2.3 `Valuation*` names no longer describe a valuation-only boundary. Complete the bounded C1R migration to provider-facing `Financial*` fact names and cache-facing `ResolvedInputCache*` names before C2 adds another strategy consumer. Preserve semantics and avoid permanent aliases without a demonstrated compatibility need.
23. **Future composite discovery input** — The candidate five-component forward-return screen and risk filters are unapproved aggregate stakeholder input for later analytical expansion/aggregation. They do not change Step 2.4, its method semantics, or its position ahead of the Step 2.5 Golden Suite.
24. **FCF classification basis** — Show both total-company-FCF and FCF-per-diluted-share growth. Total-company-FCF CAGR controls `PASS`/`FAIL` by default; an explicit typed policy/CLI switch selects FCF/share CAGR as the controlling measure. Implement this strategy-specific, versioned extension in E1–E3 before Slice F and before the Golden Suite.
25. **Security identity is time-aware metadata** — A ticker may be delisted and later reused for a materially different security. F-1 planning was approved on 2026-08-29; because E1–E3 and Slice F were already implemented and approved before this requirement was introduced, place F-1 after F and before final Slice G. Resolve identity once per run where possible, fail open to ticker-only output, and require Step 3.4 to persist the identity snapshot rather than relabel historical runs through a future ticker lookup.
26. **D1–D5 and initial-E implementation approval** — The combined implementation review completed on 2026-08-29 and approved the implemented D1–D5 provider/composition work and initial E CLI/presentation. This closes their pending review gate without declaring Step 2.4 complete or itself approving F-1 implementation or G work.
27. **Committed E3 and Slice F approval** — E3 and Slice F were committed only after human approval under the project's working agreement. Record both as complete and approved on 2026-08-29; their committed state closes the previously stale pending-review entries without approving F-1 implementation or final Slice G.
28. **F-1 implementation approval** — The committed shared security-identity implementation was approved on 2026-08-30. Slice G may synchronize documentation and run the final gate; this does not itself declare Step 2.4 complete before the final review.
29. **Deterministic versioned investor-report projection** — Step 3.4 renders persisted Analysis Runs through a pure, explicitly versioned projection contract. Projection versioning is independent of calculation method and result-schema versioning; historical rendering uses stored evidence and explicit options only, without provider/LLM calls, recalculation, or silent reinterpretation.
30. **Slice G and Step 2.4 closeout approval** — Slice G documentation synchronization and the complete repository gate passed, and explicit human approval closed Step 2.4 on 2026-08-30. Step 2.5 is the current step and consumes the approved Steps 2.3–2.4 contracts.
31. **Known-ETF applicability** — Live FLSW evidence exposed a concrete pre-Golden defect: unavailable company facts were conflated with ticker validity and provider-specific identity resolution produced inconsistent names. P1 is approved before Golden model/case work. Only affirmative provider-backed ETF evidence makes both Graham methods and company-level FCF Growth `not_applicable`; unknown kind remains fail-open, while Momentum remains applicable.
32. **P1/P2 split** — P1 adds only the stable contract seam, request-scoped provider composition, native applicability outcomes, presentation/error corrections, and deterministic regression evidence. Durable instrument-profile caching and the distinct ETF aggregate FCF-growth strategy are P2, planned only after Step 3.1 and subject to a later provider/product-policy gate.
33. **Step 2.6 reliability-plan approval** — The bounded reliability contract, defaults, timeout precedence, retry and schema-counter semantics, structured terminal outcome, deterministic verification matrix, and A–C slice gates in `step-2.6/STEP_2_6_RELIABILITY_SLICE_PLAN.md` were approved on 2026-09-02. Real local-model execution is not an acceptance requirement. Slice A begins only after the documentation-only checkpoint is created and pushed; this approval does not authorize later slices or Step 3.1.
34. **Step 2.6 Gate B approval and Gate C remediation** — Slice B enforcement and telemetry were approved on 2026-09-03. Slice C exposed typed terminal failures through the evaluation/CLI boundary, synchronized documentation, and passed the complete repository gate with 1,331 tests at 88% coverage. An optional LAN smoke then proved that the pre-existing `LLMClient` wire contract used invalid native Ollama endpoint/payload semantics. The corrected native `/api/chat` and `/api/generate` contracts passed focused tests and the complete repository gate with 1,332 tests at 88% coverage. Repeat LAN smoke evidence then confirmed bounded `max_steps_exceeded` and `llm_timeout` terminal outcomes with matching diagnostic/run identities and preserved reports. Gate C awaits final approval; Step 3.1 is not authorized.
35. **Step 2.6 final Gate C approval** — The complete reliability implementation, native Ollama remediation, deterministic verification, and optional LAN smoke evidence received explicit human approval on 2026-09-03. Step 2.6 is complete; its implementation checkpoint and PR workflow may proceed. Step 3.1 implementation remains a separate handoff.

### Explicitly deferred
1. **Ollama schema/model support matrix** — Empirical validation remains outstanding for the actual Light Mode model configuration. Record the tested Ollama version, model identifier, schema-constrained request, observed response behaviour, and pass/fail result when completed. This is non-blocking for the Step 2.2 implementation/merge.
2. **Provider/analyst consensus-growth policy** — Do not ingest a provider forecast until its field meaning, time horizon, provenance, update behavior, and licensing are verified.
3. **Tangible-book and sector-specific variants** — Defer these until the base Graham methods and their limitations are validated.
4. **Step 2.4 product refinements** — P/FCF thresholds, alternate FCF definitions, smoothing, horizons outside the approved three/four/five-year set, peer comparisons, cash conversion, and user-defined composite thresholds remain deferred. FCF yield and FY1/FY2 consensus EPS are in scope only as documented optional context and only after their provider evidence gates are satisfied. FCF/share growth is approved current scope under the versioned E1–E3 extension, not a deferred composite feature.
5. **Ollama Modelfile consolidation (resolved 2026-08-30)** — `docs/project/deploy/ollama/` is the canonical location. The identical root `Modelfile.agents` duplicate was removed, the application artifact was retained there, and the Step 2.5 Cline implementation model received a separately named Modelfile and documented alias so development-agent configuration cannot be confused with application or Golden model-under-evaluation configuration.
6. **P2 exact scheduling and ETF aggregation policy** — P2 is approved as a post–Step 3.1 work package, but its exact placement relative to Steps 3.2–3.4 and its provider, licensing, holdings, weighting, currency, coverage, freshness, and `as_of` policies require explicit review after the persistence boundary exists. No P2 implementation is authorized during P1 or Step 2.5.

---

## 9. Next Immediate Actions

Steps 2.3 through 2.6 are complete and approved. Step 3.1 is the next planned
implementation step but has not started.

1. Preserve classified unavailability so later representative live validation
   can measure the useful-result ratio and identify whether a separately
   reviewed provider-mapping expansion is warranted.
2. Create the approved Step 2.6 implementation checkpoint and complete its PR
   workflow.
3. Plan Step 3.1 persistence as a separate handoff. Review P2's exact placement
   only after Step 3.1 is approved.
