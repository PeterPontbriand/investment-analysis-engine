# R2 Contract and Implementation Handoff — Analysis Strategy Package Split

Defines the analysis-package split, shared-helper scope and compatibility requirements.

Work-package order and status: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## Sequence and status

| Order | Scope | Local gate |
| :--- | :--- | :--- |
| A → B → C | Contract; legacy retirement; shared helpers | Accepted |
| D → E | Atomic package/consumer migration; documentation | Accepted |

## 1. Scope

 This is a sequencing choice, not a technical dependency. P2-ETF retains its independent deferral beyond Step 3.6.


Momentum and FCF retain their internal behavior and heterogeneous interfaces. `base_analyzer.py` stays at its existing path; no new strategy must subclass it. No discovery/registry framework, self-registering CLI commands, new financial algorithms, dependency changes, persistence migration, or provider/model calls are included.

### Existing-strategy reuse assessment (2026-09-06)

Reviewed Momentum's `momentum_analyzer.py` and package exports, and FCF Growth's `analyzer.py`, `input_resolver.py`, `calculators.py`, model contracts, and package exports. The following decisions distinguish equivalent operations from superficially similar financial inputs.

| Candidate | Momentum | FCF Growth | R2 decision |
| :--- | :--- | :--- | :--- |
| Profile/ticker validation | Its analyzer/resolver has no equivalent profile-validation branch | `run_analysis` compares profile ticker with `ticker.strip().upper()`, exactly as Graham does, with its own error message | Reuse `validate_profile_ticker` in FCF during R2-C; pass the complete FCF-specific message; do not add a new Momentum validation rule |
| Affirmative ETF evidence | Momentum remains applicable to ETFs; no company-fundamental applicability check belongs here | Same profile/kind-evidence/`InstrumentKind.ETF` predicate as Graham | Reuse `is_known_etf` in FCF during R2-C; preserve FCF's native not-applicable result builder and messages |
| EPS normalization | No EPS inputs | Aligns annual diluted EPS with OCF/CapEx and optional diluted shares, then selects a contiguous 3/4/5-year growth span | Keep FCF annual resolution local; Graham's three-year-average/TTM scalar resolution is not interchangeable |
| Optional current quote and valuation comparison | Uses the last eligible historical close, not a current-quote boundary or valuation ceiling | Production execution does not resolve a current quote; market-cap/consensus context remains explicitly unavailable pending approved mappings | No new quote fetch, margin-of-safety calculation, or substitute FCF-yield context |
| Provider-backed-evidence guard | Historical resolver already retains provider-backed series | Annual resolver already requires provider-backed aligned facts | Do not add Graham's override-only rejection guard to either strategy; their existing validation remains authoritative |
| Cache, clock, currency, and period rules | Historical frames, timestamp truncation, and market-data context | Annual-series cache, fiscal-period/currency alignment, availability timestamps, and same-accession share evidence | Preserve their distinct boundaries; use existing data-layer primitives, not Graham's scalar resolver or `common_currency` helper |
| Metrics and trace construction | Already uses `src/core/metric_result.py` and data-layer trace/provenance models | Uses the same core metric and trace/provenance contracts | Retain existing reuse. Do not extract trivial constructor wrappers or strategy-specific financial formulas solely because both use these types |

Thus R2 includes two demonstrated FCF shared-helper adoptions and Momentum relocation without internal refactoring. Momentum's existing SMA/crossover/RSI semantics, fallback ticker, data-client compatibility, clock behavior, and signatures remain intact. FCF calculations, horizon selection, annual-series cache policy, classification, and optional-evidence policy remain intact. Additional sharing requires demonstrated semantic equivalence and a reviewed scope amendment; helper adoption is not an acceptance quota for each strategy.

## 2. R2-A — Contract and documentation checkpoint

**Prerequisites and deliverables**

- Verify the R1 commit exists locally and reconcile its affected-file inventory against its diff. Use the recorded R1 gate evidence and establish a fresh managed baseline before production refactoring.
- Freeze section 5's symbol/dependency map and identify intentional interface removals.
- Enumerate exact production, test, configuration, script, and active documentation consumers before authorizing their edits. Search dotted imports, slash/backslash paths, patch targets, exported symbols, and dynamic module strings. Include tracked hidden configuration such as `.github/` and `.claude/`; exclude `.git/`, virtual environments, caches, and generated artifacts.
- Record the inventory in a companion `R2_MIGRATION_INVENTORY.md` in this directory, separating executable consumers, active guidance, approved historical references, and planned deleted tests. Record source revision and discovery commands. The inventory is a required R2-A deliverable, not an assumed completed audit.
- Update only the owning status table.
- Prepare a reviewable documentation checkpoint; commit/push only when authorized.

**Acceptance and Gate R2-A**

- R1 checkpoint and gate evidence reconciled; fresh managed baseline recorded in the [migration inventory](R2_MIGRATION_INVENTORY.md).
- Exact consumer/deletion inventory complete, including exports and configuration.
- Section 9.1/9.2 decisions resolved; separate-resolver design and named retirements accepted on 2026-09-06.
- Planning references agree and documentation evidence is prepared and checked.
- Gate R2-A stakeholder review of the documentation checkpoint and evidence is complete; R2-B execution authorized on 2026-09-07.
- Explicit approval covers R2-B's two named deletions and supersedes R1's legacy-preservation constraint for those interfaces only; execution awaits review of the completed R2-A evidence.

## 3. R2-B — Retire the legacy Graham analyzer

R1 preserved `GrahamValueAnalyzer` and `GrahamValueConfig`. R2 proposes reversing that constraint explicitly. Repository inspection found callers only in the dedicated tests and the module's self-test; repeat this check at Gate R2-A. Repository search alone does not establish the absence of external consumers.

The legacy wrapper uses a different data boundary and lacks the production path's provenance, applicability, and compatibility semantics. It calls the existing growth calculator; removal retires the alternate wrapper/configuration behavior, not a second independent implementation of the pure formula.

**Delete-only production/test scope**

- `src/analysis/graham_value/graham_value_analyzer.py`
- `tests/analysis/graham_value/test_graham_value_analyzer.py`

No other production file changes are permitted. Unexpected callers or required active documentation changes must be reconciled into the approved inventory before deletion.

**Acceptance and Gate R2-B**

## 4. R2-C — Shared financial-resolution helpers

Create `src/analysis/shared/__init__.py` and `financial_resolution.py`. Shared helpers depend on existing data/core contracts, never on strategy packages. They must not reimplement `src/data/financial/resolver.py` cache/provider precedence.

| New helper | Existing implementation and preserved contract |
| :--- | :--- |
| `resolve_normalized_eps` | `GrahamInputResolver._resolve_eps`; accept an injected `InputResolver` followed by the existing keyword arguments; return `InputResolutionResult`; preserve override bypass, three-year averaging, and existing single-observation basis handling |
| `resolve_optional_quote` | `GrahamInputResolver._resolve_optional_quote`; same injected-resolver pattern and result type; preserve request construction and status without translating it |
| `validate_profile_ticker` | Preserve normalization and rejection; require keyword-only `mismatch_message: str`, supplied fully formatted by the strategy caller, and raise `ValueError(mismatch_message)` unchanged on mismatch; no strategy-specific default |
| `is_known_etf` | Preserve the affirmative ETF-evidence predicate; return a boolean without constructing applicability messages |
| `has_provider_backed_evidence` | Preserve the current evidence predicate; return a boolean without constructing failure messages or imposing additional product policy |
| `margin_of_safety`, `common_currency` | Service helpers; preserve signatures, unknown/mismatched currency handling, optional security-unit checks, and unavailable comparison behavior |

The optional-quote helper returns the existing status. Assemblies retain `INVALID_INPUT` as fatal; `INPUT_UNAVAILABLE` and `PROVIDER_ERROR` degrade non-fatally. Preserve required-input short-circuiting before quote resolution.

**Message ownership:** Shared helpers must not construct strategy-specific text, embed strategy names or message templates, or select wording based on strategy identity. When a shared helper raises or returns a caller-specific diagnostic, the strategy caller supplies the complete formatted message through an explicit argument; the helper passes it through unchanged. Passing only a method name into a shared strategy-specific template is insufficient. Strategy-neutral diagnostics intrinsic to the shared operation may remain in shared code.

For example, the Graham service supplies `mismatch_message="Instrument profile ticker does not match the Graham analysis ticker."` to `validate_profile_ticker`. The helper knows only the ticker/profile comparison and the supplied message. Existing public wording is preserved by the caller, with no exception to shared-helper neutrality.

Keep `_etf_not_applicable_reason` and `_unverified_ticker_reason` in the Graham service during R2-C; they are not shared financial-resolution primitives. Callers use the boolean predicates and construct their own result reasons. In R2-D, place these message builders in the respective strategy service modules, preserving each method's current wording. Do not introduce a shared pass-through helper solely to return a supplied string. The same ownership rule applies to errors, warnings, logs, and resolution-trace messages, including helpers in `shared/graham_contracts.py`: they may carry caller-provided text but must not generate strategy-specific text.

Update both `graham_value/input_resolver.py` and `graham_value/service.py` to delegate to these helpers and remove their superseded private implementations. Assemblies, configs, models, calculators, services, and the public `GrahamInputResolver` remain at their current paths in this slice.

Also update `src/analysis/fcf_earnings_growth/analyzer.py` at its existing path: replace the inline profile mismatch check with `validate_profile_ticker(ticker, instrument_profile, mismatch_message="Instrument profile ticker does not match the FCF & Earnings Growth analysis ticker.")`, and replace only the inline ETF predicate with `is_known_etf(instrument_profile)`. Keep boundary calculation, normalized ticker, validation order, early return, and `_etf_not_applicable_result` unchanged. If needed for strict typing, assert the profile is non-None inside the true ETF branch; do not broaden the predicate or rebuild the retained profile. FCF retains ownership of all result reasons, forward-evidence/metric statuses, and warnings.

**Acceptance and Gate R2-C**

- Shared helpers and direct tests in `tests/analysis/shared/test_financial_resolution.py` exist.
- Resolver and service delegate without duplicated private implementations.
- Shared helpers contain no strategy-specific message templates or defaults. Direct tests prove caller-supplied diagnostic text is passed through unchanged, while strategy-level regressions preserve exact existing public messages.
- FCF uses the two shared checks with its own exact mismatch text and native ETF result. Deterministic tests cover absent profile, matching/mismatched normalized ticker, confirmed ETF, equity, and absent/unknown kind evidence; mismatch still raises before resolver access and confirmed ETFs still skip annual resolution. Retained profiles, effective/requested boundaries, all result statuses/reasons, and optional-context fields are unchanged.
- Existing Graham assertions remain unchanged; necessary private patch-target adaptations are inventoried and preserve the same fault injection.
- The inventoried direct private-helper consumer in `tests/analysis/graham_value/test_security_unit_compatibility.py` imports/calls shared `margin_of_safety` instead of service `_margin_of_safety`, with every argument and assertion preserved.
- Fixed-clock regression evidence satisfies section 7, including explicit trace comparisons.
- No existing file is relocated; only the three named production consumers (Graham resolver/service and FCF analyzer), shared package, approved tests, and planning evidence change.

## 5. R2-D — Strategy decomposition and atomic consumer migration

### Proposed target and complete contract map

Paths below are relative to `src/analysis/`. The separate-resolver design was accepted on 2026-09-06; no combined resolver is retained.

| Current symbol/file | Destination and contract |
| :--- | :--- |
| `base_analyzer.py` | Unchanged at current path |
| `momentum/`, `fcf_earnings_growth/` | `strategy/momentum/`, `strategy/fcf_earnings_growth/`; move all existing source files, preserving package exports, signatures, and behavior; imports/patch targets only relative to the approved post-R2-C state |
| R2-C helpers | `shared/financial_resolution.py`; unchanged during relocation |
| `GrahamMethod`, `_GrahamConfig` | `shared/graham_contracts.py`; retain one enum identity, exact `graham_number` / `graham_growth_value` values, and existing private config validators/default resolution; this is explicitly Graham-specific shared code |
| Assembly `_event` / `_trace_event` helpers | `shared/graham_contracts.py`; preserve trace construction and order; no generic tracing framework |
| Analyzer `_resolve_ticker` helper | `shared/graham_contracts.py`; preserve explicit/default ticker selection, normalization, and error text |
| Service `_etf_not_applicable_reason`, `_unverified_ticker_reason` | Respective Number/Growth `service.py` modules; strategy callers own complete message construction; no strategy-specific templates in shared helpers |
| Calculator `_GRAHAM_MULTIPLIER` | Number `calculation.py`; retain the named, documented 22.5 constant and its existing semantics |
| `GrahamNumberConfig`, `GrahamGrowthConfig` | Respective `strategy/graham_number/config.py`, `strategy/graham_growth/config.py`; inherit the relocated `_GrahamConfig`; frozen/extra-forbid/type/default semantics unchanged |
| `GrahamNumberInputAssembly`, `GrahamNumberResult`, `compute_graham_number` | `strategy/graham_number/calculation.py`; names, fields, result invariants, math, and discriminator unchanged |
| `GrowthValueInputAssembly`, `GrahamGrowthValueResult`, `compute_graham_growth_value`, `GrahamGrowthCalculationPolicy` | `strategy/graham_growth/calculation.py`; preserve all policy validation and result semantics |
| `GrahamInputResolver.assemble_graham_number`, `_with_semantic_bvps_basis` | `GrahamNumberInputResolver(InputResolver)` and method-local helper in Number `calculation.py`; preserve assembly method name and all keyword parameters/defaults |
| `GrahamInputResolver.assemble_growth_value`, `_resolve_expected_growth` | `GrahamGrowthInputResolver(InputResolver)` in Growth `calculation.py`; preserve assembly method name and all keyword parameters/defaults; expected-growth resolution remains an instance method using inherited injected `_clock()` |
| `GrahamNumberAnalysis`, `run_graham_number_analysis` | Number `service.py`; complete return evidence unchanged; resolver parameter becomes `GrahamNumberInputResolver` |
| `GrahamGrowthAnalysis`, `run_graham_growth_analysis` | Growth `service.py`; complete return evidence unchanged; resolver parameter becomes `GrahamGrowthInputResolver` |
| `GrahamNumberAnalyzer`, `GrahamGrowthAnalyzer` | Respective `analyzer.py`; retain configs, ticker selection, profile/policy arguments, and typed results; injected resolver type changes to the corresponding method resolver |
| Existing Graham package exports | Re-export method-specific symbols from their destination package `__init__.py`; `GrahamMethod` and `CalculationStatus` remain available from both method packages as the same enum objects; no aliases at deleted paths |
| Legacy `GrahamValue*` interfaces | Removed in R2-B; no destination |

Create `strategy/__init__.py`. Each Graham package has `__init__.py`, `config.py`, `calculation.py`, `service.py`, and `analyzer.py`. This four-module arrangement beyond `__init__.py` is a Graham implementation choice, not a universal strategy template. Pure calculator functions remain deterministic even though their module also contains resolver assembly code.

The complete non-Graham source relocation is mandatory in R2-D:

| Existing directory | New directory | Files retained under the same filenames |
| :--- | :--- | :--- |
| `src/analysis/momentum/` | `src/analysis/strategy/momentum/` | `__init__.py`, `momentum_analyzer.py` |
| `src/analysis/fcf_earnings_growth/` | `src/analysis/strategy/fcf_earnings_growth/` | `__init__.py`, `analyzer.py`, `input_resolver.py`, `calculators.py`, `models.py` |

Preserve each package's exports and any direct module entry points. Do not impose Graham's file layout on these packages. FCF keeps the R2-C shared-helper imports after moving. Include all old/new module paths in the atomic consumer inventory, even for files without package-level exports. Test directories may remain at their existing locations; updating imports/patch targets and preserving behavioral coverage is required regardless of physical test placement.

### Resolver, composition, and compatibility contract

The two narrow resolvers inherit the existing `InputResolver` constructor unchanged; they add no provider/cache/clock construction or ownership. Shared EPS/quote helpers consume the injected resolver through its public methods. Growth continues using the same injected clock for expected-growth provenance. No changes to the underlying data resolver are needed.

This explicitly replaces the combined public `GrahamInputResolver`; the old constructor dependency cannot simultaneously be promised unchanged. Preserve all other analyzer/service parameter names, defaults, validation, and return schemas. Callers choosing a Graham method construct the matching resolver with the same provider, cache, and clock arguments. Callers that previously shared a resolver across methods may construct two borrowed wrappers over the same dependencies without creating additional providers/caches or changing closure behavior. Preserve `financial_facts_analysis_scope` placement and provider request order.

In `AnalysisToolDependencies`, replace `graham_resolver` with two required fields, `graham_number_resolver: GrahamNumberInputResolver` and `graham_growth_resolver: GrahamGrowthInputResolver`. Each handler passes its matching dependency to the unchanged method-specific tool operation. Update evaluation composition and every dependency fixture atomically. This Python dependency-container interface change is part of the proposed R2-D authorization; the LLM-facing tool argument models, names, routing, and outputs remain unchanged.

No shims are retained for any relocated package, including Momentum and FCF.  Serialized method identifiers, tool names, config/result fields, CLI commands/options/output, and persisted data contracts remain unchanged.

### Atomic migration and acceptance

Relocate Momentum/FCF with `git mv` when implementation is authorized. Decompose Graham, migrate exports and every executable consumer in the same slice, then remove the old packages. Consumer scope includes CLI/support, orchestration, evaluation, reporting, scripts/configuration, all affected tests, and executable documentation examples. R2-E must not be needed to restore an importable/testable tree.

The [completed migration inventory](R2_MIGRATION_INVENTORY.md) enumerates the exact production/test consumers, including CLI, orchestration, evaluation, and reporting. Inspection found no moved imports in `src/cli_support.py`; do not edit it without an actual affected reference. Refresh the inventory before implementation edits and reconcile newly demonstrated consumers first.

- All symbols have reviewed destinations; old strategy directories are removed.
- All executable imports, patches, resolver construction sites, and exports migrate together within the approved inventory.
- Consumer edits are restricted to imports, method-resolver selection/construction, and corresponding typing; financial, presentation, routing, and resource behavior is preserved.
- Tests retain every surviving behavioral case. Resolver fixture construction may change as specified; assertions cannot be weakened to accommodate regressions.
- Full managed gate passes with all consumers working, including CLI, reporting, orchestration, evaluation/Golden cases, and cache/composition tests.
- Actual diff and section 7 evidence reviewed and approved on 2026-09-07.

## 6. R2-E — Documentation reconciliation and final sweep

Update remaining active architecture/user/developer guidance from the approved inventory to describe the new package ownership and import migration. Preserve historical milestone records and annotate only where necessary to avoid presenting them as current instructions.

Require zero executable references and zero obsolete active guidance to old dotted or filesystem paths and removed symbols. Allow historical approvals, archived implementation evidence, and explicit old-to-new migration explanations; record exact retained files/reasons in the inventory. This document itself necessarily contains old names. A repository-wide zero-hit rule is not an acceptance criterion.

- Active guidance, examples, exports, and the destination map agree.
- Every reference-inventory entry is migrated, removed under approval, or explicitly retained with a reason.
- Any newly discovered executable consumer is remediated under a reviewed R2-D scope amendment, not hidden in a documentation-only slice.
- Final managed gate passes; test and coverage changes are reconciled under section 7.

## 7. Write boundaries and verification

All slices may update R2 planning evidence and milestone status only as supported by actual results/approval. Exact affected files must be recorded before edits; discovering an additional necessary file requires inventory/scope reconciliation first.

| Slice | Write allowlist |
| :--- | :--- |
| R2-A | This record, companion migration inventory, milestone implementation plan, and relevant scheduling references in `docs/project/MASTER_PLAN.md` / `DISCOVERY_WORKBOOK.md` |
| R2-B | Two named deletion paths in section 3; planning evidence |
| R2-C | `src/analysis/shared/{__init__,financial_resolution}.py`, `src/analysis/graham_value/{input_resolver,service}.py`, `src/analysis/fcf_earnings_growth/analyzer.py`, `tests/analysis/shared/test_financial_resolution.py`, `tests/analysis/test_instrument_applicability.py`, `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_analyzer.py`, and `tests/analysis/graham_value/test_security_unit_compatibility.py` for the direct private-symbol adaptation; planning evidence |
| R2-D | Existing and new strategy directories, `src/analysis/strategy/__init__.py`, `src/analysis/shared/graham_contracts.py`, shared export adjustments, and all exact executable consumer/test/config/example paths approved in the inventory; planning evidence |
| R2-E | Inventoried remaining active documentation and planning evidence; no production/test repair by default |

Before each implementation slice, establish the managed baseline on the actual starting revision. After each slice and for final closeout run from PowerShell:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

The wrapper runs non-mutating Ruff/formatting, strict mypy, and deterministic pytest/coverage with isolated repository-local caches/temp files and `uv run --no-sync`. No dependency installation, live provider, or LLM call is authorized. Record revision, scope, test counts, coverage, artifact directory, and diff review at each gate.

**Behavior preservation matrix**

- Config normalization/default/provider/EPS matrices, invalid numeric inputs, explicit/default tickers, profile mismatch, and affirmative ETF versus unknown-kind handling.
- Required-input ordering, optional-quote outcomes, override/cache/provider precedence, unavailable data, and exact status/reason text.
- Fixed-clock provenance including `resolved_at`, requested `as_of`, lineage, currencies, security-unit evidence, and ordered resolution events. Compare traces explicitly: assembly dataclass equality excludes `resolution_trace`.
- Financial outputs and unavailable margins, complete typed service evidence, unchanged serialized discriminators/schemas, and CLI JSON/concise/details/diagnostics outputs and exit/stream behavior.
- Provider-call counts/order, request-scoped fact snapshots, cache reuse/bypass, inherited clock identity, and resource closure on success/failure. Both CLI analyzer and direct orchestration-service paths remain covered.
- Momentum historical-price truncation/provenance, configured windows and insufficient-history outcomes, ETF applicability, fallback ticker, and legacy client entry points; FCF normalized profile checks, ETF short-circuit, annual alignment/horizon fallback, total-FCF versus FCF/share classification, and unavailable market-cap/consensus context. Exercise existing deterministic Momentum/FCF suites, reporting, CLI, and evaluation cases after relocation; no new live execution is required.

Retain existing cases and add focused tests for extracted helpers and new dependency wiring. Itemize R2-B's removed test node IDs; map moved/split test IDs to their retained behavioral cases. New tests cannot compensate for unexplained loss of old cases. Compare totals after accounting for authorized deletions and parameterization changes, rather than requiring raw pre-R2 test-count equality. Report coverage percentage and covered/missing lines: deletion changes the denominator. Preserve coverage of retained behavior, meet the project >=85% overall target, and investigate unexplained losses instead of masking them with newly covered helper lines.

## 10. Gate R2-A approval and R2-B execution record

The reviewed section 9.3 evidence and exact migration inventory are accepted.

Before deletion, the full managed baseline passed with only the pending R2 planning evidence in the working tree: Ruff, formatting, strict mypy, and 1,809 tests in 30.97 seconds, with 89% reported coverage (9,398 statements, 793 missing). Artifacts: `.tmp/quality-runs/20260907091113599-35368-9bc6aceb6d46487da66be740a194b65d/`. The refreshed caller audit again found executable legacy references only in the two approved retirement files.

Deleted only `src/analysis/graham_value/graham_value_analyzer.py` (298 lines) and `tests/analysis/graham_value/test_graham_value_analyzer.py` (337 lines). All retained production/test files remain unchanged. The 44 retired test node IDs are preserved in the migration inventory. No executable reference to the three retired symbols or deleted module name remains; historical R1/R2 planning references are retained as classified.

The post-retirement managed gate passed Ruff, formatting (274 files), strict mypy (214 source files), and 1,765 tests in 28.28 seconds. The decrease is exactly the 44 inventoried legacy cases. Coverage remains 89% reported: 9,308 statements, 777 missing, 8,531 covered (approximately 91.7% statement coverage); 2,966 branches, 499 partial branches. Artifacts: `.tmp/quality-runs/20260907091231334-20260-ba040cce936748129cbd33d2f865d6fd/`.

Per-file coverage reconciliation shows the retired module accounts for all 90 removed statements and all 16 fewer missing statements. Every retained module has the same covered/missing statement count. All retained financial-analysis branch counts are unchanged. One additional unexercised branch is reported in the unchanged logging adapter (`src/utils/logger_util.py`, the optional context condition at line 396); this is ancillary logging coverage, not a financial regression or a removed retained test. No logging refactor is included.

Final scope/whitespace and executable-reference checks passed.

## 11. Gate R2-B approval and R2-C implementation evidence

The fresh pre-refactor managed baseline passed Ruff, formatting, strict mypy, and 1,765 tests in 28.03 seconds with 89% reported coverage. Artifacts: `.tmp/quality-runs/20260907091845275-5796-7266e8f7f742480390eb9c9f42de7d56/`. The base revision remained unchanged, plus the approved R2-B deletions and pending planning evidence; no intervening source changes were present.

Created `src/analysis/shared/__init__.py` and `financial_resolution.py`. Extracted EPS/optional-quote request construction and profile/evidence/comparison helpers, preserving existing data-layer precedence and ownership. Graham resolver/services delegate without retaining duplicate private implementations. Graham keeps applicability and unverified-ticker messages locally and supplies its full profile-mismatch message. FCF adopts only the equivalent profile/ETF checks, supplies its complete mismatch message, and retains its native result/message construction. No existing file moved; Momentum, base/data resolvers, configs, calculators, service entry points, orchestration, CLI, and dependencies remain unchanged.

Test work follows the exact R2-C inventory: new shared-helper tests; additional FCF analyzer and applicability cases; and import/call-spelling adaptation of the existing private margin helper test without argument/assertion changes. No surviving existing test assertion was removed or weakened. New helper tests first failed collection because the shared module did not yet exist. During implementation, new cache fixtures were corrected to reflect required origin/schema metadata and the existing cache-bypass `not_used` trace, without changing production behavior to accommodate test assumptions.

The 46 added cases comprise 39 direct shared-helper cases, 3 complete-result FCF profile cases, and 4 FCF mismatch/ETF-result cases. Coverage exercises finite/non-finite and zero/negative overrides, EPS bases, provider/cache/bypass behavior, fixed-clock provenance/lineage and traces, optional-quote outcomes, caller-supplied diagnostic text, affirmative ETF evidence, mixed/absent currencies, and unavailable comparisons. Existing unchanged Graham tests preserve assembly short-circuit/status behavior, traces, clocks, ownership, and service/CLI/orchestration outputs. Focused verification passed 56 tests.

Final complete managed gate passed on 2026-09-07: Ruff; formatting (277 files); strict mypy (217 source files); and 1,811 tests in 28.99 seconds. Coverage remains 89% reported: 9,317 statements, 775 missing, 8,542 covered (approximately 91.7% statement coverage), 2,964 branches, 497 partial branches. The new shared module has all 39 statements and all branches covered. No other retained module gained missing statements/branches; FCF analyzer and Graham service each improved by one missing statement and one missing branch. Artifact directory: `.tmp/quality-runs/20260907093014278-31416-5509ab07c8b04649b7681d441668cc65/`.

Final scope and whitespace checks passed. Shared production code has no Graham/FCF/Momentum-specific text or imports; removed private implementations are absent. The working-tree R2-B deletions predate this slice; R2-C adds only its inventoried shared module/tests and edits the three authorized production consumers and three authorized existing test files.

## 12. Gate R2-C approval and R2-D implementation evidence

The refreshed inventory and fresh full baseline are recorded in inventory section 11. Baseline: 1,811 tests in 27.54 seconds; 89% combined coverage; 9,317 statements, 775 missing (8,542 covered), 2,964 branches, 497 partial branches.

Implemented the approved Number/Growth packages with separate inherited-constructor resolvers and shared Graham contracts. Relocated all Momentum/FCF source with Git moves, retaining their filenames and behavior. Removed all three old source directories without shims. Migrated the inventoried CLI, reporting, orchestration, evaluation, and test consumers atomically. CLI construction selects the concrete resolver type; evaluation shares provider/cache/clock dependencies across the two wrappers. Strategy services continue owning their public messages; shared trace helpers accept caller-supplied text. `base_analyzer.py` and the R2-C financial-resolution helper implementation are unchanged.

The final managed gate passed Ruff, formatting (282 files), strict mypy (222 source files), and all 1,811 tests in 28.72 seconds. Artifacts: `.tmp/quality-runs/20260907094917827-8304-ac5a5a68cc78411ca6d7d2a23afee9dc/`. Coverage remains 89% combined: 9,376 statements, 776 missing (8,600 covered; approximately 91.7% statement coverage), 2,964 branches, 497 partial branches. The 59 additional statements are from package decomposition/imports and explicit dependency wiring: 49 within Graham packages/contracts, three in CLI, three in evaluation composition, one in evaluation runner, and three in orchestration. The one additional missing statement is the Number service's now-local `_unverified_ticker_reason` return: its Number branch was already unexercised, while the former shared function was covered through Growth. Retained branch totals and partial counts are unchanged, and every corresponding non-Graham module retains its missing statement/branch counts.

All existing test functions and the 1,811-case total are retained; no test files or behavioral cases were removed. Existing resolver, analyzer, CLI builder/provider-routing, and dependency fixtures now exercise the method-specific wiring. Source AST comparison confirms both pure Graham calculators and all Momentum/FCF non-import code are unchanged. The first post-migration gate exposed two stale CLI builder mock expectations; they now require the Growth resolver explicitly, preserving all provider assertions. A subsequent formatting check caught mixed line endings in that test edit; normalization and the final full gate resolved it.

The executable source/test reference audit has zero old package paths or `GrahamInputResolver` references. Test fixture namespaces remain intentionally unchanged. Diff scope and whitespace checks passed. Active architecture/discovery directory-tree reconciliation remains R2-E work.

## 13. Gate R2-D approval and R2-E final reconciliation

Execution started from that clean revision on 2026-09-07. Updated the six inventoried documentation/planning files, including the additional active resolver references reconciled before edits in inventory section 13. Final reference dispositions are recorded in inventory section 14. Active package trees, resolver terminology, dependency ownership, exports, and shared caller-message policy agree with the implementation. Historical design/approval evidence remains intact.

Fresh baseline: Ruff, formatting (282 files), strict mypy (222 source files), and 1,811 tests passed in 27.90 seconds. Artifacts: `.tmp/quality-runs/20260907111845372-25472-5e96817a79544456851e744b5811db07/`.

Final managed gate: Ruff, formatting (282 files), strict mypy (222 source files), and 1,811 tests passed in 26.14 seconds. Artifacts: `.tmp/quality-runs/20260907112056976-33320-b8dad7a8f5754c63b8ef2449f6e2f866/`. Both runs report 89% combined coverage: 9,376 statements, 776 missing, 8,600 covered (approximately 91.7% statement coverage), 2,964 branches, 497 partial branches. R2-E changes no source/tests, so its test count and coverage are unchanged. Across R2, the initial 1,809 cases minus 44 explicitly retired cases plus 46 shared-helper/applicability cases equals the final 1,811. R2-B/C/D sections preserve the per-slice denominator and retained-coverage reconciliation; no behavioral case loss is unexplained.

Final diff/whitespace and old-reference checks passed. No production, test, dependency, persisted-data, or runtime-contract changes are included in R2-E. Later milestone work remains separately authorized.
