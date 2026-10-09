# Investment Analysis Engine Architecture

## 1. Purpose and how to read this document

This document explains system boundaries, data ownership, and execution flow. Content describes current behavior unless it appears in [*Planned work*](#12-planned-work), which is the only place a not-yet-built item is described.

**Related roadmap:** [MASTER_PLAN.md](MASTER_PLAN.md)<br/>
**Active implementation detail:** [milestones/v0.2/IMPLEMENTATION_PLAN.md](milestones/v0.2/IMPLEMENTATION_PLAN.md)<br/>
**Rationale:** [DISCOVERY_WORKBOOK.md](DISCOVERY_WORKBOOK.md)<br/>
**Adding a strategy:** [ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md](ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md)<br/>

For work-package sequencing and status, see the [milestone table](milestones/v0.2/IMPLEMENTATION_PLAN.md#sequence-and-status).

---

## 2. Architectural invariants

- **LLM orchestration, deterministic execution:** The LLM plans/selects tools and synthesizes results; Python performs calculations, validation, data processing, and persistence.
- **Typed boundaries:** Tool/analyzer/data inputs and outputs are explicitly typed at application boundaries.
- **Heterogeneous strategies:** Different financial strategies may have different config/data/result shapes. The architecture must not impose one strategy's data or result shape on other strategies.
- **No speculative strategy framework:** Reuse the existing `BaseAnalyzer` and current tool-dispatch flow unless implementation proves a new abstraction is necessary.
- **Provider isolation:** Historical-price access stays behind its own narrow boundary (`BaseDataClient`/`MarketDataProvider`); financial facts use a dedicated provider/resolution boundary rather than enlarging a price-history-shaped interface.
- **Historical prices, quotes, fundamentals, and macro series are distinct capabilities:** A composed valuation façade may coordinate narrow providers, but no upstream service is assumed to supply every capability.
- **Evaluation is not persistence:** Golden fixtures, evaluation results, trajectory telemetry, and production market-data storage are separate concerns.
- **Local-LLM boundary:** The LLM cannot directly execute shell/code or access the external network. Registered data tools may perform controlled provider access.
- **Telemetry is observational:** Telemetry failures must not change business execution semantics.
- **Light Mode first:** Core useful analysis must remain viable under the documented [Light Mode](../user/GLOSSARY.md#light-mode) workflow.
- **Method-explicit financial semantics:** Distinct analysis methods retain explicit names, inputs, typed results, and limitations.
- **Time-bounded provenance:** Resolved inputs preserve source, reporting/observation and availability dates, transformations, cache/override state, and requested analysis `as_of`.
- **Presentation without homogenization:** Analysis strategies use a coherent investor-facing visual grammar while retaining their own typed result models.
- **Operational logs are not product UI:** User results are rendered by a presentation boundary; logs and trajectory telemetry remain diagnostics/execution evidence.
- **Analysis Run is a product-domain record:** persisted requested analysis/config/result/provenance history is kept separate from telemetry `RunContext`; reports/views render that record.
- **Bounded agentic behavior:** User-initiated refresh may execute independent analysis jobs concurrently. Daemons, unattended scheduling, proactive monitoring, and notifications remain later autonomy work.
- **Deterministic, versioned investor-report projection:** A stored Analysis Run is projected into an investor report without provider access, LLM synthesis, financial recalculation, or current-state enrichment. The projection contract has its own explicit version, independent of strategy method and result-schema versions.
- **One clock per run:** Time-dependent decisions use injected clocks derived from `executed_at`; see [*Time and the analysis boundary*](#5-time-and-the-analysis-boundary).

---

## 3. System overview

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
                  selected analysis method
                              │
                    typed input resolution
                              │
       ┌──────────────────────┼──────────────────────┐
       ▼                      ▼                      ▼
 historical series     financial facts        quotes / macro data
       │                      │                      │
 BaseDataClient /      FinancialFactsProvider / narrow providers
 MarketDataProvider
       └──────────────────────┬──────────────────────┘
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
                                             │
                                             ▼
                                later report/view formats
```

`BaseAnalyzer` remains the existing common analyzer abstraction where applicable. The diagram does **not** imply a new strategy registry, plugin system, factory hierarchy, or unified strategy-result model.

The presentation boundary is intentionally downstream of deterministic calculation and provenance. Persisted Analysis Runs are rendered through the same presentation contract rather than recalculated merely to display historical results.

---

## 4. Composition roots and dependency wiring

A composition root is where a run's concrete dependencies — provider, cache, resolver, clock, and (when persisting) the durable instrument-profile cache and Analysis Run repository — are constructed and wired together before an analyzer ever runs. The current composition roots are each strategy's `src/strategies/<strategy>/cli.py` (its direct command, added to the application by `src/cli.py` through the CLI tier) and `src/cli_workspace.py` (workspace/watchlist commands); the latter's `_execute_*` functions perform per-job composition and read `executed_at`, including for each job a concurrent watchlist refresh runs. `src/workspace/refresh.py` supplies its own clock only to timestamp each job's persisted `AnalysisRun` capture — it never composes a job's dependencies and never supplies the `executed_at` an analysis runs against. `src/cli_composition.py` and `src/cli_support.py` hold the factory helpers both composition roots draw on (provider/resolver builders, production client/cache construction) rather than acting as composition roots themselves. Composition is not a strategy's own concern: an analyzer and its resolver receive already-composed dependencies through their constructors and never construct or close them.

Every composition root reads `executed_at` exactly once per analysis it runs, via `utc_now()` — a watchlist refresh takes a separate reading for each job. That single reading threads through everything the analysis touches; see [*Time and the analysis boundary*](#5-time-and-the-analysis-boundary) for the resulting clock model. `maybe_save_run` (`src/cli_run_support.py`) is the one place shared by all four direct commands that decides, from `--save-run`, whether a run's capture ever reaches persistence.

For the concrete sequence a request follows from composition through to a rendered or saved result, see the [Analysis Strategy Contributor Guide](ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md)'s execution trace rather than a second copy of it here.

---

## 5. Time and the analysis boundary

Every time-dependent decision in the data layer ("is this cached value still fresh?", "had this
filing been published yet?") is made against one of three well-defined instants, never against
an ad-hoc read of the wall clock. The helpers and the tolerance constant live in
`src/core/clock.py`.

### The three instants

- **`executed_at`: when the run happens.** The composition root reads the wall clock once, via
  `utc_now()`, at the start of each analysis (a watchlist refresh takes a separate reading for
  each analysis it runs) and threads the value down through `AnalysisContext`. It is never
  re-read mid-run, so every decision within one analysis sees the same instant.

- **`as_of`: the date the analysis is about, if the user asked for one.** Supplied with
  `--as-of`, it asks for the analysis as it could have been performed at that earlier point: only
  information that was publicly available by then may be used, even though the run itself happens
  later. When no `--as-of` is given, `as_of` is `None`, meaning "as of right now": a *live* run.
  Requests carry `as_of` down unchanged, `None` included, because `as_of is None` is the only way
  the data layer can tell a live run from a historical one, and the two behave differently:
  - live runs tolerate frozen-clock skew and historical runs don't (see below);
  - requests for current data keep stable cache keys across live runs;
  - historical runs omit current quotes rather than compare a past valuation with today's price.

  Never fill in a missing `as_of` with a substitute value before passing it on. Code that needs a
  concrete instant uses the analysis boundary instead.

- **The analysis boundary: the instant eligibility is judged against.** It answers "was this
  information knowable by then?" For a historical run it is `as_of`. A live run has no requested
  date, so its boundary is `executed_at`, the latest instant the run can know anything about.
  Compute it with `effective_as_of(as_of, executed_at)` from `src/core/clock.py`, which
  `AnalysisContext.effective_as_of` also uses. Don't re-derive it inline, so there is exactly one
  definition. Because the boundary is always a concrete instant, it cannot tell you whether a run
  is live; check `as_of is None` for that.

### Reading the wall clock

`utc_now()` is the only permitted read of the real wall clock in `src/`. The single exception is
log-rotation timing in `src/utils/logger_util.py`. A structural conformance test in
`tests/analysis/test_base_analyzer_conformance.py` enforces this. Everything else receives its
clock by injection, and which clock depends on what it is used for:

- A **decision clock** determines an outcome: cache or TTL freshness, a quality or eligibility
  check. It is a required constructor parameter with no default, and composition roots pass
  `lambda: executed_at`. A default would let a forgotten wire silently fall back to the wall
  clock, making one decision in a run use a different "now" from every other.
- An **event clock** only records when something happened: a row written, a provider response
  received. It defaults to `utc_now` and is injected only in tests.

### Which instant to compare against

- Freshness and TTL ("is this still recent enough?") compare against `executed_at`.
- Point-in-time eligibility ("was this knowable by then?") compares against the analysis
  boundary.

### Frozen-clock skew

In a live run, `executed_at` is fixed at the start, but provider timestamps (a quote's retrieval
time, a market observation, a fact's availability time) are stamped later, when each fetch
completes. A timestamp slightly after `executed_at` is therefore normal in a live run, not a data
problem. The timestamp-versus-boundary checks in `src/data/quality.py` (`evaluate_freshness`,
the single owner of these comparisons in the resolver) and the retrieval-age check in
`src/data/financial/quote_freshness.py` accept up to `FROZEN_CLOCK_SKEW_TOLERANCE` of it.

A historical run accepts none: a timestamp after an explicitly requested `as_of` is look-ahead,
and must fail. The tolerance is ten minutes. A timezone misconfiguration, such as local time
mistaken for UTC, produces an error of at least 30 minutes for any real-world UTC offset, so the
tolerance cannot hide that kind of defect.

---

## 6. Analysis strategies: the boundary

Every current analyzer implements `BaseAnalyzer[ConfigT, ResultT]` and shares the same `run_analysis(ticker, config, context)` signature — that shared signature is the full extent of what strategies share by contract. Each strategy's own execution adapter composes and invokes it differently, as the [Analysis Strategy Contributor Guide](ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md) documents. What a strategy owns:

- its own configuration/policy model;
- its own input resolution (which provider capabilities it needs, and how it resolves them);
- its own deterministic calculation;
- its own typed result and metrics.

What every strategy shares instead of rebuilding: `BaseAnalyzer` and `AnalysisContext`, the provider/cache contracts and `ResolvedInput`/`ResolutionTrace` provenance model, workspace execution and Analysis Run persistence, and the concise/details/diagnostics/JSON presentation grammar. `MetricResult` is a per-metric outcome convention some strategies use, not a type every strategy is required to return. When a strategy needs something none of these shared layers cover, it extends its own layer first; nothing here is a reason to build a second, strategy-specific version of shared infrastructure.

No two strategies share a strategy-specific base beyond `BaseAnalyzer` itself: each owns its config, resolver, calculation, and result type independently, and a resolver pattern used by one strategy — such as evidence truncated to `effective_as_of` and recorded as a `ResolutionTrace` — is a convention other strategies may follow, not a shared class they inherit.

For which strategies exist today and what each one computes, see the [user strategy guides](../user/strategies/README.md). For how to add a new one, trace an existing strategy end to end in the [Analysis Strategy Contributor Guide](ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md) rather than here.

---

## 7. Data providers and input resolution

The project distinguishes the financial execution flow:

```text
External Provider
      │
      ▼
Provider Adapter Boundary
      │
      ├── BaseDataClient / MarketDataProvider ──► historical series ──► Momentum
      ├── SecurityIdentityProvider ──────────────► identity / instrument-kind snapshot
      │                                                                   │
      │                                                                   ▼
      │                                    durable instrument-profile cache (optional)
      │                                                                   │
      └── FinancialFactsProvider                                          │
              ├── quote                                                   │
              ├── company fundamentals                                    │
              └── macro observation contract                              │
                      │                                                   │
        ┌─────────────┴─────────────┐                                     │
        ▼                           ▼                                     │
method-specific Graham        FCF annual-series                           │
resolver ◄── override/cache   resolver ◄── cache                          │
        │                           │                                     │
        ▼                           ▼                                     │
  resolved inputs             resolved inputs                             │
        │                           │                                     │
        ▼                           ▼                                     │
deterministic Graham method   deterministic FCF method                    │
        │                           │                                     │
        └─────────────┬─────────────┘                                     │
                       ▼                                                  │
              typed strategy result ◄─────────────────────────────────────┘
                       │
                       ▼
             presentation boundary
```

### `BaseDataClient` and `MarketDataProvider`
`BaseDataClient` is the original concrete provider boundary for historical market prices; it remains price-history focused rather than becoming the owner of fundamentals, valuation quotes, macro series, and cache policy. `MarketDataProvider` (`src/data/market_data.py`) is a narrower structural protocol — `provider_id` plus `fetch_historical_data` — and is the boundary Momentum's resolver actually consumes. `MomentumAnalyzer` takes one required `MarketDataProvider` and the series start date at construction. `BaseDataClient` satisfies the protocol structurally through its `fetch_historical_data` method, so a data client, the cached historical client, or a fixture provider is passed directly with no adapter.

Current quote retrieval is a separate valuation capability; it is not implemented as a one-day historical request.

### `FinancialFactsProvider` boundary
A dedicated provider-neutral financial-fact boundary supplies or composes the quote, company-fundamental, and annual-series capabilities the two Graham methods and FCF & Earnings Growth require. The contract can represent macro observations, but the production CLI does not currently claim an approved live AAA-yield series.

Implemented production adapters are deliberately narrow:

- **SEC EDGAR (`sec_edgar`)** — completed annual duration facts from `10-K`, `10-K/A`, `20-F`, `20-F/A`, `40-F`, and `40-F/A`. Existing exact US-GAAP mappings cover diluted EPS, diluted weighted-average shares, operating cash flow, and CapEx. Exact IFRS mappings cover diluted EPS, diluted weighted-average shares, operating cash flow, and physical-PP&E CapEx. Fiscal-year-end balance-sheet components and conservative BVPS derivation remain US-GAAP-only; IFRS BVPS and preferred-zero inference are unsupported.
- **Massive (`massive`)** — current TTM diluted EPS and current price when Massive is explicitly selected. Live use requires `MASSIVE_API_KEY`; current-only facts do not masquerade as historical evidence.
- **Yahoo Finance (`yfinance`)** — narrow current-price financial-facts adapter used for quote comparison on the Graham analyses using SEC EDGAR financial facts. It does not claim historical quote support through the financial-facts contract.

The Graham Number's default SEC route pairs SEC financial facts with Yahoo current quote comparison. Its explicit Massive route is deliberately limited to Massive TTM EPS plus a BVPS override and may use a Massive quote. SEC-backed Growth defaults to three-year-average EPS plus Yahoo quote; explicitly selecting Massive uses its supported TTM EPS/current-price data. Unsupported provider/basis combinations are rejected before provider work.

### Security identity and instrument applicability
`SecurityIdentityProvider` is a narrow optional capability beside, not inside, numeric financial facts. The identity capability returns an immutable current descriptive snapshot with normalized ticker, optional instrument name/listing venue/issuer and instrument identifiers, provider identity, and timezone-aware `resolved_at`. SEC retains current ticker-title/CIK evidence from its ticker mapping; Yahoo retains supported instrument metadata, including non-company names where available.

The instrument-kind capability preserves that one-provider snapshot and adds a separate immutable `InstrumentKindEvidence` value with normalized kind, retained raw provider classification, provider identity, and resolution time. A composed `InstrumentProfile` can therefore retain SEC identity/CIK and Yahoo kind evidence without pretending that one provider supplied both. Kind is provider-backed metadata: it is never inferred from a ticker, name, missing financial facts, or another strategy's success. The exact field mappings and schema consequences are recorded in the [instrument applicability mapping record](milestones/v0.2/step-2.5/STEP_2_5_P1_INSTRUMENT_APPLICABILITY_MAPPING_RECORD.md).

An ordered, explicitly injected profile resolver selects the best available descriptive identity by provider precedence and obtains kind evidence independently. Each provider/capability is consulted at most once per run, and one YFinance metadata fetch is shared by its identity and kind capabilities. Missing metadata, unsupported capability, and lookup failure remain unknown and fail open. They cannot invalidate or downgrade otherwise usable financial evidence. Affirmative kind evidence is different from lookup failure: a provider-confirmed ETF establishes that both Graham methods and the existing company-level FCF Growth strategy are `not_applicable`, while Momentum remains applicable. This strategy-specific applicability decision does not change any financial formula and does not silently select a future ETF strategy.

A present name uses `Instrument Name (TICKER) — Analysis` in successful, unsuccessful, and `not_applicable` presentations; whitespace is normalized without changing official capitalization or punctuation. Ordinary unavailability/provider failures do not claim the ticker is invalid without affirmative provider evidence. Current metadata does not prove the identity or instrument kind that applied at a historical analysis `as_of`.

### Input resolution: override, cache, provider, unavailable

Each required field resolves independently through one general precedence:

```text
explicit override → valid cache → configured provider → unavailable
```

Calculators receive resolved values and do not perform I/O. The resolver enforces requested `as_of` boundaries and preserves typed provenance.

Today, `GrahamNumberInputResolver` and `GrahamGrowthInputResolver` are the resolvers that use this pattern by directly inheriting the shared `InputResolver` constructor and field-resolution behavior; each lives in its strategy package's `calculation.py`, assembles only its own method inputs, and borrows the provider, cache, and clock supplied by composition without constructing or closing them. Method-input assembly adds only method-semantic annotations that are justified by retained evidence, such as fiscal-year-end basis on derived BVPS.

### Resolved input and provenance models
Typed records preserve value, units/currency, source kind, provider field/series, reporting/observation period, availability/filing date where supplied, analysis `as_of`, retrieval time, transformations/derived lineage, and override/cache state.

### Fixture-backed data capabilities
Fixture-backed data capabilities prove the historical-price and financial-fact contracts:
- deterministic;
- historical data for Momentum;
- quote, EPS history/TTM EPS, BVPS facts/components, and AAA-yield observations for Graham;
- annual operating-cash-flow, CapEx, and diluted-EPS series for FCF & Earnings Growth;
- override/cache/provider/unavailable resolution branches;
- realistic reporting, availability, `as_of`, and retrieval metadata;
- explicit failure when data is absent;
- no live network fallback.

Fixture support for a capability does not claim that the same capability exists in a production adapter. Golden cases reuse this same foundation.

### SEC foreign-private-issuer seam

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

The Graham services complete missing unit evidence after financial input
resolution, inside the existing request-scoped SEC snapshot. The optional SEC
capability verifies original source accessions and current annual filing class
evidence through a bounded Inline XBRL reader. It supports the reviewed domestic
US-GAAP single-common-class mapping for current requests; unsupported evidence
produces a structured absence. Derived shares and inferred preferred-share
guards retain typed source lineage through the existing financial cache format.
This seam adds no durable evidence cache and requires no database migration. Shared comparison
evaluation supplies both the legacy percentage and structured status/reason;
the Graham presentation schema exposes sanitized evidence and provenance.

IFRS BVPS is not in this seam. Company Facts does not preserve the
dimensional ordinary/preference share-class evidence needed to infer common
equity and denominator safely; missing preferred-share evidence is never zero.
The exact approved scope and deferrals are in the
[FPI / IFRS D0 Mapping Record](milestones/v0.2/step-2.5a/SEC_EDGAR_FPI_IFRS_D0_MAPPING_RECORD.md).

---

## 8. Persistence

The project separately distinguishes persistence and artifacts:

```text
Golden fixture data ──► fixture adapter ──► deterministic/evaluation execution
trajectory events   ──► telemetry sink (JSONL / SQLite)
production data     ──► SQLite/cache repositories
analysis result     ──► Analysis Run repository
identity/profile snapshot ─► same Analysis Run (never re-resolved for historical viewing)
Analysis Run        ──► versioned deterministic report projection
report projection   ──► concise/details/diagnostic/JSON view
evaluation result   ──► Golden evaluation artifact
```

These stores/artifacts must not be collapsed merely because they can all be serialized. In particular, telemetry describes execution, while an Analysis Run is the durable investor-facing outcome of one requested analysis.

### Resolved-input cache seam
A narrow in-memory/fixture-backed `get`/`put` seam proves precedence, temporal eligibility, and provenance. The resolver—not the cache—owns provider fallback. Durable SQLite-backed caching is implemented; see `SQLiteResolvedInputCache` below.

### Typed SQLite repositories and administrative inspection

`SQLiteDatabase` owns lazy connection scopes and explicit transactions. File-backed
connections verify WAL mode, foreign keys, and the configured busy timeout;
SQLite serializes competing writers. `read()` provides a query-only snapshot.
In-memory databases support sequential scopes only. Repositories borrow an
already-migrated database and do not migrate or close it implicitly.

The first analysis that needs local storage automatically initializes a missing
or verified empty SQLite database. Existing databases require explicit upgrades;
readiness failures identify the target and next action. See
[Local Database Operations](../user/DATABASE.md) for inspection, upgrades and recovery.

| Repository | Public access | Semantics |
| :--- | :--- | :--- |
| `SQLiteMarketDataRepository` | `put`, `get`, `list_keys` | Exact historical request snapshots preserve frame structure/precision, context, and cache/retrieval timestamps. `get` returns the validated stored snapshot or `None` for a miss. |
| `SQLiteResolvedInputCache` | `put`, `get`, `get_series`, `list_keys`, `inspect`, `ttl` | Normal retrieval applies existing TTL and historical availability rules. `inspect` returns the validated stored entry irrespective of eligibility, preserving original provenance and timestamps; only an absent key returns `None`. |
| `SQLiteInstrumentProfileRepository` | `get`, `get_by_id`, `put` | `put` mints, updates in place, or supersedes-and-mints a profile per the identity-anchor/ticker-reuse rule, atomically within one transaction. Only identity-anchored resolutions are ever written; a superseded row is retained, never deleted. |
| `SQLiteAnalysisRunRepository` | `insert`, `get`, `list` | Runs are immutable and append-only: `insert` is the only write, a duplicate `analysis_run_id` conflicts, and there is no update or delete. `get` decodes the full envelope and cross-checks it against its own indexed relational columns; `list` reads only those indexed summary columns, so a corrupt full envelope elsewhere cannot break listing. |
| `SQLiteWatchlistRepository` | `create`, `get`, `list`, `summary`, `rename`, `delete`, `add_entries`, `remove_entry`, `remove_entries_for_ticker`, `remove_entries_for_method` | Each public method is one short transaction; nothing is left partially written on failure. A watchlist holds one ordered, contiguous list of entries — every removal renumbers the survivors from zero rather than leaving a gap. `create`/`rename`/lookup/removal raise typed conflict/not-found errors rather than leaking SQLAlchemy/SQLite exceptions. `delete`, `rename`, `summary` and the removal methods never decode a stored entry, so they work on a watchlist holding an entry an earlier version saved; `delete` returns the decoded watchlist only when every entry can be read. |
| `SQLiteTrajectoryRepository` | `record`, `read_trajectory` | Immutable atomic events; identical event-ID retries are no-ops, conflicts raise, and readback returns typed events in sequence order with gaps preserved. A missing run returns an empty list. |

Both `list_keys` methods require an explicit positive integer `limit` and accept
a nonnegative integer `offset` (default zero); booleans are rejected. They select
only key columns, validate stored keys and encoding versions, and return typed
tuples ordered by canonical stored identity. Each page uses one snapshot;
separate pages across concurrent writes do not form a frozen database view.
Empty pages return empty tuples. Malformed selected data raises explicitly.

Inspection is read-only administrative access: it performs no provider calls,
refresh, deletion, financial recalculation, or freshness-policy change. Normal
financial input resolution continues through `get` / `get_series`; the existing
cache protocols do not acquire these SQLite-specific inspection methods.

`SQLiteTrajectorySink` and the public `read_trajectory(database, run_id)` function
keep stable signatures and import paths, delegating to the repository underneath.
The sink retains flush/close synchronization and optional database disposal;
by default, closing it leaves the borrowed database open. Repository errors
propagate; the recorder retains fail-open handling. Event encoding and readback
validation preserve the existing contract, including the readback encoding
check without adding a new write-time encoding policy.

### Durable instrument profiles

`SQLiteInstrumentProfileRepository` persists composed identity/kind evidence keyed by a minted `profile_id`, not by ticker: only a resolution that yields a provider-verified identity anchor (`SecurityIdentity.issuer_identifier`) becomes durable, so a ticker that never earns an anchor keeps resolving live on every request, exactly as the request-scoped composer above does unwrapped. `CachedInstrumentProfileResolver` layers freshness/TTL/refresh over that repository: a fresh durable profile is reused without a provider call; a stale or missing one refreshes live. When a refresh's anchor disagrees with the stored one — a **ticker reuse**, such as delisting and relisting — the prior row is superseded (retained, never deleted or overwritten) and a new profile is minted; the resolver serializes this decision per ticker so concurrent callers (watchlist refresh's worker pool) cannot mint two competing profiles for the same ticker. Provider precedence and disagreement handling remain entirely owned by the request-scoped composer described above; the durable layer adds only persistence, freshness and the identity/ticker-reuse rule on top of it, matching the "Time-bounded provenance" invariant (see [*Architectural invariants*](#2-architectural-invariants)). See the [P2-Profiles contract](milestones/v0.2/p2-profiles/P2_PROFILES_CONTRACT_AND_SLICE_PLAN.md) for the full identity-key, precedence, freshness and historical-snapshot design.

Every production instrument-profile composition site (Momentum's direct/refresh paths, and the Graham Number/Growth/FCF Growth shared composition helper, covering both direct commands and watchlist refresh) resolves through this durable cache wherever a database is already open for another reason; a genuinely storage-free CLI invocation (no `--save-run`, no refresh) remains live-only rather than opening a database solely to populate the cache.

An `AnalysisRun`'s persisted `instrument_profile` is the immutable value captured at execution time regardless of whether it came from a live call or the durable cache; a later ticker-reuse supersession never relabels an already-persisted run, since replay (see [*`AnalysisRun`*](#analysisrun) below) reads only that stored snapshot and never the durable cache's current state.

### `AnalysisRun`
A durable investor-domain record of one requested analysis. It owns an `analysis_run_id`, ticker, analysis/method, requested `as_of`, configuration snapshot, status, typed result payload, resolved-input provenance, warnings, timestamps, calculation/version identifiers, and the nullable security identity/instrument-profile snapshot used by that completed run (including provider and `resolved_at`). It may link to execution/trajectory identity but must not overload telemetry `RunContext`.

A report is a rendering of an Analysis Run, not a second canonical result object. Viewing an old run must use its persisted identity snapshot rather than re-resolving the ticker and silently relabeling history after ticker reuse.

The investor-report boundary is a deterministic, versioned projection. Given the same persisted Analysis Run, projection version, presentation mode, and explicit locale/format options, it must produce the same semantic report without provider calls, LLM calls, financial recalculation, mutable cache reads, or wall-clock-dependent enrichment. The report exposes its projection version separately from the run's calculation method version and typed result-schema version. A breaking change to report structure or field meaning requires a new projection version; historical projection versions remain reproducible or require an explicit, auditable migration rather than being silently reinterpreted.

### Watchlist / refresh workspace
Named watchlists hold tickers and supported requested analyses. A user-initiated refresh may execute independent ticker/analysis jobs concurrently and persist each outcome as it finishes. No daemon, scheduler, proactive monitoring, or notification service is implied.

### Database readiness and explicit maintenance

The [fresh database readiness contract](milestones/v0.2/step-3.3a/STEP_3_3A_CONTRACT_AND_SLICE_PLAN.md)
is implemented by `src/data/repositories/readiness.py`. CLI cache composition
checks required persistence before use and initializes only missing or verified
empty storage through bundled Alembic migrations. Existing schemas require
explicit operator upgrades. Repositories remain lazy borrowers; analyzers own no
schema management. `readiness_lock.py` coordinates automatic, explicit and manual
migration owners through a persistent OS-locked sidecar, followed by an authoritative
recheck, transactional DDL and revision/structure verification before commit.

`inspect_database()` uses a read-only consistent snapshot without initialization;
`upgrade_database()` explicitly migrates only fresh or supported compatible
storage. The hidden `src/cli_database.py` maintenance group exposes these through
`db status` and `db upgrade`, with target overrides and versioned JSON reports.
Typed sanitized errors preserve stable reason categories and analysis envelopes.
Optional telemetry neither initializes storage nor controls business execution;
financial cache bypass and storage-free help/imports avoid opening that cache.
The migration bundle currently comprises `0001_persistence`, `0002_research_workspace`,
`0003_watchlist_entries`, `0004_instrument_profiles`, and `0005_remove_cancelled_outcome`; older-schema support
is verified with synthetic history. See [Local Database Operations](../user/DATABASE.md)
for target selection, error recovery and installation/platform limits.

---

## 9. Presentation and reports

### Investor-facing result presentation
A narrow presentation seam maps each strategy's typed outputs (see [*Analysis strategies: the boundary*](#6-analysis-strategies-the-boundary)) into a common investor-facing grammar without altering their domain models. The default view is concise and result-first; details expose financial provenance; diagnostics expose resolution mechanics; JSON exposes each strategy's stable versioned machine-readable contract. Material overrides and warnings remain visible. For the identity-name formatting rule this presentation applies (`Instrument Name (TICKER) — Analysis`), see [*Security identity and instrument applicability*](#security-identity-and-instrument-applicability).

Each JSON presentation exposes one explicit nullable `security_identity` snapshot. Identity is presentation metadata: each strategy's presentation `schema_version` bumps when identity or other presentation-only content changes, while its typed result's `result_schema_version` bumps only when the calculation result itself changes. The two version numbers are independent and are not expected to stay in step with each other.

Each strategy's concise view uses investor-facing wording specific to its own method — see the [user strategy guides](../user/strategies/README.md) for what each one says and why; the presentation seam does not impose shared wording across strategies. Successful concise output omits redundant `Status: ok` and `As of: current`; historical requests surface the `as_of` boundary in the heading. All required-input/provider/ticker failures pass through the typed presentation boundary, and every calculation status has an exhaustive plain-English investor label.

---

## 10. Orchestration and evaluation

### Structured-output boundary

Structured-output enforcement uses layered defenses:

1. use native Ollama/provider schema constraints when capability is confirmed;
2. retain Pydantic validation at the application boundary;
3. use the configured prompt-based schema fallback when native capability is unavailable or unknown;
4. retain legacy compatibility parsing only as the final fallback where required.

Do not rewrite the runtime around a model-specific assumption merely to make one model pass.

### Golden-Suite architecture

The production orchestration seam gives each strategy its own dependency class and handler in its `tool.py` under `src/strategies/` (see [*Analysis strategies: the boundary*](#6-analysis-strategies-the-boundary)); the handler is built from that dependency class and a shared `ToolRuntime` (`src/orchestrator/tool_runtime.py`) that carries only the injected clock and optional profile resolver. The composition root, `src/strategy_wiring.py`, declares one frozen descriptor per strategy (identity, tool, arguments model, description and a typed behavior bundle) and builds read-only indexes from that closed tuple. `register_analysis_tools(dispatcher, handlers)` in `src/orchestrator/analysis_tools.py` registers an injected mapping from tool to bound handler on the existing `AsyncToolDispatcher`, and rejects the mapping unless it matches `ToolName` in both directions. The caller builds the mapping with `bind_handlers(...)` from each strategy's injected analyzers, provider selections, calculation policy and the runtime. This keeps deterministic fixture composition and live production composition behind the same tool boundary without import-time registration, a second dispatcher, or a generic strategy framework. The tool names are the `ToolName` enum in `src/orchestrator/tool_names.py`. Each strategy's strict Pydantic arguments model lives in its `tool.py` and subclasses `AnalysisToolArguments` (`src/orchestrator/analysis_tool_arguments.py`). Tool argument schemas are read from each descriptor's `tool_arguments`; an input that matches no declared strategy raises `UndeclaredStrategyError` (`src/core/strategy_errors.py`) rather than falling to a default. Successful calls retain each strategy's native typed execution result.

Deterministic fixture composition follows the same shape. A Golden case selects fixtures by identifier only, each identifier defined in the fixture module of its evidence. The generic `src/evaluation/composition.py` builds one cross-strategy context (`src/evaluation/fixture_context.py`) and asks the evaluation tier, the closed tuple `EVALUATION_STRATEGIES` in `src/evaluation/strategy_fixtures.py`, for each declared strategy's dependency class, fixture requirement and declared fixture identifiers (the supported identifier set is derived from the entries). Each strategy states both in its package's `evaluation.py` (the two Graham strategies share `src/strategies/_graham/evaluation.py`), and the tier pairs them with the strategy's core bundle by dependency type; a declared tool with no entry raises `UndeclaredStrategyError`. Each case module under `src/evaluation/cases/` is single-strategy, named for its strategy package, and holds the reviewed production arguments beside its cases; `src/evaluation/catalog.py` fixes the case order and suite versions and reads the arguments from those modules.

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

---

## 11. Reliability, logging and telemetry

### `TrajectoryEvent` / `TrajectoryRecorder` / `TrajectorySink`
Structured telemetry supports JSONL (the default) and SQLite sinks. `SQLiteTrajectorySink` delegates event persistence to `SQLiteTrajectoryRepository`, retaining synchronous locking and database ownership. The recorder owns sanitization and fail-open handling.

Telemetry records observable execution evidence and does not provide benchmark ground truth.

### Logging and telemetry boundary

Operational logging, investor presentation, and trajectory telemetry remain separate:

```text
Agent Runtime
   │
   ├── typed analysis result ─► investor presenter ─► terminal/run view
   ├── operational logging ───► human-readable execution diagnostics
   │
   └── trajectory telemetry ──► machine-readable execution evidence
                                ├── JSONL
                                └── SQLite
```

Telemetry may capture observable provider/model metadata, prompts/completions, tool arguments/results, latency, and exposed token metrics subject to retention/redaction policy.

Private model reasoning is never reconstructed.

### Failure and reliability boundary

- Recoverable failures may enter a bounded retry/repair flow.
- Non-recoverable failures halt with structured diagnostics.
- Hard execution/time/error caps are enforced through one immutable
  `ReliabilityLimits` value per orchestration run. The default caps are 10
  planning steps, 3 transient retries, 4 consecutive schema violations, 300
  seconds overall, 180 seconds per step, 120 seconds per LLM call, and 60
  seconds per tool call; terminal diagnostics retain 5 sanitized recent-event
  summaries.
- A breached cap returns `ReliabilityFailure` on the terminal
  `AgentStepResult`. Its stable reason and `run_id` cross the consumer boundary;
  the internal circuit-trip exception does not.
- Overall, step, and operation deadlines use monotonic time, and the earliest
  applicable deadline determines the reason. No new work begins after a trip.
- Asynchronous work is cooperatively cancelled. Synchronous tool handlers run
  off the event-loop thread, but Python cannot safely terminate arbitrary
  running thread work; a timeout therefore reports unconfirmed cancellation,
  and handlers still require their own I/O timeouts and idempotency safeguards.
- The configured limits are authoritative; runtime documents must not invent a separate fixed turn limit.
- Telemetry sink failures fail open.

---

## 12. Planned work

- **ETF aggregate FCF** (P2-ETF, deferred beyond Step 3.6): remains planned. The strategy will own its holdings-effective-date, weighting, cash/derivative, currency, missing/stale constituent, coverage, rebalancing, and `as_of` semantics plus native typed configuration/result/tool identity. It may reuse company-level calculations for constituents but must not add ETF branches to or redefine the existing company-level FCF Growth strategy. Company-level FCF requested for a known ETF remains explicitly `not_applicable`; orchestration cannot silently substitute the aggregate strategy.

---

## 13. Module boundaries

This is a package-level map, not a generated file listing — it names what each top-level `src/` package owns, not every file in it:

- `src/analysis/` — the generic `BaseAnalyzer`/`AnalysisContext` contract and strategy-neutral helpers (`shared/financial_resolution.py`: EPS/quote resolution, price-relationship comparison, ticker normalization).
- `src/strategies/` — one package per strategy, each file named for its role (analyzer modules, `selection.py` for the persisted selection snapshot, `tool.py` for the analysis-tool arguments model, `codec.py`, `execution.py`, `presenter.py`), plus `_shared/` and `_graham/` for code several strategies share.
- `src/core/` — the shared clock (`clock.py`), core result/status types, and trajectory telemetry.
- `src/data/` — provider contracts and adapters (`base_client.py`, `market_data.py`, `sec_edgar/`, `massive/`, `yfinance/`), financial provenance and resolution (`financial/`), instrument identity/profiles, and SQLite repositories under `repositories/`.
- `src/evaluation/` — the Golden case catalog, deterministic evaluator, fixtures, and evaluation reporting.
- `src/llm/` — the local-model client.
- `src/orchestrator/` — LLM tool selection/dispatch and the analysis-tool handlers registered on it.
- `src/reporting/` — direct strategy presenters and saved-run report projections.
- `src/schema/` — structured-output schema constraints and validation.
- `src/tools/` — the tool-dispatch protocol and argument-schema generation.
- `src/utils/` — logging and worker/concurrency helpers.
- `src/workspace/` — the selection base and the closed selection and native-evidence unions (`selection_base.py`, `strategy_types.py`), analysis requests, run capture, watchlists, and refresh.

The provider/resolver/cache seams live with the narrowest responsible package rather than inside `BaseDataClient`. Production SQLite persistence is implemented under `src/data/repositories/`; callers consume typed domain objects rather than SQL rows.

---

## 14. Contributor guardrails

- Preserve existing behavior outside the active step.
- Use the smallest change that satisfies the current milestone plan.
- Do not create a generic strategy registry merely because multiple strategies exist.
- Do not collapse distinct analysis methods behind ambiguous names or optional-field bags.
- Keep calculators free of provider/cache/CLI I/O.
- Enforce requested `as_of` as an information boundary; do not substitute later current facts.
- Do not claim a production AAA-yield series until its identity, semantics, availability, and integration are explicitly approved.
- Do not use operational logger lines as the primary investor-facing result renderer.
- Do not force heterogeneous strategies into one generic result object merely for presentation.
- Do not build a daemon, scheduler, proactive-monitoring service, notification system, full-screen TUI, or executive-report generator before the roadmap step that owns it.
- Keep application persistence SQL in `src/data/repositories/`; migration DDL and test setup/assertion SQL retain their established owners.
- Run Ruff, `mypy --strict`, and pytest according to the active milestone plan.
- Never read the wall clock directly; use an injected clock (see [*Time and the analysis boundary*](#5-time-and-the-analysis-boundary)).
