# Usage Guide

This guide covers the common ways to use Financial Data Agents after installation. Strategy-specific formulas, assumptions, and limitations live in the individual [Analysis Strategy Guides](strategies/README.md).

## The basic command shape

Commands are run from the Financial Data Agents installation folder:

```text
uv run financial-agents ANALYSIS [arguments] [options]
```

An [analysis strategy](GLOSSARY.md#analysis-strategy) is a deterministic analytical capability such as Graham analysis or Momentum. A [method](GLOSSARY.md#method) is a particular calculation within a strategy when that strategy offers more than one approach.

See all available commands:

```bash
uv run financial-agents --help
```

See help for a strategy:

```bash
uv run financial-agents graham --help
uv run financial-agents momentum --help
```

## Available analysis strategies

| Strategy | Basic command | What it examines | Guide |
|---|---|---|---|
| Graham Analysis | `uv run financial-agents graham KO` | Earnings/book-value screening and optional forecast-dependent Graham valuation | [Graham](strategies/GRAHAM.md) |
| Momentum | `uv run financial-agents momentum AAPL` | Simple-moving-average relationship/crossover over historical prices | [Momentum](strategies/MOMENTUM.md) |

## Graham analysis

The default Graham method is the Graham Number:

```bash
uv run financial-agents graham KO
```

Select the separate Graham Growth Value method explicitly:

```bash
uv run financial-agents graham KO \
    --method growth \
    --expected-growth 5 \
    --aaa-yield 4.5
```

The two methods use different values and have different interpretations. See the [Graham Analysis Strategy Guide](strategies/GRAHAM.md).

## Momentum analysis

```bash
uv run financial-agents momentum AAPL
```

With custom moving-average windows:

```bash
uv run financial-agents momentum AAPL \
    --short-window 10 \
    --long-window 30
```

See the [Momentum Analysis Strategy Guide](strategies/MOMENTUM.md).

## Presentation modes

The strategies use a common progressive-disclosure convention.

### Default — concise investor view

Omit presentation switches:

```bash
uv run financial-agents graham KO
```

The default view emphasizes the result, its meaning, key source/freshness information, warnings, and limitations.

### `--details` — inspect the financial evidence

```bash
uv run financial-agents graham KO --details
```

Use this when you want values, dates, measurement bases, data sources, and derivations.

### `--diagnostics` — inspect software resolution behavior

```bash
uv run financial-agents graham KO --diagnostics
```

Diagnostics are intentionally more technical. They can show how overrides, cache lookup, providers, and derivations were attempted.

### `--json` — machine-readable output

```bash
uv run financial-agents graham KO --json
```

[Machine-readable output](GLOSSARY.md#machine-readable-output) is structured for another program to consume reliably rather than primarily for a person to read. Financial Data Agents currently uses [JSON](GLOSSARY.md#json-javascript-object-notation) for this mode.

JSON intentionally retains stable machine identifiers such as snake_case field names where those identifiers are part of the programmatic contract.

## Historical / point-in-time analysis

Where supported:

```bash
uv run financial-agents graham KO --as-of 2025-12-31
```

`--as-of` creates an information boundary. Financial facts that had not yet been published by that date cannot be used merely because their reporting period ended earlier. See [`as_of`](GLOSSARY.md#as_of), [publication date](GLOSSARY.md#available-at--filing-date--publication-date), and [look-ahead bias](GLOSSARY.md#look-ahead-bias).

A provider that only supplies today's quote does not manufacture a historical quote. A historical calculation may therefore succeed without a market-price comparison.

## Overrides

An [override](GLOSSARY.md#override) explicitly supplies a value instead of accepting the normal resolved value.

Examples:

```bash
uv run financial-agents graham KO --eps 3.25 --bvps 8.10
uv run financial-agents graham KO --current-price 75
```

Overrides are recorded as overrides rather than being presented as provider-verified evidence. See the strategy guide before overriding a value whose measurement basis matters.

## Selecting a data source

Some methods allow explicit data-source selection. For example, users with configured [Massive](GLOSSARY.md#massive) access can select it where the Graham Growth Value method supports its data:

```bash
uv run financial-agents graham KO \
    --method growth \
    --data-provider massive \
    --expected-growth 5 \
    --aaa-yield 4.5
```

Data sources are not interchangeable merely because they expose similarly named values. Financial Data Agents rejects unsupported combinations rather than silently substituting a different financial basis.

## When a command cannot produce a result

Common reasons include:

- the ticker is invalid or unsupported;
- a required financial fact is unavailable;
- the selected method does not apply to the supplied facts;
- a requested historical boundary excludes later-published information;
- a selected data source does not support that field/date; or
- a configured external service could not be reached.

Start with the ordinary error message. Use `--details` or `--diagnostics` when you need more evidence.

## Optional local AI

The commands above are deterministic analysis commands and do not require a local LLM.

Local-AI orchestration/synthesis is an additional capability. See [Hardware & Local AI](HARDWARE.md) and the project's user-facing AI guidance as those workflows mature.
