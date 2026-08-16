# Financial Data Agents: Master Plan

**Repository:** github.com/PeterPontbriand/financial-data-agents  
**Core Strategy:** 100% Local AI (Ollama-Driven Orchestration) with Explicit Reliability Guardrails  
**Primary Focus:** Quantitative investment analysis and research briefs for personal & professional networks  
**Secondary Focus:** Production-grade local-first AI systems engineering  
**Quality Gate:** Ruff, Strict Static Typing (`mypy --strict`), Pytest  
**Hardware Context:** Two supported modes — **Light Mode** (single-tier, ~8–16 GB VRAM **or** 32 GB+ unified memory) as the default path for most users, and **Full Dual-Tier Mode** (~24–28 GB VRAM) for deeper reasoning. See `docs/HARDWARE.md`.  
**Out of Scope (Separate Project):** Full UI integration (e.g., Osiris or WorldMonitor)

**Companion Document:** Master Plan Discovery Workbook (records *why* decisions were made; this Master Plan records *what* and *when*. References to either document mean the current version unless explicitly qualified as a prior or subsequent version).

**Document versioning:** These documents are versioned by Git. Document version numbers are never used within the Master Plan or Discovery Workbook; references to either document mean the current version unless explicitly qualified as a prior or subsequent version.


---

## 1. Portfolio Competencies & Flagship Showcase

This repository delivers a usable local investment analysis engine while demonstrating production-grade AI systems engineering:

- **Local LLM Orchestration & Tool Dispatching:** Multi-turn state management, schema enforcement, and async function calling on local open-weight models.
- **Systems & Architectural Design:** Modular tiering, async runtime loops, provider abstractions, and clean separation of concerns.
- **Data Engineering & Persistence:** Transactional SQLite storage, schema migration versioning, data quality gates, and local caching pipelines.
- **Quantitative Financial Modeling:** Mathematical rigor in intrinsic valuation (Benjamin Graham formula), momentum indicators, and risk metrics.
- **Production Quality & Security:** Defensive static typing (`mypy --strict`), automated unit testing, dependency auditing, and local network isolation.
- **Localization (i18n):** Deep internationalization for Canadian financial standards (`en-CA` / `fr-CA`).

Illustrative use case: A long-time retail investor hears a ticker mentioned informally, runs a quick CLI analysis under Light Mode, and decides whether to add it to an ongoing watch list for agent-driven tracking.

*(These competencies are the natural output of building something genuinely useful — not a separate target to design toward.)*

---

## 2. High-Level System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                      User Interfaces (CLI / Reports)                    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Agent Orchestrator & Planner Loop                    │
│      - Context Manager (Truncation & System Prompt Injection)           │
│      - Reliability Circuit Breaker & Step Boundary Guard                │
└───────────────────┬─────────────────────────────────┬───────────────────┘
                    │                                 │
                    ▼                                 ▼
┌───────────────────────────────┐   ┌─────────────────────────────────────┐
│ Execution Tier (≈14B)         │   │ Deep Reasoning Tier (≈32B)          │
│ - Default for most users      │   │ - Optional Full Dual-Tier mode      │
│ - Tool Call Extraction        │   │ - Task Decomposition & Synthesis    │
│ - Schema Validation           │   │ - Narrative & Report Generation     │
│ - Planning/Synthesis (Light)  │   │                                     │
└───────────────┬───────────────┘   └─────────────────┬───────────────────┘
                │                                     │
                └───────────────────┬─────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   Async Tool Dispatcher & Parser                        │
└──────┬────────────────────────────┬─────────────────────────────┬───────┘
       │                            │                             │
       ▼                            ▼                             ▼
┌───────────────┐           ┌───────────────┐             ┌───────────────┐
│  Data Layer   │           │ Analytics Mod │             │ Report Mod    │
│  - DAO        │           │ - Intrinsic V │             │ - Jinja2      │
│  - Cache      │           │ - Momentum    │             │ - Charting    │
└──────┬────────┘           └───────────────┘             └───────────────┘
       │
       ▼
┌───────────────┐
│ SQLite DB     │
│ (WAL Mode)    │
└───────────────┘
```

---

## 3. Core Design Principles

1. **Deterministic Execution over Autonomous Guesswork:** Perform math, caching, and data processing in native Python functions; use the LLM strictly for task planning, tool selection, and narrative synthesis.
2. **Local-First & Isolated by Default:** No cloud dependencies for core reasoning; network outbound calls require an explicit local cache miss and pass through an outbound guardrail.
3. **Observable & Auditable by Default:** Agent trajectories are captured as structured telemetry suitable for reconstruction and evaluation. Human-oriented operational logging remains a complementary concern.
4. **Explicit Schema over Prompt Parsing:** Enforce native JSON Schema validation at the API boundary to eliminate unstructured string parsing where supported.
5. **Fail Safely & Gracefully:** Classify failures into transient retries vs. hard boundaries; surface clear diagnostic traces rather than unhandled crashes.
6. **Configurability over Brittle Dependencies:** Prefer clean abstractions and configuration so third-party libraries or engines can be swapped without cascading changes.
7. **Light Mode First for Adoption:** Core useful analysis must work under Light Mode (single-tier / modest hardware) before external validation and before heavier dual-tier features are treated as required.

---

## 4. Hardware Strategy & Model Tiering

| Mode / Tier | Target Models (examples) | Typical Footprint | Primary Responsibilities |
| :--- | :--- | :--- | :--- |
| **Light Mode (default)** | `qwen2.5-coder:14b-instruct-q4_K_M` or smaller quantized models | ~8–16 GB VRAM **or** 32–64 GB unified memory | Tool extraction, schema validation, single-step analysis, basic synthesis. Usable by most target users. |
| **Full Dual-Tier — Fast** | `qwen2.5-coder:14b-instruct-q4_K_M` | ~9–11 GB | Tool extraction, schema validation (when dual-tier is active). |
| **Full Dual-Tier — Deep** | `qwen2.5-coder:32b-instruct-q4_K_M` **or** `deepseek-r1:32b` (configurable) | ~19–24 GB | Multi-step planning, complex synthesis, higher-fidelity report generation. |

- Light Mode is the **recommended default** and the path external testers are expected to use.
- Full Dual-Tier Mode remains fully supported for users with workstation-class hardware.
- See `docs/HARDWARE.md` for consumer hardware guidance (Apple Silicon, high-memory mini-PCs, discrete GPUs).

Deep-tier model selection (when used) remains a configuration choice rather than a hard commitment.

---

## 5. Security & Isolation Model

- **Tool Execution Boundaries:** Tools operate on explicit typed parameters. No dynamic string evaluation (`eval()`) or raw shell command invocation.
- **Outbound Network Guard:** All remote calls (e.g., `yfinance`) are routed through a single outbound client wrapper enforcing rate limits, local cache checks, and domain whitelisting.
- **Filesystem Constraints:** File outputs (reports, logs) are restricted to designated subdirectories (`/reports`, `/logs`, `/data`).
- **Prompt Injection Defense:** External data (e.g., news headlines, raw text from financial APIs) is sanitized and wrapped in clear data delimiters before injection into model context.
- **Secret Management:** Sensitive parameters and API keys are ingested via environment variables managed by Pydantic BaseSettings, never hardcoded or committed.

---

## 6. Failure Taxonomy & Handling Strategy

```text
               ┌─────────────────────────────────┐
               │         System Failure          │
               └────────────────┬────────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
┌───────────────────────────────┐               ┌───────────────────────────────┐
│     Transient / Recoverable   │               │   Non-Recoverable / Fatal     │
├───────────────────────────────┤               ├───────────────────────────────┤
│ - Model Timeout               │               │ - Database Corruption         │
│ - Malformed JSON Output       │               │ - Missing Ticker Data         │
│ - Rate-Limited External API   │               │ - Exhausted Loop Max-Steps    │
├───────────────────────────────┤               ├───────────────────────────────┤
│ Action:                       │               │ Action:                       │
│ Safe retry with error context │               │ Halt step, log audit trace,   │
│ up to max-retry threshold.    │               │ emit human-readable diagnostic│
└───────────────────────────────┘               └───────────────────────────────┘
```

---

## 7. Configuration Strategy

System settings are managed through the project's centralized `ProjectSettings` model in `src/config.py`, using `pydantic-settings` and environment-variable overrides.

- **LLM Settings:** Local Ollama base URL and model selection, with Light Mode as the default adoption path.
- **Execution Limits:** Max planning steps (default: 10), Max transient retries (default: 3); subsequent reliability work may add more explicit timeout/error limits.
- **Cache & Database:** SQLite connection path and later persistence/cache settings.
- **Localization:** System default locale (`en-CA` / `fr-CA`), Currency defaults (`CAD`).
- **Operational Logging:** The existing `src/utils/logger_util.py` uses configurable log level, file name, maximum file size, backup count, encoding, and time-based rotation settings. Structured trajectory telemetry should reuse the existing configuration conventions rather than inventing a separate logging configuration mechanism.
- **Trajectory Telemetry:** Structured telemetry has its own configuration namespace within the same settings system where its storage/retention controls differ materially from human-readable operational logs. Retention and storage limits are configurable, not architectural constants.

---

## 8. Ordered Implementation Steps & Release Milestones

### **Milestone v0.1: Core Orchestration Engine**
#### Step 1: Local Orchestration Engine & Structured Tool Dispatch `[COMPLETED]`
* **Status:** Merged to main (Tag: v0.1.0)
* **Step 1.1: Environment Config & Core LLM Client** `[COMPLETED]`
* **Step 1.2: Pydantic Tool Definition & Parsing Layer** `[COMPLETED]`
* **Step 1.3: Asynchronous Orchestration Loop & Message Context** `[COMPLETED]`

### **Milestone v0.2: Reliability, Observability & Data Persistence**
#### Step 2: Agent Reliability, Evaluation & Observability Foundation
* **Branch strategy:** Use fine-grained feature branches aligned with coherent implementation units within each step (for example, `feature/step-2.1-telemetry-model` and `feature/step-2.1-runtime-instrumentation`). Avoid one branch spanning the entire milestone.
* **Step 2.1: Trajectory Logging & Telemetry:** Establish a typed, sink-independent trajectory telemetry model and recorder. Persist deterministic JSONL first; a SQLite sink is added in Step 3.1 behind the same abstraction. Capture observable LLM requests/responses, tool calls/results, step boundaries, token usage when available, latency, failures, and model-emitted auxiliary output when explicitly exposed. Do not infer or reconstruct private model reasoning.
* **Step 2.2: Native Schema Enforcement:** Enable native Ollama JSON schema constraints (`format=Schema` or the current supported equivalent) at the structured-output boundary, with Pydantic validation retained as a second line of defense. Verify actual support/behaviour for supported Light Mode models during this step; no model-support matrix is required before Step 2.1.
* **Step 2.3: Golden-Test Suite:** Establish deterministic benchmark cases using a data-access abstraction with fixture-backed historical market data. The abstraction is defined before the suite; production SQLite-backed data access is implemented later in Step 3.1. Target ≥90% aggregate pass rate, with tool-selection and numeric accuracy reported separately.
* **Step 2.4: Circuit Breakers & Timeout Limits:** Enforce hard execution caps, wall-clock time bounds, and error thresholds.

### **Milestone v0.2: Reliability, Observability & Data Persistence**

Detailed sequencing, branch strategy, acceptance criteria, and architectural decisions
for this milestone live in:

→ **`docs/MILESTONE_v0_2_IMPLEMENTATION_PLAN.md`**

#### Step 2: Agent Reliability, Evaluation & Observability Foundation
* **Branch strategy:** Fine-grained feature branches aligned with coherent implementation units
  (see Implementation Plan).
* **Step 2.1: Trajectory Logging & Telemetry:** Establish a typed, sink-independent trajectory telemetry model and recorder. Persist deterministic JSONL first; a SQLite sink is added in Step 3.1 behind the same abstraction. Capture observable LLM requests/responses, tool calls/results, step boundaries, token usage when available, latency, failures, and model-emitted auxiliary output when explicitly exposed. Do not infer or reconstruct private model reasoning.
  Implementation lives under `src/core/telemetry/`.
* **Step 2.2: Native Schema Enforcement:** Enable native Ollama JSON schema constraints (`format=Schema` or the current supported equivalent) at the structured-output boundary, with Pydantic validation retained as a second line of defense. Verify actual support/behaviour for supported Light Mode models during this step; no model-support matrix is required before Step 2.1.
* **Step 2.3: Golden-Test Suite:** Establish deterministic benchmark cases using a data-access abstraction with fixture-backed historical market data. The abstraction is defined before the suite; production SQLite-backed data access is implemented later in Step 3.1. Target ≥90% aggregate pass rate, with tool-selection and numeric accuracy reported separately.
* **Step 2.4: Circuit Breakers & Timeout Limits:** Enforce hard execution caps, wall-clock time bounds, and error thresholds.

#### Step 3: Relational Data Persistence Layer & Data Quality (SQLite)
* **Branch strategy:** Use fine-grained branches aligned with Step 3 implementation units.
* Repositories land under `src/data/repositories/`.
* **Step 3.1: SQLite DB & Migration Infrastructure:** Setup Alembic for schema migrations, enforce WAL mode, establish core market-data tables (prices, instruments/metadata), and add the SQLite implementation of the trajectory telemetry sink and the production data-access abstraction used by the Golden Suite. This step must preserve the distinction between telemetry persistence, market-data persistence, and deterministic Golden Suite fixtures.
* **Step 3.2: DAO & Repository Layer:** Build strongly typed Python data-access/repository interfaces and SQLite implementations for market data, trajectory records, and metadata. The Golden Suite's fixture-backed implementation must satisfy the same market-data contract.
* **Step 3.3: Data Quality & Cache Invalidation Pipeline:** Validate incoming financial data (CAD/USD FX adjustments, corporate actions, stale cache invalidation).

#### Step 3.5: Light Mode Support (new, required before v0.2.5)
* **Goal:** Ensure the full single-step analysis path (data fetch → deterministic analytics → basic synthesis/report) runs cleanly under Light Mode configuration with a 14B-class (or smaller) model.
* **Deliverables:** Configuration defaults favor Light Mode; documentation and README point new users to Light Mode; basic smoke tests pass under Light Mode resource constraints.
* **Exit criterion:** A user following only the Light Mode instructions in `docs/HARDWARE.md` and the README can complete a real analysis end-to-end.

### **Milestone v0.2.5: Real-User Validation Checkpoint**
This milestone answers a question none of the technical quality gates can answer: does this help anyone besides the author? It sits after a working analysis loop (including Light Mode) exists and before larger investments in analytics expansion, localization, autonomy, and reporting.

* **Step 0.5.1: Recruit real testers.** At least 3 people outside the author, ideally matching the Primary User description, install the tool under **Light Mode** and run at least one real analysis end-to-end.
* **Step 0.5.2: Capture structured feedback.** For each tester: what confused them, where they stalled or gave up, whether the output told them something they wanted to know, and what they'd want next.
* **Step 0.5.3: Confirm hardware assumptions.** Use what testers actually had available to validate or adjust the Light Mode recommendations.
* **Step 0.5.4: Re-prioritize Milestone v0.3** using this input, including whether `fr-CA` localization stays in v0.3 or moves later.
* **Exit criterion:** At least 3 completed tester sessions under Light Mode, findings documented, and Milestone v0.3 scope confirmed or adjusted before Step 4 work begins.

### **Milestone v0.3: Analytics Expansion & Canadian Localization**
#### Step 4: Analytical Modules & Quantitative Modeling
* **PR Branch:** `feature/step-4.1-graham-valuation`
* **Step 4.1: Benjamin Graham Intrinsic Value Engine:** Type-safe Graham valuation calculations with negative EPS and yield edge-case handling.
* **Step 4.2: Technical Momentum Indicators:** Vectorized RSI, SMA, and price-crossover calculation tools.
* **Step 4.3: Analytical Aggregator & Risk Metrics:** Combine technical and fundamental outputs into unified data models with basic risk metrics (max drawdown, volatility).

#### Step 5: Localization Engine for Canadian Markets (en-CA / fr-CA)
* **PR Branch:** `feature/step-5-localization`
* **Status note:** Scope and timing confirmed at Milestone v0.2.5 (Step 0.5.4).
* **Step 5.1: i18n Core Framework:** Translation catalogs for English (`en-CA`) and French (`fr-CA`).
* **Step 5.2: Localized Financial & Currency Formatters:** CAD currency formatting, date/time standards, and metric translations.
* **Step 5.3: Disclaimers & Agent Reasoning Localization:** Locale-aware agent reasoning output and mandatory compliance disclaimers.

### **Milestone v1.0: Multi-Step Autonomy & Executive Reporting**
* **Entry criterion:** Milestone v0.2.5 exit criteria met, and at least 1 tester has confirmed an output was genuinely useful to them. This is the most expensive remaining work — it should be built on evidence.

#### Step 6: Autonomous Multi-Step Tool Integration (Hardened)
* **PR Branch:** `feature/step-6-autonomous-tool-loop`
* **Step 6.1: Multi-Step Planner:** Autonomous chaining of database queries, calculation tools, and synthesis.
* **Step 6.2: Argument Sanitization & Self-Correction:** Intercept malformed tool calls, feed exception context back to the agent, and retry up to limits.
* **Step 6.3: Golden Suite Evaluation Gate:** Continuous integration validation against the Golden Benchmark suite.

#### Step 7: High-Fidelity Data Visualization & Report Generation
* **PR Branch:** `feature/step-7-reporting-visualization`
* **Step 7.1: Visual Plotting Engine:** Render static charts (intrinsic value bands, momentum indicators) in PNG/SVG.
* **Step 7.2: Executive PDF & Markdown Report Generator:** Compile Jinja2-templated Markdown and PDF research briefs with embedded charts, audit snapshot IDs, and disclaimers.

---

## 9. Performance & Quality Targets

| Category | Metric | Target Threshold |
| :--- | :--- | :--- |
| **Code Quality** | Type Coverage | Zero mypy (`mypy --strict`) errors in supported source code |
| **Code Quality** | Annotation Completeness | 100% typed public interfaces |
| **Testing** | Unit Test Line Coverage | ≥ 85% project-wide (`pytest --cov=src`) |
| **Agent Accuracy** | Golden Benchmark Pass Rate | ≥ 90% aggregate pass rate, with tool-selection and numeric correctness measured separately |
| **Performance** | CLI Startup Latency | < 500 ms (excluding Ollama/model initialization and network access) |
| **Performance** | SQLite Query Latency | < 50 ms (indexed local cache lookup under representative single-user workload) |
| **Reliability** | Unhandled Agent Exceptions | 0 on golden test suite |
| **Adoption** | Light Mode end-to-end path documented and smoke-tested | Required before Milestone v0.2.5 |
| **User Validation** | External testers who completed a real analysis under Light Mode | ≥ 3 before Milestone v1.0 begins |
| **User Validation** | External testers confirming a genuinely useful output | ≥ 1 before Milestone v1.0 begins |

---

## 10. Operational Risk Register & Mitigations

| Risk Event | Potential Impact | Architectural Mitigation Strategy |
| :--- | :--- | :--- |
| **External API Changes (`yfinance`)** | Upstream data fetch failures | Abstract data provider behind `BaseDataClient` interface; rely on SQLite cache first. |
| **Local LLM Output Drift / Schema Violation** | Failed tool parsing, infinite retries | Enforce native Ollama JSON schemas (`format`) + Pydantic validation + circuit breaker caps. |
| **Context Degradation on Long Turns** | Model forgets original goal or tool rules | Prune middle conversation context while strictly locking `Role.SYSTEM` at index 0. |
| **Database Lock / Concurrency Latency** | DB timeouts during multi-tool execution | Enforce SQLite Write-Ahead Logging (WAL) mode and single-writer/multi-reader connection pooling. |
| **Hardware barrier excludes target users** | Dual-tier requirements out of reach for most Primary Users | **Light Mode is the default path.** Full Dual-Tier is optional. Hardware requirements are surfaced early in README and `docs/HARDWARE.md`. External validation (v0.2.5) runs under Light Mode. |

---

## 11. CI/CD Pipeline & Automated Quality Gates

Every Pull Request must pass the following automated GitHub Actions pipeline before merge approval:

1. **Lint & Code Style:** `ruff check . && ruff format --check .`
2. **Strict Static Analysis:** `mypy --strict src/`
3. **Unit Tests & Coverage:** `pytest --cov=src --cov-report=term-missing`
4. **Security & Dependency Audit:** `uv audit` / `pip-audit` for known vulnerabilities.
5. **Golden Agent Evaluation:** Headless execution of golden query suite against mocked LLM outputs.

---

## 11.5 Market-Data Access & Golden-Test Determinism

The project distinguishes three related but separate forms of persistence:

1. **Operational logs** answer what happened operationally.
2. **Trajectory telemetry** answers what an agent did during a specific execution.
3. **Market-data persistence and Golden fixtures** answer what financial data was available to an analysis or benchmark.

The Golden Suite must not depend on live external market-data calls. Before Step 2.3, the project will define the minimal typed market-data access abstraction needed by benchmark cases and provide a deterministic fixture-backed implementation. Step 3.1 will provide the production SQLite-backed implementation of that same abstraction and the cache-first external-data path.

This allows the Golden Suite to remain deterministic without prematurely coupling it to a particular provider or requiring the entire production persistence layer before evaluation work can begin.

---

## 12. Telemetry & Operational Logging Boundary

The project distinguishes **human-oriented operational logging** from **structured agent trajectory telemetry**.

- `src/utils/logger_util.py` remains the operational logging infrastructure. It already provides asynchronous queue-based logging, console/file routing, time- and size-based rotation, configurable backup counts, background compression, contextual metadata, and graceful shutdown. Its configuration is driven through the existing settings system.
- Step 2.1 introduces a separate typed trajectory telemetry model and recorder for machine-readable execution history. Telemetry is observational and must not become a second orchestration engine.
- The telemetry model records observable execution events such as trajectory/step boundaries, LLM requests and responses, tool calls/results, failures, latency, and token usage when available.
- Model-emitted auxiliary/reasoning output may be recorded when explicitly exposed to the application. Private/internal model reasoning is never inferred or reconstructed.
- JSONL is the first telemetry persistence sink. SQLite is added in Step 3.1 behind the same sink abstraction.
- Telemetry retention is configurable and follows the project's existing configuration philosophy. It is not hard-coded into the event model.
- Operational logs and trajectory telemetry may share configuration conventions and filesystem policy, but they serve different consumers and should not be collapsed into one record format.

---

## 13. Documentation Strategy

Documentation lives in the repository and is updated with the code:

- **`docs/ARCHITECTURE.md`:** System architecture, layer responsibilities, and data flow diagrams.
- **`docs/TOOL_DEVELOPMENT.md`:** Guide for implementing new typed tools with Pydantic schemas.
- **`docs/EVALUATIONS.md`:** Instructions for running and extending the Golden Benchmark suite.
- **`docs/I18N_GUIDE.md`:** Standard operating procedures for adding translation strings and localized report templates.
- **`docs/HARDWARE.md`:** Light Mode vs Full Dual-Tier requirements and consumer hardware guidance.
- **Master Plan Discovery Workbook:** Living record of architectural rationale, principles, and decision history (companion to this execution plan).

---

*This Master Plan records the current execution roadmap. It is versioned through Git; document version numbers are intentionally not embedded in this document.*
