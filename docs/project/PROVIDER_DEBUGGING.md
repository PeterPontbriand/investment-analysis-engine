# Provider Debugging Runbook

For the maintainer. It covers how to tell whether Yahoo (through yfinance) and SEC EDGAR still answer in the shape
the adapters read, how to read the kept results of the scheduled run, and what to look at when a check fails.
Setup problems on a new machine are covered by the
[installation troubleshooting section](../user/INSTALLATION.md); the manual command walk-through is
[Smoke Testing](../user/SMOKE_TESTING.md).

The checks assert response *shape* (the fields and columns an adapter reads), never a value. They make real
requests, at most three per check, and never run in the default test run, the managed quality gate or the normal
continuous-integration workflow. Massive is not checked: its adapter has no live endpoint. The local Ollama
service is not an online dependency and is not checked.

The check bodies live in one module, [`src/data/provider_checks.py`](../../src/data/provider_checks.py). The live
tests and the `health` command call the same functions, so a probe is written once.

## 1. Running the checks

| What | Command |
| :--- | :--- |
| Every provider, printed one line each | `uv run ian health` |
| One provider | `uv run ian health --provider yfinance` or `--provider sec_edgar` |
| The live tests, with kept results (PowerShell) | `& scripts/run-live-checks.ps1` |
| The live tests, with kept results (Git Bash, Linux, macOS) | `bash scripts/run-live-checks.sh` |
| One live test only | add `-k yahoo` or `-k sec_edgar` to either wrapper |
| The live tests directly | `uv run pytest --live tests/live` |

`ian health` prints `<provider>: <verdict> (probe: <description>, <elapsed> s)`, with the failure detail after a
dash when the check failed. The exit status is 0 when every selected check passes and 1 otherwise; an unknown
`--provider` value exits 2 and lists the valid ids.

| Verdict | What it means | Look at first |
| :--- | :--- | :--- |
| `ok` | Every request answered in the shape the adapter reads. | Nothing. |
| `unreachable` | The service did not serve the request: connection, DNS or TLS fault, a timeout, throttling or blocking (HTTP 403 or 429), a server error. For Yahoo the opening connection step reports only a connection, DNS, TLS or timeout fault; it does not detect throttling. | The network, a proxy, and for SEC the declared identity or request rate. |
| `unexpected response` | The service answered, but not in the form the adapter reads: a missing field or column, invalid JSON, a non-numeric or non-positive quote. | The detail names what is missing; the provider changed its format or the library changed. |
| `no data` | The service answered correctly and has nothing for the probe: an empty history, or SEC has no document for the probe company. | See "`no_data` from a history download" below. |
| `failed` | The check failed without a kind: SEC access is not configured, or an unexpected exception was raised inside the check. | The detail: for the first, set `SEC_USER_AGENT`; for the second, the exception name points at a defect in the check or the adapter. |

The wrappers write each run to its own new directory under the ignored `.tmp/live-runs/`, never delete earlier
runs, and return pytest's exit status. The results file is `live-results.xml` in the run directory.

A check has a 20-second deadline for the whole check, not per request: each request gets the time remaining. A check
that has not finished by then fails with `timed out after 20 s`, and the process still exits normally.

The SEC check needs the declared identity in the `SEC_USER_AGENT` setting. When it is missing, the check fails with
"SEC EDGAR access is not configured"; it is never skipped.

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

The check starts with a connection step, then reads the current quote for the probe ticker, then downloads about
30 days of daily history. That is three requests, the most a check may make.

**The connection step.** yfinance hides connection faults in several places, so its own calls cannot reliably say
whether Yahoo was reachable. The check therefore first opens a direct TCP and TLS connection to
`query2.finance.yahoo.com:443`, the host yfinance requests quote and history data from, without using yfinance.

- A failure to connect is `unreachable` and ends the check; no quote or history is requested.
- The step separates "cannot reach Yahoo" from everything else. It does **not** detect throttling: Yahoo can accept
  the connection and still refuse or empty the requests that follow.
- A command such as `ian momentum` or a Graham command does not run this step. Offline, it can still report
  `unexpected response` (the quote read) or `no data` (the history download), because yfinance hides the
  connection fault from the adapter. Run `ian health --provider yfinance` to find out whether Yahoo is reachable.

| Verdict and detail | What to look at first |
| :--- | :--- |
| `unreachable`: `Cannot open a TLS connection to query2.finance.yahoo.com:443: ...` | The machine cannot reach Yahoo: the network, DNS, a proxy or a firewall. The step does not use a proxy configured only for yfinance. |
| `unreachable`: `timed out after 20 s` | The connection, the quote or the history did not finish within the whole-check deadline. The network or a proxy. |
| `unexpected response`: `history is missing columns: ...`, `history index is not a monotonic date index`, `history is not a data frame` | The yfinance library changed the shape it returns. Compare the installed version with the one the lock file pins, read its release notes, and read `fetch_data` in [`src/data/yfinance/client.py`](../../src/data/yfinance/client.py). |
| `unexpected response`: `quote last price is not a positive finite number`, or a quote error | The connection opened, so the machine reaches Yahoo, but the quote read (`fast_info`) failed in a way yfinance reports as a shape error. Yahoo changed what it returns, or throttled or refused the request and yfinance hid that. Read `fetch_current_quote` in the same module. |
| `no data`: `history is empty` | See the next section. |
| `failed`: `<ExceptionName>: ...` | An exception the adapter does not classify was raised inside the check. It is a defect, not a provider condition; reproduce it with the same adapter call and read the code. |

#### `no_data` from a history download

yfinance's `download` catches every per-ticker exception itself and returns an empty frame, and no supported setting
changes that. So an empty history means only that Yahoo returned no rows. It can be an unknown or delisted ticker,
a throttled request, or an unreachable service, and a command cannot tell which.

- **What it can tell you:** Yahoo returned nothing for this request. In `ian health` the connection step comes
  first, so a `no data` verdict there means the machine reached Yahoo and the quote read passed; only the history
  was empty.
- **What it cannot tell you:** that the ticker is unknown, that Yahoo is throttling, or, in a command, that Yahoo
  is down. The sentence of a command such as `ian momentum` says only that Yahoo returned no data for the ticker.
- **To find out:** run `ian health --provider yfinance`; an `unreachable` verdict settles that the machine cannot
  reach Yahoo, and a pass settles that Yahoo answers the probe. The reason yfinance itself recorded (for example
  `Failed to get ticker ... reason: ...`) is in `logs/app.log`.

Yahoo may throttle or block shared cloud addresses. If only the cloud run fails and `ian health` passes on your
machine, the failure says little about what users see; see the fallback below.

### SEC EDGAR (`sec_edgar`)

The check reads the ticker map and one company-facts document for the probe ticker.

| Detail | What to look at first |
| :--- | :--- |
| `failed`: `SEC EDGAR access is not configured` | `SEC_USER_AGENT` is not set (locally, or the repository secret for the cloud run). |
| `unreachable`: `FinancialProviderError: HTTP request failed ... 403` or `429` | SEC rejected the identity or the rate. SEC requires a declared identity and limits request rates; check the value and that nothing else was calling at the same time. |
| `unexpected response`: `ticker map entries are missing fields: ...`, `ticker map entry for AAPL is missing fields: ...`, `ticker map has no entry for AAPL` | The ticker map document changed. Read `_ticker_cik_map` in [`src/data/sec_edgar/financial_facts.py`](../../src/data/sec_edgar/financial_facts.py). |
| `unexpected response`: `company facts document has no 'facts' mapping` or no `'us-gaap'` mapping | The company-facts document changed. Read how the same module parses `facts`. |
| `unreachable`: `timed out after 20 s` | The network, or SEC is slow; retry once. |

## 4. The application log

Every command writes its log records to one file and prints none of them. A record from one of the project's modules
or from a library such as `yfinance` or `alembic` at the configured level (`IAN_LOG_LEVEL`, `INFO` by default) or above
goes to `logs/app.log` under the project folder. Set `IAN_LOG_DIR` to move it, and `IAN_LOG_FILE_NAME` to rename it. The
file rotates daily or at 1 MB, keeps five backups and compresses older ones to `.zip`.

Standard output and standard error carry only the command's own result and messages, so `--json` output is unaffected.
That means a provider failure's cause may be in the log and not on the screen. A command's own message names the
kind of the failure (the service did not serve the request, answered in a form the application does not read, or
returned no data) and the provider, but not the library's error text. For example, a connection failure that
escapes a history download writes `yfinance download for '<ticker>' failed (unreachable): <error>` to the
log and the command prints that yfinance did not serve the request. A fault that yfinance's `download` swallows
reaches the command only as `no data`, and the cause, if yfinance recorded one, is in the log. When a command fails and its message is
too general, read the last lines of `logs/app.log` first. An unexpected error that a command reports with a generic
sentence is logged with its traceback, and an exception that no command handled is logged as `CRITICAL` under
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

1. In `src/data/provider_checks.py`, add a typed, frozen spec (probe ticker or request, the fields the adapter
   reads, the timeout), one check function that takes its adapter or transport and a monotonic clock by injection,
   and one entry in the `PROVIDER_CHECKS` tuple. It is a plain tuple: no registration, base class or discovery.
2. Keep to at most three requests per check, assert shape and never a value, and run each provider call through the
   existing timeout helper so a hung call cannot keep the process alive.
3. Add the new client to the injected clients and to `build_provider_clients` in `src/cli_health.py`.
4. Add offline tests of the check body against fakes (a passing response, each missing field, an exception, a
   timeout), and one `live_network` test in `tests/live/` that calls the shared body.
