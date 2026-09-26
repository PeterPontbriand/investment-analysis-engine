# A Beginner’s Guide to Investment Analysis in This Project

You do not need a background in finance to start exploring Investment Analysis Engine. This guide introduces the basic ideas behind the numbers it works with, shows how those numbers become an analysis, and points to deeper explanations. It is an orientation, not an investing course.

## Investment analysis, in everyday terms

Investment analysis means examining information about a business and the market for its shares to understand what the information may suggest. Someone might look at a company’s reported earnings, the cash it generates, how those figures have changed, or how a share price compares with a particular measure.

“Quantitative investment research” means using numbers and explicit calculation rules as part of that research. In this project, **quantitative** does not necessarily mean advanced mathematics: an average or a comparison can also be quantitative. The important point is that the calculation is defined and repeatable. The project’s software performs financial arithmetic; an artificial intelligence (AI) model is not treated as a calculator or source of financial facts.

Numbers can help organize evidence and raise questions. Their meaning depends on definitions, dates, and business context, and a result is not by itself a recommendation.

## Facts, metrics, methods, and strategies

These four terms describe different layers:

- A **financial fact** is a reported or observed input, such as earnings for a reporting period, a share count, or a historical market price.
- A **metric** is a measurement calculated from facts, such as free cash flow per share or a growth rate. Some measures, including [earnings per share (EPS)](GLOSSARY.md#eps-earnings-per-share), may also be reported directly by a company and used as an input. The important distinction is whether a value is reported evidence or a result calculated from other inputs in the particular analysis.
- An **analysis method** applies a defined calculation to selected inputs to address a particular question.
- An **analysis strategy** organizes one or more methods around an analytical question and presents the result, including relevant evidence and limits.

Here is a deliberately simplified example using the project’s [Graham Number](GLOSSARY.md#graham-number) method. EPS is profit attributable to common shareholders for each share. [Book value per share (BVPS)](GLOSSARY.md#bvps-book-value-per-share) is the company’s reported assets minus its liabilities, attributed to common shareholders and expressed per share; it is not the market price. A [fiscal year](GLOSSARY.md#fiscal-year) is a company's annual accounting period.

```text
Reported annual diluted earnings per share, plus accounting and share facts that meet the method’s data rules
                              ↓
 Three-year average earnings per share and derived book value per share
                              ↓
       Graham Number calculation (analysis method)
                              ↓
          Graham Analysis Strategy (strategy)
                              ↓
 A screening ceiling, with its inputs, sources, dates, and limitations
```

In the standard Graham Number path, the project uses reported diluted EPS from three completed fiscal years to form an average. “Diluted” means the share calculation also allows for certain shares that could be created, for example through employee options. The project derives BVPS from year-end accounting facts that meet the method’s data rules, including common shareholders’ equity (the accounting value left for common owners after liabilities and other claims) and shares outstanding. The method combines the average EPS and BVPS to produce a [maximum indicated price](GLOSSARY.md#maximum-indicated-price--screening-ceiling), or screening ceiling (a price limit indicated by this formula). If the project has a current share price for the same kind of share and currency as the financial figures, the result can show how they compare. This is one limited screen, not a complete judgment of what a company is worth or whether its shares are suitable for someone. See the [Graham strategy guide](strategies/GRAHAM.md) and [Financial Math & Data Conventions](FINANCE_MATH.md#graham-analysis-strategy) for the exact inputs, formula, and data rules.

The diagram is a conceptual guide, not a substitute formula.

## What kinds of information are involved?

Different analyses use different kinds of information. A term may be useful background even when it is not an input to a particular strategy.

### Company facts and per-share measures

Companies report financial information for defined periods. **Earnings** describe profit under an accounting basis. **EPS** expresses earnings per share; basic and diluted EPS use different share assumptions. **Shares outstanding** is a share count at a point in time, while weighted-average shares are averaged across a reporting period. These distinctions matter because a per-share figure depends on which earnings and share basis are used. See [EPS](GLOSSARY.md#eps-earnings-per-share), [diluted EPS](GLOSSARY.md#basic-eps--diluted-eps), and [shares outstanding](GLOSSARY.md#shares-outstanding).

**[Free cash flow (FCF)](GLOSSARY.md#free-cash-flow-fcf)** is an analytical measure of cash generated after spending on long-lived assets such as buildings or equipment (capital expenditures). Different sources may define it differently. In the Free Cash Flow & Earnings Growth strategy, the project calculates annual FCF as cash generated by normal business operations minus capital expenditures, then also calculates FCF per diluted share. See the [strategy guide](strategies/FCF_EARNINGS_GROWTH.md) for the project’s calculation and limits.

### Change over time

A **growth rate** describes how a value changes across a period. **[CAGR (compound annual growth rate)](GLOSSARY.md#cagr-compound-annual-growth-rate)** is the constant annual rate that would connect a beginning value to an ending value over a stated number of years. It summarizes the endpoints; it does not mean the value actually changed at that steady rate each year. A historical CAGR describes the past and does not predict the future.

### Prices, yields, and valuation measures

A **historical price** is one observed share price in a series of prices over time. The current market price is a separate kind of input: it is a quote, and the time the project retrieves it does not necessarily establish when the underlying trade occurred.

A **[yield](GLOSSARY.md#yield)** expresses an amount of income relative to an investment’s price or value, usually as a percentage. In this project’s [Graham Growth Value](strategies/GRAHAM.md#graham-growth-value-secondary-method) method, a user supplies an expected growth estimate and the yield on AAA-rated (highest credit category) corporate bonds; the project does not currently provide a live series of that yield. See the glossary’s [AAA definition](GLOSSARY.md#aaa).

**Market capitalization** is the market value of a company’s shares, generally calculated from share price and shares outstanding. It is different from accounting book value. **Valuation measures** compare a price or market value with a financial measure. For example, the [price-to-earnings ratio (P/E)](GLOSSARY.md#pe-price-to-earnings-ratio) compares price per share with EPS; the [price-to-book ratio (P/B)](GLOSSARY.md#pb-price-to-book-ratio) compares price per share with BVPS. A ratio can help frame a comparison, but it does not establish what a business should be worth. In the current FCF strategy, market capitalization may support an optional, informational [FCF yield](GLOSSARY.md#fcf-yield); it does not determine the growth classification.

Relevant inputs can also include economic or market data. For example, the Graham Growth Value calculation refers to a corporate-bond yield. Not every strategy needs every type of information.

## Why examine these measurements—and what are their limits?

An investor may examine earnings and EPS to understand reported profitability on a per-share basis, cash flow to consider cash generated after investment in long-lived assets, or growth to summarize how a measure changed across years. Price comparisons and valuation measures put a share price alongside selected financial information. Historical prices can be used to describe price trends and changes in those trends.

These measurements answer limited questions. Earnings depend on accounting definitions and reporting periods. FCF is not defined identically by every source or analyst. Growth depends on the chosen start and end values, the length of the period, and whether the values are comparable. Per-share measurements depend on share basis and share-count changes. Price-based comparisons also depend on quote timing and compatible units or currency. Business circumstances can make the same measurement more or less informative in different cases.

Treat a metric as evidence to inspect, not as a verdict. A historical growth rate is not a forecast; a valuation formula is not a complete valuation; and no one metric determines whether a security is good or bad for an investor.

## How the project applies this model today

The project’s current strategy guides describe examples of distinct analytical questions:

- The **Graham Number** method combines earnings and book value per share to produce a screening ceiling. Positive EPS and BVPS are required. A current-price comparison is optional and depends on compatible evidence.
- **Graham Growth Value** is a separate calculation that depends on estimates about future growth. Under the current implementation, the user supplies an expected growth estimate and a current AAA corporate-bond yield; the method is not the Graham Number.
- **Momentum** examines recent share-price behavior using simple moving averages (averages over selected numbers of past prices) and whether their relationship changes, called a crossover. It also reports [RSI (Relative Strength Index)](GLOSSARY.md#rsi-relative-strength-index), a momentum indicator—a score that compares recent price gains with losses. The strategy describes price behavior; it does not assess business quality or estimate [intrinsic value](GLOSSARY.md#intrinsic-value), meaning what an investment may be economically worth.
- **Free Cash Flow & Earnings Growth** is a historical screen that looks at whether the company’s total FCF, FCF per diluted share, and diluted EPS grew over completed fiscal years with comparable data. By default, the screen uses total-company FCF growth; it can instead use FCF growth per diluted share. Optional FCF yield provides extra context and does not affect the screen.

These examples have different purposes and inputs. The set of strategies can evolve as the project grows; this list is an orientation to current documentation, not a permanent inventory or a requirement that future strategies use the same measures. The [strategy index](strategies/README.md) links to each guide and its limitations.

## Where values come from, and why dates matter

Financial facts and market observations come from sources with different roles. The [United States Securities and Exchange Commission (SEC)](GLOSSARY.md#sec) makes company filings available through [EDGAR (Electronic Data Gathering, Analysis, and Retrieval)](GLOSSARY.md#edgar); the project uses filings that meet its data rules for some annual company facts. The project uses a software component called `yfinance` to access Yahoo Finance historical prices and certain current share prices. [Massive](GLOSSARY.md#massive) is another data service that can supply a limited set of current inputs when selected. Some commands also accept user-provided overrides—values supplied for a particular run rather than confirmed by a data service. Each strategy guide describes its specific sources.

A **fiscal period** is the period a reported figure describes. The date that period ended is not necessarily when investors could first know the figure: a company may file its report weeks or months later. For a historical analysis, using a fact before its public release would use information that arrived later, an error called [look-ahead bias](GLOSSARY.md#look-ahead-bias). The project’s [`as_of`](GLOSSARY.md#as_of) date is a cutoff: where the source supports it, the analysis only uses information available by that date. A current-only quote does not become a historical quote just because an analysis has an earlier `as_of` date. See [filing and publication dates](GLOSSARY.md#available-at--filing-date--publication-date) for more detail.

**[Provenance](GLOSSARY.md#provenance)** means the record of where a value came from and how it was changed or calculated. Source details, reporting periods, availability dates, and when data were retrieved help someone inspect or reconstruct what an analysis used. They do not prove that a source is complete or correct, that a measure suits every purpose, or that the result predicts future performance.

## What the project does not establish

Investment Analysis Engine does not provide personalized investment advice, guarantee source-data quality or future performance, or turn one formula or metric into a complete valuation or investment decision. Its results have to be understood in context, and decisions require judgment beyond the calculation. Read the [project limitations and disclaimer](../../README.md#limitations--disclaimer) and the limitations in the relevant [strategy guide](strategies/README.md).

## Where to go next

- [Glossary](GLOSSARY.md) — short definitions of financial and project terms.
- [Analysis Strategy Guides](strategies/README.md) — current strategy examples, inputs, interpretation, sources, and limits.
- [Financial Math & Data Conventions](FINANCE_MATH.md) — authoritative formulas and calculation semantics.
- [Usage Guide](USAGE.md) — how to run analyses and inspect their output.
- [Project & Technical Documentation](../project/README.md) — architecture and implementation details for readers who want to go deeper.
