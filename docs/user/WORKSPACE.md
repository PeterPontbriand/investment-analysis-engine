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

The file is UTF-8, as all output is; see [`--json`](USAGE.md#--json--machine-readable-output).

`--save-run` saves exactly what you asked for, including a result the method could not calculate (missing data, a known ETF, and so on) — a "could not calculate" outcome is still a real, saved attempt, not a skipped one. Every direct command, `momentum` included, requires a ticker; there is no default ticker.

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

`--analysis` accepts any strategy alias in the [strategy table](#strategies-and-their-watchlist-options) — the same names used everywhere else in this guide — and each one's flags are exactly its direct command's own flags. Each strategy's flags are in the Watchlist options section of its guide, linked from the table below. A method that needs your own assumptions still needs them here: Graham Growth Value requires `--expected-growth`/`--aaa-yield` whether you run it directly or seed it into a watchlist, and omitting either is an `invalid_parameter` failure (exit `1`), not a silently-unselected method:

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
    [2] graham-number: as_of=None, bvps_override=None, eps_override=None, ...
    [3] graham-number: as_of=None, bvps_override=12.5, eps_override=None, ...
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

Every command that removes entries starts with `remove-`, and text output names methods by the same hyphenated names you type (the `--analysis` values in the [strategy table](#strategies-and-their-watchlist-options)). `--json` output keeps the stored method identifiers, listed in the same table, which never change.

### Renaming a watchlist

```bash
uv run ian watchlist rename "Core Holdings" "Long-Term Holdings"
```

Renaming is not destructive, so it never asks for confirmation. It prints `Renamed watchlist 'Core Holdings' to 'Long-Term Holdings'.` and then the renamed watchlist as `watchlist show` would. With `--json` it prints only the `watchlist show --json` document, or on a failure the failure document described in [USAGE](USAGE.md#--json--machine-readable-output). The watchlist keeps its ID and its entries. Changing only the capitalization (`core holdings` to `Core Holdings`) is allowed; renaming to another watchlist's name is exit `1`, and a blank new name is an `invalid_parameter` failure (exit `1`).

Saved Analysis Runs keep the name the watchlist had when they ran, by design: each run stores its own snapshot of the watchlist's name and ID, and a rename changes neither the snapshot nor anything else about a saved run. Today `runs list` and `runs show` do not print that snapshot.

If the watchlist holds an entry saved by an earlier version that this version can no longer read, the rename still happens. The command then prints the confirmation, followed by the one-line error that names the unreadable entry and the `remove-entry` command that removes it, and exits `1`; with `--json`, the confirmation goes to stderr and stdout holds the failure document (`reason_code` `stored_selection_unreadable`) in place of the error line.

### Deleting a watchlist

```bash
uv run ian watchlist delete "Scratch"
```

On an interactive terminal this shows the watchlist's name, ID and entry count and asks for confirmation; answering no deletes nothing and exits `1`. Anywhere else (a script, an agent, a pipe) there is no one to ask, so `--yes` is required and its absence is an `invalid_parameter` failure (exit `1`, the failure document with `--json`) before the database is opened:

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

### Strategies and their watchlist options

These are the flags `watchlist create --analysis METHOD` and `watchlist add-selection --analysis METHOD` accept, one method at a time. They mirror that method's direct command exactly — same names, same defaults, same required fields.

Each strategy's flags and notes are in the Watchlist options section of its guide, linked from this table:

<!-- BEGIN GENERATED strategy-table: written by uv run python -m scripts.generate_strategy_docs; generated, do not edit by hand. -->
| `--analysis` value | Strategy | Stored method id | Method-specific flags |
| :--- | :--- | :--- | :--- |
| `momentum` | Momentum | `sma_crossover` | [Watchlist options](strategies/MOMENTUM.md#watchlist-options) |
| `graham-number` | Graham Number | `graham_number` | [Watchlist options](strategies/GRAHAM_NUMBER.md#watchlist-options) |
| `graham-growth` | Graham Growth | `graham_growth_value` | [Watchlist options](strategies/GRAHAM_GROWTH.md#watchlist-options) |
| `fcf-growth` | FCF Growth | `reported_fcf_eps_cagr` | [Watchlist options](strategies/FCF_GROWTH.md#watchlist-options) |
<!-- END GENERATED strategy-table -->

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

A Momentum entry whose price provider fails, whose data fails a quality check, or whose history is too short is recorded the same way: as a run with the outcome `failed` or `unavailable`, not as an error without a run, so you can list it and replay it with `runs show`. Such a refresh exits 1.

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

The summary is described by `schemas/refresh-summary.schema.json`. Its first key is `schema_version` (currently `2`); it was unversioned before the `provider_rate_limited` code was added. Its last key is `provider_check`: when a job failed on a provider, one test request per implicated provider runs after the batch ends (never inside it, and once per provider however many jobs failed), and the summary lists what it found as `provider_id` and `verdict` entries, one per provider; `null` when no job failed on a provider. See [After a provider failure](USAGE.md#after-a-provider-failure-the-first-line) for the six verdicts. `--no-provider-check` or `IAN_PROVIDER_CHECK=false` turns the request off, and the entries are then present with `not_checked`. Because the request is sent before the summary is written, a failed refresh can take up to 12 seconds longer for each implicated provider, which `--no-provider-check` avoids. Each result carries `error` (the one message the application wrote for the failure, or `null`; it is the message and the code a direct command gives the same failure, and the detail is in the log) and `reason_code`: the stable code of the failure when the job raised (`error` is set) or when its saved run, or its unsaved outcome, has the status `failed`, otherwise `null`. A failed run's code is the one stored on the run (`failure_reason_code`): a provider code (`provider_unreachable`, `provider_rate_limited`, `provider_unexpected_response`, `provider_no_data`, or `provider_error` when the adapter could not classify the failure), `invalid_input` or `execution_error`. A job whose status is `unavailable` or `not_applicable` (a Graham Number for a company with negative earnings, for example) is an analysis outcome, not a failure, and carries no code. Branch on `reason_code`; `error` is for people. The codes are the ones in the [failure document](USAGE.md#--json--machine-readable-output). A refresh that cannot start at all (an unknown watchlist, a watchlist with no entries, an unreadable stored entry, storage that needs attention) writes that failure document instead of this summary and exits `1`; without `--json` it prints the message on standard error.

One ticker's failure never stops the rest of the watchlist: a method that could not calculate (or a storage hiccup for that one attempt) is recorded as an error for that ticker only, and every other ticker in the watchlist still runs. The exit code reflects the whole batch:

| Exit code | Meaning |
|---|---|
| `0` | Every attempt completed, or did not apply (a known ETF, and similar). |
| `1` | At least one attempt was unavailable, failed, or could not be saved; or the refresh could not start: the watchlist does not exist, or it has no entries (`watchlist_empty`). |
| `2` | The parser rejected the command line (an unknown option, a missing argument, a value of the wrong type); no command code ran. A value the command rejects itself, such as an invalid `--workers`, is an `invalid_parameter` failure with exit `1`. |
| `130` | You interrupted the refresh (Ctrl+C). |

### After a provider failure

When a job failed because a data provider failed, the text summary is preceded by one line per implicated provider
saying what one test request to it found, for example `Yahoo Finance is not answering: a test request also
failed.` The request is sent once per provider after the whole batch ends, however many tickers failed, and never
changes the summary or the exit code. `--no-provider-check` or `IAN_PROVIDER_CHECK=false` turns it off, and
`--json` never sends it and adds nothing to the summary. The seven wordings are explained in
[Usage](USAGE.md#after-a-provider-failure-the-first-line).

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

`runs show --json` prints the saved run's own strategy document, described by that strategy's schema in `schemas/` (for example `schemas/momentum.schema.json`, or `schemas/graham-number.schema.json`); a failure is the [failure document](USAGE.md#--json--machine-readable-output). The document's `provider_check` element is always `null` here: replaying a saved run sends no test request, and the verdict is never stored. A direct command that failed on a provider and the replay of its saved run differ in that one key.

### Comparing a refresh side by side

Every refresh records one refresh ID on the runs it saves, and `runs compare` shows those runs as one table: one row per ticker, in the order of the watchlist when it ran, and one column group per strategy, in the order of the strategy table above. Each group shows that strategy's headline numbers and the run's outcome, so you can read a watchlist across strategies without opening each run:

```bash
uv run ian runs compare 7c1a...
uv run ian runs compare 7c1a... --json
```

```text
Refresh 7c1a... · watchlist "Core" · 3 tickers · 4 strategies

         Momentum                      Graham Number                       Graham Growth                     FCF Growth
Ticker   Trend     RSI    Outcome      Max price      Margin  Outcome      Value          Margin  Outcome    FCF CAGR / FCF/share CAGR  EPS CAGR  Class          Outcome
ACME     Bullish   100.0  completed    36.69 USD      —       completed    66.28 USD      —       completed  10.2%                      17.6%     PASS           completed
BOLT     —         100.0  unavailable  —              —       unavailable  no stored run  —       —          —                          —         INDETERMINATE  unavailable
CRUX     —         —      failed       —              —       failed       —              —       failed     10.2%†                     17.6%     PASS           completed

† marks a value labelled FCF/share CAGR, not the first label of its column header

Period ends
  ACME     Graham Number: earnings input period end 2024-06-30 · Graham Growth: earnings input period end 2024-06-30 · FCF Growth: selected span end 2025-01-01
  BOLT     Graham Number: earnings input period end not recorded · FCF Growth: selected span end not recorded
  CRUX     Graham Number: earnings input period end not recorded · Graham Growth: earnings input period end not recorded · FCF Growth: selected span end 2025-01-01

Could not be read (stored under an older version, or for a strategy no longer declared): 9d1e...

Runs (open one with: ian runs show <run-id>)
  ACME     momentum       cbbd...
  ACME     graham-number  7a65...
  ACME     graham-growth  db73...
  ACME     fcf-growth     6b82...
  BOLT     momentum       2f07...
  BOLT     graham-number  b265...
  BOLT     fcf-growth     01fc...
  CRUX     momentum       9d1e...
  CRUX     graham-number  99e3...
  CRUX     graham-growth  27de...
  CRUX     fcf-growth     4136...
```

- The header of each column is its cell's name. A text value is the word the strategy's own output uses: Momentum's trend (`Bullish`, `Bearish`) and the FCF Growth screen (`PASS`, `FAIL`, `INDETERMINATE`). FCF Growth's first column is `FCF CAGR` for the total basis and `FCF/share CAGR` for the per-share basis, as each run was made. When the runs of one column give it different names, the header lists them all (`FCF CAGR / FCF/share CAGR`), every value whose name is not the first one carries a marker (`10.2%†`), and a line under the table says which name the marker stands for. The line appears only then.
- A per-share amount is written as a number followed by its currency (`36.69 USD`). When no currency was recorded, for example because you gave the earnings per share with `--eps`, it reads `142.10 (currency unspecified)`, and nothing guesses one.
- `—` means a value is absent: the run did not calculate it, or the strategy has none to show. A ticker with no run for a strategy that others have reads `no stored run`. Momentum's `Trend` is `—` when the history is too short to tell.
- Under the table, each ticker's fiscal period end is listed in the strategy's own words. The Graham strategies show the period end of the earnings input; their book value can come from another period, and no code compares them. Differing period ends are shown, not adjusted. A run that recorded no period end (earnings per share given with `--eps`, an FCF Growth run with no span, a failed run) reads `not recorded`. Momentum has no fiscal period and is not listed.
- The last block lists each run's full ID, so that you can open it with `runs show`.

The command rebuilds the table from what is stored. It calls no data provider, reads no cache and recalculates nothing, so the same refresh always gives the same table. It exits `0` whenever a table is shown, even if every run in it failed: a failed run is a row, not a failure of the command.

A refresh ID the command cannot find is reported as `analysis_run_not_found` (exit `1`). A refresh run with `--no-save` stores nothing, and storage cannot tell it from an unknown ID, so one message covers both. A refresh that holds two runs of the same ticker and strategy (a watchlist can hold two Momentum entries for one ticker) is refused as `invalid_input`, naming each; the table shows one run in each cell and never picks one for you.

A run saved by an older version of the application, or for a strategy this version no longer declares, still has its row. Its outcome is read from the stored record, its cells read `—`, and a line under the table lists its ID; `--json` states why its headline is missing. `runs show` refuses such a run with `unsupported_run_version`. Runs are never converted: a new version of a stored shape leaves older runs in the database, and they are refused by version rather than misread. A run whose stored evidence is invalid refuses the whole table, as it refuses `runs show`, with `invalid_stored_run` and the run's ID.

`runs compare --json` prints one document, described by `schemas/runs-compare.schema.json`, whose first key is `schema_version` (1).

`runs show` exits `0` even for a saved run whose own financial outcome was unavailable or failed — you asked to *see* a record, and it exists; the record's own status tells you what happened when it ran.
