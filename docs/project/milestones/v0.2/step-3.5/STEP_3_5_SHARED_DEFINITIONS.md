# Step 3.5 — Shared Definitions

Owns the definitions every Step 3.5 strategy shares: applicability, outcomes, data sources, the
shared metrics, the ranking helper, and the side-by-side refresh table. Per-strategy formulas live
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
| Beneish | Not applicable | Applicable | |
| Cash-Flow Valuation Multiples | Not applicable | Applicable | |
| Magic Formula | Not applicable | Not applicable | Greenblatt excludes both |
| Interest Coverage | Not applicable | Applicable | |
| ROIC | Not applicable | Applicable | |

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
  `nonpositive_denominator` is added by the first slice that produces it.
- No value is ever `NaN` or `Inf`. A ratio with a zero or non-positive denominator is `unavailable`
  or `not_applicable` with a reason code, as each definition below states.
- **What is not a `MetricResult`:** strategy-level scores, zones, bands, completeness and
  eligibility flags are typed fields of the strategy's own result. Ranks and percentiles belong to
  the ranked view. None of them is forced through `MetricResult`, and none is a new status. A
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
| Beneish M-Score | All eight indices computed and the score is `ok`. There is no partial score. | Any index cannot be computed, including DEPI with neither basis and TATA with discontinued operations and no continuing income, or an unknown industry class. | A financial issuer. |
| Cash-Flow Valuation Multiples | At least one of EV/EBITDA and FCF yield is `ok`. | Neither is `ok` and at least one is `unavailable`, or an unknown industry class. | A financial issuer, or both metrics `not_applicable`. |
| Interest Coverage | A band is assigned, including "no material interest expense". | Interest expense is not reported while total debt is positive, only net interest is reported, EBIT is missing, or an unknown industry class. | A financial issuer. |
| ROIC and Incremental ROIC | Trailing ROIC is `ok`; incremental ROIC's own availability is reported separately. | Trailing ROIC is `unavailable`, or an unknown industry class. | A financial issuer, or average invested capital not positive. |
| Greenblatt Magic Formula | Return on capital and earnings yield are both `ok`. | Either is `unavailable`, or an unknown industry class. | A financial issuer or a utility, or either metric `not_applicable` with neither `unavailable`. |

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

- **Anchor year:** year *t* is the newest completed fiscal year available at the boundary. If its
  inputs are missing, the affected metrics are `unavailable`. A strategy never steps back to an
  older year to produce a complete-looking result.
- **Actual dates decide:** periods are matched on their reported start and end dates. The
  Company Facts `fy` and `frame` labels describe the filing an observation appeared in, not the
  period it measures, and are never used to align years.
- **Annual durations:** the existing annual-duration tolerance applies, so 52- and 53-week years
  are consecutive. Quarters, year-to-date periods, and transition or stub years are rejected.
- **Balance-sheet values** are instants at a fiscal year-end, never durations. A metric that
  needs several year-ends requests each exact date and never reuses the newest one.
- **Comparatives:** prior-year values come from the anchor filing where it reports them. An earlier
  year-end it does not report (such as *t−2* total assets) may come from an earlier eligible
  filing, on the same taxonomy and currency. Every such value passes the same boundary check.
- **Conflicts:** two eligible values of equal priority that disagree make the input `unavailable`.
- **One basis:** a run never mixes us-gaap with ifrs-full, or two reporting currencies.

### Absent-component convention

These optional components are treated as zero when the filing reports no element for them, with
a diagnostic saying so:

- preferred stock;
- noncontrolling interest;
- short-term investments;
- long-term investments.

Filers do not tag a line they do not have, so for these items an absent element is the normal way
a filing says "none", and requiring an explicit zero would make EV unavailable for most issuers.

- **Equivalent concepts:** a field may map to a priority list of concepts where the evidence shows they are the same
  line item (receivables, short-term investments). The convention applies only when none of the listed
  concepts is tagged for the year-end. One issuer uses one concept for every year of a run, so a year the run's concept
  does not cover is absent, not zero. Alphabet (marketable securities) and Moderna (investments) tag
  short-term investments under other names than `ShortTermInvestments`; Walmart tags receivables as
  `ReceivablesNetCurrent`.
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
    before `as_of`, from the historical market-data boundary. The provider has no unadjusted close; the
    split-adjusted close and the split history together recover it. The dividend-adjusted series is never used for
    market cap;
  - without one: the current quote, through the existing quote boundary and its freshness rules.
  A one-day historical download is never used as a quote.
- **Split adjustment:** a cover-page count is scaled by every split whose ex-date is after the cover date, and a
  balance-sheet count by every split whose ex-date is after the filing date of the filing
  the count was taken from, up to the adjustment date of the price data. The accession and filing date are those in the
  count's own provenance; the anchor filing is not assumed, because a later filing's comparative restates an earlier
  year-end for splits up to that later filing's own date. A filing restates its share counts for a split effective before
  it is issued (SEC Staff Accounting Bulletin Topic 4.C), so such a split is already in the count and is not applied
  again. Stock dividends appear in the split history as fractional splits and are scaled the same way; they are not
  issuance.
- **Effect:** the market cap is the same as the one the unadjusted price and the unscaled count of the same date give. The
  formula and the value are unchanged; this states only how it is computed. Splits after `as_of` are used only to undo the
  provider's retroactive adjustment ([§3](#3-data-sources-periods-and-point-in-time)).
- **Availability, security unit and currency:** the market cap does not use the security-unit rule of Graham
  (`evaluate_security_unit_compatibility`): that rule refuses every run with `as_of`, every filer other than a us-gaap
  10-K filer, and any cover with more than one class title (Alphabet). The market cap is available only when all four
  hold:
  1. **The anchor annual filing is a 10-K or 10-K/A** (`incompatible_scope` otherwise). A 20-F or 40-F filer is a foreign private
     issuer whose US listing may be a depositary receipt at a ratio the structured data cannot show. SAP's market cap
     is therefore `unavailable`.
  2. **The quote currency equals the filing currency** (`incompatible_currency` otherwise). When either is unknown, the
     market cap is `unavailable`.
  3. **A listing check on the anchor 10-K's cover affirms the requested ticker.** The ticker must appear there under
     this CIK, on a registered title that is a share of the issuer. Class designations and "ordinary shares" are
     accepted; depositary shares, units, warrants and preferred securities are refused (`incompatible_units`); a
     missing or unreadable cover is `unavailable` (`missing_fact`). The check works with `as_of`, because the cover of
     a filing on or before the boundary is historical evidence.
  4. **The share-count rule for several classes below holds:** Alphabet's single combined count is valued at the
     requested ticker's price, and per-class counts with no total are `unavailable`.
- **Limitation, stated in the guides:** a ticker renamed after the anchor filing does not match the cover and is
  `unavailable`.
- **Critical inputs:** shares and price.
- **Dates stay visible** in the result: the share-count date, the filing date of the count's source and the price date.

### Share-count rule

- **One observation:** the count at fiscal year-end *t*, as the existing resolver returns it:
  reported directly, or as shares issued minus treasury shares at the same date. The share-count
  date is that fiscal year-end.
- **IFRS filers:** `ifrs-full:NumberOfSharesOutstanding` is a direct path. There is no IFRS
  issued-minus-treasury path: no IFRS treasury share count exists in the evidence.
- **Cover-page fallback:** when the balance-sheet paths give no count at year-end *t*, the cover-page count
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
  (Piotroski and Beneish use it).
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
  EV/EBITDA, earnings yield, return on capital, ROIC and interest coverage.
- **Invested capital** ([§7](#7-invested-capital)) uses net PP&E as reported. Right-of-use assets
  reported on their own line are not added, under either framework.
- **What the product does about it:** every result names its taxonomy. The ranked view and the
  side-by-side table show it per row, and a ranking whose members mix us-gaap and ifrs-full
  carries a diagnostic saying the members are not fully comparable. The guides state the
  limitation.

## 7. Invested capital

Greenblatt's tangible capital employed:

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

## 9. Ranking helper

A pure, analysis-agnostic function in `investment_analysis_engine/analysis/shared/ranking.py`. It knows nothing about
strategies, runs or persistence.

**Input**

- Members: each with a ticker, an issuer key (an opaque, non-empty string the caller supplies) and, per requested
  metric, a `MetricResult`. A result that is not `ok` excludes the member and carries its own reason code and
  reason into the exclusion.
- Metrics: each with a name and a direction (higher-is-better or lower-is-better).

**Behavior**

1. **Deduplicate by issuer.** When several members share an issuer key (share classes of one SEC
   filer), the member whose ticker sorts first alphabetically is kept and the others are reported
   in a diagnostic. The choice does not depend on input order, and the issuer stays in the
   ranking. The kept ticker is a canonical representative for ranking only. The diagnostic says so,
   and says the rule does not assert that the share classes are economically equivalent: their
   prices and rights can differ. Tickers are compared by ordinal order after upper-casing.
2. **Determine the eligible set,** after deduplication. A member is eligible only if every requested metric is `ok`.
   Each excluded member is listed with its reason. When the kept share class lacks a metric, the issuer is excluded
   even if another class has the value, and the diagnostic names both classes.
3. **Enforce a minimum universe.** With fewer than 10 eligible members, the helper returns no ranks,
   only the values and a diagnostic.
4. **Rank each metric.** Rank 1 is best. Tied values share the average (fractional) rank. Values and ranks are
   compared exactly, with no tolerance: ranks are multiples of one half.
5. **Report a display percentile:** 100 × (N − rank) ÷ (N − 1). Higher is better.
6. **Aggregate.** The aggregate is the sum of per-metric ranks, with equal weights and no weights
   parameter. Final positions follow the ascending sum.
7. **Assign positions** by competition ranking: equal sums share a position, and the next position
   skips the tied ones (1, 1, 3). Ticker order among tied members is display order only and
   carries no ranking meaning.

**Guarantees**

- The same members produce the same output in any input order.
- Values are never imputed.
- Every exclusion carries its reason.
- The universe is exactly the members passed in.

The minimum of 10 eligible members is a named, documented module constant of the helper
(`MINIMUM_ELIGIBLE_MEMBERS`), not a parameter and not a number buried in the calculation: no caller can lower it for
one ranking.

### Ranked refresh view

The ranked view (3.5.6) applies the helper to the persisted runs of one watchlist refresh:

- **Universe:** the refresh's runs of the selected strategy. The universe is always a watchlist;
  an ad-hoc ticker list is out of scope.
- **Time consistency:** every included run must share the same requested `as_of`. If the refresh
  mixes `as_of` values, the view refuses to rank and says why. Runs with no requested `as_of` rank
  together and the view shows the refresh's execution window.
- **One run per member:** the refresh must hold at most one run of the selected strategy per
  ticker. If it holds more (two configurations of one strategy), the view refuses to rank and names
  the duplicates.
- **Mixed frameworks:** members on different taxonomies are ranked together with the diagnostic
  [lease liabilities](#lease-liabilities) describes.
- **Not persisted:** the view is recomputed from the stored runs each time it is requested.

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
- **Ranking:** once the [ranked refresh view](#ranked-refresh-view) exists (3.5.6), the table can sort by
  it for any strategy in the refresh.
- **No new persistence:** no batch ID, schema field or run type is added.
