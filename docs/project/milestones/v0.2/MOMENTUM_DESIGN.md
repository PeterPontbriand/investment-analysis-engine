# Technical Momentum Analysis Strategy

This document defines the deterministic momentum analysis strategy in Financial Data Agents. The strategy evaluates a public security's short-term and long-term trend strength using simple moving averages, moving average crossover posture, and relative strength indicators derived from historical daily closing price series.

The strategy supports direct execution from the command line and defines the typed analysis contract used by runtime agents. Calculations are strictly deterministic, handling missing or insufficient historical price data without using language models or non-deterministic fallbacks.

## Decision summary

| Decision | Contract |
| :--- | :--- |
| Strategy identifier | `strategy_id = momentum` |
| Method identifier | `method_id = sma_crossover_rsi` |
| Short-term moving average | 50-trading-day Simple Moving Average ($\text{SMA}_{50}$) |
| Long-term moving average | 200-trading-day Simple Moving Average ($\text{SMA}_{200}$) |
| Momentum oscillator | 14-period Relative Strength Index ($\text{RSI}_{14}$) via Wilder's Smoothing |
| Minimum history for full evaluation | 200 completed daily price observations |
| Minimum history for partial metrics | 15 completed daily price observations (allows $\text{RSI}_{14}$; $\text{SMA}_{50}$ requires 50) |
| Crossover evaluation | Static relative posture ($\text{SMA}_{50} > \text{SMA}_{200}$ vs $\text{SMA}_{50} < \text{SMA}_{200}$), not dynamic window transition |
| Signal classification | `BULLISH`, `BEARISH`, `NEUTRAL`, `UNKNOWN` |
| Insufficient history classification | Returns `UNKNOWN` headline signal; missing metrics evaluate to `None` / JSON `null` (never `NaN`) |
| Historical boundary | Strict `as_of` cut-off filtering (`bar_timestamp <= effective_as_of`) |
| Data source seam | `MarketDataProvider` historical daily price series, with the legacy `BaseDataClient` adapted at the boundary |
| Contextual metadata | Market source, freshness, and currency managed in execution/presentation context |
| Versions | Strategy method semantics remain version 1; public investor-presentation JSON is `schema_version = 2` after the additive security-identity snapshot |

---

# Part I — Financial Strategy and Investor Experience

## 1. Investment question and interpretation

The strategy asks:

> Over the available daily price history up to the analysis boundary, does the target security exhibit positive trend alignment across short-term and long-term moving averages combined with constructive relative strength?

Momentum analysis identifies securities experiencing sustained directional price movements. Strong technical momentum can indicate institutional accumulation or broad market trend alignment, while technical breakdown may indicate distribution.

The strategy does not evaluate fundamental financial health, valuation metrics, capital structure, or qualitative management performance. It reflects historical price dynamics only and is subject to lag, whipsaws in sideways markets, and rapid trend reversals.

## 2. Technical measures

### 2.1 Moving averages and crossover posture

The analysis uses:
- 50-trading-day Simple Moving Average ($\text{SMA}_{50}$);
- 200-trading-day Simple Moving Average ($\text{SMA}_{200}$);
- Current closing price position relative to both moving averages;
- Moving average crossover posture (`golden_cross` vs `death_cross`).

```text
SMA_N = sum(closing_price_i, i = 1..N) / N
```

Crossover evaluation measures static relative posture on the analysis date:
- `golden_cross`: $\text{SMA}_{50} > \text{SMA}_{200}$
- `death_cross`: $\text{SMA}_{50} < \text{SMA}_{200}$
- `equal`: $\text{SMA}_{50} == \text{SMA}_{200}$

The method evaluates static posture rather than detecting whether a cross event occurred within a specific trailing lookback window.

### 2.2 Relative Strength Index (RSI)

The strategy calculates the standard 14-period Relative Strength Index ($\text{RSI}_{14}$) using Wilder's Smoothed Moving Average (RMA):

```text
change_t = price_t - price_{t-1}
gain_t = max(change_t, 0)
loss_t = max(-change_t, 0)

avg_gain_14 = Wilder_SMA(gain, 14)
avg_loss_14 = Wilder_SMA(loss, 14)

RS = avg_gain_14 / avg_loss_14
RSI = 100 - (100 / (1 + RS))
```

Wilder's initialization uses a simple 14-period average of gains and losses for the first observation (requiring a minimum of 15 price closes), followed by exponential smoothing:

$$\text{avg\_gain}_t = \frac{\text{avg\_gain}_{t-1} \times 13 + \text{gain}_t}{14}$$

Boundary conditions:
- When $\text{avg\_loss} = 0$ and $\text{avg\_gain} > 0$, $\text{RSI} = 100.0$.
- When $\text{avg\_gain} = 0$ and $\text{avg\_loss} = 0$, $\text{RSI} = 50.0$.

Defined indicator zones:
- $\text{RSI} \ge 70.0$: Overbought region;
- $50.0 \le \text{RSI} < 70.0$: Bullish / constructive region;
- $30.0 \le \text{RSI} < 50.0$: Bearish / neutral region;
- $\text{RSI} < 30.0$: Oversold region.

## 3. Classification logic

The strategy evaluates indicators in strict deterministic sequence to assign the headline signal.

| Priority | Condition / Predicate | Signal | Explanation |
| ---: | :--- | :--- | :--- |
| 1 | Fewer than 200 eligible daily price bars available | `UNKNOWN` | Insufficient history for 200-day moving average |
| 2 | $\text{Price} > \text{SMA}_{50} > \text{SMA}_{200}$ AND $\text{SMA}_{50} > \text{SMA}_{200}$ AND $50.0 \le \text{RSI}_{14} < 70.0$ | `BULLISH` | Full positive trend alignment and constructive non-overbought momentum |
| 3 | $\text{Price} < \text{SMA}_{50} < \text{SMA}_{200}$ AND $\text{SMA}_{50} < \text{SMA}_{200}$ AND $\text{RSI}_{14} < 50.0$ | `BEARISH` | Full negative trend alignment and downward momentum |
| 4 | All required indicators present, but failing predicates 2 and 3 | `NEUTRAL` | Mixed technical signals (e.g., price above SMA50 but below SMA200, or RSI overbought $\ge 70.0$) |

### 3.1 Unambiguous classification rules

- An overbought condition ($\text{RSI} \ge 70.0$) prevents a `BULLISH` classification even if price alignment is perfect, causing the classification to resolve to `NEUTRAL`.
- An $\text{RSI} = 48.0$ with perfect price alignment ($\text{Price} > \text{SMA}_{50} > \text{SMA}_{200}$) fails predicate 2 and evaluates to `NEUTRAL`.
- Partial indicator availability (e.g., 100 bars available: $\text{SMA}_{50}$ and $\text{RSI}_{14}$ compute, but $\text{SMA}_{200}$ is `None`) results in `UNKNOWN` signal classification. Partial metrics remain reportable in output structures.

## 4. Investor controls and output

### 4.1 Command

```text
financial-agents momentum TICKER [options]
```

```text
--as-of DATE_OR_TIMESTAMP
--data-provider PROVIDER_ID
--no-cache
--details
--diagnostics
--json
```

### 4.2 Concise output contract

```text
AAPL — Technical Momentum Analysis

Signal: BULLISH
Price: $185.50
SMA (50-day): $178.20 (Price +4.10%)
SMA (200-day): $165.40 (Price +12.15%)
Crossover posture: Golden Cross (SMA-50 > SMA-200)
RSI (14-period): 62.40 (Constructive)
Source: Daily close history via BaseDataClient
Note: Technical momentum reflects historical price action and does not measure business fundamentals or intrinsic valuation.
```

Order of rendering:
1. Ticker and strategy heading;
2. Headline `Signal` (`BULLISH`, `BEARISH`, `NEUTRAL`, or `UNKNOWN`);
3. Current price observation;
4. 50-day SMA and percentage distance;
5. 200-day SMA and percentage distance;
6. Crossover posture (`Golden Cross` or `Death Cross`);
7. 14-period RSI and state descriptor;
8. Data source summary;
9. Strategy limitation notice.

### 4.3 Other presentation modes

- `--details` exposes raw input price series length, exact indicator values, percentage deviations, and calculation windows.
- `--diagnostics` exposes cache utilization, data fetching attempts, date truncation parameters, and execution errors.
- `--json` emits public presentation `schema_version = 2`, including an explicit nullable `security_identity` snapshot. Unavailable values are JSON `null` (never `NaN`).

## 5. Interpretation limits

This strategy does not provide:
- Fundamental valuation, balance sheet evaluation, or earnings quality analysis;
- Forward price target projections or guaranteed trend duration;
- Automated order routing or portfolio risk management;
- Intraday pattern recognition or multi-timeframe analysis (daily closing price series only).

---

# Part II — Normative Implementation Contract

## 6. Versions and evolution

Every result contains:

```text
strategy_id = "momentum"
method_id = "sma_crossover_rsi"
method_version = 1
schema_version = 1
```

These identifiers describe the typed strategy result semantics. The investor-presentation JSON envelope is versioned independently and is currently version 2 because Slice F-1 added nullable security-identity metadata without changing the calculation method.

- `strategy_id` identifies the momentum analysis family.
- `method_id` identifies the specific indicator combination (`sma_crossover_rsi`).
- `method_version` increments when indicator parameter logic or math changes.
- `schema_version` increments when the machine-readable output structure changes.

## 7. Normative typed contract

### 7.1 Enums and pure result types

```text
MomentumSignal = BULLISH | BEARISH | NEUTRAL | UNKNOWN
CrossoverPosture = golden_cross | death_cross | equal | unknown
```

```text
MomentumMetrics
    price: float | None
    sma_50: float | None
    sma_200: float | None
    rsi_14: float | None
    crossover: CrossoverPosture
```

```text
MomentumResult
    schema_version: int = 1
    strategy_id: str = "momentum"
    method_id: str = "sma_crossover_rsi"
    method_version: int = 1
    ticker: str
    requested_as_of: datetime | None
    effective_as_of: datetime
    execution_status: CalculationStatus
    signal: MomentumSignal
    reason: str | None
    metrics: MomentumMetrics
    warnings: tuple[str, ...]
    diagnostics: ResolutionTrace
```

### 7.2 Result invariants

- When `execution_status` is `ok` and history $\ge 200$ bars, all `metrics` fields are non-null and `crossover` is `golden_cross`, `death_cross`, or `equal`.
- When history $< 200$ bars, `signal` is `UNKNOWN`, `sma_200` is `None`, and `reason` states `insufficient_history`.
- When history $< 50$ bars, `sma_50` is `None`.
- When history $< 15$ bars, `rsi_14` is `None`.
- No metric field ever renders `NaN`, `Inf`, or `-Inf`. In JSON serialization, unavailable values map to `null`.

## 8. Deterministic calculation algorithms

Pure calculation functions reside in `src/analysis/momentum/`:

```text
compute_sma(prices: list[float], window: int) -> float | None
compute_rsi(prices: list[float], period: int = 14) -> float | None
evaluate_crossover(sma_short: float | None, sma_long: float | None) -> CrossoverPosture
classify_momentum_signal(
    price: float | None,
    sma_short: float | None,
    sma_long: float | None,
    rsi: float | None,
    crossover: CrossoverPosture
) -> MomentumSignal
```

### 8.1 Input validation and constraints

1. `prices` must be sorted chronologically ascending (`prices[0]` is oldest, `prices[-1]` is newest).
2. All elements in `prices` must be finite numbers strictly greater than zero. Non-finite (`NaN`, `Inf`) or non-positive values trigger `invalid_input`.
3. If duplicate timestamps exist in the raw input, the resolver must deduplicate before passing price series to pure calculators.

### 8.2 RSI mathematical specification

For `compute_rsi(prices, 14)`:
1. Require `len(prices) >= 15`. Return `None` if unsatisfied.
2. Calculate price changes $D_t = P_t - P_{t-1}$ for $t = 1 \dots N$.
3. Compute initial average gain $AG_1$ and loss $AL_1$ over first 14 changes using simple average.
4. Apply Wilder's smoothing for $t = 15 \dots N$:
   $$AG_t = \frac{AG_{t-1} \times 13 + \text{gain}_t}{14}$$
   $$AL_t = \frac{AL_{t-1} \times 13 + \text{loss}_t}{14}$$
5. If $AL_N == 0$: return `100.0` if $AG_N > 0$ else `50.0`.
6. Return $100.0 - \left(\frac{100.0}{1.0 + \frac{AG_N}{AL_N}}\right)$.

## 9. Data architecture and provider seam

The current Momentum implementation resolves daily bars through `MarketDataProvider`. A compatibility adapter wraps the legacy `BaseDataClient` implementation at that boundary rather than exposing it as the modern analysis contract.

- The resolver requests historical daily prices up to `effective_as_of`.
- Price series truncation occurs strictly at the point-in-time boundary: bars where `bar_timestamp > effective_as_of` are discarded prior to calculation.
- Provider identifier, quote freshness, and ISO currency codes are managed within the execution and presentation context.

## 10. Verification contract

Deterministic unit and integration tests enforce:

1. **Indicator Accuracy:** Exact output verification for `compute_sma` and `compute_rsi` against standard reference series (e.g., Wilder's 14-period RSI test fixtures).
2. **Boundary Conditions:** Division-by-zero handling in RSI (zero losses -> 100.0; zero gains & losses -> 50.0).
3. **Classification Integrity:** Exhaustive test matrix covering all combinations of Price/SMA50/SMA200 relationships and RSI zones.
4. **Truncated Series:** Handling of series lengths 0, 10, 14, 15, 49, 50, 199, and 200 bars, asserting exact status, metric nullability, and `UNKNOWN` signal behavior.
5. **No Look-ahead:** Verification that price bars past `effective_as_of` do not alter indicator calculations.
6. **JSON Serialization:** Rejection of `NaN` outputs across all unavailable metric states.
7. **Zero Live Calls:** Test suite executes completely isolated from external network/provider APIs.

---

# Pre-Golden Modernization Record

Step 2.4 Slice F completed and approved the bounded Momentum modernization before Golden fixtures freeze its public behavior:

- the resolver enforces `bar_timestamp <= effective_as_of` before calculation;
- `sma_50`, `sma_200`, and `rsi_14` expose standard `MetricResult` status/reason semantics for unavailable evidence;
- market data resolves through `MarketDataProvider` with retained `ResolvedInput` provenance and market context;
- typed `MomentumPolicy`/`MomentumConfig` values support the `--short-window`, `--long-window`, and `--rsi-period` CLI options; and
- `ResolutionTrace` covers provider fetch, point-in-time filtering, and calculation stages.

Slice F-1 subsequently added best-effort security identity across concise/details/diagnostics/JSON presentation. Identity failure remains display-only and never changes Momentum calculation semantics.
