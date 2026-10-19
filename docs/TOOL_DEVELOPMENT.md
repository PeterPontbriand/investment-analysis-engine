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

```bash
uv run python -m scripts.new_strategy <module_name> --label "<Label>" [--alias <alias>]
```

- `<module_name>` is the snake-case package name. It gives the analysis identifier, the method identifier and the tool name. The alias defaults to the hyphenated module name.
- It writes typed stubs for the role files into `investment_analysis_engine/strategies/<module_name>/`: `vocabulary`, `analyzer`, `tool`, `selection`, `codec`, `execution`, `cli`, `presenter`, `envelope`, `replay` and `evaluation`.
- It makes one insertion in each of five existing files: `strategy_wiring.py`, `orchestrator/tool_names.py`, `workspace/strategy_types.py`, `cli_strategy_wiring.py` and `evaluation/strategy_fixtures.py`.
- It refuses to overwrite. If a target file exists, or the module name, alias, tool or method identifier is already used, it writes nothing and exits with code 2, listing the conflicts.
- Every unfilled body calls `unfilled_stub(...)`. The generated files type-check as written, and the test suite fails while any such call remains under `investment_analysis_engine/`.
- The generated descriptor has `settings_type=None`; see [Strategy settings](#strategy-settings).

### 2. Check the status command

```bash
uv run python -m scripts.strategy_status <module_name> [--alias <alias>]
```

- It prints `done` or `missing` for each site in the [edit-site table](#edit-sites-of-a-strategy), in table order, and a diagnostic under each missing one. It exits with code 1 while any site is missing.
- It runs the same check functions as the conformance tests, so the two cannot disagree.
- It does not run the type checker; the gate does.
- `done` means the site exists, has the required names and calls no `unfilled_stub`. A new-file site whose file still calls `unfilled_stub` is `missing`, and its diagnostic names the file and the line of each call.
- Right after the generator, expect `missing` on every site whose file has an unfilled body (`analyzer`, `tool`, `codec`, `execution`, `cli`, `presenter`, `replay` and `evaluation`), on the reviewed sites you have not yet written, and on `schema` and `strategy-docs` until step 5. `codec`, `presenter` and `replay` run the strategy's stored run, which needs the `evaluation` file's sample selection; until that is written their diagnostic ends `not checked: depends on unfilled evaluation (<file>:<line>)`. Fill the site it names first.
- If a strategy file was deleted or emptied, or a wiring entry removed, the package cannot be imported and no other site can be checked. The command matches the failing module or file against the site files and prints one `missing <site-id>` line with the file to change, and the original Python error on the next line; restore or write that site, and run the command again. An error that matches no site is printed as `missing  import` with the Python error.

### 3. Fill the stubs

- Start from the financial question and the evidence it needs. Fill `vocabulary`, the models, `analyzer` and the resolver first, then the files that package the result: `selection`, `codec`, `execution`, `presenter`, `envelope`, `replay`, `tool`, `cli` and `evaluation`.
- The status command lists every `unfilled_stub` call that remains in a site's file, with file and line, and `uv run python -m pytest tests/test_no_unfilled_stubs.py` lists them all. The strict type check is `uv run mypy --strict investment_analysis_engine tests scripts`.
- Financial math is deterministic Python. The authority for formula semantics is [Financial Math & Data Conventions](user/FINANCE_MATH.md); add the strategy's definitions there and in the [Glossary](user/GLOSSARY.md).
- Keep missing, unavailable and not-applicable evidence explicit (`MetricResult`, reason codes, retained provenance). Never substitute zero.
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
| `help-snapshot` | The strategy's command row in the stored application help | `uv run python -m tests._cli_help_output` |
| `guide` | The investor-facing guide under `docs/user/strategies/`, with Finance Math and Glossary links | none; written by hand |
| `watchlist-options` | Options of its own on the watchlist commands, only if it has any beyond the shared ones | none; written by hand |

What a Golden case, a fixture and a catalog entry must contain, and how their expected values are established, is in [Evaluations & Golden Suite](EVALUATIONS.md#5-golden-cases-and-fixtures) and its [maintenance rules](EVALUATIONS.md#10-maintenance-rules). For the shape of a `cases` module, a catalog entry, a guide or a settings file, open the file named in the edit-site table for an existing strategy (replace `{module}` with its package name); take the structure, not its rules.

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
| `analyzer` | Analyzer modules: config, result, analyzer. The analyzer defines the strategy's result type, which the descriptor must agree with. | `investment_analysis_engine/strategies/{module}/analyzer.py` | new_file | yes | `site_analyzer`: the file is missing, or defines no `.+Analyzer`; analyzer X (result Y) has no descriptor |
| `settings` | Settings: the shipped settings file beside the model, only when the strategy has user-tunable defaults. A strategy's tunable defaults live in a settings.toml beside the model that validates them, and the descriptor names the model; a strategy with none has no settings.py and nothing to add. | `investment_analysis_engine/strategies/{module}/settings.toml` | reviewed | no | `site_settings`: the package has a settings.py but no settings.toml beside it, or the descriptor's settings_type is not the model that file defines |
| `descriptor` | Descriptor constant, StrategyBehavior declaration and STRATEGIES entry. The closed tuple of descriptors is what every generic consumer iterates. | `investment_analysis_engine/strategy_wiring.py` | edit | yes | `site_descriptor`: no descriptor in STRATEGIES carries the strategy's alias or package |
| `tool-name` | ToolName member. The tool enumeration is a type-level list that mypy needs and no descriptor can generate. | `investment_analysis_engine/orchestrator/tool_names.py` | edit | yes | `site_tool_name`: ToolName member X has no descriptor |
| `tool` | Arguments model, dependency class, handler. The model-facing tool surface of the strategy. | `investment_analysis_engine/strategies/{module}/tool.py` | new_file | yes | `site_tool`: the file is missing, or defines no `.+ToolArguments`, `.+ToolDependencies`, `.+ToolHandler`; tool-argument model X has no descriptor |
| `unions` | NativeEvidence and SelectionMember entries. Both unions are type-level lists that the descriptor's bounds are checked against. | `investment_analysis_engine/workspace/strategy_types.py` | edit | yes | `site_unions`: the descriptor's selection class or result type is not in the union |
| `selection` | Selection class. The stored, typed choice of this strategy's parameters. | `investment_analysis_engine/strategies/{module}/selection.py` | new_file | yes | `site_selection`: the file is missing, or defines no `.+Selection`; descriptor X has no selection member |
| `codec` | Codec and native-status function. A stored run is encoded and decoded by the strategy's own functions. | `investment_analysis_engine/strategies/{module}/codec.py` | new_file | yes | `site_codec`: the file is missing, or defines no `encode_.+`, `decode_.+`, `.+_native_status`, `.+_ticker`; the stored run does not decode to the result execute stored |
| `execution` | Execution adapter, capture type, normalizer. The adapter turns an analyzer outcome into a stored run. | `investment_analysis_engine/strategies/{module}/execution.py` | new_file | yes | `site_execution`: the file is missing, or defines no `.+Capture`, `from_.+_capture` |
| `cli` | CLI file: direct command, selection builder, refresh executor. The strategy's command-line behavior lives in its own package. | `investment_analysis_engine/strategies/{module}/cli.py` | new_file | yes | `site_cli`: the file is missing, or defines no `build_selection`, `refresh`, `command` |
| `cli-tier` | CLI-tier entry. A lower layer cannot import the command file, so the tier pairs it with the descriptor's behavior. | `investment_analysis_engine/cli_strategy_wiring.py` | edit | yes | `site_cli_tier`: strategy X is not wired in: CLI tier |
| `presenter` | Presenter and JSON builder. The strategy renders its own result in every presentation mode. | `investment_analysis_engine/strategies/{module}/presenter.py` | new_file | yes | `site_presenter`: the file is missing, or defines no `render_.+`; the replayed JSON does not validate as X |
| `envelope` | Envelope model and document version. Every --json document is a typed model with a published schema. | `investment_analysis_engine/strategies/{module}/envelope.py` | new_file | yes | `site_envelope`: the file is missing, or defines no `DOCUMENT_SCHEMA_VERSION`; command X offers --json but has no typed document model |
| `replay` | Replay projector and headline function. A stored run is replayed through the strategy's own projector. | `investment_analysis_engine/strategies/{module}/replay.py` | new_file | yes | `site_replay`: the file is missing, or defines no `project_.+`; replay in X mode raised or is empty |
| `evaluation` | Evaluation file: fixture composition, requirement, the fixture ids it understands and a sample selection. The evaluation tier composes the strategy's fixtures from this file. | `investment_analysis_engine/strategies/{module}/evaluation.py` | new_file | yes | `site_evaluation`: the file is missing, or defines no `FIXTURE_IDS`, `REQUIREMENT`, `SAMPLE_SELECTION`, `compose`; strategy X requires fixture ids that its evaluation tier entry and the context do not declare |
| `evaluation-tier` | Evaluation-tier entry. The tier pairs the strategy's bundle with its requirement, ids, sample selection and composition. | `investment_analysis_engine/evaluation/strategy_fixtures.py` | edit | yes | `site_evaluation_tier`: strategy X is not wired in: evaluation tier |
| `cases` | Fixtures with their fixture ids, and cases with their reviewed arguments table. Reviewed case truth is written by hand against tool names; the fixtures live in the evaluation fixtures package. | `investment_analysis_engine/evaluation/cases/{module}.py` | new_file | no | `site_cases`: the file is missing, or defines no `{module_upper}_ARGUMENTS`, `{module_upper}_CASES`; tool X is required by no golden case |
| `catalog` | Catalog: the case-module import, the case tuple entries and the suite version bump; the pinned id list in the catalog test. The case tuple, the suite version and the pinned ids are reviewed evaluation truth; the check cannot tell whether the suite version was bumped. | `investment_analysis_engine/evaluation/catalog.py` | reviewed | no | `site_catalog`: the catalog does not import the case module, or a case id is not pinned in the catalog test |
| `direct-output` | Direct command expected output: the command's fixed arguments and its stored text and JSON output. The direct command's text and JSON output are compared byte for byte with reviewed files, and the failure-message and save-run tests run the command from its fixed arguments. | `tests/expected_output/direct_commands/{alias}.txt` | reviewed | no | `site_direct_output`: tests/_direct_command_output.py has no entry for the alias in _COMMANDS, or the stored .txt or .json output does not exist |
| `strategy-documents` | Stored strategy document: the success case and its stored direct and replayed documents. The typed document is compared byte for byte with a reviewed file, direct and replayed, and the provider-check and envelope-version tests start from the strategy's cases. | `tests/expected_output/strategy_documents/{alias}-success.direct.json` | reviewed | no | `site_strategy_documents`: tests/_strategy_document_output.py has no case named <alias>-success, or the stored .direct.json or .replay.json document does not exist |
| `help-snapshot` | Application help snapshot: the strategy's command row. The application's help is compared byte for byte with a reviewed snapshot that lists every command in the order it is added. | `tests/expected_output/cli_help/application.txt` | reviewed | no | `site_help_snapshot`: the snapshot has no command row for the alias |
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

## Testing and quality expectations

Test the method's own meaning and boundaries: valid calculations, policy branches, time-boundary behavior, missing or incompatible evidence, and provenance. Deterministic tests should use fixtures or provider fakes rather than real external API or LLM calls. Test adapter outcome mapping and workspace persistence at their respective boundaries when those areas are touched.

Follow the repository's established static checks and pytest practices described in the [project instructions](../AGENTS.md).

## Background: how a strategy fits into the code

The sections below explain the code the workflow relies on. They describe the current extension points; the [Architecture](project/ARCHITECTURE.md) documents the boundaries and the rationale.

### What an analysis strategy is

An analysis strategy is a named, deterministic method that resolves the evidence it needs, applies explicit financial rules in Python, and returns a typed result. Strategies may have different inputs, policies, calculations, and result models while sharing application infrastructure.

The [user-facing strategy guides](user/strategies/README.md) explain the behavior and limitations of implemented strategies. This guide focuses on how they fit into the code.

### The current analyzer contract

[`BaseAnalyzer`](../investment_analysis_engine/analysis/base_analyzer.py) is an abstract generic contract, `BaseAnalyzer[ConfigT, ResultT]`. Its `run_analysis(ticker, config, context)` method accepts a strategy-owned configuration and the shared `AnalysisContext`, and returns that strategy's typed result. The type variables are intentionally unconstrained: configuration may be a Pydantic model, frozen dataclass, or another typed shape. The base contract does not implement input resolution, provider access, presentation, or persistence.

All current strategy analyzers inherit from `BaseAnalyzer` with their own configuration and result types. The common interface does not make their calculation semantics or result models interchangeable.

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

The strategy supplies its own config, resolver, calculations, and result; composition supplies the context and shared infrastructure. Persistence is conditional, not automatic: `maybe_save_run` (`investment_analysis_engine/cli_run_support.py`) is the one place shared by all four direct commands that decides whether a run reaches `workspace.execute()` at all, based on `--save-run`; a watchlist refresh reaches the same `execute()` through its own composition in `investment_analysis_engine/workspace/refresh.py` instead.

**What the contributor owns:** strategy policy/configuration, required input semantics and resolution, deterministic calculations, typed result, tests, user-facing presentation where needed, and its execution-adapter integration. **What is shared:** provider/cache contracts, provenance values, the `maybe_save_run`/refresh persistence decision, workspace execution, run persistence, and shared financial conventions. Reuse the shared boundaries instead of rebuilding them inside a strategy.

#### What happens during an FCF & Earnings Growth run

`maybe_save_run` (`investment_analysis_engine/cli_run_support.py`) is a pure passthrough to the adapter when `--save-run` is not given — the default direct-command path never touches `workspace.execute()`, opens no database, and builds no durable profile cache. Only when `--save-run` is set does it open a database, build the capture closure, and call `execute()`. A watchlist refresh never goes through `maybe_save_run`; it reaches `workspace.execute()` through its own composition in `investment_analysis_engine/workspace/refresh.py`, following the same adapter/normalize contract.

The steps below follow one `fcf-growth` command. The shared table gives the order; steps 4 and 13 differ by whether `--save-run` is set, and the two short tables after it give those steps for each branch.

**Shared steps**

| Step | Who | Does what |
| --- | --- | --- |
| 1 | User | Invokes `fcf-growth`. |
| 2 | CLI composition | Validates the selection, reads `executed_at` once, and composes the cache, the provider, and the `ProductionAnnualGrowthSeriesResolver`. |
| 3 | CLI composition | Calls `maybe_save_run` with `save_run`, `executed_at`, `request_factory`, `run_adapter`, and `normalize`. |
| 4 | `maybe_save_run` | Reaches the adapter, `execute_fcf_growth(...)`: steps 4a, or 4b to 4d. |
| 5 | Adapter | Composes the instrument profile, through the profile cache when one was supplied. |
| 6 | Adapter | Constructs the `AnalysisContext` from `as_of`, `executed_at`, `use_cache`, and the profile. |
| 7 | Adapter | Calls `FCFEarningsGrowthAnalyzer.run_analysis(ticker, config, context)`. |
| 8 | Analyzer | Reads `effective_as_of`, `use_cache`, and the profile from the context and calls the resolver with `as_of` and `effective_as_of` separately. |
| 9 | Resolver | Looks up the resolved-input cache when it is enabled and, on a miss, fetches the annual facts from the `FinancialFactsProvider`. |
| 10 | Resolver | Returns the resolved observations and their provenance trace to the analyzer. |
| 11 | Analyzer | Calculates the growth metrics and classification and returns a `FCFEarningsGrowthResult`. |
| 12 | Adapter | Returns an `FCFGrowthCapture` holding the result, the profile, and the mapped outcome. |
| 13 | `maybe_save_run` | Hands the capture back to the command: step 13a, or 13b to 13d. |
| 14 | CLI | Renders the capture's result in the requested mode (concise, details, diagnostics, or JSON) and exits non-zero unless the execution status is `OK` or `NOT_APPLICABLE`. |

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

`FCFEarningsGrowthAnalyzer` implements `BaseAnalyzer[FCFEarningsGrowthConfig, FCFEarningsGrowthResult]`; the steps above show the per-run interactions after composition. Presentation always renders the adapter's own capture — `--save-run` changes only whether that capture is also persisted, never what the user sees.

The direct command and watchlist-refresh paths reuse the same method adapter, but the common persistence wrapper (`workspace.execute()`) is only involved when an Analysis Run is being recorded. A financially negative screen can still have a completed execution outcome; the strategy's classification and software run status answer different questions.

### Where financial data comes from

The strategy determines which financial capability its semantics require. FCF growth uses a `FinancialFactsProvider` through its production annual-series resolver, currently backed by SEC EDGAR for the required completed annual cash-flow and EPS facts. The resolution layer can use an optional cache and returns typed inputs with source, period, availability, retrieval, and transformation lineage. Historical prices, company financial facts, quotes, and macro observations are distinct capabilities; do not treat one as a substitute for another.

`use_cache` controls whether the resolver can use its configured resolved-input cache. Provider and cache composition belongs at the application boundary. Detailed financial definitions, conventions, and data limitations belong in [Financial Math & Data Conventions](user/FINANCE_MATH.md) and the relevant [strategy guide](user/strategies/FCF_GROWTH.md).

### How inputs and provenance are handled

An input resolver turns provider evidence into strategy-appropriate typed observations. For FCF growth, `ProductionAnnualGrowthSeriesResolver` selects compatible, contiguous annual evidence under the requested `as_of`, records a `ResolutionTrace`, and returns annual observations whose component values retain `ResolvedInput` provenance. The analyzer consumes the resolved assembly; it does not fetch from providers itself.

Keep missing, unavailable, and not-applicable evidence explicit. Preserve source and time metadata, transformations, cache/override state, and diagnostics at the boundary that resolves the value. Do not silently substitute zero or hide a provider limitation.

### How calculations produce a typed result

Calculations are deterministic Python operations. The FCF strategy derives free cash flow and free cash flow per diluted share from admissible annual evidence, computes its growth metrics, and classifies the result using its explicit policy. `FCFEarningsGrowthResult` retains the metrics, classification, selected horizon, observations, warnings, instrument profile, and resolution diagnostics. Its financial `PASS`, `FAIL`, or `INDETERMINATE` classification is distinct from `CalculationStatus` and from the workspace's run outcome.

Do not make the LLM responsible for financial calculations. Avoid copying formulas into a contributor guide when the financial authority already documents them.

### How results become user-visible

Direct analysis commands send a native typed result to the strategy's presentation function. FCF uses `render_fcf_earnings_growth`, with concise, details, diagnostics, and JSON modes built around the strategy's own model. Shared formatting utilities in [`investment_analysis_engine/reporting/presentation.py`](../investment_analysis_engine/reporting/presentation.py) provide common vocabulary; they do not homogenize strategy result types. Saved-run views project from the persisted evidence rather than rerunning providers or calculations.

Provide presentation behavior that makes the result, limitations, and relevant provenance understandable. Keep presentation-only wording out of financial calculations.

### Execution capture and durable persistence

The FCF-specific `execute_fcf_growth` adapter composes the profile and `AnalysisContext`, invokes the analyzer, and maps the analyzer's execution status into a `RunOutcome`. It returns an `FCFGrowthCapture` with the native result and profile; the caller normalizes that capture to the common `ExecutionCapture`. The common [`workspace.execute()`](../investment_analysis_engine/workspace/execution.py) invokes a capture callable, records its own `started_at` and `completed_at` envelope timestamps, encodes the native evidence, assembles the common run record, and inserts it into the provided repository. These persistence-envelope timestamps are separate from the analysis context's `executed_at`. [`AnalysisRun`](../investment_analysis_engine/workspace/runs.py) is the durable domain record for the request/configuration snapshot, timing, versions, status, result evidence, presentation inputs, and profile.

The adapter is strategy-specific integration work. The workspace execution service is shared infrastructure and must not become a second implementation of a strategy's semantics. Do not assume every adapter has the same signature or that `BaseAnalyzer` is a unified execution interface.

### Strategy-specific responsibilities and shared infrastructure

| Strategy-specific work | Shared infrastructure to reuse |
| --- | --- |
| Configuration or policy and its semantic rules | `BaseAnalyzer[ConfigT, ResultT]`, `AnalysisContext`, workspace request selections |
| Strategy analyzer and typed result | `ResolvedInput`, `ResolutionTrace`, provider contracts |
| Input requirements and strategy-owned resolver/calculations | Financial-fact providers, historical-price providers, and caches where applicable |
| Focused tests for rules, unavailable evidence, and edge cases | Common `workspace.execute()`, `AnalysisRun`, repositories, and evidence codecs |
| Investor-facing rendering and strategy guide | Shared presentation vocabulary and financial conventions |
| Strategy-specific execution adapter integration | CLI/workspace composition and persistence boundaries |

This is a responsibility map. A strategy's analyzer, codec, execution adapter and presenter live in `investment_analysis_engine/strategies/<strategy>/`, in files named for their role. Keep method semantics in the strategy layer, provider composition at application boundaries, and common execution capture/persistence in the workspace layer.

### Existing strategy reference: FCF & Earnings Growth

FCF growth is a useful end-to-end example because its resolver, calculation, presentation, adapter, and workspace capture are separately visible. Current names and locations:

| Generic concept | FCF & Earnings Growth implementation |
| --- | --- |
| Strategy configuration | `FCFEarningsGrowthConfig` in [`models.py`](../investment_analysis_engine/strategies/fcf_growth/models.py), built from `FCFGrowthSelection.to_fcf_config()` in [`selection.py`](../investment_analysis_engine/strategies/fcf_growth/selection.py) |
| Strategy policy | `FCFEarningsGrowthPolicy` in [`models.py`](../investment_analysis_engine/strategies/fcf_growth/models.py), held by the config |
| Strategy analyzer | `FCFEarningsGrowthAnalyzer(BaseAnalyzer[FCFEarningsGrowthConfig, FCFEarningsGrowthResult])` in [`analyzer.py`](../investment_analysis_engine/strategies/fcf_growth/analyzer.py) |
| Strategy result | `FCFEarningsGrowthResult` in [`models.py`](../investment_analysis_engine/strategies/fcf_growth/models.py) |
| Input resolution | `ProductionAnnualGrowthSeriesResolver` in [`input_resolver.py`](../investment_analysis_engine/strategies/fcf_growth/input_resolver.py) |
| Execution adapter | `execute_fcf_growth` and `FCFGrowthCapture` in [`execution.py`](../investment_analysis_engine/strategies/fcf_growth/execution.py) |
| Common execution context | `AnalysisContext` from [`base_analyzer.py`](../investment_analysis_engine/analysis/base_analyzer.py), constructed by the adapter from the run boundary, cache choice, and profile |
| Common request boundary | `AnalysisRequest` in [`requests.py`](../investment_analysis_engine/workspace/requests.py); `FCFGrowthSelection` and `to_fcf_config()` in [`selection.py`](../investment_analysis_engine/strategies/fcf_growth/selection.py) |
| Common execution and persistence | [`workspace.execute()`](../investment_analysis_engine/workspace/execution.py), [`AnalysisRun`](../investment_analysis_engine/workspace/runs.py), and the Analysis Run repository |
| Strategy presentation | `render_fcf_earnings_growth` in [`presenter.py`](../investment_analysis_engine/strategies/fcf_growth/presenter.py) |

The policy remains strategy-owned. `FCFGrowthSelection` is the validated, persisted/request-facing snapshot and converts to the analyzer's `FCFEarningsGrowthConfig`; the adapter supplies the separate common `AnalysisContext`. See the [FCF & Earnings Growth user guide](user/strategies/FCF_GROWTH.md) for method semantics and limitations.

### Ready to add a strategy?

Start from the strategy's financial question and required evidence. Read the relevant financial conventions, identify the narrow provider and provenance needs, define strategy-owned policy and result semantics, then integrate through the existing composition and execution boundaries. Use the FCF example to trace those responsibilities in code.

## Deeper references

- [Architecture](project/ARCHITECTURE.md) — system boundaries and rationale.
- [Financial Math & Data Conventions](user/FINANCE_MATH.md) — shared financial semantics.
- [Glossary](user/GLOSSARY.md) — project and finance terminology.
- [Analysis Strategy Guides](user/strategies/README.md) — investor-facing strategy behavior.
