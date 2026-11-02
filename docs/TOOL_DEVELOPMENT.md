# Analysis Strategy Development Guide

How to add a deterministic financial analysis strategy to the engine, and how the code a strategy plugs into is organised. The workflow comes first; the explanation it relies on is under [Background](#background-how-a-strategy-fits-into-the-code).

## At a glance

- **What this is:** the one contributor guide for adding an analysis strategy. It is the only place the workflow, the list of edit sites and the settings convention are written down.
- **What the tooling does:** a generator writes the typed wiring and leaves every unfilled body failing the test suite; a status command lists which edit sites are done and which are missing; conformance tests and the quality gate fail, naming the missing site, if any is left out.
- **What stays yours:** the financial rules. A strategy owns its configuration, its inputs, its calculation and its result type. The generator writes no formula, classification, presentation text or settings file, and copies nothing from another strategy.
- **What no strategy does:** register itself, load as a plugin or be discovered at run time. The set of strategies is one closed, statically declared tuple that the generator extends and a reviewer reads (`investment_analysis_engine/strategy_wiring.py`).
- **Commands run from the repository root** through `uv run`, as [`AGENTS.md`](../AGENTS.md) describes.

## Add a strategy: the workflow

Do the steps in this order. Each one ends with something you can check.

| Step | Do | You know it worked when |
| :--- | :--- | :--- |
| 1 | [Run the generator](#1-run-the-generator) | it lists the files it wrote and edited |
| 2 | [Check the status command](#2-check-the-status-command) | it prints a line per site and lists what is missing |
| 3 | [Fill the stubs](#3-fill-the-stubs) | `tests/test_no_unfilled_stubs.py` passes and the strict type check passes |
| 4 | [Write the reviewed sites](#4-write-the-reviewed-sites) | the status command shows no missing site |
| 5 | [Regenerate the schemas and the lists](#5-regenerate-the-schemas-and-the-generated-lists) | both scripts report current output |
| 6 | [Run the complete gate](#6-run-the-complete-gate) | every step in its closing summary passes |

### 1. Run the generator

**Code written before the generator runs.** The generator refuses a package that already exists, and `test_t14_wiring_files_declare_no_discovery_or_registration` requires an `evaluation.py` in every strategy folder, so code that must land first cannot live in the future package.

- Put it in one module directly under `investment_analysis_engine/strategies/` (Piotroski's was `strategies/piotroski_calculation.py`), with no `__init__.py` and no `<module_name>/` directory. Only its tests import it.
- Move it into the generated package as the first step after the generator runs.
- That placement was approved for Piotroski ([3.5.3 slice plan A.3](project/milestones/v0.2/step-3.5/STEP_3_5_3_SLICE_PLAN.md#a3-authorization-of-the-calculators-location-2026-10-29)); ask before using it for another strategy, and if it breaks another check, stop and ask rather than adjust the check.

```bash
uv run python -m scripts.new_strategy <module_name> --label "<Label>" [--alias <alias>]
```

- `<module_name>` is the snake-case package name. It gives the analysis identifier, the method identifier and the tool name. The alias defaults to the hyphenated module name.
- It writes typed stubs for the role files into `investment_analysis_engine/strategies/<module_name>/`: `vocabulary`, `analyzer`, `tool`, `selection`, `codec`, `execution`, `cli`, `presenter`, `envelope`, `replay` and `evaluation`.
- It makes one insertion in each of five existing files: `strategy_wiring.py`, `orchestrator/tool_names.py`, `workspace/strategy_types.py`, `cli_strategy_wiring.py` and `evaluation/strategy_fixtures.py`.
- A label is at most 40 characters and a module name at most 40 (`MAX_LABEL_LENGTH` and `MAX_MODULE_NAME_LENGTH` in `scripts/new_strategy.py`), the lengths at which no generated line passes 120 characters, proven by `tests/scripts/test_new_strategy_label_limits.py`. A longer one is a usage error: the generator exits with code 2 and writes nothing. The longest name in the Step 3.5 specifications, "Cash-Flow Valuation Multiples", has 29.
- It refuses to overwrite. If a target file exists, or the module name, alias, tool or method identifier is already used, it writes nothing and exits with code 2, listing the conflicts.
- Every unfilled body calls `unfilled_stub(...)`. The generated files type-check as written, and the test suite fails while any such call remains under `investment_analysis_engine/`.
- The generated descriptor has `settings_type=None`; see [Strategy settings](#strategy-settings).
- The analyzer stub is the form with no configuration, `BaseAnalyzer[<Name>Result]`; see [When a strategy gains a selection parameter](#when-a-strategy-gains-a-selection-parameter).
- It writes these bodies in full, from the helpers in [Execution capture and durable persistence](#execution-capture-and-durable-persistence), as Piotroski's files do:
  - `execute_<module_name>` composes the instrument profile with `compose_production_profile`, so an ETF is recognized, builds the context from the selection and calls the analyzer;
  - the direct command, with `--details`, `--diagnostics`, `--json`, `--save-run` and `--no-provider-check`, and `refresh`, which both call `compose_<module_name>`;
  - `build_selection`, which carries the shared `as_of` and `use_cache` fields only;
  - the tool handler's `__call__`, which validates the arguments, builds the context with `tool_context` and calls the analyzer;
  - the result's common fields: the analyzer module declares `<Name>Result` with the names, types and checks of Piotroski's result for the ticker, the requested and effective boundaries, the instrument profile, the execution status, the reason code and reason, the input failure and the warnings and diagnostics, which the shared document header and tail and the normalizer read. Add the strategy's own fields after them;
  - `from_<module_name>_capture`, which passes the evidence, the profile, the status and the recorded provider failure, as `from_piotroski_capture` does.
- It leaves these as stubs, because each is the strategy's own:
  - `compose_<module_name>(executed_at)` in `cli.py`, which builds the analyzer and the provider the profile is composed from; `executed_at` is the run's single reading of the current time, never the `--as-of` boundary;
  - the analyzer's body;
  - the presenter;
  - the evaluation `compose`.

### 2. Check the status command

```bash
uv run python -m scripts.strategy_status <module_name> [--alias <alias>]
```

- It prints `done` or `missing` for each site in the [edit-site table](#edit-sites-of-a-strategy), in table order, and a diagnostic under each missing one. It exits with code 1 while any site is missing.
- It runs the same check functions as the conformance tests, so the two cannot disagree.
- It does not run the type checker; the gate does.
- `done` means the site exists, has the required names and calls no `unfilled_stub`. A new-file site whose file still calls `unfilled_stub` is `missing`, and its diagnostic names the file and the line of each call.
- Right after the generator, expect `missing` on every site whose file has an unfilled body (`analyzer`, `codec`, `cli`, `presenter`, `replay` and `evaluation`; `execution` and `tool` are `done`), on the reviewed sites you have not yet written, and on `schema` and `strategy-docs` until step 5. `codec`, `presenter` and `replay` run the strategy's stored run, which needs the `evaluation` file's sample selection; until that is written their diagnostic ends `not checked: depends on unfilled evaluation (<file>:<line>)`. Fill the site it names first.
- If a strategy file was deleted or emptied, or a wiring entry removed, the package cannot be imported and no other site can be checked. The command matches the failing module or file against the site files and prints one `missing <site-id>` line with the file to change, and the original Python error on the next line; restore or write that site, and run the command again. An error that matches no site is printed as `missing  import` with the Python error.

### 3. Fill the stubs

- Start from the financial question and the evidence it needs. Fill `vocabulary`, the models, `analyzer` and the resolver first, then the files that package the result: `codec`, `compose_<module_name>` in `cli`, `presenter`, `replay` and the `compose` function of `evaluation`. Add fields to `envelope` for what the result reports. `selection`, `tool`, `execution` and the rest of `cli` are complete as generated; edit them only when the strategy gains a parameter, as [When a strategy gains a selection parameter](#when-a-strategy-gains-a-selection-parameter) describes.
- The status command lists every `unfilled_stub` call that remains in a site's file, with file and line, and `uv run python -m pytest tests/test_no_unfilled_stubs.py` lists them all. The strict type check is `uv run python -m mypy --strict investment_analysis_engine tests scripts`.
- Financial math is deterministic Python. The authority for formula semantics is [Financial Math & Data Conventions](user/FINANCE_MATH.md); add the strategy's definitions there and in the [Glossary](user/GLOSSARY.md).
- Keep missing, unavailable and not-applicable evidence explicit (`MetricResult`, reason codes, retained provenance). Never substitute zero.
- Write a reason message in plain words: name an operand in words with its year-end ("Net income for 2025-12-31 is unavailable: ..."), never by its stored key (`net_income_t`). Piotroski's calculation receives the three year-ends in `PiotroskiInputs` for this purpose and spells any underscore-joined name in a provider's reason as words; the operand keys in the stored result are unchanged.
- Before writing a resolver, check [Shared metrics and SEC inputs](#shared-metrics-and-sec-inputs).
- Write tests for the rules, the unavailable-evidence cases and the edge cases as you go; see [Testing and quality expectations](#testing-and-quality-expectations).

### 4. Write the reviewed sites

The generator cannot write these. Each holds content a reviewer must judge, and its check shows only that the content exists. The kind of each site is in the [edit-site table](#edit-sites-of-a-strategy). A stored output is written by a command from the current code, so an intended change shows up as a diff to review; read each written file before committing it.

| Site | What you write | Command that writes it |
| :--- | :--- | :--- |
| `settings` | A `settings.toml` and its model, only if the strategy has user-tunable defaults ([Strategy settings](#strategy-settings)) | none; written by hand |
| `cases` | Fixtures (under `investment_analysis_engine/evaluation/fixtures/`) and reviewed Golden cases against the tool name, in `evaluation/cases/<module_name>.py` | none; written by hand |
| `catalog` | The case-module import, the case entries and the suite version bump in `evaluation/catalog.py`, and the pinned id list in `tests/evaluation/test_catalog.py` | none; written by hand |
| `direct-output` | An entry for the alias in `_COMMANDS` of `tests/_direct_command_output.py` (the command's fixed arguments), then its stored text and JSON output | `uv run python -m tests._direct_command_output` |
| `strategy-documents` | A `<alias>-success` entry in `CASES` of `tests/_strategy_document_output.py`, then its stored direct and replayed documents | `uv run python -m tests._strategy_document_output` |
| `help-snapshot` | The strategy's command row in the stored application help, and the stored help of its own command (`<alias>.txt`, which `tests/test_cli_help_output.py` requires of every declared strategy) | `uv run python -m tests._cli_help_output` |
| `guide` | The investor-facing guide under `docs/user/strategies/`, with Finance Math and Glossary links | none; written by hand |
| `watchlist-options` | Options of its own on the watchlist commands, only if it has any beyond the shared ones | none; written by hand |

What a Golden case, a fixture and a catalog entry must contain, and how their expected values are established, is in [Evaluations & Golden Suite](EVALUATIONS.md#5-golden-cases-and-fixtures) and its [maintenance rules](EVALUATIONS.md#10-maintenance-rules). For the shape of a `cases` module, a catalog entry, a guide or a settings file, open the file named in the edit-site table for an existing strategy (replace `{module}` with its package name); take the structure, not its rules.

A data file that the evaluation tier reads must be listed, as an explicit path, in `[tool.setuptools.package-data]` of `pyproject.toml`, or the installed package lacks it; `tests/evaluation/test_package_data_coverage.py` fails naming any file that is not.

**Notes on the reviewed sites**

- `direct-output`: a strategy that builds its own provider reaches Yahoo (identity and instrument kind) unless the harness replaces the provider's Yahoo adapter. Patch the strategy's names in `enter_fixture_providers` of `tests/_direct_command_output.py`, as it does for Piotroski (its `ProductionFinancialFactsProvider`, given `_FixtureYahoo`) and for the others (their `YFinanceClient`). Otherwise regeneration calls the live service and stores its answer.
- `catalog`: the patches in `tests/scripts/generator_fills/patches.toml` anchor on structural text (the end of a tuple and the definition after it), never on a strategy, a case id, a version or a count, and the generator's end-to-end test bumps the suite version and the case counts itself from the files as they stand. Adding a strategy or a Golden case therefore needs no `patches.toml` edit. A Golden case still moves the suite and fixture-set versions in `evaluation/catalog.py`, [`EVALUATIONS.md`](EVALUATIONS.md) and the case counts in `tests/evaluation/test_catalog.py` together; edit them by hand.
- A new failure: a class that declares a `reason_code` must be pinned in `tests/_failure_code_table.py`, which is written by hand and is not derived from the code.

**Regeneration commands**

| Command | Rewrites | Provider-check switch |
| :--- | :--- | :--- |
| `uv run python -m tests._direct_command_output` | `tests/expected_output/direct_commands/` | Needed; it runs inside `provider_check_switched_off()` |
| `uv run python -m tests._strategy_document_output` | `tests/expected_output/strategy_documents/` | Needed; the same context manager |
| `uv run python -m tests._cli_help_output` | `tests/expected_output/cli_help/` | Not needed; it runs `--help` only |
| `uv run python -m tests._workspace_command_output` | `tests/expected_output/workspace_commands/` | Not needed; its fixtures cannot fail on a provider |

- The provider-check switch matters because these commands run outside pytest, where `tests/conftest.py` does not apply: a command that fails on a provider would otherwise send a real test request while its output was being stored. A new entry point that runs a command wraps its work in `provider_check_switched_off()` from `tests/_direct_command_output.py`.
- A new workspace command needs the last command, and the scenario's steps (`_STEPS` in `tests/_workspace_command_output.py`) are edited by hand.

Each command rewrites every stored file of its kind, not only the new strategy's. Run `git diff --stat` afterwards and confirm that no existing strategy's file changed. The status command shows when a site is `done`.

### 5. Regenerate the schemas and the generated lists

```bash
uv run python -m scripts.generate_schemas
uv run python -m scripts.generate_strategy_docs
```

- The first writes the strategy's published schema under `schemas/` and rewrites the two watchlist schemas, which list every strategy. The second rewrites the strategy lists in `docs/user/USAGE.md` and `docs/user/WORKSPACE.md` and the edit-site table in this guide.
- Add `--check` to either command to report what is out of date without writing. A current tree prints nothing and exits 0; a stale one prints each file and exits 1. Drift tests in the suite fail on stale output.
- Run both as `uv run python -m scripts.<name>` from the repository root, the form every diagnostic and generated-block comment gives. Running `generate_schemas.py` or `generate_strategy_docs.py` by its file path fails with `ModuleNotFoundError: No module named 'scripts'`.

### 6. Run the complete gate

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

```bash
bash "$(git rev-parse --show-toplevel)/scripts/run-quality-gates.sh"
```

- Run the wrapper that matches your shell. It runs Ruff, the strict type check and the full test suite with coverage, and keeps its complete output in `gate-output.txt`; the last line it prints is that file's path. [`AGENTS.md`](../AGENTS.md) §10 has the details.
- The gate fails while any `unfilled_stub` call remains, while any site is missing, and while a schema or generated list is stale. The conformance tests are in `tests/test_strategy_wiring_conformance.py`, one test per site and strategy, named `test_t25_every_site_is_done_for_every_declared_strategy[<strategy>-<site>]`; the pytest failure repeats the status command's diagnostic for that site.
- If a strategy file is deleted or a wiring entry removed, pytest cannot collect the conformance test modules and reports the Python error (for example `ModuleNotFoundError` or `UndeclaredStrategyError`), followed by a line that says to run the status command. Run it: it names the site and the file to change, as in step 2.
- A stale published schema fails the schema drift test, `tests/scripts/test_generate_schemas.py::test_published_schemas_are_current`, and the `schema` site; both end with `run uv run python -m scripts.generate_schemas`. The tier coverage test checks only that each strategy has a schema file.

## Edit sites of a strategy

A strategy touches the places below. Run the [status command](#2-check-the-status-command) to see which are `done` and which are `missing` for one strategy, with the diagnostic for each missing one.

- **Kind:** `new_file` is a new Python file the strategy owns, with required module-level names. `edit` is an entry added to an existing file. `reviewed` is hand-written content that a reviewer checks. `command` is a script whose output must be regenerated.
- **Generated:** `yes` means the generator makes the change in step 1.
- **Placeholders in a path or a check:** `{module}` is the strategy's package name, `{module_upper}` the same name in upper case, `{alias}` its hyphenated command alias and `{guide}` its upper-case guide name.

<!-- BEGIN GENERATED edit-sites: written by uv run python -m scripts.generate_strategy_docs; generated, do not edit by hand. -->
| Site | Edit | File | Kind | Generated | Check |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `vocabulary` | Vocabulary: the strategy's identity constants and the enumerations several of its files use. Every other file of the strategy reads its identifiers from this leaf, so it imports nothing from its package. | `investment_analysis_engine/strategies/{module}/vocabulary.py` | new_file | yes | `site_vocabulary`: the file is missing, or defines no `ANALYSIS_ID`, `METHOD_ID`, `CONFIG_SCHEMA_VERSION`; the file imports from its own package |
| `analyzer` | Analyzer module: result and analyzer, and the configuration when the strategy has one. The analyzer defines the strategy's result type, which the descriptor must agree with. | `investment_analysis_engine/strategies/{module}/analyzer.py` | new_file | yes | `site_analyzer`: the file is missing, or defines no `.+Analyzer`; analyzer X (result Y) has no descriptor |
| `settings` | Settings: the shipped settings file beside the model, only when the strategy has user-tunable defaults. A strategy's tunable defaults live in a settings.toml beside the model that validates them, and the descriptor names the model; a strategy with none has no settings.py and nothing to add. | `investment_analysis_engine/strategies/{module}/settings.toml` | reviewed | no | `site_settings`: the package has a settings.py but no settings.toml beside it, or the descriptor's settings_type is not the model that file defines |
| `descriptor` | Descriptor constant, StrategyBehavior declaration and STRATEGIES entry. The closed tuple of descriptors is what every generic consumer iterates. | `investment_analysis_engine/strategy_wiring.py` | edit | yes | `site_descriptor`: no descriptor in STRATEGIES carries the strategy's alias or package |
| `tool-name` | ToolName member. The tool enumeration is a type-level list that mypy needs and no descriptor can generate. | `investment_analysis_engine/orchestrator/tool_names.py` | edit | yes | `site_tool_name`: ToolName member X has no descriptor |
| `tool` | Arguments model, dependency class, handler. The model-facing tool surface of the strategy. | `investment_analysis_engine/strategies/{module}/tool.py` | new_file | yes | `site_tool`: the file is missing, or defines no `.+ToolArguments`, `.+ToolDependencies`, `.+ToolHandler`; tool-argument model X has no descriptor |
| `unions` | NativeEvidence and SelectionMember entries. Both unions are type-level lists that the descriptor's bounds are checked against. | `investment_analysis_engine/workspace/strategy_types.py` | edit | yes | `site_unions`: the descriptor's selection class or result type is not in the union |
| `selection` | Selection class. The stored, typed choice of this strategy's parameters. | `investment_analysis_engine/strategies/{module}/selection.py` | new_file | yes | `site_selection`: the file is missing, or defines no `.+Selection`; descriptor X has no selection member |
| `codec` | Codec and native-status function. A stored run is encoded and decoded by the strategy's own functions, and the native-status function returns the `CalculationStatus` the strategy reports. | `investment_analysis_engine/strategies/{module}/codec.py` | new_file | yes | `site_codec`: the file is missing, or defines no `encode_.+`, `decode_.+`, `.+_native_status`, `.+_ticker`; the stored run does not decode to the result execute stored |
| `execution` | Execution adapter, capture type, normalizer. The adapter runs the analyzer and the normalizer hands `ExecutionCapture` the evidence, the profile, the native status and the provider failure it recorded. It never names a `RunOutcome`: `RunOutcome.from_status` produces the outcome and `ExecutionCapture` derives it. | `investment_analysis_engine/strategies/{module}/execution.py` | new_file | yes | `site_execution`: the file is missing, or defines no `.+Capture`, `from_.+_capture` |
| `cli` | CLI file: direct command, selection builder, refresh executor. The strategy's command-line behavior lives in its own package, and the command takes its exit code from `exit_code_of` in `cli_support.py`. | `investment_analysis_engine/strategies/{module}/cli.py` | new_file | yes | `site_cli`: the file is missing, or defines no `build_selection`, `refresh`, `command` |
| `cli-tier` | CLI-tier entry. A lower layer cannot import the command file, so the tier pairs it with the descriptor's behavior. | `investment_analysis_engine/cli_strategy_wiring.py` | edit | yes | `site_cli_tier`: strategy X is not wired in: CLI tier |
| `presenter` | Presenter and JSON builder. The strategy renders its own result in every presentation mode. | `investment_analysis_engine/strategies/{module}/presenter.py` | new_file | yes | `site_presenter`: the file is missing, or defines no `render_.+`, `.+_document`; the replayed JSON does not validate as X |
| `envelope` | Envelope model and document version. Every --json document is a typed model with a published schema. | `investment_analysis_engine/strategies/{module}/envelope.py` | new_file | yes | `site_envelope`: the file is missing, or defines no `DOCUMENT_SCHEMA_VERSION`; command X offers --json but has no typed document model |
| `replay` | Replay projector and headline function. A stored run is replayed through the strategy's own text projector and document projector, and the same file holds the strategy's headline function, which supplies its cells to the side-by-side refresh table. | `investment_analysis_engine/strategies/{module}/replay.py` | new_file | yes | `site_replay`: the file is missing, or defines no `project_.+`, `project_.+_document`, `headline_.+`; replay in X mode raised or is empty, or the replayed document is not X's document |
| `evaluation` | Evaluation file: fixture composition, requirement, the fixture ids it understands and a sample selection. The evaluation tier composes the strategy's fixtures from this file. | `investment_analysis_engine/strategies/{module}/evaluation.py` | new_file | yes | `site_evaluation`: the file is missing, or defines no `FIXTURE_IDS`, `REQUIREMENT`, `SAMPLE_SELECTION`, `compose`; strategy X requires fixture ids that its evaluation tier entry and the context do not declare |
| `evaluation-tier` | Evaluation-tier entry. The tier pairs the strategy's bundle with its requirement, ids, sample selection and composition. | `investment_analysis_engine/evaluation/strategy_fixtures.py` | edit | yes | `site_evaluation_tier`: strategy X is not wired in: evaluation tier |
| `cases` | Fixtures with their fixture ids, and cases with their reviewed arguments table. Reviewed case truth is written by hand against tool names; the fixtures live in the evaluation fixtures package. | `investment_analysis_engine/evaluation/cases/{module}.py` | new_file | no | `site_cases`: the file is missing, or defines no `{module_upper}_ARGUMENTS`, `{module_upper}_CASES`; tool X is required by no golden case |
| `catalog` | Catalog: the case-module import, the case tuple entries and the suite version bump; the pinned id list in the catalog test. The case tuple, the suite version and the pinned ids are reviewed evaluation truth; the check cannot tell whether the suite version was bumped. | `investment_analysis_engine/evaluation/catalog.py` | reviewed | no | `site_catalog`: the catalog does not import the case module, or a case id is not pinned in the catalog test |
| `direct-output` | Direct command expected output: the command's fixed arguments and its stored text and JSON output. The direct command's text and JSON output are compared byte for byte with reviewed files, and the failure-message and save-run tests run the command from its fixed arguments. | `tests/expected_output/direct_commands/{alias}.txt` | reviewed | no | `site_direct_output`: tests/_direct_command_output.py has no entry for the alias in _COMMANDS, or the stored .txt or .json output does not exist |
| `strategy-documents` | Stored strategy document: the success case and its stored direct and replayed documents. The typed document is compared byte for byte with a reviewed file, direct and replayed, and the provider-check and envelope-version tests start from the strategy's cases. | `tests/expected_output/strategy_documents/{alias}-success.direct.json` | reviewed | no | `site_strategy_documents`: tests/_strategy_document_output.py has no case named <alias>-success, or the stored .direct.json or .replay.json document does not exist |
| `help-snapshot` | Help snapshots: the strategy's row in the application help and the help of its own command. The application's help is compared byte for byte with a reviewed snapshot that lists every command in the order it is added, and each strategy command's help with a snapshot of its own. | `tests/expected_output/cli_help/application.txt` | reviewed | no | `site_help_snapshot`: the application snapshot has no command row for the alias, or tests/expected_output/cli_help/<alias>.txt does not exist |
| `guide` | User guide with FINANCE_MATH.md and GLOSSARY.md links. Each strategy has an investor-facing guide. | `docs/user/strategies/{guide}.md` | reviewed | no | `site_guide`: no guide for alias X |
| `watchlist-options` | Watchlist options of the strategy, only when it has any beyond the shared ones. A flag the selection builder reads needs a typed field in WatchlistFlags and an option on both watchlist commands. | `investment_analysis_engine/cli_watchlist_flags.py` | reviewed | no | `site_watchlist_options`: the selection builder reads a flag that WatchlistFlags or a watchlist command lacks |
| `schema` | Published schema (run uv run python -m scripts.generate_schemas). Every strategy document has a checked-in schema. | `schemas/{alias}.schema.json` | command | no | `site_schema`: schema schemas/<alias>.schema.json is missing or out of date; run uv run python -m scripts.generate_schemas |
| `strategy-docs` | Generated strategy lists (run uv run python -m scripts.generate_strategy_docs). The strategy lists in USAGE.md and WORKSPACE.md are generated from the descriptors, one entry per strategy. | `docs/user/USAGE.md` | command | no | `site_strategy_docs`: the strategy is missing from the generated block of USAGE.md or WORKSPACE.md, or a block is out of date; run uv run python -m scripts.generate_strategy_docs |
<!-- END GENERATED edit-sites -->

## Strategy settings

A strategy gets a settings file only when it has defaults a user may reasonably tune without changing what the method is, such as window lengths, look-back periods or a history start date. Values that define the method (for example Graham's 22.5) and data-eligibility rules stay in code as documented constants. A strategy with nothing to tune has no `settings.py` and no `settings.toml`, and its descriptor has `settings_type=None`. The generator writes no settings file: it cannot know the settings, and a model that can hold only one value is not allowed.

When a strategy does get settings, add these, in this order:

| # | Add | Rule |
| :--- | :--- | :--- |
| 1 | `settings.py` in the strategy package with a `<Strategy>Settings` model | Frozen, forbids unknown keys, strict types and **no defaults**; validators enforce invariants (for example short window < long window); each field's docstring documents its key |
| 2 | `settings.toml` beside `settings.py` | The shipped file is the single source of every default value: flat keys, each with a one-line comment |
| 3 | The model on the descriptor | Set `settings_type` to the model in `strategy_wiring.py` |
| 4 | The entry points below | The strategy never reads settings; composition loads them and passes them in |

Users override any subset of the keys in `strategies/<alias>.toml` in their settings folder. The loader merges the two files per key, and a missing, invalid or unknown key stops every command, including `--help`, with exit code 2.

**Entry points**

| Entry point | How the settings arrive |
| :--- | :--- |
| Direct command | A loader function in `cli_composition.py`, beside `momentum_settings`, supplies the command's option defaults, so `--help` shows the configured values |
| Workspace selection | The configured values are copied into the selection when it is created; a later edit to the file never changes a saved entry, and replay never reads settings |
| Calculation constants | Passed to the analyzer when it is built |
| Local-model tool | The handler receives the settings in its dependencies; a tool argument with a configured default is optional, `None` means "use the configured value", and the field description says so |

Golden evaluation never reads a settings file: its composition passes fixed settings, so editing a file cannot change Golden results or the model prompt.

The `settings` site is reviewed. It is done when the package has no `settings.py`, and when it has one only if a `settings.toml` sits beside it and the descriptor's `settings_type` is the model that file defines. A conformance test also checks that every declared model has a shipped file that validates, that every shipped file belongs to a descriptor, and that every model is frozen, forbids unknown keys and has no defaults. The [Architecture](project/ARCHITECTURE.md#6-analysis-strategies-the-boundary) gives the rationale.

### When a strategy gains a selection parameter

The generator writes the form with no configuration. When the strategy gets a parameter a user selects (a window length, a horizon), move to the configured form, as FCF & Earnings Growth did. The names below are FCF-Growth's.

1. In `analyzer.py`, change `BaseAnalyzer[XResult]` to `BaseAnalyzer[XResult, XConfig]`.
2. Add the `config` parameter to `run_analysis`, after `context`: `run_analysis(self, ticker, context, config)`.
3. Add `<Name>Config` (`FCFEarningsGrowthConfig` in `models.py`) and `to_<name>_config()` on the selection (`to_fcf_config()` in `selection.py`), and the parameter itself as a field of the selection.
4. Pass the config through every caller: the tool handler builds it from the validated arguments (`tool.py`), `execute_<name>` takes it as a parameter, the direct command builds it from its options, and `refresh` builds it from the stored selection with `stored_configuration(selection.to_<name>_config)`.
5. Bump `CONFIG_SCHEMA_VERSION` in `vocabulary.py`, because the persisted selection changed shape: runs stored under the older version are refused when read, with no migration, and the pull request lists the change among its user-visible changes ([`AGENTS.md`](../AGENTS.md) §4).
6. Add the option to the direct command and to `build_selection`, and the argument to the tool arguments model; then regenerate the schemas and the stored outputs as in steps 4 and 5 of the workflow. A watchlist option is the `watchlist-options` site.

## Testing and quality expectations

Test the method's own meaning and boundaries: valid calculations, policy branches, time-boundary behavior, missing or incompatible evidence, and provenance. Deterministic tests should use fixtures or provider fakes rather than real external API or LLM calls. Test adapter outcome mapping and workspace persistence at their respective boundaries when those areas are touched.

Follow the repository's established static checks and pytest practices described in the [project instructions](../AGENTS.md).

### Where tests and fixtures live

| What | Where | Notes |
| :--- | :--- | :--- |
| A strategy's tests | `tests/analysis/<folder>/` | One folder per method, named for the method: `piotroski`, `momentum`, `fcf_earnings_growth` (package `fcf_growth`) and `graham_value` (both Graham packages) |
| Shared-metric tests | `tests/analysis/shared/` | Helpers `_issuer_inputs.py` and `_metric_input_rig.py` serve captured issuers to the assembly functions |
| Captured balance-sheet documents | `evaluation/fixtures/sec_edgar/instant_facts/` | One trimmed Company Facts and submissions document per issuer; a `SHA256SUMS` file lists the folder, and a test fails when a file and its sum differ |
| Captured annual documents | `evaluation/fixtures/sec_edgar/annual_facts/` | The same issuers' annual concepts; the same `SHA256SUMS` rule |
| Captured filing headers | `evaluation/fixtures/sec_edgar/filing_headers/` | The as-filed SIC code of an issuer's anchor filing (`<issuer>_fy<year>.hdr.sgml`); the same `SHA256SUMS` rule |
| Frozen foreign-private-issuer documents | `evaluation/fixtures/sec_edgar_fpi.py`, documents in `evaluation/fixtures/sec_edgar/step_2_5a_d0/` | Four fixed issuers (ASML, Nutrien, SAP, Novo Nordisk) for the Golden cases of the foreign-filer boundaries |

- **Which to use:** use the captured folders for a regression test of a shared metric or a strategy over real filings, and the frozen foreign-private-issuer documents when the case is the foreign-filer boundary itself (Form 20-F or 40-F, IFRS, the security unit).
- **Merging:** a test that needs both the balance-sheet and the annual concepts of an issuer has to merge the two documents. `fixture_statements_adapter(fixture_id, clock_at=...)` in `evaluation/fixtures/sec_edgar_statements.py` does it: it merges the two Company Facts documents and the filings of both, serves the issuer's filing header, and returns the real SEC adapter, so Golden cases and tests run its own year-end discovery and series resolution with no network access.
- **Point-in-time trimming:** a capture as of a past boundary keeps only the filings accepted by that boundary. Apple's keeps its fiscal 2024 report and the two before it, and its tests use the boundary 2024-11-15 ([input evidence](project/milestones/v0.2/step-3.5/STEP_3_5_3_INPUT_EVIDENCE.md#2-sources)).
## Background: how a strategy fits into the code

The sections below explain the code the workflow relies on. They describe the current extension points; the [Architecture](project/ARCHITECTURE.md) documents the boundaries and the rationale.

### What an analysis strategy is

An analysis strategy is a named, deterministic method that resolves the evidence it needs, applies explicit financial rules in Python, and returns a typed result. Strategies may have different inputs, policies, calculations, and result models while sharing application infrastructure.

The [user-facing strategy guides](user/strategies/README.md) explain the behavior and limitations of implemented strategies. This guide focuses on how they fit into the code.

### The current analyzer contract

[`BaseAnalyzer`](../investment_analysis_engine/analysis/base_analyzer.py) is one abstract generic class, `BaseAnalyzer[ResultT, *ConfigT]`. `ResultT` is the complete evidence type the strategy returns. `ConfigT` holds zero or one type; a class that gives more than one raises a `TypeError` naming it, and a configuration is never added to hold a single value. The argument order is `(ticker, context, config)` everywhere.

| Specialization | Method | Example |
| :--- | :--- | :--- |
| `BaseAnalyzer[XResult]`, no configuration; the form the generator writes | `run_analysis(self, ticker, context)` | `PiotroskiAnalyzer(BaseAnalyzer[PiotroskiResult])` |
| `BaseAnalyzer[XResult, XConfig]`, one typed configuration | `run_analysis(self, ticker, context, config)` | `FCFEarningsGrowthAnalyzer(BaseAnalyzer[FCFEarningsGrowthResult, FCFEarningsGrowthConfig])` |

The configuration may be a Pydantic model, a frozen dataclass or another typed shape. `analyzer_result_type` and `analyzer_config_type` in the same module read the types a class declares, and the second returns `None` for the form with no configuration. The base contract does not implement input resolution, provider access, presentation, or persistence.

Every analyzer inherits from `BaseAnalyzer` with its own result type; Momentum, Graham Number, Graham Growth and FCF & Earnings Growth also have a configuration type and Piotroski has none. The common interface does not make their calculation semantics or result models interchangeable. To move a strategy from the first form to the second, follow [When a strategy gains a selection parameter](#when-a-strategy-gains-a-selection-parameter).

`AnalysisContext` is the frozen per-run value object for cross-cutting execution concerns:

- `as_of` is the requested point-in-time boundary, or `None` when the caller did not request one. It is not replaced with a fabricated historical date.
- `executed_at` is the timezone-aware execution clock captured once by the caller for the analysis run.
- `effective_as_of` is a derived property: the requested `as_of` when present, otherwise `executed_at`. Analysis-layer data must respect this cutoff.
- `use_cache` is the run-wide permission governing cache reads and writes used by the analysis.
- `instrument_profile` carries the run's identity evidence. It is retained in results even when the calculation does not consult it.

For the full clock model — which instant each kind of check compares against, the decision-clock/event-clock distinction, `utc_now()`, and why frozen-clock skew is tolerated only for live runs — see ARCHITECTURE.md's [*Time and the analysis boundary*](project/ARCHITECTURE.md#5-time-and-the-analysis-boundary) rather than this guide; duplicating those rules here would let the two drift.

The workspace selections expose `to_analysis_context(executed_at, instrument_profile)` alongside method-specific config conversion. Direct execution adapters and orchestrator handlers construct this context at their execution boundary. See [`AnalysisSelection`](../investment_analysis_engine/workspace/strategy_types.py) and each strategy's `selection.py` under `investment_analysis_engine/strategies/` for its method-specific request model, and [`AnalysisRequest`](../investment_analysis_engine/workspace/requests.py) for the workspace request boundary. The [Architecture](project/ARCHITECTURE.md) documents broader boundaries and rationale.

### How a strategy runs

An invocation begins in CLI or orchestrator composition, which validates the method-specific selection and composes the provider, cache, resolver, and adapter dependencies. The adapter prepares the run's config and `AnalysisContext`, invokes the analyzer, and packages the native result with its profile and normalized execution outcome. A direct command presents that result. In the workspace flow, a capture callable returns a normalized capture to common `workspace.execute()`, which records envelope timing, encodes native evidence, constructs an `AnalysisRun`, and inserts it through the run repository.

The adapter connects a method to execution capture; it does not duplicate its financial rules. Common workspace execution owns the shared run envelope and persistence boundary; it does not calculate strategy metrics or reclassify the financial result.

#### Strategy integration architecture

The strategy supplies its own configuration (when it has one), inputs, calculations, and result; composition supplies the context and shared infrastructure. Persistence is conditional, not automatic: `maybe_save_run` (`investment_analysis_engine/cli_run_support.py`) is the one place that decides, from `--save-run`, whether a run reaches `workspace.execute()` at all. Every direct command calls it through `analyze_and_maybe_save`. A watchlist refresh reaches the same `execute()` through its own composition in `investment_analysis_engine/workspace/refresh.py` instead.

**What the contributor owns:** strategy policy/configuration where there is any, required input semantics, deterministic calculations, typed result, tests, user-facing presentation where needed, and its execution-adapter integration. **What is shared:** provider/cache contracts, provenance values, the shared metrics and input assembly of [Shared metrics and SEC inputs](#shared-metrics-and-sec-inputs), the `maybe_save_run`/refresh persistence decision, workspace execution, run persistence, and shared financial conventions. Reuse the shared boundaries instead of rebuilding them inside a strategy.

#### What happens during an FCF & Earnings Growth run

`analyze_and_maybe_save` (`investment_analysis_engine/cli_run_support.py`) runs `maybe_save_run`, marking the normalizer so that a failure after the analysis finished is reported as a failure while saving. `maybe_save_run` is a pure passthrough to the adapter when `--save-run` is not given — the default direct-command path never touches `workspace.execute()`, opens no database, and builds no durable profile cache. Only when `--save-run` is set does it open a database, build the capture closure, and call `execute()`. A watchlist refresh never goes through `maybe_save_run`; it reaches `workspace.execute()` through its own composition in `investment_analysis_engine/workspace/refresh.py`, following the same adapter/normalize contract.

The steps below follow one `fcf-growth` command. The shared table gives the order; steps 4 and 13 differ by whether `--save-run` is set, and the two short tables after it give those steps for each branch.

**Shared steps**

| Step | Who | Does what |
| --- | --- | --- |
| 1 | User | Invokes `fcf-growth`. |
| 2 | CLI composition | Reads `executed_at` once, resolves the ticker and the presentation mode with `resolve_command_target`, and composes the cache, the provider (`build_sec_production_provider`), and the `ProductionAnnualGrowthSeriesResolver`. |
| 3 | CLI composition | Calls `analyze_and_maybe_save` with `save_run`, `executed_at`, `request_factory`, `run_adapter`, and `normalize`; it calls `maybe_save_run`. |
| 4 | `maybe_save_run` | Reaches the adapter, `execute_fcf_growth(...)`: steps 4a, or 4b to 4d. |
| 5 | Adapter | Composes the instrument profile, through the profile cache when one was supplied. |
| 6 | Adapter | Constructs the `AnalysisContext` from `as_of`, `executed_at`, `use_cache`, and the profile. |
| 7 | Adapter | Calls `FCFEarningsGrowthAnalyzer.run_analysis(ticker, context, config)`. |
| 8 | Analyzer | Reads `effective_as_of`, `use_cache`, and the profile from the context and calls the resolver with `as_of` and `effective_as_of` separately. |
| 9 | Resolver | Looks up the resolved-input cache when it is enabled and, on a miss, reads each annual field through `InputResolver.resolve_annual_series` from the `FinancialFactsProvider`. |
| 10 | Resolver | Returns the resolved observations and their provenance trace to the analyzer. |
| 11 | Analyzer | Calculates the growth metrics and classification; when the FCF yield is requested, takes its market capitalization from `anchor_year_end_scope` and `resolve_market_cap_inputs` in `analysis/shared/metric_inputs.py`; returns a `FCFEarningsGrowthResult`. |
| 12 | Adapter | Returns an `FCFGrowthCapture` holding the result and the profile. The normalizer `from_fcf_growth_capture` passes the result's `execution_status` and the recorded provider failure to `ExecutionCapture`, which derives the outcome through `RunOutcome.from_status`. |
| 13 | `maybe_save_run` | Hands the capture back to the command: step 13a, or 13b to 13d. |
| 14 | CLI | Calls `render_execution` on the normalized capture, which takes the exit code from `exit_code_of` of its outcome (1 for unavailable and failed, 0 otherwise), runs the provider check once and only after a failure, and calls the strategy's renderer in the requested mode (concise, details, diagnostics, or JSON). It then calls `emit_output`, which writes the text and exits with that code. |

**Branch: `--save-run` not set (default)**

| Step | Who | Does what |
| --- | --- | --- |
| 4a | `maybe_save_run` | Calls the adapter directly with no profile cache. |
| 13a | `maybe_save_run` | Returns the `FCFGrowthCapture` unchanged. |

**Branch: `--save-run` set**

| Step | Who | Does what |
| --- | --- | --- |
| 4b | `maybe_save_run` | Builds the request with `request_factory`, opens the database, checks that it is ready, and builds the durable profile cache. |
| 4c | `maybe_save_run` | Calls `workspace.execute(request, capture)`. |
| 4d | `workspace.execute()` | Calls `capture()` once. `capture()` calls the adapter with the profile cache, then normalizes the adapter's capture with `from_fcf_growth_capture()` into an `ExecutionCapture`. |
| 13b | `workspace.execute()` | Inserts the `AnalysisRun` into the repository and returns it. |
| 13c | `maybe_save_run` | Writes the saved run id to stderr. |
| 13d | `maybe_save_run` | Returns the adapter's own `FCFGrowthCapture`, unchanged. |

`FCFEarningsGrowthAnalyzer` implements `BaseAnalyzer[FCFEarningsGrowthResult, FCFEarningsGrowthConfig]`; the steps above show the per-run interactions after composition. Presentation always renders the adapter's own capture — `--save-run` changes only whether that capture is also persisted, never what the user sees.

**For a new strategy's SEC inputs, start from `analysis/shared/metric_inputs.py`** ([Shared metrics and SEC inputs](#shared-metrics-and-sec-inputs)), not from FCF-Growth's `ProductionAnnualGrowthSeriesResolver`. That resolver exists for FCF-Growth's own annual growth series and its checks and selection; the FCF analyzer itself already takes its market capitalization from the shared entry (step 11). Piotroski, the form with no configuration, shows a strategy built wholly on the shared inputs.

The direct command and watchlist-refresh paths reuse the same method adapter, but the common persistence wrapper (`workspace.execute()`) is only involved when an Analysis Run is being recorded. A financially negative screen can still have a completed execution outcome; the strategy's classification and software run status answer different questions.

### Where financial data comes from

The strategy determines which financial capability its semantics require. FCF growth uses a `FinancialFactsProvider` through its production annual-series resolver, currently backed by SEC EDGAR for the required completed annual cash-flow and EPS facts; a strategy that needs other SEC evidence starts from the shared assembly functions in [Shared metrics and SEC inputs](#shared-metrics-and-sec-inputs). The resolution layer can use an optional cache and returns typed inputs with source, period, availability, retrieval, and transformation lineage. Historical prices, company financial facts, quotes, and macro observations are distinct capabilities; do not treat one as a substitute for another.

`use_cache` controls whether the resolver can use its configured resolved-input cache. Provider and cache composition belongs at the application boundary. Detailed financial definitions, conventions, and data limitations belong in [Financial Math & Data Conventions](user/FINANCE_MATH.md) and the relevant [strategy guide](user/strategies/FCF_GROWTH.md).

### How inputs and provenance are handled

An input resolver turns provider evidence into strategy-appropriate typed observations. For FCF growth, `ProductionAnnualGrowthSeriesResolver` selects compatible, contiguous annual evidence under the requested `as_of`, records a `ResolutionTrace`, and returns annual observations whose component values retain `ResolvedInput` provenance. The analyzer consumes the resolved assembly; it does not fetch from providers itself.

Keep missing, unavailable, and not-applicable evidence explicit. Preserve source and time metadata, transformations, cache/override state, and diagnostics at the boundary that resolves the value. Do not silently substitute zero or hide a provider limitation.

### Shared metrics and SEC inputs

Before writing a private resolver, check whether a shared function already supplies the input. The shared code is under [`investment_analysis_engine/analysis/shared/`](../investment_analysis_engine/analysis/shared/); a strategy calls it and does not rebuild it.

| Entry point | Home | Call it when | Instead of |
| :--- | :--- | :--- | :--- |
| Pure shared metrics | Modules of `analysis/shared/`: `cash_flow`, `enterprise_value` (`compute_total_debt`, `compute_long_term_debt`, `compute_enterprise_value`), `invested_capital`, `market_cap` (`compute_market_cap`), `operating_metrics` (`compute_gross_profit`, `compute_ebit`, `compute_ebitda`), `split_adjustment`, `applicability` and `ranking` | The strategy needs a metric another strategy may share | Writing the formula again |
| Assembly functions | [`analysis/shared/metric_inputs.py`](../investment_analysis_engine/analysis/shared/metric_inputs.py): `anchor_year_end_scope`, `resolve_market_cap_inputs`, `resolve_year_ends`, `resolve_balance_sheet_values` and `resolve_balance_sheet_values_at`, `resolve_annual_values` and `resolve_annual_values_at`, `resolve_share_count_series`, `resolve_industry_class` | The metric's inputs are needed at the anchor year-end or at several year-ends | A private resolver that fetches from the provider |
| Scope-bound source protocol | `AsFiledSicSource` in `metric_inputs.py` | The input is tied to the analysis scope, such as the industry class from the as-filed SIC code. The SEC adapter implements the protocol | Passing the resolver, which reaches the adapter only through the production provider |
| Adapter builder | `build_sec_edgar_adapter` in [`cli_composition.py`](../investment_analysis_engine/cli_composition.py) | Composition needs the SEC adapter itself. It checks the declared identity and applies the ticker overrides | Constructing `SecEdgarFinancialFactsAdapter` by hand |

- **Composition:** build the adapter once. `compose_piotroski` in `strategies/piotroski/cli.py` wraps it in a `ProductionFinancialFactsProvider` for the resolver and passes the same adapter as the analyzer's `AsFiledSicSource`, so the industry class and the inputs are read from the same analysis scope.
- **Failures:** the assembly functions never raise a provider failure. They return a `MetricInputsFailure` that carries the provider-failure record, and a strategy calls no metric after one. An input that is merely unavailable is returned as its reason, so the metric can report it.
- **A new optional provider capability is still forwarded by hand.** `ProductionFinancialFactsProvider` in `data/financial/production.py` has one method per optional capability, answers with its own typed result when the adapter lacks the capability, and checks the capability's protocol, so a new request type needs an edit there. A conformance test (`tests/data/test_production_capability_forwarding.py`) finds every runtime-checkable capability protocol that a production adapter implements and fails, naming the protocol and the adapter, when the production provider does not implement it too. Extending the instant series avoided a new capability for the share counts, and the adapter as `AsFiledSicSource` avoids it for the SIC code; that protocol is not runtime-checkable, so the test does not cover it.

### How calculations produce a typed result

Calculations are deterministic Python operations. The FCF strategy derives free cash flow and free cash flow per diluted share from admissible annual evidence, computes its growth metrics, and classifies the result using its explicit policy. `FCFEarningsGrowthResult` retains the metrics, classification, selected horizon, observations, warnings, instrument profile, and resolution diagnostics. Its financial `PASS`, `FAIL`, or `INDETERMINATE` classification is distinct from `CalculationStatus` and from the workspace's run outcome.

Do not make the LLM responsible for financial calculations. Avoid copying formulas into a contributor guide when the financial authority already documents them.

### How results become user-visible

Direct analysis commands send a native typed result to the strategy's presentation function. FCF uses `render_fcf_earnings_growth`, with concise, details, diagnostics, and JSON modes built around the strategy's own model. Shared formatting utilities in [`investment_analysis_engine/reporting/presentation.py`](../investment_analysis_engine/reporting/presentation.py) provide common vocabulary; they do not homogenize strategy result types. Saved-run views project from the persisted evidence rather than rerunning providers or calculations.

Provide presentation behavior that makes the result, limitations, and relevant provenance understandable. Keep presentation-only wording out of financial calculations.

### Execution capture and durable persistence

The FCF-specific `execute_fcf_growth` adapter composes the profile and `AnalysisContext`, and invokes the analyzer. It returns an `FCFGrowthCapture` with the native result and profile; the caller normalizes that capture to the common `ExecutionCapture`, which takes the result's `execution_status` and derives the `RunOutcome` through `RunOutcome.from_status`, the one rule every strategy shares. The common [`workspace.execute()`](../investment_analysis_engine/workspace/execution.py) invokes a capture callable, records its own `started_at` and `completed_at` envelope timestamps, encodes the native evidence, assembles the common run record, and inserts it into the provided repository. These persistence-envelope timestamps are separate from the analysis context's `executed_at`. [`AnalysisRun`](../investment_analysis_engine/workspace/runs.py) is the durable domain record for the request/configuration snapshot, timing, versions, status, result evidence, presentation inputs, and profile.

The adapter is strategy-specific integration work. The workspace execution service is shared infrastructure and must not become a second implementation of a strategy's semantics. Do not assume every adapter has the same signature or that `BaseAnalyzer` is a unified execution interface.

The helpers that the 3.5.3 repetition review extracted are functions, not a base class or mixin ([review](project/milestones/v0.2/step-3.5/STEP_3_5_3_SLICE_PLAN.md#b4-repetition-review-353e1)). Use them in a strategy's files:

| Helper | Home | What it does |
| :--- | :--- | :--- |
| `snapshot_by_revalidation` | `analysis/run_models.py` | Codec: dumps the evidence model to JSON, decodes the dump and returns it |
| `validate_wire` | `analysis/run_models.py` | Codec: strict JSON validation of the wire object, refusing a non-finite number |
| `decode_with_native_identifiers` | `analysis/run_models.py` | Codec: checks the identifiers and versions of a stored result against the declared ones, then validates (FCF-Growth, Piotroski) |
| `decode_with_method_sections` | `analysis/run_models.py` | Codec: checks each method section of a stored analysis carries the declared method, then validates (the Graham strategies) |
| `resolve_command_target` | `cli_support.py` | Command: resolves the ticker and the presentation mode and records each on the failure scope |
| `render_execution` | `cli_support.py` | Command: exit code of the outcome, the provider check once and only after a failure, the strategy's render |
| `emit_output` | `cli_support.py` | Command: writes the output (standard error for a failure in the concise and details modes) and exits with the code |
| `AS_OF_OPTION`, `SAVE_RUN_OPTION`, `NO_PROVIDER_CHECK_OPTION` | `cli_support.py` | Command: the three option declarations that read the same in every command |
| `analyze_and_maybe_save` | `cli_run_support.py` | Command: the save stage and `maybe_save_run`, with the normalizer marked |
| `tool_context` | `strategies/_shared/tool.py` | Tool handler: validates the clock, resolves the profile once, builds the `AnalysisContext` |
| `run_analyzer_with_profile` | `strategies/_shared/invocation.py` | Execution: composes the profile, builds the context and runs the analyzer (the Graham strategies) |
| `compose_production_profile` | `strategies/_shared/profile.py` | Execution: the instrument profile composition |

The `use_cache` field is declared once, in `AnalysisToolArguments` (`orchestrator/analysis_tool_arguments.py`), which every tool arguments model subclasses. `from_<name>_capture`, the evidence validators, `build_selection` and `refresh` stay in each strategy: each reads, builds or composes something different.

### Strategy-specific responsibilities and shared infrastructure

| Strategy-specific work | Shared infrastructure to reuse |
| --- | --- |
| Configuration or policy and its semantic rules, when the strategy has any | `BaseAnalyzer[ResultT, *ConfigT]`, `AnalysisContext`, workspace request selections |
| Strategy analyzer and typed result | `ResolvedInput`, `ResolutionTrace`, provider contracts |
| Input requirements and calculations; a resolver of its own only for evidence no shared entry supplies | The shared metrics and input assembly of `analysis/shared/` ([Shared metrics and SEC inputs](#shared-metrics-and-sec-inputs)), financial-fact providers, historical-price providers, and caches where applicable |
| Focused tests for rules, unavailable evidence, and edge cases | Common `workspace.execute()`, `AnalysisRun`, repositories, and evidence codecs |
| Investor-facing rendering and strategy guide | Shared presentation vocabulary and financial conventions |
| Strategy-specific execution adapter integration | CLI/workspace composition and persistence boundaries |

This is a responsibility map. A strategy's analyzer, codec, execution adapter and presenter live in `investment_analysis_engine/strategies/<strategy>/`, in files named for their role. Keep method semantics in the strategy layer, provider composition at application boundaries, and common execution capture/persistence in the workspace layer.

### Existing strategy reference: FCF & Earnings Growth and Piotroski

FCF growth is a useful end-to-end example of the configured form because its resolver, calculation, presentation, adapter, and workspace capture are separately visible. Piotroski is the example of the config-free form with shared SEC inputs. Current names and locations, under `investment_analysis_engine/strategies/`:

| Generic concept | FCF & Earnings Growth (configured form) | Piotroski (config-free form, shared SEC inputs) |
| --- | --- | --- |
| Strategy configuration | `FCFEarningsGrowthConfig` in [`models.py`](../investment_analysis_engine/strategies/fcf_growth/models.py), built from `FCFGrowthSelection.to_fcf_config()` in [`selection.py`](../investment_analysis_engine/strategies/fcf_growth/selection.py) | None; `PiotroskiSelection` in [`selection.py`](../investment_analysis_engine/strategies/piotroski/selection.py) holds `as_of` and `use_cache` only |
| Strategy policy | `FCFEarningsGrowthPolicy` in [`models.py`](../investment_analysis_engine/strategies/fcf_growth/models.py), held by the config | The nine tests, fixed in code in [`calculation.py`](../investment_analysis_engine/strategies/piotroski/calculation.py) |
| Strategy analyzer | `FCFEarningsGrowthAnalyzer(BaseAnalyzer[FCFEarningsGrowthResult, FCFEarningsGrowthConfig])` in [`analyzer.py`](../investment_analysis_engine/strategies/fcf_growth/analyzer.py) | `PiotroskiAnalyzer(BaseAnalyzer[PiotroskiResult])` in [`analyzer.py`](../investment_analysis_engine/strategies/piotroski/analyzer.py) |
| Strategy result | `FCFEarningsGrowthResult` in [`models.py`](../investment_analysis_engine/strategies/fcf_growth/models.py) | `PiotroskiResult` in [`analyzer.py`](../investment_analysis_engine/strategies/piotroski/analyzer.py) |
| Input resolution | `ProductionAnnualGrowthSeriesResolver` in [`input_resolver.py`](../investment_analysis_engine/strategies/fcf_growth/input_resolver.py) for the annual series, and the shared `anchor_year_end_scope` and `resolve_market_cap_inputs` for the market capitalization | The shared assembly functions of [`metric_inputs.py`](../investment_analysis_engine/analysis/shared/metric_inputs.py) over an `InputResolver`, with the SEC adapter as the `AsFiledSicSource`; no resolver of its own |
| Execution adapter | `execute_fcf_growth` and `FCFGrowthCapture` in [`execution.py`](../investment_analysis_engine/strategies/fcf_growth/execution.py) | `execute_piotroski` and `PiotroskiCapture` in [`execution.py`](../investment_analysis_engine/strategies/piotroski/execution.py) |
| Common execution context | `AnalysisContext` from [`base_analyzer.py`](../investment_analysis_engine/analysis/base_analyzer.py), constructed by the adapter from the run boundary, cache choice, and profile | The same, built by `PiotroskiSelection.to_analysis_context` |
| Common request boundary | `AnalysisRequest` in [`requests.py`](../investment_analysis_engine/workspace/requests.py); `FCFGrowthSelection` and `to_fcf_config()` | `AnalysisRequest`; `PiotroskiSelection` |
| Common execution and persistence | [`workspace.execute()`](../investment_analysis_engine/workspace/execution.py), [`AnalysisRun`](../investment_analysis_engine/workspace/runs.py), and the Analysis Run repository | The same |
| Strategy presentation | `render_fcf_earnings_growth` in [`presenter.py`](../investment_analysis_engine/strategies/fcf_growth/presenter.py) | `render_piotroski` in [`presenter.py`](../investment_analysis_engine/strategies/piotroski/presenter.py) |

The policy remains strategy-owned. `FCFGrowthSelection` is the validated, persisted/request-facing snapshot and converts to the analyzer's `FCFEarningsGrowthConfig`; the adapter supplies the separate common `AnalysisContext`. Piotroski's selection converts to no configuration, only to the context. See the [FCF & Earnings Growth user guide](user/strategies/FCF_GROWTH.md) and the [Piotroski F-Score user guide](user/strategies/PIOTROSKI.md) for method semantics and limitations.

### Ready to add a strategy?

Start from the strategy's financial question and required evidence. Read the relevant financial conventions, identify the narrow provider and provenance needs, define strategy-owned policy and result semantics, then integrate through the existing composition and execution boundaries. Use the FCF example to trace those responsibilities in code for the configured form and the Piotroski example for the form with no configuration.

## Changing what every strategy provides

This section is for a change to the strategy contract itself: a new member of the behavior bundle, a new edit site or a new required name in a strategy's file. A single strategy never makes such a change. Take the rows that apply, then run the [status command](#2-check-the-status-command) and the generator's end-to-end test.

| File | What changes |
| :--- | :--- |
| `investment_analysis_engine/strategy_wiring.py` | The `StrategyBehavior` member and its exact-type accessor, the accessor of `BehaviorView`, a `..._by_key` function with its `..._BY_KEY` constant when generic code reads the member by key (as `headlines_by_key` does), and the member in each production behavior declaration |
| The generic code that reads the member (for example `cli_workspace.py` for `headline_for`) | It calls the view's accessor, never a strategy's module |
| `scripts/strategy_conformance.py` | The closed sets `BEHAVIOR_MEMBERS` and `VIEW_ACCESSORS` (and `EVAL_COMPOSITION_MEMBERS` or `CLI_COMPOSITION_MEMBERS` for a tier's member), the exact-type probes of the behavior check, and the file site's check for a new required name. A member that replays a stored run also changes `StoredRun` (its replay functions) and check T8, which replays every stored run through each projection |
| `scripts/strategy_sites.toml` | The owning site's `title`, `why`, `defines` and `fails` for a new required name, or a new `[[site]]` for a new edit site |
| This guide's edit-site table | Regenerate it with `uv run python -m scripts.generate_strategy_docs` after the sites file changes; it is not edited by hand |
| `tests/scripts/test_strategy_sites.py` | The pinned list of site ids, for a new edit site |
| `scripts/strategy_status.py` and `tests/scripts/test_strategy_status.py` | The status command reads the sites file, so a new site needs no edit there; change it only when a site must report its state another way, and update the test that pins its output |
| `scripts/new_strategy.py` | The generated behavior declaration and its import in the composition-root edit; `STUB_ROLES` or `EDITS` for a new file or a new edit of an existing file |
| `scripts/strategy_templates/*.py.tmpl` | The generated file or function for the new name, calling `unfilled_stub` where the body is strategy-specific |
| `tests/scripts/test_new_strategy.py` | The map of stubbed functions per template and the tests parametrized over the template files |
| `tests/scripts/generator_fills/*.py.fill` and `tests/scripts/test_new_strategy_end_to_end.py` | A `#: body` section in the fill for each new stub; a new fill and `STUB_FILL_ROLES` for a new file; `patches.toml` only for an edit of an existing file |
| `tests/specimen/` | `behavior.py` (the specimen implements the erased view by hand), the specimen file that defines the member's function (for example `replay.py` or `codec.py`), `wiring.py` for the descriptor, and, for a member that replays a stored run, `runs.py` (the specimen's own replay functions) and `site_context.py` (its `StoredRun` entry) |
| The generic replay: `investment_analysis_engine/workspace_documents/run_replay.py` and `investment_analysis_engine/reporting/replay_inputs.py` | A member that replays a stored run adds its projector type to `replay_inputs.py` and its path to `run_replay.py`, which stays strategy-free |
| Tests of the replay contract: `tests/workspace_documents/test_analysis_run_replay.py`, `tests/workspace_documents/test_run_replay_documents.py`, `tests/test_specimen_strategy.py`, and any test that calls `project_run`, `project_run_document` or a strategy's projector directly (search for those names) | They call the replay functions directly, so a change to a projection's signature or to the modes it accepts changes them. A test of an `ian` command and its output does not, and must pass unedited |

- A fill holds only bodies, so a template's signature has one copy; a new parameter that a body does not use still needs a `del` in the body.
- The conformance checks T15 and T16 and the generator's end-to-end test fail one file at a time. The list above is the whole set; work through it before running them.
- A file this list lacks belongs in the list. Add the row in the same change.

## Deeper references

- [Architecture](project/ARCHITECTURE.md) — system boundaries and rationale.
- [Financial Math & Data Conventions](user/FINANCE_MATH.md) — shared financial semantics.
- [Glossary](user/GLOSSARY.md) — project and finance terminology.
- [Analysis Strategy Guides](user/strategies/README.md) — investor-facing strategy behavior.
