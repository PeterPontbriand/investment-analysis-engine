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
- **Where the history lives:** decisions S1 to S21 are in [Appendix A](#appendix-a-decision-records), approved by the
  project owner on 2026-11-03.

## 2. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| API.2a | [Versioned list documents and this plan](#api2a--versioned-list-documents) | Next | |
| API.2b | [`ian serve` and the read endpoints](#api2b--ian-serve-and-the-read-endpoints) | Planned | |

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
- **Detail:** ⚠ no slice plan yet. This plan owns its decisions; the slice plan of API.2b is written at the start of that
  slice.

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

S1 to S21 were approved by the project owner on 2026-11-03.

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

`ian serve` has the options `--port`, `--allow-origin` and `--database-url` (as the workspace commands have). Settings
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
| `GET /v1/runs/{run_id}` | the strategy's document |
| `GET /v1/runs/{run_id}/text?mode=concise\|details\|diagnostics` | [S17](#s17-the-replay-text-endpoint-returns-json-2026-11-03) |
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
