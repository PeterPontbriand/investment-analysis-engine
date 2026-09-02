# Financial Data Agents: Master Plan

**Repository:** github.com/PeterPontbriand/financial-data-agents<br/>
**Core Strategy:** 100% Local AI (Ollama-Driven Orchestration) with Explicit Reliability Guardrails<br/>
**Primary Focus:** Quantitative investment analysis and a local investor research workbench for personal & professional networks<br/>
**Secondary Focus:** Production-grade local-first AI systems engineering<br/>
**Quality Gate:** Ruff, Strict Static Typing (`mypy --strict`), Pytest<br/>
**Hardware Context:** Two supported modes — **Light Mode** (single-tier, ~8–16 GB VRAM **or** 32 GB+ unified memory) as the recommended mode for most users, and **Full Dual-Tier Mode** (~24–28 GB VRAM) for deeper reasoning. See `docs/user/HARDWARE.md`.<br/>
**Out of Scope (Separate Project):** Full UI integration (e.g., Osiris or WorldMonitor)

**Companion Document:** Master Plan Discovery Workbook (records *why* decisions were made; this Master Plan records *what* and *when*. References to either document mean the current version unless explicitly qualified as a prior or subsequent version).

**Document versioning:** These documents are versioned by Git. Document version numbers are never used within the Master Plan or Discovery Workbook; references to either document mean the current version unless explicitly qualified as a prior or subsequent version.

**Implementation authority:** The Master Plan defines milestone intent and ordering. During an active milestone, the current milestone implementation plan is the more specific operational source for branch sequencing, guardrails, and acceptance criteria. `docs/project/milestones/v0.2/step-2.3/STEP_2_3_GRAHAM_DESIGN.md` is the compact approved specification for completed Step 2.3; `docs/project/milestones/v0.2/step-2.4/STEP_2_4_FCF_EARNINGS_GROWTH_DESIGN.md` is the initial approved design authority for Step 2.4 once its product-policy checkpoint is resolved. Neither overrides milestone scope or review gates. `docs/project/ARCHITECTURE.md` describes current boundaries and labeled target seams; `docs/project/DISCOVERY_WORKBOOK.md` records rationale. If documents conflict, do not blend the instructions—use the more specific/current source and surface the conflict.

---

## 1. Portfolio Competencies & Flagship Showcase

This repository delivers a usable local investment analysis engine while demonstrating production-grade AI systems engineering:

- **Local LLM Orchestration & Tool Dispatching:** Multi-turn state management, schema enforcement, and async function calling on local open-weight models.
- **Systems & Architectural Design:** Modular tiering, async runtime loops, provider abstractions, and clean separation of concerns.
- **Data Engineering & Persistence:** Transactional SQLite storage, schema migration versioning, data quality gates, and local caching pipelines.
- **Quantitative Financial Modeling:** Mathematical rigor across materially different analytical strategies, including the Graham Number screening ceiling, a separate forecast-dependent Graham growth estimate, market-price momentum, historical free-cash-flow and earnings-growth analysis, and later valuation multiples and risk metrics. Analytical strategies are deterministic Python capabilities exposed through typed, swappable interfaces rather than model-specific reasoning.
- **Production Quality & Security:** Defensive static typing (`mypy --strict`), automated unit testing, dependency auditing, and local network isolation.
- **Localization (i18n):** Deep internationalization for Canadian financial standards (`en-CA` / `fr-CA`).

Illustrative use case: An investor adds a ticker to a local watchlist or analyzes it directly under Light Mode, lets the system perform the repetitive quantitative work, and later inspects concise results, detailed provenance, and completed analysis history before deciding what deserves further research.

*(These competencies are the natural output of building something genuinely useful — not a separate target to design toward.)*

---

## 2. High-Level System Architecture

```text
┌────────────────────────────────────────────────────────────────────────────┐
│              Investor-facing terminal / local research workspace           │
│ direct analysis · watchlists (Step 3.4) · run history · result views       │
└───────────────────────────────┬────────────────────────────────────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
     direct deterministic flow             bounded local-LLM flow
      method-specific requests          planning / selection / synthesis
              │                                   │
              └─────────────────┬─────────────────┘
                                ▼
                     Typed Tool / Analysis Dispatch
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
 Momentum analysis        Graham analysis       FCF / earnings growth
 historical prices    number / growth methods   annual financial facts
          │                     │                     │
          │              resolved typed inputs        │
          │                     ▲                     │
          │              InputResolver ◄──────────────┘
          │         override → cache → provider
          │                     │
          ▼                     ▼
   BaseDataClient       Financial-fact providers
 historical prices    quote / fundamentals / macro
          │                     │
          └─────────────┬───────┘
                        ▼
             SQLite / durable cache (Step 3.1)
                        │
                        ▼
            Analysis Run library (Step 3.4)
                        │
                        ▼
       concise · details · diagnostics · JSON views
```

Momentum, Graham, and the Step 2.4 Free Cash Flow & Earnings Growth strategy are intentionally **heterogeneous**. They share the existing tool/orchestration environment and a coherent investor-facing presentation language, but they do not require a common internal result shape. The project must not introduce a speculative strategy/plugin/registry framework or giant generic `AnalysisResult` merely to make the strategies look alike.

Step 2.3 established Graham's method, input-resolution, production-provider, and terminal-presentation foundations. Step 2.4 adds a third deterministic cash-flow/growth strategy to exercise and minimally extend those foundations, then closes the bounded Graham/shared-contract hardening discovered during design-to-implementation reconciliation. Step 2.5 evaluates the resulting stable v0.2 deterministic strategy/tool contracts. Step 3.1 adds durable production persistence/cache. Step 3.4 adds the local research workspace: watchlists, user-initiated concurrent refresh, and a durable Analysis Run library. Step 3.5 validates the complete Light Mode investor workflow and adds only bounded local-model synthesis over already-computed typed results.

## 3. Core Design Principles

1. **Deterministic Execution over Autonomous Guesswork:** Perform math, caching, and data processing in native Python functions; use the LLM strictly for task planning, tool selection, and narrative synthesis.
2. **Local-First & Isolated by Default:** No cloud dependencies for core reasoning; network outbound calls require an explicit local cache miss and pass through an outbound guardrail.
3. **Observable & Auditable by Default:** Agent trajectories are captured as structured telemetry suitable for reconstruction and evaluation. Human-oriented operational logging remains a complementary concern.
4. **Explicit Schema over Prompt Parsing:** Enforce native JSON Schema validation at the API boundary to eliminate unstructured string parsing where supported.
5. **Fail Safely & Gracefully:** Classify failures into transient retries vs. hard boundaries; surface clear diagnostic traces rather than unhandled crashes.
6. **Configurability over Brittle Dependencies:** Prefer clean abstractions and configuration so third-party libraries or engines can be swapped without cascading changes.
7. **Light Mode First for Adoption:** Core useful analysis must work under Light Mode (single-tier / modest hardware) before external validation and before heavier dual-tier features are treated as required.
8. **Heterogeneous Strategy Independence:** Financial-analysis strategies remain independently typed and deterministic. The runtime, data layer, and evaluation harness must not assume that every financial-analysis request is a Momentum request or force materially different strategies into one shape.
9. **Method and Assumption Explicitness:** The Graham Number and forecast-dependent Graham growth value are separate methods. Outputs identify the selected method, input basis, and applicability; the growth method never invents a growth rate. Historical FCF/earnings-growth metrics likewise identify their period basis and do not masquerade as forecasts.
10. **Point-in-Time Data Integrity:** Financial inputs are resolved as of the requested analysis time, carry auditable provenance, and fail unavailable when a provider cannot support the requested historical boundary without look-ahead.
11. **Progressive Disclosure for Investors:** Default output answers the investment question concisely; detailed provenance, resolution diagnostics, and machine-readable output remain one explicit option away. Operational logs are not the investor-facing presentation surface.
12. **Bounded Agentic Work Before Unattended Autonomy:** v0.2 may queue and concurrently execute deterministic analyses in response to a user request and retain completed results. Unattended scheduling, proactive monitoring, notifications, and autonomous multi-step research remain later work.
13. **Time-Aware Security Identity:** A ticker is a venue-scoped, reusable display identifier rather than permanent issuer or instrument identity. Investor views retain the ticker plus best-effort instrument identity and its resolution time; persisted historical runs keep the identity snapshot used at execution instead of silently relabeling an old result through a later ticker lookup.
14. **Deterministic, Versioned Investor-Report Projection:** An investor report is a reproducible projection of a persisted Analysis Run, not a new calculation or canonical result. Projection versions evolve independently from strategy method and result-schema versions, and historical rendering never fetches current provider data or invokes an LLM.

---

## 4. Hardware Strategy & Model Tiering

| Mode / Tier | Target Models (examples) | Typical Footprint | Primary Responsibilities |
| :--- | :--- | :--- | :--- |
| **Light Mode (default)** | `qwen2.5-coder:14b-instruct-q4_K_M` or smaller quantized models | ~8–16 GB VRAM **or** 32–64 GB unified memory | Tool extraction, schema validation, single-step analysis, basic synthesis. Usable by most target users. |
| **Full Dual-Tier — Fast** | `qwen2.5-coder:14b-instruct-q4_K_M` | ~9–11 GB | Tool extraction, schema validation (when dual-tier is active). |
| **Full Dual-Tier — Deep** | `qwen2.5-coder:32b-instruct-q4_K_M` **or** `deepseek-r1:32b` (configurable) | ~19–24 GB | Multi-step planning, complex synthesis, higher-fidelity report generation. |

- Light Mode is the **recommended default** and the operating mode external testers are expected to use.
- Full Dual-Tier Mode remains fully supported for users with workstation-class hardware.
- See `docs/user/HARDWARE.md` for consumer hardware guidance (Apple Silicon, high-memory mini-PCs, discrete GPUs).

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

- **LLM Settings:** Local Ollama base URL and model selection, with Light Mode as the recommended adoption mode.
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

### **Milestone v0.2: Reliability, Observability, Strategy Generalization, Data Persistence & Investor Workflow**

Detailed sequencing, branch strategy, acceptance criteria, implementation guardrails, and review gates for this milestone live in:

→ **`docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md`**

#### Step 2: Agent Reliability, Strategy Generalization, Evaluation & Observability Foundation
* **Branch strategy:** Use fine-grained feature branches aligned with coherent implementation units within each step. Reviewed intermediate checkpoints may be committed/pushed after explicit human approval; an incomplete step must not be represented as complete merely because it has a checkpoint commit.
* **Step 2.1: Trajectory Logging & Telemetry** `[IMPLEMENTED]`: Typed, sink-independent trajectory telemetry with deterministic JSONL persistence. SQLite is added later in Step 3.1 behind the same sink abstraction.
* **Step 2.2: Native Schema Enforcement** `[IMPLEMENTATION COMPLETE / MERGE-READY]`: Prefer native Ollama JSON-schema constraints at structured-output boundaries, retain Pydantic validation as an application-level defense, and use the documented fallback flow when native capability is unavailable or unknown. **Empirical model-by-model Light Mode compatibility remains a non-blocking validation item and must be completed before the Step 3.5 Light Mode exit criterion.**
* **Step 2.3: Dual-Method Graham Strategy, Valuation Input Resolution & Investor Presentation** `[COMPLETE / APPROVED]`: Step 2.3 is complete and approved. It establishes the two Graham methods, provider-neutral resolution/provenance contracts, deterministic fixtures, production SEC/Massive/Yahoo financial-facts adapters, conservative SEC-backed BVPS derivation, investor-facing presenters, and unified direct CLI. The Graham Number using its standard SEC financial facts uses SEC three-year-average diluted EPS plus fiscal-year-end BVPS derivation and Yahoo current quote comparison. SEC-backed Growth uses three-year-average EPS; explicitly selected Massive Growth uses TTM EPS/current quote. Expected growth is always explicit, and no production AAA-yield series is currently approved, so the direct Growth command requires an explicit AAA-yield override. `docs/project/milestones/v0.2/step-2.3/STEP_2_3_GRAHAM_DESIGN.md` remains the compact implementation specification and historical design record.
* **Step 2.4: Free Cash Flow & Earnings Growth Analysis** `[COMPLETE / APPROVED]`: The third deterministic strategy, E1–E3 FCF/share extension, pre-Golden shared-contract hardening, F-1 shared security-identity presentation work, and Slice G documentation/final-gate closeout are complete and approved as of 2026-08-30. The approved strategy is a historical cash-flow/growth screen using project-defined `FCF = CFO - CapEx`, explicit period alignment and provenance, both total-company-FCF and FCF-per-diluted-share growth, and historical diluted-EPS growth. Total-company-FCF CAGR controls classification by default; an explicit typed policy/CLI override may select FCF/share CAGR instead. Do not silently turn this into DCF, analyst-forecast growth, a broad named-investor methodology, or a composite recommendation score. `docs/project/milestones/v0.2/step-2.4/STEP_2_4_FCF_EARNINGS_GROWTH_DESIGN.md` governs the strategy.
* **Step 2.5: Golden-Test Suite & Strategy Evaluation** `[COMPLETE / APPROVED]`: P1, the Gate M-directed Slice H corrections, Slices I–J, and Slice K closeout are complete and approved as of 2026-08-31. The canonical deterministic report passed 15/15; optional empirical execution is explicitly recorded as not run. The closeout record reconciles every acceptance criterion without weakening the benchmark.
* **Step 2.5A: SEC EDGAR Foreign-Private-Issuer Annual-Filing Coverage** `[COMPLETE / APPROVED]`: completed and approved on 2026-09-01. The existing SEC adapter now supports reviewed foreign annual forms, request-scoped snapshot/taxonomy selection, exact IFRS duration concepts, and fail-closed security-unit comparison. Golden `h1-v3` passed 19/19 cases and the repository gate passed 1,288 tests at 88% coverage. IFRS BVPS, absence-based preferred-zero inference, ADR/ADS conversion, currency conversion, custom extensions, and broad concept fallback remain deferred.
* **Step 2.6: Circuit Breakers & Timeout Limits**: Enforce hard execution caps, wall-clock bounds, retry/error thresholds, and clean diagnostics.

#### Step 3: Relational Data Persistence, Data Quality & Local Research Workspace (SQLite)
* **Branch strategy:** Use fine-grained branches aligned with Step 3 implementation units.
* Repositories live under `src/data/repositories/`.
* **Step 3.1: SQLite DB & Migration Infrastructure:** Set up Alembic, enforce WAL mode, establish market-data and trajectory storage, add `SQLiteTrajectorySink`, and implement durable cache/persistence behind the historical-price and financial-fact contracts established in Steps 2.3–2.4.
* **P2: Durable Instrument Profiles & ETF Aggregate FCF Growth — after Step 3.1:** After Step 3.1 is implemented and approved, review P2's exact placement relative to Steps 3.2–3.4. Persist time-aware instrument profiles behind the P1 seam with explicit provenance/freshness/invalidation rules, then complete a separate provider/product-policy gate before adding a distinct look-through ETF FCF-growth strategy. The ETF strategy owns its holdings, weighting, currency, coverage, and `as_of` semantics and must not be hidden inside or silently substituted for the existing company-level strategy.
* **Step 3.2: DAO & Repository Layer:** Build strongly typed data-access/repository interfaces and SQLite implementations for market data, trajectory records, and metadata.
* **Step 3.3: Data Quality & Cache Invalidation Pipeline:** Validate incoming financial data (currency consistency, corporate actions where applicable, continuity/missing data, and staleness) and apply controlled cache refresh/invalidation rules.
* **Step 3.4: Local Research Workspace & Analysis Run Library:** Add named watchlists, ticker membership and supported analysis selections, durable Analysis Run records, user-initiated concurrent refresh, and commands to list/show completed runs. The initial automatic/default watchlist profile uses analyses that require no invented forecast assumptions (Momentum, Graham Number, and the historical FCF/Earnings Growth strategy once Step 2.4 is complete); the Graham growth method participates only with explicit stored/user-supplied assumptions. An Analysis Run is the durable product artifact; an investor report is a deterministic, explicitly versioned projection of that run rather than a separately generated canonical object. The projection version is independent of calculation method and result-schema versions; replaying a stored run does not call a provider or LLM, recalculate financial values, read mutable current state, or silently reinterpret an older projection contract. Each run persists the security identity/instrument-profile snapshot used at execution, including its provider, resolution time, kind evidence, and any available venue/issuer/instrument identifiers; historical views do not re-resolve ticker alone and thereby risk relabeling a recycled symbol. No background daemon, unattended scheduler, notifications, full-screen TUI, or executive-report generator is introduced here.

#### Step 3.5: Light Mode Support (required before v0.2.5)
* **Goal:** Ensure the complete investor workflow—data fetch/cache → deterministic analytics → stored Analysis Run → concise/detailed inspection → bounded local-model synthesis—runs cleanly under Light Mode with a 14B-class (or smaller) model.
* **Deliverables:** Configuration defaults favor Light Mode; README and `docs/user/HARDWARE.md` provide the supported workflow; basic smoke tests pass; Step 2.2 empirical schema/model compatibility is recorded; a simple `analyze TICKER` workflow may combine the default deterministic analyses and optionally synthesize their already-computed typed results.
* **Synthesis boundary:** The LLM may explain or compare deterministic evidence, but it does not create financial facts, perform valuation arithmetic, or invent growth assumptions. Failure of synthesis must not discard valid deterministic results.
* **Exit criterion:** A new user following only the Light Mode instructions can add or analyze a real ticker, run/refresh supported analyses, inspect a concise result and its provenance, revisit completed Analysis Runs, and obtain bounded synthesis without developer intervention.

### **Milestone v0.2.5: Real-User Validation Checkpoint**
This milestone answers a question none of the technical quality gates can answer: does this help anyone besides the author?

* **Step 0.5.1:** Recruit at least 3 external testers using Light Mode.
* **Step 0.5.2:** Capture structured feedback about setup, watchlist/direct-analysis workflow, confusion, failures, whether concise/detail views expose the right information, whether provenance builds trust, whether the output changed what the tester wanted to investigate next, and desired capabilities.
* **Step 0.5.3:** Confirm or adjust hardware assumptions using actual tester hardware.
* **Step 0.5.4:** Re-prioritize Milestone v0.3 using the findings, including whether `fr-CA` localization remains in v0.3.
* **Exit criterion:** At least 3 completed tester sessions using the real Light Mode investor workflow, documented findings, and v0.3 scope confirmed or adjusted before Step 4 begins.

### **Milestone v0.3: Analytics Expansion & Canadian Localization**
#### Step 4: Analytical Expansion & Quantitative Modeling
Momentum, Graham, and the historical Free Cash Flow & Earnings Growth strategy are established earlier as architectural/evaluation exemplars. Step 4 expands the analytical library rather than defining its first strategy contracts. New strategies remain independently specified, deterministic, and strongly typed; the roadmap does not treat a broad named-investor philosophy as an implementable strategy unless it is decomposed into explicit, testable analytical rules.

* **Step 4.1: Additional Fundamental Valuation Multiples & Screening Analyzers:** Add deterministic fundamental and relative-valuation screens using the existing typed analysis and financial-fact boundaries.
  * **Price-to-Cash-Flow and Price-to-Free-Cash-Flow Screens (`P/CF` & `P/FCF`):** Implement analyzers evaluating market capitalization against operating cash flow (`P/CF = Market Cap / Operating Cash Flow`) and free cash flow (`P/FCF = Market Cap / FCF`). These are valuation multiples/screens rather than intrinsic-value models.
  * **Free-Cash-Flow Reuse:** Reuse the Step 2.4 canonical FCF definition (`FCF = CFO - CapEx`), CapEx sign normalization, period-alignment rules, provenance, and edge-case semantics rather than defining a competing FCF calculation. Broader FCF variants or discounted-cash-flow models require separate explicit specification.
  * **Candidate Independent Analyses:** Subject to separate product-policy approval and data evidence, consider independently typed deterministic analyses for cash-conversion quality; ROIC and incremental-ROIC/reinvestment opportunity; point-in-time estimate revisions; growth-adjusted cash-flow valuation; and leverage and earnings stability. FCF/share growth is owned by Step 2.4 and may be consumed independently by later aggregation. These candidates do not define a composite method.
  * **Data & Resolution Seam:** Reuse and extend the financial-fact boundary established in Steps 2.3–2.4 rather than adding provider-specific retrieval logic to the analyzer.
* **Step 4.2: Additional Technical Indicators:** Expand beyond the initial SMA/crossover Momentum implementation (for example RSI/EMA/MACD only when explicitly selected and specified).
* **Step 4.3: Analytical Aggregator & Risk Metrics:** Combine independent deterministic strategy outputs (for example Graham ceilings, momentum signals, FCF/earnings-growth trends, and cash-flow valuation multiples) into unified typed models with basic risk measures such as maximum drawdown and volatility. Later product-policy work may define a composite screen, universe screening, or cross-sectional ranking over those outputs. Before implementation, any such method must explicitly define and validate its comparison universe; sector-relative versus absolute treatment; normalization and outlier handling; missing-data policy; formulas, thresholds, and weights; point-in-time data boundaries; evaluation/rebalancing frequency; empirical or backtest evidence; and versioned deterministic result semantics. The LLM may select, combine, and explain typed results, but it may not perform, improvise, or silently reweight the financial calculations.

#### Step 5: Localization Engine for Canadian Markets (en-CA / fr-CA)
* **Status note:** Scope and timing are confirmed at Milestone v0.2.5.
* **Step 5.1:** i18n core framework.
* **Step 5.2:** Localized financial/currency formatters.
* **Step 5.3:** Locale-aware reporting text and compliance disclaimers.

### **Milestone v1.0: Multi-Step Autonomy & Executive Reporting**
* **Entry criterion:** Milestone v0.2.5 exit criteria met, and at least 1 tester has confirmed an output was genuinely useful.

#### Step 6: Autonomous Multi-Step Tool Integration (Hardened)
* **Step 6.1:** Multi-Step Planner, including unattended/scheduled research only after the v0.2.5 evidence gate justifies it.
* **Step 6.2:** Argument Sanitization & Self-Correction, bounded recovery, and proactive-monitoring guardrails.
* **Step 6.3:** Continuous Golden-Suite Evaluation Gate using the Step 2.5 benchmark infrastructure. Notifications/proactive monitoring must remain opt-in and policy-bounded.

#### Step 7: High-Fidelity Data Visualization & Report Generation
* **Step 7.1:** Static plotting engine.
* **Step 7.2:** Executive Markdown/PDF report generation with charts, audit identifiers, and disclaimers.

---

## 9. Performance & Quality Targets

| Category | Metric | Target Threshold |
| :--- | :--- | :--- |
| **Code Quality** | Type Coverage | Zero mypy (`mypy --strict`) errors in supported source code and tests |
| **Code Quality** | Annotation Completeness | 100% typed public interfaces |
| **Testing** | Unit Test Line Coverage | ≥ 85% project-wide (`pytest --cov=src`) |
| **Agent Accuracy** | Golden Benchmark Pass Rate | ≥ 90% aggregate pass rate, with tool-selection and numeric correctness measured separately |
| **Performance** | CLI Startup Latency | < 500 ms (excluding Ollama/model initialization and network access) |
| **Performance** | SQLite Query Latency | < 50 ms (indexed local cache lookup under representative single-user workload) |
| **Reliability** | Unhandled Agent Exceptions | 0 on golden test suite |
| **Adoption** | Light Mode investor workflow (analyze/watchlist → refresh → stored run → concise/details/provenance) documented and smoke-tested | Required before Milestone v0.2.5 |
| **User Validation** | External testers who completed the real Light Mode investor workflow | ≥ 3 before Milestone v1.0 begins |
| **User Validation** | External testers confirming a genuinely useful output | ≥ 1 before Milestone v1.0 begins |

---

## 10. Operational Risk Register & Mitigations

| Risk Event | Potential Impact | Architectural Mitigation Strategy |
| :--- | :--- | :--- |
| **External API Changes (`yfinance`)** | Upstream data fetch failures or field-semantic drift | Keep historical prices and financial facts behind narrow provider boundaries; validate fields and provenance; rely on the appropriate cache where available. |
| **Point-in-time look-ahead** | Historical analysis accidentally consumes facts published later | Enforce `as_of` at resolution time, record observation/publication/availability timestamps, and return unavailable when a provider cannot answer safely. |
| **Local LLM Output Drift / Schema Violation** | Failed tool parsing, infinite retries | Enforce native Ollama JSON schemas (`format`) + Pydantic validation + circuit breaker caps. |
| **Context Degradation on Long Turns** | Model forgets original goal or tool rules | Prune middle conversation context while strictly locking `Role.SYSTEM` at index 0. |
| **Database Lock / Concurrency Latency** | DB timeouts during multi-tool execution | Enforce SQLite Write-Ahead Logging (WAL) mode and single-writer/multi-reader connection pooling. |
| **Hardware barrier excludes target users** | Dual-tier requirements out of reach for most Primary Users | **Light Mode is the default operating mode.** Full Dual-Tier is optional. Hardware requirements are surfaced early in README and `docs/user/HARDWARE.md`. External validation (v0.2.5) runs under Light Mode. |
| **Strategy fixation / analytical monoculture** | Local model repeatedly selects the first/only familiar analytical strategy even when another is appropriate | Maintain materially different deterministic analyzers behind the same existing runtime interface; Step 2.5 measures strategy selection separately from numerical correctness; do not special-case the orchestrator around one strategy. |
| **User-facing architecture remains developer-shaped** | Real testers can run the software but cannot quickly understand or revisit results | Use concise investor-facing presentation, progressive disclosure, durable Analysis Runs, and Step 3.4 watchlist/run browsing before v0.2.5. |

---

## 11. CI/CD Pipeline & Automated Quality Gates

Every Pull Request must pass the following automated GitHub Actions pipeline before merge approval:

1. **Lint & Code Style:** `ruff check . && ruff format --check .`
2. **Strict Static Analysis:** `mypy --strict src tests`
3. **Unit Tests & Coverage:** `pytest --cov=src --cov-report=term-missing`
4. **Security & Dependency Audit:** `uv audit` / `pip-audit` for known vulnerabilities.
5. **Golden Agent Evaluation:** Headless deterministic execution of the Step 2.5 Golden Suite in its no-LLM/test mode. Optional real-local-Ollama evaluation is recorded separately and is not a mandatory CI dependency unless explicitly configured.

---

## 11.5 Strategy/Data Contracts & Golden-Test Determinism

The project distinguishes these related but separate concerns:

1. **Operational logs** answer what happened operationally.
2. **Trajectory telemetry** answers what the agent/runtime did during an execution.
3. **Historical-price and financial-fact contracts** define what deterministic analytics may request.
4. **Golden fixtures** provide immutable deterministic evidence for benchmark execution.
5. **Production persistence/cache** provides durable market/fundamental data storage beginning in Step 3.1.
6. **Evaluation results** record whether a benchmark run selected the correct strategy/tool and produced the correct deterministic result.
7. **Analysis Runs** are durable investor-domain records of requested analyses, configurations, typed results, provenance, warnings, status, and timestamps; Step 3.4 owns this product-facing history.
8. **Result views/reports** are deterministic, explicitly versioned projections of an Analysis Run in concise terminal, detailed, diagnostic, JSON, or later Markdown/PDF form. In v0.2 a report is not a second canonical persisted result object. Projection versions evolve independently from calculation method and result-schema versions; historical projections use only persisted run evidence and explicit rendering options.

Step 2.3 established the minimum data capabilities required by Momentum and Graham:

- historical market data for Momentum through `BaseDataClient`;
- quote and fundamental facts for Graham through a dedicated valuation boundary, plus a macro-observation contract that does not imply an approved production AAA series;
- field-by-field input resolution with overrides, a minimal cache seam, strict as-of handling, and provenance.

Step 2.4 minimally extends those financial-fact/resolution foundations for period-aligned operating cash flow and capital expenditures, derives project-defined FCF with explicit lineage, and adds historical FCF/diluted-EPS growth semantics without creating a parallel data architecture. Before closeout, it also hardens the shared contracts that the Golden Suite will depend on: result invariants, investor-facing status language, typed failure presentation, quote classification, earnings/share compatibility, supported Graham routing, and exact presentation regression evidence.

Step 2.5 builds the Golden Suite only after that hardening is complete and approved, so benchmark fixtures record deliberate public behavior rather than known incidental inconsistencies. Its Gate M review requires exact expected domain outcomes and one canonical deterministic report before approval. Step 2.5A then extends the current SEC adapter through the same provider-neutral fact/provenance boundaries: foreign annual forms for existing US-GAAP duration facts first, followed by exact IFRS duration concepts behind analysis-scoped payload consistency, latest-eligible-accession taxonomy selection, and security-unit compatibility. Step 3.1 later supplies production SQLite/cache-backed implementations.

The Golden Suite must never silently fall back to live market data when fixture evidence is missing.

---

## 11.6 Investor-Facing Presentation Boundary

Investor-facing output is a presentation concern, not an excuse to force heterogeneous strategies into one internal result model. Momentum, Graham, and Free Cash Flow & Earnings Growth retain strategy/method-specific typed result objects; strategy-specific presenters map those results into a coherent visual grammar. Before the Golden Suite begins, every status must have an explicit plain-English investor label and successful and failed executions must cross one typed result/presentation boundary, even when concise rendering reduces a failure to one friendly sentence:

- identity: ticker, analysis/method, requested `as_of`;
- status/applicability;
- headline metrics and plain-language relationship between them;
- source/freshness summary;
- material warnings and visible user overrides;
- `--details` for financial provenance/derivations;
- `--diagnostics` for resolution/cache/provider behavior; and
- `--json` for stable machine-readable output.

Operational logging remains on the diagnostics/logging subsystem and must not be used as the primary investor-facing renderer. The default view favors high-signal financial information; raw provider/cache mechanics are progressively disclosed.

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
- **`docs/project/ARCHITECTURE.md`:** Current architectural boundaries and near-term target seams.
- **`docs/project/DISCOVERY_WORKBOOK.md`:** Architectural rationale, decisions, and trade-offs.
- **`docs/user/FINANCE_MATH.md`:** Authoritative project math/data semantics for implemented and explicitly planned deterministic strategies.
- **`docs/user/GLOSSARY.md`:** Shared project terminology.
- **`docs/user/HARDWARE.md`:** Light Mode vs Full Dual-Tier requirements and consumer hardware guidance.
- **`docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md`:** Operational implementation detail for the active v0.2 milestone.
- **`docs/project/milestones/v0.2/step-2.3/STEP_2_3_GRAHAM_DESIGN.md`:** Compact approved Step 2.3 method, resolution, provenance, CLI, fixture, and review record.
- **`docs/project/milestones/v0.2/step-2.4/STEP_2_4_FCF_EARNINGS_GROWTH_DESIGN.md`:** Initial Step 2.4 financial, data, CLI, presentation, and review design.
- **`docs/EVALUATIONS.md`:** Step 2.5 Golden Suite status, usage target, scoring, fixtures, reporting, and extension policy.
- **`docs/TOOL_DEVELOPMENT.md`:** **Planned.** Guide for implementing new typed tools.
- **`docs/I18N_GUIDE.md`:** **Planned for localization work.** Translation/report-localization procedures.

Do not assume a planned guide already exists. During implementation, create/update planned documents only in the step that explicitly owns them.

---

*This Master Plan records the current execution roadmap. It is versioned through Git; document version numbers are intentionally not embedded in this document.*
