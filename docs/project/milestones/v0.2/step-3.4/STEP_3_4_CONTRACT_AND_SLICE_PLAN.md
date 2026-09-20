# Step 3.4 — Workspace Contract and Cline Slice Plan

**Prepared:** 2026-09-13 (America/Toronto).  
**Status:** **Step 3.4 is complete and accepted** (final acceptance granted 2026-09-20). Gate A and Slices B1–B6, C1, C2, C3, D1, D2, D3, D4, D5, E1, E2, E3, E4, F1, F2, F3, G1, G2, G3 and H (batch 4) accepted; see [E1](SLICE_E1_COMPLETION_EVIDENCE.md), [E2](SLICE_E2_COMPLETION_EVIDENCE.md), [E3/E4/F1/F2](SLICE_E3_E4_F1_F2_COMPLETION_EVIDENCE.md), [F3/G1](SLICE_F3_G1_COMPLETION_EVIDENCE.md), [G2](SLICE_G2_COMPLETION_EVIDENCE.md) and [G3/H](SLICE_G3_H_COMPLETION_EVIDENCE.md) completion evidence. H's own review surfaced a watchlist-model UX defect (arbitrary default selections, file-based per-method configuration, no per-ticker/multi-variant selections); **Contract Amendment A1 (§12)** was authorized on 2026-09-19 to address it via new Slices I1–I3, all now accepted: I1 (entry model, repository, migration) accepted 2026-09-19 against its [completion evidence](SLICE_I1_COMPLETION_EVIDENCE.md); I2 (watchlist CLI surface) accepted 2026-09-19 against its [completion evidence](SLICE_I2_COMPLETION_EVIDENCE.md); I3 (docs, test revisit, full regression) accepted 2026-09-20 against its [completion evidence](SLICE_I3_COMPLETION_EVIDENCE.md), carrying explicit final Step 3.4 acceptance per its own §9 acceptance criteria — this closes out Step 3.4 in full, including the G3/H review that had remained outstanding since batch 4. A short, separately-authorized series of related UX fixes (not part of Amendment A1's own slices) was also made on this branch before final acceptance; see the note at the end of §12.
**Branch:** `feat/step-3.4-local-research-workspace`.  
**Authority:** [Implementation Plan §4.10](../IMPLEMENTATION_PLAN.md#410-step-34--local-research-workspace--analysis-run-library).

## 1. Authorization and source reconciliation

The project owner approved Gate A on 2026-09-13 (America/Toronto) and requested preparation of the B1 handoff. The contracts and structural file scope below are approved. B1 is authorized after the documentation checkpoint; B2 and later slices remain subject to their predecessor review gates. This turn records approval and prepares documents only. Database readiness is complete.

The planning changes are retained against its reorganized documents; readiness closeout and the selected sequence are already incorporated.

The selected order is readiness complete → Step 3.4 → P2-Profiles → ESC-D renewed acceptance → Step 3.5 → Step 3.6. Older P2-before-workspace prose is superseded. Persist the existing request-scoped `InstrumentProfile`; a durable profile cache is not a prerequisite. No new financial formulas, provider mappings, dependencies, autonomous scheduling, LLM synthesis, ETF aggregation, UI, or report-file exports are included.

## 2. Inspected seams and gaps

Paths below are repository-relative implementation targets, not claims that proposed files already exist.

| Existing seam | Reuse / missing work |
| :--- | :--- |
| `src/data/repositories/sqlite.py`, `schema.py`, `readiness.py`, `migrations.py`; `alembic/versions/0001_persistence.py` | Connection/read/write ownership, WAL and readiness already exist. Add a successor migration; never edit the initial revision or auto-upgrade an existing database. |
| `src/cli.py`, `src/cli_support.py`, `src/cli_database.py` | Four direct commands and scoped production caches exist. Command helpers currently mix execution and rendering, especially Graham; extract only the seams required for typed capture. Keep `src.cli` a module. |
| `src/analysis/strategy/momentum/momentum_analyzer.py` | `MomentumConfig`, `MomentumRun`, `run_with_context`; retain price inputs, market context, trace, data resolution and profile. No public historical `--as-of` capability is invented. |
| `src/analysis/strategy/graham_number/`, `graham_growth/` | Independent configs/analyzers return full analysis evidence. Growth requires `expected_growth` and `aaa_yield_override`, in percent units. Preserve comparison availability and share-unit evidence. |
| `src/analysis/strategy/fcf_earnings_growth/` | Own policy and `run_analysis` signature; canonical result already carries method/result versions. Do not force it into Momentum or Graham inheritance/config shapes. |
| `src/data/instrument_profile.py`, `security_identity.py`, `security_unit.py` | Existing immutable evidence and diagnostic shapes; retain execution snapshot, including missing/unsupported reasons. No ticker-only historical enrichment. |
| `src/reporting/momentum.py`, `graham.py`, `fcf_earnings_growth.py`, `presentation.py` | Existing progressive views and public JSON versions (Momentum 4, Graham/FCF presentation 5). They are not the new run-envelope version. Some presenters derive display metrics; audit and capture these before pure replay. |
| `tests/test_existing_strategy_output_contracts.py`, `test_existing_strategy_failure_output.py`, `test_graham_comparison_composition.py`, reporting/cache/readiness suites | Preservation evidence to retain. Workspace storage, codecs, lifecycle, queries and refresh do not exist yet. |

## 3. Watchlist and request contract

Planned modules: `src/workspace/models.py`, `requests.py`, `watchlists.py`. Use strict typed models and explicit method dispatch, not discovery, plugins, registration, or a generic strategy hierarchy.

* A watchlist has an immutable UUID, unique normalized name, creation/update UTC timestamps, ordered unique ticker membership, and an ordered list of analysis selections. Trim names, reject empty names, compare names case-insensitively, preserve display spelling. Normalize tickers using current uppercase/trim conventions and preserve venue suffixes. No provider lookup occurs during editing.
* **Superseded by Amendment A1 (§12):** ~~Selections are watchlist-wide in this release. One configuration per supported method; every member receives that selection. Per-ticker overrides, multiple variants of one method, rename/delete watchlist, and run deletion are deferred. Removing membership never deletes historical runs.~~
* **Superseded by Amendment A1 (§12):** ~~Creation materializes a version-1 default selection containing Momentum, Graham Number and historical FCF/Earnings Growth. Resolve and save existing method defaults at creation; later settings changes or new strategies cannot change an existing list. Do not include Growth or enable forward-evidence requirements by default.~~
* **Superseded by Amendment A1 (§12):** ~~`watchlist configure NAME --analysis METHOD --config PATH` adds/replaces one selection from a UTF-8 JSON object. `watchlist disable NAME --analysis METHOD` removes it. Unknown methods, extra/foreign fields, non-finite numbers and malformed configs are usage errors. Validate the complete edit before opening a write transaction; never store partial edits. The config file is request data, not executable code or a settings/secrets dump.~~
* Growth configuration must explicitly supply both growth and AAA yield; never derive forecasts from historical growth. Preserve the existing validation of units/ranges and effective calculation policy. Show assumptions in watchlist details and run views.
* `AnalysisRequest` contains normalized ticker, method discriminator, `config_schema_version=1`, the appropriate typed config, requested temporal boundary and cache-use choice. Method aliases map explicitly to current canonical analysis/method identifiers; do not derive persistent identifiers from CLI spelling. The matrix below freezes current identifiers; B1 asserts them in request/configuration fixtures. Result-evidence codecs begin at B3.
* Momentum wraps `MomentumConfig`; Number and Growth wrap their existing configs plus effective calculation policy where applicable. FCF has a narrow request model containing its existing policy, currency, provider, requested `as_of` and `use_cache`. No shared financial field bag.
* Snapshot all effective defaults/provider choices and financial assumptions. Exclude credentials, database URLs, raw logs, provider objects, model prompts and unrelated application settings. Persist sanitized diagnostics only.
* `refresh` freezes membership and selections in one read snapshot. Edits made afterward apply to the next refresh. Empty membership or zero selections is a usage error before work begins. Repeating refresh deliberately creates new runs; it is not a deduplication operation.
* No batch `--as-of` override in this release: method-specific stored configs retain existing supported semantics. For financial methods, record both requested and actual effective boundary. Momentum records requested `as_of=null`, execution time and actual historical request/data bounds; execution time must not be labeled a point-in-time analysis guarantee.

### Method/config matrix

| CLI selection alias | Canonical analysis / method | Configuration source and explicit defaults |
| :--- | :--- | :--- |
| `momentum` | `momentum` / `sma_crossover` | Existing `MomentumConfig` windows/RSI defaults, materialized from current configured policy; existing historical provider. No `as_of` field accepted. |
| `graham-number` | `graham` / `graham_number` | `GrahamNumberConfig`: SEC EDGAR default, provider-dependent EPS basis, resolved quote provider, optional EPS/book-value/quote overrides, `as_of=null`, `use_cache=true`. |
| `graham-growth` | `graham` / `graham_growth_value` | `GrahamGrowthConfig`: same applicable shared fields, explicit growth and AAA yield, plus captured effective `GrahamGrowthCalculationPolicy`. No book-value override. |
| `fcf-growth` | `fcf_earnings_growth` / `reported_fcf_eps_cagr` | Existing `FCFEarningsGrowthPolicy` (longest available horizon, total FCF, display-only forward policy, optional yield enabled), provider `sec_edgar`, currency `USD`, `as_of=null`, `use_cache=true`. |

**Superseded by Amendment A1 (§12):** ~~Config JSON uses existing Python model field names and enum values, not CLI flag spelling. The FCF wrapper nests its policy under `policy`; the Graham wrappers nest their existing config under `config` and captured calculation policy is execution evidence, not arbitrary user configuration. Momentum nests `MomentumConfig` under `config`. No requested ticker or method override is accepted inside the config file. Selection identity comes from `--analysis` and ticker identity from membership.~~ Production provider choices remain restricted to those supported by the current CLI composition, even where a base config permits arbitrary identifiers for dependency injection.

FCF retains native method version 2 and result schema 3. For Momentum/Graham native types without equivalent numeric version fields, define an explicit workspace evidence method/result version 1 at this checkpoint; it denotes the captured current semantics, not a claim about historical public JSON versions. All four evidence codecs start at version 1. Existing public presentation versions remain separate.

## 4. Durable Analysis Run contract

Planned `src/workspace/runs.py` and `codecs.py` define a versioned, immutable terminal record. One run represents one ticker/method attempt, not one watchlist or telemetry session.

| Field group | Required meaning |
| :--- | :--- |
| Identity | UUID `analysis_run_id`; optional `refresh_id`, zero-based batch position, watchlist ID/name snapshot; optional telemetry correlation without an FK to telemetry. |
| Request | Normalized ticker, canonical analysis/method identifiers, exact validated requested and effective config snapshots, request/config schema version. |
| Time | Aware UTC start/completion timestamps, nullable requested `as_of`, truthful effective boundary and source observation/retrieval dates; completion cannot precede start. |
| Versions | `run_schema_version=1`, explicit method version, result-schema version, method-specific evidence-codec version, `projection_version=1`. Preserve existing versions; define an evidence wrapper where the native type has no version. Do not equate these with presenter JSON versions. |
| Outcome | `completed`, `unavailable`, `not_applicable`, `failed`, or `cancelled`; preserve native status/reason alongside the workspace classification. Partial optional metrics remain in a completed typed result. |
| Evidence | Full method-specific typed result/assembly, resolved inputs, transformations, units, market context, traces, quote comparison, warnings/overrides, identity/profile/security-unit snapshot and diagnostics actually used. Failed-before-resolution attempts may have no profile/result with a classified reason. |
| Presentation inputs | Versioned typed values needed for every view, including display-derived financial values calculated at execution. These are part of the run evidence, never a persisted rendered report or competing canonical result. |
| Failure | Safe stable reason code/message and retained available evidence. No raw exception traceback, credentials or zero substitutes. |

Execution outcomes and financial signals are separate: negative growth, bearish Momentum, and a failed financial screen are not execution failures. Native `NOT_APPLICABLE` maps to `not_applicable`; missing required evidence maps to `unavailable`; invalid inputs/execution errors map to `failed`. An optional quote/metric missing does not erase an otherwise valid calculation. Each adapter freezes its exact status mapping with fixtures before integration.

Codecs must explicitly encode/decode the existing dataclasses, enums, Pydantic models, aware timestamps and optional values. Use strict finite JSON; never pickle or decode arbitrary Python classes. Reject ticker/method/payload mismatches. Round trips must preserve provenance order, nulls, units and version metadata. Unknown versions are a typed `unsupported_run_version`; corrupt evidence is `invalid_stored_run`, never a request to recalculate or silently reinterpret.

Terminal insertion is atomic and append-only. Duplicate IDs fail without overwrite. No `running` row is required: a killed process may leave no record for in-flight/unstarted jobs. This limitation is explicit; completed committed runs survive. A refresh ID groups retained outcomes and positions without a durable scheduler/batch state table. No automatic resume, retries or interrupted-work recovery is promised.

## 5. SQLite and repository contract

Planned files: `src/data/repositories/watchlists.py`, `analysis_runs.py`, with schema declarations in existing `schema.py` and a new `0002_research_workspace.py` revision (`down_revision=0001_persistence`, verified at implementation entry).

| Table | Keys / payload / constraints |
| :--- | :--- |
| `watchlists` | ID PK, normalized-name UNIQUE, display name, UTC timestamps. |
| `watchlist_members` | `(watchlist_id, ticker)` PK; FK to watchlists; ordered position unique per list; nonempty ticker, nonnegative position. |
| `watchlist_selections` | `(watchlist_id, method_id)` PK; FK to watchlists; ordered position unique per list; config version and strict config JSON. |
| `analysis_runs` | Run ID PK; indexed ticker, method, outcome, completion timestamp and optional refresh ID; request/evidence/versioned envelope JSON. No cascading dependency on mutable watchlists, caches or telemetry. |

Relational query columns must agree with validated envelope fields on write/read. Apply SQL nonempty, outcome, version, position and timestamp constraints using current schema conventions; model validation owns nested JSON invariants. Add `(completed_at, analysis_run_id)` and refresh/position query indexes. Do not duplicate result data into a report table.

Narrow typed interfaces (concrete classes are sufficient):

* `WatchlistRepository.create(spec) -> Watchlist`; `get(name) -> Watchlist | None`; `list() -> tuple[WatchlistSummary, ...]`; `add_members(name, tickers)`; `remove_members(name, tickers)`; `set_selection(name, selection)`; `disable_selection(name, method)`.
* `AnalysisRunRepository.insert(run) -> None`; `get(run_id) -> AnalysisRun | None`; `list(query) -> tuple[AnalysisRunSummary, ...]`.
* Watchlist duplicate create is a conflict. Repeated add/remove and disabling an absent method are idempotent no-ops; missing watchlist is an error. Batch membership edits are all-or-nothing. Preserve insertion order and allocate positions transactionally without shared in-memory counters.
* Query supports ticker, method, outcome, refresh ID, `limit` (default 20, range 1–100) and `offset` (default 0, nonnegative). Order by completion descending then run ID descending; filters combine with AND. Offset pages reflect each current read snapshot, not a frozen cross-command listing.
* List queries use validated summaries without decoding every full result. A corrupt full record fails only that `show`; unknown evidence versions can remain visible as metadata in listings.

Reuse `SQLiteDatabase` and readiness composition. Repositories borrow storage and do not initialize schemas or close caller-owned resources. Writes are short transactions; no provider/calculator work holds a transaction. Migration tests use disposable storage only and retain existing cache/telemetry sentinel records across explicit upgrade. Existing `0001` storage must report upgrade-required through normal application access; fresh storage initializes at the new head. Readiness schema-signature checks must recognize both supported production revisions accurately.

## 6. Execution and direct-command boundary

Planned `src/workspace/execution.py` and explicit method adapter modules under `src/workspace/` expose `execute(request, dependencies) -> terminal evidence`. The service owns IDs/timing and capture, while adapters borrow dependencies and call existing analyzers. Production composition owns and closes providers/caches. Avoid having refresh invoke Typer commands or parse terminal JSON back into canonical results.

Extract execution from `_run_graham_number` / `_run_graham_growth` only as needed; maintain their direct-command behavior and tests. Capture the exact profile supplied to each analyzer. For Momentum, retain the profile currently composed by its CLI after calculation without claiming it was used by the calculator. Unavailable profile evidence remains explicit.

Approved direct-command integration is opt-in `--save-run` on the four existing commands. Default calls preserve output, exit codes and storage independence, including `--no-cache`. With `--save-run`, run storage is required even when financial input caching is disabled. Preflight readiness before provider work; insert before rendering a saved success. Keep existing direct JSON documents intact; explicit saving can report the run ID on stderr without corrupting JSON stdout. CLI tests must cover this stream change only when saving is requested. Orchestrator/evaluation tools do not automatically save investor runs in this step.

Storage errors are not telemetry: failed durable insertion must be visible, terminate refresh admission, and produce nonzero exit. Never claim a run is saved or silently return ordinary success. Already committed runs remain readable. Do not convert a storage exception into a successfully stored failed-analysis record. Telemetry failure remains fail-open and never decides the outcome.

## 7. Pure report replay

Planned `src/reporting/analysis_runs.py` provides `project_run(run, options) -> str`, where options explicitly select concise/details/diagnostics/JSON, `en-CA` locale and UTC time formatting for projection v1. Reject unsupported options/versions. Use the run's stored projection version by default; no automatic latest-version fallback.

Replay must not call analyzers, financial calculators, providers, profile resolvers, mutable caches, settings defaults, LLMs or current time. Formatting and label selection are allowed; financial derivations are not. In particular, current Momentum presentation computes spread values: capture those values during execution and consume them in v1 replay. Audit every method's concise/details/diagnostics/JSON path for similar hidden computations before sharing render helpers.

The JSON run view has its own versioned envelope identifying the run, method/result versions and projection version; existing direct-command JSON remains unchanged. Preserve all current financial meaning, warnings and progressively disclosed evidence. Reuse pure formatting helpers where appropriate, but future breaking presenter changes cannot silently alter v1 replay. Keep a dedicated v1 path and checked-in deterministic replay fixtures; a future incompatible implementation needs a new version or separately authorized audited migration.

## 8. Refresh and CLI behavior

Approved commands:

```text
financial-agents watchlist create NAME
financial-agents watchlist list
financial-agents watchlist add NAME TICKER...
financial-agents watchlist remove NAME TICKER...
financial-agents watchlist show NAME [--json]
financial-agents watchlist configure NAME --analysis METHOD --config PATH
financial-agents watchlist disable NAME --analysis METHOD
financial-agents refresh NAME [--workers N] [--json]
financial-agents runs list [--ticker T] [--method M] [--status S] [--refresh-id ID] [--limit N] [--offset N] [--json]
financial-agents runs show ID [--details|--diagnostics|--json]
```

`src/cli_workspace.py` owns Typer sub-apps, registered explicitly in existing `src/cli.py`. Help/import has no storage/provider side effects. Watchlist mutation reports the resulting change; show includes selections and assumptions. Usage errors exit 2; missing list/run, readiness/storage/version errors exit 1 with sanitized messages. Pure successful reads exit 0 even when showing a failed historical run.

Refresh uses a typed `RefreshPolicy`: default workers 2, range 1–4, chosen for a small local workspace and tested, not a financial assumption. Use bounded admission (at most N in-flight jobs), not eager submission of the whole list. Snapshot order is member position then selection position. Workers return evidence; the coordinator is the only run writer and persists each finished result before admitting replacement work. Providers/resolvers/cache connections are job-scoped unless existing thread safety is proven; preserve existing egress budgets/rate limits and timeouts across concurrent work rather than multiplying shared provider allowances per worker.

Provider failure or unavailability affects only its job; no new automatic job retry. Graceful Ctrl+C stops admission, cancels unstarted futures, lets already-running bounded calls settle, persists returned outcomes, and exits 130. No fabricated cancellation rows for jobs never started; no promise of killing a blocked Python thread. Hard termination can lose uncommitted work. Tests use event/barrier coordination, not timing guesses.

Text refresh output lists persisted run IDs and a final count by outcome. JSON emits one final stable document containing refresh ID, ordered saved-run summaries and counts; no worker/progress chatter on stdout. A second CLI process can inspect committed results before refresh ends. Exit 0 if all attempts are completed/not-applicable, 1 if any are unavailable/failed or persistence fails, 130 on interruption. Individual financial outcomes remain explicit in output.

## 9. Fine-grained implementation slices

Gate A approved this contract and verified readiness. Authorize **one slice at a time**, with focused evidence and explicit review before the next. Each row is one Cline task, normally 1–3 production files plus focused tests; if it exceeds that scope, stop and propose a split. Gate A approval covers the new package, migration and named structural file scope; implementation remains limited to the currently authorized slice.

| Slice | Prerequisites | Bounded edit surface and deliverable | Required focused proof / stop |
| :--- | :--- | :--- | :--- |
| B1 Requests | A | `workspace/__init__.py`, `requests.py`; four request/config variants, canonical identifier/version matrix, default selection builder. | Defaults frozen; Growth omissions rejected; FCF and Momentum retain distinct fields; no settings/secrets serialized. Review B1. |
| B2 Run envelope | B1 | `workspace/models.py`, `runs.py`; immutable outcome/envelope/watchlist/query types. | Invalid time/status/version/ticker and nonfinite rejection; failed-without-result supported. Review B2. |
| B3 Momentum codec | B2 | `workspace/codecs.py`, `workspace/momentum.py`; Momentum evidence round trip only. | Full context/profile/trace/optional metric fidelity; unknown/corrupt rejection. No execution integration. Review B3. |
| B4 Number codec | B3 | `workspace/graham_number.py`, explicit codec dispatch. | Number assembly/result/comparison/unit evidence round trip incl unavailable and not-applicable. Review B4. |
| B5 Growth codec | B4 | `workspace/graham_growth.py`, codec dispatch. | Growth policy/assumptions and independent result/assembly round trip; no Number coercion. Review B5. |
| B6 FCF codec | B5 | `workspace/fcf_growth.py`, codec dispatch. | Native result versions, annual observations, per-share classification, forward unavailability and profile preserved. Review B6. |
| C1 Schema | B6 | `schema.py`, new migration; disposable migration/readiness tests. | Fresh head and explicit predecessor upgrade; old data retained; normal older DB rejected; rollback and schema signature verified. Review C1. |
| C2 Watchlist repository | C1 | `repositories/watchlists.py`, `workspace/watchlists.py`. | Create/edit/idempotence/atomic conflict/order/reopen; no network calls. Review C2. |
| C3 Run repository | C1 | `repositories/analysis_runs.py`. | Four typed round trips after reopen; duplicate ID rejection; filter/tie ordering; independent cache/telemetry deletion cannot erase runs. Review C3. |
| D1 Momentum capture | C3 | Momentum adapter, minimal CLI execution extraction. | Same direct output/math; captured price inputs/profile and display derivations; fake dependencies only. Review D1. |
| D2 Number capture | D1 | Number adapter and bounded `_run_graham_number` extraction. | Existing Number CLI/output/comparison regressions; exact capture/status mapping. Review D2. |
| D3 Growth capture | D2 | Growth adapter and bounded `_run_graham_growth` extraction. | Explicit assumptions and effective policy; nonpositive growth/comparison regression. Review D3. |
| D4 FCF capture | D3 | FCF adapter and bounded CLI extraction. | Currency/provider/policy/as-of/ETF and partial metric semantics unchanged. Review D4. |
| D5 Save service | D4, C2 | `workspace/execution.py`; inject capture, ID, clock and repository. | Readiness before work; insert-before-success; persistence error visible; telemetry independent. Review D5. |
| E1 Momentum replay | D5 | `reporting/analysis_runs.py`, Momentum v1 projection helper. | All modes from reopened run with calculators/providers/settings/clock forbidden. Review E1. |
| E2 Number replay | E1 | Number v1 projection helper and dispatch. | All modes incl comparison unavailable, invalid and ETF fixtures; no recalculation. Review E2. |
| E3 Growth replay | E2 | Growth v1 projection helper and dispatch. | All modes with assumptions, negative growth and unavailable comparison; no recalculation. Review E3. |
| E4 FCF replay | E3 | FCF v1 projection helper and dispatch. | All modes, partial evidence, missing forward context; old v1 output invariant under current-settings changes. Review E4. |
| F1 Watchlist CLI | C2, E4 | `cli_workspace.py`, explicit registration in `cli.py`. | Complete CRUD subset/config/disable CLI workflow, usage validation, no provider calls, help side-effect freedom. Review F1. |
| F2 Run browsing CLI | F1, C3 | Existing workspace CLI module. | Listing/filtering and all show modes; unknown ID/version/corruption; no network/cache/clock enrichment. Review F2. |
| F3 Direct saving | F2, D5 | `cli.py`, bounded support helper if needed; add `--save-run`. | Four default commands unchanged; save IDs/streams; no-cache plus save; DB failure and typed unavailable persisted. Review F3. |
| G1 Sequential refresh | F3 | `workspace/refresh.py`; injected execution/repository, workers=1 first. | Frozen list, independent failures, saved IDs, repeated refresh distinct, per-completion durability. Review G1. |
| G2 Bounded concurrency | G1 | Same refresh service plus scoped composition only. | Max N calls, bounded admission, connection ownership, shared egress budget, immediate save visible to another connection/process. Review G2. |
| G3 Refresh CLI / interruption | G2 | Workspace CLI and refresh cancellation boundary. | Partial-failure exits, JSON isolation/counts, graceful interrupt and storage-failure stop; committed history survives. Review G3. |
| H Acceptance/docs | G3 | `README.md`, durable `docs/user/` workflow, planning evidence; integration tests only unless separately reviewed defect. | Multi-command offline scenario, all four regressions, migration/readiness, pure replay, full managed gate and explicit final acceptance. Stop before P2. |
| I1 Entry model & migration (Amendment A1, §12) | H | `workspace/runs.py`, `workspace/requests.py` (remove `default_selections`), new migration, `data/repositories/schema.py`, `data/repositories/watchlists.py`; `cli_workspace.py` narrowly (see note below). | Lossless upgrade in exact prior order; downgrade rejects a diverged watchlist rather than corrupting it; position uniqueness/duplicate-method-allowed invariants; `refresh_watchlist`'s one-line adjustment verified against G1-G3's existing test suite; `create`/`list`/`show` still work (rendering `.entries`); `add`/`remove`/`configure`/`disable` removed rather than left calling a deleted repository method. Review I1. |
| I2 Watchlist CLI surface (Amendment A1, §12) | I1 | `cli_workspace.py`: revised `create`; new `add-selection`, `remove-entry`; repurposed `remove`/`disable`; revised `show` with `--group-by`; `configure` removed. | One-command seeded creation; fan-out add; index-addressed single removal; bulk-by-ticker/bulk-by-method removal; a method's own missing required fields rejected exactly as its direct command rejects them; no `--config` file path remains anywhere. Review I2. |
| I3 Regression, docs, and final acceptance (Amendment A1, §12) | I2 | `docs/user/WORKSPACE.md`, `docs/user/GLOSSARY.md`; `tests/test_workspace_integration.py` rewritten for the new model; full managed gate. | Existing E1-E4/G1-G3 suites pass unchanged; docs and examples corrected for the new commands; full managed gate; explicit final Step 3.4 acceptance. Stop before P2. |

Do not combine adapter extraction with calculator refactoring. Codec tasks may add private serialization helpers for their own evidence; do not prebuild universal serializers. Parallel implementation is not assumed: despite shared prerequisites, use the listed order to avoid Cline editing shared dispatch/CLI files concurrently.

## 10. Cline handoff and acceptance protocol

For B1, use the [phased Cline handoff](SLICE_B1_CLINE_HANDOFF.md#phased-cline-prompts), which fixes request/selection ownership and avoids dependencies on B2 models. Send one phase prompt at a time and stop after each phase. These execution checkpoints may span Cline tasks but retain one B1 acceptance gate, the same file allowlist and all required verification. Start or resume with its read-only Phase 1 verification; preserve existing work and recorded baseline evidence. Use this instruction for later authorized tasks, replacing the slice ID:

> Implement only slice [ID] from this contract after verifying its predecessor's approval and the current branch/revision. Read AGENTS.md and the relevant source/tests. Establish the focused baseline before edits. Add meaningful deterministic tests; use injected providers/clock/IDs and disposable databases. Do not change financial math, dependencies, unrelated CLI behavior or later slices. If the frozen interface cannot work, document the concrete conflict and stop for a contract amendment. Run focused checks and the full managed quality wrapper before requesting slice acceptance. Report files, behavior, test evidence and limitations. Do not commit, push, open a PR, or start the next slice without authorization.

The full wrapper is `& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')` in PowerShell. It uses `uv run --no-sync` and unique ignored run directories. No operational database migration or real provider/LLM call is part of deterministic acceptance.

Final evidence must map every §4.10 criterion to tests: named configuration/membership; bounded fan-out and independently durable outcomes; list/show across all statuses; four-method provenance/identity/config fidelity; independent versions; deterministic historical replay; telemetry identity separation; absence of unattended services. Add explicit migration upgrade/rollback, storage error, graceful/hard interruption limitation, and direct-command compatibility evidence. Full gate must pass with coverage at least 85%; renewed ESC-D remains mandatory before Step 3.5.

## 11. Planning verification and review state

Source inspection and the initial clean-worktree check are complete. The managed baseline initially could not query the existing Python interpreter (`Access is denied`); the same non-mutating wrapper was retried with approved elevated access. The retry passed: Ruff, formatting (327 files), strict mypy (248 source/test files), and 2,338 tests in 93.08 seconds; reported combined coverage was 90% (10,984 statements, 861 missed, approximately 92.16% line coverage). Artifacts: `.tmp/quality-runs/20260913074742304-42680-39da973f436c43e5a44455b461a42545/`. Subsequent edits are planning Markdown only. No dependency synchronization or user-data migration was requested.

Slice B1 was accepted on 2026-09-13 against its [completion evidence](SLICE_B1_COMPLETION_EVIDENCE.md) (full managed gate passed, combined coverage 90%). Slice B2 was accepted on 2026-09-14 against its [completion evidence](SLICE_B2_COMPLETION_EVIDENCE.md) (full managed gate passed: Ruff, formatting, strict mypy over 255 files, 2,670 tests; combined coverage 90%; zero deviations from the B2 field spec). B3 acceptance was recorded in the B4 completion evidence. B4 was accepted and B5 implementation authorized by the project owner on 2026-09-15 (America/Toronto). B5 was accepted by the project owner on 2026-09-15 against its [completion evidence](SLICE_B5_COMPLETION_EVIDENCE.md). B6 was accepted by the project owner on 2026-09-15 against its [completion evidence](SLICE_B6_COMPLETION_EVIDENCE.md). C1 was accepted by the project owner on 2026-09-16 against its [completion evidence](SLICE_C1_COMPLETION_EVIDENCE.md). The standalone env-var casing defect fix below was sequenced and completed before C2 began. C2 implementation was authorized by the project owner on 2026-09-18 (America/Toronto) and accepted by the project owner on 2026-09-18 (America/Toronto) against its [completion evidence](SLICE_C2_COMPLETION_EVIDENCE.md). The CLI test-isolation defect fix above was completed in the same session before C3 began. C3 implementation was authorized by the project owner on 2026-09-18 (America/Toronto) and accepted by the project owner on 2026-09-18 (America/Toronto) against its [completion evidence](SLICE_C3_COMPLETION_EVIDENCE.md). D1 implementation was authorized by the project owner on 2026-09-18 (America/Toronto) and accepted by the project owner on 2026-09-18 (America/Toronto) against its [completion evidence](SLICE_D1_COMPLETION_EVIDENCE.md). D2 implementation was authorized by the project owner on 2026-09-18 (America/Toronto) and accepted by the project owner on 2026-09-18 (America/Toronto) against its [completion evidence](SLICE_D2_COMPLETION_EVIDENCE.md). D3 implementation was authorized by the project owner on 2026-09-18 (America/Toronto) and accepted by the project owner on 2026-09-18 (America/Toronto) against its [completion evidence](SLICE_D3_COMPLETION_EVIDENCE.md). D4 implementation was authorized by the project owner on 2026-09-18 (America/Toronto) and accepted by the project owner on 2026-09-18 (America/Toronto) against its [completion evidence](SLICE_D4_COMPLETION_EVIDENCE.md). D5 implementation was authorized by the project owner on 2026-09-18 (America/Toronto) and accepted by the project owner on 2026-09-18 (America/Toronto) against its [completion evidence](SLICE_D5_COMPLETION_EVIDENCE.md). D5 completes the D-series (Momentum, Number, Growth, and FCF adapters plus the save service). E1 implementation was authorized by the project owner on 2026-09-19 (America/Toronto) and accepted by the project owner on 2026-09-19 (America/Toronto) against its [completion evidence](SLICE_E1_COMPLETION_EVIDENCE.md). E1 uncovered a Momentum-specific profile-persistence gap in D5's `execute()`; the project owner authorized fixing it as an amendment to the already-accepted `AnalysisRun` model (B2) and `execute()` (D5), applied within this same E1 session and covered by the same completion evidence. E2 (Number replay) was authorized for a Cline-driven implementation attempt now that E1 is accepted. A first attempt (Cline running glm-4.7-flash) was reviewed and rejected before any acceptance: it dispatched on an incorrect method identifier, making its new code path unreachable, and its replacement presentation constructor did not match the real target dataclass's fields. That change was discarded via `git checkout` before any commit. A second attempt (Cline running qwen3.8:27b) implemented E2 correctly on the merits — correct dispatch, correct field mapping, and a sound relocation of Graham Number's/Growth's quote-reason label helpers from `cli.py` into `src/reporting/graham.py` (authorized as a narrow scope extension beyond `analysis_runs.py`/tests/docs, since it removes a duplication-drift risk that would otherwise recur identically in E3) — but review found the relocated helper was never actually invoked from the new replay path, so a stored optional-quote-failure would have replayed with a raw technical reason instead of the investor-facing sentence the live command originally showed; none of that submission's own tests exercised the `quote_status`/`quote_reason` path, so this passed a fully green gate undetected. Cline was sent a corrective follow-up naming the exact gap; the correction applied `number_with_public_quote_reason(evidence.assembly)` at the replay call site and added a regression test that verifiably fails without the fix. Both the original submission and the correction are documented in [E2's completion evidence](SLICE_E2_COMPLETION_EVIDENCE.md), which was independently verified (diff, code paths, and a from-scratch full managed-gate re-run) before acceptance. E2 was accepted by the project owner on 2026-09-19 (America/Toronto).

The project owner then authorized batching the remaining slices (E3 onward) into four review checkpoints instead of one-at-a-time, given the contract's per-slice granularity was calibrated for a local model rather than direct implementation in this session; Cline's involvement in Step 3.4 ended with E2. Batch 1 — E3 (Growth replay), E4 (FCF replay), F1 (Watchlist CLI), F2 (Run browsing CLI) — was authorized and implemented on 2026-09-19 (America/Toronto) against its [completion evidence](SLICE_E3_E4_F1_F2_COMPLETION_EVIDENCE.md); acceptance is pending project owner review. Building E3 surfaced a second retroactive gap in the already-accepted E2 code, of the same kind as the quote-reason gap E2's own correction fixed: Number's stored failure `reason` was never normalized through `friendly_graham_failure` at replay time either. That helper was relocated from `cli.py` into `src/reporting/graham.py` (the same authorized pattern as E2's quote-reason relocation) and applied retroactively to Number alongside its new use in Growth, with regression tests for both. F2's own development separately surfaced a live defect (not retroactive): `runs show` did not catch the plain `ValueError` `SQLiteAnalysisRunRepository.get()` raises for a corrupted stored row, which would have printed a raw traceback instead of the contract's required sanitized exit 1; this was found and fixed within the same batch, before requesting review. Batch 1 (E3, E4, F1, F2) was accepted by the project owner on 2026-09-19 (America/Toronto). Batch 2 — F3 (direct-command `--save-run` wiring) and G1 (sequential refresh) — was authorized and implemented on 2026-09-19 (America/Toronto) against its [completion evidence](SLICE_F3_G1_COMPLETION_EVIDENCE.md); acceptance is pending project owner review. This batch required one small additive extension to the already-accepted D5 `execute()`: an optional `batch: BatchContext | None = None` parameter stamping `refresh_id`/`batch_position`/`watchlist_id`/`watchlist_name`, fields `AnalysisRun` (B2) already defined but D5 never wired through, since batch identity was explicitly out of D5's own scope — omitted by every existing caller, leaving prior behavior unchanged. Building F3's `_maybe_save_run` helper surfaced a real defect before any test was written: its first draft constructed the workspace `AnalysisRequest`/selection eagerly as a call argument, which Python evaluates unconditionally even on the non-saving path; this broke 15 existing Graham tests that use a synthetic test-only provider id the stricter workspace selection types reject. Fixed by deferring construction to a `request_factory` callable invoked only when saving, confirmed by the full pre-existing CLI/Graham/FCF/existing-strategy-output suite passing unchanged. G1 (`src/workspace/refresh.py`) is the pure sequential service only; no CLI wiring exists yet — that is G3. Batch 2 (F3, G1) was accepted by the project owner on 2026-09-19 (America/Toronto). Batch 3 — G2 (bounded concurrency), isolated as its own review checkpoint given its distinct risk profile (races, connection ownership, admission control) — was authorized by the project owner on 2026-09-19 (America/Toronto) to begin, and was implemented the same day against its [completion evidence](SLICE_G2_COMPLETION_EVIDENCE.md); acceptance is pending project owner review. `refresh_watchlist` gained a `policy: RefreshPolicy` parameter selecting between the unmodified G1 sequential path (`workers=1`, the function's own default, distinct from `RefreshPolicy`'s own class-level default of `workers=2`, so no existing caller's behavior changes) and a new bounded-concurrent-admission path (`workers>1`): at most `workers` jobs run at once, a worker's only role is calling the injected `executor` and reporting its outcome back, and this function's own calling thread is the only thread that ever calls `execute()`/`repository.insert`, persisting one finished job before admitting its replacement. A worker measures its own `started_at`/`completed_at` around the real work in its own thread; a small `_replay_clock` helper replays those two already-measured instants through the already-accepted D5 `execute()`'s existing two-call clock contract, so the persisted run's timing reflects real work time without any further change to `execute()` itself. Every new concurrency test synchronizes via `threading.Event` and a shared causal-ordering log rather than timing guesses, per the contract's own testing requirement; one test proves immediate cross-connection visibility against real SQLite storage while a refresh is deliberately still in flight. Batch 3 (G2) was accepted by the project owner on 2026-09-19 (America/Toronto). Batch 4 — G3 (refresh CLI wiring and cooperative interruption) and H (acceptance/docs), completing the contract's full slice table — was authorized by the project owner on 2026-09-19 (America/Toronto) to begin, and was implemented the same day against its [completion evidence](SLICE_G3_H_COMPLETION_EVIDENCE.md); acceptance is pending project owner review. G3 added the contract's bare `refresh NAME [--workers N] [--json]` command to `src/cli_workspace.py`, dispatching each stored selection to its method's existing production adapter by `isinstance`, and added a cooperative `cancellation: threading.Event | None` parameter to `refresh_watchlist`/`_refresh_concurrently` (never raising `KeyboardInterrupt`, never killing a running thread — a job already admitted always finishes and persists, a job never admitted never appears in the summary). Building the dispatch executor required calling the SEC/Massive provider and Graham resolver builders (previously private to `cli.py`) from `cli_workspace.py` too; relocating them into the existing `src.cli_support` was tried first and reverted upon discovering it would have silently defeated existing tests that patch the real shared settings singleton for SEC identity, since that module's own `settings` binding is deliberately rebound for database isolation by the shared test fixture. A new module, `src/cli_composition.py`, holds these four functions instead, with its own `settings` binding never rebound by any fixture. A defect in the first draft of the cancellation logic — not removing a successfully-cancelled `Future` from the pending set, which would have crashed on `CancelledError` the first time a genuinely-queued-but-unstarted job was cancelled — was found and fixed before any test caught it. H added `docs/user/WORKSPACE.md` (linked from the user documentation index and the root README, with four new Glossary terms) and one end-to-end integration test proving the full documented workflow — create, configure, disable, add, refresh, then browse every saved run through all four presentation modes — works together offline, specifically confirming E1-E4's "no recalculation" replay guarantee also holds for a run `refresh` produced, not only one saved directly. A CLI-level test that ran a real `ThreadPoolExecutor` under `--workers 2` through Click's `CliRunner` was found to trigger a rare, Windows-specific test-harness race unrelated to refresh's own correctness (already exhaustively proven concurrent-safe directly against `refresh_watchlist` in G2/G3's own tests); removed and every CLI-level test pinned to `--workers 1` instead. With G3 and H implemented, every slice in the contract's table has been implemented; per the contract's own sequencing, P2-Profiles, ESC-D renewed acceptance, and Step 3.5 are separate, subsequent items not started in this batch.

**Defect: env-var casing in subprocess environment (found during C1 review).**
While reviewing Slice C1 completion evidence on 2026-09-16 (America/Toronto),
`tests/test_cli_database_readiness.py:168` and `tests/test_readiness.py:260`
were found to set `DATABASE_URL` and `TELEMETRY_LEVEL` uppercase when
constructing a subprocess environment dict. This passes locally only because
Windows' environment-variable lookup is case-insensitive; it is fragile
against the project's `case_sensitive=True` settings convention and would be
expected to silently break under a POSIX GitHub CI runner. The defect is
test-only, independent of C1's schema/migration scope, and is not part of
C1's accepted evidence or proof obligations.

Authorized as a standalone fix task, scoped to: confirming the ground-truth
casing from the settings definition; correcting both identified test files
plus any other code location (tests, scripts, CI workflow files) found to
depend on the same incorrect casing; and syncing Markdown documentation that
shows the incorrect casing in a form a reader could copy-paste and run. Also corrected a stale uppercase env-var reference in the UPGRADE_REQUIRED error message itself (production code), not only test scaffolding. No
production schema/migration code, dependencies, or Slice C2/C3 work is in
scope. Sequenced after C1 acceptance and before C2 begins, so the corrected
convention is established before further CLI/subprocess-driven tests are
added.

**Defect: pre-existing Momentum/Graham CLI test failures (found during the C2 full-gate run).**
The full managed wrapper run for C2 surfaced 31 pre-existing failures confined
to `tests/test_cli.py`, `tests/test_cli_graham_nonpositive_growth.py`,
`tests/data/test_massive_cli_configuration.py` and
`tests/test_graham_growth_default_policy.py`. Reverting to the pre-C2 working
tree and rerunning one representative test reproduced the identical failure,
confirming this predates C2 and is unrelated to its edit surface.

Root cause, confirmed by direct reproduction with a full traceback (not
inferred): `src/cli_support.py`'s `_production_historical_client` and
`_production_financial_cache` both call `ensure_database_ready()` against the
real local database at the default `database_url`
(`data/financial-data-agents.sqlite3`), not an isolated or mocked one. Slice
C1 added migration `0002_research_workspace` as the new schema head; this
machine's real local database file predates that migration and was never
upgraded, so `ensure_database_ready()` now correctly raises
`DatabaseReadinessError(UPGRADE_REQUIRED)`, which the CLI's `execution_errors`
handler converts to `typer.Exit(code=1)` — matching every failing test.
`tests/test_cli_fcf_earnings_growth.py` is unaffected because it already
patches `src.cli._production_financial_cache` to an in-memory cache instead of
touching real storage; the 31 failing tests do not patch either production
context manager and so fall through to the real, stale database.

This is not a logic defect: readiness is behaving exactly as designed. It is
a test-isolation gap — these tests implicitly assumed an always-ready ambient
database and had never been exercised against a newer migration before. Two
independent remediations exist: (1) an operational one-time
`alembic upgrade head` against the real local database (a migration against
user data; requires the project owner's explicit action, not an agent's), and
(2) a durable test fix making the affected CLI tests database-isolated the
same way `test_cli_fcf_earnings_growth.py` and `test_cli_database_readiness.py`
already are.

**Resolved:** remediation (2) was applied directly in this session, at the
project owner's request, after an initial attempt to spin the fix off into a
separate isolated-worktree session found the failure was not reproducible
there — a fresh worktree has no ambient local database file at all, so a new
one initializes cleanly at the current head and the failure's precondition
never exists, which would have left any fix there unverifiable against the
real symptom. A shared `isolated_cli_database` autouse pytest fixture was
added to `tests/_cli_helpers.py`: it migrates a disposable SQLite database to
head and points `src.cli_support.settings` at it via `monkeypatch`, exactly
mirroring the isolation pattern already used by
`tests/test_cli_historical_cache.py` and `tests/test_cli_financial_cache.py`.
The four affected test modules import that fixture name (activating it for
every test in each module, per pytest's normal cross-module fixture sharing)
instead of relying on the real ambient database. The full managed gate now
passes: Ruff, format and strict mypy clean, all 2,879 tests passing, 90%
combined coverage. Remediation (1) — upgrading the real local database itself
— remains a separate, optional operational step for the project owner and was
not performed by the agent.

## 12. Contract Amendment A1 — Watchlist Entry Model

**Status:** authorized by the project owner on 2026-09-19 (America/Toronto);
implementation not yet started (slices I1-I3 below).

**Trigger.** Reviewing H's own `docs/user/WORKSPACE.md` deliverable
(2026-09-19) surfaced that §3's "selections are watchlist-wide" model does
not serve users well: watchlist creation materializes three methods a user
did not choose (§3's original third bullet — Momentum, Graham Number, and
FCF/Earnings Growth were simply the first three methods this project
happened to implement, not a considered default set), the same method
cannot be configured differently for different tickers or compared across
providers on one watchlist, and per-method configuration required writing a
JSON file to disk before running a command (§3's original fourth bullet).
Per §10's own protocol — "If the frozen interface cannot work, document the
concrete conflict and stop for a contract amendment" — this is that
amendment, discovered during H's own review before final Step 3.4
acceptance was granted. It supersedes §3's second, third, and fourth
bullets and the file-based config-JSON paragraph in the "Method/config
matrix" subsection (each struck through in place with a pointer to this
section). §3's other provisions — ticker/name normalization, `AnalysisRequest`'s
shape, the method/config canonical-identifier matrix itself, snapshot/redaction
rules, and refresh's frozen-read/no-dedup semantics — are unchanged.

**New model.** A watchlist holds one ordered list of entries, not two
separate properties. Each entry is `{position, ticker, selection}`:
`position` is a stable ordinal unique within its watchlist. Stored/internal
`position` stays 0-based, matching the existing `watchlist_members`/
`watchlist_selections` position-column convention it replaces; every
user-facing surface (`watchlist show`'s display and the `INDEX` argument to
`remove-entry`) instead shows and accepts a 1-based number derived from it
(displayed index = `position + 1`; a supplied index N addresses stored
`position` N-1) — a non-technical investor reads and counts entries as an
ordinary numbered list, never a zero-based one. `ticker` and `selection` are
exactly as validated today. The same method may appear more than once
within a watchlist (different tickers, or the same ticker with a different
provider/config); the previous "one selection per method" constraint is
removed. `refresh`/execution read the entry list directly; there is no
implicit cross product of two separate lists.

**Creation.** `watchlist create NAME` with no further arguments creates an
empty watchlist — zero entries, no method materialized by default.
`watchlist create NAME --analysis METHOD [method-specific flags] TICKER...`
additionally seeds the new watchlist with one entry per given ticker for
that method, in the same command. Method-specific flags mirror the
corresponding direct command's own flags exactly, including which are
required (for example, `graham-growth` requires `--expected-growth`/
`--aaa-yield` here exactly as the direct command already requires them); a
method missing a required flag is a usage error exactly as the direct
command's own validation already produces — no separate "unsupported at
creation" rejection list is needed.

**Editing.** `watchlist add-selection NAME --analysis METHOD
[method-specific flags] TICKER...` appends one entry per given ticker to an
existing watchlist — the same one-command fan-out as creation, for the
common single-method/multiple-ticker case. `watchlist remove-entry NAME
INDEX` removes exactly one entry by its displayed 1-based index (as shown by
`watchlist show`). `watchlist remove NAME
TICKER...` removes every entry for the given ticker(s) (bulk, across every
method — preserving the old command's bulk convenience). `watchlist disable
NAME --analysis METHOD` removes every entry for the given method (bulk,
across every ticker — likewise preserved). `watchlist configure` and its
file-based `--config PATH` are retired; there is no in-place edit of one
entry's configuration — replace it with `remove-entry` followed by
`add-selection`.

**Display.** `watchlist show NAME [--group-by ticker|method] [--json]`;
default `--group-by ticker`. Text output groups entries under their ticker
(or method, if requested) for readability; `--json` emits the flat, ordered
entry list, each carrying the same 1-based `index` a human sees and would
type back into `remove-entry` — not the raw internal 0-based `position` —
so there is one number to learn across text, JSON, and command input alike.

**Persistence.** A new migration replaces `watchlist_members`/
`watchlist_selections` with one `watchlist_entries` table: `(watchlist_id,
position)` primary key, `ticker`, `method_id`, `config_schema_version`,
`selection_json` columns, matching the existing schema's non-blank/
JSON-object check-constraint conventions. Upgrade is lossless: every
existing watchlist's member-position-then-selection-position cross product
becomes its entries list in that exact order, so no watchlist created under
the old model changes behavior. Downgrade is the inverse where the data
still forms a clean cross product; a watchlist that has since diverged
(duplicate methods, gaps) cannot roll back losslessly, and the downgrade
must fail loudly rather than silently drop data, matching C1's own
established "reject rather than corrupt" convention.

**Effect on already-accepted work.** `refresh_watchlist` (G1) changes by one
line — the job list is read directly from `watchlist.entries` instead of
computed as a cross product of `members`/`selections`. G2 (bounded
concurrency), G3 (cancellation, CLI wiring, exit codes, output format), D1-D5
(adapters/save service), and E1-E4 (replay) are unaffected: all operate on
one `(ticker, selection)` pair, or an already-flattened job list, never on
the watchlist's own internal shape.

**I1/I2 boundary clarification (found during I1 planning, authorized by the
project owner on 2026-09-19).** `cli_workspace.py`'s existing `add`/`remove`/
`configure`/`disable` commands call repository methods
(`add_members`/`remove_members`/`set_selection`/`disable_selection`) that
have no coherent meaning once a ticker only exists as part of an entry —
there is no interim shape that preserves their old behavior without
prejudging I2's own command design. I1 therefore removes those four
commands outright (rather than leaving them calling a deleted repository
method, or building a throwaway interim semantic), keeping `create`/`list`/
`show` working and adapted to render `.entries`. Watchlist add/remove/
configure/disable are unavailable for the short window between I1 and I2;
I2 restores equivalent and expanded capability under the new command names
(`add-selection`, `remove-entry`, repurposed `remove`/`disable`, `show
--group-by`).

**Deferred, not included in this amendment.** Watchlist rename and delete
were separately flagged during this review as a plain missing-CRUD gap;
they are not part of Amendment A1 and remain open for a future, separately
authorized change. The `--analysis` alias vs. canonical `method_id`
vocabulary inconsistency across commands (`watchlist configure/disable`
use hyphenated aliases; `runs list --method` uses the canonical identifier)
was also separately flagged and is likewise not addressed here. Neither
gap blocks I1-I3.

Final Step 3.4 acceptance (previously targeted at H) is deferred until I3
(see §9's slice table) completes. P2-Profiles, ESC-D renewed acceptance, and
Step 3.5 remain unstarted until then, per §1's existing sequencing note.

I1 (entry model, repository, migration) was implemented on 2026-09-19
(America/Toronto) against its [completion evidence](SLICE_I1_COMPLETION_EVIDENCE.md)
and accepted by the project owner the same day. `Watchlist.members`/
`.selections` became one `entries: tuple[WatchlistEntry, ...]` field
(`src/workspace/runs.py`); `default_selections()` was removed
(`src/workspace/requests.py`); the repository (`src/data/repositories/watchlists.py`)
was rewritten around `add_entries`/`remove_entry`/`remove_entries_for_ticker`/
`remove_entries_for_method`, renumbering survivors contiguously on every
removal so the amendment's `displayed index = position + 1` rule never
drifts from stored positions; a new migration, `0003_watchlist_entries`,
replaces `watchlist_members`/`watchlist_selections` with one table,
upgrading existing watchlists losslessly (their old cross product becomes
their entries list in the same order) and rejecting rather than corrupting
a downgrade of a watchlist that has since diverged from a clean cross
product. Implementing I1 surfaced that `cli_workspace.py`'s `add`/`remove`/
`configure`/`disable` commands call repository methods with no coherent
replacement under the new model; the project owner authorized removing
those four commands outright within I1 (rather than an interim shim or
merging I1/I2), keeping `create`/`list`/`show` working and adapted to the
new model, with I2 restoring equivalent and expanded capability under new
command names. `refresh_watchlist` (G1) changed by one line; G2/G3/D1-D5/
E1-E4 were unaffected. Full managed gate: 3,056 tests passed, 91% combined
coverage, with `cli_workspace.py`, the rewritten repository, the schema
module, and `runs.py` all at 100% line/branch coverage.

I2 (watchlist CLI surface) was implemented on 2026-09-19 (America/Toronto)
against its [completion evidence](SLICE_I2_COMPLETION_EVIDENCE.md) and
accepted by the project owner the same day. Entirely within
`src/cli_workspace.py`:
`create` gained an optional `--analysis METHOD [flags] TICKER...` seeding
form; a new `add-selection` command provides the same one-command fan-out
for an existing watchlist; `remove-entry NAME INDEX` removes one entry by its
displayed 1-based index; `remove`/`disable` are repurposed onto the
repository's bulk-by-ticker/bulk-by-method removal methods; `show` gained
`--group-by ticker|method` and its `--json` output now carries an explicit
1-based `index` per entry rather than the internal 0-based `position`.
Method-specific flags mirror each direct command's own flags and validation
exactly, including graham-growth's required `--expected-growth`/
`--aaa-yield`; no `--config` file path exists anywhere in the module. Full
managed gate: 3,086 tests passed, 91% combined coverage, with
`cli_workspace.py` at 100% line/branch coverage.

I3 (docs, test revisit, full regression) was implemented on 2026-09-20
(America/Toronto) against its [completion evidence](SLICE_I3_COMPLETION_EVIDENCE.md)
and accepted by the project owner the same day, carrying explicit final Step
3.4 acceptance per its own §9 acceptance criteria — Step 3.4 is now complete,
including the G3/H review that had remained outstanding since batch 4.
`docs/user/WORKSPACE.md`'s "Watchlists" section and
`docs/user/GLOSSARY.md`'s `Selection`/`Watchlist`/`Refresh` entries (plus a
new `Entry` entry) were rewritten around the entry model and I2's commands,
retiring the default-selection-materialization and file-based `--config`
examples; `tests/test_workspace_integration.py`'s one full-workflow scenario
now seeds its entries through the real `watchlist create --analysis`/
`add-selection` commands instead of I1/I2's interim direct-repository
seeding. Full managed gate: 3,086 tests passed, 91% combined coverage,
identical to I2's run, confirming every previously-accepted slice's tests
are unaffected. Amendment A1 (I1, I2, I3) is now complete end to end.

**Related UX fixes made on this branch after I3, before final acceptance.**
None of the following are Amendment A1 slices or otherwise part of this
plan's own sequencing; each was raised, scoped, and separately authorized
in conversation, gated with its own full managed run, and is recorded here
only so this plan's history stays complete:

- `financial-agents graham-number ... --save-run` against a database
  needing a schema upgrade produced a message recommending raw `alembic`
  over the project's own `financial-agents db upgrade`, using `--no-sync`
  (a managed-agent-only convention), and omitting the target revision.
  `src/data/repositories/readiness.py`'s `UPGRADE_REQUIRED` message was
  rewritten to recommend `db upgrade`, name the target revision, and
  correctly scope its concurrency caution to a single local SQLite file.
- `runs show`/`runs list --refresh-id` given a shortened or mistyped
  Analysis Run ID produced a message that did not say what a valid ID
  looks like or name the affected parameter. `_parse_run_id` in
  `src/cli_workspace.py` now states the expected format, points to `runs
  list`/`refresh` for a valid ID, and carries a `param_hint`. Git-style
  prefix matching for Analysis Run/refresh IDs was considered and
  deliberately deferred; see
  [DEFERRED_RUN_ID_PREFIX_MATCHING.md](../DEFERRED_RUN_ID_PREFIX_MATCHING.md).
- A broader structured-error-reporting gap for programmatic/agentic CLI
  consumers was identified while reviewing the message above (a stable
  `reason_code` exists, but `expected_revision`/`database_path` are not
  exposed as JSON fields, and workspace commands have no JSON error
  envelope at all). Deliberately deferred, not fixed on this branch; see
  [DEFERRED_STRUCTURED_ERROR_REPORTING.md](../DEFERRED_STRUCTURED_ERROR_REPORTING.md).
- `refresh` always saved every result with no opt-out, unlike direct
  commands' opt-in `--save-run`. After considering and rejecting the
  reverse change (defaulting direct commands to save, which would leave
  every exploratory invocation as a permanent, undeletable row — Analysis
  Runs have no delete/prune capability), `refresh` gained a `--no-save`
  preview option instead. `RefreshJobResult` (`src/workspace/refresh.py`)
  gained a third `outcome` state (executed, not persisted) alongside its
  existing `run`/`error` states, threaded through both the sequential and
  concurrent admission paths; `cli_workspace.py`'s refresh rendering shows
  `(not saved)` in place of a fabricated run ID. Full managed gate: 3,092
  tests passed, 91% combined coverage.
- `docs/user/WORKSPACE.md` gained a "Saving vs. caching" section
  disambiguating the two concepts for a non-technical reader (with a plain
  ASCII flow diagram), and "Showing a watchlist" was reordered to
  immediately follow watchlist creation — both to fix a reading-order
  problem where later sections referenced concepts (watchlists, refresh)
  before they were introduced.
