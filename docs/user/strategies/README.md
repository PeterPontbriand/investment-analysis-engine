# Analysis Strategy Guides

An [analysis strategy](../GLOSSARY.md#analysis-strategy) is a deterministic analytical capability in Investment Analysis Engine. A [method](../GLOSSARY.md#method) is a particular calculation within a strategy when the strategy offers more than one approach.

## Available strategies

- [Graham Valuation Strategies](GRAHAM.md) — two independent fundamental valuation/screening strategies, each with its own formula and guide:
  - [Graham Number](GRAHAM_NUMBER.md) — earnings-and-book-value screening ceiling
  - [Graham Growth Value](GRAHAM_GROWTH.md) — forecast-dependent growth valuation
- [Momentum Analysis Strategy](MOMENTUM.md) — simple-moving-average/crossover analysis over historical prices.
- [Free Cash Flow & Earnings Growth Strategy](FCF_EARNINGS_GROWTH.md) — historical total-company FCF, FCF-per-diluted-share, and diluted-EPS growth screening with explicit `PASS`, `FAIL`, or `INDETERMINATE` classification.

Each strategy guide follows the same general order where applicable: what the strategy does, quick start, available methods, presentation modes, inputs/assumptions/overrides, data sources, historical behavior, comparison with other calculators, limitations, and related user documentation.
