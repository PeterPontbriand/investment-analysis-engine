# Financial Data & Mathematics

This document is the project authority for deterministic financial-math semantics that are currently implemented or explicitly selected for the active milestone.

It is **not** a wish list of every future indicator.

**Step 2.3 status:** The dual-method Graham semantics below are the approved target design. The local Graham implementation is still uncommitted and may not yet match this document. `docs/milestones/v0.2/STEP_2_3_GRAHAM_DESIGN.md` is the compact implementation specification; the active milestone plan supplies acceptance criteria and review gates.

---

## 1. Data-boundary rules

### Provider abstraction
Historical price data is consumed through `BaseDataClient` and its provider adapters. Step 2.3 adopts a separate valuation-input boundary rather than making a historical-price interface own company fundamentals and macroeconomic series.

- `yfinance` is an active provider adapter.
- Other provider clients may exist as placeholders/alternatives.
- Do not treat a placeholder provider as the production authority merely because a file exists.
- Do not introduce a new provider/dependency solely because an older document mentioned it.
- The exact provider field mappings for annual/TTM EPS, BVPS or its components, quotes, and AAA yield must be verified before implementation.
- A valuation provider may compose narrower quote, fundamentals, and macro-series capabilities; no single upstream service is assumed to supply them all.

### Historical series vs current quote
These are distinct data capabilities:

- **Historical series**: ordered observations used by time-series analysis such as Momentum.
- **Current quote / market price**: point-in-time market price used for comparison such as Graham margin of safety.

Step 2.3 makes current quote a first-class valuation-input operation. Do not implement it as a disguised one-day historical request.

### Resolution and time boundaries

Graham calculators receive typed resolved values. They do not call providers, inspect caches, or interpret CLI precedence.

Each required field resolves independently:

```text
explicit override → valid cache → configured provider → unavailable
```

Every resolved input records its value, units/currency where applicable, source kind, provider field or series, reporting/observation period, availability/filing date where supplied, analysis `as_of`, retrieval time, transformations, and override/cache status.

A requested analysis `as_of` is a hard information boundary. A financial fact with an earlier fiscal period end but a later filing/publication date was not yet knowable and must not be used. If a provider cannot answer a historical request without look-ahead bias, the input is unavailable; current data is not silently substituted.

### Missing data and applicability
Missing/unavailable financial data is explicit. Never substitute numeric zero for "unknown."

The Graham result contract distinguishes:

- `applicable` — required inputs are available and the method applies;
- `not_applicable` — the supplied facts are valid but the method should not be used, such as non-positive EPS or BVPS for the Graham Number;
- `input_unavailable` — a required value cannot be resolved within the permitted source/time policy;
- operational failure — provider/cache/runtime execution failed unexpectedly.

---

## 2. Current Momentum implementation

The currently implemented `MomentumAnalyzer` is a deterministic **SMA/crossover** analyzer. It does not currently define RSI, MACD, Sharpe ratio, or a 12-month-minus-1-month return strategy.

### Inputs

`MomentumConfig` contains:
- `short_window`
- `long_window`

Validation requires:

```text
short_window < long_window
```

Current repository configuration supplies defaults (currently 50 / 200), but callers may provide other valid values.

### Price series

The analyzer operates on the normalized `Close` series supplied by the current `BaseDataClient` path.

Do not change the existing Momentum price-column semantics as part of Step 2.3 unless a specific bug/task requires it.

### SMA formulas

For window `n`:

```text
SMA_t(n) = mean(P[t-n+1 : t])
```

The analyzer computes:

```text
short_sma = rolling_mean(Close, short_window)
long_sma  = rolling_mean(Close, long_window)
signal    = 1 if short_sma > long_sma else 0
crossover = signal[t] - signal[t-1]
```

Interpretation:
- `signal == 1` → short SMA above long SMA → bullish state.
- `signal == 0` → otherwise bearish state.
- final SMA unavailable/NaN due to insufficient history → `TrendStatus.UNKNOWN`.
- positive crossover → transition into bullish relation.
- negative crossover → transition out of bullish relation.

The exact result fields are owned by `MomentumMetrics`.

---

## 3. Benjamin Graham methods (Step 2.3 target)

Step 2.3 implements two explicitly named methods. They share a price-comparison envelope but have different formulas, inputs, purposes, and limitations. Neither method is sufficient by itself for an investment decision.

### 3.1 Graham Number — `graham_number` (default)

```text
maximum_indicated_price = sqrt(22.5 × EPS × BVPS)
```

The factor `22.5` is derived from the combined limits:

```text
maximum P/E = 15
maximum P/B = 1.5
15 × 1.5 = 22.5
```

Because:

```text
P/E × P/B = price² / (EPS × BVPS)
```

solving the combined limit for price produces the square-root expression.

The output is a **maximum indicated price** or **screening ceiling** derived from two of Graham's defensive-investor criteria. It is not a complete defensive-investor qualification and must not be labeled as an unqualified intrinsic value.

#### EPS convention

The default basis is `three_year_average`:

```text
three_year_average_eps =
    (fiscal_eps_1 + fiscal_eps_2 + fiscal_eps_3) / 3
```

Requirements:

- use three completed fiscal-year EPS observations;
- record each fiscal period and whether EPS is basic or diluted;
- do not average incompatible share bases or share classes;
- record split adjustments and transformations;
- preserve the component observations in derived-input provenance.

`ttm` is a supported modern variation only when explicitly selected and labeled. It must never silently replace the three-year default.

#### BVPS convention

```text
BVPS = common_shareholders_equity / period_end_common_shares_outstanding
```

A provider-reported BVPS may be used only when its definition and provenance are retained. Tangible BVPS is a distinct variation and must not be substituted silently.

#### Applicability

Positive EPS and BVPS are required. Non-positive EPS or BVPS produces `not_applicable`, not a zero valuation, complex number, or missing-input exception.

### 3.2 Graham growth-value method — `graham_growth_value` (secondary)

```text
growth_value = normalized_eps
    × (base_pe + growth_multiplier × g)
    × baseline_aaa_yield / current_aaa_yield
```

Initial configurable convention:

```text
base_pe = 8.5
growth_multiplier = 2.0
baseline_aaa_yield = 4.4
```

Where:

- `normalized_eps` uses an explicitly documented earnings basis/transformation;
- `g` is expected annual growth in **percentage points** (`6.5` means 6.5%, not `0.065`);
- `baseline_aaa_yield` is a historical formula constant in percentage points, not a live observation;
- `current_aaa_yield` is a resolved observation from a documented corporate-bond-yield series, also in percentage points.

This is a simplified, forecast-dependent growth-stock estimate. It is not the Graham Number and must not be described as precise or universally applicable intrinsic value.

#### Growth policy

The initial required policy is `explicit_override`: the user supplies `g` for the growth method. The LLM never invents growth and the software never supplies a silent default.

An explicitly selected `historical_eps_cagr_proxy` may be added only as a deterministic, labeled historical proxy. Provider/analyst consensus growth is deferred until field meaning, horizon, provenance, update behavior, and licensing are verified.

Do not clip, cap, floor, or silently annualize growth without an approved policy, rationale, and tests.

#### AAA-yield policy

The exact production series/provider remains a Step 2.3 provider-feasibility decision. Before implementation, document the selected series identifier, issuer/rating scope, maturity scope, frequency, units, observation date, publication availability, retrieval mechanism, and licensing constraints. Do not treat an arbitrary market ticker as equivalent to a defined AAA corporate-bond-yield series.

Both baseline and current yields must be strictly positive.

### 3.3 Shared reference-value and margin-of-safety semantics

The method-specific reference value is:

- `maximum_indicated_price` for `graham_number`;
- `growth_value` for `graham_growth_value`.

When a valid current price and reference value are available:

```text
margin_of_safety_percent =
    (reference_value - current_price)
    / reference_value
    × 100
```

Semantics:

- positive → current price is below the selected reference value;
- zero → current price equals the reference value;
- negative → current price exceeds the reference value.

This percentage describes a discount or premium to the selected formula output; it does not eliminate business or investment risk.

When current price or reference value is unavailable:

```text
current_price = None       # when quote resolution failed
margin_of_safety_percent = None
```

Do not use `0.0` to represent unavailable margin of safety. The typed result exposes the actual current price used, the method identifier, calculation version, applicability status/reason, resolved inputs, assumptions, and warnings.

### 3.4 Mathematical validation

Reject NaN, infinity, and mathematically invalid configuration values deterministically. Do not add arbitrary financial-domain cutoffs merely because a number looks unusual. Any non-mathematical domain bound requires explicit rationale and tests.

In particular, a value greater than 100 does not prove that a decimal fraction such as `0.05` was supplied; that inference is backwards.

---

## 4. Deterministic-test requirements

### Momentum
Tests should cover:
- configured window validation;
- reference SMA values;
- bullish/bearish/unknown behavior;
- crossover behavior;
- insufficient history;
- injected deterministic historical data.

### Graham
Tests should cover:
- independently calculated references for both formulas;
- three-year-average derivation from three fiscal observations;
- explicit TTM variation;
- non-positive EPS/BVPS → `not_applicable` for the Graham Number;
- invalid yield/growth configuration for the growth method;
- override/cache/provider/unavailable resolution precedence;
- provenance for provider, cache, override, fixture, and derived values;
- requested `as_of` rejecting later or not-yet-published facts;
- supplied and resolved current price;
- unavailable quote → current price and MOS `None`;
- positive and negative margin-of-safety semantics;
- fixture mode performing no live network calls;
- method-specific CLI validation and the default Graham Number selection.

Expected/reference values must not be generated by simply calling the implementation under test.

---

## 5. Future analytical metrics

RSI, EMA/MACD, Sharpe ratio, volatility, drawdown, additional valuation models, and aggregation/risk metrics are later analytical-expansion candidates unless/until explicitly implemented.

Do not add them to Momentum or Graham merely because they are common financial metrics.

When a future step adopts one, its exact formula, price semantics, annualization basis, missing-data behavior, and tests must be documented here.

---

## 6. Evaluation semantics

Step 2.4 Golden evaluation distinguishes:
- correct strategy/tool selection;
- correct Graham method selection where applicable;
- correct deterministic numerical result;
- overall case pass/fail.

The LLM's prose is not the authoritative numeric result when a deterministic analyzer result exists.

Golden fixtures contain deterministic test evidence and must not silently fetch live market data.

---

## 7. Source notes

- Benjamin Graham, *The Intelligent Investor*, Chapter 14: defensive-investor limits on price relative to average earnings and book value, including the combined product limit of 22.5.
- Benjamin Graham, *The Intelligent Investor*, Chapter 11: simplified growth-stock formula and cautions about the reliability of projected growth.
- Federal Reserve Bank of St. Louis FRED, [Moody's Seasoned Aaa Corporate Bond Yield (AAA)](https://fred.stlouisfed.org/series/AAA): a candidate reference series, not yet the approved production integration.

Secondary calculators or articles may illustrate common modern usage, but they do not override the formula, input, provenance, and naming conventions selected in this document.
