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
| API.3b2 | [Selections and Site 19](#api3b2--selections-and-site-19) | Complete | 2026-11-06 |
| API.3c | [Refresh with progress](#api3c--refresh-with-progress) | Complete | 2026-11-06 |

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
  - the scripts, templates and site data that name the moved files, Architecture §13, `docs/project/STRATEGY_DEVELOPMENT.md`, this
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
  - the implementation decisions W1, W3 to W7, W12, W13 and W27 to W46 ([Appendix A](#appendix-a-decision-records));
    W2 was done before API.3b, in its own pull request.
- **Scope:** `build_selection`; the selection schemas and their generator and conformance check; the CLI change of C12
  with the documents it touches; the closure of Site 19 in the documents named in C12.
- **Branch:** `feat/api-selections`.
- **Detail:** [Implementation record](#33-api3b2-implementation-record).

### API.3c — Refresh with progress

- **Problem:** a refresh reports nothing until it ends, and the CLI owns its coordination.
- **Decision:** refresh moves into `application` with a typed progress event sent only from the refresh's coordinating
  thread ([C15](#c15-progress-events-2026-11-04)); a failing callback never fails the refresh
  ([C16](#c16-a-failing-progress-callback-2026-11-04)); `ian refresh` shows no progress and its output does not change
  ([C17](#c17-ian-refresh-shows-no-progress-2026-11-04)).
- **Scope:** the refresh operation, which builds its own probe as `analyze` does, the progress event types, the cancellation event the CLI already uses, and the CLI
  switched to the operation.
- **Branch:** `feat/api-refresh-progress`.
- **Detail:** [Implementation record](#34-api3c-implementation-record). Decisions C15 to C17 and W47 to W58 are in [Appendix A](#appendix-a-decision-records).

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
- **Docs:** Architecture §13 (the rule and the `application` row), `docs/project/STRATEGY_DEVELOPMENT.md` (including the regenerated
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

### 3.3 API.3b2 implementation record

What changed, by area:

- **`application`:**
  - `selections.py`: `build_selection(context, method_id, fields)` and `as_of_boundary` ([W27](#w27-build_selections-place-and-input-2026-11-05), [W4](#w4-the-as-of-date-rule-is-shared-2026-11-05)). It rejects an undeclared method under `method_id`, rejects the three fixed fields as unknown, converts `as_of`, fills the descriptor's `selection_settings_fields` from the strategy's settings, lets the selection model validate and reports the first error;
  - `parameters.py`: `ActionParameterError` substitutes only the placeholders it declares, carries a `rule` and named `arguments` ([W31](#w31-rule-templates-2026-11-05), [W42](#w42-errors-keep-what-a-translation-needs-2026-11-05)); every watchlist action error carries a `watchlist.<rule>` identifier;
  - `watchlists.py`: `check_watchlist_name` and `check_tickers` are private again ([W40](#w40-the-argument-checks-are-private-again-2026-11-05)); `alias_for_method_id` moved here from the CLI.
- **Core and strategies:**
  - `analysis/selection_base.py`: `SelectionRuleError`; `StrategyDescriptor.selection_settings_fields` (all five descriptors; Momentum names its three); `BehaviorView.selection_type`;
  - every selection model has a description on every field, including FCF Growth's `policy` ([W33](#w33-field-descriptions-2026-11-05)); Momentum's positivity and window-order rules, the non-finite override rule and the currency rule raise templated `SelectionRuleError`s; `GrahamGrowthSelection.eps_basis` and `GrahamGrowthConfig.eps_basis` default to `"three_year_average"` ([W34](#w34-graham-growths-eps_basis-2026-11-05)).
- **CLI:**
  - `cli_support.py`: `SelectionOption`, `selection_from_options`, `cache_enabled`, `parse_as_of_option` (syntax only, through the application's `parse_as_of_text`), the shared options as `Annotated` aliases ([W36](#w36-one-option-style-2026-11-05)), and the failure reporting and watchlist rendering the watchlist commands share, which `cli_workspace.py` held (`workspace_failures`, `fail`, `fail_with`, `watchlist_action`, `watchlist_text`, `watchlist_json`, `document_json`, `add_selection_entries`). `config_usage_errors` is deleted;
  - each strategy's `cli.py` declares its selection options once as `Annotated` aliases, a `SELECTION_OPTIONS` table, its direct command and `add_selection`; Momentum's three window options default to omitted ([W29](#w29-momentums-window-options-default-to-the-settings-2026-11-05));
  - `cli_strategy_wiring.py`: `CliComposition` and `CliStrategy` hold `command`, `add_selection` and `selection_options` and lose `build`; `add_selection_commands` registers each strategy's subcommand with a summary generated from its label ([W38](#w38-help-for-the-new-and-changed-commands-2026-11-05)); the builder lookups are deleted. `cli_watchlist_flags.py` is deleted;
  - `cli_workspace.py`: `create` takes a name and `--json` only; `add-selection` is a group holding the subcommands.
- **Scripts and data:** `scripts/generate_schemas.py` writes `schemas/selections/<alias>.schema.json` ([W35](#w35-how-the-selection-schemas-are-produced-2026-11-05)); `scripts/strategy_conformance.py` loses the Site 19 check and gains `selection_options_gaps` (T27: the two commands' options agree, the table covers every field, form types, descriptions, `selection_settings_fields`, duplicated defaults); `scripts/strategy_sites.toml` loses row 19 and `cli` defines `SELECTION_OPTIONS`, `add_selection` and `command`; the generator emits the new descriptor field, tier entry and `cli.py`/`selection.py` templates.
- **Documents:** the Site 19 closures in SWC.1 H.10 and Step 3.5.3 B.3 and the removal of row 19; the exit-code sentence in `docs/user/USAGE.md`; `docs/user/WORKSPACE.md`, the five strategy guides and `docs/project/STRATEGY_DEVELOPMENT.md` for the new commands; the API.4 entry of the contract gains two requirements.

User-visible changes:

- `ian watchlist create NAME [--json]` creates an empty watchlist. Before: `create NAME [TICKER...] [--analysis METHOD] [strategy options]`. After: `watchlist create "Core Holdings"` then `watchlist add-selection momentum "Core Holdings" AAPL MSFT KO`. Passing a ticker or a strategy option to `create` is a parser error (exit 2).
- `ian watchlist add-selection <alias> NAME TICKERS... [options]`, one subcommand per strategy, replaces `add-selection NAME TICKERS... --analysis METHOD [options]`. Its options are its direct command's selection options with their help, plus `--json`. Before: `add-selection "Core" AAPL --analysis graham-number --bvps 12.5`. After: `add-selection graham-number "Core" AAPL --bvps 12.5`.
- A missing required option is a parser error (exit 2), as on the direct command. Before: `--expected-growth is required when --analysis is graham-growth.` with exit 1. After: usage text naming the option, exit 2.
- A missing or unknown method is a parser error. `add-selection` alone: "Missing command." exit 2; `add-selection foo ...`: "No such command 'foo'." exit 2. Before: `--analysis must be one of: ...`, exit 1 ([W39](#w39-a-missing-or-unknown-method-is-a-parser-error-2026-11-05)).
- `momentum --help` and `watchlist add-selection momentum --help` show the window defaults as `[default: (from settings: 50)]`, `(from settings: 200)` and `(from settings: 14)`. Before: `[default: 50]`, `[default: 200]`, `[default: 14]`.
- `ian watchlist --help` lists `add-selection` after the other commands, because it is now a command group (Typer lists groups after commands). Before: `create`, `add-selection`, `remove-entry`, ... After: `create`, `remove-entry`, `remove-ticker`, `remove-method`, `delete`, `rename`, `list`, `show`, `add-selection`; its summary is "Add entries for one method to an existing watchlist, one per ticker."
- With several bad options at once, which error is reported may change ([W32](#w32-first-error-only-2026-11-05)): a value a converter rejects (`--as-of` syntax, `--growth-years`, `--forward-policy`, `--classification-basis`) is reported before a rule of the selection model. Every single-failure message is unchanged.
- Published schemas: `schemas/watchlist.schema.json`, `schemas/watchlist-delete.schema.json` and `schemas/openapi.json` carry the field descriptions of [W33](#w33-field-descriptions-2026-11-05) and describe `eps_basis` as the plain enumeration `three_year_average` | `fiscal_year` with default `three_year_average`. Before: `"anyOf": [{"enum": ["three_year_average", "fiscal_year"], "type": "string"}, {"type": "null"}]` with default `null`. No key was added or removed, and no stored or served document ever held a null `eps_basis`, because the selection resolved it on construction. `schemas/selections/<alias>.schema.json` are new.
- Help for `watchlist create`, the `add-selection` group and each subcommand is new (snapshots below).
- No stored shape or `config_schema_version` changed; no dependency changed.

Tests edited, and why:

- Moved or removed names ([W6](#w6-each-strategy-declares-its-selection-options-once-2026-11-05), [W31](#w31-rule-templates-2026-11-05)): `tests/workspace_documents/test_workspace_documents.py` (`watchlist_json` moved to `cli_support.py`), `tests/test_cli_piotroski.py` (the selection builder is the option table), `tests/test_failure_messages.py` (a selection is built with `build_selection`), `tests/test_cli_support.py` (`parse_as_of` returns a date or a datetime and leaves the end-of-day and offset rules to `build_selection`; the `config_usage_errors` tests became tests of the option table's error spelling), `tests/test_cli_workspace.py::test_the_alias_choices_are_formatted_as_a_comma_list_with_a_final_or` (the alias vocabulary is `BY_ALIAS`).
- `tests/test_cli_strategy_wiring.py` is rewritten for the new tier (option tables build each strategy's selection, fail-closed lookups, the add-selection group, the Momentum defaults); the Site 19 conformance test in `tests/test_strategy_wiring_conformance.py` is deleted, its probes name `cli_entries`, and the descriptor and CLI-tier member sets and the `--json` command list follow the new fields and per-strategy subcommands.
- The `create --analysis` setups are `create` followed by `add-selection <alias>` ([W41](#w41-re-recorded-outputs-and-the-specimen-2026-11-05)): `tests/test_command_validation_failures.py` (the rows that only existed for `create --analysis`, the missing-required and unknown-method rows, and the Graham Number `--eps-basis` test move to the parser rejections; three first-error-order rows follow [W32](#w32-first-error-only-2026-11-05)), `tests/test_cli_workspace.py` (the seeding tests became `add-selection` tests; the `create` and `add-selection` entries of the `--analysis` help and unknown-alias tests are removed), `tests/test_cli_watchlist_json.py`, `tests/test_cli_failure_envelope.py`, `tests/test_workspace_integration.py`, `tests/test_documented_conventions.py` and `tests/_workspace_command_output.py`.
- Output and help: `tests/test_cli.py` (Momentum help defaults), `tests/_cli_help_output.py` and `tests/test_cli_help_output.py` (new targets).
- Selection rules ([W31](#w31-rule-templates-2026-11-05)): `tests/workspace/test_requests.py` (a non-positive window is rejected by the templated rule, whose error names the field in its context and not in the location; the order rule's message is the template's).
- `GrahamGrowthConfig` ([W34](#w34-graham-growths-eps_basis-2026-11-05)): `tests/analysis/graham_value/test_analyzer_config.py::test_growth_basis_default` became a test that the basis is kept and that the default is the three-year average and never `None`. `tests/workspace/test_graham_growth_execution.py` needed no edit: it builds the config without a basis and gets the same default.
- Layering and generator: `tests/test_strategy_import_layering.py` lists `application/selections.py` as a composition-root importer, because it looks the strategy up by method identifier as `application/watchlists.py` does; `cli_support.py` does not import the root (`alias_for_method_id` lives in `application/watchlists.py`). `tests/test_specimen_strategy.py` counts one more crossing in `closed_types.py` (`selection_member_type`, for `BehaviorView.selection_type`); `tests/scripts/test_new_strategy.py` follows the template (`Annotated` aliases, `SELECTION_OPTIONS`, `add_selection`); `tests/scripts/test_strategy_sites.py` loses `watchlist-options`; `tests/scripts/test_generate_schemas.py` covers the selection schemas; `tests/scripts/generator_fills/guide.md.fill` follows the guide text.
- `tests/application/test_parameters.py` passes a `rule` to each error.
- The help-snapshot site also requires `watchlist-add-selection-<alias>.txt` (a strategy added later needs that snapshot): `tests/test_strategy_wiring_conformance.py::test_the_help_snapshot_site_requires_the_command_snapshot_and_names_the_file` expects both gaps, and the generator's end-to-end test (`tests/scripts/test_new_strategy_end_to_end.py`) takes a reviewed fill `generator_fills/expected/help.add-selection.txt`. `tests/test_cli_strategy_wiring.py` skips a strategy it has no option values for, since the end-to-end copy adds one.

Re-recorded files: `tests/expected_output/cli_help/momentum.txt` (W29: the window defaults); new help snapshots `watchlist-create.txt` and `watchlist-add-selection-<alias>.txt` for each strategy; five new workspace-command steps, `watchlist-create-seeded-setup.txt`, `watchlist-create-single-entry-setup.txt`, `watchlist-create-failing-setup.txt`, `watchlist-create-as-of-setup.txt` and `watchlist-create-seeded-json-setup.txt`. Every existing file of `tests/expected_output/workspace_commands/` is byte for byte what it was, and every other help snapshot is unchanged. `schemas/watchlist.schema.json`, `schemas/watchlist-delete.schema.json` and `schemas/openapi.json` are regenerated as above.

Tests added: `tests/application/test_selections.py` (declared method, fixed and unknown fields, the as-of rule and its message, the settings fill and given values, every Momentum rule with its identifier and values, missing and built-in errors with their type, nested names, first error only); `tests/application/test_parameters.py` (rule and values, a dotted nested name as a template placeholder); `tests/test_selection_conformance.py` (T27, production and specimen, and each way it can fail); selection-schema tests in `tests/scripts/test_generate_schemas.py` (the properties are exactly what `build_selection` accepts, no default or requirement for a settings-filled field); the help snapshot checks.

Review fixes (2026-11-06, [W43](#w43-the-as-of-syntax-parser-is-in-the-application-layer-2026-11-06) to [W46](#w46-the-add-selection-groups-help-is-tested-without-a-snapshot-2026-11-06)): no output, help, schema or stored shape changed.

- **R1 (W43).** `application/selections.py` gains `parse_as_of_text`; `cli_support.parse_as_of` becomes `parse_as_of_option`, which calls it and names the error `--as-of`; the five strategies' option tables, the generator's `cli.py` template and the specimen use it. Tests edited: `tests/test_cli_support.py` (the parser tests now call `parse_as_of_option` and assert the CLI messages and `parameters` unchanged, one case per message). Tests added: `tests/application/test_selections.py` (the rules of `parse_as_of_text` and its two rule identifiers).
- **R2 (W44).** `_substitute` in `application/parameters.py` is one `re.sub` pass. Tests added in `tests/application/test_parameters.py`: an argument value that contains a declared placeholder's text appears unchanged, and an undeclared placeholder stays as written.
- **R3 (W45).** `BehaviorView.selection_type` is `type[FrozenSelection]`; the specimen's behavior returns `SpecimenSelection` and `selection_member_type` is deleted from `tests/specimen/closed_types.py`; `build_selection` narrows with `isinstance`. Test edited: `tests/test_specimen_strategy.py` expects five `cast(` again (reverting the edit listed above).
- **R4 (W46).** Test added: `tests/test_cli_strategy_wiring.py::test_the_add_selection_help_lists_exactly_the_declared_strategies_with_their_summaries`.
- **R5.** API.3b2 is Complete on 2026-11-06 in this plan's sequence table and the contract's.

Accepted deviations: the first error follows the order the options are read, then the field order ([W32](#w32-first-error-only-2026-11-05)); the V3 test of the original prompt (an invalid Momentum file no longer stops a command that does not use Momentum) is not added, because the startup check stops every command by design ([W29](#w29-momentums-window-options-default-to-the-settings-2026-11-05)).

Noticed for later slices:

- API.4: serve a form client each strategy's current configured defaults (C13), every field's error at once and each error's rule identifier and values; the contract's API.4 entry records them.
- API.4: `build_selection` accepts `as_of` as a date or a datetime only; a client that sends text parses it first, with the same end-of-day rule through `as_of_boundary`.
- A strategy's `ian watchlist add-selection` subcommand takes its options from the same aliases as its direct command, so a new option is declared once.

### 3.4 API.3c implementation record

What changed, by area:

- **`workspace/refresh.py` (the coordinator):**
  - `refresh_watchlist` is renamed `coordinate_refresh` and takes a `WatchlistRef` ([W47](#w47-the-refresh-operation-2026-11-06), [W48](#w48-the-coordinator-is-renamed-coordinate_refresh-2026-11-06)). `WatchlistLookup` has `get(name)` and `get_by_id(id)`, the repository's existing reads, and the coordinator chooses by the reference, so no adapter and no stored shape is added. A missing watchlist raises `WatchlistNotFoundError` with `not_found_message(ref)`;
  - one admission path serves every worker count: the sequential branch, `_SEQUENTIAL_POLICY` and the default policy are deleted, and `policy` is a required argument ([W49](#w49-one-admission-path-2026-11-06)). An admitted job always runs and is settled; the cancellation of a submitted but unstarted future is deleted ([W50](#w50-an-admitted-job-always-runs-2026-11-06));
  - `RefreshTotals`, `RefreshJobStarted`, `RefreshJobFinished` and `RefreshProgress`, sent from the coordinating thread by a private reporter that counts and guards the callback ([W51](#w51-the-progress-event-types-2026-11-06), [W52](#w52-emission-and-the-failing-callback-guard-2026-11-06));
  - `DEFAULT_WORKERS` is declared beside `MIN_WORKERS` and `MAX_WORKERS` and used by `RefreshPolicy` ([W54](#w54-the-worker-count-check-2026-11-06)).
- **`application`:**
  - `refresh.py` is new: `refresh_watchlist(context, ref, *, workers, save, provider_check, cancellation, on_progress) -> RefreshOutcome`, with `RefreshOutcome` (`document`, `failed`, `render_text()`) and `build_refresh_document`. `_refresh_executor`, `_describe_job_failure`, `_refresh_has_failure` and the text builder moved here from `cli_workspace.py` ([W53](#w53-what-moves-into-applicationrefreshpy-and-the-outcome-2026-11-06)). The worker-count check runs before the database opens and raises `ActionParameterError` (rule `refresh.workers_range`);
  - `failures.py` gains `describe_failure`, `FailureDescription`, `provider_failure_message` and the message tables they use, moved unchanged from `cli_support.py` ([W58](#w58-the-failure-description-rule-moves-to-applicationfailurespy-2026-11-06)). They keep their text and behavior; the logger is now `investment_analysis_engine.application.failures`, which carries a null handler as the CLI's did.
- **CLI:** `cli_workspace.py` calls the operation inside `watchlist_action` and prints `document` with `--json` or `render_text()` otherwise; it exits 130 from its own cancellation event and 1 from `failed`. `_workspace_database`, `_refresh_executor`, `_describe_job_failure`, `_refresh_has_failure`, `_refresh_text`, `_refresh_result_document` and `_refresh_json` are deleted, and the command's `--workers` default is `DEFAULT_WORKERS`. `cli_support.py` imports `describe_failure` from `application/failures.py`; nothing forwards from it.
- **Documents:** `ARCHITECTURE.md` (the composition roots, the operations in `application` and the package table); this plan; the contract's API.4 entry ([W56](#w56-serving-refresh-progress-over-http-2026-11-06)).

User-visible changes:

- None to `ian refresh` or any other command: text, `--json`, help, messages and exit codes are unchanged, and every file under `tests/expected_output/` is byte for byte what it was ([C17](#c17-ian-refresh-shows-no-progress-2026-11-04)).
- A refresh addressed by watchlist ID reports an empty watchlist as `Watchlist '<display name>' has no entries; there is nothing to refresh.`, using the display name where a name-addressed refresh uses the name as typed. No current caller addresses a refresh by ID.
- The log line `Failure reported to the user as: ...` is now written by the logger `investment_analysis_engine.application.failures` instead of `investment_analysis_engine.cli_support`; its text and traceback are the same.
- No stored shape, `config_schema_version`, schema file, formula, classification or dependency changed.

Tests edited, and why:

- Renamed coordinator ([W48](#w48-the-coordinator-is-renamed-coordinate_refresh-2026-11-06)), a `WatchlistName` reference and a required policy ([W49](#w49-one-admission-path-2026-11-06)): `tests/workspace/test_refresh.py` (its test names follow; its fake lookup gains `get_by_id`), `test_refresh_provider_failure.py`, `test_failure_reason_codes.py`, `test_not_applicable_calculation.py`, `test_workspace_fail_closed.py`, `tests/workspace/repositories/test_watchlist_repository.py`, `tests/test_cli_refresh.py` (docstring) and `tests/_wiring.py` (docstring). Each call that passed no policy passes `RefreshPolicy(workers=1)`, the old default.
- Moved functions ([W53](#w53-what-moves-into-applicationrefreshpy-and-the-outcome-2026-11-06), [W58](#w58-the-failure-description-rule-moves-to-applicationfailurespy-2026-11-06)): `tests/test_failure_messages.py` and `tests/test_cli_support.py` import `describe_failure` and `provider_failure_message` from `application/failures.py` (their tests stay where they are, since each also exercises the CLI); `tests/test_failure_messages.py` and `tests/test_cli_failure_envelope.py` patch `application.refresh` for the executor, the tier lookup and `RUN_SPECS_BY_KEY`, and call `_refresh_executor` with a context; the failing executor in the latter takes the context first; `tests/test_cli_runs_compare.py` patches `application.refresh.utc_now`; `tests/workspace_documents/test_workspace_documents.py` builds the summary through `build_refresh_document` and `document_json`; `tests/_probe_injection.py` patches the probe builder in `application.refresh`.
- `tests/data/test_sec_edgar_settings.py::test_an_invalid_cik_is_refused_naming_the_file_and_the_key_but_not_the_value` (review fix R4): it failed whenever the temporary path contained `abc`. Each case now checks that its own value (`0`, `abc` or `12345678901`) is absent from the message with the `Settings file <path> is invalid: ` prefix removed, so a path cannot affect it.
- `tests/application/test_providers.py`: `test_only_the_application_and_the_refresh_command_build_a_probe` is renamed `test_no_module_outside_the_application_builds_a_probe`, and only `application/` may build a probe.
- `tests/test_strategy_import_layering.py`: `application/refresh.py` is a composition-root importer and an application-tier importer; `cli_workspace.py` no longer imports the application tier.

Tests added: `tests/workspace/test_refresh_progress.py` (events only on the calling thread with one and four workers; one started and one finished event per job, in order, with matching position and refresh ID, non-decreasing totals, `admitted + remaining` equal to the job count and `finished == admitted` on the last event; a ticker under two methods; every admitted job finished and `remaining` counting the jobs never admitted after a cancellation; a callback that raises on its first and on a later event, logged once with its traceback, never called again, with a result equal to a refresh without one; an ID-addressed refresh and a missing ID); `tests/application/test_refresh.py` (a watchlist by name and by ID; the missing and empty messages; the worker-count error with its rule, values and CLI rendering; the check before the database opens; `failed`, `document` and `render_text()` with and without a provider failure; the switched-off check; progress through the operation).

Review fixes (2026-11-06): no output, help, schema or stored shape changed.

- **R1 (W50).** A job can be submitted and not yet taken by a worker thread when the cancellation event is set: the coordinator submits the replacement as soon as it settles a job, and the freed worker may not have dequeued it, which is the window the removed cancel loop acted on. Test added: `tests/workspace/test_refresh_progress.py::test_a_replacement_job_submitted_before_the_event_is_set_still_runs_and_is_saved` (one and two workers, five jobs; the observer sets the event on the started event of the first replacement job; that job is finished, saved, in the summary and inserted, no later job starts, and the last totals are `admitted == finished == workers + 1`).
- **R2.** The `--workers` help text is built from `MIN_WORKERS`, `MAX_WORKERS` and `DEFAULT_WORKERS`; the rendered help is byte for byte what it was (the help snapshot is unchanged).
- **R3.** The coordinator's module docstring states the settled behavior: a failure while saving a job is isolated to that job and recorded as its result, and the refresh continues admitting the remaining jobs.

Accepted deviations: the coordinator's lookup keeps the repository's `get` and `get_by_id` and chooses by reference, in place of one `get(ref)` that would need an adapter ([W47](#w47-the-refresh-operation-2026-11-06)); the failure description rule moved too ([W58](#w58-the-failure-description-rule-moves-to-applicationfailurespy-2026-11-06)), because `application` cannot import `cli_support`.

Noticed for later slices:

- API.4: serving refresh progress needs an event document, a transport and a way for the client to set cancellation ([W56](#w56-serving-refresh-progress-over-http-2026-11-06)).
- With cancellation set before the first admission, a refresh admits no job and returns an empty summary; the CLI exits 130 as before.

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

C1 to C18 and C5a were approved by the project owner on 2026-11-04, with C2 as amended and C5a in place of C5. W1 to W13, API.3b's implementation decisions, were approved on 2026-11-05, and W14 to W26 and W27 to W42 on 2026-11-05, and W43 to W46 on 2026-11-06.

### C1 API.3 is three slices (2026-11-04)

API.3 is three slices:

| Slice | Decisions | Branch |
| :--- | :--- | :--- |
| API.3a | C2 to C8 and this plan | `feat/api-execution-composition` |
| API.3b1 | C9, W8 to W11, W15 to W26: the watchlist actions, with the CLI switched to them | `feat/api-watchlist-actions` |
| API.3b2 | C10 to C14, W1, W3 to W7, W12, W13, W27 to W46: selection from model fields, the selection schemas and their conformance check, Site 19 | `feat/api-selections` |
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
  docs and `docs/project/STRATEGY_DEVELOPMENT.md` follow.
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

### W27 build_selection's place and input (2026-11-05)

`build_selection(context, method_id, fields: Mapping[str, object]) -> SelectionMember` lives in `application/selections.py`. `fields` is keyed by model field names, and a nested model (FCF Growth's `policy`) is a nested mapping. `analysis_id`, `method_id` and `config_schema_version` in `fields` are rejected as unknown fields. A `method_id` this version does not declare is rejected under the parameter `method_id`, as [W25](#w25-removing-by-method-needs-a-declared-method-2026-11-05) does for removals.

### W28 Configured defaults are declared on the descriptor (2026-11-05)

`StrategyDescriptor` gains `selection_settings_fields: tuple[str, ...]`, empty for a strategy with none. `build_selection` fills each named field the caller omitted from the strategy's `settings_type`, loaded through the context and read by the same attribute name. A conformance check requires each named field to be a required field of the strategy's selection model and a field of its `settings_type`. The schema generator reads the same declaration ([W35](#w35-how-the-selection-schemas-are-produced-2026-11-05)).

### W29 Momentum's window options default to the settings (2026-11-05)

As amended on review. Momentum's `--short-window`, `--long-window` and `--rsi-period` default to omitted, in its direct command and its `add-selection` subcommand, and `build_selection` fills them from the strategy's settings, so the command line and the API share one defaulting path. Their help shows the value in effect, read through the cached loader the startup check also uses (which has already validated every settings file), as Click's string default: `[default: (from settings: 50)]`. `_MOMENTUM_CLI_DEFAULTS` is removed from `cli_workspace.py` and `strategies/momentum/cli.py`. `load_all_component_settings` stays in `cli.py` by design, so an invalid settings file stops every command with one message; that is the startup check's doing and not an effect of the CLI modules' imports.

### W30 What a converter may reject (2026-11-05)

As amended by [W43](#w43-the-as-of-syntax-parser-is-in-the-application-layer-2026-11-06). A converter ([W3](#w3-the-field-to-option-table-carries-converters-2026-11-05)) translates the command-line spelling of a value and may reject a value that has no field spelling, keeping its current message: `--growth-years must be 3, 4, or 5.` and the two FCF Growth messages that list hyphenated values. The syntax of `as_of` is shared by the command line and the API, so it is parsed in the application layer and the converter only names the option. Every rule about a field's value (positivity, window order, finiteness, currency format, membership of an enum or `Literal`, presence of a required field, a timestamp's timezone offset) is in the model and is enforced only through `build_selection`. The end-of-day rule ([W4](#w4-the-as-of-date-rule-is-shared-2026-11-05)) and the timezone rule are `build_selection`'s; the timezone message is the template "Timestamp {as_of} values must include an explicit timezone offset." so the CLI's message is unchanged.

### W31 Rule templates (2026-11-05)

Validators raise a `SelectionRuleError(ValueError)` that carries a template and the fields it names. A built-in pydantic field error renders as "Invalid {field}: <pydantic text>", which is today's form; a missing required field renders as "{field} is required." and only the API can reach it, since the command line's parser rejects a missing required option first. Momentum keeps `Field(gt=0)`, so its schema keeps `exclusiveMinimum`, and a before-validator raises the templated positivity rule first, so the CLI's message is unchanged. `config_usage_errors` and its substring heuristic are deleted. `ActionParameterError` substitutes exactly the placeholders it declares, by explicit replacement and not by `str.format`, because a dotted nested name such as `{policy.historical_horizon}` is attribute access in a format string.

### W32 First error only (2026-11-05)

`build_selection` reports the first error, as the command line does. When several options are bad at once, the one reported may change, because it follows field order: an accepted deviation. Every single-failure CLI message stays byte-identical.

### W33 Field descriptions (2026-11-05)

Every selection field, including the fields of FCF Growth's `policy`, has a `Field(description=...)` written in plain English for a person filling in a form, describing what the field means and not its command-line spelling. The command line's help text is unchanged and stays separate. A conformance check requires a non-empty description on every form field.

### W34 Graham Growth's eps_basis (2026-11-05)

As amended on review. The selection field's default is `"three_year_average"` in place of `None` resolved by a validator, and `GrahamGrowthConfig`'s `eps_basis` defaults to `"three_year_average"` with its defaulting validator removed. No stored shape changes, because stored rows already hold the resolved value. The config's only production callers are the selection, which passes the resolved value, and the tool, whose argument defaults to `"three_year_average"`; none passes `None`.

### W35 How the selection schemas are produced (2026-11-05)

`scripts/generate_schemas.py` transforms each selection model's own JSON schema: it drops `analysis_id`, `method_id` and `config_schema_version`, describes `as_of` as a date or a date-time with an offset ([W4](#w4-the-as-of-date-rule-is-shared-2026-11-05)), and removes `default` and `required` for the fields of [W28](#w28-configured-defaults-are-declared-on-the-descriptor-2026-11-05). A test checks that each schema's properties are exactly the fields `build_selection` accepts. There is no separate input model.

### W36 One option style (2026-11-05)

Every direct-command option is an `Annotated` alias, including the shared ones in `cli_support.py` (`AS_OF_OPTION`, `SAVE_RUN_OPTION` and `NO_PROVIDER_CHECK_OPTION`), not only the selection options [W6](#w6-each-strategy-declares-its-selection-options-once-2026-11-05) requires. Help output is unchanged.

### W37 Duplicated defaults are checked (2026-11-05)

Where a CLI option's literal default duplicates a model field default (FCF Growth's `--forward-policy`, `--classification-basis` and `--currency`), the literal stays, so the help is unchanged, and a conformance check requires each such option's default, run through its converter, to equal the model's field default.

### W38 Help for the new and changed commands (2026-11-05)

The CLI tier generates each `add-selection` subcommand's summary from the descriptor's `label`: "Add one <label> entry per ticker to an existing watchlist." The `add-selection` group's help is "Add entries for one method to an existing watchlist, one per ticker." `watchlist create`'s help is "Create an empty watchlist." followed by the paragraph "Add entries to it with 'ian watchlist add-selection METHOD NAME TICKER...'." The subcommand's arguments are `NAME` ("Watchlist name.") and `TICKERS...` ("Tickers to add this selection for."), and its options are its direct command's selection options with their direct-command help, plus `--json` ("Emit the updated watchlist document."). Help snapshots for `watchlist create` and each `watchlist add-selection <alias>` are generated from the declared strategies.

### W39 A missing or unknown method is a parser error (2026-11-05)

`ian watchlist add-selection` alone exits 2 with "Missing command."; `ian watchlist add-selection foo ...` exits 2 with "No such command 'foo'." in place of "--analysis must be one of: ..." with exit 1. `_parse_analysis` stays for `remove-method` and `runs list --analysis`.

### W40 The argument checks are private again (2026-11-05)

`check_watchlist_name` and `check_tickers` are private in `application/watchlists.py` again, since `create` no longer seeds.

### W41 Re-recorded outputs and the specimen (2026-11-05)

Every recorded workspace-command output and test that used `create --analysis` as setup is rewritten as `create` followed by `add-selection <alias>`, and each re-recorded file is listed in the implementation record. `tests/specimen/` and the `scripts/new_strategy.py` templates follow W28, W31, W33, W36 and W42, so a generated strategy passes every new check.

### W42 Errors keep what a translation needs (2026-11-05)

A `SelectionRuleError` carries a stable rule identifier (form `<alias>.<rule>`, for example `momentum.window_order`), the fields it names, and its values as named arguments. Templates use placeholders for both field names and values ("Invalid momentum windows: {short_window} ({short_window_value}) must be smaller than {long_window} ({long_window_value})."), and the CLI renders every message byte-identically. A built-in pydantic error keeps its error `type` and its plain context values beside its rendered text, with the rule identifier `pydantic.<type>`. `ActionParameterError` gains the same, a rule identifier (form `watchlist.<rule>` for the watchlist actions) and value arguments, so [W17](#w17-an-actions-parameter-error-is-a-template-2026-11-05)'s errors follow one rule with the selection errors. The failure document does not change in this slice.

### W43 The as-of syntax parser is in the application layer (2026-11-06)

Amends [W30](#w30-what-a-converter-may-reject-2026-11-05). `parse_as_of_text(value: str | None) -> date | datetime | None` is in `application/selections.py`, with the rules the command line has always had: the text is stripped, an empty value is an error, a 10-character value is a date, a trailing `Z` or `z` means `+00:00`, and anything else is read by `datetime.fromisoformat`. It raises `ActionParameterError` under the parameter `as_of`: "{as_of} must be non-empty when supplied." (rule `selection.as_of_empty`) and "{as_of} must be YYYY-MM-DD or a valid timezone-aware ISO-8601 timestamp." (rule `selection.as_of_syntax`). The command line's `--as-of` converter, `parse_as_of_option` in `cli_support.py`, calls it and names the error `--as-of`, so every message, `parameters` value and exit code is unchanged; `cli_support.parse_as_of` is removed. `build_selection` still accepts only a date or a datetime.

### W44 Placeholders are substituted in one pass (2026-11-06)

`ActionParameterError` replaces every placeholder of its template in a single pass, so text inserted for one placeholder is never itself substituted, and a placeholder the error does not declare stays as written.

### W45 The specimen needs no cast for its selection type (2026-11-06)

`BehaviorView.selection_type` is typed `type[FrozenSelection]`, the base every selection shares, so the specimen returns its own class without a cast and the count of `cast(` in `tests/specimen/closed_types.py` is back to five. `build_selection` narrows the validated selection to `SelectionMember` with `isinstance` and fails closed with `UndeclaredStrategyError` for any other type.

### W46 The add-selection group's help is tested without a snapshot (2026-11-06)

A test checks that `ian watchlist add-selection --help` exits 0 and lists exactly the declared strategies' aliases, each with the summary "Add one <label> entry per ticker to an existing watchlist.", the expected text built from the declared strategies. The group has no stored snapshot, because it would change with every strategy added.

### W47 The refresh operation (2026-11-06)

`application/refresh.py` holds `refresh_watchlist(context: ApplicationContext, ref: WatchlistRef, *, workers: int = DEFAULT_WORKERS, save: bool, provider_check: bool, cancellation: threading.Event | None = None, on_progress: Callable[[RefreshProgress], None] | None = None) -> RefreshOutcome`. It opens, checks and closes its own database as `analyze` does, and builds its own provider probe from the context's settings. It takes a `WatchlistRef` ([W19](#w19-watchlistref-is-a-name-or-an-id-2026-11-05)); the CLI passes `WatchlistName`. The coordinator's snapshot lookup accepts a `WatchlistRef` instead of a name, and a missing watchlist raises `WatchlistNotFoundError` with `not_found_message(ref)`, which for a name is byte-identical to today's message. The lookup keeps the repository's `get(name)` and `get_by_id(id)` and the coordinator chooses between them by the reference; no adapter is added. An empty watchlist addressed by ID is reported under its display name.

### W48 The coordinator is renamed coordinate_refresh (2026-11-06)

The workspace coordinator `workspace.refresh.refresh_watchlist` is renamed `coordinate_refresh`, so the two layers do not share a function name (as `analyze` and `execute` do not). Every reference follows, tests included.

### W49 One admission path (2026-11-06)

The coordinator's sequential branch (`workers == 1`) is deleted; one worker runs through the same bounded-admission path as several. `_SEQUENTIAL_POLICY` and the coordinator's default policy are deleted: `policy` is a required argument. The module docstring is rewritten to describe one path. With one worker the executor runs on a worker thread and a saved run's times come from the replay clock, which holds the measured instants.

### W50 An admitted job always runs (2026-11-06)

After the cancellation event is set, no new job is admitted, but the coordinator no longer cancels a submitted future that has not started: every admitted job runs to completion and is settled (saved when saving) normally.

### W51 The progress event types (2026-11-06)

Defined in `workspace/refresh.py`: `RefreshTotals(admitted, finished, remaining)`, where `remaining` counts the jobs not yet admitted and stays above 0 after a cancellation; `RefreshJobStarted(refresh_id, position, ticker, selection, totals)`; `RefreshJobFinished(refresh_id, position, result, totals)`; and `type RefreshProgress = RefreshJobStarted | RefreshJobFinished`, all frozen dataclasses. "Started" is sent when the coordinator admits the job to a free worker slot (totals already counting it as admitted). "Finished" is sent after the coordinator has settled the job, so a saved run is already persisted (totals already counting it as finished). Both are sent only from the coordinating thread ([C15](#c15-progress-events-2026-11-04)). `position` pairs a job's two events when one ticker appears under two methods; `refresh_id` lets a client link a refresh before the summary.

### W52 Emission and the failing-callback guard (2026-11-06)

Emission and the failing-callback guard ([C16](#c16-a-failing-progress-callback-2026-11-04)) are both in `workspace/refresh.py`, beside the coordinator. The guard catches `Exception` (never `BaseException`); the first exception is logged once with its traceback through the module's logger (`logging.getLogger(__name__)`), every later event is dropped, and the refresh completes normally with a result identical to a refresh with no callback.

### W53 What moves into application/refresh.py, and the outcome (2026-11-06)

From `cli_workspace.py`: `_refresh_executor` (the durable instrument-profile cache is built once per refresh over the operation's database, as now), `_describe_job_failure`, `_refresh_has_failure`, the provider check after the batch, the summary document builder renamed `build_refresh_document`, and `_refresh_text`. `RefreshOutcome` mirrors `AnalysisOutcome`: `document` (the `RefreshSummaryDocument`, `provider_check` element included), `failed: bool` (today's `_refresh_has_failure` rule), and `render_text()` returning the text mode's complete output, provider-check lines first, exactly as the CLI prints it today. The CLI prints `document` with `--json` or `render_text()` otherwise, and sets exit 1 from `failed`. The refresh executor's context is the operation's `context`. `_workspace_database` is deleted.

### W54 The worker-count check (2026-11-06)

The worker-count check is in the operation and runs before the database opens ([W18](#w18-arguments-are-checked-before-the-database-opens-2026-11-05)). It raises `ActionParameterError` ([W17](#w17-an-actions-parameter-error-is-a-template-2026-11-05), [W42](#w42-errors-keep-what-a-translation-needs-2026-11-05)) with rule identifier `refresh.workers_range`, a `{workers}` placeholder and the value, minimum and maximum as named arguments (`value`, `minimum`, `maximum`). The CLI renders it as "--workers must be between 1 and 4." with the same `parameters` value and exit code as today. `DEFAULT_WORKERS = 2` is declared once (beside `MIN_WORKERS` and `MAX_WORKERS`) and used by the operation, `RefreshPolicy` and the CLI option default; the `--workers` help text does not change.

### W55 Cancellation stays an event (2026-11-06)

Cancellation stays a `threading.Event` passed by the caller. SIGINT handling stays in the CLI. `RefreshOutcome` has no `cancelled` field; the CLI exits 130 from its own event, as now.

### W56 Serving refresh progress over HTTP (2026-11-06)

The contract's API.4 entry ("Action endpoints and refresh jobs") records that serving refresh progress over HTTP needs an event document, a transport (server-sent events, WebSocket or polling, not chosen) and a way for the client to set cancellation.

### W57 The tests (2026-11-06)

The tests are those of the implementation record's "Tests added" paragraph: events on the calling thread with one and four workers; one started and one finished event per job with matching position and refresh ID and consistent totals; two pairs for a ticker under two methods; the behavior after a cancellation; a failing callback on its first and on a later event; the operation by ID and by name, the worker-count error, the check before the database opens, and `failed`, `document` and `render_text()` with and without a provider failure; and the recorded `ian refresh` outputs, unchanged.

### W58 The failure description rule moves to application/failures.py (2026-11-06)

Amends [W53](#w53-what-moves-into-applicationrefreshpy-and-the-outcome-2026-11-06). `describe_failure`, `FailureDescription`, `provider_failure_message` and the private constant sets and message tables they use move from `cli_support.py` to `application/failures.py`, unchanged in behavior and message text, because the refresh operation needs the rule and `application` cannot import the CLI. `cli_support.py` (the direct commands' failure reporting) and `application/refresh.py` import them from there; nothing forwards from `cli_support.py`. The tests of these functions keep their files and follow the move by their imports.
