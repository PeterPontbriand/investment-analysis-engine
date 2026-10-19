# Analysis Strategy Contributor Guide

This guide orients contributors who want to add a deterministic financial analysis strategy. It describes the current extension points without prescribing a fixed file layout or coding recipe.

## What an analysis strategy is

An analysis strategy is a named, deterministic method that resolves the evidence it needs, applies explicit financial rules in Python, and returns a typed result. Strategies may have different inputs, policies, calculations, and result models while sharing application infrastructure.

The [user-facing strategy guides](../user/strategies/README.md) explain the behavior and limitations of implemented strategies. This guide focuses on how they fit into the code.

## The current analyzer contract

[`BaseAnalyzer`](../../investment_analysis_engine/analysis/base_analyzer.py) is an abstract generic contract, `BaseAnalyzer[ConfigT, ResultT]`. Its `run_analysis(ticker, config, context)` method accepts a strategy-owned configuration and the shared `AnalysisContext`, and returns that strategy's typed result. The type variables are intentionally unconstrained: configuration may be a Pydantic model, frozen dataclass, or another typed shape. The base contract does not implement input resolution, provider access, presentation, or persistence.

All current strategy analyzers inherit from `BaseAnalyzer` with their own configuration and result types. The common interface does not make their calculation semantics or result models interchangeable.

`AnalysisContext` is the frozen per-run value object for cross-cutting execution concerns:

- `as_of` is the requested point-in-time boundary, or `None` when the caller did not request one. It is not replaced with a fabricated historical date.
- `executed_at` is the timezone-aware execution clock captured once by the caller for the analysis run.
- `effective_as_of` is a derived property: the requested `as_of` when present, otherwise `executed_at`. Analysis-layer data must respect this cutoff.
- `use_cache` is the run-wide permission governing cache reads and writes used by the analysis.
- `instrument_profile` carries the run's identity evidence. It is retained in results even when the calculation does not consult it.

For the full clock model — which instant each kind of check compares against, the decision-clock/event-clock distinction, `utc_now()`, and why frozen-clock skew is tolerated only for live runs — see ARCHITECTURE.md's [*Time and the analysis boundary*](ARCHITECTURE.md#5-time-and-the-analysis-boundary) rather than this guide; duplicating those rules here would let the two drift.

The workspace selections expose `to_analysis_context(executed_at, instrument_profile)` alongside method-specific config conversion. Direct execution adapters and orchestrator handlers construct this context at their execution boundary. See [`AnalysisSelection`](../../investment_analysis_engine/workspace/strategy_types.py) and each strategy's `selection.py` under `investment_analysis_engine/strategies/` for its method-specific request model, and [`AnalysisRequest`](../../investment_analysis_engine/workspace/requests.py) for the workspace request boundary. The [Architecture](ARCHITECTURE.md) documents broader boundaries and rationale.

## How a strategy runs

An invocation begins in CLI or orchestrator composition, which validates the method-specific selection and composes the provider, cache, resolver, and adapter dependencies. The adapter prepares the run's config and `AnalysisContext`, invokes the analyzer, and packages the native result with its profile and normalized execution outcome. A direct command presents that result. In the workspace flow, a capture callable returns a normalized capture to common `workspace.execute()`, which records envelope timing, encodes native evidence, constructs an `AnalysisRun`, and inserts it through the run repository.

The adapter connects a method to execution capture; it does not duplicate its financial rules. Common workspace execution owns the shared run envelope and persistence boundary; it does not calculate strategy metrics or reclassify the financial result.

### Strategy integration architecture

The strategy supplies its own config, resolver, calculations, and result; composition supplies the context and shared infrastructure. Persistence is conditional, not automatic: `maybe_save_run` (`investment_analysis_engine/cli_run_support.py`) is the one place shared by all four direct commands that decides whether a run reaches `workspace.execute()` at all, based on `--save-run`; a watchlist refresh reaches the same `execute()` through its own composition in `investment_analysis_engine/workspace/refresh.py` instead.

**What the contributor owns:** strategy policy/configuration, required input semantics and resolution, deterministic calculations, typed result, tests, user-facing presentation where needed, and its execution-adapter integration. **What is shared:** provider/cache contracts, provenance values, the `maybe_save_run`/refresh persistence decision, workspace execution, run persistence, and shared financial conventions. Reuse the shared boundaries instead of rebuilding them inside a strategy.

### What happens during an FCF & Earnings Growth run

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

## Where financial data comes from

The strategy determines which financial capability its semantics require. FCF growth uses a `FinancialFactsProvider` through its production annual-series resolver, currently backed by SEC EDGAR for the required completed annual cash-flow and EPS facts. The resolution layer can use an optional cache and returns typed inputs with source, period, availability, retrieval, and transformation lineage. Historical prices, company financial facts, quotes, and macro observations are distinct capabilities; do not treat one as a substitute for another.

`use_cache` controls whether the resolver can use its configured resolved-input cache. Provider and cache composition belongs at the application boundary. Detailed financial definitions, conventions, and data limitations belong in [Financial Math & Data Conventions](../user/FINANCE_MATH.md) and the relevant [strategy guide](../user/strategies/FCF_GROWTH.md).

## How inputs and provenance are handled

An input resolver turns provider evidence into strategy-appropriate typed observations. For FCF growth, `ProductionAnnualGrowthSeriesResolver` selects compatible, contiguous annual evidence under the requested `as_of`, records a `ResolutionTrace`, and returns annual observations whose component values retain `ResolvedInput` provenance. The analyzer consumes the resolved assembly; it does not fetch from providers itself.

Keep missing, unavailable, and not-applicable evidence explicit. Preserve source and time metadata, transformations, cache/override state, and diagnostics at the boundary that resolves the value. Do not silently substitute zero or hide a provider limitation.

## How calculations produce a typed result

Calculations are deterministic Python operations. The FCF strategy derives free cash flow and free cash flow per diluted share from admissible annual evidence, computes its growth metrics, and classifies the result using its explicit policy. `FCFEarningsGrowthResult` retains the metrics, classification, selected horizon, observations, warnings, instrument profile, and resolution diagnostics. Its financial `PASS`, `FAIL`, or `INDETERMINATE` classification is distinct from `CalculationStatus` and from the workspace's run outcome.

Do not make the LLM responsible for financial calculations. Avoid copying formulas into a contributor guide when the financial authority already documents them.

## How results become user-visible

Direct analysis commands send a native typed result to the strategy's presentation function. FCF uses `render_fcf_earnings_growth`, with concise, details, diagnostics, and JSON modes built around the strategy's own model. Shared formatting utilities in [`investment_analysis_engine/reporting/presentation.py`](../../investment_analysis_engine/reporting/presentation.py) provide common vocabulary; they do not homogenize strategy result types. Saved-run views project from the persisted evidence rather than rerunning providers or calculations.

Provide presentation behavior that makes the result, limitations, and relevant provenance understandable. Keep presentation-only wording out of financial calculations.

## Execution capture and durable persistence

The FCF-specific `execute_fcf_growth` adapter composes the profile and `AnalysisContext`, invokes the analyzer, and maps the analyzer's execution status into a `RunOutcome`. It returns an `FCFGrowthCapture` with the native result and profile; the caller normalizes that capture to the common `ExecutionCapture`. The common [`workspace.execute()`](../../investment_analysis_engine/workspace/execution.py) invokes a capture callable, records its own `started_at` and `completed_at` envelope timestamps, encodes the native evidence, assembles the common run record, and inserts it into the provided repository. These persistence-envelope timestamps are separate from the analysis context's `executed_at`. [`AnalysisRun`](../../investment_analysis_engine/workspace/runs.py) is the durable domain record for the request/configuration snapshot, timing, versions, status, result evidence, presentation inputs, and profile.

The adapter is strategy-specific integration work. The workspace execution service is shared infrastructure and must not become a second implementation of a strategy's semantics. Do not assume every adapter has the same signature or that `BaseAnalyzer` is a unified execution interface.

## Strategy-specific responsibilities and shared infrastructure

| Strategy-specific work | Shared infrastructure to reuse |
| --- | --- |
| Configuration or policy and its semantic rules | `BaseAnalyzer[ConfigT, ResultT]`, `AnalysisContext`, workspace request selections |
| Strategy analyzer and typed result | `ResolvedInput`, `ResolutionTrace`, provider contracts |
| Input requirements and strategy-owned resolver/calculations | Financial-fact providers, historical-price providers, and caches where applicable |
| Focused tests for rules, unavailable evidence, and edge cases | Common `workspace.execute()`, `AnalysisRun`, repositories, and evidence codecs |
| Investor-facing rendering and strategy guide | Shared presentation vocabulary and financial conventions |
| Strategy-specific execution adapter integration | CLI/workspace composition and persistence boundaries |

This is a responsibility map. A strategy's analyzer, codec, execution adapter and presenter live in `investment_analysis_engine/strategies/<strategy>/`, in files named for their role. Keep method semantics in the strategy layer, provider composition at application boundaries, and common execution capture/persistence in the workspace layer.

## Existing strategy reference: FCF & Earnings Growth

FCF growth is a useful end-to-end example because its resolver, calculation, presentation, adapter, and workspace capture are separately visible. Current names and locations:

| Generic concept | FCF & Earnings Growth implementation |
| --- | --- |
| Strategy configuration | `FCFEarningsGrowthConfig` in [`models.py`](../../investment_analysis_engine/strategies/fcf_growth/models.py), built from `FCFGrowthSelection.to_fcf_config()` in [`selection.py`](../../investment_analysis_engine/strategies/fcf_growth/selection.py) |
| Strategy policy | `FCFEarningsGrowthPolicy` in [`models.py`](../../investment_analysis_engine/strategies/fcf_growth/models.py), held by the config |
| Strategy analyzer | `FCFEarningsGrowthAnalyzer(BaseAnalyzer[FCFEarningsGrowthConfig, FCFEarningsGrowthResult])` in [`analyzer.py`](../../investment_analysis_engine/strategies/fcf_growth/analyzer.py) |
| Strategy result | `FCFEarningsGrowthResult` in [`models.py`](../../investment_analysis_engine/strategies/fcf_growth/models.py) |
| Input resolution | `ProductionAnnualGrowthSeriesResolver` in [`input_resolver.py`](../../investment_analysis_engine/strategies/fcf_growth/input_resolver.py) |
| Execution adapter | `execute_fcf_growth` and `FCFGrowthCapture` in [`execution.py`](../../investment_analysis_engine/strategies/fcf_growth/execution.py) |
| Common execution context | `AnalysisContext` from [`base_analyzer.py`](../../investment_analysis_engine/analysis/base_analyzer.py), constructed by the adapter from the run boundary, cache choice, and profile |
| Common request boundary | `AnalysisRequest` in [`requests.py`](../../investment_analysis_engine/workspace/requests.py); `FCFGrowthSelection` and `to_fcf_config()` in [`selection.py`](../../investment_analysis_engine/strategies/fcf_growth/selection.py) |
| Common execution and persistence | [`workspace.execute()`](../../investment_analysis_engine/workspace/execution.py), [`AnalysisRun`](../../investment_analysis_engine/workspace/runs.py), and the Analysis Run repository |
| Strategy presentation | `render_fcf_earnings_growth` in [`presenter.py`](../../investment_analysis_engine/strategies/fcf_growth/presenter.py) |

The policy remains strategy-owned. `FCFGrowthSelection` is the validated, persisted/request-facing snapshot and converts to the analyzer's `FCFEarningsGrowthConfig`; the adapter supplies the separate common `AnalysisContext`. See the [FCF & Earnings Growth user guide](../user/strategies/FCF_GROWTH.md) for method semantics and limitations.

## Edit sites of a strategy

A strategy touches the places below. Run `uv run python scripts/strategy_status.py <module_name> [--alias <alias>]` to see which are `done` and which are `missing` for one strategy, with the diagnostic for each missing one; it runs the same check functions as the conformance tests, and it does not run the type checker, which the managed quality gate does. In a path, `{module}` is the strategy's package name, `{alias}` its hyphenated command alias, and `{guide}` its upper-case guide name.

<!-- BEGIN GENERATED edit-sites: written by scripts/generate_strategy_docs.py; generated, do not edit by hand. -->
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
| `schema` | Published schema (run scripts/generate_schemas.py). Every strategy document has a checked-in schema. | `schemas/{alias}.schema.json` | command | no | `site_schema`: schema schemas/<alias>.schema.json is missing or out of date; run scripts/generate_schemas.py |
| `strategy-docs` | Generated strategy lists (run scripts/generate_strategy_docs.py). The strategy lists in USAGE.md and WORKSPACE.md are generated from the descriptors, one entry per strategy. | `docs/user/USAGE.md` | command | no | `site_strategy_docs`: the strategy is missing from the generated block of USAGE.md or WORKSPACE.md, or a block is out of date; run scripts/generate_strategy_docs.py |
<!-- END GENERATED edit-sites -->

## Testing and quality expectations

Test the method's own meaning and boundaries: valid calculations, policy branches, time-boundary behavior, missing or incompatible evidence, and provenance. Deterministic tests should use fixtures or provider fakes rather than real external API or LLM calls. Test adapter outcome mapping and workspace persistence at their respective boundaries when those areas are touched.

Follow the repository's established static checks and pytest practices described in the [project instructions](../../AGENTS.md).

## Deeper references

- [Architecture](ARCHITECTURE.md) — system boundaries and rationale.
- [Financial Math & Data Conventions](../user/FINANCE_MATH.md) — shared financial semantics.
- [Glossary](../user/GLOSSARY.md) — project and finance terminology.
- [Analysis Strategy Guides](../user/strategies/README.md) — investor-facing strategy behavior.

## Ready to add a strategy?

Start from the strategy's financial question and required evidence. Read the relevant financial conventions, identify the narrow provider and provenance needs, define strategy-owned policy and result semantics, then integrate through the existing composition and execution boundaries. Use the FCF example to trace those responsibilities in code.
