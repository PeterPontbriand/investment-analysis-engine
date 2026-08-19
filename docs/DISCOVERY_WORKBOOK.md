# Financial Data Agents
# Master Plan Discovery Workbook

> **Purpose:** This workbook records why major architectural and product decisions are made. The Master Plan records what/when; the active milestone plan records implementation sequencing and acceptance criteria.

Git history is the authoritative revision history. When this workbook conflicts with a more current Master Plan or active milestone implementation plan on sequencing, the plan governs and this workbook should be updated.

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
15. Extensibility Strategy
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
`financial-data-agents` is a local-first investment-analysis project combining deterministic financial software with locally hosted LLM orchestration.

## Scope
The project covers local Ollama orchestration, typed deterministic tools/analyzers, market-data access, SQLite/Alembic persistence, evaluation, Canadian localization, and report generation. Full GUI/frontend integration belongs to separate projects.

---

# 2. How to Use This Workbook

- **Master Plan** = execution roadmap and milestone intent.
- **Milestone implementation plan** = active implementation sequencing, guardrails, review gates, and acceptance criteria.
- **Discovery Workbook** = rationale, trade-offs, long-lived constraints.
- **Architecture Guide** = current architectural boundaries.

Do not infer implementation scope from this workbook when the active milestone plan explicitly narrows it.

---

# 3. Project Identity & Vision

### 3.1 Project Purpose
Deliver reliable local quantitative investment analysis and research briefs for serious retail investors and investment professionals.

### 3.2 Long-Term Vision
A self-contained, local-first financial reasoning hub with controlled external market-data access, deterministic analytics, durable local persistence, and auditable reports.

### 3.3 Mission
Use local LLMs for planning/tool selection/synthesis while deterministic Python owns financial calculations, validation, data handling, and persistence.

### 3.4 Definition of Success
- ≥90% aggregate Golden Benchmark pass rate with strategy/tool selection and numerical correctness reported separately.
- Zero `mypy --strict` errors in supported source.
- Zero unhandled exceptions in required deterministic Golden tests.
- Light Mode usable before real-user validation.
- At least 3 external Light Mode testers before v1.0 autonomy work.
- At least 1 tester confirms a genuinely useful output.

### 3.5 Values
- Determinism over speculation.
- Local privacy over cloud convenience.
- Explicit typed boundaries over prompt cleverness.
- Usefulness over portfolio optics.
- Accessible default path; heavier capability is optional.
- Heterogeneous strategies over analytical monoculture.

---

# 4. Guiding Principles

### 4.1 Engineering
- Strict typing.
- Pydantic/typed validation at boundaries.
- Automated quality gates.
- Small, reviewable changes.
- Preserve existing behavior outside the active task.

### 4.2 Architecture
- LLM and data providers sit behind narrow boundaries.
- `BaseAnalyzer` is the existing analyzer abstraction; do not invent a parallel strategy framework without evidence it is required.
- `BaseDataClient` is the market-data provider boundary.
- Historical-series access and current-quote access are distinct capabilities.
- Different strategies may have different inputs and result models.
- Production persistence, telemetry, fixtures, and evaluation artifacts are separate concerns.

### 4.3 AI
- The model selects deterministic capabilities; it does not perform financial arithmetic.
- LLM output is untrusted and schema validated.
- Hard execution bounds are preferable to open-ended autonomy.
- The model must not default to Momentum when a different registered strategy is appropriate.

---

# 5. Project Success Criteria

### Technical / Engineering
- CLI startup target <500 ms excluding model/network initialization.
- Indexed SQLite cache-read target <50 ms under representative local load.
- ≥85% project line coverage target.
- Strict typing and Ruff compliance.

### Agent / Evaluation
- ≥90% aggregate Golden pass-rate target.
- Strategy/tool-selection score reported separately.
- Deterministic numerical-correctness score reported separately.
- Benchmark criteria are not weakened to obtain the target.

### User Validation
- Light Mode is documented and usable before Milestone v0.2.5.
- ≥3 external tester sessions before v1.0.
- Findings influence v0.3 scope.

---

# 6. Stakeholders & Target Audiences

- Primary: serious retail investors and investment professionals.
- Secondary: integrators embedding the local engine elsewhere.
- Contributors: developers adding analyzers, tools, data providers, persistence, or localization.
- Reviewers: peers/recruiters evaluating architecture and engineering quality.

When these audiences conflict, usefulness to primary users wins.

---

# 7. AI Philosophy

### Role of the LLM
Planning, capability selection, structured parameter extraction, bounded recovery, and narrative synthesis.

### Role of deterministic software
Market-data handling, Momentum/Graham/risk calculations, caching, persistence, validation, evaluation, and rendering.

### Autonomy
Bounded by configured steps/retries/timeouts. The roadmap default is 10 planning steps; the runtime must not invent an independent five-turn cap.

### Explainability
Capture observable execution evidence through structured trajectory telemetry. Never infer private model reasoning.

---

# 8. Software Architecture

### High-level flow

```text
CLI
  → Orchestrator
    → structured analysis/tool selection
      → BaseAnalyzer implementations
        ├─ MomentumAnalyzer
        └─ GrahamValueAnalyzer (Step 2.3)
      → BaseDataClient
        ├─ historical series
        └─ current quote
      → provider/fixture adapter
      → deterministic result
  → synthesis/reporting
```

The initial Momentum and Graham pair is deliberately heterogeneous. Their coexistence tests whether the architecture is genuinely general rather than Momentum-specific.

### Current package intent

```text
src/
├── core/telemetry/
├── llm/
├── tools/
├── orchestrator/
├── data/
│   ├── base_client.py
│   ├── provider clients
│   └── repositories/
├── analysis/
│   ├── base.py
│   └── momentum/
├── reporting/
└── utils/
```

Repositories belong under `src/data/repositories/`.

---

# 9. Reliability & Quality

### Testing pyramid
- deterministic unit tests for analyzers/tools;
- contract/integration tests for data adapters/repositories;
- deterministic Golden evaluator tests with fixture-backed data;
- optional real-local-Ollama empirical evaluation for strategy/tool selection.

The deterministic/no-LLM mode cannot measure actual LLM strategy selection.

### Observability
Step 2.1 established structured trajectory telemetry separately from operational logging. JSONL is the initial sink; SQLite is added in Step 3.1.

### Structured output
Step 2.2 prefers native schema constraints when supported, retains Pydantic validation, and uses configured fallbacks. Empirical Light Mode model/schema compatibility remains a non-blocking validation item before Step 3.5 exit.

---

# 10. Security

- No arbitrary code/shell execution by the LLM.
- Registered tools only.
- External data treated as untrusted.
- Secrets from environment/settings only.
- Outbound provider access is controlled by application/data boundaries.
- No cloud LLM dependency for core reasoning.

---

# 11. Data Strategy

- **Provider boundary:** `BaseDataClient`.
- **Current provider:** yfinance is an active adapter; other clients may exist as placeholders/alternatives but are not automatically the production authority.
- **Historical data:** first-class capability used by Momentum/time-series strategies.
- **Current quote:** first-class capability introduced in Step 2.3 for Graham/valuation comparison.
- **Step 2.3 fixtures:** minimal deterministic adapter/data proving both capabilities; no live fallback.
- **Step 2.4 fixtures:** Golden evidence using the stable Step 2.3 contract.
- **Step 3.1 production persistence:** SQLite/WAL/cache-backed implementation of the shared contract.
- **Provenance:** stored/fixture data carries enough source/date/schema information to audit its origin.
- **Separation:** market-data persistence, trajectory telemetry, Golden fixtures, and evaluation results are distinct.

---

# 12. AI Engineering Strategy

### Model modes
Light Mode is the default adoption path; Full Dual-Tier remains optional.

### Prompt/schema discipline
- system-role invariants;
- context management;
- native structured output where supported;
- Pydantic validation/fallbacks.

### Evaluation
Step 2.4 measures:
- strategy/tool selection;
- deterministic numerical correctness;
- overall case success.

Real-model evaluation is empirical and separate from deterministic regression infrastructure.

---

# 13. User Experience Philosophy

- Fast, understandable CLI.
- High-signal diagnostics.
- Honest hardware expectations.
- Minimal setup friction.
- Human review before financial use.
- Reports/localization are roadmap capabilities and must not be pulled into Step 2.3 merely because they are long-term goals.

---

# 14. Performance & Scalability

Single-node local usage is the primary target. Optimize deterministic local paths first; accept that LLM latency depends heavily on local hardware.

---

# 15. Extensibility Strategy

Extension points include:
- new analyzers under `src/analysis/`;
- new provider adapters behind `BaseDataClient`;
- new typed tools through existing registration/dispatch;
- repository implementations under `src/data/repositories/`.

**Do not build a strategy plugin/registry framework speculatively.** The system should generalize only when concrete strategies expose a repeated need.

---

# 16. Documentation Strategy

Current documents:
- `README.md`
- `AGENTS.md`
- `RUNTIME_AGENTS.md`
- `docs/MASTER_PLAN.md`
- `docs/MILESTONE_v0_2_IMPLEMENTATION_PLAN.md`
- `docs/ARCHITECTURE.md`
- `docs/DISCOVERY_WORKBOOK.md`
- `docs/FINANCE_MATH.md`
- `docs/GLOSSARY.md`
- `docs/HARDWARE.md`

Planned when their owning work lands:
- `docs/EVALUATIONS.md` — Step 2.4;
- `docs/TOOL_DEVELOPMENT.md`;
- `docs/I18N_GUIDE.md`.

A planned document must not be treated as an existing source of instructions.

---

# 17. Development Workflow

- Fine-grained feature branches aligned with coherent implementation units.
- Follow active milestone review gates.
- Ruff + strict mypy + pytest before completion.
- Do not opportunistically redesign unrelated architecture.
- Documentation changes accompany durable architecture changes.

---

# 18. Release Strategy

- **v0.1** — Core orchestration engine.
- **v0.2** — Reliability/observability + Graham/data-contract foundation + heterogeneous Golden evaluation + circuit breakers + SQLite/data quality + Light Mode completion.
- **v0.2.5** — Real-user Light Mode validation.
- **v0.3** — Analytics expansion beyond the initial Momentum/Graham pair plus localization subject to user feedback.
- **v1.0** — Hardened autonomy and executive reporting.

---

# 19. Portfolio Objectives

The repository naturally demonstrates local-LLM orchestration, strict Python engineering, deterministic quantitative analysis, typed data architecture, evaluation discipline, and technical writing. These are outcomes of building a useful tool, not competing product goals.

---

# 20. Long-Term Vision

Finance remains primary. Core layers remain modular enough for possible later reuse, but the project does not commit to becoming a generic agent framework.

---

# 21. Non-Goals

- Full GUI/frontend.
- Cloud LLM dependency for core reasoning.
- Automated order execution/HFT.
- Real-time websocket market data in the current milestone.
- Premature plugin/framework generalization.
- Pulling later risk/localization/reporting work into Step 2.3.

---

# 22. Architectural Regrets to Avoid

- LLM arithmetic replacing deterministic Python.
- Momentum-specific assumptions embedded in generic orchestration.
- Speculative strategy registries/plugin systems.
- Treating a one-day historical download as a quote API when a current quote is a distinct requirement.
- Telemetry becoming business control flow.
- Golden expectations generated from the same implementation under test.
- Live network fallback from deterministic fixtures.
- Broad refactors under narrow milestone tasks.
- Weakening benchmarks until the model reaches a target.
- Requiring workstation-class dual-tier hardware for basic use.

---

# 23. Open Questions & Future Decisions

1. Will WAL + connection discipline remain sufficient for future denser multi-tool/multi-agent workloads?
2. Does `fr-CA` localization remain in v0.3 after v0.2.5 user feedback?
3. Do future additional strategies reveal a genuine need for a richer analyzer registry/plugin mechanism? This remains intentionally unresolved until concrete repetition justifies it.

---

# 24. Glossary

- **BaseAnalyzer** — Existing abstract analysis boundary.
- **BaseDataClient** — Market-data provider boundary.
- **Golden Benchmark Suite** — Fixed deterministic cases with verified behavioral/numeric expectations.
- **Fixture adapter** — Deterministic test implementation of the market-data contract.
- **Strategy-selection correctness** — Whether the appropriate deterministic analytical capability/tool was selected with valid arguments.
- **Numerical correctness** — Whether deterministic outputs match independently verified expectations.
- **Light Mode** — Default single-tier/modest-hardware path.
- **Full Dual-Tier Mode** — Optional fast+deep local-model path.
- **WAL** — SQLite Write-Ahead Logging.

---

# 25. Revision History

| Date | Summary |
|---|---|
| 2026-07-15 | Initial outline skeleton |
| 2026-08-01 | Expanded content and decision log |
| 2026-08-13 | Positioning, user-validation gate, and Light Mode decisions |
| 2026-08-16 | Telemetry/persistence sequencing and deterministic Golden-data boundary clarified |
| 2026-08-19 | Heterogeneous strategy independence adopted; Graham moved into v0.2 Step 2.3; current quote made first-class; Golden Suite separated into Step 2.4; circuit breakers bumped to Step 2.5; speculative strategy framework explicitly rejected |

---

# 26. Appendix A: Decision Log

| ID | Date | Decision | Rationale / Consequence | Status |
|---|---|---|---|---|
| D1 | 2026-Q2 | 100% local LLM orchestration; no cloud LLM in core loop | Privacy, local control, zero cloud dependency | Accepted |
| D2 | 2026-Q2 | Dual-tier model option | Preserves higher-capability local path | Accepted |
| D3 | 2026-Q2 | All quantitative work in deterministic Python | Eliminates LLM arithmetic hallucination class | Accepted |
| D4 | 2026-Q2 | SQLite + WAL + Alembic | Zero-ops local persistence | Accepted |
| D5 | 2026-Q2 | Strict mypy + typed/Pydantic boundaries | Maintainability and reliability | Accepted |
| D6 | 2026-Q2 | Prefer native Ollama JSON-schema constraints | Reduces structured-output drift | Accepted |
| D7 | 2026-Q2 | Canadian localization as a first-class roadmap concern | Matches target network; timing still feedback-sensitive | Accepted |
| D8 | 2026-Q2 | Full GUI out of scope | Keeps repository focused | Accepted |
| D9 | 2026-08 | Deep-tier model remains configurable | Avoid premature model lock-in | Accepted |
| D10 | 2026-08 | Investment-analysis positioning primary | Aligns with user value | Accepted |
| D11 | 2026-08 | Finance-first scope with modular core | Optional future reuse without premature framework extraction | Accepted |
| D12 | 2026-08 | Prefer configuration/abstraction over brittle dependencies | Reduces long-term fragility | Accepted |
| D13 | 2026-08 | Real-user validation gate before expensive v1.0 work | Build autonomy on evidence of usefulness | Accepted |
| D14 | 2026-08 | User usefulness wins over portfolio optics | Product-purpose priority | Accepted |
| D15 | 2026-08 | Make hardware adoption constraints explicit | Prevent persona/hardware mismatch | Accepted |
| D16 | 2026-08 | Let v0.2.5 feedback decide `fr-CA` timing | Avoid premature localization investment | Accepted |
| D17 | 2026-08 | Light Mode is default; dual-tier optional | Makes project accessible to intended users | Accepted |
| D18 | 2026-08-16 | Rationalized module layout, including `src/data/repositories/` | Clear ownership for data and telemetry layers | Accepted |
| D19 | 2026-08-16 | JSONL-first telemetry; deterministic fixture-backed market-data abstraction before production SQLite | Unblocks reliability/evaluation while preserving determinism | Accepted |
| D20 | 2026-08-19 | Use Momentum + Graham as intentionally heterogeneous early strategies | Tests whether architecture generalizes beyond Momentum | Accepted |
| D21 | 2026-08-19 | Current quote is a first-class market-data capability distinct from historical series | Avoids one-day-history workaround; supports valuation cleanly | Accepted |
| D22 | 2026-08-19 | Split Graham/data foundation (2.3) from Golden evaluation (2.4); bump circuit breakers to 2.5; reject speculative strategy registry | Gives Cline/humans a review gate and limits scope creep | Accepted |

---

### Document Versioning Policy

The Master Plan and Discovery Workbook are versioned through Git. Embedded document version numbers are intentionally avoided.

*End of Discovery Workbook*
