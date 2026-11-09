# API.1 — Slice Plan: Replay Documents and the Application Layer (Reading)

Splits [API.1](API_CONTRACT_AND_SLICE_PLAN.md#api1a--replay-document-projection) into two slices. The first makes a
stored run's JSON projection a typed document. The second adds the `application` unit and switches the read commands
to it.

## 1. At a glance

- **What this plan does:**
  - API.1a gives a stored run a document projection, so a caller gets the strategy's typed `--json` document
    instead of a string;
  - API.1b adds the `application` unit, with one plain function per read operation, and switches the CLI's read
    commands to it.
- **What it does not do:** add an endpoint, change a stored shape, an existing `schemas/` file, a formula or any
  existing CLI output, or move an action command. The one new CLI output is `ian watchlist list --json`
  ([A10](#a10-a-watchlist-list-document-and---json-2026-11-01), [A16](#a16-the-watchlist-list-document-2026-11-02)),
  and the one new `schemas/` file is `watchlist-list.schema.json`.
- **Rules both slices follow:**
  - a strategy declares its replay behavior through its descriptor, and generic code stays strategy-free
    (`AGENTS.md` §3 and §9);
  - existing CLI tests pass without edits;
  - the managed quality gate, with the Python 3.14 second pass, after each slice, and the project owner's approval
    before the next slice starts.
- **Where the history lives:** decisions A1 to A15 are in [Appendix A](#appendix-a-decision-records), approved by the
  project owner on 2026-11-01, and A16 to A23, approved on 2026-11-02.

## 2. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| API.1a | [Replay document projection](#api1a--replay-document-projection) | Complete | 2026-11-01 |
| API.1b | [Application layer: reading](#api1b--application-layer-reading) | Complete | 2026-11-02 |

## 3. The slices

### API.1a — Replay document projection

- **Problem:** every replay projector returns `str`. In the JSON mode the presenter builds the typed document inside
  the projector and serializes it, so the API would have to parse text it could have received as a model.
- **Decision:** a replay has two projections ([A8](#a8-a-stored-runs-json-projection-is-a-typed-document-2026-11-01)):
  - the text projection renders the concise, details and diagnostics modes and returns `str`. Its options carry
    `TextPresentationMode`, a `Literal` of those three members of the existing `PresentationMode`, so the JSON mode
    is a type error and no new enum or change to the direct commands is needed;
  - the document projection returns the strategy's `--json` document model. Serializing it with
    `strategy_document_json` happens only at the edge: the direct command's JSON branch and `ian runs show --json`.
- **Scope:**
  - each presenter's public `<module>_document` builder is called by its JSON branch and by the strategy's
    `project_<module>_document`, and a replay passes no provider check;
  - the descriptor's behavior bundle gains `document` and the erased view `document_for`, with
    `documents_by_key` and `DOCUMENTS_BY_KEY`;
  - `workspace_documents/run_replay.py` gains `project_run_document` beside `project_run`, sharing the version check,
    the lookup and the decode;
  - `ian runs show --json` serializes the document projection; text modes call the text projection;
  - `scripts/new_strategy.py`, its two templates, the presenter and replay fills and `scripts/strategy_sites.toml`,
    so a generated strategy gets both projections.
- **Branch:** `feat/api-replay-documents`.
- **Detail:** [Implementation record](#31-api1a-implementation-record).

### API.1b — Application layer: reading

- **Problem:** each Typer command in `cli_workspace.py` parses, composes, works and prints in one function and fails
  through `typer.Exit`, and production composition lives in `cli`, so nothing else can reuse it.
- **Decision:** a new unit, `application`, owns the read operations
  ([A2](#a2-the-application-package-2026-11-01) to [A7](#a7-operations-return-domain-objects-and-documents-2026-11-01)).
  It returns domain objects and documents, raises typed failures that carry a `FailureReasonCode`, and knows no
  presentation and no strategy.
- **Scope:**
  - `application/database.py`, `watchlists.py` and `runs.py`, with the operations of watchlist list and show, runs
    list, show and compare;
  - the new `AnalysisRunNotFoundError`, `reason_code` on `DuplicateRefreshRunsError`, and `InvalidStoredRunError`
    raised from a repository `ValueError` ([A6](#a6-typed-failures-with-unchanged-messages-2026-11-01));
  - the watchlist and runs-list document builders move from `cli_workspace.py` to `workspace_documents`
    ([A7](#a7-operations-return-domain-objects-and-documents-2026-11-01)), and the compare columns move into
    `application` ([A9](#a9-the-compare-columns-move-into-application-2026-11-01));
  - `WatchlistListDocument`, `schemas/watchlist-list.schema.json` and `ian watchlist list --json`;
  - the CLI's read commands call the operations inside `_workspace_failures`, and `_workspace_database`, used by the
    action commands, opens its connection with `application/database.py`;
  - [Architecture](../../../ARCHITECTURE.md) §13 and §4, and the `docs/project/STRATEGY_DEVELOPMENT.md` row that names
    `cli_workspace.py` as the reader of `headline_for` ([A12](#a12-documents-api1b-updates-2026-11-01)).
- **Branch:** `feat/api-application-read`.
- **Detail:** [Implementation record](#32-api1b-implementation-record).

### 3.1 API.1a implementation record

Tests moved to the document path, and why:

- The type restriction makes the JSON mode a type error for the text projection. The tests that replayed in JSON
  mode through `project_run` or a projector call, and the tests that passed a `PresentationMode` loop variable to
  `ReplayOptions`, test the replay contract this slice changes. Each JSON-mode case moved to `project_run_document`
  and keeps its assertions, and each loop over every mode covers the three text modes through the text projection and
  the serialized document projection.
- Moved: `tests/workspace_documents/test_analysis_run_replay.py`, `tests/test_specimen_strategy.py`, the specimen
  files (`replay.py`, `behavior.py`, `runs.py`, `site_context.py`), every other test that called `project_run` or a
  strategy's projector directly, and check T8 in `scripts/strategy_conformance.py`, which now replays every text mode through the text projection and
  the document projection for every strategy.
- No test of an `ian` command or its output was edited.

New tests: `tests/workspace_documents/test_run_replay_documents.py`, which for every strategy in `STRATEGIES`
stores a run and checks that the document projection is an instance of the strategy's document type and that
serializing it equals the `runs show --json` output, and which covers the generic replay's two paths, an unsupported
projection version and an undeclared method on each.

Files "Changing what every strategy provides" in [`STRATEGY_DEVELOPMENT.md`](../../../STRATEGY_DEVELOPMENT.md#changing-what-every-strategy-provides)
missed, now in that section:

- `investment_analysis_engine/workspace_documents/run_replay.py` and `investment_analysis_engine/reporting/replay_inputs.py`
  (the generic replay and the projector types);
- `StoredRun` and check T8 in `scripts/strategy_conformance.py`, beyond its closed sets;
- `tests/specimen/runs.py` and `tests/specimen/site_context.py`;
- the tests of the replay contract, which call the replay functions directly.

Noticed for later slices:

- API.1b's `runs show` operation takes `TextPresentationMode` for the text projection and offers the document
  projection as a separate operation, so `application` does not accept the JSON mode on the text path.
- The direct commands still pass `PresentationMode` to each presenter's `render_*`, whose JSON branch they use. That
  stays as it is.

### 3.2 API.1b implementation record

What changed, by area:

- **`application`** (new unit, layer 8): `context.py` (`ApplicationContext`), `database.py` (`open_database`),
  `watchlists.py` (`list_watchlists`, `get_watchlist`, `watchlist_repository`) and `runs.py` (`list_runs`,
  `replay_run_text`, `replay_run_document`, `compare_refresh_runs` and the compare columns). Each operation opens and
  closes its own connection. Its imports are exactly the units A2 names.
- **Typed failures:** `AnalysisRunNotFoundError` in `workspace/runs.py`; `reason_code` on `DuplicateRefreshRunsError`;
  `InvalidStoredRunError` raised from a repository `ValueError`, logged by `application.runs`' logger.
- **`cli_workspace.py`:** the read commands call the operations inside the new `_workspace_failures`;
  `_workspace_database` is `_workspace_failures` plus `open_database`, and only the action commands use it;
  `_watchlist_repository` and `_stored_method_alias` moved to `application/watchlists.py`.
- **`workspace_documents`:** `WatchlistSummaryDocument`, `WatchlistListDocument`, `build_watchlist_document`,
  `build_watchlist_list_document`, `build_runs_list_document`, and the `watchlist-list.schema.json` row.
- **Builder names ([A22](#a22-document-builder-names-2026-11-02)):** every strategy presenter's public builder, the
  generator template and the sites file, `build_health_document`, `indented_json` and `failure_document_json`.

User-visible changes:

- `ian watchlist list --json`, with the help line "Emit one JSON array of watchlist summaries.", and
  `schemas/watchlist-list.schema.json`.
- An unexpected exception while `runs show` replays a stored run is now the fixed failure "runs show failed
  unexpectedly." under `execution_error`, exit 1, with the traceback in the log. It escaped as a raw traceback before.
  Approved by the project owner on 2026-11-02; `tests/test_cli_runs_show_unexpected_failure.py` pins it in text and
  JSON.

Tests moved to a name's new home ([A23](#a23-tests-2026-11-02)); no assertion changed in any of them:

- `tests/test_cli_failure_envelope.py`: the import on line 15 and the call on line 221 now name
  `investment_analysis_engine.application.watchlists.watchlist_repository`, and the two patches on lines 193 and 206
  now name `investment_analysis_engine.application.database.ensure_database_ready`.
- `tests/test_command_validation_failures.py` line 859: the patch names
  `investment_analysis_engine.workspace.repositories.watchlists.SQLiteWatchlistRepository.add_entries`.
- A22 renames in `tests/test_cli_health.py` (`build_health_document`, two references) and
  `tests/reporting/test_failure_envelope.py` (`failure_document_json`, four references).
- A22 renames in test data that pins generated names: the specimen presenter and replay (`build_specimen_document`),
  the generator fills `tests/scripts/generator_fills/presenter.py.fill` and `replay.py.fill`, and the expected stub
  names in `tests/scripts/test_new_strategy.py`.

Test data that follows from the new unit and the new typed failures:

- `tests/test_strategy_import_layering.py`: `_ROOT_IMPORTERS` lists `application.runs` and `application.watchlists`,
  as its comment requires of the change that first makes a module import the composition root. No check was added.
- `tests/_failure_code_table.py` gains the rows of `AnalysisRunNotFoundError` and `DuplicateRefreshRunsError`, which
  the table must list because each now declares its code.
- `tests/reporting/test_failure_envelope.py`: `_COMMAND_CONTEXT_CODES` is removed, because no code is raised without an
  exception any more, and the coverage test now asserts that every failure code comes from an exception.

New tests: `tests/application/` (`test_context.py`, `test_database.py`, `test_watchlists.py`, `test_runs.py`, with
`runs show` parametrized over `STRATEGIES` in every text mode and in JSON, and the readiness failure of every
operation), `tests/workspace_documents/test_watchlist_list_document.py`,
`tests/test_cli_runs_show_unexpected_failure.py`, and three steps in the workspace-output scenario
(`watchlist-list-empty-json`, `watchlist-list-json`, `watchlist-list-json-timestamps`).

Noticed for later slices:

- The runs-list and watchlist-list documents are top-level arrays, so API.2's plan decides whether its endpoints wrap
  them.
- The action commands still open their connection with `_workspace_database` and compose through `cli_composition.py`;
  API.3 moves both.

## 4. Scope limits and acceptance criteria

- No CLI output changes by a byte, text or `--json`, except the added `ian watchlist list --json` in API.1b. Existing
  CLI tests pass unedited in both slices.
- No stored shape, formula or existing `schemas/` file changes; the one new file is `watchlist-list.schema.json`.
- For every strategy, the document projection of a stored run is an instance of the strategy's `json_envelope`, and
  its serialization equals `ian runs show --json`.
- A strategy added through `scripts/new_strategy.py` has both projections and passes the conformance checks with no
  edit to the generic replay, `application` or the CLI.
- `application` imports only the units named in [A2](#a2-the-application-package-2026-11-01), and
  `scripts/check_package_dependencies.py` passes. No import-enforcement check is added
  ([A13](#a13-tests-2026-11-01)).
- `application` has tests per operation, failure cases included, and `runs show` has a test parametrized over
  `STRATEGIES` in every mode.

## 5. Background

The API needs the same objects the CLI prints. The workspace commands print through functions that return strings,
and a stored run's JSON projection was a string too. Making the projection a typed document first (API.1a) lets
the application layer (API.1b) return it as it returns every other document, and leaves serialization to the edge
that needs text. What counts as an addition inside `/v1` (for example a new warning code such as the one in
[issue 204](https://github.com/PeterPontbriand/investment-analysis-engine/issues/204)) and extensible authentication
([issue 205](https://github.com/PeterPontbriand/investment-analysis-engine/issues/205)) are settled in API.2 ([A14](#a14-the-application-context-and-205-2026-11-01),
[A15](#a15-the-v1-additions-rule-2026-11-01)).

## Appendix A: Decision records

A1 to A15 were approved by the project owner on 2026-11-01, and A16 to A23 on 2026-11-02.

### A1 The slice plan is committed in API.1a's PR (2026-11-01)

This plan is written and committed in the PR of API.1a, for both slices.

### A2 The application package (2026-11-01)

A new package `investment_analysis_engine/application/` at layer 8, importing `config`, `core`, `data`, `reporting`,
`strategy_wiring`, `workspace` and `workspace_documents`. `cli` imports it. It has one module per area
(`database.py`, `watchlists.py`, `runs.py`), each holding plain functions, not a class that grows with each action.

### A3 The application context (2026-11-01)

Every operation takes a frozen `ApplicationContext` as its first argument. For now it holds only the settings, and
the CLI builds it at call time from its own `settings`, so the test isolation fixtures keep working. `application`
never reads a module-level `settings`, and knows nothing about how a caller signs in. A later caller identity or
workspace choice becomes a new field, not a new signature ([#205](https://github.com/PeterPontbriand/investment-analysis-engine/issues/205)).

### A4 One database connection per operation (2026-11-01)

One readiness-checked database connection per operation, opened and closed inside `application`. The opener lives in
`application/database.py`, and the CLI's `_workspace_database`, still used by the action commands until API.3,
delegates to it, so there is one opening path. Whether a server keeps a connection is decided in API.2.

### A5 Typed inputs (2026-11-01)

Operations take typed inputs: `str` names, `RunQuery`, `UUID`, `method_id` and the presentation mode. Flag parsing,
the alias to `method_id` translation and every message naming a flag or a command stay in `cli`. API.2 does its own
parameter parsing.

### A6 Typed failures with unchanged messages (2026-11-01)

- `watchlist show` raises the existing `WatchlistNotFoundError`.
- A new `AnalysisRunNotFoundError` (`ANALYSIS_RUN_NOT_FOUND`) serves `runs show`, and `runs compare` when a refresh
  has no runs, with the `no_runs_message` text.
- `DuplicateRefreshRunsError` declares `reason_code` (`INVALID_INPUT`).
- A repository `ValueError` on `get` is logged and raised as `InvalidStoredRunError` with the current sanitized
  message.

The catch-all "<command> failed unexpectedly" stays in `cli`.

### A7 Operations return domain objects and documents (2026-11-01)

The list and show operations return domain objects (`WatchlistSummary` tuples, `Watchlist`, `AnalysisRunSummary`
tuples); `runs compare` returns `RunsCompareDocument`. The watchlist and runs-list document builders move from
`cli_workspace.py` to `workspace_documents`. Text renderers stay in `cli`.

### A8 A stored run's JSON projection is a typed document (2026-11-01)

A stored run's JSON projection becomes a typed document in API.1a, before the application layer in API.1b. The
text projection cannot be given the JSON mode: the restriction is the type `TextPresentationMode`, a `Literal` of
the three text members of `PresentationMode`, so no new enum and no change to how the direct commands select their
mode were needed.

### A9 The compare columns move into application (2026-11-01)

The compare columns built from `STRATEGIES` move into `application`. The row in `docs/project/STRATEGY_DEVELOPMENT.md` that
names `cli_workspace.py` as the generic reader of `headline_for` is updated.

### A10 A watchlist list document and --json (2026-11-01)

A `WatchlistListDocument` and `ian watchlist list --json` are added in API.1b.

### A11 cli_composition.py stays in cli until API.3 (2026-11-01)

`cli_composition.py` (provider and resolver builders, settings loaders) stays in `cli` until API.3, when it moves
into `application` with the actions that use it.

### A12 Documents API.1b updates (2026-11-01)

API.1b updates `docs/project/ARCHITECTURE.md` §13 (Module boundaries) and §4 (Composition roots), and the
`docs/project/STRATEGY_DEVELOPMENT.md` row from A9. Historical milestone documents are not edited.

### A13 Tests (2026-11-01)

Existing CLI tests pass unedited. `application` gets tests per operation, failure cases included. `runs show` gets a
test parametrized over `STRATEGIES` in every mode. No new import-enforcement check is added.

### A14 The application context and #205 (2026-11-01)

The `ApplicationContext` of [A3](#a3-the-application-context-2026-11-01) is API.1's part of
[#205](https://github.com/PeterPontbriand/investment-analysis-engine/issues/205). The issue stays open for API.2.

### A15 The /v1 additions rule (2026-11-01)

The rule on what counts as an addition inside `/v1` is recorded in API.2's entry of the
[API contract](API_CONTRACT_AND_SLICE_PLAN.md#api2--ian-serve-and-the-read-endpoints).

### A16 The watchlist list document (2026-11-02)

Approved by the project owner on 2026-11-02. It refines [A10](#a10-a-watchlist-list-document-and---json-2026-11-01).

- `WatchlistListDocument` in `workspace_documents/watchlist.py` is a `RootModel` tuple of `WatchlistSummaryDocument`,
  unversioned, the pattern of `RunsListDocument`. Each item has the five `WatchlistSummary` fields in this order:
  `watchlist_id`, `display_name`, `entry_count`, `created_at`, `updated_at`. Timestamps use `DocumentTimestamp`, written
  with `+00:00`; `updated_at` is null until the watchlist is first changed. An empty store prints `[]`.
- `ian watchlist list --json` has the help text "Emit one JSON array of watchlist summaries." A failure writes the
  failure envelope to standard output, as the other workspace commands do. The text output is unchanged.
- The API contract's API.2 entry states that the runs-list and watchlist-list documents are both top-level arrays, so a
  list-level field can never be added to either, and that API.2's plan decides whether its endpoints wrap them.

### A17 Plan and document corrections (2026-11-02)

Approved by the project owner on 2026-11-02.

- §1 and §4 of this plan make an exception to "no `schemas/` file changes" for `schemas/watchlist-list.schema.json`.
- `DOCUMENTS` in `workspace_documents/json_documents.py` gains
  `JsonDocument("watchlist-list.schema.json", WatchlistListDocument, ("watchlist list",))`, and the schema is generated
  by `scripts/generate_schemas.py`.
- `docs/user/USAGE.md` lists `watchlist list` among the commands offering `--json`; `docs/user/WORKSPACE.md` describes
  the document beside the `watchlist list` example.
- The API contract's API.1b Decision bullet says `application` owns the read operations and production composition joins
  it in API.3 ([A11](#a11-cli_compositionpy-stays-in-cli-until-api3-2026-11-01)).
- `docs/project/ARCHITECTURE.md` §4 describes the current code: it names `application` as the home of the read
  operations and of the one database opener, and no longer names the `_execute_*` functions that do not exist.

### A18 AnalysisRunNotFoundError (2026-11-02)

Approved by the project owner on 2026-11-02. `AnalysisRunNotFoundError` is defined in `workspace/runs.py`, beside
`AnalysisRun`, with `reason_code: ClassVar[FailureReasonCode] = ANALYSIS_RUN_NOT_FOUND`, following
`WatchlistNotFoundError`. `InvalidStoredRunError` (`workspace/codecs.py`) is reused, not redefined.

### A19 Modules and names of application (2026-11-02)

Approved by the project owner on 2026-11-02.

- `application/context.py`: `ApplicationContext`, a frozen dataclass whose one field is `settings: ProjectSettings`.
- `application/database.py`: `open_database(context)`, a context manager that builds `SQLiteDatabase(context.settings)`,
  runs `ensure_database_ready`, yields the database and closes it. `DatabaseReadinessError` passes through unchanged.
- `application/watchlists.py`: `list_watchlists(context)` and `get_watchlist(context, name)`, which raises
  `WatchlistNotFoundError(f"No watchlist named {name!r} exists.")` when the repository returns `None`.
- `application/runs.py`: `list_runs(context, query)`, `replay_run_text(context, run_id, mode)`,
  `replay_run_document(context, run_id)`, `compare_refresh_runs(context, refresh_id)` and the private compare-column
  builder moved from `cli_workspace.py` ([A9](#a9-the-compare-columns-move-into-application-2026-11-01)).
- Each operation opens one connection through `open_database` and closes it inside the operation
  ([A4](#a4-one-database-connection-per-operation-2026-11-01)); replay and compare work only from the stored runs
  already read.
- Failures ([A6](#a6-typed-failures-with-unchanged-messages-2026-11-01)), with today's messages: a missing run is
  `AnalysisRunNotFoundError(f"No Analysis Run with ID {run_id} exists.")`; a refresh with no runs is
  `AnalysisRunNotFoundError(no_runs_message(refresh_id))`; `DuplicateRefreshRunsError` declares `reason_code`
  `INVALID_INPUT`; a plain `ValueError` from the run repository's `get()` is logged with
  `logger.exception("Analysis Run %s could not be read.", run_id)` from `application`'s module logger and raised as
  `InvalidStoredRunError`, catching only around the `get()` call.
- `application` never reads a module-level settings object. The CLI builds `ApplicationContext(settings=settings)` at
  call time from `cli_workspace`'s own binding, so `isolated_cli_settings` keeps working.

### A20 One home for the watchlist repository wiring (2026-11-02)

Approved by the project owner on 2026-11-02. `_watchlist_repository` and `_stored_method_alias` move from
`cli_workspace.py` into `application/watchlists.py` as the public `watchlist_repository(database)`. The action commands
call it from there, so that wiring has one home.

### A21 Failure translation (2026-11-02)

Approved by the project owner on 2026-11-02.

- `cli_workspace.py` splits the failure handling out of `_workspace_database` into
  `_workspace_failures(command, *, json_output=False)`. A `DatabaseReadinessError` or any exception with a
  `FailureReasonCode` `reason_code` is reported with its own message; `typer.Exit` and `typer.Abort` pass through;
  anything else is logged and reported as "<command> failed unexpectedly." under `execution_error`.
- The read commands parse their parameters as before (flag messages, the alias to `method_id` translation, ticker and
  run-ID parsing), then call the operation inside `_workspace_failures` and render the result.
- `_workspace_database` is `_workspace_failures` plus `open_database`, and only the action commands use it.
- Consequence, accepted by the project owner on 2026-11-02: an unexpected exception during the replay in `runs show`
  is the standard "runs show failed unexpectedly." failure, where it escaped as a traceback before.

### A22 Document builder names (2026-11-02)

Approved by the project owner on 2026-11-02. The name of a function that builds a document model starts with `build_`.

- New: `build_watchlist_document` (moved from `cli_workspace.py`), `build_watchlist_list_document` and
  `build_runs_list_document`.
- Renamed: each strategy presenter's public `<module>_document` to `build_<module>_document`, with
  `scripts/strategy_templates/presenter.py.tmpl`, the presenter site's `defines` pattern in
  `scripts/strategy_sites.toml`, and `health_document` in `cli_health.py` to `build_health_document`.
- Renamed because they return serialized text, not a model: `json_document` to `indented_json` and
  `failure_document` to `failure_document_json` in `reporting/presentation.py`.
- `project_<module>_document` and `project_run_document` already start with a verb and are unchanged. Dated
  historical milestone records are not edited ([A12](#a12-documents-api1b-updates-2026-11-01)).

### A23 Tests (2026-11-02)

Approved by the project owner on 2026-11-02. It refines [A13](#a13-tests-2026-11-01).

- `tests/application/` has one file per module, covering each operation's success and failure cases, the readiness
  failure included. `runs show` has a test parametrized over `STRATEGIES` in every mode: the text modes through
  `replay_run_text`, JSON through `replay_run_document`.
- Workspace-output snapshots cover `ian watchlist list --json` with watchlists and with an empty store (`[]`), and a
  test checks that the output validates as the document.
- Existing CLI tests pass with no assertion changed. Amendment, approved by the project owner on 2026-11-02: a test
  that refers to a name this slice moves (a patch target or a direct call) is pointed at the name's new home, and
  listing every such reference in [§3.2](#32-api1b-implementation-record) is part of the slice. A renamed reference
  that sits in an assertion which would have to change in meaning stops the work.
- A test of an unexpected replay exception in `runs show` checks the text output and the `--json` envelope
  ([A21](#a21-failure-translation-2026-11-02)).
