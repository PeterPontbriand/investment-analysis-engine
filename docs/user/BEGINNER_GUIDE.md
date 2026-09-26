# A Beginner’s Guide to Investment Analysis in This Project

You do not need a background in finance to start exploring Investment Analysis Engine. This guide introduces the basic ideas behind the numbers it works with, shows how those numbers become an analysis, and points to deeper explanations. It is an orientation, not an investing course.

## Investment analysis, in everyday terms

Investment analysis means examining information about a business and the market for its shares to understand what the information may suggest. Someone might look at a company’s reported earnings, the cash it generates, how those figures have changed, or how a share price compares with a particular measure.

“Quantitative investment research” means using numbers and explicit calculation rules as part of that research. In this project, **quantitative** does not necessarily mean advanced mathematics: an average or a comparison can also be quantitative. The important point is that the calculation is defined and repeatable. The project’s Python code performs financial arithmetic; an AI model is not treated as a calculator or source of financial facts.

Numbers can help organize evidence and raise questions. Their meaning depends on definitions, dates, and business context, and a result is not by itself a recommendation.

## Facts, metrics, methods, and strategies

These four terms describe different layers:

- A **financial fact** is a reported or observed input, such as earnings for a reporting period, a share count, or a historical market price.
- A **metric** is a measurement calculated from facts, such as FCF per share or a growth rate. Some measures, including EPS, may also be reported directly by a company and used as an input. The important distinction is whether a value is reported evidence or a result calculated from other inputs in the particular analysis.
- An **analysis method** applies a defined calculation to selected inputs to address a particular question.
- An **analysis strategy** organizes one or more methods around an analytical question and presents the result, including relevant evidence and limits.

Here is a deliberately simplified example using the project’s Graham Number method:

```text
Reported annual diluted EPS, plus eligible balance-sheet and share facts
                              ↓
      Three-year-average EPS and derived book value per share
                              ↓
       Graham Number calculation (analysis method)
                              ↓
          Graham Analysis Strategy (strategy)
                              ↓
 A screening ceiling, with its inputs, sources, dates, and limitations
```

EPS means profit attributable to common shareholders expressed per share. Book value per share (BVPS) represents accounting book value attributable to common shareholders per share; it is not the market price. In the standard Graham Number path, the project uses diluted EPS from three completed fiscal years to form an average, and derives fiscal-year-end BVPS from eligible accounting facts. The method combines these measures to produce a maximum indicated price, also described as a screening ceiling. If a compatible current quote is available, the result can also show the price relationship. The ceiling is the output of that method—not a complete judgment of what a company is worth or whether its shares are suitable for someone.

The diagram is a conceptual guide, not a substitute formula. The [Graham strategy guide](strategies/GRAHAM.md) and [Financial Math & Data Conventions](FINANCE_MATH.md#graham-analysis-strategy) explain the actual inputs, formula, and eligibility rules.

## What kinds of information are involved?

Different analyses use different kinds of information. A term may be useful background even when it is not an input to a particular strategy.

### Company facts and per-share measures

Companies report financial information for defined periods. **Earnings** describe profit under an accounting basis. **EPS** expresses earnings per share; basic and diluted EPS use different share assumptions. **Shares outstanding** is a share count at a point in time, while weighted-average shares relate to a reporting period. These distinctions matter because a per-share figure depends on which earnings and share basis are used. See [EPS](GLOSSARY.md#eps-earnings-per-share), [diluted EPS](GLOSSARY.md#basic-eps--diluted-eps), and [shares outstanding](GLOSSARY.md#shares-outstanding).

**Free cash flow** is an analytical measure of cash generation after capital expenditures, but definitions can vary. In the FCF & Earnings Growth strategy, the project calculates annual FCF as operating cash flow minus normalized capital expenditures, then also calculates FCF per diluted share. See [FCF](GLOSSARY.md#free-cash-flow-fcf) and the [strategy guide](strategies/FCF_EARNINGS_GROWTH.md).

### Change over time

A **growth rate** describes how a value changes across a period. **CAGR**, or compound annual growth rate, is the constant annual rate that would connect a beginning value to an ending value over a stated number of years. It summarizes the endpoints; it does not mean the value actually changed at that steady rate each year. A historical CAGR describes the past and does not predict the future. See [CAGR](GLOSSARY.md#cagr-compound-annual-growth-rate).

### Prices, yields, and valuation measures

A **historical price** is an observation in a price series. The current market price is a separate kind of input: it is a quote, and its retrieval time does not necessarily establish when the underlying trade occurred.

A **yield** expresses an amount of income relative to an instrument’s price or value, usually as a percentage. In this project’s Graham Growth Value method, a user supplies an expected growth assumption and a current AAA corporate-bond yield; the project does not currently provide a live AAA-yield series for that method. See [yield](GLOSSARY.md#yield) and the [Graham guide](strategies/GRAHAM.md#graham-growth-value-secondary-method).

**Market capitalization** is the market value of a company’s shares, generally calculated from share price and shares outstanding. It is different from accounting book value. **Valuation measures** relate a price or market value to a financial measure. For example, P/E compares price per share with EPS; P/B compares price per share with BVPS. A ratio can help frame a comparison, but it does not establish what a business should be worth. In the current FCF & Earnings Growth method, market capitalization may support an optional, informational FCF yield; that yield does not determine the growth classification. See [P/E](GLOSSARY.md#pe-price-to-earnings-ratio), [P/B](GLOSSARY.md#pb-price-to-book-ratio), and [FCF yield](GLOSSARY.md#fcf-yield).

Relevant inputs can also include economic or market data. For example, the Graham Growth Value calculation refers to a corporate-bond yield. Not every strategy needs every type of information.

## Why examine these measurements—and what are their limits?

An investor may examine earnings and EPS to understand reported profitability on a per-share basis, cash flow to consider cash generated after investment in long-lived assets, or growth to summarize how a measure changed across years. Price comparisons and valuation measures put a share price alongside selected financial information. Historical prices can be used to describe price trends and changes in those trends.

These measurements answer limited questions. Earnings depend on accounting definitions and reporting periods. FCF is not defined identically by every source or analyst. Growth depends on the chosen start and end values, the length of the period, and whether the values are comparable. Per-share measurements depend on share basis and share-count changes. Price-based comparisons also depend on quote timing and compatible units or currency. Business circumstances can make the same measurement more or less informative in different cases.

Treat a metric as evidence to inspect, not as a verdict. A historical growth rate is not a forecast; a valuation formula is not a complete valuation; and no one metric determines whether a security is good or bad for an investor.

## How the project applies this model today

The project’s current strategy guides describe examples of distinct analytical questions:

- The **Graham Number** method combines earnings and book value per share to produce a screening ceiling. Positive EPS and BVPS are required. A current-price comparison is optional and depends on compatible evidence.
- **Graham Growth Value** is a separate, forecast-dependent calculation. Its expected growth and current AAA-yield inputs are supplied by the user under the current implementation; it is not the Graham Number.
- **Momentum** examines historical closing prices using moving averages and crossover state, with RSI as a supporting indicator. It describes price-series behavior, not business quality or intrinsic value.
- **Free Cash Flow & Earnings Growth** is a historical screen that calculates total-company and per-diluted-share FCF growth and diluted-EPS growth over compatible completed fiscal years. Its default classification is controlled by total-company FCF growth; per-share FCF can be selected instead. Optional FCF yield is informational, not a classification input.

These examples have different purposes and inputs. The set of strategies can evolve as the project grows; this list is an orientation to current documentation, not a permanent inventory or a requirement that future strategies use the same measures. The [strategy index](strategies/README.md) links to each guide and its limitations.

## Where values come from, and why dates matter

Financial facts and market observations come from sources with different roles. The current user guides describe SEC EDGAR filings as a source of company financial facts for the documented annual analyses, Yahoo Finance data through `yfinance` for historical prices and certain current quotes, and Massive data for a limited, optional set of current inputs when selected. Some commands also accept user-provided overrides. An override is an assumption supplied for that run; it is not the same as a value verified from a provider. See each strategy guide for its exact data-source support.

A **fiscal period** is the period a reported figure describes. The date that period ended is not necessarily when investors could first know the figure: a company may file its report weeks or months later. For a historical analysis, using a fact before its public availability could make the past look knowable with information that arrived later. The project’s `as_of` boundary limits eligible information to what was available by the requested date where the source supports that check. Current-only quotes do not become historical quotes merely because an analysis has an earlier `as_of` date. See [available at / filing date](GLOSSARY.md#available-at--filing-date--publication-date), [`as_of`](GLOSSARY.md#as_of), and [look-ahead bias](GLOSSARY.md#look-ahead-bias).

**Provenance** records where a value came from and how it was transformed. Source fields, reporting periods, availability dates, retrieval times, and derivations can help someone inspect or reproduce what an analysis used. They do not prove that a source is complete or correct, that a measure suits every purpose, or that the result predicts future performance. See [provenance](GLOSSARY.md#provenance).

## What the project does not establish

Investment Analysis Engine does not provide personalized investment advice, guarantee source-data quality or future performance, or turn one formula or metric into a complete valuation or investment decision. Its results have to be understood in context, and decisions require judgment beyond the calculation. Read the [project limitations and disclaimer](../../README.md#limitations--disclaimer) and the limitations in the relevant [strategy guide](strategies/README.md).

## Where to go next

- [Glossary](GLOSSARY.md) — short definitions of financial and project terms.
- [Analysis Strategy Guides](strategies/README.md) — current strategy examples, inputs, interpretation, sources, and limits.
- [Financial Math & Data Conventions](FINANCE_MATH.md) — authoritative formulas and calculation semantics.
- [Usage Guide](USAGE.md) — how to run analyses and inspect their output.
- [Project & Technical Documentation](../project/README.md) — architecture and implementation details for readers who want to go deeper.
