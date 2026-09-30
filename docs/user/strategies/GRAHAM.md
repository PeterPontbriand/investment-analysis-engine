# Graham Valuation Strategies

Investment Analysis Engine implements two independent Graham-style valuation strategies. They are not variants of one calculation — each has its own formula, its own required inputs, and its own complete guide — and neither is a complete investment decision.

## Graham Number

The earnings-and-book-value screening ceiling: `sqrt(22.5 × EPS × BVPS)`. Requires no forecast — only EPS and book value per share.

```bash
uv run ian graham-number KO
```

Full guide: [Graham Number Strategy Guide](GRAHAM_NUMBER.md).

## Graham Growth Value

A forecast-dependent Graham-style valuation using earnings, an explicit user-supplied expected-growth assumption, and the current AAA corporate-bond yield.

```bash
uv run ian graham-growth KO --expected-growth 5 --aaa-yield 4.5
```

Full guide: [Graham Growth Value Strategy Guide](GRAHAM_GROWTH.md).

## Presentation modes

Both strategies share the same presentation shape.

### Default

Designed to answer:

- What is the result?
- What does it mean?
- What are the most important sources/assumptions?
- Is there an important limitation or warning?

When supported provider evidence supplies an instrument name, the heading shows `Instrument Name (TICKER)`; otherwise it uses the ticker alone. Identity metadata is descriptive and cannot change a calculation or its status.

### `--details`

Shows compact financial inputs, reporting dates, bases, sources, calculation formulas and material assumptions. Repeated source components appear once. Where retained, the filing link and its historical exchange evidence are shown separately from current listing verification. Display rounding does not change the calculation. For the Graham Number specifically, an inferred preferred-share zero is also explicitly qualified.

### `--diagnostics`

Retains the full technical input evidence and software resolution behavior: provider fields, recursive lineage, notes, retrieval timestamps, share contexts, and override/cache/provider selection or failures. JSON also retains this evidence.

### `--json`

Emits [machine-readable output](../GLOSSARY.md#machine-readable-output) in [JSON](../GLOSSARY.md#json-javascript-object-notation), including the stable result/provenance representation and an explicit nullable security-identity snapshot.

## Point-in-time analysis

`--as-of` creates an information boundary, for either strategy:

```bash
uv run ian graham-number KO --as-of 2025-12-31
uv run ian graham-growth KO --expected-growth 5 --aaa-yield 4.5 --as-of 2025-12-31
```

A fiscal period ending before that date is not automatically eligible. The supporting filing must also have been available by the requested boundary.

This distinction helps prevent [look-ahead bias](../GLOSSARY.md#look-ahead-bias).

Current-only quote providers do not manufacture historical quotes. A historical calculation can therefore succeed while the market-price comparison is omitted.

## Related user documentation

- [Usage Guide](../USAGE.md)
- [Financial Math — Graham Number Strategy](../FINANCE_MATH.md#graham-number-strategy)
- [Financial Math — Graham Growth Value Strategy](../FINANCE_MATH.md#graham-growth-value-strategy)
- [Glossary](../GLOSSARY.md)
- [Installation & Configuration](../INSTALLATION.md)
