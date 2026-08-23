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

### Graham Analysis
The Step 2.3 deterministic fundamental-analysis family containing two explicitly named methods: the default Graham Number and the secondary Graham growth-value formula. “Graham analysis” does not mean that both methods are interchangeable or that either is a complete investment decision.

### Graham Number Method (`graham_number`)
The proposed default Graham method. It combines positive earnings per share and book value per share to estimate a conservative maximum indicated price for screening.

### Graham Growth-Value Method (`graham_growth_value`)
The separate forecast-dependent Graham method using earnings, expected growth, and a current AAA corporate-bond yield. It is retained as a secondary method and must be selected explicitly.

### Method Discriminator
A stable field such as `number` or `growth` that tells the software which Graham configuration, input requirements, calculation, and result model apply.

### Discriminated Union
A typed set of alternative models selected by a discriminator. It prevents invalid combinations such as supplying a growth rate to a Graham Number request or omitting growth-policy information from a growth-method result.

### Input-Resolution Layer
The code between a CLI/tool request and a deterministic calculator. It obtains each required field from an explicit override, valid cache entry, configured provider, or deterministic fixture and returns typed resolved inputs.

### Resolved Input
An input value packaged with the information needed to interpret and reproduce it, including units, source, provider field or series, reporting period, `as_of`, retrieval time, transformations, and override/cache status.

### Heterogeneous Strategy Independence
The principle that materially different financial strategies may use different inputs and outputs while sharing the existing orchestration/tool architecture. Generic orchestration must not assume all analysis is Momentum.

---

## Market data

### `BaseDataClient`
An existing provider boundary used by deterministic analyzers and data consumers. Step 2.3 may supplement it with narrower typed contracts when quotes, company financial facts, macro series, or cache access do not fit a historical-price-shaped interface cleanly.

### Data Provider
An external or local source that supplies market prices, company financial facts, or economic-series observations. Examples include a quote API, a financial-statements service, or a macroeconomic data service.

### Cache
A stored copy of previously retrieved data. A cache hit may be used only when the entry satisfies the requested `as_of` and freshness policy; otherwise resolution proceeds to an allowed provider or reports the input unavailable.

### Cache Hit / Cache Miss / Stale Cache Entry
A **cache hit** finds a valid reusable observation. A **cache miss** finds none. A **stale cache entry** exists but is too old or otherwise outside the active policy and therefore cannot silently be treated as current.

### Historical Market Data
A time-indexed series of observations used for time-series calculations such as Momentum.

### Current Quote / Current Market Price
A point-in-time market price. For an analysis with an explicit `as_of`, it means the latest permitted market observation at or before that boundary, not necessarily the wall-clock price when the program runs.

### Company Financial Facts / Fundamentals
Reported accounting values such as earnings, common shareholders' equity, and shares outstanding. They come from financial statements and have reporting periods that usually differ from market-quote timestamps.

### Macro Series
A time-indexed economic or market benchmark, such as a corporate-bond-yield series. A specific observation must retain its series identifier, units, source, and observation date.

### Provenance
The record of where a value came from and how it was transformed. Provenance can include source kind, provider, source field, observation period, retrieval time, calculation steps, and whether the value was overridden.

### `as_of`
The time boundary for an input or analysis. A requested analysis `as_of` prevents the resolver from using observations or information that became available after that boundary.

### Available At / Filing Date / Publication Date
The time when a fact became knowable to an investor. A financial statement's fiscal-period end may precede its filing date by weeks or months, so historical analysis must not treat the period-end value as if it had already been published.

### Look-Ahead Bias
An error in historical analysis caused by using information that was not yet available at the analysis date. Tracking availability dates separately from reporting periods helps prevent it.

### Data Vintage
The version of a time-series observation available at a particular time. Some economic data are revised after first publication, so a reproducible historical analysis may need the original vintage rather than today's revised value.

### `retrieved_at`
The timestamp when the application obtained a value. It is different from `as_of`: an old financial statement might be retrieved today while still retaining its historical reporting date.

### Override
A value explicitly supplied by the user or caller instead of accepting the cache/provider-resolved value. Overrides have highest resolution precedence and must be identified in provenance.

### Resolution Precedence
The ordered source policy used for each field in Step 2.3: explicit override, then valid cache, then configured provider, then explicit unavailability.

### OHLCV
Open, High, Low, Close, Volume observations for a market-data interval.

### Fixture Adapter
A deterministic, no-network implementation of the data contracts used to validate resolution behavior and later run Golden cases. It must never silently fall back to a live provider.

### Fixture
Version-controlled test data with fixed values and metadata. The same fixture and configuration must produce the same resolved inputs and analytical results on every run.

### Production Persistence
SQLite/cache-backed durable access introduced in Step 3.1 for market data, required financial facts, macro observations, and telemetry. Production persistence is separate from Golden fixtures.

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

### RSI (Relative Strength Index)
A bounded momentum indicator commonly used to compare the magnitude of recent gains and losses. Its presence in this glossary does not mean it is currently implemented by `MomentumAnalyzer`.

### EMA (Exponential Moving Average)
A moving average that gives more weight to recent observations. It differs from an SMA's equal weighting and is not currently part of the implemented Momentum calculation.

### MACD (Moving Average Convergence Divergence)
A trend/momentum indicator derived from the relationship between exponential moving averages. It is not currently part of the implemented Momentum calculation.

---

## Graham valuation terms

### EPS (Earnings Per Share)
Profit attributable to common shareholders expressed per common share. EPS may be basic or diluted and may cover a fiscal year or the trailing twelve months, so its basis and period must always be identified.

### Basic EPS / Diluted EPS
**Basic EPS** uses the weighted-average common shares actually outstanding during the reporting period. **Diluted EPS** also reflects potentially dilutive securities such as options or convertible instruments. Values with different share bases must not be combined silently.

### TTM (Trailing Twelve Months)
The most recent continuous twelve-month period represented by available reports. TTM EPS is a current-looking accounting measure but is not the same as one completed fiscal year's EPS or Graham's three-year average.

### Three-Year-Average EPS
The arithmetic mean of EPS from three completed fiscal years. Step 2.3 proposes this as the default Graham Number earnings basis because Graham's defensive-investor price criterion referred to average earnings over the preceding three years.

### Normalized EPS / Normal Earnings
Earnings adjusted according to an explicit policy to reduce the effect of unusual or non-recurring items. “Normalized” is not self-defining: every adjustment and period must be documented. The software must not invent normalized earnings silently.

### Fiscal Year
A company's twelve-month accounting period. It may differ from the calendar year, so annual EPS observations must retain their fiscal-period dates.

### Reporting Period
The span or date to which a financial fact applies, such as a fiscal year, quarter, TTM interval, or balance-sheet date.

### Stock Split Adjustment
A transformation that restates per-share values after the number of shares changes through a stock split or reverse split. EPS, BVPS, and price must use compatible share bases.

### BVPS (Book Value Per Share)
Book value attributable to common shareholders divided by period-end common shares outstanding. BVPS is an accounting measure of net assets per common share, not a market price.

### Common Shareholders' Equity
The portion of reported equity attributable to common shareholders after claims belonging to preferred shareholders or other senior equity interests are excluded where applicable.

### Shares Outstanding
The number of issued common shares currently held by investors, usually measured at a reporting date. This period-end figure is commonly used when deriving BVPS and differs from weighted-average shares used in EPS.

### Book Value
The accounting value of assets minus liabilities attributable to the relevant equity holders. It may differ greatly from market value and may not capture internally generated intangible assets.

### Tangible Book Value / Tangible BVPS
Book value after subtracting goodwill and other intangible assets, expressed in total or per-share form. It is a distinct variation and must never be silently substituted for ordinary book value or BVPS.

### P/E (Price-to-Earnings Ratio)
Current price per share divided by earnings per share. A P/E of 15 means the share price is fifteen times the selected EPS measure.

### P/B (Price-to-Book Ratio)
Current price per share divided by book value per share. A P/B of 1.5 means the share price is one and one-half times BVPS.

### Graham Number
A commonly used algebraic expression of Graham's combined defensive-investor limits of P/E ≤ 15 and P/B ≤ 1.5:

```text
sqrt(22.5 × EPS × BVPS)
```

The result is a maximum indicated price or screening ceiling when EPS and BVPS are positive. It does not by itself prove that a company satisfies Graham's other defensive-investor criteria or that the stock is a suitable investment.

### Factor 22.5
The product of the Graham Number's component limits: `15 × 1.5 = 22.5`. Algebraically, `P/E × P/B = price² / (EPS × BVPS)`, which leads to the square-root formula.

### Maximum Indicated Price / Screening Ceiling
The preferred description of the Graham Number result. It is the highest price indicated by this limited earnings-and-book-value screen, not a promise of fair value or future return.

### Defensive Investor
Graham's term for an investor seeking a relatively conservative, low-maintenance approach. His complete defensive-stock framework included additional size, financial-strength, earnings-stability, dividend, and growth criteria beyond the two ratios represented by the Graham Number.

### Applicability Status
A structured indication of whether a method can be meaningfully calculated. Step 2.3 uses statuses such as `applicable`, `not_applicable`, and `input_unavailable` instead of forcing every security into a numeric result.

### `not_applicable`
A valid outcome meaning the method should not be used for the supplied facts—for example, when Graham Number EPS or BVPS is non-positive. It is not the same as a software failure or a zero valuation.

### Expected Growth Rate (`g`)
The assumed annual earnings-growth rate used only by `graham_growth_value`, expressed in **percentage points**. For example, `6.5` means 6.5%. Its source, intended horizon, and policy must be reported.

### Growth-Estimation Policy
The explicit rule that supplies `g`. Step 2.3 initially supports a user-provided override and may support an explicitly selected historical EPS CAGR proxy. An LLM or silent default must not invent growth.

### Historical EPS CAGR Proxy
An explicitly selected policy that uses historical EPS compound growth as a stand-in for `g`. It is deterministic and reproducible, but past growth is not proof of future growth and the result must be labeled as a proxy.

### Analyst Consensus Estimate
An aggregation of forecasts from multiple analysts. Step 2.3 defers using such estimates until the provider's field meaning, forecast horizon, provenance, update behavior, and licensing are verified.

### CAGR (Compound Annual Growth Rate)
The constant annual rate that would transform a beginning value into an ending value over a stated number of years:

```text
(ending_value / beginning_value)^(1 / years) - 1
```

A historical EPS CAGR describes the past. It is only a proxy—not a forecast—unless a separate justified policy says otherwise.

### AAA Corporate Bond Yield
The yield on a documented series of highest-rated corporate debt, used only by `graham_growth_value`. The exact provider series, units, observation date, and rating scope must be recorded.

### AAA
The highest credit-rating category in commonly used rating scales, indicating very low assessed credit risk. The precise label and methodology depend on the rating agency or published series.

### Yield
Annual income from a bond or other instrument expressed as a percentage of its price or value. A yield is a rate, not a dollar amount.

### Basis Point (bp / bps)
One hundredth of one percentage point. For example, a move from 4.40% to 4.65% is an increase of 25 basis points.

### Baseline AAA Yield
The historical `4.4` formula constant used in the selected growth-value convention. It is configurable formula normalization, not a current market observation.

### Current AAA Yield
The resolved AAA corporate-bond-yield observation used in the denominator of the growth-value formula. It must be positive and retain its series provenance and observation date.

### Graham Growth-Value Formula
The project's explicitly identified secondary convention:

```text
normalized_eps × (base_pe + growth_multiplier × g)
× baseline_aaa_yield / current_aaa_yield
```

It is a simplified, forecast-dependent growth-stock estimate. It is not the Graham Number and must not be presented as a precise or universally applicable intrinsic value.

### Base P/E (`base_pe`)
The no-growth earnings multiple used as a configurable constant in the selected growth-value convention. The initial conventional value is `8.5`.

### Growth Multiplier (`growth_multiplier`)
The configurable constant multiplying `g` inside the growth-value formula. The initial conventional value is `2.0`.

### Intrinsic Value
An estimate of what an investment is economically worth based on a stated model and assumptions, rather than its current market price. Different models can produce different intrinsic-value estimates. Step 2.3 avoids using this term without qualification for the Graham Number.

### Reference Value
The method-specific value used for comparison with current price: `maximum_indicated_price` for the Graham Number or `growth_value` for the growth method.

### Margin of Safety (MOS)
In this project, the percentage difference between a method's reference value and current market price:

```text
(reference_value - current_price) / reference_value × 100
```

Positive means price is below the selected reference value; negative means it is above it. This calculation measures a valuation discount or premium but does not eliminate business or investment risk. If the reference value or current price is unavailable, MOS is unavailable (`None`), not zero.

### Discount / Premium to Reference Value
A neutral description of the same price comparison represented by project MOS. A discount is below the reference value; a premium is above it.

### Percentage Point
The arithmetic difference between two percentages. Moving from 4% to 6% is an increase of 2 percentage points, or 50% relative to the original 4%.

---

## Evaluation

### Golden Benchmark Suite
The Step 2.4 deterministic benchmark of typed cases, fixtures, expected behavior, and independently verified numerical results.

### Strategy/Tool-Selection Correctness
Whether the runtime selected the appropriate registered deterministic capability and supplied valid case-appropriate arguments.

### Method-Selection Correctness
Whether the runtime selected the requested method within a strategy family—for example, Graham Number rather than Graham growth value. This is narrower than deciding between Momentum and Graham.

### Numerical Correctness
Whether deterministic Python output matches independently verified expected values within case-specific tolerance.

### Overall Case Pass
Whether all required case-level acceptance criteria pass. A correct strategy choice does not rescue an incorrect deterministic result, and vice versa.

### Deterministic / No-LLM Mode
Test mode that validates fixtures, contracts, analyzers, evaluator logic, and report serialization without a live model. It cannot measure actual LLM strategy selection.

### Real-Local-Ollama Evaluation
Empirical evaluation mode that measures actual local-model behavior. It remains separate from deterministic regression testing.

### Golden Fixture
A fixed, reviewable data set used by a Golden case. It includes enough provenance and timestamps to reproduce the expected resolved inputs and numerical outputs without a network call.

### Numerical Tolerance
The permitted difference between a calculated value and an independently verified expected value, used to accommodate controlled floating-point or rounding effects without masking substantive errors.

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

---

## Project and software acronyms

### API (Application Programming Interface)
A defined way for software components or services to exchange requests and responses. A provider API may supply quotes, financial facts, or macro data.

### CLI (Command-Line Interface)
The text-based commands used to run the project, such as `financial-agents graham TICKER`.

### CI (Continuous Integration)
Automated checks run when changes are proposed, including formatting, linting, type checking, and tests.

### DAO (Data Access Object)
A typed component that reads or writes persistent data while keeping database details out of analyzers and orchestration code.

### DI (Dependency Injection)
Providing a component's dependencies from outside rather than constructing them internally. It allows an analyzer to use a live provider, cache, or deterministic fixture without changing its calculation code.

### JSON (JavaScript Object Notation)
A structured text format used for data exchange and machine-readable results.

### JSONL (JSON Lines)
A text format containing one JSON object per line. Step 2.1 uses it as the initial trajectory-telemetry sink format.

### LLM (Large Language Model)
The model used for planning, tool selection, and narrative synthesis. Project financial calculations remain deterministic Python operations rather than LLM arithmetic.

### MOS (Margin of Safety)
See **Margin of Safety** in the Graham valuation section.

### PR (Pull Request)
A proposed set of repository changes submitted for review before merge.

### Pydantic
The Python validation library used to define typed request, configuration, result, and telemetry models.

### SQL (Structured Query Language)
The language used to define and query relational databases.

### SQLite
The embedded relational database selected for the project's production persistence layer.

### UTC (Coordinated Universal Time)
The common time standard used for unambiguous timestamps across systems and time zones.

### UUID (Universally Unique Identifier)
A widely used identifier format. The project uses UUIDs for values such as run or event identifiers where globally unique correlation is useful.
