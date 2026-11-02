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
- **What it does not do:** add an endpoint, change a stored shape, a `schemas/` file, a formula or any existing CLI
  output, or move an action command. The one new CLI output is `ian watchlist list --json`
  ([A10](#a10-a-watchlist-list-document-and---json-2026-11-01)).
- **Rules both slices follow:**
  - a strategy declares its replay behavior through its descriptor, and generic code stays strategy-free
    (`AGENTS.md` §3 and §9);
  - existing CLI tests pass without edits;
  - the managed quality gate, with the Python 3.14 second pass, after each slice, and the project owner's approval
    before the next slice starts.
- **Where the history lives:** decisions A1 to A15 are in [Appendix A](#appendix-a-decision-records), approved by the
  project owner on 2026-11-01.

## 2. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| API.1a | [Replay document projection](#api1a--replay-document-projection) | Complete | 2026-11-01 |
| API.1b | [Application layer: reading](#api1b--application-layer-reading) | Next | |

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
  - each presenter's document builder is public (`piotroski_document`, `fcf_growth_document`,
    `momentum_document`, `graham_number_document`, `graham_growth_document`); its JSON branch and the strategy's
    document projector (`project_<module>_document`) call the same builder, and a replay passes no provider check;
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
  - `WatchlistListDocument` and `ian watchlist list --json`;
  - the CLI's read commands call the operations, and `_workspace_database` delegates to `application/database.py`;
  - [Architecture](../../../ARCHITECTURE.md) §13 and §4, and the `docs/TOOL_DEVELOPMENT.md` row that names
    `cli_workspace.py` as the reader of `headline_for` ([A12](#a12-documents-api1b-updates-2026-11-01)).
- **Branch:** `feat/api-application-read`.
- **Detail:** ⚠ no implementation record yet; API.1b adds one here when it starts.

### 3.1 API.1a implementation record

Tests moved to the document path, and why:

- The type restriction makes the JSON mode a type error for the text projection. The tests that replayed in JSON
  mode through `project_run` or a projector call, and the tests that passed a `PresentationMode` loop variable to
  `ReplayOptions`, test the replay contract this slice changes. Each JSON-mode case moved to `project_run_document`
  and keeps its assertions, and each loop over every mode covers the three text modes through the text projection and
  the serialized document projection.
- Moved: `tests/workspace_documents/test_analysis_run_replay.py`, `tests/analysis/graham_value/test_effective_as_of.py`,
  `tests/test_specimen_strategy.py` and the specimen files (`replay.py`, `behavior.py`, `runs.py`, `site_context.py`),
  and check T8 in `scripts/strategy_conformance.py`, which now replays every text mode through the text projection and
  the document projection for every strategy.
- No test of an `ian` command or its output was edited.

New tests: `tests/workspace_documents/test_run_replay_documents.py`, which for every strategy in `STRATEGIES`
stores a run and checks that the document projection is an instance of the strategy's document type and that
serializing it equals the `runs show --json` output, and which covers the generic replay's two paths, an unsupported
projection version and an undeclared method on each.

Files "Changing what every strategy provides" in [`TOOL_DEVELOPMENT.md`](../../../../TOOL_DEVELOPMENT.md#changing-what-every-strategy-provides)
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

## 4. Scope limits and acceptance criteria

- No CLI output changes by a byte, text or `--json`, except the added `ian watchlist list --json` in API.1b. Existing
  CLI tests pass unedited in both slices.
- No stored shape, `schemas/` file or formula changes.
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
that needs text. [Issue 205](https://github.com/PeterPontbriand/investment-analysis-engine/issues/205) (extensible
authentication) and [issue 204](https://github.com/PeterPontbriand/investment-analysis-engine/issues/204) (what
counts as an addition inside `/v1`) are settled in API.2 ([A14](#a14-the-application-context-and-205-2026-11-01),
[A15](#a15-the-v1-additions-rule-2026-11-01)).

## Appendix A: Decision records

All approved by the project owner on 2026-11-01.

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

The compare columns built from `STRATEGIES` move into `application`. The row in `docs/TOOL_DEVELOPMENT.md` that
names `cli_workspace.py` as the generic reader of `headline_for` is updated.

### A10 A watchlist list document and --json (2026-11-01)

A `WatchlistListDocument` and `ian watchlist list --json` are added in API.1b.

### A11 cli_composition.py stays in cli until API.3 (2026-11-01)

`cli_composition.py` (provider and resolver builders, settings loaders) stays in `cli` until API.3, when it moves
into `application` with the actions that use it.

### A12 Documents API.1b updates (2026-11-01)

API.1b updates `docs/project/ARCHITECTURE.md` §13 (Module boundaries) and §4 (Composition roots), and the
`docs/TOOL_DEVELOPMENT.md` row from A9. Historical milestone documents are not edited.

### A13 Tests (2026-11-01)

Existing CLI tests pass unedited. `application` gets tests per operation, failure cases included. `runs show` gets a
test parametrized over `STRATEGIES` in every mode. No new import-enforcement check is added.

### A14 The application context and #205 (2026-11-01)

The `ApplicationContext` of [A3](#a3-the-application-context-2026-11-01) is API.1's part of
[#205](https://github.com/PeterPontbriand/investment-analysis-engine/issues/205). The issue stays open for API.2.

### A15 The /v1 additions rule (2026-11-01)

The rule on what counts as an addition inside `/v1` is recorded in API.2's entry of the
[API contract](API_CONTRACT_AND_SLICE_PLAN.md#api2--ian-serve-and-the-read-endpoints).
