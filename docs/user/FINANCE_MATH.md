# Financial Math & Data Conventions

This document defines the deterministic financial formulas and data conventions used by the analysis strategies that Investment Analysis Engine currently implements.

It is not a catalogue of every financial indicator the project may someday support. Strategy-specific usage and interpretation live in each strategy's guide.

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

A requested [`as_of`](GLOSSARY.md#as-of-date) date is a hard information boundary.

A company's fiscal year may end on December 31 while the corresponding filing is not published until weeks or months later. A historical analysis dated January 15 must not use a filing that did not become public until February.

This distinction helps prevent [look-ahead bias](GLOSSARY.md#look-ahead-bias).

### Missing data

Unknown or unavailable financial data does not silently become zero.

A calculation may instead report that:

- required data is unavailable;
- supplied data is invalid; or
- the method is not applicable to otherwise valid facts.

## Momentum Strategy

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

Historical observations are truncated to `bar_timestamp <= as_of` before any metric is calculated. The short SMA, long SMA, and RSI use typed metric results: insufficient history produces `status = unavailable`, `reason_code = insufficient_history`, and no numeric value. The short window, the long window and the RSI period are each configurable.

See the [Momentum Strategy Guide](strategies/MOMENTUM.md).

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

See the [Graham Number Strategy Guide](strategies/GRAHAM_NUMBER.md) and the [Graham Growth Value Strategy Guide](strategies/GRAHAM_GROWTH.md).

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

When [market capitalization at the boundary](#market-capitalization) is available:

```text
fcf_yield_percent =
    latest_completed_fiscal_year_fcf / market_capitalization_at_the_boundary * 100
```

The numerator is annual and the denominator is the market capitalization at the boundary, so both dates remain visible. The yield is computed only when the latest completed fiscal year ends at the anchor filing's fiscal year-end *t*, which the market capitalization is also taken at; otherwise it is `unavailable` with `incompatible_period`, and an older year is never used. When market capitalization is `unavailable`, the yield is `unavailable` with its reason code, and a market-data failure makes it `unavailable` with `provider_error`. FCF yield is informational only and has no pass threshold in the current method version.

### Optional forward EPS evidence

Compatible analyst-consensus diluted EPS for FY1 and FY2 may provide two implied growth intervals: latest actual to FY1 and FY1 to FY2. Each prior value must be positive for the corresponding growth rate to be meaningful.

The `display_only` and `confirmation` policies do not change the historical classification. Under `hard_gate`, both intervals must be available and positive for `PASS`; missing required forward evidence produces `INDETERMINATE`. The current production SEC mapping may not supply analyst consensus, and the software does not generate estimates to fill that gap.

See the [Free Cash Flow & Earnings Growth Strategy Guide](strategies/FCF_GROWTH.md).

## Piotroski F-Score Strategy

This implementation follows the Piotroski nine-test structure but substitutes the net change in split-adjusted shares outstanding for the original equity-issuance signal, because issuance cannot be established reliably from structured filings.

The strategy runs nine pass/fail tests on one company's reported statements at three consecutive fiscal year-ends and counts the tests passed. Year *t* is the fiscal year of the anchor annual filing, the latest at the boundary; *t−1* is the day before the start of the completed annual period that ends at *t*, and *t−2* is derived the same way from the period that ends at *t−1*. A year-end is never taken from a filing date, and an older year is never scored in place of *t*.

### The nine tests

```text
1  net_income(t) / total_assets(t-1) > 0
2  operating_cash_flow(t) / total_assets(t-1) > 0
3  net_income(t) / total_assets(t-1) > net_income(t-1) / total_assets(t-2)
4  operating_cash_flow(t) > net_income(t)
5  long_term_debt(t) / average(total_assets(t), total_assets(t-1))
       < long_term_debt(t-1) / average(total_assets(t-1), total_assets(t-2)),
   or long_term_debt is zero in both years
6  current_assets(t) / current_liabilities(t) > current_assets(t-1) / current_liabilities(t-1)
7  shares_outstanding(t) <= shares_outstanding(t-1)
8  gross_profit(t) / sales(t) > gross_profit(t-1) / sales(t-1)
9  sales(t) / total_assets(t-1) > sales(t-1) / total_assets(t-2)
```

Comparisons are strict and made on unrounded values with no tolerance: each operand is converted to an exact fraction, so an unchanged ratio earns no point. The two exceptions are test 5's zero-debt case and test 7, where an unchanged share count passes. A reported ratio is the float nearest the exact value.

### Conventions fixed by the method

None of these is a user option.

- **Income** is net income as reported. The paper uses income before extraordinary items; US GAAP removed extraordinary items in 2015, so net income is the modern equivalent. Income from continuing operations is not used, because many filers never report it.
- **Turnover** uses beginning-of-year total assets, following the paper's method text.
- **Long-term debt** is the current portion of long-term debt plus the noncurrent long-term debt, decided by the rules of [Total debt](#total-debt). Short-term borrowings and lease liabilities are excluded except that they count as a debt concept present at the date. Long-term debt is unavailable where the mapping is unsupported, as for every IFRS filer.
- **Zero debt:** a company with no long-term debt in either year passes test 5 whatever its assets, so a missing *t−2* total assets does not make the test unavailable in that case.
- **Dilution** compares the split-adjusted common share counts at *t* and *t−1* instead of the paper's equity-issuance test. Issuance proceeds include option exercises, which would fail nearly every issuer, and issuance evidence is unreliable in structured filings. The counts are compared only when both come from the same filing, which puts them on one split basis because a filing restates its counts for splits effective before it is issued, and when both come by the same path (reported directly, or issued less treasury shares). A *t−1* count from another filing, or a direct count with a derived one, makes the test unavailable (`ambiguous_fact`). The test has no price and needs no market data. It measures net dilution: a company can issue shares and still pass when buybacks exceed issuance.

### Outcomes and the score

Each test is `pass`, `fail` or `unavailable`, with its ratios, operands and provenance. A test is unavailable when an operand is missing, when the currencies of its monetary operands differ (`incompatible_currency`), when its operands mix us-gaap and ifrs-full (`incompatible_scope`), or when a denominator is not positive (`nonpositive_denominator`); an unavailable test is never a fail. Total assets, sales and current liabilities must be positive wherever they are a denominator.

| Tests available | Score | Completeness |
|---|---|---|
| 9 | `ok`, the number passed | complete |
| 6 to 8 | `ok`, the number passed, shown as "*x* of *n*" | partial |
| Fewer than 6 | `unavailable` with `insufficient_tests` | none |

A partial score is always shown as "*x* of *n*" with the unavailable tests named. The usual reading of high and low scores applies to complete scores only, and a partial score never enters a ranking. If year *t−1* or *t−2* is unavailable, every operand of that year carries the reason, so the result always holds nine tests.

### Execution status and applicability

The status is `ok` for a complete or partial score, `input_unavailable` below six available tests, `provider_error` after a provider failure while the inputs were assembled (the result then holds the failure and no tests), and `not_applicable` for a provider-confirmed ETF. A financial issuer is applicable with a warning, because the gross-margin and current-ratio tests are typically unavailable for it. The industry class is that of the SIC code on the anchor filing, as filed; an unknown class runs and says so.

The result records one taxonomy, us-gaap or ifrs-full, only when every resolved operand states the same one; otherwise it records none.

See the [Piotroski F-Score Strategy Guide](strategies/PIOTROSKI.md).

## Shared metrics

These metrics are defined once and used by every strategy that needs them. Each is a pure calculation over resolved inputs; every result is a typed outcome that is either `ok` with a finite number or `unavailable` with a reason code and a reason. Nothing missing becomes zero, neutral or `NaN`, except the absent components named below. Balance-sheet values are instants at the anchor fiscal year-end *t*; annual values are those of the fiscal year ending at *t*. Free cash flow and the FCF yield keep their entries under [Free Cash Flow & Earnings Growth Strategy](#free-cash-flow--earnings-growth-strategy).

### Market capitalization

```text
market_cap = scaled_share_count * price
scaled_share_count = share_count * product of the ratios of the provider split adjustments
                     of the two windows below, with after < ex_date <= adjustment_date
```

- **Share count:** the common shares outstanding at fiscal year-end *t*, reported directly or as shares issued minus treasury shares at the same date. When no balance-sheet path gives a count at *t*, the single non-dimensional cover-page count of the anchor filing is used and the result says so. A year-end count dated other than *t* (an older year's count) is `unavailable` with `incompatible_period` and is never substituted. Conflicting counts, and per-class counts with no total, are `unavailable`. One combined count for several share classes is valued at the requested ticker's price.
- **Price:** the split-adjusted close, without dividend adjustment, on the last trading day on or before the boundary.
- **Provider split adjustments:** `after` is the filing date of the filing a year-end count was taken from, or the date of the cover page for a cover-page count, and `adjustment_date` is the date up to which the provider adjusted the price. The provider's split history reports splits and other adjustments alike (a spin-off appears as a ratio such as 0.9535), and only a split changes the share count, so the events apply in two windows. An event after the price date is always applied, whatever its ratio: it undoes the provider's adjustment of the historical close and never changes the market cap at the boundary. An event after `after` and not after the price date is applied only when its ratio is a recognizable split ratio: *p*-for-*q* with *p* in 2 to 10, 15, 20, 25, 30, 40, 50 or 100, *q* in 1 to 4 and *p* greater than *q*, or the reciprocal of one. Any other ratio, such as a spin-off or a stock dividend of 1.05, makes market cap `unavailable` with `ambiguous_fact`, naming the event. Without an as-of date the price date is the quote's date, so every event after the count's date is in the second window. A filing restates its counts for a split effective before it is issued, so such a split is not applied again.
- **Availability:** market cap is available only when all four hold, and each refusal has its reason code.
  1. The anchor annual filing is a 10-K or a 10-K/A (`incompatible_scope`). A 20-F or 40-F filer, or an amendment of either, is a foreign private issuer whose US listing may be a depositary receipt at a ratio the structured data cannot show.
  2. The quote currency equals the filing currency (`incompatible_currency`). When either is unknown, market cap is `unavailable`.
  3. A listing check on the anchor 10-K's cover affirms the requested ticker, under the issuer's CIK, on a registered title that is a share of the issuer. A depositary share, unit, warrant or preferred security is refused (`incompatible_units`), and a missing or unreadable cover is `unavailable` (`missing_fact`).
  4. A share count and a price are present (the code of the missing input).
- **Limitations:** buybacks and issuance between the fiscal year-end and the price date are not reflected. A split announced before the filing but effective just after it is assumed not to be reflected in the filing. A spin-off or stock dividend between the count and the price makes market cap unavailable. A ticker renamed after the anchor filing does not match the cover and is `unavailable`.
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

### Long-term debt

```text
long_term_debt = current_portion_of_long_term_debt + noncurrent_long_term_debt
```

Long-term debt follows the rules of total debt, applied to its two parts. The direct long-term-debt total is reconciled with the two parts first, with the same outcomes, and is never added. An absent part counts as zero, with a diagnostic, only when it is `not_tagged` with no related concept and at least one of the four mapped debt concepts (short-term borrowings, current portion, noncurrent long-term debt, lease liabilities counted as debt) is present at the year-end; any other absence makes long-term debt `unavailable` with the code total debt gives, and an unsupported mapping decides first. Short-term borrowings and leases are never added: they count only as a debt concept present, so a gap in either does not make long-term debt `unavailable`. With none of the four present, the "no reported debt" row of total debt applies to all four components and the year's interest expense. An IFRS issuer's long-term debt is `unavailable` with `unsupported_mapping` while the IFRS noncurrent long-term debt mapping is unsupported.

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

## Source notes

- Benjamin Graham, *The Intelligent Investor*, Chapter 14: defensive-investor limits on price relative to average earnings and book value, including the combined product limit of 22.5.
- Benjamin Graham, *The Intelligent Investor*, Chapter 11: simplified growth-stock formula and cautions about the reliability of projected growth.
- Federal Reserve Bank of St. Louis FRED, [Moody's Seasoned Aaa Corporate Bond Yield (AAA)](https://fred.stlouisfed.org/series/AAA): useful background on a defined AAA corporate-bond-yield series; Investment Analysis Engine does not currently retrieve it automatically.

Secondary calculators or articles may illustrate common modern usage, but they do not override the formula, input, provenance, and naming conventions documented here.
