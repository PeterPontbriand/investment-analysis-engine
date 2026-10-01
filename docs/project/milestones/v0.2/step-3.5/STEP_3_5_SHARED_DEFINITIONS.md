# Step 3.5 — Shared Definitions

Owns the definitions every Step 3.5 strategy shares: applicability, outcomes, data sources, the
shared metrics, the ranking helper, and the side-by-side refresh table. Per-strategy formulas live
in [Strategy specifications](STEP_3_5_STRATEGY_SPECIFICATIONS.md). Scope, sequencing and status
live in the [contract](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status).

Each shared metric is defined here once and used by every consumer. A strategy never carries its
own variant or fallback formula for any of them.

## 1. Applicability

Industry class comes from the SEC SIC code in the issuer's EDGAR submissions data, recorded in the
instrument profile (3.5.1). GICS is not used: it is proprietary and unavailable from the project's
sources.

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

When the SIC code is unknown, a sector-gated strategy's metrics are `unavailable` with a reason
code saying so.

## 2. Outcomes and reason codes

Every metric is a `MetricResult` (`src/core/metric_result.py`); no new status is introduced.

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
- A result-level summary (a score, a zone, a band) is a field of the strategy's own result type,
  not a new status.

## 3. Data sources, periods and point-in-time

- **Fundamentals:** SEC EDGAR XBRL annual filings only (10-K, 20-F, 40-F; us-gaap and ifrs-full),
  resolved through the existing financial-fact resolver. No other configured provider serves a
  historical `as_of` for fundamentals, so none is offered for these strategies.
- **Prices:** see [§4](#4-market-capitalization).
- **Periods:** fiscal-year filings only. A year-over-year test compares consecutive fiscal years
  of the same issuer.
- **Point-in-time:** a strategy uses the latest annual filing with a filing date on or before
  `context.effective_as_of`. Restatements follow the existing amendment-selection rules.

### Absent-component convention

These optional components are treated as zero when the filing reports no element for them, with
a diagnostic saying so:

- preferred stock;
- noncontrolling interest;
- short-term investments;
- long-term investments;
- each individual debt component (short-term borrowings, current portion of long-term debt,
  long-term debt, finance-lease liabilities).

The convention never applies to the critical inputs each definition below names. It is the only
case in which an absent element yields a number.

## 4. Market capitalization

**Market cap = common shares outstanding × price**

- **Shares:** the existing `COMMON_SHARES_OUTSTANDING` field from the selected filing.
- **Price:**
  - with a requested `as_of`: the unadjusted close on the last trading day on or before `as_of`,
    from the historical market-data boundary;
  - without one: the current quote, through the existing quote boundary and its freshness rules.
  A one-day historical download is never used as a quote.
- **Split adjustment:** if a split occurred between the share-count date and the price date, the
  share count is scaled by the split ratio.
- **Multiple share classes:** valued at the primary listing's price. This is a documented
  limitation.
- **Critical inputs:** shares and price.
- **Both dates stay visible** in the result: the share-count date and the price date.

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

- **Total debt:** short-term borrowings + current portion of long-term debt + long-term debt +
  finance-lease liabilities.
- **Operating-lease liabilities are always excluded.** This keeps EV consistent with EBITDA, which
  is already after operating-lease cost under ASC 842 and IFRS 16.
- **Critical inputs:** market cap and cash.

## 7. Invested capital

Greenblatt's tangible capital employed:

**IC = net working capital + net PP&E**

- **Net working capital:** (current assets − cash − short-term investments) − (current liabilities
  − short-term borrowings − current portion of long-term debt).
- Goodwill and intangibles are excluded.
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

1. **Deduplicate by issuer.** Two members with the same issuer key (share classes of one SEC
   filer) keep the first listed; the other is reported in a diagnostic.
2. **Determine the eligible set.** A member is eligible only if every requested metric has a value.
   Each excluded member is listed with its reason.
3. **Enforce a minimum universe.** With fewer than 10 eligible members, the helper returns no ranks,
   only the values and a diagnostic.
4. **Rank each metric.** Rank 1 is best. Tied values share the average (fractional) rank.
5. **Report a display percentile:** 100 × (N − rank) ÷ (N − 1). Higher is better.
6. **Aggregate.** The aggregate is the sum of per-metric ranks, with equal weights and no weights
   parameter. Final positions follow the ascending sum. Equal sums share a position and are listed
   in ticker order.

**Guarantees**

- The same input always produces the same output.
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
- **Not persisted:** the view is recomputed from the stored runs each time it is requested.

## 10. Side-by-side refresh table

Built on the existing watchlist refresh, which already runs every enabled strategy for every
member and records one `refresh_id` on each run.

- **Rows and columns:** one row per ticker. Each strategy contributes its headline values and
  outcome, the fiscal period end used, and the run ID for drill-down.
- **Rebuilt from storage:** the table is recomputed from the persisted runs of one `refresh_id`,
  with no recalculation, provider access or clock reads.
- **Fiscal year-ends** that differ across members are displayed, not normalized.
- **Ranking:** the table can sort by the [ranked refresh view](#ranked-refresh-view) for any strategy
  in the refresh.
- **No new persistence:** no batch ID, schema field or run type is added.
