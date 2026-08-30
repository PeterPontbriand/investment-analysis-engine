# Financial Data Agents Glossary

This glossary defines terms used in Financial Data Agents. Formula details and authoritative calculation semantics live in [Financial Math & Data Conventions](FINANCE_MATH.md).

---

## Analysis architecture

### Analysis Strategy
A deterministic analytical capability in Financial Data Agents. An analysis strategy owns the rules needed to calculate and interpret a particular kind of analysis. Examples currently include the Graham Analysis Strategy and Momentum Analysis Strategy.

In the Python implementation, an analysis strategy may be represented by an *analyzer* class. User documentation standardizes on **analysis strategy** rather than using internal class terminology as the product concept.

### Method
A particular calculation or analytical approach within an analysis strategy. A strategy may have one method or several. For example, the Graham Analysis Strategy currently contains the Graham Number and Graham Growth Value methods.

A method is an application concept; it does not imply that Benjamin Graham or another source used the word “method” in exactly this project-specific sense.

### `BaseAnalyzer`
The existing common analysis abstraction. Supporting multiple analyzers does not imply a separate strategy registry/plugin framework.

### Momentum Analyzer
The existing deterministic technical-analysis strategy. The current implementation uses configurable short/long simple moving averages and crossover state.

### Graham Analysis
The deterministic fundamental-analysis strategy containing two explicitly named methods: the default Graham Number and the secondary Graham growth-value formula. “Graham analysis” does not mean that both methods are interchangeable or that either is a complete investment decision.

### Graham Number Method (`graham_number`)
The implemented default Graham method. It combines positive earnings per share and book value per share to estimate a conservative maximum indicated price for screening.

### Graham Growth-Value Method (`graham_growth_value`)
The separate implemented forecast-dependent Graham method using earnings, expected growth, and a current AAA corporate-bond yield input. It is retained as a secondary method and must be selected explicitly.

### Method Discriminator
A stable field such as `number` or `growth` that tells the software which Graham configuration, input requirements, calculation, and result model apply.

### Discriminated Union
A typed set of alternative models selected by a discriminator. It prevents invalid combinations such as supplying a growth rate to a Graham Number request or omitting growth-policy information from a growth-method result.

### Input-Resolution Layer
The code between a CLI/tool request and a deterministic calculator. It obtains each required field from an explicit override, valid cache entry, configured provider, or deterministic fixture and returns typed resolved inputs.

### Resolved Input
An input value packaged with the information needed to interpret and reproduce it, including units, source, provider field or series, reporting period, `as_of`, retrieval time, transformations, and override/cache status.

### Typed Evidence
Structured, validated information passed between project components with explicit fields and expected data types—for example, a resolved financial value with its units, source, dates, and provenance, or a deterministic strategy result. “Typed evidence” is distinct from free-form model prose: an AI model may reason about it, but the model does not get to silently redefine or invent the underlying financial values.

### Heterogeneous Strategy Independence
The principle that materially different financial strategies may use different inputs and outputs while sharing the existing orchestration/tool architecture. Generic orchestration must not assume all analysis is Momentum.

---

## Market data

### `BaseDataClient`
The existing historical-price provider boundary used by deterministic analyzers and data consumers. Financial Data Agents supplements it with a separate financial-facts provider/resolution boundary for current quotes, company financial facts, macro observations, and valuation-cache semantics rather than enlarging `BaseDataClient` into a generic financial-data interface.

### Data Provider
An external or local source that supplies market prices, company financial facts, or economic-series observations. Examples include a quote API, a financial-statements service, or a macroeconomic data service.

### SEC
The [U.S. Securities and Exchange Commission](https://www.sec.gov/), the U.S. federal securities regulator. Financial Data Agents currently uses public SEC data as a source of company financial facts.

### EDGAR
The SEC's **Electronic Data Gathering, Analysis, and Retrieval** system, which provides public access to company filings and structured filing data. See the SEC's [EDGAR search resources](https://www.sec.gov/search-filings) and [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).

### Massive
[Massive](https://massive.com/) is a commercial financial-market-data service with an [API](#api-application-programming-interface) that software can use to request licensed market/fundamental data.

A **Massive API key** is a credential issued by Massive that authorizes API requests according to the user's account/plan. Financial Data Agents can optionally use Massive for the supported current TTM diluted-EPS and current-price data used by the Graham Growth Value method. Massive is not required for the Graham Number or Momentum strategies.

See the [Massive API documentation](https://massive.com/docs) for the service itself and [Installation & Configuration](INSTALLATION.md#optional-massive-market-data-access) for Financial Data Agents configuration.


### Cache
A stored copy of previously retrieved data. A cache hit may be used only when the entry satisfies the requested `as_of` and freshness policy; otherwise resolution proceeds to an allowed provider or reports the input unavailable.

### Cache Hit / Cache Miss / Stale Cache Entry
A **cache hit** finds a valid reusable observation. A **cache miss** finds none. A **stale cache entry** exists but is too old or otherwise outside the active policy and therefore cannot silently be treated as current.

### Historical Market Data
A time-indexed series of observations used for time-series calculations such as Momentum.

### Current Quote / Current Market Price
A point-in-time market price used for current valuation comparison. For an analysis with an explicit historical `as_of`, a quote is usable only if the selected provider can establish an eligible observation at or before that boundary. A current-only quote adapter therefore returns unavailable for historical financial-fact requests rather than substituting today's price.

### Security Identity
Best-effort descriptive metadata that associates a ticker with an instrument name and, when available, listing venue and issuer/instrument identifiers at a recorded resolution time. A ticker is not permanent identity and may be reused. Missing identity metadata never changes a financial result, and historical Analysis Runs retain their original identity snapshot rather than silently re-resolving the ticker later.

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
The ordered source policy used for each resolved financial field: explicit override, then valid cache, then configured provider, then explicit unavailability.

### OHLCV
Open, High, Low, Close, Volume observations for a market-data interval.

### Fixture Adapter
A deterministic, no-network implementation of the data contracts used to validate resolution behavior and later run Golden cases. It must never silently fall back to a live provider.

### Fixture
Version-controlled test data with fixed values and metadata. The same fixture and configuration must produce the same resolved inputs and analytical results on every run.

### Production Persistence
SQLite/cache-backed durable access planned for persistent application data for market data, required financial facts, macro observations, and telemetry. Production persistence is separate from Golden fixtures.

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

### Sharpe Ratio
A risk-adjusted-return measure comparing excess return with return volatility. It is not currently part of the implemented Momentum Analysis Strategy.

### EPS (Earnings Per Share)
Profit attributable to common shareholders expressed per common share. EPS may be basic or diluted and may cover a fiscal year or the trailing twelve months, so its basis and period must always be identified.

### Basic EPS / Diluted EPS
**Basic EPS** uses the weighted-average common shares actually outstanding during the reporting period. **Diluted EPS** also reflects potentially dilutive securities such as options or convertible instruments. Values with different share bases must not be combined silently.

### TTM (Trailing Twelve Months)
The most recent continuous twelve-month period represented by available reports. TTM EPS is a current-looking accounting measure but is not the same as one completed fiscal year's EPS or Graham's three-year average. In the current application it is used when the Graham Growth Value method explicitly uses Massive data, not as the standard Graham Number basis.

### Three-Year-Average EPS
The arithmetic mean of EPS from three completed fiscal years. Financial Data Agents uses this as the standard Graham Number earnings basis and when the Graham Growth Value method uses SEC EDGAR earnings data, reflecting Graham's defensive-investor emphasis on average earnings over the preceding three years.

### Normalized EPS / Normal Earnings
Earnings adjusted according to an explicit policy to reduce the effect of unusual or non-recurring items. “Normalized” is not self-defining: every adjustment and period must be documented. The growth calculator accepts an EPS value on the explicitly selected basis; the software does not invent discretionary normalization adjustments.

### Fiscal Year
A company's twelve-month accounting period. It may differ from the calendar year, so annual EPS observations must retain their fiscal-period dates.

### Reporting Period
The span or date to which a financial fact applies, such as a fiscal year, quarter, TTM interval, or balance-sheet date.

### Stock Split Adjustment
A transformation that restates per-share values after the number of shares changes through a stock split or reverse split. EPS, BVPS, and price must use compatible share bases.

### BVPS (Book Value Per Share)
Book value attributable to common shareholders divided by period-end common shares outstanding. BVPS is an accounting measure of net assets per common share, not a market price. When using SEC EDGAR data, Financial Data Agents derives it from eligible fiscal-year-end balance-sheet components rather than claiming a direct SEC BVPS field.

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
A structured indication of whether a method can be meaningfully calculated. Financial Data Agents uses machine-readable statuses including `ok`, `not_applicable`, `input_unavailable`, `invalid_input`, and `provider_error` instead of forcing every security into a numeric result.

### `not_applicable`
A valid outcome meaning the method should not be used for the supplied facts—for example, when Graham Number EPS or BVPS is non-positive. It is not the same as a software failure or a zero valuation.

### Expected Growth Rate (`g`)
The assumed annual earnings-growth rate used only by `graham_growth_value`, expressed in **percentage points**. For example, `6.5` means 6.5%. Its source, intended horizon, and policy must be reported. The current direct CLI requires it explicitly through `--expected-growth`.

### Growth-Estimation Policy
The explicit rule that supplies `g`. The current application supports only a user-provided expected-growth assumption. An LLM, data provider, or silent default must not invent growth.

### Historical EPS CAGR Proxy
A possible future deterministic policy that could use historical EPS compound growth as a stand-in for `g`. It is **not currently implemented**. Any future adoption must be labeled as a historical proxy because past growth is not proof of future growth.

### Analyst Consensus Estimate
An aggregation of forecasts from multiple analysts. The Free Cash Flow & Earnings Growth contract can carry compatible FY1/FY2 diluted-EPS consensus as optional evidence, but the current production SEC mapping may not provide it. Such evidence requires verified field meaning, forecast horizon, provenance, update behavior, and licensing; the software does not invent it.

### CAGR (Compound Annual Growth Rate)
The constant annual rate that would transform a beginning value into an ending value over a stated number of years:

```text
(ending_value / beginning_value)^(1 / years) - 1
```

A historical EPS CAGR describes the past. It is only a proxy—not a forecast—unless a separate justified policy says otherwise.

### AAA Corporate Bond Yield
The yield on a documented series of highest-rated corporate debt, used only by `graham_growth_value`. No production series is approved in the current implementation; the direct Growth command therefore requires an explicit user-supplied AAA-yield value. A future provider integration must retain exact series, units, observation/publication date, and rating/maturity scope.

### AAA
The highest credit-rating category in commonly used rating scales, indicating very low assessed credit risk. The precise label and methodology depend on the rating agency or published series.

### Yield
Annual income from a bond or other instrument expressed as a percentage of its price or value. A yield is a rate, not a dollar amount.

### Basis Point (bp / bps)
One hundredth of one percentage point. For example, a move from 4.40% to 4.65% is an increase of 25 basis points.

### Baseline AAA Yield
The historical `4.4` formula constant used in the selected growth-value convention. It is configurable formula normalization, not a current market observation.

### Current AAA Yield
The AAA corporate-bond-yield value used in the denominator of the growth-value formula. It must be strictly positive. In the current production CLI it is a user override and is identified as such; a future provider-resolved value would additionally need series provenance and observation/publication dates.

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
An estimate of what an investment is economically worth based on a stated model and assumptions, rather than its current market price. Different models can produce different intrinsic-value estimates. Financial Data Agents avoids using this term without qualification for the Graham Number.

### Reference Value
The method-specific value used for comparison with current price: `maximum_indicated_price` for the Graham Number or `growth_value` for the growth method.

### Margin of Safety (MOS)
In this project, the typed percentage difference between a method's reference value and current market price:

```text
(reference_value - current_price) / reference_value × 100
```

Positive means price is below the selected reference value; negative means it is above it. This calculation measures a valuation discount or premium but does not eliminate business or investment risk. If the reference value or current price is unavailable, MOS is unavailable (`None`), not zero.

### Price Relationship
The investor-facing prose representation of the same reference-value comparison, such as “20.00% below the Graham Number” or “89.57% above the Graham growth value.” It avoids requiring a user to interpret the sign convention of the internal `margin_of_safety_percent` field.

### Discount / Premium to Reference Value
A neutral description of the same price comparison represented by project MOS. A discount is below the reference value; a premium is above it.

### Percentage Point
The arithmetic difference between two percentages. Moving from 4% to 6% is an increase of 2 percentage points, or 50% relative to the original 4%.

---

## Free Cash Flow & Earnings Growth terms

### Free Cash Flow & Earnings Growth Strategy
A deterministic historical screen that asks whether both the selected free-cash-flow measure and diluted EPS grew at positive, meaningful compound annual rates over one compatible contiguous period. It returns `PASS`, `FAIL`, or `INDETERMINATE`; it is not a valuation or investment recommendation.

### Operating Cash Flow (OCF)
Net cash provided by operating activities for a completed fiscal year. It is the starting component in the project's free-cash-flow calculation.

### Capital Expenditures (CapEx)
Cash spent to acquire or improve long-lived productive assets. Provider sign conventions differ, so Financial Data Agents normalizes CapEx to a positive expenditure amount and retains the transformation in provenance.

### Free Cash Flow (FCF)
For this strategy, completed annual operating cash flow minus normalized capital expenditures. FCF is a non-GAAP analytical measure, so another provider may use a different definition.

### Total-Company FCF
Free cash flow measured for the company as a whole. Its CAGR is the default FCF classification basis.

### FCF per Diluted Share
Annual total-company FCF divided by compatible weighted-average diluted shares for the same fiscal year. It reflects dilution and repurchases and can be selected as the controlling classification basis.

### Weighted-Average Diluted Shares
The average diluted share count applicable to an earnings period, including the effect of potentially dilutive securities under the reported accounting basis. It is not interchangeable with an ending shares-outstanding snapshot.

### Classification Basis
The explicit FCF measure whose CAGR controls the growth screen: `total_fcf` by default or `fcf_per_share` when selected. Both measures remain visible regardless of the choice.

### `PASS` / `FAIL` / `INDETERMINATE`
The FCF-growth strategy's financial screen outcomes. `PASS` means required growth rates are positive; `FAIL` means complete, meaningful evidence includes a nonpositive required rate; `INDETERMINATE` means the required classification cannot be made from admissible evidence. These are distinct from software execution status.

### FCF Yield
Latest completed annual FCF divided by current market capitalization, expressed as a percentage. It mixes an annual numerator with a current denominator and is informational only in the current method.

### Forward Policy
The rule controlling how optional FY1/FY2 analyst-consensus EPS evidence is treated: `display_only`, `confirmation`, or `hard_gate`. Only `hard_gate` can alter an otherwise passing historical classification.

---

## Evaluation

### Golden Benchmark Suite
The project's deterministic benchmark of typed cases, fixtures, expected behavior, and independently verified numerical results.

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
Machine-readable structured execution history used to record observable application behavior.

### Operational Logging
Human-oriented runtime diagnostics. It is separate from trajectory telemetry and from investor-facing result presentation.

### Circuit Breaker
Configured hard limits on execution steps, retries/errors, or wall-clock time that prevent unbounded execution.

### Light Mode
Recommended single-tier/modest-hardware operating mode.

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

### Machine-Readable Output
Structured output designed so another program can consume it reliably rather than being optimized primarily for a person to read. Financial Data Agents currently provides machine-readable analysis output using **JSON (JavaScript Object Notation)** through the `--json` presentation mode.

Machine-readable output may intentionally retain stable identifiers such as snake_case field names because those identifiers form part of a programmatic contract.

### JSON (JavaScript Object Notation)
A widely used text format for structured data made from objects, arrays, names, strings, numbers, booleans, and null values. Financial Data Agents uses JSON for its `--json` machine-readable presentation mode and for other structured software interfaces.

### JSONL (JSON Lines)
A text format containing one JSON object per line. Financial Data Agents uses JSONL for structured trajectory-telemetry records.

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
