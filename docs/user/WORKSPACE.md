# Local Research Workspace

The commands on this page let you save an analysis result durably, group tickers into a named [watchlist](GLOSSARY.md#watchlist) with their own analysis choices, and [refresh](GLOSSARY.md#refresh) a whole watchlist in one command. Everything here builds on the [ordinary analysis commands](USAGE.md); nothing here changes how those commands calculate a result.

All workspace commands read and write your local database (see [Local Database Operations](DATABASE.md)). No workspace command makes a network call on its own beyond what the underlying analysis method already needs.

## Saving a single result

Every direct analysis command accepts `--save-run` to persist that one attempt as a durable [Analysis Run](GLOSSARY.md#analysis-run), in addition to printing its normal output:

```bash
uv run financial-agents graham-number AAPL --save-run
```

The saved run's ID is printed on a separate line so it never disturbs `--json` output:

```bash
uv run financial-agents graham-number AAPL --save-run --json > result.json
```

`--save-run` saves exactly what you asked for, including a result the method could not calculate (missing data, a known ETF, and so on) — a "could not calculate" outcome is still a real, saved attempt, not a skipped one. `momentum --save-run` requires an explicit ticker; the configured default ticker is never saved implicitly.

Once a result is saved this way — or automatically by [refreshing a watchlist](#refreshing-a-watchlist) (see below) — it becomes available for later listing, filtering, and replaying. See [Browsing saved runs](#browsing-saved-runs) for how to do this. If you're wondering whether re-running the same request costs you anything, see [Saving vs. caching](#saving-vs-caching-theyre-not-the-same-thing) once you've read about watchlists and refreshing them below.

## Watchlists

A watchlist is a named, ordered list of [entries](GLOSSARY.md#entry) — each one a ticker paired with a [selection](GLOSSARY.md#selection) (an analysis method and its own configuration) — that you want to run and revisit as a group. There is no separate "list of tickers" and "list of methods": each entry stands on its own, so the same method can appear more than once, whether for different tickers or for the *same* ticker with different configuration (comparing Graham Number computed from SEC EDGAR data against Massive data, for example).

```bash
uv run financial-agents watchlist create "Core Holdings"
```

An empty watchlist like this one has nothing to refresh yet. The common case — one method across several tickers — is one command, using `--analysis` and that method's own flags:

```bash
uv run financial-agents watchlist create "Core Holdings" --analysis momentum AAPL MSFT KO
```

`--analysis` accepts `momentum`, `graham-number`, `graham-growth`, or `fcf-growth` — the same names used everywhere else in this guide — and each one's flags are exactly its direct command's own flags (see the table below). A method that needs your own assumptions still needs them here: Graham Growth Value requires `--expected-growth`/`--aaa-yield` whether you run it directly or seed it into a watchlist, and omitting either is a usage error, not a silently-unselected method:

```bash
uv run financial-agents watchlist create "Value Watch" --analysis graham-growth --expected-growth 6.0 --aaa-yield 4.4 AAPL
```

### Showing a watchlist

```bash
uv run financial-agents watchlist show "Core Holdings"
```

```text
Watchlist: Core Holdings
ID: 5f1c9e2a-...
Entries (4):
  AAPL:
    [1] sma_crossover: long_window=200, rsi_period=14, short_window=50
    [2] graham_number: as_of=None, bvps_override=None, eps_basis=three_year_average, security_provider_id=sec_edgar, ...
    [3] graham_number: as_of=None, bvps_override=12.5, eps_basis=ttm, security_provider_id=massive, ...
  MSFT:
    [4] sma_crossover: long_window=200, rsi_period=14, short_window=50
```

Entries are grouped by ticker by default; `--group-by method` groups them by method instead — useful once a watchlist has several tickers sharing the same handful of methods. Either way, the number in front of each entry is the same 1-based index `remove-entry` expects, so what you see is exactly what you'd type back in.

Add `--json` to `watchlist show` for the complete, machine-readable document — a flat, ordered list of entries, each carrying that same 1-based `index`:

```bash
uv run financial-agents watchlist show "Core Holdings" --json
```

List every watchlist you have:

```bash
uv run financial-agents watchlist list
```

### Adding, removing, and comparing entries

Add one method across one or more tickers to an existing watchlist the same way — `add-selection` is `create`'s seeding form, minus the creation:

```bash
uv run financial-agents watchlist add-selection "Core Holdings" AAPL MSFT --analysis graham-number
```

Adding the same method again for a ticker that already has it does not replace anything — it appends a second entry, so you can compare configurations side by side:

```bash
uv run financial-agents watchlist add-selection "Core Holdings" AAPL --analysis graham-number --data-provider massive --bvps 12.5
```

Remove one entry by the number `watchlist show` gives it:

```bash
uv run financial-agents watchlist remove-entry "Core Holdings" 3
```

Remove every entry for a ticker (across every method) or every entry for a method (across every ticker):

```bash
uv run financial-agents watchlist remove "Core Holdings" KO
uv run financial-agents watchlist disable "Core Holdings" --analysis graham-number
```

### Method-specific flags

These are the flags `watchlist create --analysis METHOD` and `watchlist add-selection --analysis METHOD` accept, one method at a time. They mirror that method's direct command exactly — same names, same defaults, same required fields.

| `--analysis` value | Flags | Notes |
|---|---|---|
| `momentum` | `--short-window`, `--long-window`, `--rsi-period` | Defaults match the configured Momentum policy. |
| `graham-number` | `--as-of`, `--data-provider`, `--no-cache`, `--eps`, `--eps-basis`, `--bvps`, `--current-price` | `--bvps` is required when `--data-provider massive`. |
| `graham-growth` | Same as `graham-number`, plus `--expected-growth`/`--aaa-yield` | The growth/yield assumptions are required; there is no default. |
| `fcf-growth` | `--growth-years`, `--forward-policy`, `--classification-basis`, `--currency` | Always uses SEC EDGAR data, matching the direct `fcf-growth` command. |

## Refreshing a watchlist

`refresh` runs every entry in one watchlist and, by default, saves each result as its own Analysis Run — automatically, every time, unlike the direct commands in [Saving a single result](#saving-a-single-result), which need an explicit `--save-run`. A watchlist is something you built on purpose, so refresh treats persisting its results as the point, not an extra step:

```bash
uv run financial-agents refresh "Core Holdings"
```

```text
Refresh 7c1a... for 'Core Holdings':
  3f9b...  AAPL       sma_crossover            completed
  3f9c...  AAPL       graham_number            completed
  3f9d...  MSFT       sma_crossover            completed
  3f9e...  MSFT       graham_number            unavailable
Counts: completed=3, unavailable=1
```

Add `--no-save` to preview current numbers across the watchlist without adding anything to its saved history — every entry still runs, but nothing is written to storage, so there is no Analysis Run ID to browse or replay afterward:

```bash
uv run financial-agents refresh "Core Holdings" --no-save
```

```text
Refresh 7c1a... for 'Core Holdings':
  (not saved)                           AAPL       sma_crossover            completed
  (not saved)                           AAPL       graham_number            completed
Counts: completed=2
```

Nothing is printed until the whole refresh finishes (or is interrupted) — there is no per-ticker progress chatter to parse. `--json` emits one final document instead, with the refresh ID, every result in the same order, and the same counts:

```bash
uv run financial-agents refresh "Core Holdings" --json
```

One ticker's failure never stops the rest of the watchlist: a method that could not calculate (or a storage hiccup for that one attempt) is recorded as an error for that ticker only, and every other ticker in the watchlist still runs. The exit code reflects the whole batch:

| Exit code | Meaning |
|---|---|
| `0` | Every attempt completed, or did not apply (a known ETF, and similar). |
| `1` | At least one attempt was unavailable, failed, or could not be saved. |
| `2` | A usage error — an unknown watchlist argument, or a watchlist with no entries to refresh. |
| `130` | You interrupted the refresh (Ctrl+C). |

### Concurrency and interruption

`--workers N` (1–4, default 2) controls how many tickers refresh concurrently. A higher number can finish a large watchlist faster, at the cost of a proportionally higher burst of calls to your configured data source(s) at once.

```bash
uv run financial-agents refresh "Core Holdings" --workers 4
```

Pressing Ctrl+C during a refresh stops starting new work; any ticker already in progress is left to finish and is still saved normally. A ticker that never started does not appear anywhere in the output — there is no placeholder "cancelled" row for work that never ran. The command then exits `130`.

A refresh's saved results are visible to `runs list`/`runs show` (see below) as soon as each one is saved — including from a second terminal, while a large refresh is still running.

## Saving vs. caching (they're not the same thing)

Two different things happen every time you run an analysis, and it's easy to mix them up:

- **Caching** happens automatically, every single time, whether or not you save anything. It's about the *raw data* a calculation needs — a company's earnings per share, its book value, a stretch of daily prices. The first time you ask for a ticker, that data is fetched from your configured provider (SEC EDGAR, Massive, Yahoo Finance) and kept locally. The next time you ask for the *same* data, it's reused instead of fetched again — you don't have to do anything for this, and there is no separate "cached result" to go find later.
- **Saving** is about the *finished result* — permanently keeping the full record of one specific analysis attempt, calculation and all, so you can find that exact result again later by browsing or by its ID (see [Browsing saved runs](#browsing-saved-runs)). A watchlist refresh always saves, automatically; a direct command only saves when you add `--save-run`, and does so the same way a refresh always does. This makes direct commands well suited to quick, temporary experimentation by default — nothing is kept unless you ask for it. A watchlist doesn't need more than one entry, either: if you find yourself repeatedly retyping the same direct command with `--save-run`, a single-entry watchlist you can `refresh` instead may be more convenient.

```text
Run a command
  |
  v
Step 1 - Get the raw data (earnings, prices, and so on)
         CACHING happens here, automatically, every time:
         reuse it if it's already stored and still fresh;
         otherwise fetch it once and store it for next time.
  |
  v
Step 2 - Calculate the result and show it on screen
         This always happens, whether or not anything is saved.
  |
  v
Step 3 - Save it? (optional)
         SAVING happens here automatically when this is a
         watchlist refresh; for other commands, saving only
         happens if you asked for it with --save-run.
         A saved result becomes a permanent Analysis Run
         you can find again later.
```

This matters most if you're paying for data access (a Massive subscription, for example): re-running the *same* request later does not re-fetch and does not re-charge, because caching already covers that automatically — for Graham and FCF/Earnings Growth data specifically, the local copy doesn't expire on its own by default (see [Local Database Operations](DATABASE.md#cache-and-telemetry-behavior) for the exact per-method rules, including the shorter-lived momentum and quote caches, which refresh sooner on purpose since you'd want current numbers there). You don't need to save a result just to avoid paying for it twice. Save a result when you want a permanent, addressable copy of it to come back to on purpose — a watchlist refresh does this for you automatically, because that's what a watchlist is for.

## Browsing saved runs

```bash
uv run financial-agents runs list
```

```text
3f9b...  AAPL       sma_crossover            completed      2026-09-19T14:02:11+00:00
3f9c...  AAPL       graham_number            completed      2026-09-19T14:02:12+00:00
```

Filter by ticker, method, outcome, or the refresh batch that produced a run:

```bash
uv run financial-agents runs list --ticker AAPL --method graham_number
uv run financial-agents runs list --status unavailable
uv run financial-agents runs list --refresh-id 7c1a...
uv run financial-agents runs list --json
```

Show one saved run in full, exactly as it was originally captured — replaying a saved run never re-fetches data or recalculates anything, so it always shows the same result it showed the moment it was saved, even if your configuration or a data provider has since changed:

```bash
uv run financial-agents runs show 3f9b...
uv run financial-agents runs show 3f9b... --details
uv run financial-agents runs show 3f9b... --diagnostics
uv run financial-agents runs show 3f9b... --json
```

`runs show` exits `0` even for a saved run whose own financial outcome was unavailable or failed — you asked to *see* a record, and it exists; the record's own status tells you what happened when it ran.
