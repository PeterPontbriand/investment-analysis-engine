# Momentum Analysis Strategy Guide

This guide explains the Financial Data Agents **Momentum Analysis Strategy** from an investor/user perspective.

## What this strategy does

Momentum compares a short [SMA](../GLOSSARY.md#sma-simple-moving-average) with a longer [SMA](../GLOSSARY.md#sma-simple-moving-average) over historical closing prices and reports the current relationship plus [crossover](../GLOSSARY.md#crossover) state.

It is a price-series analysis. It does not determine business quality, intrinsic value, or whether a security should be bought or sold.

## Quick start

```bash
uv run financial-agents momentum AAPL
```

The current defaults are:

```text
short window = 50
long window = 200
```

Choose different valid windows when useful:

```bash
uv run financial-agents momentum AAPL \
    --short-window 10 \
    --long-window 30
```

The short window must be smaller than the long window.

## How the calculation works

For a window of `n` observations:

```text
SMA_t(n) = mean(P[t-n+1 : t])
```

The strategy calculates a short moving average and a long moving average over the historical `Close` series, then evaluates their relationship and whether that relationship changed on the latest observation.

In investor terms:

- short SMA above long SMA → bullish price-momentum state;
- short SMA not above long SMA → bearish price-momentum state under the current rule;
- transition into the bullish relationship → bullish crossover;
- transition out of the bullish relationship → bearish crossover.

See [Financial Math](../FINANCE_MATH.md#momentum-analysis-strategy) for the exact deterministic convention.

## Presentation modes

### Default

```bash
uv run financial-agents momentum AAPL
```

Shows the current moving averages, their relationship, recent crossover information when applicable, data-source/freshness information, and the strategy limitation. When provider metadata supplies an instrument name, the heading shows `Instrument Name (TICKER)`; otherwise it uses the ticker alone.

### `--details`

```bash
uv run financial-agents momentum AAPL --details
```

Shows additional data context and configuration.

### `--diagnostics`

```bash
uv run financial-agents momentum AAPL --diagnostics
```

Shows more technical execution/diagnostic information.

### `--json`

```bash
uv run financial-agents momentum AAPL --json
```

Produces [machine-readable output](../GLOSSARY.md#machine-readable-output) in [JSON](../GLOSSARY.md#json-javascript-object-notation), including an explicit nullable security-identity snapshot.

## Sufficient history is required

A moving average cannot be calculated until enough price observations exist for its window.

If the returned history is too short, the strategy reports the affected values/result as unavailable or unknown rather than pretending that missing values are zero.

Machine-readable JSON uses `null` for unavailable numeric outputs rather than non-standard `NaN`.

## Data source

Momentum currently obtains historical market-price data from Yahoo Finance through the third-party [`yfinance`](https://ranaroussi.github.io/yfinance/) library and operates on the normalized historical `Close` values returned to the strategy. `yfinance` is not affiliated with or endorsed by Yahoo.

## Why another momentum calculation may disagree

Common causes include:

- different short/long windows;
- a different price field, such as adjusted close instead of close;
- different trading-day coverage;
- missing-price handling;
- different crossover definitions/reporting rules; and
- different market-data revisions or provider histories.

When comparing results, first confirm that both tools are calculating the same indicator over the same price series and dates.

## What this strategy does not currently implement

The current Momentum strategy is specifically an SMA/crossover analysis. It does not currently implement [RSI](../GLOSSARY.md#rsi-relative-strength-index), [MACD](../GLOSSARY.md#macd-moving-average-convergence-divergence), [Sharpe ratio](../GLOSSARY.md#sharpe-ratio), or a 12-month-minus-1-month momentum factor.

Those are separate analytical methods; they should not be inferred from the generic word “momentum.”

## Important limitations

SMA/crossover analysis is backward-looking. It can lag rapid price changes, produce whipsaws in sideways markets, and says nothing by itself about valuation, balance-sheet quality, earnings durability, or future returns.

Nothing produced by this strategy is investment advice.

## Related user documentation

- [Usage Guide](../USAGE.md)
- [Financial Math — Momentum Analysis Strategy](../FINANCE_MATH.md#momentum-analysis-strategy)
- [Glossary](../GLOSSARY.md)
