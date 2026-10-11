# PH.3 — Provider check and health JSON: decisions

Owned by [PH](PH_CONTRACT_AND_SLICE_PLAN.md#ph3a--health-json-and-the-not-configured-outcome). It holds the
PH.3 decisions settled by the project owner. Files, tests and output changes are in the
[PH.3 slice plan](PH3_SLICE_PLAN.md). A slice plan may refine files and tests but not these decisions without
project-owner review.

## 1. Three slices

PH.3 is three slices. PH.3a is complete; PH.3b is next, after [PH.2e](PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md#ph2e--a-fourth-provider-failure-kind-rate-limited),
which added the fourth failure kind.

| Slice | What it adds | Status |
| :--- | :--- | :--- |
| PH.3a | `ian health --json` with a typed document and schema, and the `not_configured` outcome | Complete |
| PH.3b | The probe, its settings, the `--no-provider-check` option and the first line in the text modes | Next |
| PH.3c | The `provider_check` element in the six documents that report an analysis outcome | Planned |

Between PH.3b and PH.3c, `--json` output carries no verdict.

After [PH.1](PH1_LIVE_SUITE_SLICE_PLAN.md) the project has the shared check bodies and a text-only `ian health`.
After [PH.2](PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md) a failure carries one of four kinds and reaches the
failure envelope as a stable reason code. The user still cannot tell whether the provider is down or the request
was wrong, and a script cannot read `ian health`. PH.3a fixes the second; PH.3b and PH.3c the first.

## 2. PH.3a: `ian health --json` and the not-configured outcome

| # | Decision |
| :--- | :--- |
| D1 | A health check has six outcomes (PH.2e added `rate_limited`, making seven): `ok`, `unreachable`, `unexpected_response`, `no_data`, `not_configured` (SEC access is not set up) and `failed` (an unexpected error inside a check). `ProviderCheckResult` tells the last two apart with a typed field, never by reading the detail text. `passed` and `kind` keep their meaning. |
| D2 | Text output keeps one line per provider in its present form. Only the not-configured case changes: it prints `not configured` where it printed `failed`. |
| D3 | `ian health --json` writes one typed document to standard output and nothing else: a schema version, and per provider its identity, verdict (one of the six), probe description, elapsed seconds and, when the check did not pass, the failure detail. `--provider` works with `--json`. |
| D4 | The document is a report, as `db status` is: it is written whether or not every check passed, and it is not the failure envelope. Exit codes are unchanged: 1 when any check did not pass, 0 otherwise. |
| D5 | The model lives with the other shared documents under `src/reporting/documents/`, is listed in the document table in `src/reporting/json_documents.py`, and has a generated, checked-in schema. |
| D6 | Tests call no real service: each of the six outcomes in text and in JSON; the JSON validates against its model and schema; `--provider` with `--json`; exit codes; standard output holds only the document; the schema drift check; the JSON-command conformance test passes with `health` listed. |
| D7 | The user documents change: the provider debugging runbook, the usage guide's section on `ian health`, and any text that calls the command text only. |

How the six outcomes arise:

| Outcome | Produced when |
| :--- | :--- |
| `ok` | The check passed. |
| `unreachable`, `rate_limited`, `unexpected_response`, `no_data` | The check failed and carries that kind. |
| `not_configured` | The SEC identity is not set, so the SEC check cannot run. The typed field `not_configured` is true. |
| `failed` | The check failed with no kind and `not_configured` is false: an exception no rule classified, or an adapter failure that carries no kind. |

## 3. PH.3b and PH.3c: the automatic provider check

PH.3b and PH.3c are recorded here and not built. PH.3b builds the probe and the first line in the text modes; PH.3c
adds the `provider_check` element to the documents. The settled behavior:

| # | Decision |
| :--- | :--- |
| P1 | PH.3 is three slices: PH.3a (complete); PH.3b (the probe, the settings, the option and the first line in the text modes); PH.3c (the `provider_check` element in the six documents). Between PH.3b and PH.3c, `--json` output carries no verdict. |
| P2 | **Trigger.** Any direct command or refresh whose outcome is a provider failure, whether raised or returned as a result. The provider comes from the typed `provider_failure` element, never from message text. A failed optional input on an otherwise successful analysis does not trigger it. A refresh job's in-memory result carries the `provider_failure` element so the check knows which provider to probe; the per-job part of the refresh document is unchanged. If the element cannot be obtained without storing something new, PH.3b stops and reports. |
| P3 | PH.3c takes the refresh summary's `schema_version` from 1 to 2. The six documents are the failure envelope, the four strategy documents and the refresh summary; each strategy document and the failure envelope take their own version bump. |
| P4 | **The `provider_check` element.** It is null when there is nothing to report: on success, on every replay of a stored run (a replay runs no live check), and for a failure that names no provider (`provider_error`; no probe runs, no verdict line is printed). Otherwise it is a list with one entry per implicated provider, in the existing kind order (`unreachable`, `rate_limited`, `unexpected_response`, `no_data`), each holding `provider_id` and `verdict`. The "direct equals replay" comparison excludes the element by name. The verdict is never stored. |
| P5 | **Six verdicts and their first lines** (below). A line states what the test request found. It makes no claim about the user's request beyond the two hedged sentences marked below, and it offers no remedy. |
| P6 | **Health outcome to verdict.** `ok` is `healthy`; `unreachable`, `rate_limited`, `unexpected_response` and `no_data` carry over; `not_configured` and `failed` are `not_checked`. |
| P7 | **Names.** The option is `--no-provider-check`, the setting is `PROVIDER_CHECK` and the timeout setting is `PROVIDER_CHECK_TIMEOUT_SECONDS`. The word "canary" appears in nothing a user types or reads. This replaces `--no-canary` and `PROVIDER_CANARY`. |
| P8 | **Where the line goes.** In text modes the line is written to the same stream as the failure text, immediately before it. In `--json` mode nothing extra is printed. |
| P9 | **Library version.** In PH.3b the health document gains the installed version of the library behind each provider, where there is one, with a schema version bump. The library is pinned, so an unchanged version means a new failure came from the provider's side. |
| P10 | The earlier wording "the probe timed out after 10 s" is dropped from the `unreachable` line, because a provider can be unreachable without any timeout. |
| P11 | **Unchanged bounds.** One probe under a 10-second limit, once per provider per process, no retry, no cache, no repair, fails open, and injection from the composition root. |

Why a line states only what the test request found (P5): a probe tests the provider, not the user's request. A
sentence such as "your request was not the problem" claims more than a passing or failing test request can show,
and a remedy is outside what the project does ([scope limits](PH_CONTRACT_AND_SLICE_PLAN.md#4-scope-limits)). The
two hedged sentences, `no_data` ("It may be limiting requests.") and `healthy` ("The failure may be specific to
this request."), say what the evidence allows.

First lines (Yahoo shown; the provider's display name is used):

| Verdict | First line |
| :--- | :--- |
| `unreachable` | Yahoo Finance is not answering: a test request also failed. |
| `rate_limited` | Yahoo Finance is limiting requests: a test request was also refused. |
| `unexpected_response` | Yahoo Finance answered a test request in a form this application does not read. |
| `no_data` | Yahoo Finance returned no data for a known test ticker. It may be limiting requests. |
| `healthy` | Yahoo Finance answered a test request normally. The failure may be specific to this request. |
| `not_checked`, switched off | Yahoo Finance was not checked (the provider check is turned off). |
| `not_checked`, any other cause | Yahoo Finance could not be checked. |

When the switch is off, the verdict is `not_checked` and, from PH.3c, the entry is present.

### Bounds, all settled

- It never runs the test suite and does not import pytest.
- It never retries the failed call, never remediates (no cache clearing, credential change or migration), and
  reads and writes no cache.
- It runs one probe under a timeout, 10 seconds by default, passed to the shared body's timeout parameter, and at
  most once per provider per process; a refresh over many tickers probes once and reuses the verdict.
- The timeout and the switch are typed settings in `src/config.py` with documented defaults (P7).
- **Fails open.** An error inside the check leaves the original failure, its message and its exit code unchanged
  and reports `not_checked`. The check can add a first line; it can never replace or hide the failure.
- **`refresh`.** Jobs keep their per-job `reason_code`. The check runs once per implicated provider after the
  batch ends, never inside the job loop.
- **Layering.** It is built at the composition root and passed in; no module below the root imports it
  ([SWC §3.3](../swc/SWC_CONTRACT_AND_SLICE_PLAN.md#33-static-declaration-typing-and-conformance)).

## 4. Files and tests

Per slice, in the [PH.3 slice plan](PH3_SLICE_PLAN.md).

## 5. Branches

PH.3a: `feat/ph-3a-health-json`, from `main`. PH.3b: `feat/ph-3b-automatic-provider-check`, from `main` after
PH.2e has merged. PH.3c: `feat/ph-3c-provider-check-element`, from `main` after PH.3b has merged.

## 6. What changed and why

Recorded when PH.3 was split into two slices (2026-10-11). The earlier version of this document described one
slice.

| Earlier decision | Now | Why |
| :--- | :--- | :--- |
| One slice, PH.3. | PH.3a and PH.3b. | `ian health --json` and the outcome split need no probe, so they land first and give the second slice a stable document to build on. |
| Health verdicts are `ok` plus the three failure kinds; a failed check with no kind is `failed`. | Six outcomes; `not_configured` is separate from `failed`. | Missing SEC access and an unexpected error inside a check were reported with the same word, though one is the user's setup and the other a defect. A typed field carries the difference. |
| Trigger: a command that ends in a failure whose code is one of the four provider codes. | Any direct command or refresh whose outcome is a provider failure, raised or returned. | Since PH.2c three of four strategies return a provider failure as a result, so a trigger on the failure envelope alone would miss them. |
| Only the failure envelope gains a typed `provider` object. | A shared `provider_check` element beside `provider_failure` in every document that reports an analysis outcome. | The same reason: a returned provider failure never reaches the failure envelope, so the envelope alone cannot carry the verdict. |
| Verdicts: the three kinds, `healthy` and `not_checked`; no rule for a failure that names no provider. | Five verdicts with fixed first lines; `provider_error` gets one line and no probe; several providers follow the existing order. | The earlier text left both cases open. |

Recorded when PH.2e added the fourth failure kind and PH.3b was split into PH.3b and PH.3c (2026-10-11). The
decisions R1 to R7 above became P1 to P11.

| Earlier decision | Now | Why |
| :--- | :--- | :--- |
| PH.3 is two slices. | Three slices; PH.3b has the probe and the text, PH.3c the `provider_check` element. | The probe and the first line need no document change, so they land first; the element changes six documents and their versions. Between the two, `--json` carries no verdict. |
| Five verdicts; `not_checked` only when the switch is off. | Six verdicts: `not_checked` for the switch being off, and `rate_limited` added. A health outcome of `not_configured` or `failed` is `not_checked` (P6). | A fourth failure kind needs its own verdict; a check that could not run is a different statement from one that was switched off. |
| A failure that names no provider gets one line saying the provider was not checked. | No probe, no line, and a null element (P4). | A verdict line names a provider, and none is implicated. The earlier line was not among the fixed first lines; a null element says there is nothing to report. |
| The element is empty when there was no provider failure and on replay. | Null in those cases and for a failure that names no provider; otherwise a list (P4). | One representation for "nothing to report". |
| `unreachable` first line: "Yahoo Finance is not answering (probe timed out after 10 s). Your request was not the problem." | "Yahoo Finance is not answering: a test request also failed." (P5, P10) | A provider can be unreachable without any timeout, and a test request cannot show that the user's request was not the problem. |
| `healthy` first line: "The problem is specific to this request." | "The failure may be specific to this request." (P5) | A passing test request does not prove it. |
| `--no-canary` and `PROVIDER_CANARY`. | `--no-provider-check`, `PROVIDER_CHECK`, `PROVIDER_CHECK_TIMEOUT_SECONDS` (P7). | "Canary" is internal vocabulary; a user should not have to learn it. |
| The line is printed first. | The line goes to the same stream as the failure text, immediately before it; `--json` prints nothing extra (P8). | Keeps standard output a single document in JSON mode. |
| The health document is unchanged by PH.3b. | It gains the installed library version for each provider (P9). | The library is pinned, so an unchanged version means a new failure came from the provider's side. |
| The refresh summary is unchanged by PH.3b. | A refresh job's in-memory result carries the `provider_failure` element (P2); PH.3c takes the summary from version 1 to 2 (P3). | The check must know which provider to probe, and the summary gained its first version in PH.2e. |
