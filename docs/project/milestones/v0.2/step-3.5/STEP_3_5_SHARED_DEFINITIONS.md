# Step 3.5 — Shared Definitions

Owns the definitions every Step 3.5 strategy shares: applicability, outcomes, data sources, the
shared metrics, and the side-by-side refresh table. Per-strategy formulas live
in [Strategy specifications](STEP_3_5_STRATEGY_SPECIFICATIONS.md). Scope, sequencing and status
live in the [contract](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status).

Each shared metric is defined here once and used by every consumer. A strategy never carries its
own variant or fallback formula for any of them.

## 1. Applicability

Industry class comes from the issuer's SEC SIC code (3.5.1). GICS is not used: it is proprietary
and unavailable from the project's sources.

| Class | SIC range |
| :--- | :--- |
| Financial (includes REITs) | 6000–6799 |
| Utility | 4900–4999 |
| Manufacturer | 2000–3999 |

| Strategy | Financial | Utility | Notes |
| :--- | :--- | :--- | :--- |
| Piotroski | Applicable, with a warning | Applicable | |
| Altman | Not applicable | Applicable | Classic Z for manufacturers, Z″ for all others |
| Cash-Flow Valuation Multiples | Not applicable | Applicable | |
| Interest Coverage | Not applicable | Applicable | |
| ROIC | Not applicable | Applicable | |

The accrual ratio's and Shareholder Yield's rows are set in their slice plans ([A.16](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a16-strategy-set-revised-2026-11-02)).

An issuer whose SIC code falls in none of the three ranges is an ordinary non-financial,
non-manufacturing issuer.

### Industry-class evidence

- **Source:** for an analysis anchored to an eligible annual filing (the anchor filing of
  [§3](#period-alignment)), applicability is decided from the `ASSIGNED-SIC` in that filing's SEC
  header.
- **Point-in-time:** the code is kept as filing evidence with the filing's accession, filing date
  and acceptance time, and passes the same boundary check as every other input. A live run uses
  the same rule, so one issuer and one filing always give one class.
- **Never the current value:** the `sic` field of the EDGAR submissions data is the issuer's
  classification today. It never substitutes for the as-filed code, because applying it to a
  historical run would be look-ahead.
- **Where it lives:** in the strategy's resolved evidence, with its provenance. It is not added to
  the instrument profile, which holds request-scoped identity evidence and has no historical form.
- **Unknown:** when the as-filed code cannot be read, a sector-gated strategy's metrics are
  `unavailable` with a reason code saying so. Piotroski, which is not sector-gated, runs without
  the financial-issuer warning and says the class is unknown.
- **Limitation:** the SEC assigns one coarse code per filer. A diversified issuer is classified by
  that one code.

## 2. Outcomes and reason codes

Every calculated numeric metric is a `MetricResult` (`investment_analysis_engine/core/metric_result.py`); no new status is
introduced.

| Situation | `MetricStatus` |
| :--- | :--- |
| Computed | `ok`, with a finite value |
| A required input is missing, ambiguous or not available as of the boundary | `unavailable` |
| The strategy does not apply to the issuer's industry class | `not_applicable` |
| The inputs are valid but the value has no economic meaning (for example, EV/EBITDA with negative EBITDA) | `not_applicable` |

- Each non-`ok` result carries a `ReasonCode`. Existing codes are reused where one fits; 3.5.1 adds
  the codes no existing one covers, such as sector applicability and unknown SIC. 3.5.2b adds `unsupported_mapping` and
  `debt_not_visible`. A balance-sheet value absent at a year-end maps to a code by one table: `not_tagged`,
  `other_concept` and `no_anchor_filing` give `missing_fact`; `conflict` gives `ambiguous_fact`; `unsupported` gives
  `unsupported_mapping`; `after_boundary` gives `not_available_as_of`; `basis_mismatch` gives `incompatible_scope`.
  3.5.3a adds `nonpositive_denominator`, for a denominator that is not positive, and `insufficient_tests`, for a
  Piotroski score with fewer than six tests available.
  The stale-anchor slice ([A.17](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a17-stale-anchor-filing-and-the-anchor-rule-2026-11-09))
  adds `stale_anchor`, for a market cap refused because the anchor filing is stale ([§3](#stale-anchor)).
- No value is ever `NaN` or `Inf`. A ratio with a zero or non-positive denominator is `unavailable`
  or `not_applicable` with a reason code, as each definition below states.
- **What is not a `MetricResult`:** strategy-level scores, zones, bands, completeness and
  eligibility flags are typed fields of the strategy's own result. None of them is forced through `MetricResult`, and none is a new status. A
  field that is itself a number with its own availability (the Piotroski score) is the one case
  that is also a `MetricResult`.

### Result-level status

Every strategy result carries one explicit `execution_status`, a `CalculationStatus` (no new status is
introduced), as `FCFEarningsGrowthResult` does. It is the software outcome of the run, independent of any
band, zone or score, and it is what the strategy's native-status function returns. The strategy reports that
status and the shared rule `RunOutcome.from_status` produces the workspace outcome (`ok` is completed,
`not_applicable` is not applicable, `input_unavailable` is unavailable); no strategy decides an outcome itself.
No strategy reports a missing status because of how many numbers it displays. A calculation that cannot run for a reason outside the inputs raises, as today; it is not a
status.

| Strategy | `ok` | `input_unavailable` | `not_applicable` |
| :--- | :--- | :--- | :--- |
| Piotroski F-Score | The score is `ok`: nine tests available (complete) or six to eight (partial). | Fewer than six tests available. An unknown industry class does not change the status: Piotroski is not sector-gated, runs, and states the class is unknown. | None: financial issuers are applicable with a warning. |
| Altman Z / Z″ | The score is `ok` for the selected model. | The score is `unavailable`, including total assets or total liabilities not positive, or an unknown industry class. | A financial issuer. |
| Cash-Flow Valuation Multiples | At least one of EV/EBITDA and FCF yield is `ok`. | Neither is `ok` and at least one is `unavailable`, or an unknown industry class. | A financial issuer, or both metrics `not_applicable`. |
| Interest Coverage | A band is assigned, including "no material interest expense". | Interest expense is not reported while total debt is positive, only net interest is reported, EBIT is missing, or an unknown industry class. | A financial issuer. |
| ROIC and Incremental ROIC | Trailing ROIC is `ok`; incremental ROIC's own availability is reported separately. | Trailing ROIC is `unavailable`, or an unknown industry class. | A financial issuer, or average invested capital not positive. |

The accrual ratio's and Shareholder Yield's rows are set in their slice plans ([A.16](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a16-strategy-set-revised-2026-11-02)).
The outcome that decides each row is the one the strategy specification already states for its metrics;
the table adds no formula, threshold or classification. Momentum's result carries an `execution_status` too
([3.5.0a](STEP_3_5_0_SLICE_PLAN.md#350a--momentum-result-level-status)): `ok` when the trend is bullish or
bearish; `input_unavailable` when the trend is `UNKNOWN`, when no price observation exists at or before the
boundary, or when the data-quality check fails; `provider_error` when the market-data provider fails.

## 3. Data sources, periods and point-in-time

- **Fundamentals:** SEC EDGAR XBRL annual filings only (10-K, 20-F, 40-F; us-gaap and ifrs-full),
  resolved through the existing financial-fact resolver. No other configured provider serves a
  historical `as_of` for fundamentals, so none is offered for these strategies.
- **Prices:** see [§4](#4-market-capitalization).
- **Periods:** fiscal-year filings only. A year-over-year test compares consecutive fiscal years
  of the same issuer.
- **Point-in-time:** a strategy uses the latest annual filing with a filing date on or before
  `context.effective_as_of`. Restatements follow the existing amendment-selection rules.
- **Exception, split history:** the price data is adjusted by the provider for every later split, so splits after the
  boundary are used, only to undo that adjustment ([§4](#4-market-capitalization)). They never change the market cap
  at the boundary, and no other input uses information from after it.

### Period alignment

- **Anchor year:** year *t* is the fiscal year of the anchor annual filing, the newest completed fiscal year available
  at the boundary. If its inputs are missing, the affected metrics are `unavailable`. A strategy never steps back to an
  older year to produce a complete-looking result.
- **Anchor filing:** the annual filings accepted at or before the boundary are read newest first by acceptance time. The
  first original annual report read (a 10-K, 20-F or 40-F, not an amendment) fixes the anchor's fiscal year, matched on
  the filing's report date. The anchor is the newest filing for that fiscal year, so it is an amendment of that year when
  one was accepted after the original. An amendment for an older fiscal year never becomes the anchor, however recently it
  was filed: it restates a year that is no longer the newest, and taking its year-end would step back to an older year.
  The rule rests on original annual reports being filed in fiscal-year order. Fiscal years are matched on the report
  date, never on `fy` or `frame` labels. When the recent block of the registrant's submissions holds no original annual
  report at or before the boundary, the adapter reads the older submissions pages newest first, skipping a page that
  starts after the boundary, until one does, at most `_MAX_SUBMISSION_PAGES` pages. When that many pages hold none, the
  anchor is `no_anchor_filing` and its message states the earliest filing date the pages reached.
- **Actual dates decide:** periods are matched on their reported start and end dates. The
  Company Facts `fy` and `frame` labels describe the filing an observation appeared in, not the
  period it measures, and are never used to align years.
- **Annual durations:** the existing annual-duration tolerance applies, so 52- and 53-week years
  are consecutive. Quarters, year-to-date periods, and transition or stub years are rejected.
- **Balance-sheet values** are instants at a fiscal year-end, never durations. A metric that
  needs several year-ends requests each exact date and never reuses the newest one.
- **Prior year-ends:** year-end *t−1* is the day before the reported start date of year *t*'s completed annual period,
  and *t−2* is derived the same way from year *t−1*'s period. The start date is read from an explicit, strategy-neutral
  priority list of completed-annual fields (`YEAR_END_START_FIELDS` in `analysis/shared/metric_inputs.py`: net income, sales
  and operating cash flow); every listed field present for that year must give the same start date,
  otherwise that year-end is `unavailable` with `ambiguous_fact`, and when no listed field is present it is `unavailable`
  with `missing_fact`. The derived date must be 335
  to 395 days before the later year-end. A transition or stub year is not a completed annual period: it breaks the chain,
  and the earlier year-ends are `unavailable`. The `reportDate` of earlier filings is never used.
- **Comparatives:** prior-year values come from the anchor filing where it reports them. An earlier
  year-end it does not report (such as *t−2* total assets) may come from an earlier eligible
  filing, on the same taxonomy and currency. Every such value passes the same boundary check.
- **Conflicts:** two eligible values of equal priority that disagree make the input `unavailable`.
- **One basis:** a run never mixes us-gaap with ifrs-full, or two reporting currencies.

### Stale anchor

The anchor filing is **stale** when the next annual report was overdue at the boundary and none had been filed by it.
The boundary's date is the UTC date of `context.effective_as_of`.

- **Age:** it runs from the anchor's fiscal year-end, never from its filing date.
- **Due date:** `next_report_due` is the anchor's `year_end` plus one calendar year (29 February becomes 1 March), plus
  7 days so a 53-week fiscal year is never judged late, plus the form's allowance below, extended by any relief period
  below that its original due date falls in. A calendar-month allowance is added to the date after the 7 days, and a
  month's end clamps to the last day of a shorter month.
- **Stale:** the boundary's date is after `next_report_due`. On the due date itself the anchor is not stale.
- **Never early:** every allowance is the most generous regular deadline for the form plus any automatic extension, so the
  rule never warns early. The limitation is that a large accelerated filer, whose 10-K is due 60 days after year-end,
  gets up to 45 days of grace without a warning.

The form's allowance, one declaration in code (`ALLOWANCES` in `analysis/shared/anchor_filing.py`) that a test compares
with this table:

| Forms | Fiscal year-ends | Allowance |
| :--- | :--- | :--- |
| 10-K, 10-K/A | every | 105 days |
| 20-F, 20-F/A | on or after 2011-12-15 | 4 calendar months + 15 days |
| 20-F, 20-F/A | before 2011-12-15 | 6 calendar months + 15 days |
| 40-F, 40-F/A | every | 120 days |

- **10-K:** 90 days after year-end is the deadline of the most generous filer category (General Instruction A of Form
  10-K: 60, 75 or 90 days), and 15 calendar days more are the extension of Rule 12b-25 (17 CFR 240.12b-25(b)(2)(ii)).
  The text of both was read.
- **20-F:** Release 33-8959 (2008) set the deadline at four months after the fiscal year-end for fiscal years ending on or
  after 2011-12-15 (General Instruction A.(b) of Form 20-F); the earlier deadline was six months, which is what 17 CFR
  249.220f(b) shows in the republication read (Cornell LII). Rule 12b-25 adds 15 calendar days to either. The four-month
  deadline rests on the Release as the project owner gave it; its text was not read.
- **40-F:** the filing is due when the Canadian annual documents are, which National Instrument 51-102 sets at 90 days
  after year-end, or 120 days for a venture issuer; 120 days is the longest regular deadline. Rule 12b-25 does not list
  Form 40-F, so no extension is added. The General Instructions of Form 40-F state no due date of their own; the figure
  rests on the instrument as the project owner gave it, and its text was not read.

Relief periods, one declaration in code (`RELIEF_PERIODS`) that a test compares with this table. A report whose original
due date (the date above before any relief) falls inside a window gets its extra days, whatever the form:

| Original due dates | Extra days | Source |
| :--- | :--- | :--- |
| 2020-03-01 to 2020-07-01 | 45 | SEC COVID-19 order (March 2020; Release 34-88465), for 10-K and 20-F; the Canadian securities regulators' blanket 45-day relief (March 2020), for the Canadian annual filings a 40-F follows |

The SEC relief required the filer to give notice, which the engine cannot check. It is applied to every filer, so the rule
never warns early.

- **Effect, one rule for every strategy:** a result built only from filing evidence keeps its status and carries the
  anchor filing element and the warning message; no strategy decides this itself.
  - The element is `anchor_filing` in the common strategy-document header, after `effective_as_of`, with `year_end`,
    `form`, `accession`, `filing_date` (null when the submissions data does not date the filing), `next_report_due` and
    `stale`. It is null for a strategy that does not report the anchor filing and on replay of a run stored before it
    existed.
  - The warning message is: "The newest annual report filed by {boundary date} is for the fiscal year ended {year_end}
    ({form}, filed {filing_date}). The next one was due by {next_report_due} at the latest, and none had been filed." The
    clause ", filed {filing_date}" is dropped when the filing date is null. Dates are ISO dates. The message is also the
    first entry of the document's warnings.
  - Market cap at a stale anchor is `unavailable` with `stale_anchor` ([§4](#4-market-capitalization)).

### Absent-component convention

These optional components are treated as zero when the filing reports no element for them, with
a diagnostic saying so:

- preferred stock;
- noncontrolling interest;
- short-term investments;

Filers do not tag a line they do not have, so for these items an absent element is the normal way
a filing says "none", and requiring an explicit zero would make EV unavailable for most issuers.

- **Equivalent concepts:** a field may map to a priority list of concepts where the evidence shows they are the same
  line item (short-term investments). The convention applies only when none of the listed
  concepts is tagged for the year-end. One issuer uses one concept for every year of a run, so a year the run's concept
  does not cover is absent, not zero. Alphabet (marketable securities) and Moderna (investments) tag
  short-term investments under other names than `ShortTermInvestments`.
- **Unsupported mappings:** the convention never applies to a field whose mapping is recorded as unsupported for the
  taxonomy. The field is `unavailable`.
- **Short-term investments need a classified balance sheet:** the zero applies to short-term investments only when
  current assets are tagged at that date. On an unclassified balance sheet the absence of the line does not show that
  the filer has none, so short-term investments are `unavailable`. Deere's balance sheet is unclassified and it holds
  1,411 million of marketable securities its listed concepts do not read, so its EV is `unavailable`
  ([mapping evidence §5.6](STEP_3_5_1_MAPPING_EVIDENCE.md#56-findings-the-owner-decides)).

The convention never applies to the critical inputs each definition below names. Debt is not
covered by it: [total debt](#total-debt) has its own, stricter rule. These two are the only cases
in which an absent element yields a number.

## 4. Market capitalization

**Market cap = common shares outstanding × price**

- **Shares:** the existing `COMMON_SHARES_OUTSTANDING` field: common shares outstanding on the
  balance sheet at fiscal year-end *t* of the selected filing. See
  [share-count rule](#share-count-rule).
- **Price:**
  - with a requested `as_of`: the split-adjusted close, without dividend adjustment, on the last trading day on or
    before `as_of`, from the historical market-data boundary. A date-only `--as-of` includes that day's close, and
    sessions are read by exchange-local date, as Momentum reads them. The provider has no unadjusted close; the
    split-adjusted close and the split history together recover it. The dividend-adjusted series is never used for
    market cap;
  - without one: the current quote, through the existing quote boundary and its freshness rules. The split history is
    requested as adjusted on the quote's date, so the count is scaled up to the quote.
  A one-day historical download is never used as a quote.
- **Provider split adjustments, in two windows.** The provider's split history reports splits and other adjustments
  alike: a spin-off appears as a ratio such as 1.061 or 0.9535, and a spin-off does not change the share count. A
  cover-page count is scaled by the events whose ex-date is after the cover date, and a balance-sheet count by those
  whose ex-date is after the filing date of the filing the count was taken from, up to the adjustment date of the price
  data, in two windows:
  1. **After the price date** (and not after the adjustment date): always applied, whatever the ratio. The provider
     adjusted the historical close for the event and the count of that date is untouched by it, so scaling undoes the
     retroactive adjustment of the price.
  2. **After the count's date and not after the price date:** applied only when the ratio is recognizable, where
     a ratio is a recognizable split ratio when it is *p*-for-*q* with *p* in 2 to 10, 15, 20, 25, 30, 40, 50 or 100, *q* in 1 to 4 and *p* greater than *q* (2-for-1, 3-for-1, 10-for-1, 3-for-2, 5-for-4, ...), or the reciprocal of one (a reverse split, 1-for-10 is 0.1), compared exactly (`RECOGNIZED_SPLIT_RATIOS` in `analysis/shared/split_adjustment.py`). Any other ratio makes the market cap `unavailable` with `ambiguous_fact`, and the message names the
     event's ex-date and ratio, because the history cannot say whether the shares changed. On the live path the price
     date is the quote's date, so every event after the count's date is in this window. A stock dividend such as
     Commerce Bancshares' 1.05 or Tootsie Roll's 1.03 is refused here (W1 of the 3.5.2 plan reverses F7 of the 3.5.1
     plan inside this window).

  The evidence lists the applied events as provider split adjustments, each with its window.
  The accession and filing date are those in the count's own provenance; The accession and filing date are those in the
  count's own provenance; the anchor filing is not assumed, because a later filing's comparative restates an earlier
  year-end for splits up to that later filing's own date. A filing restates its share counts for a split effective before
  it is issued (SEC Staff Accounting Bulletin Topic 4.C), so such a split is already in the count and is not applied
  again.
- **Effect:** the market cap is the same as the one the unadjusted price and the unscaled count of the same date give. The
  formula and the value are unchanged; this states only how it is computed. Splits after `as_of` are used only to undo the
  provider's retroactive adjustment ([§3](#3-data-sources-periods-and-point-in-time)).
- **Availability, security unit and currency:** the market cap does not use the security-unit rule of Graham
  (`evaluate_security_unit_compatibility`): that rule refuses every run with `as_of`, every filer other than a us-gaap
  10-K filer, and any cover with more than one class title (Alphabet). The market cap is available only when all of
  these hold:
  1. **The anchor annual filing is a 10-K or 10-K/A** (`incompatible_scope` otherwise). A 20-F or 40-F filer is a foreign private
     issuer whose US listing may be a depositary receipt at a ratio the structured data cannot show. SAP's market cap
     is therefore `unavailable`.
  2. **The quote currency equals the filing currency** (`incompatible_currency` otherwise). When either is unknown, the
     market cap is `unavailable`. The filing currency is that of the monetary facts resolved at *t*, never one
     requested in a configuration; the quote currency is the quote's, or with `as_of` the split-history response's.
  3. **A listing check on the anchor 10-K's cover affirms the requested ticker.** The ticker must appear there under
     this CIK, on a registered title that is a share of the issuer. Class designations and "ordinary shares" are
     accepted; depositary shares, units, warrants and preferred securities are refused (`incompatible_units`); a
     missing or unreadable cover is `unavailable` (`missing_fact`). The check works with `as_of`, because the cover of
     a filing on or before the boundary is historical evidence. A ticker that is not on the anchor cover is read
     against the cover of the registrant's latest 10-K or 10-K/A and affirmed only when the anchor cover lists exactly
     one share line and no depositary share and the latest cover lists the ticker as the only share line: the one share
     line is renamed, not replaced, and the result records both accessions and symbols ([P22](STEP_3_5_2_SLICE_PLAN.md#a6-decided-under-delegation-during-352c-2026-10-26)).
     The accepted titles are common stock, common shares,
     ordinary shares and the class designations of the captured covers, with or without a par-value clause; a title
     outside that list is `unavailable` (`missing_fact`), never affirmed
     ([vocabulary and evidence](STEP_3_5_2_LISTING_EVIDENCE.md#6-the-title-vocabulary)).
  4. **The share-count rule for several classes below holds:** Alphabet's single combined count is valued at the
     requested ticker's price, and per-class counts with no total are `unavailable`.
  5. **The anchor filing is not stale** ([stale anchor](#stale-anchor)): otherwise the market cap is `unavailable` with
     `stale_anchor` and the message "Market cap unavailable: the anchor filing is stale, so its share count is not the
     count at {boundary date}." The share count is that of a filing that was overdue to be replaced, so pairing it with
     the boundary's price would not give the market cap at the boundary. Everything built on market cap follows through
     the existing propagation, with no per-strategy code.
- **Limitation, stated in the guides:** a ticker renamed after the anchor filing is affirmed only by the rename rule
  of item 3; any other renamed ticker does not match the cover and is `unavailable`.
- **Critical inputs:** shares and price.
- **Dates stay visible** in the result: the share-count date, the filing date of the count's source and the price date.

### Share-count rule

- **One observation:** the count at fiscal year-end *t*, as the existing resolver returns it:
  reported directly, or as shares issued minus treasury shares at the same date. The share-count
  date is that fiscal year-end.
- **IFRS filers:** `ifrs-full:NumberOfSharesOutstanding` is a direct path. There is no IFRS
  issued-minus-treasury path: no IFRS treasury share count exists in the evidence.
- **Cover-page fallback:** when the balance-sheet paths give no count at year-end *t* (a count dated another day is
  not a count at *t*), the cover-page count
  (`dei:EntityCommonStockSharesOutstanding`) of the anchor filing is used for market cap, and only when the filing
  tags it as a single non-dimensional total. Its own date is the share-count date, and the result says that the
  count is a cover-page count. Filers that report only per-class cover counts, with no total, have no usable count.
  Piotroski's dilution test never uses it: it compares year-end balance-sheet counts.
- **No count at year-end *t* by any path:** market cap is `unavailable`. An older year's balance-sheet count is
  never substituted.
- **Conflicting counts** for the same date make market cap `unavailable`
  ([§3](#period-alignment)).
- **Several share classes:** when the filer reports counts per class and no unambiguous total,
  market cap is `unavailable`. Where one total is reported, it is valued at the requested ticker's
  price.
- **Limitation, stated in the guides:** buybacks and issuance between the fiscal year-end and the
  price date are not reflected. A split announced before the filing but effective just after it is assumed not to be
  reflected in the filing.

## 5. Gross profit, EBIT, D&A and EBITDA

- **Gross profit:** the reported gross profit; otherwise sales minus cost of revenue when both are reported, keeping
  both inputs' provenance. It is never taken from operating income, and a filer that reports neither form has none
  (Piotroski uses it).
- **EBIT:** reported operating income (`OperatingIncomeLoss`, or
  `ProfitLossFromOperatingActivities` under IFRS). It is never rebuilt from pretax income plus
  interest. Absent operating income makes EBIT `unavailable`.
- **D&A:** depreciation, depletion and amortization from the cash-flow statement, using the
  concept priority list in the field mapping.
- **EBITDA:** EBIT + D&A.

## 6. Enterprise value

**EV = market cap + total debt + preferred stock + noncontrolling interest − cash and cash
equivalents − short-term investments**

- **Total debt:** defined [below](#total-debt), including which
  [lease liabilities](#lease-liabilities) count as debt.
- **Critical inputs:** market cap and cash.

### Total debt

**Total debt = short-term borrowings + current portion of long-term debt + long-term debt +
lease liabilities counted as debt**

A missing debt figure is not assumed to be zero. Debt is tagged in more varied ways than the
optional items in [§3](#absent-component-convention), so a missing mapped concept is weak evidence
that the debt does not exist, and a wrong zero always flatters the issuer: lower EV, a passed
leverage test, "no interest expense". An absent component counts as zero only with supporting
evidence:

| What the filing reports for the year-end | Treatment |
| :--- | :--- |
| At least one mapped debt concept at the year-end | An absent component is zero, with a diagnostic, only when its mapping is not unsupported for the taxonomy and none of the [related concepts](#related-debt-concepts) recorded for it is tagged at that date. Otherwise the component is `unavailable`. |
| No mapped debt concept, no related concept tagged, no component unsupported for the taxonomy, and interest expense absent or zero | Total debt is zero ("no reported debt"), with a diagnostic. |
| No mapped debt concept, but interest expense is positive, a related concept is tagged, or a component is unsupported | Total debt is `unavailable`: the issuer has debt the mapping does not see. |

- **Direct totals:** where a filer reports a direct long-term-debt total, it must reconcile with its current and
  noncurrent parts, and the total is never added to its parts or used as a value. A part absent as `not_tagged` with
  no related concept counts as zero for the check. A mismatch makes total debt `unavailable`: `ambiguous_fact` when a
  part is present, with both parts as the affected components, and `debt_not_visible` when neither is. A part absent
  for any other reason, or with a related concept, keeps its own outcome. The check comes before the other component
  rules, so a filer that tags only the direct total never has zero debt.
- **Short-term borrowings are not current maturities.** Commercial paper belongs to short-term borrowings
  (`CommercialPaper` is read only where `ShortTermBorrowings` is not tagged, and never added to it) and never stands in
  for the current portion of long-term debt.

#### Related debt concepts

A related concept is one the evidence shows a filer tags for part of the same quantity, without being the line item of
the mapped concept: Deere's `DebtCurrent` (short-term borrowings and the current portion together), Honeywell's
`LongTermDebtAndCapitalLeaseObligationsCurrent` and `LongTermDebtAndCapitalLeaseObligations` (debt with finance
leases), SAP's combined current-borrowings concept. They are recorded per debt field in the
[mapping evidence](STEP_3_5_1_MAPPING_EVIDENCE.md#related-concepts-of-the-debt-fields). A related concept is never a
value; the balance-sheet series reports, for each absent date, which related concept is tagged, and the rule above reads
that report.

- **IFRS:** the noncurrent long-term debt mapping is unsupported for every IFRS filer, decided by the project owner, so
  an IFRS issuer's total debt is `unavailable`, and so is every metric that needs it, EV included, while the mapping is
  unsupported. Nutrien's noncurrent debt is never read as zero.
- Every consumer of a debt figure uses this rule, including Piotroski's long-term debt and
  Interest Coverage's zero-debt outcome.
- **Long-term debt** (Piotroski) is the current portion of long-term debt plus noncurrent long-term debt, decided by the
  rules above: the direct-total reconciliation comes first; an absent part is zero only when it is `not_tagged` with no
  related concept and at least one of the four mapped debt concepts is present at the date; with none present, the
  no-reported-debt row applies, using that year's interest expense; an unsupported mapping makes it `unavailable`, so
  Piotroski's test 5 is unavailable for every IFRS filer. It is never total debt less short-term borrowings, because a gap
  in short-term borrowings would remove long-term debt.

### Lease liabilities

Lease figures are used as each accounting framework reports them. Nothing is normalized.

| Framework | Counted as debt | Not counted | Effect on reported EBITDA |
| :--- | :--- | :--- | :--- |
| US GAAP (ASC 842) | Finance-lease liabilities | Operating-lease liabilities | After operating-lease cost |
| IFRS (IFRS 16) | All lease liabilities | — | Before all lease cost |

- **Each framework is consistent with itself.** A lease liability counts as debt exactly when its
  cost sits below EBITDA.
- **The two frameworks are not comparable with each other.** For the same leased assets, an IFRS
  filer shows higher EBITDA, higher EBIT and higher EV than a US GAAP filer. This affects
  EV/EBITDA, ROIC and interest coverage.
- **Invested capital** ([§7](#7-invested-capital)) uses net PP&E as reported. Right-of-use assets
  reported on their own line are not added, under either framework.
- **What the product does about it:** every result names its taxonomy. The side-by-side table
  shows it per row. The guides state the limitation.

## 7. Invested capital

Tangible capital employed:

**IC = net working capital + net PP&E**

- **Net working capital:** (current assets − cash − short-term investments) − (current liabilities
  − short-term borrowings − current portion of long-term debt).
- Goodwill and intangibles are excluded.
- Net PP&E is taken as reported; see [lease liabilities](#lease-liabilities) for right-of-use
  assets.
- **Critical inputs:** current assets, current liabilities, net PP&E and cash.
- Any ratio with IC ≤ 0 as its denominator is `not_applicable`.

## 8. Free cash flow and FCF yield

- **FCF:** the existing canonical definition, operating cash flow − capital expenditures (CapEx
  sign-normalized). Missing CapEx makes FCF `unavailable`.
- **FCF yield:** the existing FCF-Growth definition, latest completed fiscal-year FCF ÷ market cap
  × 100, reported in percent. Both FCF-Growth and the valuation strategy use this one calculation
  with the [§4](#4-market-capitalization) market cap. 3.5.2 supplies FCF-Growth's market-cap
  evidence; its formula does not change.

## 9. Ranking

The engine does not rank companies against each other. A ranking helper built in 3.5.2a and the ranked refresh view
planned for 3.5.6 were removed on 2026-11-02; ranking across companies belongs in a separate evaluator application
([A.16](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a16-strategy-set-revised-2026-11-02)).

## 10. Side-by-side refresh table

Built on the existing watchlist refresh, which already runs every enabled strategy for every
member and records one `refresh_id` on each run.

- **Rows and columns:** one row per ticker. Each strategy contributes its headline cells and outcome,
  the fiscal period end used, the taxonomy, and the run ID for drill-down.
- **Headline cells:** each strategy supplies one pure `headline` function over its decoded result, in the
  SWC behavior bundle. A cell is a fixed-order entry with a stable key, a label, a number or a text, an
  explicit unit and the metric's own status; the period end, the label that says what the period end is, and the
  taxonomy are fields of the whole headline.
  A strategy with no fiscal period (Momentum) has neither period end nor label and is left out of the table's
  period-ends block. A strategy that has a fiscal period but whose run recorded none (a Graham override, an
  FCF-Growth run with no span) shows "not recorded". The taxonomy line is left out of the text while no run
  records a taxonomy.
- **Build order:** the table is built first, over the four existing strategies; every new strategy
  supplies `headline` from its own slice. It needs nothing from the new data mappings or shared metrics.
- **One run per cell:** a refresh executes (ticker, selection) pairs, so the table requires at most
  one run per ticker and strategy. If the refresh holds more, the table refuses and names the
  duplicates. It never picks one silently.
- **Rebuilt from storage:** the table is recomputed from the persisted runs of one `refresh_id`,
  with no recalculation, provider access or clock reads.
- **Fiscal year-ends** that differ across members are displayed, not normalized.
- **Text layout:** the text table packs the strategies' column groups into bands, in `STRATEGIES` order, up to
  `TEXT_WIDTH` (120) characters, a named constant of `runs_compare.py` and not a command option. A band's width counts
  the Ticker column and the two-space gaps, and a group's width is measured as it is rendered, including its strategy
  name. A new band starts when the next group would make a line wider than 120. A group is never split or moved, and a
  group wider than 120 gets a band of its own. Each band repeats the Ticker column, the strategy-name row, the heading
  row and every ticker row in the same order, with one blank line between bands; the marker legend comes once, after the
  last band. A ticker's period-end entries and the list of runs that could not be read wrap at 120 as well, at an
  entry, and an entry wider than 120 is left whole. This holds at every strategy count. `--json` is unchanged.
- **No new persistence:** no batch ID, schema field or run type is added.
