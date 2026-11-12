# Graham Growth Value Strategy Guide

This guide explains how the Investment Analysis Engine **Graham Growth Value** strategy works, where its financial values come from, and how to interpret its results.

Graham Growth Value is an explicitly selected, forecast-dependent calculation. It is a complete, independent strategy — not one of two "Graham methods" sharing a base — and it is not a complete investment decision. For the related but formula-independent Graham Number strategy, see [its own guide](GRAHAM_NUMBER.md).

## What this strategy does

Graham Growth Value applies a forecast-dependent Graham-style formula using earnings, expected growth, and a current AAA corporate-bond yield, using a deterministic calculation based on explicitly defined financial values and conventions.

The exact formula is documented in [Financial Math](../FINANCE_MATH.md#graham-growth-value-strategy).

## Quick start
<!-- help:exclude -->

```bash
ian graham-growth KO \
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

They ship with the application and may be overridden key by key in the strategy's settings file, which is read each time an analysis runs; the keys are `base_pe`, `growth_multiplier` and `baseline_aaa_yield`.

Expected growth and both yields are expressed in **percentage points**. For example, an expected growth of 5 means 5%, not `0.05`.

This method is forecast-dependent. It is not the Graham Number and should not be interpreted as a universally precise intrinsic value.

### The fiscal year of the earnings

The earnings come from the [anchor filing](../GLOSSARY.md#anchor-filing), the newest annual report filed by the analysis date. The newest fiscal year of the earnings must end on that report's fiscal year-end, on exactly that date. When it ends on another day, the growth value is unavailable and says which dates differ. The engine never steps back to an older year to produce a number.

With the three-year average, the three earnings years must also be consecutive fiscal years. When one is missing, the growth value is unavailable and names the missing year. When a [stock split](../GLOSSARY.md#reason-earlier-basis) or conflicting filings left years out of the series and that is why fewer than three years are left, the message names each year left out and why, and the JSON lists them in `left_out_years`.

A value saved from an earlier run is not reused when it is for an older fiscal year: the engine asks the provider again, once, and keeps the answer. An EPS you supply yourself has no year and is not checked, and then no filing is read and no anchor filing is reported.

When the anchor filing is stale, because the next annual report was overdue at the analysis date and none had been filed, the status does not change. The result names the filing and the date the next report was due, and a warning says so; it is the first warning shown.

### Required user-supplied values

At present the user must supply:

- expected annual growth; and
- the current AAA corporate-bond yield.

The software and local AI model do not invent either value. No live AAA-yield series is currently integrated for this calculation.

#### On the command line
<!-- help:exclude -->

Pass them with `--expected-growth` and `--aaa-yield`.

### Applicability

Positive EPS is required for a meaningful growth-value output, and current AAA yield must be strictly positive. If a required input cannot be resolved, the result reports that limitation rather than guessing.

### Current-price comparison

A current quote is optional to Graham Growth Value itself. When a compatible current price is available, Investment Analysis Engine shows how far the market price is above or below the calculated growth value.

If the quote is unavailable, the growth value can still remain valid.

The analysis automatically verifies share-unit compatibility for a narrow
set of current SEC US-GAAP domestic `10-K` inputs and Yahoo Finance quotes. The
verification matches the original financial source filings and current eligible
annual filing to a single registered ordinary common-stock class, with matching
issuer, ticker, currency, periods, and source values. The 1:1 relationship is a
documented inference from that evidence, not an upstream ratio field. It does
not establish exhaustive coverage of intervening corporate actions.

Unsupported classes (including ADR/ADS and multiple common classes), ambiguous
filings, provider failures, and explicit historical requests leave the comparison
unavailable with a reason. They do not invalidate an otherwise valid growth value.

Older cached inputs may lack the source lineage needed for verification, and the
output then identifies missing share-unit evidence. Resolving fresh inputs can
supply it; unsupported or inaccessible evidence can still prevent comparison.

Verification reads at most four filings, each limited to 8 MiB and a 20-second
transport timeout, without redirects or automatic retries. Filing evidence is
verified again on each analysis, including when financial inputs are cached.

#### On the command line
<!-- help:exclude -->

`--details` and `--diagnostics` show the comparison decision and filing provenance.

If the output identifies missing share-unit evidence, retry with `--no-cache` to resolve
fresh inputs; this bypass does not rewrite existing cache entries.

To replace older cached inputs as well as bypass them, temporarily set the
existing financial-cache TTL to zero for a normal run. Only entries requested
by that command are refreshed through the normal provider/cache path. For
example, in PowerShell:

```powershell
$previousTtl = $env:IAN_FINANCIAL_CACHE_TTL_SECONDS
try {
    $env:IAN_FINANCIAL_CACHE_TTL_SECONDS = "0"
    ian graham-growth KO --expected-growth 5 --aaa-yield 4.5
} finally {
    $env:IAN_FINANCIAL_CACHE_TTL_SECONDS = $previousTtl
}
```

Then rerun the ordinary command. Zero-TTL refreshes can emit cache-age rejection
notes; those indicate the old entries were bypassed. No database deletion or
schema migration is needed.

### On the command line
<!-- help:exclude -->

`--expected-growth 5` means 5%, not `0.05`.

The constants can be overridden key by key in `strategies/graham-growth.toml` in your settings folder. See [Strategy settings files](../INSTALLATION.md#strategy-settings-files).

## Presentation modes
<!-- help:exclude -->

Both Graham strategies share the same presentation shape.

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

Emits [machine-readable output](../GLOSSARY.md#machine-readable-output) in [JSON](../GLOSSARY.md#json), including the stable result/provenance representation and an explicit nullable security-identity snapshot.

## Inputs, assumptions, and overrides

The analysis supports explicit [overrides](../GLOSSARY.md#override) for values including EPS, current price, and the growth-method assumptions (expected growth and the AAA yield).

An override is recorded as an override rather than being presented as provider-verified evidence.

### On the command line
<!-- help:exclude -->

Examples:

```bash
ian graham-growth KO --expected-growth 5 --aaa-yield 4.5 --eps 3.25
ian graham-growth KO --expected-growth 5 --aaa-yield 4.5 --current-price 75
```

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

### Quotes and filing evidence

Quote responses are reused for at most five minutes by default, independently of annual-fact age. Reports retain retrieval time and distinguish it from market observation time, which the current Yahoo adapter does not supply. An expired quote is refreshed automatically; a failed refresh cannot produce a stale price relationship.

Detailed provenance distinguishes guarded inferred zeroes from reported zeroes and includes nested derivations. A verified filing listing venue is shown with its filing date, separately from current identity metadata; it is not silently treated as current registration evidence.

### On the command line
<!-- help:exclude -->

`--no-cache` bypasses financial cache reads and writes.

## Point-in-time analysis

An [as-of date](../GLOSSARY.md#as-of-date) creates an information boundary for this strategy.

A fiscal period ending before that date is not automatically eligible. The supporting filing must also have been available by the requested boundary. A ticker names the registrant it maps to today: with an as-of date, every input is that registrant's evidence as filed or priced at the boundary, so the boundary limits the information used and not which company is studied.

This distinction helps prevent [look-ahead bias](../GLOSSARY.md#look-ahead-bias).

Current-only quote providers do not manufacture historical quotes. A historical calculation can therefore succeed while the market-price comparison is omitted.

### On the command line
<!-- help:exclude -->

`--as-of` sets the boundary:

```bash
ian graham-growth KO --expected-growth 5 --aaa-yield 4.5 --as-of 2025-12-31
```

## Why another Graham growth-value calculator may disagree

Before treating a difference as a bug, compare the conventions.

### EPS basis

Ask:

- three completed fiscal years averaged together, a trailing twelve months, or a single completed fiscal year?
- basic EPS or diluted EPS?
- were stock-split adjustments handled consistently?
- which exact fiscal periods were used?

The EPS basis is `three_year_average` (the default, for every provider) or `fiscal_year` for reviewed workflows. `fiscal_year` is a single completed fiscal year's diluted EPS and is a Graham Growth Value-only basis: the Graham Number has only the three-year average. See [Financial Math](../FINANCE_MATH.md#eps-basis) for the authoritative formula-level statement. An unsupported basis is rejected, never silently transformed into a different basis.

#### On the command line
<!-- help:exclude -->

`--eps-basis` selects the basis. The Graham Number has no `--eps-basis` option.

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

## Watchlist options
<!-- help:exclude -->

`watchlist add-selection graham-growth` accepts the same flags as `graham-number` without `--bvps` (see [Graham Number watchlist options](GRAHAM_NUMBER.md#watchlist-options)), plus `--eps-basis` and `--expected-growth`/`--aaa-yield`. The growth/yield assumptions are required; there is no default. See [Local Research Workspace](../WORKSPACE.md#strategies-and-their-watchlist-options) for the command that takes them.

## Reason codes

Whenever the status is anything other than `ok`, the analysis also gives a reason code and a message that says the same thing in words. A script or the desktop app can act on the code; the message is for reading. A successful analysis has no code. These are the codes this strategy can give, with when each happens:

- [Missing input](../GLOSSARY.md#reason-missing-input) (`missing_fact`): the data provider has no value for earnings per share, or for the anchor filing.
- [Not available as of](../GLOSSARY.md#reason-not-available-as-of) (`not_available_as_of`): a value exists, but it was not public at the as-of date, or the provider gave no date when it became public.
- [Insufficient history](../GLOSSARY.md#reason-insufficient-history) (`insufficient_history`): fewer than three fiscal years of earnings are available and none was left out for a reason of its own.
- [Earlier basis](../GLOSSARY.md#reason-earlier-basis) (`earlier_basis`): the earnings of the older years are on a different basis from the newest, so the engine does not combine them.
- [Ambiguous fact](../GLOSSARY.md#reason-ambiguous-fact) (`ambiguous_fact`): the filings give two values for one fiscal year, or share counts that cannot be used.
- [Incompatible inputs](../GLOSSARY.md#reason-incompatible-inputs) (`incompatible_period`, `incompatible_currency`, `incompatible_units` or `incompatible_scope`): the earnings are not for the anchor filing's fiscal year, or the earnings years differ in currency, units or scope.
- [Provider error](../GLOSSARY.md#status-provider-error) (`provider_error`): the data provider could not be reached or its answer was rejected.
- [Security not applicable](../GLOSSARY.md#reason-security-not-applicable) (`instrument_kind_not_applicable`): the security is an ETF, and the method is a company-level valuation.
- [Override only](../GLOSSARY.md#reason-override-only) (`override_only`): every input was supplied as an override and none came from a data provider, so the analysis is not run.
- [Invalid request](../GLOSSARY.md#reason-invalid-request) (`invalid_request`): the valuation P/E, which is the base P/E plus the growth multiplier times the expected growth, is zero or negative, or the value is too large to compute.

## Related user documentation
<!-- help:exclude -->

- [Graham Number Strategy Guide](GRAHAM_NUMBER.md)
- [Usage Guide](../USAGE.md)
- [Financial Math — Graham Growth Value Strategy](../FINANCE_MATH.md#graham-growth-value-strategy)
- [Glossary](../GLOSSARY.md)
- [Installation & Configuration](../INSTALLATION.md)
