# Milestone v0.2 Implementation Plan
## Reliability, Observability & Data Persistence

**Project:** Financial Data Agents  
**Repository:** [https://github.com/PeterPontbriand/financial-data-agents](https://github.com/PeterPontbriand/financial-data-agents)  
**Source of truth:** Current `docs/MASTER_PLAN.md` (Milestone v0.2 section)  
**Companion rationale:** Current `docs/DISCOVERY_WORKBOOK.md`  
**Prepared:** 2026-08-15  
**Revised:** 2026-08-16 — Reframed telemetry boundaries, added constraint-to-package mapping, explicitly typed initial telemetry events, and finalized step sequencing.  
**Status:** Step 2.2 → Complete
↳ Follow-up validation: empirically verify native schema support for the actual Light Mode model configuration.

---

## 1. Purpose & Scope

This plan turns the high-level Master Plan steps for Milestone v0.2 into an actionable, sequenced work package that the development team can organize around **before** writing production code.

**In scope**
- Step 2 – Agent Reliability, Evaluation & Observability Foundation (2.1 → 2.4)
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
| **Python Determinism** | Deterministic math stays in Python; LLM is used only for planning, tool selection, and narrative synthesis. | Step 2.2, Step 2.3 |
| **Typed Tool Interfaces** | All tool arguments and return structures must be strictly defined via Pydantic models. | Step 2.1, Step 2.2, Step 3.2 |
| **Native Schema Formatting** | Native Ollama `format=Schema` (or provider equivalent) is preferred over post-hoc string/regex parsing. | Step 2.2 |
| **Light-Mode Default** | Light Mode is the default adoption and execution path; Full Dual-Tier remains optional. | Step 3.5 |
| **Strict Quality Gates** | Strict typing (`mypy --strict`), Ruff, and pytest coverage are non-negotiable CI gates. | All Work Packages |
| **Guarded Egress** | Outbound network access is strictly guarded (cache-first, rate-limited, domain-whitelisted). | Step 3.1, Step 3.3 |
| **Classified Diagnostics** | Failures are categorized (transient vs. non-recoverable) and surface structured diagnostics. | Step 2.1, Step 2.4 |
| **Decoupled Contracts** | Decoupled, swappable implementations behind narrow interfaces are preferred over direct library dependencies. | Step 2.1, Step 2.3, Step 3.1 |

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
| Step 2.3 data abstraction | `feat/step-2.3-data-fixtures` | Defines deterministic benchmark data contract |
| Step 2.3 Golden runner | `feat/step-2.3-golden-suite` | Implements benchmark cases and evaluation harness |
| Step 2.4 reliability limits | `feat/step-2.4-circuit-breakers` | Isolates hard execution limits |
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
  is still minimal, wire this when Step 2.4 circuit-breakers / repair policy
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

> **Status:** Implementation complete and ready for PR/merge. The remaining unchecked item is deferred to Step 2.3/3.5 validation because it requires empirical evaluation rather than further Step 2.2 implementation.

**Dependencies / risks**
- The detailed Ollama/model support matrix is deferred to empirical validation against the actual Light Mode model configuration.
- Verify the actual installed Ollama version and supported Light Mode model configurations.
- Define a documented fallback for model/provider configurations that do not reliably honour native schema constraints.
- Retain Pydantic validation as the application-level defense even when native schema enforcement is active.

### Step 2.2 Follow-up Validation

- **Empirical Light Mode model compatibility:** The runtime currently
  determines native schema capability from Ollama server-version information
  and falls back conservatively when capability is unknown. A model-by-model
  empirical verification of native JSON-schema enforcement against the
  supported Light Mode model configuration remains to be performed.

  This validation is intentionally non-blocking for the Step 2.2 merge.
  Record the tested Ollama version, model identifier, schema-constrained
  request, observed response behavior, and pass/fail result when completed.
  
---

### 4.3 Step 2.3 – Golden-Test Suite

**Goal**  
Establish a deterministic benchmark of representative investment-analysis tasks with verified quantitative outcomes and observable tool-selection behaviour.

**Key architectural decision**  
The Golden Suite must not depend on repeatedly fetching live market data. Before benchmark cases are implemented, define the **minimal typed market-data access abstraction** required by the cases. Step 2.3 uses a deterministic fixture-backed implementation of that abstraction. Step 3.1 later supplies the production SQLite/cache-backed implementation of the same contract.

This deliberately separates:
1. **Golden fixtures** — immutable/deterministic benchmark evidence;
2. **Market-data persistence** — production cached historical data;
3. **Trajectory telemetry** — execution history.

**Implementation outline**
1. Define the minimal market-data access contract needed by benchmark scenarios.
2. Implement an in-memory/file-backed fixture adapter for deterministic historical market data.
3. Define a small, high-signal initial set of golden cases (start with roughly 8–15).
4. Store benchmark cases and fixtures as structured, reviewable data.
5. Define expected tool-selection behaviour and verified numeric outcomes/tolerances.
6. Build a headless runner that can execute against deterministic mocks/fixtures and, where explicitly desired, a real local Ollama configuration.
7. Record the trajectory and final outputs for every run.
8. Produce a machine-readable report separating tool-selection accuracy, numeric accuracy, and overall case pass/fail status.
9. Add at least one intentionally failing case to prove the harness detects regressions.
10. Document fixture creation, provenance, update policy, and benchmark execution in `docs/EVALUATIONS.md`.

**Acceptance criteria**
- [ ] Golden cases do not require live external market-data calls.
- [ ] Historical fixture data is deterministic and provenance is documented.
- [ ] The benchmark consumes the shared market-data abstraction rather than bypassing it.
- [ ] Tool-selection and numeric correctness are measured separately.
- [ ] The suite is runnable through a documented command.
- [ ] At least one intentionally failing case demonstrates regression detection.
- [ ] Current pass rate is measured, with ≥90% remaining the Master Plan target.

---

### 4.4 Step 2.4 – Circuit Breakers & Timeout Limits

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

### 4.5 Step 3.1 – SQLite DB & Migration Infrastructure

**Goal**  
Establish the production SQLite persistence foundation while implementing the SQLite telemetry sink and production market-data access behind the abstractions established earlier.

**Implementation outline**
1. Add Alembic and establish the migration environment using the existing application database configuration.
2. Create the initial production schema for market prices/OHLCV, instrument/source metadata, and trajectory telemetry storage.
3. Enforce SQLite WAL mode and appropriate busy-timeout/connection settings.
4. Implement `SQLiteTrajectorySink` against the exact `TrajectorySink` contract established in Step 2.1.
5. Implement the production market-data repository/data source against the minimal contract consumed by the Golden Suite.
6. Place implementation under `src/core/repositories/`.
7. Ensure cache-first retrieval reuses previously fetched historical market data rather than repeatedly querying external providers.
8. Provide a documented migration command and fresh-database smoke test.
9. Verify that trajectories can be persisted and reconstructed identically through either JSONL or SQLite sinks.

**Acceptance criteria**
- [ ] `alembic upgrade head` succeeds on a clean environment.
- [ ] WAL mode is verified.
- [ ] Schema is migration-controlled.
- [ ] `SQLiteTrajectorySink` conforms to the Step 2.1 sink contract.
- [ ] A representative trajectory can be written to and reconstructed from SQLite.
- [ ] Production market-data implementation satisfies the shared abstraction consumed by the Golden Suite.
- [ ] Previously fetched historical data can be reused without an unnecessary external refetch.

---

### 4.6 Step 3.2 – DAO & Repository Layer

**Goal**  
Strongly-typed Python data-access objects for cache inspection, audit logging, and later analytics.

**Implementation outline**
1. Define narrow repository interfaces (e.g. `PriceRepository`, `TrajectoryRepository`, `MetadataRepository`).
2. Implement SQLite-backed concrete classes that accept/return Pydantic models only under `src/core/repositories/`.
3. Keep all SQL inside the repository layer; no raw SQL in the orchestrator or tools.
4. Unit tests with an in-memory or temporary-file SQLite DB.

**Acceptance criteria**
- [ ] Public repository methods are fully typed and mypy-clean.
- [ ] Round-trip tests pass for core entities.
- [ ] Connection management is consistent with WAL / single-writer guidance.

---

### 4.7 Step 3.3 – Data Quality & Cache Invalidation Pipeline

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

### 4.8 Step 3.5 – Light Mode Support

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

Phase B — Reliability / structured-output foundation
  ├─ 2.2 native schema enforcement
  └─ 2.4 circuit breakers & timeout limits

Phase C — Deterministic evaluation
  ├─ 2.3 market-data fixture abstraction
  └─ 2.3 Golden Suite runner/cases
        │
        ▼
     ≥90% target measured

Phase D — Production persistence
  ├─ 3.1 Alembic + SQLite schema
  ├─ 3.1 SQLite telemetry sink
  └─ 3.1 production market-data/cache implementation
        │
        ▼
  3.2 repositories
        │
        ▼
  3.3 data quality / cache invalidation

Phase E — Adoption gate
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

1. Steps 2.1–2.4, 3.1–3.3, and 3.5 are fully implemented and merged.
2. Golden-test suite exists, runs headlessly, and reports a clear pass rate against the ≥ 90 % target.
3. A fresh repository clone running Light Mode setup instructions completes an end-to-end analysis successfully.
4. CI pipeline is green on `main`.
5. Master Plan and Discovery Workbook cross-references remain consistent.
6. Temporary scaffolding and blocking TODOs are cleaned up or documented.

---

## 8. Decisions & Deferred Questions

### Resolved before implementation
1. **Trajectory storage sequencing** — JSONL first in Step 2.1; SQLite sink in Step 3.1 behind the same sink abstraction.
2. **Golden Suite market-data determinism** — Shared market-data access abstraction defined prior to Step 2.3; deterministic fixtures used for Golden Suite; production SQLite implementation supplied in Step 3.1.
3. **Telemetry retention** — Configurable via `ProjectSettings`, adhering to existing `logger_util.py` options.
4. **Branch granularity** — Fine-grained branches mapped to coherent implementation units.
5. **Telemetry boundaries** — Telemetry captures observable provider output; missing metrics are stored explicitly as `None` rather than estimated.
6. **Step 2.2 enforcement fallback** — Native schema enforcement is preferred when capability is confirmed; prompt-based schema instructions with Pydantic validation/retry provide the configured fallback when native capability is unavailable or unknown; legacy parsing remains the final compatibility fallback.

### Explicitly deferred
1. **Ollama schema/model support matrix** — Empirical validation remains outstanding for the actual Light Mode model configuration. Record the tested Ollama version, model identifier, schema-constrained request, observed response behaviour, and pass/fail result when completed. This is non-blocking for the Step 2.2 implementation/merge.

---

## 9. Next Immediate Actions

1. Merge the Step 2.2 schema-enforcement PR after CI and review pass.
2. Record the outstanding empirical Light Mode model/schema compatibility validation as a non-blocking follow-up.
3. Begin Step 2.3 by agreeing on the minimal market-data access contract.
4. Implement the deterministic fixture adapter and Golden Suite runner/cases.
5. Complete the empirical Light Mode schema-compatibility validation before the Step 3.5 Light Mode exit criterion.

---

