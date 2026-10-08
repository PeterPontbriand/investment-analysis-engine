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
dash when the check failed. The verdict is `ok` or `failed`. The exit status is 0 when every selected check passes
and 1 otherwise; an unknown `--provider` value exits 2 and lists the valid ids.

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

The check downloads about 30 days of daily history for the probe ticker and reads the quote.

| Detail | What to look at first |
| :--- | :--- |
| `history is missing columns: ...`, `history index is not a monotonic date index`, `history is not a data frame` | The yfinance library changed the shape it returns. Compare the installed version with the one the lock file pins, read its release notes, and read `fetch_data` in [`src/data/yfinance/client.py`](../../src/data/yfinance/client.py). |
| `history is empty` or `DataFetchError: No market data was returned` | Yahoo answered with nothing. Retry once and try a second ticker with `ian momentum`; a persistent empty answer for a liquid ticker points to a block or an upstream change. |
| `quote last price is not a positive finite number` or a quote error | The quote read (`fast_info`) changed or was refused. Read `fetch_current_quote` in the same module. |
| `timed out after 20 s` or a transport error | The network, a proxy, or throttling. |

Until failure classification lands, a failed Yahoo check's detail cannot distinguish an unreachable service from no
data. Offline, the check reports `No market data was returned` because yfinance returns an empty result instead of
raising. Before concluding that Yahoo has no data, confirm the machine's connection (for example with a browser or
`ian health --provider sec_edgar`, which does distinguish a transport error).

Yahoo may throttle or block shared cloud addresses. If only the cloud run fails and `ian health` passes on your
machine, the failure says little about what users see; see the fallback below.

### SEC EDGAR (`sec_edgar`)

The check reads the ticker map and one company-facts document for the probe ticker.

| Detail | What to look at first |
| :--- | :--- |
| `SEC EDGAR access is not configured` | `SEC_USER_AGENT` is not set (locally, or the repository secret for the cloud run). |
| `OSError: HTTP request failed ... 403` or `429` | SEC rejected the identity or the rate. SEC requires a declared identity and limits request rates; check the value and that nothing else was calling at the same time. |
| `ticker map entries are missing fields: ...`, `ticker map entry for AAPL is missing fields: ...`, `ticker map has no entry for AAPL` | The ticker map document changed. Read `_ticker_cik_map` in [`src/data/sec_edgar/financial_facts.py`](../../src/data/sec_edgar/financial_facts.py). |
| `company facts document has no 'facts' mapping` or no `'us-gaap'` mapping | The company-facts document changed. Read how the same module parses `facts`. |
| `timed out after 20 s` | The network, or SEC is slow; retry once. |

## 4. The application log

Every command writes its log records to one file and prints none of them. A record from one of the project's modules
or from a library such as `yfinance` or `alembic` at the configured level (`log_level`, `INFO` by default) or above
goes to `logs/app.log` under the project folder. Set `LOG_DIR` to move it, and `log_file_name` to rename it. The
file rotates daily or at 1 MB, keeps five backups and compresses older ones to `.zip`.

Standard output and standard error carry only the command's own result and messages, so `--json` output is unaffected.
That means a provider failure's cause may be in the log and not on the screen. For example, a connection failure
during a history download writes `Low-level connection error during yfinance download for '<ticker>': <error>` to the
log, while the command prints only that Yahoo returned no usable price history. When a command fails and its message is
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
