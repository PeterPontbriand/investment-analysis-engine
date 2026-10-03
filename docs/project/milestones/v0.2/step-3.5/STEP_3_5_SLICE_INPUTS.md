# Step 3.5 — Slice Inputs

What is already known for each slice, so its slice plan starts from here. Sequence, status and the
slice-plan rule live in the [contract](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status).
Definitions live in [Shared definitions](STEP_3_5_SHARED_DEFINITIONS.md) (SD) and
[Strategy specifications](STEP_3_5_STRATEGY_SPECIFICATIONS.md) (SS).

## 1. At a glance

- **What this is:** per slice, the new data, the result shape, the tests and edge cases, and the
  non-goals. These follow from the definitions and do not change with the code layout.
- **What this is not:** a slice plan. File lists, interfaces, wiring and CLI integration are
  written after SWC and PKG land, against the `main` of that day.
- **Every strategy slice also delivers:** analyzer, descriptor wiring, presenter with concise,
  details, diagnostics and JSON views, stored-run replay, user guide, `FINANCE_MATH.md` and
  `GLOSSARY.md` entries. This is not repeated per slice below.
- **Every strategy slice also tests:** a financial issuer, an unknown industry class, a missing
  critical input, a boundary before the filing, stored-run replay with provider, cache, clock and
  calculator disabled, and unchanged output of the four existing strategies.
- **Candidate mappings are hypotheses.** A concept named here becomes a production mapping only
  after captured filings show its meaning, units, period behavior and the filers it holds for.
- **No open decisions.** Decisions and their reasons are in the contract's
  [Appendix A](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#appendix-a-decision-records-and-history).

## 2. 3.5.1 — Data mappings and applicability

**Starting points in the code (verified on `main`, 2026-10-02)**

- `src/data/financial/facts.py`: a new `FinancialField` falls through to the per-share unit by
  default. Each new monetary field needs explicit unit routing.
- `src/data/financial/provenance.py`: `PeriodKind` has annual, quarterly and TTM members and no
  instant. Balance-sheet series need an additive instant representation, not a relabeled duration.
- `src/data/sec_edgar/financial_facts.py`: balance-sheet selection returns the single latest
  fact. Multi-year instants need a series request that leaves the latest-only behavior unchanged.
- `src/data/sec_edgar/filing_document.py`: the bounded filing reader accepts primary `.htm`
  documents only, four per run. Reading a filing's SEC header is a new, equally bounded request
  shape.
- No SIC code is read or stored anywhere. The submissions payload is already fetched for
  acceptance times; its `sic` field is the current value and must not be used.
- `src/data/yfinance/` supplies quotes and price history only, with no annual fundamentals.

**New fields**

The us-gaap concepts are candidates. The slice plan pins one mapping per field and taxonomy, with
captured evidence, and adds the ifrs-full equivalents.

| Field | Candidate us-gaap concept | Kind | Used by |
| :--- | :--- | :--- | :--- |
| Total assets | `Assets` | Instant | Piotroski, Altman, Beneish |
| Total liabilities | `Liabilities` | Instant | Altman |
| Current assets | `AssetsCurrent` | Instant | Piotroski, Altman, Beneish, IC |
| Current liabilities | `LiabilitiesCurrent` | Instant | Piotroski, Altman, Beneish, IC |
| Cash and equivalents | `CashAndCashEquivalentsAtCarryingValue` | Instant | EV, IC |
| Short-term investments | `ShortTermInvestments` | Instant | EV, IC |
| Long-term investments | `LongTermInvestments` | Instant | Beneish |
| Net PP&E | `PropertyPlantAndEquipmentNet` | Instant | IC, Beneish |
| Receivables | `AccountsReceivableNetCurrent` | Instant | Beneish |
| Retained earnings | `RetainedEarningsAccumulatedDeficit` | Instant | Altman |
| Short-term borrowings | `ShortTermBorrowings` | Instant | Total debt, IC |
| Current portion of long-term debt | `LongTermDebtCurrent` | Instant | Total debt, Piotroski, IC |
| Noncurrent long-term debt | `LongTermDebtNoncurrent` | Instant | Total debt, Piotroski, Beneish |
| Long-term debt, direct total | `LongTermDebt` | Instant | Reconciliation only |
| Lease liabilities counted as debt | `FinanceLeaseLiability` | Instant | Total debt |
| Preferred stock | `PreferredStockValue` | Instant | EV |
| Noncontrolling interest | `MinorityInterest` | Instant | EV |
| Sales | `RevenueFromContractWithCustomerExcludingAssessedTax`, `Revenues` | Annual | Piotroski, Altman, Beneish |
| Cost of revenue | `CostOfRevenue`, `CostOfGoodsAndServicesSold` | Annual | Gross profit |
| Gross profit | `GrossProfit` | Annual | Piotroski, Beneish |
| Operating income | `OperatingIncomeLoss` | Annual | EBIT |
| SG&A | `SellingGeneralAndAdministrativeExpense` | Annual | Beneish |
| D&A | `DepreciationDepletionAndAmortization` | Annual | EBITDA, Beneish DEPI (fallback basis) |
| Depreciation alone | `Depreciation` | Annual | Beneish DEPI (preferred basis) |
| Interest expense, gross | `InterestExpense` | Annual | Interest Coverage, total debt |
| Pretax income | `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest` | Annual | ROIC |
| Income tax expense | `IncomeTaxExpenseBenefit` | Annual | ROIC |
| Net income | `NetIncomeLoss` | Annual | Piotroski, Beneish |
| Income from continuing operations | `IncomeLossFromContinuingOperations` | Annual | Beneish |
| Discontinued operations | `IncomeLossFromDiscontinuedOperationsNetOfTax` | Annual | Beneish |

Already mapped and reused: operating cash flow, capital expenditures, stockholders' equity, common
shares outstanding.

**Other new evidence**

- As-filed SIC code from the selected filing's SEC header (SD §1).
- Split and stock-dividend history from the historical market-data boundary.
- Unadjusted historical close on or before a requested `as_of` (SD §4).

**Entry criterion: SIC evidence**

Checked before any mapping or applicability code is written.

- Confirm from captured filings that a filing's SEC header keeps the `ASSIGNED-SIC` of its filing
  date, using an issuer whose SIC is known to have changed.
- If it does not, sector-gated strategies are `unavailable` for a requested `as_of`. The current
  SIC is not a fallback, and the slice returns to the project owner before continuing.

**Mapping evidence gate**

For every field in the table, the slice captures filing evidence and records, per taxonomy:

- the concept, context, units and scale;
- whether it is a period amount or a balance at a date;
- which filer populations report it, and what the others report instead;
- the disposition: approved, approved with a stated limit, or unsupported.

An unsupported field makes its consumers `unavailable`. It is never approximated by a neighbor.

**Depreciation evidence (for Beneish DEPI)**

- A filing reporting depreciation alone, one reporting only combined D&A, and one reporting both.
- Where both are reported, check the identity D&A = depreciation + amortization. If it does not
  hold, the candidate concepts do not mean what the table assumes.
- Confirm the depreciation concept is the year's expense, not accumulated depreciation.
- Confirm net PP&E is consistently obtainable for the same dates.
- US GAAP and IFRS examples of each where they exist.
- Outcome: the depreciation-alone mapping is approved, limited or unsupported. If unsupported,
  every Beneish run uses the D&A basis (SS §3).

**Tests**

- Each new field carries its correct unit; existing fields and stored values are unchanged.
- Exact-date selection of three year-ends; the newest balance sheet is never returned for an
  earlier date.
- 52/53-week pairs accepted; quarters, year-to-date and stub years rejected.
- A filing after the boundary, a later comparative restatement, a conflicting duplicate, and a
  wrong CIK, taxonomy or currency are each rejected or reported as the rules require.
- Total revenue is not confused with a segment figure; overlapping revenue concepts are never
  summed.
- Debt: a direct total reconciles with its parts and is never double counted; each row of the
  [total-debt](STEP_3_5_SHARED_DEFINITIONS.md#total-debt) table; commercial paper is not a current
  maturity.
- Leases: a US GAAP operating-lease liability is not debt; an IFRS lease liability is.
- Split and stock-dividend history adjusts a share count without reading as issuance.
- SIC: a known bank, insurer, REIT, utility and manufacturer classify correctly; a code in no
  range is non-financial non-manufacturing; an unreadable header is `unavailable`; a header filed
  after the boundary is rejected.

**Non-goals:** no strategy calculation; no change to Graham's latest-only balance-sheet
selection; no SIC in the instrument profile; no schema migration.

## 3. 3.5.2 — Shared metrics and ranking helper

**New data:** none beyond 3.5.1.

**Result shape:** each shared metric is a pure function over resolved facts that returns a
`MetricResult` plus the operands and provenance it used. Market cap also returns its share-count
date and price date. EV and total debt return each component and which absent components were
taken as zero.

**Tests**

- Market cap: count at year-end *t* only; no count is `unavailable`; conflicting counts are
  `unavailable`; a split between the two dates scales the count; per-class counts with no total
  are `unavailable`; a one-day historical download is never used as a quote.
- EV: each absent-component case; missing cash is `unavailable`; negative EV is a valid number.
- Invested capital: IC ≤ 0 makes dependent ratios `not_applicable`.
- FCF-Growth: FCF yield becomes available through the shared market cap with its formula and
  every existing expected value unchanged.
- Ranking helper, on synthetic members:
  - any input order gives the same output;
  - duplicate issuers keep the alphabetically first ticker and report the rest, with the
    canonical-representative diagnostic;
  - a member missing any metric is excluded with its reason;
  - nine eligible members return no ranks, ten return ranks;
  - tied values share the average rank;
  - tied sums share a position and the next position skips (1, 1, 3);
  - higher-is-better and lower-is-better directions.

**Non-goals:** no weights; no persistence; no knowledge of strategies or runs in the helper; no
change to the FCF or FCF-yield formulas.

## 4. 3.5.3 — Piotroski F-Score

**New data:** none beyond 3.5.1. Needs total assets at three year-ends and the other inputs SS §1
lists.

**Result shape:** nine test results in fixed order, each with status (pass, fail, unavailable),
operands, ratios and provenance; the score as a `MetricResult`; completeness (complete or
partial); the count of available tests; the industry class and its warning; the method version.

**Tests**

- Every case in the [arithmetic oracle](STEP_3_5_PIOTROSKI_EVIDENCE.md#4-arithmetic-oracle), with
  expected values written as independent fractions, never produced by the calculator.
- Each strict comparison at equality and on either side.
- Shuffled input order gives the identical result.
- A missing newest-year input never triggers an older-year score.
- Missing *t−2* assets affects exactly tests 3, 5 and 9.
- A complete score of 0 is a completed run; a partial score is `ok` and partial; fewer than six
  tests is `unavailable`.
- A partial score is never shown as a bare number or as "*x* of 9".
- Result invariants: exactly nine tests, points consistent with status, finite numbers only.
- One issuer case from captured fixtures, checked independently
  ([candidate](STEP_3_5_PIOTROSKI_EVIDENCE.md#5-apple-recorded-values-and-worked-example)).

**Non-goals:** no issuance-proceeds reading; no user-selectable denominators or income basis; no
ranking of partial scores. An envelope change Piotroski needs is applied to every analyzer.

## 5. 3.5.4 — Altman and Beneish

Two sub-slices: 3.5.4a Altman, 3.5.4b Beneish.

**New data:** none beyond 3.5.1.

**Result shape**

- Altman: the model used (Z or Z″), each variable as a `MetricResult`, the score, and the zone as
  a result field.
- Beneish: eight indices as `MetricResult`s, the score, the threshold flag, the income basis TATA
  used and the DEPI basis.

**Tests**

- Altman: model selection by industry class; each zone boundary at equality and on either side;
  negative retained earnings and negative book equity are valid; total assets or total liabilities
  ≤ 0 is `unavailable`; market cap unavailable makes Z `unavailable` and leaves Z″ unaffected.
- Beneish: any one missing index makes the score `unavailable`; no index defaults to 1.0; each
  zero denominator; TATA's three income cases (SS §3); LVGI uses noncurrent debt only; the flag
  wording never says "manipulator" and never states a probability.
- Beneish DEPI basis: depreciation alone in both years gives the canonical basis; D&A only gives
  the D&A basis with its diagnostic; depreciation alone in one year only gives the D&A basis for
  both; neither gives `unavailable`; the basis appears in every view and in stored-run replay.

**Entry criterion for 3.5.4b:** 3.5.1's depreciation evidence is complete, and the DEPI algebra
(period expense over expense plus net PP&E, prior year over current year) has been checked by hand
against one captured filing.

**Non-goals:** no imputation; no probability; no partial Beneish score; Z′ (the private-firm
model) is not offered.

## 6. 3.5.5 — Valuation multiples, Interest Coverage and ROIC

Three sub-slices: 3.5.5a Valuation Multiples, 3.5.5b Interest Coverage, 3.5.5c ROIC.

**New data:** none beyond 3.5.1. ROIC needs four annual filings.

**Result shape**

- Valuation Multiples: EV/EBITDA and FCF yield as `MetricResult`s, with EV's components and both
  market-cap dates.
- Interest Coverage: EBIT and EBITDA coverage as `MetricResult`s; the band as a result field.
- ROIC: trailing ROIC and incremental ROIC as `MetricResult`s; per year, the reported tax rate,
  the rate used and whether it was clamped.

**Tests**

- Valuation Multiples: EBITDA ≤ 0 and EV ≤ 0 are `not_applicable`; a negative FCF yield is
  reported with its sign note; FCF yield equals FCF-Growth's value for the same run.
- Interest Coverage: each band boundary at equality; zero debt with no interest is
  `not_applicable` with the favorable band; no interest with debt is `unavailable`; net-only
  interest is `unavailable`; negative EBIT is `ok` and Distressed.
- ROIC: a rate above 0.50 and a negative rate are clamped, flagged and keep the reported rate;
  pretax income ≤ 0 gives a zero rate; missing tax expense is `unavailable`; average IC ≤ 0 is
  `not_applicable`; incremental ROIC's four requirements fail in order with the right reason and
  leave trailing ROIC reported; the 10% floor at equality.

**Non-goals:** no FCF / EV; no fixed-charge coverage; no non-recurring adjustments; no lease
normalization; no EBIT-only ROIC variant.

## 7. 3.5.6 — Magic Formula and ranked refresh view

Two sub-slices: 3.5.6a the analyzer, 3.5.6b the ranked view.

**New data:** none beyond 3.5.1 and 3.5.2.

**Result shape**

- Analyzer: return on capital and earnings yield as `MetricResult`s, with their operands. No rank.
- Ranked view: per member, each metric's rank and percentile, the rank sum, the position and the
  taxonomy; the excluded members with reasons; the duplicate-issuer and mixed-framework
  diagnostics. Nothing is persisted.

**Tests**

- Analyzer: EBIT ≤ 0, IC ≤ 0 and EV ≤ 0 are `not_applicable`; financial issuers and utilities are
  `not_applicable`.
- Ranked view: built from stored runs with provider, cache, clock and calculator disabled; mixed
  `as_of` values refuse; fewer than ten eligible members return values without ranks; two runs of
  the strategy for one ticker refuse and name the duplicates; two share classes of one issuer keep
  one member; mixed taxonomies rank with the diagnostic; the same refresh always gives the same
  view.

**Non-goals:** no ad-hoc ticker list; no persisted ranks; no market-wide universe; no weights.

## 8. 3.5.7 — Side-by-side refresh table

**New data:** none.

**Result shape:** one row per ticker; per strategy, the headline values and outcome, fiscal period
end, taxonomy and run ID; text and `--json` forms.

**Tests:** built from one `refresh_id` with provider, cache, clock and calculator disabled;
differing fiscal year-ends shown, not normalized; a failed or unavailable run shows its outcome
and does not drop the row; two runs for one ticker and strategy refuse and name the duplicates;
sorting by a ranked view matches that view.

**Non-goals:** no new persistence, batch ID or run type; no composite column.

## 9. 3.5.8 — Golden suite and cross-cutting docs

**New data:** captured fixtures for the regression issuer set in the contract's acceptance
criteria.

**Tests:** one Golden case per strategy with independently checked expected values; available,
unavailable and `not_applicable` outcomes reproducible without live providers; every existing
Golden value unchanged.

**Non-goals:** no change to the meaning of the existing benchmark; no live calls in the suite.
