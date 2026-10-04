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

Every calculated numeric metric is a `MetricResult` (`src/core/metric_result.py`); no new status is
introduced.

| Situation | `MetricStatus` |
| :--- | :--- |
| Computed | `ok`, with a finite value |
| A required input is missing, ambiguous or not available as of the boundary | `unavailable` |
| The strategy does not apply to the issuer's industry class | `not_applicable` |
| The inputs are valid but the value has no economic meaning (for example, EV/EBITDA with negative EBITDA) | `not_applicable` |

- Each non-`ok` result carries a `ReasonCode`. Existing codes are reused where one fits; 3.5.1 adds
  the codes no existing one covers, such as sector applicability and unknown SIC.
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
band, zone or score, and it is what the strategy's native-status function returns and what its execution
adapter maps to the workspace outcome (`ok` is completed, `not_applicable` is not applicable,
`input_unavailable` is unavailable). No strategy reports a missing status because of how many numbers it
displays. A calculation that cannot run for a reason outside the inputs raises, as today; it is not a
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
the table adds no formula, threshold or classification. Momentum's analyzer has no status and its native
status stays `None`.

## 3. Data sources, periods and point-in-time

- **Fundamentals:** SEC EDGAR XBRL annual filings only (10-K, 20-F, 40-F; us-gaap and ifrs-full),
  resolved through the existing financial-fact resolver. No other configured provider serves a
  historical `as_of` for fundamentals, so none is offered for these strategies.
- **Prices:** see [§4](#4-market-capitalization).
- **Periods:** fiscal-year filings only. A year-over-year test compares consecutive fiscal years
  of the same issuer.
- **Point-in-time:** a strategy uses the latest annual filing with a filing date on or before
  `context.effective_as_of`. Restatements follow the existing amendment-selection rules.

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

The convention never applies to the critical inputs each definition below names. Debt is not
covered by it: [total debt](#total-debt) has its own, stricter rule. These two are the only cases
in which an absent element yields a number.

## 4. Market capitalization

**Market cap = common shares outstanding × price**

- **Shares:** the existing `COMMON_SHARES_OUTSTANDING` field: common shares outstanding on the
  balance sheet at fiscal year-end *t* of the selected filing. See
  [share-count rule](#share-count-rule).
- **Price:**
  - with a requested `as_of`: the unadjusted close on the last trading day on or before `as_of`,
    from the historical market-data boundary;
  - without one: the current quote, through the existing quote boundary and its freshness rules.
  A one-day historical download is never used as a quote.
- **Split adjustment:** if a split occurred between the share-count date and the price date, the
  share count is scaled by the split ratio.
- **Critical inputs:** shares and price.
- **Both dates stay visible** in the result: the share-count date and the price date.

### Share-count rule

- **One observation:** the count at fiscal year-end *t*, as the existing resolver returns it:
  reported directly, or as shares issued minus treasury shares at the same date. The share-count
  date is that fiscal year-end.
- **Not the cover page.** The later cover-page count is never used, even though it is closer to
  the price date. It is not a balance-sheet fact, and filers with several classes report it per
  class.
- **No count at year-end *t*:** market cap is `unavailable`. An older year's count is never
  substituted.
- **Conflicting counts** for the same date make market cap `unavailable`
  ([§3](#period-alignment)).
- **Several share classes:** when the filer reports counts per class and no unambiguous total,
  market cap is `unavailable`. Where one total is reported, it is valued at the requested ticker's
  price.
- **Limitation, stated in the guides:** buybacks and issuance between the fiscal year-end and the
  price date are not reflected.

## 5. EBIT, D&A and EBITDA

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
| At least one mapped debt concept | Each absent component is zero, with a diagnostic. The filer demonstrably tags its debt. |
| No mapped debt concept, and interest expense is absent or zero | Total debt is zero ("no reported debt"), with a diagnostic. |
| No mapped debt concept, but interest expense is positive | Total debt is `unavailable`: the issuer has debt the mapping does not see. |

- **Direct totals:** where a filer reports both a direct long-term-debt total and its current and
  noncurrent parts, they must reconcile, and the total is never added to its parts. A mismatch
  makes the affected component `unavailable`.
- **Short-term borrowings are not current maturities.** Commercial paper and similar borrowings
  are their own component and never stand in for the current portion of long-term debt.
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

A pure, analysis-agnostic function in `src/analysis/shared/ranking.py`. It knows nothing about
strategies, runs or persistence.

**Input**

- Members: each with an issuer key and, per requested metric, either a finite value or an
  unavailable reason.
- Metrics: each with a name and a direction (higher-is-better or lower-is-better).

**Behavior**

1. **Deduplicate by issuer.** When several members share an issuer key (share classes of one SEC
   filer), the member whose ticker sorts first alphabetically is kept and the others are reported
   in a diagnostic. The choice does not depend on input order, and the issuer stays in the
   ranking. The kept ticker is a canonical representative for ranking only. The diagnostic says so,
   and says the rule does not assert that the share classes are economically equivalent: their
   prices and rights can differ.
2. **Determine the eligible set.** A member is eligible only if every requested metric has a value.
   Each excluded member is listed with its reason.
3. **Enforce a minimum universe.** With fewer than 10 eligible members, the helper returns no ranks,
   only the values and a diagnostic.
4. **Rank each metric.** Rank 1 is best. Tied values share the average (fractional) rank.
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

The minimum of 10 eligible members is a named, documented default, not a constant buried in the
calculation.

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
  explicit unit and the metric's own status; the period end and taxonomy are fields of the whole headline.
  A strategy with no fiscal period or no filing taxonomy (Momentum) shows "not recorded" for them.
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
