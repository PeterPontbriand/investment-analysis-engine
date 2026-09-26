# Milestone v0.2 Implementation Plan

This plan defines the work, constraints and acceptance criteria for reliable
financial analysis, local persistence and the investor research workspace.

## Sequence and status

This table owns work-package order and status. Linked companion plans own local
slice order and review gates; evidence records do not repeat either. Git history
retains earlier decisions and publication history.

**Work-package identifiers.** The `Order` column mixes numbered Steps/Slices in the roadmap's own
decimal sequence (`2.3`, `3.3A`, `3.5`, ...) with short lettered work-package codes, per the
[Master Plan](../../MASTER_PLAN.md#8-ordered-implementation-steps--release-milestones)'s general
convention for when a letter code is used instead of a decimal sub-number. This milestone's
current codes:

- `R1` / `R2` — a refactor-work code: the Graham analyzer separation and the analysis-package
  split, both pure refactors with no new functionality.
- `R3` — a repository-wide dead code audit ([plan](R3_DEAD_CODE_AUDIT_PLAN.md)): locate and remove
  code, branches, and files that can no longer be reached, across all of `src/`, not scoped to one
  strategy or module. Scheduled deliberately before Step 3.5 (which adds five new
  quantitative-screen analyzers) so the audit runs while the codebase is still a manageable size,
  rather than after another substantial expansion makes the same audit larger and more error-prone.
- `P1` / `P2` — short for "Profile": the instrument-identity/kind applicability work, then the
  durable instrument-profile cache built on it.
- `ESC-A` through `ESC-D` — an acronym of "Existing Strategy Correctness" (the correctness
  audit/repair/renewal work package), which uses its own internal `A`→`D` gate sequence rather than
  decimal sub-numbers.
- `IR` — short for "Integration Readiness"
  ([contract](integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md)): makes the existing four
  analyses safely consumable by an external harness (point-in-time evidence/filter provider, not a
  trading-signal generator), scheduled after `R3` and before Step 3.5 for the same reason `R3`
  precedes it — corrected before, not after, more analyzers are added.
- `PKG` — the `src` → real top-level package rename ([plan](PKG_RENAME_PLAN.md)), split out of `IR`
  given its scale. Not `R4`, deliberately: that code is already used as a document-local
  requirement/test-ID label elsewhere, and reusing it here would recreate the same collision noted
  below for `graham-comparison`'s local `R1`/`R2`/`R3`.

Note the resulting collision: `graham-comparison/GRAHAM_COMPARISON_REPAIR_PLAN.md` uses its own
document-local `R1 → R2 → R3` sequence (evidence → implementation → verification), unrelated to
this milestone's `R1`/`R2`/`R3` codes above — that document's own status line marks it closed, its
evidence already folded into the Existing Strategy Correctness audit, so it carries no current
sequencing meaning.

| Order | Work | Status / next gate |
| :--- | :--- | :--- |
| 1 | Telemetry and native schema enforcement (2.1–2.2) | Implemented; model-specific empirical validation belongs to Light Mode. |
| 2 | Graham, FCF growth, evaluation and SEC FPI/IFRS (2.3–2.5A) | Complete and accepted. |
| 3 | Reliability, SQLite, analyzer/CLI separation and package split (2.6, 3.1, R1, R2) | Complete and accepted. |
| 4 | Repositories, telemetry verification and data quality (3.2, Issue #17, 3.3) | Complete and accepted. |
| 5 | Existing-analysis correctness | Initial audit/repair accepted; [renewal requirements](existing-strategy-correctness/EXISTING_STRATEGY_CORRECTNESS_PLAN.md#sequence-and-status) remain applicable. |
| 6 | [Database readiness (3.3A)](step-3.3a/STEP_3_3A_CONTRACT_AND_SLICE_PLAN.md#sequence-and-status) | Complete and accepted. |
| 7 | [Research workspace (3.4)](step-3.4/STEP_3_4_CONTRACT_AND_SLICE_PLAN.md) | Complete and accepted; final acceptance granted 2026-09-20 (Amendment A1's I3). |
| 8 | [Durable instrument profiles (P2-Profiles)](p2-profiles/P2_PROFILES_CONTRACT_AND_SLICE_PLAN.md#sequence-and-status) | Complete and accepted; final acceptance granted 2026-09-22 (see [final summary](p2-profiles/P2_PROFILES_CONTRACT_AND_SLICE_PLAN.md#153-milestone-summary)). |
| 9 | [Existing-analysis renewal (ESC-D)](existing-strategy-correctness/ESC_D_RENEWAL_PLAN.md) | Complete and accepted; final acceptance granted 2026-09-23 (see [final acceptance record](existing-strategy-correctness/ESC_D_FINAL_ACCEPTANCE.md)). Full seven-dimension audit-matrix re-run found and repaired ESC-19; ESC-18 was corrected (its branch was already unreachable dead code, tracked as R3). No unresolved correctness defects. |
| 10 | [Repository-wide dead code audit (R3)](R3_DEAD_CODE_AUDIT_PLAN.md) | Not started; next in sequence now that ESC-D is accepted. Scope/contract review required before implementation. |
| 11 | [Integration readiness (IR)](integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md) | Scope drafted, pending review; scheduled after R3 and before Step 3.5 so the codebase's integration surface is corrected before more analyzers are added on top of it. IR.4 (Python-version reproducibility) was split out and delivered independently; see [IR4_PYTHON_VERSION_REPRODUCIBILITY.md](integration-readiness/IR4_PYTHON_VERSION_REPRODUCIBILITY.md). |
| 12 | [`src` package rename (PKG)](PKG_RENAME_PLAN.md) | Not started; scheduled after IR and before Step 3.5, so Step 3.5's five new analyzers are written once under the final import path. |
| 13 | [Quantitative screens (3.5)](step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#sequence-and-status) | Plan accepted; implementation waits for the dead code audit (R3), integration readiness (IR), and the package rename (PKG). |
| 14 | Light Mode (3.6) | Not started; includes empirical model/schema and end-to-end workflow validation. |
| Deferred | ETF aggregation (P2-ETF) | Separate prioritization and provider/product-policy approval after 3.6; not a validation prerequisite. |
| Deferred | [Standard delivery surfaces (MCP server, HTTP API, Parquet/Arrow export)](DEFERRED_STANDARD_DELIVERY_SURFACES.md) | Decided as its own future work package; not started, and not to be scheduled until after Step 3.5. Discovered 2026-09 via the evidence provider roadmap. |
| Deferred | [Structured error reporting for programmatic/agentic CLI consumers](DEFERRED_STRUCTURED_ERROR_REPORTING.md) | Not started; discovered 2026-09-20 during 3.4 review. Scope/contract review required; not a validation prerequisite. |
| Deferred | [Prefix matching for Analysis Run/refresh IDs](DEFERRED_RUN_ID_PREFIX_MATCHING.md) | Not started; discovered 2026-09-20 during 3.4 review. Scope/contract review required; not a validation prerequisite. |
| Deferred | [Deduplicate Momentum's instrument-profile composition sites](DEFERRED_MOMENTUM_PROFILE_COMPOSITION_DEDUPLICATION.md) | Not started; discovered 2026-09-21 during P2-Profiles Slice D reconnaissance, raised again in PR #39 review. Scope/contract review required; not a validation prerequisite. |

## 1. Purpose & Scope

This plan turns the high-level Master Plan steps for Milestone v0.2 into an actionable, sequenced work package that the development team can organize around **before** writing production code.

**In scope**

Reliable orchestration, deterministic analysis/evaluation, provider evidence,
SQLite repositories and caches, data quality, watchlists, Analysis Runs,
quantitative screens and Light Mode verification.

**Out of scope (explicit)**
- Milestone v0.2.5 real-user validation activities (recruitment, feedback sessions)
- Milestone v0.3 analytics expansion or localization
- Unattended scheduling, proactive monitoring/notifications, autonomous multi-step research, and executive reporting (Milestone v1.0)
- Graphical UI/dashboard and full-screen TUI work. Rich terminal presentation, CLI workspace commands, and persistent run browsing are in scope where required for v0.2.5 validation.

**Success definition for the milestone**<br/>
A clean, Light-Mode-capable analysis workflow exists that:
1. Logs full trajectories (prompts, tool calls, latency, tokens).
2. Enforces native Ollama JSON schema constraints + Pydantic validation.
3. Passes a golden-test suite at the ≥ 90 % target.
4. Has hard circuit-breaker and timeout limits.
5. Persists data, execution logs, and later investor-facing Analysis Run history in SQLite (WAL) with typed repositories and basic data-quality checks.
6. Presents Momentum, Graham, Free Cash Flow & Earnings Growth, **and the Step 3.5 quantitative screening suite** through a coherent terminal experience with concise defaults, detailed provenance, explicit overrides/warnings or assumptions, resolution diagnostics, and machine-readable output.
7. Can be used end-to-end by a new user following only Light Mode instructions to analyze or add a ticker, refresh supported analyses (including the Step 3.5 screens), revisit completed runs, and inspect the evidence behind a result.

---

## 2. Guiding Constraints

The following core principles govern all technical decisions across Milestone v0.2.

| Constraint | Description & Architectural Principle | Primary Impacted Packages |
| :--- | :--- | :--- |
| **Python Determinism** | Deterministic math stays in Python; LLM is used only for planning, tool selection, and narrative synthesis. | Step 2.2, Step 2.3, Step 2.4, Step 2.5 |
| **Typed Tool Interfaces** | All tool arguments and return structures must be strictly defined via Pydantic models. | Step 2.1, Step 2.2, Step 2.3, Step 2.4, Step 3.2 |
| **Native Schema Formatting** | Native Ollama `format=Schema` (or provider equivalent) is preferred over post-hoc string/regex parsing. | Step 2.2 |
| **Light-Mode Default** | Light Mode is the recommended adoption and execution mode; Full Dual-Tier remains optional. | Step 3.5 |
| **Strict Quality Gates** | Strict typing (`mypy --strict`), Ruff, and pytest coverage are non-negotiable CI gates. | All Work Packages |
| **Guarded Egress** | Outbound network access is strictly guarded (cache-first, rate-limited, domain-whitelisted). | Step 2.3, Step 2.4, Step 3.1, Step 3.3 |
| **Classified Diagnostics** | Failures are categorized (transient vs. non-recoverable) and surface structured diagnostics. | Step 2.1, Step 2.6 |
| **Decoupled Contracts** | Decoupled, swappable implementations behind narrow interfaces are preferred over direct library dependencies. | Step 2.1, Step 2.3, Step 2.4, Step 3.1 |
| **Heterogeneous Strategy Independence** | Financial-analysis strategies must be independently selectable, deterministic, typed, and swappable. The runtime and data layer must not assume that all financial analysis follows a single analytical pattern. | Step 2.3, Step 2.4, Step 2.5, Step 3.1, Step 4 |
| **Method-Explicit Financial Semantics** | Every financial result identifies the exact method, input convention, output meaning, assumptions, and applicability; related formulas are never silently conflated. | Step 2.3, Step 2.4 |
| **Traceable, Time-Bounded Inputs** | Resolved values retain provenance, reporting/observation and availability dates, retrieval time, transformations, override/cache state, and the requested analysis `as_of`. | Step 2.3, Step 2.4, Step 3.1, Step 3.3 |
| **Progressive Investor Disclosure** | Default terminal output is concise and financial; provenance, derivations, resolution diagnostics, and JSON are explicit deeper views. Operational logs are not the presentation surface. | Step 2.3, Step 2.4, Step 3.4, Step 3.5 |
| **Analysis Run as Canonical Product Record** | Persist the requested analysis/configuration, typed result, provenance, warnings, and timestamps; render reports/views from that record rather than generating a competing canonical artifact. | Step 3.4, Step 7 |
| **Deterministic Versioned Report Projection** | Project investor reports from persisted Analysis Runs without provider/LLM calls, financial recalculation, or mutable current-state enrichment. Version the projection contract independently from calculation methods and result schemas. | Step 3.4, Step 7 |
| **Bounded Agentic Workflow** | v0.2 may concurrently execute user-requested work and synthesize completed typed results; unattended scheduling/proactive monitoring remains v1.0 work. | Step 3.4, Step 3.5, Step 6 |

---

## 3. Branch and review practice

Use a branch for a coherent unit of work and a purpose-specific prefix such as
`docs/`, `feat/` or `fix/`. A passing quality gate does not grant an outstanding
approval. Follow the linked contract for local gates and scope changes.

## 4. Detailed Work Packages

### 4.1 Step 2.1 – Trajectory Logging & Telemetry

Trajectory logging separates typed, fail-open execution telemetry from operational logging. Retain provider-reported metrics, sanitize payloads before hashing/persistence, and preserve ordered span linkage.

See [Architecture](../../ARCHITECTURE.md#8-logging-and-telemetry-boundary) and the [telemetry verification contract](issue-17/ISSUE_17_TELEMETRY_CLOSEOUT_PLAN.md).

### 4.2 Step 2.2 – Native Schema Enforcement

Use native Ollama JSON-schema constraints where supported, followed by Pydantic validation and bounded recovery. Unknown native capability uses the configured conservative fallback.

Light Mode verification must record the actual Ollama/model versions, constrained request, observed response and pass/fail result. See [reliability contracts](step-2.6/STEP_2_6_RELIABILITY_SLICE_PLAN.md).

### 4.3 Step 2.3 – Graham Methods, Input Resolution & Data Contracts

Provide separately typed Graham Number and growth-value methods, field-level input resolution, provenance and progressive disclosure. Preserve explicit growth assumptions and first-class quote retrieval.

The [Graham design](step-2.3/STEP_2_3_GRAHAM_DESIGN.md) owns detailed semantics; the [slice plan](step-2.3/STEP_2_3_GRAHAM_SLICE_PLAN.md) owns local delivery detail.

### 4.4 Step 2.4 – Free Cash Flow & Earnings Growth Analysis

Provide historical total/per-share FCF and diluted-EPS growth with explicit classification, period alignment, availability and provider-evidence rules. Preserve the heterogeneous strategy boundary.

The [FCF design](step-2.4/STEP_2_4_FCF_EARNINGS_GROWTH_DESIGN.md) owns semantics; the [provider mapping](step-2.4/STEP_2_4_PROVIDER_MAPPING_RECORD.md) owns source evidence.

### 4.5 Step 2.5 – Golden-Test Suite & Strategy Evaluation

Evaluate tool/method selection and deterministic numerical correctness over provider-free fixtures, including applicability, historical boundaries and unavailable outcomes. Require the heterogeneous minimum catalog, evaluator self-tests and separate empirical reporting.

See the [evaluation contract](../../../EVALUATIONS.md), [slice plan](step-2.5/STEP_2_5_GOLDEN_SUITE_SLICE_PLAN.md), and [independent expected values](step-2.5/STEP_2_5_EXPECTED_VALUES.md).

### 4.5A Step 2.5A – SEC EDGAR Foreign-Private-Issuer Annual-Filing Coverage

Support reviewed foreign annual forms and exact IFRS duration concepts with one analysis-scoped snapshot, taxonomy lock and affirmative security-unit compatibility. Do not infer missing preferred equity as zero or introduce ADR/FX conversion.

See the [mapping contract](step-2.5a/SEC_EDGAR_FPI_IFRS_D0_MAPPING_RECORD.md) and [slice plan](step-2.5a/SEC_EDGAR_FPI_IFRS_SLICE_PLAN.md).

### 4.6 Step 2.6 – Circuit Breakers & Timeout Limits

Enforce bounded retries, execution deadlines and circuit-breaker limits with structured terminal outcomes and fail-open telemetry.

See the [reliability contract, verification and slice plan](step-2.6/STEP_2_6_RELIABILITY_SLICE_PLAN.md).

### 4.7 Step 3.1 – SQLite DB & Migration Infrastructure

Use Alembic-controlled SQLite, typed transactions, WAL, durable financial/historical caches and optional SQLite telemetry. Keep JSONL telemetry as the default.

See the [SQLite plan](step-3.1/STEP_3_1_SQLITE_SLICE_PLAN.md) and [field-level mapping](step-3.1/STEP_3_1_D0_PERSISTENCE_MAPPING.md).

### 4.7A P2 – Durable Instrument Profiles & ETF Aggregate FCF Growth

**P2-Profiles — durable instrument profiles:** Owns items 1–2, 8, and 9 below
and the profile-specific fixtures in item 6. Before
implementation, review the identity key, provider disagreement/precedence,
freshness/invalidation, refresh, and historical-snapshot contract against the
completed repository and data-quality boundaries. Acceptance requires migrated
storage, deterministic reopen/reuse and ticker-reuse tests, truthful retained
provenance, an immutable execution snapshot suitable for Analysis Runs, the
unified data-quality exception hierarchy in item 8, and every production
instrument-profile composition site (item 9) actually resolving through the
durable cache rather than the primitive existing unused — a cache no
production code calls does not replace a live lookup.
No ETF holdings ingestion or aggregation belongs to this deliverable.

**P2-ETF — ETF aggregation strategy:** Owns items 3–5, holdings/aggregate fixtures
in item 6, and item 7. Preserve the separate evidence/product-policy gate before
implementation. Do not create
speculative ETF schemas or infrastructure while implementing P2-Profiles or 3.4.

**Goal:** Replace repeated live descriptive/classification lookups with durable, time-aware instrument profiles and add a distinct look-through FCF-growth strategy for ETFs without changing the meaning of the existing company-level strategy.

**Required planning and implementation work:**

1. Persist normalized instrument kind, raw provider classification, name, venue, stable identifiers where available, provider provenance, retrieval/resolution time, and explicit freshness/expiry metadata behind a narrow repository/cache contract. Ticker alone is not a permanent identity or sufficient cache key.
2. Define cache precedence, TTL/invalidation, refresh, provider disagreement, ticker-reuse, and historical-snapshot rules. Step 3.4 Analysis Runs retain the exact identity/profile snapshot used at execution and never relabel a historical run from mutable current metadata.
3. Complete a separate provider-evidence and product-policy checkpoint for ETF holdings: provider/licensing constraints, holdings effective dates, weights, cash/derivatives, duplicate exposure, constituent identifiers, currency conversion, missing/stale constituents, coverage thresholds, rebalancing, and `as_of` semantics.
4. Implement ETF aggregate FCF Growth as a separate strategy/tool with its own typed configuration, result, method/version identifiers, coverage diagnostics, aggregation semantics, fixtures, and investor limitations. It may reuse approved company-level calculations per constituent, but it must not add ETF branches to or redefine `analyze_fcf_earnings_growth`.
5. Keep selection explicit and auditable. A company-level FCF request for a known ETF remains `not_applicable`; it must not silently invoke the aggregate strategy. Any later convenience routing belongs at the orchestration layer and requires its own reviewed selection behavior.
6. Add deterministic holdings/profile fixtures and independently verified aggregate expectations. Live providers and mutable caches remain excluded from deterministic tests and Golden fixture truth.
7. Revisit Golden coverage only after the strategy's contracts and production behavior pass their own review gate. Add cases through the existing review-directed expansion process rather than changing the original benchmark retrospectively.
8. Standardize data-quality validation failures under a single exception hierarchy (a `DataQualityError` base with focused subclasses) so `cached_client`, the Momentum analyzer, and financial-input resolvers raise consistent, orchestrator-catchable errors instead of the current mix of `DataFetchError` and bare `ValueError`. Carry the underlying quality-decision/failure reason on the exception and update the affected unit tests accordingly. Discovered during Step 3.3 review (Issue #33).
9. Wire the durable instrument-profile cache into every production instrument-profile composition site (Momentum's CLI/refresh call sites and the shared Graham/FCF composition helper), not merely provide it as an unused capability. A genuinely storage-free CLI path is not forced to open a database solely for this cache; sites reviewed and classified as intentionally database-free remain live-only. Discovered during P2-Profiles Slice C review 2026-09-21; scoped in [P2_PROFILES_CONTRACT_AND_SLICE_PLAN.md §13](p2-profiles/P2_PROFILES_CONTRACT_AND_SLICE_PLAN.md#13-slice-d--wire-the-durable-cache-into-production-instrument-profile-composition).

**P2 non-goals:** treating an ETF as an operating company, deriving holdings from an instrument name, hiding incomplete constituent coverage, using an LLM for aggregation mathematics, silently substituting the ETF strategy, or coupling strategy calculators directly to SQLite.

### 4.7B R1 – Graham Analyzer Separation & Shared CLI Plumbing Extraction

Separate method-specific Graham analyzers/configuration and shared CLI support while preserving financial semantics and heterogeneous interfaces.

See the [R1 contract](r1/R1_CONTRACT_AND_SLICE_PLAN.md).

### 4.7b R2 – Analysis Strategy Package Split

Separate analysis packages and extract only demonstrably equivalent shared helpers. Preserve Momentum/FCF behavior and use explicit dependency injection without a registry or auto-discovery framework.

See the [R2 contract](r2/R2_CONTRACT_AND_SLICE_PLAN.md) and [migration inventory](r2/R2_MIGRATION_INVENTORY.md).

### 4.8 Step 3.2 – DAO & Repository Layer

Provide bounded cache-key enumeration, stored-fact inspection and trajectory SQL ownership behind typed repositories. Preserve storage representation, eligibility and public telemetry interfaces.

See the [repository contract](step-3.2/STEP_3_2_CONTRACT_AND_SLICE_PLAN.md).

### 4.9 Step 3.3 – Data Quality & Cache Invalidation Pipeline

Validate incoming data and control cache refresh/invalidation while preserving financial semantics and provenance; do not turn telemetry into execution control.

See the [data-quality contract](step-3.3/STEP_3_3_CONTRACT_AND_SLICE_PLAN.md).

### 4.9R Existing Strategy Correctness Audit and Repair

Require independent arithmetic, realistic provider-shaped tests, complete output/consumer coverage and a defect ledger. Missing financial values and freshness limitations must be explicit.

See the [correctness contract](existing-strategy-correctness/EXISTING_STRATEGY_CORRECTNESS_PLAN.md).

### 4.9A Step 3.3A – Fresh Database Initialization & Schema Readiness

Initialize only verified fresh storage through bundled Alembic; reject incompatible storage, keep existing-schema upgrades explicit and expose sanitized actionable errors. No repair, fallback database or new business tables.

See the [readiness contract](step-3.3a/STEP_3_3A_CONTRACT_AND_SLICE_PLAN.md) and [final evidence](step-3.3a/SLICE_D_FINAL_ACCEPTANCE.md).

### 4.10 Step 3.4 – Local Research Workspace & Analysis Run Library

The [approved contract and 25 Cline slices](step-3.4/STEP_3_4_CONTRACT_AND_SLICE_PLAN.md) define request/storage/replay/refresh interfaces, file scopes and focused verification. Gate A and Slice B1 were accepted on 2026-09-13, with [completion evidence](step-3.4/SLICE_B1_COMPLETION_EVIDENCE.md). Slices B2–B4 are also accepted; B4 acceptance and B5 implementation authorization were granted on 2026-09-15. B5 was accepted on 2026-09-15 against its [completion evidence](step-3.4/SLICE_B5_COMPLETION_EVIDENCE.md). B6 was accepted on 2026-09-15 against its [completion evidence](step-3.4/SLICE_B6_COMPLETION_EVIDENCE.md). C1 was accepted on 2026-09-16 against its [completion evidence](step-3.4/SLICE_C1_COMPLETION_EVIDENCE.md); C2 is the next slice and has not been started.

**Goal**
Turn the command-line program into a small local research workbench before real-user validation: users maintain ticker/analysis lists, initiate a refresh, and revisit durable completed results without requiring a GUI or unattended service.

**Product model**
- A **watchlist** is a named local collection of tickers plus supported requested analysis types/configuration.
- An **Analysis Run** is the durable investor-domain record of one requested analysis: `analysis_run_id`, ticker, analysis/method, requested `as_of`, configuration snapshot, status, typed result payload, resolved-input provenance, the security identity/instrument-profile snapshot used by the run, warnings, start/completion times, and calculation/version identifiers. It may reference execution/telemetry identity, but does not overload `RunContext`.
- A **report/view** is a deterministic, explicitly versioned projection of an Analysis Run. v0.2 does not persist a competing canonical report document.
- A **refresh** is a user-initiated batch that may execute multiple ticker/analysis jobs concurrently and persist each completed Analysis Run immediately.

**Initial CLI workflow**
```text
ian watchlist create core
ian watchlist add core KO MSFT CNR.TO
ian watchlist remove core MSFT
ian watchlist show core
ian refresh core
ian runs list
ian runs show ANALYSIS_RUN_ID [--details|--diagnostics|--json]
```

Exact command spelling may be refined during implementation, but the user capability must remain equivalent. The initial default watchlist profile uses analyses that require no invented forward-growth assumption: Momentum, Graham Number, and historical FCF/Earnings Growth. `graham_growth_value` may be enabled only when an explicit persisted/user-supplied growth configuration is attached and shown as an assumption.

**Extension boundary:** Use stable method identifiers and versioned configuration/result
contracts independently of CLI spelling or inheritance. Retain heterogeneous
result/provenance shapes and explicit watchlist analysis selections; adding a
strategy must not silently change existing watchlists. Persist the exact request-scoped
instrument-profile snapshot used during execution and replay it without mutable
metadata reads. P2-Profiles follows this step.
Unsupported requests retain explicit applicability outcomes. ETF holdings and
aggregation are not required for this workspace and are deferred to P2-ETF;
no speculative plugin framework or ETF schema is authorized here.

**Concurrency boundary**
`refresh` may run independent jobs concurrently within the user-started process and write completed runs as they finish; a second CLI invocation may read already-persisted completed results under SQLite/WAL. Step 3.4 does **not** install a daemon/service, schedule unattended work, monitor markets proactively, or send notifications.

**Implementation outline**
1. Add migration-controlled persistence for watchlists, memberships/configuration, refresh batches if useful, and Analysis Runs.
2. Add narrow typed repositories/services for watchlist management and Analysis Run storage/query.
3. Add a narrow investor-report projector that consumes only the persisted Analysis Run plus explicit presentation mode/locale/format options. Reuse strategy presentation semantics where practical, but do not regenerate financial calculations merely to view a completed run.
4. Add user-initiated concurrent refresh with bounded worker/concurrency limits and per-job classified status.
5. Persist each completed/failed/unavailable run independently so one ticker/provider failure does not discard other completed work.
6. Preserve reproducibility: `as_of`, config, method version, result, provenance, warnings, and source timestamps travel with the Analysis Run.
7. Give the report projection contract its own explicit version, independent of method and typed result-schema versions. Persist or emit the selected projection version so rendered history is auditable; breaking structural or semantic changes require a new projection version.
8. Keep projection replay pure with respect to external and mutable state: no provider or LLM calls, financial recalculation, current identity lookup, mutable cache reads, or implicit current-clock enrichment. The same stored run, projection version, mode, and explicit locale/format options produce the same semantic output.
9. Retain historical projection implementations or provide an explicit, auditable migration. Never silently reinterpret an old run under a breaking projection contract.
10. Add deterministic tests for create/add/remove/show, refresh fan-out, partial failures, persistence/reload, run-list ordering/filtering, projection-version dispatch, historical projection replay, and view rendering.

**Acceptance criteria**
- Named watchlists can add/remove tickers and show configured supported analyses.
- A refresh over multiple ticker/analysis combinations executes with bounded concurrency and independently persisted outcomes.
- `runs list` exposes completed/unavailable/failed work without requiring recomputation.
- `runs show` renders the same concise/details/diagnostic/JSON information from the stored Analysis Run.
- Investor reports expose an explicit projection version that evolves independently from calculation method and typed result-schema versions.
- Replaying the same stored Analysis Run under the same projection version and explicit rendering options produces the same semantic report without provider/LLM access, financial recalculation, mutable cache reads, identity re-resolution, or current-clock enrichment.
- Breaking report changes create a new projection version; historical versions remain reproducible or use an explicit audited migration.
- Analysis Run identity is distinct from, but linkable to, execution telemetry identity.
- No daemon, unattended scheduler, proactive monitoring, notifications, full-screen TUI, or executive report generator is introduced.

### 4.11 Step 3.5 – Deterministic Quantitative Screening Strategies

Implement independently typed Piotroski, Altman, Beneish, valuation-multiple and
Magic Formula analyses using public data, explicit applicability and provenance.
The [screening contract](step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md) owns
component scope and local delivery detail.

### 4.12 Step 3.6 – Light Mode Support

**Goal**
The complete investor workflow—data fetch/cache → deterministic analytics → durable Analysis Run → concise/detailed inspection → bounded local-model synthesis—runs cleanly under Light Mode with a 14B-class (or smaller) model.

**Implementation outline**
1. Make Light Mode the configuration default (model tag, single-tier behaviour).
2. Ensure README and `docs/user/HARDWARE.md` give a new user a complete workflow to first analysis/watchlist refresh and stored-run inspection.
3. Add a minimal smoke test covering direct analysis or watchlist refresh, result persistence, concise rendering, and provenance inspection under Light Mode resource assumptions.
4. Confirm dual-tier functionality remains available as opt-in features.
5. Complete the Step 2.2 empirical schema/model compatibility check for the supported Light Mode configuration.
6. Add or validate a simple `ian analyze TICKER` entry point that can request the default deterministic analyses and optionally ask the local LLM to synthesize only their completed typed results.
7. Ensure synthesis failure, timeout, or schema failure never discards valid deterministic Analysis Runs.

**Synthesis boundary**
The model may summarize, compare, flag tensions, and suggest what the investor may wish to inspect next. It may not invent financial facts, perform the deterministic arithmetic, silently select a growth assumption, or turn a screening result into an investment recommendation.

**Acceptance criteria (exit criterion for Step 3.6)**
- A new user following only Light Mode instructions can analyze/add a real ticker, refresh supported analyses, and revisit stored results.
- The user can see a concise result and inspect detailed provenance without developer assistance.
- Bounded local-model synthesis works on the supported Light Mode configuration and is clearly downstream of deterministic results.
- Synthesis failure leaves deterministic results usable.
- Configuration defaults favor Light Mode and dual-tier remains optional.
- Documentation is consistent across README, `docs/user/HARDWARE.md`, Master Plan, and Discovery Workbook.

## 6. Quality Gates

The following quality checks must pass on every pull request within this milestone:

* `ruff check . && ruff format --check .`
* `mypy --strict src tests`
* `pytest` (unit and integration) with monitored coverage trends
* Zero untyped public interfaces
* Zero secret or API key leaks in trajectory outputs
* Verified Light Mode workflow functionality once Step 3.5 lands

---

## 7. Exit Criteria for Milestone v0.2

All of the following must be true before declaring the milestone complete and opening the v0.2.5 validation window:

1. Steps 2.1–2.6 and 3.1–3.6, including the Step 3.4 research workspace and the Step 3.5 quantitative screening suite, are fully implemented and merged.
2. Step 2.5 Golden-test suite exists, runs headlessly, exercises Momentum, both Graham methods, and Free Cash Flow & Earnings Growth, and reports strategy-selection, Graham method-selection, numerical-correctness, and overall pass rates against the ≥ 90 % target.
3. A fresh repository clone running Light Mode setup instructions completes the investor workflow: direct/watchlist analysis (including selected Step 3.5 screens), refresh, persisted Analysis Run, concise view, detailed provenance, and bounded synthesis.
4. CI pipeline is green on `main`.
5. Master Plan and Discovery Workbook cross-references remain consistent.
6. Temporary scaffolding and blocking TODOs are cleaned up or documented.

---

## 8. Design references

Financial semantics live in the strategy designs and [Finance Math](../../../user/FINANCE_MATH.md). Architectural rationale lives in the [Discovery Workbook](../../DISCOVERY_WORKBOOK.md). Scope exclusions remain in the relevant work package; approval history is available in Git.
