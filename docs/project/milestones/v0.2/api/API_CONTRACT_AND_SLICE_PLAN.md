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
    ([S3](API_2_SLICE_PLAN.md#s3-the-list-documents-are-versioned-objects-2026-11-03)), and the changes
    [A.7](#a7-structured-units-run-overview-and-command-free-database-messages-2026-11-13) records;
  - the managed quality gate after every slice, and the project owner's approval before the next
    slice starts.
- **Where the history lives:** decisions behind this plan are in
  [Appendix A](#appendix-a-decision-records-and-history).

## 2. Sequence and status

Implementation starts after Step 3.5's 3.5.3e merges and its slice 3.5.3e1c and its issues 207 and 210 are complete ([Step 3.5 order](../step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status)), and 3.5.5 starts after API.8 merges
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
| API.6a | [Term references](API_6_SLICE_PLAN.md#api6a--term-references) | Complete | 2026-11-07 |
| API.6b | [Help endpoints and locales](API_6_SLICE_PLAN.md#api6b--help-endpoints-and-locales) | Complete | 2026-11-08 |
| API.7 | [Refreshes list](#api7--refreshes-list) | Complete | 2026-11-10 |
| API.8 | [Structured units, run overview and command-free database messages](#api8--structured-units-run-overview-and-command-free-database-messages) | Complete | 2026-11-13 |
| API.9 | [A date as-of is served as written](#api9--a-date-as-of-is-served-as-written) | Complete | 2026-11-14 |
| API.10 | [Engine version, installation folder and commit](#api10--engine-version-installation-folder-and-commit) | Complete | 2026-11-14 |
| API.11 | [The runs comparison carries its refresh's summary](#api11--the-runs-comparison-carries-its-refreshs-summary) | Complete | 2026-11-15 |
| API.13 | [Form labels, error templates, refresh totals and provider names](#api13--form-labels-error-templates-refresh-totals-and-provider-names) | Complete | 2026-11-16 |
| API.12 | [The stored run envelope's outcome](#api12--the-stored-run-envelopes-outcome) | Complete | 2026-11-17 |
| API.14 | [Option terms and the duplicate message](#api14--option-terms-and-the-duplicate-message) | Complete | 2026-11-18 |
| API.15 | [Instrument profiles](#api15--instrument-profiles) | Complete | 2026-11-20 |
| API.16 | [Ticker check on adding entries, duplicate wording and provider statuses](#api16--ticker-check-on-adding-entries-duplicate-wording-and-provider-statuses) | Complete | 2026-11-20 |
| API.17 | [Listing venue for profiles identified by SEC EDGAR](#api17--listing-venue-for-profiles-identified-by-sec-edgar) | Complete | 2026-11-21 |
| API.18 | [Provider no-data is an unavailable input](#api18--provider-no-data-is-an-unavailable-input) | Complete | 2026-11-21 |
| API.19 | [Database errors after the readiness check](#api19--database-errors-after-the-readiness-check) | Complete | 2026-11-21 |
| API.22 | [Listing venue codes](#api22--listing-venue-codes) | Complete | 2026-11-23 |
| API.23 | [SEC EDGAR ticker coverage, explained and warned](#api23--sec-edgar-ticker-coverage-explained-and-warned) | Complete | 2026-11-26 |
| Issue 305 | [Investor glossary wording](#issue-305--investor-glossary-wording) | Complete | 2026-11-27 |
| Issue 310 | [Served guides in investor words](#issue-310--served-guides-in-investor-words) | Next | |
| API.24 | [Explain why a result has no number](#api24--explain-why-a-result-has-no-number) | Planned | |
| API.20 | [Sample workspace](#api20--sample-workspace) | Planned | |
| API.21 | [The SEC identity through the API](#api21--the-sec-identity-through-the-api) | Planned | |

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

### API.6a — Term references

- **Problem:** no API document says which term explains a label, status or code, so a GUI cannot explain what it
  shows, and a new strategy could add an unexplained column.
- **Decision:** every value of every closed code set in `openapi.json` (every `enum` with more than one value), and every
  label (headline cells, strategies and selection fields), names a glossary term. An explicit exemption list, with a reason
  for each entry, held `schema_version`, the headline cell `kind`, the replay text `mode` and the `method_id` path
  parameter when API.6a merged and has since gained the headline cell `unit` ([A.7](#a7-structured-units-run-overview-and-command-free-database-messages-2026-11-13), U4), and a test that walks `openapi.json` fails the gate on any value that has no term and is not exempt. A
  strategy document's field names and rendered text are explained through the strategy's term and its guide, not field by
  field ([T2](API_6_SLICE_PLAN.md#t2-what-must-name-a-term-2026-11-07)).
- **Scope:**
  - a term table beside each code set, including one mapping table each for run outcomes, calculation statuses and failure
    reason codes ([T3](API_6_SLICE_PLAN.md#t3-how-values-map-to-terms-2026-11-07),
    [T4](API_6_SLICE_PLAN.md#t4-where-the-tables-live-2026-11-07));
  - a `term` on each headline cell (an additive change; the runs-compare document's `schema_version` goes up and nothing
    stored changes) and on each strategy descriptor and in the strategies document;
  - a term in each selection field's metadata;
  - "glossary terms" as an edit site in `scripts/strategy_sites.toml`;
  - term references for every declared strategy;
  - an orphan-term check: every served term is referenced by a table, a headline cell, a strategy or a selection field, or
    linked from served content ([H9](API_5_SLICE_PLAN.md#h9-boundary-with-api6-2026-11-07)).
- **Branch:** `feat/api-term-references`.
- **Detail:**
  - It follows "Changing what every strategy provides" in [`STRATEGY_DEVELOPMENT.md`](../../../STRATEGY_DEVELOPMENT.md#changing-what-every-strategy-provides)
    for the "glossary terms" edit site, and records any file that section missed in its implementation record.
  - [API.6 slice plan](API_6_SLICE_PLAN.md#31-api6a-implementation-record)

### API.6b — Help endpoints and locales

- **Problem:** the help bundle is packaged but nothing serves it, a client cannot ask which term a value maps to, and
  engine text has one language.
- **Decision:** three read endpoints over the bundle, a references endpoint over the API.6a tables, a list of locales and
  `Accept-Language` negotiation ([T11](API_6_SLICE_PLAN.md#t11-api6b-help-endpoints-2026-11-07) to
  [T15](API_6_SLICE_PLAN.md#t15-docs-2026-11-07)).
- **Scope:**
  - `/v1/help`, `/v1/help/terms/{id}` and `/v1/help/documents/{id}`, which return Markdown, never HTML, and
    `/v1/help/references`;
  - only term ids and document ids are stable references: section ids and group ids are valid only within the bundle that
    carries them, and a client follows them but never stores them
    ([H54](API_5_SLICE_PLAN.md#h54-stable-references-across-locales-2026-11-07));
  - locale choice: every endpoint that returns engine text follows [A.5](#a5-locale-choice-2026-11-07).
- **Branch:** `feat/api-help`.
- **Detail:** [API.6 slice plan](API_6_SLICE_PLAN.md#33-api6b-implementation-record)

### API.7 — Refreshes list

- **Problem:** the desktop application needs a read-only screen of past refreshes, and the API cannot list them: a
  refresh is only the `analysis_runs` rows that share a `refresh_id`, and the watchlist it ran is stored only inside
  each row's `envelope_json`.
- **Decision:** migration `0006` copies the watchlist's id and name from the envelope into two nullable columns of
  `analysis_runs`, and a grouped, paged read over summary columns serves `GET /v1/refreshes` and `ian runs refreshes`
  through one application-layer function ([A.6](#a6-refreshes-list-2026-11-10)).
- **Scope:** migration `0006` with its backfill and index, and the matching `schema.py` change; the insert filling the
  two columns; the repository read; the application-layer function; `GET /v1/refreshes`, its versioned document, its
  JSON Schema and the regenerated `openapi.json`; `ian runs refreshes` with `--watchlist`, `--limit`, `--offset` and
  `--json`; term references for the new fields; `docs/user/API.md`, `docs/user/WORKSPACE.md` and one smoke-test step;
  tests.
- **Branch:** `feat/api-refreshes-list`.
- **Detail:** no separate slice plan; decisions in [A.6](#a6-refreshes-list-2026-11-10).

### API.8 — Structured units, run overview and command-free database messages

- **Problem:** the desktop application's next screens (comparison, run detail, saved runs) need numbers they can format
  without parsing English, one run's headline, one name for a run's outcome, and database failure messages that name
  no command.
- **Decision:** a headline cell's unit becomes a closed code set with a separate currency; `GET /v1/runs/{analysis_run_id}/overview`
  serves one run's headline through the builder the comparison uses, and both read a run's requested point in time from its
  envelope, refusing a run whose envelope cannot be read; a run's outcome is called `outcome` everywhere it was called
  `status`, refresh results included; a database failure's message states only the database's state, and the command line adds the
  target and the remedy ([A.7](#a7-structured-units-run-overview-and-command-free-database-messages-2026-11-13)).
- **Scope:** `CellUnit` and the cell's `currency` in `reporting/headline.py`, the compare document and its JSON Schema;
  the term-reference exemption for `CellUnit`; `DatabaseReadinessError`'s message and the command line's form of it; the
  run overview document, its application-layer function, route, JSON Schema and the regenerated `openapi.json`; the
  `status` to `outcome` rename in the runs-list document, the `/v1/runs` query, `ian runs list` and the refresh results (the
  refresh summary and refresh job documents' versions go up), and the plain wording for a job that stopped because of an
  unexpected problem; `docs/user/API.md`,
  `docs/user/USAGE.md`, `docs/user/WORKSPACE.md` and `docs/user/SMOKE_TESTING.md`; tests.
- **Branch:** `feat/api-run-overview`.
- **Detail:** no separate slice plan; decisions in [A.7](#a7-structured-units-run-overview-and-command-free-database-messages-2026-11-13).

### API.9 — A date as-of is served as written

- **Problem:** a selection given a date as-of (`--as-of 2025-12-31`) is stored as the last instant of that day in UTC and
  was served as that instant, so a client could not tell a date from a time and showed one the user never chose
  ("Dec 31, 2025, 6:59 PM" in Toronto).
- **Decision:** stored selections do not change. An end-of-day UTC instant is served as its date wherever a document
  carries an as-of boundary, and any other timestamp is served as given; the rule has one definition, and the affected
  documents' `schema_version` goes up ([A.7](#a7-structured-units-run-overview-and-command-free-database-messages-2026-11-13),
  U13 to U18).
- **Scope:** the shared end-of-day predicate and `DocumentAsOf` in `reporting/documents/timestamp.py`, used by
  `format_as_of`; the strategy documents' `requested_as_of`, `effective_as_of` and resolved-input `as_of`; the watchlist
  documents' selection `as_of`; the run overview's and the comparison's `requested_as_of`; the raised versions, the
  regenerated JSON Schemas and `openapi.json`; `docs/user/API.md` and `docs/user/USAGE.md`; tests.
- **Branch:** `fix/as-of-served-as-written`.
- **Detail:** no separate slice plan; decisions in [A.7](#a7-structured-units-run-overview-and-command-free-database-messages-2026-11-13).

### API.10 — Engine version, installation folder and commit

- **Problem:** nothing the user can run says which installation the `ian` command executes, which version it is or which
  commit it is at, so a smoke-test record and a support report cannot name the code that produced them.
- **Decision:** a new command, `ian about`, with `--json`, reports the engine's version, the installation folder (the
  source checkout the code runs from, or none for a wheel) and that folder's Git commit with whether it has uncommitted
  changes; a fact it cannot establish is reported as absent and the command always exits 0 ([A.8](#a8-engine-version-installation-folder-and-commit-2026-11-14), D1 to D7).
- **Scope:** `INSTALLATION_FOLDER` in `core/package_root.py`; `cli_about.py`; the `AboutDocument` in
  `reporting/documents/about.py`, its registration and `schemas/about.schema.json`; the command's entry in the
  non-strategy command list of the conformance script; `scripts/check_installed_package.py`; `docs/user/USAGE.md`,
  `docs/user/INSTALLATION.md` and `docs/user/SMOKE_TESTING.md`; tests. The launcher, `scripts/install_command.py`, the
  API, `/v1/info` and `openapi.json` do not change.
- **Branch:** `feat/ian-about`.
- **Detail:** no separate slice plan; decisions in [A.8](#a8-engine-version-installation-folder-and-commit-2026-11-14).

### API.11 — The runs comparison carries its refresh's summary

- **Problem:** the refresh comparison screen has to say which refresh it shows, when it ran and how its runs ended, but
  the comparison document carries no completion time and no outcome count, and its heading in `ian runs compare` has the
  same gap; the refreshes list already carries both.
- **Decision:** the comparison document gains `first_completed_at`, `last_completed_at`, `run_count` and `outcome_counts`,
  named, typed and described as the refreshes list's item has them, and its `schema_version` goes from 6 to 7. Both
  documents read one SQL summary, and the comparison's watchlist comes from it, so it shows even when no run's envelope can
  be read. The `ian runs compare` heading names the last completion. A run's outcome is named `outcome` in the in-memory
  run records too ([A.9](#a9-runs-comparison-carries-its-refreshs-summary-2026-11-15), C1 to C7).
- **Scope:** `workspace_documents/runs_compare.py` and `refreshes.py`; the summary select and the single-refresh read in
  `workspace/repositories/analysis_runs.py`; `compare_refresh_runs` in `application/runs.py`; the `status` to `outcome`
  rename on `StoredRefreshRun`, `StoredRun`, `AnalysisRunSummary` and `RunQuery`; regenerated
  `schemas/runs-compare.schema.json` and `schemas/openapi.json`; `docs/user/API.md` and `docs/user/WORKSPACE.md`; tests.
  The refreshes list, the stored envelope and the database do not change.
- **Branch:** `feat/api-compare-summary`.
- **Detail:** no separate slice plan; decisions in [A.9](#a9-runs-comparison-carries-its-refreshs-summary-2026-11-15).

### API.13 — Form labels, error templates, refresh totals and provider names

- **Problem:** a client building a form from the selection schemas has no label for a field, only its name; a rule's
  message names the command line's options, so a client cannot say it in its own words; a refresh job reports no total;
  a client cannot name a data provider or show the entry a refused refresh was refused for
  ([issue 267](https://github.com/PeterPontbriand/investment-analysis-engine/issues/267)).
- **Decision:** every selection field declares a JSON Schema `title` as its label, a field having one label in every
  strategy and the conformance check enforcing it; `errors[].template` carries the message with its placeholders;
  a `stored_selection_unreadable` failure carries `unreadable`; the refresh totals gain `total`; `/v1/info` lists
  `providers`. `FailureEnvelope` goes from 13 to 14, `RefreshJobDocument` from 2 to 3 and `InfoDocument` from 2 to 3
  ([A.10](#a10-form-labels-error-templates-refresh-totals-and-provider-names-2026-11-16), N1 to N11).
- **Scope:** the five strategies' selections, the specimen and the generator templates; `application/parameters.py`,
  `core/operator_errors.py`, `core/failure_classification.py`, `reporting/failure_envelope.py` and the failure and shared
  document parts; `api/documents.py` and `api/refresh_documents.py`; the selection-options conformance check; regenerated
  schemas and `openapi.json`; `docs/user/API.md` and `docs/project/STRATEGY_DEVELOPMENT.md`; tests.
- **Branch:** `feat/api-form-labels`.
- **Detail:** no separate slice plan; decisions in [A.10](#a10-form-labels-error-templates-refresh-totals-and-provider-names-2026-11-16).

### API.12 — The stored run envelope's outcome

- **Problem:** the stored envelope model `AnalysisRun` still named a run's outcome `status`, the one place left
  ([issue 264](https://github.com/PeterPontbriand/investment-analysis-engine/issues/264)).
- **Decision:** `AnalysisRun.status` becomes `outcome` and `run_schema_version` goes from 3 to 4, with no migration:
  version 3 runs stay in the database and are refused by version, as `docs/user/WORKSPACE.md` says. The repository reads
  the row's version column before it validates an envelope, so an older run is refused as `unsupported_run_version` and
  not as malformed. `native_status` and `native_reason` keep their names. The supported run and projection versions are
  each one constant, typed from a `Literal` alias
  ([A.11](#a11-the-stored-run-envelopes-outcome-2026-11-17), D1 to D6).
- **Scope:** `AnalysisRun` and the two version constants in `workspace/runs.py`; `workspace/codecs.py`;
  `workspace/repositories/analysis_runs.py`; `workspace/refresh.py`, `workspace/execution.py`, `application/refresh.py`
  and `application/runs.py`; `workspace_documents/runs_compare.py` and `workspace_documents/run_replay.py`; the test
  helper `refresh_run(outcome=...)` and the tests and fixtures that build or store envelopes; this plan and
  `docs/project/STRATEGY_DEVELOPMENT.md`.
- **Branch:** `chore/run-envelope-outcome`.
- **Detail:** no separate slice plan; decisions in [A.11](#a11-the-stored-run-envelopes-outcome-2026-11-17).

### API.14 — Option terms and the duplicate message

- **Problem:** the desktop application's GUI.3b cannot name the options of a drop-down list, because every option of a
  selection field pointed at the same glossary term, and the duplicate-entry message shows a raw method code instead of
  the strategy's name.
- **Decision:** each option of a selection field's closed set names its own glossary term through the strategy's code-term
  tables, one table for each code set, shared by both of its component names; the field keeps its own `x-term` and the
  schemas gain no option labels. The `entries.duplicate` rule names the strategy by its label, in one of two message
  templates, and its arguments become `ticker` and `strategy`; `FailureEnvelope` goes from 14 to 15
  ([A.12](#a12-option-terms-and-the-duplicate-message-2026-11-18), O1 to O12).
- **Scope:** `strategies/fcf_growth/vocabulary.py` and `strategies/graham_growth/vocabulary.py`;
  `application/watchlists.py` and `application/refresh.py`; the failure document's version; ten glossary entries
  (`docs/user/GLOSSARY.md`) and the overview entries that list them; the help bundle, `schemas/openapi.json` and
  `schemas/failure.schema.json`; `docs/user/API.md`, `docs/user/USAGE.md`, `docs/user/WORKSPACE.md`,
  `docs/project/STRATEGY_DEVELOPMENT.md` and `docs/project/PROVIDER_DEBUGGING.md`; this plan; tests.
- **Branch:** `feat/api-option-terms`.
- **Detail:** no separate slice plan; decisions in [A.12](#a12-option-terms-and-the-duplicate-message-2026-11-18).

### API.15 — Instrument profiles

- **Problem:** the desktop application cannot tell a reader which company a ticker is, except on a saved run's detail
  screen. The engine keeps a durable instrument profile for every ticker it has analyzed, but serves it nowhere; desktop
  issue #19 asks for a ticker's details wherever a ticker appears in a table or a heading.
- **Decision:** a read of the stored profile that never contacts a provider, a separate live lookup, and one document
  for both; a run's overview carries the identity the run retained; the stored profile gains the quote currency, under
  one payload version bump ([A.13](#a13-instrument-profiles-2026-11-20), I1 to I11). The new failure code raises
  `FailureEnvelope` from 15 to 16, the only document that can carry it
  ([J44](API_4_SLICE_PLAN.md#j44-a-new-reason-code-bumps-the-documents-that-can-carry-it-2026-11-07)).
- **Scope:** `GET /v1/instrument-profiles/{ticker}` and `POST /v1/instrument-profiles/{ticker}/lookup`; the
  `InstrumentProfileDocument`; the `instrument_profile_not_found` failure code with its glossary entry, and glossary entries
  for the three instrument kinds; `ian instrument show` with `--lookup` and `--json`; `security_identity` on the run
  overview (version 2 to 3); `quote_currency` on the stored profile (`INSTRUMENT_PROFILE_SCHEMA_VERSION` 3 to 4); the
  application-layer operations the CLI and the API share; `docs/user/API.md`, `docs/user/USAGE.md` and
  `docs/user/DATABASE.md`; the help bundle, the schemas and `schemas/openapi.json`; this plan; tests.
- **Branch:** `feat/api-instrument-profiles`.
- **Detail:** no separate slice plan; decisions in [A.13](#a13-instrument-profiles-2026-11-20).

### API.16 — Ticker check on adding entries, duplicate wording and provider statuses

- **Problem:** adding a watchlist entry accepts any non-blank ticker, so a mistyped ticker fails on every refresh until
  someone notices (engine issue 269). The duplicate-entry message says "with an equal selection", which does not tell a
  person what to change (engine issue 275). The `provider_*` failure codes and `configuration_error` answer HTTP 500 on
  every endpoint, so a client cannot tell a provider problem from a server fault by status (engine issue 269's comment).
- **Decision:** adding entries looks each distinct ticker up once, after the entries are written, and answers a new
  document that carries the watchlist and one warning for each ticker that could not be confirmed; nothing is ever
  refused for it. The two duplicate templates name the as-of date and the options. The provider failure codes and
  `configuration_error` get their own statuses ([A.14](#a14-ticker-check-on-adding-entries-duplicate-wording-and-provider-statuses-2026-11-20),
  P1 to P12).
- **Scope:** `application/watchlists.py` and a new application operation for the check, which uses
  `application/instrument_profiles.py`; the storage-failure classifier of `data/repositories/readiness.py`, made public;
  `POST /v1/watchlists/{watchlist_id}/entries` and
  `ian watchlist add-selection`, with the new `EntriesAddedDocument` and its schema; the two warning codes with glossary
  entries served through the term references; `STATUS_BY_CODE` and the documented responses of every endpoint it
  reaches; the `entries` body description in `api/request_bodies.py`; `schemas/openapi.json`; `docs/user/API.md`,
  `docs/user/USAGE.md` and `docs/user/WORKSPACE.md`; this plan; tests.
- **Branch:** `feat/api-entry-check`.
- **Detail:** no separate slice plan; decisions in [A.14](#a14-ticker-check-on-adding-entries-duplicate-wording-and-provider-statuses-2026-11-20).

### API.17 — Listing venue for profiles identified by SEC EDGAR

- **Problem:** an instrument profile identified by SEC EDGAR has a null `listing_venue`, because the ticker file the engine
  reads (`company_tickers.json`) carries no exchange (engine issue 282).
- **Decision:** the engine reads SEC's `company_tickers_exchange.json` as its one SEC ticker file, so the venue comes from
  the same provider and request as the rest of the identity. It is served as SEC writes it; a missing exchange stays null;
  explaining venues to users is engine issue 284 ([A.15](#a15-listing-venue-for-profiles-identified-by-sec-edgar-2026-11-21),
  L1 to L8).
- **Scope:** `data/sec_edgar/financial_facts.py` (the file URL, its parsing and the identity's `listing_venue`),
  `data/provider_checks.py` (the SEC check's URL and fields), the evaluation fixtures that serve the file, the three
  documents that name the file (`ARCHITECTURE.md`, `PROVIDER_DEBUGGING.md`, `EVIDENCE_PROVIDER_ROADMAP.md`), this plan;
  tests.
- **Branch:** `feat/api-sec-listing-venue`.
- **Detail:** no separate slice plan; decisions in [A.15](#a15-listing-venue-for-profiles-identified-by-sec-edgar-2026-11-21).

### API.18 — Provider no-data is an unavailable input

- **Problem:** a run for an unknown ticker is recorded as `provider_error` and the outcome `failed`, although the provider
  answered correctly and has nothing for the ticker (engine issue 281). A client cannot tell it from a provider that is
  down. The SEC-backed strategies reported such a ticker as a missing annual filing, with no provider failure at all.
- **Decision:** a run whose failed required inputs are all of kind `no_data` is `input_unavailable`, outcome
  `unavailable`, with the new reason code `provider_no_data`, a `provider_failure` element, a message that names the
  provider, and a null failure code. The provider check still runs. A ticker absent from SEC's ticker list stops a run of
  a strategy that needs SEC EDGAR the same way ([A.16](#a16-provider-no-data-is-an-unavailable-input-2026-11-21), E1 to
  E13).
- **Scope:** the one function in `core/failure_classification.py` from a recorded failure to a status, and the rule every
  validator applies; `ReasonCode.PROVIDER_NO_DATA`; `reporting/provider_messages.py`; the five strategies' status, code and
  message; `workspace/capture.py`, `workspace/refresh.py` and `workspace_documents/refresh.py`; the shared document model;
  the SEC adapter's missing-CIK handling (`data/sec_edgar/financial_facts.py`) and the typed fields that carry a failure's
  message and unlisted ticker (`data/base_client.py`, `data/financial/facts.py`, `data/provider_failure.py`); each
  strategy's document and result versions; the schemas, `openapi.json` and the help bundle; `docs/user/USAGE.md`,
  `WORKSPACE.md`, `GLOSSARY.md` and `FINANCE_MATH.md`; the note at PH.2's D13; this plan; tests.
- **Branch:** `fix/provider-no-data-unavailable`.
- **Detail:** no separate slice plan; decisions in [A.16](#a16-provider-no-data-is-an-unavailable-input-2026-11-21).

### API.19 — Database errors after the readiness check

- **Problem:** a raw `sqlite3` or SQLAlchemy error raised after the readiness check has passed, such as a database locked
  by another process or an I/O failure, reaches a user as `execution_error` (HTTP 500) with a generic message, instead of
  the precise database code the readiness check gives (engine issue 279). API.16 handled it only inside the ticker check
  on adding entries.
- **Decision:** `SQLiteDatabase` itself re-raises a storage error, raised while it opens a connection or inside a
  `transaction()` or `read()` scope, as the typed database error that readiness already raises, so every repository, the
  command line, the API, refresh jobs and the instrument-profile cache are covered without changes of their own. The
  error type is renamed `DatabaseError` and its reasons `DatabaseReason`. Only SQLite errors of the storage families
  are converted; any other error stays raw and stays an `execution_error`. The `database_busy` message no longer
  mentions readiness. A storage error while one refresh entry is analyzed or saved is that entry's failure, with its
  precise code ([A.17](#a17-database-errors-after-the-readiness-check-2026-11-21), K1 to K8).
- **Scope:** `data/repositories/sqlite.py`; a new `data/repositories/database_errors.py` that holds `DatabaseError`,
  `DatabaseReason`, their messages and `storage_reason` (moved out of `readiness.py`, which `sqlite.py` cannot import);
  `data/repositories/readiness.py`, `application/entry_check.py`, `cli_support.py`, `cli_database.py` and
  `reporting/failure_envelope.py`, for the rename and the one rule; the application docstrings that name the type;
  `docs/user/API.md` and `docs/user/DATABASE.md`; this plan; tests. `openapi.json` and the JSON Schemas do not change.
- **Branch:** `fix/database-storage-errors`.
- **Detail:** no separate slice plan; decisions in [A.17](#a17-database-errors-after-the-readiness-check-2026-11-21).

### API.20 — Sample workspace

- **Problem:** a new user starts with an empty database, so every screen of the desktop application and every listing
  command is empty until the user has learned enough to fill it. Runs are append-only and cannot be deleted
  ([Architecture](../../../ARCHITECTURE.md)), so sample rows cannot be added to the user's own database and taken out
  again.
- **Decision:** the engine keeps a separate sample workspace beside the user's own, built on the user's machine from a
  versioned sample definition the engine owns. The engine never works on the pristine sample: opening the sample
  workspace always makes a fresh working copy, and switching back discards it. The engine alone controls where the
  pristine sample and the copy are stored; no document or output names a path. The CLI and the API offer the same
  operations, the active workspace is engine-wide, and every interface makes it unmistakable that the sample is in use
  and that anything added there is not kept ([A.18](#a18-sample-workspace-and-the-sec-identity-through-the-api-2026-11-22), W1 to W10).
- **Scope:** the sample definition; the application operations to build, remove, open and leave the sample workspace;
  `GET` and `POST /v1/workspace`, `POST` and `DELETE /v1/sample`; `ian workspace show`, `ian workspace use sample`,
  `ian workspace use mine`, `ian sample build` and `ian sample remove`; the `IAN-Workspace` response header and its field
  in `GET /v1/info`; the standard-error notice of the command line; a "Sample workspace" glossary term; a migration for
  the active-workspace record; `openapi.json`, the JSON Schemas, `docs/user/API.md`, `docs/user/WORKSPACE.md` and
  `docs/user/DATABASE.md`; tests.
- **Branch:** `feat/sample-workspace`.
- **Detail:** ⚠ no slice plan yet. The slice plan fixes the sample's entries (W5), the storage layout under
  `data/repositories/`, the endpoint documents and the failure codes before implementation starts.

### API.21 — The SEC identity through the API

- **Problem:** the desktop application's plan passes the user's SEC identity to `ian serve` as the `SEC_USER_AGENT`
  environment variable when it starts the server. That works only while the application and the engine run on the same
  computer, and it is a setting the command line sets one way and the API cannot set at all.
- **Decision:** the engine accepts the SEC identity through an API operation and a matching `ian` command, and keeps
  it in its own storage, never in the settings folder ([A.18](#a18-sample-workspace-and-the-sec-identity-through-the-api-2026-11-22), W11 and W12).
- **Scope:** the application operation, its endpoint and command, the stored setting and its migration, the reading order of W12 and the
  field that names the source in `GET /v1/info` and `ian about`; `openapi.json`,
  `docs/user/API.md` and `docs/user/INSTALLATION.md`; tests.
- **Branch:** `feat/sec-identity-setting`.
- **Detail:** ⚠ no slice plan yet. The reading order is W12.

### API.22 — Listing venue codes

- **Problem:** `listing_venue` is plain text as each of three sources wrote it (SEC's ticker file, Yahoo, and a filing's
  cover), and many users cannot understand values such as `NYSE`, `NasdaqGS` or `CboeBZX` (engine issue 284).
- **Decision:** every venue the engine serves becomes a part `{code, provider_value}` that is null exactly when the
  source gave no venue. The code comes from one reviewed table per source, each value backed by a captured specimen,
  and is worked out each time a document is built, so nothing stored changes. Each code and the field itself have a
  glossary term, and every text rendering writes the term's name with the provider's wording in parentheses when it
  differs ([A.19](#a19-listing-venue-codes-2026-11-23), V1 to V19).
- **Scope:** `data/listing_venue.py` (the codes, the three tables, the one reading function, the glossary term table and
  the live check's exchange test); `ListingVenuePart` and the venue parts in `reporting/documents/shared_parts.py`;
  the instrument profile document, the run overview and every strategy document's identity part and share-unit
  provenance, each with a raised `schema_version` (the specimen strategy's fixture included); `reporting/listing_venue_text.py` and the places that print a venue
  (`evidence_presentation.py`, `valuation_presentation.py`, the instrument profile text and the FCF Growth and Momentum
  presenters); the term-reference registry; the `help` import of `reporting` in
  [Architecture §13](../../../ARCHITECTURE.md#13-module-boundaries); the glossary terms and the help bundle; the JSON
  Schemas and `openapi.json`; `docs/user/API.md`, `docs/user/USAGE.md` and the
  [mapping record](API_22_LISTING_VENUE_MAPPING_RECORD.md); the live SEC check; this plan; tests.
- **Branch:** `feat/api-listing-venue-codes`.
- **Detail:** no separate slice plan; decisions in [A.19](#a19-listing-venue-codes-2026-11-23), evidence in the
  [mapping record](API_22_LISTING_VENUE_MAPPING_RECORD.md).

### API.23 — SEC EDGAR ticker coverage, explained and warned

- **Problem:** a ticker that is not in SEC EDGAR's ticker list, such as NTR.TO (Nutrien on the Toronto Stock Exchange),
  makes the strategies that read SEC filings unavailable with no explanation of why, and Yahoo's "Toronto" venue has no
  named code (engine issue 302).
- **Decision:** the run's reason names the input and says SEC lists companies under US ticker symbols only; adding an
  entry gives a new warning, `ticker_not_in_sec_list`; each strategy declares whether a selection reads SEC EDGAR; four
  Canadian listing venues get codes and glossary entries; the plans record the Canadian-listings work package and the
  engine order ([A.20](#a20-sec-edgar-ticker-coverage-explained-and-warned-2026-11-25), C1 to C11).
- **Scope:** `reporting/provider_messages.py`; `core/entry_warnings.py`; `application/entry_check.py`; one method of the
  SEC financial-facts adapter; `data/listing_venue.py` and its mapping record; `strategy_wiring.py`, each strategy's
  `selection.py` and the strategy generator, its conformance check and the specimen; the regenerated help bundle and
  schemas; the glossary and `docs/user/` documents that quote the old text or list the codes; this plan, the
  implementation plan's `CAN` entry and Step 3.5's order line; tests.
- **Branch:** `feat/api-sec-coverage`.
- **Detail:** this slice's spec: [specs/api-23.md](specs/api-23.md); decisions in
  [A.20](#a20-sec-edgar-ticker-coverage-explained-and-warned-2026-11-25).

### API.24 — Explain why a result has no number

- **Problem:** a result without a number gives a short reason that does not say what the method needed, what was
  found, why a guessed number would mislead, or what the investor can do (engine issue 306).
- **Decision:** every result without a number gets an explanation built from the stored structured fields
  ([A.21](#a21-explain-why-a-result-has-no-number-2026-11-25), C23 to C30).
- **Scope:** every strategy's documents and text, the glossary, tests.
- **Branch:** `feat/api-no-answer-explanations`.
- **Detail:** ⚠ no slice plan yet.

### Issue 305 — Investor glossary wording

- **Problem:** investor glossary entries speak about this project's machinery ("the engine", "the provider"),
  the data-source status terms are named after it, and the Nasdaq entry explains how venue text is matched rather
  than what the tiers mean (engine issue 305).
- **Decision:** investor entries use "this application" and "data source"; eight status term names change with
  their ids kept; the Nasdaq tiers are explained qualitatively; the help-content check refuses "engine" and
  "provider" in investor entries ([A.22](#a22-investor-glossary-wording-2026-11-27), G1 to G10).
- **Scope:** the user glossary's investor section, one contributor glossary entry, the glossary rules in the
  project README, `scripts/check_help_content.py` and its tests, the regenerated help bundle.
- **Branch:** `docs/investor-glossary-wording`.
- **Detail:** this unit's spec: [specs/issue-305.md](specs/issue-305.md); decisions in
  [A.22](#a22-investor-glossary-wording-2026-11-27).

### Issue 310 — Served guides in investor words

- **Problem:** the served guides (the Beginner Guide, Finance Math and the strategy guides) speak about this
  project's machinery ("Investment Analysis Engine", "the engine", "the provider", "the Yahoo adapter", "the
  resolver"), and links to renamed glossary terms still show the old names (engine issue 310).
- **Decision:** served sections use "this application" and "data source", wording only in Finance Math; the FCF
  Growth split-adjustment output label is renamed to match; the help-content check refuses "engine" and "provider"
  in every served section ([A.23](#a23-served-guides-in-investor-words-2026-11-27), H1 to H10).
- **Scope:** the served sections of the Beginner Guide, Finance Math and the strategy guides, one presenter label
  and its test, the served-documents rules in the project README, `scripts/check_help_content.py` and its tests, the
  regenerated help bundle.
- **Branch:** `docs/investor-guide-wording`.
- **Detail:** this unit's spec: [specs/issue-310.md](specs/issue-310.md); decisions in
  [A.23](#a23-served-guides-in-investor-words-2026-11-27).

## 4. Out of scope

- A GUI, HTML pages or static web assets in this repository.
- Access from another computer, user accounts, or any authentication beyond the per-launch token.
- An MCP server and Parquet/Arrow export; they stay with the
  [deferred delivery-surfaces note](../deferred/DEFERRED_STANDARD_DELIVERY_SURFACES.md).
- Writing to the settings folder. API.21 keeps the SEC identity in the engine's own storage instead
  ([A.18](#a18-sample-workspace-and-the-sec-identity-through-the-api-2026-11-22), W11).
- Serving installation, quick-start, usage, workspace, database, hardware or smoke-testing documents, or
  `docs/user/API.md`, the client authors' reference written in API.2b
  ([S5](API_2_SLICE_PLAN.md#s5-the-client-reference-is-docsuserapimd-2026-11-03)); the GUI writes its own help on
  using the application.
- HTML in any help response, and contributor terms in the served help.
- Local-model synthesis endpoints; they belong to
  [Step 3.6](../IMPLEMENTATION_PLAN.md#412-step-36--light-mode-support).
- Database maintenance, provider health, evaluation and settings editing through the API, except the sample workspace (API.20) and the SEC identity (API.21).
- A change to any stored shape, formula or classification, or to existing CLI output, except the two list documents
  of [S3](API_2_SLICE_PLAN.md#s3-the-list-documents-are-versioned-objects-2026-11-03), the two summary columns that
  API.7's migration adds to `analysis_runs` ([A.6](#a6-refreshes-list-2026-11-10), L3), the changes API.8 records
  ([A.7](#a7-structured-units-run-overview-and-command-free-database-messages-2026-11-13), U3 and U9) and the stored
  run envelope's `outcome` under `run_schema_version` 4 that API.12 records
  ([A.11](#a11-the-stored-run-envelopes-outcome-2026-11-17), D1).
- A command-line counterpart of the run overview. The command line shows a run through `runs show`, whose concise text
  already leads with the headline values; the overview exists for clients that lay out their own display
  ([A.7](#a7-structured-units-run-overview-and-command-free-database-messages-2026-11-13), U10).
- A sector or an industry for an instrument. Several competing classification schemes exist, and choosing among them is
  a portfolio-organization judgement that belongs to the
  [future portfolio application](../../../MASTER_PLAN.md#future-portfolio-application), outside the engine
  ([A.13](#a13-instrument-profiles-2026-11-20), I9).

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
- From the first engine release that includes the API, a change inside `/v1` only adds, and a breaking change is a new
  version path. Until then a slice may make an incompatible change when it records it and raises the affected document's
  `schema_version` ([A.7](#a7-structured-units-run-overview-and-command-free-database-messages-2026-11-13), U2).
- API.6a: every value of every closed code set the API returns, and every headline cell, strategy and selection field, names a
  term, except the exemptions listed in `api/term_references.py`, and every named term exists in the help bundle; the gate
  fails otherwise.
- API.6b: every glossary term and served section is reachable through the help endpoints, and no served text contains an
  `ian` command.
- The help bundle is regenerated and compared in the managed gate; a drift fails it.
- API.7: `GET /v1/refreshes` and `ian runs refreshes` return the same refreshes through one application-layer function,
  newest first by `last_completed_at` then `refresh_id` descending, paged by `limit` and `offset` with `has_more`, filtered
  by `watchlist_id` as L8 says, with counts of stored runs only; the read uses summary columns and never decodes an
  envelope; migration `0006` upgrades with its backfill (a watchlist run, a list-of-entries run and an unreadable
  envelope) and downgrades; the document's JSON Schema is in `schemas/` and `openapi.json` is regenerated, both compared
  in the managed gate; the new fields pass the API.6a conformance test; `docs/user/API.md`, `docs/user/WORKSPACE.md` and
  the smoke test describe it; existing CLI output is unchanged.
- API.8: a headline cell's `unit` is one of the `CellUnit` values and its `currency` is an ISO 4217 code only for a
  per-share cell (null when the run recorded none), a text cell has neither, and `HeadlineCell` enforces it; the compare
  document's `schema_version` is raised and the CLI's text comparison table is unchanged; `DatabaseReadinessError`'s
  message names no `ian` command, option, environment variable or path for any readiness reason, and the command line's
  text and `--json` output of the same failures are unchanged; `GET /v1/runs/{analysis_run_id}/overview` serves the
  overview document through one application-layer function and one shared headline builder, for every declared strategy
  and for a strategy no longer declared, and fails as `GET /v1/runs/{analysis_run_id}` does; its JSON Schema is in
  `schemas/` and `openapi.json` is regenerated, both compared in the managed gate; the new fields pass the API.6a
  conformance test; a run's outcome is `outcome` in the runs-list document, the `/v1/runs` query and `ian runs list
  --outcome`, and `status` is no longer accepted there; a refresh job's run outcome is `outcome` in the refresh summary
  (version 4) and the refresh job document (version 2); a run's `requested_as_of` is read from its envelope for every run, so
  null always means now, in the overview and the comparison alike, and a run whose envelope cannot be read is refused with
  `invalid_stored_run`, whether or not its strategy is still declared; `docs/user/API.md`, `docs/user/WORKSPACE.md` and
  `docs/user/SMOKE_TESTING.md` describe it.
- API.10: `ian about` is listed in `ian --help` and prints the three lines D6 gives for a clean checkout, a checkout with
  uncommitted changes (tracked, or untracked and not ignored), a folder that is not a Git checkout (including one inside
  another repository), a machine without Git and a package installation; `ian about --json` writes the `about` document
  (`schema_version` 1), whose JSON Schema is in `schemas/` and compared in the managed gate; the command exits 0 in every
  one of these cases and stops with exit 2 and one message on invalid settings, as every command does; the installed
  wheel reports the version in `pyproject.toml` with a null installation folder, commit and `uncommitted_changes`;
  `/v1/info` and `openapi.json` are unchanged; `docs/user/USAGE.md`, `docs/user/INSTALLATION.md` and
  `docs/user/SMOKE_TESTING.md` describe it.
- API.13: every served selection schema, nested fields included, carries the labels of A.10 N3 as `title`, and the
  conformance check reports a field without one and a field name titled differently in two strategies; `errors[].template`
  filled gives `message` for a single error, a list, a nested selection field and a watchlist add, and an
  `ActionParameterError` refuses an argument named like a parameter and an undeclared placeholder; `unreadable` is set
  exactly for a `stored_selection_unreadable` failure that names its entry, through the API and `--json`; `totals.total`
  equals `admitted + remaining`; `/v1/info` lists `providers` and every provider check identifier has a display name;
  versions 14, 3 and 3; the schemas, `openapi.json` and help snapshots pass their checks; `docs/user/API.md` describes it.
- API.14: `GET /v1/help/references` gives each option of the closed sets of the FCF Growth and Graham Growth selection
  fields its own term, none of them the field's own `x-term`, and a test requires this of every declared strategy;
  `entries.duplicate` names the strategy by its label in two templates, with the arguments `ticker` and `strategy`, in
  the API and on the command line; `FailureEnvelope` is version 15; the help bundle, `openapi.json` and
  `failure.schema.json` pass their drift checks; `docs/user/GLOSSARY.md`, `docs/user/API.md` and `docs/user/USAGE.md`
  describe it.
- API.15: `GET /v1/instrument-profiles/{ticker}` serves the ticker's current stored profile, however old, with no provider
  call, and fails with `instrument_profile_not_found` (404) when there is none, a profile stored under another payload
  version included; `POST /v1/instrument-profiles/{ticker}/lookup` resolves through the cached resolver as an analysis
  does, stores only an identity-anchored result, serves the same document, and fails with the existing `provider_*`
  codes when no provider identifies the ticker; `ian instrument show` prints the same document, as text or `--json`,
  through the same application-layer operations; the run overview is version 3 and carries the run's own
  `security_identity`; `INSTRUMENT_PROFILE_SCHEMA_VERSION` is 4; every instrument kind value has a glossary term; the
  help bundle, the schemas and `openapi.json` pass their drift checks; `docs/user/API.md`, `docs/user/USAGE.md` and
  `docs/user/DATABASE.md` describe it; `FailureEnvelope` is version 16, and the strategy documents, the database
  maintenance report and the refresh summary are regenerated without a bump, as J44 says.
- API.16: `POST /v1/watchlists/{watchlist_id}/entries` and `ian watchlist add-selection --json` answer an
  `EntriesAddedDocument` (`schema_version` 1) with the unchanged watchlist document and a `warnings` list, empty when
  every ticker was confirmed; a ticker no provider recognizes gets `ticker_not_recognized` and one that could not be
  checked gets `ticker_not_checked` with the provider failure as its `reason_code`; every entry is added whatever the
  warnings; each distinct ticker is looked up once, and after the first `provider_unreachable`, `provider_rate_limited`
  or database failure no further ticker is looked up, a database failure being a readiness error or a raw storage error
  with its classified `database_*` code; duplicates, blank tickers, an unreadable stored entry and an
  unknown watchlist are refused before any provider is asked; the text output prints the watchlist and then a
  `Warnings:` section; both warning codes have glossary terms; `entries.duplicate` says "the same as-of date and
  options" in both templates, the `entries` body description, `docs/user/API.md` and `docs/user/WORKSPACE.md`;
  `provider_no_data` answers 404, `provider_unreachable`, `provider_unexpected_response` and `provider_error` 502,
  `provider_rate_limited` 429 and `configuration_error` 409 on every endpoint that can return them, each documented in
  `openapi.json` and `docs/user/API.md`; the schemas and `openapi.json` pass their drift checks.
- API.19: a storage error raised after the readiness check, while a connection opens or inside a `transaction()` or
  `read()` scope (busy or locked, read-only, permission or auth, not a database or corrupt, I/O, full or can't-open), is
  a `DatabaseError` chained from the driver's error, with the reason `storage_reason` gives, the database path and a null
  expected revision; any other error, a constraint violation or an unrecognized SQLite code included, is raised
  unchanged and is an `execution_error`; a read endpoint and a write endpoint answer `database_busy` with 503 and the
  message "The database is in use by another operation and did not become free within the configured wait. Close other
  database operations and retry." while a second connection holds a real lock; `ian runs list --json` and
  `ian watchlist create --json` write the same code with the `database` element; a refresh entry whose save meets the
  lock fails with `database_busy` and the other entries finish; readiness's own codes are unchanged and its messages
  are unchanged apart from `database_busy`; `openapi.json`, the JSON Schemas and every `schema_version` are unchanged.
- API.18: an unknown ticker run through every declared strategy is `input_unavailable` with `provider_no_data`, a
  `provider_failure` of kind `no_data`, the outcome `unavailable` and a null run `failure_reason_code`, for a ticker
  absent from SEC's ticker list and for a listed ticker whose company documents answer 404; a failure while loading the
  ticker list keeps its own kind and is a `provider_error`; a run with any other kind among its failed required inputs
  is a `provider_error`; every validator enforces the same rule for `provider_failure` and the status; the automatic
  provider check runs after a no-data run, in a direct command, the refresh summary and the text first line, and the
  verdict is never stored; each strategy's document and result version and the refresh summary's version are bumped, and
  a run stored under an older version is refused by version; no run that completed before the change changes; the
  schemas, `openapi.json` and the help bundle pass their drift checks.
- API.17: an instrument profile, a run overview and a run's identity identified by SEC EDGAR serve the exchange SEC's
  `company_tickers_exchange.json` lists for the ticker, as SEC writes it (`Nasdaq`, `NYSE`, `OTC`, `CBOE`), and null when
  the file gives none; a ticker the file lists under more than one CIK is still refused, and a reviewed override still
  wins and says `cik_source=override`; a Yahoo identity keeps Yahoo's wording; no stored shape or version changes; the
  live suite checks that the real file still has `cik`, `name`, `ticker` and `exchange`.
- API.12: a new run stores `outcome` and `run_schema_version` 4 in `envelope_json` and in the column, and reads back; a
  version 3 run is refused with `unsupported_run_version` by `runs show` (text and `--json`), the run endpoint, the run
  overview and replay, logs no exception, and still appears in `runs list` and the refreshes list with its outcome and in
  `runs compare` with `—` cells; a run of the supported version with a malformed envelope is still refused as
  `invalid_stored_run`; no migration, schema module, served document, failure code, JSON Schema or `openapi.json`
  changes.
- API.11: `GET /v1/refreshes/{refresh_id}/compare` and `ian runs compare --json` carry `first_completed_at`,
  `last_completed_at`, `run_count` and `outcome_counts` (`schema_version` 7), and with the watchlist fields they equal the
  refreshes list's item for the same refresh, for a watchlist refresh, a refresh of a list of entries and a refresh
  stopped partway; the watchlist shows when no run's envelope can be read; the `ian runs compare` heading names the last
  completion in the form `ian runs refreshes` prints, with no outcome counts; the refreshes list is unchanged and
  byte-identical; the JSON Schemas, `openapi.json` and the term-reference test pass; no stored shape, migration or served
  name other than these changes; `docs/user/API.md` and `docs/user/WORKSPACE.md` describe it.
- API.20: building, opening, leaving and removing the sample workspace give the same results through the CLI and the API;
  opening it twice in a row starts from the same pristine sample each time; leaving it discards every change made there
  and leaves the user's own workspace byte-for-byte unchanged; switching is refused while a refresh job runs; every API
  response carries `IAN-Workspace: sample` while the sample is active, and every command prints the notice on standard
  error with `--json` output unchanged; no document or output names a storage path; the tests build the sample with
  fake providers under the network guard.
- API.21: the SEC identity set through the API or the command is the one the next provider request uses, survives a
  restart of `ian serve`, and is never written to the settings folder; the reading order of W12 holds.
- API.22: every venue the API serves is `{code, provider_value}` or null (the instrument profile document at
  `schema_version` 2, the run overview at 4, FCF Growth, Graham Growth and Graham Number at 15, Momentum at 14 and
  Piotroski at 6, and the specimen strategy's fixture at 2); each value of each table has a captured specimen in the mapping record and a value no table lists
  has a null code with its wording served; a run saved and a profile cached before the change gain their codes with no
  migration and no stored-shape change; every text rendering writes the term's name with the wording in parentheses
  when it differs; `ListingVenue` and the `Listing Venue` term are in the term references and the help bundle; the
  live SEC check fails, naming the exchange, when SEC's file lists one the table does not know; the package
  dependency check, the JSON Schemas, `openapi.json` and the help bundle pass.

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
| Precondition for a new locale | Before any locale beyond the default is added, every producer of labels, rendered text and messages takes the locale first, because a response that states a locale in `Content-Language` is true only while all of its text follows it ([T14](API_6_SLICE_PLAN.md#t14-api6b-negotiation-2026-11-07)). Where a translation's source documents live is decided with the first added locale ([T33](API_6_SLICE_PLAN.md#t33-bundle-file-and-packaging-2026-11-08)) |

### A.6 Refreshes list (2026-11-10)

Approved by the project owner on 2026-11-10. That approval includes the database migration in L3, as `AGENTS.md` §11
requires.

| # | Decision |
| :--- | :--- |
| L1 | Where it is planned: a new slice API.7, Refreshes list, added to the API work package's sequence table, with its section in the API contract plan and no separate slice plan (it is one pull request). These decisions are recorded in a new Appendix A.6 of that plan. |
| L2 | Sequencing: API.7 is IAN's next slice, ahead of further Step 3.5 work, because the desktop application's GUI.2b waits for it. Branch `feat/api-refreshes-list`. |
| L3 | Storage: migration `0006` adds nullable `watchlist_id` and `watchlist_name` columns to `analysis_runs`. New runs fill them from the envelope at insert. Existing rows are backfilled in SQL with `json_extract` on `envelope_json`; a row whose envelope has no watchlist, or cannot be read, stays null. An index on `watchlist_id` is added. The envelope remains the source of truth; the columns are copies of immutable envelope fields, like `ticker`. Rejected: `json_extract` at query time (reads every envelope on every list, and breaks the rule that listing never depends on envelopes); a new `refreshes` table (a larger change, a second write path at refresh start, and the same backfill). |
| L4 | Endpoint: `GET /v1/refreshes`, with query parameters `watchlist_id`, `limit` (1 to 100, default 20) and `offset` (default 0); the same paging as `/v1/runs`, with `has_more` and no total. It is an addition inside `/v1` under S4. |
| L5 | Document: a new versioned refreshes-list document, `{schema_version, items, has_more}`. Each item has `refresh_id`, `watchlist_id` and `watchlist_name` (both null for a refresh of a list of entries or an unreadable envelope), `first_completed_at`, `last_completed_at`, `run_count`, and `outcome_counts` with one integer for each `RunOutcome` value. Its JSON Schema is in `schemas/`, and `openapi.json` is regenerated. |
| L6 | Ordering: newest first by `last_completed_at`, then by `refresh_id` descending. |
| L7 | Watchlist name: an item carries the name recorded when the refresh ran, not the current name, as the compare document does. A client that wants the current name reads `/v1/watchlists/{id}`. A deleted watchlist's refreshes keep appearing with their recorded name. |
| L8 | Filter: a `watchlist_id` that matches nothing, including a deleted watchlist, returns an empty list, not 404. A malformed id is `invalid_parameter`. Refreshes of a list of entries appear only when no filter is given. |
| L9 | Counts: counts are of stored runs only. A stopped refresh shows fewer runs, and a refresh run with saving off does not appear. There is no stopped or complete flag, because storage does not record one. `docs/user/API.md` says so. |
| L10 | Command line: `ian runs refreshes`, with `--watchlist`, `--limit`, `--offset` and `--json`, through the same application-layer function as the endpoint. |
| L11 | Term references: the new fields go through the API.6a conformance test. Outcome values already name terms. If the test requires a term for a new label, it is added to the investor glossary in the same pull request. |
| L12 | Documentation and tests: `docs/user/API.md` (endpoint row and a short section), `docs/user/WORKSPACE.md` (the new command) and one smoke-test step. Tests: migration upgrade with backfill (a watchlist run, a list-of-entries run, an unreadable envelope) and downgrade; repository grouping, ordering, filter and paging; in-process endpoint tests; CLI text and `--json`. The managed gate runs as usual. |

### A.7 Structured units, run overview and command-free database messages (2026-11-13)

Approved by the project owner on 2026-11-13. No database migration, stored shape, formula or classification changes.

| # | Decision |
| :--- | :--- |
| U1 | Where it is planned: a new slice API.8, Structured units, run overview and command-free database messages, in this plan's sequence table and §3, in the form of API.7 and with no separate slice plan. It is IAN's next slice. Step 3.5's plan and §2 above say 3.5.5 starts after API.8 merges. Branch `feat/api-run-overview`. The pull request marks API.8's row Complete, dated the day it is opened. |
| U2 | Changes before the first release amend [S4](API_2_SLICE_PLAN.md#s4-the-v1-additions-rule-2026-11-03): the additions rule applies from the first engine release that includes the API. Until then an incompatible change inside `/v1`, CLI `--json` included, is allowed when the slice that makes it records it and raises the affected document's `schema_version`. `docs/user/API.md` and `docs/user/USAGE.md` say so where they state the rule. API.8's own incompatible changes (U3, U9) are recorded under this rule. |
| U3 | Unit shape: a headline cell's `unit` is the closed code set `CellUnit` (`percent`, `points`, `multiple`, `per_share`) and a new nullable `currency` holds an ISO 4217 code. A number cell has a unit; `currency` is non-null only when the unit is `per_share`, and null then means the run recorded no currency, which replaces "currency unspecified per share". A text cell has a null `unit` and a null `currency`. The `value` description says a `percent` value is the percentage itself (18.4 means 18.4 %). `HeadlineCell` changes the same way and enforces these rules; `per_share_unit` and `UNSPECIFIED_CURRENCY_PER_SHARE` are removed. The compare document's `schema_version` is raised (it was 4 and is now 5, not 1 and 2 as the decision was first worded). The CLI's text comparison table reads the new fields and its output does not change. Every currency a strategy can put in a cell is a three-letter ISO 4217 code: SEC per-share units are checked to three letters before they become a currency, and an override carries none. |
| U4 | Terms: `CellUnit` is exempt from term references, like `CellKind`, because a cell's unit is shown by its formatted value and the cell's own term explains what it measures. It is added to `EXEMPT_CODE_SETS` and `EXEMPT_LOCATIONS`; the module's docstrings and the tests and documents that stated how many exemptions there are stop stating a count. |
| U5 | Database messages: `DatabaseReadinessError`'s message states only the database's state, with no `ian` command, option, environment variable or file path; the path is already served as `database.database_path` in the failure envelope. The command line puts the target and the remedy back, as [W16](API_3_SLICE_PLAN.md#w16-the-cli-adds-the-remedy-for-an-unreadable-entry-2026-11-05) does for an unreadable entry: `cli_support.database_message` builds the form the command line has always written, and it is the message of the failure envelope in `--json` too, as W16's is, so the command line's text and `--json` output do not change. `ian serve`'s start-up failure output is command-line output and keeps the full form. The API serves the bare message. |
| U6 | One test, parametrized over every readiness reason, checks that the served reason has no `ian ` command, no `--` option, no environment variable name and no path, and that the command line's form of the same failure keeps the remedy and the path where it does today. |
| U7 | Run overview: `GET /v1/runs/{analysis_run_id}/overview` returns a new versioned document, `RunOverviewDocument` (`schema_version` 1): `analysis_run_id`, `ticker`, `outcome`, `completed_at`, `refresh_id`, `requested_as_of`, `strategy` (the compare document's strategy shape; a strategy no longer declared shows its stored label with `declared` false and a null term), `headline` and `headline_unavailable` (exactly one is set, as in the compare document). It fails with the same reason codes and statuses as `GET /v1/runs/{analysis_run_id}`: not found, an unsupported run version, an invalid stored run and database failures. A run of a strategy no longer declared succeeds, because its row, not its envelope, is read; its `requested_as_of` is null because its envelope is not decoded. It goes through an application-layer function, one route, its own JSON Schema and the regenerated `openapi.json`, and its new fields pass the API.6a conformance test. |
| U8 | One headline builder: `resolve_headline` in `workspace_documents/runs_compare.py` builds a run's headline, or its `headline_unavailable`, for both the overview and the comparison. The parametrized endpoint test covers the overview for every declared strategy, so a new strategy appears with no edit. |
| U9 | One name for a run's outcome: where a `RunOutcome` value was called `status` for a run, it is `outcome`: the runs-list item's field (the runs-list document's `schema_version` is raised from 1 to 2), the `/v1/runs` query parameter, and `ian runs list --status`, now `--outcome`. A calculation status and a cell's status keep their names. **Amendment (approved by the project owner on 2026-11-13):** U9 extends to refreshes. A refresh job's run outcome is `outcome` in `RefreshResultDocument` (it was `status`), with a plain-words description; the refresh summary's `schema_version` goes from 3 to 4, and the refresh job document, which embeds the summary and the results, from 1 to 2 (the refresh event document has no version of its own). A job's `state` and a calculation status keep their names. The `counts` description becomes "How many jobs ended in each outcome. A job that stopped because of an unexpected problem, before it produced an outcome, is counted under the key `error`.", and served descriptions and `docs/user/` say a job or entry "stopped because of an unexpected problem" instead of "raised". |
| U10 | No command-line counterpart for the overview; see [§4](#4-out-of-scope). |
| U11 | Documentation and tests: `docs/user/API.md` (the endpoint row and a short section, the unit and currency fields with the percent scale, the U2 rule, the U9 rename), `docs/user/USAGE.md` (the U2 rule), `docs/user/WORKSPACE.md` and `docs/user/SMOKE_TESTING.md` (`--outcome`); regenerated JSON Schemas and `openapi.json`; tests for each strategy's number cells, `HeadlineCell`'s rules, the unchanged comparison table, U6, the overview's cases and the U9 rename. |
| U12 | A run's `requested_as_of` is read from its envelope for every run, including a run of a strategy no longer declared and a run stored under an unsupported version, so null always means "now". The envelope does not depend on the strategy; only decoding the evidence needs the strategy's codec, so `resolve_headline`, the one builder the overview and the comparison share, reads the field without it. The comparison had the same ambiguity before API.8: it showed null for those runs. A run of a strategy no longer declared, or stored under an unsupported version, whose envelope cannot be read now fails with `invalid_stored_run`, the same as a declared strategy's run, in both the comparison and the overview; before, such a run succeeded only because its envelope was never read. The overview's description is "The point in time the run asked for; null means now." Approved by the project owner on 2026-11-13. |
| U13 | A date given as an `as_of` stays stored as the end of that day in UTC (`time.max`, the last microsecond), as before: no migration and no change to a stored shape. It is served as that date (`YYYY-MM-DD`); any other timestamp is served as given, with its offset. A timestamp entered as exactly `23:59:59.999999` in UTC is indistinguishable from a date and is also served as the date; `docs/user/API.md` and `docs/user/USAGE.md` say so. The rule is one predicate, `is_end_of_day_utc` in `reporting/documents/timestamp.py`, which `as_of_text` (the served spelling) and `format_as_of` (text output) both use; `format_as_of` now also requires the UTC offset, as the served rule does. Approved by the project owner on 2026-11-14. |
| U14 | The rule applies to every served as-of boundary, in API responses and in CLI `--json` output: a strategy document's `requested_as_of` and `effective_as_of`; the `as_of` of a resolved input in the Graham Number, Graham Growth and Piotroski documents (the shared `ResolvedInputPart`) and in the FCF Growth document (`FCFResolvedInputPart`); a stored selection's `as_of` in the watchlist, rename, removal and delete documents (and the API's entry and watchlist responses, which are the watchlist document); and `requested_as_of` in the run overview and the runs comparison. Event times (`completed_at`, `created_at`, `updated_at`, `observed_at`, `available_at`, `retrieved_at`, `resolved_at`, observation periods) are unchanged, as is Momentum's `data_as_of`, which is already a date. The refresh summary, refresh job, runs list, refreshes list and watchlist list documents carry no as-of boundary. |
| U15 | Under U2, each document whose served shape changes (a field widened from date-time to date or date-time) raises its `schema_version`: the watchlist, watchlist rename, watchlist removal and watchlist delete documents 1 to 2; the run overview 1 to 2; the runs comparison 5 to 6; the Momentum document 11 to 12; the Graham Number and Graham Growth documents 12 to 13; the FCF Growth document 12 to 13; the Piotroski document 3 to 4. |
| U16 | The JSON Schemas, `openapi.json` and the stored command-output snapshot are regenerated as reviewed diffs. The watchlist documents describe a selection's `as_of` as a date or a date-time without changing the selection models, which are stored shapes. |
| U17 | Tests: the shared predicate (the end of a day, one microsecond before it, other offsets, null); a date as-of added through the API, refreshed, and read back as the entry, the saved run's overview, its strategy document and the comparison, each showing the date; the same through the CLI `--json` forms; a timestamp as-of unchanged; the stored selection still holding the end-of-day instant. |
| U18 | Documentation: `docs/user/API.md` and `docs/user/USAGE.md` say that a date as-of is stored as the end of that day in UTC and served as the date, and note the exactly-end-of-day timestamp. Approved by the project owner on 2026-11-14. |

### A.8 Engine version, installation folder and commit (2026-11-14)

Approved by the project owner on 2026-11-14. No database migration, stored shape, formula or classification changes.

| # | Decision |
| :--- | :--- |
| D1 | Installation folder: `investment_analysis_engine/core/package_root.py` defines `INSTALLATION_FOLDER: Final[Path | None]`, which is `PACKAGE_ROOT.parent` when that folder holds the project's `pyproject.toml` (a source checkout, which uv installs in editable mode) and `None` otherwise (installed from a wheel). It reports the code that is actually running however `ian` was started, so the launcher is not changed and passes nothing to the engine. The module's docstring states the one exception to "the package never names the folder that contains it". `tests/test_one_home_per_name.py` keeps its guard against deriving the repository root and gives `core/package_root.py` a stated exception; `scripts/repository_root.py` stays as it is. |
| D2 | Command: `ian about`, with `--json`, listed in `ian --help`; there is no `--version` option. It is in `investment_analysis_engine/cli_about.py`, registered in `cli.py` the way `cli_health.py` is. The command never fails on its own account and always exits 0; like every command it still stops with exit 2 and one message when the engine settings or a component settings file is invalid (D7). Its name is added to the conformance script's list of non-strategy commands (approved by the project owner, 2026-11-14), because the script's command-table check names every top-level command that is not a strategy. |
| D3 | Commit: when `INSTALLATION_FOLDER` is not `None`, `git -C <folder> rev-parse --show-toplevel` and `git -C <folder> rev-parse HEAD` run as subprocesses with output captured. The commit is the full 40-character hash, and only when the reported top level resolves to the installation folder itself; a folder inside some other repository is not a checkout of the engine. It is null when there is no installation folder, Git is not installed, a Git call exits nonzero, or the top level is a different folder. |
| D4 | Uncommitted changes: when the commit is not null, `uncommitted_changes` is true when `git -C <folder> status --porcelain` prints anything (tracked changes and untracked files that are not ignored) and false otherwise. It is null whenever the commit is null, including when this status call itself fails. |
| D5 | JSON document: `AboutDocument` in `reporting/documents/about.py`, in the form of the health document: frozen, `extra="forbid"`, with `schema_version` 1, `engine_version`, `installation_folder` (the native path form), `commit` and `uncommitted_changes`. It is a report, not the failure envelope, and carries facts and no instructions. It is registered in `workspace_documents/json_documents.py` and published as `schemas/about.schema.json`. The version comes from `installed_engine_version()`, not from `pyproject.toml`. `/v1/info` and `openapi.json` do not change. |
| D6 | Text output: three lines, `Investment Analysis Engine <version>`, `Installation folder: <folder>` and `Commit: <hash>`, where the commit line ends in ` (with uncommitted changes)` when there are any, reads `none (not a Git checkout)` for a source folder with no commit, `none (Git is not installed)` when Git cannot be started, and `none` for a package installation, whose folder line reads `none (installed as a package)`. The help text is "Show the engine's version, installation folder and commit." |
| D7 | Invalid settings: startup is left as it is. An invalid engine environment variable or component settings file stops `ian about`, as it stops every command, with one message on standard error and exit 2, and `--json` then produces no document. The cost, accepted: with invalid settings `ian about --json` produces no document, because changing that would change startup for every command. |

### A.9 Runs comparison carries its refresh's summary (2026-11-15)

Approved by the project owner on 2026-11-15. No database migration, stored shape, formula or classification changes.

| # | Decision |
| :--- | :--- |
| C1 | Shape: `RunsCompareDocument` gains four flat top-level fields, `first_completed_at`, `last_completed_at`, `run_count` and `outcome_counts`, the last typed as the existing `RefreshOutcomeCountsDocument`. Their names, types, constraints (`run_count` at least 1) and descriptions are those of `RefreshSummaryItemDocument`, and each description is defined once in `workspace_documents/refreshes.py` and used by both documents, so the two cannot drift. `refresh_id`, `watchlist_id`, `watchlist_name`, `strategies` and `rows` stay. Rejected: nesting the list item as a `summary` member, which repeats `refresh_id` and the watchlist fields. |
| C2 | One source: the SQL grouping in `list_refreshes` becomes one summary select that both callers use. The list is unchanged (paging, the watchlist filter and the order), and a new repository read, `get_refresh`, returns one refresh's `RefreshSummary` together with its runs from the same database read, so the counts and the rows always agree. `compare_refresh_runs` uses it, and the comparison's `watchlist_id` and `watchlist_name` come from that summary (the indexed columns), not from decoded envelopes. The envelope-based derivation (`RunHeadline.watchlist` and the `watchlist = next(...)` line in `build_runs_compare`) is deleted. The comparison's watchlist field descriptions become the list item's, shared as in C1. The effect: the watchlist shows even when no run's envelope can be read. |
| C3 | Version: under U2 ([A.7](#a7-structured-units-run-overview-and-command-free-database-messages-2026-11-13)) the comparison document's `schema_version` goes from 6 to 7. `schemas/runs-compare.schema.json` and `schemas/openapi.json` are regenerated. The refreshes-list document stays at version 1 with byte-identical output. |
| C4 | `ian runs compare` heading: it adds the last completion time, in the ISO form `ian runs refreshes` prints, after the watchlist part, as in `Refresh 7c1a... · watchlist "Core" · completed 2026-09-19T14:02:12+00:00 · 3 tickers · 4 strategies`. For a refresh of a list of entries the watchlist part stays absent: `Refresh 7c1a... · completed 2026-09-19T14:02:12+00:00 · 3 tickers · 4 strategies`. The heading carries no outcome counts, and nothing else in the text output changes. |
| C5 | A run's outcome is named `outcome` in the in-memory records. As amended (C5a): `status` becomes `outcome` on exactly four types, `StoredRefreshRun` and `StoredRun` in `workspace/repositories/analysis_runs.py` and `AnalysisRunSummary` and `RunQuery` in `workspace/runs.py`, with every reader and writer. The stored envelope model `AnalysisRun` keeps its `status` field, because it is written into `envelope_json` under `run_schema_version` 3; a comment on the field says so and names [issue 264](https://github.com/PeterPontbriand/investment-analysis-engine/issues/264), which API.12 resolves. No stored shape, migration, CLI option, served name or output changes. The first version of C5 renamed `AnalysisRun.status` too and was replaced, because that is a stored-shape change. |
| C6 | Tests: the comparison's four new fields and its watchlist fields equal the refreshes-list item for the same refresh, for a watchlist refresh, a refresh of a list of entries and a refresh stopped partway; the watchlist shows when no run's envelope can be read; the heading in both forms of C4; the endpoint returns the new fields; the JSON Schema and OpenAPI drift checks and the API.6a term-reference test pass for the new fields, which the list item's fields already cover. |
| C7 | Plan and docs: the API.11 row, its section 3 entry and acceptance line and this section; `docs/user/API.md` and `docs/user/WORKSPACE.md` (the compare heading and the document's fields and version). The API.12 row and entry record the issue for the stored envelope's `status`. No glossary change. |

### A.10 Form labels, error templates, refresh totals and provider names (2026-11-16)

Approved by the project owner on 2026-11-16. No database migration, stored shape, request, formula or classification changes.

| # | Decision |
| :--- | :--- |
| N1 | Slice and records: API.13 is one slice and one pull request, recorded like API.7 to API.11. There is no separate slice plan. The row is dated the day the pull request is opened. |
| N2 | Selection field labels go in the JSON Schema `title`, declared with `Field(title=...)` on every selection field of every strategy, the nested `policy` group of FCF Growth and each of its fields included. The labels replace pydantic's generated titles, are in the default locale, and are not an `x-label` key. |
| N3 | Labels capitalize only their first word and proper names, and a field name has the same label in every strategy that has it: `as_of` As of; `use_cache` Use cached data; `short_window` Short window; `long_window` Long window; `rsi_period` RSI period; `bvps_override` Book value per share override; `eps_override` Earnings per share override; `quote_override` Share price override; `expected_growth` Expected growth rate; `aaa_yield_override` AAA corporate bond yield; `eps_basis` EPS basis; `currency` Reporting currency; `policy` Growth policy; `policy.classification_basis` Classification basis; `policy.forward_policy` Forward policy; `policy.historical_horizon` Historical horizon. Units stay in the descriptions, which do not change. The specimen strategy and the generator templates declare titles too. |
| N4 | Enforcement: the selection-options conformance check (T27, `selection_options_gaps`) also reports a selection field, nested fields included, that declares no title or a blank one, and a field name whose title differs between strategies. The selection-field steps of `docs/project/STRATEGY_DEVELOPMENT.md` say so. |
| N5 | Error templates: `FailureRuleError` gains `template`, the rule's message with each parameter as a placeholder spelled as in `parameters` and each value as a placeholder named as in `arguments`, so filling every placeholder gives `message`. The value comes from the template `ActionParameterError` holds, under the caller's parameter spellings; `RuleViolation` carries it to the envelope. Parameters and arguments share one placeholder namespace. Building an `ActionParameterError` raises when an argument name equals a parameter name and when the template has a placeholder that names neither a parameter nor an argument. Tests that used an undeclared placeholder assert that refusal. |
| N6 | Unreadable entry on a refusal: `FailureEnvelope` gains `unreadable`, typed as `UnreadableEntryDocument` (`entry_number`, `ticker`, `method_id`, `reason`), whose model lives in `reporting`'s shared document parts with its class name, OpenAPI component name and fields unchanged; `workspace_documents` imports it from there, and no second document model exists. Core gets a small frozen dataclass holding the same four facts, in the style of `RuleViolation`, in `core/failure_classification.py`. A new `unreadable_entry_of_exception` there, beside `provider_failure_of_exception`, `parameters_of_exception` and `violations_of_exception` and in their style, returns that dataclass: it names no exception type, reads the attributes by `getattr` with type checks, and returns a value only when `entry_number`, `ticker` and `method_id` are all present. `failure_envelope` calls it only when `reason_code` is `stored_selection_unreadable` and builds the `UnreadableEntryDocument` from it, as `_rule_error` builds `FailureRuleError` from a `RuleViolation`; the field is null otherwise. The entry's `reason` is the text the rename, removal and delete documents put in their `unreadable.reason` for the same entry. The package dependency table does not change. |
| N7 | Refresh totals: `RefreshTotalsDocument` gains `total`, the number of entries in the refresh, which is the snapshot's size and always equals `admitted + remaining`. The command line's refresh output does not change. |
| N8 | Provider names: `InfoDocument` (`/v1/info`) gains `providers`, a list of `{id, name}` (component `ProviderItem`): one item per data provider in `PROVIDER_CHECKS`, in that order, named from `PROVIDER_DISPLAY_NAMES`. A conformance test checks that every `PROVIDER_CHECKS` identifier has a display name. `instrument_profile_cache` and `user_override` are sources of a value, not data providers, and are not listed. `ProviderCheckItem` and `data/instrument_profile_cache.py` do not change. |
| N9 | Versions, as `docs/user/USAGE.md` allows for additions: `FailureEnvelope` 13 to 14 (N5, N6), `RefreshJobDocument` 2 to 3 (N7), `InfoDocument` 2 to 3 (N8). The selection form document and the selection schemas keep their versions: titles change their content, not their shape. The pull request lists the three changes. |
| N10 | Documents and generated files: `docs/user/API.md` (Errors, Selection forms, Refresh jobs and the `/v1/info` row), `docs/user/USAGE.md` (the `--json` failure-document paragraph: version 14, `errors[].template` and `unreadable`), `docs/user/DATABASE.md` (links to the failure document instead of stating its version), `schemas/openapi.json` and the schemas the changes reach, regenerated with their drift checks passing, and `docs/project/STRATEGY_DEVELOPMENT.md` (N4). No command-line text changes. |
| N11 | Out of scope: localized labels; an endpoint for a ticker's details; checking a ticker when an entry is added; any change to a request, a stored shape, the database or an existing field's name, type, nullability or meaning. |

### A.11 The stored run envelope's outcome (2026-11-17)

Approved by the project owner on 2026-11-17. The stored run envelope changes shape; no database migration, served document, failure code, formula or classification changes.

| # | Decision |
| :--- | :--- |
| D1 | Refuse by version; do not convert. `AnalysisRun.status` is renamed `outcome`, and `run_schema_version` goes from 3 to 4. There is no migration. Version 3 runs stay in the database. `runs list`, the refreshes list and `runs compare` still show them, because they read the indexed columns; `runs compare` gives them `—` cells, as for any older version. `runs show`, the run overview and replay refuse them with `unsupported_run_version`. The rule in `docs/user/WORKSPACE.md` that runs are never converted stays as it is. |
| D2 | Refused by version, not as malformed. Before this slice `SQLiteAnalysisRunRepository._decode` validated `envelope_json` against `AnalysisRun` before it checked any version, so a run of another `run_schema_version` failed validation with a `ValueError` and was reported as `invalid_stored_run` (version 1 and 2 runs already were). Now `_decode` reads the row's `run_schema_version` column first and raises `UnsupportedRunVersionError`, the error `decode_evidence` raises, when it is not the supported version. `_stored_run` in `application/runs.py`, the one caller of `get`, lets that error through unlogged; the run overview and the comparison already read the version columns before decoding an envelope. `decode_evidence` is unchanged apart from D4. |
| D3 | `native_status` and `native_reason` keep their names. "Native status" is a defined contributor term, the same name is used by the codec site check and by `ExecutionCapture.native_status`, and a version 4 `status` key with a different meaning from version 3's would invite misreading. |
| D4 | One place for each supported version, in `workspace/runs.py`: `RunSchemaVersion = Literal[4]` with `RUN_SCHEMA_VERSION: Final[RunSchemaVersion] = 4`, and `ProjectionVersion = Literal[1]` with `PROJECTION_VERSION: Final[ProjectionVersion] = 1`. The `AnalysisRun` fields are typed and defaulted from them, so `mypy --strict` reports a disagreement between an alias and its constant; the stored JSON and the generated schema are unchanged (const 4 and const 1). `workspace/codecs.py`, the D2 pre-check, `workspace_documents/runs_compare.py` and `workspace_documents/run_replay.py` use the constants, and the private `_SUPPORTED_RUN_SCHEMA_VERSION` and `_SUPPORTED_PROJECTION_VERSION` constants are removed. `projection_version` keeps its value. `Literal[RUN_SCHEMA_VERSION]` is rejected by mypy, which is why the alias comes first. |
| D5 | No migration; D1. |
| D6 | Branch `chore/run-envelope-outcome`. |

### A.12 Option terms and the duplicate message (2026-11-18)

Approved by the project owner on 2026-11-17 (O1 to O3) and 2026-11-18 (O4 to O15). No database migration, stored shape, request shape, formula or classification changes.

| # | Decision |
| :--- | :--- |
| O1 | Option terms: each option of a selection field's closed set names its own glossary term through the strategy's code-term tables, so `GET /v1/help/references` gives each option a distinct term. The field keeps its own `x-term`. No `title` or label is added to options in the schemas. |
| O2 | Duplicate message: the `entries.duplicate` rule names the strategy by its label, not its method code, in the API and on the command line. The rule identifier stays `entries.duplicate`. |
| O3 | Other raw codes: no change to the built-in field-type messages (for example "Input should be 'three_year_average' or 'fiscal_year'"). |
| O4 | Slice and records: API.14 is one slice and one pull request with no separate slice plan, recorded like API.7 to API.13: a sequence-table row after API.12 dated the day the pull request is opened, a section 3 entry, an acceptance-criteria line and this appendix entry. No GitHub issue is opened. |
| O5 | EPS basis options: `three_year_average` maps to the existing `three-year-average-eps`, unchanged. `fiscal_year` maps to a new entry `fiscal-year-eps`, "Fiscal-Year EPS". The existing `fiscal-year` entry is unchanged. |
| O6 | New glossary entries: `fiscal-year-eps`; `historical-horizon-longest-available`, `historical-horizon-three-years`, `historical-horizon-four-years`, `historical-horizon-five-years`; `forward-policy-display-only`, `forward-policy-confirmation`, `forward-policy-hard-gate`; `classification-basis-total-fcf`, `classification-basis-fcf-per-share`. Each has a short definition checked against `docs/user/FINANCE_MATH.md` and `docs/user/strategies/FCF_GROWTH.md`, ends with a line pointing to its overview, and sits in its overview's section as the per-value entries of the stored-outcome overviews do. |
| O7 | One table per code set: each of the four code sets has one term table, declared once in its strategy's `vocabulary.py`, and `CODE_TERMS` maps both of its component names (the bare one and the selection one) to that same table. |
| O8 | Overview entries: EPS Basis, Historical Horizon, Forward Policy and Classification Basis keep their text and gain a final line listing their values' entries in table order, in the form the other overviews use. In EPS Basis it replaces the sentence that linked the two older entries. Three-Year-Average EPS is not changed. |
| O9 | Test: `tests/test_term_references.py` requires, for every closed set that a declared strategy's selection schema offers, nested fields and `$ref` included, that each value maps to a different term and no value maps to the field's own `x-term`. It applies to selection options only; other code sets keep the rule that values differing only in detail may share an entry. `docs/project/STRATEGY_DEVELOPMENT.md` states the rule in its selection-field steps, beside the title rule of A.10 (N4). |
| O10 | Duplicate templates: `duplicate_entry_error` takes the strategy's label, read from the descriptor, instead of `method_id`, and its arguments are exactly `ticker` and `strategy`. The `where` argument goes; a two-value enum selects one of two templates, "{<parameter>} must not duplicate an entry: {ticker} is already listed for {strategy} with an equal selection in the watchlist." or "{<parameter>} must not duplicate an entry: {ticker} is listed twice for {strategy} with an equal selection in this request.", so no English text is passed in as an argument. The command line's message changes the same way; no other command-line text changes. |
| O11 | Versions: `FailureEnvelope` goes from 14 to 15 under the pre-release rule ([A.7](#a7-structured-units-run-overview-and-command-free-database-messages-2026-11-13) U2), because the duplicate rule's arguments change. The selection schemas, the selection form document, the references document and the help bundle keep their versions: their content changes, not their shape (as A.10 N9). The pull request lists the version change. |
| O12 | Documents and generated files: `docs/user/GLOSSARY.md`, `docs/user/API.md`, `docs/user/USAGE.md`, `docs/project/STRATEGY_DEVELOPMENT.md`, every other place that states the failure document's version, the help bundle, `schemas/openapi.json` and any schema the changes reach, regenerated with their drift checks passing. |
| O13 | Glossary placement: in the Free Cash Flow & Earnings Growth Strategy terms section, the overview and other entries come first in their existing order, then the value entries, grouped by overview in the order the overviews appear and, within a group, in the order of the overview's "The values are explained in" line. Entries move whole and no entry's text changes. The Graham Growth Value Strategy terms section already follows the rule. |
| O14 | Option-terms test: it looks each set up in the shared registry merged with every strategy's tables (`code_terms_by_component`), and a separate test requires the walk to find at least one closed set across the declared strategies' selection schemas, so the check cannot pass with nothing to check. |
| O15 | Runbook versions: `docs/project/PROVIDER_DEBUGGING.md` states no version number; it links to the published schemas that describe the documents, as `docs/user/DATABASE.md` does (A.10 N10), and drops the sentence "No stored version changed.". It names no strategy: it describes the strategy schemas by their naming pattern in `schemas/` (the strategy's command alias) and does not list them. Its description of the check after a command failure names no strategy either; it previously omitted Piotroski. |

### A.13 Instrument profiles (2026-11-20)

Approved by the project owner on 2026-11-20. On 2026-11-20 the owner also confirmed, after review, that saved runs do not keep `quote_currency` and the run envelope is unchanged (every price a run uses carries its own currency), that `FailureEnvelope` goes from 15 to 16, that a lookup that cannot confirm an anchor answers the stored profile with its old `refreshed_at` and a profile with no anchor is answered and not stored, and that the lookup failure statuses stay 500 in API.15 (changing them is recorded on engine issue 269 for slice API.16). The stored instrument profile's payload changes shape and its version goes up (I9); no database migration, formula or classification changes.

| # | Decision |
| :--- | :--- |
| I1 | A read that never contacts a provider. `GET /v1/instrument-profiles/{ticker}` returns the ticker's current stored instrument profile, even when it is older than the configured freshness window (`instrument_profile_ttl_seconds`); `refreshed_at` tells the reader when it was last checked. It never contacts a data provider. With no current stored profile, it answers 404 with a new failure code, `instrument_profile_not_found`. A profile stored under another payload version counts as absent, as the cache already treats it. Rejected: resolving live on read, because a popup that opens on hover must answer at once and must not use provider quota. |
| I2 | A separate live lookup. `POST /v1/instrument-profiles/{ticker}/lookup` resolves the profile exactly as an analysis does, through the existing cached resolver without `force_refresh`: the stored profile when it is within the freshness window, otherwise live. It stores the result only under the resolver's existing identity-anchor rule. On success it returns the same document as I1. When the providers return nothing that identifies the ticker, it fails with the existing `provider_no_data`. Provider failures use the matching existing `provider_*` codes, with the HTTP statuses those codes already have. A lookup is allowed while a refresh job runs (I13). Amended by I12. Rejected: no lookup in this slice, which would leave newly added tickers with no details until a refresh runs. |
| I3 | The word "lookup". The action is called a lookup in the path, the command line, the glossary and the documents, never a "refresh", because Refresh is a glossary term for refreshing a watchlist or a list of entries. |
| I4 | Paths. `/v1/instrument-profiles/{ticker}` and `/v1/instrument-profiles/{ticker}/lookup`, named after the Instrument Profile glossary term. The ticker is trimmed and upper-cased as elsewhere. Rejected: `/v1/tickers/{ticker}`, because a ticker is not the thing described. |
| I5 | One ticker per request. No batch endpoint. Rejected for now: a batch read, which can come when a company-name column is wanted. |
| I6 | The document. `InstrumentProfileDocument`, with its own `schema_version` starting at 1, and the same document for I1 and I2. Fields: `ticker`; `refreshed_at` (ISO 8601 instant with offset); `instrument_name`, `listing_venue`, `issuer_identifier`, `instrument_identifier`, each nullable; `kind`, nullable, one of the reviewed instrument kinds; `quote_currency`, nullable (I9); `provider_id`, the provider of the identity, whose name the application takes from `/v1/info`'s `providers`. No status field: the document always describes a resolved, stored profile, and anything else is a failure (I1, I2). Each instrument kind value (equity, ETF, cryptocurrency) gets its own glossary entry and is served through the term references, as API.14 did for selection options, so a reader of the document can show its term's name. The Instrument Kind entry links to them. Rejected: a `status` field, which on the read could hold only one value. |
| I7 | Only the current profile. Profiles retired by a ticker reuse are not served. |
| I8 | A run's own identity on its overview. `RunOverviewDocument` gains `security_identity`, the identity snapshot the run retains (the existing `SecurityIdentityPart`), so a client showing a ticker tied to a past run uses that run's identity and never relabels it with the ticker's current meaning. The overview document's `schema_version` goes from 2 to 3. Rejected: serving only the current profile, which could name a different company for a reused ticker. |
| I9 | Quote currency in, sector out. The stored profile gains the trading currency, `quote_currency`: the currency the listing's price is quoted in. It is read from the yfinance metadata already fetched for the identity, never from a new request. `INSTRUMENT_PROFILE_SCHEMA_VERSION` goes from 3 to 4, once, with no migration: as the cache already does, an older record counts as absent and is overwritten by the next anchored resolution, so until a ticker is next analyzed or looked up, `GET /v1/instrument-profiles/{ticker}` answers `instrument_profile_not_found` for it. The stored Analysis Run envelope keeps its shape: it does not retain the quote currency. Reporting currency is not added. Sector and industry are out of scope for the engine: several competing classification schemes exist, and choosing among them is a portfolio-organization judgement that belongs to a future portfolio analysis and rebalancing feature set outside the engine ([Out of scope](#4-out-of-scope)). |
| I10 | Command-line parity. `ian instrument show <ticker>` prints the stored profile (I1). `--lookup` resolves it as I2 does. `--json` prints the document. The command line and the API call the same application-layer operations. Plain text output follows the existing read commands' style. Rejected: `ian profile ...`, which reads like a user profile. |
| I11 | Recording. API.15 in this plan with this appendix entry. The desktop application's GUI.4 slice plan names API.15 as its prerequisite; that is the desktop repository's work, not this slice's. |
| I12 | A lookup with no SEC identity uses Yahoo alone. Amends I2. When no SEC identity is set up, the lookup composes the profile with Yahoo as its only identity and kind provider, through the existing composition code, and answers the result without storing it, as the no-anchor path does. A stored profile, if one exists, is answered as before. When Yahoo identifies nothing the lookup fails with `provider_no_data`, and a provider failure uses its `provider_*` code, as with an SEC identity. Rejected: failing without an SEC identity, which leaves ticker details empty on a fresh install. |
| I13 | Lookup while a refresh job runs. An API test starts a refresh job with the existing test doubles and, while it runs, performs a lookup that succeeds. |

### A.14 Ticker check on adding entries, duplicate wording and provider statuses (2026-11-20)

Approved by the project owner on 2026-11-20. Closes engine issues 269 and 275. No database migration, stored shape, formula or classification changes.

| # | Decision |
| :--- | :--- |
| P1 | Scope. This slice does three things: the ticker check on adding entries (issue 269), the HTTP statuses of provider failures (issue 269's comment), and the duplicate-entry rewording (issue 275). Issues 248 and 268 are out of scope. |
| P2 | Where the check runs. Only when entries are added to a watchlist: `ian watchlist add-selection` and `POST /v1/watchlists/{watchlist_id}/entries`. Not a refresh of entries and not `/v1/analyses`, whose own results already report an unknown ticker. Rejected: checking before those too, which would add provider calls and delay to work that reports the problem anyway. |
| P3 | Warn, never refuse. Every entry that passes today's checks is added. Each ticker that could not be confirmed gets one warning, of one of two kinds: `ticker_not_recognized` when the providers answered and none identified the ticker, and `ticker_not_checked` when it could not be checked. Rejected: refusing an unrecognized ticker, because a provider occasionally answers nothing for a valid ticker, a refusal would need an override option, and an add should still work offline. |
| P4 | What the check consults. API.15's lookup operation (`lookup_instrument_profile`), called once per distinct ticker of the request, in order of first appearance. A stored profile within the freshness window answers with no network request; otherwise the providers are asked, with Yahoo alone when no SEC identity is set up ([A.13](#a13-instrument-profiles-2026-11-20), I12). A result with an identity anchor is stored, as every lookup stores it. Outcomes: resolved gives no warning; `provider_no_data` gives `ticker_not_recognized`; `provider_unreachable`, `provider_rate_limited`, `provider_unexpected_response` and `provider_error` give `ticker_not_checked`, with that code as its `reason_code`. The check runs only after the entries have been written successfully, so today's refusals (duplicates, blank tickers, an unreadable stored entry, an unknown watchlist) happen before any provider is asked and are unchanged. The check never turns a successful add into a failure. Amended by P13. |
| P5 | Stop asking after a network failure. After the first `provider_unreachable` or `provider_rate_limited`, the remaining tickers are not looked up. Each gets `ticker_not_checked` with that same `reason_code`. `provider_unexpected_response` and `provider_error` do not stop the check. Rejected: asking for every ticker, which makes an offline add of many tickers wait out one timeout per ticker. Amended by P13. |
| P6 | Ticker reuse. No extra handling. The lookup's resolver already retires a reused ticker's old profile, and an entry stores only its ticker. |
| P7 | The result document. `POST /v1/watchlists/{watchlist_id}/entries` and `ian watchlist add-selection --json` answer a new `EntriesAddedDocument` with `schema_version` 1 and two fields: `watchlist`, today's `WatchlistDocument`, unchanged; and `warnings`, a list, empty when every ticker was confirmed. Each item has `ticker`; `code` (`ticker_not_recognized` or `ticker_not_checked`); `reason_code`, the provider failure code for `ticker_not_checked` and null for `ticker_not_recognized`; and `template`, `arguments` and `message`, with the same shape and rules as API.13's rule errors (the filled template equals `message`). The two warning codes form their own closed set, separate from the failure reason codes. Each gets a glossary entry served through the term references, the way failure codes are. The document's JSON schema is added and `schemas/openapi.json` regenerated. Other endpoints keep answering `WatchlistDocument`. Rejected: a `warnings` field on `WatchlistDocument`, which would sit empty in every other response. Amended by P13. |
| P8 | The warning messages, in US spelling as the user docs use, one template per case. Not recognized: "No data provider recognizes {ticker}. Check the ticker, and remove the entry if it is wrong." Not checked, unreachable: "{ticker} could not be checked, because the data providers could not be reached." Not checked, rate-limited: "{ticker} could not be checked, because a data provider asked the engine to wait before asking again." Not checked, unexpected response or provider error: "{ticker} could not be checked, because a data provider gave an unexpected answer." A ticker skipped under P5 gets the message of the failure that stopped the check. Amended by P13. |
| P9 | Command-line text output prints the watchlist exactly as today, then, when there are warnings, a `Warnings:` line followed by each warning's message indented by two spaces, on standard output. The exit status stays 0. |
| P10 | The duplicate-entry wording, as issue 275 proposes, in both templates, the `entries` body description in `api/request_bodies.py`, `docs/user/API.md` and `docs/user/WORKSPACE.md`. The filled examples of the issue are the expected output: "{parameter} must not duplicate an entry: {ticker} is already in the watchlist for {strategy} with the same as-of date and options." and "{parameter} must not duplicate an entry: {ticker} is listed twice for {strategy} with the same as-of date and options." The rule identifier, its parameters, its arguments and the one-placeholder-namespace rule are unchanged. |
| P11 | HTTP statuses of provider failures, in `STATUS_BY_CODE`: `provider_no_data` 404; `provider_unreachable`, `provider_unexpected_response` and `provider_error` 502; `provider_rate_limited` 429; `configuration_error` 409. They apply on every endpoint that can return them, each documented in the OpenAPI description and `docs/user/API.md`, which no longer says these codes answer 500. Clients still branch on `reason_code`. The failure envelope's shape and version do not change. |
| P12 | Recording. API.16 and this appendix entry in this plan. The pull request closes issues 269 and 275 and sets API.16's status row to Complete, dated the day it is opened. Any desktop follow-up is the desktop repository's work, not this slice's. |
| P13 | The lookup's database failure. Amends P4, P5, P7 and P8. The lookup opens the database, so it can raise `DatabaseReadinessError` after the entries were written. During the check, that error gives its ticker `ticker_not_checked`; no new warning code is added and `provider_error` is not used for it. P7's `reason_code` is the failure reason code that kept the ticker from being checked: a provider failure code, or the readiness error's own failure reason code (for example `database_busy`); it is still null for `ticker_not_recognized`. P5's stop rule applies to a readiness error as it does to `provider_unreachable` and `provider_rate_limited`: the remaining tickers are not looked up and each gets `ticker_not_checked` with the same `reason_code` and message. P8 gains one template: "{ticker} could not be checked, because the engine's database was not available." Any other exception the lookup raises still propagates. Rejected: letting a readiness error propagate, which would turn an add whose entries are stored into a failure. Amended by P14. |
| P14 | Raw storage errors during the check. Amends P13. Every database error the lookup raises during the check gives its ticker `ticker_not_checked`, applies P5's stop and uses P13's message: `DatabaseReadinessError`, and the raw storage errors `OSError`, `sqlite3.Error` and `SQLAlchemyError` that the profile cache can raise after the readiness check. The `reason_code` of a raw storage error is the failure reason code of the category the engine already classifies it into, `storage_reason` in `data/repositories/readiness.py` (made public under that name, behavior unchanged), mapped to its failure reason code as a readiness error's is, so a locked database gives `database_busy` and an I/O failure `database_io_error`. Each caught database error is logged with its traceback through the operational logging. An exception that is neither a provider failure nor a database error still propagates. Rejected: one blanket `database_io_error`, which mislabels a locked database. |

### A.15 Listing venue for profiles identified by SEC EDGAR (2026-11-21)

Approved by the project owner on 2026-11-21. Closes engine issue 282. No stored shape, version, formula or classification changes.

| # | Decision |
| :--- | :--- |
| L1 | This slice is API.17, on branch `feat/api-sec-listing-venue`, recorded as this entry. |
| L2 | Source. SEC's `company_tickers_exchange.json` replaces `company_tickers.json` as the engine's one SEC ticker file, so an SEC EDGAR identity's `listing_venue` comes from the same provider and the same request as the rest of the identity. Before the change, current copies of both files were compared on 2026-11-21: 10,399 rows each, the same 10,399 tickers, the same CIK for every ticker, and no ticker under more than one CIK in either. The exchange file is `{"fields": ["cik", "name", "ticker", "exchange"], "data": [[cik, name, ticker, exchange], ...]}`; a missing exchange is written as `null` (155 rows). The exchanges it lists were `Nasdaq`, `NYSE`, `OTC`, `CBOE` and `TXSE`. The adapter refuses a document with other fields as an unexpected response. Rejected: Yahoo's exchange name inside an SEC identity, because the profile would name SEC EDGAR for a value Yahoo supplied; the anchor filing's cover exchange, because it describes the filing's date, not today. |
| L3 | Venue values are served as SEC writes them, with no mapping to full names; a missing or blank exchange stays null; a Yahoo-identified profile keeps Yahoo's wording. Explaining venues to users, by serving a code with a glossary entry, is a requirement recorded in engine issue 284. |
| L4 | No instrument profile schema version bump. A stored profile gains its venue when it next refreshes after the freshness window. A bump would make every stored profile read as not found (404) until looked up again. |
| L5 | Saved runs are unchanged. A run keeps the identity it had when it ran, a null venue included. No migration. |
| L6 | The internal CIK provenance value `CIK_SOURCE_TICKER_FILE` is renamed from `company_tickers` to `ticker_file`: the engine no longer reads that file, and the new value names the kind of source rather than a file, so it does not go stale if SEC's file changes again. Nothing stores or serves the value (only `cik_source=override` is written to a fact's notes), so there is no compatibility concern. |
| L7 | `ARCHITECTURE.md`, `PROVIDER_DEBUGGING.md` and `EVIDENCE_PROVIDER_ROADMAP.md` name the new file and describe the SEC identity's venue. Offline tests use the exchange layout and cover a venue served for an SEC identity, a missing exchange served as null, the duplicate-CIK refusal, the reviewed override (it wins over the file, and the provenance says `cik_source=override`) and a document in another layout. The live suite's SEC check requires the fields `cik`, `name`, `ticker` and `exchange` in the real file. |
| L8 | No desktop slice. The desktop application re-vendors in its GUI.4b slice. |

### A.16 Provider no-data is an unavailable input (2026-11-21)

Approved by the project owner on 2026-11-21. Closes engine issue 281. A ticker absent from SEC's ticker list is decided in E13, which amends [PH.2](../provider-health/PH2_FAILURE_CLASSIFICATION_SLICE_PLAN.md) D13.

| # | Decision |
| :--- | :--- |
| E1 | A run whose failed required inputs are all of kind `no_data` has the calculation status `input_unavailable`, so its outcome is `unavailable`, not `failed`. The provider answered correctly and has nothing; no input was invalid and no provider failed. |
| E2 | A run with any other kind among its failed required inputs stays `provider_error`, and the existing kind precedence (unreachable, rate-limited, unexpected response, no data) picks its code. Optional inputs, such as a Graham quote or FCF Growth's market capitalization, are unchanged. |
| E3 | The `provider_failure` element stays. Every strategy result, capture and codec, and the shared document model, enforce one rule: `provider_error` comes with a failure whose code is anything except `provider_no_data`, or with none; `input_unavailable` may come with a failure whose code is `provider_no_data` only; every other status has none. |
| E4 | The automatic provider check still runs after a no-data run that is unavailable: in a direct command, in the refresh summary and as the first line of text output. `ExecutionCapture` keeps `provider_failure` for an unavailable run whose failure code is `provider_no_data`. The refresh summary's `provider_check` is filled when a job failed on a provider or ended unavailable with a `provider_no_data` failure. The verdict is never stored, so a replayed run carries none. |
| E5 | One function in `core` maps the recorded provider failure to the status of a run a provider stopped, and every strategy calls it. A test runs an unknown ticker through each declared strategy, iterating the declared strategies, and asserts `input_unavailable`, a `provider_failure` with `provider_no_data`, the outcome `unavailable` and a null run `failure_reason_code`; a second test does the same for a listed ticker whose company documents answer 404. A unit test of the function covers E2's mixed kinds. |
| E6 | A new reason code, `provider_no_data`, in `ReasonCode`, explained by the existing glossary term `provider-no-data`. |
| E7 | The reason message names the provider and what it returned none of, in the form "<provider> returned no <what> for <ticker>.", for example "Yahoo Finance returned no price history for ZZZZQ.". It uses no internal shorthand and never says the ticker does not exist. A ticker absent from SEC's list reads "SEC EDGAR's ticker list does not include ZZZZQ.". Amended by E7a. |
| E7a | A `no_data` failure whose adapter message names the SEC override file uses the adapter's own message as the run's reason, unchanged. Those are the ambiguous CIK in `_resolve_cik`, the override CIK for which SEC has no company data in `_fetch_registrant_document`, and the registrant with no annual report in `_annual_filing_gap`. Every other `no_data` failure uses E7's message. The two are told apart by a typed field on the error, never by reading the message, and the adapter messages are not reworded. |
| E8 | An unavailable run has a null `failure_reason_code`, and its refresh result has a null `reason_code`. |
| E9 | Each strategy's document and result schema versions and the refresh summary's `schema_version` are bumped, as the table below shows. No migration or compatibility decoder is written: a run stored under an older version stays in the database and is refused by version when read. `run_schema_version` and the database schema are unchanged. |
| E10 | The user documents (`USAGE.md`, `WORKSPACE.md`, `GLOSSARY.md`, `FINANCE_MATH.md`), the help bundle, `openapi.json` and the JSON Schemas change in the same pull request. |
| E11 | Recording. API.18 and this entry in this plan. The pull request closes engine issue 281 and sets API.18's status row to Complete, dated the day it is opened. The desktop repository gets one issue, opened after the pull request is approved, that lists what the engine now serves differently; its GUI.4b re-vendor picks the changes up. |
| E12 | The ambiguous-CIK failure stays kind `no_data`, so a run it stops is `input_unavailable`. SEC answered correctly, so `unexpected_response` is rejected: a provider check would report SEC healthy. SEC's file listed no ticker under more than one CIK when [A.15](#a15-listing-venue-for-profiles-identified-by-sec-edgar-2026-11-21) L2 compared it on 2026-11-21. |
| E13 | A ticker absent from SEC's ticker list stops a run of a strategy that needs SEC EDGAR the same way an unknown ticker stops Momentum: `input_unavailable`, `provider_no_data`, a `provider_failure` naming `sec_edgar`, kind `no_data` and the required input that needed the CIK, and the provider check runs. The reason is "SEC EDGAR's ticker list does not include ZZZZQ.". The previous message, "no annual filing accepted by the boundary", was wrong for this case; the lookup, the entry check and Momentum already give `provider_no_data` for the same ticker; under E1 a `no_data` failure is already an unavailable input, so D13's separate absence path protected nothing; and this slice bumps every strategy's versions anyway. D13's other half stands: a failure while loading the ticker list keeps its own kind and is never a missing CIK, and `_MissingCikError` remains the only condition that means no CIK. Mechanism: the analysis snapshot carries the missing-CIK failure, and the anchor lookup raises it; the SEC annual series reads raise it. Not changed, so no run that completed before changes: the plain scope of a Graham run with both inputs overridden, the instant series and the single-fact read. |

Versions bumped by E9:

| Item | Old | New |
| :--- | :--- | :--- |
| Momentum document, result | 12, 5 | 13, 6 |
| Graham Number document, result | 13, 4 | 14, 5 |
| Graham Growth document, result | 13, 4 | 14, 5 |
| FCF Growth document, result | 13, 9 | 14, 10 |
| Piotroski document, result | 4, 2 | 5, 3 |
| Refresh summary `schema_version` | 4 | 5 |

### A.17 Database errors after the readiness check (2026-11-21)

Approved by the project owner on 2026-11-21. Closes engine issue 279. It builds on [A.14](#a14-ticker-check-on-adding-entries-duplicate-wording-and-provider-statuses-2026-11-20) P14, which classified a raw storage error only inside the ticker check.

| # | Decision |
| :--- | :--- |
| K1 | Where storage errors are classified. In `SQLiteDatabase` itself (`data/repositories/sqlite.py`): a storage error raised while it opens a connection, or inside a `transaction()` or `read()` scope, leaves that scope as the typed database error of K3, chained from the raw error. Every repository, the command line, the API, refresh jobs, the instrument-profile cache and the operations that open `SQLiteDatabase` themselves (`application/analysis.py`, `application/providers.py`) are covered without changes of their own. Not `open_database`: it misses those operations, and provider work inside its scope can raise `OSError` subclasses that are not database errors. |
| K2 | What counts as a storage error. Only SQLite errors whose primary result code is busy or locked; read-only, permission or auth; not a database or corrupt; I/O error, full or can't-open. That is the set readiness's `_initialize` already treats as storage failures. Their reasons are as `storage_reason` gives them: busy or locked, `database_busy`; read-only, permission or auth, `database_permission_denied`; not a database or corrupt, `database_invalid_file`; I/O, full or can't-open, `database_io_error`. Any other error, such as a constraint violation or a programming error, is left raw and stays an `execution_error`, because it is a defect, not a database state. `storage_reason` states this rule in one place, and readiness and `entry_check` use it. It no longer returns `database_io_error` for an unrecognized SQLite code. A raw `OSError` is classified only where readiness already classifies it, `database_permission_denied` for `EACCES` and `EPERM` and `database_io_error` otherwise; K1's scopes do not convert `OSError`. |
| K3 | The error type. `DatabaseReadinessError` is renamed `DatabaseError` and `ReadinessReason` `DatabaseReason`, and both serve readiness failures and K1's storage errors. `ReadinessOutcome` keeps its name. The reason values (the failure codes) do not change. The failure envelope's `database` element, the command line's per-reason details and remedies, and `classify_failure` (through the class's own `reason_code`) apply unchanged to the new uses. A K1 error carries the database path as readiness errors do, and an expected revision of null. The rename covers code, tests and current contributor and user documentation; historical text, such as decision records and completed slices' reports and evidence, stays as written. |
| K4 | Messages. The `database_busy` message, shared by readiness and K1, is "The database is in use by another operation and did not become free within the configured wait. Close other database operations and retry." The other storage messages (permission denied, invalid file, I/O error) are unchanged. The command line's added target and remedy are unchanged. |
| K5 | HTTP statuses are unchanged: `database_busy` answers 503, and the other database codes answer the status they already answer as readiness failures. The OpenAPI description already documents 503 on every endpoint that opens the database and 500 on every endpoint, so it does not change. |
| K6 | Refresh. A storage error while one entry is analyzed or saved becomes that entry's failure, with its precise database code, through the existing per-job failure description. The refresh carries on with the remaining entries, as for any one entry's failure. There is no new stopping behavior. |
| K7 | Tests. Unit tests: each K2 code family maps to its reason, a constraint violation stays raw and an unrecognized SQLite code stays raw. Real-lock tests: a second connection holding a write lock on a temporary file database, with a short busy timeout set through settings, covering a read endpoint and a write endpoint answering `database_busy` with 503 and the K4 message; one command-line command each way with `--json`, writing the failure document with `database_busy` and its `database` element; and one refresh entry whose save meets the lock, giving that entry's failure `database_busy` while the other entries finish. Readiness's own codes and messages are unchanged apart from K4's wording. No test waits longer than the short busy timeout. |
| K8 | Recording. API.19 and this entry in this plan. The pull request closes engine issue 279 and sets API.19's status row to Complete, dated the day it is opened. Any desktop follow-up is the desktop repository's work, not this slice's. |

Implementation notes, which follow from K1 to K4 and add no decision:

- `SQLiteDatabase` cannot import `readiness.py`, which imports it, so `DatabaseError`, `DatabaseReason`, the messages and `storage_reason` live in `data/repositories/database_errors.py`, which `readiness.py`, `sqlite.py` and their callers import.
- Readiness keeps its own results. It reports an error it cannot classify as `database_io_error`, as before, and it gives a storage error that a scope raised while it initializes or upgrades the verified revision, as before.
- The command line's text for `database_busy` follows K4's wording, because the old text named readiness.
- A read-only error inside a `read()` scope is left raw and stays an `execution_error`, because that scope is query-only, so SQLite refuses a write there as read-only and it is a defect in the caller, not a permission problem.

### A.18 Sample workspace and the SEC identity through the API (2026-11-22)

Approved by the project owner on 2026-11-22. The desktop application's matching decisions are recorded in its v0.1
implementation plan, under GUI.5.

| # | Decision |
| :--- | :--- |
| W1 | Where the sample lives. In a separate sample workspace, not in the user's own database. Runs are append-only and a refresh is only a tag on its runs, so sample rows mixed into the user's database could not be removed without breaking that rule; a separate workspace cannot touch the user's data by construction. Rejected: tagged sample rows in the user's database with a delete path for them. |
| W2 | Real or synthetic data. Real data, built on the user's machine from the sample definition by the engine's own analyses, calling the data providers. Rejected: synthetic tickers, which the ticker check and instrument profiles would reject and which teach nothing real; a pre-built sample shipped with the installer, which would redistribute data the providers do not license for redistribution, go stale, and need rebuilding for every schema or envelope version. |
| W3 | Who owns the sample. The engine owns the versioned sample definition (which tickers, strategies and as-of dates make a good demonstration is analysis content) and builds the pristine sample from it. The desktop application asks for it through the API and never defines sample content of its own. |
| W4 | A fresh copy every time. The engine never opens the pristine sample. Opening the sample workspace makes a new working copy of the pristine sample and makes it active; switching back to the user's own workspace discards the copy. Both are stated before they happen: a switch asks for confirmation on a terminal and needs `--yes` elsewhere, as `watchlist delete` does, and the desktop application asks before it switches. |
| W5 | What the sample holds. One watchlist named "Sample: well-known US companies" with about five well-known tickers across the shipped strategies, some entries pinned to a past as-of date to show point-in-time analysis, one completed refresh so the comparison has content, and one saved direct analysis. Every name starts with "Sample". The slice plan fixes the exact entries. |
| W6 | Storage belongs to the engine. Where the pristine sample and the copy are kept is decided by the storage layer: for SQLite, files beside the user's database in the engine's data folder; for a future database server, separate databases or schemas. No API document, CLI output or desktop setting names a path, and no other application deletes or copies them. |
| W7 | Operations. `GET /v1/workspace` serves the active workspace (`user` or `sample`) and the pristine sample's state (absent, building, ready or failed) and version. `POST /v1/workspace` with `kind` `sample` makes the copy and switches to it; with `kind` `user` it switches back and discards the copy. `POST /v1/sample` builds or rebuilds the pristine sample as a job with progress, as a refresh job does. `DELETE /v1/sample` removes it and is refused while the sample is active. The command line offers the same operations as `ian workspace show`, `ian workspace use sample`, `ian workspace use mine`, `ian sample build` and `ian sample remove`, through the same application operations. |
| W8 | One active workspace for every interface. The active workspace is recorded in the engine's own storage, in the user's database, not in the settings folder. A running `ian serve` reads it for each request, so a switch made from the command line shows in the desktop application at once, and the reverse. A switch is refused while a refresh job is running. |
| W9 | Unmistakable in every interface. While the sample is active, every API response carries the header `IAN-Workspace: sample` and `GET /v1/info` serves the active workspace; every command prints one line on standard error, "Sample workspace: anything you add is discarded when you switch back. Run `ian workspace use mine` to return.", so `--json` output is unchanged; the glossary gains a "Sample workspace" term that every interface links to. |
| W10 | Failure and upgrades. A build that fails leaves no pristine sample and reports what failed; a rebuild starts from nothing. An engine upgrade upgrades the pristine sample with the user's database, or rebuilds it when the sample definition's version has changed. |
| W11 | The SEC identity through the API. The engine accepts the SEC identity through an API operation and a matching `ian` command and keeps it in its own storage, never in the settings folder. It replaces the desktop application passing `SEC_USER_AGENT` to the server it starts, which works only on one computer. |
| W12 | Reading order. A stored value, which exists only after someone sets it through W11's operation or command, comes first; then `SEC_USER_AGENT`; then the settings folder's `.env`. Existing command-line setups therefore behave as before, and a value the desktop application sets is never silently overridden. `GET /v1/info` and `ian about` say which of the three is in use, without showing the value. |

Recording: API.20 and API.21 in this plan, the interface rules in the
[Master Plan's Product boundaries](../../../MASTER_PLAN.md#interfaces-and-separate-computers), and one engine issue that
the API.20 and API.21 pull requests close.

### A.19 Listing venue codes (2026-11-23)

Approved by the project owner on 2026-11-23, with the decisions made while the slice was built and reviewed recorded as amendments (V4, V6, V10) and additions (V13 to V19).
Closes engine issue 284. The evidence behind every mapped value is in the
[mapping record](API_22_LISTING_VENUE_MAPPING_RECORD.md).

| # | Decision |
| :--- | :--- |
| V1 | Slice identity: API.22, branch `feat/api-listing-venue-codes`, decisions recorded as this entry. Closes engine issue 284. |
| V2 | All three venue sources get a code: the identity's venue wherever it is served (the instrument profile document, the run overview, every strategy document's identity part and the replay documents) and the filing cover's venue in the share-unit provenance. One rule everywhere; no venue is left with provider wording alone because of where it appears. |
| V3 | Document shape. `listing_venue` becomes `ListingVenuePart \| null`, mirroring `InstrumentKindPart`: `{code: ListingVenue \| null, provider_value: str}`. The part is null exactly when the source gave no venue. This is an incompatible change made before the first release under [U2](#a7-structured-units-run-overview-and-command-free-database-messages-2026-11-13): the instrument profile document goes from `schema_version` 1 to 2, the run overview from 3 to 4, FCF Growth, Graham Growth and Graham Number from 14 to 15, Momentum from 13 to 14 and Piotroski from 5 to 6 and the specimen strategy's fixture from 1 to 2; the JSON Schemas, `openapi.json` and the help bundle are regenerated. Rejected: a sibling `listing_venue_code` field beside the unchanged string (two fields for one concept, and a silent change for clients). |
| V4 | Code granularity. A code means exactly what its source asserts. Amended on 2026-11-23: a code is exchange-level when the source names one exchange, and group-level when the source names only the group. The codes are `nasdaq`, `nyse`, `nyse_group`, `nyse_arca`, `nyse_american`, `cboe`, `cboe_bzx`, `txse` and `otc`. Tiers stay in `provider_value` (Yahoo's `NasdaqGS`, `NasdaqGM` and `NasdaqCM` map to `nasdaq`). The check the owner required of SEC's `NYSE` and `CBOE` found that `NYSE` covers listings on the New York Stock Exchange, NYSE American and NYSE Arca, so it maps to the group-level `nyse_group` with the term "NYSE Group Exchange". SEC's `CBOE` and Yahoo's `Cboe US` map to `cboe`, whose term says the source does not name which Cboe U.S. equities exchange. A filing cover's `Cboe BZX Exchange, Inc` and `CboeBZX` name one exchange and map to `cboe_bzx` ("Cboe BZX Exchange"). A bare `NYSE` on a cover is written by filers of all three NYSE exchanges and maps to `nyse_group`. |
| V5 | Unmapped values. A value in no reviewed table gets `code: null` with `provider_value` still served. The new glossary term "Listing Venue" explains the field itself, so every venue has at least that help; the venue field's term reference points to it. Its text says only that the venue is as the provider reports it, never that it is the primary listing, and that a cryptocurrency is not listed on an exchange and a provider's venue text for one may name where its price comes from. Non-US venues are out of scope and stay unmapped. Yahoo's `CCC` stays unmapped: no source was found for what it denotes, which the mapping record states. |
| V6 | Where the mapping lives. One module, `investment_analysis_engine/data/listing_venue.py`, holds the `ListingVenue` enum, one reviewed table per source (SEC ticker file, Yahoo, filing cover), the one function from a source and a provider's text to a code, and `LISTING_VENUE_TERMS`, registered as `ListingVenue` in `SHARED_CODE_TERMS`. Every value in a table has a captured specimen in the mapping record. Amended on 2026-11-23: the Yahoo table holds the `fullExchangeName` values and the `exchange` fallback codes the identity can store, captured under the same rule (`NMS`, `NGM`, `NCM`, `NYQ`, `PCX`, `ASE`, `BTS`, `TEX`, `PNK`, `OID`, `OQX`). |
| V7 | Keeping it current. The live suite requests SEC's ticker file once and fails, naming each exchange, when the file lists one the SEC table does not know. It is a separate live check, so `ian health` does not report an engine-side gap as a provider fault. Yahoo has no such check (open-ended set). |
| V8 | Saved runs and cached profiles. The code is worked out each time a document is built, from the stored provider text and the identity's provider; nothing new is stored: no `run_schema_version` change, no instrument profile schema bump, no migration. Old runs and cached profiles gain codes at once. This differs from instrument kind, which decides applicability and is therefore stored, because the venue only explains. A replayed old run's code can change from null to a code when a value is mapped later. |
| V9 | Open vocabulary. `ListingVenue` is an open vocabulary under [S4](API_2_SLICE_PLAN.md#s4-the-v1-additions-rule-2026-11-03): a new code is an addition within `/v1`. S4's list is amended, and `docs/user/API.md` says a client treats an unknown code like a null one, with `provider_value` still available. |
| V10 | Command-line text. A venue shows the code's glossary term name, followed by the provider's wording in parentheses when the two are not exactly equal; an unmapped value prints the provider's wording. The name has one home, the glossary, and is read through the help loader. Every text rendering (the instrument profile text, the strategy presenters' "Current listing venue" lines and the filing-venue lines of the price comparison) uses the one helper in `reporting/listing_venue_text.py`. Amended on 2026-11-23: `reporting` gains `help` among its imports in [Architecture §13](../../../ARCHITECTURE.md#13-module-boundaries) (layer 0, no cycle), the strategy presenters call the helper, the helper requests the English locale explicitly and the bundle is loaded once through the loader's cache. |
| V11 | Glossary content. Each code's entry gives, in plain English, the full name, the kind of market, the country, the venue's ISO 10383 market identifier code and one line of useful context, and no trading hours. The entries and the "Listing Venue" term are in `docs/user/GLOSSARY.md` next to the instrument kind terms, with Title Case names, served through the help bundle and the term references. |
| V12 | No desktop work in this slice. After the branch is pushed an issue on the desktop repository, "Venue term help and re-vendor to engine API.22", asks GUI.4c to re-vendor to API.22's merge commit, adapt ticker details and run detail to the `listing_venue` part, and show the venue's term help in the popups. |
| V13 | A filing cover's `SecurityExchangeName` of `NONE`, in any letter case, is the filer stating no exchange. It gives a null part, as V3 does for a source that gave no venue, never `code: null` with `provider_value` "NONE". Energy Transfer's latest cover says `NONE` for its common units although SEC's file and Yahoo list the ticker as `TXSE`; the mapping record states the finding. |
| V14 | A joined cover value (distinct values joined with `; `) is not in the table and stays unmapped, with its whole text as `provider_value`. |
| V15 | The specimen strategy's checked-in schema, a test fixture, is regenerated for the shared identity part (its version: V18). |
| V16 | Market identifier codes. Every MIC named in the glossary (`XNAS`, `XNYS`, `ARCX`, `XASE`, `BATS`, `BATY`, `EDGX`, `EDGA`, `TXSE`, `OTCM`) was verified on 2026-11-23 against the official ISO 10383 list published by the registration authority at iso20022.org, and a MIC is kept only where that list confirms it for that market. All ten were confirmed and none removed; the mapping record names the list and each entry. |
| V17 | Glossary wording. NYSE Arca says "Many" exchange-traded funds are listed on it. The over-the-counter entry no longer says the market is run by OTC Markets Group: it says OTC Markets Group operates the main US over-the-counter quotation system, that OTCQX, OTCID and OTCPK (Pink) are tiers of that system, and that SEC's list writes OTC without naming a tier. Amended on 2026-11-23: the entry's first sentence no longer gives a market identifier code, because OTCM names OTC Markets Group's quotation system and not the over-the-counter market as a whole; the second paragraph says so. |
| V18 | Specimen strategy. Its document's shape changed with the identity and provenance parts, so its fixture `DOCUMENT_SCHEMA_VERSION` rises from 1 to 2, per V3. The generator's template for a new strategy still starts at 1. |
| V19 | Text locale. `reporting/listing_venue_text.py` requests English by the named constant `_TEXT_LOCALE = "en"`, not through `DEFAULT_LOCALE`, which is the fallback for requests and may change independently of the language the text renderings are written in. The help package has no named constant for a single locale other than `DEFAULT_LOCALE`. |

### A.20 SEC EDGAR ticker coverage, explained and warned (2026-11-25)

Approved by the project owner on 2026-11-25, as decisions C1 to C22 of one list that also planned the Canadian-listings
work package and the engine order. Closes engine issue 302. Umbrella for Canadian listings: engine issue 301.

| # | Decision |
| :--- | :--- |
| C1 | A new investor glossary entry, SEC EDGAR Ticker List (`sec-ticker-list`): SEC's list of the companies that file with it, each under its US ticker symbol, so a ticker on an exchange outside the United States, such as NTR.TO, is not in it even when the company files with the SEC (Nutrien is NTR on the New York Stock Exchange). Linked from EDGAR, Provider Returned No Data, the entry of each strategy that reads SEC filings, the new warning's entry and each Canadian venue entry. Rejected: extending the EDGAR entry, which would mix what EDGAR is with which companies it lists. |
| C2 | The reason of a run stopped because SEC's ticker list does not include the ticker reads "SEC EDGAR's ticker list does not include {ticker}, so {input} could not be read from SEC filings. SEC EDGAR lists companies under their US ticker symbols only.", where `{input}` is the label of the required input that needed the company identifier, which the failure record already carries. One template for every strategy that reads SEC filings. Amends the message of [A.16](#a16-provider-no-data-is-an-unavailable-input-2026-11-21) E7 and E13 for this case only; a `ticker_unlisted` failure of another provider keeps its message. |
| C3 | New runs get C2's message; stored runs keep theirs, since runs are append-only. No method, result-schema, evidence-codec or document version changes: the status, reason code, failure element and every shape stay the same. |
| C4 | Each strategy declares in its behavior bundle a predicate saying whether a selection reads SEC EDGAR. A selection that supplies every filing input as an override does not (Graham Number with both EPS and book value per share overridden, Graham Growth with EPS overridden); Momentum never does. Rejected: one flag per strategy, which would warn wrongly for fully overridden selections. |
| C5 | A new entry warning, `ticker_not_in_sec_list`, an addition to the open warning-code vocabulary within `/v1`, with its own glossary entry. It is given when the add-entries check identified the ticker, an SEC identity is set up, at least one entry just added for the ticker reads SEC EDGAR, and SEC's ticker file, once loaded, lists no such ticker and no CIK override names it. At most one warning per ticker; `reason_code` null; the entry is never refused. A failure while asking SEC gives no warning and does not stop the check. |
| C6 | Its message: "{ticker} is not in SEC EDGAR's ticker list, so {strategies} will be unavailable for it: they read the company's financial statements from SEC filings. SEC EDGAR lists a company only under its US ticker symbol, so a ticker on an exchange outside the United States is not in the list even when the company files with the SEC." `{strategies}` joins the labels of the affected entries' strategies. |
| C7 | With no SEC identity set up, no new warning: SEC's list cannot be asked, and the strategies report the missing identity themselves. |
| C8 | No warning before a direct analysis; its result carries C2's reason. Same reasoning as [A.14](#a14-ticker-check-on-adding-entries-duplicate-wording-and-provider-statuses-2026-11-20) P2. |
| C9 | Listing-venue codes `tsx`, `tsxv`, `cboe_canada` and `cse` for the Toronto Stock Exchange, TSX Venture Exchange, Cboe Canada and Canadian Securities Exchange, each mapped only from Yahoo values captured live and recorded in the [mapping record](API_22_LISTING_VENUE_MAPPING_RECORD.md), each with an investor glossary entry linking `sec-ticker-list`. New codes are additions under [A.19](#a19-listing-venue-codes-2026-11-23) V9. |
| C10 | The command line prints the new warning as it prints the others ([A.14](#a14-ticker-check-on-adding-entries-duplicate-wording-and-provider-statuses-2026-11-20) P9). |
| C11 | No desktop change in this slice; the desktop repository re-vendors and shows the warning and venue names in its own work. |
| C12 | A new v0.2 work package, `CAN` (Canadian listings), row 15B of the [implementation plan](../IMPLEMENTATION_PLAN.md#sequence-and-status), with its own plan written by CAN.0. Milestone v0.4's Step 5 in the [Master Plan](../../../MASTER_PLAN.md#step-5-localization-engine-for-canadian-markets-en-ca--fr-ca) stays language and number formatting; CAN.0 adds a line there pointing to CAN for Canadian market data, and names CAN in the [Evidence Provider Roadmap](../../../EVIDENCE_PROVIDER_ROADMAP.md)'s security-identity row. |
| C13 | Order of coverage. First, a Canadian-listed ticker whose company files annual reports with the SEC (10-K, 20-F or 40-F), which covers most large companies on the Toronto Stock Exchange. Companies that file only in Canada are researched in CAN.0 with no commitment until a data source is approved (C17). |
| C14 | Slices. CAN.0: evidence and plan, documentation only (captures for about ten issuers, linking methods, the currency-rate source and its licence, a survey of sources for companies that do not file with the SEC, and how many targets file under IFRS). CAN.1: link a Canadian ticker to its SEC filer, so the strategies that read financial facts run; price comparisons stay suppressed where currencies differ; folds in engine issue 293. CAN.2: currency conversion for price comparisons, which also serves US listings of companies that report in Canadian dollars. CAN.3, only if approved later: a source for companies that do not file with the SEC. CAN.0 places engine issue 294 (IFRS book value per share) from its IFRS count. |
| C15 | Linking a Canadian ticker to its SEC filer is deterministic, never fuzzy name matching (company names already differ between sources). CAN.0 evaluates matching the share-class FIGI of the Canadian and US listings through OpenFIGI, a reviewed link table built from captured evidence, and a link the investor declares, including the existing CIK override file. The link and its evidence show in the instrument profile; like today's identity, it is current only. |
| C16 | Never compare across currencies without conversion. CAN.2 converts with an official, free, point-in-time rate whose publication time is known and recorded in provenance; Bank of Canada daily rates are the first candidate, its licence confirmed in CAN.0. A new outbound host goes through the guarded-egress rule with its own decision. |
| C17 | No source is chosen for companies that do not file with the SEC. CAN.0 surveys candidates (licence for local use, cost, point-in-time, coverage) and brings a separate decision; until then those tickers get C1's and C9's explanation. |
| C18 | Engine order from 2026-11-25: API.23, engine issue 304 (fast lane), engine issue 305, API.24, CAN.0, CAN.1, engine issue 307, API.20 and API.21, CAN.2, then Step 3.5's 3.5.5 and 3.5.4 as planned. |
| C19 | 3.5.5 follows CAN.2; [A.15](../step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a15-355-before-354-2026-11-02) (3.5.5 before 3.5.4) is unchanged. |
| C20 | New investor text in this slice follows engine issue 305's wording rule (no "the engine", no "the provider"); issue 305 rewords the rest of the glossary. |
| C21 | When this slice merges, the spec-workflow pilot's measures go to the project owner for the adopt, adjust or drop decision of the [spec workflow §7](../../../SPEC_WORKFLOW.md#7-pilot), if it is the third spec-driven unit. |
| C22 | Recording: API.23 and API.24, and records A.20 and A.21, in this plan; work package CAN and the engine order in the implementation plan's `CAN` entry; one line in Step 3.5's sequence. |

### A.21 Explain why a result has no number (2026-11-25)

Approved by the project owner on 2026-11-25, as decisions C23 to C31, after a Graham Number run for MSFT read
"Book value per share is unavailable: The preferred share count could not be resolved: Provider returned no data for
the requested field. Missing preferred-share data is not assumed to be zero." Built by API.24; engine issue 306.

| # | Decision |
| :--- | :--- |
| C23 | Every result without a number (`input_unavailable`, `not_applicable` and the provider-failure statuses, every strategy) gets an explanation beside its short reason, in up to four parts: what the method needs (the input and why the method uses it), what was found (what the named data source had), why there is no number (the guess the method declines to make, and why a guessed number would mislead), and what the investor can do (an override, another strategy, checking the ticker, or nothing). |
| C24 | The explanation is built when a document or text is produced, from the stored structured fields (reason code, failed input, failed component where the trace records it, data source, failure kind), never from message text. It is an additive `explanation` part of each strategy's run document and appears in the command-line text; each document's `schema_version` goes up by one. No stored result, evidence codec, method or result-schema version changes, so saved runs get the explanation too. |
| C25 | Where the stored structure is not specific enough, the explanation falls back to the reason-code level, still in four parts. Adding structure to new results is a separate decision, never done by reading text. |
| C26 | API.24's spec catalogues every combination of status, reason code and input each strategy produces, with its explanation; a test fails when a combination has none, so every later strategy ships with explanations. |
| C27 | Investor wording only: no "resolved", "provider", "field" or "the engine"; the data source by name. The shared resolver's "Provider returned no data for the requested field." is reworded for new runs to name the source and the input. |
| C28 | A new investor glossary entry, Why a Result Can Be Unavailable (`unavailable-by-design`): an analysis gives no number rather than one built on a guess, and an unavailable result is information about the company's filings, not a fault. Linked from the Unavailable outcome entry and from every explanation. |
| C29 | Example voice, for MSFT: needs "Book value per share is stockholders' equity, less any preferred stock, divided by the common share count."; found "Microsoft's SEC filings do not report a preferred share count."; no number "A company that has no preferred stock often does not report the count at all, but a missing count can also hide preferred stock that should be subtracted. Assuming zero could overstate book value, so the Graham Number is not calculated."; you can "If you know the book value per share, enter it as an override and run the analysis again." Final texts are in API.24's spec. |
| C30 | The desktop application shows the explanation under the reason after re-vendoring, in its own work. |
| C31 | Explaining is not enough where the gap is in coverage: engine issue 307 asks for a third verified evidence path for zero preferred shares (for example a filing's balance sheet with no preferred stock line, or a reported preferred stock value of zero), captured on MSFT and similar filers, never assumed from absence. It follows CAN.1. |

### A.22 Investor glossary wording (2026-11-27)

Approved by the project owner on 2026-11-27, as decisions G1 to G10. Closes engine issue 305; the served guides follow
in engine issue 310.

| # | Decision |
| :--- | :--- |
| G1 | Recorded in this plan as sequence row Issue 305 and this record; the unit's spec is `specs/issue-305.md`, its branch `docs/investor-glossary-wording`. This plan owns it because the help bundle and the glossary rules came from API.5 and API.6. |
| G2 | Scope: every investor entry of the user glossary (names, short definitions and bodies), with the page's title, introduction and group introductions, which are served with them. The command-line section and the contributor glossary change only to receive moved detail. |
| G3 | "the engine" and "Investment Analysis Engine" become "this application" where the behavior matters to an investor, and are removed where it does not. "a/the provider" and "data provider" become "a/the data source", or the source's name (SEC EDGAR, Yahoo Finance) where one is meant. Code values in backticks, such as `provider_no_data`, stay, since they are API values. "This application" reads correctly in the desktop application and on the command line. |
| G4 | Term names change, with every id and anchor kept: Data Provider becomes Data Source; Provider Error, Data Source Error; Provider Unreachable, Data Source Unreachable; Provider Rate-Limited, Data Source Limiting Requests; Provider Unexpected Response, Unexpected Answer from a Data Source; Provider Returned No Data, No Data from the Data Source; Provider Healthy, Data Source Answering Normally; Provider Not Checked, Data Source Not Checked. |
| G5 | The Nasdaq entry explains the three tiers, Global Select Market, Global Market and Capital Market: listing standards (size, financial and liquidity requirements) are strictest for Global Select and the Capital Market serves smaller companies; a company's tier is a rough sign of its size and trading liquidity, not a rating. The tier codes stay in one sentence, because an investor sees them beside the name. No numeric thresholds: they change over time and would need checking against Nasdaq's rules on every edit. |
| G6 | Detail with no investor relevance moves to the contributor glossary, or is dropped where a contributor document already says it. The unit's spec lists each move. |
| G7 | `scripts/check_help_content.py` refuses the whole words "engine" and "provider", in any case and with their plurals, in an investor entry's name or text outside code spans and link destinations. It runs in the gate and in the help-bundle generator, like the other glossary rules. No word-level allow list. |
| G8 | The served guides (Beginner Guide, Finance Math's served sections, the strategy guides) are not in this unit. Engine issue 310 rewords them and extends G7's check to served sections; it is placed right after this unit. |
| G9 | Messages produced by code that say "the engine's database" or "data provider" are not changed here; API.24 rewords investor messages ([A.21](#a21-explain-why-a-result-has-no-number-2026-11-25), C27). |
| G10 | No API shape or version change: term ids, anchors and code values stay, only the served names and text change, and the help bundle is regenerated. Help text carries no compatibility guarantee; ids do. The desktop application picks up the text when it next re-vendors; no desktop issue is filed. |

### A.23 Served guides in investor words (2026-11-27)

Approved by the project owner on 2026-11-27, as decisions H1 to H10. Closes engine issue 310, which follows engine
issue 305 ([A.22](#a22-investor-glossary-wording-2026-11-27), G8).

| # | Decision |
| :--- | :--- |
| H1 | Recorded in this plan as sequence row Issue 310 and this record; the unit's spec is `specs/issue-310.md`, its branch `docs/investor-guide-wording`. API.24 stays Planned until this unit completes. |
| H2 | Scope: the served sections of the Beginner Guide, Finance Math and every strategy guide: titles, introductions, prose, tables, fenced text blocks and link texts. Excluded command-line sections are not changed. The glossary is not touched. |
| H3 | The words of G3: "Investment Analysis Engine" and "the engine" become "this application" where the behavior matters to an investor and are removed where it does not; "a/the provider" and "data provider" become "a/the data source", or the source's name (SEC EDGAR, Yahoo Finance). Code values in backticks, such as `provider_error`, `provider_no_data` and `provider_failure`, stay. |
| H4 | Other internal words in served text are replaced too, line by line in the spec: "the Yahoo adapter" becomes Yahoo Finance; "production tool boundary", "current production SEC EDGAR mapping" and "current production analysis" become plain statements of what the analysis does; "the resolver" and "resolver clock" become "the analysis" or the as-of rule in investor words. They are not added to the check: they are rare, and "production" has ordinary uses. |
| H5 | Where "the project" or "the program" means the software in the Beginner Guide, it becomes "this application"; the guide's title becomes "A Beginner's Guide to Investment Analysis", and the README link's text becomes "limitations and disclaimer". Finance Math's "the project may someday support" becomes "this application". Headings that carry a section id keep their wording, so section ids do not change. "Project" is not added to the check. |
| H6 | Link texts that repeat a term name renamed by G4 take the new name ("Provider error" becomes "Data source error"); link destinations and anchors do not change. |
| H7 | Finance Math changes wording only: no formula, condition, threshold, ratio, date rule, reason code or status changes meaning. The spec lists every changed Finance Math line before and after, and the review compares Finance Math with that list. "Provider concept" becomes "reported concept"; "Provider split adjustments" becomes "Split adjustments in the price history". |
| H8 | The command line's `Provider split adjustments applied:` (and its `: none` form) becomes `Split adjustments in the price history applied:` in the FCF Growth presenter and its test, so the FCF Growth guide's sample output and Finance Math keep matching the output. Every other message produced by code stays with API.24 ([A.21](#a21-explain-why-a-result-has-no-number-2026-11-25), C27; [A.22](#a22-investor-glossary-wording-2026-11-27), G9). |
| H9 | `scripts/check_help_content.py` extends G7 from investor glossary entries to every served section outside the user glossary: its title and lines, fenced blocks included, outside code spans and link destinations, never use the whole words "engine" or "provider", in any case and with their plurals. Excluded sections are not checked; no allow list. The rule is stated in the project README's "Served documents" section. |
| H10 | No API shape or version change: document ids, section ids, term ids and code values are unchanged, and the help bundle is regenerated; only served text and the Beginner Guide's title change. The desktop application picks up the text when it next re-vendors; no desktop issue is filed. |
