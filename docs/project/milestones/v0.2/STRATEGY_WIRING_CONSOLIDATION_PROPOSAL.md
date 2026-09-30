# Strategy Wiring Consolidation (SWC) — Work Package

**Status: accepted 2026-09-24, not yet scoped into slices.** Drafted during IR.2's
implementation-inventory pass, per the project owner's explicit request to survey per-strategy
hand-wiring while already reading the CLI, orchestrator, workspace, codec, and reporting layers for
that inventory. Accepted as a work package and sequenced in
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md#sequence-and-status) (row 11, code `SWC`): after
`IR` (needs the shared `run_analysis(ticker, config, context)` envelope as its prerequisite) and
before `R3` (its own dead-code audit runs against a codebase this package has already simplified).
Absorbs IR.5's scope (typed JSON envelope models and generated JSON Schemas), removed from `IR`'s
own scope for that reason — see
[`IR_CONTRACT_AND_SLICE_PLAN.md` §2 item 7](integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md).
Nothing in this document is implemented yet; slicing, local review gates, and a contract document
analogous to `IR_CONTRACT_AND_SLICE_PLAN.md` remain to be written before implementation begins.

## 1. Why this, and why before Step 3.5

Step 3.5 adds five new quantitative-screen analyzers (Piotroski F-Score, Altman Z-Score, Beneish
M-Score, unlevered valuation multiples, Greenblatt Magic Formula). Every wiring point enumerated
below is currently **hand-written once per existing strategy**, in a fixed, repeated shape: a
Pydantic tool-arguments model, a persisted selection model, an execution adapter file, a codec
dispatch branch, a presentation module, a CLI command, an evaluation fixture wiring block, and
several isinstance/dict-key dispatch chains that grow one branch per strategy. None of it is
generated, inherited, or shared — each of the four existing strategies duplicates the same shape
independently. Adding five more analyzers without consolidating this first means writing (and
reviewing, and keeping in sync) roughly five times as much boilerplate as exists today, at exactly
the size where a missed branch (a forgotten `isinstance` case, a forgotten dict entry) becomes a
silent gap rather than an immediate test failure.

This is squarely inside the current consolidation period's stated goal (`AGENTS.md` §0: "making the
existing codebase fully consistent before new strategies copy its patterns") and its explicit
permission ("An explicit, statically declared list of strategies with shared generic wiring is
permitted where it removes per-strategy duplication. Discovery-based plugin loading and speculative
frameworks remain prohibited.").

## 2. Inventory: every hand-written per-strategy wiring point

Surveyed across the five layers named in the project owner's request. Each row names the file, what
is duplicated per strategy today, and how many times (four, soon nine).

### Orchestrator (`src/orchestrator/analysis_tools.py`)

| Wiring point | Shape |
| :--- | :--- |
| `*ToolArguments` Pydantic model | One class per strategy, each hand-listing that strategy's LLM-tool-callable fields. |
| `ANALYZE_*_TOOL` string constant | One `Final` constant per strategy. |
| `ANALYSIS_TOOL_ARGUMENT_MODELS` mapping | One dict entry per strategy, tool name → arguments class. |
| `AnalysisToolDependencies` fields | Strategy-specific resolver/analyzer/policy/provider-id fields, all listed flat on one dataclass. |
| `AnalysisToolHandlers.analyze_*` method | One handler method per strategy, each independently validating arguments, resolving profile, and invoking its analyzer. |
| `register_analysis_tools`'s registration calls | One `dispatcher.register_tool(...)` line per strategy. |

### Workspace (`src/workspace/requests.py`, `src/workspace/*_execution.py`, `src/workspace/execution.py`)

| Wiring point | Shape |
| :--- | :--- |
| `*Selection` Pydantic model (`requests.py`) | One persisted-config model per strategy, plus a shared base for the two Graham variants only. |
| `AnalysisSelection` discriminated union | One union member per strategy (`requests.py:326-329`). |
| `to_*_config()` method | One conversion method per strategy (per-Selection). |
| `*_execution.py` file | One file per strategy (`graham_number_execution.py`, `graham_growth_execution.py`, `fcf_growth_execution.py`, `momentum_execution.py`), each with its own `*Capture` dataclass, `classify_*_outcome` function, and `execute_*`/`run_*` entry function. |
| `NativeEvidence` union (`execution.py:60`) | One union member per strategy's native result type. |
| `from_*_capture` normalizer (`execution.py`) | One function per strategy, each hand-mapping its `*Capture` to the shared `ExecutionCapture`. |
| `_METHOD_VERSIONS` dict (`execution.py:62-67`) | One `(analysis_id, method_id) → (method_version, result_schema_version)` entry per strategy. |
| `_refresh_executor`'s dispatch (`cli_workspace.py:854-862`) | One `isinstance(selection, *Selection)` branch per strategy. |

### Codec (`src/workspace/codecs.py`, `src/workspace/{strategy}.py`)

| Wiring point | Shape |
| :--- | :--- |
| `encode_evidence`'s isinstance chain | One `isinstance(evidence, *)` branch per strategy, order-sensitive (subclass-before-superclass concerns don't currently apply, but the chain is manually ordered). |
| `decode_evidence`'s version-check tuple | One `(analysis_id, method_id)` tuple per strategy in a manually-maintained membership check, plus one more manually-maintained literal per strategy for the expected `method_version`/`result_schema_version` (already awkward today — see the [IR.2 plan](integration-readiness/IR2_ANALYZER_ENVELOPE_PLAN.md#610-persisted-shape-version-bumps-and-alembic-per-the-project-owners-direction-item-7) §6.10 on the `3 if fcf_pair else 1` pattern this document's own IR.2 work is about to make one branch more awkward). |
| `decode_evidence`'s dispatch chain | One `if` branch per strategy, each calling that strategy's own `decode_*` function and checking ticker identity by strategy-specific field access. |
| `src/workspace/{strategy}.py` (`graham_number.py`, `graham_growth.py`, `fcf_growth.py`, `momentum.py`) | One file per strategy, each with its own `encode_*`/`decode_*` pair. |

### Reporting (`src/reporting/analysis_runs.py`, `src/reporting/{strategy}.py`)

| Wiring point | Shape |
| :--- | :--- |
| Per-strategy render function in `analysis_runs.py` | One function per strategy, each `assert isinstance(evidence, *)`-guarded before rendering (lines 120, 122, 161, 185, 213 and their surrounding functions). |
| `src/reporting/{strategy}.py` module | One presentation module per strategy family (`graham.py` covers both Graham methods, `momentum.py`, `fcf_earnings_growth.py`), each with its own concise/details/diagnostics/JSON rendering functions — none shared beneath a common presentation contract. |

### Evaluation (`src/evaluation/models.py`, `src/evaluation/composition.py`) — surfaced in passing, not one of the five named layers, but wired the same way

| Wiring point | Shape |
| :--- | :--- |
| `ToolName` enum (`models.py:19`) | One member per strategy. |
| `AnalysisToolArguments` union type (`composition.py:90-92`) | One union member per strategy. |
| `compose_fixture_dependencies` | Hand-constructs each strategy's fixture-backed analyzer/resolver and assembles one `AnalysisToolDependencies` — every new orchestrator dependency field (see above) needs a matching line here too. |
| `_tool_name`'s isinstance chain | One branch per strategy, mapping argument-model type to `ToolName`. |

### Rough count

Nine strategies (four existing + five Step 3.5) × roughly fourteen wiring points per strategy across
these layers ≈ **over a hundred hand-maintained touch points**, once Step 3.5 lands, for what is
structurally the same shape every time: a config type, a context-consuming `run_analysis`, a result
type, and version identifiers. That count is the concrete case for consolidating before Step 3.5,
not after.

## 3. What AGENTS.md §0 permits, and what it doesn't

"An explicit, statically declared list of strategies with shared generic wiring is permitted where
it removes per-strategy duplication. Discovery-based plugin loading and speculative frameworks
remain prohibited." Concretely, that means:

- **Permitted:** one plain, statically-written data structure — a tuple or frozen mapping of
  `StrategyDescriptor` entries, each naming one strategy's tool name, analysis/method identifiers,
  config/result types, and the handful of strategy-specific callables (build handler, encode,
  decode, render, classify outcome) — that the orchestrator/workspace/codec/reporting layers iterate
  or index into, replacing the isinstance chains and per-strategy dict literals above with one loop
  or lookup each.
- **Not permitted:** import-time strategy discovery (scanning `src/analysis/strategy/` for anything
  that looks like an analyzer and auto-registering it), a generic `BaseAnalyzer` subclass registry
  with `__init_subclass__` auto-registration, or a plugin-loader abstraction. Every strategy still
  gets added to the explicit list by a person, in one PR, reviewed like any other change — this
  proposal is about deduplicating the *shape* each entry takes, not about making strategies
  self-registering or dynamically discovered.

This keeps `AGENTS.md` §3's standing prohibition ("NEVER create a generic strategy/plugin/registry/
factory hierarchy merely because two analyzers differ") intact outside the consolidation period —
the temporary §0 carve-out is narrow (an explicit static list), not a general license for a
framework.

## 4. Proposed shape (illustrative, not final — for review)

```python
# src/analysis/strategy_registry.py  (illustrative only)


@dataclass(frozen=True)
class StrategyDescriptor[ConfigT, ResultT]:
    analysis_id: str
    method_id: str
    tool_name: str
    config_type: type[ConfigT]
    result_type: type[ResultT]
    method_version: int
    result_schema_version: int
    # ... the small number of genuinely strategy-specific callables each layer needs:
    # build_analyzer, tool_arguments_type, encode, decode, render_concise, render_json, ...


STRATEGIES: Final[tuple[StrategyDescriptor[Any, Any], ...]] = (
    MOMENTUM_STRATEGY,
    GRAHAM_NUMBER_STRATEGY,
    GRAHAM_GROWTH_STRATEGY,
    FCF_EARNINGS_GROWTH_STRATEGY,
)
```

Each layer's current per-strategy dispatch (the `encode_evidence`/`decode_evidence` isinstance
chains, `_refresh_executor`'s isinstance chain, `_tool_name`'s isinstance chain,
`ANALYSIS_TOOL_ARGUMENT_MODELS`, `_METHOD_VERSIONS`, `NativeEvidence`/`AnalysisSelection` unions)
becomes a lookup or iteration over `STRATEGIES` instead of a hand-maintained parallel structure.
This is a genuine reduction in duplication, not a relabeling — today, adding a strategy means
touching roughly fourteen files/dicts/chains by hand and hoping none is missed; the reviewer has no
single place to check "was this strategy wired everywhere." A `StrategyDescriptor` list gives that
single place, and a missing wiring point becomes a type error (an incomplete descriptor) rather than
a silent runtime gap.

**Exact typing shape (`Any`/covariance/how nine heterogeneous `ConfigT`/`ResultT` pairs coexist in
one tuple) needs real design work this proposal deliberately doesn't do** — that's implementation,
not scoping, and belongs to whichever slice plan eventually owns this if accepted.

## 5. Proposed `docs/TOOL_DEVELOPMENT.md`

A new developer-facing guide, referenced from `docs/project/README.md`, walking through "how to add
a new analysis strategy" as a single checklist against the `StrategyDescriptor` shape above:
define `ConfigT`/`ResultT`, implement `BaseAnalyzer[ConfigT, ResultT]`, write the descriptor entry,
and — critically — an explicit list of what does **not** need hand-written wiring anymore (tool
registration, codec dispatch, refresh dispatch, evaluation fixture-name mapping) versus what still
does (the calculation itself, its fixtures, its presentation formatting, its Golden cases). This
guide is Step 3.5's actual consumer: its five analyzers would be the first real-world test of
whether the checklist is complete, the same verification relationship IR.2's envelope has with
Piotroski specifically (IR §5 item 7).

## 6. Relationship to other work packages — decided 2026-09-24

Sequence: `IR` (IR.1, IR.2 and the slices added since; the Momentum series API, once IR.3, moved to the candidate backlog on 2026-09-30) → `SWC` (this package, including IR.5's absorbed scope) → `R3` →
`PKG` → Step 3.5.

- **Depends on IR.** The `StrategyDescriptor.build_analyzer`-shaped callable only makes sense once
  every strategy shares one `run_analysis(ticker, config, context)` shape; attempting this before IR
  lands would bake today's four-different-call-shapes problem into the registry itself.
- **Precedes R3.** This package deletes the per-strategy `isinstance` chains and dict literals
  enumerated in §2 — exactly the kind of thing R3's dead-code audit would otherwise have to reason
  about branch-by-branch. Running SWC first means R3 audits a codebase that no longer has that
  dispatch-chain shape at all, rather than auditing branches this package is about to delete anyway.
- **Precedes PKG**, along with R3 — PKG (the `src` → real package rename) changes import paths, not
  strategy-wiring shape, and gains nothing from running before either R3 or SWC; running it last
  among the three means Step 3.5's five new analyzers are written once, under the final import path,
  against an already-consolidated, already-cleaned codebase.
- **Feeds Step 3.5 directly**, per §5 above — this is the practical reason it runs *before* Step 3.5,
  not merely "sometime before."

This document proposes scope only; sequencing is now decided (above). No code changes, no new file
beyond this proposal and (once its own contract/slice plan is written) `docs/TOOL_DEVELOPMENT.md`'s
eventual authoring, have been made.
