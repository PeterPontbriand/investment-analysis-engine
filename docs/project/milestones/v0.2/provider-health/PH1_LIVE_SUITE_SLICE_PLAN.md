# PH.1 — Live suite, health command and scheduled run: slice plan

Owned by [PH](PH_CONTRACT_AND_SLICE_PLAN.md#ph1--live-suite-health-command-and-scheduled-run). It holds every
PH.1 decision; the parent holds only a summary. Written against `main` at `a0274ef` (2026-10-04) and re-checked
against the day's `main` when PH.1 is authorized.

## 1. Goal and boundary

PH.1 gives the project one sanctioned place for a deliberate live call and one set of checks that say whether
Yahoo and SEC EDGAR still answer in the shape the adapters read. It delivers the opt-in marker, the shared
check bodies, a text-only `ian health` command, two live tests, a scheduled and on-demand run with kept
results, the policy amendment and the maintainer runbook.

It does not change any adapter, classify failures (PH.2), add `--json` to the command, or add the automatic
canary (PH.3).

## 2. Marker and selection

- `live_network` is the marker the guards in [`tests/_network_guard.py`](../../../../../tests/_network_guard.py)
  already exempt. The guards `block_live_yahoo` and `block_external_sockets` are already in `tests/conftest.py`
  (landed with the suite guards); PH.1 adds no guard. It registers the marker and updates the guard module's
  docstring, which still says the marker is not registered or used.
- A collection hook in `tests/conftest.py` deselects every `live_network` test unless `--live` is passed; with
  `--live` it selects only those tests. The hook is in conftest and not in `addopts`, because the managed
  wrappers run with `-o addopts=`, so an `addopts` exclusion would not reach the managed gate.
- The marker is registered in `pytest_configure` in `tests/conftest.py`. `AGENTS.md` §3 forbids editing
  `pyproject.toml` without explicit permission and registration needs nothing there
  ([A.2](PH_CONTRACT_AND_SLICE_PLAN.md#a2-marker-registration)).

## 3. Shared check bodies

One production module, `src/data/provider_checks.py`, holds:

- `ProviderCheckResult`: provider identity, probe description, passed flag, elapsed seconds and a failure
  detail naming the missing field or the transport error. PH.2 adds the failure kind.
- A typed, frozen specification per provider: probe ticker, the fields and columns the adapter reads, and the
  timeout. These are typed constants in the module, not literals in a check body.
- One check function per provider. It takes its adapter and a monotonic clock by injection and asserts
  response *shape*, never a value.
- A module-level tuple of the two entries, `yfinance` and `sec_edgar`, in declaration order. It is a plain
  tuple read by the health command and the live tests: no registration, base class or discovery.

**Yahoo check:** a short daily history for the probe ticker is a non-empty frame with `Open`, `High`, `Low`,
`Close` and `Volume` columns and a monotonic date index; `fast_info` returns a positive finite last price.
**SEC EDGAR check:** the ticker map has entries with `cik_str`, `ticker` and `title`; the company-facts document
for the probe ticker's CIK has a `facts` mapping with a `us-gaap` mapping. The probe ticker is a large U.S.
filer, a typed constant. Massive is not checked: its adapter is a placeholder with no live endpoint
([inventory](PH2_HANDLER_INVENTORY.md#3-massive)).

**Timeout.** Each body runs the adapter call in a worker thread and stops waiting at the spec's timeout,
reporting a failed check "timed out after N s". The worker is a daemon thread, so a call that never returns
cannot keep the process alive: the command and the pytest session exit after a timed-out check.
The default is 20 seconds, matching the transport timeout in `src/data/http_json.py`; PH.3's canary passes a
shorter one. Making the timeout a parameter now means PH.3 adds a caller, not a second body.

**Request budget.** At most three requests per check. Yahoo makes three (an opening
connection, one quote read and one history download), SEC EDGAR two (the ticker map and one company-facts
document). The cap respects SEC's fair-access
limit and the project's guarded-egress rule, and a check that needs a fourth request needs project-owner
review.

## 4. The `ian health` command

- **Behavior:** `ian health [--provider <id>]` runs the shared bodies for every provider, or for the named one,
  and prints one line each: `<provider>: <verdict> (probe: <description>, <elapsed> s)`, with the failure
  detail after a dash when the check failed. In PH.1 the verdict is `ok` or `failed`; PH.2 refines `failed`
  into the three kinds. Exit 0 when every selected check passes, 1 otherwise. An unknown `--provider` value is a
  usage error (exit 2) that lists the valid ids.
- **No `--json` in PH.1.** PH.3 adds it with its typed document and generated schema. Without `--json`, the
  command is outside the rule that every command offering `--json` has a typed model and schema.
- **Composition.** `src/cli_health.py` builds the two adapters from settings, as the direct commands do, and
  hands them to the shared bodies. A missing SEC identity (`SEC_USER_AGENT`) is a failed check with the
  existing "SEC EDGAR access is not configured" wording and never a skipped one.
- **Registration.** `src/cli.py` registers the command with one line beside `evaluate`.
- **Command-table conformance.** SWC's `command_table` test (T7,
  [design §10](../swc/SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#10-conformance-tests-and-negative-control)) requires
  every top-level command to be a strategy alias, a command group, or listed in the hand-written
  `NON_STRATEGY_COMMANDS`. `health` is not a strategy and not a group, so it is listed in
  `NON_STRATEGY_COMMANDS` beside `evaluate`. That test arrives with SWC.3c, so the entry is added by whichever
  of PH.1 and SWC.3c merges second; the test names the command in its failure, so an omission cannot pass
  unnoticed. T7's `--save-run` and `--json` property applies only to strategy commands and does not apply to
  `health`. The `--json` rule (T21) does not enumerate a command without `--json`, so PH.1 needs no document or
  schema. SWC.3c's slice plan should list `health` among the non-strategy commands it finds.

## 5. Tests

**Live (`tests/live/test_provider_response_shape.py`, marked `live_network`):** one Yahoo test and one SEC
EDGAR test, each calling the shared body with the real adapter and asserting that the result passed. They
assert shape only. A failure prints the check's failure detail as the assertion message.

**Offline, in the default suite:**

- Each check body against fake adapters: a well-formed response passes; each missing field or column fails and
  names it; an adapter exception fails the check; a hung adapter times out with a short test timeout and the worker is a daemon thread; elapsed comes
  from the injected clock.
- The selection hook, driven in a sub-session over a synthetic marked test: the default run deselects it,
  `--live` selects only marked tests, and a marked test is exempt from both guards while an unmarked one is not
  (the existing guard tests already cover the exemption; this one covers the hook).
- `ian health`: all passing exits 0, the process exits after a timed-out check (a subprocess run against a
  fake adapter that never returns), one failing exits 1, `--provider` selects one, an unknown id exits 2, and
  the output has one line per provider. The adapters are injected fakes; no test calls a real service.
- The command-table entry, when the T7 test exists.

## 6. Scheduled and on-demand run

- **Workflow.** `.github/workflows/provider-health.yaml` runs on a daily `schedule` at an off-peak minute and on
  `workflow_dispatch`, which takes an optional `-k` selector. It does not run the full suite and is separate
  from the existing continuous-integration workflow, which neither runs nor needs it.
- **Wrappers.** `scripts/run-live-checks.ps1` and `.sh` mirror the quality-gate wrappers: a unique run
  directory under the ignored `.tmp/live-runs/`, isolated temp and cache directories, `uv run --no-sync`, and
  `-o addopts=` with `--live` and `--junitxml`. They never delete earlier runs.
- **Kept results.** The workflow uploads the JUnit XML as an artifact with 90-day retention. A failing run
  fails the workflow, so GitHub's own notification reaches the project owner.
- **Secret.** The SEC identity is a repository secret the project owner creates; nothing is committed. A
  missing value fails the SEC test with an explicit message.
- **No planning labels** appear in the workflow, the wrappers or the runbook.

### Where the scheduled run executes

- **Primary:** a GitHub-hosted `ubuntu-latest` runner on Python 3.14. It needs no machine of the project
  owner's to be running, and results and notification come from GitHub. SEC EDGAR accepts automated access that
  carries a declared identity.
- **The risk:** Yahoo may throttle or block shared cloud addresses, so the Yahoo check could fail for a reason
  that says nothing about what users see.
- **Fallback:** the same wrapper, run by the project owner's own scheduler (Windows Task Scheduler) on the
  project owner's machine and selecting the Yahoo check with `-k`. Results go to a new directory under
  `.tmp/live-runs/`; a non-zero exit status is its failure signal. The cloud workflow then selects the SEC
  EDGAR check alone.
- **When it is adopted:** if the Yahoo check fails on two consecutive scheduled cloud runs while the same check
  passes on the project owner's machine the same day. PH.1 does not close until one on-demand cloud run has
  completed, so the first evidence exists before acceptance.
- **Stated limit:** the fallback has no push notification, and notification services are out of scope.

### Scheduled workflows stop after inactivity

GitHub disables scheduled workflows in a public repository after 60 days without repository activity. A
disabled schedule produces no run and no failure, so silence would look like health. The runbook
(`docs/project/PROVIDER_DEBUGGING.md`) tells the project owner:

1. Treat the date of the last scheduled run as the health signal. When work resumes after a pause of several
   weeks, open the workflow's run list in the Actions tab; a last scheduled run older than two days means the
   check is not running.
2. The Actions tab shows a banner on a disabled workflow stating that it was disabled for inactivity.
3. Re-enable it with the **Enable workflow** button, or `gh workflow enable provider-health.yaml`, then start
   an on-demand run to confirm it executes.
4. Any commit to the repository counts as activity and resets the 60 days, so ordinary development keeps it
   enabled; the risk is a long pause.

## 7. Policy amendment

`AGENTS.md` §3 and §0 each forbid real external calls in tests, and the quality-gate paragraph of
`docs/project/README.md` repeats the rule. PH.1 amends all three so none contradicts another while §0 is in
force ([A.4](PH_CONTRACT_AND_SLICE_PLAN.md#a4-placement-of-the-policy-amendment)). The text is: *real provider
calls are permitted only in tests marked `live_network`, which are excluded from the default run and the
managed gate, make at most three requests per check, assert response shape and never values, and never log or
persist secrets.* Deterministic tests keep the existing prohibition unchanged. Outside `docs/project/` and
`.github/`, the amendment uses no planning labels ([`AGENTS.md`](../../../../../AGENTS.md) §4).

## 8. Debugging documentation

None exists. The nearest are the installation troubleshooting section (`docs/user/INSTALLATION.md` §4, which
covers setup problems only) and the manually run `docs/user/SMOKE_TESTING.md`. PH.1 creates
`docs/project/PROVIDER_DEBUGGING.md`, linked from `docs/project/README.md`, with:

- how to run the live suite, the wrappers and `ian health`;
- how to read the kept results, and the 60-day check in the section above;
- what a failed check means and what to look at first for each provider;
- how to move the Yahoo check to the fallback, and back;
- how to add a check for a new provider.

PH.2 adds the three failure kinds to it and PH.3 the canary and the verdict line. The user-facing counterpart,
a troubleshooting entry in `docs/user/INSTALLATION.md` §4, is added by PH.3.

## 9. Files

`tests/conftest.py`, `tests/_network_guard.py` (docstring only), `tests/live/` (new), offline tests for the
hook, the check bodies and the command, `src/data/provider_checks.py` (new), `src/cli_health.py` (new),
`src/cli.py` (one registration line), `scripts/run-live-checks.ps1` and `.sh` (new),
`.github/workflows/provider-health.yaml` (new), `AGENTS.md` §0 and §3, `docs/project/README.md`,
`docs/project/PROVIDER_DEBUGGING.md` (new). No adapter changes, no dependency and no `pyproject.toml` edit.

## 10. Verification

- The complete managed gate passes, with at least 85% coverage, and runs no `live_network` test.
- `uv run pytest` makes no network call; the guard tests and the hook tests prove it.
- `--live` runs the two live tests against the real services and both pass on the project owner's machine and
  on one on-demand cloud run, whose artifact is retained.
- `ian health` prints one line per provider and its exit status matches the results.
- The runbook, the amended rule and the wrapper commands are reviewed by the project owner.
- **Branch:** `feat/ph-1-live-suite`, from `main`.
