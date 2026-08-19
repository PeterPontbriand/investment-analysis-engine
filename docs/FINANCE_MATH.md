# Financial Data & Mathematics

This document is the project authority for deterministic financial-math semantics that are currently implemented or explicitly selected for the active milestone.

It is **not** a wish list of every future indicator.

---

## 1. Data-boundary rules

### Provider abstraction
Market data is consumed through `BaseDataClient` and provider adapters.

- `yfinance` is an active provider adapter.
- Other provider clients may exist as placeholders/alternatives.
- Do not treat a placeholder provider as the production authority merely because a file exists.
- Do not introduce a new provider/dependency solely because an older document mentioned it.

### Historical series vs current quote
These are distinct data capabilities:

- **Historical series**: ordered observations used by time-series analysis such as Momentum.
- **Current quote / market price**: point-in-time market price used for comparison such as Graham margin of safety.

Step 2.3 makes current quote a first-class market-data operation. Do not implement it as a disguised one-day historical request.

### Missing data
Missing/unavailable financial data is explicit. Never substitute numeric zero for "unknown."

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

## 3. Benjamin Graham intrinsic-value convention (Step 2.3)

The project intentionally selects one documented revised-Graham convention rather than claiming all published/restated versions use identical constants.

### Formula

```text
V = EPS × (base_pe + growth_multiplier × g)
    × baseline_aaa_yield / current_aaa_yield
```

Default convention supplied by the proposed strategy:

```text
base_pe = 8.5
growth_multiplier = 2.0
baseline_aaa_yield = 4.4
```

Where:
- `EPS` = trailing earnings per share;
- `g` = expected annual growth rate in **percentage points** (`6.5` means 6.5%, not `0.065`);
- `current_aaa_yield` = current AAA corporate bond yield in percentage points;
- `baseline_aaa_yield` = reference AAA yield in percentage points.

### Validation semantics

The implementation must deterministically reject mathematically invalid inputs, including:
- non-positive EPS for this selected convention;
- non-positive current/reference yield;
- any parameter combination that makes the valuation expression mathematically invalid for the result being produced;
- explicitly supplied non-positive current market price.

Do not add arbitrary financial-domain cutoffs merely because a number "looks unusual." Any non-mathematical domain bound requires explicit rationale and tests.

In particular, do not claim that a value greater than 100 proves a decimal fraction (such as `0.05`) was supplied; that inference is backwards.

### Current price and margin of safety

When a valid current market price is available:

```text
margin_of_safety_percent =
    (intrinsic_value - current_price)
    / intrinsic_value
    × 100
```

Semantics:
- positive → current market price is below estimated intrinsic value;
- zero → current price equals estimated intrinsic value;
- negative → current market price exceeds estimated intrinsic value.

When current price is unavailable:

```text
current_price = None
margin_of_safety_percent = None
```

Do **not** use `0.0` to represent unavailable margin of safety.

`GrahamValueMetrics` must expose the actual `current_price` used for the comparison when available.

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
- independently calculated formula reference;
- invalid/non-positive EPS;
- invalid yield/configuration values;
- supplied current price;
- injected client quote retrieval;
- unavailable quote → both quote and MOS `None`;
- positive and negative margin-of-safety semantics.

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
- correct deterministic numerical result;
- overall case pass/fail.

The LLM's prose is not the authoritative numeric result when a deterministic analyzer result exists.

Golden fixtures contain deterministic test evidence and must not silently fetch live market data.
