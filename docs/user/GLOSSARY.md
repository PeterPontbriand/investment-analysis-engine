# Investment Analysis Engine Glossary

This glossary defines the finance and analysis terms used in Investment Analysis Engine. Formula details and authoritative calculation semantics live in [Financial Math & Data Conventions](FINANCE_MATH.md). Terms for people who work on the code are in the [Contributor Glossary](../project/CONTRIBUTOR_GLOSSARY.md); terms for people who use the command line are in the last section of this page.

---

## Analysis strategies and results

<a id="analysis-strategy"></a>
### Analysis Strategy
A rule-based way of analyzing a security, with its own inputs, calculation and way of reading the result. The same inputs always give the same result.

A strategy never leaves a calculation to an AI model. This glossary and the guides call the idea an analysis strategy.

<a id="method"></a>
### Method
One calculation approach within an analysis strategy. A strategy may offer one method or several.

Several methods in one strategy are reserved for true variants of the same underlying calculation, such as a future Altman Z versus Z′′ strategy. They are not for strategies that merely address a related question with a different formula, the way Graham Number and Graham Growth Value do: each of those is its own strategy, not two methods of one.

A method is an application concept; it does not imply that Benjamin Graham or another source used the word “method” in exactly this project-specific sense.

<a id="typed-evidence"></a>
### Typed Evidence
Information with named fields and stated data types, such as a value together with its units, source and dates. It is the opposite of free-form text.

“Typed evidence” is distinct from free-form model prose: an AI model may reason about it, but the model does not get to silently redefine or invent the underlying financial values.

<a id="applicability-status"></a>
### Applicability Status
Whether a method can be meaningfully calculated for a security, instead of forcing every security into a numeric result.

Investment Analysis Engine uses machine-readable statuses including `ok`, `not_applicable`, `input_unavailable`, `invalid_input`, and `provider_error`.

<a id="not-applicable"></a>
### Not Applicable
A valid outcome meaning the method should not be used for the supplied facts, for example when earnings or book value per share is not positive.

The code value is `not_applicable`. It is not the same as a software failure or a zero valuation.

<a id="as-filed-sic-code"></a>
### As-Filed SIC Code
The four-digit industry code that the SEC header of an annual filing assigns to the issuer on the filing date. It is read from the filing an analysis is anchored to.

A historical analysis therefore sees the code the issuer had then (`ASSIGNED-SIC`). The code shown for an issuer on the SEC website today can differ, and is never used in its place. When the header cannot be read, the [industry class](#industry-class) is unknown.

<a id="industry-class"></a>
### Industry Class
The group an issuer belongs to for deciding which screening strategies apply: financial, utility, manufacturer or other. It is unknown when the issuer's industry code cannot be established.

It comes from the [as-filed SIC code](#as-filed-sic-code) of the annual report the analysis rests on. The groups are financial (SIC 6000 to 6799, which includes REITs), utility (4900 to 4999), manufacturer (2000 to 3999), or any other issuer. A strategy that does not apply to a class reports the issuer as not applicable; a strategy that depends on the class reports an unknown class as unavailable, and one that does not (Piotroski) runs and says the class is unknown. The SEC assigns one code per filer, so a diversified issuer has the class of that one code.

---

## Local research workspace

<a id="analysis-run"></a>
### Analysis Run
One saved record of a single analysis attempt: the method, the ticker, the exact configuration used and the result, or the fact that no result could be produced.

A run is saved when you ask for it, and a refresh saves one for every entry it runs. Showing a saved Analysis Run always replays its own captured evidence; it never re-fetches data or recalculates, so it keeps showing the same result even if a data provider or your configuration changes afterward.

<a id="selection"></a>
### Selection
One analysis method together with its own configuration, such as Graham Number with SEC EDGAR data or Graham Growth Value with a 6% expected-growth assumption.

The same method may appear in more than one selection, for example to compare Graham Number computed from SEC EDGAR data under two different overrides.

<a id="entry"></a>
### Entry
One ticker paired with one selection inside a watchlist. The same method can appear in several entries, for different tickers or for one ticker with different configuration.

A [watchlist](#watchlist) is an ordered list of entries, not a separate list of tickers and a separate list of [selections](#selection). Each entry's position in the list is a number counted from 1.

<a id="watchlist"></a>
### Watchlist
A named, ordered list of entries that you want to run and revisit as a group.

Each entry pairs a [ticker](#ticker) with a [selection](#selection).

<a id="headline"></a>
### Headline
The few values a strategy picks to stand for one analysis run, so that runs can be compared side by side. It summarizes the run; it is not the full result.

A value the run could not calculate is shown as a dash.

<a id="refresh"></a>
### Refresh
Running every entry in one watchlist and saving each result as its own analysis run.

A refresh limits how many tickers run at once, and one ticker's failure never stops the rest of the watchlist.

---

## Market data and timing

<a id="data-provider"></a>
### Data Provider
An external or local source of market prices, company financial facts or economic-series observations. Examples are a quote service, a financial-statements service and a macroeconomic data service.

<a id="sec"></a>
### SEC
The United States Securities and Exchange Commission, the federal securities regulator. The engine uses its public data as a source of company financial facts.

The SEC's website is at [sec.gov](https://www.sec.gov/).

<a id="edgar"></a>
### EDGAR
The SEC's Electronic Data Gathering, Analysis, and Retrieval system, which gives public access to company filings and structured filing data.

See the SEC's [EDGAR search resources](https://www.sec.gov/search-filings) and [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data).

<a id="cache"></a>
### Cache
A stored copy of previously retrieved data. A stored value is reused only if it satisfies the requested as-of date and the freshness policy.

Otherwise the engine asks an allowed provider or reports the input unavailable. Caching is automatic and distinct from saving an [Analysis Run](#analysis-run), which is optional and durable.

<a id="cache-states"></a>
### Cache Hit / Cache Miss / Stale Cache Entry
A cache hit finds a valid stored value to reuse, a cache miss finds none, and a stale entry exists but is too old to be treated as current.

A stale cache entry exists but is too old or otherwise outside the active policy, so it cannot silently be treated as current.

<a id="historical-market-data"></a>
### Historical Market Data
A time-indexed series of market observations, such as daily prices, used for time-series calculations such as Momentum.

<a id="current-quote"></a>
### Current Quote / Current Market Price
A market price taken as of now, used for comparison with a valuation. For a historical as-of date, it is usable only if the provider can establish a price at or before that date.

For an analysis with an explicit historical [as-of date](#as-of-date), a quote is usable only if the selected provider can establish an eligible observation at or before that boundary. A current-only quote adapter therefore returns unavailable for historical financial-fact requests rather than substituting today's price.

The report calls this the latest available quote. Retrieval time records when the provider response was obtained; market observation time records when the market price was observed, if actually supplied. A five-minute response-reuse bound does not prove that the underlying trade is five minutes old. The current Yahoo adapter retains retrieval time and explicitly reports unknown market observation time.

<a id="ticker"></a>
### Ticker
The short symbol that identifies a security on an exchange, such as KO for The Coca-Cola Company.

A ticker is not permanent identity: it can be reassigned after a delisting (see [Security Identity](#security-identity)).

<a id="security-identity"></a>
### Security Identity
Descriptive details that associate a ticker with an instrument name and, when known, its listing venue and issuer identifiers. They never change a financial result.

Security identity is best-effort metadata recorded at a resolution time. A ticker is not permanent identity and may be reused. Missing identity metadata never changes a financial result, and historical Analysis Runs retain their original identity snapshot rather than silently re-resolving the ticker later.

<a id="instrument-profile"></a>
### Instrument Profile
A security's identity plus a normalized kind of instrument, such as equity or ETF, each with its own provenance. It is kept so that repeated analyses do not look up details that rarely change.

The engine keeps a durable copy of an instrument profile; a stored profile expires after a configured freshness window and is refreshed live when it does. If a refresh finds a genuinely different entity behind the same ticker — a **ticker reuse**, such as a delisting followed by a new listing under the same symbol — the prior profile is retired rather than overwritten, and every Analysis Run that already used it keeps showing that original entity: reopening an old result never relabels it using the ticker's current meaning.

<a id="financial-facts"></a>
### Company Financial Facts / Fundamentals
Reported accounting values such as earnings, shareholders' equity and shares outstanding, taken from financial statements. Their reporting periods usually differ from market-quote times.

<a id="macro-series"></a>
### Macro Series
A time-indexed economic or market benchmark, such as a corporate-bond-yield series.

A specific observation must retain its series identifier, units, source and observation date.

<a id="provenance"></a>
### Provenance
The record of where a value came from and how it was transformed.

Provenance can include source kind, provider, source field, observation period, retrieval time, calculation steps, and whether the value was overridden.

<a id="as-of-date"></a>
### As-of Date
The time boundary for an analysis or an input: information that became available after that date is not used.

A requested analysis boundary (`as_of`) prevents the resolver from using observations or information that became available after that date.

<a id="availability-date"></a>
### Available At / Filing Date / Publication Date
The date a fact became knowable to an investor. A financial statement's fiscal-period end can precede its filing date by weeks or months.

Historical analysis must therefore not treat the period-end value as if it had already been published.

<a id="look-ahead-bias"></a>
### Look-Ahead Bias
An error in historical analysis caused by using information that was not yet available at the analysis date.

Tracking availability dates separately from reporting periods helps prevent it.

<a id="data-vintage"></a>
### Data Vintage
The version of a time-series observation that was available at a particular time. Some economic data are revised after first publication.

A reproducible historical analysis may therefore need the original vintage rather than today's revised value.

<a id="retrieved-at"></a>
### Retrieval Time
The time the application obtained a value. It differs from the as-of date: an old financial statement can be retrieved today and still keep its historical reporting date.

The stored field is `retrieved_at`.

<a id="override"></a>
### Override
A value you supply yourself instead of accepting the value found from the cache or a provider. An override takes precedence over every other source and is identified in provenance.

<a id="resolution-precedence"></a>
### Resolution Precedence
The order in which sources are tried for each financial value: your override, then a valid cache entry, then a configured provider, then an explicit statement that the value is unavailable.

<a id="utc"></a>
### UTC (Coordinated Universal Time)
The common time standard used for unambiguous timestamps across systems and time zones.

---

## Company financial measures

<a id="eps"></a>
### EPS (Earnings Per Share)
Profit attributable to common shareholders, expressed per common share. It may be basic or diluted and may cover a fiscal year or a trailing period.

Its basis and period must always be identified.

<a id="basic-and-diluted-eps"></a>
### Basic EPS / Diluted EPS
Basic EPS divides profit by the weighted-average common shares actually outstanding. Diluted EPS also counts potentially dilutive securities such as options and convertible instruments.

Values with different share bases must not be combined silently.

<a id="ttm"></a>
### TTM (Trailing Twelve Months)
The most recent continuous twelve-month period covered by available reports.

TTM EPS is a current-looking accounting measure but is not the same as one completed fiscal year's EPS or Graham's three-year average. No data source the application currently ships supplies it; the Graham strategies use three-year-average or fiscal-year EPS.

<a id="three-year-average-eps"></a>
### Three-Year-Average EPS
The arithmetic mean of EPS from three completed fiscal years.

Investment Analysis Engine uses this as the standard Graham Number earnings basis and when the Graham Growth Value strategy uses SEC EDGAR earnings data, reflecting Graham's defensive-investor emphasis on average earnings over the preceding three years.

<a id="normalized-eps"></a>
### Normalized EPS / Normal Earnings
Earnings adjusted by an explicit policy to reduce the effect of unusual or non-recurring items.

“Normalized” is not self-defining: every adjustment and period must be documented. The growth calculator accepts an EPS value on the explicitly selected basis; the software does not invent discretionary normalization adjustments.

<a id="fiscal-year"></a>
### Fiscal Year
A company's twelve-month accounting period, which may differ from the calendar year.

Annual EPS observations must therefore retain their fiscal-period dates.

<a id="reporting-period"></a>
### Reporting Period
The span or date a financial fact applies to, such as a fiscal year, a quarter, a trailing twelve-month interval or a balance-sheet date.

<a id="stock-split-adjustment"></a>
### Stock Split Adjustment
Restating per-share values after the number of shares changes through a stock split or reverse split.

EPS, BVPS, and price must use compatible share bases.

<a id="split-adjusted-close"></a>
### Split-Adjusted Close
A closing price restated for every stock split after its date, and for nothing else. A dividend paid later does not change it.

It is the price on the same basis as a share count scaled by those splits, and the two together give the market capitalization the shares and the price had on the day. It is not the dividend-adjusted close that the [Momentum](#momentum-strategy) series uses. A stock dividend appears in the provider's split history as a fractional split (1.05) and is treated like a split; it is not counted as new shares issued.

<a id="market-capitalization"></a>
### Market Capitalization
Common shares outstanding multiplied by the share price, both on the basis of the same date.

The share count is scaled by every stock split after the date it was taken, and the price is the split-adjusted close. It is available only for an issuer whose annual filing is a 10-K, whose quote currency equals its filing currency, and whose listing on the filing's cover page is a share of the issuer. See [Financial Math](FINANCE_MATH.md#shared-metrics).

<a id="ebitda"></a>
### EBITDA
Earnings before interest, taxes, depreciation and amortization, taken here as reported operating income plus depreciation and amortization.

The amortization and depreciation come from the cash-flow statement. Lease cost sits above or below EBITDA according to the accounting framework, so a US GAAP and an IFRS filer are not fully comparable.

<a id="enterprise-value"></a>
### Enterprise Value (EV)
Market capitalization plus total debt, preferred stock and noncontrolling interest, minus cash and short-term investments. It may be negative.

<a id="total-debt"></a>
### Total Debt
Short-term borrowings, the current portion of long-term debt, noncurrent long-term debt and the lease liabilities counted as debt.

A missing debt figure is never assumed to be zero without evidence that the filer has none.

<a id="invested-capital"></a>
### Invested Capital
The tangible capital employed: net working capital plus net property, plant and equipment, with goodwill and intangibles excluded.

Net working capital here excludes cash, short-term investments and the debt in current liabilities.

<a id="bvps"></a>
### BVPS (Book Value Per Share)
Book value attributable to common shareholders divided by period-end common shares outstanding. It is an accounting measure of net assets per share, not a market price.

When using SEC EDGAR data, Investment Analysis Engine derives it from eligible fiscal-year-end balance-sheet components rather than claiming a direct SEC BVPS field.

<a id="common-shareholders-equity"></a>
### Common Shareholders' Equity
The part of reported equity that belongs to common shareholders, after the claims of preferred shareholders and other senior equity interests are excluded where applicable.

<a id="shares-outstanding"></a>
### Shares Outstanding
The number of issued common shares held by investors, usually measured at a reporting date.

This period-end figure is commonly used when deriving BVPS and differs from weighted-average shares used in EPS.

<a id="book-value"></a>
### Book Value
The accounting value of assets minus liabilities attributable to the relevant equity holders.

It may differ greatly from market value and may not capture internally generated intangible assets.

<a id="tangible-book-value"></a>
### Tangible Book Value / Tangible BVPS
Book value after subtracting goodwill and other intangible assets, in total or per share.

It is a distinct variation and must never be silently substituted for ordinary book value or BVPS.

<a id="cagr"></a>
### CAGR (Compound Annual Growth Rate)
The constant annual rate that would turn a beginning value into an ending value over a stated number of years.

```text
(ending_value / beginning_value)^(1 / years) - 1
```

A historical EPS CAGR describes the past. It is only a proxy—not a forecast—unless a separate justified policy says otherwise.

<a id="operating-cash-flow"></a>
### Operating Cash Flow (OCF)
Net cash provided by operating activities for a completed fiscal year.

It is the starting component in the project's free-cash-flow calculation.

<a id="capital-expenditures"></a>
### Capital Expenditures (CapEx)
Cash spent to acquire or improve long-lived productive assets.

Provider sign conventions differ, so Investment Analysis Engine normalizes CapEx to a positive expenditure amount and retains the transformation in provenance.

<a id="free-cash-flow"></a>
### Free Cash Flow (FCF)
The cash a company's operations generate in a year, minus what it spends on long-lived assets such as equipment.

In the Free Cash Flow & Earnings Growth strategy, it is completed annual operating cash flow minus normalized capital expenditures.

FCF is a non-GAAP analytical measure, so another provider may use a different definition.

<a id="weighted-average-diluted-shares"></a>
### Weighted-Average Diluted Shares
The average diluted share count for an earnings period, including the effect of potentially dilutive securities under the reported accounting basis.

It is not interchangeable with an ending shares-outstanding snapshot.

---

## Valuation and price comparison

<a id="valuation"></a>
### Valuation
Estimating what a security may be worth under a stated method and assumptions, usually to compare with its market price.

In Investment Analysis Engine a valuation result is one method's reference value, such as the Graham Number's maximum indicated price, not a complete intrinsic-value conclusion or a recommendation (see [Intrinsic Value](#intrinsic-value) and [Reference Value](#reference-value)).

<a id="intrinsic-value"></a>
### Intrinsic Value
An estimate of what an investment is economically worth under a stated model and assumptions, rather than its market price.

Different models can produce different intrinsic-value estimates. Investment Analysis Engine avoids using this term without qualification for the Graham Number.

<a id="reference-value"></a>
### Reference Value
The value a method produces for comparison with the current price, such as the Graham Number's maximum indicated price or the growth value.

The stored names are `maximum_indicated_price` for the Graham Number and `growth_value` for Graham Growth Value.

<a id="margin-of-safety"></a>
### Margin of Safety (MOS)
The percentage difference between a method's reference value and the current market price, measured against the reference value. Positive means the price is below the reference value.

```text
(reference_value - current_price) / reference_value × 100
```

Negative means the price is above the reference value. This calculation measures a valuation discount or premium but does not eliminate business or investment risk. If the reference value or current price is unavailable, MOS is unavailable (`None`), not zero.

<a id="price-relationship"></a>
### Price Relationship
A plain-language statement of how the market price compares with the reference value, such as 20.00% below the Graham Number.

It avoids requiring you to interpret the sign convention of the stored `margin_of_safety_percent` field. Another example is “89.57% above the Graham growth value.”

<a id="discount-and-premium"></a>
### Discount / Premium to Reference Value
A neutral description of the same price comparison as margin of safety. A discount means the price is below the reference value; a premium means it is above it.

<a id="pe-ratio"></a>
### P/E (Price-to-Earnings Ratio)
Share price divided by earnings per share. A P/E of 15 means the price is fifteen times the selected EPS measure.

<a id="pb-ratio"></a>
### P/B (Price-to-Book Ratio)
Share price divided by book value per share. A P/B of 1.5 means the price is one and one-half times BVPS.

<a id="yield"></a>
### Yield
Annual income from a bond or other instrument as a percentage of its price or value. A yield is a rate, not a dollar amount.

<a id="percentage-point"></a>
### Percentage Point
The arithmetic difference between two percentages. Moving from 4% to 6% is an increase of 2 percentage points.

That is a 50% increase relative to the original 4%.

<a id="aaa-rating"></a>
### AAA
The highest credit-rating category in commonly used rating scales, indicating very low assessed credit risk.

The precise label and methodology depend on the rating agency or published series.

<a id="analyst-consensus-estimate"></a>
### Analyst Consensus Estimate
An aggregation of forecasts from multiple analysts.

The Free Cash Flow & Earnings Growth contract can carry compatible FY1/FY2 diluted-EPS consensus as optional evidence, but the current production SEC mapping may not provide it. Such evidence requires verified field meaning, forecast horizon, provenance, update behavior, and licensing; the software does not invent it.

---

## Momentum Strategy terms

<a id="momentum-strategy"></a>
### Momentum Strategy
A rule-based analysis of recent price behavior. It compares a short and a long simple moving average, reports a bullish or bearish trend, and shows RSI as a supporting indicator.

The moving-average windows are configurable. The strategy reports the state of the crossover of the two averages.

<a id="sma"></a>
### SMA (Simple Moving Average)
The arithmetic mean of a price series over a rolling window.

<a id="sma-windows"></a>
### Short Window / Long Window
The two averaging periods that are compared: the short window and the long window. The short window must be shorter than the long window.

<a id="crossover"></a>
### Crossover
A change in which of the short and long moving averages is higher.

The current implementation derives a binary `short_sma > long_sma` signal and differences it to identify transitions.

Both averages must exist at two consecutive observations. The first valid pair can establish trend but cannot establish a crossover. A zero crossover is a verified absence of transition, distinct from unavailable history.

<a id="momentum-states"></a>
### Bullish / Bearish / Unknown
The trend a Momentum run reports: bullish when the short moving average is above the long one, bearish when it is not, unknown when they cannot be calculated.

The run's status is then `input_unavailable`.

<a id="rsi"></a>
### RSI (Relative Strength Index)
An indicator from 0 to 100 that compares the size of recent price gains with recent losses.

The Momentum strategy uses a simple trailing-average RSI, with a default period of 14 price changes; it does not use Wilder smoothing. See [Financial Math](FINANCE_MATH.md#momentum-strategy) for the formula and zero-loss/flat-window conventions.

<a id="ema"></a>
### EMA (Exponential Moving Average)
A moving average that gives more weight to recent observations than an SMA does.

It is not currently part of the implemented Momentum calculation.

<a id="macd"></a>
### MACD (Moving Average Convergence Divergence)
A trend and momentum indicator built from the relationship between exponential moving averages.

It is not currently part of the implemented Momentum calculation.

---

## Graham Number Strategy terms

<a id="graham-number-strategy"></a>
### Graham Number Strategy
A screening strategy that combines positive earnings per share and book value per share to estimate a conservative maximum indicated price.

It is independent of Graham Growth Value: a different strategy with a different formula, not an alternative method of the same one.

<a id="graham-number"></a>
### Graham Number
The square root of 22.5 times EPS times BVPS, a price ceiling that expresses Graham's defensive limits of P/E 15 and P/B 1.5.

It is a commonly used algebraic expression of those combined limits:

```text
sqrt(22.5 × EPS × BVPS)
```

The result is a maximum indicated price or screening ceiling when EPS and BVPS are positive. It does not by itself prove that a company satisfies Graham's other defensive-investor criteria or that the stock is a suitable investment.

<a id="graham-number-factor"></a>
### Factor 22.5
The product of the Graham Number's component limits: 15 times 1.5 equals 22.5.

Algebraically, `P/E × P/B = price² / (EPS × BVPS)`, which leads to the square-root formula.

<a id="maximum-indicated-price"></a>
### Maximum Indicated Price / Screening Ceiling
The highest price indicated by the Graham Number's limited earnings-and-book-value screen. It is not a promise of fair value or future return.

This is the preferred description of the Graham Number result.

<a id="defensive-investor"></a>
### Defensive Investor
Graham's term for an investor seeking a relatively conservative, low-maintenance approach.

His complete defensive-stock framework included additional size, financial-strength, earnings-stability, dividend, and growth criteria beyond the two ratios represented by the Graham Number.

---

## Graham Growth Value Strategy terms

<a id="graham-growth-value-strategy"></a>
### Graham Growth Value Strategy
A forecast-dependent strategy that estimates a value from earnings, an expected growth rate and a current AAA corporate-bond yield.

It is independent of the Graham Number: a different strategy with a different formula, not an alternative method of the same one. The growth rate and the yield are assumptions you supply.

<a id="expected-growth-rate"></a>
### Expected Growth Rate
The assumed annual earnings-growth rate used by the Graham Growth Value strategy, in percentage points: 6.5 means 6.5%. Its source and horizon must be reported.

It is written `g` in the formula, and its policy must be reported.

<a id="growth-estimation-policy"></a>
### Growth-Estimation Policy
The explicit rule that supplies the expected growth rate. The application supports only a growth assumption that you provide.

An LLM, data provider, or silent default must not invent growth.

<a id="aaa-corporate-bond-yield"></a>
### AAA Corporate Bond Yield
The yield on a documented series of highest-rated corporate debt, used by the Graham Growth Value strategy.

No live series is currently integrated, so the strategy takes a yield you supply. A future provider integration must retain exact series, units, observation/publication date, and rating/maturity scope.

<a id="baseline-aaa-yield"></a>
### Baseline AAA Yield
The reference AAA yield, 4.4 by default, that the Graham Growth Value formula compares the current AAA yield against.

It is configurable formula normalization, not a current market observation.

<a id="current-aaa-yield"></a>
### Current AAA Yield
The AAA corporate-bond yield used in the denominator of the growth-value formula. It must be strictly positive.

It is a value you supply and is identified as such; a future provider-resolved value would additionally need series provenance and observation/publication dates.

<a id="growth-value-formula"></a>
### Graham Growth-Value Formula
The project's secondary valuation formula: earnings scaled by a growth-adjusted multiple and by the ratio of baseline to current AAA yield. It is a simplified estimate that depends on a forecast.

The project's explicitly identified secondary convention:

```text
normalized_eps × (base_pe + growth_multiplier × g)
× baseline_aaa_yield / current_aaa_yield
```

It is a simplified, forecast-dependent growth-stock estimate. It is not the Graham Number and must not be presented as a precise or universally applicable intrinsic value.

<a id="base-pe"></a>
### Base P/E
The no-growth earnings multiple used as a configurable constant in the selected growth-value convention.

The initial conventional value is `8.5` (`base_pe`).

<a id="growth-multiplier"></a>
### Growth Multiplier
The configurable constant that multiplies the expected growth rate in the growth-value formula.

The initial conventional value is `2.0` (`growth_multiplier`).

---

## Free Cash Flow & Earnings Growth Strategy terms

<a id="fcf-growth-strategy"></a>
### Free Cash Flow & Earnings Growth Strategy
A historical screen asking whether free cash flow and diluted EPS both grew at positive, meaningful compound annual rates over one compatible period. It is not a valuation.

It returns `PASS`, `FAIL`, or `INDETERMINATE`, and it is not an investment recommendation.

<a id="total-company-fcf"></a>
### Total-Company FCF
Free cash flow measured for the company as a whole. Its CAGR is the default classification basis.

<a id="fcf-per-diluted-share"></a>
### FCF per Diluted Share
Annual total-company FCF divided by compatible weighted-average diluted shares for the same fiscal year.

It reflects dilution and repurchases and can be selected as the controlling classification basis.

<a id="classification-basis"></a>
### Classification Basis
The free-cash-flow measure whose growth rate controls the growth screen: the total measure or the per-share measure.

The total is the default (`total_fcf`) and the per-share measure is the alternative (`fcf_per_share`). Both measures remain visible regardless of the choice.

<a id="fcf-classification"></a>
### FCF Classification
The growth screen's three outcomes: pass when required growth rates are positive, fail when complete evidence shows a nonpositive rate, indeterminate when no classification can be made.

`PASS` means required growth rates are positive; `FAIL` means complete, meaningful evidence includes a nonpositive required rate; `INDETERMINATE` means the required classification cannot be made from admissible evidence. These are distinct from software execution status.

<a id="fcf-yield"></a>
### FCF Yield
Latest completed annual free cash flow divided by market capitalization at the boundary, expressed as a percentage.

Its numerator covers a completed year and its denominator is taken at the boundary; it is informational only in the current method.

<a id="forward-policy"></a>
### Forward Policy
The rule for how optional analyst-consensus EPS estimates for the next two fiscal years are treated: display only, confirmation or hard gate.

The code values are `display_only`, `confirmation`, and `hard_gate`. Only `hard_gate` can alter an otherwise passing historical classification.

---

## Piotroski F-Score Strategy terms

<a id="piotroski-strategy"></a>
### Piotroski F-Score Strategy
A financial-strength screen that runs nine pass/fail tests on three consecutive fiscal years of reported statements and counts those passed. It is not a valuation.

It follows the Piotroski nine-test structure but substitutes the net change in split-adjusted shares outstanding for the original equity-issuance signal. It is not an investment recommendation.

<a id="f-score"></a>
### F-Score
The number of the nine Piotroski tests passed, from 0 to 9.

It is shown as “*x* of *n*” with *n* the tests that could be decided, and is unavailable with fewer than six decided tests.

<a id="complete-and-partial-score"></a>
### Complete Score / Partial Score
A complete score rests on all nine tests. A partial score rests on six to eight, because the other tests are unavailable.

A partial score is shown with the unavailable tests named, the usual reading of high and low scores does not apply to it, and it never enters a ranking.

<a id="unavailable-test"></a>
### Unavailable Test
A Piotroski test that cannot be decided because an input is missing or incompatible. It is never counted as a fail.

<a id="roa"></a>
### ROA (Return on Assets)
In the F-Score, a year's net income divided by total assets at the start of that year.

<a id="current-ratio"></a>
### Current Ratio
Current assets divided by current liabilities at a fiscal year-end.

<a id="gross-margin"></a>
### Gross Margin
Gross profit divided by sales for a fiscal year.

<a id="asset-turnover"></a>
### Asset Turnover
In the F-Score, a year's sales divided by total assets at the start of that year.

<a id="net-dilution"></a>
### Net Dilution
The change in the number of common shares outstanding between two fiscal year-ends, after buybacks.

The F-Score's dilution test passes when the count did not rise.

---

## Command-line terms
<!-- help:exclude -->

These entries explain terms that matter to people who run the engine from a command line or a script.

<a id="cli"></a>
### CLI (Command-Line Interface)
The text-based commands used to run the project.

An example is `ian graham-number TICKER`.

<a id="api"></a>
### API (Application Programming Interface)
A defined way for software components or services to exchange requests and responses.

A provider API may supply quotes, financial facts, or macro data.

<a id="json"></a>
### JSON (JavaScript Object Notation)
A widely used text format for structured data made from objects, arrays, names, strings, numbers, booleans, and null values.

Investment Analysis Engine uses JSON for its `--json` machine-readable presentation mode and for other structured software interfaces.

<a id="machine-readable-output"></a>
### Machine-Readable Output
Structured output designed so another program can consume it reliably rather than being optimized primarily for a person to read.

Investment Analysis Engine currently provides machine-readable analysis output using [JSON](#json) through the `--json` presentation mode.

Machine-readable output may intentionally retain stable identifiers such as snake_case field names because those identifiers form part of a programmatic contract.

<a id="uuid"></a>
### UUID (Universally Unique Identifier)
A widely used identifier format.

The project uses UUIDs for values such as run or event identifiers where globally unique correlation is useful.

<a id="sqlite"></a>
### SQLite
The embedded relational database selected for the project's production persistence layer.

<a id="light-mode"></a>
### Light Mode
The recommended operating mode for modest hardware, using a single model tier.

<a id="full-dual-tier-mode"></a>
### Full Dual-Tier Mode
An optional local configuration that uses a fast execution tier plus a larger deep-reasoning tier.

<a id="llm"></a>
### LLM (Large Language Model)
The AI model used for planning, tool selection and narrative synthesis. Financial calculations remain deterministic and are never done by the model.
