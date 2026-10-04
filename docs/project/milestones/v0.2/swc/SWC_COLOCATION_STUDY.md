# SWC — Co-location Study

**Status: adopted, 2026-10-03.** The project owner chose option D in its two-tier form (§3). The
[SWC.1 design](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md) now owns the result and does not depend on this study;
the plan's [decision record](SWC_CONTRACT_AND_SLICE_PLAN.md#b7-co-location-adoption-2026-10-03) lists what the
owner decided beyond the study's recommendation (scheduled locality moves, further edit-site reductions,
contributor tooling, a repetition checkpoint and a folder-layout decision). The figures below are the study's
and describe the form it recommended; the design's final edit-site numbers are in
[design Appendix E](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#appendix-e-adoption-of-the-co-location-result). This
document is kept as the evidence record.

A design study, written after the [SWC.1 design](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md) merged. It asks how
close the SWC design can get to "write one package and one descriptor" when per-strategy behavior moves
out of generic modules, and what that costs. When written it changed no design, plan or status; the project
owner then decided (see the status line above). Nothing under `src/`, `tests/` or `scripts/` was touched; the prototypes are scratch files
under `.tmp/colocation/` and are not committed.

## 1. At a glance

- **The question:** design [§17](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#17-edit-sites-for-a-new-strategy)
  says eight one-line entries in generic modules cannot move into the descriptor because of import
  cycles. [Appendix C of that design](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#appendix-c-import-cycle-evidence)
  tested only one import direction: generic modules import the descriptor. This study also tests moving
  the functions into strategy-owned modules, and inverting the direction.
- **The answer:** "one package and one descriptor" is not reachable under the constraints, and no option
  gets there. A new strategy still edits at least ten files that exist today (type lists, the dependency
  bundle, fixtures, the direct command, the user guides) whichever option is chosen: ten in B and C,
  eleven in D, fifteen in A. What the options differ in is the six table lines in generic modules, where
  the forgotten-entry check lives, and which import direction the foundation layers end up with.
- **Option B** (strategy-owned modules, consumers import the descriptor) is acyclic only after six
  structural fixes, each shown necessary. Afterwards the foundation layers reach 18 reporting modules and
  6 CLI modules, a layering rule changes, and the descriptor sits in a package-initialization cycle of 25
  modules.
- **Option C** (one package per strategy) has the same module graph as B. It only reduces the directories
  touched (11 to 9) and adds three costs: an empty `__init__.py` rule, a shared-Graham family package, and
  about 125 importer files rewritten.
- **A better variant, D:** put the descriptor at the composition root and inject each layer's slice into
  the generic consumers at construction, instead of letting them import it. The foundation layers and
  reporting then import nothing from it, no layering rule changes, and the descriptor is outside every
  cycle. Six of the eight table lines disappear (one CLI-tier line is added) and seven omissions become
  `mypy --strict` errors at the descriptor.
- **Typing:** the prototype passes `mypy --strict` for all four strategies with no `Any`, no `cast` and no
  `type: ignore`, and rejects nine deliberate mispairings ([Appendix C](#appendix-c-typing-prototype)).
- **Recommendation:** adopt D, in its two-tier form ([§3](#3-recommendation)). Staying with A is
  acceptable, but A needs one correction either way: a package-initialization cycle through
  `src/workspace/__init__.py` ([Appendix J](#appendix-j-findings-in-the-swc1-design)).
- **Constraints:** none of the constraints that do not move is broken by any option
  ([§6](#6-scope-limits-and-constraint-check)).

## 2. Comparison

Counts are for a new strategy named `x`, excluding tests. "Restatements" are one-line entries in tables or
lists owned by generic modules (design §17 kinds R and the R part of G+R). The module graph is built from
the real source with function-level moves ([Appendix A](#appendix-a-import-graph-evidence)).

| | A: consumer tables (current) | B: strategy-owned modules, consumers import descriptor | C: one package per strategy | D: root descriptor, injected, two-tier (recommended) |
| :--- | :--- | :--- | :--- | :--- |
| Hand-edit sites | 23 | 23 | 23 | 24 |
| Restatements in generic-owned files | 11 | 5 | 5 | 6 |
| Existing files edited | 15 | 10 | 10 | 11 |
| New files | 10 | 14 | 15 | 14 |
| Distinct files | 25 | 24 | 25 | 25 |
| Directories touched | 11 | 11 | 9 | 11 |
| Omissions that become type errors at the descriptor | 0 | 7 | 7 | 7 |
| Module-level import cycles | 0 | 0 after six fixes (1 of 23 modules before) | same graph as B | 0 (one fix plus two container moves, not six fixes) |
| Package-initialization cycle containing the descriptor | 9 modules | 25 modules | 25 modules | none |
| Foundation and reporting modules that import the descriptor | 11 | 5 | 5 | 0 |
| Layering effect | Foundation reaches 4 dependency-free reporting leaves | Foundation reaches 18 reporting and 6 CLI modules; rule changes | as B, and folders stop encoding layers | Unchanged for foundation and reporting; evaluation reaches reporting and workspace, as in A |
| Typing under `mypy --strict` | Passes (SWC.1 Appendix B) | Passes, no `Any`, no `cast` | Passes (same code) | Passes, no `Any`, no `cast`, 9 mispairings rejected |
| T10 surfaces left | 12 | 3 | 3 | 4 |
| Existing modules split or relocated | 0 beyond SWC.2a | 6 split | 6 split, about 29 relocated | 6 split |
| New modules | 15 (design) | 23 beyond A | 23 beyond A, regrouped | 23 beyond A |
| Importer files rewritten beyond SWC.2a | 0 | 29 | 105 | 29 |
| Signatures that change | 0 | 0 | 0 | 8 |
| Stored-shape or output change | none | none | none | none |

The 23 sites are not reduced because each strategy-owned function still has to be written. What changes is
where the one-line entry for it lives and what fails if it is forgotten.

## 3. Recommendation

**Adopt D, in its two-tier form.** One closed tuple of descriptors in `src/strategy_wiring.py`, at the
composition root. Each descriptor holds identity, versions, tool binding and one typed behavior bundle,
`StrategyBehavior[SelT, ResultT]`, that pairs every strategy-owned function mentioning the selection or
result type ([Appendix C](#appendix-c-typing-prototype)). The generic consumers below the root never import
the descriptor module. The composition root builds one `Mapping` per layer from the tuple and passes it in,
typed by a narrow `Protocol` that the consuming layer declares. The CLI-layer functions (selection builder
and refresh executor) sit in a second closed tuple in `src/cli_strategy_wiring.py`, typed against the same
selection type.

Reasoning, in order of weight:

1. **It is the only form that removes the six table lines without reversing a layering rule.** The
   foundation layers (`core`, `config`, `data`, `analysis`, `workspace`, `orchestrator`) and `reporting`
   import nothing from the descriptor. B, C and A all make some of them reach upward.
2. **It is cheaper than B and C to make acyclic.** Because no lower layer imports the descriptor, five of
   the six structural fixes B needs are not needed for correctness (Appendix A, table A.3). They remain
   worthwhile for locality, so the amendments schedule them with the slice that first needs each one.
3. **A forgotten behavior becomes a type error.** Seven omissions (handler, parser, builder, executor,
   projector, native status, selection-union membership) fail `mypy --strict` at the descriptor, where A
   needed a test to notice.
4. **It stops four generic modules growing.** `requests.py`, `analysis_tools.py`, `cli_workspace.py` and
   `analysis_runs.py` hold 860 lines of per-strategy code today (of about 2,200). At the measured average
   of about 215 lines per strategy, seven more strategies add about 1,500 more lines in A; in D they are
   new files in strategy-owned modules ([Appendix H](#appendix-h-cost-slices-and-the-package-rename)).
5. **Dependency injection at construction is preserved and extended.** Handlers still receive their
   analyzers at construction; refresh executors still compose their own providers per call; every generic
   dispatcher now receives its table as a parameter, which matches how `refresh_watchlist` already receives
   its executor.

What D does not do, stated plainly: it does not shrink the distinct files a contributor touches (25 in A,
25 in D), it does not remove the type lists, and it adds one declaration (the CLI-tier entry) to keep the
CLI composition helpers out of the evaluation import closure. The single-tier form, with one descriptor
holding the CLI functions as well, is measured in Appendix A (table A.1). It needs the rule "`evaluation`
may import modules that import `typer`, `yfinance` clients and `cli_support`", and is not recommended.

Staying with A remains valid if the owner prefers to keep the merged design. In that case the
`src/workspace/__init__.py` correction in Appendix J is required, and the six table lines stay.

## 4. Shape of the recommendation

Import direction, observed on `main` and under D (arrows read "imports"):

| Layer | Imports | Imported by | Under D |
| :--- | :--- | :--- | :--- |
| Foundation: `core`, `config`, `utils`, `schema`, `llm`, `tools`, `data`, `analysis`, `workspace`, `orchestrator` | itself (one 8-package cycle at package level, acyclic per module) | everything | Unchanged. Imports no descriptor and no strategy leaf of another layer. |
| `reporting` | foundation | `cli_support`, `cli_workspace`, `cli` | Unchanged. Replay leaves are new modules inside it. |
| `evaluation` | foundation | `cli` | Newly reaches `workspace` and `reporting` through the descriptor, exactly as A does. |
| `cli_support`, `cli_composition` | foundation, `reporting` | `cli_workspace`, `cli`, the CLI leaves | Unchanged. |
| `cli_workspace_<s>` leaves, `cli_strategy_wiring` | foundation, `reporting`, `cli_support`, `cli_composition` | `cli`, `cli_workspace` | New, CLI layer. |
| `strategy_wiring` (composition root) | foundation, `reporting` | `cli`, `cli_strategy_wiring`, `evaluation` | New. No foundation or reporting module imports it. |

The rule that replaces design test T13 is one line: no module under `src/data`, `src/workspace`,
`src/orchestrator`, `src/reporting`, `src/analysis`, `src/core` or `src/config` imports
`src.strategy_wiring`, including through a parent package.

## 5. Amendments if D is adopted

Nothing here is applied. "Required" means the step is needed for the design to hold; "locality" means it
moves strategy code out of a generic module and can be deferred without breaking anything. No amendment
changes the SWC sequence table or any status.

### 5.1 Design document

| Section | Amendment |
| :--- | :--- |
| §1 At a glance | Replace "consumer-owned keyed tables" with the root-descriptor shape. Replace the 23-site claim with Appendix D, table D.4. |
| §2 Decisions | D1: location is the composition root. D2: `evidence` field becomes `behavior`; field count stays 13. D3: `StrategyBehavior[SelT, ResultT]` replaces `EvidenceCodec`. D5 reversed: handlers, executors, projectors, parsers, builders and native-status functions are behavior members; the generic dispatchers receive injected mappings. Add two decisions: two-tier CLI bundle; identity constants live in the envelope leaf (SWC.4c). D10: T10 reduced to the surfaces in Appendix E. D13: re-run the Step 3.5 fit check against the new field. |
| §3.1 Fields | Replace `evidence` with `behavior`; list which slice adds each `StrategyBehavior` member (SWC.2b: `result_type`, `native_status`, `handler`; SWC.3: `selection_type`, `parse`, `encode`, `decode`, `ticker_of`; SWC.4c: `project`). `build` and `refresh` belong to the CLI tier. |
| §3.2 Exclusions | Remove handlers, executors, replay projectors, selection parsers and builders from the excluded list. Still excluded: capture types, outcome classifiers, presenters, analyzers, config types, dependencies, clocks. |
| §4 Static declaration | Location and import direction rewritten per §4 of this study. New prerequisite: `src/workspace/__init__.py` emptied (zero importers of its names today). The allow-list in the T13 description becomes the one-line rule above. |
| §5 BaseAnalyzer | Add: a handler binder constructs the handler from injected dependencies; `BaseAnalyzer` and `AnalysisContext` are untouched (T17 unchanged). |
| §6 Generic consumers | Replace "Stays explicit" with "Receives by injection" for each row (Appendix B). |
| §7 Escape hatches | Native-status row: absence is an explicit function returning `None`, not an optional field. Add the Step 3.5 views row: no descriptor. |
| §8 Typing form | Replace the chosen form with `StrategyBehavior` and its erased `BehaviorView`; add two lessons from the prototype: protocol parameters of single-argument functions are positional-only; keep the explicit type argument at each declaration. |
| §9.2 Fail-closed | Add: an injected mapping with no entry raises `UndeclaredStrategyError`; a behavior given an object of the wrong type raises it too (exact `isinstance` guard). Exceptions and messages for valid callers unchanged. |
| §10 Conformance | T4 compares the enum, the argument models and the union only (registration is derived). T10 reduced (Appendix E). T12 re-based on the remaining surfaces plus a descriptor-incompleteness check. T13 rewritten. T15 and T16 follow the field set. Add a replay test for every descriptor. |
| §11 Migration | Per-slice rows as in §5.2. |
| §12 Drift checks | A5 and A11 reworded: handler, executor and projector are permitted as `behavior` members; capture types and classifiers still escalate. Add A12: a module below the composition root imports `strategy_wiring`. |
| §15 Corrections | Add row 11: SWC.1 Appendix C and T13 ignore parent-package initialization (Appendix J). Add row 12: plan §3.2 references are now used for handlers, executors and projectors. |
| §16 Fit check | Add: every strategy slice supplies the `behavior` members; the Magic Formula ranked view and the side-by-side table have no descriptor. |
| §17 Edit sites | Replace with Appendix D, table D.4. |
| §18 Findings | Add: `src/workspace/__init__.py` re-exports are removed, owner SWC.2a. |
| Appendix A.2 | The `src/workspace/__init__.py` row changes from "kept" to "deleted". |
| Appendix C | Add the parent-package method and the variants of Appendix A. |

### 5.2 Plan and slices

| Slice | Required | Locality |
| :--- | :--- | :--- |
| SWC.2a | Empty `src/workspace/__init__.py`. Move `AnalysisToolDependencies` and its two helper methods to `src/orchestrator/tool_runtime.py`. | Place each arguments model in `src/orchestrator/<s>_tool.py` instead of one `analysis_tool_arguments.py`; the shared base and the two float aliases go to `analysis_tool_arguments.py`. |
| SWC.2b | Create `src/strategy_wiring.py` at the root with `behavior` carrying `result_type`, `native_status` and `handler`. `register_analysis_tools` takes the injected mapping. Delete `_native_status` and its FCF default; each strategy supplies a native-status function (Momentum's returns `None`). Evaluation modules import the descriptor. | Move the four handler methods to `src/orchestrator/<s>_tool.py`. |
| SWC.3 | `encode_evidence`, `decode_evidence`, `execute` and `parse_selection` receive injected mappings. `SQLiteWatchlistRepository` receives the alias resolver at construction (ten constructions in `src`, through one helper in `cli_workspace.py`). `refresh_watchlist` receives the executor lookup. Selection builder and refresh executor move to `src/cli_workspace_<s>.py`; create `src/cli_strategy_wiring.py`. `method_aliases.py` deleted as designed. | Selection classes and parsers move to `src/workspace/<s>_selection.py` plus a shared `selection_base.py`; `ExecutionCapture` moves to `src/workspace/capture.py` and each `from_*_capture` moves into its adapter. |
| SWC.4a | None. | None. |
| SWC.4b | None. | None. |
| SWC.4c | Envelope leaves hold the identity constants; the four presenters and `cli_support` do not import the descriptor. `project_run` receives the injected replay and codec mappings. | Projectors move to `src/reporting/<s>_replay.py`; `ReplayOptions` and `UnsupportedProjectionError` move to `src/reporting/replay_inputs.py`; the two Graham projectors share `graham_replay_shared.py`. |
| SWC.5 | Contributor guide carries table D.4. T13 rule. `AGENTS.md` §3 line unchanged. | None. |

Test files touched: 14 modules call the changed signatures, and with the locality moves 16 import selection
classes from their new homes; 18 distinct test modules in total (and 11 modules in `src`).

## 6. Scope limits and constraint check

- This study made no change under `src/`, `tests/`, `scripts/`, `config/`, `alembic/`, `pyproject.toml` or
  `uv.lock`, and applied none of its amendments. It changed no sequence table or status.
- No option uses discovery, self-registration, a registering decorator, plugin loading, a descriptor
  subclass hierarchy or a common result type. The tuple stays closed and source-declared; the generic
  `StrategyBehavior` is one frozen dataclass, not a hierarchy, and is erased behind a `Protocol` exactly as
  SWC.1 erased `EvidenceCodec`.
- `BaseAnalyzer` and `AnalysisContext` are untouched in every option (T17 unchanged).
- Dispatch stays fail-closed in every option ([Appendix I](#appendix-i-agent-tooling)).
- No formula or classification changes; no stored shape changes (no selection, evidence, result or run
  version bumps).
- Where the goal could not be reached (one package, one descriptor) the reason is a typing or layering
  fact, not a relaxed constraint: the four type lists cannot be derived under `mypy --strict`
  ([Appendix G](#appendix-g-residual-type-lists)), and evaluation fixtures are evaluation truth
  ([Appendix D](#appendix-d-edit-sites)).

## Appendix A: Import-graph evidence

**Method.** The Appendix C script of the SWC.1 design parses every module under `src` and finds strongly
connected components. This study extends it to function level: each top-level definition, and each member
of the one class that is split, has its own set of referenced names, resolved through the original file's
import table. A move relocates a definition to a named module; its outgoing edges follow it, and edges the
remaining definitions no longer need are dropped. With no moves the model reproduces the current graph
exactly (163 modules, no cycles, identical edge sets for the six touched files). It models import
statements, not execution, so it does not show runtime import order; the second metric below does.

Two metrics are reported. The **module cycle** count matches the SWC.1 method. The **initialization-aware
cycle** adds an edge from each module to every parent package `__init__` that exists, because Python runs a
package's `__init__.py` before any module inside it; the baseline has twelve such components, all benign
because they pass through re-exporting `__init__` files.

### A.1 Results

| Variant | Modules | Module cycles | Importers of the descriptor (foundation or reporting) | Modules reachable from it | Init-aware cycle with the descriptor |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Baseline `main` | 163 | 0 | n/a | n/a | n/a |
| A (design as merged) | 170 | 0 | 19 (11) | 53 | 9 modules |
| B, naive: descriptor references the new leaves, presenters and `cli_support` still import it | 190 | 1, of 23 modules | n/a | n/a | n/a |
| B, with six fixes | 192 | 0 | 12 (5) | 121 | 25 modules |
| B', B with the CLI functions in a second tier | 193 | 0 | 12 (5) | 80 | 15 modules |
| C | as B | as B | as B | as B | as B |
| D, single tier | 192 | 0 | 6 (0) | 121 | none |
| D, two tier (recommended) | 193 | 0 | 6 (0) | 80 | none |

The six importers of the descriptor in D are `cli`, `cli_workspace` or `cli_strategy_wiring`, and four
`evaluation` modules (`catalog`, `composition`, `ollama_runner`, `runner`).

### A.2 Package-level reach

For each top-level package, the packages its modules newly reach compared with `main`:

| Package | A | B (six fixes) | D two-tier |
| :--- | :--- | :--- | :--- |
| `data` | `reporting` (4 envelope leaves) | `reporting`, `cli_support`, `cli_composition`, 4 CLI leaves | none |
| `workspace` | `reporting` (4 leaves) | as `data` | none |
| `orchestrator` | `reporting` (4 leaves), `workspace` | as `data`, plus `workspace` | none |
| `reporting` | none | `cli_support`, `cli_composition`, 4 CLI leaves | none |
| `evaluation` | `reporting`, `workspace` | as `data`, plus `workspace` | `reporting`, `workspace` |

On `main` the foundation layers never reach `reporting` or a CLI module, and `reporting` is imported only by
`cli_support`, `cli_workspace` and `cli`. B breaks both statements; A bends the first through four
dependency-free leaves; D keeps both.

### A.3 Why B needs six fixes and D needs one

Each row adds the named edge to the otherwise acyclic graph and reports the cycles. Both B and D also move
the CLI functions out of `cli_workspace.py` and the status table out of `evaluation/runner.py`, because
those two modules import the descriptor and would otherwise be in a cycle with it (checked: the descriptor
importing `evaluation.runner` closes a two-module cycle).

| Fix | Reintroduced edge | B | D |
| :--- | :--- | :--- | :--- |
| Selection classes leave `requests.py` | descriptor to `requests.py` for the parsers | cycle | no cycle |
| `ExecutionCapture` and normalizers leave `execution.py` | CLI leaves to `execution.py` | cycle | no cycle |
| `AnalysisToolDependencies` leaves `analysis_tools.py` | handler leaves to `analysis_tools.py` | cycle | no cycle |
| `ReplayOptions` and `UnsupportedProjectionError` leave `analysis_runs.py` | replay leaves to `analysis_runs.py` | cycle | no cycle |
| Projectors take decoded evidence, not the run | replay leaves to `codecs.py` | cycle | no cycle |
| Presenters read identity from a dependency-free leaf | presenters to the descriptor | cycle | cycle |
| `cli_support` reads identity from the same leaf | `cli_support` to the descriptor | cycle | cycle |

The first cycle B hits is `strategy_wiring` to `fcf_growth_replay` to `reporting.fcf_earnings_growth` back
to `strategy_wiring`: the presenter imports the descriptor for its `analysis` and `method` strings, and the
replay leaf imports the presenter. The last two rows are the same fix: a dependency-free identity module.
Under SWC.4c the envelope leaf, which already imports only `pydantic` and `core`, is its natural home.

### A.4 Initialization-aware hazard

Emptying `src/workspace/__init__.py` removes the initialization-aware cycle in A, B and B'. D is immune
without it, because nothing under `workspace` imports the descriptor. Appendix J records the runtime
reproduction.

### A.5 Strategy independence under C

In the B' graph, no strategy-owned module imports another strategy's: the cross-strategy edge list is
empty. The generic modules that still import strategy-owned modules directly are `cli` (direct commands),
`cli_composition` (Graham resolver builders, shared by two strategies), `cli_workspace` (Momentum window
defaults), `evaluation.catalog`, `evaluation.composition` and `evaluation.runner` (cases, fixtures, result
extraction), `orchestrator.tool_runtime` (the dependency bundle), `reporting.graham_replay_shared`,
`workspace.native_evidence` and `workspace.requests` (the type lists). So C's rule "generic layers import
nothing strategy-specific except through the descriptor" holds for the dispatchers but not for these ten,
which exist because of the type lists, fixtures, the direct commands and the Graham family
([Appendix G](#appendix-g-residual-type-lists)).

### A.6 Layering rules, by option

| Option | Rule that changes |
| :--- | :--- |
| A | Foundation may reach `reporting` through the four envelope leaves. SWC.1 accepted this implicitly; it should be stated. |
| B | Foundation and `reporting` may import `cli_support`, `cli_composition` and the CLI leaves, and `typer`; foundation may import `reporting`. |
| C | B, and a package may span layers, so import direction must be stated per module role rather than per folder. |
| D | None for foundation and `reporting`. `evaluation` may import the composition root, as in A. |

## Appendix B: Dependencies of each moved function

| Function | Needs at runtime | Receives it by | Imports a generic consumer? |
| :--- | :--- | :--- | :--- |
| Tool handler (4) | The strategy's analyzer, provider ids, injected clock, optional profile resolver, argument model, `AnalysisContext` | Constructed with `AnalysisToolDependencies` through a binder, as `AnalysisToolHandlers(dependencies)` does today; the bundle moves to a leaf | No: `analysis_tools.py` imports the leaf, not the reverse |
| Selection parser (4) | The selection class; `settings` for Momentum's default windows | Module-level `settings`, as today | No, once the selection classes leave `requests.py` |
| Selection builder (4) | `cli_support` helpers (`_parse_as_of`, `_canonical_provider_id`, `config_usage_errors`), `typer`, the SEC provider constant, the FCF enums | Direct import of the helpers, as `cli_workspace.py` does today | No: helpers are not the consumer |
| Refresh executor (4) | Production composition: `YFinanceClient()`, `utc_now`, the cache context managers in `cli_support`, `build_graham_resolver`, `growth_assumptions`, `build_sec_production_provider`, the adapter, and the `profile_cache` parameter | Unchanged: each call composes fresh providers; `profile_cache` is passed in | No: it does not import `cli_workspace` |
| Replay projector (4) | Nothing at run time except stored facts: ticker, instrument profile, presentation inputs, decoded evidence, decoded selection, options | Parameters; the caller decodes, replacing the `decode_evidence` call each projector makes today | No, once `ReplayOptions` and the error type move |
| Native-status function (4) | The result object | Parameter | No |
| Codec functions (4) | None | n/a | No (unchanged) |

Dependency injection at construction is preserved for handlers and adapters. The executors are composition
roots that build their own providers per call, exactly as `_execute_*` do today; D neither adds nor removes
an injection point there. Executors and handlers are never called by composition code that bypasses the
analyzer: each ends in `analyzer.run_analysis(ticker, config, context)`.

## Appendix C: Typing prototype

Scratch files under `.tmp/colocation/proto/`, checked with `mypy --strict` (mypy 2.3.1, Python 3.12 target,
the repository's `mypy_path`). The real strategy codecs (`encode_*`, `decode_*`), the real handler methods
and the real `_execute_*` functions are referenced unmodified; the parsers, builders, replay projectors and
status functions were written with their target signatures, and the projector bodies are the current ones
minus the `decode_evidence` call and the run-model access.

**Result.** `behavior.py`, `descriptors.py` and `layers.py` (four strategies, three narrow layer protocols):
`Success: no issues found in 3 source files`. A search of the prototype for `Any`, `cast(` and
`type: ignore` finds only a docstring sentence. The one `Any` that appears in an error message
(`dict[str, Any]`) belongs to the repository's existing `StrictJsonMapping` alias.

**The bundle.** One generic dataclass pairs the selection type and result type with every function that
mentions them, so a cross-concern mispairing is a type error. It is erased once, behind a `Protocol`:

```python
@dataclass(frozen=True)
class StrategyBehavior[SelT: SelectionMember, ResultT: NativeEvidence]:
    selection_type: type[SelT]
    result_type: type[ResultT]
    parse: SelectionParser[SelT]
    build: SelectionBuilder[SelT]
    encode: EncodeFn[ResultT]
    decode: DecodeFn[ResultT]
    ticker_of: TextFn[ResultT]
    native_status: StatusFn[ResultT]
    handler: ToolHandlerFactory[ResultT]
    project: ReplayFn[ResultT, SelT]
    refresh: RefreshExecutor[SelT]
    # parse_for, build_for, encode_object, decode_for, native_status_of, bind_handler,
    # project_for and refresh_for implement BehaviorView; each guards with isinstance
    # against selection_type or result_type, which narrows object without a cast.


MOMENTUM_BEHAVIOR: Final = StrategyBehavior[MomentumSelection, MomentumRun](
    selection_type=MomentumSelection,
    result_type=MomentumRun,
    parse=parse_momentum,
    build=build_momentum,
    encode=encode_momentum,
    decode=decode_momentum,
    ticker_of=momentum_ticker,
    native_status=momentum_status,  # returns None: Momentum has no native status
    handler=momentum_handler,
    project=project_momentum,
    refresh=_execute_momentum,
)

MOMENTUM: Final = StrategyDescriptor(
    "momentum", "sma_crossover", "momentum", ToolName.ANALYZE_MOMENTUM, MomentumToolArguments, MOMENTUM_BEHAVIOR
)
```

The FCF declaration has the same shape with `FCFGrowthSelection` and `FCFEarningsGrowthResult`; Graham
Number and Graham Growth were declared too. The per-concern protocols are `ToolHandlerFn[ResultT]`
(`__call__(self, **raw_arguments: object) -> ResultT`, which the existing handler methods satisfy),
`RefreshExecutor[SelT]` (keyword-only `profile_cache`, which the existing `_execute_*` satisfy unchanged),
`SelectionParser[SelT]`, `SelectionBuilder[SelT]` and `ReplayFn[ResultT, SelT]`. No per-concern bundle like
`EvidenceCodec` is needed: one two-parameter bundle covers all of them and adds the cross-concern pairing
A lacked.

**Layer views.** `layers.py` declares `EvidenceView`, `SelectionView`, `ReplayView` and `ToolView` as
separate `Protocol`s, as the workspace, reporting and orchestrator layers would, and builds each `Mapping`
from `STRATEGIES` at the root: `CODECS: Mapping[StrategyKey, EvidenceView] = {d.key: d.behavior for d in
STRATEGIES}`. It type-checks, including `parse_for` returning a member of the real `AnalysisSelection`.

**Mispairings rejected** (`negative.py`; every one was rejected and nothing else was):

| Case | Mispairing | Error |
| :--- | :--- | :--- |
| N1 | FCF projector in a Momentum bundle | `arg-type` on `project` |
| N2 | FCF parser in a Momentum bundle | `arg-type` on `parse` |
| N3 | Native-status function omitted | `call-arg`: missing argument |
| N4 | FCF handler in a Momentum bundle | `arg-type` on `handler` |
| N5 | FCF executor in a Momentum bundle | `arg-type` on `refresh` |
| N6 | `int` as the selection type | `type-var`: not a selection member |
| N7 | `int` as the result type | `type-var`: not in `NativeEvidence` |
| N8 | FCF encoder in a Momentum bundle | `arg-type` on `encode` |
| N9 | FCF selection with a Momentum builder and projector | two `arg-type` errors |

**Second tier.** `tier2.py` types the CLI bundle against the same selection type through a `pair` function
that takes the core bundle and the CLI composition; Momentum and FCF pair correctly, and the one deliberate
mispairing (FCF composition with the Momentum bundle) is rejected. At runtime the `isinstance` guards raise
`UndeclaredStrategyError` for a selection of another strategy and for non-evidence input.

**Lessons.** Protocols for single-argument functions need positional-only parameters (`evidence, /`),
otherwise `mypy` demands the same parameter name as the protocol (eight spurious errors until fixed). As in
SWC.1, write the explicit type argument at each declaration.

## Appendix D: Edit sites

Same 23-row skeleton as SWC.1 design §17 for every option. "Check" is what fails if the row is omitted.
Rows marked **type** fail `mypy --strict` when the descriptor is constructed (and raise `TypeError` when the
dataclass is built at run time); the rest are tests.

### D.1 Option A (current design, unchanged)

Existing files edited: 15. New files: 10 (the analyzer package counted as three). Directories: 11.

The rows are exactly SWC.1 design §17 rows 1 to 23. The existing files edited are: `src/strategy_wiring.py`,
`src/orchestrator/tool_names.py`, `src/orchestrator/analysis_tool_arguments.py`,
`src/orchestrator/analysis_tools.py` (rows 6 and 7), `src/evaluation/composition.py` (rows 5, 20 and 21),
`src/workspace/native_evidence.py`, `src/workspace/requests.py` (rows 9 and 10), `src/cli_workspace.py` (rows
11 and 14), `src/workspace/execution.py` (the normalizer in row 13), `src/cli.py`, `src/reporting/analysis_runs.py`,
`src/evaluation/runner.py`, `src/evaluation/catalog.py`, `docs/user/USAGE.md` and `docs/user/WORKSPACE.md`.

### D.2 Option B (strategy-owned modules, consumers import the descriptor)

Existing files edited: 10. New files: 14. Directories: 11. Restatements: 5 (rows 3, 5, 8, 9, 20).

| # | Site | File | Check |
| :--- | :--- | :--- | :--- |
| 1 | Analyzer package | `src/analysis/strategy/x/` | T3 |
| 2 | Descriptor and `STRATEGIES` entry, naming every behavior function | `src/strategy_wiring.py` | T1, T2, T3 |
| 3 | `ToolName` member | `src/orchestrator/tool_names.py` | T4 |
| 4 | Arguments model | `src/orchestrator/x_tool.py` | **type** (`tool_arguments`), T4 |
| 5 | `AnalysisToolArguments` union | `src/evaluation/composition.py` | T4 |
| 6 | Handler and binder | `src/orchestrator/x_tool.py` | **type** (`handler`) |
| 7 | Dependency bundle fields | `src/orchestrator/tool_runtime.py` | mypy in the handler; T6 |
| 8 | `NativeEvidence` union | `src/workspace/native_evidence.py` | **type** (`result_type`), T2 |
| 9 | Selection class (parser inside); union member | `src/workspace/x_selection.py`; `src/workspace/requests.py` | **type** (`selection_type`), T1 |
| 10 | Parser | `src/workspace/x_selection.py` | **type** (`parse`) |
| 11 | Builder | `src/cli_workspace_x.py` | **type** (`build`) |
| 12 | Codec and native-status function | `src/workspace/x.py` | **type** (`encode`, `decode`, `native_status`), T8 |
| 13 | Adapter, capture, normalizer | `src/workspace/x_execution.py` | T22 |
| 14 | Refresh executor | `src/cli_workspace_x.py` | **type** (`refresh`) |
| 15 | Direct command | `src/cli.py` | T7, T22 |
| 16 | Presenter and JSON builder | `src/reporting/x.py` | T9 |
| 17 | Envelope model and identity constants | `src/reporting/envelopes/x.py` | T21 |
| 18 | Replay projector | `src/reporting/x_replay.py` | **type** (`project`), replay test |
| 19 | Native-status function (same file as row 12) | `src/workspace/x.py` | **type** (`native_status`) |
| 20 | Fixture requirement | `src/evaluation/composition.py` | T10 `fixture requirements` |
| 21 | Fixture composition | `src/evaluation/composition.py` | T6 |
| 22 | Fixtures, cases, catalog | `src/evaluation/fixtures/x.py`, `src/evaluation/cases/x.py`, `src/evaluation/catalog.py` | T5, T6 |
| 23 | Documentation | `docs/user/strategies/x.md`, `USAGE.md`, `WORKSPACE.md` | T23, doc link check |

Existing files edited: `strategy_wiring.py`, `tool_names.py`, `composition.py`, `tool_runtime.py`,
`native_evidence.py`, `requests.py`, `cli.py`, `catalog.py`, `USAGE.md`, `WORKSPACE.md`.

### D.3 Option C (one package per strategy)

Existing files edited: 10, the same set as B. New files: 15 (twelve in `src/strategies/x/`, plus fixtures,
the case module and the guide). Directories: 9. Restatements: 5.

The rows are B's, with every strategy-owned file under `src/strategies/x/` (`config.py`, `analyzer.py`,
`models.py`, `tool.py`, `selection.py`, `codec.py`, `adapter.py`, `replay.py`, `presenter.py`,
`envelope.py`, `cli_wiring.py`, `descriptor.py`). `src/strategy_wiring.py` gains one import and one tuple
entry; the descriptor itself lives in the package. The directories left are `src`, `src/strategies/x`,
`src/orchestrator`, `src/workspace`, `src/evaluation` (and its `fixtures` and `cases`), `docs/user` and
`docs/user/strategies`.

### D.4 Option D (root descriptor, injected, two tier; recommended)

Existing files edited: 11. New files: 14. Directories: 11. Restatements: 6 (rows 3, 5, 8, 9, 20, 24).
Total sites: 24.

Rows 1 to 23 are table D.2 with these differences: row 2's descriptor names the core behavior members; rows
11 and 14 (builder, executor) are referenced from the CLI tier instead, and the descriptor does not import
them. One row is added.

| # | Site | File | Check |
| :--- | :--- | :--- | :--- |
| 24 | CLI-tier entry pairing the builder and executor with the core bundle | `src/cli_strategy_wiring.py` | **type** (pairing), T10 `cli bundle` |

Rows 11 and 14 fail **type** at row 24 when the function has the wrong selection type, and fail T10
`cli bundle` when row 24 is omitted. The omissions that become type errors in B, C and D are the same seven:
handler, parser, builder, executor, projector, native status, and membership in the selection union.

Existing files edited: the ten above plus `src/cli_strategy_wiring.py`.

## Appendix E: Conformance

Tests are deterministic, make no network, provider or LLM call, and compare the descriptors to surfaces they
do not define. Where a consumer table disappears, the test that compared its key set to the descriptors
disappears with it: a table built from the descriptor cannot disagree with it, so keeping the test would be
tautological.

| T10 surface (design §10.1) | A | B and C | D | Independent surface that remains |
| :--- | :--- | :--- | :--- | :--- |
| Tool registration | table | derived | derived | T4: `ToolName`, argument-model subclasses, `AnalysisToolArguments`, tools registered on a real dispatcher |
| Evaluation routing | table | derived | derived | T5, T6: reviewed case expectations |
| Native status | table | derived | derived | none needed: required function, type error if omitted |
| Fixture requirements | table | table | table | T10 stays; evaluation truth |
| Codecs, versions, labels | table | derived | derived | T8: real evidence round trip |
| Aliases | table | derived | derived | T7: Typer command table; T23: guides |
| Selection parsing | table | derived | derived | T1: `Literal` ids on the hand-written selection classes |
| Watchlist builders | table | derived | derived (CLI tier) | none needed: type error at the pairing |
| Refresh executors | table | derived | derived (CLI tier) | T22 for the save path; the executors need production providers and cannot run in a deterministic test |
| Projectors | table | derived | derived | A replay test per descriptor: replay of a stored run equals the live presenter output |
| JSON ids | surface | surface | surface | T9: rendered documents against the selection `Literal` ids |
| Published schemas | surface | surface | surface | T20, T21 |
| CLI tier | n/a | n/a | surface | T10 `cli bundle` |

T10 surfaces left: A 12, B and C 3 (fixture requirements, JSON ids, schemas), D 4 (those plus the CLI tier).
T1 to T9, T13 to T24 keep their independent surfaces in every option. T9 weakens slightly in B, C and D
because presenters and the descriptor read identity from the same leaf; it still compares the rendered
documents to the selection `Literal` ids, which are a separate declaration.

**Negative control (T12).** It stays meaningful for every surface that remains a table: part 1 (a ghost
descriptor) is reported for fixture requirements, the CLI tier, schemas, guides and the command table; part
2 (one table missing the FCF key) and part 3 (end-to-end `monkeypatch`) apply to the fixture-requirement
table and, in D, the CLI tier. For derived surfaces it moves from "consumer incomplete" to "descriptor
incomplete": the check is that constructing `StrategyBehavior` without a field raises `TypeError` (a cheap
runtime test); the `mypy` mispairings in Appendix C are prototype evidence, as in SWC.1, not a test.

## Appendix F: Heterogeneity

**A strategy that lacks a piece.** Momentum has no native-status classifier. In B, C and D the
`native_status` member is required and Momentum supplies a function returning `None`, which is what
`_native_status` does today. Two alternatives were rejected: an optional field (`None` means absent), which
forces every consumer to branch and makes "absent" indistinguishable from "forgot"; and a closed tuple per
capability, which is a registry shape. Under A the same absence is a table entry returning `None`.

**Step 3.5 views.** The Magic Formula ranked refresh view and the side-by-side table have no evidence, tool,
selection, alias or `--save-run`. They are not strategies and have no descriptor in any option; they are
commands over persisted runs with a typed `--json` model that T21 requires. No field is made optional for
them.

| | A | B | C | D |
| :--- | :--- | :--- | :--- | :--- |
| Piotroski F-Score (one analyzer, nine tests, one result) | Rows 1 to 23; 8 table lines edited in 7 generic files | Rows 1 to 23; 5 restatements; handler, selection, builder, executor and replay each in a new leaf | Same rows, all strategy files in `src/strategies/piotroski/` | As B, plus one CLI-tier entry |
| Piotroski native status | Table entry | Function returning its completeness or execution status string, or `None` if it has none | As B | As B |
| Magic Formula per-ticker analyzer | As Piotroski | As Piotroski | As Piotroski | As Piotroski |
| Magic Formula ranked view | View module in `reporting`, command in `cli.py`, typed document, schema, guide | Same | View module may live in the Magic Formula package; the command stays in `cli.py`; still no descriptor | Same as A |

## Appendix G: Residual type lists

| List | Reduced or co-located? | Why |
| :--- | :--- | :--- |
| `ToolName` | No | A functional `StrEnum` from descriptor strings fails `mypy --strict` (SWC.1 §9.1). It must stay an import-free leaf because `evaluation.models` uses it as a field type. |
| `NativeEvidence` | Not reduced; can share a file with `AnalysisSelection` | It is the bound of `ResultT`. Both are workspace-layer lists, so one file is possible under every option. |
| `AnalysisSelection` | One list serves two purposes | A single hand-written alias, `SelectionMember = A \| B \| ...`, is both the pydantic discriminated union (`Annotated[SelectionMember, Field(discriminator="method_id")]`) and the bound of `SelT`. Checked in `.tmp/colocation/proto2/alias_check.py`: the union parses at run time, and `mypy --strict` rejects `Bundle[int]`. |
| `AnalysisToolArguments` | No | It types `dispatch_fixture_case`; replacing it with `BaseModel` loses the pairing. It cannot join `ToolName` without making that leaf import the argument models. |

No option removes any of the four lists. Under C they cannot move into the package either: `AnalysisRun` is
typed by `AnalysisSelection`, so a module that names the four selection classes must sit below
`workspace.runs`, and a package that imports `cli_support` cannot.

## Appendix H: Cost, slices and the package rename

**Per-strategy code in the four generic modules today** (measured by line span):

| File | Total lines | Strategy-specific lines |
| :--- | :--- | :--- |
| `src/workspace/requests.py` | 514 | 395 (five selection classes, `parse_selection`) |
| `src/orchestrator/analysis_tools.py` | 288 | 136 (four argument models, four handlers) |
| `src/cli_workspace.py` | 1,184 | 211 (builder, helpers, four executors) |
| `src/reporting/analysis_runs.py` | 231 | 118 (four projectors, one helper) |

That is 860 lines, about 215 per strategy. In A, seven more strategies add about 1,500 lines to these files.

**Files.** B and D split six existing files (`requests.py`, `analysis_tools.py`, `execution.py`,
`cli_workspace.py`, `analysis_runs.py`, `evaluation/runner.py`) and rewrite `codecs.py`'s two dispatchers.
They add 23 modules beyond A (Appendix A): four handler leaves, four selection leaves, four replay leaves,
four CLI leaves, and `tool_runtime`, `selection_base`, `capture`, `replay_inputs`, `graham_replay_shared`,
`strategy_identity` (the envelope leaf, in the amendment) and `cli_strategy_wiring`. C moves about 29
existing modules (17 analyzer files across four packages, four codecs, four adapters, four presenters) and
needs the three analyzer-package `__init__.py` files emptied.

**Importers rewritten beyond SWC.2a.**

| Move | `src` files | Test files |
| :--- | :--- | :--- |
| Selection classes leave `requests.py` | 6 | 16 |
| `ExecutionCapture` and normalizers move | 4 | 6 |
| Dependency bundle moves | 2 | 1 |
| `ReplayOptions` and the error type move | 2 | 2 |
| Changed dispatch signatures | 9 | 13 |
| C only: `src.analysis.strategy.*` paths | 33 | 64 |
| C only: codec, adapter and presenter paths | 5 | 24 |
| C only: package-level re-export users | 6 | 7 |

Counts overlap between rows. The distinct importer files (`src` and `tests` together) are 29 for B and D
(11 in `src`, 18 in `tests`) and 105 for C (35 and 70).

**Signatures that change in D (8):** `encode_evidence`, `decode_evidence`, `execute`, `project_run`,
`register_analysis_tools`, `parse_selection`, `refresh_watchlist`, and the `SQLiteWatchlistRepository`
constructor. Each has one to two production callers, all at or above the composition root, except `execute`
(called from `cli._maybe_save_run` and `refresh.py`).

**Stored shape and output.** No option changes a stored shape, a version number, a user-visible message or
a `--json` document beyond the changes SWC.1 already lists. The unreadable-entry message keeps its alias
text in D because the repository receives the alias resolver at construction.

**Interaction with the `src` package rename (PKG).** The PKG plan orders PKG after SWC and before Step 3.5.
PKG is a textual rename of every `src.` import and patch string; it does not depend on where code lives.

| | Together with SWC | After SWC |
| :--- | :--- | :--- |
| A, B, D | No saving: the rename touches each import line regardless. The combined diff cannot be reviewed as move versus rename, and test patch strings (the PKG plan's named risk) would change twice. | PKG rewrites the 23 additional modules (B, D) mechanically. |
| C | A real saving: C rewrites 105 importer files whose lines PKG also rewrites, so each line is edited once. | Each of those lines is edited twice. |

Recommendation: do D before PKG, as sequenced. Doing C together with PKG is the only combination that saves
work, and it is the one that adds the most review risk; D does not need it.

## Appendix I: Agent tooling

- **Closed and static.** In every option `STRATEGIES` is a module-level tuple of module-level constants. In
  A, `register_analysis_tools` iterates it. In D, the composition root builds the tool mapping from it and
  passes it to `register_analysis_tools`; registration order is declaration order. Nothing discovers,
  registers itself or loads plugins.
- **Tool names, schemas, reason codes.** Tool names stay the `ToolName` members. The argument models, the
  `tool_description` field and so the Ollama tool-schema JSON and parser are read from the same fields as in
  A. The `FailureReasonCode` set and T18 are untouched; the fail-closed errors keep their classes and
  messages for valid callers.
- **Fail-closed.** A descriptor tool with no handler entry raises `UndeclaredStrategyError` at registration
  in A; in D it cannot be constructed (a required member), and a mapping missing a key raises the same
  error at the consumer. Lookup is by exact type, so a subclass is never routed.
- **Unchanged tests.** T4, T5, T6, T11, T17 and T18 apply as written, apart from T4 no longer comparing a
  derived registration surface.

## Appendix J: Findings in the SWC.1 design

**J1. A package-initialization cycle in the merged design (defect).** Appendix C and test T13 model each
import statement as an edge to the named module only. Python also runs each parent package's
`__init__.py` first. `src/workspace/__init__.py` imports `src.workspace.requests`; under the design,
`requests.py` imports the descriptor module (SWC.3: `parse_selection` alias membership); and the descriptor
imports `src.workspace.momentum` and the other codec modules. Counting parent packages, the descriptor is in
a cycle with `src.workspace` and seven of its modules (Appendix A.1: 9 modules in all).

A reproduction with the same shape (`pkg/__init__.py` imports `pkg.req`, which imports `wiring`, which
imports `pkg.codec`): importing `wiring` first raises `ImportError: cannot import name 'BY_ALIAS' from 'wiring'`;
importing `pkg.req` or `pkg.codec` first succeeds. The failure is therefore
order-dependent, and a test module whose first project import is the descriptor module triggers it.

Fix, under A or any option except D: empty `src/workspace/__init__.py`. A search of `src/` and `tests/` for
`from src.workspace import` finds no importer of its names, and design Appendix A.2 currently lists those
re-exports as "kept". Extend T13 to add parent-package edges. D is immune because nothing under `workspace`
imports the descriptor.

**J2. The §17 conclusion is narrower than stated.** "Cannot move into the descriptor because of import
cycles" holds for a descriptor that the foundation layers import. The cycles come from that direction, not
from where the functions live: Appendix C's variants V3 and V4 fail because `analysis_runs.py` and
`cli_workspace.py` are consumers as well as containers. With the descriptor at the root and the consumers
injected, those containers can be referenced where they are (a minimal form of D has no cycle, measured with
only the CLI functions and the status table moved). The sentence in §17 should say "under consumer-imports
direction".

**J3. Presenters must not import a descriptor that references them.** Design §6 has the SWC.4c builders read
`analysis` and `method` from the descriptor. That is acyclic under A only because the descriptor does not
reference replay or presentation code. If any future change lets it, the presenters must read identity from
a dependency-free leaf, as in Appendix A.3.

Nothing else in the design was found inconsistent. The model reproduces design §4's claim of no module-level
cycle in A, and reproduces the §17 count of 23 sites and the file set in table D.1.

## Appendix K: Reproduction

Scratch files, ignored by git, under `.tmp/colocation/`: `colo.py` (the function-level model),
`variants.py` (options A, B, B', D), `sites.py` (the edit-site counts), `proto/` (the typing prototype and
its negative controls), `proto2/alias_check.py` (the selection-list check) and `toy/` (the initialization
reproduction). Run from the repository root with `py -3 .tmp/colocation/variants.py`, and the prototype with
`uv run --no-sync mypy --config-file .tmp/colocation/mypy.ini .tmp/colocation/proto/behavior.py
.tmp/colocation/proto/descriptors.py .tmp/colocation/proto/layers.py`.
