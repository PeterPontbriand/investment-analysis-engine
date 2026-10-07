# Investment Analysis Engine: Master Plan

This roadmap defines the product direction, release goals and engineering constraints.

The [milestone plan](milestones/v0.2/IMPLEMENTATION_PLAN.md) owns active work-package
scope and status. The [v0.3 plan](milestones/v0.3/IMPLEMENTATION_PLAN.md) holds the draft
scope of the next milestone. [Architecture](ARCHITECTURE.md) explains system boundaries;
the [Discovery Workbook](DISCOVERY_WORKBOOK.md) records rationale.

## 1. Portfolio Competencies & Flagship Showcase

This repository delivers a usable local investment analysis engine while demonstrating production-grade AI systems engineering:

- **Local LLM Orchestration & Tool Dispatching:** Multi-turn state management, schema enforcement, and async function calling on local open-weight models.
- **Plain-English Questions, Evidence-Backed Answers (planned, v0.3):** A person asks a question in ordinary words and gets an answer in ordinary words. Every sentence points to stored evidence, and every number is placed by the engine from that evidence, never typed by a model.
- **Systems & Architectural Design:** Modular tiering, async runtime loops, provider abstractions, and clean separation of concerns.
- **Data Engineering & Persistence:** Transactional SQLite storage, schema migration versioning, data quality gates, and local caching pipelines.
- **Quantitative Financial Modeling:** Mathematical rigor across materially different analytical strategies, including the Graham Number screening ceiling, a separate forecast-dependent Graham growth estimate, market-price momentum, historical free-cash-flow and earnings-growth analysis, the Step 3.5 quantitative screening suite (Piotroski F-Score, Altman Z-Score, Beneish M-Score, EV/EBITDA & FCF Yield, Greenblatt Magic Formula ranking, Interest Coverage, and ROIC / Incremental ROIC), and later valuation multiples and risk metrics. Analytical strategies are deterministic Python capabilities exposed through typed, swappable interfaces rather than model-specific reasoning.
- **Production Quality & Security:** Defensive static typing (`mypy --strict`), automated unit testing, dependency auditing, and local network isolation.
- **Localization (i18n):** Deep internationalization for Canadian financial standards (`en-CA` / `fr-CA`).

Illustrative use case: An investor adds a ticker to a local watchlist or analyzes it directly under Light Mode, lets the system perform the repetitive quantitative work, and later inspects concise results, detailed provenance, and completed analysis history before deciding what deserves further research.

Planned for v0.3: the same investor asks "Is this company's financial position getting weaker?" and reads a short answer in which each statement can be traced to a stored result or a quoted filing passage.

*(These competencies are the natural output of building something genuinely useful — not a separate target to design toward.)*

---

## 2. High-Level System Architecture

### Today

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

Momentum, Graham, the Step 2.4 Free Cash Flow & Earnings Growth strategy, and the Step 3.5 quantitative screening suite are intentionally **heterogeneous**. They share the existing tool/orchestration environment and a coherent investor-facing presentation language, but they do not require a common internal result shape. The project must not introduce a speculative strategy/plugin/registry framework or giant generic `AnalysisResult` merely to make the strategies look alike.

Step 2.3 established Graham's method, input-resolution, production-provider, and terminal-presentation foundations.  Step 2.5 evaluates the resulting stable v0.2 deterministic strategy/tool contracts. Step 3.1 adds durable production persistence/cache. Step 3.4 adds the local research workspace: watchlists, user-initiated concurrent refresh, and a durable Analysis Run library. Step 3.5 adds the deterministic quantitative screening suite.

### Planned for v0.3: asking in plain English

```text
"Is this company's financial position getting weaker?"
        │
        ▼
1. Understand   a local model turns the question into a typed research plan
        │       (which company, which topics, which date) or declines it
        ▼
2. Gather       deterministic analyses run and are stored as Analysis Runs;
        │       filing events and filing readings add dated evidence from SEC filings
        ▼
3. Write        a local model writes sentences; each names its evidence,
        │       and the engine fills in every number
        ▼
4. Check        each sentence is tested against its evidence;
        │       a sentence that fails is removed
        ▼
5. Answer       plain-English answer with sources, stored as an Answer Record
```

A model has four narrow jobs here: understand the question, read a named part of a filing, write sentences, and check sentences. It never calculates, never types a number, and never advises, scores or ranks. The [v0.3 plan](milestones/v0.3/IMPLEMENTATION_PLAN.md) has the detail.

## 3. Core Design Principles

1. **Deterministic Execution over Autonomous Guesswork:** Perform math, caching, and data processing in native Python functions; use the LLM strictly for task planning, tool selection, and narrative synthesis. From v0.3 those jobs narrow to four: understand the question, read a named part of a filing, write sentences, and check them. Rules, not the model, then decide which analyses apply.
2. **Local-First & Isolated by Default:** No cloud dependencies for core reasoning; network outbound calls require an explicit local cache miss and pass through an outbound guardrail.
3. **Observable & Auditable by Default:** Agent trajectories are captured as structured telemetry suitable for reconstruction and evaluation. Human-oriented operational logging remains a complementary concern.
4. **Explicit Schema over Prompt Parsing:** Enforce native JSON Schema validation at the API boundary to eliminate unstructured string parsing where supported.
5. **Fail Safely & Gracefully:** Classify failures into transient retries vs. hard boundaries; surface clear diagnostic traces rather than unhandled crashes.
6. **Configurability over Brittle Dependencies:** Prefer clean abstractions and configuration so third-party libraries or engines can be swapped without cascading changes.
7. **Light Mode First for Adoption:** Core useful analysis must work under Light Mode (single-tier / modest hardware) before heavier dual-tier features are treated as required.
8. **Heterogeneous Strategy Independence:** Financial-analysis strategies remain independently typed and deterministic. The runtime, data layer, and evaluation harness must not assume that every financial-analysis request is a Momentum request or force materially different strategies into one shape.
9. **Method and Assumption Explicitness:** The Graham Number and forecast-dependent Graham growth value are separate methods. Outputs identify the selected method, input basis, and applicability; the growth method never invents a growth rate. Historical FCF/earnings-growth metrics likewise identify their period basis and do not masquerade as forecasts.
10. **Point-in-Time Data Integrity:** Financial inputs are resolved as of the requested analysis time, carry auditable provenance, and fail unavailable when a provider cannot support the requested historical boundary without look-ahead.
11. **Progressive Disclosure for Investors:** Default output answers the investment question concisely; detailed provenance, resolution diagnostics, and machine-readable output remain one explicit option away. Operational logs are not the investor-facing presentation surface.
12. **Bounded Agentic Work Before Unattended Autonomy:** v0.2 may queue and concurrently execute deterministic analyses in response to a user request and retain completed results. Unattended scheduling, proactive monitoring, notifications, and autonomous multi-step research remain later work.
13. **Time-Aware Security Identity:** A ticker is a venue-scoped, reusable display identifier rather than permanent issuer or instrument identity. Investor views retain the ticker plus best-effort instrument identity and its resolution time; persisted historical runs keep the identity snapshot used at execution instead of silently relabeling an old result through a later ticker lookup.
14. **Deterministic, Versioned Investor-Report Projection:** An investor report is a reproducible projection of a persisted Analysis Run, not a new calculation or canonical result. Projection versions evolve independently from strategy method and result-schema versions, and historical rendering never fetches current provider data or invokes an LLM.
15. **Answers Are Built Only From Stored Evidence:** A plain-English answer may state only what stored evidence supports. Every sentence names its evidence, every number is placed by the engine from a stored value, and missing evidence is stated, not skipped. An answer is stored once; showing it again never calls a model.
16. **Evidence, Not Advice:** The engine does not tell anyone to buy, sell or hold, and it attaches no score, rank or probability to an instrument's prospects. A model's confidence is used only to decide between *found*, *not found* and *not determined* for a narrow factual reading, and is not shown beside an instrument. Forecast-ledger entries are measurement records and never appear in an investor view.
17. **Measured Before Trusted:** A model-based step is used only after its accuracy has been measured against known answers on the model Light Mode actually runs. If a plain rule does the job as well, the rule is used.

---

## 4. Hardware Strategy & Model Tiering

| Mode / Tier | Target Models (examples) | Typical Footprint | Primary Responsibilities |
| :--- | :--- | :--- | :--- |
| **Light Mode (default)** | `qwen2.5-coder:14b-instruct-q4_K_M` or smaller quantized models | ~8–16 GB VRAM **or** 32–64 GB unified memory | Tool extraction, schema validation, single-step analysis, basic synthesis. Usable by most target users. |
| **Full Dual-Tier — Fast** | `qwen2.5-coder:14b-instruct-q4_K_M` | ~9–11 GB | Tool extraction, schema validation (when dual-tier is active). |
| **Full Dual-Tier — Deep** | `qwen2.5-coder:32b-instruct-q4_K_M` **or** `deepseek-r1:32b` (configurable) | ~19–24 GB | Multi-step planning, complex synthesis, higher-fidelity report generation. |

- Light Mode is the **recommended default**. Plain-English answers (v0.3) must run within its footprint; a second, smaller model is allowed only if both fit together.
- Full Dual-Tier Mode remains fully supported for users with workstation-class hardware.
- See `docs/user/HARDWARE.md` for consumer hardware guidance (Apple Silicon, high-memory mini-PCs, discrete GPUs).

Deep-tier model selection (when used) remains a configuration choice rather than a hard commitment.

---

## 5. Security & Isolation Model

- **Tool Execution Boundaries:** Tools operate on explicit typed parameters. No dynamic string evaluation (`eval()`) or raw shell command invocation.
- **Outbound Network Guard:** All remote calls (e.g., `yfinance`) are routed through a single outbound client wrapper enforcing rate limits, local cache checks, and domain whitelisting.
- **Filesystem Constraints:** File outputs (reports, logs) are restricted to designated subdirectories (`/reports`, `/logs`, `/data`).
- **Prompt Injection Defense:** External data (e.g., news headlines, raw text from financial APIs) is sanitized and wrapped in clear data delimiters before injection into model context. From v0.3 this covers SEC filing text: a model reading a filing may answer only fixed questions with fixed choices, and the model that writes an answer sees findings and short quoted passages, never a whole filing.
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
- **Ask Settings (v0.3):** Which local model understands questions and writes answers, which reads filings and checks sentences, the accuracy bars each must meet, and how many filings one question may read.
- **Execution Limits:** Max planning steps (default: 10), Max transient retries (default: 3); subsequent reliability work may add more explicit timeout/error limits.
- **Cache & Database:** SQLite connection path and later persistence/cache settings.
- **Localization:** System default locale (`en-CA` / `fr-CA`), Currency defaults (`CAD`).
- **Operational Logging:** The existing `src/utils/logger_util.py` uses configurable log level, file name, maximum file size, backup count, encoding, and time-based rotation settings. Structured trajectory telemetry should reuse the existing configuration conventions rather than inventing a separate logging configuration mechanism.
- **Trajectory Telemetry:** Structured telemetry has its own configuration namespace within the same settings system where its storage/retention controls differ materially from human-readable operational logs. Retention and storage limits are configurable, not architectural constants.

---

## 8. Ordered Implementation Steps & Release Milestones

| Order | Release | Status | Completed |
| :--- | :--- | :--- | :--- |
| 1 | [v0.1 — orchestration](#milestone-v01-core-orchestration-engine) | Complete | 2026-07-31 |
| 2 | [v0.2 — analysis and research workspace](milestones/v0.2/IMPLEMENTATION_PLAN.md#sequence-and-status) | In progress | |
| 3 | [v0.3 — plain-English questions, evidence-backed answers](#milestone-v03-plain-english-questions-evidence-backed-answers) | Next | |
| 4 | [v0.4 — analytical expansion and localization](#milestone-v04-analytics-expansion--canadian-localization) | Planned | |
| 5 | [v1.0 — autonomy and reporting](#milestone-v10-multi-step-autonomy--executive-reporting) | Planned | |

**Work-package identifiers.** Within an active milestone's own implementation plan, most
work-package rows follow the roadmap's own decimal Step/Slice numbering (`2.3`, `3.3A`, ...).
A smaller number of rows instead use a short, milestone-scoped letter code, reserved for work
that does not fit neatly as a sub-number of one existing Step — typically because it cuts across
several existing Steps (a refactor, an audit) or was identified mid-milestone rather than planned
from the start. A bare `Issue #NN` reference is a GitHub issue folded into a work package's scope,
not a code in this scheme. Within any one lettered or numbered work package, its own contract
document may further divide implementation into slices (`Slice A`, `Slice B1`, ...) — a
convention local to that one document, not a project-wide identifier. Each milestone's own
implementation plan defines, lists, and links its current letter codes; consult that plan for what
a specific code stands for, rather than expecting this document to enumerate them.

Milestone v0.3 uses letter codes (`ASK`, `FL`, `FR`) because it was planned after Steps 4–7 had been numbered. Steps 4–7 keep their numbers, so existing references to them still hold.

### **Milestone v0.1: Core Orchestration Engine**

#### Step 1: Local Orchestration Engine & Structured Tool Dispatch
* **Step 1.1: Environment Config & Core LLM Client**
* **Step 1.2: Pydantic Tool Definition & Parsing Layer**
* **Step 1.3: Asynchronous Orchestration Loop & Message Context**

### **Milestone v0.2: Reliability, Observability, Strategy Generalization, Data Persistence & Investor Workflow**

Deliver deterministic financial analyses with provenance, reliable local orchestration,
persistent research records and a usable Light Mode workflow. The
[implementation plan](milestones/v0.2/IMPLEMENTATION_PLAN.md) owns work-package
scope, sequencing and status; its companion contracts supply technical detail.

The [research-workspace contract](milestones/v0.2/step-3.4/STEP_3_4_CONTRACT_AND_SLICE_PLAN.md) defines watchlist, Analysis Run, replay and refresh interfaces with bounded implementation slices.

### **Milestone v0.3: Plain-English Questions, Evidence-Backed Answers**
**Entry condition:** Milestone v0.2 is complete, including the Step 3.5 screens and Light Mode (Step 3.6).

A person asks a question in ordinary words and gets an answer in ordinary words, built only from evidence the engine has stored. The [v0.3 plan](milestones/v0.3/IMPLEMENTATION_PLAN.md) owns work-package scope, order and acceptance numbers; it is a draft until v0.2 closes.

| Work package | What it delivers |
| :--- | :--- |
| **ASK.0 — Feasibility checks** | Measures, before anything is designed, whether a Light Mode model can understand questions, read filing passages and check sentences well enough. |
| **FL.1 — Forecast ledger, recording only** | Each covered Analysis Run stores a few dated questions that later facts will settle. Nothing is scored yet and nothing is shown to an investor. |
| **FR.1 — Filing events** | Dated warning signs taken from SEC filing records with no model: late-filing notices, auditor changes, non-reliance statements, amended annual reports. |
| **ASK.1 — Ask** | `ian ask "<question>"`: question → research plan → Analysis Runs → written answer with sources, stored as an Answer Record. Results are ordered by how well they bear on the question. A preference the investor states in words becomes a visible filter that the engine applies by rule; the investor may name one measure to sort by. |
| **ASK.2 — Answer check** | Every sentence is tested against its evidence before it is shown; a sentence that fails is removed. |
| **FR.2 — Filing reading** | A model answers a short list of fixed questions about named parts of filings (for example, going-concern doubt) and quotes the passage it relied on. |

**Not in this milestone:** advice; any score, rank or probability about an instrument; model arithmetic; a cloud model; memory between questions. The test for any proposed model job: if its answer would change which instrument looks better, it does not belong to a model.

**Exit criterion:** Under Light Mode, a fixed set of plain-English questions is answered so that every sentence traces to stored evidence, no number was typed by a model, requests for advice are declined with an explanation, and the accuracy bars in the v0.3 plan are met on labelled examples.

**Two outcomes, both a success.** If ASK.0 shows that no Light Mode model meets the bars, the milestone delivers its floor: a fixed menu of questions, answers assembled by rule, filing events and keyword filing rules. The floor needs no model and keeps every guarantee above. The [v0.3 plan](milestones/v0.3/IMPLEMENTATION_PLAN.md#2-sequence-and-status) compares the two levels.

### **Milestone v0.4: Analytics Expansion & Canadian Localization**
**Entry condition:** Milestone v0.3 is complete.

#### Step 4: Analytical Expansion & Quantitative Modeling
Momentum, Graham, Free Cash Flow & Earnings Growth, and the Step 3.5 quantitative screening suite (Piotroski F-Score, Altman Z-Score, Beneish M-Score, EV/EBITDA & FCF Yield, Greenblatt Magic Formula) are already established. Step 4 expands the analytical library rather than introducing the first fundamental screens. New strategies remain independently specified, deterministic, and strongly typed; the roadmap does not treat a broad named-investor philosophy as an implementable strategy unless it is decomposed into explicit, testable analytical rules.

* **Step 4.1: Additional Fundamental Valuation Multiples & Screening Analyzers:** Add deterministic fundamental and relative-valuation screens using the existing typed analysis and financial-fact boundaries.
  * **Price-to-Cash-Flow and Price-to-Free-Cash-Flow Screens (`P/CF` & `P/FCF`):** Implement analyzers evaluating market capitalization against operating cash flow (`P/CF = Market Cap / Operating Cash Flow`) and free cash flow (`P/FCF = Market Cap / FCF`). These are valuation multiples/screens rather than intrinsic-value models.
  * **Free-Cash-Flow Reuse:** Reuse the Step 2.4 canonical FCF definition (`FCF = CFO - CapEx`), CapEx sign normalization, period-alignment rules, provenance, and edge-case semantics rather than defining a competing FCF calculation. Broader FCF variants or discounted-cash-flow models require separate explicit specification.
  * **Candidate Independent Analyses:** Subject to separate product-policy approval and data evidence, consider independently typed deterministic analyses for cash-conversion quality; point-in-time estimate revisions; growth-adjusted cash-flow valuation; and leverage and earnings stability. FCF/share growth is owned by Step 2.4 and may be consumed independently by later aggregation. These candidates do not define a composite method. ROIC and incremental ROIC, formerly a candidate here, moved into Step 3.5 on 2026-09-30. See the [Evidence Provider Roadmap](EVIDENCE_PROVIDER_ROADMAP.md) for further, less-developed candidates beyond this list.
  * **Data & Resolution Seam:** Reuse and extend the financial-fact boundary established in Steps 2.3–2.4 rather than adding provider-specific retrieval logic to the analyzer.
* **Step 4.2: Additional Technical Indicators:** Expand beyond the initial SMA/crossover Momentum implementation (for example RSI/EMA/MACD only when explicitly selected and specified).
* **Step 4.3: Analytical Aggregator & Risk Metrics:** Combine independent deterministic strategy outputs (for example Graham ceilings, momentum signals, FCF/earnings-growth trends, and cash-flow valuation multiples) into unified typed models with basic risk measures such as maximum drawdown and volatility. Later product-policy work may define a composite screen, universe screening, or cross-sectional ranking over those outputs. Before implementation, any such method must explicitly define and validate its comparison universe; sector-relative versus absolute treatment; normalization and outlier handling; missing-data policy; formulas, thresholds, and weights; point-in-time data boundaries; evaluation/rebalancing frequency; empirical or backtest evidence; and versioned deterministic result semantics. The LLM may select, combine, and explain typed results, but it may not perform, improvise, or silently reweight the financial calculations. A model also may not rank instruments by its own judgment: that would be an unvalidated composite under another name. A forecast ledger, which starts recording in v0.3 (FL.1), is the proposed way to collect the required evidence; see the [Discovery Workbook](DISCOVERY_WORKBOOK.md#forecast-ledger).

#### Step 5: Localization Engine for Canadian Markets (en-CA / fr-CA)
* **Step 5.1:** i18n core framework.
* **Step 5.2:** Localized financial/currency formatters.
* **Step 5.3:** Locale-aware reporting text and compliance disclaimers.

### **Milestone v1.0: Multi-Step Autonomy & Executive Reporting**
**Entry condition:** Milestones v0.3 and v0.4 are complete.

#### Step 6: Autonomous Multi-Step Tool Integration (Hardened)
* **Step 6.1:** Multi-Step Planner, including unattended/scheduled research only when the project owner judges the plain-English workflow mature enough.
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
| **Adoption** | Light Mode investor workflow (analyze/watchlist → refresh → stored run → concise/details/provenance) documented and smoke-tested | Required before Milestone v0.3 |
| **Plain-English Answers** | Sentences in an answer that trace to stored evidence | All, on the v0.3 question set |
| **Plain-English Answers** | Numbers in an answer typed by a model | 0 |
| **Plain-English Answers** | Model-based filing reading, per question | At most 4 wrong in 100 held-out passages, and a clear win over a keyword rule; detail in the [v0.3 plan](milestones/v0.3/IMPLEMENTATION_PLAN.md#5-acceptance-criteria) |
| **Plain-English Answers** | Sentence checking | Catches at least 9 in 10 planted errors; removes at most 1 in 20 correct sentences |

---

## 10. Operational Risk Register & Mitigations

| Risk Event | Potential Impact | Architectural Mitigation Strategy |
| :--- | :--- | :--- |
| **External API Changes (`yfinance`)** | Upstream data fetch failures or field-semantic drift | Keep historical prices and financial facts behind narrow provider boundaries; validate fields and provenance; rely on the appropriate cache where available. |
| **Point-in-time look-ahead** | Historical analysis accidentally consumes facts published later | Enforce `as_of` at resolution time, record observation/publication/availability timestamps, and return unavailable when a provider cannot answer safely. |
| **Local LLM Output Drift / Schema Violation** | Failed tool parsing, infinite retries | Enforce native Ollama JSON schemas (`format`) + Pydantic validation + circuit breaker caps. |
| **Context Degradation on Long Turns** | Model forgets original goal or tool rules | Prune middle conversation context while strictly locking `Role.SYSTEM` at index 0. |
| **Database Lock / Concurrency Latency** | DB timeouts during multi-tool execution | Enforce SQLite Write-Ahead Logging (WAL) mode and single-writer/multi-reader connection pooling. |
| **Hardware barrier excludes target users** | Dual-tier requirements out of reach for most Primary Users | **Light Mode is the default operating mode.** Full Dual-Tier is optional. Hardware requirements are surfaced early in README and `docs/user/HARDWARE.md`. Plain-English answers (v0.3) must run under Light Mode. |
| **Strategy fixation / analytical monoculture** | Local model repeatedly selects the first/only familiar analytical strategy even when another is appropriate | Maintain materially different deterministic analyzers behind the same existing runtime interface; Step 2.5 measures strategy selection separately from numerical correctness; do not special-case the orchestrator around one strategy. |
| **User-facing architecture remains developer-shaped** | Users can run the software but cannot quickly understand or revisit results | Use concise investor-facing presentation, progressive disclosure, durable Analysis Runs, and Step 3.4 watchlist/run browsing; v0.3 adds plain-English questions and answers. |
| **An answer says more than the evidence does** | A fluent sentence misstates a result, and the reader trusts it | The engine fills in every number; every sentence names its evidence and is checked before display; failed sentences are removed; the ordinary result views are always available as a fallback. |
| **An answer is taken as advice** | A reader acts on a sentence as if it were a recommendation | Advice requests are declined; no score, rank or probability is shown beside an instrument; every answer ends with a fixed evidence-not-advice line. |
| **A model-based reading is trusted without proof** | A wrong "found" or "not found" about a filing enters an analysis | Accuracy is measured on hand-labelled passages before use; the reader must beat a keyword rule; unsure cases are reported as *not determined*; the quoted passage is always shown. |
| **No local model is good enough** | The model-based parts of v0.3 cannot meet their bars under Light Mode | ASK.0 measures this before any design work. The milestone then delivers its floor, which is planned as a complete product: a fixed question menu, answers assembled by rule, filing events and keyword filing rules. |
| **Filing text carries instructions** | Text inside a filing steers a model | Filing text is treated as untrusted data; the reader may answer only fixed questions with fixed choices; the writing model never sees a whole filing. |

---

## 11. CI/CD Pipeline & Automated Quality Gates

Every Pull Request must pass the following automated GitHub Actions pipeline before merge approval. Dependabot pull requests are never merged: reapply the same version bump on a project branch, and Dependabot then closes its own pull request. Commits on `main` are authored by project contributors only.

1. **Lint & Code Style:** `ruff check . && ruff format --check .`, plus the Markdown checks `scripts/check_doc_links.py` and `scripts/check_sequence_tables.py`
2. **Strict Static Analysis:** `mypy --strict src tests scripts`
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
9. **Filing events and filing readings** (v0.3) are dated evidence taken from SEC filings. An event comes from filing records with no model. A reading is a model's answer to one fixed question about a named part of a filing, stored with the quoted passage, the model's name and version, and the version of the question.
10. **Answer Records** (v0.3) store one question, its research plan, the evidence used, the sentences shown and the check results. An answer is not a report projection: it is written once and stored, and showing it again never calls a model.
11. **Forecast-ledger entries** (v0.3) are dated questions stored with an Analysis Run, each with a prediction from a trivial rule, to be settled by later facts. They exist to measure methods over time. They are not evidence about an instrument and are never shown to an investor.

Step 2.3 established the minimum data capabilities required by Momentum and Graham:

- historical market data for Momentum through `BaseDataClient`;
- quote and fundamental facts for Graham through a dedicated valuation boundary, plus a macro-observation contract that does not imply an approved production AAA series;
- field-by-field input resolution with overrides, a minimal cache seam, strict as-of handling, and provenance.

Step 2.4 minimally extends those financial-fact/resolution foundations for period-aligned operating cash flow and capital expenditures, derives project-defined FCF with explicit lineage, and adds historical FCF/diluted-EPS growth semantics without creating a parallel data architecture. Before closeout, it also hardens the shared contracts that the Golden Suite will depend on: result invariants, investor-facing status language, typed failure presentation, quote classification, earnings/share compatibility, supported Graham routing, and exact presentation regression evidence.

Evaluation requires exact expected domain outcomes and one canonical deterministic report. SEC foreign-filing support uses the same provider-neutral fact and provenance boundaries.

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
- **`docs/project/milestones/v0.3/IMPLEMENTATION_PLAN.md`:** Draft scope, order and acceptance numbers for plain-English questions and evidence-backed answers.
- **`docs/project/EVIDENCE_PROVIDER_ROADMAP.md`:** Non-authoritative candidate backlog of future strategies and platform features; this Master Plan and the implementation plan above remain authoritative for scope and sequencing.
- **`docs/project/milestones/v0.2/step-2.3/STEP_2_3_GRAHAM_DESIGN.md`:** Compact approved Step 2.3 method, resolution, provenance, CLI, fixture, and review record.
- **`docs/project/milestones/v0.2/step-2.4/STEP_2_4_FCF_EARNINGS_GROWTH_DESIGN.md`:** Initial Step 2.4 financial, data, CLI, presentation, and review design.
- **`docs/EVALUATIONS.md`:** Step 2.5 Golden Suite status, usage target, scoring, fixtures, reporting, and extension policy.
- **`docs/TOOL_DEVELOPMENT.md`:** **Planned (SWC.7).** The single contributor guide for adding an analysis strategy. It will replace `docs/project/ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md`, which remains the guide until then.
- **`docs/I18N_GUIDE.md`:** **Planned for localization work.** Translation/report-localization procedures.

Do not assume a planned guide already exists. During implementation, create/update planned documents only in the step that explicitly owns them.

---

*This Master Plan records the current execution roadmap. It is versioned through Git; document version numbers are intentionally not embedded in this document.*
