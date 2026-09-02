# Financial Data Agents Architecture

**Related roadmap:** `docs/project/MASTER_PLAN.md`<br/>
**Active implementation detail:** `milestones/v0.2/IMPLEMENTATION_PLAN.md`<br/>
**Step 2.3 implementation specification:** `milestones/v0.2/step-2.3/STEP_2_3_GRAHAM_DESIGN.md`<br/>
**Rationale:** `docs/project/DISCOVERY_WORKBOOK.md`<br/>
**Last updated:** 2026-08-31<br/>
**Current status:** Steps 2.2–2.5 are complete and approved. Step 2.5A D0 and Gate A are complete; bounded A0 is implemented and verified, with work stopped and A1 blocked until A0 review. Step 3.4 research-workspace concepts are approved roadmap targets, not current implementation.

This document describes current boundaries and approved near-term target seams. Current Step 2.3 components are identified as implemented; later persistence/workspace/evaluation components remain explicitly labeled targets. It does not override the active milestone plan's sequencing or review gates.

---

## 1. Architectural invariants

1. **LLM orchestration, deterministic execution:** The LLM plans/selects tools and synthesizes results; Python performs calculations, validation, data processing, and persistence.
2. **Typed boundaries:** Tool/analyzer/data inputs and outputs are explicitly typed at application boundaries.
3. **Heterogeneous strategies:** Different financial strategies may have different config/data/result shapes. The architecture must not make every analysis Momentum-shaped.
4. **No speculative strategy framework:** Reuse the existing `BaseAnalyzer` and current tool-dispatch flow unless implementation proves a new abstraction is necessary.
5. **Provider isolation:** Historical-price access remains behind `BaseDataClient`; Step 2.3 financial facts use a dedicated provider/resolution boundary rather than enlarging a price-history-shaped interface.
6. **Historical prices, quotes, fundamentals, and macro series are distinct capabilities:** A composed valuation façade may coordinate narrow providers, but no upstream service is assumed to supply every capability.
7. **Evaluation is not persistence:** Golden fixtures, evaluation results, trajectory telemetry, and production market-data storage are separate concerns.
8. **Local-LLM boundary:** The LLM cannot directly execute shell/code or access the external network. Registered data tools may perform controlled provider access.
9. **Telemetry is observational:** Telemetry failures must not change business execution semantics.
10. **Light Mode first:** Core useful analysis must remain viable under the documented Light Mode workflow.
11. **Method-explicit financial semantics:** Graham Number and Graham growth value retain distinct names, inputs, typed results, and limitations.
12. **Time-bounded provenance:** Resolved inputs preserve source, reporting/observation and availability dates, transformations, cache/override state, and requested analysis `as_of`.
13. **Presentation without homogenization:** Momentum, Graham, and Free Cash Flow & Earnings Growth use a coherent investor-facing visual grammar while retaining strategy-specific typed result models.
14. **Operational logs are not product UI:** User results are rendered by a presentation boundary; logs and trajectory telemetry remain diagnostics/execution evidence.
15. **Analysis Run is a product-domain record:** Step 3.4 persists requested analysis/config/result/provenance history separately from telemetry `RunContext`; reports/views render that record.
16. **Bounded v0.2 agentic behavior:** User-initiated refresh may execute independent analysis jobs concurrently. Daemons, unattended scheduling, proactive monitoring, and notifications remain later autonomy work.
17. **Deterministic, versioned investor-report projection:** A stored Analysis Run is projected into an investor report without provider access, LLM synthesis, financial recalculation, or current-state enrichment. The projection contract has its own explicit version, independent of strategy method and result-schema versions.

---

## 2. Current and near-term architecture

```text
                        terminal / caller
                              │
               ┌──────────────┴──────────────┐
               ▼                             ▼
       direct analysis request        bounded orchestrator flow
               │                             │
               └──────────────┬──────────────┘
                              ▼
                    Tool / analysis dispatch
                              │
       ┌───────────────┬───────────────────┐
       ▼               ▼                   ▼
 MomentumAnalyzer  Graham analysis   FCFEarningsGrowthAnalyzer
       │           number / growth           │
historical prices  GrahamInputResolver  AnnualGrowthSeriesResolver
       │               │                   │
 BaseDataClient   FinancialFactsProvider  SEC annual facts
       └───────────────┴───────────────────┘
                              ▼
                     typed strategy result
                              │
                              ▼
               investor presentation boundary
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
Deterministic SMA/crossover/RSI analyzer. `MomentumInputResolver` consumes the provider-neutral `MarketDataProvider` boundary, applies strict `bar_timestamp <= effective_as_of` truncation before calculation, wraps retained closes in `ResolvedInput` provenance, and records a `ResolutionTrace`. `MomentumPolicy` owns the short/long/RSI defaults. SMA and RSI availability is exposed through standard `MetricResult` values with `insufficient_history` reason codes while compatibility views preserve the existing optional numeric fields.

### Graham analysis (Step 2.3 implemented through F2)
The Graham family has two method identifiers:

- `graham_number` — default screening-ceiling method using three-year-average EPS by default plus BVPS;
- `graham_growth_value` — explicit secondary method using EPS, user-supplied expected growth under the current policy, and an explicit current AAA-yield input until a production series is approved.

The implemented direct command is `financial-agents graham TICKER [--method number|growth]`. Invalid cross-method combinations are rejected at the CLI boundary. Existing transitional flag aliases remain only where intentionally retained for compatibility.

Graham is intentionally not required to return `TrendStatus` or consume a historical DataFrame merely to look like Momentum.

### Free Cash Flow & Earnings Growth analysis (Step 2.4 implemented through Slice F-1)
`FCFEarningsGrowthAnalyzer` deterministically derives completed annual total-company FCF and FCF per diluted share, computes their CAGRs alongside diluted-EPS CAGR, and returns a versioned `FCFEarningsGrowthResult`. Its classification is `PASS`, `FAIL`, or `INDETERMINATE`, separate from software execution status.

`ProductionAnnualGrowthSeriesResolver` selects compatible, contiguous annual evidence under the requested `as_of` boundary. The default horizon policy prefers 5 elapsed years, then 4, then 3; explicit horizons are strict. Total-company FCF controls classification by default, while an explicit policy can select FCF per diluted share. Optional FCF yield is informational only, and optional forward EPS evidence follows an explicit display-only, confirmation, or hard-gate policy.

The direct command is `financial-agents fcf-growth TICKER`. The strategy retains its own policy, annual-observation, metric, classification, and forward-evidence types rather than being forced into either the Momentum or Graham result shape.

### `BaseDataClient`
Existing provider boundary for historical market prices. Under the selected Step 2.3 Option A direction, it remains price-history focused rather than becoming the owner of fundamentals, valuation quotes, macro series, and cache policy.

Current quote retrieval is a separate valuation capability; it is not implemented as a one-day historical request.

### `FinancialFactsProvider` boundary (Step 2.3 implemented)
A dedicated provider-neutral financial-fact boundary supplies or composes the minimum quote and company-fundamental capabilities required by the two Graham methods. The contract can represent macro observations, but the production CLI does not currently claim an approved live AAA-yield series.

Implemented production adapters are deliberately narrow:

- **SEC EDGAR (`sec_edgar`)** — completed annual duration facts from `10-K`, `10-K/A`, `20-F`, `20-F/A`, `40-F`, and `40-F/A`. Existing exact US-GAAP mappings cover diluted EPS, diluted weighted-average shares, operating cash flow, and CapEx. Exact IFRS mappings cover diluted EPS, diluted weighted-average shares, operating cash flow, and physical-PP&E CapEx. Fiscal-year-end balance-sheet components and conservative BVPS derivation remain US-GAAP-only; IFRS BVPS and preferred-zero inference are unsupported.
- **Massive (`massive`)** — current TTM diluted EPS and current price for the Massive when explicitly selected. Live use requires `MASSIVE_API_KEY`; current-only facts do not masquerade as historical evidence.
- **Yahoo Finance (`yfinance`)** — narrow current-price financial-facts adapter used for quote comparison on the Graham analyses using SEC EDGAR financial facts. It does not claim historical quote support through the financial-facts contract.

The Graham Number using its standard SEC financial facts uses SEC financial facts plus Yahoo current quote comparison. Its explicit Massive route is deliberately limited to Massive TTM EPS plus a BVPS override and may use a Massive quote. SEC-backed Growth defaults to three-year-average EPS plus Yahoo quote; explicitly selecting Massive uses its supported TTM EPS/current-price data. Unsupported provider/basis combinations are rejected before provider work.

### Security identity and instrument applicability (Step 2.4 F-1 implemented; P1 approved)
`SecurityIdentityProvider` is a narrow optional capability beside, not inside, numeric financial facts. F-1 returns an immutable current descriptive snapshot with normalized ticker, optional instrument name/listing venue/issuer and instrument identifiers, provider identity, and timezone-aware `resolved_at`. SEC retains current ticker-title/CIK evidence from its ticker mapping; Yahoo retains supported instrument metadata, including non-company names where available.

Approved pre-Golden P1 preserves that one-provider snapshot and adds a separate immutable `InstrumentKindEvidence` value with normalized kind, retained raw provider classification, provider identity, and resolution time. A composed `InstrumentProfile` can therefore retain SEC identity/CIK and Yahoo kind evidence without pretending that one provider supplied both. Kind is provider-backed metadata: it is never inferred from a ticker, name, missing financial facts, or another strategy's success. The exact proposed mappings and schema consequences are recorded in the [P1 instrument applicability mapping record](milestones/v0.2/step-2.5/STEP_2_5_P1_INSTRUMENT_APPLICABILITY_MAPPING_RECORD.md).

An ordered, explicitly injected profile resolver selects the best available descriptive identity by provider precedence and obtains kind evidence independently. Each provider/capability is consulted at most once per run, and one YFinance metadata fetch is shared by its identity and kind capabilities. Missing metadata, unsupported capability, and lookup failure remain unknown and fail open. They cannot invalidate or downgrade otherwise usable financial evidence. Affirmative kind evidence is different from lookup failure: a provider-confirmed ETF establishes that both Graham methods and the existing company-level FCF Growth strategy are `not_applicable`, while Momentum remains applicable. This strategy-specific applicability decision does not change any financial formula and does not silently select a future ETF strategy.

A present name uses `Instrument Name (TICKER) — Analysis` in successful, unsuccessful, and `not_applicable` presentations; whitespace is normalized without changing official capitalization or punctuation. Ordinary unavailability/provider failures do not claim the ticker is invalid without affirmative provider evidence. Current metadata does not prove the identity or instrument kind that applied at a historical analysis `as_of`.

### `GrahamInputResolver` / input resolution (Step 2.3 implemented)
Resolves each required field independently using:

```text
explicit override → valid cache → configured provider → unavailable
```

Calculators receive resolved values and do not perform I/O. The resolver enforces requested `as_of` boundaries and preserves typed provenance. Method-input assembly adds only method-semantic annotations that are justified by retained evidence, such as fiscal-year-end basis on derived BVPS.

### Resolved-input cache seam (Step 2.3 implemented)
A narrow in-memory/fixture-backed `get`/`put` seam proves precedence, temporal eligibility, and provenance. The resolver—not the cache—owns provider fallback. Durable SQLite-backed caching remains Step 3.1.

### Durable instrument profiles and ETF aggregate FCF (P2 planned after Step 3.1)

P1 is request-scoped and intentionally adds no durable cache. After Step 3.1 is implemented and approved, P2 may add a repository-backed instrument-profile cache retaining normalized/raw kind, descriptive identity, stable identifiers where available, provider provenance, resolution/retrieval time, and explicit freshness metadata. Its exact dependency on the Step 3.2 repository layer and Step 3.3 invalidation policy is reviewed after Step 3.1 rather than assumed now.

P2 also plans a separate look-through ETF FCF-growth strategy after a holdings-provider and product-policy checkpoint. The strategy owns its holdings-effective-date, weighting, cash/derivative, currency, missing/stale constituent, coverage, rebalancing, and `as_of` semantics plus native typed configuration/result/tool identity. It may reuse company-level calculations for constituents but does not add ETF branches to or redefine the existing company-level FCF Growth strategy. Company-level FCF requested for a known ETF remains explicitly `not_applicable`; orchestration cannot silently substitute the aggregate strategy.

### Resolved input and provenance models (Step 2.3 implemented)
Typed records preserve value, units/currency, source kind, provider field/series, reporting/observation period, availability/filing date where supplied, analysis `as_of`, retrieval time, transformations/derived lineage, and override/cache state.

### Fixture-backed data capabilities
Introduced minimally in Step 2.3 to prove the historical-price and financial-fact contracts:
- deterministic;
- historical data for Momentum;
- quote, EPS history/TTM EPS, BVPS facts/components, and AAA-yield observations for Graham;
- override/cache/provider/unavailable resolution branches;
- realistic reporting, availability, `as_of`, and retrieval metadata;
- explicit failure when data is absent;
- no live network fallback.

Fixture support for a capability does not claim that the same capability exists in a production adapter. Step 2.4 reuses this foundation for Golden cases.

### Investor-facing result presentation (Steps 2.3 and 2.4 implemented through Slice F-1)
A narrow presentation seam maps Momentum, Graham, and Free Cash Flow & Earnings Growth typed outputs into a common investor-facing grammar without altering their domain models. The default view is concise and result-first; details expose financial provenance; diagnostics expose resolution mechanics; JSON exposes each strategy's stable versioned machine-readable contract. Material overrides and warnings remain visible.

Each JSON presentation exposes one explicit nullable `security_identity` snapshot. Momentum and Graham presentation schemas increment from 1 to 2. The FCF/Earnings Growth presentation schema increments from 2 to 3 while retaining `result_schema_version = 2`, because identity is presentation metadata and does not change the typed calculation result.

The Graham Number is labeled as a **maximum indicated price / screening ceiling**. The Growth view makes the expected-growth assumption explicit and warns when the AAA yield is user-supplied. Successful concise output omits redundant `Status: ok` and `As of: current`; historical requests surface the `as_of` boundary in the heading. All required-input/provider/ticker failures pass through the typed presentation boundary, and every calculation status has an exhaustive plain-English investor label.

### `AnalysisRun` (Step 3.4 target)
A durable investor-domain record of one requested analysis. It owns an `analysis_run_id`, ticker, analysis/method, requested `as_of`, configuration snapshot, status, typed result payload, resolved-input provenance, warnings, timestamps, calculation/version identifiers, and the nullable security identity/instrument-profile snapshot used by that completed run (including provider and `resolved_at`). It may link to execution/trajectory identity but must not overload telemetry `RunContext`.

A report is a rendering of an Analysis Run, not a second canonical result object in v0.2. Viewing an old run must use its persisted identity snapshot rather than re-resolving the ticker and silently relabeling history after ticker reuse.

The investor-report boundary is a deterministic, versioned projection. Given the same persisted Analysis Run, projection version, presentation mode, and explicit locale/format options, it must produce the same semantic report without provider calls, LLM calls, financial recalculation, mutable cache reads, or wall-clock-dependent enrichment. The report exposes its projection version separately from the run's calculation method version and typed result-schema version. A breaking change to report structure or field meaning requires a new projection version; historical projection versions remain reproducible or require an explicit, auditable migration rather than being silently reinterpreted.

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

Relevant current packages include:

```text
src/
├── analysis/
│   ├── base.py
│   ├── momentum/
│   ├── fcf_earnings_growth/
│   │   ├── analyzer.py
│   │   ├── calculators.py
│   │   ├── input_resolver.py
│   │   └── models.py
│   └── graham_value/
│       ├── calculators.py
│       ├── input_resolver.py
│       ├── models.py
│       └── ...
├── core/
│   └── telemetry/
├── data/
│   ├── base_client.py
│   ├── massive/
│   │   └── valuation.py
│   ├── sec_edgar/
│   │   └── valuation.py
│   ├── valuation/
│   │   ├── facts.py
│   │   ├── production.py
│   │   ├── provenance.py
│   │   ├── providers.py
│   │   └── resolver.py
│   └── yfinance/
│       ├── client.py
│       └── valuation.py
├── reporting/
│   ├── graham.py
│   ├── fcf_earnings_growth.py
│   ├── momentum.py
│   └── presentation.py
├── llm/
├── orchestrator/
├── tools/
└── utils/
```

The valuation-provider/resolver/cache seams live with the narrowest responsible package rather than inside `BaseDataClient`. Step 3 persistence/repositories remain planned under `src/data/repositories/`.

---

## 6. Data flow and persistence boundaries

The project distinguishes the financial execution flow:

```text
External Provider
      │
      ▼
Provider Adapter Boundary
      │
      ├── BaseDataClient ─────────────► historical series ─► Momentum
      ├── SecurityIdentityProvider ───► current identity / instrument-kind snapshot
      └── FinancialFactsProvider
              ├── quote
              ├── company fundamentals
              └── macro observation contract
                      │
                      ▼
            GrahamInputResolver ◄── override / cache
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
identity/profile snapshot ─► same Analysis Run (never re-resolved for historical viewing)
Analysis Run        ──► versioned deterministic report projection
report projection   ──► concise/details/diagnostic/JSON view
evaluation result   ──► Golden evaluation artifact
```

These stores/artifacts must not be collapsed merely because they can all be serialized. In particular, telemetry describes execution, while an Analysis Run is the durable investor-facing outcome of one requested analysis.

## 7. Golden-Suite architecture (Step 2.5)

Step 2.5 consumes the stable Steps 2.3–2.4 contracts after approved P1 instrument-applicability hardening. The initial [Gate M Review](milestones/v0.2/step-2.5/STEP_2_5_GATE_M_REVIEW.md) required bounded Slice H corrections; the corrected result and later Slice I empirical runner are now accepted, and Slice J supplies the CLI/report boundary pending review.

The production orchestration seam exposes four explicit handlers in `src/orchestrator/analysis_tools.py`: Momentum, Graham Number, Graham growth value, and Free Cash Flow & Earnings Growth. `register_analysis_tools(...)` registers them on the existing `AsyncToolDispatcher` using injected analyzers, resolvers, provider selections, calculation policy, and clock. This keeps deterministic fixture composition and live production composition behind the same tool boundary without import-time registration, a second dispatcher, or a generic strategy framework. Tool argument schemas are derived from the strict Pydantic models in `ANALYSIS_TOOL_ARGUMENT_MODELS`; successful calls retain each strategy's native typed execution result.

```text
Golden Case
   │
   ├── prompt/task
   ├── fixture IDs
   ├── expected strategy/tool behavior
   └── independently verified numeric expectations
   │
   ▼
real orchestration flow
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

Real-local-Ollama evaluation is an empirical mode and remains separate from deterministic regression/CI tests unless explicitly configured. The shared `evaluate` CLI selects one mode, one canonical full-suite or named-case request set, and one explicit local JSON report destination; it does not merge deterministic and empirical scores.

The ≥90% target is a measurement target, not permission to weaken cases until a model passes. Expected native domain outcomes are first-class evidence: a deliberate `input_unavailable` or `not_applicable` result passes only when the case expects its exact observable contract, and the same result fails when success was expected. Infrastructure/fixture failures remain distinct from valid non-success analytical outcomes.

The deterministic runner requires one canonical versioned case catalog and
request-building boundary so a mandatory gate can produce one auditable report.
Test-local per-strategy invocations are supporting evidence, not a substitute for
that complete-suite operation.

### 7.1 SEC foreign-private-issuer seam (Step 2.5A implemented)

The existing SEC adapter supports the reviewed FPI/IFRS slice without creating
a parallel provider architecture:

```text
analysis request + effective as_of
               │
               ▼
immutable request-scoped SEC snapshot
    ├── Company Facts payload
    └── submissions/accession availability evidence
               │
               ▼
latest eligible annual accession / taxonomy regime
               │
       ┌───────┴────────┐
       ▼                ▼
US-GAAP duration    exact IFRS duration
10-K/20-F/40-F      EPS / diluted shares /
                    OCF / physical-PP&E CapEx
       └───────┬────────┘
               ▼
existing provider-neutral facts, provenance, and resolvers
```

All fields in one analysis use the same snapshot. Accounting regime is selected
at the requested historical boundary, not from lifetime namespace presence.
Existing annual-period, availability, currency, duplicate/restatement,
provenance, and exact-concept rules remain authoritative.

Per-share filing values and market quotes cross a separate security-unit gate.
The implemented predicate accepts only affirmative ordinary-share / 1:1 quoted-
unit evidence; unknown and ADR/ADS shapes make quote-dependent comparisons
unavailable without erasing independently supported issuer-level facts.

IFRS BVPS is not in this seam. Company Facts does not preserve the
dimensional ordinary/preference share-class evidence needed to infer common
equity and denominator safely; missing preferred-share evidence is never zero.
The exact approved scope and deferrals are in the
[FPI / IFRS D0 Mapping Record](milestones/v0.2/step-2.5a/SEC_EDGAR_FPI_IFRS_D0_MAPPING_RECORD.md).

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

- Recoverable failures may enter a bounded retry/repair flow.
- Non-recoverable failures halt with structured diagnostics.
- Step 2.6 owns hard execution/time/error caps.
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
- Do not claim a production AAA-yield series until its identity, semantics, availability, and integration are explicitly approved.
- Do not build Step 2.5 evaluator/reporting work during Steps 2.3–2.4.
- Do not build Step 3.1 production persistence/cache during Step 2.3/2.4.
- Do not use operational logger lines as the primary investor-facing result renderer.
- Do not force Momentum and Graham into one generic result object merely for presentation.
- Do not pull Step 3.4 watchlists/Analysis Run persistence into Step 2.3.
- Do not build a daemon, scheduler, proactive-monitoring service, notification system, full-screen TUI, or executive-report generator before the roadmap step that owns it.
- Use `src/data/repositories/` for the planned repository layer.
- Run Ruff, `mypy --strict`, and pytest according to the active milestone plan.
