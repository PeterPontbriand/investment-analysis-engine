# Financial Data Agents
# Master Plan Discovery Workbook

> **Purpose:** This workbook captures the architectural decisions, engineering philosophy, long-term vision, and design rationale that guide the evolution of the Financial Data Agents project. It documents *why* major decisions are made, not the detailed execution schedule.
>
> It is the primary source from which the Master Plan, Architecture Guide, Contributor Guide, and other long-lived project documentation are derived.

---

# Table of Contents

1. Introduction
2. How to Use This Workbook
3. Project Identity & Vision
4. Guiding Principles
5. Project Success Criteria
6. Stakeholders & Target Audiences
7. AI Philosophy
8. Software Architecture
9. Reliability & Quality
10. Security
11. Data Strategy
12. AI Engineering Strategy
13. User Experience Philosophy
14. Performance & Scalability
15. Extensibility & Plugin Strategy
16. Documentation Strategy
17. Development Workflow
18. Release Strategy
19. Portfolio Objectives
20. Long-Term Vision
21. Non-Goals
22. Architectural Regrets to Avoid
23. Open Questions & Future Decisions
24. Glossary
25. Revision History
26. Appendix A: Decision Log

---

# 1. Introduction

## Purpose
This workbook is the foundational design record for `financial-data-agents`. It records the reasoning, constraints, security model, and engineering trade-offs that shape the system.

## Scope
Covers full-stack AI engineering with local LLM orchestration (Ollama), deterministic tool dispatching, relational data persistence (SQLite + Alembic), localization (`en-CA` / `fr-CA`), quantitative analytics, and automated reporting. Full GUI/frontend frameworks are explicitly out of scope and belong to downstream integration projects.

## Intended Audience
Senior software architects, AI systems engineers, technical recruiters evaluating portfolio depth, open-source contributors, and the actual investors described in Section 6 as Primary Users. See Section 3.8 for how these audiences are prioritized when they pull in different directions.

---

# 2. How to Use This Workbook

## How Decisions Are Recorded
Decisions are documented with their justification and the main alternatives considered. Durable decisions are also entered in the Decision Log (Appendix A). Decisions that require Peter's judgment call rather than being a direct restatement of already-stated goals are logged with **Status: Proposed** until confirmed.

## Living Document Policy
The workbook evolves via Pull Requests alongside major milestone completions. Changes to core principles or architecture require an update to the relevant section and an entry in the Decision Log and Revision History.

## Relationship to the Master Plan
- **Master Plan** = execution roadmap (what, when, quality gates, milestones).
- **Discovery Workbook** = rationale and constraints (why, how, non-goals, trade-offs).

---

# 3. Project Identity & Vision

### 3.1 Project Purpose
Deliver reliable, local quantitative investment analysis and research briefs for serious retail investors and investment professionals, implemented as production-grade local-first AI systems engineering.

### 3.2 Long-Term Vision
A self-contained, local-first, locally executing financial reasoning hub with controlled and auditable external data access that ingests market data, executes rigorous valuation models, and generates executive-grade localized research briefs. The core orchestration and caching layers remain designed so they could later support broader local-agent use cases if desired.

### 3.3 Mission Statement
Deliver deterministic financial analytics through an auditable, multi-tier local LLM orchestration loop guarded by strict quality and type boundaries.

### 3.4 Definition of Success
- ≥ 90 % accuracy on the Golden Benchmark suite (numeric results + correct tool selection).
- Zero `mypy --strict` errors in supported source code; 100 % typed public interfaces.
- Zero unhandled runtime exceptions on the golden suite.
- CLI startup < 500 ms and indexed SQLite cache reads < 50 ms.
- At least 3 people outside the author install the tool under **Light Mode** and complete a real analysis before Milestone v1.0 begins.
- At least 1 of those people confirms that an output told them something they'd genuinely have wanted to know.
- Light Mode end-to-end path is documented and usable before the Real-User Validation Checkpoint (Milestone v0.2.5).

### 3.5 Project Values
- Determinism over speculation.
- Local privacy and isolation over cloud convenience.
- Type safety and observability over rapid hacking.
- Explicit schemas and boundaries over prompt-engineering cleverness.
- Configurability and abstraction over hard, brittle third-party dependencies.
- Usefulness to real users over pure portfolio optics when the two conflict.
- Accessible by default, powerful when equipped.** The baseline experience should run on modest, common hardware. Heavier capability is something a user opts into, not something they're blocked without.

### 3.6 Elevator Pitch
`financial-data-agents` is a local investment analysis engine that lets serious retail and professional investors run rapid quantitative checks (intrinsic value, momentum, risk metrics) and produce audit-ready research briefs. It runs entirely on local open-weight models via Ollama, keeps all math deterministic in Python, and supports Canadian localization (`en-CA` / `fr-CA`). Most users run it in Light Mode on modest hardware.

### 3.7 Illustrative Use Case
A long-time retail investor who previously tracked stocks meticulously in FileMaker hears a friend mention a ticker over tea. He runs a quick CLI analysis or two with `financial-data-agents` under **Light Mode**, then decides whether to add the ticker to his watch list for ongoing agent-driven tracking and deeper analysis.

Light Mode (single-tier / 14B-class or smaller) is the path intended to make this persona reachable. Full Dual-Tier Mode remains available for users who have workstation-class hardware.

### 3.8 Resolving Competing Audiences
Section 6 names two different kinds of stakeholders: people who need working investment analysis, and reviewers (recruiters, peer engineers) assessing engineering depth. Most of the time these pull in the same direction. Where they don't, this project prioritizes real usefulness to Primary Users first. Portfolio value is treated as a byproduct of building something genuinely useful, not a parallel design goal optimized for directly.

---

# 4. Guiding Principles

### 4.1 Engineering Principles
- Strict static typing: no untyped parameters; enforced by `mypy --strict`.
- Defensive data parsing: every external or LLM-produced value passes through a Pydantic model before use.
- Automated quality gates: un-linted or insufficiently tested code cannot merge to `main`.
- Prefer configurability and clean abstractions over hard dependencies on specific third-party libraries or engines.

### 4.2 Architectural Principles
- Decoupled provider layers: LLM clients and data sources sit behind narrow interfaces (`BaseDataClient`, etc.) so implementations can be swapped.
- Tiered hardware utilization with an explicit Light Mode path: the default experience targets modest hardware (~8–16 GB VRAM or 32–64 GB unified memory); Full Dual-Tier (~24–28 GB) is an optional higher-capability path.
- Deterministic core: math, caching, persistence, and validation live in ordinary Python; the LLM is used only for planning, tool selection, and narrative synthesis.

### 4.3 AI Principles
- Math belongs in Python. Never ask the model to compute intrinsic value, RSI, or risk metrics.
- Treat every LLM output as untrusted input that must be schema-validated.
- Prefer hard circuit-breaker limits over unbounded autonomous loops.

### 4.4 Decision-Making Principles
- Prefer an explicit, safe halt with a diagnostic over silent continuation that could propagate hallucination.
- Record durable decisions in the Decision Log.
- When usefulness-to-real-users and portfolio-signal goals conflict, usefulness wins.

### 4.5 Architectural Principles vs. Implementation Decisions

The workbook distinguishes durable architectural principles from implementation decisions that may change as the project evolves.

- **Architectural principles** express stable constraints or values that should survive changes in libraries, models, or implementation details.
- **Implementation decisions** record the current technical means chosen to satisfy those principles.
- When an implementation decision changes without changing the underlying principle, update the Decision Log and affected implementation documentation, but do not silently redefine the principle.

This distinction is intended to prevent temporary technology choices from becoming accidental architectural commitments.

---

# 5. Project Success Criteria

### 5.1 Technical
- CLI startup latency < 500 ms.
- Indexed SQLite cache query latency < 50 ms.

### 5.2 Engineering
- Zero `mypy --strict` errors in supported source code; 100 % typed public interfaces.
- ≥ 85 % line coverage on `/src` (`pytest --cov`).

### 5.3 Agent
- ≥ 90 % pass rate on the Golden Benchmark suite (correct tool selection + numeric accuracy).
- Zero unhandled exceptions on the golden suite.

### 5.4 Portfolio / Process
- Clean feature-branch history, complete docstrings, architectural diagrams, and reproducible evaluation artifacts.

### 5.5 User Validation
- At least 3 people outside the author install the tool under **Light Mode** and complete a real analysis before Milestone v1.0 begins.
- At least 1 of those people reports that an output was something they'd have wanted anyway.
- Findings from these sessions directly inform prioritization of Milestone v0.3.
- Light Mode itself must be documented and usable before the validation checkpoint begins.

---

# 6. Stakeholders & Target Audiences

- **Primary users**: Serious retail investors and investment professionals that need fast, local quantitative analysis and localized reports. Most are expected to run Light Mode.
- **Secondary users**: System integrators who embed the agent engine into larger dashboards (Osiris, WorldMonitor, etc.).
- **Contributors**: Developers adding tools, data clients, or localization catalogs.
- **Recruiters / hiring managers**: People evaluating evidence of senior-level AI systems engineering, architecture, and testing discipline.
- **Peer architects and AI engineers**: Reviewers interested in local LLM tool routing, schema enforcement, and reliability patterns.

---

# 7. AI Philosophy

### 7.1 Role of the LLM
High-level task planning, tool selection, structured parameter extraction, and contextual narrative synthesis.

### 7.2 Role of Deterministic Software
Data fetching and caching, all mathematical processing (Graham intrinsic value, RSI, SMA, risk metrics), database operations, schema validation, and final output rendering.

### 7.3 Autonomy Boundaries
Multi-step execution is allowed but hard-capped (default max steps = 10). Circuit breakers and timeouts are non-negotiable.

### 7.4 Human Oversight
Final executive reports (Markdown / PDF) are the hand-off point for human review before any financial use.

### 7.5 Explainability
Every prompt, tool call, argument, return value, and latency measurement is recorded in structured trajectory logs.

### 7.6 Trust Boundaries
External market data and news text are treated as untrusted, sanitized, and wrapped in explicit delimiters before insertion into model context.

---

# 8. Software Architecture

### 8.1 Style
Layered, modular, asynchronous runtime. Clean separation of concerns.

### 8.2 High-Level Flow
```
CLI / Reports
    → Agent Orchestrator & Planner Loop
        (Context Manager + Circuit Breaker)
            → Light / Fast Tier (≈14B) - always on, Light Mode default
            → Deep Reasoning Tier (≈32B) [optional Full Dual-Tier]
                → Async Tool Dispatcher
                    → Data Layer (DAO / Cache)
                    → Analytics Module
                    → Report Module (Jinja2 + charts)
                        → SQLite (WAL)
```

### 8.3 Key Runtime Components
- **Context Manager**: conversation window, middle-message truncation, system-prompt lock at index 0.
- **Light / Fast Tier (≈14B)**: default mode — tool-call extraction, schema validation, single-step analysis.
- **Deep Reasoning Tier (≈32B)**: optional Full Dual-Tier mode - multi-step planning and higher-fidelity synthesis.
- **Tool Dispatcher**: typed, schema-validated function calling only.

### 8.4 Module Layout (current intent)
- `src/core` – configuration (`pydantic-settings`), telemetry, logging.
- `src/llm` – Ollama clients, JSON schema handling, context management.
- `src/tools` – strongly-typed tools.
- `src/db` – Alembic migrations, connection handling, DAOs.
- `src/analytics` – pure mathematical routines.
- `src/reporting` – Jinja2 templates, charting, PDF/Markdown generation.

### 8.5 Constraints
- No `eval()`, no raw shell execution, no cloud LLM fallbacks for core reasoning.
- All tool arguments and returns are Pydantic models.
- Outbound network calls go through a single guarded client (cache-first, rate-limited, domain-whitelisted).
- Avoid hard, brittle dependencies on specific third-party libraries or engines; prefer configuration and abstraction.
- Core useful analysis must remain functional under Light Mode.

---

# 9. Reliability & Quality

### 9.1 Testing Pyramid
- Unit tests for pure math and individual tools.
- Integration tests for DAOs and caching.
- Golden evaluation suite for full agent trajectories (mocked or recorded LLM responses), run against both Light Mode and Full Mode configurations where behavior differs.

### 9.2 Observability
Structured telemetry (JSON lines + SQLite) capturing prompts, tool calls, latencies, token usage, and payload hashes.

### 9.3 Failure Handling
- Transient (timeouts, malformed JSON, rate limits) → retry with error context, up to configured limit (default 3).
- Non-recoverable (DB corruption, missing critical data, max-steps exceeded) → immediate halt + diagnostic.

### 9.4 Quality Gates (CI)
`ruff`, `mypy --strict`, `pytest` with coverage threshold, dependency audit, and headless golden-suite run.

---

# 10. Security

### 10.1 Primary Threats
Prompt injection via external data (news, API text), overly permissive tools, leakage of secrets into traces.

### 10.2 Controls
- Tools accept only typed parameters; no dynamic code execution.
- Filesystem writes restricted to designated directories (`/reports`, `/logs`, `/data`).
- Outbound network traffic forced through a single guarded client.
- Secrets loaded exclusively via environment variables / `pydantic-settings`.
- External text sanitized and wrapped in structural delimiters before context injection.
- No cloud LLM dependency for core loops.

---

# 11. Data Strategy

- **Persistence**: SQLite in WAL mode.
- **Migrations**: Alembic.
- **Caching**: Aggressive local cache, default 24 h TTL, explicit invalidation on corporate actions or FX changes.
- **Provenance**: Every stored price/metric carries fetch timestamp, source, and snapshot identifier.
- **Audit**: Full trajectory logging of agent steps.
- **Abstraction**: All upstream providers implement `BaseDataClient` so `yfinance` (or any replacement) can be swapped without touching business logic.

---

# 12. AI Engineering Strategy

### 12.1 Model Tiering & Modes

| Mode / Tier | Example Models | Typical Footprint | Role |
|-------------|----------------|-------------------|------|
| **Light Mode (default)** | `qwen2.5-coder:14b-instruct-q4_K_M` or smaller | ~8–16 GB VRAM or 32–64 GB unified memory | Default path for most users and for external validation |
| **Full Dual-Tier — Fast** | `qwen2.5-coder:14b-instruct-q4_K_M` | ~9–11 GB | Tool extraction when dual-tier is active |
| **Full Dual-Tier — Deep** | `qwen2.5-coder:32b-instruct-q4_K_M` or `deepseek-r1:32b` (configurable) | ~19–24 GB | Optional deeper planning and synthesis |

Light Mode is the adoption path. Full Dual-Tier is an optional higher-capability path for users who have the hardware. See `docs/HARDWARE.md`.

### 12.2 Prompt & Context Discipline
- System prompt permanently locked at `Role.SYSTEM` (index 0).
- Middle-message truncation to protect context limits.
- Native Ollama JSON Schema constraints (`format=Schema`) preferred over free-form parsing.

### 12.3 Evaluation
Golden suite compares tool selection and numeric outputs against verified ground truth, for both Light and Full Mode where their behavior can diverge.

---

# 13. User Experience Philosophy

- CLI: fast startup, clear progress indication during inference, high-signal error messages.
- Reports: clean Markdown and PDF executive briefs with embedded charts, audit snapshot IDs, and mandatory disclaimers.
- Localization: first-class `en-CA` / `fr-CA` support (currency, dates, disclaimers, agent reasoning text).
- Accessibility: scannable structure, high-contrast terminal output.
- Installation: the install path itself should not be the reason someone gives up before running a single analysis. Prefer simple Ollama install paths (macOS app, Windows installer on mini-PCs). Track “time from `git clone` to first result” as a UX metric.
- Hardware expectations are surfaced early and honestly (README + `docs/HARDWARE.md`).

---

# 14. Performance & Scalability

- Designed for single-node local use (personal / small professional network).
- Light Mode targets modest consumer hardware; Full Dual-Tier targets workstation-class local hardware.
- Optimize the deterministic path (cache, DB, pure Python analytics) first; LLM latency is accepted as GPU/unified-memory bound.
- Targets: CLI startup < 500 ms, excluding Ollama/model initialization and network access; indexed local SQLite cache reads < 50 ms under a representative single-user workload.

---

# 15. Extensibility & Plugin Strategy

Extension points:
- New pure analytics functions in `src/analytics`.
- New data providers implementing `BaseDataClient`.
- New tools inheriting from the common tool base and registering with the dispatcher.

The orchestration loop and SQLite caching layer are intentionally reusable. Finance remains the primary domain, but the design does not permanently close the door on later extraction as a more general local-agent framework.

---

# 16. Documentation Strategy

Documentation lives in the repository and is updated with the code:
- `README.md` – quickstart, disclaimer, and overview.
- `docs/HARDWARE.md` – Light Mode vs Full Dual-Tier requirements and consumer hardware guidance.
- `docs/ARCHITECTURE.md` – diagrams and layer responsibilities.
- `docs/TOOL_DEVELOPMENT.md` – how to add a typed tool.
- `docs/EVALUATIONS.md` – golden suite usage and extension.
- `docs/I18N_GUIDE.md` – localization process.

Architecture and principle changes in this workbook trigger corresponding updates to the above guides.

---

# 17. Development Workflow

- Feature-branch workflow against `main`.
- Definition of Done: implemented, `mypy --strict` clean, `ruff` clean, unit tests + golden coverage, documented.
- CI enforces the quality gates listed in Section 9.

---

# 18. Release Strategy

Semantic versioning aligned with milestones:
- **v0.1** – Core Orchestration Engine (completed).
- **v0.2** – Reliability, Observability & Data Persistence + Light Mode support.
- **v0.2.5** – Real-User Validation Checkpoint (under Light Mode).
- **v0.3** – Analytics Expansion & Canadian Localization.
- **v1.0** – Hardened multi-step autonomy + executive reporting.

Database migrations via Alembic preserve compatibility of local SQLite files.

---

# 19. Portfolio Objectives

The repository is intended to demonstrate:
- Production Python async systems with strict typing.
- Local LLM orchestration (Ollama) under real hardware constraints, including a usable Light Mode path.
- Defensive architecture (circuit breakers, schema enforcement, trust boundaries).
- Transactional data engineering (SQLite + Alembic + caching).
- Quantitative correctness and evaluation discipline.
- Clear technical writing and architectural decision records.

These are treated as things a genuinely useful tool naturally demonstrates — not the primary target being optimized for.

---

# 20. Long-Term Vision

Finance-first local reasoning hub remains the primary intent:
- Multi-modal local node (earnings-call audio, PDF filings, deeper alternative data).
- Optional multi-agent debate / consensus patterns still running entirely locally.

The core orchestration and caching layers are kept deliberately modular so that, if desired later, they could support extraction into a more general local-agent framework. No commitment is made to that generalization at present.

---

# 21. Non-Goals

Explicitly out of scope for the current project:
- Full web or desktop GUI (belongs to separate integration projects).
- Any dependence on commercial cloud LLMs for core reasoning.
- Automated order execution or high-frequency trading.
- Real-time WebSocket market data (deferred).

Rejected approaches:
- Unstructured string / regex parsing of tool calls (replaced by native schema constraints).
- Hard, brittle dependencies on specific third-party libraries or engines when configurability and abstraction will suffice.
- Treating dual-tier workstation hardware as a prerequisite for basic useful analysis.

---

# 22. Architectural Regrets to Avoid

- Letting the LLM perform raw numerical calculations.
- Tight coupling of prompt templates to specific model tags.
- Un-versioned or free-form tool-call outputs.
- Loading multiple large reasoning models concurrently and exhausting VRAM.
- Bypassing static typing or schema validation for short-term velocity.
- Introducing hard third-party dependencies that reduce configurability.
- Expanding engineering scope (autonomy, localization, reporting) before anyone outside the author has confirmed the current core loop is useful to them.
- Presenting a dual-tier workstation requirement as the only supported path while describing a retail-investor persona.

---

# 23. Open Questions & Future Decisions

1. **SQLite concurrency**  
   Will WAL mode + careful connection handling remain sufficient under denser multi-tool / multi-agent workloads, or will an explicit queue / single-writer pattern become necessary?

2. **Does `fr-CA` localization belong in v0.3, or later?**  
   Recommend letting Milestone v0.2.5 feedback answer this. If real users ask for it, it stays in v0.3; if not, it can move after v1.0 without losing the core value proposition.

Resolved in this revision:
- Deep-tier model preference → both `qwen2.5-coder:32b` and `deepseek-r1:32b` kept configurable.
- Elevator pitch / positioning → investment analysis primary; local-AI systems engineering secondary.
- Long-term scope → finance-first; door left open for possible later generalization of the core layers.
- **Hardware bar vs. Illustrative Use Case (former Open Question 3)** → resolved by introducing a supported Light / single-tier mode as the default adoption path. Light Mode must be usable before Milestone v0.2.5. Full Dual-Tier remains an optional higher-capability path. See Decision D17 and `docs/HARDWARE.md`.

---

# 24. Glossary

- **DAO** – Data Access Object.
- **Ollama** – Local open-weight model serving framework.
- **Circuit Breaker** – Hard limit that stops an agent loop when step count, error count, or wall-clock time is exceeded.
- **Golden Benchmark Suite** – Fixed set of queries with verified expected numeric outcomes and tool-selection behavior.
- **WAL Mode** – SQLite Write-Ahead Logging, enabling concurrent readers with a single writer.
- **Light Mode** – Single-tier / modest-hardware path (≈14B-class or smaller) that is the default recommended experience.
- **Full Dual-Tier Mode** – Optional path that pairs a fast ≈14B tier with a deep ≈32B tier for users with sufficient local hardware.

---

# 25. Revision History

| Date       | Summary                                      |
|------------|----------------------------------------------|
| 2026-07-15 | Initial outline skeleton                     |
| 2026-08-01 | Expanded content, added Decision Log         |
| 2026-08-13 | Positioning, model, scope, and dependency answers; illustrative use case |
| 2026-08-13 | User-validation criteria; portfolio-vs-usefulness prioritization; hardware/persona mismatch flagged; Milestone v0.2.5; Open Question on `fr-CA` timing |
| 2026-08-13 | **Light Mode decision recorded.** Hardware bar resolved by making single-tier Light Mode the default adoption path; required before v0.2.5. Full Dual-Tier remains optional. Updated principles, success criteria, architecture, Decision Log, and Open Questions. |
| 2026-08-14 | Surgical cleanup: clarified local-first networking terminology, separated architectural principles from implementation decisions, standardized quality metrics and documentation references. |

---

# 26. Appendix A: Decision Log

| ID  | Date       | Decision                                                                 | Alternatives Considered                  | Rationale / Consequences                                                                 | Status   |
|-----|------------|--------------------------------------------------------------------------|------------------------------------------|------------------------------------------------------------------------------------------|----------|
| D1  | 2026-Q2    | 100 % local LLM orchestration (Ollama); no cloud LLM in core loop      | Cloud APIs (OpenAI, Anthropic, etc.)     | Privacy, zero marginal cost, forced learning of real local-model constraints             | Accepted |
| D2  | 2026-Q2    | Dual-tier model strategy (≈14B execution + ≈32B reasoning) on 28 GB VRAM | Single large model, or smaller-only      | Maximizes capability while staying inside hardware envelope; clear responsibility split  | Accepted |
| D3  | 2026-Q2    | All quantitative work (Graham, RSI, etc.) performed in deterministic Python | Asking the LLM to calculate              | Eliminates a major class of hallucination; LLM limited to planning and synthesis         | Accepted |
| D4  | 2026-Q2    | SQLite + WAL + Alembic as the persistence layer                          | PostgreSQL, pure file/JSON cache         | Zero-ops local deployment, sufficient concurrency for target workload, simple migrations | Accepted |
| D5  | 2026-Q2    | Strict `mypy --strict` + Pydantic at every boundary                      | Gradual typing or looser validation      | Portfolio signal + long-term maintainability under agent-generated code paths            | Accepted |
| D6  | 2026-Q2    | Native Ollama JSON Schema constraints preferred over free-form parsing   | Regex / string parsing of tool calls     | Dramatically reduces output drift and retry loops                                        | Accepted |
| D7  | 2026-Q2    | Canadian localization (`en-CA` / `fr-CA`) as a first-class concern       | English-only                             | Matches target user network and demonstrates i18n discipline                             | Accepted |
| D8  | 2026-Q2    | Full GUI explicitly out of scope                                         | Building a web or desktop front-end      | Keeps the repository focused; UI work belongs to separate integration projects           | Accepted |
| D9  | 2026-08    | Deep-tier models kept configurable (`qwen2.5-coder:32b` and `deepseek-r1:32b`) | Locking to a single model                | Avoids premature commitment; preserves flexibility as models evolve                      | Accepted |
| D10 | 2026-08    | Public positioning prioritizes investment analysis; local-AI engineering is secondary | Technology-first positioning             | Aligns with primary user value and the illustrative retail-investor use case             | Accepted |
| D11 | 2026-08    | Finance-first scope; core layers left modular enough for possible later generalization | Permanently finance-only, or early framework extraction | Matches current intent while preserving optionality                                      | Accepted |
| D12 | 2026-08    | Prefer configurability and abstraction; avoid hard brittle third-party dependencies | Locking to specific libraries/engines    | Reduces long-term fragility and eases future swaps                                       | Accepted |
| D13 | 2026-08    | Add a real-user validation gate (≥3 outside users) before Milestone v1.0 autonomy work begins | No validation gate; ship on the pre-set schedule | Ensures the most expensive remaining work is built only once there is evidence of usefulness | Accepted |
| D14 | 2026-08    | When real-user-usefulness goals and portfolio-signal goals conflict, usefulness wins | Optimize primarily for portfolio/recruiter signal | Directly matches the project's current stated goal                                       | Accepted |
| D15 | 2026-08    | Document the dual-tier hardware requirements as a named adoption constraint | Leave the Illustrative Use Case mismatched | Kept the persona honest; forced a deliberate choice                                      | Accepted |
| D16 | 2026-08    | Let Milestone v0.2.5 feedback decide whether `fr-CA` localization stays in v0.3 or moves later | Keep localization fixed in v0.3 regardless of demand | Avoids sinking i18n effort before knowing if real users ask for it                       | Accepted |
| D17 | 2026-08    | **Introduce a supported Light / single-tier mode as the default adoption path.** Light Mode (≈14B-class or smaller, modest hardware) must be fully usable before Milestone v0.2.5. Full Dual-Tier remains an optional higher-capability path for users with sufficient hardware. | Keep dual-tier as the only path; or abandon dual-tier entirely | Resolves the hardware/persona mismatch. Makes the Illustrative Use Case reachable. Preserves deeper capability for those who have the hardware. Aligns with usefulness-first priority. | Accepted |

---

*End of Discovery Workbook*
