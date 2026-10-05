# PH — Provider Health: Contract and Slice Plan

Makes a broken or changed online service visible without reading logs: the project owner learns from a
scheduled run, and a user learns from the first line of the error message. Placement among other work
packages: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **What this work package does:** adds an opt-in live test suite that checks the shape of what Yahoo
  (through yfinance) and SEC EDGAR return, run on a schedule and on demand with its results kept; gives each
  provider adapter three distinct, stable failure classes (unreachable, answered in an unexpected shape,
  answered with no data for this request); adds an `ian health` command and an automatic, bounded probe that
  puts a provider verdict on the first line of a provider error.
- **What it does not do:** retry, back off, repair, switch providers or run anything on the user's behalf. It
  reports a condition; it never remediates one. Full list: [Scope limits](#4-scope-limits).
- **Rules every slice follows:** one set of check bodies shared by the live suite, the health command and the
  canary; live calls only under the `live_network` marker, never in the default run or the managed gate;
  no formula or classification change; no new dependency and no `pyproject.toml` edit; the complete managed
  gate at each slice end; explicit project-owner authorization before the next slice begins.
- **Sequence:** PH.1 now, independent of SWC. PH.2 and PH.3 after SWC.4a, because they build on its failure
  envelope. All three finish before Step 3.5 begins.
- **Where the history lives:** why this exists is in [Background](#6-background-origin-of-this-work-package);
  decision records are in [Appendix A](#appendix-a-decision-records-and-history).

## 2. Sequence and status

Each slice ends with the complete managed quality gate and waits for explicit project-owner authorization
before the next begins. A prose-only documentation slice follows the documentation gate in
`docs/project/README.md`.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| PH.1 | [Live suite, scheduled run and debugging documentation](#ph1--live-suite) | Next | |
| PH.2 | [Provider failure classification](#ph2--provider-failure-classification) | Planned | |
| PH.3 | [Health command and automatic canary](#ph3--health-command-and-automatic-canary) | Planned | |

PH.2 does not start before [SWC.4a](../swc/SWC_CONTRACT_AND_SLICE_PLAN.md#swc4a--failure-envelope-and-schema-generator)
has merged. PH.3 does not start before PH.2 has merged. PH.1 has no dependency and may run alongside SWC.

## 3. The slices

### PH.1 — Live suite

- **Problem:** no check tells anyone that Yahoo or SEC EDGAR changed. The suite is fully stubbed, and the
  suite-wide guards deliberately fail any test that reaches the network. A response-shape change surfaces
  only when a user runs a command and reads a traceback.
- **Decision:**
  - **Marker and selection.** `live_network` is the opt-in marker the guards in
    [`tests/_network_guard.py`](../../../../../tests/_network_guard.py) already exempt. A collection hook in
    `tests/conftest.py` deselects every `live_network` test unless `--live` is passed, and with `--live`
    selects only those tests. The hook is in conftest, not `addopts`, because the managed wrappers run with
    `-o addopts=` and an `addopts` exclusion would not reach the managed gate.
  - **Registration without `pyproject.toml`.** The marker is registered in `tests/conftest.py`
    (`pytest_configure`), because `AGENTS.md` §3 forbids editing `pyproject.toml` without explicit permission
    and registration needs nothing there ([A.2](#a2-marker-registration)).
  - **The guards already exist.** `block_live_yahoo` and `block_external_sockets` are in
    `tests/conftest.py` through [`tests/_network_guard.py`](../../../../../tests/_network_guard.py) and
    exempt `live_network` tests. PH.1 adds no guard; it registers the marker, updates the module docstring
    that says the marker is not yet registered or used, and adds the first marked tests.
  - **Shared check bodies.** The checks live in one production module, `src/data/provider_checks.py`: a
    typed result (`ProviderCheckResult`), a typed per-provider specification (probe ticker, expected fields)
    and one function per provider that takes its adapter by injection and asserts response *shape* only, never
    a value. The live suite, the health command (PH.3) and the canary (PH.3) all call these functions; none
    holds a second copy. The probe ticker and the expected fields are typed constants in that module, not
    literals inside check bodies. The checks are a plain module-level tuple of two entries; no registration,
    base class or discovery.
  - **Two tests.** `tests/live/test_provider_response_shape.py` has one Yahoo test and one SEC EDGAR test:
    Yahoo — a short daily history has the expected columns and a monotonic date index, and `fast_info`
    returns a quote; SEC EDGAR — the ticker map and one company-facts document have the keys the adapter
    reads. Massive is not checked: its adapter is a placeholder with no live endpoint
    ([inventory](PH2_HANDLER_INVENTORY.md#3-massive)).
  - **Offline tests of the check bodies** run in the default suite against fake adapters: well-formed input
    passes, each missing field fails with its name, and a transport error fails the check. The hook has
    offline tests too: default run deselects, `--live` selects only marked tests, and a marked test is exempt
    from both guards.
  - **Scheduled and on-demand run.** A new workflow, `.github/workflows/provider-health.yaml`, runs on a
    daily `schedule` and on `workflow_dispatch` (with an optional `-k` selector input). It runs the live
    suite through a wrapper pair, `scripts/run-live-checks.ps1` and `.sh`, that mirror the quality-gate
    wrappers: isolated temp and cache directories and a unique run directory. The workflow uploads the JUnit
    XML as an artifact kept 90 days, and a failing run fails the workflow, so GitHub's own notification tells
    the project owner. The workflow needs the project owner to supply the SEC identity as a repository
    secret; a missing identity fails the SEC test with an explicit message and never skips it.
    [Where it runs](#where-the-scheduled-run-executes) and the fallback are settled below.
  - **Policy amendment.** `AGENTS.md` §3 and §0 each forbid real external calls in tests, and
    `docs/project/README.md` repeats the rule. The amendment, written for these files and applied in this
    slice, is: *real provider calls are permitted only in tests marked `live_network`, which are excluded
    from the default run and the managed gate, make one bounded request per check, assert response shape and
    never values, and never log or persist secrets.* Deterministic tests keep the existing prohibition
    unchanged. Outside `docs/project/` and `.github/`, the text uses no planning labels
    ([`AGENTS.md`](../../../../../AGENTS.md) §4).
  - **Debugging documentation.** None exists. The nearest are the installation troubleshooting section
    (`docs/user/INSTALLATION.md` §4, which covers setup problems only) and the manually run
    `docs/user/SMOKE_TESTING.md`. PH.1 creates `docs/project/PROVIDER_DEBUGGING.md`, a maintainer runbook:
    how to run the live suite and the wrappers, how to read the kept results, what each failure class means,
    how to move the Yahoo check to the fallback, and how to add a check for a new provider. It is linked from
    `docs/project/README.md`. The user-facing counterpart is a troubleshooting entry in the existing
    `docs/user/INSTALLATION.md` §4, added by PH.3 when the verdict line exists.
- **Scope:** `tests/conftest.py`, `tests/_network_guard.py` (docstring only), new `tests/live/`, new
  offline tests for the hook and the check bodies, `src/data/provider_checks.py`, `scripts/run-live-checks.ps1`
  and `.sh`, `.github/workflows/provider-health.yaml`, `AGENTS.md` §0 and §3,
  `docs/project/README.md`, `docs/project/PROVIDER_DEBUGGING.md`. No adapter behavior changes.
- **Branch:** `feat/ph-1-live-suite`, from `main`.
- **Detail:** ⚠ no slice plan yet. It is written when PH.1 is authorized, against that day's `main`.

#### Where the scheduled run executes

- **Primary:** a GitHub-hosted `ubuntu-latest` runner, Python 3.14, daily at an off-peak minute. It needs no
  machine of the project owner's to be running, results and notification come from GitHub, and SEC EDGAR
  accepts automated access that carries a declared identity.
- **The risk:** Yahoo may throttle or block shared cloud addresses, which would make the Yahoo check fail for
  a reason that says nothing about what users see.
- **Fallback:** the same wrapper (`scripts/run-live-checks`) run by the project owner's own scheduler (Windows
  Task Scheduler) on the project owner's machine, selecting the Yahoo check with `-k`. Results are written to
  a new directory under the ignored `.tmp/live-runs/` and are never deleted by the wrapper; a non-zero exit
  status is its failure signal. The cloud workflow then runs the SEC EDGAR check alone.
- **When the fallback is adopted:** if the Yahoo check fails on two consecutive scheduled cloud runs while the
  same check passes on the project owner's machine on the same day. PH.1 does not close until one on-demand
  cloud run has completed, so the first evidence arrives before the slice is accepted.
- **Limit, stated plainly:** the fallback has no push notification. Out of scope: notification services
  ([scope limits](#4-scope-limits)).

### PH.2 — Provider failure classification

- **Problem:** every adapter turns every failure into one error. `YFinanceClient` catches `Exception` at
  four places and re-raises a `DataFetchError` whose only difference is its sentence;
  `fetch_json` collapses HTTP, DNS, timeout and invalid-JSON failures into `OSError`/`ValueError`; the SEC and
  Massive adapters catch a tuple that treats a dropped connection and a missing JSON key alike. The result
  reaches the user as `provider_error` plus prose, so "Yahoo is down", "Yahoo changed its response" and "this
  ticker has no data" are indistinguishable.
- **Decision:**
  - **Three kinds, typed, never parsed from prose.** A `ProviderFailureKind` enum — `unreachable`,
    `unexpected_response`, `no_data` — and the provider identity are fields on the failure, carried by the
    existing `DataFetchError` and `FinancialProviderError` as additive attributes. No public exception is
    removed or renamed.
  - **What each means.** `unreachable`: the service did not serve the request (DNS, connect, timeout,
    throttling or blocking such as HTTP 403 and 429, server errors). `unexpected_response`: the service
    answered, but not in the form the adapter reads (invalid JSON, missing keys or columns, a non-numeric or
    non-positive quote). `no_data`: the service answered correctly and has nothing for this request (an
    unknown ticker, an empty frame, a missing company-mapping entry).
  - **The adapter reports what it observed; it does not judge provider health.** Yahoo returns an empty frame
    both for an unknown ticker and, at times, when it throttles. An adapter's `no_data` is therefore an
    observation, and the canary (PH.3) is what separates "this ticker has nothing" from "Yahoo is not
    answering".
  - **Carried to the envelope.** The kind travels as a typed field through the resolution result to the
    classifier, and the classifier maps it to three new stable reason codes in the SWC.4a failure envelope:
    `provider_unreachable`, `provider_unexpected_response`, `provider_no_data`. The existing `provider_error`
    stays, unrenamed, for failures an adapter cannot classify; its stability guarantee holds
    ([SWC.1 design §13.3](../swc/SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#133-reason-codes-and-stability)). All
    three map to status `input_unavailable`, as `provider_error` does. Adding codes needs no
    `schema_version` bump; the generated schema and its drift check show the change.
  - **Broad handlers are replaced, not wrapped.** Each handler in the
    [inventory](PH2_HANDLER_INVENTORY.md) is replaced by typed handling at the adapter boundary. After PH.2 an
    exception that is not a typed provider failure is a defect and propagates; it is no longer reported as a
    provider outage.
  - **Raise sites that do not exist today are added:** missing OHLCV columns and a non-frame response from
    `yf.download`, and a non-mapping SEC document, are `unexpected_response` instead of passing through.
  - **Provider-health checks learn the kinds.** `ProviderCheckResult` gains the kind, so a failed live check
    says which of the three it was.
- **Scope:** the files in the [inventory](PH2_HANDLER_INVENTORY.md); `src/data/base_client.py`,
  `src/data/financial/facts.py` (additive attributes), a new `src/data/provider_failure.py`,
  `src/reporting/failure_classification.py` and `src/reporting/documents/failure.py` (the three codes),
  `src/data/provider_checks.py`, the schema regenerated by SWC.4a's generator, `docs/project/PROVIDER_DEBUGGING.md`,
  and tests: one per adapter and kind, the classifier, and a test that every inventory handler is gone.
  Fakes in existing tests that raise a bare `Exception` from a provider are updated to raise a typed failure.
- **Branch:** `feat/ph-2-provider-failure-classification`, from `main` after SWC.4a has merged.
- **Detail:** [handler inventory](PH2_HANDLER_INVENTORY.md). ⚠ no slice plan yet; it is written after SWC.4a
  merges, against that day's `main`, because SWC.4a changes the classifier and failure envelope PH.2 extends.

### PH.3 — Health command and automatic canary

- **Problem:** after PH.2 a failure has a class, but the user still cannot tell whether the provider is down
  or the request was wrong, and the only way to check a provider is to read the live-suite results.
- **Decision:**
  - **`ian health`** probes each provider using the shared check bodies, prints one line per provider
    (verdict, probe, elapsed), exits 0 when all pass and 1 otherwise, and accepts `--provider` and `--json`.
    The JSON document is a typed model with a generated schema under SWC.4a's generator and conformance rule.
  - **The automatic canary.** When a command ends in a `provider_*` failure, the composition root's injected
    canary runs the shared check body for the *implicated provider only*, once, and the result is the first
    line of the message: for example `Yahoo Finance is not answering (probe timed out after 10 s). Your
    request was not the problem.` In `--json` output the failure envelope gains a typed `provider` object
    (provider identity, verdict, whether a probe ran); that is an output-shape change and bumps the
    envelope's `schema_version` with the schema regenerated. Verdicts are the three kinds plus `healthy`
    (the probe passed, so the fault is likely specific to the request) and `not_checked`.
  - **Bounds, settled.** The canary never runs the test suite and never imports pytest; it never retries the
    failed call; it never remediates; it runs one request, under a timeout of 10 seconds by default; it runs
    at most once per provider per process, so a refresh over many tickers probes once and reuses the verdict;
    it does not read or write caches. It can be disabled by the setting `PROVIDER_CANARY=off` and by a
    `--no-canary` option; a disabled canary reports `not_checked`. Timeout and the switch are typed settings
    with documented defaults, not constants in a function body.
  - **Failure to probe never masks the error.** The canary fails open: any problem inside it leaves the
    original failure and its message unchanged, with `not_checked`.
  - **Layering.** The canary and the command are built at the composition root and passed in. No module
    below the root imports them ([SWC §3.3](../swc/SWC_CONTRACT_AND_SLICE_PLAN.md#33-static-declaration-typing-and-conformance)).
  - **`refresh`.** Jobs keep their per-job `reason_code`; the canary runs once per implicated provider after
    the batch ends, never inside the job loop, and its verdict is the first line of the text summary.
  - **Documentation.** A troubleshooting entry in `docs/user/INSTALLATION.md` §4 explains the verdict line;
    `docs/user/SMOKE_TESTING.md` points to `ian health` for the provider part; the runbook is extended.
- **Scope:** `src/cli_health.py` (new), `src/data/provider_canary.py` (new), `src/data/provider_checks.py`,
  `src/cli.py` (registration), `src/cli_support.py` (`execution_errors` receives the injected canary),
  `src/cli_workspace.py` and `src/workspace/refresh.py` (post-batch probe through an injected callable),
  `src/config.py` (two settings), `src/reporting/documents/failure.py` and a new health document, the
  regenerated `schemas/`, `docs/user/INSTALLATION.md`, `docs/user/SMOKE_TESTING.md`,
  `docs/project/PROVIDER_DEBUGGING.md`, and tests (canary on each verdict, disabled, timed out, once per
  process, fails open, never retries, no network in any test).
- **Branch:** `feat/ph-3-health-command-canary`, from `main` after PH.2 has merged.
- **Detail:** ⚠ no slice plan yet. It is written after PH.2 merges.

## 4. Scope limits

- Retries, backoff, circuit breakers or provider fallback; reliability limits belong to Step 2.6 and are
  unchanged.
- Remediation of any kind, including refreshing credentials, clearing a cache or running a migration.
- Notification services, dashboards or any engine-side scheduler. The scheduled run is repository CI that
  checks third-party services for the project owner; the engine itself gains no scheduling, no background
  monitoring and no notifications, so the milestone's exclusion of unattended scheduling and proactive
  monitoring is unaffected ([A.3](#a3-reading-of-the-milestones-unattended-scheduling-exclusion)). The canary
  is synchronous, runs only after an error, and ends with the command.
- Assertions on values (prices, share counts, facts). Shape only.
- Checks for Massive until its adapter has a live endpoint, and for the local Ollama service, which is not an
  online dependency.
- Live calls in the default run, the managed gate or the normal CI workflow.
- A second logging framework, new dependencies or a `pyproject.toml` edit.
- Any formula, classification or evidence-shape change.

## 5. Acceptance criteria

- **Opt-in:** `uv run pytest` and the managed gate run no `live_network` test and make no network call; the
  deselection is covered by a test that does not use the network.
- **Live suite:** `--live` runs exactly the marked tests, which pass against the real providers and assert
  shape only; one on-demand cloud run has completed and its artifact is retained.
- **One body per check:** the live suite, `ian health` and the canary call the same functions; a test fails
  if any of them carries its own probe logic.
- **Classification:** every handler in the [inventory](PH2_HANDLER_INVENTORY.md) is replaced or retained for
  the stated reason, each of the three kinds is produced by a tested path in each live adapter, and no bare
  `except Exception` remains in a provider adapter.
- **First line:** a provider failure shows the verdict first in text and in a typed field in JSON, and
  `ian health` agrees with it.
- **Canary bounds:** one probe, implicated provider only, timeout enforced, once per provider per process,
  disabled by setting and by option, never retries, never remediates, fails open; each is tested.
- **No semantic change:** no analysis result, formula or classification changes; only failure output and the
  new command differ.
- **Policy and documentation:** `AGENTS.md` §0 and §3 and `docs/project/README.md` carry the amended rule and
  `docs/project/PROVIDER_DEBUGGING.md` exists and is linked; no planning label appears outside
  `docs/project/` and `.github/` planning artifacts.
- **Quality gate:** the complete managed gate passes after PH.1, PH.2 and PH.3, with at least 85% coverage;
  the final link and sequence-table checks pass.
- **Before Step 3.5:** all three slices are complete before Step 3.5 begins; the Step 3.5 plan's entry
  condition lists PH.

## 6. Background: origin of this work package

Yahoo access runs through a third-party library that has changed its behavior before, and SEC EDGAR's
documents are read by key. The project's tests are fully stubbed by design, so a provider-side change is
invisible until a user runs a command. The recent suite guards (a Yahoo guard on the one module that imports
`yfinance`, and a non-loopback socket guard) made accidental live calls fail loudly, which also leaves no
sanctioned place for a deliberate one. This work package adds that place, makes failures classifiable, and
tells the person affected which side is at fault. It was proposed by the project owner on 2026-10-04.

---

## Appendix A: Decision records and history

Kept for the record. Nothing here is needed to understand what PH does or what comes next.

### A.1 Sequence

PH.1 runs now because it needs no SWC work: it touches the test configuration, one new production module,
documentation and a workflow, none of which an SWC slice owns. PH.2 and PH.3 wait for SWC.4a because they
extend its failure envelope, classifier and schema generator; building them first would mean writing the
classification twice. All three precede Step 3.5, which adds seven strategies that would each inherit an
undifferentiated provider failure. The milestone table places PH after SWC and before PKG, and the Step 3.5
plan's entry condition lists it.

### A.2 Marker registration

Registering `live_network` in `pyproject.toml` is the conventional place, but `AGENTS.md` §3 forbids editing
that file without explicit permission and the marker needs nothing from it: pytest accepts a marker added in
`pytest_configure`, and the project does not use `--strict-markers`. Registration in `tests/conftest.py`
therefore avoids a permission request. If the project owner prefers `pyproject.toml`, that is a one-line move
that needs their approval.

### A.3 Reading of the milestone's unattended-scheduling exclusion

The milestone plan and Master Plan principle 12 place "unattended scheduling, proactive monitoring,
notifications" outside v0.2. The plan reads that as a limit on what the engine does for an investor, not on
repository tooling: the scheduled run is a CI job that exercises third-party services for the maintainers, and
the engine gains no scheduler, monitor or notifier. The canary is on-error and synchronous. This reading is
recorded here for the project owner's confirmation at review.

### A.4 Placement of the policy amendment

The `AGENTS.md` prohibition on real calls appears in §0 (as an unchanged rule of the consolidation period)
and §3, and the quality-gate paragraph of `docs/project/README.md` states it again. The amendment is applied
to all three in PH.1 so that none contradicts another while §0 is in force; the §0 line disappears with §0
when Step 3.5 begins, and §3 then carries the rule alone.
