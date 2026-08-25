# Financial Math & Data Conventions

This document defines the deterministic financial formulas and data conventions used by the analysis strategies that Financial Data Agents currently implements.

It is not a catalogue of every financial indicator the project may someday support. Strategy-specific usage and interpretation live in the [Analysis Strategy Guides](strategies/README.md).

## Shared data conventions

### Data sources are capabilities, not interchangeable labels

Financial Data Agents uses different sources for different kinds of information:

- **SEC EDGAR** — completed fiscal-year company financial facts used by the Graham Analysis Strategy.
- **Yahoo Finance data via [`yfinance`](https://ranaroussi.github.io/yfinance/)** — historical market prices for Momentum and current quote comparison for Graham where applicable. `yfinance` is an independent open-source library and is not affiliated with, endorsed by, or vetted by Yahoo.
- **Massive** — optional supported current TTM diluted EPS/current-price data for explicitly selected Graham Growth analysis.
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

A requested [`as_of`](GLOSSARY.md#asof) date is a hard information boundary.

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

Interpretation:

- `signal == 1` → short SMA above long SMA → bullish price-momentum state;
- otherwise → bearish state under the configured rule;
- positive crossover → transition into the bullish relationship;
- negative crossover → transition out of the bullish relationship;
- insufficient history → unavailable moving averages / unknown state rather than invented zeroes.

Machine-readable JSON uses `null` for unavailable numeric outputs rather than non-standard `NaN`.

See the [Momentum Analysis Strategy Guide](strategies/MOMENTUM.md).

## Graham Analysis Strategy

The Graham Analysis Strategy contains two distinct [methods](GLOSSARY.md#method). They share optional market-price comparison but have different formulas, required values, purposes, and limitations.

### Graham Number

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

#### Earnings convention

The standard Graham Number basis is a three-year average of completed fiscal-year diluted EPS:

```text
three-year-average EPS =
    (fiscal EPS 1 + fiscal EPS 2 + fiscal EPS 3) / 3
```

The three observations must be compatible in financial meaning/share basis and must have been available by the requested historical boundary.

TTM EPS is a distinct modern variation where explicitly supported/selected; it never silently replaces the standard three-year average.

#### Book value per common share

```text
BVPS = common shareholders' equity / period-end common shares outstanding
```

A provider-reported BVPS is usable only when its definition is understood. Financial Data Agents' SEC calculation derives fiscal-year-end BVPS from compatible accounting evidence when a safe direct value is unavailable.

Tangible BVPS is a different measure and is not silently substituted.

#### Applicability

Positive EPS and BVPS are required for the Graham Number. Non-positive EPS or BVPS means the method is not applicable rather than producing a zero or complex-number valuation.

### Graham Growth Value

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

#### EPS basis

- Graham Growth using SEC EDGAR data uses three-year-average diluted EPS.
- Graham Growth using explicitly selected Massive data uses current TTM diluted EPS.

Unsupported data-source/basis combinations are rejected rather than silently transformed into a different calculation.

#### Expected growth

The user supplies expected growth explicitly. The software and AI model do not invent, infer, clip, cap, floor, or silently annualize that forecast.

#### AAA yield

No automatic current AAA-yield data source is integrated at present. The user therefore supplies the current AAA corporate-bond yield explicitly.

Both baseline and current yields must be strictly positive.

### Price comparison

For either Graham method, a compatible current market price is optional to the formula itself.

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

If a current quote is unavailable, the Graham calculation can still remain valid while the price comparison is omitted.

A quote in a different currency is not used for a price relationship without an approved currency-conversion mechanism.

### Mathematical validation

NaN, infinity, and mathematically invalid configuration values are rejected deterministically.

Financial Data Agents does not impose arbitrary financial-domain cutoffs merely because a number “looks unusual.” A non-mathematical bound requires an explicit rationale.

See the [Graham Analysis Strategy Guide](strategies/GRAHAM.md).

## Source notes

- Benjamin Graham, *The Intelligent Investor*, Chapter 14: defensive-investor limits on price relative to average earnings and book value, including the combined product limit of 22.5.
- Benjamin Graham, *The Intelligent Investor*, Chapter 11: simplified growth-stock formula and cautions about the reliability of projected growth.
- Federal Reserve Bank of St. Louis FRED, [Moody's Seasoned Aaa Corporate Bond Yield (AAA)](https://fred.stlouisfed.org/series/AAA): useful background on a defined AAA corporate-bond-yield series; Financial Data Agents does not currently retrieve it automatically.

Secondary calculators or articles may illustrate common modern usage, but they do not override the formula, input, provenance, and naming conventions documented here.
