# Step 3.3 — Data Quality & Cache Invalidation Contract and Slice Plan

**Status:** Companion plan approved and Step 3.3 implementation explicitly authorized on 2026-09-07. A reconciliation and the baseline are complete. B pure quality rules and focused tests are implemented; verification and review evidence are recorded below. Gate B review passed on 2026-09-08; C cache/refresh and trajectory integration is implemented and verified. The full managed quality gate passed on 2026-09-08 (1,944 tests, 89% coverage); Step 3.3 final acceptance is recorded in [Implementation Plan §4.9](../IMPLEMENTATION_PLAN.md#49-step-33--data-quality--cache-invalidation-pipeline).

**Branch:** `feat/step-3.3-data-quality`, verified active at local head `ef60a4b` with a clean working tree before this documentation change.

**Authority:** [Implementation Plan, Step 3.3](../IMPLEMENTATION_PLAN.md#49-step-33--data-quality--cache-invalidation-pipeline). The [Master Plan](../../../MASTER_PLAN.md) supplies roadmap scope; [financial mathematics](../../../../user/FINANCE_MATH.md) remains authoritative for calculation semantics.

**Approval record:** On 2026-09-07 the project owner confirmed that the branch had been created and requested that approval to begin Step 3.3 be recorded and the necessary additional documentation prepared. This confirms the prior next-step authorization following Issue #17 acceptance. That initial request authorized documentation preparation. Subsequently, on 2026-09-07, the project owner stated, “Approved; Step 3.3 implementation authorized. Record & suggest checkpoint commit description.” This approves this companion plan and authorizes implementation within its scope. Complete outstanding A detail and baseline work before production edits; no repeat start/implementation authorization is required within the accepted scope. Implementation review gates and final acceptance remain applicable. This approval does not assert that unfinished reconciliation or implementation has passed verification, authorize later work packages, or request execution of a commit, push, or PR.

## 1. Scope and preservation

Validate incoming historical prices and financial facts, enforce explicit freshness and compatibility decisions before cache writes and downstream use, control refresh/invalidation, and expose quality failures through execution trajectories. Preserve Momentum and each financial strategy's existing mathematics, override precedence, historical `as_of` eligibility, provenance, and classified unavailability.

Reuse the existing clients, resolver, cache contracts, SQLite repositories, settings, reliability limits, and telemetry recorder. Do not introduce a generic validation registry, duplicate cache hierarchy, hidden network retries, schema migration, dependency change, or new CLI surface. Durable instrument profiles belong to P2-Profiles; watchlists and Analysis Runs belong to Step 3.4. Automatic FX conversion, corporate-action reconstruction, new provider mappings, and unattended refresh are not implied.

## 2. Initial source reconciliation

Paths below are repository-relative. This is an initial source inventory; A must finish call-path and test reconciliation before freezing exact interfaces.

| Existing boundary | Observed behavior | Remaining reconciliation/work |
| :--- | :--- | :--- |
| `src/data/cached_client.py` | Validates fetched frames for non-empty Close and finite numeric observations, including storage bypass. Uses exact request keys and injected TTL/clock; no stale error fallback. Current quotes delegate directly to the provider. | Validate cache-hit eligibility against quality policy; add continuity/context rules and explicit decisions without converting historical fetches into quote APIs. |
| `src/data/market_data.py` | Retains optional currency, interval, adjustment basis, observation count, and observation date. | Separate contradictory metadata from absent evidence; do not claim complete calendar or corporate-action validation from these fields alone. |
| `src/data/repositories/market_data.py` | Validates finite persisted observations and provides typed historical storage. | Preserve storage representation checks; keep business quality policy outside SQL encoding. |
| `src/data/financial/cache.py`, `src/data/repositories/resolved_input_cache.py` | Typed identity/period bounds, provenance, TTL and temporal eligibility already exist. Concrete inspection can expose stale/ineligible entries administratively. | Preserve normal read eligibility and distinguish administrative inspection from usable analytical inputs; decide bounded invalidation behavior. |
| `src/data/financial/resolver.py` | Already validates temporal availability and compatibility for selected financial inputs, including currency, period, share-class and split metadata. | Reuse existing checks; audit scalar, derived, and series paths rather than impose one strategy's requirements on every fact. |
| `src/data/financial/production.py` and production composition | Existing provider/cache composition is the integration seam. | Enumerate actual fetch/write paths, TTL configuration owners, bypass paths, and retry ownership before selecting changed files. |
| Trajectory recorder and repository | Existing sanitized, fail-open event persistence; Issue #17 regression coverage is present in local merged commit `ef60a4b` (`#31`). | Select a compatible typed quality-decision payload/event path and prove trace linkage. Local Git history does not independently confirm remote issue closure. |

Relevant existing regression suites include `tests/data/test_cached_client.py`, `tests/data/repositories/test_market_data.py`, `test_resolved_input_cache.py`, `test_series_cache.py`, and `test_persistence_smoke.py` in that repository-test directory. A must enumerate resolver/provider and telemetry tests needed for the selected paths.

## 3. Approved quality contract

Every evaluated rule should produce a typed decision with rule identifier, outcome, reason, affected input/cache identity, and relevant observation/retrieval/analysis timestamps. Distinguish pass, failure, and insufficient evidence. Insufficient evidence must never be labeled a verified pass; whether it blocks a particular use depends on that use's required evidence. Keep secrets and raw provider payloads out of diagnostic metadata.

| Rule family | Approved behavior | Detail to resolve during A |
| :--- | :--- | :--- |
| Structural/numeric validity | Reject empty required series, missing required values, and NaN/Inf before writes and analytical use; never fill missing observations with zero. | Required columns and index invariants per supported payload. |
| Continuity/missing bars | Detect duplicate/out-of-order dates and missing expected observations where a supported session schedule is available. Never infer that every weekday is a trading session or interpolate missing prices silently. | Calendar/evidence source, supported intervals, request endpoints, holidays, suspensions, partial sessions, and unknown-calendar outcome. No new dependency without permission. |
| Currency/units | Reject incompatible currencies or units when combining inputs; retain explicit missing metadata. | Required evidence by operation; CAD/USD mismatch cases; no automatic FX conversion without a separately specified rate/date/provenance contract. |
| Corporate actions | Preserve declared adjustment basis and reject demonstrably incompatible split/share bases. Do not infer a split solely from a large price move or adjust an already adjusted series again. | Supported provider evidence, unknown basis behavior, and adjustment consistency across compared inputs. |
| Financial periods | Preserve existing method-specific duration/instant, fiscal-period, availability, and series compatibility checks. Reject incompatible combinations explicitly. | Scalar/series/derived path coverage, restatements, annual versus interim facts, and historical availability boundaries. |
| Freshness | Separate cache residence age from observation/reporting age and historical analysis eligibility. Refresh an expired eligible request through the existing guarded provider path. | Typed defaults per data capability, equality boundaries, future timestamps/clock skew, market closures, and historical requests. Existing TTL semantics must not change accidentally. |

### Cache and refresh lifecycle

1. Evaluate a candidate cache hit for the requested analytical use; administrative inspection does not establish eligibility.
2. If eligible, preserve the stored evidence and original timestamps. Otherwise record why it cannot be reused and follow the existing guarded fetch path.
3. Validate fetched data before writing or returning it as usable. Invalid refresh output must not replace a valid stored snapshot or cause stale fallback.
4. Prefer logical exclusion and validated replacement over destructive deletion. A must specify how a rejected stored entry stays excluded on later requests and after reopen; do not claim durable invalidation from a transient flag.
5. Keep provider retries within existing timeout/circuit-breaker ownership. Do not add an unbounded quality-triggered re-fetch loop. Classify deterministic incompatibility separately from transient transport failure.
6. Emit quality failures with run/span linkage through the existing sanitized recorder. Telemetry failure must not change the quality decision or business outcome. Direct calls without a recorder still enforce quality rules.

## 4. Approved implementation slices and review gates

The project owner approved this handoff and authorized Step 3.3 implementation on 2026-09-07. The current recording task prepares the documentation checkpoint; execution begins with outstanding A reconciliation and baseline work. Review gates for implemented slices and final acceptance remain in force.

| Slice | Deliverable | Exit gate |
| :--- | :--- | :--- |
| 3.3-A — Reconciliation and contract | Complete fetch/read/write inventory, existing-test mapping, exact typed interfaces/file scope, policy defaults and all review details in section 3; fresh managed baseline before refactoring. | Plan accepted and implementation authorized on 2026-09-07. Finish and record concrete contract details and baseline evidence before B; material scope changes require review. |
| 3.3-B — Rules and focused tests | Implement accepted deterministic rules/configuration and regression tests for boundary conditions; reuse existing checks. | Review bounded diff, focused tests and full managed gate before C. |
| 3.3-C — Cache/refresh and trajectory integration | Apply rules to approved fetch/cache paths, controlled refresh and exclusion, transparent quality failures, and preserved fail-open telemetry. | Review lifecycle, reopen/rollback and reliability evidence plus full managed gate before D. |
| 3.3-D — Acceptance and documentation | Reconcile acceptance evidence and durable behavioral documentation with implemented contracts; final managed gate. | Explicit final acceptance before marking Step 3.3 complete. Later packages remain separate. |

## 5. Verification and acceptance matrix

Use synthetic data, injected clocks, mocked providers/LLMs, and migrated temporary SQLite databases. Never use real user databases, production cache fixtures, or live external calls in deterministic tests.

| Acceptance criterion | Required evidence |
| :--- | :--- |
| Documented quality rules with clear pass/fail behavior | Every accepted rule has valid, invalid, missing-evidence and applicable boundary cases; defaults and temporal conventions match implementation. |
| Stale/invalid data cannot silently become analytical truth | Cache hit/miss/expired/rejected, bypass, fetched-invalid, failed-refresh, historical-as-of, scalar/series/derived input and reopened-database cases. Prove no invalid write, silent zero fill, stale fallback or unbounded re-fetch. |
| Failures appear transparently in trajectories | Rule/reason and affected-input identity linked to the execution; sanitized serialization/readback; recorder failure leaves rejection/refresh outcomes unchanged. |
| Existing behavior remains valid | Momentum and heterogeneous strategy regressions, quote separation, provenance, supported TTL boundaries, repository round trips and reliability limits remain green. |

Complete non-mutating gate from the repository root:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

Record revision, date, Ruff/format/mypy results, pytest counts, coverage and ignored artifact location for each implementation gate. No fresh code baseline is claimed by this documentation-only handoff. The accepted predecessor record reports 1,870 tests and 89% coverage; that is historical evidence, not a new run.

## 6. Approved pre-implementation handoff (historical snapshot)

- Start approval and branch: recorded and verified on 2026-09-07.
- Companion plan, rule matrix, slices and verification requirements: approved on 2026-09-07; Step 3.3 implementation authorized.
- Exact interfaces, complete call-path audit, policy details and fresh baseline: outstanding in A under the granted implementation authorization.
- Production code, tests, dependencies, database contents and public behavior: unchanged by this preparation.
- Step 3.3 acceptance checkboxes remain open. Implementation review gates and final acceptance have not been completed.

## 7. A reconciliation and concrete B contract — 2026-09-07

The project owner instructed execution after checkpoint `a8f3297`. The fresh managed baseline passed: Ruff, formatting (287 files), strict mypy (224 source files), and 1,870 tests in 34.69 seconds; reported combined coverage 89% (9,422 statements, 775 missing). Artifacts: `.tmp/quality-runs/20260907215128926-40504-411e86c57c2141c2a07dc8a7b43e55ef/`. The first sandboxed attempt could not query Python; the same non-mutating wrapper passed with approved interpreter access. Dependencies were not synchronized.

### Call paths and ownership

- Historical production composition is `src/cli_support.py::_production_historical_client` → `CachedHistoricalDataClient` → `YFinanceClient.fetch_historical_data` (base-client delegation to context fetch) → repository `put`. Cache hits currently skip `_validate_data`; unknown identity/variant bypasses storage but validates fetched numeric data. Current quotes delegate separately. `ProjectSettings.historical_cache_ttl_seconds` defaults to 3,600 seconds; `None`, zero, equality and negative clock-drift behavior are already tested and remain unchanged.
- `InputResolver` owns scalar provider fetch/validation/write, three-year EPS candidate selection/derived write, and BVPS component resolution/derived write. `ProviderFact` already enforces finite values, field-specific units, currency and aware timestamps. Existing resolver helpers retain method-specific alignment, earnings basis/share-class/split checks, historical availability and derivation policy.
- `src/analysis/strategy/fcf_earnings_growth/input_resolver.py::_resolve_field` separately owns annual cache-series reads, complete-field provider fetch, selection and period-scoped writes. `_fact_rejection`, `_select_provider_facts`, `_assemble_common` and existing models retain annual period/currency/accounting compatibility and restatement selection. Its cached-series branch must be included in C; it is not covered by changing `InputResolver` alone.
- `ProductionFinancialFactsProvider` routes requests to SEC, Massive and Yahoo adapters; it owns no persistence or independent retry loop. Evaluation adapters and fixture providers stay deterministic. In-memory and SQLite financial caches preserve their existing TTL/availability contracts; `_production_financial_cache` currently selects no TTL. C must expose any configurable financial cache-age policy without silently inventing a default reporting-age cutoff.
- Repositories remain storage/encoding owners; policy exclusion occurs on every normal analytical read, including after reopen. A rejected stored snapshot may remain available to explicit inspection; replacement happens only after fetched data passes. No persistent stale flag, deletion, schema change or migration is required. Expired/rejected refresh failures cannot supply the old snapshot to analysis.
- C will emit typed quality decisions through the existing recorder's `TrajectoryRecord`/`ERROR` payload and run/span identity; it must not make quality depend on recording. No new event enum/storage format is required. Existing execution composition must supply the recorder at integration, with direct no-recorder calls still enforcing the same checks.

Regression owners: `tests/data/test_cached_client.py`, repository market/cache/series suites; `tests/analysis/graham_value/test_resolver.py`, `test_cache.py`, `test_sec_bvps_hardening.py`; `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_input_resolver.py` and model/calculator suites; `tests/analysis/shared/test_financial_resolution.py`; `tests/core/telemetry/test_telemetry.py`, `test_sqlite_sink.py`; CLI cache composition and orchestrator reliability suites.

### B interfaces and policy decisions

Add only `src/data/quality.py` and `tests/data/test_quality.py`, plus this planning evidence. B supplies pure rules and typed configuration; C owns connection to existing runtime paths. No public method is removed or changed in B.

- `QualityOutcome`: `pass`, `fail`, `insufficient_evidence`. Immutable `QualityContext(input_id, evaluated_at, analysis_as_of=None, retrieved_at=None)` carries input identity and aware execution/analysis/retrieval times. `QualityDecision(rule_id, outcome, reason, context, evidence_at=None)` is the result of each rule; freshness decisions retain the exact evaluated timestamp in `evidence_at`. Missing optional evidence is not a pass and is not itself a blanket rejection; required evidence is rejected by the applicable rule.
- `HistoricalQualityPolicy` optionally declares expected currency, adjustment basis, and an explicit tuple of expected daily session dates. Defaults are `None`; no calendar library or weekday inference is introduced. Session evidence must be supplied for the exact request by the caller; daily sessions detect missing dates, not intraday gaps. An empty supplied schedule is invalid configuration. With no schedule or unsupported interval, continuity coverage reports insufficient evidence. Duplicate/missing/out-of-order DatetimeIndex values fail; unsupported non-date indexes report insufficient evidence, preserving representation-bypass compatibility. Numeric validation requires nonempty Close and finite values in supplied OHLC/adjusted-close/volume columns; duplicate columns and complex/bool observations fail. No interpolation, sorting or frame mutation.
- `evaluate_historical_quality(data, *, context, policy=...)` returns decisions for numeric validity, index order, context count/date coherence, currency, adjustment and expected sessions. Currency/adjustment with known contradictory evidence fails; absence reports insufficient evidence. A known adjustment label is evidence of basis, not proof that every corporate action is correct. Existing strategy requirements determine whether unknown currency/basis blocks an operation.
- `FreshnessPolicy(cache_ttl=None, observation_max_age=None)` keeps residence-age and observation-age checks separate. `evaluate_freshness(*, context, policy, cached_at=None, observed_at=None, available_at=None)` evaluates TTL, observation time/age and availability. Thresholds are nonnegative timedeltas; equality passes. Disabled age limits or missing observations report insufficient evidence. Historical observation age uses requested `as_of`, not wall-clock age; historical availability is mandatory and must not exceed `as_of`. A future observation or availability fails. Future cache insertion time reports insufficient evidence (clock drift), retaining existing nonpositive-age cache semantics rather than converting it into silent verified freshness. Retrieval after historical `as_of` is allowed and never used as availability evidence.
- Existing financial currency/unit/period and split checks remain with their strategy owners; B does not duplicate or generalize them. C consumes the shared temporal decisions alongside those checks on provider and cache paths. No assumed annual reporting deadline, FX rate, or corporate-action correction is added.

These details complete A's bounded policy/interface reconciliation under the granted authorization. B may proceed. Gate B remains a review point before C runtime integration.

## 8. B implementation and verification — 2026-09-08

**Status:** Implemented and verified; Gate B review pending. C integration and D acceptance have not started. Work resumed after a usage-limit interruption; the A baseline and original authorization remain valid.

`src/data/quality.py` implements the pure typed decision/context/policy contracts and historical/freshness rule functions specified above. Decisions preserve input identity and evaluation context; freshness decisions also retain the exact timestamp evaluated. Rules neither mutate frames nor call providers, repositories or telemetry. Existing financial period/currency/unit/split checks remain with their current strategy owners. No runtime behavior is changed until C connects these rules to the audited read/fetch/write paths.

`tests/data/test_quality.py` adds 61 deterministic cases covering valid data, empty/missing/duplicate columns, NaN/Inf, nullable and mixed numeric types, unsupported/date indexes, ordering and missing dates, context contradictions, currency/adjustment conflicts, explicit daily session gaps, intraday limitations, exchange-local dates, TTL equality/zero/disabled limits, clock drift, historical observation/availability boundaries, invalid configuration and retained evidence. The initial test collection failed as expected before the new module existed. The focused suite subsequently passed; the new module has 100% line and branch coverage (133 statements, 72 branches).

The complete managed wrapper passed on `a8f3297` plus the uncommitted B changes on 2026-09-08:

- Ruff clean; formatting clean (289 files); strict mypy clean (226 source files).
- **1,931 tests passed in 40.54 seconds**, an increase of 61 from the 1,870-test baseline; no existing tests removed.
- **89% reported combined coverage**; 9,555 statements, 775 missing, 3,052 branches, 496 partial branches. The added module accounts for all 133 additional statements and 72 additional branches.
- Ignored artifacts: `.tmp/quality-runs/20260908172132293-19096-b5486d5732ab4c3c98915a08fb84477b/`.
- Whitespace and planning-link checks passed. Dependencies, schema, migrations, provider adapters, financial calculations and existing public interfaces are unchanged. No commit, push or PR was performed.

**Review handoff:** Review this concrete B diff and verification evidence before C, as required by the approved slice table: “Review bounded diff, focused tests and full managed gate before C.” Runtime cache exclusion, refresh, provider/financial-series integration and quality-failure trajectory evidence remain C deliverables; these are not claimed complete by the pure-rule tests. Gate B approval and Step 3.3 final acceptance are not inferred from passing verification.

## 9. Gate B approval and C execution — 2026-09-08

The project owner stated, “Gate B review passed. Slice 3.3-C authorized, proceed.” This closes Gate B and authorizes cache/refresh and trajectory integration. Gate C review and D closeout remain separate.

C uses the green B baseline (1,931 tests) recorded above. The integration adds normal-read historical validation and controlled replacement, shared financial temporal checks in the scalar/derived and annual-series consumers, configurable financial cache residence age (unlimited by default), and request-scoped quality reporting through the existing recorder. It retains storage inspection, existing TTL equality/clock-drift semantics, public interfaces, financial calculations, schema and dependencies.

The implementation audit identified that direct Momentum resolver/legacy fetch paths can bypass the CLI cache client. C therefore also validates those fetched frames before calculation, without changing calculation formulas or validation of explicitly preloaded frames. Financial repository reads retain the original TTL/historical-availability contract; stricter observation/lineage and annual metadata checks belong at analytical consumption, preventing administrative inspection from being mistaken for analytical eligibility. Rejected persistent snapshots remain inspectable and are rechecked on every subsequent use, including after reopen.

The scoped observer is a callback bound with ContextVar, not a second logging framework or policy registry. Orchestrated tools bind the existing recorder and tool/parent spans; direct CLI execution lazily creates a recorder under the already-established CLI RunContext only when a quality failure occurs. The existing recorder sanitizes structured payloads. Observer/recorder failures do not change quality decisions. Operational diagnostics include only the rule identifier; detailed input evidence stays behind recorder sanitization. No provider retry loop or telemetry-driven execution control is introduced.