# PH.2 — Provider failure classification: slice plan

Owned by [PH](PH_CONTRACT_AND_SLICE_PLAN.md#ph2a--kind-and-raised-failures). Decisions are recorded in §2, output
changes in §3, delivery in §4; what was checked against `main` is in §8. The
[handler inventory](PH2_HANDLER_INVENTORY.md) holds the handler-by-handler dispositions and is not repeated here.

## 1. At a glance

- **What it does:** a provider failure says which of three things happened: the service was `unreachable`, it
  answered in an `unexpected_response`, or it had `no_data` for this request. The kind is a typed field from the
  adapter to every report, and becomes one of three new stable reason codes.
- **Three slices, in this order, after SWC.4c:** PH.2a (the kind, the classifier, SEC EDGAR and Massive, the
  raised path), PH.2b (Yahoo, `ian health`, the completion test, the runbook), PH.2c (the kind in stored
  evidence, the saved run, the refresh job and the strategy documents). Issue #40 follows PH.2c.
- **What it does not do:** probe a provider, put a verdict on the first line, or add `ian health --json` (PH.3);
  retry, fall back or remediate; change any analysis result, formula or classification.
- **Rules:** a provider failure stays a recorded, stored outcome with its resolution trace; the
  `PROVIDER_ERROR` status is not split; stored data has no compatibility value, so versions are bumped and
  nothing is migrated; an exception that is not a typed provider failure is a defect and propagates.

## 2. Decisions

| # | Decision |
| :--- | :--- |
| D1 | Three slices, not one: PH.2a, PH.2b, PH.2c ([§4](#4-slices)). |
| D2 | One named helper in `src/data/provider_failure.py` wraps a third-party library call, and only that call, never project code that reads its result. It classifies an exception raised inside the call in this order: the listed `unreachable` types, the listed `unexpected_response` types, the listed `no_data` types; the listed defect types propagate unchanged; and only an unlisted exception becomes `unexpected_response`. The lists are in [§8](#8-verified-against-main). Adapters call the helper and contain no broad handler. |
| D3 | `fetch_json` and `fetch_filing` take the kind of an HTTP 404 from the caller through a required keyword, with no default, on the `JsonFetcher` protocol and every fetcher. Per-company documents pass `no_data`; fixed endpoints pass `unexpected_response`. |
| D4 | The reason-code change for existing failures is an approved output change ([§3](#3-output-changes)). `provider_error` stays valid and stable for failures an adapter cannot classify. |
| D5 | The kind is stored: typed fields on the resolver result and on the instrument-profile and security-identity diagnostics, beside the unchanged `PROVIDER_ERROR` status. Affected versions are bumped; nothing is migrated. A provider failure is not turned into a raised error. |
| D6 | Issue #40 is immediately after PH.2c, as its own small change. |
| D7 | One shared typed element, `provider_failure`, under the same key in every document that reports an analysis outcome ([§5](#5-the-shared-provider_failure-element)). |
| D8 | One fixed precedence picks the single code when several inputs failed: `unreachable`, then `unexpected_response`, then `no_data` ([§5](#5-the-shared-provider_failure-element)). |
| D9 | A refresh job carries a `reason_code` if and only if it raised or its run is `failed`; an `unavailable` run is an analysis outcome, not a failure ([§6](#6-refresh-job-reason_codes)). |
| D10 | The classifier classifies `FinancialProviderError` and `DataFetchError` by type for every command. The per-command `data_error` callback is removed in favour of one per-kind sentence table. |
| D11 | `yf.download` cannot be made to raise by any supported setting ([§8](#8-verified-against-main)), so a throttled or unreachable history download is `no_data`, and the sentence says Yahoo returned no rows. |

## 3. Output changes

Only failure output, stored provider-failure evidence and `ian health` differ. Expected output is regenerated in
the same slice and the diff is what the review approves.

| # | Where | Before | After | Slice |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Failure envelope, `--json`, a raised provider failure (every command) | `reason_code` `provider_error`; the Graham and FCF commands never produced it | One of the three new codes; `provider_error` only when the adapter cannot classify | PH.2a |
| 2 | Failure envelope document | No provider detail | New nullable `provider_failure` element; `schema_version` 6 to 7 | PH.2a |
| 3 | Failure sentence for a provider failure | One sentence from a per-command callback (Momentum only) | One sentence per kind from a shared table | PH.2a |
| 4 | Failed-schema file | No provider kinds | Three more `reason_code` values and the `provider_failure` element | PH.2a |
| 5 | A non-provider exception inside an adapter | Reported as a provider error | Propagates and is reported as an internal failure by the CLI boundary | PH.2a, PH.2b |
| 6 | Yahoo failure sentences | "Network transport fault ..." for any exception | A sentence per kind; an empty history says Yahoo returned no rows | PH.2b |
| 7 | `ian health`, failed check | `<provider>: failed (...)` | `<provider>: unreachable`, `unexpected response` or `no data` | PH.2b |
| 8 | Stored evidence of the three SEC-backed strategies and Momentum | Provider failure has status and prose only | Typed kind and provider identity; evidence and run-envelope versions bumped | PH.2c |
| 9 | Strategy `--json` documents (Momentum, Graham Number, Graham Growth, FCF Growth), direct and replayed | No code; Graham documents carry `status: provider_error` and a sentence | New nullable `provider_failure` element in every document; each document's `schema_version` bumped | PH.2c |
| 10 | Saved run, every `failed` run | `failure_reason_code` `execution_failed` | A `FailureReasonCode` value: the mapped provider code, `invalid_input` or `execution_error`; `execution_failed` is no longer written | PH.2c |
| 11 | Refresh job `reason_code` | Set only for a raised exception | Set if and only if the job raised or its run is `failed`; a failed run's job copies the stored code ([§6](#6-refresh-job-reason_codes)) | PH.2c |
| 12 | Refresh summary schema | `reason_code` set if and only if `error` is set | Set if and only if the job raised or its run is `failed` | PH.2c |
| 13 | Profile-cache payload | Unversioned, no kind | Versioned, carries the kind; an old payload is treated as stale (mechanism: [§8](#8-verified-against-main), needs a decision) | PH.2c |

Text-mode sentences keep their wording except where they state a cause the kind contradicts: the Yahoo
transport sentence (row 6) and Momentum's "returned no usable price history" (row 3).

## 4. Slices

Each branches from `main` after its predecessor merges. PH.2a does not start before
[SWC.4c](../swc/SWC_CONTRACT_AND_SLICE_PLAN.md#swc4c--typed-strategy-envelopes-and-replay-dispatch) has merged:
SWC.4c moves the failure document and replaces the four strategy payload builders and schemas that PH.2a and
PH.2c extend.

### PH.2a — Kind and raised failures

`feat/ph-2a-kind-and-raised-failures`

- **Kind.** `ProviderFailureKind` and the library-call helper in a new `src/data/provider_failure.py`;
  `DataFetchError` and `FinancialProviderError` carry the kind and provider identity as additive attributes.
- **Classifier.** The three codes join the input-unavailable codes and the direct-command codes;
  `classify_failure` classifies `FinancialProviderError` and `DataFetchError` by type for every command; the
  `data_error` parameter of `execution_errors` and its fallback to `invalid_input` are removed; one per-kind
  sentence table replaces the callback. The failure envelope gains the nullable `provider_failure` element.
  `documents/failure.py` is a leaf module that imports nothing from the application, so the element's kind
  cannot import the enum from `src/data/provider_failure.py` without a decision on that rule.
- **Transport.** `fetch_json` and `fetch_filing` classify their failures; the 404 kind is a required keyword on
  `JsonFetcher` and `FilingFetcher` and every fetcher (SEC, Massive, the check transport, the evaluation
  fixture fetcher and the test fakes). The class a classified transport failure raises is not yet decided
  (needs a decision, [§8](#8-verified-against-main)).
- **Adapters.** SEC EDGAR and Massive facts handlers and `resolve_security_unit`'s narrowing, per the inventory.
- **Gate.** The complete managed gate.

### PH.2b — Yahoo, health and completion

`feat/ph-2b-yahoo-and-health-kinds`

- **Yahoo.** The `YFinanceClient` handlers and the yfinance facts adapter, through the helper; the listed
  `unreachable` types are in [§8](#8-verified-against-main).
- **Checks.** `ProviderCheckResult` gains the kind and `ian health` prints it.
- **Completion test** (inventory §7) and the runbook, `docs/project/PROVIDER_DEBUGGING.md`.
- **Connection failure test.** A test that a connection failure during a history download is named in the
  command's own message, since the log line no longer reaches standard error. It can hold only for an exception
  that escapes `yf.download`; `yf.download` swallows a per-ticker transport fault (D11), so that case is
  reported as `no_data` and the cause is in the application log only. Needs a decision on what the test covers.
- **Gate.** The complete managed gate. The live suite still passes on the project owner's machine, since the
  check bodies changed.

### PH.2c — Stored provider failures

`feat/ph-2c-stored-provider-failures`, after SWC.4c and PH.2b.

- **Stored kind.** Typed kind and provider identity on `InputResolutionResult`, the FCF field resolution and
  assembly, `InstrumentProfileDiagnostic`, `SecurityIdentityResolution` and `SecurityUnitResolution`, beside the
  existing `PROVIDER_ERROR` status. The carrier handlers narrow to typed provider failures and record the kind.
  The result-built `PROVIDER_ERROR` sites in the inventory (§4) have no typed failure to record; their kind is
  undecided (needs a decision).
- **Codecs and versions.** The four strategy codecs encode the new fields. Bumped: each strategy's
  `result_schema_version` and `evidence_codec_version` and its document's `schema_version`;
  `AnalysisRun.run_schema_version` (a `Literal[1]` in `workspace/runs.py`, and `decode_evidence` in
  `workspace/codecs.py` accepts only 1 for it and for `projection_version` together); a new version field on
  the hand-written profile-cache payload, whose `_diagnostics_payload` and `_diagnostics_from_payload` carry the
  kind, with a test that it round-trips. Nothing is migrated; local databases may be discarded. The 73 files in
  `tests/expected_output/strategy_documents/` are regenerated (new element and version in each).
- **Derived reports.** Every report derives from the stored kind through the one kind-to-code mapping in
  `failure_classification.py`: the strategy documents and the saved run's `failure_reason_code`. The refresh
  job copies the stored code.
- **Conformance.** The check in [§5](#5-the-shared-provider_failure-element).
- **Gate.** The complete managed gate.

## 5. The shared `provider_failure` element

- **Shape.** `provider_failure` is null, or an object with `reason_code` (one of the three codes) and `inputs`,
  an array of `{input, provider_id, kind}`: each failed input with the provider that failed and its kind. It is
  populated when the analysis outcome is a provider failure, and lists the inputs that caused it. A failed
  optional input (identity, kind, share unit) that does not change the outcome stays in the profile
  diagnostics, which carry the same kind.
- **Carried by every document that reports an analysis outcome, null when there is none:** the failure envelope
  (PH.2a) and the Momentum, Graham Number, Graham Growth and FCF Growth documents, direct and replayed (PH.2c).
  The refresh summary does not carry it; a job carries a `reason_code` ([§6](#6-refresh-job-reason_codes)).
- **Precedence.** The single code is derived from the kinds of the listed inputs by one function with a fixed
  order: `unreachable`, then `unexpected_response`, then `no_data`. An outage on any input outranks a shape
  change, which outranks an absent answer, so the code names the condition most likely to need action. The
  document, the saved run and the refresh job all call that function. In the code as it stands every assembly
  returns at its first failed input, so the list holds one entry today (one exception: FCF Growth skips a
  failed diluted-share field when it classifies on total free cash flow, and that failure is not reported);
  the rule matters for the first strategy that resolves inputs without stopping. No rule that the code
  suggests is better. A raised provider failure (Momentum) has no input name; the value of `input` for it is
  not yet decided (needs a decision).
- **Conformance check.** A test iterates every strategy descriptor's `json_envelope` model (`STRATEGIES` in
  `src/strategy_wiring.py`, added by SWC.4c)
  and fails if its schema lacks the `provider_failure` property of the shared type, so a new strategy cannot
  omit it. It also checks the failure envelope.

## 6. Refresh job `reason_code`s

A refresh job carries a `reason_code` if and only if it raised, or its run is `failed`. An `unavailable` run is an
analysis outcome, not a failure, so its job carries none; neither does a `completed` or `not_applicable` job.

- A raised exception: the classifier's code, as today.
- A `failed` run: the run's stored `failure_reason_code`, copied. Every failed run stores a `FailureReasonCode`
  value (D5, row 10): the mapped provider code when the native status is a provider error, `invalid_input` when
  it is invalid input, otherwise `execution_error`. There is no translation step in the refresh.
- A `failed` outcome with no stored run (refresh with saving off) has no stored code to copy; where its code
  comes from is not decided (needs a decision).

Nothing produces a cancelled run: `RunOutcome.CANCELLED` and the `'cancelled'` value in the outcome check
constraint exist but no code writes them ([R3 close-out](../r3/R3_DEAD_CODE_AUDIT_CLOSEOUT.md)), so the rule has
no `cancelled` case and no code is added for one. `data_unavailable` is not added either.

**Safety of replacing `execution_failed`.** Nothing reads it: it is written at `workspace/execution.py:150`
and validated only as non-empty (`workspace/runs.py:126`). One test asserts it
(`tests/workspace/test_execution.py`); `test_refresh.py` and `test_workspace_fail_closed.py` only build runs that
hold it. The asserting test is updated in PH.2c. Stored data has no compatibility value, so older runs that
hold `execution_failed` need no handling.

## 7. Tests

- **Per adapter and kind:** each of the three kinds is produced by a tested path in each live adapter (Yahoo,
  SEC EDGAR), using fakes; no test calls a real service.
- **Classifier:** each kind maps to its code and status; a provider failure with no kind maps to
  `provider_error`; both exception types classify identically in every command family.
- **Carried, not lost:** a kind raised in an adapter reaches the failure envelope, and a stored kind reaches the
  strategy document, the saved run and the refresh job.
- **Helper order:** each listed type maps to its kind, a listed defect type propagates, and only an unlisted
  exception becomes `unexpected_response`.
- **Precedence:** every ordering of the three kinds yields the §5 code, and the document, the saved run and the
  refresh job agree on it.
- **Defects propagate:** a non-provider exception raised inside each narrowed handler is not reported as a
  provider failure.
- **Best-effort stays best-effort:** `_fetch_currency` still returns `None` on a typed provider failure and
  price history stays usable.
- **404 by caller:** a per-company 404 is `no_data`; a fixed-endpoint 404 is `unexpected_response`; the keyword
  is required on every fetcher.
- **Profile cache:** the payload round-trips the kind; an old unversioned payload is stale.
- **Refresh invariant:** a job carries a code if and only if it raised or its run is `failed`, for every
  outcome, including `unavailable`, which carries none; a failed run's job carries exactly the stored
  `failure_reason_code`.
- **Stored failure codes:** every `failed` run stores a `FailureReasonCode` value, and `execution_failed` is
  never written.
- **Envelope agreement:** the failure envelope's top-level `reason_code` and `provider_failure.reason_code`
  always agree, for every kind and every precedence ordering.
- **Conformance and completion:** §5 and inventory §7.
- **Schema drift:** the regenerated schemas are checked in and the drift check passes.
- **Existing fakes** that raise a bare `Exception` from a provider are changed to raise a typed failure.

## 8. Verified against `main`

Checked at `d415011` (2026-10-09).

- **Where a provider failure ends.** Momentum raises `DataFetchError`, which reaches the failure envelope.
  Graham Number, Graham Growth and FCF Growth never raise it: the resolvers catch `FinancialProviderError`
  (`resolver.py:509`, `:1113`, `fcf_growth/input_resolver.py:607`) and store a `PROVIDER_ERROR` result. The
  Graham commands render their own failed presentation and exit 1; a saved run is `failed` with
  `execution_failed`; a refresh job has no `reason_code`. This is why D5 stores the kind.
- **`PROVIDER_ERROR` without a provider exception.** `resolver.py` also builds `PROVIDER_ERROR` results where the
  provider answered and the answer was rejected: `:540` (candidate validation), `:1148` (more than one fact for a
  single-observation request), `_validate_provider_response` (`:1466`, the coherence checks) and `:803` (a
  non-finite BVPS derivation, which is project arithmetic). These carry no kind. `_bvps_component_failure`
  (`:1376`) passes a component's status through, so a kind has to pass through it as well.
- **Today's `--json` for a provider failure.** Momentum: the failure envelope. Graham Number and Graham
  Growth: a document with `status: "provider_error"`, a sentence in `reason`, null `result` and `inputs`, and no
  code. FCF Growth: the whole result with `execution_status` and per-metric `reason_code` `provider_error`.
- **Failure envelope.** `FailureEnvelope.schema_version` is `Literal[6]` in `src/reporting/documents/failure.py`,
  a leaf module that imports nothing from the application. `FailureReasonCode` and `INPUT_UNAVAILABLE_CODES` are
  there too; `DatabaseMaintenanceReport` shares the code vocabulary, so its schema also regenerates.
- **Classifier.** `src/reporting/failure_classification.py`. `CLASSIFICATION_RULES` maps `DataFetchError` and
  `DataQualityError` to `provider_error`; it does not know `FinancialProviderError`, which is not a
  `ValueError`. It imports the readiness, watchlist, stored-run, replay and `workspace.refresh` exception
  types. Callers: `execution_errors` in `cli_support.py`, `_fail_with` in `cli_workspace.py` (which shows
  `str(exception)` as the sentence) and the refresh command's `classify` argument; `refresh.py` does not import
  it. `_DIRECT_CODES` in `cli_support.py` lists the direct-command codes, and a code outside it is downgraded
  there. Only Momentum passes `data_error` (`strategies/momentum/cli.py`), and `tests/test_cli_support.py`
  passes it too. A non-historical `DataQualityError` also reaches `data_error` today; its sentence after the
  callback is removed is not decided (needs a decision).
- **Codecs that would encode the kind.** The `_MomentumEvidence`, `_NumberEvidence`, `_GrowthEvidence` and
  `_FCFEvidence` models in each strategy's `codec.py`; `AnalysisRun.model_dump` in
  `repositories/analysis_runs.py`, which stores `instrument_profile`; and the hand-written
  `_diagnostics_payload` and `_diagnostics_from_payload` in `instrument_profile_cache.py`, which list fields
  explicitly and would drop a new one. The profile table stores that payload as opaque JSON.
- **Versions today.** `AnalysisRun.run_schema_version` is 1. Document `schema_version`: Momentum 5, Graham Number
  6, Graham Growth 6, FCF Growth 5. Descriptor `result_schema_version`: Momentum 2, Graham Number 1, Graham
  Growth 1, FCF Growth `FCF_GROWTH_RESULT_SCHEMA_VERSION`; every `evidence_codec_version` is 1. All four
  descriptors in `src/strategy_wiring.py` carry `json_envelope`.
- **Profile-cache payload.** `_encode_profile` writes `identity`, `kind_evidence` and `diagnostics` and no version
  field. The stored record has a `schema_version` column that the repository writes as the constant 1
  (`repositories/instrument_profiles.py`) and the cache never reads; freshness is the age only. A new payload
  field versus a bump of that column, and what makes an old payload stale (including on the fail-open path that
  reuses a stored profile), are not decided (needs a decision).
- **Transport failure class.** `fetch_json` raises `OSError` or `ValueError`. `create_analysis_snapshot` swallows
  `FinancialProviderError` around `_resolve_cik`, which loads the ticker map, and `fetch_facts` re-wraps any
  `ValueError`, which `DataFetchError` is. A classified transport failure that is either type would be swallowed
  or re-wrapped by those handlers (needs a decision on the class and the handler order).
- **`yfinance` 1.6.0** (the version in `uv.lock`, unchanged), HTTP layer stubbed to raise a `curl_cffi`
  `ConnectionError`, no network, re-run at `d415011` with a ticker whose timezone is not cached:
  - `yf.download` returned an empty frame with `yf.config.debug.hide_exceptions` at `True` and at `False`.
    `multi.py:298` catches every per-ticker exception and substitutes an empty frame. No supported setting
    changes that.
  - `Ticker.history` raised under both settings, through an unguarded `.info` fallback in the timezone lookup;
    with the deprecated `raise_errors=True` it raised `YFTzMissingError`, a ticker-missing type, for a
    transport fault. With the timezone already cached it returned an empty frame at `True`. It would also
    change the frame `fetch_data` returns.
  - The setting is process-wide and would turn `.info`, `fast_info` and the share-count paths from returning
    `None` into raising.
  - `unreachable` types for the helper: `OSError` (both HTTP backends derive their `RequestException` from it,
    covering connection, timeout, DNS, SSL, proxy, HTTP and chunked-encoding errors) and `YFRateLimitError`.
    Checked first, as `unexpected_response`: the backends' `JSONDecodeError` and `ContentDecodingError` and
    `YFDataException`. `no_data`: `YFTickerMissingError`, `YFPricesMissingError`, `YFTzMissingError`.
    Defects, which propagate: `YFInvalidPeriodError`, `YFNotImplementedError`, a bare `YFException` and
    `InvalidURL`. The helper's order is therefore the `unexpected_response` and `no_data` types and the defect
    types first, then `unreachable` (`OSError`, `YFRateLimitError`), then any unlisted exception as
    `unexpected_response`.
- **`fetch_json` call sites.** Per-company: SEC `financial_facts.py` 245, 246, 418, 422; Massive 242; the check
  transport's company-facts call (`provider_checks.py:251`). Fixed: SEC 529 (the ticker map) and the check
  transport's ticker-map call (`:248`). `cli_health.py` builds the check transport from `fetch_json`.
- **Logging.** Every record goes to `logs/app.log` and none is printed, so the `logger.error` line in
  `YFinanceClient.fetch_data` (reached only by an exception that escapes `yf.download`) does not reach standard
  error. The adapters take the SEC identity and the Massive key as constructor arguments and do not read the
  environment; `src/config.py` is the only reader.
- **`execution_failed`.** Written at `workspace/execution.py:150`; checked only as non-empty at
  `workspace/runs.py:126`; no other reader. Only `tests/workspace/test_execution.py:197` asserts it.
  `FAILED` comes only from the three Graham and FCF `execution.py` outcome mappings.
- **Handlers.** The inventory was re-scanned against `main` at `d415011`; line numbers moved in the SEC,
  Massive, Yahoo-facts, FCF and `cli_support.py` rows, and no handler was added or removed.
- **Expected output.** `tests/expected_output/strategy_documents/` holds 73 golden documents, including
  `provider-error` pairs (direct and replay) for Graham Number, Graham Growth and FCF Growth; PH.2c regenerates
  all of them. Momentum has no provider-failure golden, since it raises. The failure envelope has no golden;
  it is covered by the Python tests that assert `provider_error` and by the schemas.

## 9. Question carried forward

Whether Momentum should record an unavailable result for a provider failure, as the other strategies do, is
outside PH.2. It is carried as a linked item of Step 3.5's result-status decision:
[Step 3.5, A.8](../step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a8-momentum-provider-failure-and-result-status-question-from-ph2-2026-10-07).
