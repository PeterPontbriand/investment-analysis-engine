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

## Related user documentation

- [Usage Guide](../USAGE.md)
- [Financial Math — Graham Analysis Strategy](../FINANCE_MATH.md#graham-analysis-strategy)
- [Glossary](../GLOSSARY.md)
- [Installation & Configuration](../INSTALLATION.md)
