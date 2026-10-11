# Analysis Strategy Contributor Guide

This guide orients contributors who want to add a deterministic financial analysis strategy. It describes the current extension points without prescribing a fixed file layout or coding recipe.

## What an analysis strategy is

An analysis strategy is a named, deterministic method that resolves the evidence it needs, applies explicit financial rules in Python, and returns a typed result. Strategies may have different inputs, policies, calculations, and result models while sharing application infrastructure.

The [user-facing strategy guides](../user/strategies/README.md) explain the behavior and limitations of implemented strategies. This guide focuses on how they fit into the code.

## The current analyzer contract

[`BaseAnalyzer`](../../src/analysis/base_analyzer.py) is an abstract generic contract, `BaseAnalyzer[ConfigT, ResultT]`. Its `run_analysis(ticker, config, context)` method accepts a strategy-owned configuration and the shared `AnalysisContext`, and returns that strategy's typed result. The type variables are intentionally unconstrained: configuration may be a Pydantic model, frozen dataclass, or another typed shape. The base contract does not implement input resolution, provider access, presentation, or persistence.

All current strategy analyzers inherit from `BaseAnalyzer` with their own configuration and result types. The common interface does not make their calculation semantics or result models interchangeable.

`AnalysisContext` is the frozen per-run value object for cross-cutting execution concerns:

- `as_of` is the requested point-in-time boundary, or `None` when the caller did not request one. It is not replaced with a fabricated historical date.
- `executed_at` is the timezone-aware execution clock captured once by the caller for the analysis run.
- `effective_as_of` is a derived property: the requested `as_of` when present, otherwise `executed_at`. Analysis-layer data must respect this cutoff.
- `use_cache` is the run-wide permission governing cache reads and writes used by the analysis.
- `instrument_profile` carries the run's identity evidence. It is retained in results even when the calculation does not consult it.

For the full clock model — which instant each kind of check compares against, the decision-clock/event-clock distinction, `utc_now()`, and why frozen-clock skew is tolerated only for live runs — see ARCHITECTURE.md's [*Time and the analysis boundary*](ARCHITECTURE.md#5-time-and-the-analysis-boundary) rather than this guide; duplicating those rules here would let the two drift.

The workspace selections expose `to_analysis_context(executed_at, instrument_profile)` alongside method-specific config conversion. Direct execution adapters and orchestrator handlers construct this context at their execution boundary. See [`AnalysisSelection`](../../src/workspace/strategy_types.py) and each strategy's `selection.py` under `src/strategies/` for its method-specific request model, and [`AnalysisRequest`](../../src/workspace/requests.py) for the workspace request boundary. The [Architecture](ARCHITECTURE.md) documents broader boundaries and rationale.

## How a strategy runs

An invocation begins in CLI or orchestrator composition, which validates the method-specific selection and composes the provider, cache, resolver, and adapter dependencies. The adapter prepares the run's config and `AnalysisContext`, invokes the analyzer, and packages the native result with its profile and normalized execution outcome. A direct command presents that result. In the workspace flow, a capture callable returns a normalized capture to common `workspace.execute()`, which records envelope timing, encodes native evidence, constructs an `AnalysisRun`, and inserts it through the run repository.

The adapter connects a method to execution capture; it does not duplicate its financial rules. Common workspace execution owns the shared run envelope and persistence boundary; it does not calculate strategy metrics or reclassify the financial result.

### Strategy integration architecture

The strategy supplies its own config, resolver, calculations, and result; composition supplies the context and shared infrastructure. Persistence is conditional, not automatic: `maybe_save_run` (`src/cli_run_support.py`) is the one place shared by all four direct commands that decides whether a run reaches `workspace.execute()` at all, based on `--save-run`; a watchlist refresh reaches the same `execute()` through its own composition in `src/workspace/refresh.py` instead.

**What the contributor owns:** strategy policy/configuration, required input semantics and resolution, deterministic calculations, typed result, tests, user-facing presentation where needed, and its execution-adapter integration. **What is shared:** provider/cache contracts, provenance values, the `maybe_save_run`/refresh persistence decision, workspace execution, run persistence, and shared financial conventions. Reuse the shared boundaries instead of rebuilding them inside a strategy.

### What happens during an FCF & Earnings Growth run

`maybe_save_run` (`src/cli_run_support.py`) is a pure passthrough to the adapter when `--save-run` is not given — the default direct-command path never touches `workspace.execute()`, opens no database, and builds no durable profile cache. Only when `--save-run` is set does it open a database, build the capture closure, and call `execute()`. A watchlist refresh never goes through `maybe_save_run`; it reaches `workspace.execute()` through its own composition in `src/workspace/refresh.py`, following the same adapter/normalize contract.

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

`use_cache` controls whether the resolver can use its configured resolved-input cache. Provider and cache composition belongs at the application boundary. Detailed financial definitions, conventions, and data limitations belong in [Financial Math & Data Conventions](../user/FINANCE_MATH.md) and the relevant [strategy guide](../user/strategies/FCF_EARNINGS_GROWTH.md).

## How inputs and provenance are handled

An input resolver turns provider evidence into strategy-appropriate typed observations. For FCF growth, `ProductionAnnualGrowthSeriesResolver` selects compatible, contiguous annual evidence under the requested `as_of`, records a `ResolutionTrace`, and returns annual observations whose component values retain `ResolvedInput` provenance. The analyzer consumes the resolved assembly; it does not fetch from providers itself.

Keep missing, unavailable, and not-applicable evidence explicit. Preserve source and time metadata, transformations, cache/override state, and diagnostics at the boundary that resolves the value. Do not silently substitute zero or hide a provider limitation.

## How calculations produce a typed result

Calculations are deterministic Python operations. The FCF strategy derives free cash flow and free cash flow per diluted share from admissible annual evidence, computes its growth metrics, and classifies the result using its explicit policy. `FCFEarningsGrowthResult` retains the metrics, classification, selected horizon, observations, warnings, instrument profile, and resolution diagnostics. Its financial `PASS`, `FAIL`, or `INDETERMINATE` classification is distinct from `CalculationStatus` and from the workspace's run outcome.

Do not make the LLM responsible for financial calculations. Avoid copying formulas into a contributor guide when the financial authority already documents them.

## How results become user-visible

Direct analysis commands send a native typed result to the strategy's presentation function. FCF uses `render_fcf_earnings_growth`, with concise, details, diagnostics, and JSON modes built around the strategy's own model. Shared formatting utilities in [`src/reporting/presentation.py`](../../src/reporting/presentation.py) provide common vocabulary; they do not homogenize strategy result types. Saved-run views project from the persisted evidence rather than rerunning providers or calculations.

Provide presentation behavior that makes the result, limitations, and relevant provenance understandable. Keep presentation-only wording out of financial calculations.

## Execution capture and durable persistence

The FCF-specific `execute_fcf_growth` adapter composes the profile and `AnalysisContext`, invokes the analyzer, and maps the analyzer's execution status into a `RunOutcome`. It returns an `FCFGrowthCapture` with the native result and profile; the caller normalizes that capture to the common `ExecutionCapture`. The common [`workspace.execute()`](../../src/workspace/execution.py) invokes a capture callable, records its own `started_at` and `completed_at` envelope timestamps, encodes the native evidence, assembles the common run record, and inserts it into the provided repository. These persistence-envelope timestamps are separate from the analysis context's `executed_at`. [`AnalysisRun`](../../src/workspace/runs.py) is the durable domain record for the request/configuration snapshot, timing, versions, status, result evidence, presentation inputs, and profile.

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

This is a responsibility map. A strategy's analyzer, codec, execution adapter and presenter live in `src/strategies/<strategy>/`, in files named for their role. Keep method semantics in the strategy layer, provider composition at application boundaries, and common execution capture/persistence in the workspace layer.

## Existing strategy reference: FCF & Earnings Growth

FCF growth is a useful end-to-end example because its resolver, calculation, presentation, adapter, and workspace capture are separately visible. Current names and locations:

| Generic concept | FCF & Earnings Growth implementation |
| --- | --- |
| Strategy configuration | `FCFEarningsGrowthConfig` in [`models.py`](../../src/strategies/fcf_growth/models.py), built from `FCFGrowthSelection.to_fcf_config()` in [`selection.py`](../../src/strategies/fcf_growth/selection.py) |
| Strategy policy | `FCFEarningsGrowthPolicy` in [`models.py`](../../src/strategies/fcf_growth/models.py), held by the config |
| Strategy analyzer | `FCFEarningsGrowthAnalyzer(BaseAnalyzer[FCFEarningsGrowthConfig, FCFEarningsGrowthResult])` in [`analyzer.py`](../../src/strategies/fcf_growth/analyzer.py) |
| Strategy result | `FCFEarningsGrowthResult` in [`models.py`](../../src/strategies/fcf_growth/models.py) |
| Input resolution | `ProductionAnnualGrowthSeriesResolver` in [`input_resolver.py`](../../src/strategies/fcf_growth/input_resolver.py) |
| Execution adapter | `execute_fcf_growth` and `FCFGrowthCapture` in [`execution.py`](../../src/strategies/fcf_growth/execution.py) |
| Common execution context | `AnalysisContext` from [`base_analyzer.py`](../../src/analysis/base_analyzer.py), constructed by the adapter from the run boundary, cache choice, and profile |
| Common request boundary | `AnalysisRequest` in [`requests.py`](../../src/workspace/requests.py); `FCFGrowthSelection` and `to_fcf_config()` in [`selection.py`](../../src/strategies/fcf_growth/selection.py) |
| Common execution and persistence | [`workspace.execute()`](../../src/workspace/execution.py), [`AnalysisRun`](../../src/workspace/runs.py), and the Analysis Run repository |
| Strategy presentation | `render_fcf_earnings_growth` in [`presenter.py`](../../src/strategies/fcf_growth/presenter.py) |

The policy remains strategy-owned. `FCFGrowthSelection` is the validated, persisted/request-facing snapshot and converts to the analyzer's `FCFEarningsGrowthConfig`; the adapter supplies the separate common `AnalysisContext`. See the [FCF & Earnings Growth user guide](../user/strategies/FCF_EARNINGS_GROWTH.md) for method semantics and limitations.

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
