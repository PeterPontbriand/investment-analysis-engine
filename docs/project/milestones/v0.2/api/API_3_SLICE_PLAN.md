# API.3 — Slice Plan: Execution Composition, Watchlist Actions and Refresh with Progress

Splits [API.3](API_CONTRACT_AND_SLICE_PLAN.md#api3--application-layer-actions) into three slices. The first moves
strategy execution out of the CLI, adds direct analysis as an operation and writes this plan. The second adds the
watchlist actions and builds a selection from its model's fields, in two slices
([W14](#w14-api3b-is-two-slices-2026-11-05)). The third adds refresh with progress.

## 1. At a glance

- **What this plan does:**
  - API.3a moves production composition and every strategy's execution into `application` and adds direct analysis of
    one ticker as an operation, which the direct commands call;
  - API.3b1 adds the watchlist actions and switches the CLI to them;
  - API.3b2 builds a selection from its model's fields, adds the per-strategy `add-selection` subcommands, the selection
    schemas and their conformance check, and settles Site 19;
  - API.3c moves refresh into `application` with an observational progress callback.
- **What it does not do:** add an endpoint, change a stored shape, a formula or a classification, or add a dependency.
  API.3a and API.3c change no CLI output. The CLI changes are API.3b1's
  ([W11](#w11-every-watchlist-writing-command-has---json-2026-11-05) and
  [W18](#w18-arguments-are-checked-before-the-database-opens-2026-11-05)) and API.3b2's
  ([C12](#c12-site-19-is-settled-by-one-add-selection-subcommand-per-strategy-2026-11-04)).
- **Rules every slice follows:**
  - one execution path: the CLI and, in API.4, the API call the same operation, and the CLI holds no
    strategy-specific rendering or composition;
  - nothing in `application` names a strategy except the application tier, which is the one declaration that pairs each
    strategy's functions with its core bundle ([C3](#c3-the-application-tier-2026-11-04));
  - composition reads no module-level settings object: it takes the application context
    ([C4](#c4-composition-takes-the-application-context-2026-11-04));
  - the managed quality gate, with the Python 3.14 second pass, after each slice, and the project owner's approval
    before the next slice starts.
- **Sequence rule** (approved 2026-11-04): each slice's pull request marks its own row Complete, dated the day the pull
  request is opened, and sets the next slice's row to Next.
- **Where the history lives:** decisions C1 to C18 and C5a are in [Appendix A](#appendix-a-decision-records), approved
  by the project owner on 2026-11-04.

## 2. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| API.3a | [Execution composition and direct analysis](#api3a--execution-composition-and-direct-analysis) | Complete | 2026-11-05 |
| API.3b1 | [Watchlist actions](#api3b1--watchlist-actions) | Complete | 2026-11-05 |
| API.3b2 | [Selections and Site 19](#api3b2--selections-and-site-19) | Next | |
| API.3c | [Refresh with progress](#api3c--refresh-with-progress) | Planned | |

## 3. The slices

### API.3a — Execution composition and direct analysis

- **Problem:** each strategy's providers, resolvers, settings loader and presentation are built inside its CLI file, and
  production composition reads a module-level settings object, so nothing but the command line can run a strategy.
- **Decision:**
  - a file directly inside a strategy package whose name is a unit belongs to that unit
    ([C2](#c2-one-rule-a-file-named-for-a-unit-belongs-to-that-unit-as-amended-2026-11-04)): `execution.py` becomes
    `workspace.py`, and each strategy gains an `application.py`;
  - an application tier pairs each strategy's run function and refresh executor with its core bundle
    ([C3](#c3-the-application-tier-2026-11-04));
  - composition takes the application context ([C4](#c4-composition-takes-the-application-context-2026-11-04));
  - direct analysis is `analyze(...)`, which returns an `AnalysisOutcome`
    ([C5a](#c5a-direct-analysis-is-an-operation-that-returns-an-outcome-2026-11-04)), with the provider check inside
    it ([C7](#c7-the-provider-check-moves-into-application-2026-11-04));
  - `cli_composition.py` is deleted ([C8](#c8-cli_compositionpy-is-deleted-2026-11-04)).
- **Scope:**
  - every strategy package: `execution.py` renamed `workspace.py`, a new `application.py`, and a `cli.py` reduced to its
    options and a call to the operation;
  - `application/`: `providers.py`, `analysis.py`, `tier.py`, `failures.py`, `provider_check.py` and `strategy_run.py`;
  - the CLI modules the moves touch, `cli_composition.py` and `cli_run_support.py` deleted;
  - the scripts, templates and site data that name the moved files, Architecture §13, `docs/TOOL_DEVELOPMENT.md`, this
    plan and the contract.
- **Branch:** `feat/api-execution-composition`.
- **Detail:** [Implementation record](#31-api3a-implementation-record).

### API.3b1 — Watchlist actions

- **Problem:** watchlist create, rename, delete, add and remove are CLI-only: each command opens the database and calls
  the repository itself, which the API cannot call.
- **Decision:**
  - watchlist actions take one reference, a name or an ID, resolved inside the action's own transaction
    ([C9](#c9-watchlist-actions-take-one-watchlistref-2026-11-04));
  - an action writes and reads back in one transaction ([W8](#w8-a-watchlist-action-writes-and-reads-back-in-one-transaction-2026-11-05)),
    delete is confirmed and done by ID ([W9](#w9-delete-is-confirmed-and-done-by-id-2026-11-05)), the actions check their
    own arguments ([W10](#w10-argument-checks-are-in-the-actions-2026-11-05)) and every writing command has `--json`
    ([W11](#w11-every-watchlist-writing-command-has---json-2026-11-05));
  - the implementation decisions W15 to W26 ([Appendix A](#appendix-a-decision-records)).
- **Scope:** the watchlist actions and `application/parameters.py`; the repository's write methods and
  `StoredSelectionError`; the CLI switched to the actions, with `--json` on five commands; the tests and the documents
  they touch. `WatchlistFlags`, the `--analysis` option of `create` and `add-selection`, and the Momentum defaults the CLI
  reads are API.3b2's and stay as they are.
- **Branch:** `feat/api-watchlist-actions`.
- **Detail:** [Implementation record](#32-api3b1-implementation-record).

### API.3b2 — Selections and Site 19

- **Problem:** a selection is built from a flag bundle that every strategy shares, and a client has no description of a
  strategy's selection fields.
- **Decision:**
  - `build_selection(context, method_id, fields)` applies the configured defaults to omitted fields and then the
    selection model validates ([C10](#c10-selection-is-built-from-model-fields-2026-11-04)), and validation names model
    fields ([C11](#c11-selection-validation-names-model-fields-2026-11-04));
  - `WatchlistFlags` is replaced by one `add-selection` subcommand per strategy
    ([C12](#c12-site-19-is-settled-by-one-add-selection-subcommand-per-strategy-2026-11-04));
  - one schema per strategy, compared in the gate ([C13](#c13-one-selection-schema-per-strategy-2026-11-04)), with the
    form-supported field types of [C14](#c14-form-supported-field-types-2026-11-04);
  - the implementation decisions W1, W3 to W7, W12 and W13 ([Appendix A](#appendix-a-decision-records)); W2 was done
    before API.3b, in its own pull request.
- **Scope:** `build_selection`; the selection schemas and their generator and conformance check; the CLI change of C12
  with the documents it touches; the closure of Site 19 in the documents named in C12.
- **Branch:** `feat/api-selections`.
- **Detail:** ⚠ no implementation record yet. Decisions C10 to C14 are in [Appendix A](#appendix-a-decision-records).

### API.3c — Refresh with progress

- **Problem:** a refresh reports nothing until it ends, and the CLI owns its coordination.
- **Decision:** refresh moves into `application` with a typed progress event sent only from the refresh's coordinating
  thread ([C15](#c15-progress-events-2026-11-04)); a failing callback never fails the refresh
  ([C16](#c16-a-failing-progress-callback-2026-11-04)); `ian refresh` shows no progress and its output does not change
  ([C17](#c17-ian-refresh-shows-no-progress-2026-11-04)).
- **Scope:** the refresh operation, which builds its own probe as `analyze` does (today `cli_workspace.py`'s refresh command is the one module outside `application/` that builds one), the progress event types, the cancellation event the CLI already uses, and the CLI
  switched to the operation.
- **Branch:** `feat/api-refresh-progress`.
- **Detail:** ⚠ no slice plan yet. Decisions C15 to C17 are in [Appendix A](#appendix-a-decision-records).

### 3.1 API.3a implementation record

What changed, by area:

- **Strategy packages:**
  - `execution.py` is `workspace.py` in each, with a module docstring that says what the file does; the `execute_<name>`
    functions keep their names;
  - each has a new `application.py` holding its run function (`run`), its refresh executor (`refresh`) and, where the
    strategy has them, its settings loader and its composition (`momentum_settings`, `graham_growth_settings`,
    `compose_piotroski`). The run function composes the run's dependencies, calls the `workspace.py` adapter and returns a
    `StrategyRun`: the normalized capture, a builder of the typed document and a renderer of the text modes, both built
    from the strategy's own presentation and presenter;
  - the Graham resolver builder is `strategies/_graham/application.py`, called by both Graham strategies with their
    resolver class;
  - each `cli.py` keeps its options, its selection builder for the watchlist commands and its command, which parses,
    builds the selection and calls the operation. None imports a presenter.
- **`application`:**
  - `providers.py`: the SEC adapter and provider builders, the SEC settings loader, `load_all_component_settings`, and
    the historical-client, financial-cache and instrument-profile-cache builders that were in `cli_support.py`. Each
    takes the application context;
  - `analysis.py`: `analyze`, `AnalysisOutcome` and `FAILURE_OUTCOMES`;
  - `strategy_run.py`: `StrategyRun`, the type a strategy's run function returns to the operation;
  - `tier.py`: the application tier ([C3](#c3-the-application-tier-2026-11-04));
  - `failures.py`: `SaveStage`, `SavingFailureError`, `saving_failures`, `InternalDefectError`,
    `stored_configuration` and `require_job_ticker`, moved out of `cli_support.py` because the operation raises them;
  - `provider_check.py`: the check, its findings, the wording of its lines and `with_provider_check`, moved out of
    `cli_provider_check.py`;
  - `providers.py` also holds `build_provider_clients` and `build_provider_probe` (review fix G1).
- **CLI:** `cli_composition.py` and `cli_run_support.py` are deleted. `cli_support.py` gains `application_context`,
  `analyze_for_command` and `analysis_output`, which every direct command calls; it keeps the failure translation and
  `get_cli_run_context`. `cli_provider_check.py` keeps the Typer-context choice and `echo_provider_check`.
  `cli_strategy_wiring.py` keeps `build` and `command`; the refresh executor moved to the application tier.
  `cli_workspace.py` and `cli_health.py` call the moved functions with a context built from their settings.
- **Scripts and data:** `scripts/package_graph.py` and `scripts/check_package_dependencies.py` attribute a file by its
  name to the unit of that name; `scripts/new_strategy.py` writes `workspace.py` and `application.py` from their
  templates and adds an entry to the application tier; `scripts/strategy_sites.toml` and `scripts/strategy_conformance.py`
  have the `workspace`, `application` and `application-tier` sites and the application tier's closed-ness and fail-closed
  checks; `scripts/check_installed_package.py` imports from the new homes.
- **Docs:** Architecture §13 (the rule and the `application` row), `docs/TOOL_DEVELOPMENT.md` (including the regenerated
  edit-site table), this plan and the contract.

The decisions as implemented, with the points that differ from the wording of the decision:

- **C2.** As approved. The shared Graham resolver builder is one function because the two strategies' code is the same;
  it takes the resolver class.
- **C3.** As approved. `application/tier.py` is the one module in `application/` that imports each strategy's
  `application.py`; this is the pairing declaration that C3 requires, as `cli_strategy_wiring.py` is for the CLI. The
  layering test lists it, and `application.analysis` and `cli_workspace`, as its only importers.
- **C4.** As approved. The settings cache was already keyed by the settings folder. `cli_workspace.py` reads Momentum's
  option defaults with the generic loader and `MomentumSettings`, because the layering rule lets a module outside the
  strategies import a strategy's settings model but not its `application` file.
- **C5a.** As approved, with two points the decision leaves open:
  - `render_text(mode)` returns what the command prints, which after a failure starts with the provider-check lines, so
    a command writes it as it is, and API.4's text endpoint gets the same lines (an amendment approved on
    2026-11-04); the lines are not added a second time;
  - the saved run's ID is reported by the command on standard error before the result, as before, from
    `analysis_run_id`.
- **C6.** As approved: no field was added.
- **C7.** As amended on 2026-11-04 ([review fix G1](#review-fixes-2026-11-04)): the probe is built per operation from
  the context's settings by `build_provider_probe(context)`, not passed on the context. `provider_check: bool` is the
  choice of `--no-provider-check`, reported to the probe as `requested`. `ian health` and the refresh command call the
  moved check.
- **C8.** As approved. `cli_run_support.py` is deleted too: nothing remained in it.

Approved output change (2026-11-04): the save step's database check runs before a strategy composes its providers.
With `--save-run`, no SEC identity and a database that needs an upgrade, a command that used to report
`configuration_error` now reports the database's code (`database_upgrade_required`). Checked against `main` for each
strategy, with and without `--no-cache`:

| Strategy | On `main` | On this branch |
| :--- | :--- | :--- |
| Momentum | database code | database code (unchanged) |
| Graham Number | database code; `configuration_error` with `--no-cache` | database code |
| Graham Growth | database code; `configuration_error` with `--no-cache` | database code |
| FCF Growth | database code; `configuration_error` with `--no-cache` | database code |
| Piotroski | `configuration_error` | database code |

The Graham and FCF Growth commands opened their cache, which checks the database, before building the SEC provider, so
only the `--no-cache` form changed. Piotroski composed its analyzer before the save step in every form. This corrects the
earlier statement that no command could reach the difference. One further difference remains in an edge case that no
valid option reaches: a Graham or FCF Growth selection that cannot convert to its configuration raises the defect error
that refresh always raised, where the direct command raised the validation error.

User-visible changes: the output change above. No other CLI output, text, `--json`, help text, message or exit code
changed, and no stored shape changed.

Tests edited, and why (each is an import path, a patch target or the C4 context argument):

- Patch targets that moved with the code (`strategies.<name>.cli.<function>` to `strategies.<name>.application.<function>`
  and `cli_run_support` to `application.analysis`): `tests/_direct_command_output.py`,
  `tests/_strategy_document_output.py`, `tests/test_cli.py`, `tests/test_cli_financial_cache.py`,
  `tests/test_cli_historical_cache.py`, `tests/test_cli_fcf_earnings_growth.py`, `tests/test_cli_save_run.py`,
  `tests/test_cli_database_readiness.py`, `tests/test_existing_strategy_failure_output.py`,
  `tests/test_graham_comparison_composition.py`, `tests/test_graham_growth_default_policy.py`,
  `tests/test_command_validation_failures.py`, `tests/test_cli_graham_commands.py`,
  `tests/test_failure_messages.py`, `tests/test_save_run_every_direct_command.py` and
  `tests/test_cli_momentum_statuses.py`.
- C4, a fake or a call that gained the context argument: the fixtures for `production_financial_cache` and
  `production_historical_client` in `tests/_direct_command_output.py`, `tests/test_cli_fcf_earnings_growth.py` and
  `tests/analysis/fcf_earnings_growth/test_market_data_composition.py`; the direct calls of the cache builders in
  `tests/test_cli_financial_cache.py`, `tests/test_cli_historical_cache.py` and `tests/test_cli_database_readiness.py`;
  the SEC settings tests in `tests/data/test_sec_edgar_settings.py` and the resolver tests in `tests/test_cli.py`, which
  pass a context whose settings folder is the test's instead of patching the removed `_settings_folder`;
  `tests/test_cli_piotroski.py` and `tests/analysis/piotroski/test_piotroski_wiring.py`, which patch the adapter builder
  with a function that takes the context; `tests/test_specimen_strategy.py`, whose settings tests pass a context;
  and `tests/test_cli.py`, whose missing-identity test patches the settings the command reads.
- The isolation fixtures no longer rebind `cli_run_support.settings`, which no longer exists: `tests/_cli_isolation.py`,
  `tests/test_cli_save_run.py`, `tests/test_failure_messages.py` and `tests/test_save_run_every_direct_command.py`.
- Moved names: `tests/_failure_code_table.py` and `tests/test_failure_messages.py` (the defect errors),
  `tests/test_cli_provider_check.py`, `tests/test_provider_check_element.py` and
  `tests/workspace_documents/test_workspace_documents.py` (the provider check; `test_provider_check_element.py` also
  looks for the probe call in its new module), `tests/test_startup_component_settings.py` and
  `tests/workspace_documents/test_analysis_run_replay.py` (the settings loader that must not be called).
- Review fixes (G1): the probe is built per operation, so tests that handed a probe through the Typer context
  (`obj=probe`) or patched `cli.build_provider_probe` use `tests/_probe_injection.py`, which patches the three builders the
  commands reach: `tests/test_cli_provider_check.py`, `tests/test_provider_check_element.py` and
  `tests/test_graham_render_execution.py`; `tests/test_cli_health.py` and `tests/live/test_provider_response_shape.py`
  call the clients builder from `application/providers.py` with a context; `tests/utils/_logging_command_driver.py` makes
  `execution_errors` raise where it made the removed `provider_check_choice` raise; `tests/application/test_context.py`
  is back to one field; `tests/scripts/test_new_strategy.py` no longer expects `typer.Context` in the command.
- Replaced with tests of the new homes: `tests/test_cli_composition_adapter.py` is `tests/application/test_providers.py`;
  `tests/test_cli_command_helpers.py` tests `analysis_output` where it tested `render_execution` and
  `analyze_and_maybe_save`, whose cases are now `tests/application/test_analysis.py`;
  `tests/test_cli_strategy_wiring.py` lost its refresh cases, which are `tests/application/test_tier.py`.
- The layering and role tests: `tests/test_strategy_import_layering.py` and `tests/_strategy_roles.py` (the `workspace`
  and `application` roles, the application tier and its importers), `tests/_wiring_gaps.py`,
  `tests/test_strategy_wiring_conformance.py` (the `workspace` site) and the specimen strategy under `tests/specimen/`
  (`workspace.py`, `application.py`, `application_tier.py`, and the context and CLI files that follow).
- Fakes and patch targets that follow the same moves, found when the gate ran: `tests/_runs_compare_refresh.py`,
  `tests/test_workspace_integration.py`, `tests/test_graham_render_execution.py`, `tests/test_cli_graham_commands.py`,
  `tests/test_command_validation_failures.py` and `tests/test_graham_growth_default_policy.py` (the last three patch the
  command's call of the operation where they patched the removed `_run_<name>` helpers); `tests/application/test_context.py`
  (the context's second field); `tests/test_documented_conventions.py`, `tests/test_cli_support.py` and
  `tests/analysis/fcf_earnings_growth/test_fcf_market_cap.py` (`exit_code_of` is now defined in `application/analysis.py`,
  the one home of the unavailable and failed pairing); `tests/scripts/test_new_strategy.py`,
  `tests/scripts/test_strategy_sites.py` and `tests/scripts/test_check_package_dependencies.py` (the new roles and sites).
- The generator's end-to-end test (`tests/scripts/test_new_strategy_end_to_end.py`) fills `application` instead of `cli`,
  and its fill file is `application.py.fill`.

New tests:

- `tests/application/test_tier.py`: pairing, the closed tuple, a strategy without an entry failing, and a selection of
  another strategy rejected.
- `tests/application/test_analysis.py`, over `STRATEGIES`:
  - unsaved (no run ID, no stored run) and saved (the ID returned, the stored run replays to the same document);
  - each text mode equals, byte for byte, what the direct command printed on `main`
    (`tests/expected_output/analysis_text/`, recorded from `main` before the change, and
    `tests/expected_output/direct_commands/` for the document), ignoring only the reading of the wall clock;
  - the outcome gives the exit code the command gives;
  - a provider failure with the check on and off, in the document and in the text, and a failure without a probe;
  - `as_of` reaches the document;
  - the outcome has exactly the four fields and none holds a raw execution or a strategy type, and no strategy's `cli.py`
    imports a presenter.
- `tests/application/test_providers.py`: the builders, two contexts with different settings folders reading each
  folder's files, and no composition module importing the module-level settings object.
- Review fixes: `tests/test_save_run_step_order.py` (over `STRATEGIES`, with and without `--no-cache`, `--json` and
  text: the database's code, not the SEC configuration error); in `tests/application/test_analysis.py` two calls build two
  probes, the settings switch the check off, and no `application` module holds a module-level probe; the existing refresh
  test with several failing jobs on one provider shows one test request per refresh.
- The package-dependency script and the layering test attribute `workspace.py` and `application.py` by name:
  `tests/scripts/test_check_package_dependencies.py` and `tests/test_strategy_import_layering.py`. The generator test
  produces a strategy whose files pass the conformance checks.

#### Review fixes (2026-11-04)

The project owner reviewed the branch and approved these fixes, all done:

- **G1.** `ApplicationContext` is back to `settings` only. `build_provider_probe(context)` is in
  `application/providers.py` and reads `provider_check` and `provider_check_timeout_seconds` from the context's settings.
  `analyze` builds one probe per call and the refresh command one per refresh (API.3c's refresh operation will follow
  this); none lives in a module. The CLI root's `build_provider_probe` and the `context.obj` hand-off are
  gone, the direct commands and `refresh` no longer take the Typer context, and `--no-provider-check` and
  `IAN_PROVIDER_CHECK` behave as before. The clients builder moved from `cli_health.py` with it.
- **G2.** The step order above is recorded as an approved output change, with a test over `STRATEGIES`.
- **G3.** `tests/application/test_analysis.py` masks only the values on the `Analysis timestamp:` and
  `Originally retrieved:` lines, the only text lines that hold the run's own reading of now. Every other time is compared
  exactly, and no recorded file differed from the operation's text on any other line.

- **H1.** The trace and its result, then the branch taken.
  - *What can leave `analyze`:* only an exception that carries a `kind` and a `provider_id` becomes a `provider_failure`
    in a failure envelope, and only `DataFetchError` and `FinancialProviderError` do. Every call that reaches a provider
    on a path of `analyze` is wrapped, so a provider failure is stored in the run:

    | Strategy | Provider calls on its path | Where the failure is caught |
    | :--- | :--- | :--- |
    | Momentum | the price history (through the cached client); the profile's identity and kind | `MomentumAnalyzer._fetch` catches `DataFetchError` and returns the stored `provider_error`; the profile lookups in `data/instrument_profile.py` catch both types |
    | Graham Number, Graham Growth | the input resolver's facts and quote; the security-unit lookup; the profile | `InputResolver` catches `FinancialProviderError` at each of its four provider calls and returns a provider-error result; `resolve_security_unit` and the profile lookups catch both types |
    | FCF Growth | the annual series; the quote, share counts, split history and cover listing; the profile | the same resolver; `metric_inputs.py` catches `FinancialProviderError` or `DataFetchError` at the anchor, split-history, cover-listing and share-count calls; the profile lookups |
    | Piotroski | the statements series; the as-filed industry class; the profile | the same resolver and `metric_inputs.py` (`resolve_industry_class` catches `FinancialProviderError`); the profile lookups |

    The save step and the composition (`build_*`, the cache and database openers) reach no provider. An instrumented full
    run of the test suite agrees: the failure translation saw a provider failure 39 times, and every time the exception
    was raised by a test that replaced a function inside the analyzer, or by a unit test of the translation itself; no
    test with real fixtures reached it. No path was found.
  - *Branch taken:* none exists, so the provider-check branch is deleted from `execution_errors` along with its
    `provider_check` parameter and every command's argument for it; a provider failure that did leave `analyze` as an
    exception would be reported without a check. Output of every reachable case is unchanged.
  - *Tests:* `tests/test_cli.py::test_cli_momentum_classified_failure_names_its_kind_in_text_and_json` forces such an
    exception by replacing `run_analysis`, a case no input reaches, and no longer expects the "not checked" line it only
    got from the deleted branch; it still checks the message, the code and the `provider_failure` element. The helper in
    `tests/_probe_injection.py` patches two builders instead of three. A new test,
    `tests/application/test_providers.py::test_only_the_application_and_the_refresh_command_build_a_probe`, fails if any
    module outside `application/` and `cli_workspace.py` builds a probe. The refresh command builds one until API.3c moves
    refresh into its operation.

Accepted deviations, as recorded above: the application tier is the only module in `application/` that names strategies;
`exit_code_of` lives in `application/analysis.py`; `cli_workspace.py` loads Momentum's option defaults until API.3b
removes them; an unconvertible Graham or FCF Growth selection raises the refresh's defect error.

Noticed for later slices:

- API.3b: `cli_workspace.py` still reads Momentum's option defaults for the watchlist commands; C12 replaces those
  options with per-strategy subcommands that share each strategy's options with its direct command.
- API.3c: the refresh executor's context is built in `cli_workspace.py` from its settings; the refresh operation takes it
  from its caller.
- API.4: the direct-analysis endpoint serves `render_text` as S17 does for saved runs, and needs an endpoint for each
  strategy's configured defaults ([C13](#c13-one-selection-schema-per-strategy-2026-11-04)); both are recorded in the
  contract's API.4 entry.

### 3.2 API.3b1 implementation record

What changed, by area:

- **Repository:**
  - `workspace/watchlists.py` gains `WatchlistName`, `WatchlistId`, `WatchlistRef` and `not_found_message`
    ([W19](#w19-watchlistref-is-a-name-or-an-id-2026-11-05)); `StoredSelectionError` carries the watchlist name, the
    1-based entry number, the ticker and the method name, and its message ends after the clause naming the entry and its
    state ([W16](#w16-the-cli-adds-the-remedy-for-an-unreadable-entry-2026-11-05));
  - `summary`, `delete`, `rename`, `add_entries` and the three removals take a `WatchlistRef`, resolved by one `_find_id`
    inside their own transaction ([W20](#w20-the-repositorys-writes-take-a-watchlistref-2026-11-05)); the name-only
    signatures are gone;
  - `rename` returns `RenamedWatchlist` and each removal `RemovedEntries` (the count removed), each holding exactly one of
    the watchlist and the error that makes an entry unreadable, read back with `_load` in the write's own transaction and
    returned, not raised, so the write commits ([W8](#w8-a-watchlist-action-writes-and-reads-back-in-one-transaction-2026-11-05)).
    `add_entries` still raises and rolls back ([W15](#w15-adding-to-a-watchlist-with-an-unreadable-entry-is-refused-2026-11-05)).
- **`application`:**
  - `parameters.py`: `ActionParameterError`, an `InvalidParameterError` carrying a message template and the action's own
    parameter names, with `named(...)` to fill in a caller's ([W17](#w17-an-actions-parameter-error-is-a-template-2026-11-05));
  - `watchlists.py`: `create_watchlist(context, name) -> Watchlist`;
    `rename_watchlist(context, ref, new_name) -> RenamedWatchlist`; `delete_watchlist(context, ref) -> DeletedWatchlist`;
    `add_watchlist_entries(context, ref, entries) -> Watchlist`;
    `remove_watchlist_entry(context, ref, entry_number)`, `remove_watchlist_tickers(context, ref, tickers)` and
    `remove_watchlist_method(context, ref, method_id)`, each `-> RemovedEntries`;
    `get_watchlist_summary(context, ref) -> WatchlistSummary`. Each checks its arguments, then opens the database with
    `open_database(context)` ([W18](#w18-arguments-are-checked-before-the-database-opens-2026-11-05)). The checks are also
    exported as `check_watchlist_name` and `check_tickers`, which the CLI's `create` calls before it creates the watchlist
    that it then seeds ([W21](#w21-create-seeds-through-two-actions-until-api3b2-2026-11-05)). An entry is addressed by
    its 1-based number; the 0-based position stays in the repository.
- **CLI:** every watchlist write command calls its action and neither opens the database nor calls the repository.
  `_watchlist_action` fills the action's parameter names in from a table per command (`NAME`, `TICKER`, `INDEX`,
  `NEW_NAME`), `_fail_with` appends the remedy to an unreadable-entry message, `delete` asks from
  `get_watchlist_summary` by name and deletes by the summary's `WatchlistId`, and `create`, `add-selection`,
  `remove-entry`, `remove-ticker` and `remove-method` gain `--json`. `_workspace_database` stays: `refresh` uses it until
  API.3c.
- **Documents:** `docs/user/USAGE.md` and `docs/user/WORKSPACE.md` list the new `--json` commands;
  `schemas/watchlist.schema.json`, `schemas/watchlist-delete.schema.json` and `schemas/openapi.json` carry the watchlist
  schema's new description, which names every command that writes it. No key or type changed.

User-visible changes:

- `--json` on `watchlist create`, `add-selection`, `remove-entry`, `remove-ticker` and `remove-method`
  ([W11](#w11-every-watchlist-writing-command-has---json-2026-11-05), [W23](#w23---json-on-the-watchlist-writing-commands-2026-11-05)).
  Help texts: "Emit the created watchlist document." and "Emit the updated watchlist document." Standard output holds the
  watchlist document; after a removal the confirmation goes to standard error; an unreadable entry after a committed
  removal writes the failure document to standard output and exits 1:

  ```text
  $ ian watchlist remove-ticker Core KO --json
  stderr:  Removed 1 entry for KO from watchlist 'Core'.
  stdout:  {"watchlist_id": "…", "display_name": "Core", …, "entries": [{"index": 1, "ticker": "MSFT", …}]}
  exit 0
  ```

- Where a command was given both a rejected argument and a database that is not ready, it now reports the argument
  (W18). Before: the database's readiness error. After: for example `NAME must not be blank.` with exit 1.
- `GET /v1/watchlists/{watchlist_id}` for a watchlist holding an unreadable entry no longer ends its `reason` with
  `Remove it with: ian watchlist remove-entry "<name>" <number>` (W16). Before:
  `Watchlist 'Core', entry 2 (MSFT, momentum): <state>. Remove it with: ian watchlist remove-entry "Core" 2`. After:
  `Watchlist 'Core', entry 2 (MSFT, momentum): <state>.` The command line's output is unchanged: it appends the remedy.
- A `remove-entry` number with no entry now reports it by the number given and the watchlist's stored name
  ([W24](#w24-a-missing-entry-is-named-by-its-number-2026-11-05)). Before: `No entry at position 4 in watchlist 'Short
  List'.` (for `remove-entry "Short List" 5`, the stored 0-based position). After: `Watchlist 'Short List' has no entry 5.`
  The same message follows an ID reference.
- No other CLI message, `parameters` value, exit code or recorded output changed: every recorded output of
  `tests/expected_output/workspace_commands/` is byte for byte what `main` writes, and the five new `--json` commands add
  seven recorded steps.

Tests edited, and why:

- `tests/test_cli_workspace.py`: two `patch(...)` targets name the module-path alias
  `investment_analysis_engine.cli_workspace.SQLiteWatchlistRepository.get`; the CLI no longer imports the repository, so
  the target names the class where it is defined. The same object is patched.
- `tests/workspace/repositories/test_watchlist_repository.py`, `tests/_runs_compare_refresh.py`,
  `tests/test_cli_refresh.py`, `tests/test_cli_momentum_statuses.py`, `tests/test_cli_failure_envelope.py`,
  `tests/api/test_endpoints.py` and `tests/application/test_watchlists.py`: each call to a repository write method wraps its
  name argument in `WatchlistName(...)` (W20); the repository tests that compared a removal's return value now compare its
  `.removed` (W8, W22).

Follow-up tests (W24 to W26): `tests/test_cli_workspace.py::test_watchlist_remove_entry_out_of_range_exits_1` now asserts the
full new message (edited from a check for `No entry at position`); `test_watchlist_actions.py` asserts the same message for
a reference by name and by ID, that an undeclared method is rejected under `method_id` before the database opens, and that
an empty `tickers` and an empty `entries` are rejected.

Tests added: `tests/application/test_watchlist_actions.py` (each action, by name and by ID, its conflicts and parameter
errors with the action's own names, the unreadable read-back after rename and each removal, the refused add, the order of
argument and database checks, and a rename between a summary and a delete); `tests/application/test_parameters.py`;
`tests/test_cli_watchlist_json.py` (`--json` on the five commands, including the unreadable and nothing-to-remove cases,
and the argument-before-database order on the command line); repository tests of ID addressing, the returned read-back
and the error's fields; `tests/workspace/test_watchlists.py` for the error's fields and the not-found message; an API test
that no failure document the API serves contains `ian `.

Accepted deviations: none from the wording of W8 to W26.

Noticed for later slices:

- API.3b2: `create` still seeds through `WatchlistFlags` (W21), and `cli_workspace.py` still reads Momentum's option
  defaults; C12 removes both. Its selection validation reuses `application/parameters.py`.
- API.3b2: `check_watchlist_name` and `check_tickers` are public in `application/watchlists.py` only because `create`
  checks its tickers before it creates and seeds; when API.3b2 removes the seeding (C12), make them private again.
- API.3c: `_workspace_database` is used only by the refresh command and goes when refresh moves into `application`.

## 4. Scope limits and acceptance criteria

- API.3a changes no CLI output, text, `--json`, help text, message or exit code, no stored shape, formula or
  classification, and no dependency, except the approved step order of 2026-11-04: with `--save-run`, no SEC identity and
  a database that needs an upgrade, Piotroski (and Graham Number, Graham Growth and FCF Growth with `--no-cache`) report
  the database's code, not `configuration_error`.
- Every direct command calls `analyze`; no command composes dependencies, builds a presentation or saves a run itself.
- No module of `application` reads a module-level settings object, and none outside the tier names a strategy.
- `cli_composition.py` and `cli_run_support.py` do not exist, and nothing forwards from them.
- A file directly inside a strategy package named for a unit belongs to that unit, in the dependency check, the layering
  test and the generator.
- A strategy added through `scripts/new_strategy.py` has a `workspace.py`, an `application.py` and an entry in the
  application tier, and passes the conformance checks.
- Each operation that reports a provider failure builds its own probe from the context's settings.
- API.3b1, API.3b2 and API.3c carry out C9 to C17 and meet the criteria of the contract's section 5 that concern them.

## 5. Background

[API.1b](API_1_SLICE_PLAN.md) moved the read operations into `application` and left production composition in the CLI,
because the actions needed it ([A11](API_1_SLICE_PLAN.md#a11-cli_compositionpy-stays-in-cli-until-api3-2026-11-01)).
The actions are larger than the reads: a direct analysis composes providers and caches, runs a strategy, presents it in
four forms and may save it, and a refresh does the same for a watchlist and reports progress. Doing them in one slice
would mix a move of existing code with new behavior, so the move and direct analysis come first (API.3a), the new
watchlist behavior and the CLI change second (API.3b1 and API.3b2) and the progress callback last (API.3c).

The CLI tests pinned the direct commands' output byte for byte, which is why API.3a can move the presentation: the
expected text of every mode was recorded from `main` before the change and the operation is compared with it.

## Appendix A: Decision records

C1 to C18 and C5a were approved by the project owner on 2026-11-04, with C2 as amended and C5a in place of C5. W1 to W13, API.3b's implementation decisions, were approved on 2026-11-05, and W14 to W26 on 2026-11-05.

### C1 API.3 is three slices (2026-11-04)

API.3 is three slices:

| Slice | Decisions | Branch |
| :--- | :--- | :--- |
| API.3a | C2 to C8 and this plan | `feat/api-execution-composition` |
| API.3b1 | C9, W8 to W11, W15 to W26: the watchlist actions, with the CLI switched to them | `feat/api-watchlist-actions` |
| API.3b2 | C10 to C14, W1, W3 to W7, W12, W13: selection from model fields, the selection schemas and their conformance check, Site 19 | `feat/api-selections` |
| API.3c | C15 to C17: refresh with progress | `feat/api-refresh-progress` |

These branches replace the contract's single `feat/api-application-actions`. Each slice switches the CLI to its
operations, and no CLI output changes except as C12 decides, in API.3b.

### C2 One rule: a file named for a unit belongs to that unit, as amended (2026-11-04)

A file directly inside a strategy package whose name is a unit belongs to that unit.

- Every strategy's `execution.py` is renamed `workspace.py` and stays in the `workspace` unit. The `execute_<name>`
  functions keep their names, and each module docstring says what the file does, since its name no longer does.
- Each strategy package gains `application.py`, in the `application` unit. It holds that strategy's provider and
  resolver building, its settings loader, its run function and its text renderer ([C5a](#c5a-direct-analysis-is-an-operation-that-returns-an-outcome-2026-11-04)).
- The Architecture §13 rule becomes: a file directly inside a package under `investment_analysis_engine/strategies/`
  whose name (without `.py`) is a unit's name (`cli`, `evaluation`, `workspace`, `application`) belongs to that unit.
  `scripts/package_graph.py`, `scripts/check_package_dependencies.py` and `tests/test_strategy_import_layering.py` match
  the file name to the unit name directly, with no mapping table.
- The template `execution.py.tmpl` is renamed `workspace.py.tmpl`, `application.py.tmpl` is added, and
  `scripts/new_strategy.py`, `scripts/strategy_sites.toml`, the conformance and status scripts, the generated strategy
  docs and `docs/TOOL_DEVELOPMENT.md` follow.
- Strategy-specific helpers in `cli_composition.py` move into the strategy they serve (`momentum_settings` to Momentum,
  `graham_growth_settings` to Graham Growth, the Graham resolver builder to the Graham strategies' `application.py`
  files, sharing one function between them only where the code is truly the same). The shared SEC adapter and provider
  builders go to `investment_analysis_engine/application/providers.py`. Nothing in `application`'s own modules names a
  strategy.

### C3 The application tier (2026-11-04)

An application tier in `application` pairs each strategy's `application.py` functions with its core bundle, like the CLI
tier: built with a `pair_` function so a mismatched pairing fails `mypy --strict`, a closed static tuple, and a strategy
without an entry fails with `UndeclaredStrategyError`. The refresh executor moves from the CLI tier to this tier; the CLI
tier keeps `build` and `command`.

### C4 Composition takes the application context (2026-11-04)

Composition reads no module-level settings object. Every function in `application/providers.py` and each strategy's
`application.py` takes the `ApplicationContext` (or the settings it holds). Strategy settings files load from
`context.settings.config_dir`; their once-per-process cache is keyed by that folder. CLI callers build an
`ApplicationContext` from their settings as `runs list` does. Tests that patch the global `settings` object to steer
composition (the reason `cli_composition.py`'s docstring gave for its separate module) are rewritten to pass a context;
these edits are approved, and each is listed in the implementation record.

### C5 Direct analysis returns a document and a saved run's ID (2026-11-04)

Superseded by [C5a](#c5a-direct-analysis-is-an-operation-that-returns-an-outcome-2026-11-04) before it was implemented.
C5 had the operation return the strategy's document. The text modes are rendered from the run's execution, not from the
document, so carrying the execution to the CLI would have left strategy-specific rendering in the CLI.

### C5a Direct analysis is an operation that returns an outcome (2026-11-04)

Direct analysis is an operation: `analyze(context, ticker, selection, *, save: bool, provider_check: bool) ->
AnalysisOutcome`, for one ticker and one selection. `AnalysisOutcome` holds:

- `document`: the strategy's typed document, exactly as `--json` writes it today, provider-check element included;
- `analysis_run_id`: the saved run's ID, or `None` when not saved;
- `outcome`: the run's outcome, from which the CLI sets its exit code as `render_execution` does today;
- `render_text(mode)`: the run rendered in a text mode (concise, details, diagnostics), built in the strategy's
  `application.py` from that strategy's own presentation and presenter, so it is byte-for-byte what the direct command
  prints today in that mode.

`AnalysisOutcome` carries no raw execution and no strategy-specific type. Each strategy's direct command calls this
operation and writes `render_text(mode)` or the document, adds the provider-check lines after a failure and exits with
the code from `outcome`, all through code shared by every strategy; so direct analysis has one execution path and the
CLI holds no strategy-specific rendering. The saving logic of `cli_run_support.py` that the operation needs moves into
`application`; what stays in `cli_run_support.py` is only CLI concerns, and if nothing remains the file is deleted.

### C6 The as-of echo is the existing document fields (2026-11-04)

The as-of echo is the strategy documents' existing `requested_as_of` and `effective_as_of`; no field is added. The
selection's `as_of` reaches the operation unchanged.

### C7 The provider check moves into application (2026-11-04)

The provider check after a failure moves into `application`: the operation runs it when `provider_check` is true, and its
result reaches the document and `render_text` as it does today. `cli_provider_check.py` keeps only the
`--no-provider-check` / `IAN_PROVIDER_CHECK` choice and the CLI's rendering of the provider-check lines; `ian health` and
the refresh command use the moved check.

### C8 cli_composition.py is deleted (2026-11-04)

`cli_composition.py` is deleted, not left as a forwarding module. Every caller, including
`scripts/check_installed_package.py`, imports from the new homes.

### C9 Watchlist actions take one WatchlistRef (2026-11-04)

Watchlist actions take one `WatchlistRef` (a name or an ID), resolved inside the action's own transaction. The
repository gains ID addressing for its writes. The S36 read operations stay.

### C10 Selection is built from model fields (2026-11-04)

`build_selection(context, method_id, fields)` applies the strategy's configured defaults to omitted fields, then the
selection model validates. The CLI's builders call it too.

### C11 Selection validation names model fields (2026-11-04)

Selection validation names model fields. The CLI maps each field to its option through a table each strategy declares.
CLI messages stay as they are, and API messages name fields.

### C12 Site 19 is settled by one add-selection subcommand per strategy (2026-11-04)

`WatchlistFlags` is replaced by one `ian watchlist add-selection <alias> NAME TICKERS…` subcommand per strategy, added by
iterating the CLI tier, each strategy's options declared once in its `cli.py` and shared with its direct command.

- `ian watchlist create NAME` only creates; it seeds nothing.
- There is no `--create` option on `add-selection`.
- A missing required option is a parser error (exit 2) as on the direct command.
- The other watchlist commands are unchanged.

Before and after, as typed:

```text
before:  ian watchlist create "Core Holdings" --analysis momentum AAPL MSFT KO
after:   ian watchlist create "Core Holdings"
         ian watchlist add-selection momentum "Core Holdings" AAPL MSFT KO

before:  ian watchlist add-selection "Core Holdings" AAPL --analysis graham-number --bvps 12.5
after:   ian watchlist add-selection graham-number "Core Holdings" AAPL --bvps 12.5

before:  ian watchlist create "Value Watch" --analysis graham-growth --expected-growth 6.0 --aaa-yield 4.4 AAPL
after:   ian watchlist create "Value Watch"
         ian watchlist add-selection graham-growth "Value Watch" AAPL --expected-growth 6.0 --aaa-yield 4.4
```

On API.3b's merge, H.10 in `SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md` and B.3 in `STEP_3_5_3_SLICE_PLAN.md` each gain a line
saying Site 19 was settled by API.3b, the strategy-site table loses row 19, and the `USAGE.md` text about the exit-code
difference for a missing required option is removed.

### C13 One selection schema per strategy (2026-11-04)

There is one schema per strategy, `schemas/selections/<alias>.schema.json`, generated from the declared strategies and
compared in the gate. Settings-backed fields carry no `default`.

### C14 Form-supported field types (2026-11-04)

The field types a form supports are bool, int, float, str, a closed set of values (`Literal` or `StrEnum`), date or
datetime, and an optional of any of these. Each field needs a description. `analysis_id`, `method_id` and
`config_schema_version` are excluded from forms and checked separately.

### C15 Progress events (2026-11-04)

A progress event is typed (job started with ticker and selection; job finished with its `RefreshJobResult`; totals
admitted, finished and remaining) and is sent only from the refresh's coordinating thread.

### C16 A failing progress callback (2026-11-04)

A progress callback's first exception is logged with its traceback, later events are dropped, and the refresh completes
normally.

### C17 ian refresh shows no progress (2026-11-04)

`ian refresh` shows no progress and its output does not change.

### C18 The plan and the contract (2026-11-04)

This plan is written in API.3a, structured like [API.2's](API_2_SLICE_PLAN.md). In
[the contract](API_CONTRACT_AND_SLICE_PLAN.md):

- the sequence table has API.2b Complete (2026-11-04) and API.3 as rows API.3a, API.3b and API.3c, kept in step with
  every table `scripts/check_sequence_tables.py` compares, API.2's §2 among them;
- the sequence rule of this plan's "At a glance" applies from API.3a: each slice's pull request marks its own row
  Complete, dated the day the pull request is opened (approved 2026-11-04);
- the API.3 entry links this plan and loses the "no slice plan yet" warning, its Site 19 line points to C12, its branch
  line names the three branches, and its `as_of` text follows C6;
- the API.4 entry records two requirements: a client needs an endpoint giving each strategy's current configured
  selection defaults, because the selection schemas carry none (C13); and the direct-analysis endpoint can serve a run's
  text in a mode through `render_text`, as S17 does for saved runs (C5a).

### W1 A nested selection model is a form type (2026-11-05)

Amends C14. A model nested one level inside a selection, whose own fields are each of a form-supported type, is a form-supported type; a form shows its fields as a group. FCF Growth's `policy` stays nested, and no stored shape changes for it.

### W2 FCF Growth's include_fcf_yield option is removed (2026-11-05)

No command, selection builder or stored selection set it to false, and the FCF Growth tool, which offered it to a model, defaulted to true, so FCF yield is always computed. Removed before API.3b, in its own pull request, with the `not_requested` metric reason code that only it produced (issue #227).

### W3 The field-to-option table carries converters (2026-11-05)

Each row of a strategy's table (C11) names a selection field, its CLI option and, when the two differ in value, a converter from the option's typed value to the field's value, for example `--no-cache` to `use_cache` and `--growth-years` to `policy.historical_horizon`. Normalization that does not belong to the command line, such as upper-casing the currency, moves into the selection model, so the API applies it too.

### W4 The as-of date rule is shared (2026-11-05)

`build_selection` accepts `as_of` as a date or a timezone-aware timestamp. A date means the end of that day in UTC, the rule the CLI's `--as-of` applies today; the rule lives in `application`, and the CLI's parser calls it.

### W5 build_selection is the only validator (2026-11-05)

The CLI builders' own checks are removed. Each selection rule's message is a template naming fields; the API fills it with field names and the CLI with option names through the strategy's table (W3), so every CLI message stays byte-identical. A current CLI message that a template cannot reproduce is reported to the project owner, not reworded.

### W6 Each strategy declares its selection options once (2026-11-05)

Each strategy's `cli.py` declares its selection options once, as module-level `Annotated` aliases that its direct command and its `add-selection` command both use. `CliComposition` loses `build` and gains the `add_selection` command and the field-to-option table, and the CLI tier registers `ian watchlist add-selection <alias>` for each strategy. `cli_watchlist_flags.py` and the Momentum defaults read in `cli_workspace.py` are removed.

### W7 A conformance check replaces site 19 (2026-11-05)

No site replaces row 19. A conformance check requires that a strategy's `add-selection` options are exactly its direct command's selection options (all but `--details`, `--diagnostics`, `--json`, `--save-run`, `--no-provider-check` and `--ticker`), and that its table covers every selection field except `analysis_id`, `method_id` and `config_schema_version`. The generator's templates emit both, and a generated strategy passes.

### W8 A watchlist action writes and reads back in one transaction (2026-11-05)

Each action does its write and its read-back in one transaction (C9) and returns a result holding either the watchlist or the error that makes an entry unreadable, as `DeletedWatchlist` does. The CLI prints what it prints today.

### W9 Delete is confirmed and done by ID (2026-11-05)

`ian watchlist delete` asks its question from the watchlist's summary and then deletes by the summary's ID, so a rename between the two cannot delete a different watchlist. Its output does not change.

### W10 Argument checks are in the actions (2026-11-05)

The actions check their own arguments (a blank name or new name, a blank or missing ticker, an entry number below 1) and raise `InvalidParameterError` naming their parameters; the CLI maps the names to its arguments and its messages do not change. An entry is addressed by its 1-based number, as `watchlist show` displays it, in the CLI and the API; the repository's 0-based position stays inside.

### W11 Every watchlist writing command has --json (2026-11-05)

`watchlist create`, each `watchlist add-selection <alias>`, `remove-entry`, `remove-ticker` and `remove-method` gain `--json`, which writes the watchlist document. After a removal the confirmation goes to standard error, as `watchlist rename --json` does. This is the one CLI change besides C12.

### W12 The selection schemas (2026-11-05)

`scripts/generate_schemas.py` also writes `schemas/selections/<alias>.schema.json` and its existing drift check covers them. Each describes the fields `build_selection` accepts: not `analysis_id`, `method_id` or `config_schema_version` (checked separately, C14); a settings-backed field has no `default` and is not required (C13). `schemas/openapi.json` does not change until API.4 refers to them.

### W13 API.3b's record and closures (2026-11-05)

API.3b's detail is a section "3.2 API.3b implementation record" in this plan, which replaces the "no slice plan yet" line. Its pull request marks its row Complete and API.3c Next, and makes C12's closures: the lines in H.10 of `SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md` and B.3 of `STEP_3_5_3_SLICE_PLAN.md`, the removal of the exit-code paragraph in `docs/user/USAGE.md`, and row 19 of the strategy-site table.

### W14 API.3b is two slices (2026-11-05)

API.3b is split into API.3b1 (C9, W8 to W11 and W15 to W26: the watchlist actions, with the CLI switched to them) on `feat/api-watchlist-actions`, and API.3b2 (C10 to C14, W1, W3 to W7, W12 and W13: selection from model fields, the per-strategy `add-selection` subcommands, the selection schemas and Site 19) on `feat/api-selections`. Each has its own implementation record, 3.2 and 3.3; API.3c's is 3.4. Amends C1's branch list.

### W15 Adding to a watchlist with an unreadable entry is refused (2026-11-05)

Adding entries writes nothing when the watchlist holds an entry this version cannot read, as before. W8's watchlist-or-unreadable result applies to rename, the removals and delete, which commit whatever the other entries hold.

### W16 The CLI adds the remedy for an unreadable entry (2026-11-05)

`StoredSelectionError` carries the watchlist name, the entry number, the ticker and the method, and its message names the entry and its state with no remedy. The CLI appends `Remove it with: ian watchlist remove-entry "<name>" <number>`, so its output does not change; the API serves no `ian` command.

### W17 An action's parameter error is a template (2026-11-05)

An action's parameter error carries a message template and the action's own parameter names, and each caller fills in its names: the CLI from a table per command, so its messages and `parameters` do not change, and the API with the action's names. It is in `application/parameters.py`, and API.3b2's selection validation uses it too.

### W18 Arguments are checked before the database opens (2026-11-05)

Every action checks its arguments before it opens the database. A command given both a rejected argument and a database that is not ready now reports the argument: an approved output change.

### W19 WatchlistRef is a name or an ID (2026-11-05)

`type WatchlistRef = WatchlistName | WatchlistId`, two frozen one-field types. Not found by name is "No watchlist named 'X' exists." and by ID "No watchlist with ID <id> exists."

### W20 The repository's writes take a WatchlistRef (2026-11-05)

`summary`, `delete`, `rename`, `add_entries` and the three removals take a `WatchlistRef`, resolved in their own transaction, in place of a name. The reads `get` and `get_by_id` stay (S36).

### W21 create seeds through two actions until API.3b2 (2026-11-05)

In API.3b1 `ian watchlist create` with `--analysis` calls the create action and then the add action; the create action takes no entries. API.3b2 removes the seeding (C12).

### W22 The watchlist actions (2026-11-05)

`create_watchlist`, `rename_watchlist`, `delete_watchlist`, `add_watchlist_entries`, `remove_watchlist_entry`, `remove_watchlist_tickers`, `remove_watchlist_method` and `get_watchlist_summary`, in `application/watchlists.py`. Rename returns `RenamedWatchlist` and each removal `RemovedEntries` (the count), each holding exactly one of the watchlist and the error that makes an entry unreadable. An entry is addressed by its 1-based number.

### W23 --json on the watchlist writing commands (2026-11-05)

`create`, `add-selection`, `remove-entry`, `remove-ticker` and `remove-method` gain `--json`, with the help texts "Emit the created watchlist document." (`create`) and "Emit the updated watchlist document." (the others). After a removal the confirmation goes to standard error. An unreadable entry after a committed change writes the failure document and exits 1, as `rename --json` does.

### W24 A missing entry is named by its number (2026-11-05)

"Watchlist 'Core' has no entry 3." names the entry by the 1-based number the caller gave and the watchlist by its stored name, whether it was addressed by name or by ID. It replaces a message that printed the stored 0-based position: an approved CLI message change.

### W25 Removing by method needs a declared method (2026-11-05)

`remove_watchlist_method` rejects a method identifier this version does not declare, under its parameter `method_id`, instead of removing nothing. An entry whose method is no longer declared is removed with `remove-entry`.

### W26 An empty ticker or entry list is rejected (2026-11-05)

`remove_watchlist_tickers` rejects an empty `tickers` and `add_watchlist_entries` an empty `entries`, instead of doing nothing. The CLI cannot send either.
