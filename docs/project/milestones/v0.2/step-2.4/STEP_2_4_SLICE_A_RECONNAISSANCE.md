# Step 2.4 Slice A Reconnaissance

**Status:** Complete and approved; Slice B authorized<br/>
**Governing design:** `docs/project/milestones/v0.2/step-2.4/STEP_2_4_FCF_EARNINGS_GROWTH_DESIGN.md`<br/>
**Scope:** Milestone v0.2, Step 2.4 Slice A only<br/>
**Prepared:** 2026-08-26

## 1. Outcome

The approved Free Cash Flow & Earnings Growth design can be implemented by extending the Step 2.3 valuation-fact, provenance, cache, resolver, production-provider, CLI, and presentation seams. No parallel provider framework, provenance model, cache hierarchy, orchestration framework, or generic strategy registry is justified.

Slice A made no production-code or test changes. It reconciled the stale implementation-plan baseline with the reviewed design and identified the concrete work boundaries below. Slice B must not begin until this record and the accompanying implementation-plan reconciliation receive human approval.

## 2. Product-policy lock

The reviewed governing design resolves the Step 2.4 product-policy checkpoint:

- use compatible completed annual actuals;
- derive FCF as operating cash flow minus normalized positive capital expenditures;
- calculate FCF and diluted-EPS CAGR over the same contiguous span;
- prefer five elapsed years, then four, then three; explicit horizons are strict;
- classify the historical screen as `PASS`, `FAIL`, or `INDETERMINATE` and also report the descriptive relationship;
- treat FCF yield as optional supporting information with no classification threshold;
- treat FY1/FY2 consensus EPS as optional context under `display_only`, `confirmation`, or `hard_gate` policy;
- keep TTM data, P/FCF gates, DCF, peer ranking, composite scores, and investment recommendations outside the initial method.

The implementation plan previously retained an older three-year-only, trend-only, no-forward baseline. Section 4.4 has been reconciled to the governing design as part of Slice A.

## 3. Reusable seams and required extensions

| Area | Reusable current seam | Step 2.4 action |
| :--- | :--- | :--- |
| Strategy boundary | `src/analysis/base_analyzer.py` and strategy-local models/calculators | Add a strategy-local `src/analysis/fcf_earnings_growth/` package. Keep policy, typed results, selection, and pure arithmetic specific to this strategy. Do not broaden `BaseAnalyzer` speculatively. |
| Software status | `src/core/analysis_status.py` | Reuse `CalculationStatus` for execution/calculation availability. Define the investor screen classification separately so `FAIL` cannot be confused with provider or input failure. |
| Fact contract | `src/data/financial/facts.py` | Minimally add semantic fields and units for annual operating cash flow and CapEx. Add only evidence-approved optional market-capitalization and consensus fields. The request currently permits multi-observation retrieval only for EPS and therefore needs a deliberate annual-series extension. |
| Provider protocol | `FinancialFactsProvider.fetch_facts()` | Reuse the tuple-of-`ProviderFact` boundary. Preserve exact concepts, periods, currency, availability, retrieval time, basis, and notes for each annual component. |
| Provenance | `ResolvedInput` and `ComponentLineage` in `src/data/financial/provenance.py` | Reuse each `ResolvedInput` for one annual fact and use `ComponentLineage` for each derived annual FCF observation. Add no second provenance model. Series/result models should contain these resolved observations rather than flattening their lineage. |
| Cache | `ResolvedInputCacheKey`, `ResolvedInputCacheProtocol`, and `InMemoryResolvedInputCache` | Reuse the existing cache. Multi-year fact identity and derived-FCF caching need explicit design because the current key does not identify an observation period and the generic resolver accepts only one observation. Prefer caching validated individual facts or an explicitly versioned derived series; do not allow period collisions. |
| Resolution | `InputResolver`, `InputResolutionResult`, and `ResolutionTrace` | Reuse precedence, temporal eligibility, typed unavailable/provider-error outcomes, and trace vocabulary. Add a strategy-specific annual-series assembler/selector rather than forcing FCF logic into the Graham-specific three-year EPS method. Pair CFO and CapEx only after identity, period, currency, scope, and availability checks. |
| SEC production adapter | `src/data/sec_edgar/financial_facts.py` | Extend only after the provider mapping record is approved. Existing annual EPS parsing, 10-K/10-K/A filtering, EDGAR acceptance-time lookup, filed-date fallback, `as_of` exclusion, and per-period restatement selection are useful patterns. Cash-flow concepts and CapEx normalization remain unapproved. |
| Production routing | `ProductionFinancialFactsProvider` | Reuse provider-ID routing. Unsupported fact/provider combinations must return unavailable without fallback to a semantically different provider field. |
| Fixtures | `tests/analysis/graham_value/fixture_financial_facts_provider.py` and resolver/provider tests | Create a strategy-local deterministic provider/fixture surface with at least six annual observations and the adverse cases required by the design. Do not extend Graham fixtures until shared regression work requires it. |
| Presentation | `src/reporting/presentation.py` and the strategy-specific Graham/Momentum presenters | Reuse shared modes, formatting, provider labels, JSON helpers, and diagnostic payloads. Add `src/reporting/fcf_earnings_growth.py`; do not calculate or classify inside the presenter. |
| Direct CLI | Typer commands and shared parsing helpers in `src/cli.py` | Add `fcf-growth` using the existing `--as-of`, provider, cache, and mutually exclusive presentation conventions. Keep command execution behind one typed result/failure boundary. |
| Runtime tools | `ToolRegistry` and `ToolDispatcher` primitives | No production analysis-tool registration is currently wired. In the integration slice, identify the existing application bootstrap seam and register one typed Step 2.4 callable through these primitives. No new registry or strategy-specific orchestrator branch is required. |

## 4. Concrete incompatibilities to resolve

1. `FinancialField` is a closed financial-fact enum and lacks operating cash flow, CapEx, market capitalization, and forward-consensus EPS semantics.
2. `FinancialFactRequest` permits `observation_count > 1` only for EPS. `InputResolver.resolve()` rejects every multi-observation request, while `resolve_three_year_average_eps()` is Graham-specific and fixed at three observations.
3. The generic cache key has no reporting-period discriminator. Storing multiple annual facts under otherwise identical keys would collide unless the series resolution/cache boundary is designed explicitly.
4. Generic provider validation and unit selection are oriented around the existing single valuation fields. Annual currency amounts, consensus horizons, and period-compatible series need explicit validation rules.
5. Existing SEC EPS selection chooses the latest knowable restatement per period but does not yet prove the full diluted/basic, share-class, split, and period compatibility predicate required by the Step 2.4 design and the pre-Golden hardening gate.
6. The direct CLI contains strategy-specific execution functions. Step 2.4 can follow that pattern, but failures must enter the typed result/presentation boundary rather than adding another untyped error route.
7. Optional market capitalization and forward consensus are distinct capabilities. Neither should block the historical analysis unless the user selects `hard_gate` for forward evidence.

These are bounded extensions, not evidence that a generic strategy framework is needed.

## 5. Provider-evidence candidates and stop conditions

SEC EDGAR Company Facts is the first candidate for required annual actuals because the repository already has ticker-to-CIK resolution, Company Facts/submissions retrieval, annual diluted-EPS parsing, acceptance timestamps, conservative filed-date fallback, historical `as_of` filtering, and restatement selection.

No Step 2.4 cash-flow mapping is approved by reconnaissance. Before Slice D enables production support, the provider mapping record required by the governing design must establish:

- the exact operating-cash-flow concept precedence and full-year duration semantics;
- the exact CapEx concept precedence, included/excluded expenditures, and sign convention;
- prohibition on silently summing multiple plausible CapEx concepts;
- same-company, fiscal-period, currency, unit, scope, and availability compatibility;
- amended/restated filing selection and unresolved-tie behavior;
- annual diluted-EPS compatibility, including diluted/basic basis, share class when exposed, and split treatment;
- authoritative evidence, retrieval date, reviewed examples, approval, and deterministic tests.

Market capitalization and FY1/FY2 consensus EPS require separate provider capability records. Existing quote support is not proof of market-capitalization support, and existing annual or TTM EPS support is not proof of forecast-consensus support. Until approved, yield and forward fields remain unavailable; the historical screen can still complete except when `hard_gate` explicitly makes forward evidence required.

Stop for review rather than implement a mapping if multiple plausible CapEx concepts cannot be resolved conservatively, availability cannot be established, periods or currencies cannot be paired, dimensional facts are ambiguous, or forecast horizon/consensus meaning is undocumented.

## 6. Recommended implementation boundaries

The implementation-plan slices remain sufficient. Reconnaissance refines them as follows:

- **Slice B:** strategy-local enums, policy, metric/result invariants, pure FCF/growth/yield/classification functions, and hand-calculated tests only.
- **Slice C:** minimally extend provider-neutral facts, annual-series resolution, compatibility/selection, FCF lineage, cache identity, traces, and six-year deterministic fixtures. Split C into contract/resolution and fixture sub-slices if the cache-period decision makes the diff too large for one review.
- **Slice D:** prepare and approve the provider mapping record, then implement only approved production capabilities with recorded/mocked payload tests. Required historical SEC support should be reviewed separately from optional market-capitalization or consensus providers.
- **Slice E:** add the direct CLI, runtime-tool entry point, and one strategy-specific presenter for concise/details/diagnostics/JSON. Treat charting as optional and do not let it delay the required presentation contract.
- **Slice F:** execute the already-defined Graham/shared-contract hardening and Momentum modernization as a separate focused correction work unit, then stop for review.
- **Slice G:** synchronize documentation, run the complete gate, review the full diff, and obtain explicit approval before Step 2.5.

## 7. Likely file inventory

Expected new files or packages after Slice A—not authorized by this reconnaissance record itself—are:

- `src/analysis/fcf_earnings_growth/` for models, calculations, and input assembly/resolution;
- `src/reporting/fcf_earnings_growth.py`;
- strategy-local tests under `tests/analysis/fcf_earnings_growth/`;
- `tests/reporting/test_fcf_earnings_growth_presenter.py` and focused CLI tests; and
- a provider mapping record if production evidence is kept separate from the governing design.

Likely existing files requiring minimal later edits are:

- `src/core/analysis_status.py` only if the current software-status vocabulary proves insufficient;
- `src/data/financial/facts.py`, `cache.py`, `resolver.py`, `production.py`, and `providers.py`;
- evidence-approved provider adapters, initially `src/data/sec_edgar/financial_facts.py`;
- `src/cli.py`, `src/reporting/presentation.py`, and the application bootstrap location selected for analysis-tool registration; and
- their focused tests.

Exact authorization belongs in each later slice. No production file is authorized for speculative renaming or generalization merely because its current name contains “valuation” or “Graham.”

## 8. Verification baseline

The documentation-only Slice A baseline was rerun successfully on 2026-08-26 through `scripts/run-quality-gates.ps1`, which derives the repository root at runtime and isolates every writable verification path below a unique ignored `/.tmp/quality-runs/` directory:

- Ruff lint with cache disabled: passed.
- Ruff format check: passed (`143 files already formatted`).
- Mypy strict: passed (`Success: no issues found in 114 source files`).
- Pytest: passed (`697 passed in 12.69s`).
- Aggregate line/branch-aware report: 84% coverage as reported by pytest-cov.
- Concurrency check: two PowerShell wrapper invocations completed simultaneously with independent artifact directories; both passed all four gates and all 697 tests.

The wrapper resolved the earlier managed-environment failures by isolating pytest temporary files, coverage output, mypy cache, and UV cache, and by using `uv run --no-sync` against the already-synchronized project environment. It required no dependency, lockfile, user-profile cache, or production-code change. The companion `scripts/run-quality-gates.sh` applies the same behavior for Cline's Git Bash shell; this host exposes only the restricted Windows WSL launcher as `bash`, so Git Bash execution remains for the planned Cline verification.

The complete prescribed quality gate remains mandatory before Step 2.4 completion. The current 84% aggregate coverage is below the project-wide ≥85% target and should be monitored as Step 2.4 tests are added; it did not fail the currently configured gate.

## 9. Slice A review gate

Slice A is complete when the human confirms that:

- the approved product policy is accurately reflected in the implementation plan;
- the reuse/extension boundaries above are acceptable;
- production mappings remain blocked on the evidence record;
- optional yield/forward capabilities may remain unavailable without blocking the historical strategy, except under explicit `hard_gate`; and
- Slice B may begin with pure typed semantics and calculations only.

No later slice is authorized by the existence of this record alone.
