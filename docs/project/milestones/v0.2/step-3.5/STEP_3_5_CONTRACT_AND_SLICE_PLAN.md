# Step 3.5 — Quantitative Screens: Contract and Slice Plan

Adds deterministic screening strategies, the shared metric definitions they depend on, and a
side-by-side view over a watchlist refresh.

Placement among other work packages: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **What this step adds:** Piotroski F-Score, Altman Z / Z″, the accrual ratio, Cash-Flow Valuation
  Multiples, Interest Coverage, ROIC / Incremental ROIC and Shareholder Yield; one shared
  definition each for market cap, EBIT, EBITDA, EV, invested capital and FCF; and a side-by-side
  view over the runs of one watchlist refresh.
- **What it does not do:** composite scores, cross-strategy weighting, ranking companies against each
  other (a separate evaluator application does that, [A.16](#a16-strategy-set-revised-2026-11-02)),
  user-defined filter expressions or trading signals. Full list: [Out of scope](#4-out-of-scope).
- **Entry condition:** implementation waits for integration readiness (IR), strategy wiring
  consolidation (SWC), the dead code audit (R3), provider health (PH), package layering (LAY, which resolves the two-way
  package dependencies filed as [issue #114](https://github.com/PeterPontbriand/investment-analysis-engine/issues/114)) and the package rename (PKG). 3.5.0b began by
  removing `AGENTS.md` §0, as that section required ([A.10](#a10-removing-the-consolidation-rules-moves-to-350b-2026-10-25)).
- **Rules every slice follows:**
  - One definition per shared metric, used everywhere, with no per-strategy fallback variants.
  - Every calculated numeric metric is a `MetricResult` with an explicit `ReasonCode`. Nothing
    missing becomes zero, neutral or `NaN`. Scores, zones, bands and completeness are typed
    fields of the strategy's own result, not `MetricResult`s.
  - Every input respects the analysis boundary, including the industry class.
  - Fundamentals come from SEC EDGAR annual filings only.
  - Every strategy result carries one explicit result-level status, `execution_status`, defined in
    [Shared definitions §2](STEP_3_5_SHARED_DEFINITIONS.md#result-level-status); the strategy's native-status
    function returns it, as FCF-Growth's does. Momentum's provider failure is a stored run
    ([A.8](#a8-momentum-provider-failure-and-result-status-question-from-ph2-2026-10-07), decided 2026-10-25), and
    its status is added by slice 3.5.0a. A second
    question, whether every strategy uses one shared mapping from statuses to a run outcome
    ([A.9](#a9-one-shared-mapping-from-statuses-to-a-run-outcome-question-from-esc-29-2026-10-10)), is decided (yes, 2026-10-19) and was implemented by slice PC.4 (2026-10-21) of the
    [pattern-cleanup plan](../pattern-cleanup/PC_CONTRACT_AND_SLICE_PLAN.md#pc4--one-shared-mapping-from-statuses-to-a-run-outcome).
  - A strategy slice ships complete: analyzer, wiring (including its `headline` function for the
    side-by-side table), presentation, tests, user guide, and `FINANCE_MATH.md` and `GLOSSARY.md` entries.
  - The managed quality gate after every slice, and explicit authorization before the next begins.
- **Where the detail lives:** shared definitions and applicability in
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
| 3.5.0a | [Momentum result-level status](STEP_3_5_0_SLICE_PLAN.md#350a--momentum-result-level-status) | Complete | 2026-10-25 |
| 3.5.0b | [Side-by-side refresh table](STEP_3_5_0_SLICE_PLAN.md#350b--side-by-side-refresh-table) | Complete | 2026-10-25 |
| 3.5.1a | [As-filed SIC code and applicability](STEP_3_5_1_SLICE_PLAN.md#351a--as-filed-sic-code-and-applicability) | Complete | 2026-10-25 |
| 3.5.1b | [Balance-sheet instants](STEP_3_5_1_SLICE_PLAN.md#351b--balance-sheet-instants) | Complete | 2026-10-25 |
| 3.5.1c | [Annual period fields](STEP_3_5_1_SLICE_PLAN.md#351c--annual-period-fields) | Complete | 2026-10-26 |
| 3.5.1d | [Split history and the market-cap price basis](STEP_3_5_1_SLICE_PLAN.md#351d--split-history-and-the-market-cap-price-basis) | Complete | 2026-10-26 |
| 3.5.2a | [Slice plan and ranking helper](STEP_3_5_2_SLICE_PLAN.md#352a--slice-plan-and-ranking-helper) | Complete | 2026-10-26 |
| 3.5.2b | [Pure shared metrics](STEP_3_5_2_SLICE_PLAN.md#352b--pure-shared-metrics) | Complete | 2026-10-26 |
| 3.5.2c | [Listing check for market capitalization](STEP_3_5_2_SLICE_PLAN.md#352c--listing-check-for-market-capitalization) | Complete | 2026-10-26 |
| 3.5.2d | [Shared input assembly](STEP_3_5_2_SLICE_PLAN.md#352d--shared-input-assembly) | Complete | 2026-10-28 |
| 3.5.2e | [FCF-Growth adopts the shared market cap](STEP_3_5_2_SLICE_PLAN.md#352e--fcf-growth-adopts-the-shared-market-cap) | Complete | 2026-10-28 |
| 3.5.2f | [FCF-Growth's annual reader on the shared resolver entry](STEP_3_5_2_SLICE_PLAN.md#352f--fcf-growths-annual-reader-on-the-shared-resolver-entry) | Complete | 2026-10-29 |
| 3.5.3a | [Slice plan and the nine-test calculator](STEP_3_5_3_SLICE_PLAN.md#353a--slice-plan-and-the-nine-test-calculator) | Complete | 2026-10-29 |
| 3.5.3b1 | [Shared year-end functions that need no new evidence](STEP_3_5_3_SLICE_PLAN.md#353b1--shared-year-end-functions-that-need-no-new-evidence) | Complete | 2026-10-29 |
| 3.5.3b2 | [Year-end discovery, share-count series and captured evidence](STEP_3_5_3_SLICE_PLAN.md#353b2--year-end-discovery-share-count-series-and-captured-evidence) | Complete | 2026-10-30 |
| 3.5.3c | [Side-by-side text layout](STEP_3_5_3_SLICE_PLAN.md#353c--side-by-side-text-layout) | Complete | 2026-10-30 |
| 3.5.3d | [The Piotroski strategy](STEP_3_5_3_SLICE_PLAN.md#353d--the-piotroski-strategy) | Complete | 2026-10-31 |
| 3.5.3e1 | [Repetition review and extraction](STEP_3_5_3_SLICE_PLAN.md#353e1--repetition-review-and-extraction) | Complete | 2026-11-01 |
| 3.5.3e1b | [One analyzer base](STEP_3_5_3_SLICE_PLAN.md#353e1b--one-analyzer-base) | Complete | 2026-11-01 |
| 3.5.3e2 | [Guide, issues and records](STEP_3_5_3_SLICE_PLAN.md#353e2--guide-issues-and-records) | Complete | 2026-11-01 |
| 3.5.3e1c | [Generated execution, command, refresh and tool bodies](STEP_3_5_3_SLICE_PLAN.md#353e1c--generated-execution-command-refresh-and-tool-bodies) | Complete | 2026-11-01 |
| Issue 207 | [Align how the existing strategies order their checks and provider requests](https://github.com/PeterPontbriand/investment-analysis-engine/issues/207) | Complete | 2026-11-01 |
| Issue 210 | [Strategy development: four generator and provider shortfalls (3.5.3)](https://github.com/PeterPontbriand/investment-analysis-engine/issues/210) | Complete | 2026-11-01 |
| #204 | [Stale anchor filing and the anchor rule](#a17-stale-anchor-filing-and-the-anchor-rule-2026-11-09) ([issue 204](https://github.com/PeterPontbriand/investment-analysis-engine/issues/204)) | Complete | 2026-11-09 |
| Issue 246 | [`sec_edgar` returns no usable EPS facts for NVDA despite Company Facts containing `EarningsPerShareDiluted`](#a18-eps-and-diluted-shares-across-a-restatement-issue-246-2026-11-09) ([issue 246](https://github.com/PeterPontbriand/investment-analysis-engine/issues/246)) | Complete | 2026-11-09 |
| Issue 245 | [Graham strategies: align input years to the shared anchor and report the anchor filing](#a19-graham-input-years-follow-the-shared-anchor-issue-245-2026-11-09) ([issue 245](https://github.com/PeterPontbriand/investment-analysis-engine/issues/245)) | Complete | 2026-11-10 |
| Issue 250 | [Graham strategies: serve a reason code with every non-OK status](https://github.com/PeterPontbriand/investment-analysis-engine/issues/250) | Next | |
| 3.5.5 | [Valuation multiples, Interest Coverage and ROIC](#355--valuation-multiples-interest-coverage-and-roic) | Planned | |
| 3.5.4 | [Altman Z-Score and accrual ratio](#354--altman-z-score-and-accrual-ratio) | Planned | |
| 3.5.6 | [Shareholder Yield](#356--shareholder-yield) | Planned | |
| 3.5.7 | [Golden suite and cross-cutting docs](#357--golden-suite-and-cross-cutting-docs) | Planned | |

Issue 207 and issue 210 finish before API.1 ([A.14](#a14-353-sub-slices-and-scope-2026-10-29)), in that order, after 3.5.3e1c; API.1 starts after them.

Issue 246 follows #204, issue 245 follows issue 246, and issue 250 follows issue 245; all three finish before 3.5.5 starts ([A.17](#a17-stale-anchor-filing-and-the-anchor-rule-2026-11-09)).

Once Step 3.5 closes, a person, not an AI agent, reviews [`docs/project/STRATEGY_DEVELOPMENT.md`](../../../STRATEGY_DEVELOPMENT.md); language and readability criticisms of the guide wait for that review.

3.5.5 starts after work package API's API.7 merges ([API plan](../api/API_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status)),
and 3.5.4 follows 3.5.5 ([A.15](#a15-355-before-354-2026-11-02)).
From 3.5.5 on, "the same completeness as 3.5.3" also covers the glossary-terms edit site that API.6 adds: an
investor glossary entry for each term the strategy's headline cells, statuses and selection fields name
([API plan A.4](../api/API_CONTRACT_AND_SLICE_PLAN.md#a4-help-content-in-the-gui-2026-10-30)).

## 3. The slices

Every slice uses its own branch off `main`, named `feat/step-3-5-<n>-<topic>`, and merges to
`main` once accepted, following the IR.4, IR.6 and IR.8 precedent.

**Slice plans come first.** No slice starts without an accepted slice plan. The plans are written
after SWC and PKG land, against the `main` of that day, because both packages change the paths and
wiring a plan must name. Each plan states:

- exact files and starting points;
- the decision this contract left open, A.8 (Momentum's provider failure), decided 2026-10-25; the run-outcome mapping
  ([A.9](#a9-one-shared-mapping-from-statuses-to-a-run-outcome-question-from-esc-29-2026-10-10)) is decided and was implemented by slice PC.4 (2026-10-21) of the
  [pattern-cleanup plan](../pattern-cleanup/PC_CONTRACT_AND_SLICE_PLAN.md#pc4--one-shared-mapping-from-statuses-to-a-run-outcome);
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

**Every strategy is added the same way.** Each strategy slice adds its strategy through the
[edit-site table in `docs/project/STRATEGY_DEVELOPMENT.md`](../../../STRATEGY_DEVELOPMENT.md#edit-sites-of-a-strategy) (the table lists every site and file and is
generated from one site data file; the original design is in [SWC.1 design §17](../swc/SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#17-edit-sites-for-a-new-strategy)): the analyzer package, the
descriptor and its behavior bundle, the CLI-tier and evaluation-tier entries, and the strategy-owned files
each of them references. That includes the orchestrator tool (a `ToolName` member, an arguments model, a
dependency class and a handler), which the golden suite needs to select the strategy. Once SWC.5 and SWC.6
land, a slice starts from `scripts/new_strategy.py`, which writes the typed stubs and the five mechanical
one-line edits, and tracks progress with `scripts/strategy_status.py`. Each slice plan names the table's
sites it touches. The guide's workflow is the reference.

Every Step 3.5 strategy slice records in its plan's implementation record every point where `docs/project/STRATEGY_DEVELOPMENT.md` fell short, and fixes the guide in the same slice where that is within its scope. 3.5.0b's own record of the points it met is
[A.3 of the 3.5.0 slice plan](STEP_3_5_0_SLICE_PLAN.md#a3-350b-implementation-record-2026-10-25); 3.5.3's plan links it.

**Repetition checkpoint.** Every strategy of this step reads SEC annual filings only and shares the same selection
fields, so their wiring is expected to be near-identical. The first strategy slice (3.5.3) owns a review
before the second strategy starts (3.5.5a):

- **Review:** compare Piotroski's final wiring files with the generator's stubs and list every region that
  differs only by strategy name, identifier or type.
- **Site 19:** weigh moving the watchlist options into strategy files, as one watchlist subcommand per
  strategy added by iterating `CLI_STRATEGIES` ([SWC.1 design H.10](../swc/SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h10-the-watchlist-flag-bundle-an-approved-exception-to-the-no-growing-shared-class-rule)).
  The change alters the command syntax users type, so it needs its own decision. Weighed in 3.5.3
  ([B.3 of the 3.5.3 slice plan](STEP_3_5_3_SLICE_PLAN.md#b3-decisions-of-353b-to-353e)): no change in Step 3.5, and
  decided with API.3.
- **Extraction:** for exactly that repeated code, extract shared helper functions into the shared module
  of the layer that owns it, and update the generator's templates to call them. Helpers are functions, not a
  base class or a registry; existing strategies' behavior and output do not change. Where nothing repeated,
  record that none was found.
- **Exit condition:** 3.5.3's implementation record states the regions found and the helpers extracted, or
  that none was found, and the extraction is merged. The 3.5.5a slice plan is not accepted until it does.

**Mappings are hypotheses until proven.** The taxonomy concepts named in these documents are
candidates. A mapping becomes a production mapping only after captured filings show its meaning,
units, period behavior and the filers it holds for. 3.5.1 does that work.

**One analyzer per review gate.** Slices 3.5.4 and 3.5.5 each hold more than one deliverable.
Their slice plans split them into sub-slices (3.5.4a Altman, 3.5.4b the accrual ratio, and so on), each with
its own quality gate and authorization.

### 3.5.0 — Side-by-side refresh table

- **Problem:** a refresh already runs several strategies over a watchlist and records one
  `refresh_id`, but its results can only be inspected run by run. The table needs a per-strategy
  headline for every strategy, and building it after the new strategies would mean retrofitting every one.
- **Decision:** build the table first, over the four existing strategies, so the SWC behavior bundle's
  `headline` member has a real consumer before any new analyzer is written and every new strategy supplies
  it from the start. It is a table view, one row per ticker and one column group per strategy, rebuilt
  from the persisted runs of one refresh, with no persistence and no new batch mechanism. It depends only
  on the finished SWC work and on runs that already exist: no new data (3.5.1), no shared metric (3.5.2).
- **Scope:** Momentum's result-level status (3.5.0a, [A.8](#a8-momentum-provider-failure-and-result-status-question-from-ph2-2026-10-07));
  `AGENTS.md` §0 removal (the first commit of 3.5.0b); the `headline` member and
  the `Headline` and `HeadlineCell` types added to the SWC behavior bundle, with the four existing
  strategies' functions. This one slice also updates, once, the generator's templates, the site data file,
  the specimen strategy and the closed-field test (T15) for the new member. The view, its command, a typed
  `--json` model and checked-in schema, the command's entry in `JSON_DOCUMENTS`
  (`workspace_documents/json_documents.py`), which T21 requires, tests and `WORKSPACE.md` documentation.
- **Detail:** [Shared definitions §10](STEP_3_5_SHARED_DEFINITIONS.md#10-side-by-side-refresh-table),
  [Slice inputs §2](STEP_3_5_SLICE_INPUTS.md#2-350--side-by-side-refresh-table) and the
  [SWC design §3.3](../swc/SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#33-behavior-members-and-the-two-tiers).
  [Slice plan for 3.5.0a and 3.5.0b](STEP_3_5_0_SLICE_PLAN.md)

### 3.5.1 — Data mappings and applicability

- **Problem:** the strategies need line items the financial-fact layer does not map yet,
  an industry classification nothing in the codebase records, and split history the market-data
  boundary does not expose.
- **Decision:** classify by the SEC SIC code as filed with the selected annual filing, so the
  industry class respects the analysis boundary like every other input. It is filing evidence, not
  part of the instrument profile. GICS is not used.
- **Entry criterion:** before any mapping or applicability code is written, the slice confirms
  from captured filings that a filing's SEC header keeps the `ASSIGNED-SIC` of its filing date. If
  it does not, sector-gated strategies are `unavailable` for a requested `as_of`, and the slice
  returns to the project owner before continuing.
- **Scope:** new `FinancialField` members with evidence-approved us-gaap
  and ifrs-full mappings; as-filed SIC evidence; applicability helpers; split history in the
  historical market-data boundary; new `ReasonCode` members these need.
- **Detail:** [Shared definitions §1–§3](STEP_3_5_SHARED_DEFINITIONS.md#1-applicability) and
  [Slice inputs §3](STEP_3_5_SLICE_INPUTS.md#3-351--data-mappings-and-applicability).
  [Slice plan for 3.5.1a to 3.5.1d](STEP_3_5_1_SLICE_PLAN.md)

### 3.5.2 — Shared metrics and ranking helper

- **Problem:** EV, invested capital and market cap would otherwise be defined inside whichever
  strategy needs them first, and diverge in the next one. No market-cap evidence exists today, so
  FCF-Growth's optional FCF yield is always unavailable.
- **Decision:** define market cap, gross profit, EBIT, D&A, EBITDA, EV and invested capital once, as pure
  functions over resolved facts, and move the existing FCF and FCF-yield definitions beside them unchanged in
  behavior. Assemble the shared inputs once (the anchor year-end, the share-count path, the price and the split
  history, and the balance-sheet and annual inputs at that year-end), so no consumer builds them itself. FCF-Growth's
  FCF yield adopts the shared market cap, with no formula change. The slice built a ranking helper in
  3.5.2a, which was removed on 2026-11-02 ([A.16](#a16-strategy-set-revised-2026-11-02)).
  The slice is six sub-slices, each with its own branch, managed gate and authorization
  ([A.13](#a13-352-sub-slices-and-scope-2026-10-26)); the listing check that decides whether a ticker is a share of
  the issuer is its own sub-slice, 3.5.2c, and the assembly follows it as 3.5.2d.
- **Scope:** shared metric functions and their tests, gross profit included; the listing check of the anchor
  filing's cover; the shared input assembly, which also routes the balance-sheet series
  through the production financial-facts provider and declares a split-history provider protocol that carries `as_of`
  and `adjusted_on`; FCF-Growth's market-cap wiring; `FINANCE_MATH.md` entries for every shared metric.
- **Detail:** [Shared definitions §4–§9](STEP_3_5_SHARED_DEFINITIONS.md#4-market-capitalization),
  [Slice inputs §4](STEP_3_5_SLICE_INPUTS.md#4-352--shared-metrics-and-ranking-helper) and the
  [slice plan for 3.5.2a to 3.5.2f](STEP_3_5_2_SLICE_PLAN.md).

### 3.5.3 — Piotroski F-Score

- **Problem:** Piotroski is the first analyzer built from scratch against the IR.2 envelope, and
  IR names it as that envelope's test.
- **Decision:** it gets a slice of its own. Any envelope change it needs is applied to every
  analyzer in the same slice, never accepted as a Piotroski-only special case.
- **Scope:** analyzer, SWC descriptor registration (direct command, watchlist selection, refresh,
  `--json`, and the orchestrator tool: `ToolName` member, arguments model, dependency class and handler),
  presenter, tests, user guide, Finance Math and Glossary entries, covering every site in the edit-site table;
  and the repetition checkpoint above. The slice is five sub-slices, each with its own branch, managed gate and
  authorization ([A.14](#a14-353-sub-slices-and-scope-2026-10-29)): the plan and the pure nine-test calculator (3.5.3a),
  the inputs at three year-ends (3.5.3b), the side-by-side text layout (3.5.3c), the strategy (3.5.3d) and the
  repetition checkpoint (3.5.3e). The checkpoint is four sub-slices, 3.5.3e1 (review and extraction), 3.5.3e1b (one
  analyzer base, `BaseAnalyzer[ResultT, *ConfigT]`), 3.5.3e2 (the guide fixes and the records) and 3.5.3e1c (the
  generated execution, command, refresh and tool bodies), all complete.
  - The side-by-side table's one-line-per-ticker text layout is about 170 characters wide over four strategies (the
    3.5.0 slice plan measured 174 to 186) and would be about 460 over eleven. This slice adds the fifth strategy, so
    3.5.3c packs the column groups into bands of at most 120 characters (Q12). `--json` is unaffected.
- **Detail:** [Strategy specifications §1](STEP_3_5_STRATEGY_SPECIFICATIONS.md#1-piotroski-f-score)
  the [Piotroski evidence record](STEP_3_5_PIOTROSKI_EVIDENCE.md),
  [Slice inputs §5](STEP_3_5_SLICE_INPUTS.md#5-353--piotroski-f-score) and the
  [slice plan for 3.5.3a to 3.5.3e](STEP_3_5_3_SLICE_PLAN.md).

### 3.5.5 — Valuation multiples, Interest Coverage and ROIC

- **Problem:** three single-ticker analyzers that consume the 3.5.2 metrics directly.
- **Decision:** the valuation strategy reports EV/EBITDA and FCF yield only. Interest Coverage
  uses gross interest expense only. ROIC uses one NOPAT definition and a guarded three-year
  incremental view.
- **Scope:** three analyzers with the same completeness as 3.5.3.
- **Detail:** [Strategy specifications §4, §6, §7](STEP_3_5_STRATEGY_SPECIFICATIONS.md#4-cash-flow-valuation-multiples)
  and [Slice inputs §7](STEP_3_5_SLICE_INPUTS.md#7-355--valuation-multiples-interest-coverage-and-roic).
  ⚠ no slice plan yet

### 3.5.4 — Altman Z-Score and accrual ratio

- **Problem:** both are distress and accounting-risk screens. Altman must refuse financial issuers and
  neither may impute a missing component.
- **Decision:** Altman selects the classic Z for manufacturers and Z″ for other non-financial
  issuers by SIC code. The accrual ratio is (net income − operating cash flow) ÷ average total assets,
  the cash-flow version, built only from data already mapped. It pairs with Altman because it keeps the
  accrual core of Beneish's model and complements Piotroski's cash-versus-income test
  ([A.16](#a16-strategy-set-revised-2026-11-02)). Its full specification, edge cases and decisions are
  settled in its slice plan.
- **Scope:** both analyzers with the same completeness as 3.5.3.
- **Detail:** [Strategy specifications §2–§3](STEP_3_5_STRATEGY_SPECIFICATIONS.md#2-altman-z-score)
  and [Slice inputs §6](STEP_3_5_SLICE_INPUTS.md#6-354--altman-and-the-accrual-ratio). ⚠ no slice plan yet

### 3.5.6 — Shareholder Yield

- **Problem:** dividends, buybacks and debt reduction each return capital to shareholders, and no
  strategy reports them together as one share of market value.
- **Decision:** Shareholder Yield is dividend yield + net buyback yield + net debt-reduction yield, each as a
  percentage of market cap, with total returned capital ÷ FCF reported as a metric (not a cap or filter).
  Net debt reduction comes from the change in the already-mapped total-debt instants and net buybacks from
  the split-adjusted share-count series (3.5.1d). Dividends paid needs a new mapping, evidenced in this
  slice's plan the way 3.5.1 evidenced the others. It takes the slice Magic Formula vacated
  ([A.16](#a16-strategy-set-revised-2026-11-02)).
- **Scope:** analyzer with the same completeness as 3.5.3, and the dividends-paid mapping.
- **Detail:** [Strategy specifications §5](STEP_3_5_STRATEGY_SPECIFICATIONS.md#5-shareholder-yield) and
  [Slice inputs §8](STEP_3_5_SLICE_INPUTS.md#8-356--shareholder-yield).
  ⚠ no slice plan yet

### 3.5.7 — Golden suite and cross-cutting docs

- **Problem:** the new strategies must take part in the golden suite, and the user-facing indexes
  must list them.
- **Scope:** golden-suite cases for each new strategy; the strategy-guide index and root README;
  the regression issuer set named in [Acceptance criteria](#5-acceptance-criteria).
- **Detail:** [Slice inputs §9](STEP_3_5_SLICE_INPUTS.md#9-357--golden-suite-and-cross-cutting-docs).
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
- Ranking companies against each other, with or without a watchlist: a separate evaluator application owns it ([A.16](#a16-strategy-set-revised-2026-11-02)).
- Reverse DCF: recorded as a candidate in the [evidence provider roadmap](../../../EVIDENCE_PROVIDER_ROADMAP.md).
- Changing any existing strategy's formulas or classifications. FCF-Growth's FCF yield becoming
  available through the shared market cap is evidence becoming available, not a formula change.
- Changing the default selection of a new or existing watchlist. Each new strategy is selected
  explicitly.
- Standard delivery surfaces (MCP server, Parquet/Arrow export): deferred, to be
  reconsidered when Step 3.5 closes ([deferred note](../deferred/DEFERRED_STANDARD_DELIVERY_SURFACES.md)).
  The HTTP API moved to work package [API](../api/API_CONTRACT_AND_SLICE_PLAN.md) on 2026-10-30.

## 5. Acceptance criteria

- **Reproducible results:** every strategy produces deterministic, provenance-tagged results for a
  regression issuer set that includes at least one manufacturer, one non-manufacturer, one bank,
  one REIT, one utility, one IFRS filer, one negative-EBIT firm, one firm with no reported debt and
  one issuer with multiple share classes.
- **Applicability:** each strategy applies, applies with a warning, or returns `not_applicable`
  exactly as the matrix in [Shared definitions §1](STEP_3_5_SHARED_DEFINITIONS.md#1-applicability)
  states for the issuer's industry class. An unknown industry class makes a sector-gated
  strategy's result `input_unavailable` with a reason code saying so, and Piotroski, which is not
  sector-gated, runs and states the class is unknown, as that section specifies.
- **Point-in-time:** a run with a requested `as_of` uses no evidence filed, priced or classified
  after that boundary, including the industry class and the share count.
- **No imputation:** no metric is zero, neutral, `NaN` or `Inf` because an input was missing.
- **Workflow:** every strategy is selectable on watchlists and refreshable, so Step 3.6 can verify
  it in the Light Mode workflow.
- **Documentation:** each strategy has a user guide under `docs/user/strategies/`, Finance Math
  entries and Glossary terms; the side-by-side table is documented in
  `WORKSPACE.md`.
- **Quality gate:** the complete managed gate after every slice, with at least 85% coverage and
  meaningful branch coverage on new financial code.

## 6. Background

Step 3.5 was accepted with five strategies: Piotroski, Altman, Beneish, unlevered valuation
multiples and Magic Formula. ROIC and interest coverage were deferred to Step 4 (then Milestone v0.3, now v0.4).

On 2026-09-30 the project owner revised the step:

- **Interest Coverage and ROIC moved in.** They answer questions the other five do not
  (near-term debt service, and returns on new capital), and they reuse line items the other five
  already need.
- **Ranking became a shared primitive.** Magic Formula is the first strategy that needs
  cross-sectional ranking, and any later multi-metric ranking would otherwise re-implement
  percentile logic, tie handling and missing-data exclusion.
- **The contract was tightened** so that it does not contradict the project's fail-closed rules.

On 2026-11-02 the project owner revised the strategy set again: Magic Formula and the ranked view left the
step, an accrual ratio replaced Beneish, and Shareholder Yield took Magic Formula's slice
([A.16](#a16-strategy-set-revised-2026-11-02)).

The decisions themselves are recorded in [Appendix A](#appendix-a-decision-records-and-history).

---

## Appendix A: Decision records and history

Kept for the record. Nothing here is needed to understand what Step 3.5 does or what comes next.

### A.1 Milestone-plan entry condition

Moved here from `IMPLEMENTATION_PLAN.md` row 15, which carries only status and date: this plan is
accepted, but implementation waits for integration readiness (IR), strategy wiring consolidation
(SWC), the dead code audit (R3), provider health (PH) and the package rename (PKG). See the
[milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status) for why those five run first.
Module paths in this plan's detail documents name the `investment_analysis_engine` package, as renamed by PKG.2.

### A.2 Strategy set expanded from five to seven (2026-09-30)

*Superseded in part: the ranking helper was removed ([A.16](#a16-strategy-set-revised-2026-11-02)).*

- **Interest Coverage added:** a direct, intuitive solvency companion to Altman, with low
  incremental data cost once EBIT, EBITDA and interest-expense mappings exist.
- **ROIC / Incremental ROIC added:** previously a Step 4.1 candidate. Kept as a
  full peer strategy after review: trailing ROIC differs from Magic Formula's return on capital in
  being after tax and using average capital, and incremental ROIC asks whether new capital still
  earns an attractive return, which no other strategy asks.
- **Ranking helper and multi-strategy views made explicit deliverables,** so that Magic Formula
  does not own private ranking logic.

### A.3 Review decisions (2026-09-30)

*Superseded in part: the Beneish and ranking-helper decisions no longer apply ([A.16](#a16-strategy-set-revised-2026-11-02)).*

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

*Superseded in part: Magic Formula and its ranked view were removed ([A.16](#a16-strategy-set-revised-2026-11-02)).*

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

*Superseded in part: the Magic Formula ranking row no longer applies ([A.16](#a16-strategy-set-revised-2026-11-02)).*

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

*Superseded in part: the Beneish and duplicate-issuer ranking rows no longer apply ([A.16](#a16-strategy-set-revised-2026-11-02)).*

A review of the reconciled documents found one contradiction and several places where a developer
would have had to decide policy while coding. Each was decided:

| Topic | Before | Decision | Why |
| :--- | :--- | :--- | :--- |
| Applicability criterion | "Financial issuers, REITs and utilities receive `not_applicable`" | The criterion defers to the matrix | The old wording contradicted the matrix for Piotroski and for utilities |
| Industry class | Current SIC from EDGAR submissions, stored in the instrument profile | The SIC as filed with the selected annual filing, kept as filing evidence | The submissions SIC is today's value. Applying it to a historical run is look-ahead |
| Leases in EV | Operating leases "always excluded", justified by ASC 842 and IFRS 16 | Each framework's own accounting, with no normalization and a stated comparability limit | The IFRS 16 justification was wrong: IFRS EBITDA is before lease cost |
| Share count for market cap | "From the selected filing" | The balance-sheet count at fiscal year-end *t*; the cover-page count is never used (reversed in part by [A.12](#a12-share-count-from-the-cover-page-and-equivalent-concepts-2026-10-25)) | The date was undefined. This is the count the existing resolver returns |
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

### A.7 Build order and result status (2026-10-03)

*Superseded in part: the sort option over the ranked view was removed ([A.16](#a16-strategy-set-revised-2026-11-02)).*

Two decisions made while finalizing the SWC design, which this step's documents own:

| Topic | Before | Decision | Why |
| :--- | :--- | :--- | :--- |
| Side-by-side table | Slice 3.5.7, after every strategy | Slice 3.5.0, before 3.5.1, over the four existing strategies | The SWC behavior bundle needs a per-strategy `headline` member. Added after the strategy slices it would force a retrofit of eleven strategies and a mid-step edit of the generator, the site list, the specimen and the closed-field test. Built first, every new strategy supplies it from its own slice and the member is added once. The table needs no new data (3.5.1) and no shared metric (3.5.2), so it does not wait for them; only its sort option over the ranked view waits, and moves to 3.5.6. The golden suite is renumbered 3.5.7 and `AGENTS.md` §0 is removed by 3.5.0, the first implementation slice. |
| Native status | One headline metric reports its status; several report none (a rule proposed in the SWC design) | Every result carries one explicit `execution_status`, and the native-status function returns it for all seven | It is a result-shape decision, so this step owns it ([Shared definitions §2](STEP_3_5_SHARED_DEFINITIONS.md#result-level-status)). The execution adapter needs the same value to map a run to its workspace outcome, FCF-Growth already works this way, and no strategy specification contradicts it: each row of the table restates an outcome the specification already defines. |

### A.8 Momentum provider failure and result status: question from PH.2 (2026-10-07)

Graham Number, Graham Growth and FCF Growth store a provider failure as an unavailable result with its
resolution trace. Momentum raises it instead, so it reaches only the failure envelope and is not a stored
outcome. Provider-failure classification
([PH.2](../provider-health/PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md)) leaves that difference as it is.
Whether Momentum should record an unavailable result for a provider failure is decided with the result-level
status ([Shared definitions §2](STEP_3_5_SHARED_DEFINITIONS.md#result-level-status)), because the answer fixes
Momentum's `execution_status` for that case. Decision pending.

**Decided 2026-10-25: yes.** The project owner approved storing a Momentum provider failure as a run with
`execution_status` `provider_error`, outcome `failed`, with its resolution trace and the provider failure passed to
the capture so the automatic provider check still fires. Too little history for the trend is `input_unavailable`
(RSI, when computed, is still stored and shown), and a failed data-quality check is `input_unavailable` with a text
reason, as in the shared financial resolver. Slice 3.5.0a implements it; the
[3.5.0 slice plan](STEP_3_5_0_SLICE_PLAN.md#350a--momentum-result-level-status) holds the mapping of every exception.

The common strategy-document header ([SWC.4c.1](../swc/SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h34-common-header-and-tail-for-strategy-documents-2026-10-09)) gives Momentum a calculation `status`. That slice left it as `ok` for every document that exists, with too little history shown as `result.trend` `UNKNOWN`; whether that case becomes `input_unavailable` is decided here.

### A.9 One shared mapping from statuses to a run outcome: question from ESC-29 (2026-10-10)

Each strategy writes its own function from its assembly and calculation statuses to a `RunOutcome`: Graham Number
(`classify_graham_number_outcome`), Graham Growth (`classify_graham_growth_outcome`) and FCF Growth
(`classify_fcf_growth_outcome`), each in its strategy's `execution.py`, and Momentum's fixed `COMPLETED`
(`from_momentum_capture`). ESC-29 was a slip in one of them: Graham Number mapped a calculation that returned
`not_applicable` to a failed run
([ledger entry](../existing-strategy-correctness/ESC_A_DEFECT_LEDGER.md#esc-29--a-calculation-that-returns-not_applicable-is-stored-as-a-failed-run),
repaired in [PR #110](https://github.com/PeterPontbriand/investment-analysis-engine/pull/110)). Graham Growth has
the same fall-through line, unreachable today because its calculation returns only `ok` or `invalid_input`. This
step adds seven strategies, each of which would write another copy.

The question to settle when the Step 3.5 slice plan is drafted: should every strategy use one shared mapping, with
a conformance test over every declared strategy, in place of a per-strategy function? A strategy with no separate
assembly status and one with a fixed outcome would need a defined place in it. Decision pending. Tracked in
[issue #111](https://github.com/PeterPontbriand/investment-analysis-engine/issues/111).

**Decided 2026-10-19: yes; implemented 2026-10-21.** The project owner approved one shared mapping. PC.4 implemented it as `RunOutcome.from_status`, with each strategy reporting a native status and `ExecutionCapture` deriving the outcome, and a shared `exit_code_of`. Slice PC.4 of the
[pattern-cleanup plan](../pattern-cleanup/PC_CONTRACT_AND_SLICE_PLAN.md#pc4--one-shared-mapping-from-statuses-to-a-run-outcome) holds the design.

### A.10 Removing the consolidation rules moves to 3.5.0b (2026-10-25)

The contract and A.7 had 3.5.0 begin by removing `AGENTS.md` §0. Slice 3.5.0 is now two sub-slices
([plan](STEP_3_5_0_SLICE_PLAN.md)). The project owner decided that §0 is removed in the first commit of 3.5.0b, not
3.5.0a: 3.5.0a changes Momentum's stored shape (the result schema version, the evidence codec version and the
document version) without compatibility code, which §0 permits and nothing after it would. The A.7 wording
"removed by 3.5.0, the first implementation slice" is kept as recorded.

### A.11 Market-cap price basis and share-count scaling (2026-10-25)

Decided by the project owner while the [3.5.1 slice plan](STEP_3_5_1_SLICE_PLAN.md) was written, after live checks
([evidence §4](STEP_3_5_1_MAPPING_EVIDENCE.md#4-price-and-split-evidence)):

| Topic | Before | Decision | Why |
| :--- | :--- | :--- | :--- |
| Price with a requested `as_of` | "The unadjusted close" | The split-adjusted close without dividend adjustment, on or before `as_of`, through a new request in the historical market-data boundary. Without `as_of`, the current quote as before | Yahoo returns no unadjusted close: `Close` is split-adjusted after the fact and `Adj Close` is adjusted for dividends too. The existing series is dividend-adjusted and is never used for market cap. Momentum's series is unchanged |
| Share count | Scaled by splits between the share-count date and the price date | Scaled by every split whose ex-date is after the filing date of the filing the count was taken from (the accession and filing date in the count's own provenance, not assumed to be the anchor filing), up to the price data's adjustment date | A filing restates its share counts for a split effective before it is issued (SEC Staff Accounting Bulletin Topic 4.C): Walmart's fiscal 2024 10-K restates for a split after the fiscal year-end, so scaling from the year-end would count it twice. A later filing's comparative restates an earlier year-end for splits up to its own date |
| Point-in-time | No exception | Splits after the boundary are used only to undo the provider's retroactive adjustment and never change the as-of market cap | The provider adjusts every historical close for all later splits |
| Stock dividends | Not addressed | Scaled like splits where the split history shows them, never issuance; the history shows them as fractional splits and cannot tell them from small splits | Shown for Commerce Bancshares (1.05) and Tootsie Roll (1.03) |
| Effect | | The market cap equals the one [Shared definitions §4](STEP_3_5_SHARED_DEFINITIONS.md#4-market-capitalization) defines; the formula and the value are unchanged, and only how it is computed is stated | |

Limitation: a split announced before the filing but effective just after it is assumed not to be reflected in the filing.

### A.12 Share count from the cover page, and equivalent concepts (2026-10-25)

Decided by the project owner after the share-count check of 3.5.1b
([evidence §5.5](STEP_3_5_1_MAPPING_EVIDENCE.md#55-share-count-coverage)) found no balance-sheet count at the latest
year-end for Walmart, SAP and Nutrien ([slice plan, H7 to H12](STEP_3_5_1_SLICE_PLAN.md#a1-decisions-f1-to-f10-2026-10-25)):

| Topic | Before | Decision | Why |
| :--- | :--- | :--- | :--- |
| Cover-page share count | Never used (A.6, 2026-10-02) | A fallback for market cap only: after the balance-sheet paths, and only when the anchor filing tags it as a single non-dimensional total; its own date is the share-count date | A.6 reversed. Walmart has tagged no balance-sheet count since 2012, so market cap and everything built on it would be `unavailable` for it. The other reason for the ban, per-class cover counts, is covered by the multi-class rule: a filer with only per-class counts stays `unavailable` |
| IFRS share count | Not read | `ifrs-full:NumberOfSharesOutstanding` is a direct balance-sheet path; no IFRS treasury share count exists in the evidence, so there is no issued-minus-treasury path | SAP and Nutrien report under IFRS, and the existing paths read us-gaap only |
| Scaling a cover-page count | By splits after the filing date | By splits whose ex-date is after the cover date | The cover date, not the filing date, is the date of the count |
| Piotroski's dilution test | Year-end balance-sheet counts | Unchanged: year-end balance-sheet counts only | The cover count is not a year-end fact |
| Absent debt component | Zero when at least one mapped debt concept is tagged ([Shared definitions §6](STEP_3_5_SHARED_DEFINITIONS.md#total-debt)) | Zero only when its mapping is not unsupported and no related concept is tagged at the date; otherwise `unavailable`. IFRS total debt and EV are `unavailable` while the IFRS noncurrent long-term debt mapping is unsupported (decided by the project owner for every filer) | A filer tags debt under concepts the mapping does not read (Deere, Honeywell, SAP), and a zero there flatters the issuer |
| Equivalent concepts | One concept per field | A priority list where the evidence shows the same line item; one concept for every year of a run; the absent-component zero only when none is tagged and never for an unsupported mapping | Alphabet and Moderna tag short-term investments under other names; Walmart tags receivables under another |

The 2026-10-02 rule in A.6 is kept as recorded.

### A.13 3.5.2 sub-slices and scope (2026-10-26)

*Superseded in part: the ranking helper of 3.5.2a was removed ([A.16](#a16-strategy-set-revised-2026-11-02)).*

Decided by the project owner while the [3.5.2 slice plan](STEP_3_5_2_SLICE_PLAN.md) was written; the plan's
[Appendix A](STEP_3_5_2_SLICE_PLAN.md#a1-decisions-k1-to-k17-2026-10-26) holds all seventeen decisions (K1 to K17).

| Topic | Before | Decision | Why |
| :--- | :--- | :--- | :--- |
| Sub-slices (K2) | One slice, 3.5.2 | Four, each with its own branch, managed gate and authorization: 3.5.2a the slice plan and the ranking helper (one pull request), 3.5.2b the pure shared metrics, 3.5.2c the shared input assembly, 3.5.2d FCF-Growth adopts the shared market cap | The ranking helper, the pure metrics, the I/O assembly and the change to a stored result shape have different inputs and risks |
| Shared input assembly (K3) | Each consumer builds its own inputs | Built once in 3.5.2c: the anchor year-end, the share-count path, the price and the split history, and the balance-sheet and annual inputs at that year-end. It closes two gaps found on `main`: the production provider does not route the balance-sheet series, and the split-history provider protocol declares neither `as_of` nor `adjusted_on` | Seven strategies would otherwise each assemble the same inputs, and diverge |
| Gross profit (K6) | Not a shared metric | The reported gross profit; otherwise sales minus cost of revenue when both are reported, keeping both inputs' provenance; never operating income | Piotroski and Beneish both use it, and the mapping evidence already assigns it to 3.5.2 |

### A.14 3.5.3 sub-slices and scope (2026-10-29)

Decided by the project owner while the [3.5.3 slice plan](STEP_3_5_3_SLICE_PLAN.md) was written; the plan's
[Appendix A](STEP_3_5_3_SLICE_PLAN.md#a1-decisions-q1-to-q17-2026-10-29) holds all seventeen decisions (Q1 to Q17).

| Topic | Before | Decision | Why |
| :--- | :--- | :--- | :--- |
| Sub-slices (Q1) | One slice, 3.5.3 | Five, each with its own branch, managed gate and authorization: 3.5.3a the plan and the pure calculator, 3.5.3b the inputs at three year-ends, 3.5.3c the side-by-side text layout, 3.5.3d the strategy, 3.5.3e the repetition checkpoint | The plan and pure code, the I/O assembly, the shared layout and the strategy have different inputs and risks, as in 3.5.2 |
| Year-ends *t−1* and *t−2* (Q2) | "Request each exact date" | Derived from the start date of the preceding completed annual period, read from an explicit list of fields that must agree, 335 to 395 days before the later year-end; a stub year breaks the chain | The `reportDate` of earlier filings is a filing label and fails first-year registrants |
| Multi-year assembly (Q3, Q4, Q6, Q7) | Inputs at one year-end | Several named year-ends in the shared assembly; share counts through the instant series; a shared long-term debt metric; one industry-class resolver for all strategies | Seven strategies would otherwise assemble these separately |
| Dilution test (Q5) | Year-end balance-sheet counts | Compared only when both counts come from one filing and one path, otherwise unavailable | One filing is on one split basis (SEC Staff Accounting Bulletin Topic 4.C); Piotroski has no price, so it needs no market data |
| Currency, taxonomy and zero debt (Q8, Q9) | Unstated across fields | Checked per test; test 5 passes with zero debt in both years whatever the assets | One test combines figures; a debt-free firm cannot reduce leverage |
| Result and statuses (Q10, Q11, Q13) | Result shape in Slice inputs §5 | Fixed shape, two new reason codes, `ok`, `input_unavailable` and `provider_error` statuses with no `not_applicable`, and a text headline reading "x of n" | A partial score must never read as a bare number |
| Text layout (Q12) | Decided by the 3.5.3 plan | Bands of at most 120 characters, each repeating the Ticker column, at every strategy count | One band per strategy is long, a filter hides columns, terminal-width packing varies by machine |
| Checkpoint and guide (Q16, Q17) | Site 19 weighed in 3.5.3 | No change to the watchlist command syntax in Step 3.5; the guide is fixed where in scope and one issue is filed for the rest | Piotroski has no watchlist options of its own |
| Split of 3.5.3b and evidence handling (U1 to U6) | 3.5.3b as one sub-slice | Two: 3.5.3b1 the shared functions that need no new evidence (long-term debt, industry class, multi-year balance-sheet and annual values), 3.5.3b2 year-end discovery, the share-count series, the Q5 measurement and the captured fixtures; evidence in `STEP_3_5_3_INPUT_EVIDENCE.md`; a stop threshold for Q5; capture only in 3.5.3b2; no new live-network check; a byte-identical proof of stored outputs | Reviewed code should not wait on a stop for live evidence; the plan's [A.5](STEP_3_5_3_SLICE_PLAN.md#a5-decisions-u1-to-u6-2026-10-29) holds the six decisions |
| Repetition checkpoint split (E1, F11) | 3.5.3e as one sub-slice | Three: 3.5.3e1 the review, the extraction and the template changes (complete 2026-11-01); 3.5.3e1b one analyzer base, `BaseAnalyzer[ResultT, *ConfigT]`, replacing `BaseAnalyzer[ConfigT, ResultT]` and `ConfigFreeAnalyzer` (complete 2026-11-01); 3.5.3e2 the guide fixes, the Site 19 record and the issues (complete 2026-11-01) | The extraction and the analyzer base change code and stored nothing new; the guide and the records are documentation only, so each has its own gate |
| Guide, Site 19 and issues (F1 to F10) | Guide fixes "where in scope", Site 19 weighed in 3.5.3 | Every B.2 fact placed in `docs/project/STRATEGY_DEVELOPMENT.md` or the one shortfall issue ([#210](https://github.com/PeterPontbriand/investment-analysis-engine/issues/210)); stale facts corrected; Site 19 weighed with no change to the watchlist syntax and decided with API.3; issue [#207](https://github.com/PeterPontbriand/investment-analysis-engine/issues/207) and #210 all finish before API.1, after 3.5.3e1c (generated bodies for the execution function, command, refresh and tool handler); every strategy slice records the guide's shortfalls and fixes the guide in the same slice where in scope | A reader of the guide is told each fact the work met; the order of the follow-up work is recorded where slice order lives |
| Generated bodies (H1 to H6) | The templates wrote the signatures and flags of the execution function and the command, with stub bodies | Complete bodies for `execute_<name>`, the command, `refresh`, `build_selection` and the tool handler, through the shared helpers; five stubs remain (the analyzer, `compose_<name>(executed_at)`, `from_<name>_capture`, the presenter and the evaluation compose); `compose_piotroski` takes the same signature; `HELP_TARGETS` follows the declared strategies (complete 2026-11-01) | A new strategy starts with its invocation envelope written and only its own composition to fill, and the end-to-end generator test runs the generated bodies |

### A.15 3.5.5 before 3.5.4 (2026-11-02)

Decided by the project owner after potential users asked for EV/EBITDA and FCF yield next.

| Topic | Before | Decision | Why |
| :--- | :--- | :--- | :--- |
| Order of 3.5.4 and 3.5.5 | 3.5.4 (Altman Z-Score and Beneish M-Score) first, 3.5.5 (valuation multiples, Interest Coverage and ROIC) second | 3.5.5 runs first and 3.5.4 follows it; 3.5.5a, valuation multiples, is the first strategy slice after API.6 | Potential users want to cross-check valuation from two independent angles rather than rely on the Graham Number alone (answer A5 in IAD's charter) |
| Numbers | 3.5.4, 3.5.5 and their sub-slices | Kept; only the order changes | Many records, including verbatim decision appendices, cite those numbers |

### A.16 Strategy set revised (2026-11-02)

Decided by the project owner. The change lands as one pull request: the documents, and the removal of the code and
tests that lose their only consumer.

| Topic | Before | Decision | Why |
| :--- | :--- | :--- | :--- |
| Magic Formula and the ranked view (D1) | A Magic Formula analyzer in 3.5.6, a ranked refresh view over the runs of one watchlist refresh, a side-by-side table sort option over that view, and the 3.5.2a ranking helper | All removed from Step 3.5, including `investment_analysis_engine/analysis/shared/ranking.py` and `tests/analysis/shared/test_ranking.py`, since Magic Formula was their only planned consumer. Git history keeps them. Ranking across companies belongs in a separate evaluator application ([Product boundaries](../../../MASTER_PLAN.md#25-product-boundaries)), not the engine | The per-ticker factors largely duplicate EV/EBITDA and ROIC, and ranking a watchlist does not reproduce Greenblatt's market-wide method |
| Beneish M-Score (D2) | A Beneish M-Score analyzer in 3.5.4 beside Altman | Replaced by an accrual-ratio strategy: (net income − operating cash flow) ÷ average total assets, the cash-flow version, built only from data already mapped. The mappings, fields and tests that existed only for Beneish were removed; a mapping that another strategy, a shared metric or the EBITDA fallback uses stays | Beneish's coefficients are old and prone to false alarms, and its result is opaque to a beginner. It needed the most special-case rules (a depreciation fallback, three income cases for TATA, no partial score), and any missing index makes it unavailable. The accrual ratio keeps Beneish's useful core, since TATA is an accrual ratio, and complements Piotroski's cash-versus-income test |
| Shareholder Yield (D3) | 3.5.6 held Magic Formula | 3.5.6 is Shareholder Yield: dividend yield + net buyback yield + net debt-reduction yield, each as a percentage of market cap, with total returned capital ÷ FCF reported as a metric (not a cap or filter). Net debt reduction comes from the change in the already-mapped total-debt instants, net buybacks from the split-adjusted share-count series (3.5.1d), and dividends paid needs a new mapping, evidenced in that slice's plan the 3.5.1 way | The slice Magic Formula vacated takes a strategy that reports capital returned to shareholders, built on evidence the step already assembles |
| Reverse DCF (D4) | A roadmap candidate | Not part of Step 3.5. Recorded in the [evidence provider roadmap](../../../EVIDENCE_PROVIDER_ROADMAP.md) as a candidate for the evaluator application or Milestone v0.3 | Its result depends mainly on the chosen cost of capital, which [the FCF-Growth guide](../../../../user/strategies/FCF_GROWTH.md) deliberately excludes |
| Numbers | 3.5.4, 3.5.6 and their sub-slices | Kept; 3.5.4 is Altman and the accrual ratio, 3.5.6 is Shareholder Yield, and 3.5.5 still runs before 3.5.4 ([A.15](#a15-355-before-354-2026-11-02)) | Many records cite those numbers |

### A.17 Stale anchor filing and the anchor rule (2026-11-09)

Decided by the project owner for [issue 204](https://github.com/PeterPontbriand/investment-analysis-engine/issues/204).
The slice runs ahead of 3.5.5; the documents and the code land in one pull request that closes the issue. The rule is
in [Shared definitions §3](STEP_3_5_SHARED_DEFINITIONS.md#stale-anchor) and [§4](STEP_3_5_SHARED_DEFINITIONS.md#4-market-capitalization).

| Topic | Before | Decision | Why |
| :--- | :--- | :--- | :--- |
| Slice shape (K1) | No stale-anchor rule | Its own slice before 3.5.5, documents and code in one pull request. One sequence row for it (unit "#204") and one for the Graham slice (K5). Shared definitions gains a "Stale anchor" subsection, the anchor rule in Period alignment and the market-cap rule in §4; the record of #204 in [P12](STEP_3_5_3_SLICE_PLAN.md) points here | One rule, decided once, before the strategies that would each have to restate it |
| Definition (K2) | A run at an old anchor looked as current as any other | The anchor is stale when the next annual report was overdue at the boundary and none had been filed. Age runs from the fiscal year-end. `next_report_due` = the anchor's `year_end` + 1 calendar year + 7 days + the form's allowance, extended by any relief period. Stale means the boundary's date is after it; on the due date it is not stale. Each allowance and relief table is one declaration in code, compared with the document by a test. A large accelerated filer gets up to 45 days of grace without a warning, which the rule states | Every allowance is the most generous regular deadline plus any automatic extension, so the rule never warns early |
| 10-K and 20-F allowances (K2a) | None | 10-K and 10-K/A: 105 days (90 plus the 15 days of Rule 12b-25). 20-F and 20-F/A, depending on the next report's fiscal year-end: 6 calendar months + 15 days before 2011-12-15, 4 calendar months + 15 days from 2011-12-15 on (changed from the anchor's year-end by K12). Sources: Release 33-8959, General Instruction A.(b) of Form 20-F, General Instruction A of Form 10-K, Rule 12b-25 | The four-month 20-F deadline was set by Release 33-8959 for fiscal years ending on or after 2011-12-15; text that still says six months is the earlier deadline |
| 40-F allowance (K2b) | None | 40-F and 40-F/A: 120 days, with no Rule 12b-25 extension. Sources: the General Instructions of Form 40-F, National Instrument 51-102 | A 40-F is due when its Canadian annual documents are: 90 days, or 120 for a venture issuer. Rule 12b-25 does not list Form 40-F |
| Relief periods (K2c) | None | One shared table. A report whose original due date falls inside an entry's window gets its extra days. The one entry: original due dates 2020-03-01 to 2020-07-01, 45 extra days, every form. Sources: the SEC COVID-19 order (March 2020, Release 34-88465) and the Canadian securities regulators' blanket 45-day relief (March 2020). The SEC relief required notice, which the engine cannot check, so it applies to every filer | The rule never warns early |
| Effect (K3) | None | One rule, decided in Shared definitions and implemented in shared code. (a) A result built only from filing evidence keeps its status and carries the shared element and the warning message. (b) Market cap at a stale anchor is `unavailable` with the new reason code `stale_anchor`; EV, EV/EBITDA and FCF yield, including FCF Growth's yield, follow through the existing propagation with no per-strategy code | Market cap would pair the boundary's price with a share count from a filing that was overdue to be replaced |
| Record (K4) | Piotroski alone wrote its anchor, in its own part | The common strategy-document header gains `anchor_filing` after `effective_as_of`: `year_end`, `form`, `accession`, `filing_date` (nullable), `next_report_due`, `stale`. One shared typed part; the conformance test is updated. Null for a strategy that does not report it and on replay of a run stored before it. Piotroski's own anchor part is removed and its document and presenter read the shared element. The warning message is also the first entry of the tail's warnings | The anchor has one home |
| Scope (K5) | Piotroski only reported an anchor | The rule applies to Piotroski, FCF Growth and every Step 3.5 strategy through the shared assembly. Graham Number and Graham Growth are unchanged here; their own slice follows issue 246 and precedes 3.5.5 ([issue 245](https://github.com/PeterPontbriand/investment-analysis-engine/issues/245)): their input years follow the shared anchor, actual dates decide, no stepping back, and they report the element and warning. Decided in [A.19](#a19-graham-input-years-follow-the-shared-anchor-issue-245-2026-11-09) | Their input years are not taken from the anchor, so aligning them is a decision of its own |
| Versioning (K6) | Versions at Piotroski 1 and 1, FCF Growth 2 and 7 (method and result schema) | The new header key is an addition, so no document `schema_version` bump for it alone. Removing Piotroski's anchor part bumps its document `schema_version` (2 to 3) and, because its stored result changes shape, its result schema version (1 to 2). The anchor rule and the market-cap classification bump the `method_version` of Piotroski (1 to 2) and FCF Growth (2 to 3); FCF Growth's stored result gains the element, so its result schema version goes 7 to 8. No migration code ([API.2 S4](../api/API_2_SLICE_PLAN.md)); stored runs of these two under the older versions are refused by version when read, never misread | API.2's additions rule, exactly as written |
| Messages (K7) | None | Warning: "The newest annual report filed by {boundary date} is for the fiscal year ended {year_end} ({form}, filed {filing_date}). The next one was due by {next_report_due} at the latest, and none had been filed." The clause ", filed {filing_date}" is dropped when the filing date is null. In Piotroski's concise text it appears where warnings already appear, prefixed "Warning: ". Market-cap reason: "Market cap unavailable: the anchor filing is stale, so its share count is not the count at {boundary date}." Dates are ISO dates; the text is a message, never a sentence | State only what is known |
| Glossary and help (K8) | None | An "Anchor Filing" term and a `stale_anchor` entry in the user glossary, the help bundle and OpenAPI regenerated, and FINANCE_MATH.md, USAGE.md and the affected strategy guides updated | The served references cover every code the engine writes |
| Tests and evidence (K9) | None | Boundary tests per form and relief, a point-in-time case, market cap `unavailable` with `stale_anchor` and its propagation through FCF Growth's yield, Piotroski at a stale anchor, a null element for Momentum and the Graham strategies and on replay of a stored run, the K10 and K11 tests, and one captured real overdue filer in the regression evidence, WeWork Inc., which filed a notice of late filing and never the report ([evidence record](STEP_3_5_STALE_ANCHOR_EVIDENCE.md)) | Each decision has a test that fails without it |
| Anchor rule (K10) | The anchor was the newest annual accession by acceptance time, amendments included | Annual filings are read newest first by acceptance time, at or before the boundary. The first original annual report (10-K, 20-F or 40-F) fixes the anchor's fiscal year, matched on the report date. The anchor is the newest filing for that fiscal year, so an amendment of that year can be the anchor, and an amendment of an older fiscal year never is. The rule is in [Shared definitions §3](STEP_3_5_SHARED_DEFINITIONS.md#period-alignment) | An older year's amendment accepted after the newest year's report had made the anchor step back a year |
| Extra-page search (K11) | The adapter read submissions pages that overlapped the 400 days before the boundary | The 400-day window is removed. When the recent block holds no original annual report at or before the boundary, the extra pages are read newest first until one does, at most `_MAX_SUBMISSION_PAGES`; a page that starts after the boundary is skipped. When the cap is reached without one, the result stays `no_anchor_filing` and its message states the earliest filing date the pages read reached | A stale anchor is by definition old, so a window measured from the boundary could not find it |
| Allowance year-end (K12) | The 20-F allowance was chosen by the anchor's fiscal year-end | Chosen by the next report's fiscal year-end: the anchor's `year_end` plus one calendar year (29 February becomes 1 March), before the 7 days are added. The six-month row applies only when that year-end is before 2011-12-15, so to anchors before 2010-12-15 | The overdue report is the one for the year after the anchor's, and its deadline is the one that applies |
| Anchor on every path (K13) | A provider failure after the anchor was resolved gave a null element and no warning, in Piotroski and in FCF Growth's yield | Once the anchor is resolved and assessed, the result reports it whatever happens afterwards, provider-error results included; a failure before the anchor is resolved still gives null. The rule is in [Shared definitions §3](STEP_3_5_SHARED_DEFINITIONS.md#stale-anchor) | A stale anchor must not be hidden by a later failure |
| Warning order (K14) | FCF Growth put the stale-anchor message after the horizon-fallback warning | The stale-anchor message is the first entry of a document's warnings, in every strategy that reports the element | One place to read it |

### A.18 EPS and diluted shares across a restatement: issue 246 (2026-11-09)

Decided by the project owner for [issue 246](https://github.com/PeterPontbriand/investment-analysis-engine/issues/246).
The documents and the code land in one pull request that closes the issue. The rule is in the
[provider mapping record §5.1](../step-2.4/STEP_2_4_PROVIDER_MAPPING_RECORD.md#51-common-splitaccounting-basis).

| Topic | Before | Decision | Why |
| :--- | :--- | :--- | :--- |
| Shortened span (D1) | A requested span that could not all be on one basis returned no series | The series is the longest run of the newest periods that satisfies the existing §5.1 rule, which is evaluated on the returned run itself and not on the full requested span. Bases are never mixed and there is no split arithmetic. EPS and weighted-average diluted shares are reconciled alike. For NVDA the result is FY2023 to FY2026 | A 10-K carries three years, so a split leaves the older years on the earlier basis and the whole series was lost |
| No split arithmetic (D2) | None | No split arithmetic and no split-adjusted mode in this slice. The "split-adjusted view (derived)" alternative is recorded in §5.1 as considered and filed as [issue 248](https://github.com/PeterPontbriand/investment-analysis-engine/issues/248) | Whether to derive values is a decision of its own, with conditions that issue lists |
| Internal and served codes (D3a) | `LeftOutReason` had two values and was internal | `LeftOutReason.EARLIER_BASIS` is internal and has no glossary entry. The served code is `ReasonCode.EARLIER_BASIS` (`earlier_basis`), with a glossary entry and term references, and the schemas, help bundle and OpenAPI regenerated. The dropped facts reach the resolver through one optional provider capability, `AnnualSeriesProvider.fetch_annual_series`, which returns `AnnualSeriesFacts(facts, earlier_basis)`; the production facade delegates to it, and a provider without it is read through `fetch_facts` exactly as before. A provider that returned facts but none survived is never reported as returning no data | The smallest typed addition to the provider-to-resolver path; no other provider changes |
| FCF Growth document (D3b) | No record of years left out | `left_out_years`, always present and empty when nothing was left out. Each entry has `field`, `fiscal_year`, `period_end` (ISO date), `reason_code` (`earlier_basis`) and `reason`: "Reported only before a later filing restated other years (for example after a stock split); not combined with the restated years." The document `schema_version` goes 11 to 12 and the result schema version 8 to 9. The name is generic so later reasons can use it; `earlier_basis` is the only one for now. No migration code; stored runs under the older version are refused by version when read | A user must be able to see which years were left out, and why |
| Text views (D3c) | None | One warning line directly after the stale-anchor message (K14) and before the horizon-fallback warning. Years are grouped into fiscal-year ranges and the fields that share a range are listed together; one field uses the singular wording; fields with different ranges give one clause each, in one line. Example: "Warning: Diluted EPS and weighted-average diluted shares for FY2020–FY2021 were reported only before a later filing restated other years (for example after a stock split); those years are left out." | One place to read it |
| Explicit `--growth-years` (D3d) | An unmet span was `insufficient_history` | When the span cannot be met because of earlier-basis years, the result is `INDETERMINATE` with `earlier_basis` and a message naming those years and the years the span needs: "Diluted EPS for FY2020–FY2021 was reported only before a later filing restated other years (for example after a stock split); 5 elapsed years need FY2020–FY2025." Other causes keep the existing precedence | An explicit span is strict, and the user needs the cause |
| Every year earlier-basis (D3e) | `_no_selection_reason` gave the "later than the analysis boundary" message | FCF Growth's `_no_selection_reason` returns `earlier_basis` with the D3b reason. `_left_out_at` in `metric_inputs.py` maps `EARLIER_BASIS` to `InputUnavailable(ReasonCode.EARLIER_BASIS, that reason)`, so every strategy gets the same code | The cause is not the analysis boundary |
| Diagnostics (D3f) | One count, "left out as ineligible" | The per-field provider line counts these years: "eps: provider/success — 4 fiscal-year observation(s) resolved; 2 left out as reported only on an earlier basis." The existing ineligible count is unchanged | Both counts stay readable |
| Evidence and capex (D4) | None | NVDA's Company Facts were read once, read-only (CIK 0001045810). FY2023 and FY2024 EPS were re-presented in the FY2025 10-K (1.74 to 0.17, 11.93 to 1.19), and FY2021 and FY2022 were never re-presented after the 2024 split. `PaymentsToAcquirePropertyPlantAndEquipment` covers 3 periods (ends 2010 to 2012), and `PaymentsToAcquireProductiveAssets` covers the five periods ending 2022 to 2026. The capex mapping is changed by C1 below | The capex evidence needs its own decision |
| Tests (D5) | One test locked in the empty series | A synthetic NVDA-shaped fixture (late-January year ends, a 4-for-1 split in 2021 and a 10-for-1 split in 2024) for EPS and diluted shares; the rejection test now expects the shortened span and the left-out records; tests for the resolver's message, the document, the warning's position and wording, an explicit span, `_no_selection_reason`, `_left_out_at` and the diagnostics; and a shortened EPS series reaching the three-year horizon under the longest-available policy. Graham's three-year average reads the shortened series through `resolve_three_year_average_eps`, which reports "Insufficient eligible fiscal-year EPS observations" when fewer than three periods remain, and is unchanged | Each decision has a test that fails without it |
| Cache (D6) | A short series is fetched again on every run | A shortened series does not meet the cache's full-count test, so it is fetched again on every run, as a short capex series already is. No cache change | Accepted |
| Per-share horizons (G1) | Under the FCF-per-share basis, one common period without a per-share value failed the run with `incompatible_scope`, even when the horizon needed only the newest years | Horizons are chosen only from the common periods that have a per-share value, by the existing contiguity and newest-first rules. The run fails with `incompatible_scope`, with the existing message, only when no horizon can be met that way. Years missing because diluted shares were left out appear in `left_out_years` with their own reason. The total-company basis is unchanged | A series shortened for one field must not stop a shorter span that the newer years can meet |
| Conflicting periods (G2) | A period whose latest versions disagree emptied the series, and the resolver said "Provider returned no data" | The disagreement is judged per run. If it is in the newest requested period, the series fails with `ambiguous_fact` and the resolver's reason says the filings give different values. If it is in an older period, that period and every older one are dropped and the run is the newer periods, judged by the existing rules. The dropped conflicting period is reported in `left_out_years` with `ambiguous_fact` and the reason "Filings filed together give different values for this year; not used." A period older than it is reported only when it is also earlier-basis, judged against the final run's boundary. The fact travels in `AnnualSeriesFacts.conflicting`, with the internal `LeftOutReason.CONFLICTING_VERSIONS`. Text views add one warning right after the earlier-basis line, or in its place, with the same grouping; one year left out ends "that year is left out" and several "those years are left out", for this line and the earlier-basis line. EPS and diluted shares alike | Section 6 of the provider mapping record names equally ranked disagreement `ambiguous_fact`; one period's disagreement should not lose the other years |
| Capex concept (C1) | The SEC capex mapping read only `PaymentsToAcquirePropertyPlantAndEquipment`, and the mapping record ruled out `PaymentsToAcquireProductiveAssets` | `us-gaap:PaymentsToAcquireProductiveAssets` is a second US-GAAP concept with the same sign, period, unit, scope and availability rules, and its own `provider_field` constant. For each request each concept's run is the number of consecutive annual periods it covers, counted back from the newest annual period either concept reports; only the facts of the longer run are returned, PP&E on a tie, and never both. The IFRS mapping is unchanged. The resolved-input cache schema version goes 3 to 4, because a series cached under the old rule could differ from what the new rule returns when the broader concept covers a longer run. The only reader of capex is FCF Growth, so no other consumer is affected | NVDA tags capex only as productive assets for 2022 to 2026, so it had no usable capex; Apple's switch is why two concepts are never mixed |
| Capex disclosure (C2) | None | When any selected observation's capex uses the broader concept, FCF Growth's text views and the document's `limitations` add: "Capital expenditures include purchases of intangible assets, which the filer reports together with property and equipment, so free cash flow may be lower than with property and equipment alone." The concept is already in each observation's provenance (`provider_field`), so the JSON gains no element | The reader must know the figure can include intangibles |
| Records and tests (C3) | The mapping record ruled out the broader concept | Section 4 and Section 6 of the provider mapping record, FINANCE_MATH.md, the FCF Growth guide and the glossary state C1, G2 and the left-out years in plain English. Tests cover each decision and an end-to-end NVDA-shaped run, which reaches a three-year horizon over FY2023 to FY2026 with the earlier-basis warning, the fallback warning and the capex limitation, in that order | Each decision has a test that fails without it |

### A.19 Graham input years follow the shared anchor: issue 245 (2026-11-09)

Decided by the project owner for [issue 245](https://github.com/PeterPontbriand/investment-analysis-engine/issues/245).
The documents and the code land in one pull request that closes the issue. It completes the scope [A.17](#a17-stale-anchor-filing-and-the-anchor-rule-2026-11-09)
K5 left to it. The rule is in [Shared definitions §3](STEP_3_5_SHARED_DEFINITIONS.md#period-alignment); the yield check of FCF Growth is the precedent.

| Topic | Before | Decision | Why |
| :--- | :--- | :--- | :--- |
| Approach (M1) | Graham read the newest fiscal-year facts the adapter held at the boundary and never looked at the anchor | Graham Number and Graham Growth Value keep their own resolvers (`resolve_normalized_eps` and `resolve_three_year_average_eps`; `resolve_bvps` with its derivation). Each filing input is checked against the shared anchor afterwards, as FCF Growth's yield is. Graham is not rebuilt on the shared annual-series or balance-sheet functions | The smallest change that makes the years agree; a rebuild is a decision of its own |
| Anchor resolution (M2) | The service opened a plain analysis scope | The service opens `anchor_year_end_scope` and resolves the anchor before EPS. A provider failure while resolving it is `provider_error`, recorded against the input name `anchor_year_end` (FCF Growth's name). With no anchor, for any reason including `report_date_unavailable`, the result is `input_unavailable` with the anchor's message; Graham never falls back to the newest facts. An ETF stays `not_applicable` before any request, with a null `anchor_filing` | One anchor for every input, found once |
| Date match (M3) | None | A filing input matches the anchor when its observation period end equals the anchor's `year_end` exactly, with no tolerance: the rule of the shared year-end share count and of FCF Growth's yield. Checked against the captured filings of the regression evidence: for every one of the 41 original annual reports in the 17 captured filing histories (Apple, Deere and Walmart among them, whose fiscal years are 52 or 53 weeks), the newest annual-duration fact ends on the filing's report date, and so does the newest balance-sheet fact of every report in the 12 histories that hold balance-sheet facts. The one fact that ends within ten days of a report date and is not on it is a cover-page share count, which is dated after the report date by design. No real filer's dates differ, so no tolerance is added | A tolerance would make "the anchor's year" a judgement |
| Year mismatch (M4) | The newest facts were used whatever year they were for | When the newest year of a filing input does not end on the anchor's `year_end` the result is `input_unavailable`, and Graham never steps back to an older year. EPS: "eps: The newest fiscal year of diluted EPS ends 2023-12-31, not the anchor filing's fiscal year-end 2024-12-31; the Graham Number is never calculated from an older year." Book value per share: "bvps: The newest book value per common share is for the fiscal year ended 2023-12-31, not the anchor filing's fiscal year-end 2024-12-31; the Graham Number is never calculated from an older year." Graham Growth Value says "the Graham Growth Value is never calculated from an older year". Dates are ISO dates. The investor sees the reason as it is, and not the general text of its status | A result must never look complete from an older year |
| Consecutive years (M5) | Nothing checked that the three EPS years were consecutive: the resolver took the three newest distinct period ends | The three years of the three-year average are *t*, *t−1* and *t−2* by actual dates: each period starts the day after the previous one ends. A gap gives `input_unavailable` and a message that names the missing year: "The fiscal years of diluted EPS are not consecutive: none ends 2023-12-31, between the years ended 2022-12-31 and 2024-12-31." Nothing upstream guaranteed this: the adapter's reconciliation keeps the newest periods it finds, and the resolver's checks compare concept, currency and units, never dates | An average over a gap is not an average of three years |
| Cache (M6) | A live run (no as-of) could reuse a cached input of an older fiscal year indefinitely: the resolved-input cache key's `analysis_as_of` is `None` and `financial_cache_ttl_seconds` defaults to `None` | One shared helper, `resolve_at_anchor_year` in `analysis/shared/metric_inputs.py`. When a cached input's period end differs from the anchor's `year_end`, the helper sets that entry aside (the resolver's cache reads are suspended for one call), resolves the input once from the provider, and the provider's answer replaces the cache entry. If the provider's year still differs, M4 applies. The helper serves Graham's EPS (the derived three-year entry, and the single-year entry of Graham Growth Value), Graham's book value per share (direct and derived) and the shared year-end share count in `_resolve_share_count`. This adds no `method_version` bump for Piotroski or FCF Growth: it restores adherence to a rule A.17 already states (K10: the anchor's year decides) | Without it the anchor rule held only for a cold cache |
| Overrides (M7) | An override bypassed year selection | The year check applies per input; an overridden input has no year and is exempt. The anchor is resolved and reported whenever at least one filing input is resolved from the provider. When every filing input is overridden (both EPS and book value per share for Graham Number; EPS for Graham Growth Value) no anchor is requested and `anchor_filing` is null. The plain analysis scope is still opened, as before this slice, so the share-unit check of a run with a quote reads the latest annual filing inside an active snapshot; without it that check can only answer `provider_unsupported` | An override states its own value |
| Stale anchor (M8) | No element and no warning | A.17's K3(a), K13 and K14 apply exactly as written. A stale anchor leaves the status unchanged and fills `anchor_filing`. The stale-anchor message (`stale_anchor_warnings`) is the first entry of the document's warnings. Once the anchor is resolved, the element and the warning are reported on every path, including the M4 and M5 unavailable results and provider-error results; a failure before it is resolved gives null | One place to read it |
| Text output (M9) | None | No new line in any text mode. The warning appears first among the "Warning: " lines, after the sources line | One place to read it, in the places warnings already appear |
| Left-out years (M10) | An EPS series that came up short because of a restatement gave only "Insufficient eligible fiscal-year EPS observations" | The resolver reads the series through the provider's annual-series capability. When the series comes up short of three years because [A.18](#a18-eps-and-diluted-shares-across-a-restatement-issue-246-2026-11-09) left years out (`earlier_basis` or `ambiguous_fact`), the reason names each left-out year and its reason, and the Graham documents carry `left_out_years`: always present, empty when nothing was left out, with the entry shape of A.18 D3b. The years are listed only when they are why the series is short; a series of three years or more lists none. FCF Growth's document part moves to a shared one, `LeftOutYearPart` in `reporting/documents/shared_parts.py`, and its evidence record `LeftOutYear` with its builder to `analysis/shared/metric_evidence.py`; FCF Growth uses them and its JSON is byte-identical. Graham never averages fewer than three years | A user must see why the series is short |
| Versions (M11) | `GRAHAM_NUMBER` and `GRAHAM_GROWTH`: method version 1, evidence codec 4, document schema 10 | Method version 1 to 2 (the years the inputs may come from change), evidence codec 4 to 5 (the stored analysis gains the anchor evidence and the left-out years), document schema 10 to 11 (the new `left_out_years` key; filling the existing `anchor_filing` key needs no bump of its own). No migration code ([API.2 S4](../api/API_2_SLICE_PLAN.md)): stored runs under the older versions are refused by version when read, never misread, which a test shows | API.2's additions rule, exactly as written |
| Records and tests (M12) | None | This record; K5 of A.17 points here; the "Stale anchor" subsection of Shared definitions names the Graham strategies; the two Graham guides and FINANCE_MATH.md say it in plain English; the help bundle and OpenAPI are regenerated. The synthetic Graham fixtures take EPS and book value from one annual report: before, EPS was from the report filed 2024-09-13 and book value from one filed 2025-02-10. One test per decision, each failing without its change, including a null element on replay and for an ETF and a stale anchor for each strategy | Each decision has a test that fails without it |
| Reason code (M13) | An unavailable input's reason was always replaced by general text: `friendly_valuation_failure` (the live commands and `friendly_graham_assembly` on replay) gave every status but OK and not-applicable one line, "required financial data is unavailable", and Graham Number's `_number_reason` then explained an unavailable EPS or book value only as "could not be resolved", naming the missing component at most. No result carried a typed cause | A `reason_code` is added to the resolution result, on the Graham input assemblies and on the anchor stop: `incompatible_period` for an input year that is not the anchor's (the code FCF Growth's yield and the shared year-end share count give for the same rule), `missing_fact` for a gap in the three EPS years, `earlier_basis` or `ambiguous_fact` taken from the newest left-out year for a short series, the anchor's own code when there is no anchor, and none for a provider failure. A code requires `input_unavailable`. The presenters show the reason message as written whenever a code is present. The code stays internal: no document field is added and no version changes beyond M11. Serving a code with every non-OK status is [issue 250](https://github.com/PeterPontbriand/investment-analysis-engine/issues/250), the slice after this one | One typed cause that lets a presenter show its message as written, and the step toward a served code |
| Direct-command harness (M14) | The Graham commands ran in the harness with no `--as-of`, at the real time of the run, as the other commands do; the synthetic Graham issuer had no anchor filing, so there was nothing to go stale. The Piotroski command already took `--as-of 2025-01-15` | The direct-command harness pins a strategy's run date through the public `--as-of` option, never by patching the clock. The Graham commands take `--as-of 2025-07-01`, the date of the Graham fixture's own clock, as the Piotroski command takes its own. The visible changes are the heading's "as of 2025-07-01" and the share-unit line, "historical share-unit evidence is unsupported" in place of "share-unit evidence is unsupported by this provider" | A test should drive the code a user drives |
