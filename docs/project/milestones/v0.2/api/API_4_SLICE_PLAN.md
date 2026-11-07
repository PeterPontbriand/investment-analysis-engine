# API.4 — Slice Plan: Action Endpoints, Selection Forms and Refresh Jobs

Splits [API.4](API_CONTRACT_AND_SLICE_PLAN.md#api4--action-endpoints-and-refresh-jobs) into two slices
([J1](#j1-api4-is-two-slices-2026-11-06)). The first adds the endpoints that change a watchlist or analyze one ticker,
the selection forms, the result documents the CLI and the API share, and every error at once. The second adds the refresh
job: start, progress, stop.

## 1. At a glance

- **What this plan does:**
  - API.4a adds eight action endpoints and the selection form endpoint to the one route table, with request bodies read as
    JSON objects, success and failure statuses for each, and a CORS preflight for every method the table declares;
  - API.4a gives rename, delete and the three removals a versioned result document that the CLI's `--json` and the API
    both write, and gives the watchlist document a `schema_version`;
  - API.4a makes `build_selection` report every error in field order, and the failure document list them;
  - API.4b adds the refresh job: a start endpoint, a polled progress document and a stop endpoint, one job at a time per
    server.
- **What it does not do:** change a stored shape, a formula, a classification or a dependency, or build a GUI. API.4a
  adds no job and no CLI command; API.4b adds no CLI command for a refresh over a list of entries
  ([J11b](#j11b-no-cli-command-for-an-entries-job-2026-11-06)).
- **Rules every slice follows:**
  - no financial logic in `cli` or `api`, and no strategy-specific code in either (`AGENTS.md` §9);
  - the managed quality gate, with the Python 3.14 second pass, after each slice, and the project owner's approval
    before the next slice starts;
  - inside `/v1` a change only adds, except where a decision here says otherwise and the pull request lists it.
- **Sequence rule** (approved 2026-11-04): each slice's pull request marks its own row Complete, dated the day the pull
  request is opened, and sets the next slice's row to Next.
- **Where the history lives:** decisions J1 to J20 and J11b are in [Appendix A](#appendix-a-decision-records), approved by
  the project owner on 2026-11-06, with J2 and J11 as revised.

## 2. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| API.4a | [Action endpoints, selection forms, result documents and error lists](#api4a--action-endpoints-selection-forms-result-documents-and-error-lists) | Complete | 2026-11-06 |
| API.4b | [Refresh jobs](#api4b--refresh-jobs) | Next | |

## 3. The slices

### API.4a — Action endpoints, selection forms, result documents and error lists

- **Problem:** a client cannot yet change a watchlist or analyze a ticker; it cannot learn the fields of a selection or
  their configured values; the CLI's rename, delete and removal outputs are not documents it could share; and a form that
  sends several bad fields learns of one at a time.
- **Decision:**
  - eight action endpoints with synchronous handlers in the one route table ([J3](#j3-the-action-endpoints-2026-11-06),
    [J4](#j4-success-statuses-2026-11-06), [J12](#j12-failure-statuses-2026-11-06));
  - bodies are one JSON object, an unknown field is rejected, and a field is named by its path
    ([J5](#j5-request-bodies-2026-11-06), [J8](#j8-as_of-in-a-selection-is-text-2026-11-06));
  - the same defaults as the CLI ([J9](#j9-defaults-match-the-cli-2026-11-06)) and one analysis document
    ([J10](#j10-the-analysis-document-2026-11-06));
  - a preflight allows the declared methods and `Content-Type` ([J6](#j6-cors-allows-the-declared-methods-2026-11-06));
  - a selection form per strategy ([J7](#j7-the-selection-form-2026-11-06));
  - result documents shared by the CLI and the API ([J2](#j2-result-documents-shared-by-the-cli-and-the-api-2026-11-06));
  - every error at once ([J13](#j13-every-error-at-once-2026-11-06)).
- **Scope:**
  - `api`: the route table, `request_bodies.py`, `selection_forms.py`, the handlers, the analysis document, the status
    table and the preflight;
  - `application`: `build_selection` and `ActionParameterError` (several errors);
  - `core` and `reporting`: the rule-violation carrier, the failure envelope's `errors` and its version;
  - `workspace_documents/watchlist.py`: the versioned documents and their builders; `StoredSelectionError` gains the stored
    method identifier;
  - `cli_workspace.py`: `--json` of rename, delete and the removals writes the result document;
  - `schemas/`, `schemas/openapi.json`, `scripts/generate_openapi.py` and `scripts/generate_schemas.py`;
  - `docs/user/USAGE.md`, `WORKSPACE.md`, `API.md`, Architecture §13, this plan and the contract.
- **Branch:** `feat/api-actions`.
- **Detail:** [Implementation record](#31-api4a-implementation-record).

### API.4b — Refresh jobs

- **Problem:** a refresh runs for minutes, and a client can neither follow it nor stop it.
- **Decision:**
  - the job is polled ([J14](#j14-refresh-progress-by-polling-2026-11-06)), its ID is the refresh ID
    ([J15](#j15-the-jobs-id-is-the-refresh-id-2026-11-06)), its state is an open vocabulary
    ([J16](#j16-job-states-2026-11-06)), stop is idempotent ([J17](#j17-stop-2026-11-06)), and only the latest job is kept
    ([J18](#j18-only-the-latest-job-is-kept-2026-11-06));
  - a job starts from a watchlist or from a list of entries ([J11](#j11-a-refresh-job-starts-from-a-watchlist-or-a-list-of-entries-2026-11-06));
  - two servers, or a server and the CLI, may share a database ([J19](#j19-several-processes-one-database-2026-11-06));
  - shutdown cancels a running job ([J20](#j20-shutdown-with-a-job-running-2026-11-06)).
- **Scope:** recorded in Part 3 of the API.4a prompt and in the decision records; its slice plan section is written when
  the slice starts.
- **Branch:** `feat/api-refresh-jobs`.
- **Detail:** ⚠ no slice plan yet

### 3.1 API.4a implementation record

What changed, by area:

- **`api`:**
  - `routes.py`: `RouteSpec.method` is `GET`, `POST`, `PATCH` or `DELETE`, a route has an optional request model and a
    `success_status`, and nine routes are added (the selection form and the eight actions). Every route declares exactly
    the statuses it can give; `GET /v1/watchlists/{watchlist_id}` gains 409, because reading a watchlist can meet an
    unreadable entry;
  - `request_bodies.py`: the strict body models, `read_body`, `read_json_object` and `read_request`. A body field is named
    by its path (`tickers[1]`, `selection.policy.historical_horizon`); a body has a size limit and refuses non-standard
    numbers ([J24](#j24-a-request-body-has-a-size-limit-2026-11-06),
    [J25](#j25-non-standard-json-numbers-are-refused-2026-11-06));
  - `handlers.py`: a route with a body reads it in an `async` shim and runs the synchronous operation in the thread pool
    ([S40](API_2_SLICE_PLAN.md#s40-synchronous-handlers-2026-11-03) stands for the operations). The handlers call the
    existing application operations; a selection is built by `build_selection`, and its errors are renamed
    `selection.<field>` ([J8](#j8-as_of-in-a-selection-is-text-2026-11-06));
  - `selection_forms.py`: the form document and its builder, and the configured defaults. The schema comes from
    `selection_schema` in `application/selections.py`, which `scripts/generate_schemas.py` also imports, so the form and the
    published file come from one code path ([J21](#j21-the-selection-schema-lives-beside-build_selection-2026-11-06));
  - `documents.py`: the analysis document and its text;
  - `responses.py`: 409 for `watchlist_name_conflict` and `stored_selection_unreadable`, 404 for
    `watchlist_entry_not_found`; `checks.py`: the preflight lists the table's methods and `Authorization, Content-Type`.
- **`application`:** `build_selection` collects every field error, and `ActionParameterError.several(...)` carries them;
  `named(...)` spells each in the caller's names. A fixed field and every `as_of` error join the list; only an undeclared
  method is raised alone ([J22](#j22-pre-check-errors-join-the-error-list-2026-11-06)).
- **`core` and `reporting`:** `RuleViolation` and `InvalidParameterError.violations`; `FailureEnvelope` goes to version 12
  and gains `errors` (`FailureRuleError`: `rule`, `parameters`, `arguments`, `message`); `json_argument` makes a rule
  argument a JSON value.
- **`workspace` and `workspace_documents`:** `StoredSelectionError` carries `method_id`, the identifier as stored (its
  `method` field holds the alias when there is one); `WatchlistDocument` gains `schema_version`; the rename, removal and
  delete result documents and the unreadable-entry document are new; `requested_name` is removed from the delete document.
- **CLI:** with `--json`, `rename`, `delete` and the three removals write their result document. After a committed change
  that left an entry unreadable they write that document, not the failure document, and still exit 1. Text output, the
  confirmations on standard error, help and exit codes are unchanged.
- **Schemas:** `watchlist-rename.schema.json` and `watchlist-removal.schema.json` are new; `failure`, `watchlist`,
  `watchlist-delete` and `openapi.json` are regenerated. `openapi.json` describes the request bodies and refers to the
  selection schemas, and to each strategy's document in the analysis document, as alternatives.
- **Documents:** `USAGE.md` (the error list and version 12), `WORKSPACE.md` (the result documents), `API.md`,
  `ARCHITECTURE.md` §13 (`api` imports `workspace`), this plan, the contract, and one pointer line each in S14 and S31 of
  [API.2](API_2_SLICE_PLAN.md).

User-visible changes:

- The failure document is `schema_version` 12 and gains `errors`, in the CLI and in the API; `reason` and `parameters` are
  still the first error's, so no message, `parameters` value or exit code changed.
- `watchlist show`, `create` and `add-selection` with `--json` write a watchlist document with `schema_version` 1 as its
  first key.
- `watchlist rename --json`, the three removals with `--json` and `watchlist delete --json` write a result document of
  their own ([J2](#j2-result-documents-shared-by-the-cli-and-the-api-2026-11-06)). The delete document loses
  `requested_name`. After a committed change that left an entry unreadable, `--json` now writes the result document with
  `unreadable` set, not the failure document; the exit code is still 1.
- `GET /v1/watchlists/{watchlist_id}` answers 409 `stored_selection_unreadable` for a watchlist holding an unreadable
  entry; it answered 500.
- A preflight allows `GET, POST, PATCH, DELETE` and `Authorization, Content-Type`.
- A request body over 1,048,576 bytes, or one holding `NaN`, `Infinity`, `-Infinity` or a number too large for a float,
  is `400 invalid_parameter` naming `body`.
- A save failure in `POST /v1/analyses` names the ticker, as the command line does.
- No stored shape, `config_schema_version`, formula, classification or dependency changed.

Re-recorded files under `tests/expected_output/workspace_commands/`: `watchlist-add-selection-json.txt`,
`watchlist-create-json.txt`, `watchlist-create-seeded-json.txt`, `watchlist-delete-json-timestamps.txt`,
`watchlist-delete-json.txt`, `watchlist-delete-missing-ok-json.txt`, `watchlist-remove-entry-json.txt`,
`watchlist-remove-method-json.txt`, `watchlist-remove-ticker-json-nothing-removed.txt`,
`watchlist-remove-ticker-json.txt`, `watchlist-rename-json-timestamps.txt`, `watchlist-rename-json.txt`,
`watchlist-show-json-as-of-timestamps.txt`, `watchlist-show-json-empty.txt`, `watchlist-show-json-timestamps.txt` and
`watchlist-show-json.txt`. No file under `cli_help/`, `direct_commands/` or `strategy_documents/` changed.

Tests edited, and why:

- Failure document version 12 and the `errors` key: `tests/api/test_errors.py`, `tests/reporting/test_failure_envelope.py`,
  `tests/test_cli_failure_envelope.py`, `tests/test_command_validation_failures.py`,
  `tests/test_existing_strategy_failure_output.py` and `tests/test_cli_database_readiness.py`.
- The status table: `tests/api/test_errors.py` (409 and the entry 404).
- Methods and headers of the route table and the preflight: `tests/api/test_request_checks.py` and
  `tests/api/test_routes_and_description.py` (a route may be any declared method, has one success status and a request
  body).
- The result documents and the watchlist `schema_version`: `tests/workspace_documents/test_workspace_documents.py` (the
  unversioned-schema test is now a version-one test, the delete test covers the new validator, and the unreadable-entry
  document is tested), `tests/test_cli_workspace.py` and `tests/test_cli_watchlist_json.py` (the documents; the
  unreadable cases now write the result document under `--json`, and a text-mode case pins the unchanged behavior).
- `StoredSelectionError`'s fifth field: `tests/workspace/test_watchlists.py`.
- Every error at once: `tests/application/test_selections.py` (the first-error-only test).
- The moved selection schema: `tests/scripts/test_generate_schemas.py` imports it from `application/selections.py`.

Tests added: `tests/api/test_actions.py` (every route: success, each failure status it declares, an unknown field, a bad
or missing content type, an unparseable body, parameter naming by body path, a nested selection field, the unreadable
cases, the selection form against the published file and a changed settings file, the analysis document for every
strategy, and a preflight for each method) and `tests/api/test_rule_error_lists.py` (several errors in field order with
rule, parameters and values, `reason` and `parameters` equal to the first, the CLI's message and exit code unchanged,
non-finite and date arguments as text).

Accepted deviations:

- `StoredSelectionError.method` holds the alias, or the stored identifier when no alias exists, so it cannot give the
  stored method identifier. The error gains a `method_id` field instead; no stored shape changes.
- An undeclared `method_id` in the selection form's path is `400 invalid_parameter` naming `method_id`, not 404
  `endpoint_not_found`: an unknown path segment never gave 404 `endpoint_not_found` (that code is for an unrouted path), and
  every other place a method identifier is checked, in a query or a body, already answers `invalid_parameter`.
- `selection_schema` and `FIXED_SELECTION_FIELDS` moved from `scripts/generate_schemas.py` into
  `investment_analysis_engine/application/selections.py`, because the package cannot import `scripts`.
- A failure while saving the result of an analysis is answered with the save message and its classified code, as the
  command line reports it, in place of the fixed `execution_error` message.

Review fixes (2026-11-06, [J21](#j21-the-selection-schema-lives-beside-build_selection-2026-11-06) to
[J28](#j28-the-ticker-rule-is-written-once-2026-11-06)): the project owner reviewed the branch and approved these fixes, all done. No stored
shape, formula, classification or dependency changed, and no CLI text, help or exit code.

- **R1 (J21).** `selection_schema` and `FIXED_SELECTION_FIELDS` are in `application/selections.py`; `build_selection` uses
  the constant, `api/selection_forms.py` and `scripts/generate_schemas.py` import the function, and the script no longer
  imports `api`. The published schemas did not change.
- **R2 (J22).** `build_selection` lists a fixed field, every `as_of` error and every field error together, in field order,
  and accepts `as_of` as text. The API handler no longer parses or type-checks `as_of`.
- **R3 (J23).** The analysis handler describes a save failure with the ticker; the generic branch is gone.
- **R4 (J24).** `MAX_REQUEST_BODY_BYTES` and `read_body`; `docs/user/API.md` states the limit.
- **R5 (J25).** `NaN`, `Infinity`, `-Infinity` and a number too large for a float are refused in a body.
- **R6 (J26).** These records, and the pointer line under S40 in API.2.
- **R7 (J27).** An operation returns only a document; a described save failure is raised as `DescribedFailure`.
- **R8 (J28).** `normalize_ticker` is in `core/tickers.py`; `analyze` checks its own ticker; the API passes it as
  received; the command line and the orchestrator delegate to the one rule and keep their messages.

Tests edited, and why: `tests/application/test_selections.py` (a non-date `as_of` has the rule `selection.as_of_type`, and the
first-error-only cases list the pre-checks); `tests/api/test_actions.py` (a number as `as_of` has an `errors` list; the save
failure names the ticker and carries the classified code; the schema import moved); `tests/scripts/test_generate_schemas.py`
(the schema import moved); `tests/api/test_rule_error_lists.py` (the API test that sent `Infinity` and `NaN` now sends two
text values for number fields, because those tokens are refused).

Tests added: `tests/api/test_request_body_limits.py` (a declared length over the limit, a body over it with no length or a
false one, a body at the limit, each non-standard number nested in `selection`, and an ordinary syntax error keeping its
message) and, in `tests/api/test_rule_error_lists.py` and `tests/application/test_selections.py`, each pre-check alone with its
rule, `parameters` and message, the command line's messages and exit codes for a bad `--as-of`, and an invalid `as_of` text
with invalid field values listed in field order through `build_selection` and `POST /v1/analyses`.

Noticed for later slices: nothing further.

## 4. Scope limits and acceptance criteria

- API.4a changes no stored shape, formula, classification or dependency, adds no job, and changes no CLI text output,
  help text or exit code.
- A strategy added through `scripts/new_strategy.py` appears in the selection form and in every action endpoint with no
  edit to `api` or `application`; the endpoint tests are parametrized over `STRATEGIES`.
- `schemas/` and `schemas/openapi.json` are regenerated and compared in the managed gate.
- Every route declares exactly the statuses it can give, and a preflight allows exactly the methods the table declares.
- A selection with several bad fields reports each in field order; `reason` and `parameters` are the first's.
- API.4b: one job at a time per server, a job that ends is kept until a new one replaces it, a job not finished at shutdown
  is not saved, and the stored runs of an API refresh are those a CLI refresh stores.

## 5. Background

The API.3 slices moved every action into the application layer. API.4 serves them. The contract recorded five
requirements for it: the selection defaults, the text of a direct analysis, every field's error at once, a transport for
refresh progress and the rule identifiers and values of an error. It also left one question open, whether two `ian serve`
processes may share a database ([J19](#j19-several-processes-one-database-2026-11-06) settles it). A refresh is the one
action that outlasts a request, so it is its own slice.

## Appendix A: Decision records

All approved by the project owner on 2026-11-06; J2 and J11 as revised.

### J1 API.4 is two slices (2026-11-06)

API.4 is split into API.4a (the action endpoints, selection forms, result documents and error lists, on
`feat/api-actions`) and API.4b (refresh jobs, on `feat/api-refresh-jobs`).

### J2 Result documents shared by the CLI and the API (2026-11-06)

- `WatchlistDocument` gains `schema_version`, `Literal[1]`; the document never had a version.
- New versioned documents: the rename result `{schema_version, watchlist, unreadable}`, the removal result
  `{schema_version, removed, watchlist, unreadable}` (used by `remove-entry`, `remove-ticker` and `remove-method`;
  `removed` is the count of removed entries) and the delete result `{schema_version, deleted, watchlist, unreadable}`
  (`requested_name` is removed; `deleted` is false only for `--missing-ok` on a missing watchlist, and then `watchlist` and
  `unreadable` are both null).
- In every result document exactly one of `watchlist` and `unreadable` is set, except that missing case. A model validator
  enforces it.
- `unreadable` is `{entry_number, ticker, method_id, reason}`; `reason` is the stored-selection error's own message, which
  names no `ian` command ([W16](API_3_SLICE_PLAN.md#w16-the-cli-adds-the-remedy-for-an-unreadable-entry-2026-11-05)).
- With `--json` the CLI writes the result document for rename, delete and the removals. After a committed change that left
  an entry unreadable it writes the result document, not the failure document, and exits 1. Text output, the confirmations
  on standard error, help and exit codes are unchanged. `create` and `add-selection` keep writing the watchlist document.
- Each document is published in `schemas/`, and the drift check covers it.

### J3 The action endpoints (2026-11-06)

All are in the one route table ([S41](API_2_SLICE_PLAN.md#s41-one-route-table-2026-11-03)), with synchronous handlers, and
`RouteSpec.method` widens to the methods used:

| Request | Body | Success |
| :--- | :--- | :--- |
| `POST /v1/watchlists` | `name` | 201, watchlist document |
| `PATCH /v1/watchlists/{watchlist_id}` | `name` | 200, rename result |
| `DELETE /v1/watchlists/{watchlist_id}` | none | 200, delete result |
| `POST /v1/watchlists/{watchlist_id}/entries` | `method_id`, `tickers`, `selection` | 200, watchlist document |
| `DELETE /v1/watchlists/{watchlist_id}/entries/{entry_number}` | none | 200, removal result |
| `POST /v1/watchlists/{watchlist_id}/remove-tickers` | `tickers` | 200, removal result |
| `POST /v1/watchlists/{watchlist_id}/remove-method` | `method_id` | 200, removal result |
| `POST /v1/analyses` | `ticker`, `method_id`, `selection`, `save`, `provider_check` | 200, analysis document |

`entry_number` is 1-based, as on the CLI. Tickers are normalized as the CLI's direct command and `add-selection` normalize
them.

### J4 Success statuses (2026-11-06)

Create answers 201; every other action answers 200. An unavailable or failed analysis is still 200, because its document
reports it.

### J5 Request bodies (2026-11-06)

A body is a JSON object only. An unknown field is `invalid_parameter` naming it. A missing or non-JSON `Content-Type`, or a
body that does not parse as a JSON object, is `invalid_parameter` with the parameter `body`. A field is named by its path:
`name`, `tickers`, `tickers[1]`, `selection.short_window`, `selection.policy.historical_horizon`, and later
`entries[2].short_window`. The actions' own parameter names fill in through `ActionParameterError.named`
([W17](API_3_SLICE_PLAN.md#w17-an-actions-parameter-error-is-a-template-2026-11-05)).

### J6 CORS allows the declared methods (2026-11-06)

Amends [S31](API_2_SLICE_PLAN.md#s31-cors-headers-2026-11-03). A preflight allows exactly the methods the route table
declares and the headers `Authorization` and `Content-Type`. Everything else in S31 stands.

### J7 The selection form (2026-11-06)

`GET /v1/strategies/{method_id}/selection` returns a new API-only document `{schema_version: 1, schema, defaults}`.
`schema` is the JSON of `schemas/selections/<alias>.schema.json`, produced by the same code path and not read from the
file. `defaults` maps each field in the strategy's `selection_settings_fields` to its current configured value, loaded
through the application context, and is empty for a strategy with none. `schemas/openapi.json` refers to the selection
schemas through this endpoint's response.

### J8 `as_of` in a selection is text (2026-11-06)

Inside `selection`, `as_of` is a string parsed by `parse_as_of_text` under the parameter `selection.as_of`; the end-of-day
rule stays with `as_of_boundary` ([W43](API_3_SLICE_PLAN.md#w43-the-as-of-syntax-parser-is-in-the-application-layer-2026-11-06)).

### J9 Defaults match the CLI (2026-11-06)

`save` is optional and defaults to false. `provider_check` is optional and defaults to the `IAN_PROVIDER_CHECK` choice read
at launch (`settings.provider_check`), the default the CLI uses.

### J10 The analysis document (2026-11-06)

`POST /v1/analyses` analyzes one ticker under one selection through `analyze` and returns a new API-only document
`{schema_version: 1, analysis_run_id, document, text: {concise, details, diagnostics}}`. `document` is the outcome's
document; each text value is `render_text` in that mode
([C5a](API_3_SLICE_PLAN.md#c5a-direct-analysis-is-an-operation-that-returns-an-outcome-2026-11-04)).

### J11 A refresh job starts from a watchlist or a list of entries (2026-11-06)

Revised. `POST /v1/refreshes` (API.4b) takes exactly one of `watchlist_id` or `entries` (a list of
`{ticker, method_id, selection}`), plus `workers`, `save` and `provider_check`. A duplicate entry is `invalid_parameter`.
The coordinator's `WatchlistLookup` becomes a source of a frozen entry snapshot. No stored shape changes, because a saved
run records only a refresh ID and a batch position. `POST /v1/analyses` stays for one selection.

### J11b No CLI command for an entries job (2026-11-06)

A refresh over a list of entries has no CLI command.

### J12 Failure statuses (2026-11-06)

Extends [S14](API_2_SLICE_PLAN.md#s14-errors-2026-11-03). `STATUS_BY_CODE` gains 409 for `watchlist_name_conflict` and
`stored_selection_unreadable` (an add refused by W15) and 404 for `watchlist_entry_not_found`. Every route's declared
responses list exactly the statuses it can give.

### J13 Every error at once (2026-11-06)

`build_selection` collects every error, in field order. `FailureEnvelope` goes from `schema_version` 11 to 12 and gains an
optional `errors`, each item `{rule, parameters, arguments, message}`. `errors` is set exactly when `reason_code` is
`invalid_parameter` and a rule rejected the argument (an `ActionParameterError`, single or several); it is null otherwise,
including a plain `InvalidParameterError` from the API's own parameter parsing. `reason` and `parameters` stay the first
error's, so every CLI message, exit code and `parameters` value is unchanged. `arguments` values are JSON values: a string,
integer, boolean or null as it is, a finite float as a number, a non-finite float as its text (`inf`, `-inf`, `nan`), a
date or timestamp as ISO 8601 text, anything else as `str()`.
([W32](API_3_SLICE_PLAN.md#w32-first-error-only-2026-11-05) and
[W42](API_3_SLICE_PLAN.md#w42-errors-keep-what-a-translation-needs-2026-11-05) are extended.)

### J14 Refresh progress by polling (2026-11-06)

`GET /v1/refreshes/{refresh_id}/job?after=<sequence>` returns
`{schema_version, refresh_id, watchlist_id, state, totals, events, next_after, summary, failure}`. Each event has
`sequence`, `kind` (`started` or `finished`), `position`, `ticker` and `method_id`; a finished event adds its
`RefreshResultDocument` and the strategy's document. Server-sent events and WebSocket were rejected because a browser
cannot send the `Authorization` header with them, and [S6](API_2_SLICE_PLAN.md#s6-205-is-settled-by-contract-rules-2026-11-03)
forbids the token in a URL.

### J15 The job's ID is the refresh ID (2026-11-06)

The ID is created before the job starts and passed to the coordinator's `refresh_id_factory` through a new optional
`refresh_id` argument of `refresh_watchlist`. The worker range, a missing or empty watchlist and, for an entries job,
`build_selection` on every entry (errors named like `entries[2].short_window`) are checked before the 202.

### J16 Job states (2026-11-06)

`state` is an open vocabulary: `running`, `stopping`, `completed`, `stopped`, `failed`. `summary` is set for `completed` and
`stopped`; `failure` (a `FailureEnvelope`) is set for `failed`.

### J17 Stop (2026-11-06)

`POST /v1/refreshes/{refresh_id}/job/stop` is idempotent and returns the job document.

### J18 Only the latest job is kept (2026-11-06)

Starting a new job replaces the previous one once it has ended. An older ID is 404 `refresh_job_not_found`. A start while a
job runs is 409 `refresh_job_running`.

### J19 Several processes, one database (2026-11-06)

Settles the open question of the contract's API.4 entry. Two `ian serve` processes, or `ian serve` and the CLI, may use
one database. One job at a time applies per server. SQLite WAL and the busy timeout serialize writes, and a write that
waits too long is `database_busy` (503). A running refresh works from its snapshot, so other actions in the same server
proceed normally. API.4b documents this in `docs/user/API.md`.

### J20 Shutdown with a job running (2026-11-06)

On shutdown with a job running, the server sets the job's cancellation event, waits up to the same 5-second grace
([S26](API_2_SLICE_PLAN.md#s26-stopping-2026-11-03)) and exits. An admitted job not finished by then is not saved. This is
the one exception to [W50](API_3_SLICE_PLAN.md#w50-an-admitted-job-always-runs-2026-11-06).

### J21 The selection schema lives beside `build_selection` (2026-11-06)

Amends the record of API.4a's `selection_forms.py`. `selection_schema` and the one declaration of the fixed fields,
`FIXED_SELECTION_FIELDS`, are in `application/selections.py`, next to `build_selection`, which uses the same constant. The
selection form builder in `api/selection_forms.py` and `scripts/generate_schemas.py` import the schema function from
`application`; the script no longer imports `api`. The published selection schemas and `openapi.json` are byte for byte
unchanged.

### J22 Pre-check errors join the error list (2026-11-06)

Amends [J13](#j13-every-error-at-once-2026-11-06), [W27](API_3_SLICE_PLAN.md#w27-build_selections-place-and-input-2026-11-05)
and [W43](API_3_SLICE_PLAN.md#w43-the-as-of-syntax-parser-is-in-the-application-layer-2026-11-06). `build_selection` reports
in one `ActionParameterError` list, in the model's field order, a fixed field present in the request, every `as_of` error
and every model field error. Only an undeclared `method_id` is raised alone, because there is then no model to validate.
`build_selection` accepts `as_of` as a date, a timestamp with an offset, or text; text is read by `parse_as_of_text` inside
the same pass, so an empty or malformed `as_of` is listed with the field errors. A value of any other type has the rule
`selection.as_of_type` and the message "{as_of} must be a date, a timestamp or text.", which replaces both the API's
"selection.as_of must be a string." and the built-in `pydantic.date_type` for this case. The command line still parses
`--as-of` itself and names its errors `--as-of`, so every single-error message, `parameters` value and exit code is
unchanged.

### J23 A save failure names the ticker (2026-11-06)

Amends [J12](#j12-failure-statuses-2026-11-06). The analysis handler describes a failure to save with
`describe_failure(cause, <the ticker>, saving=True)`, so the message is "<TICKER> was analyzed, but the result could not be
saved.", as the command line reports it. The generic branch for a saving failure in the error mapping is removed; no other
caller reaches it.

### J24 A request body has a size limit (2026-11-06)

Amends [J5](#j5-request-bodies-2026-11-06). `MAX_REQUEST_BODY_BYTES` is 1,048,576 in `api/request_bodies.py`. A body over it
is `400 invalid_parameter` with the parameter `body`; the message states the limit in bytes. A `Content-Length` that is an
integer over the limit is refused before anything is read, and the bytes actually received are counted as they arrive from
`request.stream()`, so a body with no length or a false one is stopped at the limit and never held whole. No reason code and no
status is added.

### J25 Non-standard JSON numbers are refused (2026-11-06)

Amends [J5](#j5-request-bodies-2026-11-06). A body holding `NaN`, `Infinity` or `-Infinity` anywhere is
`400 invalid_parameter` with the parameter `body` and the message "The request body must not contain NaN, Infinity or a
number too large to store.". A number too large for a float (`1e999`) is refused the same way, because Python reads it as
infinity and it would otherwise reach a field as the value the first rule refuses. A body that is not JSON keeps "The
request body must be a JSON object.". A non-finite argument can therefore reach the failure envelope only from a caller of
`build_selection`, never from the API.

### J26 Plan records (2026-11-06)

Records the review fixes. A route with a body reads it in one asynchronous step and runs its operation in the thread pool,
which is noted under [S40](API_2_SLICE_PLAN.md#s40-synchronous-handlers-2026-11-03). The change of
`GET /v1/watchlists/{watchlist_id}` from 500 to 409 `stored_selection_unreadable` for an unreadable entry is a defect fix
and not an addition under [S4](API_2_SLICE_PLAN.md): a 500 told clients the condition was unexpected, and it is corrected
before any client is built against it.

### J27 An operation returns only a document (2026-11-06)

Amends [J23](#j23-a-save-failure-names-the-ticker-2026-11-06). An operation in `api/handlers.py` returns a document and
nothing else. A failure an operation has already described is raised as `DescribedFailure(code, message, cause)`, defined in
`api/responses.py` beside the failure responses. `_analyze` catches `SavingFailureError`, describes it with
`describe_failure(cause, <the normalized ticker>, saving=True)` and raises `DescribedFailure`; `error_response` turns it into
the failure envelope with that code, that message and the cause. The body, status and log output of a save failure are
unchanged.

### J28 The ticker rule is written once (2026-11-06)

Amends [W10](API_3_SLICE_PLAN.md#w10-argument-checks-are-in-the-actions-2026-11-05) and
[W18](API_3_SLICE_PLAN.md#w18-arguments-are-checked-before-the-database-opens-2026-11-05).

- `normalize_ticker` moved from `workspace/watchlists.py` to the new `core/tickers.py`, with the same behavior and the same
  message ("ticker must not be empty."), approved by the project owner on 2026-11-06 because the orchestrator, a lower layer
  than `workspace`, needs it. Every importer imports it from `core`; nothing re-exports it. The ticker validators of
  `workspace/runs.py`, `workspace/requests.py` and `orchestrator/analysis_tool_arguments.py` call it; the orchestrator's keeps
  its own message, "ticker must be a non-empty string."
- `analyze` normalizes and checks its own ticker before any database is opened or provider called. A blank one is an
  `ActionParameterError` with the template "{ticker} must be a non-empty symbol.", rule `analysis.blank_ticker` and parameter
  `ticker`. The API handler passes the ticker as received.
- The command line keeps resolving its ticker before it checks anything else, so a blank ticker is still reported before an
  output-flag conflict or a selection error and a failure document still names the normalized ticker. `resolve_ticker` calls
  `normalize_ticker` and words the rejection with `TICKER` or `--ticker`; the conflict check compares normalized values, a
  blank one comparing as empty. This keeps every message, `parameters` value, exit code and expected output unchanged;
  moving the check into `analyze` alone would have changed the order of two errors and the ticker in a failure document.
- Other places that trim and upper-case a ticker (data providers, document validators, codecs, evaluation fixtures) are
  consistency checks of an already-normalized value or part of a provider's own subject handling, and are not changed.
