# PH.3 — Automatic canary and health JSON: decisions

Owned by [PH](PH_CONTRACT_AND_SLICE_PLAN.md#ph3--automatic-canary-and-health-json). It holds the PH.3
decisions settled at planning time. The slice plan proper is written after
[PH.2](PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md) merges, against that day's `main`,
and may refine files and tests but not these decisions without project-owner review.

## 1. What PH.1 and PH.2 leave

After [PH.1](PH1_LIVE_SUITE_SLICE_PLAN.md) the project has the shared check bodies and a text-only
`ian health`. After PH.2 a failure carries one of three kinds and reaches the failure envelope as a stable
reason code. The user still cannot tell whether the provider is down or the request was wrong, and a script
cannot read `ian health`. PH.3 adds the canary, the first line of the message and the JSON form.

## 2. `ian health --json`

- Adds `--json` to the PH.1 command. The document is a typed model with a generated, checked-in schema, built
  by SWC.4a's schema generator, with the document table entry SWC's JSON-document conformance test requires
  (T21, [design §10](../swc/SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#10-conformance-tests-and-negative-control)). A
  command that offers `--json` without a typed document fails that test by name, so PH.3 cannot land without it.
- Fields: a schema version, and per provider the identity, verdict, probe description and elapsed seconds, plus
  the failure detail when the check failed. Verdicts are the three failure kinds from PH.2 plus `ok`; a failed
  check carries its kind.
- Text output keeps PH.1's one line per provider, now with the kind as the verdict. Exit codes are unchanged.
- The failure envelope remains the shape for a command that fails; `ian health` reports a result, so it is a
  report document, as `db status` is, and does not use the envelope.

## 3. The automatic canary

- **Trigger.** When a command ends in a failure whose code is `provider_unreachable`,
  `provider_unexpected_response`, `provider_no_data` or `provider_error`, the canary runs the shared check body
  for the *implicated provider only*. The provider comes from the typed field PH.2 carries, never from the
  message text. `no_data` also triggers it, because an empty Yahoo answer can mean an unknown ticker or a
  throttled service, and the probe is what tells them apart.
- **Verdicts.** The three kinds, plus `healthy` (the probe passed, so the fault is likely specific to the
  request) and `not_checked` (the canary was disabled, or could not run).
- **The first line.** The verdict is the first line of the message, for example `Yahoo Finance is not
  answering (probe timed out after 10 s). Your request was not the problem.` In `--json` output the failure
  envelope gains a typed `provider` object (provider identity, verdict, whether a probe ran). That is an
  output-shape change: the envelope's `schema_version` is bumped and the schema regenerated in the same change.
- **Bounds, all settled.**
  - It never runs the test suite and does not import pytest.
  - It never retries the failed call.
  - It never remediates: no cache clearing, credential change or migration.
  - It runs one probe under a timeout, 10 seconds by default, passed to the shared body's timeout parameter.
  - It runs at most once per provider per process; a refresh over many tickers probes once and reuses the
    verdict.
  - It does not read or write any cache.
  - It can be disabled by the setting `PROVIDER_CANARY=off` and by a `--no-canary` option on the commands that
    use it; disabled reports `not_checked`.
  - Its timeout and switch are typed settings in `src/config.py` with documented defaults, not constants in a
    function body.
- **Fails open.** Any error inside the canary leaves the original failure, its message and its exit code
  unchanged, and reports `not_checked`. The canary can add a first line; it can never replace or hide the
  failure.
- **`refresh`.** Jobs keep their per-job `reason_code`. The canary runs once per implicated provider after the
  batch ends, never inside the job loop, and its verdict is the first line of the text summary.
- **Layering.** The canary is built at the composition root and passed in to `execution_errors` and the
  workspace commands; no module below the root imports it
  ([SWC §3.3](../swc/SWC_CONTRACT_AND_SLICE_PLAN.md#33-static-declaration-typing-and-conformance)).

## 4. Files

`src/data/provider_canary.py` (new), `src/data/provider_checks.py`, `src/cli_health.py`, `src/cli_support.py`
(`execution_errors` receives the injected canary), `src/cli_workspace.py` and `src/workspace/refresh.py`
(post-batch probe through an injected callable), `src/config.py` (two settings),
`src/reporting/documents/failure.py` and a new health document, the regenerated `schemas/`,
`docs/user/INSTALLATION.md` §4 (an entry that explains the verdict line), `docs/user/SMOKE_TESTING.md` (points
to `ian health` for the provider part), `docs/project/PROVIDER_DEBUGGING.md`, and tests.

## 5. Tests

The canary on each verdict; disabled by setting and by option; timed out; once per provider per process;
implicated provider only; fails open when the probe itself raises; never retries the failed call; the first
line in text and the `provider` object in JSON; `ian health --json` validates against its schema; the schema
drift check. No test calls a real service.

## 6. Branch

`feat/ph-3-canary-and-health-json`, from `main` after PH.2 has merged.
