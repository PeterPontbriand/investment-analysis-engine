# Step 2.3 Graham Implementation Slice Plan

**Status:** Slices A–F1 complete and approved; F2 next<br/>
**Governing design:** `docs/milestones/v0.2/STEP_2_3_GRAHAM_DESIGN.md`<br/>
**Scope:** Milestone v0.2, Step 2.3 only<br/>
**Last updated:** 2026-08-22

## 1. Purpose

This document is the concise handoff and execution plan for implementing Step 2.3 with a smaller-context coding model. It supplements, but does not replace, the detailed financial, architectural, temporal, and provenance requirements in `docs/milestones/v0.2/STEP_2_3_GRAHAM_DESIGN.md`.

Each slice must be implemented and reviewed independently. Do not begin Step 2.4 or create Step 3 durable persistence during Step 2.3. Reviewed intermediate checkpoints may be committed/pushed only after explicit human approval and a green agreed gate; such a checkpoint does not declare Step 2.3 complete.

## 2. Cross-slice rules

The following rules apply to every slice:

1. Use deterministic code only. No LLM participates in calculations, input selection, growth estimation, or fallback behavior.
2. Keep the Graham Number and Graham growth-value method explicitly distinct.
3. Missing inputs never become zero and never silently fall back to semantically different fields.
4. Preserve source, basis, provider field, observation period, availability time, requested `as_of`, retrieval time, resolution time, cache state, and derived lineage as applicable.
5. Historical requests may use only facts knowable on or before the requested `as_of` boundary.
6. `BaseDataClient` remains the historical-price-series boundary. Do not enlarge it with fundamentals, macro-series, valuation-cache, or growth-estimation responsibilities.
7. No live API or network calls are permitted in automated tests.
8. Production provider fields are not guessed. They must pass the provider evidence gate in the governing design.
9. Expected growth remains an explicit user-supplied input for the growth-value method unless a separate growth-estimation policy is approved.
10. Do not commit automatically at the end of an individual slice. A human may explicitly authorize a coherent reviewed checkpoint commit/push; Cline must otherwise leave the worktree untouched by Git write actions.

## 3. Coding-model workflow

Use one fresh Cline task per slice or tightly bounded correction. Every prompt should contain:

- a short repository-state handoff;
- the single slice objective;
- exact authorized files or file areas;
- explicit exclusions;
- focused tests and quality gates;
- a requirement to report actual files and symbols present on disk; and
- an instruction not to commit.

Paste the complete prompt before switching Cline to Act mode. Do not switch an existing task to Act mode while it still has pending instructions.

At the end of each slice:

1. Review Cline's report skeptically against the actual diff.
2. Generate a full tracked-and-untracked diff with the local `all_changes.diff.sh` convenience script.
3. Confirm that no unauthorized files or concepts were introduced.
4. Resolve only review findings within that slice before proceeding.
5. If the human designates the state as a checkpoint, rerun the agreed gate and obtain explicit commit/push authorization; a checkpoint does not complete the parent step.
6. Begin the next slice in a fresh Cline task.

## 4. Slice status and scope

| Slice | Scope | Status |
| :--- | :--- | :--- |
| A | Repository reconnaissance only | Complete |
| B | Pure calculators and typed method results | Complete and approved |
| C1 | Provenance models and in-memory cache foundation | Complete and approved |
| C2 | Provider-neutral fact contracts and field-level input resolution | Completed incrementally through C2D-2 and approved |
| D | Deterministic valuation fixtures and fixture adapter | Complete and approved |
| E1 | Production-provider evidence investigation | Complete and approved |
| E2 | Evidence-approved production adapters | Complete and approved |
| Checkpoint | Preserve coherent foundation through E2 | Human-approved commit/push permitted; Step 2.3 remains incomplete |
| E3 | User-viable default Graham production data path (BVPS gap) | Complete and approved |
| F1 | Investor-facing result presentation for Graham + Momentum | Complete and approved |
| F2 | Unified direct-analysis CLI and CLI tests | Next |
| G | Documentation synchronization, final cleanup, and full quality gate | Pending |

## 5. Slice details

### Slice A — reconnaissance only

At the time of Slice A, inspect the then-current local implementation and synchronized documentation. Identify reusable code, design conflicts, affected files, existing tests, and uncertain provider fields.

Constraints:

- Make no changes.
- Do not propose production field mappings without evidence.
- Report the exact repository state that later slices must preserve.

Acceptance:

- Current implementation and documentation are reconciled.
- Reusable and conflicting elements are identified.
- Later prompts can rely on an explicit file inventory.

### Slice B — pure calculators and typed results

Implement the two deterministic calculation methods and their typed outcomes:

- Graham Number: `sqrt(22.5 * EPS * BVPS)`;
- Graham growth value: `EPS * (base_pe + growth_multiplier * g) * baseline_aaa_yield / current_aaa_yield`.

This slice owns calculation-only validation, method discriminators, machine-readable statuses, finite-output guards, result invariants, and hand-calculated unit tests.

Constraints:

- No providers, cache, resolver, provenance, CLI, or documentation changes.
- Pure calculators perform no network, filesystem, settings, cache, or clock I/O.

Status: complete and approved.

### Slice C1 — provenance and cache foundation

Implement the immutable provenance and cache primitives required by later resolution work:

- `ValuationSubjectKind`;
- `SourceKind`;
- `ComponentLineage`;
- `ResolvedInput`;
- `ValuationCacheKey`;
- `ValuationCacheEntry`;
- `ValuationCacheProtocol`; and
- `InMemoryValuationCache`.

This slice owns constructor invariants, timezone-aware timestamps, finite values, provider-ID canonicalization, cache-key normalization, key/input coherence, TTL behavior, historical availability checks, schema isolation, and deterministic clock injection.

Constraints:

- Store only original `provider` or `derived` facts.
- Do not cache overrides, cache-sourced results, failures, or non-finite values.
- The cache does not fetch, resolve, relabel, or fall back.
- No live provider, resolver, CLI, or documentation work.

Status: complete and approved.

### Slice C2 — provider-neutral contracts and input resolver

Implement the provider-neutral fact boundary and field-level resolution behavior needed by both Graham methods.

The resolver order is:

```text
explicit override -> valid cache entry -> configured provider -> explicit unavailable/error result
```

Expected responsibilities:

- define the smallest provider-neutral requests and fact payloads required for quote, EPS, BVPS, and AAA-yield inputs;
- resolve each semantic field independently;
- validate provider facts before accepting or caching them;
- enforce requested `as_of` eligibility using `available_at`, not merely a reporting-period end;
- convert cache hits into correctly labeled cache provenance while preserving original provider or derived origin;
- distinguish invalid input, unavailable fact, and provider failure;
- ensure an override prevents provider access for that field;
- preserve optional-quote behavior separately from required valuation inputs; and
- test every branch with fakes and an injected clock.

Constraints:

- No production provider mapping or live calls.
- No deterministic fixture dataset yet beyond small test fakes.
- No CLI or documentation changes.
- No growth estimation.
- Do not redesign the approved C1 models unless a concrete incompatibility is reported and reviewed first.

The exact authorized files should be established in the C2 prompt after inspecting the approved C1 public surface.

### Slice D — deterministic valuation fixtures

Add a deterministic fixture facts provider and realistic fixture data sufficient to exercise both valuation methods without network access.

Fixtures must cover:

- three completed annual EPS observations;
- an explicit TTM EPS observation;
- provider-reported or transparently derived BVPS;
- a quote;
- an identified AAA-yield observation;
- observation/reporting periods and `available_at` timestamps;
- units, currency, retrieval metadata, and exact fixture field identifiers;
- missing, stale, future-published, malformed, and non-finite cases; and
- resolver precedence, cache, lineage, and historical rejection branches.

Constraints:

- No network fallback.
- Fixture capabilities do not imply that a live provider supports the same capabilities.
- No CLI changes unless separately authorized.

### Slice E1 — production-provider evidence investigation

Status: complete and approved.

The evidence gate established which production capabilities could be implemented without guessing field semantics or historical behavior.

### Slice E2 — verified production adapters

Status: complete and approved.

Implemented only evidence-approved production capabilities. The current foundation includes a production valuation-provider façade, SEC EDGAR annual diluted EPS, and Massive current TTM diluted EPS/current price. Unsupported capabilities remain explicit unavailable; current snapshots do not masquerade as historical evidence. Tests use deterministic mocked/recorded payloads and no live network calls.

### Human-approved checkpoint after E2

The provider/resolver foundation through E2 is a coherent durability boundary. After the agreed Ruff/mypy/pytest gate and human review, it may be committed and pushed before Investor UX changes begin.

Rules:
- the commit message must identify it as a Step 2.3 checkpoint through E2;
- do not describe Step 2.3 as complete;
- do not begin Step 2.4; and
- subsequent E3/F1/F2/G work proceeds from that preserved baseline.

### Slice E3 — user-viable default Graham data path

**Goal:** make an ordinary ticker-only Graham Number analysis genuinely useful with production data rather than merely prettier.

The verified E2 adapters do not yet provide BVPS. Research and implement a defensible production path using either:
- a provider-reported BVPS whose definition is sufficiently documented; or
- transparent derivation from common shareholders' equity and period-end common shares outstanding.

Required provenance:
- exact provider fields/concepts and provider identifier;
- common-vs-total equity semantics and applicable share class;
- reporting/balance-sheet period;
- filing/publication/availability timestamp;
- units/currency;
- transformations/derivation lineage; and
- split/share-basis compatibility with EPS and price.

Acceptance:
- a representative supported US equity can complete `financial-agents graham TICKER` using the default three-year-average Graham Number path without a manual BVPS override;
- unsupported tickers/capabilities remain explicit unavailable;
- no provider field is selected merely because its name is convenient;
- deterministic tests cover direct/derived BVPS, unavailable data, temporal eligibility, and provenance; and
- if no safe path can be established, stop for human product review rather than fabricating a fallback or hiding the limitation.

### Slice F1 — investor-facing result presentation

**Goal:** separate financial result presentation from operational logging and make Momentum + Graham feel like one coherent product.

**Status:** complete and approved.

Locked implementation outcomes:
- default/details/diagnostics/JSON rendering uses strategy-specific presenters with a shared terminal grammar rather than a generic strategy-result model;
- details mode uses fixed labels for v0.2; table-oriented terminal rendering is deferred until real-user feedback justifies it;
- JSON establishes `schema_version = 1` before F2;
- Graham diagnostics render an explicit immutable resolver execution trace that is separate from financial provenance;
- cache diagnostics report only what the current cache contract can know; a returned `None` is not fabricated into a precise stale/absent cause;
- Momentum market-source/freshness/currency metadata remains execution/presentation context rather than being added to the pure `MomentumMetrics` calculation result;
- unavailable Momentum SMA/crossover values are represented as `None`/JSON `null`, never `NaN`; an unsupported window therefore produces `UNKNOWN` with explicit unavailable metrics; and
- ordinary lower-layer provider failures raise typed/domain errors while user-facing wording remains the responsibility of the command/presentation boundary.

The F1 live-validation hardening explicitly prevents non-finite numeric sentinels and provider-library implementation details from becoming ordinary investor-facing output.

Implement strategy-specific presenters or an equivalent narrow presentation seam with four levels:

1. **Default concise:** ticker, analysis/method, `as_of`, status, headline metrics, plain-language comparison, high-level sources/freshness, material warnings, and method limitation.
2. **`--details`:** resolved inputs, basis, periods/dates, availability, source/provider, derivations, assumptions, and provenance.
3. **`--diagnostics`:** override/cache/provider resolution trace and classified failures; cache state never erases original financial source identity.
4. **`--json`:** stable machine-readable typed result/provenance representation.

Rules:
- user overrides are visually conspicuous, especially expected growth;
- the Graham Number says maximum indicated price/screening ceiling, not unqualified intrinsic value;
- raw crossover flags and similar implementation details may remain in details/JSON while the concise view uses investor language;
- Momentum and Graham share layout/terminology conventions without a generic strategy-result bag;
- stdout/result rendering is distinct from operational logger output; and
- no watchlist, SQLite Analysis Run, daemon, TUI, PDF, or executive-report work enters this slice.

Acceptance includes deterministic snapshot/semantic tests for both strategies, warnings/overrides, unavailable quote behavior, and machine-readable output.

### Slice F2 — unified direct-analysis CLI

Wire the presentation layer into the direct commands.

Pre-F2 live-validation requirements:
- the default Graham path must behave as a ticker analysis, not as a legacy formula calculator that first demands EPS, growth, and AAA-yield flags;
- a successful arithmetic calculation driven entirely by overrides must not be presented as provider-validated analysis of a security whose identity/evidence was never established; either make the override-driven/unverified nature conspicuous or reject it under a documented subject-validation policy;
- normal investor-facing output must not expose Pydantic tracebacks/documentation links, provider-library keys such as `currentTradingPeriod`, or operational logger prefixes as the primary result surface;
- missing or invalid tickers must fail with one clear user-facing message rather than producing authoritative-looking valuation output merely because unrelated manual inputs were supplied;
- material overrides must be conspicuous in concise output, especially forecast growth and any manually supplied financial fact;
- the Graham Number must use the approved maximum-indicated-price/screening-ceiling wording, while the growth method must remain visibly forecast-dependent; and
- deterministic CLI tests must include the live-probe classes that motivated F1/F2: invalid ticker, unavailable quote, override-heavy growth analysis, insufficient Momentum history, and JSON `null` rather than `NaN`.

Required behavior:
- `financial-agents graham TICKER` defaults to Graham Number;
- explicit `--method growth` gates growth-only options and requires the expected-growth assumption under the approved policy;
- incompatible flags are usage errors, never silently ignored;
- an EPS override inherits the method default basis unless explicitly changed, and that assumption is visible in provenance;
- optional quote failure preserves a valid method value while suppressing comparison fields;
- `--details`, `--diagnostics`, and `--json` behave consistently;
- existing Momentum direct analysis uses the same presentation mode vocabulary; and
- CLI tests use deterministic providers/fixtures only.

Before removing/renaming transitional flags, search tests, README/help text, and code call sites and record the intentional compatibility change.

### Slice G — documentation, final cleanup, and complete gate

Synchronize all user-facing and architectural documentation with the implementation that actually exists. Remove stale descriptions of the transitional CLI and clearly distinguish the Graham Number from the forecast-dependent growth-value method.

Required final documentation cleanup:

- verify `README.md`, `ARCHITECTURE.md`, `DISCOVERY_WORKBOOK.md`, `FINANCE_MATH.md`, `GLOSSARY.md`, `MASTER_PLAN.md`, `milestones/v0.2/IMPLEMENTATION_PLAN.md`, and `milestones/v0.2/STEP_2_3_GRAHAM_DESIGN.md` against the final implementation;
- replace intentional two-space Markdown hard breaks in changed material with explicit `<br/>` breaks;
- search for remaining trailing whitespace, including untracked files;
- confirm commands, flags, defaults, formulas, provenance terminology, growth policy, and current implementation status; and
- ensure no documentation claims an unsupported production-provider capability.

Useful whitespace search:

```bash
rg -n --glob '*.md' '[[:blank:]]+$' docs
```

Run the repository's complete quality gate, including at minimum:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy --strict src tests
uv run pytest
git diff --check
git status --short --untracked-files=all
```

Generate and review the remaining tracked-and-untracked diff since the last approved checkpoint. Stop for human review. Do not declare Step 2.3 complete or begin Step 2.4 until that review explicitly approves completion; after approval, the remaining Step 2.3 changes may be committed/pushed.

## 6. Deferred and out-of-scope work

The following are not part of Step 2.3:

- Step 2.4 Golden Suite, evaluator, or reporting work;
- durable SQLite cache storage, migrations, and eviction policy;
- watchlists, durable Analysis Run history, user-initiated batch refresh, and run browsing (Step 3.4);
- daemon/service scheduling, proactive monitoring, notifications, full-screen TUI, and executive report generation;
- LLM-generated growth estimates;
- provider or analyst consensus growth without a separately approved policy and evidence review;
- speculative strategy registry or plugin-framework work;
- complete Graham defensive-investor qualification; and
- investment recommendations.

## 7. Final completion condition

Step 2.3 is complete only when every slice through G has passed review, the default production Graham Number path is genuinely usable for representative supported securities (or the supported promise has been explicitly narrowed), Momentum and Graham share the approved investor-facing presentation grammar, implementation/documentation agree, required inputs retain provenance/temporal semantics, the complete quality gate is clean, and the human explicitly approves Step 2.3 completion. Intermediate checkpoint commits do not satisfy this condition by themselves.
