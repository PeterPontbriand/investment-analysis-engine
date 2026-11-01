# Piotroski F-Score Strategy

This implementation follows the Piotroski nine-test structure but substitutes the net change in split-adjusted shares outstanding for the original equity-issuance signal, because issuance cannot be established reliably from structured filings.

The Piotroski F-Score is a deterministic financial-strength screen. It runs nine pass/fail tests on a company's reported financial statements for three consecutive fiscal years and counts the tests passed. The result is a score from 0 to 9, not a valuation, a forecast or an investment recommendation.

## Quick start

```bash
uv run ian piotroski AAPL
```

The command reads the statements from SEC EDGAR, finds the company's latest annual report at the boundary and scores that year against the two years before it. Inspect the evidence or the machine-readable result:

```bash
uv run ian piotroski AAPL --details
uv run ian piotroski AAPL --diagnostics
uv run ian piotroski AAPL --json
```

### Command options

| Option | Purpose |
|---|---|
| `--as-of DATE_OR_TIMESTAMP` | Set a point-in-time information boundary. Only annual reports accepted by SEC at or before it are used. |
| `--no-cache` | Bypass the cache for this run. |
| `--details` | Show each test's operands with their fiscal year-end and value. |
| `--diagnostics` | Show where each operand came from (provider field, accession and filing date) and how the fiscal year-ends were found. |
| `--json` | Emit the complete versioned typed result. |
| `--save-run` | Persist this attempt as a durable Analysis Run. |

The method has no tunable choice, so the strategy has no settings file and no watchlist options of its own. Run `uv run ian piotroski --help` for the command's current option help. The three presentation switches are mutually exclusive.

## What the strategy calculates

Year *t* is the fiscal year of the latest annual report at the boundary; *t−1* and *t−2* are the two years before it. Each test is a strict comparison on unrounded values:

| # | Group | Test | Passes when |
|---|---|---|---|
| 1 | Profitability | Positive ROA | net income of *t* ÷ total assets at *t−1* is greater than zero |
| 2 | Profitability | Positive CFO | operating cash flow of *t* ÷ total assets at *t−1* is greater than zero |
| 3 | Profitability | Improving ROA | ROA of *t* is greater than ROA of *t−1* |
| 4 | Profitability | Cash exceeds income | operating cash flow of *t* is greater than net income of *t* |
| 5 | Leverage and liquidity | Falling leverage | long-term debt ÷ average total assets fell, or long-term debt is zero in both years |
| 6 | Leverage and liquidity | Improving liquidity | the current ratio at *t* is greater than at *t−1* |
| 7 | Leverage and liquidity | No dilution | shares outstanding at *t* are not more than at *t−1* |
| 8 | Efficiency | Improving margin | gross margin of *t* is greater than that of *t−1* |
| 9 | Efficiency | Improving turnover | sales ÷ total assets at the start of the year is greater than the year before |

An unchanged ratio earns no point in any test but 5 (zero debt) and 7. See [Financial Math & Data Conventions](../FINANCE_MATH.md#piotroski-f-score-strategy) for the normative definitions, the conventions the method fixes and the edge-case rules.

## Reading the result

```text
Apple Inc. (AAPL) — Piotroski F-Score: 7 of 9 (complete)
Fiscal year-end: 2024-09-28 · 10-K 0000320193-24-000123 · us-gaap
Industry class: manufacturer (SIC code as filed)
Profitability
  1 Positive ROA          pass         ROA 26.59% > 0
  2 Positive CFO          pass         CFO / assets 33.54% > 0
  3 Improving ROA         fail         ROA 26.59%, prior 27.50%
  4 Cash exceeds income   pass         CFO 118,254,000,000 USD > net income 93,736,000,000 USD
Leverage and liquidity
  5 Falling leverage      pass         long-term debt / assets 26.94%, prior 29.80%
  6 Improving liquidity   fail         current ratio 0.87x, prior 0.99x
  7 No dilution           pass         shares 15,116,786,000, prior 15,550,061,000
Efficiency
  8 Improving margin      pass         gross margin 46.21%, prior 44.13%
  9 Improving turnover    pass         asset turnover 1.11x, prior 1.09x
```

Percentages and multiples are shown with two decimals; when two compared values would look equal at two decimals but differ, both are shown with more digits so the comparison can be seen.

### Complete and partial scores

A score is **complete** when all nine tests could be decided. A test that cannot be decided is **unavailable**, never a fail: its line shows `unavailable` and the reason. A score is **partial** when six to eight tests are available, and it is always shown as "*x* of *n*" with the unavailable tests named, never as a bare number and never as "*x* of 9":

```text
Monster Beverage Corp (MNST) — Piotroski F-Score: 5 of 6 (partial: tests 1, 3, 4 unavailable)
```

With fewer than six available tests there is no score. The usual reading of the scale applies to complete scores only: a high score (8 or 9) is conventionally read as financial strength and a low score (0 or 1) as weakness. A partial score gets a note saying so and is not ranked against complete scores.

The strategy scores only the latest annual report at the boundary. If that year's inputs are missing, the affected tests are unavailable; an older year is never scored in its place.

## Industry class

The industry class comes from the SIC code on the annual report the score rests on, as filed, never from the company's current code. The F-Score was designed for non-financial firms, so a financial issuer is scored with a warning: its gross-margin and current-ratio tests are typically unavailable. If the class cannot be established, the strategy still runs and a warning says why. An ETF is not scored: the run is reported as not applicable.

## Presentation modes

| Mode | Content |
|---|---|
| Concise (default) | The score, the fiscal year-end and filing, the industry class, the nine tests and the source. |
| `--details` | Adds each test's operands with their fiscal year-end and value. |
| `--diagnostics` | Adds the provider field, accession and filing date of every operand and the notes on how the inputs were assembled. |
| `--json` | The complete versioned typed result. |

In the side-by-side table of `ian runs compare` the strategy offers two cells, **Score** ("7 of 9", or "5 of 6" for a partial score) and **Completeness** ("complete" or "partial (1, 3, 4 unavailable)"), with the fiscal year-end and the filing's taxonomy.

## Data sources

All inputs come from SEC EDGAR structured filings: balance-sheet values at three fiscal year-ends, annual income and cash-flow values for two, common shares outstanding at two year-ends and the as-filed SIC code. The fiscal year-ends are found from the periods the filings report, not from filing dates. A company filing under IFRS has no long-term-debt mapping, so test 5 is unavailable for it. The strategy uses no market data and no quote.

## Limitations

- **Dilution is net.** Test 7 compares share counts. A company can issue shares and still pass when buybacks exceed issuance, as Apple did in fiscal 2024. The two counts are compared only when both come from the same filing and the same path, so a company whose prior-year count comes from an earlier filing has test 7 unavailable.
- **Net income is as reported.** The paper uses income before extraordinary items; net income is the modern equivalent. A company that does not tag net income has tests 1, 3 and 4 unavailable.
- **A screen, not a recommendation.** A pass or fail on a test is a statement about reported statements, not about price, scarcity or durability.

## Watchlist options

`watchlist create --analysis piotroski` and `watchlist add-selection --analysis piotroski` accept only the options every strategy takes, `--as-of` and `--no-cache`: the method has no tunable choice. It always uses SEC EDGAR data, matching the direct `piotroski` command. See [Local Research Workspace](../WORKSPACE.md#strategies-and-their-watchlist-options) for the watchlist commands that take them.

## Related documentation

- [Financial Math & Data Conventions](../FINANCE_MATH.md#piotroski-f-score-strategy) — normative formulas and conventions.
- [Glossary](../GLOSSARY.md#piotroski-f-score-terms) — terms used in this guide.
- [Analysis strategy guides](README.md)
