# Investment Analysis Engine Architecture

This document explains system boundaries, data ownership, and execution flow. Content describes current behavior unless it appears in [*Planned work*](#12-planned-work), which is the only place a not-yet-built item is described.

**Related roadmap:** `docs/project/MASTER_PLAN.md`<br/>
**Active implementation detail:** `milestones/v0.2/IMPLEMENTATION_PLAN.md`<br/>
**Step 2.3 implementation specification:** `milestones/v0.2/step-2.3/STEP_2_3_GRAHAM_DESIGN.md`<br/>
**Rationale:** `docs/project/DISCOVERY_WORKBOOK.md`<br/>
**Adding a strategy:** `docs/project/ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md`<br/>

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
- **Light Mode first:** Core useful analysis must remain viable under the documented Light Mode workflow.
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
 BaseDataClient       FinancialFactsProvider / narrow providers
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

The presentation boundary is intentionally downstream of deterministic calculation and provenance. Step 3.4 later persists Analysis Runs and renders them through the same presentation contract rather than recalculating merely to display historical results.

---

## 4. Composition roots and dependency wiring

A composition root is where a run's concrete dependencies — provider, cache, resolver, clock, and (when persisting) the durable instrument-profile cache and Analysis Run repository — are constructed and wired together before an analyzer ever runs. The current composition roots are `src/cli.py` (direct commands), `src/cli_workspace.py` (workspace/watchlist commands), and `src/workspace/refresh.py` (one composition per job in a concurrent watchlist refresh). Composition is not a strategy's own concern: an analyzer and its resolver receive already-composed dependencies through their constructors and never construct or close them.

Every composition root reads `executed_at` exactly once, via `utc_now()`, and threads that single reading through everything the run touches — see [*Time and the analysis boundary*](#5-time-and-the-analysis-boundary) for the resulting clock model. `_maybe_save_run` (`src/cli.py`) is the one place shared by all four direct commands that decides, from `--save-run`, whether a run's capture ever reaches persistence.

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

Every current analyzer implements `BaseAnalyzer[ConfigT, ResultT]` and is invoked identically — `run_analysis(ticker, config, context)` — but that is the full extent of what strategies share by contract. What a strategy owns:

- its own configuration/policy model;
- its own input resolution (which provider capabilities it needs, and how it resolves them);
- its own deterministic calculation;
- its own typed result and metrics.

What every strategy shares instead of rebuilding: `BaseAnalyzer` and `AnalysisContext`, the provider/cache contracts and `ResolvedInput`/`ResolutionTrace` provenance model, the shared `MetricResult` outcome type, workspace execution and Analysis Run persistence, and the concise/details/diagnostics/JSON presentation grammar. A strategy that needs a concern one of these doesn't cover extends its own layer first; nothing here is a reason to build a second, strategy-specific version of shared infrastructure.

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
      ├── SecurityIdentityProvider ────────────► identity / instrument-kind snapshot
      │                                                    │
      │                                                    ▼
      │                                    durable instrument-profile cache (optional)
      │                                                    │
      └── FinancialFactsProvider                           │
              ├── quote                                    │
              ├── company fundamentals                     │
              └── macro observation contract                │
                      │                                     │
        ┌─────────────┴─────────────┐                       │
        ▼                           ▼                       │
method-specific Graham        FCF annual-series              │
resolver ◄── override/cache   resolver ◄── override/cache    │
        │                           │                       │
        ▼                           ▼                       │
  resolved inputs             resolved inputs                │
        │                           │                       │
        ▼                           ▼                       │
deterministic Graham method   deterministic FCF method       │
        │                           │                       │
        └─────────────┬─────────────┘                       │
                       ▼                                     │
              typed strategy result ◄─────────────────────────┘
                       │
                       ▼
             presentation boundary
```

### `BaseDataClient` and `MarketDataProvider`
`BaseDataClient` is the original concrete provider boundary for historical market prices; it remains price-history focused rather than becoming the owner of fundamentals, valuation quotes, macro series, and cache policy. `MarketDataProvider` (`src/data/market_data.py`) is a narrower structural protocol — `provider_id` plus `fetch_historical_data` — and is the boundary Momentum's resolver actually consumes. `MomentumAnalyzer` accepts either a `BaseDataClient` or a `MarketDataProvider` directly; when only the former is supplied, a private `_ClientProviderAdapter` wraps it so existing `BaseDataClient` callers keep working without duplicating the historical-price contract.

Current quote retrieval is a separate valuation capability; it is not implemented as a one-day historical request.

### `FinancialFactsProvider` boundary
A dedicated provider-neutral financial-fact boundary supplies or composes the minimum quote and company-fundamental capabilities required by the two Graham methods. The contract can represent macro observations, but the production CLI does not currently claim an approved live AAA-yield series.

Implemented production adapters are deliberately narrow:

- **SEC EDGAR (`sec_edgar`)** — completed annual duration facts from `10-K`, `10-K/A`, `20-F`, `20-F/A`, `40-F`, and `40-F/A`. Existing exact US-GAAP mappings cover diluted EPS, diluted weighted-average shares, operating cash flow, and CapEx. Exact IFRS mappings cover diluted EPS, diluted weighted-average shares, operating cash flow, and physical-PP&E CapEx. Fiscal-year-end balance-sheet components and conservative BVPS derivation remain US-GAAP-only; IFRS BVPS and preferred-zero inference are unsupported.
- **Massive (`massive`)** — current TTM diluted EPS and current price when Massive is explicitly selected. Live use requires `MASSIVE_API_KEY`; current-only facts do not masquerade as historical evidence.
- **Yahoo Finance (`yfinance`)** — narrow current-price financial-facts adapter used for quote comparison on the Graham analyses using SEC EDGAR financial facts. It does not claim historical quote support through the financial-facts contract.

The Graham Number's default SEC route pairs SEC financial facts with Yahoo current quote comparison. Its explicit Massive route is deliberately limited to Massive TTM EPS plus a BVPS override and may use a Massive quote. SEC-backed Growth defaults to three-year-average EPS plus Yahoo quote; explicitly selecting Massive uses its supported TTM EPS/current-price data. Unsupported provider/basis combinations are rejected before provider work.

### Security identity and instrument applicability
`SecurityIdentityProvider` is a narrow optional capability beside, not inside, numeric financial facts. F-1 returns an immutable current descriptive snapshot with normalized ticker, optional instrument name/listing venue/issuer and instrument identifiers, provider identity, and timezone-aware `resolved_at`. SEC retains current ticker-title/CIK evidence from its ticker mapping; Yahoo retains supported instrument metadata, including non-company names where available.

Approved pre-Golden P1 preserves that one-provider snapshot and adds a separate immutable `InstrumentKindEvidence` value with normalized kind, retained raw provider classification, provider identity, and resolution time. A composed `InstrumentProfile` can therefore retain SEC identity/CIK and Yahoo kind evidence without pretending that one provider supplied both. Kind is provider-backed metadata: it is never inferred from a ticker, name, missing financial facts, or another strategy's success. The exact proposed mappings and schema consequences are recorded in the [P1 instrument applicability mapping record](milestones/v0.2/step-2.5/STEP_2_5_P1_INSTRUMENT_APPLICABILITY_MAPPING_RECORD.md).

An ordered, explicitly injected profile resolver selects the best available descriptive identity by provider precedence and obtains kind evidence independently. Each provider/capability is consulted at most once per run, and one YFinance metadata fetch is shared by its identity and kind capabilities. Missing metadata, unsupported capability, and lookup failure remain unknown and fail open. They cannot invalidate or downgrade otherwise usable financial evidence. Affirmative kind evidence is different from lookup failure: a provider-confirmed ETF establishes that both Graham methods and the existing company-level FCF Growth strategy are `not_applicable`, while Momentum remains applicable. This strategy-specific applicability decision does not change any financial formula and does not silently select a future ETF strategy.

A present name uses `Instrument Name (TICKER) — Analysis` in successful, unsuccessful, and `not_applicable` presentations; whitespace is normalized without changing official capitalization or punctuation. Ordinary unavailability/provider failures do not claim the ticker is invalid without affirmative provider evidence. Current metadata does not prove the identity or instrument kind that applied at a historical analysis `as_of`.

### Method-specific Graham input resolution

`GrahamNumberInputResolver` and `GrahamGrowthInputResolver` inherit the shared `InputResolver` constructor and field-resolution behavior. Each lives in its strategy package's `calculation.py` and assembles only its own method inputs. Both borrow the provider, cache, and clock supplied by composition; neither constructs or closes those dependencies. Each required field resolves independently using:

```text
explicit override → valid cache → configured provider → unavailable
```

Calculators receive resolved values and do not perform I/O. The resolver enforces requested `as_of` boundaries and preserves typed provenance. Method-input assembly adds only method-semantic annotations that are justified by retained evidence, such as fiscal-year-end basis on derived BVPS.

### Resolved input and provenance models
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
No durable evidence cache or database migration is introduced. Shared comparison
evaluation supplies both the legacy percentage and structured status/reason;
Graham presentation schema 4 exposes sanitized evidence and provenance.

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
retain their existing signatures and import paths as repository delegates.
The sink retains flush/close synchronization and optional database disposal;
by default, closing it leaves the borrowed database open. Repository errors
propagate; the recorder retains fail-open handling. Event encoding and readback
validation preserve the existing contract, including the readback encoding
check without adding a new write-time encoding policy.

This storage layer does not introduce watchlists, investor Analysis Runs, new
cache invalidation rules, or a second audit log. Those remain distinct product
and policy concerns.

### Durable instrument profiles

`SQLiteInstrumentProfileRepository` persists composed identity/kind evidence keyed by a minted `profile_id`, not by ticker: only a resolution that yields a provider-verified identity anchor (`SecurityIdentity.issuer_identifier`) becomes durable, so a ticker that never earns an anchor keeps resolving live on every request, exactly as the request-scoped composer above does unwrapped. `CachedInstrumentProfileResolver` layers freshness/TTL/refresh over that repository: a fresh durable profile is reused without a provider call; a stale or missing one refreshes live. When a refresh's anchor disagrees with the stored one — a **ticker reuse**, such as delisting and relisting — the prior row is superseded (retained, never deleted or overwritten) and a new profile is minted; the resolver serializes this decision per ticker so concurrent callers (watchlist refresh's worker pool) cannot mint two competing profiles for the same ticker. Provider precedence and disagreement handling remain entirely owned by the request-scoped composer described above; the durable layer adds only persistence, freshness and the identity/ticker-reuse rule on top of it, matching the "Time-bounded provenance" invariant (§2). See the [P2-Profiles contract](milestones/v0.2/p2-profiles/P2_PROFILES_CONTRACT_AND_SLICE_PLAN.md) for the full identity-key, precedence, freshness and historical-snapshot design.

Every production instrument-profile composition site (Momentum's direct/refresh paths, and the Graham Number/Growth/FCF Growth shared composition helper, covering both direct commands and watchlist refresh) resolves through this durable cache wherever a database is already open for another reason; a genuinely storage-free CLI invocation (no `--save-run`, no refresh) remains live-only rather than opening a database solely to populate the cache.

An `AnalysisRun`'s persisted `instrument_profile` is the immutable value captured at execution time regardless of whether it came from a live call or the durable cache; a later ticker-reuse supersession never relabels an already-persisted run, since replay (§ `AnalysisRun` below) reads only that stored snapshot and never the durable cache's current state.

### `AnalysisRun`
A durable investor-domain record of one requested analysis. It owns an `analysis_run_id`, ticker, analysis/method, requested `as_of`, configuration snapshot, status, typed result payload, resolved-input provenance, warnings, timestamps, calculation/version identifiers, and the nullable security identity/instrument-profile snapshot used by that completed run (including provider and `resolved_at`). It may link to execution/trajectory identity but must not overload telemetry `RunContext`.

A report is a rendering of an Analysis Run, not a second canonical result object in v0.2. Viewing an old run must use its persisted identity snapshot rather than re-resolving the ticker and silently relabeling history after ticker reuse.

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
`0003_watchlist_entries`, and `0004_instrument_profiles`; older-schema support
is verified with synthetic history. See [Local Database Operations](../user/DATABASE.md)
for target selection, error recovery and installation/platform limits.

---

## 9. Presentation and reports

### Investor-facing result presentation
A narrow presentation seam maps Momentum, Graham, and Free Cash Flow & Earnings Growth typed outputs into a common investor-facing grammar without altering their domain models. The default view is concise and result-first; details expose financial provenance; diagnostics expose resolution mechanics; JSON exposes each strategy's stable versioned machine-readable contract. Material overrides and warnings remain visible.

Each JSON presentation exposes one explicit nullable `security_identity` snapshot. Momentum and Graham presentation schemas increment from 1 to 2. The FCF/Earnings Growth presentation schema increments from 2 to 3 while retaining `result_schema_version = 2`, because identity is presentation metadata and does not change the typed calculation result.

Each strategy's concise view uses investor-facing wording specific to its own method — see the [user strategy guides](../user/strategies/README.md) for what each one says and why; the presentation seam does not impose shared wording across strategies. Successful concise output omits redundant `Status: ok` and `As of: current`; historical requests surface the `as_of` boundary in the heading. All required-input/provider/ticker failures pass through the typed presentation boundary, and every calculation status has an exhaustive plain-English investor label.

---

## 10. Orchestration and evaluation

### Structured-output boundary

Step 2.2 establishes structured-output enforcement with layered defenses:

1. use native Ollama/provider schema constraints when capability is confirmed;
2. retain Pydantic validation at the application boundary;
3. use the configured prompt-based schema fallback when native capability is unavailable or unknown;
4. retain legacy compatibility parsing only as the final fallback where required.

Do not rewrite the runtime around a model-specific assumption merely to make one model pass.

### Golden-Suite architecture

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
                                ├── JSONL (Step 2.1)
                                └── SQLite (Step 3.1)
```

Telemetry may capture observable provider/model metadata, prompts/completions, tool arguments/results, latency, and exposed token metrics subject to retention/redaction policy.

Private model reasoning is never reconstructed.

### Failure and reliability boundary

- Recoverable failures may enter a bounded retry/repair flow.
- Non-recoverable failures halt with structured diagnostics.
- Step 2.6 owns hard execution/time/error caps through one immutable
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

Strategy implementations live under `src/analysis/strategy/`. Shared financial-resolution helpers (`shared/financial_resolution.py`) own strategy-neutral mechanics such as EPS/quote resolution, the price-relationship comparison, and ticker normalization; callers supply strategy-specific messages. Graham Number and Graham Growth Value are two fully independent strategies with no shared Graham-specific base — each owns its own config, selection, EPS-basis acceptance rule and defaults, calculation, and result type; the only Graham-adjacent code either strategy imports is the genuinely neutral, provider-facing `data/financial/eps_basis.py`. Each strategy package exports its own analyzer, configuration, calculation/resolver, and service contracts through `__init__.py`; Momentum and FCF Growth retain their distinct interfaces and internal layouts.

This is a package-level map, not a generated file listing — it names what each top-level `src/` package owns, not every file in it:

- `src/analysis/` — the generic `BaseAnalyzer`/`AnalysisContext` contract, plus each strategy's own package under `strategy/`.
- `src/core/` — the shared clock (`clock.py`), core result/status types, and trajectory telemetry.
- `src/data/` — provider contracts and adapters (`base_client.py`, `market_data.py`, `sec_edgar/`, `massive/`, `yfinance/`), financial provenance and resolution (`financial/`), instrument identity/profiles, and SQLite repositories under `repositories/`.
- `src/evaluation/` — the Golden case catalog, deterministic evaluator, fixtures, and evaluation reporting.
- `src/llm/` — the local-model client.
- `src/orchestrator/` — LLM tool selection/dispatch and the analysis-tool handlers registered on it.
- `src/reporting/` — direct strategy presenters and saved-run report projections.
- `src/schema/` — structured-output schema constraints and validation.
- `src/tools/` — the tool-dispatch protocol and argument-schema generation.
- `src/utils/` — logging and worker/concurrency helpers.
- `src/workspace/` — validated selections, strategy execution adapters, run capture, watchlists, and refresh.

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
