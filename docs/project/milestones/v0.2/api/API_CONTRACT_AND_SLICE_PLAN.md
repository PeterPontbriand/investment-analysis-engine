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
  - CLI behavior, text and `--json` output stay as they are, pinned by the existing CLI tests;
  - the managed quality gate after every slice, and the project owner's approval before the next
    slice starts.
- **Where the history lives:** decisions behind this plan are in
  [Appendix A](#appendix-a-decision-records-and-history).

## 2. Sequence and status

Implementation starts after Step 3.5's 3.5.3e merges, and 3.5.4 starts after API.6 merges
([milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status)).

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| API.0 | [Plan and milestone changes](#api0--plan-and-milestone-changes) | Complete | 2026-10-30 |
| API.1 | [Application layer: reading](#api1--application-layer-reading) | Next | |
| API.2 | [`ian serve` and the read endpoints](#api2--ian-serve-and-the-read-endpoints) | Planned | |
| API.3 | [Application layer: actions](#api3--application-layer-actions) | Planned | |
| API.4 | [Action endpoints and refresh jobs](#api4--action-endpoints-and-refresh-jobs) | Planned | |
| API.5 | [Help content](#api5--help-content) | Planned | |
| API.6 | [Term references and help endpoints](#api6--term-references-and-help-endpoints) | Planned | |

## 3. The slices

### API.0 — Plan and milestone changes

- **Problem:** the milestone plan excluded a GUI and deferred the HTTP API until Step 3.5 closed,
  while potential users do not try the engine because the command line is too hard.
- **Decision:** a separate GUI application uses a local HTTP API built here, before 3.5.4
  ([A.1](#a1-a-separate-gui-application-over-a-local-api-2026-10-30)).
- **Scope:** this plan; the milestone plan's sequence table, §1, §4.12 and exit criteria; the
  deferred delivery-surfaces note; the Discovery Workbook, Master Plan, Evidence Provider Roadmap,
  Architecture Guide §12 and v0.3 plan entries that named a GUI or the HTTP API; the removal of
  the prefix-matching note ([A.3](#a3-step-36-items-dropped-2026-10-30)).
- **Branch:** `docs/api-plan`.
- **Detail:** this document.

### API.1 — Application layer: reading

- **Problem:** each Typer command in `cli_workspace.py` parses, composes, works and prints in one
  function and fails through `typer.Exit`, and production composition lives in the `cli` unit at
  the top of the package layers, so nothing else can reuse it.
- **Decision:** a new unit, `application`, owns production composition and the operations. It
  returns the existing typed documents and domain objects, and raises typed failures that carry a
  `FailureReasonCode`. It knows no presentation and no strategy.
- **Scope:** the read operations — watchlist list and show, runs list, show (each presentation
  mode) and compare — and the composition they need; the CLI switched to them; the new unit's row
  in [Architecture §13](../../../ARCHITECTURE.md#13-module-boundaries).
- **Branch:** `feat/api-application-read`.
- **Detail:** ⚠ no slice plan yet

### API.2 — `ian serve` and the read endpoints

- **Problem:** a separate application cannot import the engine; it needs a stable, local,
  documented interface.
- **Decision:** a new unit, `api`, serves `/v1/` over HTTP with Starlette and uvicorn, bound to
  `127.0.0.1` only, behind a per-launch token and a `Host` check. Responses are the existing typed
  documents; a failure is a `FailureEnvelope`. A strategy is exposed generically, through its
  descriptor: headline cells, the replay projection text, its JSON document and its selection
  model's JSON Schema.
- **Scope:** `ian serve`; `/v1/info` (API and engine versions, and whether an SEC identity is
  configured, never its value); the read endpoints over API.1; `openapi.json`, generated by a
  script and compared by a test like `schemas/`; an endpoint test parametrized over `STRATEGIES`;
  the dependencies `starlette` and `uvicorn`, and `httpx` for tests (approved 2026-10-30, [A.2](#a2-api-shape-and-dependencies-2026-10-30)).
- **Branch:** `feat/api-serve-read`.
- **Detail:** ⚠ no slice plan yet

### API.3 — Application layer: actions

- **Problem:** creating and editing watchlists, analyzing a ticker and refreshing are still
  CLI-only, and a refresh reports nothing until it ends.
- **Decision:** the action operations move into `application` as API.1's did. A refresh accepts
  an observational progress callback, and keeps using the existing cancellation event. A selection
  is built from its model's fields, not from the CLI's flag set.
- **Scope:** watchlist create, rename, delete, add and remove; direct analysis of one ticker with
  chosen strategies, saved or not; refresh with progress; the CLI switched to each; a conformance
  check that every selection field has a description and a type the API's form schema supports.
- **Branch:** `feat/api-application-actions`.
- **Detail:** ⚠ no slice plan yet

### API.4 — Action endpoints and refresh jobs

- **Problem:** the GUI needs to start actions and follow a refresh that runs for minutes.
- **Decision:** action endpoints over API.3. A refresh runs as a job inside the `ian serve`
  process, one at a time, with a status endpoint the client polls and a stop endpoint. A job does
  not outlive the process.
- **Scope:** the action endpoints; the job status and stop endpoints; their `openapi.json` entries
  and tests.
- **Branch:** `feat/api-actions`.
- **Detail:** ⚠ no slice plan yet

### API.5 — Help content

- **Problem:** the glossary mixes investor and contributor terms, many entries have no first paragraph that
  stands alone, nothing gives a term a stable identifier, and the educational guides mix explanation with
  command-line instructions.
- **Decision:** Markdown stays the source. Each glossary entry has a stable `<a id>` anchor and a first paragraph
  that is its short definition; a checker enforces the structure. A generated help bundle ships inside the
  package and is compared in the gate like `schemas/` ([A.4](#a4-help-content-in-the-gui-2026-10-30)).
- **Scope:**
  - contributor terms move to a contributor glossary under `docs/project/`, which is not served;
  - every investor entry in `docs/user/GLOSSARY.md` gets an anchor and a short definition of at most two
    sentences and about 200 characters, with no link or code;
  - command-line sections of the served guides (Beginner Guide, Finance Math, strategy guides) carry an exclude
    marker;
  - the entry checker; the bundle generator and its drift test; the change `scripts/check_doc_links.py` needs
    to resolve `<a id>` anchors, if any.
- **Branch:** `docs/api-help-content`.
- **Detail:** ⚠ no slice plan yet

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
  - term references for all five strategies, Piotroski included.
- **Branch:** `feat/api-help`.
- **Detail:** ⚠ no slice plan yet

## 4. Out of scope

- A GUI, HTML pages or static web assets in this repository.
- Access from another computer, user accounts, or any authentication beyond the per-launch token.
- An MCP server and Parquet/Arrow export; they stay with the
  [deferred delivery-surfaces note](../deferred/DEFERRED_STANDARD_DELIVERY_SURFACES.md).
- Writing to the settings folder. The GUI passes `SEC_USER_AGENT` to the `ian serve` process it
  starts.
- Serving installation, quick-start, usage, workspace, database, hardware or smoke-testing documents; the GUI
  writes its own help on using the application.
- HTML in any help response, and contributor terms in the served help.
- Local-model synthesis endpoints; they belong to
  [Step 3.6](../IMPLEMENTATION_PLAN.md#412-step-36--light-mode-support).
- Database maintenance, provider health, evaluation and settings editing through the API.
- A change to any stored shape, formula, classification or CLI output.

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
