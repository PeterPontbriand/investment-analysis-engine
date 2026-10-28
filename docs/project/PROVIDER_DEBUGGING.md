# Provider Debugging Runbook

For the maintainer. It covers how to tell whether Yahoo (through yfinance) and SEC EDGAR still answer in the shape
the adapters read, how to read the kept results of the scheduled run, and what to look at when a check fails.
Setup problems on a new machine are covered by the
[installation troubleshooting section](../user/INSTALLATION.md); the manual command walk-through is
[Smoke Testing](../user/SMOKE_TESTING.md).

The checks assert response *shape* (the fields and columns an adapter reads), never a value. They make real
requests, at most three per check, and never run in the default test run, the managed quality gate or the normal
continuous-integration workflow. The local Ollama service is not an online dependency and is not checked.

The check bodies live in one module, [`investment_analysis_engine/data/provider_checks.py`](../../investment_analysis_engine/data/provider_checks.py). The live
tests and the `health` command call the same functions, so a probe is written once. The exceptions are the SEC filing-header test, which makes a single request to the SEC archive for a filing header and checks the fields the industry-class reader uses, the SEC cover test, which makes a single request to the SEC archive for the rendered cover of an annual filing and checks the rows the listing check reads (the document type, the registrant's CIK and, for each registered security, its title, trading symbol and exchange), and the Yahoo split-history test, which makes two requests (the unadjusted download and the currency lookup) and checks the columns, the split ratios and the adjustment date.

## 1. Running the checks

| What | Command |
| :--- | :--- |
| Every provider, printed one line each | `uv run ian health` |
| One provider | `uv run ian health --provider yfinance` or `--provider sec_edgar` |
| The same results as one JSON document, for a script | `uv run ian health --json`, with or without `--provider` |
| The live tests, with kept results (PowerShell) | `& scripts/run-live-checks.ps1` |
| The live tests, with kept results (Git Bash, Linux, macOS) | `bash scripts/run-live-checks.sh` |
| One live test only | add `-k yahoo` or `-k sec_edgar` to either wrapper |
| The SEC filing-header test only | add `-k filing_header` to either wrapper |
| The SEC cover test only | add `-k sec_edgar_cover` to either wrapper |
| The Yahoo split-history test only | add `-k split_adjusted` to either wrapper |
| The live tests directly | `uv run pytest --live tests/live` |

`ian health` prints `<provider>: <verdict> (probe: <description>, <elapsed> s)`, with the failure detail after a
dash when the check failed. The exit status is 0 when every selected check passes and 1 otherwise; an unknown
`--provider` value exits 2 and lists the valid ids.

`ian health --json` writes one document to standard output and nothing else, whether or not every check passed.
It is a report, not the failure document: the exit status says whether every check passed, and the document
says what each check found. It is described by
[`schemas/provider-health.schema.json`](../../schemas/provider-health.schema.json) and has this shape:

```json
{
  "schema_version": 3,
  "providers": [
    {
      "provider_id": "yfinance",
      "verdict": "ok",
      "probe": "connection to query2.finance.yahoo.com, AAPL quote and daily history",
      "elapsed_seconds": 0.84,
      "detail": null,
      "library": {"name": "yfinance", "version": "1.6.0"}
    },
    {
      "provider_id": "sec_edgar",
      "verdict": "not_configured",
      "probe": "AAPL ticker map and company facts",
      "elapsed_seconds": 0.0,
      "detail": "SEC EDGAR access is not configured. ...",
      "library": null
    }
  ]
}
```

Branch on `verdict`, which is one of the seven words in the table below with underscores (`rate_limited`,
`unexpected_response`, `no_data`, `not_configured`). `probe` and `detail` are messages for people and may change. `detail` is
`null` when the check passed. `library` names the library the application reaches the provider through and its
installed version, read from the installed package metadata; it is `null` for a provider with no such library (SEC
EDGAR). The library is pinned, so when a new failure appears and the version is unchanged, the cause came from the
provider's side. Compare the version in a failing run's document with an earlier one before suspecting the code.

| Verdict | What it means | Look at first |
| :--- | :--- | :--- |
| `ok` | Every request answered in the shape the adapter reads. | Nothing. |
| `unreachable` | The service did not serve the request: connection, DNS or TLS fault, a timeout, blocking (HTTP 403, which SEC also answers for a rejected identity), a server error. For Yahoo the opening connection step reports only a connection, DNS, TLS or timeout fault; it does not detect throttling. | The network, a proxy, and for SEC the declared identity. |
| `rate limited` | The service refused the request because it is limiting requests: HTTP 429, or the yfinance library's own rate-limit error. | Wait before the next run, and check that nothing else is calling the same service. |
| `unexpected response` | The service answered, but not in the form the adapter reads: a missing field or column, invalid JSON, a non-numeric or non-positive quote. | The detail names what is missing; the provider changed its format or the library changed. |
| `no data` | The service answered correctly and has nothing for the probe: an empty history, or SEC has no document for the probe company. | See "`no_data` from a history download" below. A throttled Yahoo history download also lands here. |
| `not configured` | SEC access is not set up, so the SEC check could not run. It is never skipped. | Set `SEC_USER_AGENT` (locally, or the repository secret for the cloud run). |
| `failed` | An unexpected exception was raised inside the check, or an adapter failed without saying which kind. It is a defect, not a provider condition. | The detail: the exception name points at a defect in the check or the adapter. |

The wrappers write each run to its own new directory under the ignored `.tmp/live-runs/`, never delete earlier
runs, and return pytest's exit status. The results file is `live-results.xml` in the run directory.

A check has a 20-second deadline for the whole check, not per request: each request gets the time remaining. A check
that has not finished by then fails with `timed out after 20 s`, and the process still exits normally.

The SEC check needs the declared identity in the `SEC_USER_AGENT` setting. When it is missing, the check reports
`not configured` with the detail "SEC EDGAR access is not configured"; it is never skipped.

### The check after a command failure

After `momentum`, `graham-number`, `graham-growth` or `fcf-growth` fails on a provider, or `refresh` has a job that
did, the application runs the same check body for the provider the failure names (read from the failure's typed
`provider_failure` element, never from message text) and reports what it found: a line before the failure text in the
text modes, and the `provider_check` element in `--json`. The probe is
[`investment_analysis_engine/data/provider_probe.py`](../../investment_analysis_engine/data/provider_probe.py); the wording and the rules are in
[`investment_analysis_engine/cli_provider_check.py`](../../investment_analysis_engine/cli_provider_check.py). It is built once, at the composition root in
`investment_analysis_engine/cli.py`, and reaches the commands through the Typer context.

- It runs one check under a 10-second limit (`IAN_PROVIDER_CHECK_TIMEOUT_SECONDS`), passed to the check body through
  its spec, at most once per provider per process; a refresh over many tickers probes once, after the batch.
- It never retries the failed call, repairs anything, or reads or writes a cache, and it fails open: an error,
  a hang past the limit or an unexpected value inside the check gives `not_checked` and leaves the failure, its
  message and its exit code unchanged.
- A health outcome maps to a verdict: `ok` is `healthy`; `unreachable`, `rate_limited`, `unexpected_response` and
  `no_data` carry over; `not_configured` and `failed` are `not_checked`. A provider with no health check, and a
  switched-off check, are also `not_checked` and make no request.
- `--no-provider-check` and `IAN_PROVIDER_CHECK=false` switch it off. The switched-off verdict is still reported:
  in `--json` the entries are present with `not_checked`.
- A command runs it once and builds the text lines and the JSON element from the same findings (`provider_check_findings`
  in `investment_analysis_engine/cli_provider_check.py`); no presenter calls the probe.
- The wait is bounded: the limit plus a 2-second grace period, so up to 12 seconds per implicated provider at the
  default, and up to 24 seconds when a `refresh` implicates both. In `--json` mode this wait now comes before the
  document is written; `--no-provider-check` or `IAN_PROVIDER_CHECK=false` avoids it.

The seven first lines (Yahoo shown) and what each tells you:

| First line | Verdict | What it tells you |
| :--- | :--- | :--- |
| `Yahoo Finance is not answering: a test request also failed.` | `unreachable` | The provider is down or unreachable from this machine; run `ian health` for the detail. |
| `Yahoo Finance is limiting requests: a test request was also refused.` | `rate_limited` | The provider is throttling this machine. |
| `Yahoo Finance answered a test request in a form this application does not read.` | `unexpected_response` | The provider or the library changed its format; compare `library.version` in `ian health --json`. |
| `Yahoo Finance returned no data for a known test ticker. It may be limiting requests.` | `no_data` | Yahoo's history download hides a throttled answer as an empty frame, so this can be throttling. |
| `Yahoo Finance answered a test request normally. The failure may be specific to this request.` | `healthy` | The provider works for the test ticker; look at the ticker, date or options that failed. |
| `Yahoo Finance was not checked (the provider check is turned off).` | `not_checked` | The option or setting is off. |
| `Yahoo Finance could not be checked.` | `not_checked` | The check could not run (SEC access not set up, a provider with no check, or an error inside the check). |

#### The `provider_check` element in `--json`

The element is the last piece of the finding a script can read. It sits directly after `provider_failure` in the
failure document and the four strategy documents, and is the last key of the `refresh` summary.

- **Value.** `null` on success, for a failure that names no provider (`provider_error`), for a failed optional
  input on an analysis that otherwise succeeded, and in every document `runs show --json` writes. Otherwise a list
  with one entry per implicated provider, each with `provider_id` and `verdict`, in the order `unreachable`,
  `rate_limited`, `unexpected_response`, `no_data` of the provider's most severe failed kind.
- **Verdicts.** `healthy`, `unreachable`, `rate_limited`, `unexpected_response`, `no_data` and `not_checked`, mapped
  from the health outcomes as above.
- **Replay.** A replay runs no live check, so it writes `null`; a direct command and its replay differ in this one key
  and no other. The verdict is never stored.
- **Consistency.** A document carries a non-null element only beside a non-null `provider_failure`, naming exactly the
  providers that element names. A `refresh` summary lists each provider once.
- **Versions.** The failure document is `schema_version` 9, the strategy documents 9 (Momentum), 10 (Graham Number),
  10 (Graham Growth) and 9 (FCF Growth), and the refresh summary 2. No stored version changed.

## 2. The scheduled and on-demand run

The workflow [`provider-health.yaml`](../../.github/workflows/provider-health.yaml) runs the live tests daily at
06:17 UTC on a GitHub-hosted runner and on demand. A failing run fails the workflow, and GitHub's own notification
reaches the repository owner.

**One-time setup.** Create the repository secret that holds the declared SEC identity (the value is a name and an
e-mail address, as the installation guide describes). The workflow reads it and never prints it:

```bash
gh secret set SEC_USER_AGENT
```

**Run on demand.** From the Actions tab choose **Provider Health** and **Run workflow**, or:

```bash
gh workflow run provider-health.yaml
gh workflow run provider-health.yaml -f selector=yahoo
gh run list --workflow provider-health.yaml --limit 5
```

**Read the kept results.** Every run uploads `live-results.xml` as the `provider-health-results` artifact, kept for
90 days. Open the run, download the artifact, and read the `failure` or `error` element of the failing test case:
its message is the check's own detail, for example `history is missing columns: Volume`. The job log shows the same
text under the failing test.

**Leaked SQLite connections.** yfinance's caches leave a SQLite connection open in the Yahoo check's worker thread.
The live tests excuse that leak and no other. Each excused leak adds a line to the run output, under the heading
`live leaks excused (SQLite connections left open by third-party caches, issue #152)`, for example
`excused a leaked sqlite3.Connection allocated by peewee for yfinance`; it is a notice, not a failure. A leak the live
tests do not excuse (a connection allocated by this project's code, by peewee without a yfinance frame above it, or by
another package; a connection with no recorded allocation; or another kind of object) fails whichever test is running when it is freed, as a
`PytestUnraisableExceptionWarning` naming the object and showing where it was allocated. Read that allocation trace
to find the source, and do not widen the rule in `tests/live/conftest.py` unless the leak is one this project cannot close.

### Scheduled workflows stop after inactivity

GitHub disables scheduled workflows in a public repository after 60 days without repository activity. A disabled
schedule produces no run and no failure, so silence would look like health.

1. Treat the date of the last scheduled run as the health signal. When work resumes after a pause of several weeks,
   open the workflow's run list in the Actions tab; a last scheduled run older than two days means the check is not
   running.
2. The Actions tab shows a banner on a disabled workflow stating that it was disabled for inactivity.
3. Re-enable it with the **Enable workflow** button, or `gh workflow enable provider-health.yaml`, then start an
   on-demand run to confirm it executes.
4. Any commit to the repository counts as activity and resets the 60 days, so ordinary development keeps it
   enabled; the risk is a long pause.

## 3. What a failed check means

Start with `uv run ian health --provider <id>` on your own machine, then compare with the cloud run.

### Yahoo (`yfinance`)

Unless a proxy is configured, the check starts with a connection step, then reads the current quote for the probe ticker, then downloads about
30 days of daily history. That is three requests, the most a check may make (two when the connection step is skipped).

**The connection step.** yfinance hides connection faults in several places, so its own calls cannot reliably say
whether Yahoo was reachable. The check therefore first opens a direct TCP and TLS connection to
`query2.finance.yahoo.com:443`, the host yfinance requests quote and history data from, without using yfinance.

- A failure to connect is `unreachable` and ends the check; no quote or history is requested.
- The step separates "cannot reach Yahoo" from everything else. It does **not** detect throttling: Yahoo can accept
  the connection and still refuse or empty the requests that follow.
- **With a proxy configured, the step is skipped.** The check looks for a proxy the way yfinance's HTTP layer
  (`curl_cffi`, on libcurl) does: the `https_proxy` or `all_proxy` environment variable, in either case, unless
  `NO_PROXY` names `query2.finance.yahoo.com`. It does not read the Windows or macOS system proxy settings, because
  that HTTP layer does not either; a proxy set only there is not used by yfinance, so the step still runs. A direct
  connection says nothing about reaching Yahoo through a proxy, so when the variables name one the step does not run
  and the probe in the `ian health` line reads
  `AAPL quote and daily history (connection step skipped: a proxy is configured)`. The quote and history reads
  run as usual, and the check then makes two requests. Without the step, an offline machine behind a proxy can show
  the `unexpected response` or `no data` verdicts described below. The proxy address is never printed.
- A command such as `ian momentum` or a Graham command does not run this step. Offline, it can still report
  `unexpected response` (the quote read) or `no data` (the history download), because yfinance hides the
  connection fault from the adapter. Run `ian health --provider yfinance` to find out whether Yahoo is reachable.

| Verdict and detail | What to look at first |
| :--- | :--- |
| `unreachable`: `Cannot open a TLS connection to query2.finance.yahoo.com:443: ...` | The machine cannot reach Yahoo directly: the network, DNS or a firewall. |
| `unreachable`: `timed out after 20 s` | The connection, the quote or the history did not finish within the whole-check deadline. The network or a proxy. A timeout is always `unreachable`. |
| `rate limited`: `DataFetchError: ... Too Many Requests` | Yahoo answered HTTP 429 to the quote read and yfinance raised its rate-limit error. Wait, then run the check again. |
| `unexpected response`: `history is missing columns: ...`, `history index is not a monotonic date index`, `history is not a data frame` | The yfinance library changed the shape it returns. Compare the installed version with the one the lock file pins, read its release notes, and read `fetch_data` in [`investment_analysis_engine/data/yfinance/client.py`](../../investment_analysis_engine/data/yfinance/client.py). |
| `unexpected response`: `quote last price is not a positive finite number`, or a quote error | The connection opened, so the machine reaches Yahoo, but the quote read (`fast_info`) failed in a way yfinance reports as a shape error. Yahoo changed what it returns, or throttled or refused the request and yfinance hid that. Read `fetch_current_quote` in the same module. |
| `no data`: `history is empty` | See the next section. |
| `failed`: `<ExceptionName>: ...` | An exception the adapter does not classify was raised inside the check. It is a defect, not a provider condition; reproduce it with the same adapter call and read the code. |

#### `no_data` from a history download

yfinance's `download` catches every per-ticker exception itself, including its own rate-limit error, and returns an
empty frame, and no supported setting changes that. So an empty history means only that Yahoo returned no rows. It
can be an unknown or delisted ticker, a throttled request, or an unreachable service, and a command cannot tell
which. For that reason an empty history is still `no_data` and is never `rate_limited`: telling them apart would
mean replacing `yf.download` or reading the library's log text, and neither is done. Throttling is reported as
`rate_limited` only where the library raises its error: the quote, instrument-profile and identity reads.

- **What it can tell you:** Yahoo returned nothing for this request. In `ian health` the connection step comes
  first, so a `no data` verdict there means the machine reached Yahoo and the quote read passed; only the history
  was empty.
- **What it cannot tell you:** that the ticker is unknown, that Yahoo is throttling, or, in a command, that Yahoo
  is down. The message of a command such as `ian momentum` says only that Yahoo returned no data for the ticker.
- **To find out:** run `ian health --provider yfinance`; an `unreachable` verdict settles that the machine cannot
  reach Yahoo, and a pass settles that Yahoo answers the probe. The reason yfinance itself recorded (for example
  `Failed to get ticker ... reason: ...`) is in `logs/app.log`.

Yahoo may throttle or block shared cloud addresses. If only the cloud run fails and `ian health` passes on your
machine, the failure says little about what users see; see the fallback below.

### SEC EDGAR (`sec_edgar`)

The check reads the ticker map and one company-facts document for the probe ticker.

| Detail | What to look at first |
| :--- | :--- |
| `not configured`: `SEC EDGAR access is not configured` | `SEC_USER_AGENT` is not set (locally, or the repository secret for the cloud run). |
| `unreachable`: `FinancialProviderError: HTTP request failed ... 403` | SEC refused the request. A blocked client and a rejected identity both get HTTP 403, so it cannot be told apart from a rejected identity and stays `unreachable`. SEC requires a declared identity; check the value of `SEC_USER_AGENT`. |
| `rate limited`: `FinancialProviderError: HTTP request failed ... 429` | SEC is limiting the request rate. Wait, and check that nothing else was calling at the same time. |
| `unexpected response`: `ticker map entries are missing fields: ...`, `ticker map entry for AAPL is missing fields: ...`, `ticker map has no entry for AAPL` | The ticker map document changed. Read `_ticker_cik_map` in [`investment_analysis_engine/data/sec_edgar/financial_facts.py`](../../investment_analysis_engine/data/sec_edgar/financial_facts.py). |
| `unexpected response`: `company facts document has no 'facts' mapping` or no `'us-gaap'` mapping | The company-facts document changed. Read how the same module parses `facts`. |
| `unreachable`: `timed out after 20 s` | The network, or SEC is slow; retry once. |

#### Which registrant a ticker names

A ticker names the registrant SEC's `company_tickers.json` maps it to today, and a run with `--as-of` studies that registrant's evidence as filed or priced at the boundary ([Architecture](ARCHITECTURE.md#which-registrant-a-ticker-names)). The messages below follow from that, and each names the CIK and the override that fixes it:

| Message | What it means | What to do |
| :--- | :--- | :--- |
| `SEC's ticker file lists XOM under more than one CIK (...)` | The file lists the ticker twice with different CIKs; `no_data`. The order of the file never decides. | Decide which registrant the ticker stands for and write an override. |
| `The registrant CIK ... that XOM names (...) has filed no annual report.` | The CIK has no 10-K, 20-F or 40-F (or an amendment); `no_data`, a provider failure that also starts the automatic provider check. A ticker moved to a new holding company shows this. | If the ticker stands for another registrant, write an override. |
| `... filed its first annual report on 2020-02-01, after the boundary 2019-06-01.` | The registrant has annual reports, none accepted by the `--as-of` boundary. Not a failure: the input is unavailable (`not_available_as_of`) and no provider check runs. | Choose a later boundary, or write an override if the ticker stands for another registrant. |
| `The override XOM = 99999 in providers/sec_edgar.toml ... names a CIK ... for which SEC has no company data.` | The override names a CIK SEC does not know; `no_data`. | Correct the CIK. |

To write an override, create `providers/sec_edgar.toml` in the settings folder ([Installation](../user/INSTALLATION.md#provider-settings-files)) with a table of ticker = CIK:

```toml
[ticker_overrides]
XOM = 34088
```

The ticker may be written in any case; the CIK is a number or a string of digits (one to ten). An override wins over SEC's file. The facts it resolves carry the note `cik_source=override`, so a saved run shows that the mapping was reviewed rather than read from the file. The shipped file holds the table empty. Raw responses for a check go under `.tmp/`, never in the repository.

## 4. The application log

Every command writes its log records to one file and prints none of them. A record from one of the project's modules
or from a library such as `yfinance` or `alembic` at the configured level (`IAN_LOG_LEVEL`, `INFO` by default) or above
goes to `logs/app.log` under the project folder. Set `IAN_LOG_DIR` to move it, and `IAN_LOG_FILE_NAME` to rename it. The
file rotates daily or at 1 MB, keeps five backups and compresses older ones to `.zip`.

Standard output and standard error carry only the command's own result and messages, so `--json` output is unaffected.
That means a provider failure's cause may be in the log and not on the screen. A command's own message names the
kind of the failure (the service did not serve the request, is limiting requests, answered in a form the
application does not read, or returned no data) and the provider, but not the library's error text. For example, a connection failure that
escapes a history download writes `yfinance download for '<ticker>' failed (unreachable): <error>` to the
log and the command prints that yfinance did not serve the request. A fault that yfinance's `download` swallows
reaches the command only as `no data`, and the cause, if yfinance recorded one, is in the log. When a command fails and its message is
too general, read the last lines of `logs/app.log` first. An unexpected error that a command reports with a generic
message is logged with its traceback, and an exception that no command handled is logged as `CRITICAL` under
`system.crash`.

## 5. Moving the Yahoo check to the fallback, and back

If the Yahoo check fails on two consecutive scheduled cloud runs while the same check passes on your own machine the
same day, run the Yahoo check from your machine and leave only the SEC check in the cloud.

1. On your machine, schedule the wrapper with Windows Task Scheduler (a daily trigger and the action below), with
   the repository as the start-in directory and `SEC_USER_AGENT` configured for your account:

   ```powershell
   pwsh -NoProfile -File scripts/run-live-checks.ps1 -k yahoo
   ```

   Results go to a new directory under `.tmp/live-runs/`, and a non-zero exit status is the failure signal. There is
   no push notification; read the scheduler's last-run result.
2. In `.github/workflows/provider-health.yaml`, change `SELECTOR: ${{ inputs.selector }}` to
   `SELECTOR: ${{ inputs.selector || 'sec_edgar' }}` so the scheduled cloud run selects the SEC test alone.

To move back, disable the scheduled task and restore the original `SELECTOR` line.

## 6. Adding a check for a new provider

1. In `investment_analysis_engine/data/provider_checks.py`, add a typed, frozen spec (probe ticker or request, the fields the adapter
   reads, the timeout), one check function that takes its adapter or transport and a monotonic clock by injection,
   and one entry in the `PROVIDER_CHECKS` tuple. It is a plain tuple: no registration, base class or discovery.
2. Keep to at most three requests per check, assert shape and never a value, and run each provider call through the
   existing timeout helper so a hung call cannot keep the process alive.
3. Add the new client to the injected clients and to `build_provider_clients` in `investment_analysis_engine/cli_health.py`. Give the
   entry the `library` name when the provider is reached through an installed library, so `ian health --json`
   reports its version.
4. Add offline tests of the check body against fakes (a passing response, each missing field, an exception, a
   timeout), and one `live_network` test in `tests/live/` that calls the shared body.
