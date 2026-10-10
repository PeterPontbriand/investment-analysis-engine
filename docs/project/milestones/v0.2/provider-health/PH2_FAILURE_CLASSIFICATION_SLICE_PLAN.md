# PH.2 — Provider failure classification: slice plan

Owned by [PH](PH_CONTRACT_AND_SLICE_PLAN.md#ph2a--kind-and-raised-failures). Decisions are recorded in §2, output
changes in §3, delivery in §4; what was checked against `main` is in §8. The
[handler inventory](PH2_HANDLER_INVENTORY.md) holds the handler-by-handler dispositions and is not repeated here.

## 1. At a glance

- **Massive:** removed by [MR](../massive-removal/MR_MASSIVE_REMOVAL_PLAN.md) after PH.2a and PH.2b delivered; the Massive
  text in §4 and §8 records what was delivered.
- **What it does:** a provider failure says which of three things happened: the service was `unreachable`, it
  answered in an `unexpected_response`, or it had `no_data` for this request. The kind is a typed field from the
  adapter to every report, and becomes one of three new stable reason codes.
- **Three slices, in this order, after SWC.4c:** PH.2a (the kind, the classifier, SEC EDGAR and Massive, the
  raised path), PH.2b (Yahoo, `ian health`, the completion test, the runbook), PH.2c (the kind in stored
  evidence, the saved run, the refresh job and the strategy documents). All three are complete, so PH.2 is
  complete. [Issue #40](https://github.com/PeterPontbriand/investment-analysis-engine/issues/40) is next.
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
| D3 | `fetch_json` and `fetch_filing` take the kind of an HTTP 404 from the caller through the required keyword `not_found`, and the provider through the required keyword `provider_id`, both keyword-only with no default, on the `JsonFetcher` and `FilingFetcher` protocols and every fetcher. Per-company documents and filings pass `no_data`; fixed endpoints pass `unexpected_response`. |
| D4 | The reason-code change for existing failures is an approved output change ([§3](#3-output-changes)). `provider_error` stays valid and stable for failures an adapter cannot classify. |
| D5 | The kind is stored: typed fields on the resolver result and on the instrument-profile and security-identity diagnostics, beside the unchanged `PROVIDER_ERROR` status. Affected versions are bumped; nothing is migrated. A provider failure is not turned into a raised error. |
| D6 | Issue #40 is immediately after PH.2c, as its own small change. |
| D7 | One shared typed element, `provider_failure`, under the same key in every document that reports an analysis outcome ([§5](#5-the-shared-provider_failure-element)). |
| D8 | One fixed precedence picks the single code when several inputs failed: `unreachable`, then `unexpected_response`, then `no_data` ([§5](#5-the-shared-provider_failure-element)). |
| D9 | A refresh job carries a `reason_code` if and only if it raised or its run is `failed`; an `unavailable` run is an analysis outcome, not a failure ([§6](#6-refresh-job-reason_codes)). |
| D10 | The classifier classifies `FinancialProviderError` and `DataFetchError` by type for every command. The per-command `data_error` callback is removed in favour of one per-kind sentence table. |
| D11 | `yf.download` cannot be made to raise by any supported setting ([§8](#8-verified-against-main)), so a throttled or unreachable history download is `no_data`, and the sentence says Yahoo returned no data for the ticker, never that the ticker is unknown. |
| D12 | `fetch_json` and `fetch_filing` raise `FinancialProviderError`, carrying the kind and the provider. The resolvers already catch that type, so a transport failure stays a recorded outcome, and the adapters' passthrough handlers let it through. |
| D13 | A missing CIK is its own condition. `_resolve_cik` raises a private subclass of `FinancialProviderError` (kind `no_data`) for a ticker absent from SEC's map, and the two handlers that mean "no CIK mapping" (`create_analysis_snapshot` and the top of `fetch_facts`) catch only that subclass, so an outage while loading the ticker map is not turned into an empty snapshot or an empty fact tuple. |
| D14 | `ProviderFailureKind` lives in `src/core/provider_failure_kind.py`, which imports nothing from the application. The library-call helper stays in `src/data/provider_failure.py`. `documents/failure.py` stays a leaf under a wider rule: it imports only modules that themselves import nothing from the application. The shared `provider_failure` element models live in that module, so the failure envelope and the strategy documents import the same types. |
| D15 | `provider_failure.inputs[].input` is nullable: null if and only if the failure was raised and not recorded against a strategy input. Every entry PH.2a produces has a null `input`. |
| D16 | A plain `DataQualityError` cannot be raised: for freshly fetched data the historical-quality check either raises `HistoricalDataQualityError` itself or returns nothing. The three unreachable `raise DataQualityError(...)` branches in `cached_client.py`, the classifier rule for the plain type and the tests that built one by hand are removed; the class stays as the base of the historical error. |
| D17 | `_fail_with` in `cli_workspace.py` is called only with watchlist, stored-run, readiness and parameter errors. It stays outside the sentence table and is not changed. |
| D18 | An opening connection step in the Yahoo health check (PH.2b). `check_yfinance` begins with a TCP and TLS connection to `query2.finance.yahoo.com:443` (`YFINANCE_DATA_HOST`), the host yfinance's `_BASE_URL_` names for its quote and history calls, made with the standard library and no yfinance code and classified through `call_library`. A failure is `unreachable` and ends the check; success lets the quote and history reads run in that order. When the proxy environment variables name an HTTPS proxy for the host (`https_proxy` or `all_proxy`, either case, unless `NO_PROXY` names the host; read with `urllib.request.getproxies_environment`, the system settings not read), the step is skipped, because a direct connection says nothing about reaching Yahoo through the proxy; the probe description says so and the check makes two requests. The step shares the check's whole-check deadline and is one of the three requests; `MAX_REQUESTS_PER_CHECK` is unchanged, and a test pins the host to yfinance's base URL. It is a TCP and TLS connection and not a web request because a plain standard-library request is answered with HTTP 429 unless it sends a browser `User-Agent`, so a status code could not tell an unreachable service from one rejecting the client ([§8](#8-verified-against-main)). The adapter's classification is unchanged: it reports what it observed, so a swallowed connection fault stays `no_data` (history) or `unexpected_response` (the quote `KeyError`), and the step does not detect throttling. It replaces the earlier decision to read the quote before the history, whose premise holds only with an empty time zone cache. |
| D19 | The connection-failure test is two tests (PH.2b). An exception that escapes `yf.download` reaches the Momentum command's own output as the `unreachable` code and sentence, with nothing needed from the log. A fault that `yf.download` swallows (an empty frame) is `no_data`, and the sentence does not claim the ticker is unknown. |
| D20 | `ProviderCheckResult` gains a nullable kind (PH.2b). A typed provider failure raised by an adapter keeps its own kind. The check's own failures: a timeout is `unreachable`; a wrong shape (not a frame, missing columns, bad index, a non-positive or non-finite quote, a wrong SEC document shape) is `unexpected_response`; an empty history is `no_data`. No kind, by design: SEC not configured (`SecUnavailable`), and an unexpected exception inside a check. `ian health` prints `<provider>: unreachable`, `unexpected response` or `no data` for a failed check with a kind and `<provider>: failed` for one without, each followed by the detail. A passed check is unchanged. |
| D21 | Best-effort currency stays best-effort (PH.2b). `_fetch_currency` and the optional currency read in `fetch_current_quote` still return no currency, including when a connection fault surfaces there as `KeyError`. `_fetch_currency` catches only that and typed provider failures; anything else propagates. |
| D22 | The `no_data` sentence stays as merged: "returned no data for it" (PH.2b). The plan's earlier wording, an empty history "says Yahoo returned no rows", is replaced to match the sentence table. |
| D23 | Result-built provider errors (PH.2c, decision a). Where the resolver builds `PROVIDER_ERROR` because the provider answered and the answer was rejected (a fact that fails `_validate_candidate`, more than one fact for a single-observation request, a failed coherence check in `_validate_provider_response`), the stored kind is `unexpected_response` and the provider is the one the request named. `_bvps_component_failure` passes a component's kind and provider through unchanged. The same holds for an identity or kind answer that describes another instrument (a profile diagnostic or an identity resolution): `unexpected_response` from the candidate that answered. |
| D24 | The BVPS non-finite branch (PH.2c, decision b). The branch can run: every component is finite and the shares are strictly positive, but nothing bounds their size, so a finite equity over very small shares overflows to infinity (equity `1e300`, shares `1e-10`). It stays, takes `unexpected_response` from the requested provider, and keeps its status. Whether `PROVIDER_ERROR` is the right status for project arithmetic is a question for the project owner: [ESC-28](../existing-strategy-correctness/ESC_A_DEFECT_LEDGER.md#esc-28--a-non-finite-bvps-derivation-is-reported-as-a-provider-error). |
| D25 | The Yahoo clock guard (PH.2c, decision c). A naive datetime from the injected clock in `YFinanceFinancialFactsAdapter.fetch_facts` is a defect, not a provider failure: it raises `ValueError`, the type every other naive-datetime guard in the project raises, and it propagates. Every other raise of a provider failure without a kind is in an evaluation fixture; none is in a production adapter ([§8](#8-verified-against-main)). |
| D26 | The profile cache version (PH.2c, decision d). The stored profile record's existing `schema_version` column carries the version: its constant is 2 and the cache reads it. A record whose version is not current is treated as absent on the fresh-reuse path and on the fail-open path that reuses a stored profile when a refresh cannot confirm an identity anchor; the next anchored resolution overwrites it, including its version. The payload has no version field of its own. |
| D27 | One function from a result to its failure code (PH.2c, decision e). `failure_reason_code` in `failure_classification.py` returns the mapped provider code when the native status is a provider error (`provider_error` when no kind was recorded), `invalid_input` for invalid input, otherwise `execution_error`. Each strategy's capture calls it once, for a `failed` outcome, so a saved run and an unsaved refresh job read the same code; `execution_failed` is no longer written. A refresh job carries a `reason_code` if and only if it raised or its outcome is `failed`, with saving on or off. |

## 3. Output changes

Only failure output, stored provider-failure evidence and `ian health` differ. Expected output is regenerated in
the same slice and the diff is what the review approves.

| # | Where | Before | After | Slice |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Failure envelope, `--json`, a raised provider failure (every command; a raised refresh job's `reason_code` too) | `reason_code` `provider_error`; the Graham and FCF commands never produced it | One of the three new codes; `provider_error` only when the adapter cannot classify | PH.2a |
| 2 | Failure envelope document | No provider detail | New nullable `provider_failure` element; `schema_version` 6 to 7 | PH.2a |
| 3 | Failure sentence for a provider failure | One sentence from a per-command callback (Momentum only) | One sentence per kind from a shared table | PH.2a |
| 4 | Generated schemas | No provider kinds | `failure`: three more `reason_code` values, the `provider_failure` element, version 7. `database-maintenance-report` and `refresh-summary`: the three values join the enumeration | PH.2a |
| 5 | A non-provider exception inside an adapter | Reported as a provider error | Propagates and is reported as an internal failure by the CLI boundary | PH.2a, PH.2b |
| 6 | Yahoo failure sentences | "Network transport fault ..." for any exception | A sentence per kind; an empty history says Yahoo returned no data for the ticker (D22) | PH.2b |
| 7 | `ian health`, failed check | `<provider>: failed (...)` | `<provider>: unreachable`, `unexpected response` or `no data`; `<provider>: failed` only for a failure with no kind (D20) | PH.2b |
| 8 | Stored evidence of the three SEC-backed strategies and Momentum | Provider failure has status and prose only | Typed kind and provider identity; evidence and run-envelope versions bumped | PH.2c |
| 9 | Strategy `--json` documents (Momentum, Graham Number, Graham Growth, FCF Growth), direct and replayed | No code; Graham documents carry `status: provider_error` and a sentence | New nullable `provider_failure` key in the shared document header, after `status`, so every document takes it; each document's `schema_version` bumped | PH.2c |
| 10 | Saved run, every `failed` run | `failure_reason_code` `execution_failed` | A `FailureReasonCode` value: the mapped provider code, `invalid_input` or `execution_error`; `execution_failed` is no longer written ([D27](#2-decisions)) | PH.2c |
| 11 | Refresh job `reason_code` | Set only for a raised exception | Set if and only if the job raised or its run is `failed`; a failed run's job copies the stored code ([§6](#6-refresh-job-reason_codes)) | PH.2c |
| 12 | Refresh summary schema | `reason_code` set if and only if `error` is set | Set if and only if the job raised or its run is `failed` | PH.2c |
| 13 | Profile-cache payload | Stored under `schema_version` 1, no kind | Stored under `schema_version` 2 and carries the kind; a record of another version is treated as absent on the fresh path and the fail-open path ([D26](#2-decisions)) | PH.2c |

Text-mode sentences keep their wording except where they state a cause the kind contradicts: the Yahoo
transport sentence (row 6) and Momentum's "returned no usable price history" (row 3).

## 4. Slices

Each branches from `main` after its predecessor merges. PH.2a does not start before
[SWC.4c](../swc/SWC_CONTRACT_AND_SLICE_PLAN.md#swc4c--typed-strategy-envelopes-and-replay-dispatch) has merged:
SWC.4c moves the failure document and replaces the four strategy payload builders and schemas that PH.2a and
PH.2c extend.

### PH.2a — Kind and raised failures

`feat/ph-2a-kind-and-raised-failures`

- **Kind.** `ProviderFailureKind` in `src/core/provider_failure_kind.py` (D14) and the library-call helper in
  `src/data/provider_failure.py`; `DataFetchError` and `FinancialProviderError` carry the kind and provider
  identity as additive attributes.
- **Classifier.** The three codes join the input-unavailable codes and the direct-command codes;
  `classify_failure` classifies `FinancialProviderError` and `DataFetchError` by type for every command, and a
  typed failure with no kind is `provider_error`; the kind-to-code mapping is `PROVIDER_CODE_BY_KIND` in
  `failure_classification.py`. The `data_error` parameter of `execution_errors` and its fallback to
  `invalid_input` are removed; `provider_failure_sentence` in `cli_support.py` is the one sentence table. The
  failure envelope gains the nullable `provider_failure` element (D14, D15), `schema_version` 7, and a
  validator that `reason_code` and `provider_failure.reason_code` agree. The plain `DataQualityError` branches
  are removed (D16).
- **Transport.** `fetch_json` and `fetch_filing` classify their failures and raise `FinancialProviderError`
  (D12); `not_found` and `provider_id` are required keywords on both protocols and every fetcher (D3): SEC,
  Massive, the check transport, the evaluation fixture fetcher and the test fakes.
- **Adapters.** SEC EDGAR and Massive facts handlers, `_resolve_cik` (D13) and `resolve_security_unit`'s
  narrowing, per the inventory. A filing identifier or a non-object document that SEC supplies is an
  `unexpected_response`.
- **Gate.** The complete managed gate.

### PH.2b — Yahoo, health and completion

`feat/ph-2b-yahoo-and-health-kinds`

- **Yahoo.** The `YFinanceClient` handlers and the yfinance facts adapter, through the helper; the listed
  `unreachable` types are in [§8](#8-verified-against-main).
- **Checks.** `ProviderCheckResult` gains the nullable kind (D20), `check_yfinance` opens with a connection step
  and then reads the quote and the history (D18), and `ian health` prints the kind.
- **Completion test** (inventory §7) and the runbook, `docs/project/PROVIDER_DEBUGGING.md`.
- **Connection failure tests (D19).** Two tests, since the log line no longer reaches standard error. An
  exception that escapes `yf.download` is named in the command's own message as `unreachable`. A fault that
  `yf.download` swallows (D11) is reported as `no_data` and the sentence does not claim the ticker is unknown;
  its cause is in the application log only.
- **Gate.** The complete managed gate. The live suite still passes on the project owner's machine, since the
  check bodies changed.

### PH.2c — Stored provider failures

`feat/ph-2c-stored-provider-failures`, after SWC.4c and PH.2b. Complete 2026-10-10.

- **Stored kind.** A `ProviderFailureRecord` (kind, provider, and the strategy input once an assembly records it)
  in `src/core/provider_failure_kind.py`, carried by `InputResolutionResult`, the FCF field resolution and
  assembly and result, the Graham assemblies, `InstrumentProfileDiagnostic`, `SecurityIdentityResolution` and
  `SecurityUnitResolution`, beside the unchanged `PROVIDER_ERROR` status. The seven carrier handlers narrow to
  typed provider failures and record the kind; anything else propagates. The result-built `PROVIDER_ERROR` sites
  take `unexpected_response` ([D23](#2-decisions)), the BVPS non-finite branch is kept ([D24](#2-decisions)) and
  the Yahoo naive-clock guard is a defect ([D25](#2-decisions)).
- **Codecs and versions.** The four strategy codecs encode the new fields through their native types. Bumped,
  with nothing migrated:

  | Version | Before | After |
  | :--- | :--- | :--- |
  | `AnalysisRun.run_schema_version` (and its paired check in `decode_evidence`) | 1 | 2 |
  | `result_schema_version`: Momentum, Graham Number, Graham Growth, FCF Growth | 2, 2, 2, 3 | 3, 3, 3, 4 |
  | `evidence_codec_version`: Momentum, Graham Number, Graham Growth, FCF Growth | 1, 2, 2, 1 | 2, 3, 3, 2 |
  | Document `schema_version`: Momentum, Graham Number, Graham Growth, FCF Growth | 6, 7, 7, 6 | 7, 8, 8, 7 |
  | Instrument-profile record `schema_version` ([D26](#2-decisions)) | 1 | 2 |

  Momentum's evidence bumps too, because it embeds the instrument profile and its diagnostics gain the kind.
  The 73 files in `tests/expected_output/strategy_documents/` are regenerated (the new element and the versions
  differ and nothing else), and six files are added for a provider failure that carries a kind.
- **The element is added in one place.** The strategy documents share a header and a tail declared once in
  `src/reporting/documents/strategy_document.py` ([design H.34](../swc/SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h34-common-header-and-tail-for-strategy-documents-2026-10-09)).
  PH.2c adds `provider_failure: ProviderFailure | None` (the type the failure envelope carries) to
  `StrategyDocumentHeader` directly after `status`, adds the key to `HEADER_KEYS`, and populates it in each
  presenter. No strategy envelope changes. The shape test `tests/reporting/test_strategy_document_shape.py` then
  covers every descriptor's `json_envelope` and the failure envelope.
- **Derived reports.** Every report derives from the stored kind through the one kind-to-code mapping and the one
  precedence function in `failure_classification.py` (`provider_failure_of`): the strategy documents and, through
  `failure_reason_code`, the saved run's `failure_reason_code`. The refresh job copies the code its run or its
  unsaved capture holds ([D27](#2-decisions)).
- **Conformance.** The check in [§5](#5-the-shared-provider_failure-element).
- **Gate.** The complete managed gate.

## 5. The shared `provider_failure` element

- **Shape.** `provider_failure` is null, or an object with `reason_code` (one of the three codes) and `inputs`,
  an array of `{input, provider_id, kind}`: each failed input with the provider that failed and its kind (`input` is null for a raised failure, D15). It is
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
  returns at its first failed input, so the list holds one entry today (FCF Growth skips a failed diluted-share
  field when it classifies on total free cash flow; that failure is not part of the element, and its trace event,
  which carries the failure's sentence, stays in the document's diagnostics); the rule matters for the first
  strategy that resolves inputs without stopping. No rule that the code
  suggests is better. A raised provider failure (Momentum) has no input name, so its `input` is null (D15).
- **Conformance check.** The shared strategy-document test (`tests/reporting/test_strategy_document_shape.py`, added by SWC.4c.1)
  iterates every strategy descriptor's `json_envelope` model (`STRATEGIES` in `src/strategy_wiring.py`) and fails if
  it does not take the shared header, which PH.2c extends with `provider_failure`, so a new strategy cannot omit it.
  PH.2c adds the failure envelope to the check.

## 6. Refresh job `reason_code`s

A refresh job carries a `reason_code` if and only if it raised, or its run is `failed`. An `unavailable` run is an
analysis outcome, not a failure, so its job carries none; neither does a `completed` or `not_applicable` job.

- A raised exception: the classifier's code, as today.
- A `failed` run: the run's stored `failure_reason_code`, copied. Every failed run stores a `FailureReasonCode`
  value (D5, row 10): the mapped provider code when the native status is a provider error, `invalid_input` when
  it is invalid input, otherwise `execution_error`. There is no translation step in the refresh.
- A `failed` outcome with no stored run (refresh with saving off) carries the code the saved run would have
  stored: the capture computes it once with the same function ([D27](#2-decisions)).

A run cannot be cancelled: the outcome does not exist ([R3 close-out](../r3/R3_DEAD_CODE_AUDIT_CLOSEOUT.md)), so
the rule has no `cancelled` case and no code is added for one. `data_unavailable` is not added either.

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

Checked at `847d28a` (2026-10-09). The PH.2c items (the carriers, the versions, the profile cache, the kindless raises
and the expected output) were checked and delivered at `2983bd2` (2026-10-10); the bullets below describe `main`
before PH.2c unless they say otherwise.

- **Where a provider failure ends.** Momentum raises `DataFetchError`, which reaches the failure envelope.
  Graham Number, Graham Growth and FCF Growth never raise it: the resolvers catch `FinancialProviderError`
  (`resolver.py:509`, `:1113`, `fcf_growth/input_resolver.py:607`) and store a `PROVIDER_ERROR` result. The
  Graham commands render their own failed presentation and exit 1; a saved run is `failed` with
  `execution_failed`; a refresh job has no `reason_code`. This is why D5 stores the kind.
- **`PROVIDER_ERROR` without a provider exception.** `resolver.py` also builds `PROVIDER_ERROR` results where the
  provider answered and the answer was rejected: `:540` (candidate validation), `:1148` (more than one fact for a
  single-observation request), `_validate_provider_response` (`:1466`, the coherence checks) and `:803` (a
  non-finite BVPS derivation, which is project arithmetic). These carried no kind. `_bvps_component_failure`
  (`:1376`) passes a component's status through, so a kind has to pass through it as well. PH.2c settles them in
  [D23 and D24](#2-decisions): the first four take `unexpected_response` from the requested provider, and the
  component failure passes its component's kind through.
- **Today's `--json` for a provider failure.** Momentum: the failure envelope. Graham Number and Graham
  Growth: a document with `status: "provider_error"`, a sentence in `reason`, null `result` and `inputs`, and no
  code. FCF Growth: the whole result with `status` and per-metric `reason_code` `provider_error`.
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
  passes it too. A non-historical `DataQualityError` also reached `data_error`, but cannot be raised (D16).
- **Codecs that would encode the kind.** The `_MomentumEvidence`, `_NumberEvidence`, `_GrowthEvidence` and
  `_FCFEvidence` models in each strategy's `codec.py`; `AnalysisRun.model_dump` in
  `repositories/analysis_runs.py`, which stores `instrument_profile`; and the hand-written
  `_diagnostics_payload` and `_diagnostics_from_payload` in `instrument_profile_cache.py`, which list fields
  explicitly and would drop a new one. The profile table stores that payload as opaque JSON.
- **Versions before PH.2c** (the table in [§4](#ph2c--stored-provider-failures) gives the new ones).
  `AnalysisRun.run_schema_version` was 1. Document `schema_version`: Momentum 6, Graham Number
  7, Graham Growth 7, FCF Growth 6. Descriptor `result_schema_version`: Momentum 2, Graham Number 2, Graham
  Growth 2, FCF Growth `FCF_GROWTH_RESULT_SCHEMA_VERSION`; `evidence_codec_version` is 2 for the two Graham strategies and 1 for the others. All four
  descriptors in `src/strategy_wiring.py` carry `json_envelope`.
- **Profile-cache payload.** `_encode_profile` writes `identity`, `kind_evidence` and `diagnostics` and no version
  field. The stored record has a `schema_version` column, which the repository wrote as the constant 1
  (`repositories/instrument_profiles.py`) and the cache never read; freshness was the age only. [D26](#2-decisions)
  settles it: the constant is 2, the cache reads the column, and the repository writes it on an update in place as
  well as on an insert, so a version-1 row refreshed under the same identity anchor becomes a version-2 row.
- **Transport failure class.** Before PH.2a `fetch_json` raised `OSError` or `ValueError`. `create_analysis_snapshot`
  swallowed `FinancialProviderError` around `_resolve_cik`, which loads the ticker map, and `fetch_facts` re-wrapped
  any `ValueError`, which `DataFetchError` is; a classified transport failure of either type would have been
  swallowed or re-wrapped. D12 and D13 settle it.
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
- **Yahoo connection fault through the client (D18).** PH.2b ran the stubbed-transport method at `847d28a` (the
  `curl_cffi` session's `request` raising `ConnectionError`, no network, `hide_exceptions` at its default of `True`)
  with the time zone cache empty and populated (`cache.get_tz_cache().store(...)`). The cache is what differs:
  with it populated `Ticker.history` skips the time zone lookup, its chart request fails inside a bare
  `except Exception` that returns when `hide_exceptions` is true (`yfinance/scrapers/history.py:235`), and the
  metadata is `{}`, so `FastInfo._get_1y_prices` raises `KeyError` on `self._md["currentTradingPeriod"]`
  (`scrapers/quote.py:153`). The right-hand column is a stubbed Yahoo answer with prices missing and no
  `currentTradingPeriod` in the metadata.

  | Call | Cache empty, offline | Cache populated, offline | Cache populated, Yahoo answers without the field |
  | :--- | :--- | :--- | :--- |
  | `yf.download` | empty frame | empty frame | empty frame |
  | `fast_info["last_price"]` | `ConnectionError` | `KeyError('currentTradingPeriod')` | `KeyError('currentTradingPeriod')` |
  | `fast_info["currency"]` | `KeyError('currency')` | `KeyError('currency')` | not measured |
  | `Ticker.info` | `ConnectionError` | `ConnectionError` | not measured |
  | `Ticker.history(period="1y", raise_errors=True)` (deprecated) | `ConnectionError` | `ConnectionError` | `YFPricesMissingError` |
  | `fast_info["last_price"]` with `hide_exceptions=False` | `ConnectionError` | `ConnectionError` | `YFPricesMissingError` |

  With the cache populated, "offline" and "answered without the field" give the same `KeyError` from the call the
  adapter makes, so no typed signal there separates them. The two typed signals (`raise_errors=True`, or
  `hide_exceptions=False`) are a deprecated parameter and a process-wide setting that refresh jobs on a thread pool
  would share, and neither is used. The opening connection step is what separates "cannot reach Yahoo".
- **Yahoo host and a plain request (D18).** yfinance 1.6.0 requests quote and history data from
  `https://query2.finance.yahoo.com` (`yfinance/const.py` `_BASE_URL_`, path `/v8/finance/chart/`), through the
  chart endpoint for `download`, `history` and `fast_info` alike. Its cookie and crumb setup uses `fc.yahoo.com` and
  `query1.finance.yahoo.com` and is cached. At `847d28a`, a standard-library `urllib` GET of
  `https://query2.finance.yahoo.com/` and of `/v8/finance/chart/AAPL` with the default `User-Agent` returned HTTP
  `429` (`Edge: Too Many Requests`); the chart request with a browser `User-Agent` returned `200`. A TCP connection
  and TLS 1.3 handshake to `query2.finance.yahoo.com:443` succeeded in about 0.06 s. The step is therefore a TCP and
  TLS connection with no request sent.
- **Proxy detection (D18).** `curl_cffi` 0.16.0 (the HTTP layer yfinance 1.6.0 uses) has no code that reads system
  proxy settings: no use of `getproxies`, `proxy_bypass`, `winreg` or `SystemConfiguration` in `curl_cffi` or
  `yfinance`. `curl_cffi/requests/utils.py` sets `CURLOPT_PROXY` only from an explicit `proxies` mapping (yfinance
  fills it from `YfConfig.network.proxy`, which the application does not set); the session's `trust_env` flag is
  stored and never read. Otherwise libcurl chooses. Observed at `847d28a` with a request to an unresolvable host:
  with no variables the failure was a DNS error; with `https_proxy` or `HTTPS_PROXY` or `ALL_PROXY` set to a closed
  local port it was a connection failure over that proxy; with `NO_PROXY` naming the host the proxy was bypassed
  again (DNS error). A proxy set only in the system settings could not be tested without changing them; the source
  shows no path that would use one.
- **`fetch_json` call sites.** Per-company: SEC `financial_facts.py` 245, 246, 418, 422; Massive 242; the check
  transport's company-facts call (`provider_checks.py:251`). Fixed: SEC 529 (the ticker map) and the check
  transport's ticker-map call (`:248`). `cli_health.py` builds the check transport from `fetch_json`.
- **Logging.** Every record goes to `logs/app.log` and none is printed, so the `logger.error` line in
  `YFinanceClient.fetch_data` (reached only by an exception that escapes `yf.download`) does not reach standard
  error. The adapters take the SEC identity and the Massive key as constructor arguments and do not read the
  environment; `src/config.py` is the only reader.
- **`execution_failed`.** Was written at `workspace/execution.py:150`; checked only as non-empty at
  `workspace/runs.py:126`; no other reader. Only `tests/workspace/test_execution.py:197` asserted it. `FAILED`
  comes only from the three Graham and FCF `execution.py` outcome mappings. Graham Number also maps a calculation
  that does not apply (a non-positive EPS or BVPS, native status `not_applicable`) to `failed`; under
  [D27](#2-decisions) such a run stores `execution_error`, which the project owner may want to revisit.
- **Raises of a provider failure without a kind (PH.2c scan of `src/`).** None is left in a production adapter:
  the Yahoo naive-clock guard was the only one and is now a defect (D25). Three evaluation fixtures still raise one,
  so their `provider-error` expected-output cases store a `provider_error` status with a null `provider_failure`
  and show the unclassified path: `FixtureAnnualFinancialFactsProvider` (`fcf_earnings_growth.py`),
  `FixtureFinancialFactsProvider` (`graham.py`) and `FixtureDataClient` (`market_data.py`, two raises). Not
  changed. The document tests wrap the fixtures to raise a kinded failure for the `provider-unreachable` cases.
- **Stored shapes that still carry a provider failure without a kind (PH.2c).** The resolver's trace events and the
  Graham assemblies' `quote_status`/`quote_reason` for a failed optional quote carry the failure as prose only; the
  security-unit profile diagnostic keeps its `unavailable` status beside the kind. None is a changed output, and
  none was in PH.2c's list; they are carried to issue #40 and PH.3.
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
