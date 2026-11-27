# Glossary

This glossary defines the finance and analysis terms used in this application. Formula details and authoritative calculation semantics live in [Financial Math & Data Conventions](FINANCE_MATH.md). Terms for people who work on the code are in the [Contributor Glossary](../project/CONTRIBUTOR_GLOSSARY.md); terms for people who use the command line are in the last section of this page.

---

## Analysis strategies and results

<a id="analysis-strategy"></a>
### Analysis Strategy
A rule-based way of analyzing a security, with its own inputs, calculation and way of reading the result. The same inputs always give the same result.

A strategy never leaves a calculation to an AI model. This glossary and the guides call the idea an analysis strategy.

Related terms: [method](#method), [typed evidence](#typed-evidence).

<a id="method"></a>
### Method
One calculation approach within an analysis strategy. A strategy may offer one method or several.

Several methods in one strategy are reserved for true variants of the same underlying calculation, such as a future Altman Z versus Z′′ strategy. They are not for strategies that merely address a related question with a different formula, the way Graham Number and Graham Growth Value do: each of those is its own strategy, not two methods of one.

A method is an application concept; it does not imply that Benjamin Graham or another source used the word “method” in exactly this project-specific sense.

Related terms: [analysis strategy](#analysis-strategy).

<a id="typed-evidence"></a>
### Typed Evidence
Information with named fields and stated data types, such as a value together with its units, source and dates. It is the opposite of free-form text.

“Typed evidence” is distinct from free-form model prose: an AI model may reason about it, but the model does not get to silently redefine or invent the underlying financial values.

<a id="applicability-status"></a>
### Applicability Status
Whether a method can be meaningfully calculated for a security, instead of forcing every security into a numeric result.

Results carry machine-readable statuses, including `ok`, `not_applicable`, `input_unavailable`, `invalid_input`, and `provider_error`.

<a id="not-applicable"></a>
### Not Applicable
A valid outcome meaning the method should not be used for the supplied facts, for example when earnings or book value per share is not positive.

The code value is `not_applicable`. It is not the same as a software failure or a zero valuation.

<a id="analysis-warning"></a>
### Analysis Warning
A note in one analysis result about something in that run that may affect how far you can rely on it, such as a value you entered instead of a data source's value, or a fallback the method had to use.

Warnings depend on the run: two runs of the same strategy can carry different warnings, or none.

Related terms: [analysis limitation](#analysis-limitation).

<a id="analysis-limitation"></a>
### Analysis Limitation
A caveat about what an analysis strategy's method can and cannot tell you, such as that a passing result is not an investment recommendation.

Most limitations come with every result of a strategy, and a few appear only when the data the method used calls for them. A limitation is not a sign of a problem with the run.

Related terms: [analysis warning](#analysis-warning).

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

A run is saved when you ask for it, and a refresh saves one for every entry it runs. Showing a saved Analysis Run always replays its own captured evidence; it never re-fetches data or recalculates, so it keeps showing the same result even if a data source or your configuration changes afterward.

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

Related terms: [entry](#entry).

<a id="headline"></a>
### Headline
The few values a strategy picks to stand for one analysis run, so that runs can be compared side by side. It summarizes the run; it is not the full result.

A value the run could not calculate is shown as a dash.

<a id="refresh"></a>
### Refresh
Running every entry of a watchlist, or of a list of entries that belongs to no watchlist, and saving each result as its own analysis run.

A refresh limits how many tickers run at once, and one ticker's failure never stops the rest of the refresh.

<a id="refresh-event"></a>
### Refresh Event
A progress record of a refresh: one is recorded when an entry starts running and one when it finishes.

A finished event carries the entry's result. A refresh runs one entry at a time or several at once, so events of different entries can interleave.

<a id="headline-unavailable"></a>
### Headline Unavailable
The reason a saved run has no headline in a side-by-side comparison: it was stored under an older version, its strategy is no longer available, or it stored no result.

A run stored under an older version is kept but not read by this version. A run of a strategy that is no longer available shows only its outcome. A run that stored no result has an outcome but nothing to summarize. The comparison shows a dash for the missing cells.

Related terms: [headline](#headline).

---

## Market data and timing

<a id="data-provider"></a>
### Data Source
An external or local source of market prices, company financial facts or economic-series observations. Examples are a quote service, a financial-statements service and a macroeconomic data service.

<a id="sec"></a>
### SEC
The United States Securities and Exchange Commission, the federal securities regulator. Its public data is a source of company financial facts for the analyses.

The SEC's website is at [sec.gov](https://www.sec.gov/).

<a id="edgar"></a>
### EDGAR
The SEC's Electronic Data Gathering, Analysis, and Retrieval system, which gives public access to company filings and structured filing data.

See the SEC's [EDGAR search resources](https://www.sec.gov/search-filings) and [Accessing EDGAR Data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data). Which companies it lists is explained in [SEC EDGAR ticker list](#sec-ticker-list).

<a id="sec-ticker-list"></a>
### SEC EDGAR Ticker List
The SEC's list of the companies that file with it, each under its US ticker symbol.

A company listed on an exchange outside the United States appears only under its US symbol, if it has one. Nutrien is NTR on the New York Stock Exchange, and NTR.TO on the Toronto Stock Exchange is not in the list. A company that does not file with the SEC is not in it at all. An analysis that reads a company's financial statements from SEC filings finds the company through this list, so it is unavailable for a ticker the list does not include. See [EDGAR](#edgar) and [listing venue](#listing-venue).

<a id="cache"></a>
### Cache
A stored copy of previously retrieved data. A stored value is reused only if it satisfies the requested as-of date and the freshness policy.

Otherwise the value is fetched from an allowed data source, or the input is reported unavailable. Caching is automatic and distinct from saving an [Analysis Run](#analysis-run), which is optional and durable.

Related terms: [cache states](#cache-states).

<a id="cache-states"></a>
### Cache Hit / Cache Miss / Stale Cache Entry
A cache hit finds a valid stored value to reuse, a cache miss finds none, and a stale entry exists but is too old to be treated as current.

A stale cache entry exists but is too old or otherwise outside the active policy, so it cannot silently be treated as current.

<a id="historical-market-data"></a>
### Historical Market Data
A time-indexed series of market observations, such as daily prices, used for time-series calculations such as Momentum.

<a id="current-quote"></a>
### Current Quote / Current Market Price
A market price taken as of now, used for comparison with a valuation. For a historical as-of date, it is usable only if the data source can establish a price at or before that date.

For an analysis with an explicit historical [as-of date](#as-of-date), a quote is usable only if the selected data source can establish an eligible observation at or before that boundary. A source that gives only current quotes therefore gives no quote for a historical as-of date, and today's price is never substituted.

The report calls this the latest available quote. Retrieval time records when the data source's answer was obtained; market observation time records when the market price was observed, if actually supplied. A five-minute response-reuse bound does not prove that the underlying trade is five minutes old. Quotes from Yahoo Finance keep their retrieval time and report the market observation time as unknown.

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

This application keeps a durable copy of an instrument profile and can show it without contacting a data source. A stored profile expires after a configured freshness window and is looked up again live when it does, and a lookup can also be asked for directly. A profile includes the [quote currency](#quote-currency) of the listing. If a refresh finds a genuinely different entity behind the same ticker — a **ticker reuse**, such as a delisting followed by a new listing under the same symbol — the prior profile is retired rather than overwritten, and every Analysis Run that already used it keeps showing that original entity: reopening an old result never relabels it using the ticker's current meaning.

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

Provenance can include source kind, data source, source field, observation period, retrieval time, calculation steps, and whether the value was overridden.

<a id="as-of-date"></a>
### As-of Date
The time boundary for an analysis or an input: information that became available after that date is not used.

A requested analysis boundary (`as_of`) prevents the resolver from using observations or information that became available after that date.

Related terms: [UTC](#utc), [data vintage](#data-vintage).

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
A value you supply yourself instead of accepting the value found from the cache or a data source. An override takes precedence over every other source and is identified in provenance.

<a id="resolution-precedence"></a>
### Resolution Precedence
The order in which sources are tried for each financial value: your override, then a valid cache entry, then a configured data source, then an explicit statement that the value is unavailable.

<a id="utc"></a>
### UTC (Coordinated Universal Time)
The common time standard used for unambiguous timestamps across systems and time zones.

<a id="source-kind"></a>
### Input Source
How a resolved input value was obtained: you supplied it as an override, it came from the cache, it was fetched from a data source, or it was derived from other inputs.

The source is kept with every input so that a saved run can show where each figure came from. See [override](#override), [cache](#cache) and [provenance](#provenance).

Related terms: [resolution precedence](#resolution-precedence), [financial facts](#financial-facts), [macro series](#macro-series).

<a id="period-kind"></a>
### Period Kind
The kind of reporting period behind a financial fact: a completed fiscal year, a quarter, the trailing twelve months, or a single instant.

A completed annual fact covers one fiscal year. A quarterly fact covers one quarter, and a trailing-twelve-month fact covers the twelve months ending at a quarter. An instant fact is a balance measured on one date, such as a share count or total debt. A calculation uses only the kind its method needs. See [reporting period](#reporting-period) and [TTM](#ttm).

<a id="accounting-scope"></a>
### Accounting Scope
Whether a financial figure covers the whole consolidated group, the parent company alone, or one segment of the business.

The scope is recorded with the figure, so a consolidated figure is not mistaken for a parent-company or segment figure.

<a id="capex-sign-convention"></a>
### Capital Expenditure Sign
How a data source writes capital expenditures: as a positive amount of spending or as a negative cash outflow.

The convention is recorded so that free cash flow subtracts spending once, whichever sign the data source used. When the convention is missing the figure is ambiguous and is not used. See [capital expenditures](#capital-expenditures) and [free cash flow](#free-cash-flow).

<a id="instrument-kind"></a>
### Instrument Kind
The kind of security a ticker names: an equity, an exchange-traded fund or a cryptocurrency.

A strategy that is built for company financial statements reports an instrument kind it does not cover as not applicable. See [instrument profile](#instrument-profile).

The kinds are explained in [Equity](#instrument-kind-equity), [ETF](#instrument-kind-etf) and [Cryptocurrency](#instrument-kind-cryptocurrency).

<a id="instrument-kind-equity"></a>
### Equity
A share of ownership in a company, such as a common stock.

An equity is the kind of instrument that the strategies built for company financial statements cover. See [instrument kind](#instrument-kind).

<a id="instrument-kind-etf"></a>
### ETF
An exchange-traded fund: a fund that holds a collection of securities and is bought and sold on an exchange like a share.

An ETF has no financial statements of its own, so a strategy built for company financial statements reports it as not applicable. See [instrument kind](#instrument-kind).

<a id="instrument-kind-cryptocurrency"></a>
### Cryptocurrency
A digital currency or token whose price is quoted on cryptocurrency markets.

A cryptocurrency has no financial statements, so a strategy built for company financial statements reports it as not applicable. See [instrument kind](#instrument-kind).

<a id="listing-venue"></a>
### Listing Venue
The market where an instrument's shares or units are listed for trading, written as the data source reports it.

You see the data source's own wording and, when this application recognizes that wording, the name of the market it stands for. A venue it does not recognize is shown in the data source's words alone, and this entry explains it. The venue is as the data source reports it, and two data sources can report different venues for the same ticker. A cryptocurrency is not listed on an exchange, and a data source's venue text for one may name where its price comes from rather than an exchange. See [instrument profile](#instrument-profile) and [security identity](#security-identity).

The markets this application recognizes are explained in [Nasdaq Stock Market](#listing-venue-nasdaq), [New York Stock Exchange](#listing-venue-nyse), [NYSE Group Exchange](#listing-venue-nyse-group), [NYSE Arca](#listing-venue-nyse-arca), [NYSE American](#listing-venue-nyse-american), [Cboe U.S. Equities Exchange](#listing-venue-cboe), [Cboe BZX Exchange](#listing-venue-cboe-bzx), [Texas Stock Exchange](#listing-venue-txse), [Over-the-Counter Market](#listing-venue-otc), [Toronto Stock Exchange](#listing-venue-tsx), [TSX Venture Exchange](#listing-venue-tsxv), [Cboe Canada](#listing-venue-cboe-canada) and [Canadian Securities Exchange](#listing-venue-cse).

<a id="listing-venue-nasdaq"></a>
### Nasdaq Stock Market
The Nasdaq Stock Market, a national securities exchange in the United States, with the market identifier code XNAS.

Nasdaq lists companies in three tiers: the Global Select Market, the Global Market and the Capital Market. Its listing standards (size, financial and liquidity requirements) are strictest for the Global Select Market, and the Capital Market serves smaller companies. A company's tier is a rough sign of its size and trading liquidity, not a rating. Data sources write the tiers as NasdaqGS, NasdaqGM and NasdaqCM. See [listing venue](#listing-venue).

<a id="listing-venue-nyse"></a>
### New York Stock Exchange
The New York Stock Exchange, a national securities exchange in the United States, with the market identifier code XNYS.

It is the oldest and largest of the exchanges that carry the NYSE name, and it lists many of the largest US companies. See [listing venue](#listing-venue) and [NYSE Group Exchange](#listing-venue-nyse-group).

<a id="listing-venue-nyse-group"></a>
### NYSE Group Exchange
One of the exchanges of the NYSE group, which the data source names as NYSE without saying which one.

The group runs the New York Stock Exchange, NYSE American and NYSE Arca, all national securities exchanges in the United States. The data source does not say which of them the security is listed on, so only the group is shown. See [New York Stock Exchange](#listing-venue-nyse), [NYSE American](#listing-venue-nyse-american), [NYSE Arca](#listing-venue-nyse-arca) and [listing venue](#listing-venue).

<a id="listing-venue-nyse-arca"></a>
### NYSE Arca
NYSE Arca, a national securities exchange in the United States, with the market identifier code ARCX.

Many exchange-traded funds are listed on NYSE Arca. See [ETF](#instrument-kind-etf) and [listing venue](#listing-venue).

<a id="listing-venue-nyse-american"></a>
### NYSE American
NYSE American, a national securities exchange in the United States, with the market identifier code XASE.

It lists mostly smaller companies, and it was formerly called the American Stock Exchange. See [listing venue](#listing-venue).

<a id="listing-venue-cboe"></a>
### Cboe U.S. Equities Exchange
One of the Cboe group's national securities exchanges for stocks in the United States, which the data source names as Cboe without saying which one.

The Cboe group runs four such exchanges: Cboe BZX (market identifier code BATS), Cboe BYX (BATY), Cboe EDGX (EDGX) and Cboe EDGA (EDGA). The data source does not say which of them the security is listed on, so only the group is shown. Many bitcoin and volatility funds are listed there. See [Cboe BZX Exchange](#listing-venue-cboe-bzx) and [listing venue](#listing-venue).

<a id="listing-venue-cboe-bzx"></a>
### Cboe BZX Exchange
Cboe BZX Exchange, a national securities exchange in the United States, with the market identifier code BATS.

It is the Cboe group's main exchange for listing stocks and funds. See [Cboe U.S. Equities Exchange](#listing-venue-cboe) and [listing venue](#listing-venue).

<a id="listing-venue-txse"></a>
### Texas Stock Exchange
The Texas Stock Exchange, a national securities exchange in the United States, with the market identifier code TXSE.

It is a new exchange, and some companies list on it as well as on an older exchange. See [listing venue](#listing-venue).

<a id="listing-venue-otc"></a>
### Over-the-Counter Market
The over-the-counter market in the United States, where brokers trade shares directly with each other instead of through a national securities exchange.

OTC Markets Group operates the main US over-the-counter quotation system, which the code OTCM names. OTCQX, OTCID and OTCPK (Pink) are tiers of OTC Markets Group's system, and SEC's list writes OTC without naming a tier. Over-the-counter shares usually trade less often than exchange-listed shares and face lighter listing and reporting requirements, so prices can move more and be harder to rely on. See [listing venue](#listing-venue).

<a id="listing-venue-tsx"></a>
### Toronto Stock Exchange
The Toronto Stock Exchange, Canada's main exchange for senior companies, with the market identifier code XTSE.

Many of Canada's largest companies are listed there, and some are also listed in the United States under a US ticker symbol. See [listing venue](#listing-venue) and [SEC EDGAR ticker list](#sec-ticker-list).

<a id="listing-venue-tsxv"></a>
### TSX Venture Exchange
The TSX Venture Exchange, a Canadian exchange for early-stage and smaller companies, with the market identifier code XTSX.

Its companies are usually smaller and trade less often than those on the Toronto Stock Exchange, and few of them file with the SEC. See [listing venue](#listing-venue) and [SEC EDGAR ticker list](#sec-ticker-list).

<a id="listing-venue-cboe-canada"></a>
### Cboe Canada
Cboe Canada, a Canadian exchange formerly called the NEO Exchange, with the market identifier code NEOE.

It lists companies and many exchange-traded funds. See [listing venue](#listing-venue) and [SEC EDGAR ticker list](#sec-ticker-list).

<a id="listing-venue-cse"></a>
### Canadian Securities Exchange
The Canadian Securities Exchange, a Canadian exchange for smaller and emerging companies, with the market identifier code XCNQ.

Its companies are usually small, and few of them file with the SEC. See [listing venue](#listing-venue) and [SEC EDGAR ticker list](#sec-ticker-list).

<a id="quote-freshness"></a>
### Quote Freshness
How recent the price quote behind a comparison is: recently retrieved, expired, of unknown retrieval time, dated in the future, supplied by you, or historical.

A recently retrieved quote is younger than the freshness limit and an expired quote is older. A quote with no recorded retrieval time is unknown, and one dated after the time of the analysis is a future timestamp. A quote you supplied as an override is user supplied. A quote read for a past as-of date is historical. See [current quote](#current-quote) and [retrieved at](#retrieved-at).

The values are explained in [Recently Retrieved Quote](#quote-recent), [Expired Quote](#quote-expired), [Quote With Unknown Retrieval Time](#quote-retrieval-unknown), [Future-Dated Quote](#quote-future-timestamp), [User-Supplied Quote](#quote-user-supplied), [Historical Quote](#quote-historical).

<a id="reporting-currency"></a>
### Reporting Currency
The currency a company states its financial figures in, written as a three-letter ISO 4217 code such as USD.

A method that combines figures with a price needs the filing currency and the [quote currency](#quote-currency) to agree. A selection can require annual facts in one reporting currency.

<a id="quote-currency"></a>
### Quote Currency
The currency a listing's price is quoted in, as the data source reports it, such as USD.

It can differ from the reporting currency of the company's statements. A data source may report a smaller unit of a currency, such as pence. See [reporting currency](#reporting-currency) and [instrument profile](#instrument-profile).

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

It is the standard Graham Number earnings basis, and the Graham Growth Value strategy's basis when it uses SEC EDGAR earnings data, reflecting Graham's defensive-investor emphasis on average earnings over the preceding three years.

<a id="normalized-eps"></a>
### Normalized EPS / Normal Earnings
Earnings adjusted by an explicit policy to reduce the effect of unusual or non-recurring items.

“Normalized” is not self-defining: every adjustment and period must be documented. The growth calculator accepts an EPS value on the explicitly selected basis; the software does not invent discretionary normalization adjustments.

<a id="fiscal-year"></a>
### Fiscal Year
A company's twelve-month accounting period, which may differ from the calendar year.

Annual EPS observations must therefore retain their fiscal-period dates.

<a id="anchor-filing"></a>
### Anchor Filing
The annual report an analysis rests on: the newest annual report the company had filed by the as-of date, for its newest completed fiscal year. Its fiscal year-end is the date every input is taken at.

The analysis reads the annual reports filed by the as-of date, starting from the newest. The first original report (not an amendment) fixes the fiscal year, and the anchor filing is the newest filing for that year, so an amendment of that year can be the anchor and an amendment of an older year never is. The anchor filing is **stale** when the next annual report was overdue at the as-of date and none had been filed: the as-of date is after the latest date it was due, counted from the fiscal year-end and never from the filing date. No warning is given early. See [fiscal year](#fiscal-year), [as-of date](#as-of-date) and [stale anchor](#reason-stale-anchor).

<a id="reporting-period"></a>
### Reporting Period
The span or date a financial fact applies to, such as a fiscal year, a quarter, a trailing twelve-month interval or a balance-sheet date.

<a id="stock-split-adjustment"></a>
### Stock Split Adjustment
Restating per-share values after the number of shares changes through a stock split or reverse split.

EPS, BVPS, and price must use compatible share bases.

Related terms: [split-adjusted close](#split-adjusted-close).

<a id="split-adjusted-close"></a>
### Split-Adjusted Close
A closing price restated for every stock split after its date, and for nothing else. A dividend paid later does not change it.

It is the price on the same basis as a share count scaled by those splits, and the two together give the market capitalization the shares and the price had on the day. It is not the dividend-adjusted close that the [Momentum](#momentum-strategy) series uses. A stock dividend appears in the data source's split history as a fractional split (1.05) and is treated like a split; it is not counted as new shares issued.

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

When it comes from SEC EDGAR data, it is derived from eligible fiscal-year-end balance-sheet components rather than read from a single reported figure.

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

Data sources write CapEx with different signs, so it is converted to a positive amount of spending and the conversion is kept in provenance.

From SEC filings the analysis uses purchases of property and equipment, or, for a filer that reports only the broader purchases of productive assets, that concept. It uses one of the two for a company, never both. The broader concept includes intangible assets such as software, and a result that uses it says so.

<a id="free-cash-flow"></a>
### Free Cash Flow (FCF)
The cash a company's operations generate in a year, minus what it spends on long-lived assets such as equipment.

In the Free Cash Flow & Earnings Growth strategy, it is completed annual operating cash flow minus normalized capital expenditures.

FCF is a non-GAAP analytical measure, so another data source may use a different definition.

<a id="weighted-average-diluted-shares"></a>
### Weighted-Average Diluted Shares
The average diluted share count for an earnings period, including the effect of potentially dilutive securities under the reported accounting basis.

It is not interchangeable with an ending shares-outstanding snapshot.

<a id="share-count-basis"></a>
### Share-Count Basis
Where a share count was taken from: the balance sheet at the fiscal year-end, or the cover page of the annual filing.

The year-end count is preferred. The cover-page count is used only when no balance-sheet path gives a count at the year-end, and the result says so. See [shares outstanding](#shares-outstanding) and [market capitalization](#market-capitalization).

<a id="split-adjustment-window"></a>
### Split-Adjustment Window
Where a data source's adjustment fell relative to the share count and the price: between the count and the price, or between the price and the date the data source adjusted to.

A recognizable split between the share count and the price is applied to the share count. An adjustment after the price date is always applied, because it undoes the data source's adjustment of the historical close. See [stock split adjustment](#stock-split-adjustment) and [market capitalization](#market-capitalization).

---

## Valuation and price comparison

<a id="valuation"></a>
### Valuation
Estimating what a security may be worth under a stated method and assumptions, usually to compare with its market price.

Here a valuation result is one method's reference value, such as the Graham Number's maximum indicated price, not a complete intrinsic-value conclusion or a recommendation (see [Intrinsic Value](#intrinsic-value) and [Reference Value](#reference-value)).

Related terms: [book value](#book-value), [tangible book value](#tangible-book-value), [common shareholders' equity](#common-shareholders-equity), [EBITDA](#ebitda), [enterprise value](#enterprise-value), [invested capital](#invested-capital), [normalized EPS](#normalized-eps).

<a id="intrinsic-value"></a>
### Intrinsic Value
An estimate of what an investment is economically worth under a stated model and assumptions, rather than its market price.

Different models can produce different intrinsic-value estimates. The Graham Number is never called an intrinsic value without qualification.

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

Related terms: [discount and premium](#discount-and-premium), [percentage point](#percentage-point).

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

<a id="price-comparison-status"></a>
### Price Comparison Status
Whether a comparison between a method's value and the price could be made: available when it could, unavailable when it could not.

An unavailable comparison leaves the [margin of safety](#margin-of-safety) without a value; it is never replaced by zero. See [price relationship](#price-relationship).

The values are explained in [Price Comparison Available](#price-comparison-available), [Price Comparison Unavailable](#price-comparison-unavailable).

---

## Momentum Strategy terms

<a id="momentum-strategy"></a>
### Momentum Strategy
A rule-based analysis of recent price behavior. It compares a short and a long simple moving average, reports a bullish or bearish trend, and shows RSI as a supporting indicator.

The moving-average windows are configurable. The strategy reports the state of the crossover of the two averages.

Related terms: [historical market data](#historical-market-data), [EMA](#ema).

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

The latest signal is one of three states: a bullish crossover, where the short average moved above the long one; a bearish crossover, where it moved below; or no new crossover, where neither happened.

The values are explained in [Bullish Crossover](#crossover-bullish), [Bearish Crossover](#crossover-bearish), [No New Crossover](#crossover-none).

<a id="momentum-states"></a>
### Bullish / Bearish / Unknown
The trend a Momentum run reports: bullish when the short moving average is above the long one, bearish when it is not, unknown when they cannot be calculated.

The run's status is then `input_unavailable`.

The values are explained in [Bullish Trend](#trend-bullish), [Bearish Trend](#trend-bearish), [Unknown Trend](#trend-unknown).

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

<a id="price-basis"></a>
### Price Basis
Which close the current price is: the latest adjusted historical close, or the latest historical close without the adjustment.

The basis shows which price series the averages and the RSI were calculated from. Data sources revise adjusted prices after the fact, so an adjusted close can differ from the price quoted on that day.

<a id="trend-relationship"></a>
### Trend Relationship
How the short moving average stands against the long one: above it, below it or equal to it.

Above is the bullish reading of the [trend](#momentum-states); below or equal is the bearish reading. The relationship describes the latest observation, and a [crossover](#crossover) describes a change in it.

<a id="trend-bullish"></a>
### Bullish Trend
The short moving average is above the long one at the latest observation, so the trend is read as bullish.

Only the latest observation counts; a bullish trend is not a new crossover. See [Bullish / Bearish / Unknown](#momentum-states) for the whole set of values.

<a id="trend-bearish"></a>
### Bearish Trend
The short moving average is not above the long one at the latest observation, so the trend is read as bearish.

The averages can be equal, which is also read as bearish. See [Bullish / Bearish / Unknown](#momentum-states) for the whole set of values.

<a id="trend-unknown"></a>
### Unknown Trend
The trend could not be calculated, because the moving averages are not available.

The run's status is then input unavailable. See [Bullish / Bearish / Unknown](#momentum-states) for the whole set of values.

<a id="crossover-bullish"></a>
### Bullish Crossover
The relationship moved into the bullish one since the previous observation: the short moving average rose above the long one.

It needs two consecutive valid pairs of averages. See [Crossover](#crossover) for the whole set of values.

<a id="crossover-bearish"></a>
### Bearish Crossover
The relationship moved out of the bullish one since the previous observation: the short moving average stopped being above the long one.

It needs two consecutive valid pairs of averages. See [Crossover](#crossover) for the whole set of values.

<a id="crossover-none"></a>
### No New Crossover
Neither a bullish nor a bearish transition happened at the latest observation.

It is a verified absence of transition, which differs from history too short to tell. See [Crossover](#crossover) for the whole set of values.

---

## Graham Number Strategy terms

<a id="graham-number-strategy"></a>
### Graham Number Strategy
A screening strategy that combines positive earnings per share and book value per share to estimate a conservative maximum indicated price.

It is independent of Graham Growth Value: a different strategy with a different formula, not an alternative method of the same one. It reads the company's financial statements from SEC filings; see [SEC EDGAR ticker list](#sec-ticker-list).

Related terms: [Graham Number factor](#graham-number-factor), [defensive investor](#defensive-investor).

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

It is independent of the Graham Number: a different strategy with a different formula, not an alternative method of the same one. The growth rate and the yield are assumptions you supply. It reads the company's financial statements from SEC filings; see [SEC EDGAR ticker list](#sec-ticker-list).

Related terms: [Graham growth-value formula](#growth-value-formula), [growth multiplier](#growth-multiplier), [base P/E](#base-pe), [growth-estimation policy](#growth-estimation-policy), [AAA corporate bond yield](#aaa-corporate-bond-yield), [baseline AAA yield](#baseline-aaa-yield), [current AAA yield](#current-aaa-yield).

<a id="expected-growth-rate"></a>
### Expected Growth Rate
The assumed annual earnings-growth rate used by the Graham Growth Value strategy, in percentage points: 6.5 means 6.5%. Its source and horizon must be reported.

It is written `g` in the formula, and its policy must be reported.

<a id="growth-estimation-policy"></a>
### Growth-Estimation Policy
The explicit rule that supplies the expected growth rate. The application supports only a growth assumption that you provide.

A language model, a data source or a silent default never invents growth.

<a id="aaa-corporate-bond-yield"></a>
### AAA Corporate Bond Yield
The yield on a documented series of highest-rated corporate debt, used by the Graham Growth Value strategy.

No live series is connected yet, so the strategy takes a yield you supply.

<a id="baseline-aaa-yield"></a>
### Baseline AAA Yield
The reference AAA yield, 4.4 by default, that the Graham Growth Value formula compares the current AAA yield against.

It is configurable formula normalization, not a current market observation.

<a id="current-aaa-yield"></a>
### Current AAA Yield
The AAA corporate-bond yield used in the denominator of the growth-value formula. It must be strictly positive.

It is a value you supply and is identified as such.

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

<a id="eps-basis"></a>
### EPS Basis
Which earnings figure a valuation uses: the three-year average, or the earnings of one completed fiscal year.

The three-year average smooths a single unusual year. The fiscal-year basis uses one year's earnings as reported.

The values are explained in [Three-Year-Average EPS](#three-year-average-eps), [Fiscal-Year EPS](#fiscal-year-eps).

<a id="fiscal-year-eps"></a>
### Fiscal-Year EPS
The earnings per share of one completed fiscal year, as reported, used instead of a three-year average.

See [EPS Basis](#eps-basis) for the whole set of values.

---

## Free Cash Flow & Earnings Growth Strategy terms

<a id="fcf-growth-strategy"></a>
### Free Cash Flow & Earnings Growth Strategy
A historical screen asking whether free cash flow and diluted EPS both grew at positive, meaningful compound annual rates over one compatible period. It is not a valuation.

It returns `PASS`, `FAIL`, or `INDETERMINATE`, and it is not an investment recommendation. It reads the company's financial statements from SEC filings; see [SEC EDGAR ticker list](#sec-ticker-list).

Related terms: [total-company FCF](#total-company-fcf), [FCF per diluted share](#fcf-per-diluted-share), [weighted-average diluted shares](#weighted-average-diluted-shares), [operating cash flow](#operating-cash-flow).

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

The values are explained in [Total FCF Basis](#classification-basis-total-fcf), [FCF-per-Share Basis](#classification-basis-fcf-per-share).

<a id="fcf-classification"></a>
### FCF Classification
The growth screen's three outcomes: pass when required growth rates are positive, fail when complete evidence shows a nonpositive rate, indeterminate when no classification can be made.

`PASS` means required growth rates are positive; `FAIL` means complete, meaningful evidence includes a nonpositive required rate; `INDETERMINATE` means the required classification cannot be made from admissible evidence. These are distinct from software execution status.

The values are explained in [FCF Growth Pass](#fcf-growth-pass), [FCF Growth Fail](#fcf-growth-fail), [FCF Growth Indeterminate](#fcf-growth-indeterminate).

<a id="fcf-yield"></a>
### FCF Yield
Latest completed annual free cash flow divided by market capitalization at the boundary, expressed as a percentage.

Its numerator covers a completed year and its denominator is taken at the boundary; it is informational only in the current method.

<a id="forward-policy"></a>
### Forward Policy
The rule for how optional analyst-consensus EPS estimates for the next two fiscal years are treated: display only, confirmation or hard gate.

The code values are `display_only`, `confirmation`, and `hard_gate`. Only `hard_gate` can alter an otherwise passing historical classification.

The values are explained in [Display-Only Policy](#forward-policy-display-only), [Confirmation Policy](#forward-policy-confirmation), [Hard-Gate Policy](#forward-policy-hard-gate).

<a id="forward-evidence-status"></a>
### Forward Evidence Status
How complete the analyst-consensus evidence is: complete when every estimate was found, partial when only some were, unavailable when none was.

Forward evidence is optional. Whether it can change the result is set by the [forward policy](#forward-policy). See [analyst consensus estimate](#analyst-consensus-estimate).

The values are explained in [Complete Forward Evidence](#forward-evidence-complete), [Partial Forward Evidence](#forward-evidence-partial), [Unavailable Forward Evidence](#forward-evidence-unavailable).

<a id="historical-horizon"></a>
### Historical Horizon
The number of elapsed years of history the growth screen looks back over: three, four or five, or the longest available.

The default picks the longest history available, up to five years. A longer horizon needs more consecutive annual facts and is unavailable when there are too few.

The values are explained in [Longest Available Horizon](#historical-horizon-longest-available), [Three-Year Horizon](#historical-horizon-three-years), [Four-Year Horizon](#historical-horizon-four-years), [Five-Year Horizon](#historical-horizon-five-years).

<a id="growth-trend"></a>
### Growth Trend
How free cash flow growth and earnings growth compare over the screened period: both growing, only one growing, neither growing, or too little meaningful data to say.

The trend is evidence and not a score. Both growing and neither growing mean what they say. Free cash flow growing without earnings, or earnings growing without free cash flow, names the one that grew. The last value means a growth rate could not be calculated meaningfully. See [free cash flow](#free-cash-flow) and [CAGR](#cagr).

The values are explained in [Both Growing](#growth-trend-both), [Only Free Cash Flow Growing](#growth-trend-fcf-only), [Only Earnings Growing](#growth-trend-earnings-only), [Neither Growing](#growth-trend-neither), [Insufficient Growth Evidence](#growth-trend-insufficient).

<a id="classification-basis-total-fcf"></a>
### Total FCF Basis
The growth screen is decided by the growth of the company's total free cash flow. This is the default.

See [Classification Basis](#classification-basis) for the whole set of values.

<a id="classification-basis-fcf-per-share"></a>
### FCF-per-Share Basis
The growth screen is decided by the growth of free cash flow per diluted share, which reflects changes in the share count.

See [Classification Basis](#classification-basis) for the whole set of values.

<a id="fcf-growth-pass"></a>
### FCF Growth Pass
The growth screen passes: the free cash flow and diluted EPS growth rates are both meaningful and above zero, and any forward hard gate is met.

It is a screen result, not a valuation or a recommendation. See [FCF Classification](#fcf-classification) for the whole set of values.

<a id="fcf-growth-fail"></a>
### FCF Growth Fail
The screen fails: a historical growth rate of free cash flow or diluted EPS is zero or negative, or, under the hard gate, forward consensus growth is not positive in both years.

It is a screen result, not a valuation or a recommendation. See [FCF Classification](#fcf-classification) for the whole set of values.

<a id="fcf-growth-indeterminate"></a>
### FCF Growth Indeterminate
The screen cannot be decided, because a required growth rate could not be calculated or is not meaningful, or the hard gate lacks complete consensus evidence.

It is not a failed screen: the classification cannot be made from the evidence the analysis may use. See [FCF Classification](#fcf-classification) for the whole set of values.

<a id="forward-policy-display-only"></a>
### Display-Only Policy
Analyst-consensus estimates are shown when available and never change the growth screen's result. This is the default.

See [Forward Policy](#forward-policy) for the whole set of values.

<a id="forward-policy-confirmation"></a>
### Confirmation Policy
The result reports whether the estimates confirm positive growth in both forward years, without changing the growth screen's result.

See [Forward Policy](#forward-policy) for the whole set of values.

<a id="forward-policy-hard-gate"></a>
### Hard-Gate Policy
The screen passes only when the estimates show positive growth in both forward years; without complete estimates the result is indeterminate.

See [Forward Policy](#forward-policy) for the whole set of values.

<a id="forward-evidence-complete"></a>
### Complete Forward Evidence
The latest actual EPS and both consensus estimates were found, and both growth intervals between them could be calculated.

See [Forward Evidence Status](#forward-evidence-status) for the whole set of values.

<a id="forward-evidence-partial"></a>
### Partial Forward Evidence
At least one consensus estimate was found, but not enough to calculate both growth intervals.

See [Forward Evidence Status](#forward-evidence-status) for the whole set of values.

<a id="forward-evidence-unavailable"></a>
### Unavailable Forward Evidence
No usable consensus estimate was found, so the forward evidence is empty.

No source of consensus estimates is approved yet, so this is the usual value. See [Forward Evidence Status](#forward-evidence-status) for the whole set of values.

<a id="historical-horizon-longest-available"></a>
### Longest Available Horizon
Growth is measured over the longest span the history allows: five elapsed years when there is enough history, otherwise four, otherwise three. This is the default.

See [Historical Horizon](#historical-horizon) for the whole set of values.

<a id="historical-horizon-three-years"></a>
### Three-Year Horizon
Growth is measured over exactly three elapsed years, which needs four consecutive fiscal years of figures; with fewer, the screen does not fall back to a shorter span.

See [Historical Horizon](#historical-horizon) for the whole set of values.

<a id="historical-horizon-four-years"></a>
### Four-Year Horizon
Growth is measured over exactly four elapsed years, which needs five consecutive fiscal years of figures; with fewer, the screen does not fall back to a shorter span.

See [Historical Horizon](#historical-horizon) for the whole set of values.

<a id="historical-horizon-five-years"></a>
### Five-Year Horizon
Growth is measured over exactly five elapsed years, which needs six consecutive fiscal years of figures; with fewer, the screen does not fall back to a shorter span.

See [Historical Horizon](#historical-horizon) for the whole set of values.

<a id="growth-trend-both"></a>
### Both Growing
Free cash flow and diluted EPS both increased over the measured period.

See [Growth Trend](#growth-trend) for the whole set of values.

<a id="growth-trend-fcf-only"></a>
### Only Free Cash Flow Growing
Free cash flow increased over the measured period, but diluted EPS did not.

See [Growth Trend](#growth-trend) for the whole set of values.

<a id="growth-trend-earnings-only"></a>
### Only Earnings Growing
Diluted EPS increased over the measured period, but free cash flow did not.

See [Growth Trend](#growth-trend) for the whole set of values.

<a id="growth-trend-neither"></a>
### Neither Growing
Neither free cash flow nor diluted EPS increased over the measured period.

See [Growth Trend](#growth-trend) for the whole set of values.

<a id="growth-trend-insufficient"></a>
### Insufficient Growth Evidence
At least one of the two growth rates, of free cash flow and of diluted EPS, could not be calculated or is not meaningful, so the trend cannot be described.

Without both rates the analysis cannot say which of the two grew. See [Growth Trend](#growth-trend) for the whole set of values.

---

## Piotroski F-Score Strategy terms

<a id="piotroski-strategy"></a>
### Piotroski F-Score Strategy
A financial-strength screen that runs nine pass/fail tests on three consecutive fiscal years of reported statements and counts those passed. It is not a valuation.

It follows the Piotroski nine-test structure but substitutes the net change in split-adjusted shares outstanding for the original equity-issuance signal. It is not an investment recommendation. It reads the company's financial statements from SEC filings; see [SEC EDGAR ticker list](#sec-ticker-list).

Related terms: [ROA](#roa), [current ratio](#current-ratio), [gross margin](#gross-margin), [asset turnover](#asset-turnover), [net dilution](#net-dilution).

<a id="f-score"></a>
### F-Score
The number of the nine Piotroski tests passed, from 0 to 9.

It is shown as “*x* of *n*” with *n* the tests that could be decided, and is unavailable with fewer than six decided tests.

<a id="complete-and-partial-score"></a>
### Complete Score / Partial Score
A complete score rests on all nine tests. A partial score rests on six to eight, because the other tests are unavailable.

A partial score is shown with the unavailable tests named, the usual reading of high and low scores does not apply to it, and it never enters a ranking.

The values are explained in [Complete Score](#score-complete), [Partial Score](#score-partial).

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

<a id="test-result"></a>
### Test Result
The result of one test of the score: a pass when its condition holds and a fail when it does not.

A test that cannot be decided is not a fail; it is an [unavailable test](#unavailable-test). The [F-Score](#f-score) counts the passes.

The values are explained in [Passed Test](#test-passed), [Failed Test](#test-failed).

<a id="test-passed"></a>
### Passed Test
A Piotroski F-Score test whose condition holds. It adds one point to the score.

See [Test Result](#test-result) for the whole set of values.

<a id="test-failed"></a>
### Failed Test
A Piotroski F-Score test whose condition does not hold. It adds nothing to the score.

See [Test Result](#test-result) for the whole set of values.

<a id="score-complete"></a>
### Complete Score
A score that rests on all nine tests.

See [Complete Score / Partial Score](#complete-and-partial-score) for the whole set of values.

<a id="score-partial"></a>
### Partial Score
A score that rests on six to eight tests, because the others are unavailable.

See [Complete Score / Partial Score](#complete-and-partial-score) for the whole set of values.

---

## Outcomes, statuses and reasons

These entries explain the words an analysis uses to say how it went: the outcome of a run, the status of a
calculation or a metric, a data source failure, a failure code and the reason behind a missing value. A word that
means the same everywhere shares one entry.

<a id="outcome-completed"></a>
### Completed
A run outcome meaning the strategy calculated its result from the inputs it was given.

It is the outcome of a run whose calculation status is [ok](#status-ok). It says that a result exists, not that the result is favorable: a screen can complete and still report that a company failed it.

<a id="outcome-unavailable"></a>
### Unavailable
A run outcome meaning the analysis could not be calculated because an input it needs was not available.

It is the outcome of a run whose calculation status is [input unavailable](#status-input-unavailable), which includes a run whose data source answered and had nothing for a required input, such as an unknown ticker. The run is saved so that it can be revisited; nothing is estimated or replaced by zero.

<a id="outcome-failed"></a>
### Failed
A run outcome meaning the analysis stopped because an input was invalid or a data source failed. No result was produced.

It is the outcome of a run whose calculation status is [invalid input](#status-invalid-input) or [data source error](#status-provider-error). The run's failure code says which. A data source that answered with nothing does not make a run failed; see [no data from the data source](#provider-no-data).

<a id="status-ok"></a>
### OK Status
The calculation finished: every required input was found and the value could be calculated.

It is the calculation status that gives a run the outcome [completed](#outcome-completed). For a single metric it means the metric has a value.

<a id="status-unavailable"></a>
### Unavailable Metric
A single metric that could not be calculated, usually because an input it needs is missing. It shows no value, and nothing takes its place.

A metric that is unavailable usually comes with a reason code that says why. See [Applicability Status](#applicability-status).

<a id="status-input-unavailable"></a>
### Input Unavailable
A required input could not be found for the date and the data the analysis was asked to use. The analysis is not calculated rather than guessed.

It is the calculation status of an [unavailable run](#outcome-unavailable). It is also the category of a failure whose data could not be used, such as a data-quality failure, a lack of observations or a data source that answered with nothing for a required input.

<a id="status-invalid-input"></a>
### Invalid Input
A value given to the analysis, or read from a data source, is not valid, so the analysis cannot be calculated.

It is the calculation status that makes a run [failed](#outcome-failed), and the failure code of the same name. The shown message says only that the inputs or the data source's data were invalid; the details are kept in this application's log.

<a id="status-provider-error"></a>
### Data Source Error
A data source failed in a way that is not an absent answer, so the analysis could not be calculated.

It is the calculation status that makes a run [failed](#outcome-failed). The failure code `provider_error` is used when the data source's failure could not be classified; a classified failure has its own entry: [unreachable](#provider-unreachable), [rate-limited](#provider-rate-limited) or [unexpected response](#provider-unexpected-response). A data source that answered with nothing is not a data source error; see [no data](#provider-no-data).

<a id="provider-unreachable"></a>
### Data Source Unreachable
The data source did not serve the request, because of a connection problem, a timeout, a block or a server error.

It says nothing about whether the data exists. The same request can succeed later.

<a id="provider-rate-limited"></a>
### Data Source Limiting Requests
The data source refused the request because it is limiting how many requests it accepts.

The analysis can be tried again after a pause.

<a id="provider-unexpected-response"></a>
### Unexpected Answer from a Data Source
The data source answered, but not in a form this application reads, so the answer could not be used.

The data source may have changed its format. Nothing in the answer is used.

<a id="provider-no-data"></a>
### No Data from the Data Source
The data source answered correctly and has nothing for this request.

Unlike an unreachable data source, the data source worked; it holds no data for what was asked. A run it stops is [unavailable](#outcome-unavailable), not failed, with the reason code `provider_no_data`, and the data source is still checked, so a mistyped ticker can be told from a data source that is down. A ticker that is not in SEC EDGAR's ticker list is the common case for an analysis that reads SEC filings; see [SEC EDGAR ticker list](#sec-ticker-list).

<a id="provider-healthy"></a>
### Data Source Answering Normally
A test request to the data source was answered normally.

The check is made after a failure to tell a problem with the data source from a problem with one ticker. See [data source](#data-provider).

<a id="provider-not-checked"></a>
### Data Source Not Checked
No test request was made to the data source, so nothing is known about its condition.

A data source is checked only when a failure suggests a problem with it.

<a id="failure-execution-error"></a>
### Unexpected Failure
The analysis failed in a way this application did not anticipate. The details are in this application's log, not in the message shown.

It is the code used for any failure that no other code describes.

<a id="failure-historical-quality"></a>
### Historical Data Quality Failure
The price history failed the data-quality checks, so it was not used.

The check names what was wrong with the data. It is not a data source outage: the data source answered, and the answer was rejected. Its category is [input unavailable](#status-input-unavailable).

<a id="failure-no-eligible-observations"></a>
### No Eligible Observations
No observation exists at or before the requested date, so the analysis has nothing to start from.

Asking for a date earlier than the first available data gives this failure. Its category is [input unavailable](#status-input-unavailable). See [as-of date](#as-of-date).

<a id="failure-configuration-error"></a>
### Configuration Error
A setting of this application prevents the analysis. The message says what to change.

The message is written for the person who set up this application.

<a id="failure-invalid-parameter"></a>
### Invalid Parameter
A value in the request, such as a ticker, a date or a window, was rejected before any analysis ran. The message names what was wrong.

Nothing was calculated or saved. Correct the named value and ask again.

<a id="failure-database"></a>
### Database Failure
The local database could not be used. The code says whether it needs an upgrade, is busy, cannot be read or written, or could not be set up.

Every code that begins with database is explained here, and the message shown says what to do:

- upgrade required: the database comes from an older version and needs a one-time upgrade, which keeps its data;
- incompatible schema: the database's structure does not match this version of the application;
- busy: the database could not be accessed within the wait, so close other operations and try again;
- permission denied: this application may not use the file or its folder;
- invalid file: the file is not a readable database, or it is corrupt;
- input or output error: the storage could not be accessed, so check the path, the space and the disk;
- resources unavailable: the files this application uses to set up or upgrade a database are missing or inconsistent;
- initialization failed: setting up a new database did not complete;
- migration failed: an upgrade did not complete and was rolled back.

<a id="failure-stored-data-unreadable"></a>
### Stored Data Unreadable
A saved run or watchlist entry cannot be read by this version of the application, so it cannot be shown or replayed.

A saved run may be malformed or may not match its summary. A watchlist entry's saved selection may be unreadable. A saved run may also have no replay in this version.

<a id="failure-unsupported-run-version"></a>
### Unsupported Run Version
A saved run was stored under an older version of its shape or method than this version of the application reads.

The run stays in the database and is refused by its version; it is never read as if it were current.

<a id="failure-not-found"></a>
### Not Found
The watchlist, entry, saved run, refresh job, help term, help document or address that was asked for does not exist.

Check the identifier. A refresh job exists only while the server that started it runs.

<a id="failure-instrument-profile-not-found"></a>
### Instrument Profile Not Found
No instrument profile is stored for the ticker, so there are no details to show.

A profile is stored the first time the ticker is analyzed or looked up. A profile kept by an earlier version of the application counts as absent until then. See [instrument profile](#instrument-profile).

<a id="entry-warning-ticker-not-recognized"></a>
### Ticker Not Recognized
When an entry was added, the data sources answered and none of them identified the ticker. The entry was still added.

A ticker that is mistyped, or no longer trades, is unavailable on every refresh. Check the ticker, and remove the entry if it is wrong. A data source sometimes answers nothing for a valid ticker, which is why the entry is kept. See [ticker](#ticker) and [no data from the data source](#provider-no-data).

<a id="entry-warning-ticker-not-checked"></a>
### Ticker Not Checked
When an entry was added, the ticker could not be checked, because a data source or this application's database was not available. The entry was still added.

The check asks the data sources about each new ticker once. After the data sources could not be reached, asked this application to wait, or the database was not available, the remaining tickers are not asked. Adding the entry again is not needed; a refresh shows whether the ticker works. See [data source unreachable](#provider-unreachable) and [data source limiting requests](#provider-rate-limited).

<a id="entry-warning-ticker-not-in-sec-list"></a>
### Ticker Not in SEC EDGAR's List
When an entry was added, the ticker was recognized but is not in SEC EDGAR's ticker list. The entry was still added.

The strategies of the new entries that read financial statements from SEC filings will be unavailable for this ticker. Strategies that use only prices still work. A company listed outside the United States may file with the SEC under its US ticker symbol; see [SEC EDGAR ticker list](#sec-ticker-list).

<a id="failure-watchlist-empty"></a>
### Empty Watchlist
The watchlist has no entries, so there is nothing to refresh.

Add an entry first. See [watchlist](#watchlist) and [refresh](#refresh).

<a id="failure-name-conflict"></a>
### Name Already in Use
A watchlist with that name already exists, so the name cannot be used again.

Choose another name, or change the existing watchlist.

<a id="failure-request-refused"></a>
### Request Refused
The local interface refused the request, because it carried no valid token or came from a host or origin that is not allowed.

The interface answers only the application that started it, on this computer.

<a id="failure-refresh-running"></a>
### Refresh Already Running
A refresh is already running, and only one runs at a time.

Wait for it to finish or stop it, then start the next one. See [refresh](#refresh).

<a id="failure-port-unavailable"></a>
### Port Unavailable
The local interface could not start, because the network port it was asked to use is not available.

Choose another port, or stop whatever is using this one.

<a id="failure-category-error"></a>
### Error Category
The category of a failure that is not about unusable data. The failure code says what went wrong.

The other category is [input unavailable](#status-input-unavailable). A failure that fits neither category is treated as this one.

<a id="reason-insufficient-history"></a>
### Insufficient History
The history does not cover enough periods for the calculation, or its periods are not consecutive.

Too few observations are not filled in, and a gap is not bridged. The value stays unavailable.

<a id="reason-missing-input"></a>
### Missing Input
A fact or an input the calculation needs is missing, so the value is not calculated rather than assumed.

The missing input can be a reported fact, the analyst consensus or the market capitalization. A missing figure is never replaced by zero.

<a id="reason-incompatible-inputs"></a>
### Incompatible Inputs
Two inputs cannot be combined because their reporting periods, units, currencies or scopes differ.

A scope can be the accounting scope or the filing taxonomy. Nothing is converted or substituted to make the inputs fit. See [period kind](#period-kind), [accounting scope](#accounting-scope) and [reporting currency](#reporting-currency).

<a id="reason-ambiguous-fact"></a>
### Ambiguous Fact
Facts conflict, or a fact cannot be identified reliably, so none of them is used.

Choosing one would be a guess. The value stays unavailable.

<a id="reason-not-available-as-of"></a>
### Not Available As Of
An input was not yet available on the as-of date, for example because it was filed or published after it.

No information from after the boundary is used. See [as-of date](#as-of-date) and [look-ahead bias](#look-ahead-bias).

<a id="reason-quote-timing-unusable"></a>
### Quote Timing Unusable
A price quote cannot be used because the time it was retrieved is unknown, it is dated in the future, or it is older than the quote freshness rules allow.

See [quote freshness](#quote-freshness).

<a id="reason-nonpositive-input"></a>
### Nonpositive Input
An input the formula needs is zero or negative, so the method does not apply to this company.

<a id="reason-override-only"></a>
### Override Only
Every input was supplied as an override and none came from a data source, so the analysis is not run.

<a id="reason-stale-anchor"></a>
### Stale Anchor
The market capitalization is not calculated: the newest annual report was overdue for replacement at the as-of date and none was filed.

The share count in that report is not the count at the as-of date. The run keeps its status and a warning states the fiscal year, the form and the date the next report was due. See [anchor filing](#anchor-filing).

<a id="reason-earlier-basis"></a>
### Earlier Basis
A year is left out because the company reported it only before a later filing restated other years, for example after a stock split.

The restated years and the older years are on different bases, so the analysis never combines them and does no split arithmetic to convert one to the other. It uses the newest run of years that share one basis and names the years it left out. A year whose filings, filed together, give different values is left out too, with the reason [ambiguous fact](#reason-ambiguous-fact), and so is every year older than it. When a requested history needs those years, the result is indeterminate with this reason. See [stock split adjustment](#stock-split-adjustment) and [fiscal year](#fiscal-year).

<a id="reason-growth-not-meaningful"></a>
### Growth Not Meaningful
A growth rate or ratio cannot be calculated meaningfully, because a base value is zero or negative or the sign changed across the period.

A compound growth rate needs a positive start and a positive end. See [CAGR](#cagr).

<a id="reason-not-growing"></a>
### Not Growing
A required growth rate is not positive, so a growth screen does not pass: free cash flow, earnings or both did not grow.

The code says which of the two did not grow. See [FCF classification](#fcf-classification).

<a id="reason-forward-not-confirmed"></a>
### Forward Growth Not Confirmed
The analyst consensus does not confirm the historical growth, which counts when the forward policy requires confirmation.

See [forward policy](#forward-policy) and [analyst consensus estimate](#analyst-consensus-estimate).

<a id="reason-insufficient-tests"></a>
### Insufficient Tests
Fewer than six of the nine tests could be decided, so no score is given.

See [F-Score](#f-score) and [unavailable test](#unavailable-test).

<a id="reason-invalid-request"></a>
### Invalid Request
A metric was asked for with an invalid input, or its result is too large to represent, so it is not calculated.

The metric is reported as not applicable. See [not applicable](#not-applicable).

<a id="reason-security-not-applicable"></a>
### Security Not Applicable
The strategy does not apply to this kind of security or to its industry class.

A strategy built for company financial statements does not cover every instrument or every industry. See [instrument kind](#instrument-kind), [industry class](#industry-class) and [not applicable](#not-applicable).

<a id="reason-industry-class-unknown"></a>
### Industry Class Unknown
The issuer's industry class could not be established, so the strategy could not decide whether it applies.

The class comes from the as-filed SIC code. See [industry class](#industry-class) and [as-filed SIC code](#as-filed-sic-code).

<a id="reason-debt-not-visible"></a>
### Debt Not Visible
Total debt cannot be determined from the filing: related debt is tagged but no usable component is shown, or the filing's debt mapping is not supported.

An absent debt component counts as zero only when nothing related to it is tagged. Otherwise total debt is unavailable. See [total debt](#total-debt).

<a id="quote-recent"></a>
### Recently Retrieved Quote
A quote retrieved within the freshness limit, so it is treated as current.

See [Quote Freshness](#quote-freshness) for the whole set of values.

<a id="quote-expired"></a>
### Expired Quote
A quote retrieved longer ago than the freshness limit, so it is no longer treated as current.

See [Quote Freshness](#quote-freshness) for the whole set of values.

<a id="quote-retrieval-unknown"></a>
### Quote With Unknown Retrieval Time
No retrieval time was recorded for the quote, so its age cannot be judged.

See [Quote Freshness](#quote-freshness) for the whole set of values.

<a id="quote-future-timestamp"></a>
### Future-Dated Quote
The quote's retrieval or market time is later than the time of the analysis, so its freshness cannot be judged.

See [Quote Freshness](#quote-freshness) for the whole set of values.

<a id="quote-user-supplied"></a>
### User-Supplied Quote
The price was supplied as an override, so no retrieval age applies.

See [Quote Freshness](#quote-freshness) for the whole set of values.

<a id="quote-historical"></a>
### Historical Quote
The price was read for a past as-of date and not as a current quote, so no freshness limit applies.

See [Quote Freshness](#quote-freshness) for the whole set of values.

<a id="price-comparison-available"></a>
### Price Comparison Available
The method's value could be compared with the price, so a margin of safety was calculated.

See [Price Comparison Status](#price-comparison-status) for the whole set of values.

<a id="price-comparison-unavailable"></a>
### Price Comparison Unavailable
The method's value could not be compared with the price, so no margin of safety is shown.

See [Price Comparison Status](#price-comparison-status) for the whole set of values.

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
