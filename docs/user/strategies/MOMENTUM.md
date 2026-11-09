# Momentum Strategy Guide

This guide explains the Investment Analysis Engine **Momentum Strategy** from an investor/user perspective.

## What this strategy does

Momentum compares a short [SMA](../GLOSSARY.md#sma) with a longer [SMA](../GLOSSARY.md#sma) over historical closing prices and reports the current relationship plus [crossover](../GLOSSARY.md#crossover) state.

It is a price-series analysis. It does not determine business quality, intrinsic value, or whether a security should be bought or sold.

## Quick start
<!-- help:exclude -->

```bash
ian momentum AAPL
```

## Default windows

The current defaults are:

```text
short window = 50
long window = 200
```

They ship with the application and may be overridden key by key in the strategy's settings file; the keys are `short_window`, `long_window`, `rsi_period` (14) and `history_start_date` (the first day of the price history, 2021-01-01).

The short window must be smaller than the long window.

### On the command line
<!-- help:exclude -->

Choose different valid windows when useful:

```bash
ian momentum AAPL \
    --short-window 10 \
    --long-window 30
```

The settings file is `strategies/momentum.toml` in your settings folder. See [Strategy settings files](../INSTALLATION.md#strategy-settings-files).

## How the calculation works

For a window of `n` observations:

```text
SMA_t(n) = mean(P[t-n+1 : t])
```

The strategy calculates a short moving average and a long moving average over the historical `Close` series, then evaluates their relationship and whether that relationship changed on the latest observation.

A crossover needs two consecutive valid SMA pairs. Having exactly enough prices for the long SMA establishes today's relationship but not a prior relationship; crossover is unavailable in that case. The RSI uses simple trailing averages of gains/losses, as specified in [Financial Math](../FINANCE_MATH.md#momentum-strategy).

The result's technical evidence retains original provider retrieval time and cache origin. Historical daily labels are not verified exchange-close timestamps, and the provider's past adjusted-price vintages are not retained. Observation-date filtering alone is not a guarantee of historical knowability. Missing or nonfinite prices cause a failure with the affected field/date when known; the application does not silently remove bad rows or substitute an older close.

In investor terms:

- short SMA above long SMA → bullish price-momentum state;
- short SMA not above long SMA → bearish price-momentum state under the current rule;
- transition into the bullish relationship → bullish crossover;
- transition out of the bullish relationship → bearish crossover.

See [Financial Math](../FINANCE_MATH.md#momentum-strategy) for the exact deterministic convention.

## Point-in-time analysis and cache control

Only price observations at or before the as-of boundary are used. The boundary is a date or a timezone-aware timestamp. A run can bypass historical price cache reads and writes.

The result reports the latest observation that remained after the boundary was applied, not the boundary you requested. A date-only boundary includes that whole day.

`data_as_of` and each price observation's `observed_at` are exchange-local trading dates. A daily series stamped at local midnight in its own timezone is read by those local calendar dates, so each observation is reported as that date at 00:00 UTC, the same form a timezone-naive series produces, and a date-only as-of boundary includes the bars dated on or before that date in the exchange's calendar. A series with any bar at another time of day keeps the exact instants its provider supplied. One case is not corrected: a daily bar stamped as the UTC instant of a non-UTC local midnight (for example 15:00 UTC for a Tokyo date), because the series does not carry the exchange's timezone.

As-of runs fetch history only up to the boundary, so they are cached separately from live runs, and an invalid price dated after the boundary does not affect them. The one exception is a provider that stamps a daily price later in its date than the boundary time; Yahoo stamps daily prices at midnight, so it does not apply to them.

Provider-adjusted prices are revised retroactively: splits and dividends restate history. An as-of result is therefore filtered to a date but reflects today's adjusted view of the prices on that date, not the prices as they would have looked then. See [look-ahead bias](../GLOSSARY.md#look-ahead-bias).

Bypassing the cache affects the historical price cache only. A saved run stores the as-of and cache choices with the run, and refreshing a watchlist entry saved this way reuses them.

### On the command line
<!-- help:exclude -->

```bash
ian momentum AAPL --as-of 2025-12-31
ian momentum AAPL --no-cache
```

| Option | Meaning |
| :--- | :--- |
| `--as-of DATE_OR_TIMESTAMP` | Use only price observations at or before this boundary, given as `YYYY-MM-DD` or a timezone-aware ISO-8601 timestamp. |
| `--no-cache` | Bypass historical price cache reads and writes for this run. |

With `--no-cache` and without `--save-run`, the command does not open or create the local database. `--save-run` stores the `--as-of` and `--no-cache` choices with the run.

## Presentation modes
<!-- help:exclude -->

### Default

```bash
ian momentum AAPL
```

Shows the current moving averages, their relationship, recent crossover information when applicable, data-source/freshness information, and the strategy limitation. When provider metadata supplies an instrument name, the heading shows `Instrument Name (TICKER)`; otherwise it uses the ticker alone.

### `--details`

```bash
ian momentum AAPL --details
```

Explains the SMA windows, crossover requirement, simple-average RSI convention, price basis and observation coverage. It separates trend from a new crossover event and states the limits of historical date labels.

### `--diagnostics`

```bash
ian momentum AAPL --diagnostics
```

Retains technical execution traces, original retrieval/cache evidence and identity/classification metadata. JSON retains the corresponding typed evidence.

### `--json`

```bash
ian momentum AAPL --json
```

Produces [machine-readable output](../GLOSSARY.md#machine-readable-output) in [JSON](../GLOSSARY.md#json), including an explicit nullable security-identity snapshot.

## Sufficient history is required

A moving average cannot be calculated until enough price observations exist for its window.

If the returned history is too short, the strategy reports the affected values/result as unavailable or unknown rather than pretending that missing values are zero. A history too short for the long average gives a trend of `UNKNOWN` and the status `input_unavailable`. The RSI is still calculated and shown when the history is longer than the RSI period.

Machine-readable JSON uses `null` for unavailable numeric outputs rather than non-standard `NaN`.

## Statuses and failures

Every Momentum result carries a status, as the other strategies' results do:

| Situation | Status | Run outcome |
| :--- | :--- | :--- |
| A bullish or bearish trend | `ok` | `completed` |
| The history is too short for the long average (trend `UNKNOWN`) | `input_unavailable` | `unavailable` |
| No price history exists at or before the as-of boundary | `input_unavailable` | `unavailable` |
| The price data failed a data-quality check | `input_unavailable` | `unavailable` |
| The price provider failed | `provider_error` | `failed` |

A result that could not be calculated has a reason, and a reason code where one fits (`insufficient_history`, `not_available_as_of` or `provider_error`; a failed data-quality check has the reason only). A provider failure never stores the provider's own error text: the stored reason is a fixed message, and `provider_failure` names the provider and the kind of failure.

A saved run keeps a failed or unavailable outcome, and refreshing a watchlist entry records it as a run with that outcome instead of an error without a run.

### On the command line
<!-- help:exclude -->

The exit code is 0 for an `ok` result and 1 otherwise.

A result that could not be calculated has no `result` part in `--json`. In the text output, a result with a status other than `ok` is written to standard error, as the other strategies do, and after a provider failure the [provider check](../USAGE.md#after-a-provider-failure-the-first-line) runs unless you pass `--no-provider-check`.

`--save-run` stores a failed or unavailable run, and [`refresh`](../WORKSPACE.md#refreshing-a-watchlist) records it as a run with its outcome instead of an error without a run. A refresh that holds one exits 1.

A request that is itself wrong (a naive `--as-of`, a window or period that is not positive) is rejected before anything is fetched and exits 1 with a failure document, as before.

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

The current Momentum strategy is specifically an SMA/crossover analysis, reporting [RSI](../GLOSSARY.md#rsi) as a supporting indicator (see [above](#how-the-calculation-works) for its simple-average, not-Wilder-smoothing convention). It does not currently implement [MACD](../GLOSSARY.md#macd), Sharpe ratio, or a 12-month-minus-1-month momentum factor.

Those are separate analytical methods; they should not be inferred from the generic word “momentum.”

## Important limitations

SMA/crossover analysis is backward-looking. It can lag rapid price changes, produce whipsaws in sideways markets, and says nothing by itself about valuation, balance-sheet quality, earnings durability, or future returns.

Nothing produced by this strategy is investment advice.

## Watchlist options
<!-- help:exclude -->

`watchlist add-selection momentum` accepts `--short-window`, `--long-window`, `--rsi-period`, `--as-of` and `--no-cache`. A window left out takes the value in the Momentum settings. `--no-cache` bypasses the historical price cache. See [Local Research Workspace](../WORKSPACE.md#strategies-and-their-watchlist-options) for the command that takes them.

## Related user documentation
<!-- help:exclude -->

- [Usage Guide](../USAGE.md)
- [Financial Math — Momentum Strategy](../FINANCE_MATH.md#momentum-strategy)
- [Glossary](../GLOSSARY.md)
