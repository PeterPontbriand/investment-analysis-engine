# ESC-E — Existing-analysis re-run after integration readiness

Defines scope, sequencing and acceptance for the re-run of the existing-analysis audit that the IR
contract requires once integration readiness (IR) is complete.

Local sequence and status: [companion plan](EXISTING_STRATEGY_CORRECTNESS_PLAN.md#sequence-and-status).
IR requirement: [IR contract §5](../integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md#5-acceptance-criteria).

## 1. At a glance

- **What ESC-E is:** one more pass of the [audit matrix](EXISTING_STRATEGY_CORRECTNESS_PLAN.md#3-required-audit-matrix)
  over Graham Number, Graham Growth, Momentum and FCF/Earnings Growth, on the revision after IR, before
  Step 3.5's new analyzers copy these patterns.
- **What it is not:** a repair package. Discrepancies go to the [defect ledger](ESC_A_DEFECT_LEDGER.md) and
  are decided by the project owner; nothing is repaired inside a comparison or audit slice.
- **Where it starts:** a side-by-side comparison against ESC-D's accepted revision `7e2f8d2` (PR #42). That
  comparison and a file-by-file change inventory decide how much re-verification each analysis needs; the
  plan proposes a scope for each and leaves the decision to review.
- **Baseline and target:** ESC-D's accepted revision `7e2f8d2` against `main` at `e6b1f76` (IR.6 merged,
  PR #51), 7 merged pull requests and 78 changed source files later.
- **Rules it follows:** the ESC plan's matrix and verification requirements, the complete managed gate with
  at least 85% coverage, dated live checks, and `AGENTS.md` §0 (no network or LLM calls in tests).
- **Where the detail lives:** the change inventory and the expected-difference register are
  [Appendix A](#appendix-a-change-inventory-7e2f8d2-to-e6b1f76) and
  [Appendix B](#appendix-b-expected-difference-register); the E.1 evidence is
  [ESC_E1_COMPARISON_EVIDENCE.md](ESC_E1_COMPARISON_EVIDENCE.md).

## 2. Sequence and status

Each slice ends with the managed quality gate where it changes code or tests, and is gated by explicit
authorization before the next begins.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| E.1 | [Side-by-side comparison against ESC-D's revision](#e1--side-by-side-comparison) | Complete | 2026-09-30 |
| E.2 | [Graham Number matrix](#e2--graham-number) | Complete | 2026-09-30 |
| E.3 | [Graham Growth matrix](#e3--graham-growth) | Complete | 2026-09-30 |
| E.4 | [Momentum matrix](#e4--momentum) | Complete | 2026-10-01 |
| E.5 | [FCF/Earnings Growth matrix](#e5--fcfearnings-growth) | Complete | 2026-10-01 |
| E.6 | [Reconciliation and final acceptance](#e6--reconciliation-and-final-acceptance) | Complete | 2026-10-01 |

E.1 was accepted by the project owner on 2026-09-30, with three corrections (ESC-21, ESC-20's closure, one branch). The [proposal in §4](#4-proposed-scope-for-e2-to-e5) is approved per dimension, with one change: the cross-cutting paths E.1 did not reach (`--save-run`, replay, watchlist refresh, the orchestrator) are verified once, at the start of E.2, for all four analyses, and E.3 to E.5 cite that evidence instead of repeating it. E.2 to E.6 were authorized the same day.

## 3. The slices

### E.1 — Side-by-side comparison

- **Problem:** IR changed every analyzer's entry point, clock, cache control and the Graham presenters after
  the last accepted audit, and its records list what was meant to change. Nothing has yet checked that list
  against what the commands actually do.
- **Decision:** run the same invocations on both revisions, back to back, and classify every difference as
  expected (citing a register entry) or unexplained (a ledger entry). The unit of comparison is the
  command's output and exit code, not its pass/fail.
- **Scope:** the deterministic Golden suite (19 cases, 91 observed values compared); 70 live command pairs
  across the four analyses, KO, AAPL, MSFT, SPY, ESC-17's historical scenario and `--as-of`/`--no-cache`
  cases; an earlier 70-pair pass and five added pairs for Momentum's success path; a re-run of the pairs that
  differed in a way live data could explain.
- **Result:** no unexplained difference in any calculated value, status, reason or exit code. One
  unexplained difference in a public contract: Graham's JSON `schema_version` moved from 5 to 6 with no
  IR record ([ESC-20](ESC_A_DEFECT_LEDGER.md#esc-20--graham-json-presentation-schema-version-changed-from-5-to-6-with-no-ir-record-and-two-user-documents-still-say-5)).
- **Branch:** `audit/esc-e-renewal`, the one branch for all of ESC-E.
- **Detail:** [ESC_E1_COMPARISON_EVIDENCE.md](ESC_E1_COMPARISON_EVIDENCE.md).

### E.2 — Graham Number

- **Problem:** the comparison exercised Graham Number only on KO (success), AAPL and MSFT (the same
  preferred-share failure on both revisions), SPY (not applicable) and two historical and cache-bypass
  cases. The changed code reaches further than that.
- **Decision:** re-verify in proportion to what changed; see [the proposal below](#4-proposed-scope-for-e2-to-e5).
- **Scope:** the seven matrix dimensions for `graham-number`, including its `--save-run`, replay, watchlist
  refresh and orchestrator paths.
- **Branch:** `audit/esc-e-renewal`, the one branch for all of ESC-E.
- **Detail:** [ESC_E2_GRAHAM_NUMBER_EVIDENCE.md](ESC_E2_GRAHAM_NUMBER_EVIDENCE.md). It also holds the cross-cutting evidence for all four analyses, which E.3 to E.5 cite.

### E.3 — Graham Growth

- **Problem:** Graham Growth shares Graham Number's changed resolver, clock and presenter code, and IR also
  made an EPS basis (`fiscal_year`) reachable from the CLI that it never was before.
- **Decision:** as E.2.
- **Scope:** the seven matrix dimensions for `graham-growth`, in ESC-D's order.
- **Branch:** `audit/esc-e-renewal`, the one branch for all of ESC-E.
- **Detail:** [ESC_E3_GRAHAM_GROWTH_EVIDENCE.md](ESC_E3_GRAHAM_GROWTH_EVIDENCE.md).

### E.4 — Momentum

- **Problem:** Momentum changed most in kind: a new `--as-of`, a new `--no-cache`, a required clock, an
  embedded instrument profile, a pure calculation function and a different order of profile and price work.
- **Decision:** as E.2.
- **Scope:** the seven matrix dimensions for `momentum`, with particular attention to the new time and
  cache controls, which have no baseline behavior to compare against.
- **Branch:** `audit/esc-e-renewal`, the one branch for all of ESC-E.
- **Detail:** [ESC_E4_MOMENTUM_EVIDENCE.md](ESC_E4_MOMENTUM_EVIDENCE.md). ESC-22, ESC-23 and ESC-24 were repaired on the project owner's decision (`d55c450`, `d9fa796`, `dfd0cf6`).

### E.5 — FCF/Earnings Growth

- **Problem:** FCF's calculation, resolver logic and presenter are unchanged except for how a run's clock and
  boundary reach them.
- **Decision:** as E.2.
- **Scope:** the seven matrix dimensions for `fcf-growth`.
- **Branch:** `audit/esc-e-renewal`, the one branch for all of ESC-E.
- **Detail:** [ESC_E5_FCF_EVIDENCE.md](ESC_E5_FCF_EVIDENCE.md).

### E.6 — Reconciliation and final acceptance

- **Problem:** the four slices produce separate evidence, and the ESC-20 style public-contract questions
  need one place to be closed.
- **Decision:** reconcile every ledger entry, repeat dated live checks for all four analyses, run the
  complete managed gate, and record acceptance in the same form as ESC-D.
- **Scope:** `ESC_E_FINAL_ACCEPTANCE.md` in the format of [ESC_D_FINAL_ACCEPTANCE.md](ESC_D_FINAL_ACCEPTANCE.md).
- **Branch:** `audit/esc-e-renewal`, the one branch for all of ESC-E.
- **Detail:** [ESC_E_FINAL_ACCEPTANCE.md](ESC_E_FINAL_ACCEPTANCE.md), awaiting the project owner's acceptance; ESC-D's
  [sixth slice](ESC_D_RENEWAL_PLAN.md#11-esc-d6--reconciliation-and-final-acceptance-record) was the template.

## 4. Proposed scope for E.2 to E.5

This section proposes; it does not decide. Where a dimension can be verified more narrowly than a full
re-run, the proposal says so and gives the reason, so review can accept or overrule each one.

### What the comparison and the inventory show

- **Calculation code is unchanged.** `git diff 7e2f8d2..main` shows no change to FCF's calculation, to either
  Graham calculation module beyond a literal method tag and a trace-helper name, or to Momentum's SMA and RSI
  arithmetic, which moved into a pure function with the same body. This is what lets Financial claims be
  verified more narrowly.
- **Time and data-lifecycle code changed everywhere.** One clock per run, a SEC eligibility boundary passed
  as data, a ten-minute skew tolerance for live runs (the hand-written future-availability comparisons were
  replaced by the shared freshness check, [ESC-21](ESC_A_DEFECT_LEDGER.md#esc-21--frozen-clock-skew-tolerance-and-the-consolidated-availability-check-have-no-ir-record)),
  and a single cache control ([Appendix A](#appendix-a-change-inventory-7e2f8d2-to-e6b1f76) groups G4 to G7).
  The comparison exercised these only on cold fetch, cache hit, `--no-cache` and three historical requests.
- **The Graham presenters were rewritten** (about 1,200 lines removed from one module and 1,400 added across four new ones). The
  comparison compared all four modes on KO, AAPL, MSFT, SPY and the ESC-17 scenario and found the text
  identical, which is strong evidence for those cases and none for branches those inputs do not reach.
- **Public contracts moved:** Graham JSON schema 6 (ESC-20), Momentum's new flags, version fields on
  persisted shapes, help text. Momentum's and FCF's JSON schema versions are unchanged.
- **The comparison did not reach** `--save-run`, replay, watchlist refresh, the orchestrator path, the
  Massive provider, expired or corrupt cache entries, or any invalid-input failure. IR rewrote these paths
  (Appendix A groups G9 and G11), and ESC-D had a separate cross-cutting slice for them.

### Proposal per dimension

| Dimension | Proposed scope | Reason |
| :--- | :--- | :--- |
| Presentation | Graham Number and Growth: the comparison's identical text and JSON count as evidence for the modes and cases it ran; add a differential render of every presenter branch (unavailable, not applicable, user override, warnings, failure reasons) through both revisions' presenters on the repository's existing fixtures, instead of hand-checking each branch live. Momentum and FCF: the comparison plus the new `--as-of` cases is enough; their presenter files are unchanged. | The presenter rewrite is the largest diff and the comparison cannot reach its error branches. Momentum's and FCF's presenters are byte-identical to the baseline; all 19 FCF pairs matched, and Momentum's text modes matched in the first pass and on RY.TO. |
| Data lifecycle | Full re-run for all four: cold, hit, bypass, expired, stale, future, legacy, corrupt, and provider failure during refresh. | The decision clock, the cache gate and the availability check all changed, and the comparison exercised three of the nine states. |
| Time | Full re-run for all four, with boundary cases at, just before and just after each eligibility boundary (filing acceptance for SEC, observation date for Momentum), and the new Momentum `--as-of`. | The boundary source changed from the adapter's clock to `effective_as_of`; look-ahead is the failure this dimension exists to catch. |
| Inputs and applicability | Full for Graham Number and Growth (the EPS-basis accept and default rule was rewritten and now differs by provider). Narrow for FCF and Momentum to the paths that changed: FCF's config object and Momentum's new options and ticker default. | FCF's and Momentum's input validation is otherwise unchanged. |
| Financial claims | One independent recomputation per analysis on dated evidence (two for FCF, one failing and one passing), plus the boundary and sign cases the ESC plan already lists, rather than re-deriving every classification. Momentum's recomputation uses a constructed fixture, as ESC-D did. | The diff shows the arithmetic unchanged. The comparison also shows identical calculated values on all four analyses. Overrule this if review wants the full oracle re-run. |
| Composition | Full for all four, and add the cross-cutting paths E.1 did not reach: `--save-run`, replay, watchlist refresh and the orchestrator handler for that analysis, each compared against the direct command's output. | IR changed every composition root, and ESC-D's separate cross-cutting slice has no equivalent here. Folding it into each analysis keeps the slice list as requested. |
| Public contracts | Full for all four: JSON keys, schema versions, exit codes, help text, documented examples against dated behavior (USAGE.md and SMOKE_TESTING.md already disagree with ESC-20's finding). | Version fields and documentation are where this package already found a gap. |

### What this means per slice

- **E.2 Graham Number:** the heaviest slice. Everything except Financial claims runs in full.
- **E.3 Graham Growth:** as E.2, plus the `fiscal_year` basis, which the baseline's CLI rejected.
- **E.4 Momentum:** heavy on Time, Data lifecycle and Composition because the controls are new and have no
  baseline; light on Presentation and Inputs.
- **E.5 FCF:** the lightest. Full Time, Data lifecycle and Composition, because its resolver's clock changed
  from the historical boundary to the run's execution time; narrow elsewhere.

## 5. Scope limits

- ESC-E uses one branch, `audit/esc-e-renewal`, and merges as one pull request at the end.
- No repair in E.1 to E.5. A finding is a ledger entry and a proposed disposition.
- No new strategies, algorithms, persistence schemas or provider coverage, as the ESC plan already excludes.
- The Massive provider is exercised only where a key is configured; otherwise its paths are covered by
  offline tests and the gap is recorded.
- Live checks do not certify universal upstream data accuracy; they supplement deterministic tests.

## 6. Acceptance criteria

- Every ledger entry, including ESC-20, has a verified disposition.
- Each of E.2 to E.5 covers its approved scope, with actual test and evidence links, and records any
  dimension verified more narrowly than a full re-run together with the reason review accepted.
- Independent arithmetic, dated live checks for all four analyses, and the complete managed gate with at
  least 85% coverage, recorded with revision and artifact paths.
- `ESC_E_FINAL_ACCEPTANCE.md` in ESC-D's format, including the limits retained.
- The IR contract's ESC re-run requirement ([§5](../integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md#5-acceptance-criteria))
  is met once the project owner accepts that record.

## 7. Background: why now

The IR contract requires the full audit matrix to re-run once, after IR as a whole is complete, to confirm
no analysis result changed across the work package. IR is complete as of IR.6 (2026-09-30), IR.3 having
moved out to the candidate backlog and IR.5 to the strategy wiring consolidation package. ESC-D's accepted
revision is the last point at which the four analyses were audited end to end.

---

## Appendix A: Change inventory, 7e2f8d2 to e6b1f76

`git diff 7e2f8d2..main -- src/` touches 78 files (3,220 insertions, 2,223 deletions) across 7 merged
pull requests (#44, #45, #46, #48, #49, #50 and #51). `pyproject.toml` changed in two
fields only (the license and mypy's target version), and `uv.lock` did not change. The table groups the files;
the lists below name every file.

| Group | Change | Files | Lines | Analyses it can affect | Matrix dimensions |
| :--- | :--- | ---: | :--- | :--- | :--- |
| G1 | Analyzer envelope: one `run_analysis(ticker, config, context)` | 7 | +220 / -258 | All four | Time, Composition, Public contracts |
| G2 | Graham strategy separation and EPS-basis rule | 6 | +143 / -104 | Graham Number, Graham Growth | Inputs and applicability, Public contracts |
| G3 | Graham calculation modules (method tag and trace helper only; no formula) | 3 | +26 / -18 | Graham Number, Graham Growth | Financial claims (structural), Presentation (trace) |
| G4 | FCF/Earnings Growth resolver clock and boundary threading | 1 | +43 / -14 | FCF/Earnings Growth | Time, Data lifecycle |
| G5 | Financial data layer: clock, freshness, provider eligibility | 11 | +199 / -69 | Graham Number, Graham Growth, FCF/Earnings Growth (quality.py also Momentum) | Data lifecycle, Time, Inputs and applicability |
| G6 | Historical market-data layer | 5 | +54 / -18 | Momentum | Data lifecycle, Time |
| G7 | Instrument-profile clock wiring | 2 | +6 / -5 | All four (identity and kind evidence) | Inputs and applicability, Data lifecycle |
| G8 | CLI and settings: new flags, composition, path guard | 6 | +296 / -88 | All four | Composition, Public contracts, Inputs and applicability |
| G9 | Orchestrator tool arguments and handlers | 1 | +49 / -31 | All four (orchestrator path) | Composition, Public contracts |
| G10 | Presenters: Graham presenter split and shared primitives | 6 | +1400 / -1238 | Graham Number, Graham Growth (`analysis_runs.py` replay dispatch serves all four) | Presentation, Public contracts |
| G11 | Workspace: execution adapters, selections, codecs, watchlists, refresh | 14 | +731 / -225 | All four (through `--save-run`, replay, watchlists and refresh) | Composition, Public contracts |
| G12 | Golden suite and evaluation harness | 14 | +49 / -153 | All four (offline evidence only) | Composition |
| G13 | Telemetry and worker utilities | 2 | +4 / -2 | None directly (telemetry is observational) | None |

Files not in the diff, and therefore byte-identical to the baseline: every FCF calculation, classification
and presenter module; `src/reporting/momentum.py` and `src/reporting/fcf_earnings_growth.py`; the SEC
facts parsers other than the adapter's eligibility argument; `src/data/financial/` modules other than those
in G5; and every Graham calculation formula.

**Files by group**

- **G1** (Analyzer envelope: one `run_analysis(ticker, config, context)`): `analysis/base_analyzer.py`, `analysis/strategy/graham_number/analyzer.py`, `analysis/strategy/graham_growth/analyzer.py`, `analysis/strategy/fcf_earnings_growth/analyzer.py`, `analysis/strategy/fcf_earnings_growth/models.py`, `analysis/strategy/fcf_earnings_growth/__init__.py`, `analysis/strategy/momentum/momentum_analyzer.py`
- **G2** (Graham strategy separation and EPS-basis rule): `analysis/shared/graham_contracts.py`, `analysis/strategy/graham_number/config.py`, `analysis/strategy/graham_growth/config.py`, `analysis/strategy/graham_number/__init__.py`, `analysis/strategy/graham_growth/__init__.py`, `data/financial/eps_basis.py`
- **G3** (Graham calculation modules (method tag and trace helper only; no formula)): `analysis/strategy/graham_number/calculation.py`, `analysis/strategy/graham_growth/calculation.py`, `data/financial/resolution_trace.py`
- **G4** (FCF/Earnings Growth resolver clock and boundary threading): `analysis/strategy/fcf_earnings_growth/input_resolver.py`
- **G5** (Financial data layer: clock, freshness, provider eligibility): `core/clock.py`, `data/financial/resolver.py`, `data/financial/cache.py`, `data/financial/facts.py`, `data/financial/production.py`, `data/financial/quote_freshness.py`, `data/quality.py`, `data/repositories/resolved_input_cache.py`, `data/sec_edgar/financial_facts.py`, `data/yfinance/financial_facts.py`, `data/massive/financial_facts.py`
- **G6** (Historical market-data layer): `data/cached_client.py`, `data/base_client.py`, `data/yfinance/client.py`, `data/market_data.py`, `data/repositories/market_data.py`
- **G7** (Instrument-profile clock wiring): `data/instrument_profile_cache.py`, `data/repositories/instrument_profiles.py`
- **G8** (CLI and settings: new flags, composition, path guard): `cli.py`, `cli_support.py`, `cli_composition.py`, `cli_database.py`, `config.py`, `utils/paths.py`
- **G9** (Orchestrator tool arguments and handlers): `orchestrator/analysis_tools.py`
- **G10** (Presenters: Graham presenter split and shared primitives): `reporting/graham.py`, `reporting/evidence_presentation.py`, `reporting/valuation_presentation.py`, `reporting/graham_number.py`, `reporting/graham_growth.py`, `reporting/analysis_runs.py`
- **G11** (Workspace: execution adapters, selections, codecs, watchlists, refresh): `workspace/execution.py`, `workspace/graham_number_execution.py`, `workspace/graham_growth_execution.py`, `workspace/fcf_growth_execution.py`, `workspace/momentum_execution.py`, `workspace/graham_number.py`, `workspace/graham_growth.py`, `workspace/requests.py`, `workspace/codecs.py`, `workspace/refresh.py`, `workspace/watchlists.py`, `workspace/method_aliases.py`, `cli_workspace.py`, `data/repositories/watchlists.py`
- **G12** (Golden suite and evaluation harness): `evaluation/__init__.py`, `evaluation/catalog.py`, `evaluation/composition.py`, `evaluation/evaluator.py`, `evaluation/models.py`, `evaluation/ollama_runner.py`, `evaluation/reporting.py`, `evaluation/runner.py`, `evaluation/cases/graham_number.py`, `evaluation/cases/graham_growth.py`, `evaluation/cases/graham_resolution.py`, `evaluation/fixtures/fcf_earnings_growth.py`, `evaluation/fixtures/graham.py`, `evaluation/fixtures/market_data.py`
- **G13** (Telemetry and worker utilities): `core/telemetry/recorder.py`, `utils/worker.py`

## Appendix B: Expected-difference register

Every intentional, accepted change to output or behavior since the baseline, each with its source. Nothing
is listed as expected unless a record says so. **Seen in E.1** says whether the comparison reached it.

| ID | Expected change | Source | Seen in E.1 |
| :--- | :--- | :--- | :--- |
| X-01 | Graham `--json` `analysis` value is `graham_number` or `graham_growth_value`, not `graham`; the same split applies to stored `analysis_id` | [IR.2 plan §6.13.6](../integration-readiness/IR2_ANALYZER_ENVELOPE_PLAN.md#6136-persistence-analysis_id-and-version-bumps) | Yes: all 12 Graham JSON pairs |
| X-02 | Invalid-input failure prose reads "the requested inputs are invalid", not "the requested Graham inputs are invalid" (`friendly_graham_failure` is now `friendly_valuation_failure`) | [IR contract Appendix A.3](../integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md#a3-accepted-exceptions-to-the-presentation-output-rule), IR.2.2 exception | No: no pair produced an invalid-input failure |
| X-03 | `graham-growth --eps-basis fiscal_year` is accepted by the CLI and `--save-run` (the baseline rejected it); both Graham commands' `--eps-basis` help text names the per-method rule | [IR.2 plan §6.1 item 11](../integration-readiness/IR2_ANALYZER_ENVELOPE_PLAN.md#61-problems-verified-against-the-code) | Yes: `graham-growth_KO_fiscalyear_json` (exit 2 to 0) and both commands' `--help` |
| X-04 | One provider-driven default EPS basis (SEC EDGAR `three_year_average`, every other provider `ttm`), applied by both Graham methods at every entry point; Graham Number with Massive and no `--eps-basis` now defaults to `ttm` where the CLI path used to reject it | [IR.2 plan §6.13.2 and §6.13.3](../integration-readiness/IR2_ANALYZER_ENVELOPE_PLAN.md#6132-file-inventory--removed-new-and-modified); divergence found at §6.1 item 13 | No: needs a Massive key |
| X-05 | Momentum gains `--as-of` and `--no-cache`; `MomentumSelection` gains `as_of` and `use_cache`; `MomentumToolArguments` gains `use_cache` | [IR.2 acceptance record](../integration-readiness/IR2_ANALYZER_ENVELOPE_PLAN.md#ir2-acceptance-record), [IR.2.6 plan A.1](../integration-readiness/IR2_6_MOMENTUM_PARITY_PLAN.md) | Yes: `momentum --help`; `--as-of` runs on `main` only |
| X-06 | A Momentum `--as-of` run reports the truncated observation date, not the requested date; provider-adjusted prices are revised retroactively, so an `--as-of` result is filtered to a date but reflects today's adjusted view | [IR.2.6 plan B.1 item 2](../integration-readiness/IR2_6_MOMENTUM_PARITY_PLAN.md#b1-decisions-flagged-for-the-project-owner) and A.5 | Partly: `--as-of 2025-12-31` runs on `main` only (no baseline equivalent) |
| X-07 | Momentum composes the instrument profile before calculation, so a failed price fetch costs one extra metadata lookup | [IR.2.6 plan B.1 item 3](../integration-readiness/IR2_6_MOMENTUM_PARITY_PLAN.md#b1-decisions-flagged-for-the-project-owner) | No |
| X-08 | Persisted version fields: `MomentumSelection.config_schema_version` 1 to 2; Momentum `(method_version, result_schema_version)` (1, 1) to (1, 2); the evidence codec checks a per-method table; Graham selections carry their own `analysis_id`; stored Momentum runs and watchlist entries saved earlier no longer decode | [IR.2 acceptance record](../integration-readiness/IR2_ANALYZER_ENVELOPE_PLAN.md#ir2-acceptance-record), [IR.2.6 plan B.1 item 1](../integration-readiness/IR2_6_MOMENTUM_PARITY_PLAN.md#b1-decisions-flagged-for-the-project-owner), IR.2 plan §6.10 | No: direct commands do not print them |
| X-09 | One `executed_at` per run feeds every decision and event clock; Momentum's result timestamp is the run's boundary, not a wall-clock read taken during calculation; Graham resolvers' quote-freshness clock is injected | IR.2 plan [§6.1 item 9](../integration-readiness/IR2_ANALYZER_ENVELOPE_PLAN.md#61-problems-verified-against-the-code) and §6.11; IR.2.3 and IR.2.4 rows | Yes: Golden `MOM-01`, `MOM-02`, `MOM-ETF-01` timestamps; `--as-of` timestamp on `main` |
| X-10 | SEC EDGAR filing-eligibility checks take the analysis boundary as an explicit `effective_as_of` argument instead of reusing the adapter's retrieval clock | IR.2 plan §6.11; IR.2.4 row | Yes, as no change: the SEC-backed `--as-of` pairs matched |
| X-12 | `use_cache=False` (`--no-cache`) never opens storage or runs the readiness check, for all four analyses; one cache control | [IR.2.5 plan, final acceptance record](../integration-readiness/IR2_5_CACHE_UNIFICATION_PLAN.md#5-final-acceptance-record) | Yes: the three `--no-cache` pairs and the Momentum `--no-cache` run |
| X-13 | Golden suite version `h1-v3` to `h1-v4`; the `graham_method_selection` component and each Graham case's method constraint are removed, folded into ordinary strategy selection | [IR.2 plan §6.13.7](../integration-readiness/IR2_ANALYZER_ENVELOPE_PLAN.md#6137-evaluation-harness-graham_method_selection-folds-into-ordinary-strategy-selection) | Yes: case definitions differ only by those constraints |
| X-14 | Orchestrator Graham handlers run through `GrahamNumberAnalyzer` and `GrahamGrowthAnalyzer` instead of the service functions | [IR.2 plan §6.1 item 5](../integration-readiness/IR2_ANALYZER_ENVELOPE_PLAN.md#61-problems-verified-against-the-code) | Yes: the Golden suite dispatches through it and every observed value matched |
| X-15 | Workspace command names, `runs list --analysis`, alias text, `watchlist delete` and `rename`; Momentum entries in `watchlist show` gain `as_of` and `use_cache` | [IR contract Appendix A.3](../integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md#a3-accepted-exceptions-to-the-presentation-output-rule) (IR.6.1), [IR.6 plan](../integration-readiness/IR6_WATCHLIST_LIFECYCLE_COMPLETION.md), [IR.2.6 plan B.3 item 7](../integration-readiness/IR2_6_MOMENTUM_PARITY_PLAN.md#b3-found-during-implementation) | No: direct commands do not reach them |
| X-16 | On Windows, a partly anchored path is rejected with a readable reason; relative `log_dir` and `telemetry_log_dir` resolve under the project folder | [IR.8 plan](../integration-readiness/IR8_WINDOWS_PATH_ANCHORING_GUARD.md#5-acceptance-criteria) | No: no pair used such a path |
| X-17 | Momentum's presentation `schema_version` is 5 (was 4), and a boundary before the first observation is `input_unavailable` with reason code `no_eligible_observations`; a live run rejects a bar dated beyond the skew tolerance after the execution time; an `--as-of` run fetches history only up to the boundary and is cached separately from a live run | The decisions recorded in ESC-22 to ESC-24 in the defect ledger (project owner, 2026-10-01); commits `dfd0cf6`, `d9fa796` and `d55c450` | Yes: Momentum JSON pairs after the repairs |

X-11 was withdrawn from the register on 2026-09-30 and is not reused: its only sources are `ARCHITECTURE.md` and a commit
message, so it is [ESC-21](ESC_A_DEFECT_LEDGER.md#esc-21--frozen-clock-skew-tolerance-and-the-consolidated-availability-check-have-no-ir-record).

Not in the register, so not expected: Graham's JSON `schema_version` 5 to 6
([ESC-20](ESC_A_DEFECT_LEDGER.md#esc-20--graham-json-presentation-schema-version-changed-from-5-to-6-with-no-ir-record-and-two-user-documents-still-say-5)).

## Appendix C: Decision records and history

- **Baseline choice (2026-09-30).** ESC-D's accepted revision `7e2f8d2` (PR #42), as the ESC-E request
  specified. The baseline cannot import on Python 3.12 or 3.13 (the defect IR.4 fixed), so both revisions
  were run on the baseline worktree's Python 3.14.7 environment, which has the same locked dependencies as
  `main` (`uv.lock` is unchanged between the revisions). A first pass ran the baseline on 3.14.7 and
  `main` on its pinned 3.12.14; its results agree with the reported ones and are kept in the evidence.
