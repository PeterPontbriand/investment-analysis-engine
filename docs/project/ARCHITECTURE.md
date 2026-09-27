# Investment Analysis Engine Architecture

This document describes the system's current boundaries, data ownership, and execution flow.

## Architectural invariants

1. **Deterministic analysis:** Python performs calculations, validation, data processing, and persistence. The language model selects registered tools and synthesizes results.
2. **Controlled model boundary:** The language model invokes registered tools; it does not directly execute shell/code or access the external network.
3. **Typed boundaries:** Requests, analyzer configurations, results, provider facts, and persisted records use explicit typed contracts.
4. **Heterogeneous strategies:** Strategies keep their own inputs, configuration, policies, calculations, and result types.
5. **Shared analyzer contract:** Current analyzers implement `BaseAnalyzer[ConfigT, ResultT]` and receive an `AnalysisContext`; this common invocation shape does not impose a common financial result model.
6. **Narrow provider capabilities:** Historical prices, financial facts, quotes, identity evidence, and macro observations are distinct capabilities.
7. **Time-bounded provenance:** Resolved inputs retain source, period, availability and retrieval times, transformations, cache/override state, and the requested analysis boundary where applicable.
8. **Presentation without homogenization:** Strategy results retain their native types while sharing investor-facing presentation conventions.
9. **Persistence has a product boundary:** `AnalysisRun` records an analysis outcome. It is separate from trajectory telemetry and market-data storage.
10. **Telemetry is observational:** Telemetry failures do not change business execution semantics.
11. **Historical reports are reproducible:** A stored result is rendered from its persisted evidence without provider access, financial recalculation, or LLM synthesis.

## System structure

```text
                         terminal / caller
                               │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
       direct analysis request      bounded orchestrator flow
                 │                           │
                 └─────────────┬─────────────┘
                               ▼
                   CLI / analysis dispatch
                               │
                 method config + AnalysisContext
                               │
                               ▼
                 BaseAnalyzer[ConfigT, ResultT]
                               │
                   strategy-specific resolver
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
      historical prices   financial facts    identity/profile
      and market data       and quotes           evidence
             └─────────────────┼─────────────────┘
                               ▼
                   typed strategy result
                               │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
         direct presentation      capture adapter → workspace
                                                │
                                                ▼
                                         AnalysisRun store
                                                │
                                                ▼
                                      saved-run presentation
```

Direct output and saved-run output use presentation boundaries. Data providers, calculators, execution capture, and persistence remain separate responsibilities.

## Analyzer contract and execution context

[`BaseAnalyzer[ConfigT, ResultT]`](../../src/analysis/base_analyzer.py) defines the abstract invocation `run_analysis(ticker, config, context) -> result`. Its type variables are unconstrained so each strategy can use an appropriate typed configuration and result.

`AnalysisContext` is a frozen per-run value object:

- `as_of` is the requested point-in-time boundary, or `None` when no boundary was requested.
- `executed_at` is the timezone-aware execution clock captured once for the analysis.
- `effective_as_of` is `as_of` when supplied and otherwise `executed_at`. Analysis inputs must respect this information cutoff.
- `use_cache` controls cache reads and writes used for the run. Cache freshness is judged relative to execution time, separately from the requested historical boundary.
- `instrument_profile` optionally carries the run's identity evidence. Results retain the profile when present, whether or not calculations use it.

The workspace captures `started_at` and `completed_at` separately around its capture callable. Those persistence-envelope timestamps do not replace the analyzer context's `executed_at`.

Current analyzers are:

- **Momentum** — historical-price series and its own window policy, metrics, and `MomentumRun` result.
- **Graham Number** — fundamental facts and quote comparison under its own configuration and `GrahamNumberAnalysis` result.
- **Graham Growth Value** — its own valuation assumptions, inputs, and `GrahamGrowthAnalysis` result.
- **Free Cash Flow & Earnings Growth** — annual company financial facts and its `FCFEarningsGrowthConfig` / `FCFEarningsGrowthResult` types.

The [Analysis Strategy Contributor Guide](ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md) traces these boundaries through an implementation example.

## Data providers and resolution

### Historical prices and financial facts

`BaseDataClient` supplies historical market prices. It does not also own company fundamentals, quotes, or macro data. `FinancialFactsProvider` supplies financial facts through a provider-neutral request boundary. `SecurityIdentityProvider` supplies descriptive identity and instrument-kind evidence independently of numeric facts.

Production adapters have narrow capabilities:

- **SEC EDGAR (`sec_edgar`)** supplies mapped annual financial-statement facts. Supported US-GAAP and IFRS concepts differ by field; unsupported mappings remain unavailable.
- **Massive (`massive`)** supplies selected current TTM EPS and quote facts when explicitly configured.
- **Yahoo Finance (`yfinance`)** supplies current quote comparison and supported instrument metadata. It does not make a historical quote from a one-day price request.

The Graham strategies compose the financial-fact and quote capabilities they need. The FCF growth resolver requires compatible completed annual operating cash flow, capital expenditures, and diluted EPS evidence; its current production resolver uses SEC EDGAR mappings for those fields.

### Input resolution and provenance

Strategy resolvers select inputs that satisfy the strategy's semantic and time-boundary requirements. Resolved values use `ResolvedInput` provenance; derived values retain `ComponentLineage`; resolver actions can be recorded in a `ResolutionTrace`. Missing, invalid, or inapplicable data remains explicit instead of being replaced with zero.

Graham input resolution handles explicit overrides, eligible cached evidence, and configured providers. Calculators consume resolved values and do not perform provider or cache I/O. The FCF annual-series resolver selects compatible contiguous observations under `as_of`, applies horizon policy, and returns typed observations with their input lineage.

### Cache and identity profile

Resolvers own precedence and provider fallback; caches store resolved evidence and apply their eligibility rules. Resolved financial inputs can use in-memory or SQLite-backed cache implementations. A caller's `use_cache` setting governs cache access for the analysis.

`InstrumentProfile` composes descriptive identity and provider-backed instrument-kind evidence without implying that one provider supplied both. `CachedInstrumentProfileResolver` uses `SQLiteInstrumentProfileRepository` when persistence is composed. Identity-anchored records are keyed by profile identity; when a ticker is later associated with a different identity, the older profile remains available for historical records and a new profile is stored. Missing or unsupported metadata remains unknown and does not invalidate otherwise usable financial facts.

Quote-dependent per-share comparisons require compatible filing-share and quoted-share unit evidence. When that compatibility cannot be established, the comparison remains unavailable while independently supported financial results remain usable; the system does not infer a conversion.

## Strategy calculations and presentation

Each analyzer applies its own deterministic rules and returns its own typed result. For example, FCF & Earnings Growth derives free cash flow and free cash flow per diluted share, computes growth metrics, and classifies the historical evidence. Its `PASS`, `FAIL`, or `INDETERMINATE` classification is distinct from the software execution outcome.

Direct commands render results through strategy-specific presenters. Shared helpers in [`src/reporting/presentation.py`](../../src/reporting/presentation.py) provide common labels and formatting, not a universal result schema. Investor output supports concise, details, diagnostics, and JSON views where the strategy exposes them.

Saved-run reporting decodes the stored native evidence and invokes the corresponding presenter. It does not fetch current provider data, rerun calculations, or reinterpret a historical result using current configuration.

The report projection has an explicit version independent of the strategy method and typed result schema. A breaking presentation-contract change requires a new projection version so persisted runs can retain reproducible report semantics.

## Execution capture and persistence

Strategy-specific execution adapters integrate an analyzer with application composition and execution capture. The FCF adapter constructs `AnalysisContext`, invokes the analyzer, and returns `FCFGrowthCapture`. Composition normalizes method-specific captures to `ExecutionCapture` while retaining native evidence.

Common [`workspace.execute()`](../../src/workspace/execution.py) invokes the capture callable, records envelope timestamps, encodes native evidence, builds an [`AnalysisRun`](../../src/workspace/runs.py), and inserts it through the supplied repository. It does not resolve financial inputs or implement strategy calculations. `SQLiteAnalysisRunRepository` persists the complete run envelope; its summaries support bounded listing without decoding every result.

An `AnalysisRun` retains the request and configuration snapshot, strategy identifiers and versions, execution outcome and times, native result evidence, presentation inputs, and instrument profile. Reports and views are projections of this record. Watchlists pair tickers with method-specific selections; user-initiated refresh can execute independent jobs concurrently and persist each result.

## Storage, evaluation, and telemetry

Storage concerns remain distinct:

```text
historical market data ──► market-data repository/cache
resolved financial facts ─► resolved-input cache
instrument identity ─────► instrument-profile repository
analysis result ─────────► AnalysisRun repository ─► saved-run report
trajectory events ───────► telemetry sink
evaluation fixtures ─────► deterministic evaluation result
```

Golden evaluation fixtures contain reproducible evidence and expected behavior. Deterministic evaluation exercises the case catalog, analyzers, scoring, and report serialization without live model calls. Real local-model evaluation is a separate empirical mode.

Operational logging provides readable runtime diagnostics. Investor presentation renders analysis outcomes. `TrajectoryRecorder` emits structured execution evidence to JSONL or SQLite sinks, sanitizes telemetry, and fails open when telemetry storage fails. Telemetry is not benchmark ground truth or an alternate source of financial data.

## Structured output and reliability

The orchestrator uses native provider schema constraints when available, Pydantic validation at application boundaries, and configured schema fallback behavior when native constraints are unavailable or unknown. Legacy compatibility parsing is retained only where the application still requires it.

`ReliabilityLimits` bounds orchestration work units, retries, schema violations, and elapsed time for the full run and its individual operations. Monotonic deadlines determine which limit is reached first. Asynchronous work is cooperatively cancelled; synchronous handlers still need their own I/O timeouts and idempotency safeguards. Telemetry failures fail open.

## Module boundaries

- `src/analysis/base_analyzer.py` — generic analyzer interface and `AnalysisContext`.
- `src/analysis/strategy/` — strategy-specific analyzers, configs, resolvers, calculations, and result models.
- `src/data/` — provider contracts/adapters, financial provenance, caches, identity profiles, and repositories.
- `src/workspace/` — validated selections, strategy execution adapters, run capture, and common workspace execution.
- `src/reporting/` — direct strategy presenters and saved-run projections.
- `src/orchestrator/` — LLM tool selection and invocation of typed analysis handlers.

SQLite access stays behind repository interfaces in `src/data/repositories/`. `SQLiteDatabase` owns lazy connection scopes and transactions; repositories borrow a ready database and do not migrate or close it implicitly. Readiness checks initialize a missing or verified empty database; existing schemas require explicit operator upgrades. Administrative inspection is read-only. See [Local Database Operations](../user/DATABASE.md) for usage and recovery details.
