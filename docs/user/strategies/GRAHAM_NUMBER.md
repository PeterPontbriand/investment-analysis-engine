# Graham Number Strategy Guide

This guide explains how the Investment Analysis Engine **Graham Number** strategy works, where its financial values come from, and how to interpret its results.

The Graham Number is the earnings-and-book-value screening ceiling. It is a complete, independent strategy — not one of two "Graham methods" sharing a base — and it is not a complete investment decision. For the related but formula-independent Graham Growth Value strategy, see [its own guide](GRAHAM_GROWTH.md).

## What this strategy does

The Graham Number asks whether a market price is above or below a conservative earnings/book-value screening ceiling, using a deterministic calculation based on explicitly defined financial values and conventions.

The exact formula is documented in [Financial Math](../FINANCE_MATH.md#graham-analysis-strategy).

## Quick start

Quote responses are reused for at most five minutes by default, independently of annual-fact age. Reports retain retrieval time and distinguish it from market observation time, which the current Yahoo adapter does not supply. An expired quote is refreshed automatically; a failed refresh cannot produce a stale price relationship. `--no-cache` bypasses financial cache reads and writes.

Detailed provenance distinguishes guarded inferred zeroes from reported zeroes and includes nested derivations. A verified filing listing venue is shown with its filing date, separately from current identity metadata; it is not silently treated as current registration evidence.

```bash
uv run ian graham-number KO
```

## The Graham Number

The formula is:

```text
maximum indicated price = sqrt(22.5 × EPS × BVPS)
```

The factor `22.5` combines the conventional maximum P/E of 15 and maximum P/B of 1.5.

Investment Analysis Engine describes the result as a **maximum indicated price** or **screening ceiling**. It does not present the Graham Number as an unquestionable intrinsic value or as proof that a stock satisfies Graham's complete defensive-investor framework.

### Earnings basis

The standard basis is [Three-Year-Average EPS](../GLOSSARY.md#three-year-average-eps), using three completed fiscal years of [diluted EPS](../GLOSSARY.md#basic-eps--diluted-eps).

SEC EDGAR observations are eligible only when the filing information was actually available by the analysis date. An earlier fiscal-year end does not make a later-filed fact historically knowable.

### Book value per common share

The implemented convention is:

```text
BVPS = common shareholders' equity / period-end common shares outstanding
```

When using [SEC](../GLOSSARY.md#sec) [EDGAR](../GLOSSARY.md#edgar) data, Investment Analysis Engine derives BVPS conservatively from eligible fiscal-year-end accounting facts rather than pretending that EDGAR provides one universal BVPS field.

If the evidence required for a defensible calculation is unavailable, the result reports that limitation rather than guessing.

### Applicability

Positive EPS and BVPS are required. If either is non-positive, the method reports that it is not applicable rather than forcing a zero, complex number, or misleading price estimate.

### Current-price comparison

A current quote is optional to the Graham Number itself. When a compatible current price is available, Investment Analysis Engine shows how far the market price is above or below the Graham Number.

If the quote is unavailable, the Graham Number can still remain valid.

The `graham-number` command automatically verifies share-unit compatibility for a narrow
set of current SEC US-GAAP domestic `10-K` inputs and Yahoo Finance quotes. The
verification matches the original financial source filings and current eligible
annual filing to a single registered ordinary common-stock class, with matching
issuer, ticker, currency, periods, and source values. The 1:1 relationship is a
documented inference from that evidence, not an upstream ratio field. It does
not establish exhaustive coverage of intervening corporate actions.

Unsupported classes (including ADR/ADS and multiple common classes), ambiguous
filings, provider failures, and explicit historical requests leave the comparison
unavailable with a reason. They do not invalidate an otherwise valid Graham Number.
`--details` and `--diagnostics` show the comparison decision and filing provenance.

Older cached inputs may lack the source lineage needed for verification. If the
output identifies missing share-unit evidence, retry with `--no-cache` to resolve
fresh inputs; this bypass does not rewrite existing cache entries. Unsupported
or inaccessible evidence can still prevent comparison after a refresh.

To replace older cached inputs as well as bypass them, temporarily set the
existing financial-cache TTL to zero for a normal run. Only entries requested
by that command are refreshed through the normal provider/cache path. For
example, in PowerShell:

```powershell
$previousTtl = $env:financial_cache_ttl_seconds
try {
    $env:financial_cache_ttl_seconds = "0"
    uv run ian graham-number KO
} finally {
    $env:financial_cache_ttl_seconds = $previousTtl
}
```

Then rerun the ordinary command. Zero-TTL refreshes can emit cache-age rejection
notes; those indicate the old entries were bypassed. No database deletion or
schema migration is needed.

Verification reads at most four filings, each limited to 8 MiB and a 20-second
transport timeout, without redirects or automatic retries. Filing evidence is
verified again on each invocation, including when financial inputs are cached.

## Presentation modes

### Default

Designed to answer:

- What is the result?
- What does it mean?
- What are the most important sources/assumptions?
- Is there an important limitation or warning?

When supported provider evidence supplies an instrument name, the heading shows `Instrument Name (TICKER)`; otherwise it uses the ticker alone. Identity metadata is descriptive and cannot change a Graham Number calculation or its status.

### `--details`

Shows compact financial inputs, reporting dates, bases, sources, calculation formulas and material assumptions. Repeated source components appear once. Inferred preferred-share zero is explicitly qualified. Where retained, the filing link and its historical exchange evidence are shown separately from current listing verification. Display rounding does not change the calculation.

### `--diagnostics`

Retains the full technical input evidence and software resolution behavior: provider fields, recursive lineage, notes, retrieval timestamps, share contexts, and override/cache/provider selection or failures. JSON also retains this evidence.

### `--json`

Emits [machine-readable output](../GLOSSARY.md#machine-readable-output) in [JSON](../GLOSSARY.md#json-javascript-object-notation), including the stable result/provenance representation and an explicit nullable security-identity snapshot.

## Inputs, assumptions, and overrides

The direct command supports explicit [overrides](../GLOSSARY.md#override) for values including EPS, BVPS, and current price.

Examples:

```bash
uv run ian graham-number KO --eps 3.25 --bvps 8.10
uv run ian graham-number KO --current-price 75
```

An override is recorded as an override rather than being presented as provider-verified evidence.

Use `--details` to inspect what financial values were used and `--diagnostics` to inspect how resolution proceeded.

## Data sources

### SEC EDGAR

[SEC](../GLOSSARY.md#sec) [EDGAR](../GLOSSARY.md#edgar) is the U.S. Securities and Exchange Commission's public filing system.

Investment Analysis Engine currently uses eligible SEC filing facts for:

- completed annual diluted EPS from reviewed `10-K`/`20-F`/`40-F` forms and
  exact US-GAAP or IFRS concepts; and
- US-GAAP fiscal-year-end accounting components used to derive BVPS
  conservatively.

IFRS BVPS, preferred-zero inference for IFRS, custom-extension fallbacks, and
broader-concept substitution are not supported. A filing per-share value is
compared with a current quote only when affirmative evidence establishes a
matching-currency ordinary-share 1:1 relationship. ADR/ADS and currency
conversion are not performed; the valuation can remain available while its
market-price comparison is unavailable.

For market-price comparison, Investment Analysis Engine obtains current quote data from Yahoo Finance through the third-party [`yfinance`](https://ranaroussi.github.io/yfinance/) library when available. `yfinance` is not affiliated with or endorsed by Yahoo.

### Massive (optional)

[Massive](../GLOSSARY.md#massive) is a commercial financial-market-data service. A Massive API key is useful only if you have Massive access and want Investment Analysis Engine to obtain data that the current Massive integration supports.

For the Graham Number, users with a configured Massive API key can explicitly select Massive:

```bash
uv run ian graham-number KO --data-provider massive --bvps 8.10
```

The current Massive integration supplies current [TTM](../GLOSSARY.md#ttm-trailing-twelve-months) diluted EPS and current stock trade price. It does **not** currently supply historical `as_of` support or BVPS — an explicit `--bvps` override is required when using Massive.

See [Installation & Configuration — Massive](../INSTALLATION.md#optional-massive-market-data-access).

## Point-in-time analysis

`--as-of` creates an information boundary:

```bash
uv run ian graham-number KO --as-of 2025-12-31
```

A fiscal period ending before that date is not automatically eligible. The supporting filing must also have been available by the requested boundary.

This distinction helps prevent [look-ahead bias](../GLOSSARY.md#look-ahead-bias).

Current-only quote providers do not manufacture historical quotes. A historical Graham Number calculation can therefore succeed while the market-price comparison is omitted.

## Why another Graham Number calculator may disagree

Before treating a difference as a bug, compare the conventions.

### EPS basis

Ask:

- three completed fiscal years averaged together, TTM, or a single completed fiscal year?
- basic EPS or diluted EPS?
- were stock-split adjustments handled consistently?
- which exact fiscal periods were used?

Investment Analysis Engine uses three-year-average diluted EPS as the standard Graham Number basis. The accepted `--eps-basis` values, and the default when none is given, are provider-driven and method-specific — they are not interchangeable with the Graham Growth Value strategy's:

| Provider | Accepted `--eps-basis` | Default |
| :--- | :--- | :--- |
| SEC EDGAR | `three_year_average` only | `three_year_average` |
| Massive | `ttm` only | `ttm` |

The Graham Number never accepts an explicit single-fiscal-year (`fiscal_year`) basis, with either provider — that basis is a Graham Growth Value-only capability. See [Financial Math](../FINANCE_MATH.md#eps-basis) for the authoritative formula-level statement. An unsupported provider/basis combination is rejected, never silently transformed into a different basis.

### BVPS definition

Ask:

- which balance-sheet date?
- which common-equity definition?
- period-end shares outstanding or another share count?
- ordinary book value or tangible book value?

Investment Analysis Engine uses a documented common-equity/period-end-share convention and does not silently substitute tangible book value.

### Publication timing

A filing's fiscal-year end and its public filing date are different things. A historical calculator that uses information not yet available at the requested date can differ because of look-ahead bias.

### Quote timing and currency

Otherwise identical calculations can show different price relationships if they compare against different market prices or incompatible currencies.

### Different Graham strategy

The Graham Number and Graham Growth Value are different, independent strategies with different required values and different formulas. A result from one should not be treated as merely another implementation of the other; see [the Graham Growth Value guide](GRAHAM_GROWTH.md).

### Rounding and source revisions

Provider corrections, accounting restatements, and intermediate rounding can create smaller differences.

The goal is not to force every external calculator to match. It is to make Investment Analysis Engine's formula, evidence, dates, and assumptions inspectable enough that a difference can be explained.

## Important limitations

The Graham Number uses only earnings and book value. It does not test Graham's complete defensive-investor criteria and may be economically inappropriate for some businesses.

Accurate arithmetic does not guarantee that this strategy is appropriate for a particular security.

Nothing produced by this strategy is investment advice.

## Related user documentation

- [Graham Growth Value Strategy Guide](GRAHAM_GROWTH.md)
- [Usage Guide](../USAGE.md)
- [Financial Math — Graham Analysis Strategy](../FINANCE_MATH.md#graham-analysis-strategy)
- [Glossary](../GLOSSARY.md)
- [Installation & Configuration](../INSTALLATION.md)
