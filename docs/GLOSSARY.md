# Financial Data Agents Glossary

This glossary defines project terms. Formula details and authoritative calculation semantics live in `docs/FINANCE_MATH.md`.

---

## Analysis architecture

### Analyzer / Analytical Strategy
A deterministic Python capability that implements one financial-analysis method. Each analyzer owns its typed configuration, calculation, and result model.

### `BaseAnalyzer`
The existing common analysis abstraction. Supporting multiple analyzers does not imply a separate strategy registry/plugin framework.

### Momentum Analyzer
The existing deterministic technical-analysis strategy. The current implementation uses configurable short/long simple moving averages and crossover state.

### Graham Value Analyzer
The Step 2.3 deterministic fundamental-valuation strategy using the project's selected revised Graham formula convention.

### Heterogeneous Strategy Independence
The principle that materially different financial strategies may use different inputs and outputs while sharing the existing orchestration/tool architecture. Generic orchestration must not assume all analysis is Momentum.

---

## Market data

### `BaseDataClient`
The provider boundary used by deterministic analyzers/data consumers.

### Historical Market Data
A time-indexed series of observations used for time-series calculations such as Momentum.

### Current Quote / Current Market Price
A point-in-time market price. Step 2.3 treats this as distinct from historical-series access.

### OHLCV
Open, High, Low, Close, Volume observations for a market-data interval.

### Fixture Adapter
A deterministic, no-network implementation of the market-data contract used to validate contracts and later run Golden cases.

### Production Persistence
SQLite/cache-backed durable market-data access introduced in Step 3.1. Production persistence is separate from Golden fixtures.

---

## Momentum terms

### SMA (Simple Moving Average)
The arithmetic mean of the selected price series over a rolling window.

### Short Window / Long Window
The two configured SMA windows. The current Momentum configuration requires `short_window < long_window`.

### Crossover
A transition in the relation between short and long SMAs. The current implementation derives a binary `short_sma > long_sma` signal and differences it to identify transitions.

### Bullish / Bearish / Unknown
Momentum result states. `UNKNOWN` is used when the final rolling values are not available, such as insufficient history.

### RSI / EMA / MACD
Common technical indicators that may be added in later analytics-expansion work. Their presence in this glossary does not mean they are currently implemented by `MomentumAnalyzer`.

---

## Graham valuation terms

### EPS (Earnings Per Share)
Earnings attributable per share. The selected Step 2.3 Graham convention requires positive EPS.

### Expected Growth Rate (`g`)
Growth assumption expressed in **percentage points** for the selected Graham formula. Example: `6.5` represents 6.5%.

### AAA Corporate Bond Yield
Yield input used in the selected revised Graham convention. The Step 2.3 strategy uses a current yield and a baseline/reference yield.

### Intrinsic Value
The deterministic value estimate produced by `GrahamValueAnalyzer` using the project-selected formula convention.

### Margin of Safety (MOS)
Percentage difference between estimated intrinsic value and current market price:

```text
(intrinsic_value - current_price) / intrinsic_value × 100
```

Positive means price below estimated intrinsic value; negative means price above it. If current price is unavailable, MOS is unavailable (`None`), not zero.

---

## Evaluation

### Golden Benchmark Suite
The Step 2.4 deterministic benchmark of typed cases, fixtures, expected behavior, and independently verified numerical results.

### Strategy/Tool-Selection Correctness
Whether the runtime selected the appropriate registered deterministic capability and supplied valid case-appropriate arguments.

### Numerical Correctness
Whether deterministic Python output matches independently verified expected values within case-specific tolerance.

### Overall Case Pass
Whether all required case-level acceptance criteria pass. A correct strategy choice does not rescue an incorrect deterministic result, and vice versa.

### Deterministic / No-LLM Mode
Test mode that validates fixtures, contracts, analyzers, evaluator logic, and report serialization without a live model. It cannot measure actual LLM strategy selection.

### Real-Local-Ollama Evaluation
Empirical evaluation mode that measures actual local-model behavior. It remains separate from deterministic regression testing.

---

## Reliability & observability

### Trajectory Telemetry
Machine-readable structured execution history introduced in Step 2.1.

### Operational Logging
Human-oriented runtime diagnostics. It is separate from trajectory telemetry.

### Circuit Breaker
Configured hard limits on execution steps, retries/errors, or wall-clock time. Step 2.5 owns the reliability-limit implementation.

### Light Mode
Default single-tier/modest-hardware operating path.

### Full Dual-Tier Mode
Optional local configuration using a fast/execution tier plus a larger deep-reasoning tier.

### WAL (Write-Ahead Logging)
SQLite mode allowing readers to continue while writes are serialized appropriately.
