# PH — Provider Health: Contract and Slice Plan

Makes a broken or changed online service visible without reading logs: the project owner learns from a
scheduled run, and a user learns from the first line of the error message. Placement among other work
packages: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **What this work package does:** adds an opt-in live test suite and a text-only `ian health` command that
  check the shape of what Yahoo (through yfinance) and SEC EDGAR return, run on a schedule and on demand with
  results kept; gives each provider failure one of four distinct, stable classes (unreachable, rate limited,
  answered in an unexpected shape, answered with no data for this request), kept in stored evidence and reported
  by every output that shows the failure; adds `ian health --json` with a typed document and
  a separate not-configured outcome, and an automatic, bounded probe that puts a provider verdict on the first
  line of a provider error.
- **What it does not do:** retry, back off, repair, switch providers or run anything on the user's behalf. It
  reports a condition; it never remediates one. Full list: [Scope limits](#4-scope-limits).
- **Rules every slice follows:** one set of check bodies shared by the live suite, the health command and the
  automatic provider check; live calls only under the `live_network` marker, never in the default run or the managed gate;
  no formula or classification change; no new dependency and no `pyproject.toml` edit; the complete managed
  gate at each slice end; explicit project-owner authorization before the next slice begins.
- **Sequence:** PH.1 now, independent of SWC. Then, after SWC.4c: PH.2a, PH.2b, PH.2c, PH.2d, issue #40, PH.3a,
  PH.2e, PH.3b and PH.3c, in that order (PD, the package dependency map, has merged), because they build on the
  failure envelope and the typed strategy envelopes. All finish before Step 3.5 begins.
- **Where the history lives:** why this exists is in [Background](#6-background-origin-of-this-work-package);
  decision records are in [Appendix A](#appendix-a-decision-records-and-history).

## 2. Sequence and status

Each slice ends with the complete managed quality gate and waits for explicit project-owner authorization
before the next begins. A prose-only documentation slice follows the documentation gate in
`docs/project/README.md`.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| PH.1 | [Live suite, health command and scheduled run](#ph1--live-suite-health-command-and-scheduled-run) | Complete | 2026-10-05 |
| PH.2a | [Kind and raised failures](#ph2a--kind-and-raised-failures) | Complete | 2026-10-09 |
| PH.2b | [Yahoo, health and completion](#ph2b--yahoo-health-and-completion) | Complete | 2026-10-09 |
| PH.2c | [Stored provider failures](#ph2c--stored-provider-failures) | Complete | 2026-10-10 |
| PH.2d | [Failure codes and classifier move to core](#ph2d--failure-codes-and-classifier-move-to-core) | Complete | 2026-10-11 |
| Issue #40 | [Tool failure codes](#issue-40--tool-failure-codes) | Complete | 2026-10-11 |
| PH.3a | [Health JSON and the not-configured outcome](#ph3a--health-json-and-the-not-configured-outcome) | Complete | 2026-10-11 |
| PH.2e | [A fourth provider failure kind, rate limited](#ph2e--a-fourth-provider-failure-kind-rate-limited) | Complete | 2026-10-11 |
| PH.3b | [The automatic provider check](#ph3b--the-automatic-provider-check) | Complete | 2026-10-11 |
| PH.3c | [The provider check in the documents](#ph3c--the-provider-check-in-the-documents) | Next | |

PH.2a does not start before [SWC.4c](../swc/SWC_CONTRACT_AND_SLICE_PLAN.md#swc4c--typed-strategy-envelopes-and-replay-dispatch)
has merged. PH.2b follows PH.2a, PH.2c follows PH.2b, and PH.3a does not start before PH.2d has merged. PH.2e follows PH.3a, PH.3b follows PH.2e and PH.3c follows PH.3b. PH.1 has
no dependency and may run alongside SWC. PH.2d follows PH.2c.

[Issue #40](https://github.com/PeterPontbriand/investment-analysis-engine/issues/40) (orchestrator
classification of `DataQualityError` in trajectory events) comes immediately after PH.2d, as its own small
change, because it reuses the reason codes and failure kinds PH.2 delivers. It calls the classifier in `core`, so
`orchestrator` gains no dependency on `reporting`. It is complete (2026-10-11). PH.3a, PH.2e and PH.3b are complete (2026-10-11), and PH.3c is next.

## 3. The slices

Settled across slices: the live suite, `ian health` and the automatic provider check share one set of check
bodies; the provider check never runs the test suite, never retries the failed call and never remediates, has a
timeout and can be disabled; the scheduled run executes on a GitHub-hosted runner with a named local fallback (PH.1 slice plan);
the broad handlers PH.2 replaces are inventoried by file and symbol; a provider failure stays a recorded, stored
outcome with its resolution trace, and the existing `PROVIDER_ERROR` status is not split.

### PH.1 — Live suite, health command and scheduled run

- **Problem:** nothing tells anyone that Yahoo or SEC EDGAR changed; the suite is fully stubbed and a shape
  change surfaces only as a traceback.
- **Decision:** opt-in `live_network` marker, shared check bodies, a text-only `ian health`, a daily and
  on-demand run with kept results, an `AGENTS.md` amendment (at most three requests per check) and a runbook.
- **Scope:** test configuration, `src/data/provider_checks.py`, `src/cli_health.py`, a workflow and wrappers,
  `AGENTS.md`, `docs/project/PROVIDER_DEBUGGING.md`; no adapter change.
- **Branch:** `feat/ph-1-live-suite`, from `main`.
- **Detail:** [PH.1 slice plan](PH1_LIVE_SUITE_SLICE_PLAN.md).

### PH.2a — Kind and raised failures

- **Problem:** every adapter turns every failure into one error, so "down", "changed" and "no data for this
  ticker" read the same.
- **Decision:** a typed kind (`unreachable`, `unexpected_response`, `no_data`) carried by the existing
  exceptions, three new stable reason codes, a classifier that classifies both provider exceptions by type for
  every command, one shared `provider_failure` element in the failure envelope, and the SEC EDGAR and Massive
  handlers replaced.
- **Scope:** the exceptions, the classifier and failure document, `fetch_json`, `fetch_filing`, the SEC EDGAR and
  Massive facts adapters.
- **Branch:** `feat/ph-2a-kind-and-raised-failures`, from `main` after SWC.4c has merged.
- **Detail:** [PH.2 slice plan](PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md#ph2a--kind-and-raised-failures) and the
  [handler inventory](PH2_HANDLER_INVENTORY.md).

### PH.2b — Yahoo, health and completion

- **Problem:** the Yahoo client turns every exception into one error, and `ian health` can say only `failed`.
- **Decision:** one library-call helper wraps each third-party call; the Yahoo handlers use it; the check
  results and `ian health` carry the kind; a completion test keeps broad handlers out of the adapters. The Yahoo check opens with a direct
  connection step, so an unreachable Yahoo is reported as such.
- **Scope:** `src/data/yfinance/`, `src/data/provider_checks.py`, `src/cli_health.py`, the completion test and
  `docs/project/PROVIDER_DEBUGGING.md`.
- **Branch:** `feat/ph-2b-yahoo-and-health-kinds`, from `main` after PH.2a has merged.
- **Detail:** [PH.2 slice plan](PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md#ph2b--yahoo-health-and-completion).

### PH.2c — Stored provider failures

- **Problem:** three of four strategies store a provider failure as a result, so the kind never reaches a
  report, a saved run or a refresh job.
- **Decision:** the kind and provider identity are typed fields on the stored resolver result and the profile
  and identity diagnostics; every report derives from them through one kind-to-code mapping with a fixed
  precedence; every strategy document carries one shared `provider_failure` element; a refresh job carries a
  `reason_code` if and only if it raised or its run failed.
- **Scope:** the resolvers and carriers, the four strategy codecs and documents, the run envelope, the
  profile-cache payload, the saved run's failure code and the refresh job and summary.
- **Branch:** `feat/ph-2c-stored-provider-failures`, from `main` after PH.2b has merged.
- **Detail:** [PH.2 slice plan](PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md#ph2c--stored-provider-failures) and the
  [handler inventory](PH2_HANDLER_INVENTORY.md#4-carriers-handlers-that-keep-the-class-from-reaching-the-envelope).

### PH.2d — Failure codes and classifier move to core

- **Problem:** the stable failure codes and the classifier lived in `src/reporting`, so anything that needs to
  classify a failure had to depend on `reporting`; the classifier sat that high only because it was one central
  table that imported every exception type.
- **Decision:** each classified exception states its own code where it is defined, the classifier reads that
  code and imports no exception type, and the codes, the `provider_failure` element and the classifier move to
  `src/core`. The failure envelope stays in `reporting`. A pure move: no command output, stored value, schema or
  classification result changes. Issue #40 calls the classifier in `core`, so `orchestrator` gains no
  dependency on `reporting`.
- **Scope:** new `src/core` modules for the codes, the `provider_failure` element, the classifier and the two
  operator errors; the exceptions that now declare a code; every importer; the pinned classification test; the
  package map and the plans.
- **Branch:** `refactor/failure-codes-to-core`, from `main` after PH.2c.
- **Detail:** [PH.2 slice plan](PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md#ph2d--failure-codes-and-classifier-move-to-core).

### Issue #40 — Tool failure codes

- **Problem:** the dispatcher kept only the message of a failed tool call and the loop recorded every failure as
  `ToolExecutionError`, so a data-quality rejection, an unreachable provider, bad arguments and a defect were
  indistinguishable in the trajectory.
- **Decision:** every failed tool call is classified with the `core` classifier where the dispatcher catches it;
  `ToolCallResult` carries the stable `reason_code` and, for a provider failure with a kind and a provider, the
  shared `provider_failure` element, built by one function in `src/core` that the failure envelope also calls;
  an unregistered tool is `invalid_input`; the error event and the failed `tool_result` summary carry both
  values; the trajectory schema version, the text sent to the model and every command output are unchanged.
- **Scope:** `ToolCallResult`, the dispatcher, the loop's failure recording, the recorder's error record, the
  shared element function and the failure envelope's use of it, the architecture text and these plans.
- **Branch:** `feat/orchestrator-tool-failure-codes`, from `main` after PH.2d.
- **Detail:** [Issue #40](https://github.com/PeterPontbriand/investment-analysis-engine/issues/40) holds the detail; no slice plan was written.

### PH.3a — Health JSON and the not-configured outcome

- **Problem:** `ian health` prints text only, so a script cannot read it, and it reports missing SEC access and an
  unexpected error inside a check with the same word, `failed`.
- **Decision:** `ian health --json` writes one typed report document, with a generated schema and a row in the
  document table; a health check has six outcomes, and `not_configured` is separate from `failed` through a typed
  field on the check result. Exit codes are unchanged.
- **Scope:** `src/data/provider_checks.py`, `src/cli_health.py`, the health document, its schema, the help
  golden for `health`, tests and the user documents.
- **Branch:** `feat/ph-3a-health-json`, from `main`.
- **Detail:** [PH.3 slice plan](PH3_SLICE_PLAN.md#3-ph3a-as-built) and the
  [PH.3 decisions](PH3_CANARY_AND_HEALTH_JSON_DETAIL.md#2-ph3a-ian-health---json-and-the-not-configured-outcome).

### PH.2e — A fourth provider failure kind, rate limited

- **Problem:** when a provider answers "too many requests", the application records it as `unreachable` (the Yahoo
  quote read and SEC) or `no_data` (the Yahoo history download). Throttling has a different cause and a different
  remedy from both.
- **Decision:** a fourth kind, `rate_limited`, and a fourth stable code, `provider_rate_limited`. Yahoo's
  rate-limit error and an HTTP 429 from the shared transport are `rate_limited`. An HTTP 403 stays `unreachable`
  and an empty Yahoo history stays `no_data`, because neither can be told from its look-alike without changing
  how history is fetched. The precedence becomes `unreachable`, `rate_limited`, `unexpected_response`, `no_data`.
  `ian health` has seven outcomes. Every stored shape and document that names a kind or a code is versioned again
  with nothing migrated, and the refresh summary gains its first `schema_version`.
- **Scope:** the kind and code, the Yahoo and HTTP rule tables, the sentence table, the health check and document,
  the versions, generated schemas, expected output, tests and the project and user documents. It builds no probe
  and adds no `provider_check` element.
- **Branch:** `feat/ph-2e-rate-limited-kind`, from `main`.
- **Detail:** [PH.2 slice plan](PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md#ph2e--a-fourth-provider-failure-kind-rate-limited).

### PH.3b — The automatic provider check

- **Problem:** a classified failure still does not say whether the provider is down or the request was wrong.
- **Decision:** after any direct command or refresh whose outcome is a provider failure, raised or returned, a
  bounded probe of each implicated provider puts a verdict on a first line in the text modes. In `--json` mode
  nothing extra is printed, so between this slice and PH.3c the JSON documents carry no verdict. The health
  document gains the installed version of the library behind each provider.
- **Scope:** the probe, two settings, the `--no-provider-check` option, `execution_errors`, the four strategy
  commands and `refresh`, the in-memory refresh result carrying the `provider_failure` element, the health
  document's library versions, and user troubleshooting text.
- **Branch:** `feat/ph-3b-automatic-provider-check`, from `main` after PH.2e has merged.
- **Detail:** [PH.3 slice plan](PH3_SLICE_PLAN.md#4-ph3b-as-built) and the
  [PH.3 decisions](PH3_CANARY_AND_HEALTH_JSON_DETAIL.md#3-ph3b-and-ph3c-the-automatic-provider-check).

### PH.3c — The provider check in the documents

- **Problem:** a script reading `--json` output gets no verdict, because PH.3b writes the verdict in text modes only.
- **Decision:** a shared `provider_check` element beside `provider_failure` in the six documents that report an
  analysis outcome (the failure envelope, the four strategy documents and the refresh summary). It is null when
  there is nothing to report and otherwise a list with one entry per provider. The refresh summary's
  `schema_version` goes from 1 to 2.
- **Scope:** the shared element in `src/core`, the six documents and their versions, every affected schema and
  expected output, and the user documents.
- **Branch:** `feat/ph-3c-provider-check-element`, from `main` after PH.3b has merged.
- **Detail:** [PH.3 slice plan](PH3_SLICE_PLAN.md#5-ph3c-as-planned) and the
  [PH.3 decisions](PH3_CANARY_AND_HEALTH_JSON_DETAIL.md#3-ph3b-and-ph3c-the-automatic-provider-check).

## 4. Scope limits

- Retries, backoff, circuit breakers or provider fallback; reliability limits belong to Step 2.6 and are
  unchanged.
- Remediation of any kind, including refreshing credentials, clearing a cache or running a migration.
- Notification services, dashboards or any engine-side scheduler. The scheduled run is repository CI that
  checks third-party services for the project owner; the engine itself gains no scheduling, no background
  monitoring and no notifications, so the milestone's exclusion of unattended scheduling and proactive
  monitoring is unaffected ([A.3](#a3-reading-of-the-milestones-unattended-scheduling-exclusion)). The automatic
  provider check is synchronous, runs only after an error, and ends with the command.
- Assertions on values (prices, share counts, facts). Shape only.
- Checks for any provider other than Yahoo and SEC EDGAR, and for the local Ollama service, which is not an
  online dependency.
- Live calls in the default run, the managed gate or the normal CI workflow.
- A second logging framework, new dependencies or a `pyproject.toml` edit.
- Any formula or classification change, and any evidence-shape change other than the typed provider-failure
  kind and provider identity PH.2c adds, with the version bumps that change requires and no migration.

## 5. Acceptance criteria

- **Opt-in:** `uv run pytest` and the managed gate run no `live_network` test and make no network call; the
  deselection is covered by a test that does not use the network.
- **Live suite:** `--live` runs exactly the marked tests, which pass against the real providers and assert
  shape only; one on-demand cloud run has completed and its artifact is retained.
- **Health command:** after PH.1, `ian health` prints one line per provider (verdict, probe, elapsed), exits 0
  when every check passes and 1 otherwise, accepts `--provider`, has no `--json` and is listed in the
  command-table test's non-strategy commands. After PH.3a it also accepts `--json`, whose typed document has a
  checked-in schema, and reports missing SEC access as `not configured`.
- **One body per check:** the live suite, `ian health` and the provider check call the same functions; a test fails
  if any of them carries its own probe logic.
- **Classification:** every handler in the [inventory](PH2_HANDLER_INVENTORY.md) is replaced or retained for
  the stated reason, each of the four kinds is produced by a tested path where the adapter can observe it (a throttled Yahoo history
  download is `no_data`, [PH.2e](PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md#ph2e--a-fourth-provider-failure-kind-rate-limited)), and no bare
  `except Exception` remains in a provider adapter.
- **First line:** a provider failure shows the verdict first in text and in a typed field in JSON, and
  `ian health` agrees with it.
- **Provider check bounds:** one probe, implicated provider only, timeout enforced, once per provider per process,
  disabled by setting and by option, never retries, never remediates, fails open; each is tested.
- **No semantic change:** no analysis result, formula or classification changes; only failure output, stored
  provider-failure evidence, the saved run's failure code, the refresh job's reason code and the new command
  differ, and the slice plan lists every output change.
- **Policy and documentation:** `AGENTS.md` §0 and §3 and `docs/project/README.md` carry the amended rule and
  `docs/project/PROVIDER_DEBUGGING.md` exists and is linked; no planning label appears outside
  `docs/project/` and `.github/` planning artifacts.
- **Quality gate:** the complete managed gate passes after PH.1, PH.2a, PH.2b, PH.2c, PH.2d, PH.3a, PH.2e, PH.3b and PH.3c, with at least 85% coverage;
  the final link and sequence-table checks pass.
- **Before Step 3.5:** every slice and issue #40 are complete before Step 3.5 begins; the Step 3.5 plan's entry
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
the engine gains no scheduler, monitor or notifier. The automatic provider check is on-error and synchronous. The project owner
confirmed this reading on 2026-10-04.

### A.4 Placement of the policy amendment

The `AGENTS.md` prohibition on real calls appears in §0 (as an unchanged rule of the consolidation period)
and §3, and the quality-gate paragraph of `docs/project/README.md` states it again. The amendment is applied
to all three in PH.1 so that none contradicts another while §0 is in force; the §0 line disappears with §0
when Step 3.5 begins, and §3 then carries the rule alone.

### A.5 Sequence after SWC.4c (2026-10-07)

PH.2 was split into PH.2a, PH.2b and PH.2c, and PH.2 and PH.3 now wait for SWC.4c instead of SWC.4a. SWC.4c
moves the failure document and replaces the strategy payload builders and schemas that PH.2a and PH.2c extend,
so building either earlier would mean editing code that SWC.4c replaces. The project owner chose the order
SWC.4c, PH.2a, PH.2b, PH.2c, issue #40, PH.3 on 2026-10-07. PH.2c is a third slice because three of four
strategies store a provider failure as a result: the kind reaches a report only if it is stored, so PH.2c
changes evidence shapes, which the original scope limits excluded; the scope limits were amended to allow it.

### A.6 PH.3 split into PH.3a and PH.3b (2026-10-11)

PH.3 was split into PH.3a (`ian health --json` and the not-configured outcome) and PH.3b (the automatic provider
check). The first needs no probe and gives the second a stable health document. The project owner approved the
split and the PH.3b decisions on 2026-10-11; they are recorded in the
[PH.3 decisions](PH3_CANARY_AND_HEALTH_JSON_DETAIL.md#6-what-changed-and-why), which also explain why the verdict is
carried by a shared `provider_check` element in every analysis-outcome document and not by a `provider` object in
the failure envelope alone: since PH.2c three of four strategies return a provider failure as a result.

### A.7 A fourth kind, and PH.3b split into PH.3b and PH.3c (2026-10-11)

The project owner approved a fourth provider failure kind, `rate_limited`, as PH.2e, ahead of the automatic
provider check, because throttling has a different cause and remedy from an outage or an empty answer. PH.3b was
split in two: PH.3b builds the probe, its settings, the option and the first line in the text modes; PH.3c adds the
`provider_check` element to the six documents. Between the two, `--json` output carries no verdict. The decisions
are in the [PH.3 decisions](PH3_CANARY_AND_HEALTH_JSON_DETAIL.md#6-what-changed-and-why). The user-facing names
changed from `--no-canary` and `PROVIDER_CANARY` to `--no-provider-check` and `PROVIDER_CHECK`.
