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
- **Step 2.3 Graham design** = compact approved implementation specification for the active Graham work; it does not override milestone scope or review gates.
- **Discovery Workbook** = rationale, trade-offs, long-lived constraints.
- **Architecture Guide** = current architectural boundaries and explicitly labeled near-term target seams.

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
- Zero `mypy --strict` errors in supported source and tests.
- Zero unhandled exceptions in required deterministic Golden tests.
- Light Mode usable before real-user validation.
- At least 3 external Light Mode testers before v1.0 autonomy work.
- At least 1 tester confirms a genuinely useful output.

### 3.5 Values
- Determinism over speculation.
- Local privacy over cloud convenience.
- Explicit typed boundaries over prompt cleverness.
- Usefulness over portfolio optics.
- Accessible default experience; heavier capability is optional.
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
- `BaseDataClient` remains the historical-price provider boundary.
- Step 2.3 financial facts use a dedicated provider/resolution boundary rather than enlarging a historical-price-shaped interface.
- Historical prices, current quotes, company fundamentals, and macro series are distinct capabilities even when a composed façade coordinates them.
- Different strategies may have different inputs and result models.
- Financial method names and result meanings are explicit; Graham Number and Graham growth value are not interchangeable.
- Requested analysis `as_of` and fact-availability dates are correctness boundaries, not decorative metadata.
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

### Stakeholder input: forward-return composite concept

Stakeholder discovery input includes a broad possible future screen with these unapproved candidate components: 25% “FCF Power” (FCF yield, forward FCF growth, FCF/share growth, and cash conversion); 20% “ROIC/Reinvestment” (ROIC minus WACC, incremental ROIC, and returns on new invested capital/reinvestment opportunity); 20% “Estimate Revisions” (changes in consensus EPS, FCF, revenue, EBITDA/margins, and management guidance); 20% “Growth-Adjusted Valuation” (EV/forward FCF or P/FCF relative to expected FCF growth and historical valuation); and 15% “Momentum” (6–12 month relative price strength, earnings revisions, and accelerating fundamentals). Candidate risk filters include excessive leverage, poor cash conversion, and unstable or highly cyclical earnings.

This product-discovery evidence for a possible later composite screener is not a replacement specification for the current independently typed deterministic strategy. All proposed components, formulas, weights, and filters are as-yet unapproved. The cited AQR Quality Minus Junk and MSCI factor materials support only the broad observation that quality or factor analysis can combine multiple descriptors; they do not validate this particular screen, its formulas, or its weights.

A related current-method policy question was whether historical FCF growth should use total company FCF, FCF per diluted share, or both. The approved decision is to show both, use total-company-FCF CAGR as the default `PASS`/`FAIL` control, and offer an explicit policy/CLI override that instead makes FCF/share CAGR controlling. This distinction is material because FCF/share incorporates dilution and repurchases; the approved extension therefore requires explicit weighted-average diluted-share, split/share-class compatibility, provenance, fixture, schema, and method-version decisions rather than an unversioned display calculation.

Cash conversion is important to stakeholders but remains only a future candidate: “reject” and “penalize” describe different policies, and no ratio, period, threshold, or missing-data treatment was supplied. Before any future composite can become a specification, it must define formulas, normalization and outlier treatment, comparison universe, sector-relative versus absolute treatment, missing-data policy, thresholds, point-in-time data boundaries, evaluation/rebalancing frequency, and empirical or backtest validation.

---

# 7. AI Philosophy

### Role of the LLM
Planning, capability selection, structured parameter extraction, bounded recovery, and narrative synthesis.

### Role of deterministic software
Market-data handling, Momentum/Graham/risk calculations, caching, persistence, validation, evaluation, and rendering.

### Autonomy
The product distinguishes **bounded agentic workflow** from **unattended autonomy**.

Before v0.2.5, the system may respond to an explicit user request by queuing/fanning out independent deterministic analyses, executing them concurrently within bounded process/resource limits, retaining completed Analysis Runs, and using the local LLM to synthesize already-computed typed evidence.

Unattended scheduling, proactive monitoring, notifications, self-initiated multi-step research, and long-lived background services remain v1.0 work and require evidence from real users before investment. Configured steps/retries/timeouts remain hard boundaries for any LLM orchestration.

### Explainability
Capture observable execution evidence through structured trajectory telemetry. Never infer private model reasoning.

---

# 8. Software Architecture

### High-level flow

```text
CLI / bounded orchestrator
  → structured analysis/tool selection or direct analysis request
      → deterministic strategies
        ├─ MomentumAnalyzer
        └─ Graham analysis
           ├─ graham_number (default)
           └─ graham_growth_value (explicit)
      → data boundaries
        ├─ BaseDataClient → historical prices
        └─ FinancialFactsProvider → quote/fundamentals/macro contract
             → GrahamInputResolver ← override/cache
             → SEC / Massive / Yahoo financial-facts adapters
      → deterministic result
  → investor presentation
      → concise / details / diagnostics / JSON
```

The initial Momentum and Graham pair is deliberately heterogeneous. Their coexistence tests whether the architecture is genuinely general rather than Momentum-specific.

Steps 2.3 and 2.4 are complete and approved. Slice G documentation synchronization, the complete repository gate, and explicit Step 2.4 closeout approval completed on 2026-08-30. Step 2.5 is now the current step and consumes the stable approved strategy contracts.

### Current package intent

```text
src/
├── core/telemetry/
├── llm/
├── tools/
├── orchestrator/
├── data/
│   ├── base_client.py
│   ├── massive/
│   ├── sec_edgar/
│   ├── financial/
│   ├── security_identity.py
│   ├── yfinance/
│   └── repositories/        # Step 3 target
├── analysis/
│   ├── base.py
│   ├── fcf_earnings_growth/
│   ├── momentum/
│   └── graham_value/
├── reporting/
└── utils/
```

Repositories belong under `src/data/repositories/` when Step 3 introduces them.

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

- **Historical-price boundary:** `BaseDataClient` remains focused on historical market series.
- **Financial-fact boundary:** Step 2.3 uses a dedicated financial-facts provider boundary, narrow resolved-input cache seam, input resolver, and typed provenance models.
- **SEC EDGAR production facts:** eligible completed fiscal-year diluted EPS plus fiscal-year-end balance-sheet components used for conservative BVPS derivation. Direct SEC BVPS is not claimed.
- **Yahoo production quote:** narrow current-price financial-facts adapter used for quote comparison on the Graham analyses using SEC EDGAR financial facts; historical valuation-quote support is not claimed.
- **Massive when explicitly selected:** current TTM diluted EPS and current quote when explicitly selected; live access requires `MASSIVE_API_KEY` and current facts do not masquerade as historical evidence.
- **Historical data:** first-class capability used by Momentum/time-series strategies.
- **Current quote:** first-class valuation input used for Graham price comparison; it is not a one-day historical request.
- **Fundamentals:** annual/TTM EPS and BVPS or its components retain their accounting basis, periods, availability dates, transformations, and source fields.
- **Macro series:** the contract can represent macro observations, but no production AAA-yield series is approved in Step 2.3. The current Growth CLI requires an explicit AAA-yield override rather than inventing or substituting a ticker proxy.
- **Growth EPS basis:** default/SEC Growth uses three-year-average diluted EPS; explicitly selected Massive Growth uses TTM diluted EPS. Unsupported provider/basis combinations fail explicitly.
- **Resolution:** each field uses override → valid cache → provider → unavailable precedence.
- **Subject validation:** override arithmetic alone does not verify a ticker; authoritative direct Graham output requires provider-backed security evidence.
- **Temporal correctness:** requested `as_of` rejects information not yet available; current snapshots do not silently answer historical requests.
- **Step 2.3 fixtures:** minimal deterministic data proving historical-price and financial-fact contracts plus resolution precedence/provenance; no live fallback.
- **Step 2.4 fixtures:** deterministic annual financial-series evidence extending the stable Step 2.3 fixture/data contracts for FCF and earnings growth.
- **Step 2.5 fixtures:** Golden evidence using the stable Steps 2.3–2.4 contracts.
- **Step 3.1 production persistence:** SQLite/WAL/cache-backed implementation of the shared contract.
- **Step 3.4 Analysis Run persistence:** durable investor-domain history of requested analyses, configs, typed results, provenance, warnings, and timestamps; distinct from execution telemetry.
- **Step 3.4 watchlists/refresh:** named ticker/analysis collections and user-initiated concurrent refresh; no daemon or unattended scheduler.
- **Report/view semantics:** a report is a deterministic, explicitly versioned projection of an Analysis Run. v0.2 does not create a second canonical report object. The projection version evolves independently from calculation method and result-schema versions, and replay uses persisted evidence plus explicit rendering options rather than provider/LLM calls, recalculation, mutable cache state, current identity lookup, or current-clock enrichment.
- **Provenance:** stored/fixture data carries enough source/date/schema information to audit its origin.
- **Separation:** market-data persistence, trajectory telemetry, Analysis Runs, Golden fixtures, rendered views, and evaluation results are distinct concerns.

---

# 12. AI Engineering Strategy

### Model modes
Light Mode is the recommended adoption mode; Full Dual-Tier remains optional.

### Prompt/schema discipline
- system-role invariants;
- context management;
- native structured output where supported;
- Pydantic validation/fallbacks.

### Evaluation
Step 2.5 measures:
- strategy/tool selection;
- Graham method selection where applicable;
- deterministic numerical correctness;
- overall case success.

Real-model evaluation is empirical and separate from deterministic regression infrastructure.

---

# 13. User Experience Philosophy

The pre-v0.2.5 product is a **terminal-first local investor research workbench**, not merely a collection of calculator commands and not yet a GUI/dashboard.

### Default interaction
An ordinary investor should be able to analyze a ticker directly or maintain a small watchlist, ask the system to perform the repetitive quantitative work, then revisit completed results without needing to understand provider APIs, cache keys, or Python internals.

The implemented direct Graham workflow now embodies that principle: `financial-agents graham TICKER` is a ticker analysis with a default Graham Number rather than an override-first formula calculator.

### Progressive disclosure
A successful concise result leads with the financial conclusion and only then exposes supporting context. Graham Number leads with the maximum indicated price/screening ceiling; Growth leads with the Growth Value and immediately states the expected-growth assumption. Current price and the plain-language price relationship follow when a compatible quote exists.

The concise view then exposes source/freshness summary, material warnings, and method limitations. Redundant success metadata such as `Status: ok` and `As of: current` does not compete with the result; historical `as_of` remains prominent in the heading.

Deeper views remain explicit:
- `--details` = financial provenance, accounting basis, dates, derivations, assumptions;
- `--diagnostics` = override/cache/provider resolution behavior and classified failures;
- `--json` = machine-readable typed result/provenance.

Operational logs are not the investor-facing result surface. A cache hit never hides the original economic data source. User overrides remain visible, but warnings should add information rather than mechanically repeat an assumption that the concise view has already labeled clearly.

### Coherent strategies, heterogeneous models
Momentum and Graham should feel like parts of one product through shared presentation vocabulary and layout, while remaining internally strategy-specific. Do not invent a generic strategy result bag merely for rendering consistency.

### Analysis history and “reports”
The durable product artifact is an **Analysis Run**, not a pre-rendered document. A run contains the requested method/configuration, typed result, provenance, warnings, temporal boundary, and version information. Terminal/JSON output and later Markdown/PDF reports are deterministic projections of the same underlying run.

Report projection is separately versioned because presentation contracts can evolve without changing financial method semantics or the stored typed-result schema. Given the same persisted run, projection version, mode, and explicit locale/format options, replay must produce the same semantic report. It does not fetch current provider data, invoke an LLM, recalculate financial values, re-resolve security identity, or consult mutable cache/clock state. Breaking report changes create a new projection version; older versions remain reproducible or move through an explicit audited migration.

### Agentic feel before autonomy
Step 3.4 should let a user maintain ticker/analysis lists, start a refresh, and inspect already-completed runs while the user-started process handles other independent jobs concurrently. This delivers useful “do the legwork for me” behavior without pretending a daemon or proactive autonomous analyst already exists.

Step 3.5 may add bounded local-model synthesis over completed deterministic results. The LLM may explain and compare evidence or suggest what to inspect next; it never invents financial facts, performs the deterministic calculation, or supplies an unrequested growth assumption.

### Real-user validation priority
Rich terminal presentation and the workspace/run-history workflow are intentionally pulled forward because v0.2.5 must test whether the tool is useful, not merely whether testers can execute a developer-oriented command. Graphical UI, full-screen TUI, high-fidelity charts, and executive report generation remain deferred until validation provides evidence.

# 14. Performance & Scalability

Single-node local usage is the primary target. Optimize deterministic local operations first; accept that LLM latency depends heavily on local hardware. User-initiated watchlist refresh may use bounded concurrency, but v0.2 does not require a continuously running service.

---

# 15. Extensibility Strategy

Extension points include:
- new analyzers under `src/analysis/`;
- new historical-price adapters behind `BaseDataClient`;
- new valuation quote/fundamentals/macro adapters behind the dedicated Step 2.3 financial-fact boundary;
- new typed tools through existing registration/dispatch;
- repository implementations under `src/data/repositories/`.

**Do not build a strategy plugin/registry framework speculatively.** The system should generalize only when concrete strategies expose a repeated need.

---

# 16. Documentation Strategy

Current documents:
- `README.md`
- `AGENTS.md`
- `RUNTIME_AGENTS.md`
- `docs/project/MASTER_PLAN.md`
- `docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md`
- `docs/project/milestones/v0.2/STEP_2_3_GRAHAM_DESIGN.md` — active compact specification for Step 2.3;
- `docs/project/milestones/v0.2/STEP_2_3_GRAHAM_SLICE_PLAN.md` — live slice-status tracker and completion gate;
- `docs/project/ARCHITECTURE.md`
- `docs/project/DISCOVERY_WORKBOOK.md`
- `docs/user/FINANCE_MATH.md`
- `docs/user/GLOSSARY.md`
- `docs/user/HARDWARE.md`

Planned when their owning work lands:
- `docs/EVALUATIONS.md` — Step 2.5;
- `docs/TOOL_DEVELOPMENT.md`;
- `docs/I18N_GUIDE.md`.

A planned document must not be treated as an existing source of instructions.

Product documentation records aggregate stakeholder needs, evidence, and resulting policy decisions. It does not attribute an input to an identifiable individual or narrate a distinctive exchange, response, interview fragment, or personal scenario unless explicit attribution is required and approved. Examples and personas remain generalized so stakeholders can recognize that their concerns are addressed without being identifiable from the text.

---

# 17. Development Workflow

- Fine-grained feature branches aligned with coherent implementation units.
- Follow active milestone review gates.
- Ruff + strict mypy + pytest before completion.
- Do not opportunistically redesign unrelated architecture.
- Documentation changes accompany durable architecture changes.
- Coding agents do not commit automatically; coherent checkpoint commits require explicit human approval.

---

# 18. Release Strategy

- **v0.1** — Core orchestration engine.
- **v0.2** — Reliability/observability + Graham/data/presentation foundation + heterogeneous Golden evaluation + circuit breakers + SQLite/data quality + local watchlists/Analysis Run history + Light Mode investor-workflow completion.
- **v0.2.5** — Real-user Light Mode validation.
- **v0.3** — Analytics expansion beyond the initial Momentum/Graham pair plus localization subject to user feedback.
- **v1.0** — Hardened unattended/multi-step autonomy, proactive monitoring/notifications where justified, visualization, and executive reporting.

---

# 19. Portfolio Objectives

The repository naturally demonstrates local-LLM orchestration, strict Python engineering, deterministic quantitative analysis, typed data architecture, evaluation discipline, and technical writing. These are outcomes of building a useful tool, not competing product goals.

---

# 20. Long-Term Vision

Finance remains primary. Core layers remain modular enough for possible later reuse, but the project does not commit to becoming a generic agent framework.

---

# 21. Non-Goals

- Full GUI/frontend or full-screen TUI before real-user validation evidence justifies it.
- Cloud LLM dependency for core reasoning.
- Automated order execution/HFT.
- Real-time websocket market data in the current milestone.
- Premature plugin/framework generalization.
- Pulling durable watchlists/Analysis Run persistence into Step 2.3 (owned by Step 3.4).
- Installing a daemon, unattended scheduler, proactive monitoring, or notification service in v0.2.
- Pulling later risk/localization/high-fidelity reporting work into Step 2.3.

---

# 22. Architectural Regrets to Avoid

- LLM arithmetic replacing deterministic Python.
- Momentum-specific assumptions embedded in generic orchestration.
- Speculative strategy registries/plugin systems.
- Treating a one-day historical download as a quote API when a current quote is a distinct requirement.
- Conflating the Graham Number with the forecast-dependent Graham growth formula.
- Burying financial input provenance in untyped metadata.
- Accepting look-ahead bias by using facts that were not yet filed/published at the requested analysis date.
- Assuming one upstream provider supplies well-defined quotes, fundamentals, and macro series without verifying field semantics.
- Treating missing accounting evidence as numeric zero merely to make a valuation complete.
- Letting override-heavy arithmetic create authoritative-looking analysis for an unverified ticker.
- Letting stale repository documentation compete with an approved active-step design.
- Telemetry becoming business control flow.
- Golden expectations generated from the same implementation under test.
- Live network fallback from deterministic fixtures.
- Broad refactors under narrow milestone tasks.
- Weakening benchmarks until the model reaches a target.
- Requiring workstation-class dual-tier hardware for basic use.
- Using operational log lines as the investor-facing result UI.
- Building a separate canonical “report” object when the durable Analysis Run already contains the result/evidence.
- Building a full-screen TUI or GUI before the v0.2.5 checkpoint proves the workflow is useful.
- Introducing a long-running background daemon before scheduling, freshness, recovery, rate-budget, and notification semantics are justified by user evidence.

---

# 23. Open Questions & Future Decisions

1. Will WAL + connection discipline remain sufficient for future denser multi-tool/multi-agent workloads?
2. Does `fr-CA` localization remain in v0.3 after v0.2.5 user feedback?
3. Do future additional strategies reveal a genuine need for a richer analyzer registry/plugin mechanism? This remains intentionally unresolved until concrete repetition justifies it.
4. Which exact AAA corporate-bond-yield series, frequency, provider, retrieval mechanism, and licensing terms should `graham_growth_value` eventually use instead of the current explicit user override?
5. Which future provider capabilities can honor historical `as_of` without look-ahead bias, especially for point-in-time quotes and later financial facts not yet represented by the current SEC integration?
6. At v0.2.5, do real investors prefer direct one-off analysis, watchlist/refresh/run-history workflow, or both—and which information belongs in the concise default versus details?
7. Does real-user feedback justify adding a deterministic historical-EPS-growth proxy, or should Growth remain assumption-only until analyst-consensus semantics are evidence-approved?

---

# 24. Glossary

- **BaseAnalyzer** — Existing abstract analysis boundary.
- **BaseDataClient** — Historical-price provider boundary.
- **FinancialFactsProvider** — Step 2.3 provider-neutral boundary for the minimum quote, fundamentals, and macro-observation contracts required by Graham analysis.
- **GrahamInputResolver** — Field-level override/cache/provider/unavailable resolution with typed provenance and time boundaries.
- **Analysis Run** — Durable investor-domain record of one requested analysis, distinct from trajectory telemetry; contains configuration, status, typed result, provenance, warnings, timestamps, and version identifiers.
- **Watchlist** — Named local set of tickers plus supported requested analysis configuration used by Step 3.4 user-initiated refresh.
- **Result View / Report** — Rendering of an Analysis Run in concise terminal, detailed, diagnostic, JSON, or later document form; not a competing canonical calculation record.
- **Graham Number** — Default earnings-and-book-value screening ceiling, not a complete intrinsic-value determination.
- **Graham growth value** — Explicit secondary, forecast-dependent growth-stock estimate.
- **Golden Benchmark Suite** — Fixed deterministic cases with verified behavioral/numeric expectations.
- **Fixture adapter** — Deterministic test implementation of the market-data contract.
- **Strategy-selection correctness** — Whether the appropriate deterministic analytical capability/tool was selected with valid arguments.
- **Numerical correctness** — Whether deterministic outputs match independently verified expectations.
- **Light Mode** — Default single-tier/modest-hardware mode.
- **Full Dual-Tier Mode** — Optional fast+deep local-model mode.
- **WAL** — SQLite Write-Ahead Logging.

---

# 25. Revision History

| Date | Summary |
|---|---|
| 2026-07-15 | Initial outline skeleton |
| 2026-08-01 | Expanded content and decision log |
| 2026-08-13 | Positioning, user-validation gate, and Light Mode decisions |
| 2026-08-16 | Telemetry/persistence sequencing and deterministic Golden-data boundary clarified |
| 2026-08-19 | Heterogeneous strategy independence adopted; Graham moved into v0.2 Step 2.3; current quote made first-class; Golden evaluation separated from the Graham/data foundation; speculative strategy framework explicitly rejected (the later Step 2.4 strategy addition placed Golden evaluation in Step 2.5 and circuit breakers in Step 2.6) |
| 2026-08-20 | Graham split into default Graham Number and explicit growth-value methods; Option A financial-facts provider/cache/resolver boundary adopted; provenance, `as_of`, and no-look-ahead rules made explicit; compact Step 2.3 specification added |
| 2026-08-21 | Investor-facing UX reconsidered before Slice F: E3 added for a user-viable standard Graham data configuration; F split into presentation/direct CLI; Step 3.4 watchlists + Analysis Run library added; Light Mode validation strengthened; bounded v0.2 agentic workflow separated from v1.0 unattended autonomy |
| 2026-08-24 | F2 investor workflow synchronized: standard Graham analyses using SEC EDGAR financial facts, Yahoo quote routing, explicit Massive TTM configuration, provider-backed ticker verification, result-first concise presentation, and explicit AAA-yield override policy recorded; Slice G final synchronization/gate began |
| 2026-08-30 | Step 2.4 shared security identity synchronized; Slice G documentation, complete repository gate, and explicit closeout approval completed; Step 2.5 became current; Step 3.4 investor reports defined as deterministic, independently versioned projections of persisted Analysis Runs |

---

# 26. Appendix A: Decision Log

| ID | Date | Decision | Rationale / Consequence | Status |
|---|---|---|---|---|
| D1 | 2026-Q2 | 100% local LLM orchestration; no cloud LLM in core loop | Privacy, local control, zero cloud dependency | Accepted |
| D2 | 2026-Q2 | Dual-tier model option | Preserves higher-capability local configuration | Accepted |
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
| D22 | 2026-08-19 | Separate the Graham/data foundation from Golden evaluation; later sequencing places the Step 2.4 strategy addition before Golden evaluation in 2.5 and circuit breakers in 2.6; reject a speculative strategy registry | Gives humans an explicit review gate and limits scope creep while allowing one additional heterogeneous strategy before fixtures freeze public behavior | Accepted |
| D23 | 2026-08-20 | Implement two explicit Graham methods: default `graham_number` and secondary `graham_growth_value` | Avoids conflating a defensive screening ceiling with a forecast-dependent growth estimate | Accepted |
| D24 | 2026-08-20 | Use Option A: keep `BaseDataClient` historical-price focused and add a dedicated financial-facts provider boundary, cache seam, resolver, and provenance models | Keeps materially different quote/fundamental/macro inputs out of a price-history-shaped interface while preserving narrow contracts | Accepted |
| D25 | 2026-08-20 | Resolve each valuation input through override → valid cache → provider → unavailable with strict `as_of` and availability-date rules | Makes results reproducible, auditable, and resistant to silent look-ahead bias | Accepted |
| D26 | 2026-08-20 | Use one `graham` CLI with an explicit method discriminator; omitted method selects the Graham Number | Keeps the user-facing strategy coherent while preventing silent method substitution | Accepted |
| D27 | 2026-08-21 | Treat the pre-validation product as a terminal-first investor research workbench with concise/default and detailed/diagnostic/JSON views | Real-user validation must test usefulness and trust, not merely command execution | Accepted |
| D28 | 2026-08-21 | Add Slice E3 before CLI polish to close the production BVPS/default-Graham viability gap | A default command that routinely lacks a required input is a product blocker, not a presentation issue | Accepted |
| D29 | 2026-08-21 | Persist Analysis Runs in Step 3.4; treat reports as renderings of runs | Avoids duplicate canonical result artifacts and supports later terminal/Markdown/PDF views | Accepted |
| D30 | 2026-08-21 | Add watchlists and user-initiated concurrent refresh in v0.2, but defer daemons/unattended scheduling/proactive monitoring/notifications to v1.0 | Delivers useful agentic legwork before validation without prematurely owning long-running-service semantics | Accepted |
| D31 | 2026-08-21 | Permit explicitly human-approved intermediate checkpoint commits/pushes after review/gates | Protects substantial reviewed work and improves history without weakening step-completion review gates | Accepted |
| D32 | 2026-08-24 | Default production Graham routing uses SEC EDGAR financial facts plus Yahoo current quote; explicit Massive Growth uses TTM EPS/current quote | Keeps default analysis usable without Massive credentials while preserving provider-specific EPS semantics and narrow capabilities | Accepted |
| D33 | 2026-08-24 | Keep Growth's AAA yield as an explicit user input until a production series passes the evidence gate | Avoids inventing macro provenance or treating an arbitrary finance ticker as a documented AAA corporate-bond series | Accepted |
| D34 | 2026-08-24 | Require provider-backed security evidence before authoritative direct Graham output | Prevents fully override-driven arithmetic from falsely validating an arbitrary ticker identity | Accepted |
| D35 | 2026-08-24 | Use result-first concise success output and avoid redundant assumption/warning repetition | Prioritizes the investor's financial question while retaining progressive disclosure and material caveats | Accepted |
| D36 | 2026-08-30 | Treat investor reports as deterministic, independently versioned projections of persisted Analysis Runs | Preserves one canonical financial record, makes historical rendering reproducible, and prevents current provider/LLM/cache/clock state from silently changing old reports | Accepted |
| D37 | 2026-08-30 | Approve Slice G and Step 2.4 closeout; make Step 2.5 the current step | The synchronized documentation and complete quality gate satisfy the final Step 2.4 review gate, so Golden evaluation may begin against the stable approved contracts | Accepted |

---

### Document Versioning Policy

The Master Plan and Discovery Workbook are versioned through Git. Embedded document version numbers are intentionally avoided.

*End of Discovery Workbook*
