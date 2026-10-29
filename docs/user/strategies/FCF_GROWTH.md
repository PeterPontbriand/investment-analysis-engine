# Free Cash Flow & Earnings Growth Strategy

The Free Cash Flow & Earnings Growth strategy is a deterministic historical screen. It asks whether a company produced positive, measurable growth in both free cash flow (FCF) and diluted earnings per share (EPS) over a common span of completed fiscal years.

The result is a `PASS`, `FAIL`, or `INDETERMINATE` screen—not a valuation, moat rating, forecast, or investment recommendation.

Explanations follow the selected classification basis: total-company FCF or FCF per diluted share. Those measures can move in opposite directions when share counts change. Details retain component currency, source/cache origin, derivation notes and reasons for unavailable optional metrics. The effective analysis time controls input eligibility as well as the reported execution time; a later resolver clock cannot admit later filings into an earlier execution boundary.

## Quick start

```bash
uv run ian fcf-growth MSFT
```

The default policy:

- selects the longest usable contiguous history, preferring 5 elapsed years, then 4, then 3;
- uses total-company FCF growth as the classification basis;
- requires positive growth in both the controlling FCF measure and diluted EPS for `PASS`; and
- treats optional forward EPS evidence as display-only.

Inspect the evidence or machine-readable result:

```bash
uv run ian fcf-growth MSFT --details
uv run ian fcf-growth MSFT --diagnostics
uv run ian fcf-growth MSFT --json
```

### Command options

| Option | Purpose |
|---|---|
| `--growth-years 3|4|5` | Require an exact elapsed-year horizon; omit it for automatic 5 → 4 → 3 selection. |
| `--classification-basis total-fcf|fcf-per-share` | Select which FCF CAGR controls classification. |
| `--forward-policy display-only|confirmation|hard-gate` | Select how optional forward EPS evidence affects the result. |
| `--as-of DATE_OR_TIMESTAMP` | Set a point-in-time information boundary. |
| `--currency USD` | Require a compatible three-letter ISO 4217 reporting currency for annual facts. |
| `--no-cache` | Bypass resolved-input cache reads and writes for this run. |
| `--details` | Explain annual inputs, calculation formulas and selected classification basis. |
| `--diagnostics` | Show the resolver execution trace. |
| `--json` | Emit the complete versioned typed result. |

Run `uv run ian fcf-growth --help` for the command's current option help. The three presentation switches are mutually exclusive.

## What the strategy calculates

For each eligible completed fiscal year:

```text
free cash flow = operating cash flow - normalized capital expenditures
FCF per diluted share = free cash flow / weighted-average diluted shares
```

It then calculates compound annual growth rates (CAGRs) for:

- total-company FCF;
- FCF per diluted share; and
- diluted EPS.

Both FCF growth measures are reported. Total-company FCF controls classification by default because it measures growth in the business's aggregate cash generation. The optional per-share basis incorporates the effect of dilution and repurchases.

See [Financial Math & Data Conventions](../FINANCE_MATH.md#free-cash-flow--earnings-growth-strategy) for the normative formulas and edge-case rules.

## FCF yield

The command also shows an informational FCF yield: the latest completed fiscal year's free cash flow divided by the company's [market capitalization at the boundary](../FINANCE_MATH.md#market-capitalization), as a percentage. It never changes the classification or the execution status.

- **When it is shown.** The concise view has a `FCF yield:` line only when the yield is a number. The yield requires the latest fiscal year to end at the fiscal year-end of the most recent annual report at the boundary, the year the share count is taken at; otherwise it is unavailable, and an older year is never used.
- **What it needs.** A share count from the annual report (or its cover page), a split-adjusted closing price, the splits since the count was taken, and a check of the annual report's cover that the ticker is a share of the company. Without `--as-of` the price is the current quote; with `--as-of` it is the closing price on the last trading day on or before that date.
- **When it is unavailable.** The line is left out and a warning, `FCF yield is unavailable:`, gives the reason: for example a filer of a 20-F or 40-F, a ticker that is a depositary share, unit or warrant on the cover, a quote and annual figures in different currencies, or no share count. When a market-data provider fails, the warning names the provider and the kind of failure (such as `yfinance` and `rate_limited`) and never repeats the provider's own message. The run is still a completed run: its status, classification and exit code are the same as without the yield, and no provider check is made. The failure is not recorded as a provider failure of the run.
- **No request when it is not wanted.** For an ETF no market data is requested. When no completed fiscal year could be resolved there is nothing to divide, and none is requested either.

`--details` adds the evidence behind the market capitalization under the calculation notes:

```text
Market capitalization: 1,300.00 USD
  Share count: 200 (year end, dated 2025-01-01; source filed 2025-02-01)
  Share count on the price's basis: 400
  Splits applied: 2025-03-03 ×2
  Price: 3.25 USD (split-adjusted close, 2026-10-28)
  Currencies: filing USD, quote USD
  Listing check: affirmed on 0000000000-25-000001
```

The share count line names its basis (`year end` or `cover page`), the date of the count and the date the filing it came from was filed. A ticker renamed since the annual report is shown with both reports: `affirmed; FB on 10-K <accession>, renamed META on 10-K <accession>`. `--diagnostics` shows the same lines, and `--json` carries the whole `market_capitalization` part, with every field above and the provenance of the share count.

### Limits of the yield

- With a date-only `--as-of`, the price includes that day's close, and a session is read by its exchange-local date, as Momentum reads its prices.
- The share count is the count at the fiscal year-end, so buybacks and issuance between the year-end and the price date are not reflected.
- A filing restates its counts for a split effective before it is issued. A split announced before the filing but effective just after it is assumed not to be reflected in the filing.
- A filer of a 20-F or 40-F (a foreign private issuer) is unavailable, because its US listing may be a depositary receipt at a ratio the structured data cannot show. A listing that is not a share of the company on the annual report's cover (a depositary share, unit, warrant or preferred security) is unavailable.
- The yield uses an annual numerator and a market denominator, so it is context, not a valuation.

## Historical period

The automatic policy tries these spans in order:

| Elapsed years | Required annual observations |
|---:|---:|
| 5 | 6 |
| 4 | 5 |
| 3 | 4 |

For example, FY2020 through FY2025 contains six observations and five elapsed annual intervals. The observations must be compatible and contiguous. If the automatic policy falls back to a shorter span, the result discloses that fallback.

Request an exact span with `--growth-years`:

```bash
uv run ian fcf-growth MSFT --growth-years 5
```

An explicit span is strict. If the required history is unavailable, the strategy returns `INDETERMINATE` rather than silently choosing a shorter span.

## Classification

The screen returns:

- `PASS` when the selected FCF CAGR and diluted-EPS CAGR are both meaningful and greater than zero, subject to any selected forward hard gate;
- `FAIL` when the required historical metrics are meaningful and at least one is zero or negative; or
- `INDETERMINATE` when required evidence is missing, incompatible, non-contiguous, or mathematically nonmeaningful.

An `INDETERMINATE` result is not a failed financial screen. It means the software cannot make the requested classification from the admissible evidence. Software execution status is recorded separately from the financial classification.

## Classification basis

Use total-company FCF, the default:

```bash
uv run ian fcf-growth MSFT --classification-basis total-fcf
```

Or make FCF per diluted share controlling:

```bash
uv run ian fcf-growth MSFT --classification-basis fcf-per-share
```

Changing the basis can change the screen when share issuance or repurchases cause total and per-share FCF growth to differ. The result always identifies the selected basis and still reports both FCF CAGRs.

## Forward EPS policy

The typed strategy supports analyst-consensus diluted EPS evidence for FY1 and FY2 when compatible evidence is available:

| Option | Effect |
|---|---|
| `display-only` | Show available forward evidence without changing the historical conclusion. This is the default. |
| `confirmation` | Report whether both forward intervals confirm positive growth without changing the historical conclusion. |
| `hard-gate` | Require both forward intervals to be available and positive for `PASS`; missing required evidence yields `INDETERMINATE`. |

```bash
uv run ian fcf-growth MSFT --forward-policy hard-gate
```

Forward estimates are optional provider evidence, not predictions generated by Investment Analysis Engine. The current production SEC EDGAR mapping supplies historical company facts but may not supply forward analyst consensus. In that case, `display-only` leaves the historical conclusion unchanged, while `hard-gate` produces `INDETERMINATE` as designed.

## Point-in-time analysis

```bash
uv run ian fcf-growth MSFT --as-of 2025-12-31
```

`--as-of` is an information boundary. A fiscal year is not eligible merely because it ended before that date; its supporting filing must also have been available by the boundary. This prevents later-published facts from leaking into a historical analysis. A ticker names the registrant it maps to today: with `--as-of`, every input is that registrant's evidence as filed or priced at the boundary, so the boundary limits the information used and not which company is studied.

## Presentation modes

- The default view shows the classification, basis, period, principal metrics, source summary, warnings, and limitation.
- `--details` adds a compact annual input table, calculation formulas, share counts, the [market capitalization evidence](#fcf-yield) behind the FCF yield, and optional-metric reasons, using readable monetary magnitudes.
- `--diagnostics` retains full annual provider fields, dates, notes, recursive lineage, provider attempts, candidate selection/rejection, cache behavior, and execution trace information.
- `--json` returns the complete versioned typed result for software integration.

The presentation modes render the same result. They do not recalculate or reclassify it. `--details`, `--diagnostics`, and `--json` are mutually exclusive.

When supported provider evidence supplies an instrument name, the heading shows `Instrument Name (TICKER)`; otherwise it uses the ticker alone. JSON includes an explicit nullable security-identity snapshot. Identity metadata is descriptive and cannot change the screen classification or execution status.

## Data sources and provenance

The current production command resolves annual financial facts from SEC EDGAR. Required evidence includes:

- net cash provided by operating activities;
- capital expenditures, normalized to a positive expenditure amount;
- diluted EPS; and
- weighted-average diluted shares.

Eligible annual forms are `10-K`, `10-K/A`, `20-F`, `20-F/A`, `40-F`, and
`40-F/A` for the reviewed duration fields. US-GAAP uses the existing exact
concept mappings. IFRS support is deliberately limited to exact diluted EPS,
diluted weighted-average shares, operating cash flow, and physical-PP&E CapEx
concepts. Broader combined investing concepts, custom extensions, fuzzy
matches, negative-to-positive CapEx normalization, and missing-value
substitution remain unsupported.

Issuer-level operating cash flow, CapEx, and derived FCF can remain valid even
when per-share or quote-unit evidence is unavailable. ADR/ADS conversion and
currency conversion are not performed.

The calculation does not accept a provider's precomputed “free cash flow” solely because its label matches. It derives FCF from the resolved components and retains their provider fields, period dates, publication/availability dates, retrieval times, units, currency, and derivation lineage.

The resolver rejects incompatible facts instead of combining values with mismatched fiscal periods, units, currency, or measurement bases. Amendments and restatements are handled by deterministic selection rules.

## Why another calculator may disagree

Differences can arise when another source:

- defines capital expenditures or FCF differently;
- uses trailing-twelve-month rather than completed annual values;
- mixes basic and diluted EPS or uses ending shares rather than weighted-average diluted shares;
- smooths or normalizes annual values;
- selects different filings, restatements, fiscal periods, or publication cutoffs;
- calculates growth across a different number of elapsed years; or
- reports growth from zero, negative, or sign-changing endpoints using a different convention.

Investment Analysis Engine preserves the reported annual history and does not use absolute values to manufacture a CAGR from nonpositive endpoints.

## Interpretation and limitations

Positive FCF and diluted-EPS growth can be evidence of strengthening cash-generation economics, but this strategy does not establish:

- a durable competitive moat, scarcity, market opportunity, or management quality;
- relative leadership versus peers;
- fair value, discounted cash flow, terminal value, or cost of capital;
- a minimum acceptable FCF yield;
- future growth; or
- an investment recommendation.

FCF yield may appear as optional context when market capitalization at the boundary is available, but it never changes classification in the current method version.

## Watchlist options

`watchlist create --analysis fcf-growth` and `watchlist add-selection --analysis fcf-growth` accept `--growth-years`, `--forward-policy`, `--classification-basis` and `--currency`. It always uses SEC EDGAR data, matching the direct `fcf-growth` command. See [Local Research Workspace](../WORKSPACE.md#strategies-and-their-watchlist-options) for the watchlist commands that take them.

## Related documentation

- [Usage Guide](../USAGE.md)
- [Financial Math & Data Conventions](../FINANCE_MATH.md#free-cash-flow--earnings-growth-strategy)
- [Glossary](../GLOSSARY.md#free-cash-flow--earnings-growth-terms)
- [Human Smoke Testing Commands](../SMOKE_TESTING.md)
