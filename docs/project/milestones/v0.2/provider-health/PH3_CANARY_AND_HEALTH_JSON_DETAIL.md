# PH.3 — Provider check and health JSON: decisions

Owned by [PH](PH_CONTRACT_AND_SLICE_PLAN.md#ph3a--health-json-and-the-not-configured-outcome). It holds the
PH.3 decisions settled by the project owner. Files, tests and output changes are in the
[PH.3 slice plan](PH3_SLICE_PLAN.md). A slice plan may refine files and tests but not these decisions without
project-owner review.

## 1. Two slices

PH.3 is two slices. PH.3a is complete; PH.3b is next.

| Slice | What it adds | Status |
| :--- | :--- | :--- |
| PH.3a | `ian health --json` with a typed document and schema, and the `not_configured` outcome | Complete |
| PH.3b | The automatic provider check after a provider failure, and the `provider_check` element | Next |

After [PH.1](PH1_LIVE_SUITE_SLICE_PLAN.md) the project has the shared check bodies and a text-only `ian health`.
After [PH.2](PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md) a failure carries one of three kinds and reaches the
failure envelope as a stable reason code. The user still cannot tell whether the provider is down or the request
was wrong, and a script cannot read `ian health`. PH.3a fixes the second; PH.3b the first.

## 2. PH.3a: `ian health --json` and the not-configured outcome

| # | Decision |
| :--- | :--- |
| D1 | A health check has six outcomes: `ok`, `unreachable`, `unexpected_response`, `no_data`, `not_configured` (SEC access is not set up) and `failed` (an unexpected error inside a check). `ProviderCheckResult` tells the last two apart with a typed field, never by reading the detail text. `passed` and `kind` keep their meaning. |
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
| `unreachable`, `unexpected_response`, `no_data` | The check failed and carries that kind. |
| `not_configured` | The SEC identity is not set, so the SEC check cannot run. The typed field `not_configured` is true. |
| `failed` | The check failed with no kind and `not_configured` is false: an exception no rule classified, or an adapter failure that carries no kind. |

## 3. PH.3b: the automatic provider check

PH.3b is recorded here and not built in PH.3a. The settled behavior:

| # | Decision |
| :--- | :--- |
| R1 | PH.3 is two slices, PH.3a and PH.3b. |
| R2 | **Trigger.** Any direct command or refresh whose outcome is a provider failure, whether raised or returned as a result. The provider comes from the typed `provider_failure` element, never from message text. A failed optional input on an otherwise successful analysis does not trigger it. |
| R3 | **Where the verdict appears.** In text modes, one line per implicated provider, printed first. In `--json`, a shared element `provider_check` beside `provider_failure` in every document that reports an analysis outcome: the failure envelope, the four strategy documents and the refresh summary. Each entry holds `provider_id` and `verdict`. The element is empty when there was no provider failure and on every replay of a stored run, because a replay runs no live check; the "direct equals replay" comparison excludes this one element by name. The verdict is never stored. |
| R4 | **No provider named.** A failure that names no provider (`provider_error`) gets one line saying the provider was not checked because the failure did not identify one. No probe runs. |
| R5 | **Several providers.** Each implicated provider is probed once; lines and entries follow the existing order: unreachable, unexpected response, no data. |
| R6 | **Verdicts.** Five, with the first lines below. When the switch is off the entry is present with `not_checked`. |
| R7 | **Unchanged bounds.** One probe under a 10-second limit, once per provider per process, no retry, no cache, no repair, fails open, the `PROVIDER_CANARY` setting and the `--no-canary` option, and injection from the composition root. |

First lines (Yahoo shown; the provider's display name is used):

| Verdict | First line |
| :--- | :--- |
| `unreachable` | Yahoo Finance is not answering (probe timed out after 10 s). Your request was not the problem. |
| `unexpected_response` | Yahoo Finance answered a test request in a form this application does not read. Your request was not the problem. |
| `no_data` | Yahoo Finance returned no data for a known test ticker. It may be limiting requests. |
| `healthy` | Yahoo Finance answered a test request normally. The problem is specific to this request. |
| `not_checked` | Yahoo Finance was not checked (the provider check is turned off). |

### Bounds, all settled

- It never runs the test suite and does not import pytest.
- It never retries the failed call, never remediates (no cache clearing, credential change or migration), and
  reads and writes no cache.
- It runs one probe under a timeout, 10 seconds by default, passed to the shared body's timeout parameter, and at
  most once per provider per process; a refresh over many tickers probes once and reuses the verdict.
- The timeout and the switch are typed settings in `src/config.py` with documented defaults.
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
PH.3a has merged.

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
