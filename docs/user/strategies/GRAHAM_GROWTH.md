# Graham Growth Value Strategy Guide

This guide explains how the Investment Analysis Engine **Graham Growth Value** strategy works, where its financial values come from, and how to interpret its results.

Graham Growth Value is an explicitly selected, forecast-dependent calculation. It is a complete, independent strategy — not one of two "Graham methods" sharing a base — and it is not a complete investment decision. For the related but formula-independent Graham Number strategy, see [its own guide](GRAHAM_NUMBER.md).

## What this strategy does

Graham Growth Value applies a forecast-dependent Graham-style formula using earnings, expected growth, and a current AAA corporate-bond yield, using a deterministic calculation based on explicitly defined financial values and conventions.

The exact formula is documented in [Financial Math](../FINANCE_MATH.md#graham-growth-value-strategy).

## Quick start

Quote responses are reused for at most five minutes by default, independently of annual-fact age. Reports retain retrieval time and distinguish it from market observation time, which the current Yahoo adapter does not supply. An expired quote is refreshed automatically; a failed refresh cannot produce a stale price relationship. `--no-cache` bypasses financial cache reads and writes.

Detailed provenance distinguishes guarded inferred zeroes from reported zeroes and includes nested derivations. A verified filing listing venue is shown with its filing date, separately from current identity metadata; it is not silently treated as current registration evidence.

```bash
uv run ian graham-growth KO \
    --expected-growth 5 \
    --aaa-yield 4.5
```

## Graham Growth Value

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

### Required user-supplied values

At present the user must supply:

- expected annual growth with `--expected-growth`; and
- the current AAA corporate-bond yield with `--aaa-yield`.

The software and local AI model do not invent either value. No live AAA-yield series is currently integrated for this calculation.

### Applicability

Positive EPS is required for a meaningful growth-value output, and current AAA yield must be strictly positive. If a required input cannot be resolved, the result reports that limitation rather than guessing.

### Current-price comparison

A current quote is optional to Graham Growth Value itself. When a compatible current price is available, Investment Analysis Engine shows how far the market price is above or below the calculated growth value.

If the quote is unavailable, the growth value can still remain valid.

The `graham-growth` command automatically verifies share-unit compatibility for a narrow
set of current SEC US-GAAP domestic `10-K` inputs and Yahoo Finance quotes. The
verification matches the original financial source filings and current eligible
annual filing to a single registered ordinary common-stock class, with matching
issuer, ticker, currency, periods, and source values. The 1:1 relationship is a
documented inference from that evidence, not an upstream ratio field. It does
not establish exhaustive coverage of intervening corporate actions.

Unsupported classes (including ADR/ADS and multiple common classes), ambiguous
filings, provider failures, and explicit historical requests leave the comparison
unavailable with a reason. They do not invalidate an otherwise valid growth value.
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
    uv run ian graham-growth KO --expected-growth 5 --aaa-yield 4.5
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

Presentation modes (default, `--details`, `--diagnostics`, `--json`) are shared across both Graham strategies — see the [overview's Presentation modes section](GRAHAM.md#presentation-modes).

## Inputs, assumptions, and overrides

The direct command supports explicit [overrides](../GLOSSARY.md#override) for values including EPS, current price, and the growth-method assumptions (`--expected-growth`, `--aaa-yield`).

Examples:

```bash
uv run ian graham-growth KO --expected-growth 5 --aaa-yield 4.5 --eps 3.25
uv run ian graham-growth KO --expected-growth 5 --aaa-yield 4.5 --current-price 75
```

An override is recorded as an override rather than being presented as provider-verified evidence.

Use `--details` to inspect what financial values were used and `--diagnostics` to inspect how resolution proceeded.

## Data sources

### SEC EDGAR

[SEC](../GLOSSARY.md#sec) [EDGAR](../GLOSSARY.md#edgar) is the U.S. Securities and Exchange Commission's public filing system.

Investment Analysis Engine currently uses eligible SEC filing facts for completed annual diluted EPS from reviewed `10-K`/`20-F`/`40-F` forms and exact US-GAAP or IFRS concepts.

IFRS custom-extension fallbacks and broader-concept substitution are not supported. A filing per-share value is
compared with a current quote only when affirmative evidence establishes a
matching-currency ordinary-share 1:1 relationship. ADR/ADS and currency
conversion are not performed; the valuation can remain available while its
market-price comparison is unavailable.

For market-price comparison, Investment Analysis Engine obtains current quote data from Yahoo Finance through the third-party [`yfinance`](https://ranaroussi.github.io/yfinance/) library when available. `yfinance` is not affiliated with or endorsed by Yahoo.

### Massive (optional)

[Massive](../GLOSSARY.md#massive) is a commercial financial-market-data service. A Massive API key is useful only if you have Massive access and want Investment Analysis Engine to obtain data that the current Massive integration supports.

Users with a configured Massive API key can explicitly select Massive:

```bash
uv run ian graham-growth KO \
    --data-provider massive \
    --expected-growth 5 \
    --aaa-yield 4.5
```

The current Massive integration supplies current [TTM](../GLOSSARY.md#ttm-trailing-twelve-months) diluted EPS and current stock trade price. It does **not** currently supply historical `as_of` support or an AAA-yield series.

See [Installation & Configuration — Massive](../INSTALLATION.md#optional-massive-market-data-access).

Point-in-time (`--as-of`) analysis is also shared across both Graham strategies — see the [overview's Point-in-time analysis section](GRAHAM.md#point-in-time-analysis).

## Why another Graham growth-value calculator may disagree

Before treating a difference as a bug, compare the conventions.

### EPS basis

Ask:

- three completed fiscal years averaged together, TTM, or a single completed fiscal year?
- basic EPS or diluted EPS?
- were stock-split adjustments handled consistently?
- which exact fiscal periods were used?

The accepted `--eps-basis` values, and the default when none is given, are provider-driven and method-specific — they are not interchangeable with the Graham Number strategy's:

| Provider | Accepted `--eps-basis` | Default |
| :--- | :--- | :--- |
| SEC EDGAR | `three_year_average` (default), or an explicit `fiscal_year` for reviewed workflows | `three_year_average` |
| Massive | `ttm` only | `ttm` |

`fiscal_year` (a single completed fiscal year's diluted EPS) is a Graham Growth Value-only basis; the Graham Number never accepts it, with either provider. See [Financial Math](../FINANCE_MATH.md#eps-basis) for the authoritative formula-level statement. An unsupported provider/basis combination is rejected, never silently transformed into a different basis.

### Publication timing

A filing's fiscal-year end and its public filing date are different things. A historical calculator that uses information not yet available at the requested date can differ because of look-ahead bias.

### Quote timing and currency

Otherwise identical calculations can show different price relationships if they compare against different market prices or incompatible currencies.

### Different Graham strategy

The Graham Number and Graham Growth Value are different, independent strategies with different required values and different formulas. A result from one should not be treated as merely another implementation of the other; see [the Graham Number guide](GRAHAM_NUMBER.md).

### Rounding and source revisions

Provider corrections, accounting restatements, and intermediate rounding can create smaller differences.

The goal is not to force every external calculator to match. It is to make Investment Analysis Engine's formula, evidence, dates, and assumptions inspectable enough that a difference can be explained.

## Important limitations

Graham Growth Value depends materially on a user-supplied forecast and current AAA-yield assumption.

Accurate arithmetic does not guarantee that this strategy is appropriate for a particular security.

Nothing produced by this strategy is investment advice.

## Related user documentation

- [Graham Number Strategy Guide](GRAHAM_NUMBER.md)
- [Usage Guide](../USAGE.md)
- [Financial Math — Graham Growth Value Strategy](../FINANCE_MATH.md#graham-growth-value-strategy)
- [Glossary](../GLOSSARY.md)
- [Installation & Configuration](../INSTALLATION.md)
