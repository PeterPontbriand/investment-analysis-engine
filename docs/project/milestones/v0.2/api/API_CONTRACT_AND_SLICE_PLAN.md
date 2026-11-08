# API — Local HTTP API: Contract and Slice Plan

Gives the engine a versioned local HTTP API, so that a separate GUI application, and later other
consumers, can use watchlists, refreshes, stored runs and direct analysis without the command line.

Placement among other work packages: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **What this work package does:**
  - moves the work every workspace command does into one application layer, which the CLI and the
    API both call;
  - adds `ian serve`, a local HTTP server, with an OpenAPI document checked in like `schemas/`;
  - exposes reading, editing, direct analysis and refresh (with progress and stop) through it;
  - serves the investor-facing help content (glossary terms and the educational guides), and links every
    label, status and code the API returns to the term that explains it, so that a GUI user never leaves the
    application to understand what is shown.
- **What it does not do:** build a GUI. The GUI is a separate application in its own repository
  ([Background](#6-background)). Nothing here is reachable from another computer. Full list:
  [Out of scope](#4-out-of-scope).
- **Rules every slice follows:**
  - no financial logic in `cli` or `api`, and no strategy-specific code in either
    (`AGENTS.md` §9);
  - each operation moves into the application layer in the same slice that switches the CLI to it,
    so there is never a second path;
  - existing CLI output, text and `--json`, stays as it is, pinned by the existing CLI tests; a read command may
    gain `--json` ([A10](API_1_SLICE_PLAN.md#a10-a-watchlist-list-document-and---json-2026-11-01)); the one exception
    is the runs-list and watchlist-list documents, which become versioned objects in API.2a
    ([S3](API_2_SLICE_PLAN.md#s3-the-list-documents-are-versioned-objects-2026-11-03));
  - the managed quality gate after every slice, and the project owner's approval before the next
    slice starts.
- **Where the history lives:** decisions behind this plan are in
  [Appendix A](#appendix-a-decision-records-and-history).

## 2. Sequence and status

Implementation starts after Step 3.5's 3.5.3e merges and its slice 3.5.3e1c and its issues 207 and 210 are complete ([Step 3.5 order](../step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status)), and 3.5.5 starts after API.6 merges
([milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status)).

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| API.0 | [Plan and milestone changes](#api0--plan-and-milestone-changes) | Complete | 2026-10-30 |
| API.1a | [Replay document projection](#api1a--replay-document-projection) | Complete | 2026-11-01 |
| API.1b | [Application layer: reading](#api1b--application-layer-reading) | Complete | 2026-11-02 |
| API.2a | [Versioned list documents](API_2_SLICE_PLAN.md#api2a--versioned-list-documents) | Complete | 2026-11-03 |
| API.2b | [`ian serve` and the read endpoints](#api2--ian-serve-and-the-read-endpoints) | Complete | 2026-11-04 |
| API.3a | [Execution composition and direct analysis](API_3_SLICE_PLAN.md#api3a--execution-composition-and-direct-analysis) | Complete | 2026-11-05 |
| API.3b1 | [Watchlist actions](API_3_SLICE_PLAN.md#api3b1--watchlist-actions) | Complete | 2026-11-05 |
| API.3b2 | [Selections and Site 19](API_3_SLICE_PLAN.md#api3b2--selections-and-site-19) | Complete | 2026-11-06 |
| API.3c | [Refresh with progress](API_3_SLICE_PLAN.md#api3c--refresh-with-progress) | Complete | 2026-11-06 |
| API.4a | [Action endpoints, selection forms, result documents and error lists](API_4_SLICE_PLAN.md#api4a--action-endpoints-selection-forms-result-documents-and-error-lists) | Complete | 2026-11-06 |
| API.4b | [Refresh jobs](API_4_SLICE_PLAN.md#api4b--refresh-jobs) | Complete | 2026-11-07 |
| API.5a | [Help content: the glossary](#api5a--help-content-the-glossary) | Complete | 2026-11-07 |
| API.5b1 | [Help content: the guides](#api5b1--help-content-the-guides) | Complete | 2026-11-07 |
| API.5b2 | [Help content: the bundle](#api5b2--help-content-the-bundle) | Complete | 2026-11-07 |
| API.6 | [Term references and help endpoints](#api6--term-references-and-help-endpoints) | Next | |

## 3. The slices

### API.0 — Plan and milestone changes

- **Problem:** the milestone plan excluded a GUI and deferred the HTTP API until Step 3.5 closed,
  while potential users do not try the engine because the command line is too hard.
- **Decision:** a separate GUI application uses a local HTTP API built here, before the remaining Step 3.5 strategies
  ([A.1](#a1-a-separate-gui-application-over-a-local-api-2026-10-30)).
- **Scope:** this plan; the milestone plan's sequence table, §1, §4.12 and exit criteria; the
  deferred delivery-surfaces note; the Discovery Workbook, Master Plan, Evidence Provider Roadmap,
  Architecture Guide §12 and v0.3 plan entries that named a GUI or the HTTP API; the removal of
  the prefix-matching note ([A.3](#a3-step-36-items-dropped-2026-10-30)).
- **Branch:** `docs/api-plan`.
- **Detail:** this document.

### API.1a — Replay document projection

- **Problem:** every replay projector returns `str` in every presentation mode. In the JSON mode a strategy's
  presenter builds its typed document and serializes it inside the projector, so a caller that needs the document
  itself, as the API does, must parse text it could have been given as a model.
- **Decision:** a replay has two projections. The text projection renders the three text modes and cannot be given
  the JSON mode; the document projection returns the strategy's typed `--json` document, and serializing it is the
  caller's edge ([A8](API_1_SLICE_PLAN.md#a8-a-stored-runs-json-projection-is-a-typed-document-2026-11-01)).
- **Scope:** the document projector in each strategy's replay file, built by the presenter's public document
  builder; the descriptor member and its view accessor; the generic replay's second path; the generator, its
  templates and the sites file; `ian runs show --json` writing the serialized document; the tests of the replay
  contract moved to the document path; this plan's slice plan.
- **Branch:** `feat/api-replay-documents`.
- **Detail:** [API.1 slice plan](API_1_SLICE_PLAN.md).

### API.1b — Application layer: reading

- **Problem:** each Typer command in `cli_workspace.py` parses, composes, works and prints in one
  function and fails through `typer.Exit`, and production composition lives in the `cli` unit at
  the top of the package layers, so nothing else can reuse it.
- **Decision:** a new unit, `application`, owns the read operations; production composition joins it
  in API.3a ([A11](API_1_SLICE_PLAN.md#a11-cli_compositionpy-stays-in-cli-until-api3-2026-11-01)). It
  returns the existing typed documents and domain objects, and raises typed failures that carry a
  `FailureReasonCode`. It knows no presentation and no strategy.
- **Scope:** the read operations — watchlist list and show, runs list, show (each presentation
  mode) and compare — and the composition they need; the CLI switched to them; the new unit's row
  in [Architecture §13](../../../ARCHITECTURE.md#13-module-boundaries).
- **Branch:** `feat/api-application-read`.
- **Detail:** [API.1 slice plan](API_1_SLICE_PLAN.md#32-api1b-implementation-record).

### API.2 — `ian serve` and the read endpoints

- **Problem:** a separate application cannot import the engine; it needs a stable, local,
  documented interface.
- **Decision:** the work is split in two ([S1](API_2_SLICE_PLAN.md#s1-api2-is-split-2026-11-03)). API.2a makes the
  two list documents versioned objects. API.2b adds a new unit, `api`, which serves `/v1/` over HTTP with Starlette
  and uvicorn, bound to `127.0.0.1` only, behind a per-launch token and a `Host` check. Responses are the existing
  typed documents; a failure is a `FailureEnvelope`. A strategy is exposed generically, through its descriptor:
  headline cells, the replay projection text and its JSON document.
- **Scope:**
  - API.2a: the versioned runs-list and watchlist-list documents in the CLI and in `schemas/`, and the API.2 slice
    plan;
  - API.2b: `ian serve`; `/v1/info` (API and engine versions, and whether an SEC identity is configured, never its
    value); the read endpoints over API.1b; `openapi.json`, generated by a script and compared by a test like
    `schemas/`; an endpoint test parametrized over `STRATEGIES`; the dependencies `starlette` and `uvicorn`, and
    `httpx` for tests (approved 2026-10-30, [A.2](#a2-api-shape-and-dependencies-2026-10-30)).
- **Branch:** `feat/api-list-documents` (API.2a) and `feat/api-serve-read` (API.2b).
- **Detail:** [API.2 slice plan](API_2_SLICE_PLAN.md). It decides what counts as an addition inside `/v1`
  ([S4](API_2_SLICE_PLAN.md#s4-the-v1-additions-rule-2026-11-03)) and settles the extensible authentication of
  [#205](https://github.com/PeterPontbriand/investment-analysis-engine/issues/205)
  ([S6](API_2_SLICE_PLAN.md#s6-205-is-settled-by-contract-rules-2026-11-03)); API.1b's `ApplicationContext` is only its
  first part ([A14](API_1_SLICE_PLAN.md#a14-the-application-context-and-205-2026-11-01)).

### API.3 — Application layer: actions

- **Problem:** creating and editing watchlists, analyzing a ticker and refreshing are still
  CLI-only, and a refresh reports nothing until it ends.
- **Decision:** the action operations move into `application` as API.1b's did, in three slices
  ([C1](API_3_SLICE_PLAN.md#c1-api3-is-three-slices-2026-11-04)). A refresh accepts an observational progress
  callback, and keeps using the existing cancellation event. A selection is built from its model's fields, not from the
  CLI's flag set.
- **Scope:**
  - API.3a: strategy execution moves out of the CLI, with production composition, and direct analysis of one ticker is
    an operation, saved or not;
  - API.3b1: watchlist create, rename, delete, add and remove;
  - API.3b2: selection from model fields; the selection models' JSON
    Schema ([S19](API_2_SLICE_PLAN.md#s19-the-selection-model-schema-moves-to-api3-2026-11-03)) and a conformance
    check that every selection field has a description and a type the API's form schema supports; Site 19;
  - API.3c: refresh with progress;
  - the CLI switched to each operation in the slice that adds it.
- **`as_of`:** direct-analysis and run endpoints (served in API.4) accept an optional `as_of`, matching `--as-of` on the
  CLI, so a client such as the future predictive evaluator
  ([Product boundaries](../../../MASTER_PLAN.md#25-product-boundaries)) can request results as of a past date. The echo
  is the strategy documents' existing `requested_as_of` and `effective_as_of`; no field is added, and the selection's
  `as_of` reaches the operation unchanged ([C6](API_3_SLICE_PLAN.md#c6-the-as-of-echo-is-the-existing-document-fields-2026-11-04)).
- **Site 19:** the watchlist flag bundle is replaced by one `add-selection` subcommand per strategy, decided in
  [C12](API_3_SLICE_PLAN.md#c12-site-19-is-settled-by-one-add-selection-subcommand-per-strategy-2026-11-04) and
  implemented in API.3b2.
- **Branches:** `feat/api-execution-composition` (API.3a), `feat/api-watchlist-actions` (API.3b1),
  `feat/api-selections` (API.3b2) and `feat/api-refresh-progress` (API.3c); they replace the single `feat/api-application-actions`.
- **Also moved:** `investment_analysis_engine/cli_composition.py` (the provider and resolver builders and the settings
  loaders) was deleted in API.3a: the shared builders are in `application/providers.py` and each strategy's own are in its
  `application.py` ([A11](API_1_SLICE_PLAN.md#a11-cli_compositionpy-stays-in-cli-until-api3-2026-11-01),
  [C2](API_3_SLICE_PLAN.md#c2-one-rule-a-file-named-for-a-unit-belongs-to-that-unit-as-amended-2026-11-04),
  [C8](API_3_SLICE_PLAN.md#c8-cli_compositionpy-is-deleted-2026-11-04)).
- **Detail:** [API.3 slice plan](API_3_SLICE_PLAN.md).

### API.4 — Action endpoints and refresh jobs

- **Problem:** the GUI needs to start actions and follow a refresh that runs for minutes.
- **Decision:** action endpoints over API.3, in two slices ([J1](API_4_SLICE_PLAN.md#j1-api4-is-two-slices-2026-11-06)),
  both done. A refresh runs as a job inside the `ian serve` process, one at a time, with a start endpoint, a status
  endpoint the client polls, a latest-job endpoint and a stop endpoint. A job starts from a watchlist or from a list of
  entries ([J11](API_4_SLICE_PLAN.md#j11-a-refresh-job-starts-from-a-watchlist-or-a-list-of-entries-2026-11-06),
  [J29](API_4_SLICE_PLAN.md#j29-prepare-and-run-2026-11-07) to
  [J44](API_4_SLICE_PLAN.md#j44-a-new-reason-code-bumps-the-documents-that-can-carry-it-2026-11-07)). A job does not
  outlive the process: when the server stops, a job that outlives the grace is abandoned.
- **Scope:** the action endpoints, with the optional `as_of` and its echoed effective value on the
  direct-analysis and run endpoints (API.4a); the refresh job start, status, latest-job and stop endpoints (API.4b);
  their `openapi.json` entries and tests.
- **Requirements recorded for API.4's slice plan:**
  - clients need an endpoint that gives each strategy's current configured selection defaults, because the selection
    schemas carry none ([C13](API_3_SLICE_PLAN.md#c13-one-selection-schema-per-strategy-2026-11-04));
  - the direct-analysis endpoint can serve a run's text in a mode through the outcome's `render_text`, as S17 does for
    saved runs ([C5a](API_3_SLICE_PLAN.md#c5a-direct-analysis-is-an-operation-that-returns-an-outcome-2026-11-04));
  - a form client is likely to want every field's error at once, and `build_selection` reports the first only
    ([W32](API_3_SLICE_PLAN.md#w32-first-error-only-2026-11-05)); the error can gain a list of every error additively;
  - serving refresh progress over HTTP needs an event document, a transport (server-sent events, WebSocket or polling, not chosen) and a way for the client to set cancellation ([W56](API_3_SLICE_PLAN.md#w56-serving-refresh-progress-over-http-2026-11-06));
  - a client may need each error's rule identifier and value arguments served, to translate a message or place it on a form field ([W42](API_3_SLICE_PLAN.md#w42-errors-keep-what-a-translation-needs-2026-11-05)).
- **Two `ian serve` processes against one database:** [J19](API_4_SLICE_PLAN.md#j19-several-processes-one-database-2026-11-06) settled it.
- **Branches:** `feat/api-actions` (API.4a) and `feat/api-refresh-jobs` (API.4b).
- **Detail:** [API.4 slice plan](API_4_SLICE_PLAN.md).

### API.5a — Help content: the glossary

- **Problem:** the glossary mixes investor, command-line and contributor terms, many entries have no first paragraph that
  stands alone, and nothing gives a term a stable identifier.
- **Decision:** Markdown stays the source. Each glossary entry has a permanent `<a id>` id and a first paragraph that is its
  short definition; a checker enforces the structure ([A.4](#a4-help-content-in-the-gui-2026-10-30),
  [H1](API_5_SLICE_PLAN.md#h1-api5-is-split-in-two-2026-11-07)).
- **Scope:**
  - contributor terms move to `docs/project/CONTRIBUTOR_GLOSSARY.md`, which is not served; command-line terms stay in the
    user glossary, in a section that carries the exclude marker;
  - every entry gets an id; every investor entry gets a short definition of at most 200 characters and two sentences, with
    no link or code, and no command, flag or closed list of strategies;
  - every link to a glossary entry targets the id; `scripts/check_doc_links.py` resolves `<a id>` anchors and refuses a
    link to a heading slug;
  - `scripts/check_help_content.py`, a gate step beside `check_doc_links.py`.
- **Branch:** `feat/api-help-glossary`.
- **Detail:** [API.5 slice plan](API_5_SLICE_PLAN.md).

### API.5b1 — Help content: the guides

- **Problem:** the educational guides mix explanation with command-line instructions, so none of them can be served as it
  stands.
- **Decision:** every served section is interface-neutral and command-line material stays in excluded sections; leak checks
  keep commands, flags and links to unserved documents out of served content
  ([H23](API_5_SLICE_PLAN.md#h23-api5b-is-split-in-two-2026-11-07) to
  [H30](API_5_SLICE_PLAN.md#h30-the-beginner-guide-2026-11-07)).
- **Scope:** the exclude markers and the interface-neutral rewording in the served guides; `strategies/GRAHAM.md` retired;
  the leak checks in `scripts/check_help_content.py` and the command-name test.
- **Branch:** `feat/api-help-guides`.
- **Detail:** [API.5 slice plan](API_5_SLICE_PLAN.md).

### API.5b2 — Help content: the bundle

- **Problem:** nothing packages the served content for the API.
- **Decision:** a generated help bundle, with a loader, ships inside the package and is compared in the gate like `schemas/`
  ([H13](API_5_SLICE_PLAN.md#h13-the-bundle-2026-11-07),
  [H14](API_5_SLICE_PLAN.md#h14-links-in-the-bundle-2026-11-07) and
  [H31](API_5_SLICE_PLAN.md#h31-the-bundles-shape-2026-11-07) to
  [H33](API_5_SLICE_PLAN.md#h33-generator-and-drift-2026-11-07)).
- **Scope:** the `help` package with the bundle model, its loader and `help_bundle.json`; the bundle generator with its drift
  check; package-data, Architecture §13 and `check_installed_package`.
- **Branch:** `feat/api-help-bundle`.
- **Detail:** [API.5 slice plan](API_5_SLICE_PLAN.md#api5b2--the-bundle).

### API.6 — Term references and help endpoints

- **Problem:** no API document says which term explains a label, status or code, so a GUI cannot explain what it
  shows, and a new strategy could add an unexplained column.
- **Decision:** every piece of engine text the API returns carries a term reference, and a conformance test fails
  the gate when one is missing or names no term.
- **Scope:**
  - a `term` on each headline cell (an additive change; the runs-compare document's `schema_version` goes up and
    nothing stored changes);
  - a `term` on each strategy descriptor;
  - one mapping table each for run outcomes, calculation statuses and failure reason codes;
  - a term in each selection field's metadata;
  - "glossary terms" as an edit site in `scripts/strategy_sites.toml`;
  - `/v1/help/terms/{id}` and `/v1/help/documents/{id}`, which return Markdown, never HTML;
  - term references for all five strategies, Piotroski included;
  - an orphan-term check: every served term is referenced by an API.6 mapping or linked from served content
    ([H9](API_5_SLICE_PLAN.md#h9-boundary-with-api6-2026-11-07));
  - only term ids and document ids are stable references: section ids and group ids are valid only within the bundle that
    carries them, and a client follows them but never stores them
    ([H54](API_5_SLICE_PLAN.md#h54-stable-references-across-locales-2026-11-07));
  - locale choice: every endpoint that returns engine text follows [A.5](#a5-locale-choice-2026-11-07).
- **Branch:** `feat/api-help`.
- **Detail:**
  - It follows "Changing what every strategy provides" in [`TOOL_DEVELOPMENT.md`](../../../../TOOL_DEVELOPMENT.md#changing-what-every-strategy-provides)
    for the "glossary terms" edit site, and records any file that section missed in its own implementation record.
  - ⚠ no slice plan yet

## 4. Out of scope

- A GUI, HTML pages or static web assets in this repository.
- Access from another computer, user accounts, or any authentication beyond the per-launch token.
- An MCP server and Parquet/Arrow export; they stay with the
  [deferred delivery-surfaces note](../deferred/DEFERRED_STANDARD_DELIVERY_SURFACES.md).
- Writing to the settings folder. The GUI passes `SEC_USER_AGENT` to the `ian serve` process it
  starts.
- Serving installation, quick-start, usage, workspace, database, hardware or smoke-testing documents, or
  `docs/user/API.md`, the client authors' reference written in API.2b
  ([S5](API_2_SLICE_PLAN.md#s5-the-client-reference-is-docsuserapimd-2026-11-03)); the GUI writes its own help on
  using the application.
- HTML in any help response, and contributor terms in the served help.
- Local-model synthesis endpoints; they belong to
  [Step 3.6](../IMPLEMENTATION_PLAN.md#412-step-36--light-mode-support).
- Database maintenance, provider health, evaluation and settings editing through the API.
- A change to any stored shape, formula or classification, or to existing CLI output, except the two list documents
  of [S3](API_2_SLICE_PLAN.md#s3-the-list-documents-are-versioned-objects-2026-11-03).

## 5. Acceptance criteria

- Every workspace command calls the application layer; no command composes dependencies itself.
- A new strategy added through `scripts/new_strategy.py` appears in every endpoint with no edit to
  `application`, `api` or the GUI, and the parametrized endpoint test covers it.
- `openapi.json` is regenerated and compared in the managed gate; a drift fails it.
- Endpoint tests run in process, open no socket, and pass under the network guard.
- `ian serve` refuses a request without the token or with another `Host`, and binds to
  `127.0.0.1` only.
- A refresh started through the API reports progress per job, can be stopped, and stores the same
  runs a CLI refresh of the same watchlist stores.
- Inside `/v1`, a change only adds; a breaking change is a new version path.
- Every headline cell, strategy, run outcome, calculation status, failure reason code and selection field the API
  returns names a term, and every named term exists in the help bundle; the gate fails otherwise.
- Every glossary term and served section is reachable through the help endpoints, and no served text contains an
  `ian` command.
- The help bundle is regenerated and compared in the managed gate; a drift fails it.

## 6. Background

Potential users, including some whose opinion on the financial side the project owner values, do
not try the engine because a command line is "too hard to use". The installation guide also asks
them to install Git, Python and `uv`, clone the repository and write a `.env` file into a hidden
folder by hand.

A GUI built inside this repository was considered first. A separate application was chosen
instead: it keeps this repository focused on the engine, as the Discovery Workbook has said since
the start, it turns the deferred HTTP API into a surface with a real consumer, and it gives the
installer to the GUI application, which can install a pinned copy of the engine behind the scenes.

The project owner also wants a user new to investing never to leave the GUI to look up a term. That makes the
engine the owner of every explanation: it decides what the GUI shows, and a new strategy brings new labels.

The GUI application has its own repository and plan. Step 3.6's new-user exit criterion is met
through it ([A.1](#a1-a-separate-gui-application-over-a-local-api-2026-10-30)).

## Appendix A: Decision records and history

### A.1 A separate GUI application over a local API (2026-10-30)

Approved by the project owner on 2026-10-30.

| Item | Decision |
| :--- | :--- |
| Products | Two: the engine (this repository) and a GUI application in its own repository. The Discovery Workbook's "full GUI/frontend integration belongs to separate projects" stands |
| Work in this repository | A versioned local HTTP API over a new application layer, as work package `API`, after 3.5.3e and before 3.5.4 |
| Why before 3.5.4 | The six remaining Step 3.5 strategies use the application layer from the start, and users can comment while they are still unbuilt. Once API.6 merges, Step 3.5 continues here while the GUI is built in parallel |
| GUI technology | Decided in the GUI repository's own contract; the initial lean is a Tauri desktop shell with a TypeScript interface, which builds installers and starts `ian serve` as a background process |
| Installer | Owned by the GUI application, which installs a version-pinned engine with `uv tool install`. "Use my own engine install" is not in its first release |
| SEC identity | Kept in the GUI application's own settings and passed to the `ian serve` process as `SEC_USER_AGENT`; the engine still never writes to its settings folder |
| Versioning | Changes inside `/v1` only add. A breaking change becomes `/v2`, and both are served for one engine minor release. Each GUI release pins the engine version it installs |
| v0.2 exit | Option (a): v0.2 closes when a GUI release works with engine v0.2, and the GUI is the documented route for a new user. The alternative, (b), kept the exit on the engine's own surfaces and left the new-user goal to the GUI's plan |

Rejected:

- **A GUI inside this package** (server-rendered pages from the engine): simplest to change, but it
  put a GUI and its dependencies inside the engine, kept the installer here, and needed an exception
  to the rule that the engine never writes to its settings folder.
- **A GUI that runs `ian ... --json` for each action:** no engine work, but every action pays
  Python's start-up, a refresh cannot report progress, and Windows shows a console window.
- **A separate GUI written in Python:** it still needs the API, and Python desktop packaging is the
  weakest option for an installer.

### A.2 API shape and dependencies (2026-10-30)

Approved by the project owner on 2026-10-30.

- Transport: HTTP and JSON on `127.0.0.1`, a random or given port, a per-launch token and a `Host`
  check against DNS rebinding.
- Dependencies: `starlette` and `uvicorn`; `httpx` as a development dependency for the in-process
  test client. FastAPI was the alternative; it was not chosen, so `openapi.json` is generated by a
  project script from the route table and the Pydantic document models.
- Testing: endpoint tests use the in-process test client, so they open no socket; `openapi.json` is
  checked in and compared like `schemas/`.

### A.3 Step 3.6 items dropped (2026-10-30)

Approved by the project owner on 2026-10-30, as part of the Light Mode decision in A.1.

- **Prefix matching for Analysis Run and refresh IDs** (Step 3.6 item 8): dropped. A GUI user never
  types an ID, and a CLI user copies the full ID that `runs list` and `refresh` print. The deferred
  note was deleted with this plan.
- **A CLI command to look up `docs/user/GLOSSARY.md` entries** (Step 3.6 item 9): dropped. The GUI
  links column headers to their glossary entries instead.

### A.4 Help content in the GUI (2026-10-30)

Approved by the project owner on 2026-10-30.

| Item | Decision |
| :--- | :--- |
| Owner | The engine owns every explanation and serves it through the API; the GUI bundles none. Rejected: the GUI copying the documents of the engine version it pins, which splits the label-to-term mapping between two repositories |
| Source | Markdown stays the source, with an enforced entry structure and a generated, drift-checked help bundle in the package. Rejected: TOML as the source with `GLOSSARY.md` generated, which is stricter but awkward for prose |
| Glossary split | Contributor terms move to a contributor glossary under `docs/project/`; only investor terms are served |
| Term references | Headline cells, strategies, run outcomes, calculation statuses, failure reason codes and selection fields each name a term; a conformance test enforces it, and "glossary terms" is a strategy edit site |
| Served documents | The glossary, the Beginner Guide, Finance Math and the strategy guides' explanatory sections. Installation, quick-start, usage, workspace, database, hardware and smoke-testing documents are not served |
| Links | Links to terms and served sections become in-app links; other links are optional further reading. A short definition depends on no link. Responses are Markdown; the GUI renders them with a sanitizing renderer |
| Sequence | API.5 and API.6, after API.4 and before 3.5.4; API.5 waits for 3.5.3e because 3.5.3d adds Piotroski's glossary entries |
| GUI behavior | A popup on hover or focus with the short definition, and a help panel on click with the full entry, linked terms and the longer guide. A run's own derivation stays in its Details view. The GUI repository decides the interaction details |

### A.5 Locale choice (2026-11-07)

Approved by the project owner on 2026-11-07. Recorded as
[H55](API_5_SLICE_PLAN.md#h55-locale-choice-2026-11-07) and implemented in API.6.

| Item | Decision |
| :--- | :--- |
| Request and response | Every endpoint that returns engine text honours `Accept-Language` and falls back to the engine's default locale. Every such response states the locale it used in `Content-Language` |
| Available locales | The API serves a list of available locales, each with its name in its own language. A GUI builds its language picker from that list. The list holds many locales by design, so it is not a single-value option |
| What follows the locale | Every piece of engine text the API serves: help content, term names, labels, status and outcome wording, and error messages. W42's rule identifiers and arguments are what make translated error messages possible |
| What does not | Raw values stay language-neutral (JSON numbers, ISO dates); a client formats them |
| Left to API.6 | Whether the list is its own endpoint or a field of an existing document, and whether the bundle has one file per locale |
| Not in API.5b2 | No locale field, argument or header handling |
