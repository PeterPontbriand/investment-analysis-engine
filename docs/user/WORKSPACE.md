# Local Research Workspace

The commands on this page let you save an analysis result durably, group tickers into a named [watchlist](GLOSSARY.md#watchlist) with their own analysis choices, and [refresh](GLOSSARY.md#refresh) a whole watchlist in one command. Everything here builds on the [ordinary analysis commands](USAGE.md); nothing here changes how those commands calculate a result.

All workspace commands read and write your local database (see [Local Database Operations](DATABASE.md)). No workspace command makes a network call on its own beyond what the underlying analysis method already needs.

## Saving a single result

Every direct analysis command accepts `--save-run` to persist that one attempt as a durable [Analysis Run](GLOSSARY.md#analysis-run), in addition to printing its normal output:

```bash
uv run ian graham-number AAPL --save-run
```

The saved run's ID is printed on a separate line so it never disturbs `--json` output:

```bash
uv run ian graham-number AAPL --save-run --json > result.json
```

`--save-run` saves exactly what you asked for, including a result the method could not calculate (missing data, a known ETF, and so on) — a "could not calculate" outcome is still a real, saved attempt, not a skipped one. `momentum --save-run` requires an explicit ticker; the configured default ticker is never saved implicitly.

Once a result is saved this way — or automatically by [refreshing a watchlist](#refreshing-a-watchlist) (see below) — it becomes available for later listing, filtering, and replaying. See [Browsing saved runs](#browsing-saved-runs) for how to do this. If you're wondering whether re-running the same request costs you anything, see [Saving vs. caching](#saving-vs-caching-theyre-not-the-same-thing) once you've read about watchlists and refreshing them below.

## Watchlists

A watchlist is a named, ordered list of [entries](GLOSSARY.md#entry) — each one a ticker paired with a [selection](GLOSSARY.md#selection) (an analysis method and its own configuration) — that you want to run and revisit as a group. There is no separate "list of tickers" and "list of methods": each entry stands on its own, so the same method can appear more than once, whether for different tickers or for the *same* ticker with different configuration (comparing Graham Number under two different overrides, for example).

```bash
uv run ian watchlist create "Core Holdings"
```

An empty watchlist like this one has nothing to refresh yet. The common case — one method across several tickers — is one command, using `--analysis` and that method's own flags:

```bash
uv run ian watchlist create "Core Holdings" --analysis momentum AAPL MSFT KO
```

`--analysis` accepts `momentum`, `graham-number`, `graham-growth`, or `fcf-growth` — the same names used everywhere else in this guide — and each one's flags are exactly its direct command's own flags (see the table below). A method that needs your own assumptions still needs them here: Graham Growth Value requires `--expected-growth`/`--aaa-yield` whether you run it directly or seed it into a watchlist, and omitting either is a usage error, not a silently-unselected method:

```bash
uv run ian watchlist create "Value Watch" --analysis graham-growth --expected-growth 6.0 --aaa-yield 4.4 AAPL
```

### Showing a watchlist

```bash
uv run ian watchlist show "Core Holdings"
```

```text
Watchlist: Core Holdings
ID: 5f1c9e2a-...
Entries (4):
  AAPL:
    [1] momentum: long_window=200, rsi_period=14, short_window=50
    [2] graham-number: as_of=None, bvps_override=None, eps_basis=three_year_average, security_provider_id=sec_edgar, ...
    [3] graham-number: as_of=None, bvps_override=12.5, eps_basis=three_year_average, security_provider_id=sec_edgar, ...
  MSFT:
    [4] momentum: long_window=200, rsi_period=14, short_window=50
```

Entries are grouped by ticker by default; `--group-by method` groups them by method instead — useful once a watchlist has several tickers sharing the same handful of methods. Either way, the number in front of each entry is the same 1-based index `remove-entry` expects, so what you see is exactly what you'd type back in.

Add `--json` to `watchlist show` for the complete, machine-readable document — a flat, ordered list of entries, each carrying that same 1-based `index`:

```bash
uv run ian watchlist show "Core Holdings" --json
```

The document is described by `schemas/watchlist.schema.json`, which `watchlist rename --json` shares. It has no `schema_version`: a change to its keys or types shows in the schema. Its `created_at` and `updated_at` (`null` until the watchlist is first changed) are written with their UTC offset, as `+00:00`. Each entry's `selection` is the stored selection of that entry's method, told apart by its `method_id`; its `as_of`, when set, is written the same way (`+00:00`; it was `Z` before the workspace documents were typed, so a reader that matched the literal `Z` must accept the offset form).

List every watchlist you have:

```bash
uv run ian watchlist list
```

### Adding, removing, and comparing entries

Add one method across one or more tickers to an existing watchlist the same way — `add-selection` is `create`'s seeding form, minus the creation:

```bash
uv run ian watchlist add-selection "Core Holdings" AAPL MSFT --analysis graham-number
```

Adding the same method again for a ticker that already has it does not replace anything — it appends a second entry, so you can compare configurations side by side:

```bash
uv run ian watchlist add-selection "Core Holdings" AAPL --analysis graham-number --bvps 12.5
```

Remove one entry by the number `watchlist show` gives it:

```bash
uv run ian watchlist remove-entry "Core Holdings" 3
```

Remove every entry for a ticker (across every method) or every entry for a method (across every ticker):

```bash
uv run ian watchlist remove-ticker "Core Holdings" KO
uv run ian watchlist remove-method "Core Holdings" --analysis graham-number
```

Every command that removes entries starts with `remove-`, and text output names methods by the same hyphenated names you type (`momentum`, `graham-number`, `graham-growth`, `fcf-growth`). `--json` output keeps the stored method identifiers (`sma_crossover`, `graham_number`, `graham_growth_value`, `reported_fcf_eps_cagr`), which never change.

### Renaming a watchlist

```bash
uv run ian watchlist rename "Core Holdings" "Long-Term Holdings"
```

Renaming is not destructive, so it never asks for confirmation. It prints `Renamed watchlist 'Core Holdings' to 'Long-Term Holdings'.` and then the renamed watchlist as `watchlist show` would. With `--json` it prints only the `watchlist show --json` document, or on a failure the failure document described in [USAGE](USAGE.md#--json--machine-readable-output). The watchlist keeps its ID and its entries. Changing only the capitalization (`core holdings` to `Core Holdings`) is allowed; renaming to another watchlist's name is exit `1`, and a blank new name is a usage error (exit `2`).

Saved Analysis Runs keep the name the watchlist had when they ran, by design: each run stores its own snapshot of the watchlist's name and ID, and a rename changes neither the snapshot nor anything else about a saved run. Today `runs list` and `runs show` do not print that snapshot.

If the watchlist holds an entry saved by an earlier version that this version can no longer read, the rename still happens. The command then prints the confirmation, followed by the one-line error that names the unreadable entry and the `remove-entry` command that removes it, and exits `1`; with `--json`, the confirmation goes to stderr and stdout holds the failure document (`reason_code` `stored_selection_unreadable`) in place of the error line.

### Deleting a watchlist

```bash
uv run ian watchlist delete "Scratch"
```

On an interactive terminal this shows the watchlist's name, ID and entry count and asks for confirmation; answering no deletes nothing and exits `1`. Anywhere else (a script, an agent, a pipe) there is no one to ask, so `--yes` is required and its absence is a usage error (exit `2`) before the database is opened:

```bash
uv run ian watchlist delete "Scratch" --yes
```

Deleting removes the watchlist and its entries. **Saved Analysis Runs are kept**: each run carries its own snapshot of the watchlist's name and ID, so `runs list` and `runs show` still work afterward. Creating a new watchlist with the same name gives it a new ID; the old runs stay tied to the old one.

An unknown name is exit `1`, like every other watchlist command. For idempotent cleanup, `--missing-ok` turns that into exit `0` with nothing deleted:

```bash
uv run ian watchlist delete "Scratch" --yes --missing-ok
```

`--json` prints one document, with `watchlist` holding the same document `watchlist show --json` prints for the watchlist as it was just before deletion (or `null` when nothing was deleted):

```text
{"requested_name": "Scratch", "deleted": true, "watchlist": {...}}
{"requested_name": "Nonexistent", "deleted": false, "watchlist": null}
```

The document is described by `schemas/watchlist-delete.schema.json` and has no `schema_version`.

A watchlist holding an entry saved by an earlier version, which this version can no longer read, is still deleted. In text mode that succeeds quietly. With `--json` there is no entry document to print, so the confirmation goes to stderr, stdout holds the failure document (`reason_code` `stored_selection_unreadable`, its `reason` naming the unreadable entry) and the exit code is `1`.

### Method-specific flags

These are the flags `watchlist create --analysis METHOD` and `watchlist add-selection --analysis METHOD` accept, one method at a time. They mirror that method's direct command exactly — same names, same defaults, same required fields.

| `--analysis` value | Flags | Notes |
|---|---|---|
| `momentum` | `--short-window`, `--long-window`, `--rsi-period`, `--as-of`, `--no-cache` | Window defaults match the configured Momentum policy. `--no-cache` bypasses the historical price cache. |
| `graham-number` | `--as-of`, `--data-provider`, `--no-cache`, `--eps`, `--eps-basis`, `--bvps`, `--current-price` | |
| `graham-growth` | Same as `graham-number`, plus `--expected-growth`/`--aaa-yield` | The growth/yield assumptions are required; there is no default. |
| `fcf-growth` | `--growth-years`, `--forward-policy`, `--classification-basis`, `--currency` | Always uses SEC EDGAR data, matching the direct `fcf-growth` command. |

## Refreshing a watchlist

`refresh` runs every entry in one watchlist and, by default, saves each result as its own Analysis Run — automatically, every time, unlike the direct commands in [Saving a single result](#saving-a-single-result), which need an explicit `--save-run`. A watchlist is something you built on purpose, so refresh treats persisting its results as the point, not an extra step:

```bash
uv run ian refresh "Core Holdings"
```

```text
Refresh 7c1a... for 'Core Holdings':
  3f9b...  AAPL       momentum                 completed
  3f9c...  AAPL       graham-number            completed
  3f9d...  MSFT       momentum                 completed
  3f9e...  MSFT       graham-number            unavailable
Counts: completed=3, unavailable=1
```

Add `--no-save` to preview current numbers across the watchlist without adding anything to its saved history — every entry still runs, but nothing is written to storage, so there is no Analysis Run ID to browse or replay afterward:

```bash
uv run ian refresh "Core Holdings" --no-save
```

```text
Refresh 7c1a... for 'Core Holdings':
  (not saved)                           AAPL       momentum                 completed
  (not saved)                           AAPL       graham-number            completed
Counts: completed=2
```

Nothing is printed until the whole refresh finishes (or is interrupted) — there is no per-ticker progress chatter to parse. `--json` emits one final document instead, with the refresh ID, every result in the same order, and the same counts:

```bash
uv run ian refresh "Core Holdings" --json
```

The summary is described by `schemas/refresh-summary.schema.json` and has no `schema_version`. Each result carries `error` (the failure's own text, or `null`) and `reason_code`: the stable code of the failure when `error` is set, otherwise `null`. Branch on `reason_code`; `error` is for people. The codes are the ones in the [failure document](USAGE.md#--json--machine-readable-output). A refresh that cannot start at all (an unknown watchlist, a watchlist with no entries, an unreadable stored entry, storage that needs attention) writes that failure document instead of this summary and exits `1`; without `--json` it prints the sentence on standard error.

One ticker's failure never stops the rest of the watchlist: a method that could not calculate (or a storage hiccup for that one attempt) is recorded as an error for that ticker only, and every other ticker in the watchlist still runs. The exit code reflects the whole batch:

| Exit code | Meaning |
|---|---|
| `0` | Every attempt completed, or did not apply (a known ETF, and similar). |
| `1` | At least one attempt was unavailable, failed, or could not be saved; or the refresh could not start: the watchlist does not exist, or it has no entries (`watchlist_empty`). |
| `2` | A usage error, such as an invalid `--workers`. |
| `130` | You interrupted the refresh (Ctrl+C). |

### Concurrency and interruption

`--workers N` (1–4, default 2) controls how many tickers refresh concurrently. A higher number can finish a large watchlist faster, at the cost of a proportionally higher burst of calls to your configured data source(s) at once.

```bash
uv run ian refresh "Core Holdings" --workers 4
```

Pressing Ctrl+C during a refresh stops starting new work; any ticker already in progress is left to finish and is still saved normally. A ticker that never started does not appear anywhere in the output — there is no placeholder "cancelled" row for work that never ran. The command then exits `130`.

A refresh's saved results are visible to `runs list`/`runs show` (see below) as soon as each one is saved — including from a second terminal, while a large refresh is still running.

## Saving vs. caching (they're not the same thing)

Two different things happen every time you run an analysis, and it's easy to mix them up:

- **Caching** happens automatically, every single time, whether or not you save anything. It's about the *raw data* a calculation needs — a company's earnings per share, its book value, a stretch of daily prices. The first time you ask for a ticker, that data is fetched from your configured provider (SEC EDGAR, Yahoo Finance) and kept locally. The next time you ask for the *same* data, it's reused instead of fetched again — you don't have to do anything for this, and there is no separate "cached result" to go find later.
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

This matters most if a data source charges or throttles you: re-running the *same* request later does not re-fetch and does not re-charge, because caching already covers that automatically — for Graham and FCF/Earnings Growth data specifically, the local copy doesn't expire on its own by default (see [Local Database Operations](DATABASE.md#cache-and-telemetry-behavior) for the exact per-method rules, including the shorter-lived momentum and quote caches, which refresh sooner on purpose since you'd want current numbers there). You don't need to save a result just to avoid paying for it twice. Save a result when you want a permanent, addressable copy of it to come back to on purpose — a watchlist refresh does this for you automatically, because that's what a watchlist is for.

## Browsing saved runs

```bash
uv run ian runs list
```

```text
3f9b...  AAPL       momentum                 completed      2026-09-19T14:02:11+00:00
3f9c...  AAPL       graham-number            completed      2026-09-19T14:02:12+00:00
```

Filter by ticker, analysis, outcome, or the refresh batch that produced a run. `--analysis` (or `-a`) takes the same names as the watchlist commands:

```bash
uv run ian runs list --ticker AAPL --analysis graham-number
uv run ian runs list --status unavailable
uv run ian runs list --refresh-id 7c1a...
uv run ian runs list --json
```

`runs list --json` prints one JSON array, described by `schemas/runs-list.schema.json`; it has no `schema_version`. Each `completed_at` is written with its UTC offset, as `+00:00` (it was written as `Z` before the workspace documents were typed, so a reader that matched the literal `Z` must accept the offset form).

Show one saved run in full, exactly as it was originally captured — replaying a saved run never re-fetches data or recalculates anything, so it always shows the same result it showed the moment it was saved, even if your configuration or a data provider has since changed:

```bash
uv run ian runs show 3f9b...
uv run ian runs show 3f9b... --details
uv run ian runs show 3f9b... --diagnostics
uv run ian runs show 3f9b... --json
```

`runs show --json` prints the saved run's own strategy document, described by that strategy's schema in `schemas/` (for example `schemas/momentum.schema.json`, or `schemas/graham-number.schema.json`); a failure is the [failure document](USAGE.md#--json--machine-readable-output).

`runs show` exits `0` even for a saved run whose own financial outcome was unavailable or failed — you asked to *see* a record, and it exists; the record's own status tells you what happened when it ran.
