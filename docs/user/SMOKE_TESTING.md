# Smoke Testing Commands

Run this short set of commands by hand after installing or updating Investment Analysis Engine. It is for a person checking the command line from a terminal they opened themselves, and judging the output as a user would see it. On Windows, a terminal started by another application, such as an AI assistant's desktop app, may see different settings and data folders, and so a different database. An agent or script may rehearse these steps, but its run is not a formal smoke test.

Run every command in one terminal, from the installation folder (the folder `git clone` created). Every command uses the `ian` command from [Make the `ian` command available](INSTALLATION.md#make-the-ian-command-available).

The test needs live provider access. It checks that the command line starts, that the data providers answer, that each analysis command produces a well-formed result, and that the watchlist workflow saves, lists and replays results. It does not try to cover every option.

Provider data changes over time, so exact values are not prescribed. For each command, confirm that the output is well-formed, identifies the requested ticker and method, contains no traceback or `NaN`/infinity, and either produces a typed result or explains classified unavailability clearly. Every step has a number (S1, S2, ... then A1, A2, ... and B1, B2, ...) so that [the record](#recording-the-result) can refer to it.

## Before you start

S1. Get a current installation.

- No copy yet: follow [Installation, section 1](INSTALLATION.md#1-installation), which ends with making the `ian` command available, then [section 2](INSTALLATION.md#2-configuration) to configure it.
- A copy already exists: follow [Updating an existing installation](INSTALLATION.md#updating-an-existing-installation), which first has you make the `ian` command available if it is not yet. It never changes your settings, your database or your logs.

Also check two prerequisites:

- Outbound access to Yahoo Finance and SEC EDGAR must be allowed. If a provider does not answer later, see [Installation, troubleshooting](INSTALLATION.md#4-troubleshooting).
- The SEC EDGAR application identity must be configured, as [Installation, SEC EDGAR identification](INSTALLATION.md#sec-edgar-identification) explains.

### Use a throwaway database

The smoke test saves analysis runs and a watchlist. A saved run cannot be deleted, and an empty database makes the expectations below exact, so the test runs against a dedicated throwaway SQLite file and not against your real database.

S2. Open a new terminal, change to the installation folder, and check your real database once, before you set `IAN_DATABASE_URL` for the throwaway file. Do not unset or change any `IAN_DATABASE_URL` you already use, since the check must see your real database exactly as you normally run it. This command only reads; it writes nothing:

```powershell
ian db status
```

Expect `State: ready`, or `State: missing` with `Database is not initialized yet.` if you have never run an analysis (there is no database yet, which is correct, although the command then exits with status 1). If it reports `upgrade_required`, follow [First use and explicit upgrades](DATABASE.md#first-use-and-explicit-upgrades) before going on. For any other state, stop and use [Local Database Operations](DATABASE.md).

S3. In that same terminal, point the session at a new throwaway file. This creates a new timestamped folder under the repository's ignored `.tmp/smoke/` and sets an absolute URL from it, so there is no folder to prepare. PowerShell:

```powershell
$smoke = Join-Path (git rev-parse --show-toplevel) ".tmp/smoke/$(Get-Date -Format yyyyMMdd-HHmmss)"
New-Item -ItemType Directory -Force $smoke | Out-Null
$env:IAN_DATABASE_URL = "sqlite:///$($smoke -replace '\\', '/')/smoke-test.sqlite3"
```

Git Bash, macOS or Linux:

```bash
smoke="$(git rev-parse --show-toplevel)/.tmp/smoke/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$smoke"
export IAN_DATABASE_URL="sqlite:///$smoke/smoke-test.sqlite3"
```

Each run gets its own folder, so a repeated smoke test also starts with an empty database. The setting lasts until the terminal closes. [Local Database Operations](DATABASE.md) explains the URL forms.

S4. Create the file's schema and confirm it is ready:

```powershell
ian db upgrade
ian db status
```

Expect the second command to name the throwaway file and report `State: ready`.

### Check the providers

S5. Check that the data providers answer:

```powershell
ian health
ian health --json
```

Expect every provider to be reported as answering (`ok`), and the JSON to parse and carry an integer `schema_version`. If a provider is not answering, stop here and use the troubleshooting section of [Installation](INSTALLATION.md#4-troubleshooting): the later steps would only repeat that provider's failure.

## A. Direct analysis

A1. Confirm that the CLI starts and lists its commands:

```powershell
ian --help
```

Expect every strategy command plus `evaluate`, `health`, `serve`, `refresh`, `watchlist` and `runs`. The `db` commands stay hidden from this list. Shell-setup options such as `--show-completion` and `--install-completion` must not appear; help must not emit shell scripts.

A2. Run the default Momentum analysis over a liquid U.S. equity:

```powershell
ian momentum AAPL
```

A3. Exercise custom SMA and RSI periods with detailed market-data context:

```powershell
ian momentum MSFT --short-window 10 --long-window 30 --rsi-period 14 --details
```

A4. Inspect Momentum diagnostics for a defensive consumer company:

```powershell
ian momentum KO --diagnostics
```

Confirm that resolver/provider or cache events are present without duplicated messages. The price is an adjusted historical Close with an observation date, not a live quote. A zero crossover means no transition between two valid SMA pairs; insufficient transition history must have an unavailable reason.

A5. Immediately repeat the same Momentum request in JSON to inspect cache provenance:

```powershell
ian momentum KO --json
```

With historical caching enabled and the preceding snapshot still eligible, expect `data_resolution.source_kind` to be `cache`, with the original retrieval time retained and cache evidence in `diagnostics`. Expect the top-level `schema_version` to be an integer. Cache reuse must not relabel the snapshot as freshly retrieved provider data.

A6. Inspect the default SEC-backed Graham Number calculation, quote comparison and detailed lineage:

```powershell
ian graham-number KO --details
```

Check quote retrieval separately from market observation time; Yahoo's missing exchange timestamp must be stated honestly. Expect a compact explanation of EPS, book value, the formula and material assumptions. Inferred preferred-share zero must be qualified as not explicitly reported; repeated share components should appear once. BVPS must consistently use its supported fiscal-year-end basis. Filing venue must be identified as historical evidence. Raw provider fields, context IDs and recursive notes belong in diagnostics/JSON. With compatible inputs, expect a numeric price relationship; unexplained unavailability requires investigation.

A7. Immediately repeat Graham Number in JSON to check quote reuse and typed evidence:

```powershell
ian graham-number KO --json
```

Expect an integer top-level `schema_version` and `price_comparison.quote_freshness` with original retrieval time, response age and the configured maximum (300 seconds by default). An eligible cache hit retains its retrieval time; an expired or unverifiable quote must refresh or explain unavailability, never silently fall back to stale data. A missing market timestamp remains `null`. If legacy-input evidence prevents comparison, rerun A6 with `--no-cache`; continuing unavailability requires its own supported explanation, not automatic acceptance of the refresh hint.

A8. Exercise a historical Graham boundary and its resolver diagnostics:

```powershell
ian graham-number MSFT --as-of 2025-12-31 --diagnostics
```

An unavailable Graham Number must identify the unresolved financial input in the opening, before diagnostics, and the command exits with status 1. If preferred-share evidence cannot be established, explain why BVPS cannot be derived and state that missing preferred-share data is not assumed to be zero. Direct common shares plus absent preferred-share concepts do not satisfy the supported SEC zero-preferred inference rules. Distinguish a price that was not requested after required-input failure from an attempted quote retrieval that failed. No price comparison is performed without a calculated Graham Number; current-only quote adapters also cannot supply a historical quote. Retain resolver evidence in diagnostics, and do not use information published after the requested boundary.

A9. Run the separate forecast-dependent Graham Growth Value method with explicit assumptions:

```powershell
ian graham-growth KO --expected-growth 5 --aaa-yield 4.5 --details
```

Expect the growth and the AAA yield to be shown as user-supplied assumptions, with a warning that the yield is not provider-verified.

A10. Run the default historical Free Cash Flow & Earnings Growth screen:

```powershell
ian fcf-growth AAPL
```

A11. Exercise a strict horizon, FCF-per-share classification, and detailed annual evidence:

```powershell
ian fcf-growth MSFT --growth-years 3 --classification-basis fcf-per-share --details
```

Confirm that the explanation refers to FCF **per diluted share** and agrees with that measure's growth. Expect a compact annual table with currency, share counts and formulas. Detailed source/cache origin and derivation notes remain available in diagnostics/JSON. Unsupported optional consensus or market-cap metrics should carry reasons rather than substituted zeroes. A calculated `FAIL` is a valid screen result, not an execution error.

A12. Run the Piotroski F-Score with each test's operands:

```powershell
ian piotroski KO --details
```

Expect a heading that names the company, its ticker and the Piotroski F-Score, the score with its completeness, the fiscal year-end and the filing, and one line for each test with a pass, fail or unavailable verdict. Under the details heading, each test shows the operands it used, each with its value and year-end. A test that is unavailable carries a classified reason on its line instead of a guessed verdict, and a partial score such as "6 of 8" is a valid result: the score's usual reading applies to complete scores only.

## B. Workspace

These steps save results to the throwaway database. They use a watchlist named `Smoke Test`; [Local Research Workspace](WORKSPACE.md) explains each command in detail.

B1. Create a watchlist:

```powershell
ian watchlist create "Smoke Test"
```

Expect the name, a watchlist ID and `Entries (0)`.

B2. Add Momentum entries for two tickers:

```powershell
ian watchlist add-selection momentum "Smoke Test" KO MSFT
```

Expect one numbered entry for each ticker, with the strategy's settings filled in.

B3. Add a Piotroski entry for one ticker:

```powershell
ian watchlist add-selection piotroski "Smoke Test" KO
```

Expect a third entry, numbered 3, and the first two unchanged.

B4. Show the watchlist:

```powershell
ian watchlist show "Smoke Test"
```

Expect all three entries, grouped by ticker and numbered from 1.

B5. Refresh the watchlist, which runs every entry and saves each result:

```powershell
ian refresh "Smoke Test"
```

Expect nothing to print until the refresh finishes, then a summary headed by a refresh ID that lists every entry with its ticker, method and outcome, and a run ID for each saved run, followed by the counts. Note the refresh ID and one run ID; the next steps use them. A result the method could not calculate is still a saved run with its own outcome.

B6. List the runs of that refresh:

```powershell
ian runs list --refresh-id <refresh ID>
```

Expect exactly the runs that B5 reported, most recently completed first, each with its run ID, ticker, method, outcome and completion time.

B7. Compare the refresh:

```powershell
ian runs compare <refresh ID>
```

Expect one row per ticker and one column group per strategy. A ticker that has no entry for a strategy shows that there is no stored run for it, not an empty or zero value. The listing below the table gives a run ID for each stored run.

B8. Replay one stored run in detail:

```powershell
ian runs show <run ID> --details
```

Expect the stored run's own report, including the details, rebuilt from the evidence the run captured, not from a new provider request. It must agree with what B5 reported for that run.

B9. Refresh again as JSON:

```powershell
ian refresh "Smoke Test" --json
```

Expect one JSON document that parses and carries an integer `schema_version`, the refresh ID, the counts and one result for each entry. This refresh saves a new set of runs; the earlier ones stay.

B10. Delete the watchlist:

```powershell
ian watchlist delete "Smoke Test" --yes
```

Expect a confirmation that names the watchlist and says that saved Analysis Runs are kept. The runs from both refreshes remain in the throwaway database, which `ian runs list` shows.

When the test is finished, close the terminal you used for it, which discards the throwaway `IAN_DATABASE_URL` setting, and then delete the throwaway file, together with any `-wal` and `-shm` files beside it.

## Review checklist

- Help and option parsing complete without a traceback.
- Investor-facing output uses readable statuses, warnings, and limitations.
- Successful text reports begin with the instrument name/ticker and analysis heading. Routine cache rejection or refresh must not print an internal quality warning before that heading; diagnostic evidence remains available in `--diagnostics` and JSON.
- Detail and diagnostic views retain provider, period, freshness, and resolution evidence.
- JSON output parses as JSON and uses `null`, never non-standard numeric sentinels. Every JSON document carries an integer `schema_version`. If a runtime failure occurs during any command run with `--json` (S5, A5, A7 and B9), stdout must still contain a versioned failure document with `result: null` and a reason; `$LASTEXITCODE` must be nonzero. Historical numeric-quality failures should identify affected fields/dates without dumping raw payloads or secrets. Do not manufacture a live provider failure merely to complete this smoke test.
- Historical requests do not use information published after the requested boundary.
- Optional quote failure does not discard an otherwise valid Graham calculation.
- If a text run does fail on a provider (do not manufacture one), its first line says what a test request to that provider found, or that it was not checked; the seven wordings are explained in [Installation, troubleshooting](INSTALLATION.md#4-troubleshooting). `--json` output carries no such line.
- Any unavailable result gives a classified reason rather than silently substituting zero.
- The workspace steps leave the database consistent: every run the refresh reported can be listed and replayed, and deleting the watchlist removes no run.

Do not treat a changed market value, screening classification, or unavailable optional quote as a deployment failure by itself. Investigate malformed output, unclassified exceptions, unsupported-option errors for the commands above, missing provenance, or unexplained provider failures.

## Recording the result

Copy this block into your notes and fill it in. Mark each step `pass`, `fail` or `note`, with a few words for anything that is not a plain pass.

```text
Smoke test record
Date:
Commit (git rev-parse --short HEAD):
Operating system:
Python version (uv run python --version):
yfinance version (providers[].library.version in: ian health --json):

S1 (installation current):
S2 (database status, real database):
S3 (throwaway database set):
S4 (setup and status, throwaway database):
S5 (health, text and JSON):
A1:
A2:
A3:
A4:
A5:
A6:
A7:
A8:
A9:
A10:
A11:
A12:
B1:
B2:
B3:
B4:
B5:
B6:
B7:
B8:
B9:
B10:

Issues filed for failures:
```

Record a formal run as one GitHub issue titled `Smoke test <date> <short commit>`, with this block as its body. Give each failure its own issue (or fix), list them under "Issues filed for failures", and close the run's issue once every failure has its own issue or fix.

## What smoke testing does not cover

A smoke test shows that the installed application works against live providers on one day; it proves nothing about boundaries that live data cannot force. Exact quote-expiry boundaries, stale-refresh failures, first-valid-SMA transitions, invalid preloaded frames and historical execution-clock selection belong to deterministic regression tests. The local HTTP API is not part of this document: its automated tests and the testing of the GUI application cover it.
