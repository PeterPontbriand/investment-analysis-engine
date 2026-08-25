# Graham Analysis Strategy Guide

This guide explains how the Financial Data Agents **Graham Analysis Strategy** works, how to use its available [methods](../GLOSSARY.md#method), where its financial values come from, and how to interpret its results.

The Financial Data Agents Graham Analysis Strategy currently implements two distinct methods:

1. the **Graham Number** — the default earnings-and-book-value screen; and
2. the **Graham Growth Value** — an explicitly selected, forecast-dependent calculation.

They are not interchangeable, and neither is a complete investment decision.

## What this strategy does

The Graham Analysis Strategy provides deterministic calculations based on explicitly defined financial values and conventions.

- **Graham Number** asks whether a market price is above or below a conservative earnings/book-value screening ceiling.
- **Graham Growth Value** applies a separate forecast-dependent Graham-style formula using earnings, expected growth, and a current AAA corporate-bond yield.

The exact formulas are documented in [Financial Math](../FINANCE_MATH.md#graham-analysis-strategy).

## Quick start

Graham Number:

```bash
uv run financial-agents graham KO
```

Graham Growth Value:

```bash
uv run financial-agents graham KO \
    --method growth \
    --expected-growth 5 \
    --aaa-yield 4.5
```

## Available methods

### Graham Number (default method)

The formula is:

```text
maximum indicated price = sqrt(22.5 × EPS × BVPS)
```

The factor `22.5` combines the conventional maximum P/E of 15 and maximum P/B of 1.5.

Financial Data Agents describes the result as a **maximum indicated price** or **screening ceiling**. It does not present the Graham Number as an unquestionable intrinsic value or as proof that a stock satisfies Graham's complete defensive-investor framework.

#### Earnings basis

The standard basis is [Three-Year-Average EPS](../GLOSSARY.md#three-year-average-eps), using three completed fiscal years of [diluted EPS](../GLOSSARY.md#basic-eps-diluted-eps).

SEC EDGAR observations are eligible only when the filing information was actually available by the analysis date. An earlier fiscal-year end does not make a later-filed fact historically knowable.

#### Book value per common share

The implemented convention is:

```text
BVPS = common shareholders' equity / period-end common shares outstanding
```

When using [SEC](../GLOSSARY.md#sec) [EDGAR](../GLOSSARY.md#edgar) data, Financial Data Agents derives BVPS conservatively from eligible fiscal-year-end accounting facts rather than pretending that EDGAR provides one universal BVPS field.

If the evidence required for a defensible calculation is unavailable, the result reports that limitation rather than guessing.

#### Applicability

Positive EPS and BVPS are required. If either is non-positive, the method reports that it is not applicable rather than forcing a zero, complex number, or misleading price estimate.

#### Current-price comparison

A current quote is optional to the Graham Number itself. When a compatible current price is available, Financial Data Agents shows how far the market price is above or below the Graham Number.

If the quote is unavailable, the Graham Number can still remain valid.

### Graham Growth Value (secondary method)

The implemented convention is:

```text
growth value = normalized EPS
    × (base P/E + growth multiplier × expected growth)
    × baseline AAA yield / current AAA yield
```

Current configurable conventional constants are:

```text
base P/E = 8.5
growth multiplier = 2.0
baseline AAA yield = 4.4
```

Expected growth and both yields are expressed in **percentage points**. For example, `--expected-growth 5` means 5%, not `0.05`.

This method is forecast-dependent. It is not the Graham Number and should not be interpreted as a universally precise intrinsic value.

#### Required user-supplied values

At present the user must supply:

- expected annual growth with `--expected-growth`; and
- the current AAA corporate-bond yield with `--aaa-yield`.

The software and local AI model do not invent either value. No live AAA-yield series is currently integrated for this calculation.

## Presentation modes

### Default

Designed to answer:

- What is the result?
- What does it mean?
- What are the most important sources/assumptions?
- Is there an important limitation or warning?

### `--details`

Shows resolved financial values, dates, bases, data sources, and derivations.

### `--diagnostics`

Shows software resolution behavior such as override/cache/provider selection and failures. This view is intentionally more technical than the ordinary investor report.

### `--json`

Emits [machine-readable output](../GLOSSARY.md#machine-readable-output) in [JSON](../GLOSSARY.md#json-javascript-object-notation), including the stable result/provenance representation.

## Inputs, assumptions, and overrides

The direct command supports explicit [overrides](../GLOSSARY.md#override) for values including EPS, BVPS, current price, and growth-method assumptions where applicable.

Examples:

```bash
uv run financial-agents graham KO --eps 3.25 --bvps 8.10
uv run financial-agents graham KO --current-price 75
```

An override is recorded as an override rather than being presented as provider-verified evidence.

Use `--details` to inspect what financial values were used and `--diagnostics` to inspect how resolution proceeded.

## Data sources

### SEC EDGAR

[SEC](../GLOSSARY.md#sec) [EDGAR](../GLOSSARY.md#edgar) is the U.S. Securities and Exchange Commission's public filing system.

Financial Data Agents currently uses eligible SEC filing facts for:

- completed fiscal-year diluted EPS; and
- fiscal-year-end accounting components used to derive BVPS conservatively.

For market-price comparison, Financial Data Agents obtains current quote data from Yahoo Finance through the third-party [`yfinance`](https://ranaroussi.github.io/yfinance/) library when available. `yfinance` is not affiliated with or endorsed by Yahoo.

### Massive (optional)

[Massive](../GLOSSARY.md#massive) is a commercial financial-market-data service. A Massive API key is useful only if you have Massive access and want Financial Data Agents to obtain data that the current Massive integration supports.

For Graham Growth Value, users with a configured Massive API key can explicitly select Massive:

```bash
uv run financial-agents graham KO \
    --method growth \
    --data-provider massive \
    --expected-growth 5 \
    --aaa-yield 4.5
```

The current Massive integration supplies:

- current [TTM](../GLOSSARY.md#ttm-trailing-twelve-months) diluted EPS; and
- current stock trade price.

It does **not** currently supply historical `as_of` support, BVPS, annual EPS, or an AAA-yield series.

See [Installation & Configuration — Massive](../INSTALLATION.md#optional-massive-market-data-access).

## Point-in-time analysis

`--as-of` creates an information boundary:

```bash
uv run financial-agents graham KO --as-of 2025-12-31
```

A fiscal period ending before that date is not automatically eligible. The supporting filing must also have been available by the requested boundary.

This distinction helps prevent [look-ahead bias](../GLOSSARY.md#look-ahead-bias).

Current-only quote providers do not manufacture historical quotes. A historical Graham calculation can therefore succeed while the market-price comparison is omitted.

## Why another Graham calculator may disagree

Before treating a difference as a bug, compare the conventions.

### EPS basis

Ask:

- three completed fiscal years averaged together or TTM?
- basic EPS or diluted EPS?
- were stock-split adjustments handled consistently?
- which exact fiscal periods were used?

Financial Data Agents uses three-year-average diluted EPS for the standard Graham Number calculation.

### BVPS definition

Ask:

- which balance-sheet date?
- which common-equity definition?
- period-end shares outstanding or another share count?
- ordinary book value or tangible book value?

Financial Data Agents uses a documented common-equity/period-end-share convention and does not silently substitute tangible book value.

### Publication timing

A filing's fiscal-year end and its public filing date are different things. A historical calculator that uses information not yet available at the requested date can differ because of look-ahead bias.

### Quote timing and currency

Otherwise identical calculations can show different price relationships if they compare against different market prices or incompatible currencies.

### Different Graham method

The Graham Number and Graham Growth Value are different [methods](../GLOSSARY.md#method) with different required values. A result from one should not be treated as merely another implementation of the other.

### Rounding and source revisions

Provider corrections, accounting restatements, and intermediate rounding can create smaller differences.

The goal is not to force every external calculator to match. It is to make Financial Data Agents' formula, evidence, dates, and assumptions inspectable enough that a difference can be explained.

## Important limitations

The Graham Number uses only earnings and book value. It does not test Graham's complete defensive-investor criteria and may be economically inappropriate for some businesses.

The Graham Growth Value depends materially on a user-supplied forecast and current AAA-yield assumption.

Accurate arithmetic does not guarantee that a selected method is appropriate for a particular security.

Nothing produced by this strategy is investment advice.

## Related user documentation

- [Usage Guide](../USAGE.md)
- [Financial Math — Graham Analysis Strategy](../FINANCE_MATH.md#graham-analysis-strategy)
- [Glossary](../GLOSSARY.md)
- [Installation & Configuration](../INSTALLATION.md)
