# Milestone v0.2 Implementation Plan
## Reliability, Observability & Data Persistence

**Project:** Financial Data Agents

**Repository:** https://github.com/PeterPontbriand/financial-data-agents

**Source of truth:** Current `docs/MASTER_PLAN.md` (Milestone v0.2 section)

**Companion rationale:** Current `docs/DISCOVERY_WORKBOOK.md`

**Prepared:** 2026-08-15

**Revised:** 2026-08-16 — Sequencing, telemetry/logging boundaries, deterministic Golden Suite data access, schema-compatibility deferral, retention configuration, and fine-grained branch strategy aligned with the current planning decisions.

**Status:** Draft for development-team review and sequencing

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

## 2. Guiding Constraints (from Master Plan & Discovery Workbook)

- Deterministic math stays in Python; LLM is used only for planning, tool selection, and narrative.
- All tool arguments and returns are Pydantic models.
- Native Ollama `format=Schema` (or equivalent) is preferred over post-hoc string parsing.
- Light Mode is the default adoption path; Full Dual-Tier remains optional.
- Strict typing (`mypy --strict`), Ruff, and pytest are non-negotiable quality gates.
- Outbound network access is guarded (cache-first, rate-limited, domain-whitelisted).
- Failures are classified (transient vs. non-recoverable) and surface clear diagnostics.
- Prefer decoupled, swappable implementations behind narrow interfaces over hard dependencies on a specific storage or library choice (Discovery Workbook §4.1–4.2) — this is the principle behind the Step 2.1 sequencing design in §4.1 below.

---

## 3. Recommended Branch & PR Strategy

Use **fine-grained branches aligned with coherent implementation units within a Master Plan step**. Do not use one branch spanning the entire milestone, and do not create trivial one-change branches merely for mechanical edits.

Recommended examples:

| Work unit | Suggested branch | Rationale |
|------------|------------------|-----------|
| Step 2.1 telemetry model | `feature/step-2.1-telemetry-model` | Establishes the stable event contract |
| Step 2.1 sinks | `feature/step-2.1-telemetry-sinks` | Adds sink abstraction + JSONL persistence |
| Step 2.1 runtime instrumentation | `feature/step-2.1-runtime-instrumentation` | Wires telemetry into orchestrator/LLM/tool boundaries |
| Step 2.1 integration tests/docs | `feature/step-2.1-telemetry-integration` | Demonstrates complete trajectory reconstruction |
| Step 2.2 schema enforcement | `feature/step-2.2-schema-enforcement` | Isolates native structured-output work |
| Step 2.3 data abstraction | `feature/step-2.3-data-fixtures` | Defines deterministic benchmark data contract |
| Step 2.3 Golden runner | `feature/step-2.3-golden-suite` | Implements benchmark cases and evaluation harness |
| Step 2.4 reliability limits | `feature/step-2.4-circuit-breakers` | Isolates hard execution limits |
| Step 3.1 persistence foundation | `feature/step-3.1-sqlite-foundation` | Alembic, schema, SQLite telemetry sink, production data access |
| Step 3.2 repositories | `feature/step-3.2-repositories` | Typed DAO/repository layer |
| Step 3.3 data quality | `feature/step-3.3-data-quality` | Validation, staleness, invalidation |
| Step 3.5 Light Mode | `feature/step-3.5-light-mode` | Adoption path and smoke validation |

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

The existing `src/utils/logger_util.py` already provides asynchronous queue-based logging, dual console/file routing, time- and size-based rotation, configurable backup counts, background compression, contextual metadata, and graceful shutdown. Step 2.1 must **reuse its configuration conventions, not replace it**.

**Sequencing decision**

Step 2.1 defines a narrow `TrajectorySink` abstraction and implements JSONL first. Step 3.1 later adds a SQLite sink satisfying the same abstraction. The orchestrator and telemetry recorder therefore do not care whether telemetry is persisted to JSONL or SQLite.

**Telemetry semantics**

The initial event model should support:

- `event_id`
- `trajectory_id`
- `sequence`
- `timestamp`
- `event_type`
- `component`
- `schema_version`
- correlation/parent identifiers where needed
- model/provider metadata
- step number
- tool name and validated arguments
- tool result/error metadata
- latency
- token usage when exposed by the provider
- payload hash and/or retained payload according to configurable retention rules

Initial event categories should remain deliberately small: trajectory start/end, step start/end, LLM request/response, tool request/execution start/end/failure, and recovery attempt.

**Important reasoning boundary**

"Latent steps" means observable runtime steps and model-emitted auxiliary output that the application actually receives. The implementation must not infer, reconstruct, or claim to store private/internal model reasoning that is not exposed by the model/provider.

**Implementation outline**

1. Define typed telemetry event/envelope models.
2. Define the `TrajectorySink` Protocol.
3. Implement `JSONLTrajectorySink` as the first persistence sink.
4. Implement `TrajectoryRecorder` to own trajectory IDs and monotonic sequence assignment.
5. Place the event model, TrajectorySink Protocol, JSONLTrajectorySink, and TrajectoryRecorder under src/core/telemetry/.
6. Instrument trajectory, step, LLM, tool, and failure boundaries without changing execution semantics.
7. Capture token usage when available; represent unavailable usage explicitly rather than inventing values.
8. Add payload sanitization/redaction at the telemetry boundary.
9. Add telemetry configuration to the existing `ProjectSettings` model, following the same conventions already used by `logger_util.py`. Keep retention configurable.
10. Add unit tests for event validation, sequencing, serialization, redaction, and sink behavior.
11. Add integration tests demonstrating complete trajectory reconstruction.
12. Update `docs/ARCHITECTURE.md` with the telemetry/logging boundary and sink contract.

**Acceptance criteria**

- [ ] A complete representative analysis produces a coherent ordered trajectory.
- [ ] LLM requests/responses, tool calls/results, failures, latency, and token usage when available are observable.
- [ ] No private/internal model reasoning is inferred or reconstructed.
- [ ] Telemetry persistence is independent of the orchestrator through the sink abstraction.
- [ ] JSONL readback reconstructs the same logical event sequence that was recorded.
- [ ] Telemetry retention/storage controls are configurable.
- [ ] Telemetry failures do not silently alter business execution semantics.
- [ ] No secrets or API keys appear in telemetry payloads.
- [ ] `mypy --strict`, Ruff, and tests pass.

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
- [ ] All tool-call extraction paths use native schema constraints when the underlying Ollama version supports them.
- [ ] Schema violations are classified as transient and do not crash the process.
- [ ] Golden-test or smoke tests demonstrate reduced output-drift failures compared with the pre-constraint baseline (qualitative or measured).

**Dependencies / risks**
- The detailed Ollama/model support matrix is deliberately deferred until this step because it is an implementation/evaluation question, not a Step 2.1 prerequisite.
- Verify the actual installed Ollama version and supported Light Mode model configurations.
- Define a documented fallback for model/provider configurations that do not reliably honour native schema constraints.
- Retain Pydantic validation as the application-level defense even when native schema enforcement is active.

---

### 4.3 Step 2.3 – Golden-Test Suite

**Goal**

Establish a deterministic benchmark of representative investment-analysis tasks with verified quantitative outcomes and observable tool-selection behaviour.

**Key architectural decision**

The Golden Suite must not depend on repeatedly fetching live market data.

Before benchmark cases are implemented, define the **minimal typed market-data access abstraction** required by the cases. Step 2.3 uses a deterministic fixture-backed implementation of that abstraction. Step 3.1 later supplies the production SQLite/cache-backed implementation of the same contract.

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
8. Produce a machine-readable report separating:
   - tool-selection accuracy;
   - numeric accuracy;
   - overall case pass/fail.
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

**Dependencies / risks**

- Depends on Step 2.1 telemetry for trajectory evidence.
- Benefits from Step 2.2 schema enforcement, but the fixture/data abstraction can be developed in parallel.
- The production SQLite persistence layer is **not** required to begin Golden Suite implementation.
- The fixture representation must be designed so Step 3.1 can later implement the same data-access contract without changing benchmark cases.

### 4.4 Step 2.4 – Circuit Breakers & Timeout Limits

**Goal**
Hard execution caps, wall-clock bounds, and error thresholds that prevent unbounded loops or runaway token spend.

**Implementation outline**
1. Centralise limits in the existing Settings / config model (max steps, max transient retries, per-step and overall wall-clock timeouts, max consecutive schema violations, etc.).
2. Implement a small `CircuitBreaker` (or equivalent) that the orchestrator consults before each planning step and after each tool/LLM call.
3. On threshold breach: halt cleanly, emit a human-readable diagnostic that includes the `run_id` and last few trajectory events, and return a structured failure result to the CLI.
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
2. Create the initial production schema for:
   - market prices/OHLCV;
   - instrument and source metadata;
   - trajectory telemetry storage;
   - any other entities required by the current Master Plan, but do not prematurely absorb unrelated application state.
3. Enforce SQLite WAL mode and appropriate busy-timeout/connection settings.
4. Implement `SQLiteTrajectorySink` against the exact `TrajectorySink` contract established in Step 2.1.
5. Implement the production market-data repository/data source against the minimal contract consumed by the Golden Suite.
6. Implementation lives under `src/core/repositories/`.
7. Ensure cache-first retrieval can reuse previously fetched historical market data rather than repeatedly querying the external provider.
8. Provide a documented migration command and fresh-database smoke test.
9. Verify that the same trajectory can be persisted and reconstructed through JSONL or SQLite without changing the telemetry event model.

**Architectural distinction**

The database contains at least two conceptually distinct classes of information:

- **market-data persistence/cache** — answers what financial data is available;
- **trajectory telemetry** — answers what the agent did.

Golden fixtures remain deterministic benchmark artifacts and are not simply aliases for the mutable production cache.

**Acceptance criteria**

- [ ] `alembic upgrade head` succeeds on a clean environment.
- [ ] WAL mode is verified.
- [ ] Schema is migration-controlled.
- [ ] `SQLiteTrajectorySink` conforms to the Step 2.1 sink contract.
- [ ] A representative trajectory can be written to and reconstructed from SQLite.
- [ ] The production market-data implementation satisfies the same abstraction consumed by the Golden Suite.
- [ ] Previously fetched historical data can be reused without an unnecessary external refetch.
- [ ] No benchmark case requires rewriting because SQLite replaces the fixture adapter.

### 4.6 Step 3.2 – DAO & Repository Layer

**Goal**
Strongly-typed Python data-access objects for cache inspection, audit logging, and later analytics.

**Implementation outline**
1. Define narrow repository interfaces (e.g. `PriceRepository`, `TrajectoryRepository`, `MetadataRepository`).
2. Implement SQLite-backed concrete classes that accept/return Pydantic models only.
3. Implementation lives under `src/core/repositories/`.
4. Keep all SQL inside the repository layer; no raw SQL in the orchestrator or tools.
5. Unit tests with an in-memory or temporary-file SQLite DB.

**Acceptance criteria**
- [ ] Public repository methods are fully typed and mypy-clean.
- [ ] Round-trip tests pass for the core entities.
- [ ] Connection management is consistent with WAL / single-writer guidance.

---

### 4.7 Step 3.3 – Data Quality & Cache Invalidation Pipeline

**Goal**
Validate incoming financial data (FX adjustments, corporate actions, staleness) and invalidate or refresh cache entries when quality rules fail.

**Implementation outline**
1. Define a small set of quality rules (examples):
   - price series continuity / missing-bar detection,
   - currency consistency (CAD vs USD),
   - maximum age of a cached bar before forced refresh,
   - basic corporate-action flags if data source provides them.
2. Run rules on every fetch path before writing to the cache.
3. On failure: either reject the write, mark the entry stale, or trigger a controlled re-fetch (with circuit-breaker awareness).
4. Log quality decisions into the trajectory / execution log for auditability.
5. Unit tests with synthetic good and bad series.

**Acceptance criteria**
- [ ] Documented quality rules with clear pass/fail behaviour.
- [ ] Stale or invalid data cannot silently become the "source of truth" for downstream analytics.
- [ ] Quality failures appear in the trajectory log.

---

### 4.8 Step 3.5 – Light Mode Support

**Goal**
The full single-step analysis path (data fetch → deterministic analytics → basic synthesis/report) runs cleanly under Light Mode configuration with a 14B-class (or smaller) model.

**Implementation outline**
1. Make Light Mode the configuration default (model tag, single-tier behaviour).
2. Ensure README and `docs/HARDWARE.md` give a new user a complete, copy-pasteable path to a first successful analysis under Light Mode.
3. Add a minimal smoke-test (or mark an existing golden case) that is expected to pass under Light Mode resource constraints.
4. Confirm that dual-tier code paths remain available but are opt-in.
5. Verify that trajectory logging, schema enforcement, and circuit breakers all function under the Light Mode model.

**Acceptance criteria (exit criterion for Step 3.5)**
- [ ] A user following only the Light Mode instructions can complete a real analysis end-to-end.
- [ ] Configuration defaults favour Light Mode.
- [ ] Basic smoke tests pass under Light Mode constraints.
- [ ] Documentation is consistent across README, HARDWARE.md, Master Plan, and Discovery Workbook.

---

## 5. Suggested Sequencing & Parallelism

```text
Phase A — Step 2.1 foundation
  ├─ 2.1 telemetry model
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

**Parallelism guidance**

- Step 2.1 telemetry model/sinks and Step 2.4 circuit-breaker design can proceed independently.
- Step 2.2 schema enforcement can begin once the existing LLM boundary is understood; its detailed model-support verification belongs here, not earlier.
- Step 2.3 fixture/data-access work may begin before Step 3.1, but must use the agreed abstraction rather than a one-off mock API.
- Step 3.1 may proceed in parallel with late Step 2 work, but it must implement the abstractions already established rather than redesigning them.
- Step 3.5 is the final adoption gate and should be validated after the core reliability/persistence path is operational.

## 6. Quality Gates (apply to every PR in this milestone)

- `ruff check . && ruff format --check .`
- `mypy --strict src/`
- `pytest` (unit + any new integration tests) with coverage trend monitored
- No new untyped public interfaces
- Trajectory / diagnostic output must never leak secrets
- Light Mode path must remain functional once Step 3.5 lands

---

## 7. Exit Criteria for Milestone v0.2

All of the following must be true before declaring the milestone complete and opening the v0.2.5 real-user validation window:

1. Steps 2.1–2.4, 3.1–3.3, and 3.5 are implemented and merged.
2. Golden-test suite exists, is runnable, and current pass rate is known (path to ≥ 90 % documented).
3. A fresh clone + Light Mode setup instructions produce a successful end-to-end analysis.
4. CI is green on `main`.
5. Master Plan and Discovery Workbook cross-references are consistent (no stale document version numbers).
6. Any temporary scaffolding or TODOs that block real-user testing have been removed or clearly marked.

---

## 8. Decisions & Deferred Questions

### Resolved before implementation

1. **Trajectory storage sequencing** — JSONL first in Step 2.1; SQLite sink in Step 3.1 behind the same sink abstraction.
2. **Golden Suite market-data determinism** — define the shared market-data access abstraction before Step 2.3; use deterministic fixtures in the Golden Suite; implement the production SQLite/cache-backed version in Step 3.1.
3. **Telemetry retention** — configurable, following the existing logger's configuration conventions; no fixed retention period is required at the architectural level.
4. **Branch granularity** — use fine-grained branches aligned with coherent implementation units within each Master Plan step.

### Explicitly deferred

5. **Ollama schema/model support matrix** — deferred to Step 2.2. The matrix is only useful once native schema enforcement is being implemented and verified against the supported model/provider configurations. Step 2.1 should capture enough model/provider metadata to make those later tests reproducible.

### Design principles now locked

- The existing operational logger remains the human-oriented logging subsystem.
- Structured trajectory telemetry is a separate machine-readable subsystem.
- Telemetry is observational and must not alter business execution semantics.
- Golden Suite fixtures, production market-data cache, and trajectory telemetry are separate persistence concerns.
- Production data access and Golden Suite fixtures share a narrow typed contract.
- Document version numbers are not embedded in the Master Plan or Discovery Workbook; Git history is authoritative.

## 9. Next Immediate Actions

1. Review and approve this implementation plan.
2. Start with `feature/step-2.1-telemetry-model`.
3. Follow with the sink and runtime-instrumentation branches as coherent units.
4. Before Step 2.3, agree on the minimal market-data access contract and deterministic fixture representation.
5. Defer the Ollama/model support matrix until Step 2.2.
6. Keep the Master Plan and Discovery Workbook free of arbitrary document version numbers; Git history is authoritative.

---

*This plan is derived directly from the current Master Plan Milestone v0.2 definition and the architectural constraints recorded in the Discovery Workbook. It is intentionally detailed enough for the team to organise work, estimate, and start coding without further high-level design cycles.*
