# Financial Math & Data Conventions

This document defines the deterministic financial formulas and data conventions used by the analysis strategies that Investment Analysis Engine currently implements.

It is not a catalogue of every financial indicator the project may someday support. Strategy-specific usage and interpretation live in the [Analysis Strategy Guides](strategies/README.md).

## Shared data conventions

### Data sources are capabilities, not interchangeable labels

Investment Analysis Engine uses different sources for different kinds of information:

- **SEC EDGAR** — completed annual company financial facts used by Graham and FCF/Earnings Growth. Reviewed US-GAAP duration concepts accept `10-K`/`20-F`/`40-F` annual forms; reviewed IFRS support is limited to exact diluted EPS, diluted weighted-average shares, operating cash flow, and physical-PP&E CapEx concepts.
- **Yahoo Finance data via [`yfinance`](https://ranaroussi.github.io/yfinance/)** — historical market prices for Momentum and current quote comparison for Graham where applicable. `yfinance` is an independent open-source library and is not affiliated with, endorsed by, or vetted by Yahoo.
- **AAA corporate-bond yield** — currently supplied explicitly by the user for Graham Growth Value; no automatic live series is integrated.

A source is used only for financial values whose meaning and time behavior are understood well enough for the selected calculation.

### Historical series and current quotes are different

A historical price series is an ordered set of observations used for time-series calculations. A current quote is a point-in-time market price used for comparison.

A provider that supplies a current quote does not automatically provide a historically valid quote for an earlier `as_of` date.

### Resolution and provenance

Where a strategy resolves financial facts, each required value follows the documented precedence:

```text
explicit override → valid cache → configured data provider → unavailable
```

Resolved financial values retain enough [provenance](GLOSSARY.md#provenance) to explain their source, measurement basis, relevant dates, and derivation.

### `as_of` and publication timing

A requested [`as_of`](GLOSSARY.md#as_of) date is a hard information boundary.

A company's fiscal year may end on December 31 while the corresponding filing is not published until weeks or months later. A historical analysis dated January 15 must not use a filing that did not become public until February.

This distinction helps prevent [look-ahead bias](GLOSSARY.md#look-ahead-bias).

### Missing data

Unknown or unavailable financial data does not silently become zero.

A calculation may instead report that:

- required data is unavailable;
- supplied data is invalid; or
- the method is not applicable to otherwise valid facts.

## Momentum Analysis Strategy

Momentum currently implements a deterministic simple-moving-average/crossover calculation.

### Inputs

The strategy uses:

- a short moving-average window;
- a long moving-average window; and
- an RSI lookback period; and
- historical closing prices.

The short window must be smaller than the long window.

### Simple moving average

For a window of `n` observations:

```text
SMA_t(n) = mean(P[t-n+1 : t])
```

The current implementation calculates:

```text
short_sma = rolling_mean(Close, short_window)
long_sma  = rolling_mean(Close, long_window)
signal    = 1 if short_sma > long_sma else 0
crossover = signal[t] - signal[t-1]
```

A crossover requires valid short and long SMAs at both `t` and `t-1`. At the first valid long-SMA observation, the current trend can be classified while crossover remains unavailable. Zero means no transition between two valid states.

RSI uses the simple mean of gains and losses over the configured number of price changes, not Wilder smoothing: `100 - 100 / (1 + mean_gain / mean_loss)`. Rising-only changes produce 100, falling-only changes produce 0, and an entirely flat window produces 50. A period of `n` requires at least `n+1` prices. Invalid observations are rejected in both fetched and preloaded frames; they are not dropped or filled.

Interpretation:

- `signal == 1` → short SMA above long SMA → bullish price-momentum state;
- otherwise → bearish state under the configured rule;
- positive crossover → transition into the bullish relationship;
- negative crossover → transition out of the bullish relationship;
- insufficient history → unavailable moving averages / unknown state rather than invented zeroes.

Machine-readable JSON uses `null` for unavailable numeric outputs rather than non-standard `NaN`.

Historical observations are truncated to `bar_timestamp <= as_of` before any metric is calculated. The short SMA, long SMA, and RSI use typed metric results: insufficient history produces `status = unavailable`, `reason_code = insufficient_history`, and no numeric value. The CLI exposes `--short-window`, `--long-window`, and `--rsi-period`.

See the [Momentum Analysis Strategy Guide](strategies/MOMENTUM.md).

## Graham Number Strategy

```text
maximum indicated price = sqrt(22.5 × EPS × BVPS)
```

The factor `22.5` combines the conventional limits:

```text
maximum P/E = 15
maximum P/B = 1.5
15 × 1.5 = 22.5
```

Because:

```text
P/E × P/B = price² / (EPS × BVPS)
```

solving the combined limit for price produces the square-root formula.

The output is a **maximum indicated price / screening ceiling** based on earnings and book value. It is not a complete defensive-investor qualification and is not presented as an unquestionable intrinsic value.

### Earnings convention

The standard Graham Number basis is a three-year average of completed fiscal-year diluted EPS:

```text
three-year-average EPS =
    (fiscal EPS 1 + fiscal EPS 2 + fiscal EPS 3) / 3
```

The three observations must be compatible in financial meaning/share basis and must have been available by the requested historical boundary.

Compatibility requires the same provider concept, diluted/basic basis, currency, units, and fiscal basis across distinct fiscal years. Provider-exposed share-class and split-treatment evidence must agree. Ambiguous restatements or compatibility gaps make the series unavailable rather than triggering a guessed normalization.

The Graham Number has no other EPS basis: it always uses the three-year average, and a trailing-twelve-month EPS is not offered.

### Book value per common share

```text
BVPS = common shareholders' equity / period-end common shares outstanding
```

A provider-reported BVPS is usable only when its definition is understood. Investment Analysis Engine's SEC calculation derives fiscal-year-end BVPS from compatible accounting evidence when a safe direct value is unavailable.

Tangible BVPS is a different measure and is not silently substituted.

### Applicability

Positive EPS and BVPS are required for the Graham Number. Non-positive EPS or BVPS means the method is not applicable rather than producing a zero or complex-number valuation.

### Price comparison

See [Reference-value price comparison](#reference-value-price-comparison) — the Graham Number is one such reference value.

See the [Graham Number Strategy Guide](strategies/GRAHAM_NUMBER.md).

## Graham Growth Value Strategy

```text
growth value = normalized EPS
    × (base P/E + growth multiplier × g)
    × baseline AAA yield / current AAA yield
```

Current conventional constants:

```text
base P/E = 8.5
growth multiplier = 2.0
baseline AAA yield = 4.4
```

Where:

- `normalized EPS` is the earnings value supplied on an explicitly documented basis;
- `g` is expected annual growth in **percentage points** (`6.5` means 6.5%, not `0.065`);
- `baseline AAA yield` is a historical formula constant, also in percentage points; and
- `current AAA yield` is the user-supplied current AAA corporate-bond yield, in percentage points.

This is a forecast-dependent growth-stock estimate. It is not the Graham Number.

### EPS basis

- Graham Number always uses three-year-average diluted EPS; it has no EPS-basis option.
- Graham Growth uses three-year-average diluted EPS by default, for every provider. The production tool boundary also supports an explicit single completed fiscal-year EPS basis for reviewed workflows.

An unsupported basis is rejected rather than silently transformed into a different calculation.

SEC IFRS support does not include BVPS or preferred-zero inference. Filing
per-share values are compared with quotes only when ordinary-share 1:1 unit
evidence and matching currencies are affirmative. ADR/ADS and currency
conversion are not performed.

### Expected growth

The user supplies expected growth explicitly. The software and AI model do not invent, infer, clip, cap, floor, or silently annualize that forecast.

### AAA yield

No automatic current AAA-yield data source is integrated at present. The user therefore supplies the current AAA corporate-bond yield explicitly.

Both baseline and current yields must be strictly positive.

### Price comparison

See [Reference-value price comparison](#reference-value-price-comparison) — the Graham Growth Value estimate is one such reference value.

See the [Graham Growth Value Strategy Guide](strategies/GRAHAM_GROWTH.md).

## Reference-value price comparison

This section applies to every strategy that compares a calculated reference value against a current market price — the Graham Number and Graham Growth Value today.

A compatible current market price is optional to either formula itself.

Automatic share-unit verification currently covers only a single positively
identified ordinary common-stock class in SEC domestic US-GAAP `10-K` evidence
for current requests. It checks original source values and contexts without
replacing the financial inputs or changing the formula. Matching the sole
registered common class to entity-wide common-share inputs supports the 1:1
unit inference; an equity classification alone does not. Missing, contradictory,
or unsupported evidence suppresses only the comparison with an explicit reason.
See the [Graham Number guide](strategies/GRAHAM_NUMBER.md#current-price-comparison) or the
[Graham Growth Value guide](strategies/GRAHAM_GROWTH.md#current-price-comparison) for scope,
timing limitations, and legacy-cache handling.

When both a reference value and current price are available:

```text
margin_of_safety_percent =
    (reference_value - current_price)
    / reference_value
    × 100
```

Interpretation:

- positive → current price is below the selected reference value;
- zero → current price equals the reference value;
- negative → current price exceeds the reference value.

The concise investor report describes this as a **price relationship** (for example, “25.00% below the Graham Number”) rather than requiring a reader to interpret an internal sign convention.

The relationship is to the latest available quote response, whose retrieval age is bounded independently from annual financial-fact age. The default maximum reuse age is 300 seconds, including equality; zero disables quote cache reuse. Missing or future retrieval times cannot establish eligibility. Yahoo retrieval time is not treated as an exchange observation or publication timestamp. User price overrides remain explicitly unverified assumptions.

If a current quote is unavailable, the Graham calculation can still remain valid while the price comparison is omitted.

An invalid explicit quote override is instead a fatal input error. An override may omit currency; a provider quote may not. Provider quotes without verified currency are classified as unavailable. A known cross-currency quote remains visible, but its price relationship is suppressed.

A quote in a different currency is not used for a price relationship without an approved currency-conversion mechanism.

## Mathematical validation

NaN, infinity, and mathematically invalid configuration values are rejected deterministically.

Investment Analysis Engine does not impose arbitrary financial-domain cutoffs merely because a number “looks unusual.” A non-mathematical bound requires an explicit rationale.

See the [Graham Valuation Strategies overview](strategies/GRAHAM.md).

## Free Cash Flow & Earnings Growth Strategy

This strategy compares a company with its own completed annual history. It reports total-company free cash flow, free cash flow per diluted share, and diluted EPS growth over one compatible, contiguous span.

### Annual measures

For each eligible completed fiscal year:

```text
free_cash_flow = operating_cash_flow - normalized_capital_expenditures

free_cash_flow_per_diluted_share =
    free_cash_flow / weighted_average_diluted_shares
```

Operating cash flow is net cash provided by operating activities. Capital expenditures are normalized to a positive expenditure amount before subtraction because providers may report cash outflows with different sign conventions. The normalization and original provider field remain in provenance.

Weighted-average diluted shares must be positive and compatible with the same completed fiscal year. Ending shares outstanding are not silently substituted. A provider's precomputed “free cash flow” is not accepted merely because its label matches; the strategy derives FCF from its resolved components.

### Historical horizon

The automatic `longest_available` policy prefers 5 elapsed years, then 4, then 3. An `N`-year CAGR requires `N + 1` contiguous annual observations:

| Elapsed years | Annual observations |
|---:|---:|
| 5 | 6 |
| 4 | 5 |
| 3 | 4 |

An explicitly requested horizon is strict and never falls back. Facts must also satisfy the analysis `as_of` boundary: a period ending before the boundary is not eligible if its filing became available afterward.

### Compound annual growth

For positive endpoints separated by `N` elapsed years:

```text
cagr_percent = ((ending_value / beginning_value) ** (1 / N) - 1) * 100
```

The beginning and ending values must be strictly positive, and the annual series must be contiguous. Zero or negative endpoints and sign changes make CAGR nonmeaningful under this policy. The raw history remains available, but the metric is unavailable with a reason; the calculation does not apply absolute values or manufacture “growth from loss.”

Both total-company-FCF CAGR and FCF-per-diluted-share CAGR are returned. Total-company FCF controls classification by default. The explicit `fcf_per_share` policy makes per-share FCF controlling; presentation does not infer or change that choice.

### Classification

The selected policy returns:

- `PASS` when the controlling FCF CAGR and diluted-EPS CAGR are meaningful and greater than zero, and any selected forward hard gate is satisfied;
- `FAIL` when required metrics are meaningful and at least one required growth rate is zero or negative; or
- `INDETERMINATE` when required evidence is missing, incompatible, non-contiguous, or mathematically nonmeaningful.

Classification is separate from software execution status. `INDETERMINATE` is not equivalent to financial failure.

### Optional FCF yield

When compatible market-capitalization evidence is available:

```text
fcf_yield_percent =
    latest_completed_fiscal_year_fcf / current_market_capitalization * 100
```

The numerator is annual while the denominator is current, so both dates must remain visible. FCF yield is informational only and has no pass threshold in the current method version.

### Optional forward EPS evidence

Compatible analyst-consensus diluted EPS for FY1 and FY2 may provide two implied growth intervals: latest actual to FY1 and FY1 to FY2. Each prior value must be positive for the corresponding growth rate to be meaningful.

The `display_only` and `confirmation` policies do not change the historical classification. Under `hard_gate`, both intervals must be available and positive for `PASS`; missing required forward evidence produces `INDETERMINATE`. The current production SEC mapping may not supply analyst consensus, and the software does not generate estimates to fill that gap.

See the [Free Cash Flow & Earnings Growth Strategy Guide](strategies/FCF_GROWTH.md).

## Shared metrics

These metrics are defined once and used by every strategy that needs them. Each is a pure calculation over resolved inputs; every result is a typed outcome that is either `ok` with a finite number or `unavailable` with a reason code and a reason. Nothing missing becomes zero, neutral or `NaN`, except the absent components named below. Balance-sheet values are instants at the anchor fiscal year-end *t*; annual values are those of the fiscal year ending at *t*. Free cash flow and the FCF yield keep their entries under [Free Cash Flow & Earnings Growth Strategy](#free-cash-flow--earnings-growth-strategy).

### Market capitalization

```text
market_cap = scaled_share_count * price
scaled_share_count = share_count * product of the ratios of every split with
                     after < ex_date <= adjustment_date
```

- **Share count:** the common shares outstanding at fiscal year-end *t*, reported directly or as shares issued minus treasury shares at the same date. When no balance-sheet path gives a count at *t*, the single non-dimensional cover-page count of the anchor filing is used and the result says so. A year-end count dated other than *t* (an older year's count) is `unavailable` with `incompatible_period` and is never substituted. Conflicting counts, and per-class counts with no total, are `unavailable`. One combined count for several share classes is valued at the requested ticker's price.
- **Price:** the split-adjusted close, without dividend adjustment, on the last trading day on or before the boundary.
- **Split scaling:** `after` is the filing date of the filing a year-end count was taken from, or the date of the cover page for a cover-page count, and `adjustment_date` is the date up to which the provider adjusted the price. A filing restates its counts for a split effective before it is issued, so such a split is not applied again. A split after the boundary still scales the count, because it undoes the provider's adjustment of the price; it never changes the market cap at the boundary.
- **Availability:** market cap is available only when all four hold, and each refusal has its reason code.
  1. The anchor annual filing is a 10-K or a 10-K/A (`incompatible_scope`). A 20-F or 40-F filer, or an amendment of either, is a foreign private issuer whose US listing may be a depositary receipt at a ratio the structured data cannot show.
  2. The quote currency equals the filing currency (`incompatible_currency`). When either is unknown, market cap is `unavailable`.
  3. A listing check on the anchor 10-K's cover affirms the requested ticker, under the issuer's CIK, on a registered title that is a share of the issuer. A depositary share, unit, warrant or preferred security is refused (`incompatible_units`), and a missing or unreadable cover is `unavailable` (`missing_fact`).
  4. A share count and a price are present (the code of the missing input).
- **Limitations:** buybacks and issuance between the fiscal year-end and the price date are not reflected. A split announced before the filing but effective just after it is assumed not to be reflected in the filing. A ticker renamed after the anchor filing does not match the cover and is `unavailable`.
- **Critical inputs:** the share count and the price.

### Gross profit, EBIT, depreciation and amortization, EBITDA

```text
gross_profit = reported gross profit, else sales - cost_of_revenue (both reported)
EBIT         = reported operating income            (may be negative)
D&A          = depreciation, depletion and amortization of the cash-flow statement
EBITDA       = EBIT + D&A
```

Gross profit is never taken from operating income; a filer that reports neither form has none. EBIT is never rebuilt from pretax income plus interest. When EBIT or D&A is missing, EBITDA is `unavailable` with `missing_fact`. Critical inputs: operating income (EBIT), D&A (EBITDA), and for gross profit either the reported figure or both sales and cost of revenue.

### Total debt

```text
total_debt = short_term_borrowings + current_portion_of_long_term_debt
           + noncurrent_long_term_debt + lease_liabilities_counted_as_debt
```

A missing debt figure is not assumed to be zero. An absent component counts as zero, with a diagnostic, only with supporting evidence:

| What the filing reports for the year-end | Treatment |
| :--- | :--- |
| At least one debt component | An absent component is zero only when no concept is tagged for it (`not_tagged`) and none of its recorded related concepts is tagged at that date. Otherwise total debt is `unavailable`: `debt_not_visible` when a related concept is tagged, `unsupported_mapping` when the mapping is unsupported, and the absence's own code otherwise. |
| No component, no related concept, no unsupported mapping, and interest expense absent or zero | Total debt is zero ("no reported debt"). |
| No component, but a related concept is tagged or interest expense is not zero | `unavailable` with `debt_not_visible`. |
| No component, and a mapping is unsupported | `unavailable` with `unsupported_mapping`, which takes precedence. |

The direct long-term-debt total only reconciles. When it is present, each of the current portion and the noncurrent long-term debt that is absent as `not_tagged` with no related concept counts as zero, and the two must equal the total exactly, with no tolerance. A mismatch makes total debt `unavailable`: with `ambiguous_fact` when at least one part is present, both parts being the affected components, and with `debt_not_visible` when neither is. A part absent for any other reason, or with a related concept, keeps its own outcome. This check comes before the other component rules, so a filer that tags only the direct total never has zero debt. The direct total is never added to its parts and never used as a value. An IFRS issuer's total debt is `unavailable` with `unsupported_mapping` while the IFRS noncurrent long-term debt mapping is unsupported.

### Enterprise value

```text
EV = market_cap + total_debt + preferred_stock + noncontrolling_interest
     - cash_and_equivalents - short_term_investments
```

The critical inputs are market cap, total debt and cash. Preferred stock, noncontrolling interest and short-term investments are zero, with a diagnostic, only when the filing tags no concept for them (`not_tagged`), never when the mapping is unsupported or another concept is tagged. Short-term investments are zero only when current assets are tagged at the year-end: on an unclassified balance sheet (Deere's) a missing line does not show that the filer has none, so EV is `unavailable`. A negative EV is a valid number.

### Invested capital

```text
IC = (current_assets - cash - short_term_investments)
   - (current_liabilities - short_term_borrowings - current_portion_of_long_term_debt)
   + net_ppe
```

The critical inputs are current assets, current liabilities, net PP&E and cash. Short-term investments are zero when `not_tagged`. Short-term borrowings and the current portion of long-term debt follow the debt-component rule of total debt. Net PP&E is taken as reported, and goodwill and intangibles are excluded. An IC at or below zero is an `ok` value; a ratio that divides by it decides what that means.

## Cross-sectional ranking

A ranking orders a fixed set of members, such as the tickers of one watchlist refresh, over one or more metrics. It is a pure calculation over the members it is given: it reads no market, assumes no wider universe and imputes no value. Each metric has a direction, higher is better or lower is better.

### Eligibility

1. **One member per issuer.** Members that share an issuer key (share classes of one filer) are reduced to the one whose ticker sorts first, after upper-casing, in ordinal character order. That ticker is a canonical representative for ranking only; the rule does not assert that the share classes are economically equivalent, since their prices and rights can differ. The other tickers are listed in a diagnostic.
2. **Every metric must have a value.** A member is eligible only if each requested metric is `ok` with a finite value. A member with any metric `unavailable` or `not_applicable` is excluded, and the exclusion lists each such metric with its reason code and reason. This is judged after step 1: when the kept share class lacks a value that another class has, the issuer is excluded, and the diagnostic names both classes. Values are never taken from another class.
3. **A minimum universe.** With fewer than 10 eligible members, nothing is ranked. The result carries the eligible members' values, the exclusions and a diagnostic, and no ranks, percentiles or positions. The minimum is fixed, not an option.

### Ranks, percentile, sum and position

With `N` eligible members:

```text
rank              1 is best; equal values share the average of the ranks they span
                  (two values tied for first both have rank 1.5)
percentile        100 * (N - rank) / (N - 1)        rank 1 gives 100, rank N gives 0
rank_sum          the sum of a member's ranks over the metrics, with equal weights
position          competition ranking of the ascending rank sum: equal sums share a
                  position and the next position skips the tied ones (1, 1, 3)
```

The percentile is for display and is not used to order members. Values are compared exactly, with no tolerance. Members are listed by position, then ticker; ticker order carries no ranking meaning. The same members give the same result in any input order.

## Source notes

- Benjamin Graham, *The Intelligent Investor*, Chapter 14: defensive-investor limits on price relative to average earnings and book value, including the combined product limit of 22.5.
- Benjamin Graham, *The Intelligent Investor*, Chapter 11: simplified growth-stock formula and cautions about the reliability of projected growth.
- Federal Reserve Bank of St. Louis FRED, [Moody's Seasoned Aaa Corporate Bond Yield (AAA)](https://fred.stlouisfed.org/series/AAA): useful background on a defined AAA corporate-bond-yield series; Investment Analysis Engine does not currently retrieve it automatically.

Secondary calculators or articles may illustrate common modern usage, but they do not override the formula, input, provenance, and naming conventions documented here.
