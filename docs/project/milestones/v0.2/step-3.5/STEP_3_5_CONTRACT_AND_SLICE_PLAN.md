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
  - Every calculated numeric metric is a `MetricResult` with an explicit `ReasonCode`. Nothing
    missing becomes zero, neutral or `NaN`. Scores, zones, bands, ranks and completeness are typed
    fields of the strategy's own result, not `MetricResult`s.
  - Every input respects the analysis boundary, including the industry class.
  - Fundamentals come from SEC EDGAR annual filings only.
  - A strategy slice ships complete: analyzer, wiring, presentation, tests, user guide, and
    `FINANCE_MATH.md` and `GLOSSARY.md` entries.
  - The managed quality gate after every slice, and explicit authorization before the next begins.
- **Where the detail lives:** shared definitions, applicability and ranking in
  [Shared definitions](STEP_3_5_SHARED_DEFINITIONS.md); per-strategy formulas and edge cases in
  [Strategy specifications](STEP_3_5_STRATEGY_SPECIFICATIONS.md); live source evidence and the
  arithmetic oracle for Piotroski in the [Piotroski evidence record](STEP_3_5_PIOTROSKI_EVIDENCE.md);
  the fields, result shapes, tests and non-goals each slice plan starts from in
  [Slice inputs](STEP_3_5_SLICE_INPUTS.md).
  Why the step looks the way it does is in [Background](#6-background); decision records are in
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

**Slice plans come first.** No slice starts without an accepted slice plan. The plans are written
after SWC and PKG land, against the `main` of that day, because both packages change the paths and
wiring a plan must name. Each plan states:

- exact files and starting points;
- new data fields and their mappings;
- the boundary between resolver and calculator;
- the result shape;
- tests, including the slice's edge cases;
- presentation and CLI integration;
- documentation;
- explicit non-goals.

What is already stable for each slice is in [Slice inputs](STEP_3_5_SLICE_INPUTS.md). The
specification is complete now; only the handoff is deferred, on purpose. Each slice below carries
the standard `⚠ no slice plan yet` marker until its handoff is accepted. Here the marker means
"written immediately before the slice begins", not an omission.

**Mappings are hypotheses until proven.** The taxonomy concepts named in these documents are
candidates. A mapping becomes a production mapping only after captured filings show its meaning,
units, period behavior and the filers it holds for. 3.5.1 does that work.

**One analyzer per review gate.** Slices 3.5.4, 3.5.5 and 3.5.6 each hold more than one deliverable.
Their slice plans split them into sub-slices (3.5.4a Altman, 3.5.4b Beneish, and so on), each with
its own quality gate and authorization.

### 3.5.1 — Data mappings and applicability

- **Problem:** the seven strategies need line items the financial-fact layer does not map yet,
  an industry classification nothing in the codebase records, and split history the market-data
  boundary does not expose.
- **Decision:** classify by the SEC SIC code as filed with the selected annual filing, so the
  industry class respects the analysis boundary like every other input. It is filing evidence, not
  part of the instrument profile. GICS is not used.
- **Entry criterion:** before any mapping or applicability code is written, the slice confirms
  from captured filings that a filing's SEC header keeps the `ASSIGNED-SIC` of its filing date. If
  it does not, sector-gated strategies are `unavailable` for a requested `as_of`, and the slice
  returns to the project owner before continuing.
- **Scope:** `AGENTS.md` §0 removal; new `FinancialField` members with evidence-approved us-gaap
  and ifrs-full mappings; as-filed SIC evidence; applicability helpers; split history in the
  historical market-data boundary; new `ReasonCode` members these need.
- **Detail:** [Shared definitions §1–§3](STEP_3_5_SHARED_DEFINITIONS.md#1-applicability) and
  [Slice inputs §2](STEP_3_5_SLICE_INPUTS.md#2-351--data-mappings-and-applicability).
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
- **Detail:** [Shared definitions §4–§9](STEP_3_5_SHARED_DEFINITIONS.md#4-market-capitalization)
  and [Slice inputs §3](STEP_3_5_SLICE_INPUTS.md#3-352--shared-metrics-and-ranking-helper).
  ⚠ no slice plan yet

### 3.5.3 — Piotroski F-Score

- **Problem:** Piotroski is the first analyzer built from scratch against the IR.2 envelope, and
  IR names it as that envelope's test.
- **Decision:** it gets a slice of its own. Any envelope change it needs is applied to every
  analyzer in the same slice, never accepted as a Piotroski-only special case.
- **Scope:** analyzer, SWC descriptor registration (direct command, watchlist selection, refresh,
  `--json`), presenter, tests, user guide, Finance Math and Glossary entries.
- **Detail:** [Strategy specifications §1](STEP_3_5_STRATEGY_SPECIFICATIONS.md#1-piotroski-f-score)
  the [Piotroski evidence record](STEP_3_5_PIOTROSKI_EVIDENCE.md) and
  [Slice inputs §4](STEP_3_5_SLICE_INPUTS.md#4-353--piotroski-f-score). ⚠ no slice plan yet

### 3.5.4 — Altman Z-Score and Beneish M-Score

- **Problem:** both are distress and accounting-risk screens that must refuse financial issuers
  and must not impute missing components.
- **Decision:** Altman selects the classic Z for manufacturers and Z″ for other non-financial
  issuers by SIC code. Beneish is unavailable when any index cannot be computed; it has no partial
  score. Its depreciation index prefers depreciation alone and falls back to combined D&A as a
  named deviation.
- **Scope:** both analyzers with the same completeness as 3.5.3.
- **Detail:** [Strategy specifications §2–§3](STEP_3_5_STRATEGY_SPECIFICATIONS.md#2-altman-z-score)
  and [Slice inputs §5](STEP_3_5_SLICE_INPUTS.md#5-354--altman-and-beneish). ⚠ no slice plan yet

### 3.5.5 — Valuation multiples, Interest Coverage and ROIC

- **Problem:** three single-ticker analyzers that consume the 3.5.2 metrics directly.
- **Decision:** the valuation strategy reports EV/EBITDA and FCF yield only. Interest Coverage
  uses gross interest expense only. ROIC uses one NOPAT definition and a guarded three-year
  incremental view.
- **Scope:** three analyzers with the same completeness as 3.5.3.
- **Detail:** [Strategy specifications §4, §6, §7](STEP_3_5_STRATEGY_SPECIFICATIONS.md#4-cash-flow-valuation-multiples)
  and [Slice inputs §6](STEP_3_5_SLICE_INPUTS.md#6-355--valuation-multiples-interest-coverage-and-roic).
  ⚠ no slice plan yet

### 3.5.6 — Magic Formula and ranked refresh view

- **Problem:** Magic Formula is cross-sectional, but `BaseAnalyzer.run_analysis` is per ticker.
- **Decision:** the Magic Formula analyzer computes one ticker's return on capital and earnings
  yield like any other analyzer. Ranking is a separate, deterministic view over the persisted runs
  of one watchlist refresh, built on the 3.5.2 ranking helper and never persisted. The universe is
  always a watchlist.
- **Scope:** analyzer with the same completeness as 3.5.3; the ranked view and its command.
- **Detail:** [Strategy specifications §5](STEP_3_5_STRATEGY_SPECIFICATIONS.md#5-greenblatt-magic-formula),
  [Shared definitions §9](STEP_3_5_SHARED_DEFINITIONS.md#9-ranking-helper) and
  [Slice inputs §7](STEP_3_5_SLICE_INPUTS.md#7-356--magic-formula-and-ranked-refresh-view).
  ⚠ no slice plan yet

### 3.5.7 — Side-by-side refresh table

- **Problem:** a refresh already runs several strategies over a watchlist and records one
  `refresh_id`, but its results can only be inspected run by run.
- **Decision:** a table view, one row per ticker and one column group per strategy, rebuilt from
  the persisted runs of one refresh. It adds no persistence and no new batch mechanism.
- **Scope:** the view, its command, `--json` output, tests and `WORKSPACE.md` documentation.
- **Detail:** [Shared definitions §10](STEP_3_5_SHARED_DEFINITIONS.md#10-side-by-side-refresh-table)
  and [Slice inputs §8](STEP_3_5_SLICE_INPUTS.md#8-357--side-by-side-refresh-table).
  ⚠ no slice plan yet

### 3.5.8 — Golden suite and cross-cutting docs

- **Problem:** the new strategies must take part in the golden suite, and the user-facing indexes
  must list them.
- **Scope:** golden-suite cases for each new strategy; the strategy-guide index and root README;
  the regression issuer set named in [Acceptance criteria](#5-acceptance-criteria).
- **Detail:** [Slice inputs §9](STEP_3_5_SLICE_INPUTS.md#9-358--golden-suite-and-cross-cutting-docs).
  ⚠ no slice plan yet

## 4. Out of scope

- P/E and PEG screens; gross-margin stability.
- Composite scores and any cross-strategy weighting.
- Fixed-charge and lease-adjusted coverage.
- Unlevered FCF and FCF / EV.
- Trailing-twelve-month (quarterly) inputs.
- User-defined filter expressions (such as "coverage > 5×").
- Non-recurring-item adjustments to EBIT.
- Lease normalization across accounting frameworks
  ([Shared definitions §6](STEP_3_5_SHARED_DEFINITIONS.md#lease-liabilities)).
- Ranking an ad-hoc ticker list without a watchlist.
- Changing any existing strategy's formulas or classifications. FCF-Growth's FCF yield becoming
  available through the shared market cap is evidence becoming available, not a formula change.
- Changing the default selection of a new or existing watchlist. Each new strategy is selected
  explicitly.
- Standard delivery surfaces (MCP server, HTTP API, Parquet/Arrow export): deferred, to be
  reconsidered when Step 3.5 closes ([deferred note](../deferred/DEFERRED_STANDARD_DELIVERY_SURFACES.md)).

## 5. Acceptance criteria

- **Reproducible results:** every strategy produces deterministic, provenance-tagged results for a
  regression issuer set that includes at least one manufacturer, one non-manufacturer, one bank,
  one REIT, one utility, one IFRS filer, one negative-EBIT firm, one firm with no reported debt and
  one issuer with multiple share classes.
- **Applicability:** each strategy applies, applies with a warning, or returns `not_applicable`
  exactly as the matrix in [Shared definitions §1](STEP_3_5_SHARED_DEFINITIONS.md#1-applicability)
  states for the issuer's industry class. An unknown industry class produces the `unavailable`
  outcome that section specifies.
- **Point-in-time:** a run with a requested `as_of` uses no evidence filed, priced or classified
  after that boundary, including the industry class and the share count.
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

### A.5 Earlier Piotroski planning reconciled (2026-10-02)

Planning done in September 2026, before the step was revised, was never committed. It covered a
five-strategy contract, a Piotroski research record and a thirteen-slice Piotroski handoff plan.
Its evidence is kept in the [Piotroski evidence record](STEP_3_5_PIOTROSKI_EVIDENCE.md). Where its
decisions differ from the current documents, this table says which stands.

| Topic | September position | What stands now | Why |
| :--- | :--- | :--- | :--- |
| Dilution test | Project-owner decision of 2026-09-19: compute two readings of equity issuance, broad (scored) and narrow (shown only); no share-count proxy | Reversed. One test: split-adjusted shares outstanding did not increase. Confirmed by the project owner on 2026-10-02 | Live evidence showed issuance cannot be established from structured filings for some large issuers (Apple after fiscal 2021), and the two readings could not be separated from the available concepts. A share count is available for nearly every filer. The cost, net rather than gross dilution, is stated in the spec and the guide |
| Incomplete score | No total unless all nine tests are available | Partial score from six tests, shown as "*x* of *n*", never ranked | Financial issuers are applicable and routinely lack two tests; a null total would make the strategy useless for them. The denominator and the missing tests are always shown |
| Missing debt component | Never zero | Zero only with supporting evidence ([Shared definitions §6](STEP_3_5_SHARED_DEFINITIONS.md#total-debt)) | A blanket zero flatters the issuer; a blanket refusal makes EV unavailable for most filers |
| Unchanged leverage | No point, with no exception | No point, except zero long-term debt in both years | A debt-free firm cannot reduce leverage further |
| Income for ROA | Open: continuing operations, net income or profit including minority interests | Net income as reported | Many filers never report continuing-operations income |
| Financial issuers | Not applicable | Applicable with a warning | Decided in the 2026-09-30 revision ([Shared definitions §1](STEP_3_5_SHARED_DEFINITIONS.md#1-applicability)) |
| IFRS filers | Unsupported | In scope | The SEC provider already resolves ifrs-full annual facts |
| Delivery | Thirteen Piotroski slices, then four more strategy tracks | One slice per strategy group ([§2](#2-sequence-and-status)) | SWC removes most per-strategy wiring work |
| Magic Formula ranking | A persisted batch record of the universe and factors | A view recomputed from stored runs, never persisted | The refresh already stores every run of the universe |

Unchanged from September and now written into the spec: beginning-of-year assets for turnover,
strict comparisons, three total-asset dates, and unavailable-is-not-fail.

### A.6 Review hardening (2026-10-02)

A review of the reconciled documents found one contradiction and several places where a developer
would have had to decide policy while coding. Each was decided:

| Topic | Before | Decision | Why |
| :--- | :--- | :--- | :--- |
| Applicability criterion | "Financial issuers, REITs and utilities receive `not_applicable`" | The criterion defers to the matrix | The old wording contradicted the matrix for Piotroski and for utilities |
| Industry class | Current SIC from EDGAR submissions, stored in the instrument profile | The SIC as filed with the selected annual filing, kept as filing evidence | The submissions SIC is today's value. Applying it to a historical run is look-ahead |
| Leases in EV | Operating leases "always excluded", justified by ASC 842 and IFRS 16 | Each framework's own accounting, with no normalization and a stated comparability limit | The IFRS 16 justification was wrong: IFRS EBITDA is before lease cost |
| Share count for market cap | "From the selected filing" | The balance-sheet count at fiscal year-end *t*; the cover-page count is never used | The date was undefined. This is the count the existing resolver returns |
| Multi-class issuers | "Valued at the primary listing's price" | `unavailable` when the filer reports no unambiguous total count | The existing resolver already rejects ambiguous class values |
| Duplicate issuers in a ranking | Keep the first listed | Keep the alphabetically first ticker | "First listed" made the result depend on input order. Excluding every duplicate would drop an issuer from a watchlist holding two of its share classes |
| Tied positions | Unstated | Competition ranking (1, 1, 3); ticker order is display only | Tests and presentation need one convention |
| ROIC tax rate | Clamped to [0, 0.50] with no explanation | Same rule; the reported rate is kept, a clamp raises a diagnostic, and the reasons are stated | The clamp changes the result and must not look arbitrary |
| Incremental ROIC | Baseline capital sign implicit | Baseline invested capital must be positive | The 10% floor has no meaning otherwise |
| `MetricResult` scope | "Every metric" | Calculated numeric metrics only | Scores, zones, bands and ranks are result fields |
| Refresh views | One row per ticker, assumption unstated | At most one run per ticker and strategy; otherwise the view refuses | A refresh runs (ticker, selection) pairs |
| Beneish depreciation index | "Depreciation", with no rule for filers that report only combined D&A | Depreciation alone where an approved mapping provides it for both years; otherwise combined D&A for both years, named as a deviation in the result; otherwise `unavailable` | The model is defined on depreciation alone. Requiring it would make the score unavailable for many filers; using D&A silently would misstate what was computed |
| Partial Beneish score | Not offered | Still not offered, now stated | The score is one regression equation whose coefficients assume all eight inputs. Piotroski is an additive count, so a partial count has meaning |
| SIC evidence check | A verification step | An entry criterion of 3.5.1 | The whole applicability design rests on it |
| Field mappings | Candidate concepts listed | Hypotheses until captured filings prove them | Taxonomy names do not establish financial meaning |
| Slice plans | Marked missing, with no rule | Required before each slice, written after SWC and PKG; stable inputs recorded now | Plans written before those packages would name paths and wiring that no longer exist |

Three review points were not adopted as proposed:

- **Rewording the `⚠ no slice plan yet` markers.** The marker is the wording `AGENTS.md`
  prescribes for a work unit without a lower-level plan. It stays, and [§3](#3-the-slices) says
  what it means here.
- **Excluding duplicate issuers outright.** A deterministic choice keeps the issuer in the ranking.
- **Writing every slice plan now.** The September Piotroski plan named thirteen slices and their
  files, and was stale within two weeks. The stable part is recorded in
  [Slice inputs](STEP_3_5_SLICE_INPUTS.md); the rest waits for the code it describes.
