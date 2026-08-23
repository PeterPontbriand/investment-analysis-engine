# Financial Data Agents Architecture

**Related roadmap:** `MASTER_PLAN.md`<br/>
**Active implementation detail:** `milestones/v0.2/IMPLEMENTATION_PLAN.md`<br/>
**Step 2.3 implementation specification:** `milestones/v0.2/STEP_2_3_GRAHAM_DESIGN.md`<br/>
**Rationale:** `DISCOVERY_WORKBOOK.md`<br/>
**Last updated:** 2026-08-21<br/>
**Current status:** Step 2.2 implementation complete. Step 2.3 Slices A–E2 are implemented and approved; a reviewed checkpoint commit/push is permitted. Slice E3 closes the production default-Graham data gap, followed by F1/F2 investor presentation/direct CLI work. Step 3.4 research-workspace concepts are approved roadmap targets, not current implementation.

This document describes current boundaries and approved near-term target seams. It does not claim that Step 2.3 target components already exist, and it does not override the active milestone plan's sequencing or review gates.

---

## 1. Architectural invariants

1. **LLM orchestration, deterministic execution:** The LLM plans/selects tools and synthesizes results; Python performs calculations, validation, data processing, and persistence.
2. **Typed boundaries:** Tool/analyzer/data inputs and outputs are explicitly typed at application boundaries.
3. **Heterogeneous strategies:** Different financial strategies may have different config/data/result shapes. The architecture must not make every analysis Momentum-shaped.
4. **No speculative strategy framework:** Reuse the existing `BaseAnalyzer` and current tool dispatch path unless implementation proves a new abstraction is necessary.
5. **Provider isolation:** Historical-price access remains behind `BaseDataClient`; Step 2.3 valuation facts use a dedicated provider/resolution boundary rather than enlarging a price-history-shaped interface.
6. **Historical prices, quotes, fundamentals, and macro series are distinct capabilities:** A composed valuation façade may coordinate narrow providers, but no upstream service is assumed to supply every capability.
7. **Evaluation is not persistence:** Golden fixtures, evaluation results, trajectory telemetry, and production market-data storage are separate concerns.
8. **Local-LLM boundary:** The LLM cannot directly execute shell/code or access the external network. Registered data tools may perform controlled provider access.
9. **Telemetry is observational:** Telemetry failures must not change business execution semantics.
10. **Light Mode first:** Core useful analysis must remain viable under the documented Light Mode path.
11. **Method-explicit financial semantics:** Graham Number and Graham growth value retain distinct names, inputs, typed results, and limitations.
12. **Time-bounded provenance:** Resolved inputs preserve source, reporting/observation and availability dates, transformations, cache/override state, and requested analysis `as_of`.
13. **Presentation without homogenization:** Momentum and Graham use a coherent investor-facing visual grammar while retaining strategy-specific typed result models.
14. **Operational logs are not product UI:** User results are rendered by a presentation boundary; logs and trajectory telemetry remain diagnostics/execution evidence.
15. **Analysis Run is a product-domain record:** Step 3.4 persists requested analysis/config/result/provenance history separately from telemetry `RunContext`; reports/views render that record.
16. **Bounded v0.2 agentic behavior:** User-initiated refresh may execute independent analysis jobs concurrently. Daemons, unattended scheduling, proactive monitoring, and notifications remain later autonomy work.

---

## 2. Current and near-term architecture

```text
                        terminal / caller
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
       direct analysis request        bounded orchestrator path
               |                             │
               └──────────────┬──────────────┘
                              ▼
                    Tool / analysis dispatch
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
      MomentumAnalyzer                  Graham analysis
        (implemented)              number / growth methods
               │                             │
      historical prices              InputResolver
               │               override → cache → provider
               │                             │
       BaseDataClient              ValuationFactsProvider
               │                             │
               └──────────────┬──────────────┘
                              ▼
                     typed strategy result
                              │
                              ▼
              investor presentation boundary (F1)
          concise · details · diagnostics · JSON
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
          direct terminal view       Analysis Run library
                                     (Step 3.4 target)
                                             │
                                             ▼
                                later report/view formats
```

`BaseAnalyzer` remains the existing common analyzer abstraction where applicable. The diagram does **not** imply a new strategy registry, plugin system, factory hierarchy, or unified strategy-result model.

The presentation boundary is intentionally downstream of deterministic calculation and provenance. Step 3.4 later persists Analysis Runs and renders them through the same presentation contract rather than recalculating merely to display historical results.

## 3. Core entities and boundaries

### `BaseAnalyzer`
Existing abstract analysis boundary. A strategy owns:
- its configuration model;
- deterministic calculation;
- typed result/metrics;
- only the data capabilities it actually requires.

### `MomentumAnalyzer`
Existing deterministic SMA/crossover analyzer. It consumes historical market data and returns Momentum-specific metrics.

### Graham analysis (Step 2.3 implemented foundation; E3/F1/F2 remain)
The approved Graham family has two method identifiers:

- `graham_number` — default screening-ceiling method using three-year-average EPS by default plus BVPS;
- `graham_growth_value` — explicit secondary method using normalized EPS, user-supplied growth under the initial policy, and a documented current AAA-yield observation.

The implementation may use separate analyzer/config/result models or a typed discriminated union, but invalid cross-method combinations must not be representable. Existing transitional interfaces are not compatibility constraints when they conflict with the approved method-explicit or investor-facing contracts.

Graham is intentionally not required to return `TrendStatus` or consume a historical DataFrame merely to look like Momentum.

### `BaseDataClient`
Existing provider boundary for historical market prices. Under the selected Step 2.3 Option A direction, it remains price-history focused rather than becoming the owner of fundamentals, valuation quotes, macro series, and cache policy.

Do not implement current quote retrieval by invoking a one-day historical request merely to avoid defining the correct valuation-input capability.

### `ValuationFactsProvider` boundary (Step 2.3 implemented)
A dedicated provider-neutral valuation-input boundary supplies or composes the minimum quote, company-fundamental, and macro-series capabilities required by the two Graham methods.

The provider-neutral boundary and verified E2 production façade/adapters now exist. SEC EDGAR supplies filing-dated annual diluted EPS; Massive supplies current TTM diluted EPS/current price. Unsupported capabilities remain unavailable. Slice E3 may add only a defensible, evidenced BVPS/direct-or-derived capability.

### `InputResolver` (Step 2.3 implemented)
Resolves each required field independently using:

```text
explicit override → valid cache → configured provider → unavailable
```

Calculators receive resolved values and do not perform I/O. The resolver enforces requested `as_of` boundaries and preserves typed provenance.

### Valuation cache seam (Step 2.3 implemented)
A narrow in-memory/fixture-backed `get`/`put` seam proves precedence, temporal eligibility, and provenance. The resolver—not the cache—owns provider fallback. Durable SQLite-backed caching remains Step 3.1.

### Resolved input and provenance models (Step 2.3 implemented)
Typed records preserve value, units/currency, source kind, provider field/series, reporting/observation period, availability/filing date where supplied, analysis `as_of`, retrieval time, transformations/derived lineage, and override/cache state.

### Fixture-backed data capabilities
Introduced minimally in Step 2.3 to prove the historical-price and valuation-input contracts:
- deterministic;
- historical data for Momentum;
- quote, EPS history/TTM EPS, BVPS facts/components, and AAA-yield observations for Graham;
- override/cache/provider/unavailable resolution paths;
- realistic reporting, availability, `as_of`, and retrieval metadata;
- explicit failure when data is absent;
- no live network fallback.

Step 2.4 reuses this foundation for Golden cases.

### Investor-facing result presentation (Step 2.3 F1 target)
A narrow presentation seam maps Momentum and Graham typed outputs into a common investor-facing grammar without altering their domain models. The default view is concise; details expose financial provenance; diagnostics expose resolution mechanics; JSON exposes stable machine-readable data. Material overrides and warnings remain visible.

### `AnalysisRun` (Step 3.4 target)
A durable investor-domain record of one requested analysis. It owns an `analysis_run_id`, ticker, analysis/method, requested `as_of`, configuration snapshot, status, typed result payload, resolved-input provenance, warnings, timestamps, and calculation/version identifiers. It may link to execution/trajectory identity but must not overload telemetry `RunContext`.

A report is a rendering of an Analysis Run, not a second canonical result object in v0.2.

### Watchlist / refresh workspace (Step 3.4 target)
Named watchlists hold tickers and supported requested analyses. A user-initiated refresh may execute independent ticker/analysis jobs concurrently and persist each outcome as it finishes. No daemon, scheduler, proactive monitoring, or notification service is implied.

### `TrajectoryEvent` / `TrajectoryRecorder` / `TrajectorySink`
Step 2.1 structured telemetry components. JSONL is the initial sink; SQLite is added in Step 3.1.

Telemetry records observable execution evidence and does not provide benchmark ground truth.

---

## 4. Structured-output boundary

Step 2.2 establishes structured-output enforcement with layered defenses:

1. use native Ollama/provider schema constraints when capability is confirmed;
2. retain Pydantic validation at the application boundary;
3. use the configured prompt-based schema fallback when native capability is unavailable or unknown;
4. retain legacy compatibility parsing only as the final fallback where required.

Empirical model-by-model validation of native-schema behavior for the supported Light Mode configuration remains a non-blocking validation item before Step 3.5 completion.

Do not rewrite the runtime around a model-specific assumption merely to make one model pass.

---

## 5. Module layout

```text
src/
├── config.py
├── core/
│   ├── constants.py
│   └── telemetry/
│       ├── models.py
│       ├── recorder.py
│       ├── run_context.py
│       ├── redaction.py
│       └── sinks/
├── llm/
├── tools/
├── orchestrator/
├── data/
│   ├── base_client.py
│   ├── yfinance_client.py
│   ├── massive_client.py
│   └── repositories/
├── analysis/
│   ├── base.py
│   ├── momentum/
│   └── graham_value/          # Step 2.3 target; exact files follow approved plan
├── reporting/
└── utils/
```

Step 2.3 adds/refines Graham under `src/analysis/` according to current package conventions. The selected Option A valuation-provider/resolver/cache seams should live with the narrowest responsible package after the worktree and provider feasibility are inspected; this diagram does not pre-authorize speculative files. Step 3 persistence/repositories remain under `src/data/repositories/`.

---

## 6. Data flow and persistence boundaries

The project distinguishes the financial execution path:

```text
External Provider
      │
      ▼
Provider Adapter Boundary
      │
      ├── BaseDataClient ─────────────► historical series ─► Momentum
      │
      └── ValuationFactsProvider
              ├── quote
              ├── company fundamentals
              └── macro observation
                      │
                      ▼
              InputResolver ◄── override / cache
                      │
                      ▼
               resolved inputs
                      │
                      ▼
             deterministic Graham method
                      │
                      ▼
                typed strategy result
                      │
                      ▼
             presentation boundary
```

And it separately distinguishes persistence/artifacts:

```text
Golden fixture data ──► fixture adapter ──► deterministic/evaluation execution
trajectory events   ──► telemetry sink (JSONL / SQLite)
production data     ──► SQLite/cache repositories
analysis result     ──► Analysis Run repository (Step 3.4)
Analysis Run        ──► concise/details/diagnostic/JSON view
evaluation result   ──► Golden evaluation artifact
```

These stores/artifacts must not be collapsed merely because they can all be serialized. In particular, telemetry describes execution, while an Analysis Run is the durable investor-facing outcome of one requested analysis.

## 7. Golden-Suite architecture (Step 2.4)

Step 2.4 consumes the stable Step 2.3 contracts.

```text
Golden Case
   │
   ├── prompt/task
   ├── fixture IDs
   ├── expected strategy/tool behavior
   └── independently verified numeric expectations
   │
   ▼
real orchestration path
   │
   ├── structured strategy/tool evidence
   └── deterministic result
   │
   ▼
Evaluator
   ├── strategy/tool-selection score
   ├── Graham method-selection score
   ├── numerical-correctness score
   └── overall case pass/fail
```

Deterministic/no-LLM tests validate fixtures, contracts, analytics, evaluator behavior, and report serialization. They cannot measure actual model strategy selection.

Real-local-Ollama evaluation is an empirical mode and remains separate from deterministic regression/CI tests unless explicitly configured.

The ≥90% target is a measurement target, not permission to weaken cases until a model passes.

---

## 8. Logging and telemetry boundary

Operational logging, investor presentation, and trajectory telemetry remain separate:

```text
Agent Runtime
   │
   ├── typed analysis result ─► investor presenter ─► terminal/run view
   ├── operational logging ───► human-readable execution diagnostics
   │
   └── trajectory telemetry ──► machine-readable execution evidence
                                ├── JSONL (Step 2.1)
                                └── SQLite (Step 3.1)
```

Telemetry may capture observable provider/model metadata, prompts/completions, tool arguments/results, latency, and exposed token metrics subject to retention/redaction policy.

Private model reasoning is never reconstructed.

---

## 9. Failure and reliability boundary

- Recoverable failures may enter a bounded retry/repair path.
- Non-recoverable failures halt with structured diagnostics.
- Step 2.5 owns hard execution/time/error caps.
- The configured limits are authoritative; runtime documents must not invent a separate fixed turn limit.
- Telemetry sink failures fail open.

---

## 10. Development guardrails

- Preserve existing behavior outside the active step.
- Use the smallest change that satisfies the current milestone plan.
- Do not create a generic strategy registry merely to support Momentum + Graham.
- Do not collapse the two Graham methods behind ambiguous names or optional-field bags.
- Keep calculators free of provider/cache/CLI I/O.
- Enforce requested `as_of` as an information boundary; do not substitute later current facts.
- Do not assume yfinance or any one adapter supplies a documented AAA macro series.
- Do not build Step 2.4 evaluator/reporting work during Step 2.3.
- Do not build Step 3.1 production persistence/cache during Step 2.3/2.4.
- Do not use operational logger lines as the primary investor-facing result renderer.
- Do not force Momentum and Graham into one generic result object merely for presentation.
- Do not pull Step 3.4 watchlists/Analysis Run persistence into Step 2.3.
- Do not build a daemon, scheduler, proactive-monitoring service, notification system, full-screen TUI, or executive-report generator before the roadmap step that owns it.
- Use `src/data/repositories/` for the planned repository layer.
- Run Ruff, `mypy --strict`, and pytest according to the active milestone plan.
