# API.2 — Slice Plan: Versioned List Documents, `ian serve` and the Read Endpoints

Splits [API.2](API_CONTRACT_AND_SLICE_PLAN.md#api2--ian-serve-and-the-read-endpoints) into two slices. The first makes
the two list documents versioned objects, so the API can serve them as they are, and writes this plan. The second adds
the local server and the read endpoints.

## 1. At a glance

- **What this plan does:**
  - API.2a wraps the runs-list and watchlist-list documents in a versioned object, in the CLI and in `schemas/`;
  - API.2b adds `ian serve`, the `api` unit and the read endpoints under `/v1`.
- **What it does not do:** add an action endpoint, change a stored shape, a formula or a classification, or write
  anything to the settings folder. No CLI output changes except the two `--json` list documents and their help text
  ([S3](#s3-the-list-documents-are-versioned-objects-2026-11-03)).
- **Rules both slices follow:**
  - one document has one shape, in the CLI and in the API: there is no API-only wrapper
    ([S3](#s3-the-list-documents-are-versioned-objects-2026-11-03));
  - inside `/v1` a change only adds ([S4](#s4-the-v1-additions-rule-2026-11-03));
  - the managed quality gate, with the Python 3.14 second pass, after each slice, and the project owner's approval
    before the next slice starts.
- **Where the history lives:** decisions S1 to S44 are in [Appendix A](#appendix-a-decision-records), approved by the
  project owner on 2026-11-03.

## 2. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| API.2a | [Versioned list documents and this plan](#api2a--versioned-list-documents) | Complete | 2026-11-03 |
| API.2b | [`ian serve` and the read endpoints](#api2b--ian-serve-and-the-read-endpoints) | Complete | 2026-11-04 |

## 3. The slices

### API.2a — Versioned list documents

- **Problem:** the runs-list and watchlist-list documents are top-level arrays, so a list-level field can never be
  added to either, and a client cannot tell which version of them it holds.
- **Decision:** both become versioned objects, in the CLI and in the API alike
  ([S3](#s3-the-list-documents-are-versioned-objects-2026-11-03)):
  - runs list: `{"schema_version": 1, "has_more": <bool>, "items": [...]}`, where `has_more` is found by reading one
    row past the page, not by a count query;
  - watchlist list: `{"schema_version": 1, "items": [...]}`, which is not paged and has no `has_more`;
  - the item documents are unchanged, and so is all text output.
- **Scope:**
  - `RunsListDocument` and `WatchlistListDocument`, their builders and `schemas/runs-list.schema.json` and
    `schemas/watchlist-list.schema.json`;
  - `list_runs` in `application`, which returns the page and `has_more`;
  - `ian runs list --json` and `ian watchlist list --json`, and their help text;
  - the API contract changes this plan needs, `docs/user/WORKSPACE.md`, and the `--json` section of
    `docs/user/USAGE.md`, which gains the additions rule ([S5](#s5-the-client-reference-is-docsuserapimd-2026-11-03));
  - this plan.
- **Branch:** `feat/api-list-documents`.
- **Detail:** [Implementation record](#31-api2a-implementation-record).

### API.2b — `ian serve` and the read endpoints

- **Problem:** a separate application cannot import the engine; it needs a stable, local, documented interface.
- **Decision:** a new unit, `api`, serves `/v1` with Starlette and uvicorn on loopback only, behind a per-launch bearer
  token and a `Host` check ([S6](#s6-205-is-settled-by-contract-rules-2026-11-03) to
  [S13](#s13-the-api-unit-and-uvicorn-logging-2026-11-03)). Every non-2xx body is a `FailureEnvelope`
  ([S14](#s14-errors-2026-11-03)). Endpoints use `method_id` and `watchlist_id`, not the CLI's aliases and names
  ([S15](#s15-endpoint-paths-and-names-2026-11-03)).
- **Scope:**
  - `ian serve` with `--port`, `--allow-origin` and `--database-url`, and its ready line;
  - the `api` unit at layer 9 and a `create_app(...)` factory; `cli` moves to layer 10; the table in
    [Architecture §13](../../../ARCHITECTURE.md#13-module-boundaries);
  - the endpoints of [S15](#s15-endpoint-paths-and-names-2026-11-03), the strategies document
    ([S16](#s16-the-strategies-document-2026-11-03)), the replay text document
    ([S17](#s17-the-replay-text-endpoint-returns-json-2026-11-03)) and the info document
    ([S18](#s18-the-info-document-2026-11-03));
  - a get-by-ID watchlist read operation in `application`, which the watchlist endpoint needs;
  - the new `FailureReasonCode` values `not_authenticated`, `host_not_allowed`, `origin_not_allowed` and
    `endpoint_not_found`, with the failure schema regenerated and the `parameters` field description changed to name the
    API's parameters ([S14](#s14-errors-2026-11-03));
  - `scripts/generate_openapi.py` and `schemas/openapi.json`, compared in the managed gate
    ([S20](#s20-openapi-31-generated-and-compared-2026-11-03));
  - `docs/user/API.md`, the client authors' reference, linking the additions rule in `docs/user/USAGE.md`
    ([S5](#s5-the-client-reference-is-docsuserapimd-2026-11-03));
  - the dependencies `starlette` and `uvicorn`, and `httpx` for tests, approved on 2026-10-30
    ([contract A.2](API_CONTRACT_AND_SLICE_PLAN.md#a2-api-shape-and-dependencies-2026-10-30)); `pyproject.toml` and
    `uv.lock` change only in this slice;
  - tests: every endpoint in process with no socket, an endpoint test parametrized over `STRATEGIES`, and the one
    socket test of [S21](#s21-one-socket-test-2026-11-03).
- **Branch:** `feat/api-serve-read`.
- **Detail:** [Implementation record](#32-api2b-implementation-record). This plan owns its decisions, S22 to S44 among
  them ([S22](#s22-this-plan-is-api2bs-slice-plan-2026-11-03)).

### 3.1 API.2a implementation record

What changed, by area:

- **`workspace_documents`:** `RunsListDocument` is a frozen `BaseModel` with `extra="forbid"` and the fields
  `schema_version: Literal[1] = 1`, `has_more` and `items`, in that order. `WatchlistListDocument` has
  `schema_version` and `items`. `build_runs_list_document(summaries, *, has_more)` sets `has_more`; the module
  docstrings no longer call the documents unversioned.
- **`workspace`:** a new frozen `RunPage` (`summaries`, `has_more`) beside `RunQuery`; `SQLiteAnalysisRunRepository.list`
  returns it.
- **`application`:** `list_runs` returns the repository's `RunPage` unchanged.
- **`cli_workspace.py`:** both `--json` branches write the new documents. The help texts are "Emit one JSON object
  holding a page of run summaries." and "Emit one JSON object holding the watchlist summaries." Text output is
  unchanged.
- **`schemas/`:** the two list schemas, regenerated.
- **Docs:** `docs/user/WORKSPACE.md` (both documents, with an example and the empty case) and `docs/user/USAGE.md` (the
  additions rule), and the API contract (sequence table, API.2 and API.3 entries, §1, §4 and the not-served list).

How `has_more` is read: `RunQuery` and its bounds (limit 1 to `RUN_QUERY_MAX_LIMIT`) are unchanged. The repository's
`list` reads `limit + 1` rows in its one query, returns the first `limit` as `summaries` and sets `has_more` when the
extra row came back. A caller asking for the maximum limit therefore reads 101 rows and gets a correct `has_more`. No
parameter selects this: a page always carries its flag, so no stored shape or public bound changes.

User-visible changes:

- `ian runs list --json` and `ian watchlist list --json` write a versioned object instead of an array, and their
  `--json` help text changed. The two schemas changed with them. A program that read the array reads `items`.

Tests edited, and why:

- Tests that pin the two documents or their output:
  - `tests/workspace_documents/test_watchlist_list_document.py` and
    `tests/workspace_documents/test_workspace_documents.py`: the documents are objects, not arrays, and their schemas
    are no longer described as unversioned;
  - `tests/_workspace_command_output.py` and the stored outputs under `tests/expected_output/workspace_commands/` for
    `runs-list-json`, `runs-list-json-timestamps`, `watchlist-list-empty-json`, `watchlist-list-json` and
    `watchlist-list-json-timestamps`, plus the new `runs-list-empty-json`: the scenario step that reads the first run
    reads `items`, and the stored outputs were regenerated;
  - `tests/application/test_runs.py`: `list_runs` returns a `RunPage`.
- Tests that call the repository's `list`, edited only to read `.summaries` from the returned page; no assertion
  changed: `tests/workspace/repositories/test_analysis_runs.py`, `tests/_strategy_document_output.py`,
  `tests/test_cli_momentum_statuses.py`, `tests/test_cli_save_run.py` and `tests/test_save_run_every_direct_command.py`.
- Tests that read the array of `runs list --json`, edited only to read `items`; no assertion about a run's content
  changed:
  - `tests/test_cli_refresh.py` (eight reads), `tests/test_cli_workspace.py` (two reads) and
    `tests/test_workspace_integration.py` (one read).
- No other test was edited.

New tests:

- `tests/workspace/repositories/test_analysis_runs.py`: `has_more` false on an empty store, on a short page and when the
  store holds exactly `limit` rows; true when exactly one more row exists; correct at the maximum limit, with and without
  an offset, and past the end; the page keeps the order and drops the extra row.
- `tests/application/test_runs.py`: `list_runs` passes the page and `has_more` through.
- `tests/workspace_documents/test_runs_list_document.py`: the empty-store output, key order, `has_more` through the
  command, and text output unchanged by the flag.
- Both empty outputs, key order of both documents and the schemas matching the models are covered in
  `tests/workspace_documents/` and by the scenario steps; the existing drift test compares the regenerated schemas.

Noticed for API.2b and later slices:

- The watchlist endpoint needs a get-by-ID operation in `application`; `get_watchlist` takes a name
  ([S15](#s15-endpoint-paths-and-names-2026-11-03)).
- Paging in the API is `limit` and `offset` with `has_more`; there is no total, and the maximum `limit` stays
  `RUN_QUERY_MAX_LIMIT`.
- `has_more` comes from the same single read as the page, so it is consistent with the page. A run saved between two
  page requests can still shift an offset page, as it does for `--offset` on the CLI; this is not changed.
- The failure schema regenerates in API.2b, because it gains reason codes and a changed field description. API.2a does
  not touch it.
- API.2b adds `starlette`, `uvicorn` and `httpx` to `pyproject.toml` and `uv.lock`, which `AGENTS.md` §3 allows only
  with explicit permission; the contract records it as approved on 2026-10-30, and the slice states it in its PR.
- API.2b closes [#205](https://github.com/PeterPontbriand/investment-analysis-engine/issues/205) in its PR.
  [#204](https://github.com/PeterPontbriand/investment-analysis-engine/issues/204) stays open for Step 3.5's shared
  definitions.

### 3.2 API.2b implementation record

What changed, by area:

- **`api` (new unit, layer 9):**
  - `routes.py` holds the route table ([S41](#s41-one-route-table-2026-11-03)): each route's method, path, parameters
    and the response model for each status code;
  - `app.py` holds `create_app(...)`, which builds the Starlette application from that table, with the request checks as
    its middleware and 404 and 405 answered as `endpoint_not_found` envelopes;
  - `checks.py` holds the request checks in the order of [S30](#s30-the-order-of-the-request-checks-2026-11-03) and the
    CORS headers of [S31](#s31-cors-headers-2026-11-03);
  - `handlers.py` holds the synchronous endpoint handlers, the parameter checks and the error mapping through the core
    classifier ([S40](#s40-synchronous-handlers-2026-11-03));
  - `responses.py` holds the one serializer ([S39](#s39-one-serializer-2026-11-03)) and the status table of
    [S14](#s14-errors-2026-11-03);
  - `documents.py` holds the info, strategies and replay-text documents ([S38](#s38-the-api-only-documents-2026-11-03));
  - `origins.py` holds the one parser of an origin ([S29](#s29---allow-origin-2026-11-03)).
  - `api` imports exactly [S12](#s12-the-api-unit-2026-11-03)'s list, and no `utils`, `h11` or loop-specific API.
- **`cli`:** `cli_serve.py` holds `ian serve` ([S25](#s25-the-socket-and-the-ready-line-2026-11-03),
  [S26](#s26-stopping-2026-11-03), [S27](#s27-launch-failures-2026-11-03)); `cli_database_target.py` holds the shared
  `--database-url` validation, which `cli_database.py` and `cli_serve.py` both call
  ([S28](#s28-the---database-url-validation-is-shared-2026-11-03)); `cli.py` registers the command. `cli` moves to layer
  10 and `api` is layer 9 in [Architecture §13](../../../ARCHITECTURE.md#13-module-boundaries).
- **`application`:** `build_run_query` and `RunQueryNames` check the runs-list parameters in the caller's spelling, and
  `declared_method_id` checks a `method_id` ([S33](#s33-one-check-of-the-runs-list-parameters-2026-11-03));
  `get_watchlist_by_id`, and `get_watchlist` renamed `get_watchlist_by_name`
  ([S36](#s36-watchlists-by-id-2026-11-03)). `cli_workspace.py` calls both and keeps its own `--analysis` alias resolution.
- **`core`, `reporting`:** the five codes in `core/failure_codes.py` ([S27](#s27-launch-failures-2026-11-03)); the failure
  envelope is version 11 with reworded descriptions ([S37](#s37-the-failure-envelope-is-version-11-2026-11-03)); the
  `strategy_document_json` docstring now says what the workspace documents are.
- **`schemas/`, `scripts/`:** `schemas/openapi.json` and `scripts/generate_openapi.py`, run in check mode by both gate
  wrappers; every schema that embeds the failure code list or the failure envelope regenerated.
- **Dependencies:** `starlette`, `uvicorn` and `httpx` in `dependencies` (`httpx` started in the `dev` group and moved
  in the review fixes), `httpx2` in the `dev` group; `uv.lock` updated. The
  permission of 2026-10-30 ([contract A.2](API_CONTRACT_AND_SLICE_PLAN.md#a2-api-shape-and-dependencies-2026-10-30)) is
  stated in the pull request.
- **Docs:** `docs/user/API.md` (new) and its entry in `docs/user/README.md`; `docs/user/USAGE.md` (the failure document's
  version and the headers sentence of [S43](#s43-response-headers-are-not-part-of-the-contract-2026-11-03)); Architecture
  §13 and its read-operations paragraph; this plan and the contract's sequence tables and API.4 open question; the
  `SWC_6C_STRATEGY_PINS_PLAN.md` row for SWC.7b, set to Complete on 2026-10-19 as the SWC contract records it.

Deviations from the decisions as written:

- **S33 needed `application` to import `analysis`.** The status check builds a `RunOutcome`, which `analysis` defines, so
  Architecture §13 now lists `analysis` among `application`'s imports. The project owner approved this on 2026-11-03;
  `application` stays at layer 8.
- **S36 adds a by-ID read to the watchlist repository.** `SQLiteWatchlistRepository.get_by_id` (an edit outside the listed
  scope, approved on 2026-11-04) reads a watchlist by ID in one transaction; the first implementation, which found the
  name in the list and then read by name, was replaced (see the review fixes below).
- **One edit outside the listed scope.** `scripts/strategy_conformance.py` lists `serve` in `NON_STRATEGY_COMMANDS`,
  because test T7 requires every top-level command to be a strategy alias, a group or a listed non-strategy command. The
  project owner approved it on 2026-11-03.
- **The shared refresh-ID message.** The first implementation reused the CLI's message, which names `runs list` and
  `refresh`, because the CLI's messages could not change ([S33](#s33-one-check-of-the-runs-list-parameters-2026-11-03)).
  The review fixes replaced it with one client-neutral message (F8 below).
- **Ordering inside S30.** A request that fails the `Host` check is answered without CORS headers, because the origin has
  not been judged yet. (The first implementation also treated every `OPTIONS` request from an allowed origin as a
  preflight; F5 below limits that to one that carries `Access-Control-Request-Method`.)

User-visible changes:

- A new command, `ian serve`, with `--port`, `--allow-origin` and `--database-url`, and its help text.
- Five new failure reason codes, and `schema_version` 11 of the failure document. A program that dispatches on the
  version reads the new value; no field was removed or retyped.
- `schemas/failure.schema.json` and every schema that embeds the failure code list changed with it.
- The review fixes changed two messages: a malformed `--refresh-id` of `runs list` and a malformed `REFRESH_ID` of
  `runs compare` now read "<name> '<value>' is not a valid refresh ID." (`parameters` and exit codes are unchanged).
- No other CLI output, message or exit code changed.

Tests edited, and why:

- Patch targets that moved with the `--database-url` validation ([S28](#s28-the---database-url-validation-is-shared-2026-11-03)):
  `tests/test_cli_database.py`, `tests/test_cli_database_readiness.py`, `tests/test_command_validation_failures.py` and
  `tests/_workspace_command_output.py` patch `settings` and `is_windows` in `cli_database_target`, where they are now read.
  No assertion changed.
- `tests/application/test_watchlists.py`: `get_watchlist` is `get_watchlist_by_name` ([S36](#s36-watchlists-by-id-2026-11-03)).
- Tests that pin the failure document's version ([S37](#s37-the-failure-envelope-is-version-11-2026-11-03)):
  `tests/reporting/test_failure_envelope.py` (the version, one pinned document and the name of the version test),
  `tests/test_cli_failure_envelope.py`, `tests/test_command_validation_failures.py`,
  `tests/test_existing_strategy_failure_output.py` and `tests/test_cli_database_readiness.py` read 11. Their strategy
  and database-report versions are unchanged.
- `tests/reporting/test_failure_envelope.py`: the test that every code can be returned lists the five codes that are
  written directly, because no exception declares them.
- `tests/scripts/test_generate_schemas.py`: the file-set check ignores `openapi.json`, which has its own generator.
- `tests/specimen/specimen-test.schema.json`: regenerated, because it embeds the failure code list.
- `tests/test_strategy_import_layering.py`: `api.documents` and `api.routes` join the listed importers of the composition
  root, as [S12](#s12-the-api-unit-2026-11-03) allows `api` to import `strategy_wiring`.
- `tests/_cli_help_output.py` and `tests/test_cli_help_output.py`: `serve` is a help target and appears in the documented
  command order; `tests/expected_output/cli_help/application.txt` gains its line and `serve.txt` is new.
- No other test was edited.

New tests:

- `tests/api/test_request_checks.py`: the Host check, the Origin check, the preflight, the token, and each in order,
  including 401 for an unknown path without a token and 404 or 405 only with one; the CORS headers.
- `tests/api/test_endpoints.py`: every endpoint in process, an empty store, missing resources, and a test parametrized over
  `STRATEGIES` reading a saved run of each strategy through `/v1/runs/{analysis_run_id}` and `/text` in each mode, compared
  with the command line.
- `tests/api/test_parameters.py`: each case of [S34](#s34-parameters-that-are-rejected-2026-11-03), the defaults and the
  missing `mode` of [S35](#s35-defaults-and-the-required-mode-2026-11-03), and the runs-list checks in API spelling.
- `tests/api/test_errors.py`: every reason code reaching its status, the fixed `execution_error` with its traceback in the
  log and no token in it, and a database that is not ready.
- `tests/api/test_routes_and_description.py`: the application serves exactly the route table; `schemas/openapi.json` is
  current and the check fails when it is stale or missing; the origin parser.
- `tests/test_cli_serve.py`: each launch failure of [S27](#s27-launch-failures-2026-11-03), with `port_unavailable` from a
  socket the test holds, the [S29](#s29---allow-origin-2026-11-03) cases, and the one socket test of
  [S21](#s21-one-socket-test-2026-11-03).
- `tests/application/test_watchlists.py`: both watchlist reads and the not-found message.- The CLI's runs-list checks are covered by the existing `tests/test_command_validation_failures.py` cases, which pass
  unchanged except the refresh-ID message (see the review fixes).

Noticed for later slices:

- Ctrl+C shutdown is not covered by a test: the socket test stops the process by closing standard input, which is the
  documented way, and sending an interrupt to a child is not portable on Windows.
- `ian serve` initializes a proven-empty database at launch, as every other command does on first use
  (`ensure_database_ready`); it does not migrate an older one.
- API.4's slice plan must decide whether two `ian serve` processes may run refresh jobs and writes against one database
  ([contract](API_CONTRACT_AND_SLICE_PLAN.md#api4--action-endpoints-and-refresh-jobs)).

Review fixes (2026-11-04):

The project owner reviewed the branch and approved these fixes on 2026-11-04. They are decided and done.

- **F1, watchlist by ID.** `SQLiteWatchlistRepository.get_by_id(watchlist_id)` reads the watchlist in one read
  transaction through `_load`, and returns `None` when no watchlist has that ID. `get_watchlist_by_id` calls it; the
  list-then-name workaround is gone. The not-found message is unchanged. Repository tests cover found and not found.
- **F2, engine version.** `engine_version` is the installed version of the `investment-analysis-engine` distribution,
  read with `importlib.metadata.version` once, when the app is created; there is no fallback constant.
  `ProjectSettings.version` is deleted. Its other readers were `scripts/generate_openapi.py`, which now takes
  `info.version` from the same source (and `schemas/openapi.json` was regenerated), and `tests/test_settings_environment.py`,
  which dropped its `version` assertion in `test_unprefixed_names_are_not_read`. The info test compares the value with
  `importlib.metadata.version`. The prompt's assumption that `ProjectSettings.version` had no other reader was wrong;
  the project owner approved the corrected scope.
- **F2a, the other identity constants.** `ProjectSettings.environment` and `ProjectSettings.encoding` had no reader but
  `test_application_identity_is_constant`, so all three class constants and the `ClassVar` import are deleted, and that
  test with them. `IAN_VERSION` still fails closed, and `VERSION` is still not read.
- **F3, withdrawn.** `RouteSpec.method` stays, because API.4's action endpoints need methods other than `GET`; F4 uses it.
- **F4, undeclared methods.** The app serves exactly the method each route declares. A request with any other method,
  `HEAD` included (which Starlette otherwise adds to every `GET` route), is answered 405 `endpoint_not_found` with an
  `Allow` header naming the declared method. The route-table test now compares the served methods with the table without
  excluding `HEAD`.
- **F5, preflight.** Only an `OPTIONS` request from an allowed origin that carries `Access-Control-Request-Method` is a
  preflight. Any other `OPTIONS` request passes the token check and then routing (405 on a known path, 404 on an unknown
  one). This corrects the "Ordering inside S30" deviation above.
- **F6, errors outside a handler.** An application-level handler for any exception answers one raised outside an endpoint
  handler (in the request checks, for example) with the fixed-message `execution_error` envelope, status 500; the
  traceback goes to the log and the token never does.
- **F7, dependencies.** `httpx` moved from the `dev` group to `dependencies`, with the same lower bound, because
  production code imports it (inside the 2026-10-30 permission). `httpx2>=2.16.0` was added to the `dev` group
  (permission of 2026-11-04), so Starlette's test client no longer takes the deprecated `httpx` path; the test run shows
  no `StarletteDeprecationWarning`. `uv.lock` also gained `httpx2`'s own requirements: `httpcore2`, `httpx2-jsfetch` and
  `truststore`.
- **F8, refresh-ID messages.** Every malformed refresh ID reads "<name> '<value>' is not a valid refresh ID." with the
  caller's spelling: `--refresh-id` (`runs list`), `REFRESH_ID` (`runs compare`), `refresh_id` (the `GET /v1/runs` query
  and the `/v1/refreshes/{refresh_id}/compare` path). The two CLI messages changed; `parameters` and exit codes did not.
  `RUN_ID` on `runs show` keeps its message. The API's other path IDs name their kind: "analysis_run_id '<value>' is not
  a valid Analysis Run ID." and "watchlist_id '<value>' is not a valid watchlist ID."
- **Approved edits outside the listed scope:** `workspace/repositories/watchlists.py` (F1), `config/__init__.py`,
  `scripts/generate_openapi.py`, `schemas/openapi.json` and `tests/test_settings_environment.py` (F2, F2a).
- **Tests edited or added:** `tests/api/test_endpoints.py` (the info version), `tests/api/test_parameters.py` (the
  path-ID and refresh-ID messages), `tests/api/test_request_checks.py` (preflight, `HEAD` and other methods, an exception
  outside a handler),
  `tests/api/test_routes_and_description.py` (served methods without `HEAD`), `tests/test_command_validation_failures.py`,
  `tests/test_cli_workspace.py` and `tests/test_cli_runs_compare.py` (the refresh-ID messages),
  `tests/test_settings_environment.py` (the deleted assertions and test), and
  `tests/workspace/repositories/test_watchlist_repository.py` (`get_by_id`).

## 4. Scope limits and acceptance criteria

- API.2a changes no CLI output except the two `--json` list documents and their help texts: every text output, every
  other document and every other help text stays as it is.
- No stored shape, formula or classification changes, and `RunQuery`'s public bounds stay as they are.
- Each list document has `schema_version` 1, rejects unknown keys, and its published schema matches its model.
- `has_more` is true if and only if a row follows the page for the same filters and offset.
- API.2b adds no endpoint outside [S15](#s15-endpoint-paths-and-names-2026-11-03) and no write operation.
- API.2b serves loopback only. A request without the token, with another `Host`, or from a disallowed origin gets the
  failure of [S14](#s14-errors-2026-11-03).
- Endpoint tests run in process and open no socket, except the one test of
  [S21](#s21-one-socket-test-2026-11-03).
- `schemas/openapi.json` is regenerated and compared in the managed gate.

## 5. Background

The API serves the documents the CLI prints. Two of them, the runs list and the watchlist list, were top-level arrays,
which cannot carry a version or a list-level field. Wrapping them once, in both the CLI and the API, keeps one shape
per document and lets later additions such as `has_more` (and, if a count is ever needed, `total`) arrive without a
`/v2`.

[Issue 204](https://github.com/PeterPontbriand/investment-analysis-engine/issues/204) is a worked example of the
additions rule, not the issue that decides it: a staleness warning code is an addition, and a changed classification for
new runs is a method change under its `method_version`, which is also allowed
([S2](#s2-issue-204-is-an-example-of-the-additions-rule-2026-11-03),
[S4](#s4-the-v1-additions-rule-2026-11-03)). Authentication is
[issue 205](https://github.com/PeterPontbriand/investment-analysis-engine/issues/205)
([S6](#s6-205-is-settled-by-contract-rules-2026-11-03)).

## Appendix A: Decision records

S1 to S44 were approved by the project owner on 2026-11-03. S22 to S44 were approved after the API.2a merge, for API.2b;
where one differs from S1 to S21 it says so, and the later decision wins.

### S1 API.2 is split (2026-11-03)

API.2a wraps the runs-list and watchlist-list documents in the CLI and in `schemas/`, and writes this plan. API.2b adds
`ian serve` and the read endpoints. This plan, `API_2_SLICE_PLAN.md`, is committed in API.2a's PR.

### S2 Issue 204 is an example of the additions rule (2026-11-03)

Issue #204 ("Warn when a run's anchor annual filing is stale") is not the additions-rule issue. The contract's API.2
entry cites only #205, for authentication. This plan uses #204 as a worked example of
[S4](#s4-the-v1-additions-rule-2026-11-03): a staleness warning code is an addition; a changed classification for new
runs is a method change under its `method_version`, also allowed. #204 stays open for Step 3.5's shared definitions.

### S3 The list documents are versioned objects (2026-11-03)

Both top-level arrays become versioned objects, in the CLI and in the API alike: one document each, no API-only wrapper.
The contract's rule that existing CLI output stays as it is is amended for exactly these two documents. The runs list
carries `has_more`, computed by reading one row past the page, not `total`, which needs a second count query. The
watchlist list is not paged and has no `has_more`. Key order and shapes:

```text
runs list:      {"schema_version": 1, "has_more": <bool>, "items": [<RunSummaryDocument>, ...]}
watchlist list: {"schema_version": 1, "items": [<WatchlistSummaryDocument>, ...]}
```

Empty stores print `{"schema_version": 1, "has_more": false, "items": []}` and `{"schema_version": 1, "items": []}`. The
item documents are unchanged.

### S4 The /v1 additions rule (2026-11-03)

The rule applies to every published document, CLI `--json` included.

- **Additions, allowed within `/v1`:**
  - a new endpoint or optional request parameter;
  - a new document field;
  - a new value of an open vocabulary: `status`, run outcome, calculation status, `reason_code`, warning code or
    `method_id`;
  - a new strategy;
  - a `schema_version` increase made only for an addition;
  - a changed calculation for new runs under its `method_version`.
- **Breaking, which need a new version path (`/v2`):**
  - removing, renaming or retyping a field;
  - a nullable field becoming non-null, or the reverse;
  - changing what an existing value means;
  - a new required request parameter, or a changed default;
  - a different HTTP status for an existing condition.
- Clients must tolerate unknown fields, unknown values and a higher `schema_version`. Published schemas stay exact
  (constant versions, `additionalProperties` false) and describe this engine version; clients must not validate strictly
  against them.
- Response headers are outside the rule: [S43](#s43-response-headers-are-not-part-of-the-contract-2026-11-03).
- **Amendment (2026-11-13, [A.7](API_CONTRACT_AND_SLICE_PLAN.md#a7-structured-units-run-overview-and-command-free-database-messages-2026-11-13), U2):**
  the rule applies from the first engine release that includes the API. Until then an incompatible change inside `/v1`,
  CLI `--json` included, is allowed when the slice that makes it records it and raises the affected document's
  `schema_version`.

### S5 The client reference is docs/user/API.md (2026-11-03)

The client authors' reference is a new `docs/user/API.md`, written in API.2b. It covers `ian serve`, the handshake,
authentication, errors and the [S4](#s4-the-v1-additions-rule-2026-11-03) rule, and is listed with the documents API.5
does not serve. Because S4 covers CLI documents too and API.2a ships first, API.2a writes the rule into the JSON-output
section of `docs/user/USAGE.md`, and API.2b's `API.md` links to it.

### S6 205 is settled by contract rules (2026-11-03)

[#205](https://github.com/PeterPontbriand/investment-analysis-engine/issues/205) is settled by contract rules, not by an
authenticator abstraction:

- the credential travels only in `Authorization: Bearer`, never in a path, query string or body;
- a 401 carries `WWW-Authenticate: Bearer`, so another sign-in method is another challenge, which is an addition;
- no v1 endpoint or document describes the token or the caller, and a later caller identity becomes a new
  `ApplicationContext` field plus optional document fields;
- the `Host` check belongs to the loopback binding, and a remote binding brings its own host rules.

#205 is closed by API.2b's PR.

### S7 The token and the ready line (2026-11-03)

The engine generates the token on each launch. `--port` defaults to 0, so the operating system chooses. Once listening,
`ian serve` writes one JSON line to standard output, `{"port": <int>, "token": "<token>"}`, and nothing to disk. The
token never appears in a log.

### S8 The Host check (2026-11-03)

The `Host` header must be exactly `127.0.0.1:<port>` or `localhost:<port>`.

### S9 CORS (2026-11-03)

`--allow-origin` is repeatable and empty by default. A preflight `OPTIONS` is answered without the token only for an
allowed origin; a request whose `Origin` is not allowed is rejected. The GUI passes its own origins at launch.

### S10 Shutdown (2026-11-03)

`ian serve` exits when its standard input closes or on Ctrl+C. There is no shutdown endpoint.

### S11 Launch and the application context (2026-11-03)

`ian serve` has the options `--port`, `--allow-origin` and `--database-url` (as `ian db status` and `ian db upgrade` have
it; [S28](#s28-the---database-url-validation-is-shared-2026-11-03)). Settings
are read once at launch into one `ApplicationContext`. Database readiness is checked at launch as well as per operation;
a database that is not ready fails the launch with the failure envelope on standard output and exit 1.

### S12 The api unit (2026-11-03)

A new unit `api` at layer 9 imports `application`, `workspace_documents`, `reporting`, `strategy_wiring`, `config` and
`core`. `cli` imports `api` for `ian serve` and moves to layer 10. The app is built by a `create_app(...)` factory that
tests call directly.

### S13 The api unit and uvicorn logging (2026-11-03)

uvicorn's loggers go to the project's file log. The access log is off.

### S14 Errors (2026-11-03)

- Every non-2xx body is a `FailureEnvelope`; clients branch on `reason_code`, and the HTTP status is coarse.
- New `FailureReasonCode` values: `not_authenticated`, `host_not_allowed`, `origin_not_allowed`, `endpoint_not_found`
  (404 and 405).
- `parameters` names the API's query and path parameter names, which is a field-description change, not a shape change.
- An unexpected exception is a fixed-message `execution_error` with the traceback in the log.
- Extended by [J12](API_4_SLICE_PLAN.md#j12-failure-statuses-2026-11-06): the action endpoints add 409 and a 404.

| HTTP status | Reason codes |
| :--- | :--- |
| 400 | `invalid_parameter`, `host_not_allowed`, `origin_not_allowed` |
| 401 | `not_authenticated` |
| 404 | `analysis_run_not_found`, `watchlist_not_found`, `endpoint_not_found` |
| 503 | `database_busy` |
| 500 | everything else |

### S15 Endpoint paths and names (2026-11-03)

Paths and filters use `method_id`, not the CLI alias. Watchlists are addressed by `watchlist_id`, which needs a get-by-ID
read operation in `application`. Query parameters are named after document fields.

| Path | Notes |
| :--- | :--- |
| `GET /v1/info` | [S18](#s18-the-info-document-2026-11-03) |
| `GET /v1/strategies` | [S16](#s16-the-strategies-document-2026-11-03) |
| `GET /v1/watchlists` | the watchlist-list document |
| `GET /v1/watchlists/{watchlist_id}` | the watchlist document |
| `GET /v1/runs?ticker&method_id&status&refresh_id&limit&offset` | the runs-list document |
| `GET /v1/runs/{analysis_run_id}` | the strategy's document |
| `GET /v1/runs/{analysis_run_id}/text?mode=concise\|details\|diagnostics` | [S17](#s17-the-replay-text-endpoint-returns-json-2026-11-03) |
| `GET /v1/refreshes/{refresh_id}/compare` | the runs-compare document |

### S16 The strategies document (2026-11-03)

A new strategies document: `schema_version`, and per strategy `analysis`, `method` and `label`. It has no
supported-modes field: every strategy supports all three text modes, so it could hold only one value.

### S17 The replay text endpoint returns JSON (2026-11-03)

The replay text endpoint returns JSON (`schema_version`, `mode`, `text`), not `text/plain`.

### S18 The info document (2026-11-03)

`/v1/info` is `{"schema_version": 1, "api_versions": ["v1"], "engine_version": "<package version>",
"sec_identity_configured": <bool>}`. It lists the served versions, not a single `api_version` that is always 1 under
`/v1`, and never holds the SEC identity's value.

### S19 The selection-model schema moves to API.3 (2026-11-03)

The selection-model JSON Schema moves from API.2 to API.3, with API.3's conformance check that every selection field has a
description and a form-supported type.

### S20 OpenAPI 3.1 generated and compared (2026-11-03)

OpenAPI 3.1, generated by `scripts/generate_openapi.py` into `schemas/openapi.json`, with each response declared per
status code and compared in the gate. It is not served at runtime.

### S21 One socket test (2026-11-03)

One test opens a socket: it starts `ian serve` on loopback port 0, reads the ready line, makes one authenticated request,
closes standard input and checks that the process exits. Every endpoint test stays in process with no socket. If it hits
`WinError 10055`, that is a new occurrence for issue #116.

### S22 This plan is API.2b's slice plan (2026-11-03)

This document is API.2b's slice plan; there is no separate one. S22 to S44 are recorded here, and
[§3.2](#32-api2b-implementation-record) records what API.2b did. Both sequence tables, this one and the contract's, show
API.2a as Complete on 2026-11-03 and API.2b as Next; API.2b becomes Complete only after it merges.

### S23 API.2b is one slice (2026-11-03)

API.2b is not split further.

### S24 Dependencies (2026-11-03)

Plain `uvicorn` (no `[standard]` extras) and `starlette` are runtime dependencies, and `httpx` is a development and test
dependency. uvicorn's `loop` and `http` settings stay at their default, `auto`. Nothing in `api` imports `h11`, a
loop-specific `asyncio` API or anything else that depends on the plain stack, so moving to `uvicorn[standard]` later is a
dependency change only. The permission to edit `pyproject.toml` and `uv.lock` for exactly these three was given on
2026-10-30 ([contract A.2](API_CONTRACT_AND_SLICE_PLAN.md#a2-api-shape-and-dependencies-2026-10-30)); API.2b's pull
request states it. No other dependency is added.

### S25 The socket and the ready line (2026-11-03)

`ian serve` binds its own socket on `127.0.0.1` at `--port` (default 0), reads the actual port from the socket and hands
the socket to uvicorn. It writes the ready line of [S7](#s7-the-token-and-the-ready-line-2026-11-03) only after uvicorn
reports that startup is complete. There is one process, no workers and no reload, and `server_header` is off.

### S26 Stopping (2026-11-03)

A thread watching standard input asks uvicorn to stop when standard input reaches end of file. A request in flight gets a
5 second graceful timeout. The exit code is 0 after standard input closes and after Ctrl+C.

### S27 Launch failures (2026-11-03)

Every launch failure writes the failure envelope to standard output and exits 1:

- a `--port` outside 0 to 65535, or a malformed `--allow-origin`, is `invalid_parameter`, and `parameters` names the
  option;
- a database that is not ready is its `database_*` code ([S11](#s11-launch-and-the-application-context-2026-11-03));
- a bind failure, whether the port is in use or not permitted, is the new code `port_unavailable`.

The new codes are therefore `not_authenticated`, `host_not_allowed`, `origin_not_allowed`, `endpoint_not_found` and
`port_unavailable`, all with status `error`. This amends [S14](#s14-errors-2026-11-03), which listed the first four.
`port_unavailable` occurs only at launch, so it has no HTTP status.

### S28 The `--database-url` validation is shared (2026-11-03)

`--database-url` on `ian serve` is validated exactly as `ian db status` validates it, including the anchoring of a
relative path and the rejection of an in-memory target. That validation moves out of `cli_database.py` into one helper
that both commands call, and `ian db` behaviour and output do not change.
[S11](#s11-launch-and-the-application-context-2026-11-03) is corrected: the option matches `ian db status` and
`ian db upgrade`, not the workspace commands.

### S29 `--allow-origin` (2026-11-03)

`--allow-origin` accepts exactly `scheme://host` or `scheme://host:port`, with any scheme (so `tauri://localhost` and
`http://tauri.localhost` work), no path and no trailing slash. `*` and `null` are rejected as `invalid_parameter`.
Comparison with a request's `Origin` is exact after lower-casing the scheme and the host.

### S30 The order of the request checks (2026-11-03)

Request checks run in this order: the `Host` header ([S8](#s8-the-host-check-2026-11-03)), then `Origin`
([S9](#s9-cors-2026-11-03)), then a preflight answer for an allowed origin, then the bearer token, then routing. Without a
valid token every path, including an unknown one, gets 401 `not_authenticated`; `endpoint_not_found` (404 or 405) is
returned only to an authenticated caller. The token is `secrets.token_urlsafe(32)` and is compared with
`secrets.compare_digest`.

### S31 CORS headers (2026-11-03)

For an allowed origin, responses carry `Access-Control-Allow-Origin` with that origin echoed, and `Vary: Origin`. A
preflight answer allows method `GET` only and header `Authorization` only, with `Access-Control-Max-Age: 600`.
`Access-Control-Expose-Headers: WWW-Authenticate` is set, and `Access-Control-Allow-Credentials` never is. A request with no
`Origin` header passes the origin check.

Amended by [J6](API_4_SLICE_PLAN.md#j6-cors-allows-the-declared-methods-2026-11-06): a preflight allows the methods the route table declares and `Content-Type`.

### S32 Path parameters are named after document fields (2026-11-03)

The paths are `/v1/runs/{analysis_run_id}`, `/v1/runs/{analysis_run_id}/text`, `/v1/watchlists/{watchlist_id}` and
`/v1/refreshes/{refresh_id}/compare`. This amends the table of [S15](#s15-endpoint-paths-and-names-2026-11-03), which is
updated to match.

### S33 One check of the runs-list parameters (2026-11-03)

The runs-list parameter checks (an empty ticker, ticker normalization, the method, the status, the refresh ID, and the
limit and offset bounds) move out of `cli_workspace.py` into one function in `application`. It takes the raw values and the
caller's spelling of each parameter, and returns a `RunQuery` or raises `InvalidParameterError` whose message and
`parameters` use the caller's spelling. The CLI passes `--ticker`, `--analysis`, `--status`, `--refresh-id`, `--limit` and
`--offset`, and keeps resolving `--analysis` aliases to a method ID; the API passes `ticker`, `method_id`, `status`,
`refresh_id`, `limit` and `offset`. CLI messages, exit codes and output do not change. As a result `api` imports exactly
[S12](#s12-the-api-unit-2026-11-03)'s list.

The function turns `status` into a `RunOutcome`, which is defined in `analysis`. `application` therefore imports `analysis`,
an import the Architecture §13 table did not list. The project owner approved the new edge on 2026-11-03: `application`
imports `RunOutcome` from `investment_analysis_engine.analysis.run_models`, its defining module, and stays at layer 8.

### S34 Parameters that are rejected (2026-11-03)

Each of these is `invalid_parameter` (400) and names the parameter: an unknown `method_id`; an unknown query parameter name;
a query parameter given more than once; a malformed UUID in a path (not 404).

### S35 Defaults and the required mode (2026-11-03)

On `GET /v1/runs`, `limit` defaults to 20 and `offset` to 0, as on the CLI. On `GET /v1/runs/{analysis_run_id}/text`, `mode`
is required, with no default.

### S36 Watchlists by ID (2026-11-03)

`application/watchlists.py` gains `get_watchlist_by_id(context, watchlist_id)`, and `get_watchlist` is renamed
`get_watchlist_by_name`, with every caller updated. A missing ID raises `WatchlistNotFoundError` with the message
"No watchlist with ID <id> exists."

### S37 The failure envelope is version 11 (2026-11-03)

`FailureEnvelope.schema_version` goes from 10 to 11. Its docstrings and the descriptions of `analysis`, `method`, `ticker`
and `parameters` are reworded to cover an API response as well as a command: `parameters` names an option by its long
spelling, a command argument by its upper-case name, or an API query or path parameter by its name.
`schemas/failure.schema.json` is regenerated, and the version is updated wherever the docs state it.

### S38 The API-only documents (2026-11-03)

The info ([S18](#s18-the-info-document-2026-11-03)), strategies ([S16](#s16-the-strategies-document-2026-11-03)) and
replay-text ([S17](#s17-the-replay-text-endpoint-returns-json-2026-11-03)) document models live in `api` and are built
there. They are published only as components of `schemas/openapi.json`, not as separate `schemas/*.schema.json` files.

### S39 One serializer (2026-11-03)

Every API response body, success or failure, uses one serializer: `model_dump(mode="json")` in field order, compact,
UTF-8, `allow_nan=False`, with `Content-Type: application/json` and `Cache-Control: no-store`. Document shapes are the
CLI's; the CLI's whitespace and key order are not carried over. Tests compare parsed JSON, not text.

### S40 Synchronous handlers (2026-11-03)

Endpoint handlers are synchronous (`def`) and run in Starlette's thread pool. Each operation opens its own connection, as
the `application` operations already do.

Extended by [J26](API_4_SLICE_PLAN.md#j26-plan-records-2026-11-06): a route with a body reads it in one asynchronous step and runs its operation in the thread pool.

### S41 One route table (2026-11-03)

One declared route table in `api` lists each route's method, path, parameters and response model for each status code.
`create_app(...)` and `scripts/generate_openapi.py` both read it, and a test checks that the application serves exactly the
routes in the table. `scripts/generate_openapi.py` follows `scripts/generate_schemas.py`: a write mode, and a check mode
that fails when `schemas/openapi.json` is missing or out of date. Both gate wrappers run the check.

### S42 Logging (2026-11-03)

`ian serve` sets up the project's file logging as the other commands do. uvicorn gets `log_config=None`, so its loggers
propagate to the file log, and `access_log=False`. `api` configures no logging and imports no `utils`. An unexpected
exception is logged with its traceback and answered with the fixed-message `execution_error` of
[S14](#s14-errors-2026-11-03). The token never appears in any log.

### S43 Response headers are not part of the contract (2026-11-03)

Response headers are not part of the contract, except `Content-Type` and `WWW-Authenticate`; they may change within `/v1`.
This is added to the additions rule in `docs/user/USAGE.md` and to `docs/user/API.md`, and is cross-referenced from
[S4](#s4-the-v1-additions-rule-2026-11-03).

### S44 No client is named in the API reference (2026-11-03)

No path, field, document, reason code or text in `docs/user/API.md` names a particular client. It speaks of "a client", and
notes that a client must load its pages from an origin other than `null` (for example a custom scheme or `localhost`),
because `null` is never allowed. Plan text may still say the desktop application is the first client.
