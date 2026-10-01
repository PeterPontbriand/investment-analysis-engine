# Step 3.5 — Quantitative Screens: Contract and Slice Plan

Adds seven deterministic screening strategies, the shared metric definitions they depend on, and
cross-sectional ranking and side-by-side views over a watchlist refresh.

Placement among other work packages: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **What this step adds:** Piotroski F-Score, Altman Z / Z″, Beneish M-Score, Cash-Flow Valuation
  Multiples, Greenblatt Magic Formula, Interest Coverage, and ROIC / Incremental ROIC; one shared
  definition each for market cap, EBIT, EBITDA, EV, invested capital and FCF; a reusable ranking
  helper; and a ranked, side-by-side view over the runs of one watchlist refresh.
- **What it does not do:** composite scores, cross-strategy weighting, user-defined filter
  expressions, trading signals, or ranking against an implicit market-wide universe. Full list:
  [Out of scope](#4-out-of-scope).
- **Entry condition:** implementation waits for integration readiness (IR), strategy wiring
  consolidation (SWC), the dead code audit (R3) and the package rename (PKG). 3.5.1 begins by
  removing `AGENTS.md` §0, as that section requires.
- **Rules every slice follows:**
  - One definition per shared metric, used everywhere, with no per-strategy fallback variants.
  - Every metric is a `MetricResult` with an explicit `ReasonCode`. Nothing missing becomes zero,
    neutral or `NaN`.
  - Fundamentals come from SEC EDGAR annual filings only.
  - A strategy slice ships complete: analyzer, wiring, presentation, tests, user guide, and
    `FINANCE_MATH.md` and `GLOSSARY.md` entries.
  - The managed quality gate after every slice, and explicit authorization before the next begins.
- **Where the detail lives:** shared definitions, applicability and ranking in
  [Shared definitions](STEP_3_5_SHARED_DEFINITIONS.md); per-strategy formulas and edge cases in
  [Strategy specifications](STEP_3_5_STRATEGY_SPECIFICATIONS.md). Why the step looks the way it
  does is in [Background](#6-background); decision records are in
  [Appendix A](#appendix-a-decision-records-and-history).

## 2. Sequence and status

Each slice ends with the managed quality gate and is gated by explicit authorization before the
next begins.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| 3.5.1 | [Data mappings and applicability](#351--data-mappings-and-applicability) | Planned | |
| 3.5.2 | [Shared metrics and ranking helper](#352--shared-metrics-and-ranking-helper) | Planned | |
| 3.5.3 | [Piotroski F-Score](#353--piotroski-f-score) | Planned | |
| 3.5.4 | [Altman Z-Score and Beneish M-Score](#354--altman-z-score-and-beneish-m-score) | Planned | |
| 3.5.5 | [Valuation multiples, Interest Coverage and ROIC](#355--valuation-multiples-interest-coverage-and-roic) | Planned | |
| 3.5.6 | [Magic Formula and ranked refresh view](#356--magic-formula-and-ranked-refresh-view) | Planned | |
| 3.5.7 | [Side-by-side refresh table](#357--side-by-side-refresh-table) | Planned | |
| 3.5.8 | [Golden suite and cross-cutting docs](#358--golden-suite-and-cross-cutting-docs) | Planned | |

## 3. The slices

Every slice uses its own branch off `main`, named `feat/step-3-5-<n>-<topic>`, and merges to
`main` once accepted, following the IR.4, IR.6 and IR.8 precedent.

### 3.5.1 — Data mappings and applicability

- **Problem:** the seven strategies need line items the financial-fact layer does not map yet,
  an industry classification nothing in the codebase records, and split history the market-data
  boundary does not expose.
- **Decision:** classify by SEC SIC code, read from the EDGAR submissions data the SEC provider
  already fetches and recorded in the instrument profile. GICS is not used.
- **Scope:** `AGENTS.md` §0 removal; new `FinancialField` members with us-gaap and ifrs-full
  mappings; SIC in the instrument profile; applicability helpers; split history in the historical
  market-data boundary; new `ReasonCode` members these need.
- **Detail:** [Shared definitions §1–§3](STEP_3_5_SHARED_DEFINITIONS.md#1-applicability).
  ⚠ no slice plan yet

### 3.5.2 — Shared metrics and ranking helper

- **Problem:** EV, invested capital and market cap would otherwise be defined inside whichever
  strategy needs them first, and diverge in the next one. No market-cap evidence exists today, so
  FCF-Growth's optional FCF yield is always unavailable.
- **Decision:** define market cap, EBIT, D&A, EBITDA, EV and invested capital once, as pure
  functions over resolved facts, and reuse the existing FCF and FCF-yield definitions. FCF-Growth's
  FCF yield adopts the shared market cap, with no formula change. The ranking helper is a pure,
  analysis-agnostic function, tested here on synthetic inputs before Magic Formula consumes it.
- **Scope:** shared metric functions and their tests; `src/analysis/shared/ranking.py`;
  FCF-Growth's market-cap wiring; `FINANCE_MATH.md` entries for every shared metric.
- **Detail:** [Shared definitions §4–§9](STEP_3_5_SHARED_DEFINITIONS.md#4-market-capitalization).
  ⚠ no slice plan yet

### 3.5.3 — Piotroski F-Score

- **Problem:** Piotroski is the first analyzer built from scratch against the IR.2 envelope, and
  IR names it as that envelope's test.
- **Decision:** it gets a slice of its own. Any envelope change it needs is applied to every
  analyzer in the same slice, never accepted as a Piotroski-only special case.
- **Scope:** analyzer, SWC descriptor registration (direct command, watchlist selection, refresh,
  `--json`), presenter, tests, user guide, Finance Math and Glossary entries.
- **Detail:** [Strategy specifications §1](STEP_3_5_STRATEGY_SPECIFICATIONS.md#1-piotroski-f-score).
  ⚠ no slice plan yet

### 3.5.4 — Altman Z-Score and Beneish M-Score

- **Problem:** both are distress and accounting-risk screens that must refuse financial issuers
  and must not impute missing components.
- **Decision:** Altman selects the classic Z for manufacturers and Z″ for other non-financial
  issuers by SIC code. Beneish is unavailable when any index cannot be computed.
- **Scope:** both analyzers with the same completeness as 3.5.3.
- **Detail:** [Strategy specifications §2–§3](STEP_3_5_STRATEGY_SPECIFICATIONS.md#2-altman-z-score).
  ⚠ no slice plan yet

### 3.5.5 — Valuation multiples, Interest Coverage and ROIC

- **Problem:** three single-ticker analyzers that consume the 3.5.2 metrics directly.
- **Decision:** the valuation strategy reports EV/EBITDA and FCF yield only. Interest Coverage
  uses gross interest expense only. ROIC uses one NOPAT definition and a guarded three-year
  incremental view.
- **Scope:** three analyzers with the same completeness as 3.5.3.
- **Detail:** [Strategy specifications §4, §6, §7](STEP_3_5_STRATEGY_SPECIFICATIONS.md#4-cash-flow-valuation-multiples).
  ⚠ no slice plan yet

### 3.5.6 — Magic Formula and ranked refresh view

- **Problem:** Magic Formula is cross-sectional, but `BaseAnalyzer.run_analysis` is per ticker.
- **Decision:** the Magic Formula analyzer computes one ticker's return on capital and earnings
  yield like any other analyzer. Ranking is a separate, deterministic view over the persisted runs
  of one watchlist refresh, built on the 3.5.2 ranking helper and never persisted. The universe is
  always a watchlist.
- **Scope:** analyzer with the same completeness as 3.5.3; the ranked view and its command.
- **Detail:** [Strategy specifications §5](STEP_3_5_STRATEGY_SPECIFICATIONS.md#5-greenblatt-magic-formula)
  and [Shared definitions §9](STEP_3_5_SHARED_DEFINITIONS.md#9-ranking-helper).
  ⚠ no slice plan yet

### 3.5.7 — Side-by-side refresh table

- **Problem:** a refresh already runs several strategies over a watchlist and records one
  `refresh_id`, but its results can only be inspected run by run.
- **Decision:** a table view, one row per ticker and one column group per strategy, rebuilt from
  the persisted runs of one refresh. It adds no persistence and no new batch mechanism.
- **Scope:** the view, its command, `--json` output, tests and `WORKSPACE.md` documentation.
- **Detail:** [Shared definitions §10](STEP_3_5_SHARED_DEFINITIONS.md#10-side-by-side-refresh-table).
  ⚠ no slice plan yet

### 3.5.8 — Golden suite and cross-cutting docs

- **Problem:** the new strategies must take part in the golden suite, and the user-facing indexes
  must list them.
- **Scope:** golden-suite cases for each new strategy; the strategy-guide index and root README;
  the regression issuer set named in [Acceptance criteria](#5-acceptance-criteria).
- **Detail:** ⚠ no slice plan yet

## 4. Out of scope

- P/E and PEG screens; gross-margin stability.
- Composite scores and any cross-strategy weighting.
- Fixed-charge and lease-adjusted coverage.
- Unlevered FCF and FCF / EV.
- Trailing-twelve-month (quarterly) inputs.
- User-defined filter expressions (such as "coverage > 5×").
- Non-recurring-item adjustments to EBIT.
- Ranking an ad-hoc ticker list without a watchlist.
- Changing any existing strategy's formulas or classifications. FCF-Growth's FCF yield becoming
  available through the shared market cap is evidence becoming available, not a formula change.

## 5. Acceptance criteria

- **Reproducible results:** every strategy produces deterministic, provenance-tagged results for a
  regression issuer set that includes at least one manufacturer, one non-manufacturer, one bank,
  one REIT, one utility, one IFRS filer, one negative-EBIT firm, one firm with no reported debt and
  one issuer with multiple share classes.
- **Applicability:** financial issuers, REITs and utilities receive the `not_applicable` results
  [Shared definitions §1](STEP_3_5_SHARED_DEFINITIONS.md#1-applicability) specifies.
- **No imputation:** no metric is zero, neutral, `NaN` or `Inf` because an input was missing.
- **Workflow:** every strategy is selectable on watchlists and refreshable, so Step 3.6 can verify
  it in the Light Mode workflow.
- **Documentation:** each strategy has a user guide under `docs/user/strategies/`, Finance Math
  entries and Glossary terms; the ranked view and side-by-side table are documented in
  `WORKSPACE.md`.
- **Quality gate:** the complete managed gate after every slice, with at least 85% coverage and
  meaningful branch coverage on new financial code.

## 6. Background

Step 3.5 was accepted with five strategies: Piotroski, Altman, Beneish, unlevered valuation
multiples and Magic Formula. ROIC and interest coverage were deferred to Milestone v0.3 Step 4.

On 2026-09-30 the project owner revised the step:

- **Interest Coverage and ROIC moved in.** They answer questions the other five do not
  (near-term debt service, and returns on new capital), and they reuse line items the other five
  already need.
- **Ranking became a shared primitive.** Magic Formula is the first strategy that needs
  cross-sectional ranking, and any later multi-metric ranking would otherwise re-implement
  percentile logic, tie handling and missing-data exclusion.
- **The contract was tightened** so that it does not contradict the project's fail-closed rules.

The decisions themselves are recorded in [Appendix A](#appendix-a-decision-records-and-history).

---

## Appendix A: Decision records and history

Kept for the record. Nothing here is needed to understand what Step 3.5 does or what comes next.

### A.1 Milestone-plan entry condition

Moved here from `IMPLEMENTATION_PLAN.md` row 14, which carries only status and date: this plan is
accepted, but implementation waits for integration readiness (IR), strategy wiring consolidation
(SWC), the dead code audit (R3), and the package rename (PKG). See the
[milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status) for why those four run first.
Module paths in this plan's detail documents use the current `src` layout; they follow PKG's rename.

### A.2 Strategy set expanded from five to seven (2026-09-30)

- **Interest Coverage added:** a direct, intuitive solvency companion to Altman, with low
  incremental data cost once EBIT, EBITDA and interest-expense mappings exist.
- **ROIC / Incremental ROIC added:** previously a Milestone v0.3 Step 4.1 candidate. Kept as a
  full peer strategy after review: trailing ROIC differs from Magic Formula's return on capital in
  being after tax and using average capital, and incremental ROIC asks whether new capital still
  earns an attractive return, which no other strategy asks.
- **Ranking helper and multi-strategy views made explicit deliverables,** so that Magic Formula
  does not own private ranking logic.

### A.3 Review decisions (2026-09-30)

A critical review of the expanded contract found it contradicting its own fail-closed rules in
several places. Each resolution was decided, not left open:

- **Piotroski:** a missing input makes that test unavailable, never a fail; the score is reported
  over the tests available, and fewer than six makes it unavailable.
- **Beneish:** any index that cannot be computed makes the whole score unavailable; no index
  defaults to 1.0.
- **ROIC:** one NOPAT definition with a defined tax-rate rule; no EBIT-only fallback variant.
- **EV and invested capital:** one definition each, shared by every consumer; operating leases
  always excluded from EV, never "when disclosures permit."
- **Altman:** Z″ for non-manufacturers, selected by SIC code, because the classic model was fit on
  manufacturers.
- **Interest Coverage:** zero interest with zero debt is a distinct, favorable outcome, not
  "inapplicable"; net-only interest disclosures are unavailable; bands have fixed thresholds.
- **Valuation multiples:** renamed from "unlevered" because FCF yield is an equity-level measure;
  FCF / EV dropped as a levered-over-unlevered mismatch.
- **Fixed-charge coverage:** deferred outright rather than kept as an optional extension.
- **Data sources:** fundamentals from SEC EDGAR only, because no other configured provider can
  serve a historical `as_of`; GICS replaced by SIC because GICS is not available from the
  project's sources.
- **Ranking helper:** eligibility over the intersection of metrics, average ranks for ties, a
  minimum of ten eligible names, rank sums rather than averaged percentiles, and no weights.
- **Slicing:** each strategy slice ships its own tests and documentation instead of deferring them
  to a final slice.

### A.4 Repository fit (2026-09-30)

When the revised contract was checked against the codebase before it was committed:

- **Outcomes:** the contract's "inapplicable" and "not meaningful" states map to the existing
  `MetricStatus.NOT_APPLICABLE`; Piotroski's partial score is a field of its own result, not a new
  status.
- **Batch:** watchlist refresh already runs several strategies over one universe and records a
  shared `refresh_id`, so multi-strategy batch execution is that mechanism, not a new batch ID.
- **Magic Formula:** made a per-ticker analyzer plus a ranked view, because the analyzer envelope
  is per ticker.
- **Market cap and FCF yield:** FCF-Growth already defines FCF yield and waits for market-cap
  evidence, so the shared market cap feeds both strategies through one definition.
- **Piotroski:** split into its own slice because IR names it as the analyzer envelope's test.
