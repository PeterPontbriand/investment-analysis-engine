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

**Implementation authority:** The Master Plan defines milestone intent and ordering. During an active milestone, the current milestone implementation plan is the more specific operational source for branch sequencing, implementation guardrails, and acceptance criteria. `docs/ARCHITECTURE.md` describes architectural boundaries; `docs/DISCOVERY_WORKBOOK.md` records rationale. If a lower-level guide conflicts with the current Master Plan or active milestone plan, do not blend the instructions—use the more specific/current source and surface the conflict.


---

## 1. Portfolio Competencies & Flagship Showcase

This repository delivers a usable local investment analysis engine while demonstrating production-grade AI systems engineering:

- **Local LLM Orchestration & Tool Dispatching:** Multi-turn state management, schema enforcement, and async function calling on local open-weight models.
- **Systems & Architectural Design:** Modular tiering, async runtime loops, provider abstractions, and clean separation of concerns.
- **Data Engineering & Persistence:** Transactional SQLite storage, schema migration versioning, data quality gates, and local caching pipelines.
- **Quantitative Financial Modeling:** Mathematical rigor across materially different analytical strategies, including intrinsic valuation (Benjamin Graham), market-price momentum, and later risk metrics. Analytical strategies are deterministic Python capabilities exposed through typed, swappable interfaces rather than model-specific reasoning.
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
│      - Context Manager                                                  │
│      - Structured-output / schema boundary                              │
│      - Reliability limits (Step 2.5)                                    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     Typed Tool / Analysis Dispatch                      │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                   ┌─────────────────┴─────────────────┐
                   ▼                                   ▼
┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│ MomentumAnalyzer                │   │ GrahamValueAnalyzer             │
│ - historical market series      │   │ - EPS / growth / AAA yield      │
│ - configurable SMA crossover    │   │ - intrinsic value / MOS         │
│ - existing strategy             │   │ - Step 2.3 strategy             │
└────────────────┬────────────────┘   └────────────────┬────────────────┘
                 │                                     │
                 └──────────────────┬──────────────────┘
                                    ▼
                     Existing analyzer abstraction
                           (`BaseAnalyzer`)
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Market-Data Provider Boundary                        │
│                         (`BaseDataClient`)                              │
│        historical market data  +  current quote / market price          │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                 ┌───────────────────┴────────────────────┐
                 ▼                                        ▼
        Provider adapters                         Fixture adapter
        (e.g. yfinance)                     (Step 2.3 deterministic)
                 │                                        │
                 └───────────────────┬────────────────────┘
                                     ▼
                         Production persistence
                        SQLite / cache (Step 3.1)
```

The initial Momentum and Graham strategies are intentionally **heterogeneous**. They share the existing analyzer/tool/orchestration path, but they do not need identical inputs or outputs. The project must not introduce a speculative strategy/plugin/registry framework merely to make these two analyzers look alike.

Step 2.3 establishes the minimum shared market-data capabilities required by the two strategies: historical-series access for Momentum and current-price/quote access for Graham. Step 2.4 consumes those stable contracts for deterministic Golden-Suite evaluation. Step 3.1 later supplies production SQLite/cache-backed implementations.

---

## 3. Core Design Principles

1. **Deterministic Execution over Autonomous Guesswork:** Perform math, caching, and data processing in native Python functions; use the LLM strictly for task planning, tool selection, and narrative synthesis.
2. **Local-First & Isolated by Default:** No cloud dependencies for core reasoning; network outbound calls require an explicit local cache miss and pass through an outbound guardrail.
3. **Observable & Auditable by Default:** Agent trajectories are captured as structured telemetry suitable for reconstruction and evaluation. Human-oriented operational logging remains a complementary concern.
4. **Explicit Schema over Prompt Parsing:** Enforce native JSON Schema validation at the API boundary to eliminate unstructured string parsing where supported.
5. **Fail Safely & Gracefully:** Classify failures into transient retries vs. hard boundaries; surface clear diagnostic traces rather than unhandled crashes.
6. **Configurability over Brittle Dependencies:** Prefer clean abstractions and configuration so third-party libraries or engines can be swapped without cascading changes.
7. **Light Mode First for Adoption:** Core useful analysis must work under Light Mode (single-tier / modest hardware) before external validation and before heavier dual-tier features are treated as required.
8. **Heterogeneous Strategy Independence:** Financial-analysis strategies remain independently typed and deterministic. The runtime, data layer, and evaluation harness must not assume that every financial-analysis request is a Momentum request or force materially different strategies into one shape.

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

### **Milestone v0.2: Reliability, Observability, Strategy Generalization & Data Persistence**

Detailed sequencing, branch strategy, acceptance criteria, implementation guardrails, and review gates for this milestone live in:

→ **`docs/MILESTONE_v0_2_IMPLEMENTATION_PLAN.md`**

#### Step 2: Agent Reliability, Strategy Generalization, Evaluation & Observability Foundation
* **Branch strategy:** Use fine-grained feature branches aligned with coherent implementation units within each step. Do not use one branch spanning the entire milestone.
* **Step 2.1: Trajectory Logging & Telemetry** `[IMPLEMENTED]`: Typed, sink-independent trajectory telemetry with deterministic JSONL persistence. SQLite is added later in Step 3.1 behind the same sink abstraction.
* **Step 2.2: Native Schema Enforcement** `[IMPLEMENTATION COMPLETE / MERGE-READY]`: Prefer native Ollama JSON-schema constraints at structured-output boundaries, retain Pydantic validation as an application-level defense, and use the documented fallback path when native capability is unavailable or unknown. **Empirical model-by-model Light Mode compatibility remains a non-blocking validation item and must be completed before the Step 3.5 Light Mode exit criterion.**
* **Step 2.3: Graham Strategy & Market-Data Contract**: Add `GrahamValueAnalyzer` as the second materially different deterministic strategy. Extend the existing `BaseDataClient` boundary only as needed to support both historical market data and a first-class current-price/quote capability. Add the minimal deterministic fixture adapter needed to prove the shared contract. Do not build the Golden evaluator/reporting system in this step. Stop for review when Step 2.3 is complete.
* **Step 2.4: Golden-Test Suite & Strategy Evaluation**: Build the fixture-backed Golden Suite on the stable Step 2.3 contracts. Exercise both Momentum and Graham. Report strategy/tool-selection correctness separately from deterministic numerical correctness and from overall case pass/fail. Keep deterministic/no-LLM regression tests separate from optional real-local-Ollama empirical evaluation. Target ≥90% aggregate pass rate without weakening benchmark criteria.
* **Step 2.5: Circuit Breakers & Timeout Limits**: Enforce hard execution caps, wall-clock bounds, retry/error thresholds, and clean diagnostics.

#### Step 3: Relational Data Persistence Layer & Data Quality (SQLite)
* **Branch strategy:** Use fine-grained branches aligned with Step 3 implementation units.
* Repositories live under `src/data/repositories/`.
* **Step 3.1: SQLite DB & Migration Infrastructure:** Set up Alembic, enforce WAL mode, establish market-data and trajectory storage, add `SQLiteTrajectorySink`, and implement production historical-series/current-quote access behind the Step 2.3 market-data contracts. This step preserves the distinction between telemetry persistence, production market-data persistence, and Golden fixtures.
* **Step 3.2: DAO & Repository Layer:** Build strongly typed data-access/repository interfaces and SQLite implementations for market data, trajectory records, and metadata.
* **Step 3.3: Data Quality & Cache Invalidation Pipeline:** Validate incoming financial data (currency consistency, corporate actions where applicable, continuity/missing data, and staleness) and apply controlled cache refresh/invalidation rules.

#### Step 3.5: Light Mode Support (required before v0.2.5)
* **Goal:** Ensure the full single-step analysis path (data fetch → deterministic analytics → basic synthesis/report) runs cleanly under Light Mode configuration with a 14B-class (or smaller) model.
* **Deliverables:** Configuration defaults favor Light Mode; README and `docs/HARDWARE.md` provide the supported path; basic smoke tests pass; Step 2.2 empirical schema/model compatibility is recorded.
* **Exit criterion:** A user following only the Light Mode instructions can complete a real analysis end-to-end.

### **Milestone v0.2.5: Real-User Validation Checkpoint**
This milestone answers a question none of the technical quality gates can answer: does this help anyone besides the author?

* **Step 0.5.1:** Recruit at least 3 external testers using Light Mode.
* **Step 0.5.2:** Capture structured feedback about setup, confusion, failures, usefulness, and desired next capabilities.
* **Step 0.5.3:** Confirm or adjust hardware assumptions using actual tester hardware.
* **Step 0.5.4:** Re-prioritize Milestone v0.3 using the findings, including whether `fr-CA` localization remains in v0.3.
* **Exit criterion:** At least 3 completed tester sessions, documented findings, and v0.3 scope confirmed or adjusted before Step 4 begins.

### **Milestone v0.3: Analytics Expansion & Canadian Localization**
#### Step 4: Analytical Expansion & Quantitative Modeling
The initial Momentum and Graham strategies are established earlier as architectural/evaluation exemplars. Step 4 expands the analytical library rather than defining its first strategy contracts.

* **Step 4.1: Additional Fundamental Valuation Models:** Add further fundamental/valuation strategies using the existing typed analyzer and market-data boundaries.
* **Step 4.2: Additional Technical Indicators:** Expand beyond the initial SMA/crossover Momentum implementation (for example RSI/EMA/MACD only when explicitly selected and specified).
* **Step 4.3: Analytical Aggregator & Risk Metrics:** Combine independent strategy outputs into unified typed models with basic risk measures such as maximum drawdown and volatility.

#### Step 5: Localization Engine for Canadian Markets (en-CA / fr-CA)
* **Status note:** Scope and timing are confirmed at Milestone v0.2.5.
* **Step 5.1:** i18n core framework.
* **Step 5.2:** Localized financial/currency formatters.
* **Step 5.3:** Locale-aware reporting text and compliance disclaimers.

### **Milestone v1.0: Multi-Step Autonomy & Executive Reporting**
* **Entry criterion:** Milestone v0.2.5 exit criteria met, and at least 1 tester has confirmed an output was genuinely useful.

#### Step 6: Autonomous Multi-Step Tool Integration (Hardened)
* **Step 6.1:** Multi-Step Planner.
* **Step 6.2:** Argument Sanitization & Self-Correction.
* **Step 6.3:** Continuous Golden-Suite Evaluation Gate using the Step 2.4 benchmark infrastructure.

#### Step 7: High-Fidelity Data Visualization & Report Generation
* **Step 7.1:** Static plotting engine.
* **Step 7.2:** Executive Markdown/PDF report generation with charts, audit identifiers, and disclaimers.

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
| **Strategy fixation / analytical monoculture** | Local model repeatedly selects the first/only familiar analytical strategy even when another is appropriate | Maintain materially different deterministic analyzers behind the same existing runtime path; Step 2.4 measures strategy selection separately from numerical correctness; do not special-case the orchestrator around one strategy. |

---

## 11. CI/CD Pipeline & Automated Quality Gates

Every Pull Request must pass the following automated GitHub Actions pipeline before merge approval:

1. **Lint & Code Style:** `ruff check . && ruff format --check .`
2. **Strict Static Analysis:** `mypy --strict src/`
3. **Unit Tests & Coverage:** `pytest --cov=src --cov-report=term-missing`
4. **Security & Dependency Audit:** `uv audit` / `pip-audit` for known vulnerabilities.
5. **Golden Agent Evaluation:** Headless deterministic execution of the Step 2.4 Golden Suite in its no-LLM/test mode. Optional real-local-Ollama evaluation is recorded separately and is not a mandatory CI dependency unless explicitly configured.

---

## 11.5 Strategy/Data Contracts & Golden-Test Determinism

The project distinguishes these related but separate concerns:

1. **Operational logs** answer what happened operationally.
2. **Trajectory telemetry** answers what the agent/runtime did during a specific execution.
3. **Market-data contracts** define what deterministic analytics may request.
4. **Golden fixtures** provide immutable deterministic evidence for benchmark execution.
5. **Production persistence/cache** provides durable market-data storage in Step 3.1.
6. **Evaluation results** record whether a benchmark run selected the correct strategy/tool and produced the correct deterministic result.

Step 2.3 establishes the minimum shared market-data capabilities required by the initial heterogeneous strategies:
- historical market data for Momentum;
- current quote/market price for Graham.

Step 2.3 also supplies only the minimal fixture adapter needed to prove that contract. Step 2.4 builds the Golden Suite on those stable foundations. Step 3.1 later supplies production SQLite/cache-backed implementations.

The Golden Suite must never silently fall back to live market data when fixture evidence is missing.

---

## 12. Telemetry & Operational Logging Boundary

The project distinguishes **human-oriented operational logging** from **structured agent trajectory telemetry**.

- `src/utils/logger_util.py` remains the operational logging infrastructure. It already provides asynchronous queue-based logging, console/file routing, time- and size-based rotation, configurable backup counts, background compression, contextual metadata, and graceful shutdown. Its configuration is driven through the existing settings system.
- Step 2.1 established a separate typed trajectory telemetry model and recorder for machine-readable execution history. Telemetry is observational and must not become a second orchestration engine.
- The telemetry model records observable execution events such as trajectory/step boundaries, LLM requests and responses, tool calls/results, failures, latency, and token usage when available.
- Model-emitted auxiliary/reasoning output may be recorded when explicitly exposed to the application. Private/internal model reasoning is never inferred or reconstructed.
- JSONL is the first telemetry persistence sink. SQLite is added in Step 3.1 behind the same sink abstraction.
- Telemetry retention is configurable and follows the project's existing configuration philosophy. It is not hard-coded into the event model.
- Operational logs and trajectory telemetry may share configuration conventions and filesystem policy, but they serve different consumers and should not be collapsed into one record format.

---

## 13. Documentation Strategy

Documentation lives in the repository and is updated with the code:

- **`README.md`:** Current capabilities, quickstart, disclaimer, and high-level roadmap.
- **`AGENTS.md`:** Development-agent guardrails and documentation precedence.
- **`RUNTIME_AGENTS.md`:** Runtime-agent behavioral guardrails.
- **`docs/ARCHITECTURE.md`:** Current architectural boundaries and near-term target seams.
- **`docs/DISCOVERY_WORKBOOK.md`:** Architectural rationale, decisions, and trade-offs.
- **`docs/FINANCE_MATH.md`:** Authoritative project math/data semantics for implemented and explicitly planned deterministic strategies.
- **`docs/GLOSSARY.md`:** Shared project terminology.
- **`docs/HARDWARE.md`:** Light Mode vs Full Dual-Tier requirements and consumer hardware guidance.
- **`docs/MILESTONE_v0_2_IMPLEMENTATION_PLAN.md`:** Operational implementation detail for the active v0.2 milestone.
- **`docs/EVALUATIONS.md`:** **Planned for Step 2.4.** Golden Suite usage, scoring, fixtures, and extension policy.
- **`docs/TOOL_DEVELOPMENT.md`:** **Planned.** Guide for implementing new typed tools.
- **`docs/I18N_GUIDE.md`:** **Planned for localization work.** Translation/report-localization procedures.

Do not assume a planned guide already exists. During implementation, create/update planned documents only in the step that explicitly owns them.

---

*This Master Plan records the current execution roadmap. It is versioned through Git; document version numbers are intentionally not embedded in this document.*
