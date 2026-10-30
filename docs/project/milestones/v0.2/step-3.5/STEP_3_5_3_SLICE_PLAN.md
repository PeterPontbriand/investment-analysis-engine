# Step 3.5 slice 3.5.3 — Piotroski F-Score: Slice Plan

The slice plan for [slice 3.5.3](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#353--piotroski-f-score) of Step 3.5. It covers six
sub-slices (3.5.3b is split in two by [U1](#a5-decisions-u1-to-u6-2026-10-29)). It was written against `main` at `72c3a1f`, after the 3.5.2 plan was complete.

Placement among other work packages: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **What this plan does:** takes the Piotroski F-Score from specification to a shipped strategy in six gated steps:
  the plan and the pure nine-test calculator (3.5.3a); the inputs at three year-ends, in two parts (3.5.3b1 and
  3.5.3b2); the side-by-side text layout for many strategies (3.5.3c); the strategy through every edit site (3.5.3d); and the repetition checkpoint
  (3.5.3e).
- **What it is not:** a change to the Piotroski formulas, to the analyzer envelope, or to any existing strategy's stored
  output. No ranking, no market data and no issuance-proceeds reading. Full list:
  [Scope limits](#4-scope-limits-and-acceptance-criteria).
- **Rules every sub-slice follows:**
  - The formulas and outcomes are [Strategy specifications §1](STEP_3_5_STRATEGY_SPECIFICATIONS.md#1-piotroski-f-score)
    and the decisions Q1 to Q17 in [Appendix A](#appendix-a-decision-records). Where a case is not settled, the
    sub-slice stops and asks the project owner.
  - Every calculated number is a `MetricResult` with an explicit `ReasonCode`. A missing input makes its test
    unavailable, never a fail, and never zero.
  - Deterministic calculation stays in Python. The calculator is a pure function over frozen types.
  - A change to a persisted shape bumps its version field, with no migration, and is listed among the pull request's
    user-visible changes ([AGENTS.md](../../../../../AGENTS.md) §4).
  - An envelope change is never a Piotroski-only change: it is applied to every analyzer, so the sub-slice stops and
    asks (Q15).
  - The managed quality gate after every sub-slice, and explicit authorization before the next begins.
- **Where the detail lives:** the decisions are in [Appendix A](#appendix-a-decision-records); the implementation
  record, including where `docs/TOOL_DEVELOPMENT.md` fell short, is in [Appendix B](#appendix-b-implementation-record);
  file inventories, tests and interfaces are in [Appendix C](#appendix-c-file-inventories),
  [Appendix D](#appendix-d-tests) and [Appendix E](#appendix-e-interfaces).

## 2. Sequence and status

Each sub-slice ends with the managed quality gate and is gated by explicit authorization before the next begins.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| 3.5.3a | [Slice plan and the nine-test calculator](#353a--slice-plan-and-the-nine-test-calculator) | Complete | 2026-10-29 |
| 3.5.3b1 | [Shared year-end functions that need no new evidence](#353b1--shared-year-end-functions-that-need-no-new-evidence) | Complete | 2026-10-29 |
| 3.5.3b2 | [Year-end discovery, share-count series and captured evidence](#353b2--year-end-discovery-share-count-series-and-captured-evidence) | Complete | 2026-10-30 |
| 3.5.3c | [Side-by-side text layout](#353c--side-by-side-text-layout) | Next | |
| 3.5.3d | [The Piotroski strategy](#353d--the-piotroski-strategy) | Planned | |
| 3.5.3e | [Repetition checkpoint](#353e--repetition-checkpoint) | Planned | |

Each sub-slice has its own branch off `main`, named as its section says, after the previous pull request merges.
3.5.3a is one pull request carrying this plan and the calculator, as 3.5.2a did.

## 3. The sub-slices

### 3.5.3a — Slice plan and the nine-test calculator

- **Problem:** Piotroski is the first strategy built from scratch against the analyzer envelope, and nothing yet
  states how its inputs are found at three year-ends or what its result holds.
- **Decision (Q1, Q5, Q8 to Q10):** this plan, and a pure calculation of the nine tests over a frozen input object.
  The calculator takes each operand as a value with provenance or the reason it is unavailable, compares on exact
  unrounded values, and returns the nine test results, the score, the completeness and the available count.
  `execution_status` and the context fields belong to the analyzer.
- **Scope:** this plan and the amendments of [C.1](#c1-documents-amended-in-353a); `nonpositive_denominator` and
  `insufficient_tests` in `ReasonCode` and the regenerated schemas; the calculation module and its tests; the
  share-count types of the shared assembly; the adapter function that names the taxonomy of a provider field;
  the renaming of the example of an undeclared strategy in three test files ([C.2](#c2-353a-files)).
- **Branch:** `feat/step-3-5-3a-plan-and-calculator` (this branch).
- **Detail:** [files](#c2-353a-files), [tests](#d1-353a-tests) and [interfaces](#e1-the-calculators-input-and-result).

### 3.5.3b — Inputs at three year-ends

Split in two by [U1](#a5-decisions-u1-to-u6-2026-10-29): 3.5.3b1 is reviewed code that needs no new evidence, and
3.5.3b2 is mapping judgment from live evidence. Each has its own branch, managed gate and authorization. The names
b1 and b2 avoid renumbering 3.5.3c to 3.5.3e, which other records cite.

#### 3.5.3b1 — Shared year-end functions that need no new evidence

- **Problem:** the shared assembly returns balance-sheet and annual values at the anchor year-end only, there is no
  shared long-term debt, and no strategy-neutral industry class. Piotroski needs all three.
- **Decision (Q3, Q6, Q7, Q8, U1, U6):**
  - `compute_long_term_debt` sits beside `compute_total_debt` and follows its rules.
  - `resolve_industry_class` returns the class, the reason it is unknown, or the provider failure; the SEC adapter
    implements `AsFiledSicSource`.
  - `resolve_balance_sheet_values_at` and `resolve_annual_values_at` take several named year-ends and key their results
    by date; both accept `OPERATING_CASH_FLOW`. The one-year-end functions become calls of them.
  - Each value keeps its own currency and provider field; the calculator checks agreement per test (Q8).
- **Scope:** the functions of [E.2](#e2-shared-assembly-functions) other than year-end discovery and the share-count
  series; synthetic tests through the existing rig ([D.2](#d2-353b1-tests)); the long-term debt entry of
  `FINANCE_MATH.md`. Stored outputs and schemas stay byte-identical (U6).
- **Branch:** `feat/step-3-5-3b1-shared-year-end-functions`.
- **Detail:** [files](#c3-353b1-files), [tests](#d2-353b1-tests) and [interfaces](#e2-shared-assembly-functions).

#### 3.5.3b2 — Year-end discovery, share-count series and captured evidence

- **Problem:** the year-ends *t−1* and *t−2* are not yet found, the share count is served at the anchor only, and the
  field list and the share-count paths have no captured evidence.
- **Decision (Q2, Q4, Q5, U2 to U5):**
  - The year-ends *t−1* and *t−2* are derived from the start date of the preceding completed annual period, from an
    explicit priority list of fields that must agree, and each must lie 335 to 395 days before the later year-end.
  - Share counts come through the instant series at named year-ends, and the dilution test compares them only when
    both come from one filing.
  - The measurement for Q5 covers the regression set plus Apple and Monster at their latest year-end, and stops and
    reports at the threshold of [U3](#a5-decisions-u1-to-u6-2026-10-29).
  - The evidence is kept in `STEP_3_5_3_INPUT_EVIDENCE.md`, which this sub-slice creates ([U2](#a5-decisions-u1-to-u6-2026-10-29)).
- **Scope:** `resolve_year_ends` and `resolve_share_count_series` of [E.2](#e2-shared-assembly-functions); the captured
  fixtures of [U4](#a5-decisions-u1-to-u6-2026-10-29); tests through the assembly functions ([D.2b](#d2b-353b2-tests)).
- **Branch:** `feat/step-3-5-3b2-year-end-evidence`.
- **Detail:** [files](#c3b-353b2-files), [tests](#d2b-353b2-tests), [interfaces](#e2-shared-assembly-functions), [decisions](#a6-decided-under-delegation-during-353b2) and [evidence](STEP_3_5_3_INPUT_EVIDENCE.md).

### 3.5.3c — Side-by-side text layout

- **Problem:** the refresh table's one-line-per-ticker text is about 170 characters wide over four strategies and
  would be about 460 over eleven. The fifth strategy lands next.
- **Decision (Q12):** pack the strategies' column groups into bands of at most 120 characters, each band repeating the
  Ticker column, in `STRATEGIES` order. A group is never split; a group wider than 120 gets a band of its own. This
  applies at every strategy count, so the four-strategy example and its stored output change. `--json` is unchanged.
- **Scope:** the text layout of the side-by-side table, the named width constant, its stored expected output, and the
  documentation that shows the table.
- **Branch:** `feat/step-3-5-3c-side-by-side-layout`.
- **Detail:** [files](#c4-353c-files) and [tests](#d3-353c-tests).

### 3.5.3d — The Piotroski strategy

- **Problem:** the strategy must exist at every edit site, as the contract requires of each strategy slice.
- **Decision (Q1, Q7, Q10, Q11, Q13, Q14):**
  - The first step after running the generator is
    `git mv investment_analysis_engine/strategies/piotroski_calculation.py investment_analysis_engine/strategies/piotroski/calculation.py`,
    with the test import updated.
  - The analyzer assembles the inputs of 3.5.3b, calls the calculation, and reports `execution_status` `ok`,
    `input_unavailable` or `provider_error` (a stored run with its failure record). There is no `not_applicable`.
  - The headline is a text cell `score` reading "x of n", a text cell `completeness`, and the anchor year-end as the
    period end, labelled "fiscal year-end", with the taxonomy.
  - The sector gate is `PIOTROSKI_SECTOR_GATE = SectorGate(gated=False, warn=frozenset({IndustryClass.FINANCIAL}))`,
    pinned by a test to its row of [Shared definitions §1](STEP_3_5_SHARED_DEFINITIONS.md#1-applicability).
  - Method version and every schema version start at 1.
- **Scope:** analyzer, wiring, presenter, headline, tool, user guide, `FINANCE_MATH.md` and `GLOSSARY.md` entries,
  fixtures and the Golden cases for Apple (complete) and Monster (partial); the rest of the Golden cases wait for 3.5.7.
- **Branch:** `feat/step-3-5-3d-piotroski-strategy`.
- **Detail:** [files](#c5-353d-files), [tests](#d4-353d-tests) and [the result](#e1-the-calculators-input-and-result).

### 3.5.3e — Repetition checkpoint

- **Problem:** all seven strategies are expected to have near-identical wiring, and the 3.5.4a plan is not accepted
  until the repeated code is reviewed.
- **Decision (Q16, Q17):** the review and the extraction are done as the contract's repetition checkpoint states
  ([contract §3](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#3-the-slices)). Site 19 gets no change to the watchlist command
  syntax in Step 3.5, because Piotroski has no watchlist options of its own; the weighing is recorded in the
  implementation record and an issue is filed. `docs/TOOL_DEVELOPMENT.md` is fixed where a fix is within its scope and
  one issue is filed for the rest; the guide's worked example is repointed at `analysis/shared/metric_inputs.py` as the
  entry for a new strategy's SEC inputs, keeping FCF-Growth as the example of wiring.
- **Scope:** the review, the extracted helpers and the generator templates, the guide changes, the implementation
  record, the issues.
- **Branch:** `feat/step-3-5-3e-repetition-checkpoint`.
- **Detail:** [files](#c6-353e-files) and [Appendix B](#appendix-b-implementation-record).

## 4. Scope limits and acceptance criteria

**Scope limits**

- No change to the Piotroski formulas of [Strategy specifications §1](STEP_3_5_STRATEGY_SPECIFICATIONS.md#1-piotroski-f-score)
  other than the clarifications of [C.1](#c1-documents-amended-in-353a).
- No market data: the dilution test has no price, so the split-scaling rule for market cap does not bear on it (Q5).
- No ranking of partial scores, no issuance-proceeds reading, no user-selectable denominators or income basis.
- No envelope change, no registry, plugin loader or factory, and no dependency change (Q15).
- No compatibility decoder: a persisted shape that changes is versioned.

**Acceptance criteria**

- **3.5.3a:** the managed gate passes with at least 85% coverage; every case of the arithmetic oracle passes; the new
  reason codes appear in the regenerated schemas with no version bump; no other check is adjusted for the loose module.
- **3.5.3b1:** every rule of Q3, Q6, Q7 and Q8 that it implements is tested through the assembly functions; the
  byte-identical proof of [U6](#a5-decisions-u1-to-u6-2026-10-29) is reported; no strategy reads the SEC adapter for
  values.
- **3.5.3b2:** every rule of Q2, Q4 and Q5 is tested through the assembly functions, not only through the series; the stored
  outputs of FCF-Growth and the market cap are byte-identical; no strategy reads the SEC adapter for values.
- **3.5.3c:** no line of the text table is wider than 120 characters unless one group is; `--json` is byte-identical.
- **3.5.3d:** a financial issuer warns, an unknown class runs and says so, a boundary before the filing is
  `input_unavailable`, replay with provider, cache, clock and calculator disabled reproduces the stored result, and the
  four existing strategies' outputs are unchanged.
- **3.5.3e:** the implementation record states the regions found and the helpers extracted; the extraction is merged.

## 5. Background

[Strategy specifications §1](STEP_3_5_STRATEGY_SPECIFICATIONS.md#1-piotroski-f-score) and the
[Piotroski evidence record](STEP_3_5_PIOTROSKI_EVIDENCE.md) were written in September and October 2026. The 3.5.1 and
3.5.2 slices supplied the mappings, the shared metrics and the single-year-end assembly. This plan was written once those
were on `main`, and the project owner approved its decisions on 2026-10-29.

---

## Appendix A: Decision records

Kept for the record. Nothing here is needed to see what the sub-slices deliver.

### A.1 Decisions Q1 to Q17 (2026-10-29)

Approved by the project owner. Each is summarized in the sections above.

| # | Topic | Decision and reason |
| :--- | :--- | :--- |
| Q1 | Sub-slices | Five, each with its own branch, managed gate and authorization: 3.5.3a the slice plan and the pure nine-test calculator; 3.5.3b the inputs at three year-ends (Q2 to Q7); 3.5.3c the side-by-side text layout (Q12), before the fifth strategy lands; 3.5.3d the strategy through every edit site; 3.5.3e the repetition checkpoint and the guide follow-up. The reason is the 3.5.2 precedent: the plan and pure code, the I/O assembly, the shared layout and the strategy have different inputs and risks. |
| Q2 | Finding the year-ends *t−1* and *t−2* | *t−1* is the day before the reported start date of year *t*'s completed annual period; *t−2* is derived the same way from year *t−1*'s period. The start date is read from a short, explicit, strategy-neutral priority list of completed-annual fields. Every listed field present for that year must give the same start date; a disagreement makes that year-end unavailable (`ambiguous_fact`), and no listed field present makes it unavailable (`missing_fact`). The derived date must be 335 to 395 days before the later year-end. A transition or stub year is not a completed annual period, so it breaks the chain and the earlier year-ends are unavailable. Choosing the field list is mapping judgment, delegated to 3.5.3b under the standing terms: decide from captured evidence only, fail closed, use explicit lists rather than loose patterns, record each decision with its evidence in this plan, and stop if the evidence does not settle it. Rejected: the submissions `reportDate` of earlier annual filings, because it is a filing label that could disagree with the periods the tests compare, and it fails first-year registrants, whose anchor filing has comparatives but who have no earlier 10-K. |
| Q3 | Multi-year assembly | In `analysis/shared/metric_inputs.py`, the balance-sheet function takes several named year-ends. The annual function returns each requested year's value, or why it has none, still by the latest-available-version rule, and also accepts `OPERATING_CASH_FLOW` by name (today it raises, because the field is outside `ANNUAL_PERIOD_FIELDS`). No separate (*t*, *t−1*) pairing helper is added. Existing callers' behavior is unchanged. The interface appendix names the exact functions, signatures and return types, and 3.5.3b implements them as written or stops and asks. |
| Q4 | Share counts at named year-ends | `COMMON_SHARES_OUTSTANDING` is served through the instant series, with today's two paths: the direct count (including `ifrs-full:NumberOfSharesOutstanding`), and issued minus treasury taken from one filing at the same date. The multi-class rejection is unchanged. The latest-only path stays as it is for market cap. This is mapping judgment, delegated to 3.5.3b under the standing terms, with captured evidence for the regression set, Apple and Monster. |
| Q5 | Dilution test (test 7) | The counts at *t* and *t−1* are compared only when both come from the same filing. Such a pair is on one split basis, because a filing restates its counts for splits effective before it is issued (SEC Staff Accounting Bulletin Topic 4.C, [contract A.11](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a11-market-cap-price-basis-and-share-count-scaling-2026-10-25)). A *t−1* count from another filing makes the test unavailable (`ambiguous_fact`). Both counts must be on the same path; a direct count with a derived one is unavailable. W1 of the [3.5.2 plan](STEP_3_5_2_SLICE_PLAN.md) does not bear on this test: it governs scaling a count to a price date, and Piotroski has no price, so it needs no market data. 3.5.3b's evidence measures how often *t−1* comes from the anchor filing; if it rarely does, 3.5.3b stops and reports. |
| Q6 | Long-term debt | A shared `compute_long_term_debt` in `analysis/shared/enterprise_value.py`, beside `compute_total_debt`, which is unchanged. Long-term debt is the current portion of long-term debt plus noncurrent long-term debt, decided by the rules of [Shared definitions §6](STEP_3_5_SHARED_DEFINITIONS.md#total-debt): the direct-total reconciliation comes first; an absent part is zero only when it is `not_tagged` with no related concept and at least one of the four mapped debt concepts is present at the date; with none present, the no-reported-debt row applies, using that year's interest expense; `unsupported` makes it unavailable, so test 5 is unavailable for every IFRS filer. Rejected: subtracting from total debt, because a short-term borrowings gap would wrongly remove long-term debt. |
| Q7 | Industry class | A shared `resolve_industry_class` in `metric_inputs.py`, used by all seven strategies, returns the class, the reason it is unknown, or the provider failure. Piotroski declares `PIOTROSKI_SECTOR_GATE = SectorGate(gated=False, warn=frozenset({IndustryClass.FINANCIAL}))` in its own package, with a test pinning it to its row of the matrix in [Shared definitions §1](STEP_3_5_SHARED_DEFINITIONS.md#1-applicability). An unknown class runs and says so. |
| Q8 | Currency and taxonomy across fields | Checked per test. Operands in different currencies make that test unavailable (`incompatible_currency`). A us-gaap and ifrs-full mix makes the affected tests unavailable (`incompatible_scope`). The reason is that one test combines figures, and a figure on another currency or taxonomy cannot be combined with them; the other tests are unaffected. |
| Q9 | Zero debt | Test 5 passes when long-term debt is zero in both years, whatever the assets. A missing *t−2* total assets does not make it unavailable in that case. The reason is [Strategy specifications §1](STEP_3_5_STRATEGY_SPECIFICATIONS.md#conventions-and-deviations): a debt-free firm cannot reduce leverage further, and assets play no part in that comparison. |
| Q10 | Result shape | Nine tests in fixed order. Each has a typed outcome (pass, fail or unavailable), its ratios as `MetricResult`s, its operands with provenance, and a reason code and reason when unavailable. The score is a `MetricResult`. The result also carries completeness (complete or partial), the count of available tests, the numbers of the unavailable tests, `execution_status`, the industry class and its warning, the taxonomy, the anchor year-end and accession, and the method version. Method version and every schema version start at 1. New `ReasonCode` members: `nonpositive_denominator`, which [Shared definitions §2](STEP_3_5_SHARED_DEFINITIONS.md#2-outcomes-and-reason-codes) foresees, and `insufficient_tests`, for fewer than six tests available. |
| Q11 | Statuses | `ok`: complete or partial. `input_unavailable`: fewer than six tests. `provider_error`: any `MetricInputsFailure`, stored as a run with its failure record. No `not_applicable`, because a financial issuer is applicable with a warning. |
| Q12 | Side-by-side text layout | The column groups are packed into bands, each repeating the Ticker column, in `STRATEGIES` order, up to a fixed width of 120 characters held as a named constant. A group is never split; a group wider than 120 gets a band of its own. This applies at every strategy count, so the four-strategy example and its stored output change. `--json` is unchanged. Rejected: one band per strategy (long); a `--strategy` filter (hides columns); terminal-width packing (output varies by machine). |
| Q13 | Headline | A text cell `score` reading "x of n" (for example "7 of 9", or "5 of 7" for a partial score); it is never a bare number, and never "x of 9" for a partial score. A text cell `completeness`. The period end is the anchor year-end, labelled "fiscal year-end", with the taxonomy. |
| Q14 | Fixtures and Golden cases | Captured fixtures for Apple fiscal 2024 (with an `as_of` after its filing, checked independently against the worked example in the [Piotroski evidence record](STEP_3_5_PIOTROSKI_EVIDENCE.md#5-apple-recorded-values-and-worked-example)), Monster, one bank (JPMorgan) and one IFRS filer (SAP or Nutrien). Golden cases for Apple (complete) and Monster (partial) in 3.5.3d; the rest wait for 3.5.7. Expected values are computed independently from the captured facts, never by the calculator. |
| Q15 | Envelope | No envelope change is planned. If one is needed, it is applied to every analyzer, so the sub-slice stops and asks. |
| Q16 | Repetition checkpoint (3.5.3e) | The review and extraction are done as [contract §3](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#3-the-slices) states. Site 19: no change to the watchlist command syntax in Step 3.5, because Piotroski has no watchlist options of its own. The weighing is recorded in the implementation record, and an issue is filed so it is not lost. |
| Q17 | `TOOL_DEVELOPMENT.md` shortfalls | Each sub-slice adds what it met to the implementation record in [Appendix B](#appendix-b-implementation-record), which links [A.3 of the 3.5.0 plan](STEP_3_5_0_SLICE_PLAN.md#a3-350b-implementation-record-2026-10-25). 3.5.3e fixes the guide where a fix is within its scope and files one issue for the rest. Already recorded: the guide's worked example sends a new contributor to FCF-Growth's private `ProductionAnnualGrowthSeriesResolver`. 3.5.3e repoints the guide at `analysis/shared/metric_inputs.py` as the entry for a new strategy's SEC inputs, keeping FCF-Growth as the example of wiring. |

### A.2 Review of an external assessment (2026-10-29)

The project owner reviewed an external assessment of this plan and added two requirements to 3.5.3b:

- 3.5.3b tests the rules through the assembly functions, not only through the series. The cases are *t−2* from an
  earlier filing, a conflict at *t−1*, *t−1* filed after the boundary, and fields that disagree on currency or taxonomy.
- 3.5.3b's acceptance criterion: FCF-Growth's and the market cap's stored outputs stay byte-identical, and no strategy
  reads the SEC adapter for values.

### A.3 Authorization of the calculator's location (2026-10-29)

The proposed home, `investment_analysis_engine/strategies/piotroski/`, would have blocked 3.5.3d and failed an existing
test:

- `scripts/new_strategy.py` refuses when `<package>/__init__.py` exists, or when the package directory exists and holds
  none of its target files, so the generator would exit with code 2 and write nothing.
- `test_t14_wiring_files_declare_no_discovery_or_registration` requires an `evaluation.py` in every non-underscore folder
  under `strategies/`.

The project owner approved placing the calculation at `investment_analysis_engine/strategies/piotroski_calculation.py`
with no `__init__.py` and no `piotroski/` directory. Only its tests import it. 3.5.3d moves it into the generated
package as its first step ([3.5.3d](#353d--the-piotroski-strategy)). If a loose module under `strategies/` breaks another
check, the sub-slice stops and asks; no check is adjusted.

### A.4 Wording the plan settles (3.5.3a)

Points the decisions did not state, taken while writing the calculator. They add no behavior beyond the specification;
the project owner can reverse any.

| Topic | Wording |
| :--- | :--- |
| Exact comparison | Each float operand becomes a `Fraction` without rounding, so a ratio is compared on its unrounded value. A reported ratio is the nearest float. A ratio that does not fit a double makes its test unavailable with `invalid_request`, the code the shared metrics already use for an overflow. |
| Positive denominators | Each total-assets operand that enters a denominator must be positive, including each of the two in an average (test 5). Sales must be positive in test 8 and current liabilities in test 6. Sales is a numerator in test 9 and need not be positive there. |
| Rule order within a test | An unavailable operand first (its own reason code, the first in the test's operand order), then a currency conflict, then a taxonomy conflict, then a denominator that is not positive. |
| Unknown currency or taxonomy | A monetary operand with no currency is `incompatible_currency`; an operand whose taxonomy cannot be read from its provider field or its components is `incompatible_scope`. The calculator fails closed rather than assume agreement. Share counts are not monetary and need no currency. |
| Zero debt | When both years' long-term debt is available and zero, test 5 passes before any other check, so neither the assets nor the currency of the debt's parts is examined. |
| Debt that is not ok | Long-term debt or gross profit evidence whose result is not `ok`, whatever its status, makes its test unavailable with its own reason code. A negative debt figure is compared as given; no rule is added for it. |
| Dilution inputs | A share count carries its accession and path, which the assembly supplies. Two counts on different filings or paths are `ambiguous_fact`. |
| Share-count type | `ShareCountPath` and `YearEndShareCount` are defined once, in `analysis/shared/metric_inputs.py`, in 3.5.3a. The calculation imports them, so the analyzer maps nothing and the shared layer imports nothing from a strategy. The first draft defined a `ShareCount` in the calculation and a second type in the assembly; the project owner corrected it at review. |
| Taxonomy of a provider field | The first draft read the prefix of the provider field, which gave `derived` for the issued-less-treasury count the SEC adapter labels `derived:us-gaap:CommonStockSharesIssued-us-gaap:TreasuryStockCommonShares`, so test 7 would have been `incompatible_scope` for every derived count. `taxonomy_of_provider_field` in `data/sec_edgar/financial_facts.py` now names the taxonomy of the plain `<taxonomy>:<concept>` form and of the derived form (one taxonomy across its parts, else none), and nothing looser; the calculator uses it, and falls back to an input's components only when the input has no provider field. Found at review. |
| Outcome code of a year-end with no start date | The approved text of Q2 made "no listed field present" `ambiguous_fact`. The project owner corrected it at review: no listed field present is `missing_fact`, and only a disagreement between present fields is `ambiguous_fact`. Q2 above and [Shared definitions §3](STEP_3_5_SHARED_DEFINITIONS.md#period-alignment) now say so. |
| Shuffled order and duplicated tests | The calculator takes named fields, so it has no input order to shuffle. The result constructor refuses a duplicated, missing or reordered test, and 3.5.3a tests that. The cases "shuffled input order gives the identical result" of [Slice inputs §5](STEP_3_5_SLICE_INPUTS.md#5-353--piotroski-f-score) belong to the assembly (3.5.3b, operands arrive keyed by name) and to the analyzer (3.5.3d, which never emits a test twice). |
| Sequence rows | The contract's table replaces the 3.5.3 row with the five sub-slices, as it did for 3.5.2. |

### A.5 Decisions U1 to U6 (2026-10-29)

Approved by the project owner before 3.5.3b began.

| # | Topic | Decision and reason |
| :--- | :--- | :--- |
| U1 | Split of 3.5.3b | 3.5.3b is two sub-slices, each with its own branch, managed gate and authorization. 3.5.3b1: `compute_long_term_debt`; `resolve_industry_class` with `AsFiledSicSource` implemented on the SEC adapter; the multi-year balance-sheet and annual functions, including operating cash flow. 3.5.3b2: finding the earlier year-ends with the delegated field list (Q2); the share-count series at named year-ends (Q4); the measurement for Q5; the captured fixtures. The reason is that b1 is code reviewed against [E.2](#e2-shared-assembly-functions), while b2 is mostly mapping judgment from live evidence, and a stop on evidence should not hold up reviewed code. The names b1 and b2 avoid renumbering 3.5.3c to 3.5.3e, which other records cite. |
| U2 | Evidence document | 3.5.3b2 creates `STEP_3_5_3_INPUT_EVIDENCE.md`, modelled on `STEP_3_5_2_LISTING_EVIDENCE.md`, holding the captured values, the field-list decision, the share-count paths and the Q5 counts. [B.3](#b3-decisions-of-353b-to-353e) summarizes it in a few lines and links it. The reason is that issuer-by-issuer evidence would swamp this plan, which must stay scannable. |
| U3 | Q5's stop threshold | The measurement covers the regression set plus Apple and Monster at their latest year-end. 3.5.3b2 stops and reports if, among issuers with a balance-sheet count at both *t* and *t−1*, fewer than three-quarters have both counts from the same filing, or if any issuer's two counts come by different paths. The reason is that "rarely" left undefined would make the agent decide policy. |
| U4 | Capture | Only 3.5.3b2 captures, using the existing fixture layout and checksum file: the regression set, Apple and Monster (to choose and test the field list and measure Q5), and JPMorgan and one IFRS filer (SAP or Nutrien), which Q14 needs, so 3.5.3d only reuses fixtures. 3.5.3b1 uses synthetic inputs only. |
| U5 | Live-network checks | None new. Year-end discovery and the share-count series read documents the adapter already fetches, and the SIC header request already has its live check. A sub-slice that finds it needs a new request type stops and asks. |
| U6 | Proof of byte-identical outputs | Run `uv run python -m tests._direct_command_output`, `uv run python -m tests._strategy_document_output`, `uv run python -m tests._workspace_command_output` and `uv run python -m scripts.generate_schemas --check`, and report `git --no-pager diff --stat` showing that no stored output or schema changed. The existing tests of `resolve_balance_sheet_values` and `resolve_annual_values` stay unchanged and pass. |

### A.6 Decided under delegation during 3.5.3b2

Decided from captured evidence, failing closed, with explicit lists; the evidence is in
[`STEP_3_5_3_INPUT_EVIDENCE.md`](STEP_3_5_3_INPUT_EVIDENCE.md). The project owner approved D2 before its code was written
and confirmed D1 and D3 on 2026-10-30.

| # | Topic | Decision and evidence |
| :--- | :--- | :--- |
| D1 | Field list for year-end discovery (Q2) | Net income, sales and operating cash flow, in that order: `YEAR_END_START_FIELDS` in `analysis/shared/metric_inputs.py`. On 12 issuers and every captured year the start dates of these three and of four other completed-annual fields agree, across all versions ([§4](STEP_3_5_3_INPUT_EVIDENCE.md#4-start-dates-by-field)). Monster tags no net income and gets both earlier year-ends from the other two. The prompt's wording "the shortest list that gives every captured issuer a start date" was corrected at review: the list needs at least two fields so that a disagreement between fields can be detected, and three give redundancy when one field is missing (Monster). Sales alone would already give every captured issuer a start date, which is why the wording needed correcting. |
| D2 | How share counts are served at named year-ends (Q4) | Option 1: the instant series is extended to a shares unit for `COMMON_SHARES_OUTSTANDING` only. The reason is that it reuses the instant series' tested date selection, boundary and absence handling, while a separate share-count series (Option 2) would duplicate the resolver's series body. Scope was not the deciding factor. `INSTANT_SERIES_FIELDS` is unchanged and currency-only; the field is accepted through the separate constant `SHARE_COUNT_SERIES_FIELD` beside it, and one function, `instant_series_unit`, gives a series field's unit (shares for this field, currency for the rest, an error for any other). No other field has a shares unit. The latest-only `FinancialFactRequest` path, the cover-page path and the resolver are unchanged, and `resolve_balance_sheet_values_at` refuses the field with `ValueError` so a count cannot reach a currency metric. |
| D3 | The Q5 measurement and its threshold (U3) | Through the real series, nine of the 12 issuers have a count at both *t* and *t−1* (JPM, PLD, DUK, DE, MRNA, MNST, GOOGL, HON, AAPL). Eight of the nine, 89%, have both from one filing; Deere's *t−1* count is from its previous annual report. All nine pairs are on the direct path. The threshold of three-quarters is not crossed and no issuer's two counts come by different paths ([§5](STEP_3_5_3_INPUT_EVIDENCE.md#5-share-counts-at-the-last-two-year-ends)). |
| IFRS filer | Q14 | SAP, the default. Nutrien, the other IFRS filer, is also in the regression set, so both are captured already. Neither can give long-term debt (test 5), and neither has a count at *t* (test 7), so SAP is no worse a fit; Nutrien's fixture is used where a test needs the IFRS direct count. |

---

## Appendix B: Implementation record

Each sub-slice adds what it met. The earlier record of the same kind is
[A.3 of the 3.5.0 plan](STEP_3_5_0_SLICE_PLAN.md#a3-350b-implementation-record-2026-10-25).

### B.1 Name check for the generator (3.5.3a, 2026-10-29)

`uv run python -m scripts.strategy_status piotroski` and a reading of `scripts/new_strategy.py`:

- The module `piotroski`, the alias `piotroski` and the label "Piotroski F-Score" are used by no package, descriptor,
  tool name, schema or guide. Every site reports `missing`, except the conditional settings site, which reports `done`.
- The generator refuses a package directory that exists: `build_plan` reports a conflict for an existing `__init__.py`
  and for an existing directory that holds none of its target files, and it writes the strategy's `__init__.py`
  itself. A package created before the generator runs therefore blocks 3.5.3d ([A.3](#a3-authorization-of-the-calculators-location-2026-10-29)).
- Three tests used `piotroski` as their example of a name nothing declares. Declaring Piotroski in 3.5.3d would have
  broken them, so 3.5.3a renamed the example ([C.2](#c2-353a-files)).

### B.2 Where `docs/TOOL_DEVELOPMENT.md` fell short

1. **Code before the generator.** The guide does not say how a strategy's code can land before the generator runs. The
   generator refuses a pre-existing package, and the T14 test requires an `evaluation.py` in every non-underscore
   strategy folder, so a pure calculation written first has to live outside the future package and move in afterward
   (3.5.3a).
2. **The worked example's resolver.** The guide's worked example sends a new contributor to FCF-Growth's private
   `ProductionAnnualGrowthSeriesResolver`; the entry for a new strategy's SEC inputs is
   `analysis/shared/metric_inputs.py`. 3.5.3e repoints it (Q17).
3. **Where strategy tests go.** The guide's testing section does not say where a strategy's tests live. The suite keeps
   them under `tests/analysis/<strategy>/`, with shared-metric tests under `tests/analysis/shared/` (3.5.3a).
4. **Shared metrics and their assembly.** The guide does not mention `analysis/shared/` at all: not the pure shared
   metrics (a strategy that needs long-term debt or EBITDA should call them, not rebuild them), nor the assembly
   functions that read a metric's inputs at one or several year-ends. The strategy-responsibilities table lists "required
   input semantics and resolution" as the strategy's own work, which a reader follows by writing a private resolver
   (3.5.3b1).
5. **Capabilities that need the analysis scope.** The guide does not say how a strategy gets a scope-bound read such as
   the industry class: the shared function takes a source protocol that the SEC adapter implements, and composition
   must pass the adapter, not the resolver, which reaches the adapter only through the production provider. The guide
   names neither the protocol nor the composition step (3.5.3b1).

6. **Capturing and using SEC fixtures.** The guide sends a reader to the evaluation documents for Golden fixtures and does
   not describe the SEC adapter's own fixtures: the `instant_facts` and `annual_facts` folders (one trimmed Company Facts and
   submissions document per issuer, each folder with a `SHA256SUMS` file), that a test needing both the balance-sheet and
   the annual concepts of an issuer has to merge the two, or how a point-in-time capture is trimmed (3.5.3b2).
7. **Adding a series to the SEC adapter.** The guide does not say that the production provider forwards each optional
   provider capability by hand (`data/financial/production.py`), so a new request type needs an edit there; extending the
   instant series avoided it, but a reader who needs a new capability is not told (3.5.3b2).

### B.3 Decisions of 3.5.3b to 3.5.3e

3.5.3b2 (2026-10-30), evidence in [`STEP_3_5_3_INPUT_EVIDENCE.md`](STEP_3_5_3_INPUT_EVIDENCE.md)
([U2](#a5-decisions-u1-to-u6-2026-10-29)); the decisions are in [A.6](#a6-decided-under-delegation-during-353b2):

- The field list of Q2 is net income, sales and operating cash flow; the start dates of these and four other fields agree
  on 12 issuers (D1).
- Share counts are served through the instant series in shares; of nine issuers with a count at *t* and *t−1*, eight have
  both from one filing, and all nine are on the direct path (D2, D3).
- Apple's inputs, captured as of a boundary after its fiscal 2024 report, equal the September record's (the
  [evidence §6](STEP_3_5_3_INPUT_EVIDENCE.md#6-apples-inputs-as-captured)).

3.5.3e records the repetition review and the weighing of Site 19.

---

## Appendix C: File inventories

### C.1 Documents amended in 3.5.3a

| Document | Change |
| :--- | :--- |
| [Contract](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md) | The 3.5.3 section links this plan; the §2 rows for 3.5.3 become the five sub-slices; Appendix A.14 summarizes Q1 to Q17. |
| [Shared definitions](STEP_3_5_SHARED_DEFINITIONS.md) | §2 names the two reason codes; §3 states the year-end rule of Q2; §6 states long-term debt as a consumer of the total-debt rules; §10 states the text layout of Q12. |
| [Strategy specifications](STEP_3_5_STRATEGY_SPECIFICATIONS.md) | §1 states Q5, Q8 and Q9. |
| [Slice inputs](STEP_3_5_SLICE_INPUTS.md) | §5 where it would otherwise contradict a decision. |

### C.2 3.5.3a files

| File | Change |
| :--- | :--- |
| `docs/project/milestones/v0.2/step-3.5/STEP_3_5_3_SLICE_PLAN.md` | New: this plan. |
| The four documents of C.1 | Amended. |
| `investment_analysis_engine/core/metric_result.py` | `NONPOSITIVE_DENOMINATOR` and `INSUFFICIENT_TESTS` in `ReasonCode`. |
| `schemas/fcf-growth.schema.json`, `schemas/momentum.schema.json`, `schemas/runs-compare.schema.json` | Regenerated with `uv run python -m scripts.generate_schemas`: the two members in the `ReasonCode` enum, no version bump. |
| `investment_analysis_engine/strategies/piotroski_calculation.py` | New: the calculation. |
| `tests/analysis/piotroski/test_piotroski_calculation.py` | New: its tests. |
| `investment_analysis_engine/analysis/shared/metric_inputs.py` | `ShareCountPath` and `YearEndShareCount`, the one home of the share-count types. |
| `tests/analysis/shared/test_metric_inputs.py` | The accession check of `YearEndShareCount`. |
| `investment_analysis_engine/data/sec_edgar/financial_facts.py` | `taxonomy_of_provider_field`. |
| `tests/data/test_sec_provider_field_taxonomy.py` | New: the function against the adapter's own constants and concept tables. |
| `tests/scripts/test_strategy_status.py` | The example of an undeclared strategy `piotroski` becomes `example_undeclared`, and the alias `f-score` becomes `example-alias`, with the expected guide and schema names. The tests used the next planned strategy's name as their example, so declaring Piotroski would have broken them. |
| `tests/test_strategy_wiring_conformance.py` | `strategy_names("piotroski")` becomes `strategy_names("example_undeclared")`, for the same reason. |
| `tests/workspace_documents/test_analysis_run_replay.py` | The unimplemented method's `analysis_id` and `method_id` become `example_undeclared` and `example_method`, for the same reason. |

### C.3 3.5.3b1 files

`analysis/shared/metric_inputs.py` (the multi-year balance-sheet and annual functions, the industry-class function and
the `AsFiledSicSource` protocol); `analysis/shared/enterprise_value.py` (`compute_long_term_debt`);
`data/sec_edgar/financial_facts.py` (`resolve_as_filed_sic_at_anchor`); `tests/analysis/shared/` and `tests/data/` for
each; `docs/user/FINANCE_MATH.md` (the long-term debt entry); `docs/project/ARCHITECTURE.md` (the `analysis` row); this
plan and the contract.

### C.3b 3.5.3b2 files

| File | Change |
| :--- | :--- |
| `analysis/shared/metric_inputs.py` | `YearEnds`, `resolve_year_ends`, `resolve_share_count_series`, the constants `YEAR_END_START_FIELDS` and `YEAR_LENGTH_DAYS`; `resolve_balance_sheet_values_at` refuses the share-count field; the series lookup shared by the two series functions. |
| `data/financial/facts.py` | `SHARE_COUNT_SERIES_FIELD`, `instant_series_unit`, and `InstantSeriesRequest` accepting the field. |
| `data/sec_edgar/instant_series.py` | The share-count selector (direct, then issued less treasury from one filing); the related-concept tagging moved into `_note_related_concepts`, a pure move that kept `select_instant_series` under the branch limit. |
| `evaluation/fixtures/sec_edgar/instant_facts/aapl.json`, `annual_facts/aapl.json` and the two `SHA256SUMS` | New: Apple as of a boundary after its fiscal 2024 report. |
| `tests/analysis/shared/test_metric_inputs_year_ends.py`, `tests/data/test_instant_series_share_counts.py` | New. |
| `tests/data/test_instant_series.py` | One assertion: `COMMON_SHARES_OUTSTANDING` leaves the fields the request refuses, and `PREFERRED_SHARES_OUTSTANDING` and `WEIGHTED_AVERAGE_DILUTED_SHARES` join them. |
| `STEP_3_5_3_INPUT_EVIDENCE.md`, this plan, the contract, Shared definitions | New and amended. |

`data/financial/resolver.py`, `data/financial/production.py` and `data/sec_edgar/financial_facts.py` are unchanged.

### C.4 3.5.3c files

The side-by-side text renderer and its width constant, the stored expected output of the refresh table, and the
documentation that shows it (`WORKSPACE.md`). The exact list is written when 3.5.3c begins.

### C.5 3.5.3d files

The generator's output for module `piotroski`, alias `piotroski`, label "Piotroski F-Score"; the `git mv` of the
calculation described in 3.5.3d; the five edited wiring files; `docs/user/strategies/PIOTROSKI.md`;
`FINANCE_MATH.md` and `GLOSSARY.md` entries; fixtures for Apple, Monster, JPMorgan and one IFRS filer; the Golden cases
for Apple and Monster. The exact list is written when 3.5.3d begins.

### C.6 3.5.3e files

The extracted helpers and the generator templates that call them, `docs/TOOL_DEVELOPMENT.md`, and this plan's
implementation record. The exact list is written when 3.5.3e begins.

---

## Appendix D: Tests

### D.1 3.5.3a tests

`tests/analysis/piotroski/test_piotroski_calculation.py`, with expected values written as `Fraction` or literal outcomes:

- every case of the [arithmetic oracle](STEP_3_5_PIOTROSKI_EVIDENCE.md#4-arithmetic-oracle): the base case, the four
  variations, the equality case with long-term debt 20 and 20 and with 0 and 0, and the all-fail case;
- each strict comparison at equality and on either side; ratios that are equal in exact arithmetic but not in floats;
- a zero and a negative denominator for each ratio, and a non-finite intermediate value;
- missing *t−2* total assets affects exactly tests 3, 5 and 9, and with zero debt in both years test 5 still passes;
- a missing newest-year input never triggers an older-year score;
- per-test currency and taxonomy mismatches;
- a complete score of 0, a partial score from 6 to 8, and fewer than six available;
- the dilution rules of Q5 (different filing, different path, unavailable count);
- result invariants: exactly nine tests in fixed order, points consistent with outcomes, finite numbers only, and the
  constructors' refusals of a duplicated or reordered test.

### D.2 3.5.3b1 tests

Synthetic, through the existing rig and the assembly functions:

- every rule of `compute_long_term_debt`, including an IFRS filer whose noncurrent mapping is unsupported;
- every outcome of `resolve_industry_class`, including a provider failure and no active scope;
- for the multi-year functions: *t−2* from an earlier filing, a conflict at *t−1*, *t−1* filed after the boundary,
  fields that disagree on currency or taxonomy, and the shuffled order of requested fields and dates;
- `OPERATING_CASH_FLOW` through both annual functions.

### D.2b 3.5.3b2 tests

`tests/analysis/shared/test_metric_inputs_year_ends.py`, through the assembly functions, on synthetic providers and on the
captured fixtures (Apple, Monster, JPMorgan, Deere, Nutrien, SAP, Walmart, Alphabet), with expected values written from
the captured documents:

- year-end discovery: the derivation, a 52-week calendar, a first-year registrant, a transition period that breaks the
  chain, a missing anchor period, a start date 334, 335, 395 and 396 days back at both steps, a disagreement between
  fields and between versions of one field, only the latest version deciding, no listed field present, an issuer without
  net income, a period filed after the boundary, nothing public at the boundary, a provider failure, and the order of
  the provider's answer;
- the share-count series: each path with its accession, counts from different filings and by different paths, a
  provenance naming two filings or none, each absence reason, the shuffled order of dates and answer, a provider failure,
  the multi-class rejection with no fallback, Monster's derived count, Nutrien's IFRS direct count, issuers with no
  count, and `resolve_balance_sheet_values_at` refusing the field.

`tests/data/test_instant_series_share_counts.py`: the request and `instant_series_unit`; the selector's paths, conflicts,
non-positive counts, one-filing rule, IFRS, boundary and taxonomy; the label of a derived count equal to the latest-only
path's; `resolve_instant_series` returning units `shares` with no currency; and the latest-only count unchanged. The stored
outputs are compared byte for byte ([U6](#a5-decisions-u1-to-u6-2026-10-29)).

### D.3 3.5.3c tests

The packing of groups into bands at several widths and counts, a group wider than 120, `STRATEGIES` order, and `--json`
unchanged.

### D.4 3.5.3d tests

[Slice inputs §5](STEP_3_5_SLICE_INPUTS.md#5-353--piotroski-f-score) and the tests every strategy slice adds: a financial
issuer, an unknown industry class, a missing critical input, a boundary before the filing, stored-run replay with
provider, cache, clock and calculator disabled, the pinning of the sector gate, a partial score never shown as a bare
number or as "x of 9", the Apple worked example checked independently, Monster as a partial score, and unchanged output
of the four existing strategies.

---

## Appendix E: Interfaces

### E.1 The calculator's input and result

In `investment_analysis_engine/strategies/piotroski_calculation.py` (moving to `strategies/piotroski/calculation.py`):

```text
Value = ResolvedInput | InputUnavailable

PiotroskiInputs(                      # frozen; year t, t1 = t-1, t2 = t-2
    total_assets_t, total_assets_t1, total_assets_t2: Value,
    net_income_t, net_income_t1: Value,
    operating_cash_flow_t: Value,
    sales_t, sales_t1: Value,
    gross_profit_t, gross_profit_t1: MetricEvidence | InputUnavailable,
    long_term_debt_t, long_term_debt_t1: MetricEvidence | InputUnavailable,
    current_assets_t, current_assets_t1, current_liabilities_t, current_liabilities_t1: Value,
    shares_t, shares_t1: YearEndShareCount | InputUnavailable,   # imported from analysis/shared/metric_inputs.py
)

calculate_f_score(inputs: PiotroskiInputs) -> PiotroskiScoreResult

PiotroskiScoreResult(
    tests: tuple[PiotroskiTestResult, ...],      # exactly nine, numbered 1 to 9
    score: MetricResult,                          # ok = tests passed; unavailable/insufficient_tests below six
    completeness: Completeness | None,            # COMPLETE (nine) | PARTIAL (six to eight) | None
    available_count: int,
    unavailable_tests: tuple[int, ...],
)

PiotroskiTestResult(
    number, name, group, outcome: CheckOutcome,   # PASS | FAIL | UNAVAILABLE
    ratios: tuple[NamedMetric, ...], operands: tuple[Operand, ...], diagnostics: tuple[str, ...],
    reason_code: ReasonCode | None, reason: str | None,
)
```

In `investment_analysis_engine/analysis/shared/metric_inputs.py`, defined in 3.5.3a and returned by the share-count series
of 3.5.3b:

```text
ShareCountPath: DIRECT | ISSUED_LESS_TREASURY

YearEndShareCount(count: ResolvedInput, accession: str, path: ShareCountPath)   # accession must be non-empty
```

In `investment_analysis_engine/data/sec_edgar/financial_facts.py`, defined in 3.5.3a:

```text
taxonomy_of_provider_field(provider_field: str) -> str | None
```

The analyzer of 3.5.3d adds the fields of Q10 that are not the calculator's: `execution_status`, the industry class and its
warning, the taxonomy, the anchor year-end and accession, and the method version.

### E.2 Shared assembly functions

3.5.3b1 implements these as written in `investment_analysis_engine/analysis/shared/metric_inputs.py`, or stops and asks;
3.5.3b2 implements `resolve_year_ends` and `resolve_share_count_series` the same way.
A year-end is a `date`; the functions never reuse the newest year-end for an older one.

```text
@dataclass(frozen=True)
class YearEnds:
    year_end: date                              # t, the anchor year-end
    prior: date | InputUnavailable              # t-1
    second_prior: date | InputUnavailable       # t-2

    def available_dates(self) -> tuple[date, ...]:
        """The year-ends that are dates, newest first."""

resolve_year_ends(resolver: InputResolver, *, anchor: AnchorYearEnd, ticker: str,
                  as_of: datetime | None) -> YearEnds | InputUnavailable | MetricInputsFailure

resolve_balance_sheet_values_at(resolver: InputResolver, *, ticker: str, fields: Sequence[FinancialField],
                                year_ends: Sequence[date], as_of: datetime | None,
) -> Mapping[FinancialField, Mapping[date, BalanceSheetValue]] | InputUnavailable | MetricInputsFailure

resolve_annual_values_at(resolver: InputResolver, *, ticker: str, fields: Sequence[FinancialField],
                         year_ends: Sequence[date], as_of: datetime | None,
) -> Mapping[FinancialField, Mapping[date, AnnualValue | InputUnavailable]] | InputUnavailable | MetricInputsFailure

resolve_share_count_series(resolver: InputResolver, *, ticker: str, year_ends: Sequence[date],
                           as_of: datetime | None,
) -> Mapping[date, YearEndShareCount | InputUnavailable] | InputUnavailable | MetricInputsFailure

@dataclass(frozen=True)
class IndustryClassResolution:
    industry_class: IndustryClass | None
    unknown: InputUnavailable | None            # set exactly when industry_class is None

class AsFiledSicSource(Protocol):               # declared in metric_inputs.py, as 3.5.2d did for split history
    def resolve_as_filed_sic_at_anchor(self, ticker: str, as_of: datetime | None) -> AsFiledSicResolution: ...

resolve_industry_class(source: AsFiledSicSource, *, ticker: str,
                       as_of: datetime | None) -> IndustryClassResolution | MetricInputsFailure
```

- The calls take the year-ends the analyzer asks for, normally `YearEnds.available_dates()`, and key their results by
  the date. A year-end that `YearEnds` holds as `InputUnavailable` is not requested; the analyzer reports that reason for
  every operand of that year.
- `resolve_balance_sheet_values` and `resolve_annual_values` keep their signatures and behavior, as one-year-end calls of
  the functions above, except that `resolve_annual_values` also accepts `OPERATING_CASH_FLOW`.
- The latest-available-version rule and the `ambiguous_fact` result for conflicting versions apply per requested year.
- The year-end rule is [Shared definitions §3](STEP_3_5_SHARED_DEFINITIONS.md#period-alignment); the field list that
  gives the start date is a module constant chosen and recorded by 3.5.3b2 under Q2.
- `AsFiledSicSource` is implemented on the SEC adapter beside `resolve_as_filed_sic`, which it wraps; the shared layer
  imports no adapter. A resolution that holds a reason is returned as `unknown`, and a provider failure as
  `MetricInputsFailure`.

In `investment_analysis_engine/analysis/shared/enterprise_value.py`:

```text
compute_long_term_debt(*, short_term_borrowings: BalanceSheetValue,
                       current_portion_of_long_term_debt: BalanceSheetValue,
                       noncurrent_long_term_debt: BalanceSheetValue,
                       lease_liabilities_as_debt: BalanceSheetValue,
                       long_term_debt_total: BalanceSheetValue,
                       interest_expense: AnnualValue) -> MetricEvidence
```

It returns current portion plus noncurrent long-term debt by the total-debt rules, and ignores short-term borrowings and
leases except to decide whether any of the four mapped debt concepts is present at the date. `compute_total_debt` is
unchanged.
