# SWC.1 — Descriptor Contract and Conformance Design

Settles the descriptor, failure-envelope and conformance contracts that SWC.2a onward implement. The
[SWC plan](SWC_CONTRACT_AND_SLICE_PLAN.md) owns scope, sequence and status; this document owns the
design detail. Nothing under `src/`, `tests/`, `scripts/`, `config/`, `alembic/`, `pyproject.toml` or
`uv.lock` changes in SWC.1. The design was revised once after merge, when the project owner adopted the
co-location result recorded in [Appendix E](#appendix-e-adoption-of-the-co-location-result); this document
owns that result and is complete without the study.

## 1. At a glance

- **What it settles:** the descriptor's exact fields and exclusions, where it lives and how consumers
  reach it, its relation to `BaseAnalyzer`, each generic consumer, the typing form (proved with
  `mypy --strict` prototypes), the conformance tests and their negative control, the per-slice
  migration, the framework-drift checks, the contributor tooling, the typed failure envelope and the
  typed model and schema for every `--json` document.
- **The shape in one sentence:** one frozen, non-generic `StrategyDescriptor` per strategy, declared in a
  closed tuple in `src/strategy_wiring.py` at the composition root, holding identity, vocabulary, versions
  and one typed `StrategyBehavior[SelT, ResultT, DepsT]` bundle that pairs every strategy-owned function
  mentioning the selection or result type; two further closed tuples, one in the CLI layer and one in the
  evaluation layer, pair the functions only those layers can import with the same bundle's types; generic
  consumers below the root never import any of the three, and receive the slice they need by injection.
- **What it is not:** a registry, plugin point or factory. No discovery, no registration function or
  decorator, no descriptor subclass, no common result type. `BaseAnalyzer[ConfigT, ResultT]`,
  `AnalysisContext` and every strategy's config and result type are untouched
  ([§5](#5-relation-to-baseanalyzer)).
- **Rules it follows:** no formula or classification change; fail closed with no default strategy; no
  stored-shape change; no compatibility re-exports; every field has an audited consumer; no module
  below the composition root imports a descriptor module; strategy-owned files live in one package per
  strategy and obey a role-based layering rule; every design question ends in a decision.
- **Fit and cost:** the design holds for all seven Step 3.5 strategies; one behavior member, `headline`, is added by
  Step 3.5 slice 3.5.0, before any new strategy slice ([§16](#16-step-35-fit-check)). Adding a strategy takes 18 hand-edit sites in 21
  files across 8 directories, six of them files that already exist and five of those edited by a generator
  ([§17](#17-edit-sites-for-a-new-strategy)); a site-status command reports what is missing
  ([§19](#19-contributor-tooling)).
- **Corrections to the plan:** [§15](#15-ir2-and-corrections-to-the-plan) lists where the audit disagreed
  with the SWC plan and what changed.
- **Where the dry material lives:** the re-verified inventory is in
  [Appendix A](#appendix-a-inventory-re-verified-at-247ecdf), the typing evidence in
  [Appendix B](#appendix-b-typing-form-comparison-and-prototype-evidence), the import-graph evidence in
  [Appendix C](#appendix-c-import-cycle-evidence), the current failure shapes in
  [Appendix D](#appendix-d-current-failure-shapes) and the adoption record in
  [Appendix E](#appendix-e-adoption-of-the-co-location-result).

## 2. Decisions

| # | Decision | Detail |
| :--- | :--- | :--- |
| D1 | One non-generic frozen `StrategyDescriptor` per strategy, in a closed tuple `STRATEGIES` in `src/strategy_wiring.py`, the composition root. No module under `src/data`, `src/workspace`, `src/orchestrator`, `src/reporting`, `src/analysis`, `src/core` or `src/config` imports it. | [§3](#3-descriptor-fields-and-exclusions), [§4](#4-static-declaration-model) |
| D2 | Thirteen fields, each with an audited consumer, introduced by the slice whose consumer needs it. The `behavior` field replaces the earlier `evidence` field. | [§3.1](#31-fields) |
| D3 | `StrategyBehavior[SelT, ResultT, DepsT]` is one generic frozen dataclass, erased behind a `Protocol` view; it replaces `EvidenceCodec`. | [§8](#8-typing-form) |
| D4 | `ToolName` stays a hand-written `StrEnum`. `AnalysisToolArguments` becomes the existing shared arguments base class and the four-model union is deleted. Moved symbols keep no compatibility re-export. | [§9.1](#91-toolname) |
| D5 | Handlers, selection parsers, native-status functions and replay projectors are `behavior` members. Selection builders, refresh executors and direct commands are members of a CLI-tier tuple; fixture composition and fixture requirements are members of an evaluation-tier tuple. Generic consumers receive injected mappings. | [§6](#6-generic-consumers), [§4](#4-static-declaration-model) |
| D6 | Dispatch fails closed through one `UndeclaredStrategyError`, defined in `src/core/strategy_errors.py` so every layer can raise it; no strategy is a default branch anywhere. | [§9.2](#92-fail-closed-dispatch) |
| D7 | One shared `FailureEnvelope` for direct and workspace `--json` failures. `DatabaseMaintenanceReport` is a sibling that adopts the envelope's field names. | [§13](#13-failure-envelope-contract) |
| D8 | Momentum profile composition becomes `compose_momentum_profile` in `src/strategies/momentum/execution.py`. | [§14](#14-momentum-profile-composition-helper) |
| D9 | No IR.2 contract change is required. | [§15](#15-ir2-and-corrections-to-the-plan) |
| D10 | Conformance compares the descriptors and both tiers to independent surfaces, and its negative control runs on a checked-in specimen strategy. | [§10](#10-conformance-tests-and-negative-control) |
| D11 | Every `--json` document gets a typed model and a checked-in generated schema. SWC.4 is split into SWC.4a, SWC.4b and SWC.4c. | [§11](#11-migration-from-current-declarations), [§13.6](#136-every-json-document-is-typed) |
| D12 | Per-job failures in `refresh --json` carry a `reason_code` from the same vocabulary, alongside their existing text. | [§13.4](#134-what-changes) |
| D13 | The design fits all seven Step 3.5 strategies. The side-by-side table's per-strategy headline content is one new behavior member, `headline`, added by Step 3.5 slice 3.5.0, which builds the table first over the four existing strategies. | [§16](#16-step-35-fit-check), [§3.3](#33-behavior-members-and-the-two-tiers) |
| D14 | Every finding the audit left unowned is assigned to a slice. | [§18](#18-findings-assigned-to-a-slice) |
| D15 | `src/workspace/__init__.py` is emptied, and the layering test counts parent-package initialization. | [§4](#4-static-declaration-model), [Appendix C](#appendix-c-import-cycle-evidence) |
| D16 | Each strategy's direct command lives in its own CLI file. `cli.py` adds the commands by iterating the closed CLI-tier tuple; a strategy file never registers itself. | [§6](#6-generic-consumers), [§12](#12-framework-drift-checks) |
| D17 | The strategy lists in `USAGE.md` and `WORKSPACE.md` are generated from the descriptors, with a drift test. | [§19](#19-contributor-tooling) |
| D18 | Contributor tooling: one site-data file, a status command, a generator and a specimen strategy. | [§19](#19-contributor-tooling) |
| D19 | The moves that put each strategy's code in strategy-owned modules, including the relocation of the existing analyzers, codecs, adapters and presenters, are required scope in the slice that owns them. | [§11](#11-migration-from-current-declarations) |
| D20 | Strategy identity constants live in a dependency-free leaf: the strategy's envelope module from SWC.4c. Presenters and failure handling read them there, never from the descriptor. | [§4](#4-static-declaration-model) |
| D21 | Every file a strategy owns, except its fixtures and cases, lives in one package, `src/strategies/<strategy>/`, named by role. A role-based layering rule (T13) replaces the folder rule, and every `__init__.py` under `src/strategies/` is empty. | [§4](#4-static-declaration-model), [Appendix C.6](#c6-one-package-per-strategy) |

## 3. Descriptor fields and exclusions

### 3.1 Fields

A field exists only because a named consumer needs it, and replaces a named declaration. "Introduced"
is the slice whose consumer first reads it; a later slice adds the field, not SWC.1.

| Field | Type | Introduced | Consumers | Declarations replaced |
| :--- | :--- | :--- | :--- | :--- |
| `analysis_id` | `str` | SWC.2c | The `(analysis_id, method_id)` key of every index; conformance; the run envelope, replay, refresh. | Key literals in `_METHOD_VERSIONS`, `_EXPECTED_VERSIONS`, `project_run` (4 pairs), six `execution_errors(analysis=, method=)` calls, three reporting JSON builders, the string tests inside `decode_evidence`. |
| `method_id` | `str` | SWC.2c | As `analysis_id`; also `RunQuery`, watchlist alias lookup. | As above, plus the values of `ALIAS_METHOD_IDS`. |
| `tool` | `ToolName` | SWC.2c | Tool registration; evaluation routing; the local Ollama runner. | The four `ANALYZE_*_TOOL` constants; the three `_tool_name` isinstance chains. |
| `tool_arguments` | `type[AnalysisToolArguments]` | SWC.2c | The argument-model view; Ollama validation, schema and parser; `tool_for_arguments`. | `ANALYSIS_TOOL_ARGUMENT_MODELS`; the three `_tool_name` chains. |
| `tool_description` | `str` | SWC.2c | Ollama tool-schema JSON and parser registry. | `_TOOL_DESCRIPTIONS`. |
| `behavior` | `BehaviorView` | SWC.2c (first members) | See [§3.3](#33-behavior-members-and-the-two-tiers). | The `encode_evidence` and `decode_evidence` isinstance chains; four inline ticker-identity blocks; the runner's isinstance tuple and `_native_status`; the handler table; the parse and replay chains. |
| `alias` | `str` | SWC.3a | `parse_selection`; `_parse_analysis`; alias-to-method lookups; help text; the generated strategy lists. | `method_aliases.py` (three tables); the alias tuple in `parse_selection`. |
| `label` | `str` | SWC.3a | `encode_evidence` and `decode_evidence` error text; the generated strategy lists. | The two four-way label chains in `codecs.py`. |
| `config_schema_version` | `int` | SWC.3a | `decode_evidence`. | `_EXPECTED_VERSIONS`. |
| `method_version` | `int` | SWC.3a | `execute`; `decode_evidence`. | `_METHOD_VERSIONS`; `_EXPECTED_VERSIONS`. |
| `result_schema_version` | `int` | SWC.3a | `execute`; `decode_evidence`. | `_METHOD_VERSIONS`; `_EXPECTED_VERSIONS`. |
| `evidence_codec_version` | `int` | SWC.3a | `execute` (writes it); `decode_evidence` (checks it). | The literal `1` in `execute` and the `!= 1` test in `decode_evidence`. |
| `json_envelope` | `type[BaseModel]` | SWC.4c | The schema generator; the JSON builders' output-boundary validation. | Nothing today; this is the typed output contract IR.5 moved here. |

Notes:

- **Single source for FCF.** `STRATEGY_ID`, `METHOD_ID`, `METHOD_VERSION` and `SCHEMA_VERSION` already
  exist in the FCF analyzer's models module (`src/strategies/fcf_growth/models.py` after SWC.2a). The FCF descriptor references them
  instead of re-declaring them. Momentum and Graham have no such constants, so their descriptors are the
  declaration (and, from SWC.4c, their envelope leaves hold the identity constants).
- **`config_schema_version` duplicates a selection field on purpose.** Each selection class keeps its
  own `Literal[...]` identifiers and version, which type the `AnalysisSelection` discriminated union.
  Conformance test T1 compares them to the descriptor; it does not remove them.
- **`json_envelope` is the only field with no replaced declaration.** It stays because SWC.4c's generator
  and conformance test both iterate it; if SWC.4c finds otherwise, the field is dropped in that slice and
  the generator keeps a consumer-side list.
- **The guide filename is a rule, not a field.** A strategy's user guide is
  `docs/user/strategies/<ALIAS>.md`, with the alias upper-cased and hyphens replaced by underscores.
  SWC.5 renames `FCF_EARNINGS_GROWTH.md` to `FCF_GROWTH.md` to fit the rule and updates its links.

### 3.2 Exclusions

The descriptor must not hold, and no field may be added for:

- config, policy or selection *types* beyond the `selection_type` that bounds `behavior` (the selection
  union is compared, not derived);
- analyzer classes, analyzer construction, injected dependency instances, provider identifiers, clocks;
- capture types and outcome classifiers (strategy-owned inside the adapter);
- presenters (a replay projector calls one; the descriptor does not name it);
- formulas, thresholds, classification, calculation status, or any strategy policy;
- envelope-wide versions (`run_schema_version`, `projection_version`) and the per-document
  `schema_version` of each JSON builder (owned by `AnalysisRun` and by the envelope models);
- a generic result supertype, a registration function, a discovery hook or a factory.

Handlers, selection parsers, native-status functions and replay projectors are permitted as `behavior`
members, because the injected consumers need them and none of them constructs, discovers or registers
anything.

### 3.3 Behavior members and the two tiers

`StrategyBehavior[SelT, ResultT, DepsT]` pairs the selection type, the result type and the handler's
dependency type with every function that mentions them, so pairing one strategy's function with another
strategy's type is a type error. Each member is introduced by the slice whose consumer needs it.

| Member | Type | Introduced | Consumer |
| :--- | :--- | :--- | :--- |
| `result_type` | `type[ResultT]` | SWC.2c | Result-type membership in evaluation; `encode_object`. |
| `deps_type` | `type[DepsT]` | SWC.2c | Handler binding (exact-type guard on injected dependencies). |
| `handler` | factory from `(DepsT, ToolRuntime)` to a handler returning `ResultT` | SWC.2c | Tool registration. |
| `native_status` | function from `ResultT` to `str \| None` | SWC.2c | The evaluation runner's telemetry status. |
| `selection_type` | `type[SelT]` | SWC.3a | The selection union bound; `parse_for`. |
| `parse` | function from a decoded configuration object to `SelT` | SWC.3a | `parse_selection`. |
| `encode`, `decode`, `ticker_of` | functions over `ResultT` | SWC.3a | `encode_evidence`, `decode_evidence`. |
| `project` | function from replay inputs, `ResultT`, `SelT` and options to text | SWC.4c | `project_run`. |
| `headline` | function from `ResultT` to `Headline` | Step 3.5 slice 3.5.0 | The side-by-side refresh table. |

`native_status` returns the result's explicit result-level status. Step 3.5 gives every new result one
([Step 3.5 shared definitions §2](../step-3.5/STEP_3_5_SHARED_DEFINITIONS.md#result-level-status)); Momentum's
analyzer has none, so its function returns `None`.

**`headline`.** A pure function over a decoded result, kept in the strategy's `replay.py` because the root
may import that role and both functions read decoded evidence for reporting. It returns a `Headline`:

```python
class CellKind(StrEnum):
    NUMBER = "number"
    TEXT = "text"


@dataclass(frozen=True)
class HeadlineCell:
    key: str  # stable, unique within the strategy
    label: str  # column text
    kind: CellKind
    number: float | None  # finite; None for a text cell or an absent value
    text: str | None  # a band, zone or completeness text; None for a number
    unit: str | None  # explicit for every number cell
    status: MetricStatus | CalculationStatus | None  # the metric's own status; None for a text-only field
    reason_code: ReasonCode | None  # set when the status is not ok


@dataclass(frozen=True)
class Headline:
    cells: tuple[HeadlineCell, ...]  # fixed order
    period_end: datetime | None  # None when the strategy has no fiscal period
    taxonomy: str | None  # None when the strategy reads no filing taxonomy
```

The shape was checked on paper against all eleven strategies (four existing, seven new); the cells per
strategy are listed in [Step 3.5 slice inputs §2](../step-3.5/STEP_3_5_SLICE_INPUTS.md#2-350--side-by-side-refresh-table).
Number cells carry the metric's own `MetricStatus` or, for the Graham results, their `CalculationStatus`;
text cells carry none. The member is added by Step 3.5 slice 3.5.0, over the four existing strategies, so it
has a consumer before any new analyzer is written and every new strategy supplies it from the start. That
one slice updates, together, the four existing declarations, the generator's `replay.py` template, the
site data file's row for the replay file, the specimen's replay file and the member set that T15 checks.

The CLI tier (`src/cli_strategy_wiring.py`) holds, per strategy, a `CliComposition[SelT]` with the
selection builder `build`, the refresh executor `refresh` and the direct `command`, paired with the core
bundle by selection type. It exists because those functions import `cli_support`, `typer` and the
production provider composition, which neither the descriptor module nor `evaluation` may import. Members
are introduced by SWC.3b (`build`, `refresh`) and SWC.3c (`command`).

The evaluation tier (`src/evaluation/strategy_fixtures.py`) holds, per strategy, an `EvalComposition[DepsT]`
with the fixture `requirement` and the `compose` function that builds that strategy's dependency bundle
from the case's fixtures, paired with the core bundle by dependency type. It is introduced by SWC.2d.
Fixture values, expected outcomes and case truth stay hand-written and reviewed.

## 4. Static declaration model

- **Location:** `src/strategy_wiring.py`, one module at the composition root. Module-level constants (one
  per strategy) and the closed tuple `STRATEGIES`. Adding a strategy is a source edit to this tuple. The
  CLI tier is the closed tuple `CLI_STRATEGIES` in `src/cli_strategy_wiring.py`; the evaluation tier is the
  closed tuple `EVALUATION_STRATEGIES` in `src/evaluation/strategy_fixtures.py`. Each entry is built by a
  `pair_*` function that takes the strategy's typed core bundle and the layer's composition, so a
  mismatched pairing fails `mypy --strict`.
- **Layout:** every file a strategy owns, except its fixtures and cases, is in one package,
  `src/strategies/<strategy>/`, named for its role. Fixtures and cases stay under `src/evaluation/`.

  | File | Holds | Serves |
  | :--- | :--- | :--- |
  | Analyzer modules (`analyzer.py`, `models.py`, `config.py`, `calculation.py` and the like) | Config, result, analyzer, calculators | `analysis` |
  | `selection.py` | Selection class and parser | `workspace` |
  | `codec.py` | Encode, decode, ticker, native-status function | `workspace` |
  | `execution.py` | Execution adapter, capture type, normalizer | `workspace` |
  | `tool.py` | Arguments model, dependency class, handler | `orchestrator` |
  | `presenter.py` | Presenter and JSON builder | `reporting` |
  | `envelope.py` | Envelope model and identity constants | `reporting` |
  | `replay.py` | Replay projector and `headline` function | `reporting` |
  | `cli.py` | Direct command, selection builder, refresh executor | CLI |
  | `evaluation.py` | Fixture composition and requirement | `evaluation` |

  Code several strategies share has two homes, neither a strategy: `src/strategies/_shared/profile.py`
  (instrument-profile composition used by Graham Number, Graham Growth and FCF-Growth, which imports no
  strategy) and the Graham family package `src/strategies/_graham/` (`replay.py`, `evaluation.py`, used by
  the two Graham strategies, which may import only the analyzer modules of those two). Every
  `__init__.py` under `src/strategies/` is empty.
- **Role rule (test T13):** a file's role is its file name inside the package, so the rule needs no list of
  paths.
  1. *Within a strategy*, a role file may import another file of the same package only if the imported
     role ranks lower. Order, lowest first: envelope and analyzer modules; selection and codec; tool and
     execution; presenter; replay; cli and evaluation. Analyzer modules may import each other. A file never
     imports a role of equal or higher rank.
  2. *Between strategies*, no package imports another. `_shared` imports no strategy or family module.
     `_graham` imports only the analyzer modules of its two members, and only they import it.
  3. *From outside `src/strategies`*, foundation modules (`data`, `workspace`, `orchestrator`, `reporting`,
     `analysis`, `core`, `config`), `cli_support`, `cli_composition`, the other CLI helpers and the generic
     evaluation modules may import only analyzer and selection roles, and none of them imports the root or a
     tier. The root `src/strategy_wiring.py` may import analyzer, codec, envelope, replay, selection and tool
     roles; the CLI tier only `cli`; the evaluation tier only `evaluation`.
  4. No module under `src` imports `tests`.

  The rule was prototyped in the import-graph model: the real graph has no violation and thirteen
  deliberate violations are each rejected ([Appendix C](#appendix-c-import-cycle-evidence)). The existing
  boundary test (only classes may be imported from the analyzer modules by code outside the strategy
  packages) is retargeted to `src/strategies` and stays beside T13.
- **Who imports what:** the root imports the tool, selection, codec, replay, envelope and analyzer roles.
  The CLI tier imports the root and the `cli` files. The evaluation tier imports the root and the
  `evaluation` files. The only importers of the root and the tiers are `cli`, `cli_workspace`,
  `evaluation` and the tiers themselves.
- **Injection:** the root builds read-only `Mapping`s from the tuple (`BY_KEY`, `BY_METHOD_ID`, `BY_ALIAS`,
  `BY_TOOL`, `BY_ARGUMENTS`, `BY_RESULT_TYPE`, and from SWC.4c `BY_ENVELOPE`) and one narrow view per layer,
  for example `EVIDENCE_BY_KEY`, `PARSERS_BY_ALIAS`, `REPLAYS_BY_KEY`, `HANDLERS_BY_TOOL`. Each consuming
  layer declares the `Protocol` it needs; the root's bundle satisfies it. The caller passes the view in as a
  parameter. The builder is a pure function of the tuple, so tests call it on a modified copy, and it
  raises at import if a key repeats. Iteration order is declaration order.
- **Lookup:** each consumer looks up in its injected mapping through one helper in
  `src/core/strategy_errors.py`, which raises `UndeclaredStrategyError`
  ([§9.2](#92-fail-closed-dispatch)). Variants that return `None` serve the two consumers that must keep
  their existing exception types.
- **Identity leaf:** presenters and the strategy CLI files read `analysis` and `method` strings from the
  strategy's dependency-free `envelope.py`, never from the descriptor, because the descriptor reaches the
  presenters through the replay projectors. `cli_support` is generic: the strategy command files pass it
  the identity as arguments.
- **Parent-package initialization:** Python runs a package's `__init__.py` before any module in it, so an
  import graph that ignores parent packages misses cycles. `src/workspace/__init__.py` re-exports names
  from `requests`; no module in `src/` or `tests/` imports those names from the package. SWC.2b empties it,
  and SWC.2a empties the three re-exporting analyzer-package `__init__.py` files as it moves the analyzers.
  Test T13 builds its graph with an edge from each module to every parent `__init__.py` that exists. Eight
  re-exporting package `__init__.py` files take part in benign cycles on `main` once those are gone
  (`data.sec_edgar`, `data.massive`, `data.yfinance`, `schema`, `core.telemetry`, `evaluation`,
  `evaluation.fixtures` and `evaluation.cases`); T13 records exactly those package names and fails for any
  other package whose `__init__.py` imports a module and sits in a cycle.
- **Prerequisite moves, with no compatibility re-exports.** SWC.2a relocates the existing strategy modules
  into `src/strategies/` (analyzers, codecs, adapters, presenters, shared profile composition) and
  retargets 101 importer files. SWC.2b then moves the symbols: `ToolName` to
  `src/orchestrator/tool_names.py`; the shared arguments base (renamed `AnalysisToolArguments`),
  `FiniteFloat` and `PositiveFiniteFloat` to `src/orchestrator/analysis_tool_arguments.py`; each strategy's
  arguments model to its `tool.py`; the five selection classes to each strategy's `selection.py` and their
  shared base to `src/workspace/selection_base.py`; the `NativeEvidence` union, the new `SelectionMember`
  union and the `AnalysisSelection` union to `src/workspace/strategy_types.py`. The importers are updated in
  the same slice: seventeen modules import `ToolName`, eleven the argument models, six in `src` and sixteen
  under `tests` the selection classes, one `NativeEvidence`. No public package export has to stay:
  `src/evaluation/__init__.py` exports `ToolName`, but nothing imports it from the package, so that export
  is removed. `docs/EVALUATIONS.md` and `docs/project/ARCHITECTURE.md` name the moved symbols and are
  updated in SWC.2b.

## 5. Relation to `BaseAnalyzer`

The invocation envelope is unchanged and the descriptor does not enter it.

- `src/analysis/base_analyzer.py` is not edited by any SWC slice. `BaseAnalyzer.run_analysis(self,
  ticker, config, context)` and the four `AnalysisContext` fields (`as_of`, `executed_at`,
  `use_cache`, `instrument_profile`) keep their signatures.
- No descriptor field is typed `ConfigT`, names an analyzer class, or constructs one. A handler is built
  from its injected dependency bundle at registration, builds `AnalysisContext` at its execution boundary,
  and calls `analyzer.run_analysis(ticker=..., config=..., context=...)`. Refresh executors compose their
  own providers per call, as today, and end in the same call.
- The one coupling is declarative: `StrategyBehavior.result_type` must equal the `ResultT` the strategy's
  analyzer declares. Test T3 compares them against each analyzer's own `BaseAnalyzer[ConfigT, ResultT]`
  specialization, so the coupling is checked, not assumed. Test T17 pins the envelope's signature and
  `AnalysisContext` fields.

## 6. Generic consumers

"Receives" is read from the root's injected mapping or view. "Stays strategy-owned" is a function or type
a strategy writes. Every lookup fails closed on a missing key and is checked against the descriptors by
T10 or T11.

| Slice | File and symbol | Receives by injection | Stays strategy-owned |
| :--- | :--- | :--- | :--- |
| SWC.2c | `src/orchestrator/analysis_tools.py`: `register_analysis_tools(dispatcher, handlers)` | A mapping from tool name to bound handler, checked against `ToolName`; `AnalysisToolDependencies`, `AnalysisToolHandlers` and the four `ANALYZE_*_TOOL` constants are deleted. | Each handler and its dependency bundle, in `src/strategies/<strategy>/tool.py`; `ToolRuntime` (clock and profile resolver) is shared. |
| SWC.2c | `src/evaluation/{composition,runner,ollama_runner}.py` (three `_tool_name`, `_TOOL_DESCRIPTIONS`, `_tool_schemas_json`, `_tool_parser`, `_selection_observation`) | Imports the root: `BY_ARGUMENTS` through one `tool_for_arguments`; `tool_description` and `tool_arguments` per tool; ordinary enum lookup replaces the private `_value2member_map_`. | Prompt construction, observation evidence, fixture composition and requirement (moved by SWC.2d). |
| SWC.2c | `src/evaluation/runner.py`: `NativeAnalysisResult`, `_native_result`, `_native_status` | `BY_RESULT_TYPE` membership; each behavior's `native_status` (Momentum's returns `None`, [§7](#7-strategy-specific-escape-hatches)); the duplicate union becomes `NativeEvidence`; the FCF default is gone. | The status function of each strategy. |
| SWC.2d | `src/evaluation/composition.py`: `compose_fixture_dependencies`, `_require_tool_evidence`, `AnalysisToolArguments` union | Evaluation tier: per-strategy `compose` and `requirement`; the union is deleted for the shared base. | Fixture values, expected outcomes and case truth, in `src/strategies/<strategy>/evaluation.py`, `fixtures/` and `cases/`. |
| SWC.2b, SWC.3a | `src/workspace/execution.py`: `NativeEvidence` move; `_METHOD_VERSIONS`, `execute`; `ExecutionCapture` and the four `from_*_capture` | `execute(request, ..., spec)` receives the strategy's versions and `encode_object`; `getattr(selection, "as_of", None)` becomes `selection.as_of`. | `ExecutionCapture` (moved to `src/workspace/capture.py`), each normalizer in its adapter, `NativeEvidence`. |
| SWC.3a | `src/workspace/codecs.py`: `encode_evidence`, `decode_evidence`, `_EXPECTED_VERSIONS` | `encode_evidence(evidence, codecs)` and `decode_evidence(run, codecs)` look up the injected codec by exact type or key; expected versions, label, ticker identity. | Each strategy's `encode_*`/`decode_*`, validation and provenance rules. |
| SWC.3a | `src/workspace/requests.py`: `parse_selection`; `src/workspace/method_aliases.py` | `parse_selection(alias, config_json, parsers)`; the alias vocabulary is the descriptors' `alias`, and `method_aliases.py` is deleted. | Each selection class and parser, in `src/strategies/<strategy>/selection.py`. |
| SWC.3a | `src/data/repositories/watchlists.py`: alias lookup in the unreadable-entry message | The repository receives an alias resolver at construction (ten constructions in `src`, through one helper in `cli_workspace.py`); an unknown stored method falls back to its method id. | The message wording. |
| SWC.3a | `src/workspace/refresh.py` | `refresh_watchlist` receives the run-spec lookup for `execute`, beside the executor it already receives. | Job scheduling and isolation. |
| SWC.3a | `src/cli.py`, `src/cli_workspace.py`: three Momentum composition copies | None. | One `compose_momentum_profile` ([§14](#14-momentum-profile-composition-helper)). |
| SWC.3b | `src/cli_workspace.py`: `_parse_analysis`, `ALIAS_METHOD_IDS` and `alias_for_method_id` uses, `--analysis` help, `_build_selection`, `_refresh_executor`, the four `_execute_*` | The CLI tier supplies the alias vocabulary, `build` and `refresh`; a missing key raises `UndeclaredStrategyError`, replacing the `AssertionError` fallthrough. | The selection builder and refresh executor of each strategy, in `src/strategies/<strategy>/cli.py`. |
| SWC.3c | `src/cli.py`: the four direct commands and their helpers | `cli.py` adds the commands by iterating `CLI_STRATEGIES`. `_maybe_save_run` and `get_cli_run_context` move to `src/cli_run_support.py`. | Each command, in `src/strategies/<strategy>/cli.py`; it uses no decorator and does not import the Typer app. |
| SWC.4a | `src/cli_support.py`: `execution_errors`; `src/reporting/presentation.py`: `analysis_failure_document`; the `execution_errors(analysis=, method=)` calls in the strategy command files | Identity for the envelope (`analysis`, `method`), read from the strategy's identity leaf. | Failure classification. The `analysis == "momentum"` string test becomes an explicit parameter passed by the Momentum command. |
| SWC.4a | `src/cli_workspace.py`: `_fail` and its `--json` call sites; `src/workspace/refresh.py` | None. | One exception-to-code classifier in `src/reporting/failure_classification.py` ([§13](#13-failure-envelope-contract)); `refresh_watchlist` receives it as a parameter. |
| SWC.4b | `src/cli_workspace.py` JSON builders for watchlist, delete outcome, runs list and refresh summary | Nothing per strategy; `method_id` strings stay `str`. | The documents, now typed. `entries[].selection` is typed by the `AnalysisSelection` union ([§13.6](#136-every-json-document-is-typed)). |
| SWC.4c | `src/reporting/analysis_runs.py`: `project_run` | `project_run(run, options, codecs, replays)`; a missing key raises `UnsupportedProjectionError`. | Each projector, in `src/strategies/<strategy>/replay.py`, over decoded evidence and selection. |
| SWC.4c | `src/reporting/{momentum,graham_number,graham_growth}.py` builders | `analysis` and `method` strings from the identity leaf. | Builders and presenters. FCF reads its native ids. |
| SWC.4c | Schema generator and `src/reporting/json_documents.py` | `json_envelope` per strategy. | The failure, workspace and database documents are listed once, outside the descriptor. |

## 7. Strategy-specific escape hatches

A strategy may legitimately differ in the following, and each is expressed by a strategy-owned function or
type, not by an optional field:

| Difference | How it is expressed |
| :--- | :--- |
| Config, selection and result types | Strategy-owned classes; the selection and `NativeEvidence` unions are hand-written and compared by T1 and T2. |
| Config construction from tool arguments | The strategy's handler, which owns validation and config assembly. |
| Dependencies of the handler | A strategy-owned dependency class in its `tool.py`; the shared `ToolRuntime` carries only the clock and the profile resolver. |
| Execution adapter shape and capture type | Strategy-owned `execute_*`/`run_*`, `*Capture` and normalizer; the CLI tier's `refresh` composes the providers and calls the adapter. |
| Outcome classification | Strategy-owned `classify_*_outcome` inside the adapter. The descriptor has no classifier member. |
| Momentum has no native failure-status classifier | Every `native_status` member is required. Momentum's returns `None`, as `_native_status` does today, so absence is an explicit function and nothing is optional. An optional member was rejected: every consumer would branch on `None`, and "absent" could not be told from "forgotten". |
| Evidence ticker location | `ticker_of` (Momentum reads `run.metrics.ticker`; the others read `.ticker`). |
| Profile composition | Graham and FCF share `compose_graham_profile`; Momentum owns `compose_momentum_profile`. |
| Presentation and replay | `render_*` and the projector; projection stays versioned and strategy-owned. |
| Invalid-input detail in failures | A parameter on `execution_errors` set by the Momentum command. |
| Fixture composition and expected outcomes | The evaluation tier's `compose` and `requirement`, `catalog.py` and the case modules stay explicit evaluation truth. |
| Cross-strategy views (ranked view, side-by-side table) | Not strategies: no descriptor. They are commands over persisted runs with a typed `--json` model that T21 requires. The side-by-side table's per-strategy headline content is the `headline` member, added by Step 3.5 slice 3.5.0 ([§3.3](#33-behavior-members-and-the-two-tiers)). |

Anything else a strategy needs outside these hooks is a plan change, not a descriptor member
([§12](#12-framework-drift-checks)).

## 8. Typing form

**Chosen:** a non-generic frozen `StrategyDescriptor` whose `behavior` field holds one generic frozen
dataclass, `StrategyBehavior[SelT, ResultT, DepsT]`, through an erased `Protocol` view. The bounds tie the
selection type to a member of the hand-written `SelectionMember` union, the result type to a member of the
hand-written `NativeEvidence` union, and every function to those types, so pairing a function with another
strategy's type is a type error. Each layer declares the narrow `Protocol` it needs, and the bundle
satisfies all of them.

**Result:** the prototypes (real strategy modules; all four strategies for the core bundle, Momentum and FCF
for the tiers) pass `mypy --strict` with no `Any`, no `cast` and no `type: ignore`. Thirteen deliberate
mispairings are each rejected, and the generic-descriptor and erased forms are shown to need `Any` or
`cast`. Evidence: [Appendix B](#appendix-b-typing-form-comparison-and-prototype-evidence).

Essential sketch (prototype, `.tmp/` only, not committed):

```python
type NativeEvidence = MomentumRun | GrahamNumberAnalysis | GrahamGrowthAnalysis | FCFEarningsGrowthResult
SelectionMember = MomentumSelection | GrahamNumberSelection | GrahamGrowthSelection | FCFGrowthSelection
AnalysisSelection = Annotated[SelectionMember, Field(discriminator="method_id")]


@dataclass(frozen=True)
class StrategyBehavior[SelT: SelectionMember, ResultT: NativeEvidence, DepsT]:
    selection_type: type[SelT]
    result_type: type[ResultT]
    deps_type: type[DepsT]
    parse: SelectionParser[SelT]
    encode: EncodeFn[ResultT]
    decode: DecodeFn[ResultT]
    ticker_of: TextFn[ResultT]
    native_status: StatusFn[ResultT]
    handler: ToolHandlerFactory[DepsT, ResultT]
    project: ReplayFn[ResultT, SelT]
    headline: HeadlineFn[ResultT]  # added by Step 3.5 slice 3.5.0
    # parse_for, encode_object, decode_for, native_status_of, bind_handler, project_for and headline_of implement
    # BehaviorView; each guards with isinstance against selection_type, result_type or deps_type.


@dataclass(frozen=True)
class StrategyDescriptor:  # non-generic: no consumer needs ConfigT
    analysis_id: str
    method_id: str
    alias: str
    label: str
    tool: ToolName
    tool_arguments: type[AnalysisToolArguments]
    tool_description: str
    behavior: BehaviorView
    # plus the four version fields and, from SWC.4c, json_envelope


MOMENTUM_BEHAVIOR: Final = StrategyBehavior[MomentumSelection, MomentumRun, MomentumToolDependencies](...)
```

Points learned from the prototypes that the slices must follow:

- Write the type arguments explicitly (`StrategyBehavior[MomentumSelection, MomentumRun, ...]` at the call).
  Without them, mypy infers the whole union from the `Protocol` field's expected type and rejects every
  declaration.
- Protocol parameters of single-argument functions are positional-only (`evidence, /`); otherwise mypy
  demands the protocol's parameter name from every strategy function.
- The handler protocol is `__call__(self, **raw_arguments: object) -> ResultT`, which the existing handler
  methods satisfy; the refresh-executor protocol has a keyword-only `profile_cache`, which the existing
  `_execute_*` functions satisfy unchanged.
- Do not use `assert isinstance` narrowing inside generic consumers; the bundle's own `isinstance` guard
  narrows `object` without a cast.
- One hand-written `SelectionMember` list is both the bound and the pydantic discriminated union; the union
  parses at run time and `mypy --strict` rejects a non-member.
- A tier pairs with the core bundle through a `pair_*` function whose type parameters tie the two: the CLI
  tier by selection type, the evaluation tier by dependency type. A command is a `Callable[..., None]`
  member; Typer reads its signature, and the closed tuple supplies the names.

## 9. ToolName, fail-closed dispatch

### 9.1 `ToolName`

**Decision:** `ToolName` stays a hand-written `StrEnum`, the single declaration of the tool-name strings.
It lives in `src/orchestrator/tool_names.py`, a leaf with no project imports, because the orchestrator,
the descriptor and `evaluation.models` all need it and it must not pull a strategy into any of them. There
is no re-export: `evaluation/models.py` imports it from its new home like every other importer, and the
`src.evaluation` package export is removed. Each descriptor binds one member in `tool`.

**Why not source the enum from descriptor strings:** a functional `StrEnum(...)` built from descriptor
strings is rejected by `mypy --strict` (`StrEnum() must be ... literal ... to determine Enum members`), and
`ToolName.ANALYZE_MOMENTUM`, used in six case modules and pydantic field types, becomes an attribute error.
Evidence: Appendix B, form C.

**`AnalysisToolArguments`:** the shared base class that every arguments model already inherits becomes the
public `AnalysisToolArguments`; the four-model union in `evaluation/composition.py` is deleted. Every
consumer reads only `ticker`, `as_of` and `model_dump`, which the base defines, and `tool_for_arguments`
routes by exact type, so no typing is lost. `tool_arguments` is typed `type[AnalysisToolArguments]`, which
rejects a class that is not an analysis-tool arguments model.

**What changes in practice:** the second mapping is removed. The four `ANALYZE_*_TOOL` constants,
`ANALYSIS_TOOL_ARGUMENT_MODELS`, the three model-to-member isinstance chains, the union and the
string-keyed `_TOOL_DESCRIPTIONS` all go. The string appears once. T4 checks the enum, the descriptors, the
argument-model subclasses and the registered tools against each other in both directions.

### 9.2 Fail-closed dispatch

One exception, `UndeclaredStrategyError(LookupError)`, defined in `src/core/strategy_errors.py` with a
message that names the key or type that matched nothing and the declared alternatives. No generic consumer
has a fall-through branch.

| Consumer | Undeclared input | Result |
| :--- | :--- | :--- |
| `encode_evidence` | Evidence whose exact type matches no injected codec. | `UndeclaredStrategyError`. It is a programming error, so it is not wrapped as `InvalidStoredRunError`. |
| `decode_evidence` | `(analysis_id, method_id)` with no injected codec. | Existing `UnsupportedRunVersionError`, message and `reason_code` unchanged. |
| `project_run` | A key with no injected projector. | Existing `UnsupportedProjectionError`, message unchanged. |
| CLI tier lookups (`build`, `refresh`) | A selection or alias whose key has no entry. | `UndeclaredStrategyError`, replacing the `AssertionError` fallthrough. |
| `parse_selection` | Unknown alias. | Existing `ValueError("Unknown analysis alias: ...")`, raised when the injected parser mapping has no entry. |
| `tool_for_arguments` | Arguments of an undeclared model type. | `UndeclaredStrategyError`, replacing `TypeError`. |
| Handler registration | A `ToolName` member with no bound handler, or a handler for no member. | `UndeclaredStrategyError` at registration, naming the tool. |
| Evaluation binding | A descriptor tool with no evaluation-tier entry. | `UndeclaredStrategyError`, naming the tool. |
| `evaluation.runner._native_result`, `_native_status` | A result of an undeclared type. | `UndeclaredStrategyError`, replacing today's `TypeError` and the FCF default. |
| A behavior bundle given an object of another strategy's type | Any `*_for` method. | `UndeclaredStrategyError` (exact `isinstance` guard). |

Lookup is by exact type, not `isinstance`, so a subclass of a result type cannot be silently routed. For
valid inputs every path behaves as today; T8 round-trips real evidence for every descriptor.

## 10. Conformance tests and negative control

All tests are deterministic, make no network, provider or LLM call, and live in
`tests/test_strategy_wiring_conformance.py` (new in SWC.2c, extended by later slices) unless noted. Each
check body is a function in `scripts/strategy_conformance.py` that returns gaps; the test asserts none, and
the status command ([§19](#19-contributor-tooling)) prints them, so the two cannot disagree. Every test is
parameterized over the production tuples and over the specimen tuples ([§19.5](#195-specimen-strategy)).

### 10.1 Tests

| Test | Compares the descriptors to | Independent surface | Why it is not tautological |
| :--- | :--- | :--- | :--- |
| T1 `selection_union` | `(analysis_id, method_id, config_schema_version)` of each `get_args(SelectionMember)` member | `Literal` field defaults on the hand-written selection classes | Selections and descriptors are separate declarations. A strategy added to one only fails. |
| T2 `native_evidence_union` | `get_args(NativeEvidence)` against the set of `behavior.result_type` | The hand-written evidence union | Same reasoning; the bundle's bound also fails type-checking on mismatch. |
| T3 `analyzer_generics` | `behavior.result_type` against `ResultT` of every non-abstract `BaseAnalyzer` subclass found by walking `src.strategies` with `pkgutil` (skipping packages whose name starts with an underscore) | The analyzers' own `BaseAnalyzer[ConfigT, ResultT]` specialization | The analyzer defines its result; the descriptor must agree. Enumeration is by package walk, so a new analyzer needs no edit to the test. It also fails for an analyzer found outside `src/strategies`. It also requires exactly one descriptor per analyzer and one analyzer per descriptor. |
| T4 `tool_surfaces` | `tool` and `tool_arguments` against `set(ToolName)`, `AnalysisToolArguments.__subclasses__()` and the names bound for a real dispatcher | Two hand-written surfaces and the dispatcher | A tool in the enum or the subclass set and not in the descriptors fails and names it. Registration itself is derived, so it is no longer a compared surface. |
| T5 `cases_route_to_their_tool` | `tool_for_arguments(request.arguments)` for each catalog request, against the tools its case's expectation requires | Reviewed case expectations in `src/evaluation/cases` | Case truth is written by hand against tool names, not derived from the descriptor. |
| T6 `evaluation_coverage` | Every descriptor tool against the union of tools the golden cases require; the deterministic suite runs every case | The case catalog and the suite's own dispatch | A strategy with no deterministic case, or one the fixture composition cannot serve, fails. |
| T7 `command_table` | Descriptor aliases against the top-level command names of the real Typer app | The CLI's own command table, read from `typer.main.get_command(app)` with hidden groups included | (a) Every top-level command is a descriptor alias, a command group, or listed in the hand-written `NON_STRATEGY_COMMANDS`. (b) An alias never equals a group or non-strategy name. (c) Each strategy command offers `--save-run` and `--json`. Strategy commands are added from the CLI tier, so "every alias is a command" is now derived and is checked through T10's CLI-tier surface instead. |
| T8 `versions_and_round_trip` (SWC.3a; replay added by SWC.4c) | Run envelope versions, decoded evidence and, from SWC.4c, the replayed text for a real result per strategy | Real analyzer output via the golden fixtures, real `AnalysisRun` validation, the live presenter | Behavior, not metadata: `execute` writes, `decode_evidence` reads, and `decoded == original` must hold; the replay of a stored run equals the live presenter's output. |
| T9 `rendered_json_ids` (SWC.4c) | The `analysis` and `method` keys of each rendered `--json` document against the stored selection's `Literal` ids | Real rendered documents from the golden fixtures against the hand-written selection classes | Presenters and the descriptor read identity from the same leaf, so the document is compared to the selection class, which is a separate declaration. |
| T10 `consumers_cover_every_descriptor` | The key set of each remaining consumer surface: CLI tier, evaluation tier, JSON ids, published schemas, generated strategy lists | The tiers' own tuples and the files on disk | Fails when a descriptor has no entry in a tier, naming the surface and the strategy. The surfaces that became derived (tool registration, evaluation routing, native status, codecs, aliases, selection parsing, builders, refresh executors, projectors) are no longer tables, so they are no longer compared. |
| T11 `undeclared_inputs_fail_closed` | Every dispatcher in [§9.2](#92-fail-closed-dispatch) with an undeclared type, key, alias or arguments, and a bundle given another strategy's object | The behavior of the dispatchers over injected mappings, including the specimen | Proves no consumer routes an unknown input to Momentum or FCF. |
| T12 `incomplete_strategy_negative_control` | A deliberately incomplete specimen ([§10.2](#102-negative-control)) | See below | Proves T10 and T11 can fail. |
| T13 `import_layering` (parent-aware graph and role rule from SWC.2a; root rule from SWC.2c) | The import graph of `src`, with an edge from every module to each parent `__init__.py` | The source files | The role rule in [§4](#4-static-declaration-model): within a strategy only a higher-ranked role file imports a lower one; no strategy imports another; `_shared` and `_graham` follow their own rules; foundation, reporting and the other generic modules import only analyzer and selection roles and never the root or a tier; no module imports `tests`; no cycle outside the recorded benign package set. |
| T14 `no_discovery_or_registration` | The AST of `src/strategy_wiring.py`, both tier modules and every strategy-owned file | The source files | See [§12](#12-framework-drift-checks). |
| T15 `descriptor_is_closed` | Field names, types, frozen-ness, non-generic-ness and tuple-ness of the descriptor; member names of the behavior bundle and both tier compositions | `dataclasses.fields` | Adding a field or member forces a reviewed edit to the documented set. |
| T16 `no_unused_field` | Each field and member name against attribute reads on descriptor-typed expressions in `src/` and `scripts/` outside the defining module | The source files, read with a conservative type resolver | A bare name match would be satisfied by an unrelated attribute. The resolver counts `X.field` only when `X` is a loop variable over `STRATEGIES` or `BY_*.values()`, the result of `require(...)`, `find(...)` or `BY_*[...]`, a parameter annotated `StrategyDescriptor`, or one of the module's descriptor constants. A self-test with snippets proves that `descriptor.alias` counts and `selection.alias` does not. |
| T17 `analyzer_envelope_unchanged` | `inspect.signature(BaseAnalyzer.run_analysis)` and `AnalysisContext` fields | The base module | The descriptor work cannot alter the envelope unnoticed. |
| T18 `failure_codes` (SWC.4a) | `FailureReasonCode` against every `ReadinessReason`, every exception `reason_code` attribute, and every code the classifier can return | The source exceptions and enums | A new source code with no envelope code fails. |
| T19 `failure_envelope_closed` (SWC.4a) | Envelope fields against the documented set; no remediation-shaped field | The model | Enforces the report-never-remediate rule. |
| T20 `published_schemas_current` (SWC.4a, extended by 4b and 4c) | Regenerated schema text against `schemas/*.json` | Checked-in files | Drift detection by byte comparison; a missing file fails naming it. |
| T21 `json_commands_are_typed` (SWC.4c) | Every command offering `--json` against the `JSON_DOCUMENTS` table and the checked-in schemas | The command tree of the real Typer app, recursed through every group including hidden ones | The commands come from the CLI's own parameter declarations, the schemas from files on disk, and the table links them. A new `--json` command with no typed model fails with `command 'x' offers --json but has no typed document model`. Today it finds 12 commands. |
| T22 `save_run_through_every_direct_command` (SWC.3c) | For each alias: the real command with `--save-run` against a temporary database and that strategy's fixture providers | The CLI path, real `execute` and the repository | Exactly one stored run whose key equals the descriptor's and which `decode_evidence` accepts. The per-alias fixture setup is hand-written data; a missing entry fails with `no save-run fixture for alias 'x'`. |
| T23 `user_guides` | For each alias: a guide at `docs/user/strategies/<ALIAS>.md` that links to `FINANCE_MATH.md#...` and `GLOSSARY.md` | The documentation files | Anchor validity is enforced by `check_doc_links.py`; a missing link fails T23. The alias mentions in `USAGE.md` and `WORKSPACE.md` are generated and checked by T26. |
| T24 `uniqueness_rules` | A copy of the tuple with one duplicated value, for each of `analysis_id`+`method_id`, `method_id`, `alias`, `tool`, `tool_arguments`, `behavior.result_type` and (SWC.4c) `json_envelope` | The index builder | Each duplicate must raise naming the rule and both descriptors. Import-time failure is the same code path. |
| T25 `site_data_complete` (SWC.5) | The site data file against `scripts/strategy_conformance.py` and the generated guide table | The data file | Every site names a check that exists, every check is named by a site, and the guide's table equals the table regenerated from the file. |
| T26 `generated_lists_current` (SWC.5) | The marked blocks in `USAGE.md` and `WORKSPACE.md` against the blocks regenerated from `STRATEGIES` | Checked-in files | Byte comparison, as T20; a strategy missing from a block fails naming the file. |
| T27 `specimen_complete` (SWC.6) | The status command run on the specimen against the site data file | The specimen's files | The specimen has an artifact for every site, so the tests that run on it exercise every layer. |
| T28 `generator_end_to_end` (SWC.6) | The generator's output in a temporary copy of the repository, filled with trivial bodies | The strict type check and the conformance suite, run as subprocesses in the copy | Proves a new strategy added only through the generator and trivial fills passes both. |
| T29 `no_unfilled_stubs` (SWC.6) | Every call to `unfilled_stub` in `src/` | The source files | Fails naming each file and line, so generator output cannot merge until each stub is replaced. |

The existing `tests/workspace/test_method_aliases.py` is the model for T1. SWC.3a folds it into T1 and T10
when `method_aliases.py` is deleted.

### 10.2 Negative control

Test T12 uses a test-only helper `find_wiring_gaps(descriptors, surfaces)` that asks each named surface
whether it covers each descriptor. The negative control has four parts and must produce this diagnostic,
naming the strategy and each uncovered surface:

```text
strategy ('specimen', 'specimen_method') is not wired in: CLI tier; evaluation tier; published schemas; ...
strategy ('specimen', 'specimen_method') is not wired in: evaluation tier
```

1. **Missing declaration.** A specimen descriptor is added to a copy of the production tuple with no tier
   entries. Every surface that is still a table or a file must be reported for it.
2. **Missing entry in one tier.** The specimen's evaluation-tier entry is removed. Exactly one gap must be
   reported, naming `evaluation tier` and the specimen key, and no other strategy.
3. **End-to-end.** The production T10 body runs against the specimen tuples with one entry missing. It must
   raise `AssertionError` whose message matches the diagnostic above. This proves the shipped test, not
   only the helper, fails on a forgotten entry.
4. **Incomplete descriptor.** Constructing a `StrategyBehavior` without one member raises `TypeError`, and a
   dispatcher given an object of another strategy's type raises `UndeclaredStrategyError`. The `mypy`
   mispairings in Appendix B are prototype evidence, not a test.

## 11. Migration from current declarations

Every slice branches from `main` after its predecessor has merged, never from the predecessor's branch, and
ends with the complete managed quality gate. Opening and merging pull requests still need explicit
approval. Each slice makes its moves in the same change as the consumer it serves.

| Slice | Branch | Files touched | Declarations removed | Order of work |
| :--- | :--- | :--- | :--- | :--- |
| SWC.2a | `feat/swc-2a-strategy-packages` | New: `src/strategies/` with an empty `__init__.py` in it and in each strategy package, the layering test (T13: role rule and parent-package initialization), `src/strategies/_shared/profile.py`. Moved with `git mv` and no content change beyond imports: the 17 analyzer files from `src/analysis/strategy/<package>/` (Momentum's `momentum_analyzer.py` becomes `analyzer.py`), the four codecs (`src/workspace/<strategy>.py` to `codec.py`), the four adapters (`<strategy>_execution.py` to `execution.py`), the four presenters (`src/reporting/<strategy>.py` to `presenter.py`) and `src/workspace/graham_shared.py`. Edited: the 101 importer files (33 in `src`, 68 in `tests`; 15 tests name moved modules in patch strings), `tests/analysis/test_base_analyzer_conformance.py` (the strategy-boundary constants now name `src/strategies`), `docs/project/ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md` (paths). Also new: the patch-target resolution test, a test that every string patch target in `tests/` (the dotted target of `patch(...)`, `patch.object` by name and `monkeypatch.setattr(...)`) resolves to an existing attribute; it runs before the importer rewrite is accepted and the package-rename plan reuses it. | `src/analysis/strategy/` and its three re-exporting `__init__.py` files; the old module paths. | Package skeleton and T13 first, then one strategy at a time (analyzer files, then codec, adapter and presenter), then `_shared/profile.py`, then the importers and the boundary test, then the patch-target resolution test, which must pass over every `tests/` string target. No behavior change and no new symbol. |
| SWC.2b | `feat/swc-2b-symbol-moves` | New: `src/orchestrator/tool_names.py`, `src/orchestrator/analysis_tool_arguments.py`, `src/strategies/<strategy>/tool.py` (arguments only), `src/workspace/selection_base.py`, `src/strategies/<strategy>/selection.py`, `src/workspace/strategy_types.py`. Edited: `src/orchestrator/analysis_tools.py`, `src/workspace/{requests,execution,__init__}.py`, `src/evaluation/{__init__,models,composition,runner,ollama_runner,evaluator,catalog}.py`, the six `src/evaluation/cases/*.py` importers, `src/core/constants.py`, the importers of every moved symbol (tests included), `docs/EVALUATIONS.md`, `docs/project/ARCHITECTURE.md`. | The old definitions of every moved symbol; the `ToolName` export from `src.evaluation`; the `src.workspace` re-exports; `AnalysisType`. | One symbol group at a time (`ToolName`, arguments, selection classes, unions), updating importers and running the gate after each; then `AnalysisType`. No behavior change and no descriptor. |
| SWC.2c | `feat/swc-2c-descriptor-orchestration-wiring` | New: `src/strategy_wiring.py`, `src/core/strategy_errors.py`, `src/orchestrator/tool_runtime.py`, conformance tests and `scripts/strategy_conformance.py`. Edited: `src/orchestrator/analysis_tools.py`, `src/strategies/<strategy>/tool.py` (dependency classes and handlers), `src/evaluation/{composition,runner,ollama_runner}.py`, affected tests. | `AnalysisToolDependencies`, `AnalysisToolHandlers`; the four `ANALYZE_*_TOOL` constants; `ANALYSIS_TOOL_ARGUMENT_MODELS`; three `_tool_name`; `_TOOL_DESCRIPTIONS`; the duplicate `NativeAnalysisResult`; the FCF default in `_native_status`; the private `_value2member_map_` use. | Add the descriptor with T1 (ids), T2 to T6, T11, T13 (root rule), T14 to T17, T24, then move each handler and switch each consumer. Fixture composition stays in `composition.py` as per-strategy functions until SWC.2d. |
| SWC.2d | `feat/swc-2d-evaluation-tier` | New: `src/evaluation/strategy_fixtures.py`, `src/evaluation/fixture_context.py`, `src/evaluation/fixture_ids.py`, `src/strategies/<strategy>/evaluation.py` and `src/strategies/_graham/evaluation.py`. Edited: `src/evaluation/{composition,catalog}.py`, the case modules (reviewed arguments move beside their cases), affected tests. | The per-strategy composition functions and `_require_tool_evidence` in `composition.py`; the `_arguments` chain in `catalog.py`. | Fixture identifiers and shared context first, then one strategy at a time into its evaluation file, then the tier tuple and T10's evaluation-tier surface. No fixture value, expected outcome or score changes. |
| SWC.3a | `feat/swc-3a-workspace-consumers` | `src/strategy_wiring.py`, `src/workspace/{codecs,execution,requests,refresh,capture}.py` (`capture.py` new), the four `src/strategies/<strategy>/execution.py` adapters (each gains its normalizer; Momentum's gains `compose_momentum_profile`), delete `src/workspace/method_aliases.py`, `src/data/repositories/watchlists.py`, `src/cli_workspace.py` (the repository helper), `src/cli.py` (Momentum composition only), tests (T1, T8, T10, T11 extended; `test_method_aliases.py` folded in). | `_METHOD_VERSIONS`; `_EXPECTED_VERSIONS`; both label chains; both codec isinstance chains; `method_aliases.py`; the `parse_selection` alias tuple and Momentum fall-through; the `getattr(selection, "as_of", None)` probe; the Momentum composition copies. | Momentum helper first (independent), then descriptor fields and the `selection_type`, `parse`, `encode`, `decode`, `ticker_of` members, then codecs and execution, then aliases and `parse_selection`, then the repository alias resolver and `refresh_watchlist`. `ExecutionCapture` and the normalizers move here. |
| SWC.3b | `feat/swc-3b-cli-tier` | New: `src/cli_strategy_wiring.py`, `src/strategies/<strategy>/cli.py`. Edited: `src/cli_workspace.py`, tests (T10 CLI-tier surface). | `_build_selection` and its helpers; `_refresh_executor`; the four `_execute_*`; the `--analysis` help literals. | One strategy at a time: selection builder and refresh executor into its `cli.py`, then the tier tuple, then the lookups in `cli_workspace.py`. |
| SWC.3c | `feat/swc-3c-direct-commands` | `src/cli.py`, `src/cli_run_support.py` (new), the four `src/strategies/<strategy>/cli.py`, tests (T7, T22; retargeted patch strings in 13 test modules). | The four `@app.command` functions and their helpers in `cli.py`; `_maybe_save_run` and `get_cli_run_context` leave it. | Shared run helpers first, then one command at a time, then `cli.py` iterating `CLI_STRATEGIES`, then T7 and T22. |
| SWC.4a | `feat/swc-4a-failure-envelope` | New `src/reporting/documents/{__init__,failure,database}.py`, `src/reporting/failure_classification.py`, `scripts/generate_schemas.py`, `schemas/` (failure, database report). Edited: `src/cli_support.py`, `src/reporting/presentation.py`, the `execution_errors` call sites in the strategy `cli.py` files, `src/cli_workspace.py`, `src/cli_database.py`, `src/workspace/refresh.py`, `src/workspace/watchlists.py`, `src/data/repositories/watchlists.py`, `docs/user/DATABASE.md`, tests (T18 to T20). | `analysis_failure_document`'s hand-built dict and its wrong docstring; the `analysis == "momentum"` test; the six literal id pairs in `execution_errors` calls; the duplicate `WatchlistNotFoundError` in `refresh.py`. | Failure model and classifier, then direct commands, then workspace `--json` paths, then `refresh_watchlist`'s injected classifier and per-job codes, then the database report rename, then the generator and T20. |
| SWC.4b | `feat/swc-4b-workspace-documents` | New `src/reporting/documents/{watchlist,runs,refresh}.py`; `src/cli_workspace.py` JSON builders; `schemas/` (watchlist, watchlist delete, runs list, refresh summary); tests (T20 extended). | The hand-built dicts in `_watchlist_payload`, the delete outcome and `_refresh_json`; the `model_dump` list in `runs list`. | One model per document, each proved byte-identical to the current output except the listed changes, then the schemas. |
| SWC.4c | `feat/swc-4c-strategy-json-envelopes` | `src/strategy_wiring.py`; new `src/strategies/<strategy>/envelope.py` and `replay.py` (four each), `src/strategies/_graham/replay.py`, `src/reporting/{json_documents,replay_inputs}.py`; `src/reporting/analysis_runs.py`; `schemas/` (four strategy documents); tests (T9, T10, T20, T21, T24 extended). | Literal ids in three builders; the `project_run` pair chain; the four `_project_*_v1` functions leave `analysis_runs.py`; `ReplayOptions` and `UnsupportedProjectionError` move to `replay_inputs.py`. | Envelope models and `json_envelope`, then the builders' boundary validation, then the projectors and the injected `project_run`, then `JSON_DOCUMENTS` and T21 last, when every command is covered. `json_documents.py` lists the failure, workspace and database documents only; the generator and T20, T21 add each descriptor's `json_envelope` from the root. |
| SWC.5 | `feat/swc-5-site-data-and-status` | New: `scripts/strategy_sites.toml`, `scripts/strategy_sites.py`, `scripts/strategy_status.py`, `scripts/generate_strategy_docs.py`; `scripts/strategy_conformance.py` (extended); marked blocks in `docs/user/USAGE.md` and `docs/user/WORKSPACE.md`; the watchlist option rows move into the strategy guides; `FCF_EARNINGS_GROWTH.md` renamed; tests T25, T26. | The hand-written strategy lists and the watchlist option table in the two pages. | Site data and loader, then conformance functions in report mode, then the status command, then the generated lists and their drift test. |
| SWC.6 | `feat/swc-6-specimen-and-generator` | New: `tests/specimen/` (the specimen strategy and its two tier tuples), `scripts/new_strategy.py`, `scripts/strategy_templates/` (one template per role file), `src/core/strategy_stub.py`, tests T27 to T29 and the generator test fills; `AGENTS.md` §3 (stub exception). | None. | Specimen first, then the generator, then its end-to-end test, then the stub rule. |
| SWC.7 | `feat/swc-7-contributor-guide` | `docs/project/ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md` moved to `docs/TOOL_DEVELOPMENT.md` and extended (including the identifier rules in [§16](#16-step-35-fit-check) and the edit-site table, generated from the site data file); every link to it; the Step 3.5 contract plan's link to the edit-site table; `AGENTS.md` §3; `docs/project/DISCOVERY_WORKBOOK.md` open question 3; final conformance coverage; independent review. | None in code. | Guide, then authorization, then workbook, then final conformance. |

Why the earlier slices are split. SWC.2a relocates every existing strategy module once, as pure moves, so
every later slice creates its files in their final place; SWC.2b keeps the mechanical symbol moves apart
from the descriptor; SWC.2c is the descriptor, the handlers and the routing consumers, one coupled change;
SWC.2d moves fixture composition into the evaluation tier with no logic change. SWC.3 is three slices
because the workspace consumers (SWC.3a), the CLI tier (SWC.3b) and the direct commands, with their
patch-target changes in thirteen test modules (SWC.3c), are three reviewable concerns. SWC.4 is three
slices: with every `--json` document typed it would carry four large strategy envelope models, the failure
envelope and its classifier, the refresh and database output changes, four workspace documents, a schema
generator, the replay table and a command-coverage test. SWC.4a ships the generator and drift test with the
first schemas. T21 lands last, in SWC.4c, because it can only pass once every `--json` command is covered,
and it has no exemption list.

Stored-shape version bumps expected: **none.** No slice touches a stored shape. SWC.3a relocates version
values unchanged and changes no selection, evidence or result shape, so no `config_schema_version`,
`method_version`, `result_schema_version` or `evidence_codec_version` changes. The `--json` output versions
that change are listed in [§13.4](#134-what-changes): the failure document `schema_version` 5 to 6 and the
database report `schema_version` 1 to 2. Strategy and workspace success documents stay byte-identical, so
their versions do not change. `projection_version` stays 1. A slice that finds it must change a stored
shape bumps the version and records it.

Schema layout, settled here per the plan: one file per document under `schemas/`, with no combined
discriminated schema, because each command emits exactly one document type. Generation is
`model_json_schema(mode="serialization")` (a `TypeAdapter` for the existing dataclass and the array
document) serialized with sorted keys, two-space indent and a trailing LF. The drift test (T20)
compares bytes, so the standard pytest gate carries it and no gate-wrapper change is needed.

| File | Document | Commands | Slice |
| :--- | :--- | :--- | :--- |
| `momentum.schema.json`, `graham-number.schema.json`, `graham-growth.schema.json`, `fcf-growth.schema.json` | One strategy document each | The strategy's direct command; `runs show` for a run of that strategy | SWC.4c |
| `failure.schema.json` | `FailureEnvelope` | Every `--json` command, on failure | SWC.4a |
| `database-maintenance-report.schema.json` | `DatabaseMaintenanceReport` | `db status`, `db upgrade` | SWC.4a |
| `watchlist.schema.json` | The watchlist document | `watchlist show`, `watchlist rename` | SWC.4b |
| `watchlist-delete.schema.json` | The delete outcome (embeds the watchlist document) | `watchlist delete` | SWC.4b |
| `runs-list.schema.json` | An array of run summaries | `runs list` | SWC.4b |
| `refresh-summary.schema.json` | The refresh summary | `refresh` | SWC.4b |

## 12. Framework-drift checks

The design has drifted into a registry, plugin or factory architecture if any of these is true. T13 to T17,
T24 and the review checklist check them; each is concrete.

| # | Check | Drift if |
| :--- | :--- | :--- |
| A1 | `src/strategy_wiring.py`, either tier module or a strategy-owned file imports `importlib`, `pkgutil`, `inspect`, `entry_points`, or uses `__subclasses__`, `__init_subclass__`, `globals()`, `locals()`, `getattr` with a computed name, or `typing.get_type_hints` | Any occurrence (T14). |
| A2 | Any of those files defines or exports a name matching `register*`, `unregister*`, `*Registry`, `*Factory`, `*Plugin`, `load_*`, `discover*`, or any function that mutates a closed tuple or an index | Any occurrence (T14). The one permitted caller of `app.command` is `add_strategy_commands` in the CLI tier, which iterates the closed tuple. |
| A3 | `STRATEGIES`, `CLI_STRATEGIES` or `EVALUATION_STRATEGIES` is not a module-level `tuple` of module-level constants or direct `pair_*` calls, or an index is not a read-only `Mapping` | Either (T14, T15). |
| A4 | `StrategyDescriptor` is generic (`__parameters__` is not empty), is not a frozen dataclass, or is subclassed | Any (T15). |
| A5 | A descriptor field's type mentions `BaseAnalyzer`, a config type, an injected dependency instance, or a `Callable` returning one of them | Any (T15). Functions inside `behavior` are typed by their own protocols. |
| A6 | The field set differs from [§3.1](#31-fields), or a behavior or tier member differs from [§3.3](#33-behavior-members-and-the-two-tiers) | Always requires a reviewed test edit (T15). |
| A7 | A field or member is read nowhere outside its defining module | Dead field (T16). |
| A8 | A module below the composition root imports the root, a tier or a strategy CLI or evaluation file, directly or through a parent package; a strategy-owned file breaks the role rule in [§4](#4-static-declaration-model); or the root is in an import cycle | Either (T13). |
| A9 | `src/analysis/base_analyzer.py` differs from `main`, or `run_analysis`'s signature or `AnalysisContext` fields change | Any (T17; also a diff check in each slice review). |
| A10 | A consumer keeps an `isinstance`/`==` chain over strategies whose last branch does not raise | Reviewed per slice; T11 proves behavior for the dispatchers it lists. |
| A11 | A capture type, an outcome classifier, an analyzer or config instance appears as a descriptor field or behavior member | Always escalates to the project owner as a plan change. |
| A12 | A strategy-owned file registers itself: it imports the Typer app, uses `app.command` or `typer.Typer(`, calls a dispatcher's `register_tool`, or mutates a tuple | Any occurrence (T14, over every strategy-owned file). A command function is plain; the CLI tier supplies its name. |
| A13 | `scripts/new_strategy.py` or its templates write anything beyond wiring (formula, classification or presentation text), or a generated file imports another strategy's modules | Any occurrence (T28 checks the generated files' imports; the templates are reviewed). |

## 13. Failure-envelope contract

### 13.1 Decision

- **One new shared `FailureEnvelope`** (a frozen pydantic model in `src/reporting/documents/failure.py`)
  for every `--json` failure from the direct commands and the workspace commands, and the vocabulary
  for per-job failures in `refresh --json`.
- **`DatabaseMaintenanceReport` stays a sibling shape and adopts the envelope's field names.** Its
  stable code field is renamed `reason` to `reason_code` and its prose field `message` to `reason`, so
  a caller reads the code and the prose under the same names in both shapes. It is still a report of an
  inspection, not a failure document, for three differences verified in `src/cli_database.py`:
  1. `status` means the operation ran, not that it succeeded: `db status` on a database that needs
     upgrading reports `"success"` and exits 1.
  2. It carries `command`, `state` and `current_revision`, which have no meaning for an analysis or a
     workspace command, and lacks `analysis`, `method`, `ticker`, `result` and `diagnostics`.
  3. `db` commands are hidden technical commands with a smaller consumer set than the analysis
     commands.
- **What is shared** is the code vocabulary: every `ReadinessReason` value is a `FailureReasonCode`
  value, so a caller branches on one set of strings across both shapes (T18).
- **Hazard of the rename.** The key `reason` keeps its name in the database report but changes
  meaning, from code to prose. A caller written against version 1 that branches on `reason` would
  silently read a sentence. `schema_version` therefore goes 1 to 2, the generated schema describes the
  fields, and `docs/user/DATABASE.md` is updated in SWC.4a. No code in this repository reads either
  field; the only readers are the report's own text rendering and tests.

### 13.2 Shape

| Field | Type | Meaning |
| :--- | :--- | :--- |
| `schema_version` | `Literal[6]` | The document's shape version. It was 5; adding `database` is the change. |
| `status` | `Literal["error", "input_unavailable"]` | Unchanged. `input_unavailable` for `historical_quality`, `provider_error`, `no_eligible_observations`. |
| `reason_code` | `FailureReasonCode` | Stable ([§13.3](#133-reason-codes-and-stability)). |
| `reason` | `str` | A sanitized sentence for people. Not stable. |
| `analysis`, `method`, `ticker` | `str \| None` | Unchanged for direct commands; `null` on workspace commands. |
| `result` | `None` | Always null, so success and failure documents share top-level keys. Unchanged. |
| `diagnostics` | `list[{rule, reason}]` | Unchanged; empty unless historical quality failed. |
| `database` | `{database_path, expected_revision} \| null` | New. Set only for `database_*` codes. |

`DatabaseMaintenanceReport` version 2 has `command`, `status`, `database_path`, `state`,
`current_revision`, `expected_revision`, `reason_code` (the stable code or null), `reason` (the prose)
and `schema_version`.

Rule for typed fields: a typed field exists only for information the caller cannot reconstruct from its
own request. That is why only `database_path` and `expected_revision` are added (both are typed
properties on `DatabaseReadinessError` that today appear only in prose), and why no `command` or
run-identifier field is added. `json_document` formatting (sorted keys, two-space indent) is reused, so
key order does not matter.

### 13.3 Reason codes and stability

| Group | Codes | Source |
| :--- | :--- | :--- |
| Direct execution | `execution_error`, `historical_quality`, `provider_error`, `configuration_error`, `no_eligible_observations`, `invalid_input` | Existing, unchanged strings from `execution_errors`. `execution_error` is also the classifier's result for an exception it does not recognize. |
| Database readiness | `database_upgrade_required`, `database_incompatible_schema`, `database_busy`, `database_permission_denied`, `database_invalid_file`, `database_io_error`, `database_resources_unavailable`, `database_initialization_failed`, `database_migration_failed` | Existing `ReadinessReason` values, unchanged. |
| Workspace, existing | `invalid_stored_run`, `unsupported_run_version` | Existing `reason_code` attributes on `InvalidStoredRunError` and `UnsupportedRunVersionError`. |
| Workspace, new | `watchlist_not_found`, `watchlist_name_conflict`, `analysis_run_not_found`, `stored_selection_unreadable`, `unsupported_projection` | New, for the `--json` failure paths listed in [§13.4](#134-what-changes). |

**Stability guarantee.** A `reason_code` value is never renamed, repurposed or removed within the
project's public contract. New values may be added; a caller must treat an unrecognised value as a
generic failure and use `status` for the category. Removing or renaming a value, or changing what a
value means, requires a `schema_version` bump and explicit project-owner approval. `reason` and
`diagnostics[].reason` are prose and carry no guarantee. The generated schema lists the enumeration,
so the drift check (T20) shows any change, and T18 requires every source code to be a member.

One classifier, `classify_failure(exception)` in `src/reporting/failure_classification.py`, maps an
exception to a code and a status. `execution_errors`, the workspace commands and `refresh_watchlist`
(which receives it as a required parameter, so the workspace layer imports nothing from `reporting`)
all use it, so the families cannot diverge. The model and enumeration live in the separate leaf module
`src/reporting/documents/failure.py`. There is one `WatchlistNotFoundError` ([§18](#18-findings-assigned-to-a-slice)).

### 13.4 What changes

| # | Existing output | Change |
| :--- | :--- | :--- |
| 1 | Direct commands' `--json` failure document | `schema_version` 5 to 6; new `database` key, `null` unless a `database_*` code. All other keys and values unchanged. |
| 2 | `watchlist show`, `watchlist rename`, `watchlist delete`, `runs list`, `runs show`, `refresh` with `--json`, on a failure that today calls `_fail` | The `FailureEnvelope` is written to stdout and nothing to stderr (as the direct commands do in JSON mode). Exit code stays 1. For `watchlist delete`, the deletion confirmation already printed on stderr stays. |
| 3 | `refresh --json`, each element of `results` | New key `reason_code`: a `FailureReasonCode` when `error` is set, otherwise `null`. `error` keeps its text exactly. The existing rule that exactly one of the run, the outcome and the error is set gains a fourth statement: `reason_code` is set if and only if `error` is. |
| 4 | `db status --json` and `db upgrade --json` | `reason` (the code) is renamed `reason_code`; `message` (the prose) is renamed `reason`; `schema_version` 1 to 2. The text rendering is unchanged. |

Unchanged: every strategy success document; the watchlist, delete-outcome, `runs list` and `runs show`
success documents; text modes of every command; commands without `--json`; usage errors (exit 2,
text); the declined-confirmation message in `watchlist delete`.

Per-job failures keep their existing text. `RefreshJobResult.error` is `str(exception)` today and
stays so; the code is classified from the same exception object, so no new text is derived from raw
exception content.

### 13.5 Non-goal

The envelope helps a caller report a condition and never remediate it. It has no `remediation`,
`fix`, `command` or `action` field, and `database` carries facts, not instructions. The existing prose
for `database_upgrade_required` already tells a person to back up and run `db upgrade`; that stays
prose. T19 fails if a remediation-shaped field is added. No command in SWC runs `db upgrade` for a
caller.

### 13.6 Every JSON document is typed

Every command that offers `--json` gets a typed model and a checked-in generated schema. Twelve
commands offer `--json` today (`momentum`, `graham-number`, `graham-growth`, `fcf-growth`,
`watchlist delete`, `watchlist rename`, `watchlist show`, `runs list`, `runs show`, `refresh`,
`db status`, `db upgrade`); they emit nine success document shapes, which with the failure envelope make ten schema files, listed in
[§11](#11-migration-from-current-declarations). Each failure is the `FailureEnvelope`.

**Strategy-specific content in the workspace documents.** Exactly one family has any:

| Document | Strategy-specific content | How it is typed |
| :--- | :--- | :--- |
| `watchlist show`, `watchlist rename`, and the watchlist embedded in `watchlist delete` | `entries[].selection`, the `model_dump` of an `AnalysisSelection` member (windows for Momentum, EPS basis and overrides for Graham, the policy snapshot for FCF) | By the `AnalysisSelection` discriminated union itself, discriminated on `method_id`. The generated schema is a `oneOf` over the four selection models, so a strategy added to the union appears in the schema automatically and T1 keeps the union equal to the descriptors. No second typing of selections is written. |
| `runs show` | The whole document: it is the strategy's own replay document | By the strategy envelope model of the run's strategy; the command lists all strategy schemas in `JSON_DOCUMENTS`. |
| `runs list`, `refresh`, `db status`, `db upgrade` | None. `method_id` appears only as a string, typed `str` (a `Literal` cannot be built from the descriptors under `mypy --strict`, and T10 covers the identifiers). | Plain fields. |

**Coverage test.** T21 enumerates the commands from the CLI's own parameter declarations, recursing
the real Typer command tree through every group including hidden ones and keeping each command with a
`--json` option. That surface is independent of the `JSON_DOCUMENTS` table and of the files in
`schemas/`. It fails, naming the command, when a command is missing from the table or a schema file
it needs is not checked in.

## 14. Momentum profile composition helper

**Decision:** add `compose_momentum_profile` to `src/strategies/momentum/execution.py` with a
standalone signature:

```python
def compose_momentum_profile(
    ticker: str,
    *,
    data_client: object,
    profile_cache: InstrumentProfileResolver | None = None,
) -> InstrumentProfile: ...
```

- **Where:** `src/strategies/momentum/execution.py` (the Momentum adapter), not a shared module.
  `src/strategies/_shared/profile.py` holds the Graham helper because three strategies share it; this helper
  has three call sites of one strategy, all of which already import the adapter. There is no cycle.
- **Why not `compose_graham_profile`'s signature:** that helper takes a primary security-fact provider
  and a separate Yahoo provider, with a precedence rule that adds Yahoo only when the primary is
  another provider. Momentum has one client that is both identity and kind candidate. Calling the
  Graham helper would need the same client passed twice and a Graham-named import in Momentum code,
  which treats Graham as the template (`AGENTS.md` §9). `graham_shared.py` is not edited.
- **Behavior preserved exactly:** one identity candidate and one kind candidate, both
  `InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, data_client)`; `profile_cache.resolve(...)` when a
  cache is given, otherwise `compose_instrument_profile(...)`. The two `src/cli.py` sites and
  `src/cli_workspace.py::_execute_momentum` call it. Tests that patch
  `src.cli.compose_instrument_profile` retarget to the helper's module in SWC.3a.

## 15. IR.2 and corrections to the plan

**IR.2 contract changes: none required.** IR.2 fixed three things: every strategy subclasses
`BaseAnalyzer[ConfigT, ResultT]` and is invoked as `run_analysis(ticker, config, context)`;
`AnalysisContext` carries the cross-cutting concerns; and there is no generic result supertype,
registry or factory. The design adds closed tuples of non-generic declarations and one generic frozen
bundle per strategy, erased behind a `Protocol`. It leaves the invocation envelope, `AnalysisContext` and
every config and result type untouched (T17, A9). The `NativeEvidence` union already exists; the bundle's
bound refers to it and does not create a supertype. The descriptor constructs nothing. The remaining
tension is the one the plan already records, a bounded exception to IR.2's "no registry" wording
authorized by `AGENTS.md` §0; nothing new needs owner review.

Where the audit disagreed with the plan, and what changed:

| # | Plan statement | Finding | Change made |
| :--- | :--- | :--- | :--- |
| 1 | B.4 and Appendix A: `encode_evidence` and `decode_evidence` both fall through to Momentum. | Only `encode_evidence` does. `decode_evidence` rejects an undeclared pair before it reaches the Momentum branch (`codecs.py`, the `expected is None` guard). | Wording corrected in the plan; both dispatchers still become table-driven and fail closed. |
| 2 | §3.2/§4: `ToolName` values are sourced from the descriptor. | A functional enum from descriptor strings fails `mypy --strict` and breaks `ToolName.X` ([§9.1](#91-toolname)). | `ToolName` stays the single hand-written declaration; the plan's §4 row is amended. |
| 3 | §3.2 permits descriptor references to execution adapters and presentation functions. | Executors, handlers and projectors need production dependencies or sit above the codecs; referenced from a descriptor that the foundation layers import, they create import cycles of 2, 4 and 8 modules ([Appendix C](#appendix-c-import-cycle-evidence)). | Resolved by D1: the descriptor sits at the composition root and each layer receives its slice by injection, so the references are used. |
| 4 | SWC.4 and SWC.5 both own schema generation and the drift check. | The plan states it twice. | SWC.4a owns the generator, `schemas/` and the drift check; SWC.4b and SWC.4c add schemas to it; SWC.7 verifies per-descriptor coverage and documents. |
| 5 | Appendix A inventory. | Sites it misses ([Appendix A](#appendix-a-inventory-re-verified-at-247ecdf)), including four more default-branch patterns: `parse_selection`'s final Momentum branch, `_build_selection`'s final FCF branch, `_require_tool_evidence`'s final FCF branch and `_native_status`'s final FCF branch. | Plan Appendix A and §4 updated; SWC.2 and SWC.3 scope lines extended. |
| 6 | SWC scope lines. | SWC.2 omits `analysis_tool_arguments.py`, `tool_names.py`, `native_evidence.py` and `evaluation/models.py`; SWC.3 omits `data/repositories/watchlists.py` and the deletion of `method_aliases.py`; SWC.4 omits the `src/cli.py` call sites. | Scope lines corrected in the plan. |
| 7 | SWC.4 branch is "based on the approved SWC.1 design". | SWC.4 reads declarations SWC.2c and SWC.3 create. | Every slice branches from `main` after its predecessor merges ([§11](#11-migration-from-current-declarations)). |
| 8 | The plan makes SWC.4 one slice covering strategy envelopes and the failure envelope. | With every `--json` document typed, the refresh and database output changes and a schema generator, it is three reviewable concerns. | SWC.4 is split into SWC.4a, SWC.4b and SWC.4c ([§11](#11-migration-from-current-declarations)). |
| 9 | The plan's JSON scope is the strategies' output and the failure envelope. | The project owner's review decided that every `--json` document is typed. | The plan's At a glance, SWC.4 scope and acceptance criteria are widened ([§13.6](#136-every-json-document-is-typed)). |
| 10 | SWC.3's Decision says today `encode_evidence` and `decode_evidence` both fall through to Momentum. | Item 1 above. | The sentence is corrected in the plan. |
| 11 | The design (as merged) and test T13 treated each import statement as an edge to the named module only. | Python runs a package's `__init__.py` first. `src/workspace/__init__.py` imports `requests`, which imports the descriptor, which imports `src.workspace.*`: an initialization cycle of nine modules that makes importing the descriptor first fail with `ImportError`. | `src/workspace/__init__.py` is emptied in SWC.2b and T13 counts parent packages ([§4](#4-static-declaration-model), [Appendix C](#appendix-c-import-cycle-evidence)). |
| 12 | The design (as merged) kept handlers, executors and projectors in consumer-owned tables because a descriptor they reference creates import cycles. | The cycles come from the direction (consumers import the descriptor), not from where the functions live. With the descriptor at the composition root and each layer's slice injected, the references are acyclic and no foundation layer imports upward. | D5 is reversed: the references are used ([Appendix E](#appendix-e-adoption-of-the-co-location-result)). |
| 13 | Plan §3.2 permits references to strategy-owned encoding, decoding, presentation, selection-conversion and execution functions. | The design used fewer than §3.2 allows. | The design now uses handlers, selection parsers, replay projectors and native-status functions in the core bundle, and selection builders, refresh executors and commands in the CLI tier. |
| 14 | The plan has one SWC.2, one SWC.3 and a final SWC.5 that holds the guide. | The adopted shape makes SWC.2 and SWC.3 too large to review, relocates the existing strategy modules, and adds contributor tooling that the guide's table is generated from. | SWC.2 is four slices, SWC.3 is three, tooling is SWC.5 and SWC.6, and the guide is SWC.7 ([§11](#11-migration-from-current-declarations)). |
| 15 | The package-rename plan leaves the strategy folder layout to PKG planning. | SWC.2a onward create the strategy-owned files and SWC.5 and SWC.6 build tooling around their locations, so the layout cannot wait. | One package per strategy is adopted ([§4](#4-static-declaration-model), [Appendix C.6](#c6-one-package-per-strategy)); the package-rename plan records the outcome. |

## 16. Step 3.5 fit check

This tests the SWC design, including the behavior bundle and both tiers, against the seven strategies in
the [Step 3.5 contract](../step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md). It makes no production change
and no Step 3.5 design decision; identifiers and result shapes are left to that step.

### 16.1 How each strategy is declared and wired

| Strategy | Declared as | Notes |
| :--- | :--- | :--- |
| Piotroski F-Score | One descriptor: one tool, arguments model, evidence type, alias and envelope. | The nine tests, the score and completeness are fields of one result. |
| Altman Z / Z″ | One descriptor. | Z versus Z″ is a result field ("the model used"), not two methods, so there is one `method_id`, one evidence type and one envelope whose root model carries both variants. Splitting them later would need two of everything and the uniqueness rules would require it. |
| Beneish M-Score | One descriptor. | The DEPI basis and income basis are result fields. |
| Cash-Flow Valuation Multiples | One descriptor. | EV/EBITDA and FCF yield are two `MetricResult`s of one result. |
| Greenblatt Magic Formula | One descriptor for the per-ticker analyzer. | The ranked refresh view is a separate command over persisted runs. It has no descriptor, evidence type or `--save-run`, but it has a typed `--json` document, so T21 requires its model and schema. |
| Interest Coverage | One descriptor. | |
| ROIC and Incremental ROIC | One descriptor. | Trailing and incremental ROIC are two `MetricResult`s of one result with one `method_id`. |

The native-status function of each strategy returns the result's explicit result-level status. That is a
Step 3.5 result-shape decision, made in
[Step 3.5 shared definitions §2](../step-3.5/STEP_3_5_SHARED_DEFINITIONS.md#result-level-status), which also
lists the values; the SWC design holds only this pointer. Momentum's analyzer has no status and its
function returns `None`.

### 16.2 Every member answered for all seven

| Member or file | Answer for all seven strategies | Exceptions |
| :--- | :--- | :--- |
| Arguments model | `ticker` and `as_of` from the shared base, and `use_cache`. The strategy specifications fix every method parameter and state that none is a user option. | A slice plan that adds `currency` follows FCF's field. |
| `deps_type` and `handler` | A dependency class holding the strategy's analyzer and the SEC provider id (all seven read SEC EDGAR annual filings only), and a handler of FCF's shape. | None. |
| Selection class, `parse`, `build` | The shared selection fields (`as_of`, `use_cache`) and the strategy's own `analysis_id`, `method_id` and version `Literal`s; parse and build are trivial. | None. |
| `encode`, `decode`, `ticker_of` | A strict codec over the strategy's result; `.ticker`. | None. |
| `native_status` | Returns the result's `execution_status` value. | None for the seven. |
| `project` | Replay over decoded evidence and selection through the strategy's presenter, with no provider, cache, clock or calculator. | None. |
| `headline` | A `Headline` of one to three cells, a period end and a taxonomy, as [§3.3](#33-behavior-members-and-the-two-tiers) defines. | Momentum has no period end or taxonomy. |
| CLI file (`command`, `build`, `refresh`) | The command with `--save-run` and `--json`; a `refresh` that composes a fresh SEC provider and cache per call, as `_execute_fcf_growth` does. | None. |
| Evaluation file (`compose`, `requirement`) | Fixtures from the captured filings 3.5.7 supplies; the requirement names them. | None. |
| Envelope and identity | A typed document and unique `analysis` and `method` ids. | Altman's root model carries both model variants. |
| Cross-strategy views | The ranked view and the side-by-side table have no descriptor: they are commands over persisted runs. | The table's per-strategy content is the `headline` member. |

**Verdict.** All seven strategies fit; none needs a member the bundle lacks. The one member the bundle
lacks today, `headline`, is added by Step 3.5 slice 3.5.0, before any new strategy slice, and every
strategy then supplies it from the start.

### 16.3 Assumptions tested

| Assumption | Covering test | Result and resolution |
| :--- | :--- | :--- |
| One descriptor has exactly one tool, arguments model, evidence type, alias and JSON envelope, each unique across strategies. | T24, through `BY_TOOL`, `BY_ARGUMENTS`, `BY_RESULT_TYPE`, `BY_ALIAS` and (SWC.4c) `BY_ENVELOPE`. | Holds for all seven. **Misfit:** the Step 3.5 slice scopes name "direct command, watchlist selection, refresh, `--json`" and do not name the orchestrator tool, arguments model, `ToolName` member, handler or dependency class. SWC requires them for every strategy, and the golden suite (3.5.7) cannot select a strategy without them. *Design unchanged*: the rule stays; the edit-site table is the handoff, and the Step 3.5 contract plan states that every strategy slice covers it. |
| `method_id` is unique across all analyses. | T24, through `BY_METHOD_ID`. | Holds. It is a rule, not an accident, because runs, watchlist removal and CLI filters select by `method_id` alone (`RunQuery`, `remove_entries_for_method`, `--analysis`). It is stated in three places: the import-time error names both descriptors and the rule; the `strategy_wiring` module docstring; and the SWC.7 contributor guide's identifier section. A strategy with several methods needs distinct method ids, one descriptor per method, and so one tool, evidence type and alias per method. |
| One result concerns one ticker. | `ticker_of`, `decode_for(payload, ticker)`, and the failure envelope's `ticker`. | Holds for all seven analyzers. The ranked view and the side-by-side table concern many tickers but are views over persisted runs, store no evidence and fail with `ticker: null`. |
| One analyzer class maps to one descriptor. | T3, enumerating analyzers by package walk over `src/strategies`. | Holds; Altman's two models are one analyzer. An enumeration by hand-written list would need an edit for each of seven analyzers; the package walk needs none. |
| Every strategy command declares `--save-run`. | T7 (c). | Holds for strategy commands. **Misfit:** the ranked view and the side-by-side table are commands without `--save-run`. *Design changed*: T7 enumerates the whole command table, requires every top-level command to be an alias, a group or a listed non-strategy command, and checks `--save-run` as a property. |
| A strategy's chains and tables are keyed, not defaulted. | T10, T11. | **Misfit:** four `if` chains would have routed an eighth strategy to FCF or Momentum (`_require_tool_evidence`, `_native_status`, `parse_selection`, `_build_selection`). *Design changed*: each is now an injected mapping or a tier lookup that fails closed. |
| A cross-strategy view needs per-strategy content. | T15 and the member's type. | The `headline` member, added once by 3.5.0. |
| Dependencies stay a flat per-strategy dataclass. | mypy and T6. | **Resolved by the design:** each strategy owns its dependency class, so seven more strategies grow no shared dataclass. |
| Wiring is near-identical across the seven. | The repetition checkpoint in the Step 3.5 plan. | All seven read SEC annual filings only and share the same selection fields, so the generated stubs will be near-identical. The Step 3.5 plan reviews the repetition after the first strategy and extracts shared helper functions (not a base class) for exactly what repeated. |

## 17. Edit sites for a new strategy

Every hand-edited place, in the order a contributor meets them. "Kind": **G** is genuine heterogeneity
(per-strategy content), **R** is residual repetition (a line restating identity or a type list), **G+R**
is a strategy-owned function or class plus one entry. "Generated" means `scripts/new_strategy.py`
([§19](#19-contributor-tooling)) makes the edit or writes the typed stub; "reviewed" means reviewed truth
or prose the generator never writes. "Check" is what fails if the site is omitted. Rows marked **type**
fail `mypy --strict` when the descriptor or a tier entry is constructed, and raise `TypeError` when the
dataclass is built at run time.

| # | Site | File | Kind | Generated | Check |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Analyzer modules: config, result, analyzer | `src/strategies/<s>/` (new; analyzer-role files such as `analyzer.py`, `models.py`) | G | stub | T3: `analyzer X (result Y) has no descriptor`. |
| 2 | Descriptor constant, `StrategyBehavior` declaration and `STRATEGIES` entry | `src/strategy_wiring.py` | G+R | edit | T1, T2, T3; **type**. |
| 3 | `ToolName` member | `src/orchestrator/tool_names.py` | R | edit | T4: `ToolName member X has no descriptor`. |
| 4 | Arguments model, dependency class, handler | `src/strategies/<s>/tool.py` (new) | G | stub | **type** (`tool_arguments`, `deps_type`, `handler`); T4: `tool-argument model X has no descriptor`. |
| 5 | `NativeEvidence` and `SelectionMember` entries | `src/workspace/strategy_types.py` | R | edit | **type** (both bounds); T1, T2. |
| 6 | Selection class and parser | `src/strategies/<s>/selection.py` (new) | G | stub | **type** (`selection_type`, `parse`); T1: `descriptor X has no selection member`. |
| 7 | Codec and native-status function | `src/strategies/<s>/codec.py` (new) | G | stub | **type** (`encode`, `decode`, `ticker_of`, `native_status`); T8 round trip. |
| 8 | Execution adapter, capture type, normalizer | `src/strategies/<s>/execution.py` (new) | G | stub | T22: `alias X stored no run`. |
| 9 | CLI file: direct command, selection builder, refresh executor | `src/strategies/<s>/cli.py` (new) | G | stub | **type** (the CLI-tier pairing); T22. |
| 10 | CLI-tier entry | `src/cli_strategy_wiring.py` | G+R | edit | **type**; T10 `CLI tier`: `strategy X is not wired in: CLI tier`; T7. |
| 11 | Presenter and JSON builder | `src/strategies/<s>/presenter.py` (new) | G | stub | T9: `rendered document ids differ from selection X`. |
| 12 | Envelope model and identity constants | `src/strategies/<s>/envelope.py` (new) | G | stub | T21: `command X offers --json but has no typed document model`. |
| 13 | Replay projector and `headline` function | `src/strategies/<s>/replay.py` (new) | G | stub | **type** (`project`; `headline` from Step 3.5 slice 3.5.0); T8 replay. |
| 14 | Evaluation file: fixture composition and requirement | `src/strategies/<s>/evaluation.py` (new) | G | stub | **type** (the evaluation-tier pairing); T6. |
| 15 | Evaluation-tier entry | `src/evaluation/strategy_fixtures.py` | G+R | edit | T10 `evaluation tier`: `strategy X is not wired in: evaluation tier`; T6. |
| 16 | Fixtures and cases | `src/evaluation/fixtures/<s>.py`, `src/evaluation/cases/<s>.py` (new) | G | reviewed | T5, T6. |
| 17 | Catalog: case tuple entries and suite version bump | `src/evaluation/catalog.py` | G | reviewed | T6: `tool X is required by no golden case`. |
| 18 | User guide with `FINANCE_MATH.md` and `GLOSSARY.md` links | `docs/user/strategies/<ALIAS>.md` (new) | G | reviewed | T23: `no guide for alias X`; the doc link check for a missing anchor. |

Two commands, not edits: `scripts/generate_schemas.py` (a stale schema fails T20 with `schema
schemas/<alias>.schema.json is missing or out of date; run scripts/generate_schemas.py`) and
`scripts/generate_strategy_docs.py` (a stale strategy list fails T26 the same way). The generator also
writes the empty `src/strategies/<s>/__init__.py`, which has no content to review.

**Total: 18 hand-edit sites, in 21 files (15 new, 6 existing) across 8 directories** (`src`,
`src/strategies/<s>`, `src/orchestrator`, `src/workspace`, `src/evaluation`, `src/evaluation/fixtures`,
`src/evaluation/cases`, `docs/user/strategies`). Against the earlier design's 23 sites, 25 files (10 new, 15
existing) across 11 directories. Five of the six existing files are edited by the generator (rows 2, 3, 5,
10, 15); the sixth, `catalog.py`, stays by hand because its case tuple and suite version are reviewed
truth. Twelve of the 15 new files are generated as typed stubs (rows 1, 4, 6 to 9 and 11 to 14); fixtures,
cases and the guide are hand-written. One-line restatements in files owned by generic code fall from 11 to
5 (rows 3, 5 twice, 10, 15). Eight omissions are type errors rather than test failures (rows 4 to 7, 9, 10,
13, 14). Every file a strategy owns except its fixtures and cases is in its own package, so a contributor
works in one strategy directory plus five one-line edits.

**What could still be removed.** Nothing within the contract. Each remaining existing-file edit has a
reason:

- the `ToolName` member and the two union entries are type-level lists that `mypy --strict` needs and no
  descriptor can generate;
- there is one tuple entry per layer (root, CLI tier, evaluation tier) because a lower layer cannot import
  an upper one, so one closed tuple cannot hold all three;
- the catalog's case tuple and suite version are reviewed evaluation truth, where a silent change would be
  a regression.

## 18. Findings assigned to a slice

| Finding | Decision | Slice |
| :--- | :--- | :--- |
| `AnalysisType` in `src/core/constants.py` has one member (`MOMENTUM`) and no reader in `src/` or `tests/` (a repository search for the name finds only its definition). | Delete it. It is a dead per-strategy name list, and SWC.2b is where per-strategy name declarations are removed. | SWC.2b |
| `src/workspace/__init__.py` re-exports names that no module in `src/` or `tests/` imports from the package, and takes part in an initialization cycle once `requests.py` imports the descriptor machinery. | Empty it. | SWC.2b |
| Two classes named `WatchlistNotFoundError`, in `src/data/repositories/watchlists.py` and `src/workspace/refresh.py`. | One class, defined in `src/workspace/watchlists.py` next to `StoredSelectionError`; the repository and `refresh.py` import it; the duplicate and the aliased import in `cli_workspace.py` go. The classifier maps one class to `watchlist_not_found`, and no handler can miss the other. Tests in `tests/data` and `tests/workspace` import the single class. | SWC.4a |
| `analysis_failure_document`'s docstring says the failure document uses "the analysis presentation version", but its `schema_version` is 5 for every strategy while the Graham success documents carry 6. | The docstring is removed with the hand-built dict. `FailureEnvelope` documents that its `schema_version` is its own lineage, independent of every success document's. | SWC.4a |
| The failure envelope and the Graham success documents would share `schema_version` 6. | Acceptable. A `schema_version` identifies a shape only within its own schema file; consumers dispatch on `status` and `result` first, then on `analysis`. The generated schema's description says so, the contributor guide states it, and renumbering the failure lineage to avoid a coincidence would be a second, arbitrary output change. | SWC.4a, SWC.7 |
| `execute()` reads `getattr(selection, "as_of", None)`, although every `AnalysisSelection` member defines `as_of`. | Read `selection.as_of`; the probe adds no safety and hides a missing field. | SWC.3a |
| `ollama_runner._selection_observation` uses the private `ToolName._value2member_map_`. | Replace with ordinary enum lookup. | SWC.2c |
| `evaluation.runner.NativeAnalysisResult` duplicates `NativeEvidence`. | Remove it and use `NativeEvidence`. | SWC.2c |
| Each strategy's codec checks its own `method` string inside `workspace/{graham_number,graham_growth}.py`. | Kept: wire-integrity checks that stay with the codec. | none |
| `refresh --json` per-job `error` text is `str(exception)`. | Unchanged. The new `reason_code` is classified from the same exception. | SWC.4a |
| `cli.py` and `cli_workspace.py` each hold a Momentum window check and three FCF option converters that look duplicated. | Kept as separate functions. They differ in behavior: the direct command exits with code 2 after an echoed message, the workspace builder raises `typer.BadParameter`. Each moves into its strategy CLI file unchanged. | SWC.3b, SWC.3c |

## 19. Contributor tooling

Five items, settled here and implemented in SWC.5 and SWC.6. They are developer scripts under `scripts/`,
checked by `mypy --strict`, not `ian` commands, and none is listed in `[project.scripts]`.

### 19.1 One list of edit sites

`scripts/strategy_sites.toml` is the single source for the contributor guide's edit-site table, the status
command, the generator and the specimen's completeness test. It is read with `tomllib` through
`scripts/strategy_sites.py`, a typed loader. Each `[[site]]` has:

| Key | Meaning |
| :--- | :--- |
| `id` | Stable slug, for example `tool-name`. |
| `title`, `why` | One line each, for the guide. |
| `kind` | `new_file`, `edit`, `command` or `reviewed`. |
| `path` | The file, with placeholders `{module}` (snake_case name), `{alias}` (hyphenated) and `{guide}` (upper-case alias). |
| `generated` | Whether the generator makes this change. |
| `check` | The name of a function in `scripts/strategy_conformance.py`. |
| `fails` | The diagnostic the check produces when the site is missing. |

The table in [§17](#17-edit-sites-for-a-new-strategy) is generated from this file into marked lines in
`docs/TOOL_DEVELOPMENT.md` and in this design (the design keeps a verbatim copy; T25 compares it).

### 19.2 Status command

`uv run python scripts/strategy_status.py <module_name> [--alias <alias>]` prints, for each site in file
order, `done` or `missing`, the site id, and the resolved path; for a missing site it adds the diagnostic.
Exit code 0 when every site is done, 1 when any is missing, 2 for a usage error. A site is done exactly
when its `check` function returns no gaps for that strategy. The functions are the conformance suite's own
check bodies in report mode: each returns `Gap(site_id, path, message)` records, the tests assert the list
is empty for every declared strategy, and the command prints the same records, so the two cannot
disagree. For a strategy not yet declared, the declaration checks return gaps that name the file to edit.

### 19.3 Generator

`uv run python scripts/new_strategy.py <module_name> --label "<Label>" [--alias <alias>]` (the alias
defaults to the module name with hyphens). It writes wiring only:

- **New files:** the twelve stubs in [§17](#17-edit-sites-for-a-new-strategy) from
  `scripts/strategy_templates/<role>.py.tmpl` into `src/strategies/<module_name>/`. They carry real signatures and types: a frozen config and result
  dataclass (the result holds `ticker` and nothing else), the analyzer subclassing
  `BaseAnalyzer[ConfigT, ResultT]`, the arguments model with the shared fields, the dependency class, the
  selection class with its identity `Literal`s, and the bundle's functions. Bodies call
  `unfilled_stub("<site id>")`, which returns `NoReturn` and raises `UnfilledStubError`.
- **Edits to existing files:** five one-line insertions (rows 2, 3, 5, 10 and 15 of §17), each located by
  the AST of the target file, asserting that the file parses before and after and that the entry count
  rose by one.
- **Nothing else:** no formula, classification or presentation text, and nothing copied from an existing
  strategy's analysis modules (T28 checks that a generated file imports no other strategy's modules).
  Fixtures, cases, the catalog and the guide are not generated, and the status command reports them
  missing until they are written.
- **Identity:** the module name gives `analysis_id`, `method_id` and the tool name (`analyze_<module>`);
  all version fields are 1.

**Overwrite rule, decided: refuse.** The generator builds every change in memory first. If any target file
exists, or the name, alias, tool or method id already appears in any tuple, enum or union, it exits with
code 2, lists the conflicts and writes nothing. Otherwise it writes through temporary files and
`os.replace`, and restores the originals if any step fails. It is not idempotent on purpose: a second run
after the stubs were edited would either overwrite work or silently differ.

**Stub rule.** `AGENTS.md` §3 forbids partial files and placeholder comments. SWC.6 adds one exception: a
file written by `scripts/new_strategy.py` whose unfilled bodies call `unfilled_stub(...)`. Test T29 fails
the quality gate while any such call remains in `src/`, so none can merge. `unfilled_stub` lives in
`src/core/strategy_stub.py`.

### 19.4 Generator test

Test T28 runs in the default suite. It copies `src/`, `scripts/`, `tests/`, `schemas/`, `config/`,
`docs/user/strategies/` and `pyproject.toml` into a temporary directory (excluding caches), runs the
generator there for a fixed throwaway strategy (`ci_probe`, label `CI Probe`), and checks:

1. the generator exits 0, the status command reports the generated sites present, and T29 reports the
   stubs;
2. after the test overwrites the twelve stub files with hand-written trivial bodies kept as test data
   (`tests/scripts/generator_fills/`), `python -m mypy --strict` over the generated files and the five
   edited files passes (with `--follow-imports=silent`, so only those files are strictly checked, and a
   cache directory inside the copy), and the conformance suite passes in the copy.

It is deterministic and makes no network call: the generator, `mypy` and the conformance suite run as
subprocesses in the copy with a fixed `PYTHONHASHSEED`, no proxy variables and bytecode writing off; the
conformance suite already forbids network access; the fills contain no provider, so the throwaway
strategy's adapter and executor return fixed values. Each subprocess has a timeout of 300 seconds; SWC.6
records the measured time.

### 19.5 Specimen strategy

A checked-in specimen, not the generator's output. `tests/specimen/` holds a complete trivial strategy
(identity `specimen`, `specimen_method`, alias `specimen-test`) wired through every layer with
deterministic bodies and no providers, plus its own CLI-tier and evaluation-tier entries. Decision and
reasons:

- The generator's output exists only inside a temporary copy and takes tens of seconds, so it cannot back
  per-dispatcher unit tests, the negative control or a command run through the real Typer app. The
  specimen can, in milliseconds.
- Both are kept and share the site data file: T27 runs the status command on the specimen and requires
  every site done, so the specimen cannot lag the site list, and the generator test proves the generator
  produces every site the file lists.

How it stays out of production: it lives under `tests/`, and T13 forbids any module under `src` importing
`tests`; the production tuples are literal and closed and never name it; tests build
`SPECIMEN_STRATEGIES = (*STRATEGIES, SPECIMEN)` and equivalent tier tuples themselves; the user CLI is
built from the production CLI tier, and a test builds a separate Typer app with
`add_strategy_commands(typer.Typer(), (*CLI_STRATEGIES, SPECIMEN_CLI))`; the published schemas are
generated from the production `JSON_DOCUMENTS` only, and a test builds its own list for the specimen.

### 19.6 Effect on the conformance design

| Effect | Tests |
| :--- | :--- |
| **Replaces** | The hand-maintained edit-site table in the guide (generated from the site file). The USAGE and WORKSPACE alias half of T23 (T26). The `monkeypatch` of production tables in T12 part 3 (specimen variants instead). |
| **Strengthens** | T11 and T12: the specimen runs through every dispatcher, both tiers, replay and the real Typer app, so a derived table that silently dropped a strategy would be caught end to end. T7 and T22: a fifth strategy through the real command and `--save-run`. T13: the specimen cannot leak into `src`. |
| **Makes redundant** | The manual contributor-path rehearsal in the independent review of SWC.7: T28 performs it on every run. No test in T1 to T9 becomes redundant. |
| **Adds** | T25 `site_data_complete`, T26 `generated_lists_current`, T27 `specimen_complete`, T28 `generator_end_to_end`, T29 `no_unfilled_stubs`. |

## Appendix A: Inventory re-verified at 247ecdf

**Verified against:** `main` at `247ecdf858756c776294f9154ce612f2915afb17` (2026-10-02). Every Appendix A
row of the plan was re-read at the named symbol. No file under `src/`, `tests/`, `scripts/`, `config/`,
`alembic/`, `pyproject.toml` or `uv.lock` changed between the plan's baseline `8edbff4` and this
commit (`git diff --stat 8edbff4..HEAD` is empty for those paths), so all 25 original rows are
confirmed as written, with one wording correction (row `decode_evidence`, [§15](#15-ir2-and-corrections-to-the-plan)
item 1). The three Momentum composition sites and every `--json` failure path in the two notes match
the code: `src/cli.py` `momentum` (`--save-run` and default branches), `src/cli_workspace.py::_execute_momentum`,
`execution_errors` in `src/cli_support.py`, and `_fail` in `src/cli_workspace.py`.

Classification: **D** is duplicated wiring (descriptor-authoritative or consumer table keyed by it);
**S** is a legitimate strategy-owned contract.

### A.1 Sites in the plan's Appendix A

| Site | Class | Reason |
| :--- | :--- | :--- |
| `*ToolArguments` models | S | Strategy-owned validation and defaults; moved, not generalized. |
| `ANALYZE_*_TOOL` constants | D | Same string as `ToolName`. |
| `ANALYSIS_TOOL_ARGUMENT_MODELS` | D | Restates `tool` to `tool_arguments`. |
| `AnalysisToolDependencies` | S | Per-strategy injected analyzers and providers. |
| Handler methods | S | Own validation, config assembly and the analyzer call. |
| `register_tool` calls | D | Per-strategy repetition of name and handler. |
| Selection models, `AnalysisSelection`, `to_*_config` | S | Typed persisted contract and discriminator. |
| Execution adapters, `*Capture`, `from_*_capture`, outcome classifiers | S | Strategy-owned; Momentum has no failure classifier. |
| `NativeEvidence` | S | Hand-written union, compared by T2. |
| `_METHOD_VERSIONS`, `_EXPECTED_VERSIONS` | D | Same versions twice. |
| `_refresh_executor` | D | Per-strategy dispatch key; composition inside stays S. |
| `encode_evidence`, `decode_evidence` chains and labels | D | Per-strategy dispatch and text; codecs themselves S. |
| Momentum profile composition (3 copies) | D | One pattern copied; [§14](#14-momentum-profile-composition-helper). |
| Codec modules | S | Strategy-owned wire shapes. |
| `_project_*_v1`, presentation modules | S | Versioned replay and presentation. |
| `project_run` pair chain | D | Dispatch key. |
| `ToolName` | D (declaration S) | One declaration remains; mapping chains go. |
| Evaluation `AnalysisToolArguments` union | S | Typing; compared by T4. |
| `compose_fixture_dependencies` | S | Fixture-owned composition. |
| `_tool_name` ×3 | D | Argument-type to tool mapping. |

### A.2 Sites missing from the plan's Appendix A

| Site | Class | Reason | Owner |
| :--- | :--- | :--- | :--- |
| `src/workspace/method_aliases.py`: `ANALYSIS_ALIASES`, `ALIAS_METHOD_IDS`, `METHOD_ID_ALIASES`, `alias_for_method_id` | D | Alias and method-id vocabulary; replaced by `alias` and `method_id`. | SWC.3a |
| `src/workspace/requests.py::parse_selection`: alias tuple; final unconditional Momentum branch | D (tuple, chain); S (per-alias parsing) | Membership is repeated vocabulary; parsing differs by strategy; the fall-through is a default branch. Becomes a lookup in an injected alias-keyed mapping of strategy-owned parsers ([§6](#6-generic-consumers)). | SWC.3a |
| `src/workspace/requests.py`: `Literal` ids and version on each selection | S | Types the discriminated union; compared by T1. | none (kept) |
| `src/data/repositories/watchlists.py`: `METHOD_ID_ALIASES.get(...)` | D | Alias lookup tolerant of an unknown stored method. | SWC.3a |
| `src/cli_workspace.py`: `_parse_analysis`, `ALIAS_METHOD_IDS[...]` (2), `alias_for_method_id(...)` (4), `--analysis` help (3) | D | Alias vocabulary. | SWC.3b |
| `src/cli_workspace.py::_build_selection` | D (chain); S (flag mapping) | The `if method == ...` chain ends in an unconditional FCF return. Becomes a lookup in the CLI tier, each builder in its strategy's CLI file over one frozen flag bundle ([§6](#6-generic-consumers)). | SWC.3b |
| `src/cli_workspace.py::_execute_*` | S | Production composition; moves unchanged into each strategy's CLI file and is referenced by the CLI tier. | SWC.3b |
| `src/cli.py`: `execution_errors(analysis=, method=)` ×6 | D | Literal id pairs. | SWC.4a |
| `src/reporting/{momentum,graham_number,graham_growth}.py`: `"analysis"`, `"method"` literals | D | Literal ids. FCF reads native `strategy_id`, `method_id`. | SWC.4c |
| `src/cli_support.py:226`: `analysis == "momentum"` | S | Strategy-specific behavior inside generic code; becomes a call-site parameter. | SWC.4a |
| `src/evaluation/runner.py`: `NativeAnalysisResult`, `_native_result`, `_native_status` | D (union, membership); S (status accessor) | Duplicate of `NativeEvidence`; FCF is the default branch; Momentum has no native status. | SWC.2c |
| `src/evaluation/composition.py::_require_tool_evidence` | S (requirements); D (chain) | Per-tool fixture requirement; the final `else` makes FCF the default. Becomes a requirement in the evaluation tier ([§6](#6-generic-consumers)). | SWC.2d |
| `src/evaluation/ollama_runner.py`: `_TOOL_DESCRIPTIONS`, `_tool_schemas_json`, `_tool_parser`, `_selection_observation` | D | Per-tool description and model; private `_value2member_map_` use. | SWC.2c |
| `src/evaluation/catalog.py`, `src/evaluation/cases/*.py` | S | Reviewed case arguments and `ToolConstraints`; the independent truth for T5 and T6. | none (kept) |
| `src/workspace/{graham_number,graham_growth}.py`: string checks of `method` inside the codecs | S | Each codec's own wire integrity check; the descriptor cannot be imported there without a cycle. | none (kept) |
| `src/workspace/__init__.py` re-exports | D (cycle) | No module imports them from the package, and they make an initialization cycle once `requests.py` imports descriptor machinery. | SWC.2b (emptied) |
| `src/core/constants.py::AnalysisType` | D (dead) | A one-member per-strategy name enum with no reader in `src/` or `tests/`. | SWC.2b (deleted) |

## Appendix B: Typing form comparison and prototype evidence

Prototype files (scratch only, under the ignored `.tmp/swc1/proto/` and `.tmp/colocation/`, never
committed), over the real strategy modules. Checked with `mypy --strict` (mypy 2.3.1, Python 3.12 target,
the repository's `mypy_path`).

### B.1 Results

| Run | Result |
| :--- | :--- |
| Core bundle `StrategyBehavior[SelT, ResultT]`, all four strategies, three narrow layer protocols (workspace, reporting, orchestrator), mappings built from the tuple | `Success: no issues found in 3 source files`. Real codecs, handler methods and `_execute_*` functions referenced unmodified. At run time every `*_for` method raises `UndeclaredStrategyError` for another strategy's object. |
| Nine mispairings of the core bundle: a replay, parser, handler, executor or encoder of another strategy; a missing `native_status`; `int` as selection or result type; a builder and projector of another strategy | All rejected (`arg-type`, `call-arg`, `type-var`), nothing else rejected. |
| Final form `StrategyBehavior[SelT, ResultT, DepsT]` with `ToolRuntime`, per-strategy dependency classes and real handler bodies (Momentum, FCF), evaluation tier (`pair_eval`), CLI-tier tuple of real command functions iterated into a Typer app | `Success: no issues found in 1 source file`. The Typer app registers `momentum` and `fcf-growth`; the tool mapping lists both tools. |
| Four mispairings of the final form: FCF fixture composition with the Momentum bundle, Momentum composition with the FCF bundle, an arguments class that is not an analysis-tool arguments model, an FCF handler in a Momentum bundle | All rejected. |
| CLI tier paired with the core bundle by selection type (`pair`), an FCF composition with the Momentum bundle | Rejected. |
| One hand-written `SelectionMember` list as both the pydantic discriminated union and the bound | The union parses at run time; `mypy --strict` rejects a non-member. |

No `Any`, `cast` or `type: ignore` appears in any prototype file. The one `Any` that appears in an error
message belongs to the repository's existing `StrictJsonMapping` alias.

### B.2 Options compared

| Form | Verdict | Evidence |
| :--- | :--- | :--- |
| A. `StrategyDescriptor[ConfigT, ResultT]` | Rejected. | No consumer reads `ConfigT`. A heterogeneous tuple needs `tuple[GenericDescriptor[Any, Any], ...]`; with `Any`, `registry[0].encode(FCFEarningsGrowthResult)` (an unsound call) type-checks silently. With `object` arguments, mypy rejects the tuple by invariance. |
| B. Erased `object` callables | Rejected. | `ErasedDescriptor(encode_momentum)` is rejected by parameter contravariance; each strategy function needs a `cast`, which removes the pairing check. |
| C. Dynamic `ToolName` from descriptor strings | Rejected. | `StrEnum("DynamicToolName", mapping)` errors ("must be string, tuple, list or dict literal for mypy to determine Enum members"), and `.ANALYZE_MOMENTUM` is then an attribute error. |
| D. Concrete instances with `Any` fields | Rejected on design grounds (not prototyped). | It is form A without even the type parameters, so it accepts the same unsound calls and has no pairing check. |
| E. One descriptor subclass per strategy | Rejected on design grounds (not prototyped). | It is a class hierarchy, which is the framework shape the plan prohibits. |
| F. Non-generic descriptor plus a generic `EvidenceCodec[ResultT: NativeEvidence]` behind a `Protocol` | Superseded. | Passes `mypy --strict` and rejects five mispairings, but pairs only the codec; every other strategy function mentioning the selection or result type was left to tests. |
| G. Non-generic descriptor plus one generic `StrategyBehavior[SelT, ResultT, DepsT]` behind a `Protocol`, with tiers paired by `pair_*` | **Chosen.** | Passes `mypy --strict`; rejects every mispairing across concerns and tiers; no `Any`, no `cast`; one explicit set of type arguments per declaration. |

## Appendix C: Import-cycle evidence

### C.1 Method

A scratch script parsed every module under `src` with `ast` (module-scope and nested imports), built the
module graph, added the edges each design variant implies, and searched for strongly connected components.
The baseline graph (163 modules at `247ecdf`) has no cycle. The co-location study extended the script to
function level: each top-level definition, and each member of the one class that is split, has its own set
of referenced names, resolved through the original file's import table; a move relocates a definition and
its outgoing edges follow it. With no moves the model reproduces the baseline graph exactly. A second
metric adds an edge from each module to every parent `__init__.py` that exists, because Python runs a
package's initialization first; the baseline has twelve benign components of this kind, all through
re-exporting `__init__` files. The model reads import statements; it does not execute them.

### C.2 Consumers-import-descriptor direction (the merged design's evidence)

| Variant | Descriptor module imports | Consumers that import it | Cycles |
| :--- | :--- | :--- | :--- |
| V0 | nothing (identifiers and versions only) | codecs, execution, `project_run`, `analysis_tools`, evaluation, CLI, aliases | 0 |
| V1 | V0 plus the four codec modules | same | 0 |
| V2 | V1 plus `analysis_tools` for the argument models | same | 1: `analysis_tools` and the descriptor module |
| V3 | V2 plus `reporting.analysis_runs` for projectors | same | 1 of 4 modules |
| V4 | V1 plus `execution` normalizers and `cli_workspace` executors | same | 1 of 8 modules |
| Chosen then | codec modules, FCF constants, `native_evidence`, `tool_names`, `analysis_tool_arguments`, the four envelope leaves | all consumers across `orchestrator`, `workspace`, `data.repositories`, `reporting`, `evaluation`, `cli*` | 0 module cycles; one initialization cycle of 9 modules (C.4) |

V2 is fixed by moving the argument models out of `analysis_tools.py`. V3 and V4 are not fixed by
reordering when the consumers import the descriptor: projectors sit above `codecs`, and executors need
production providers and the CLI's composition. That direction was the only one tested, and it is why the
merged design kept handlers, executors and projectors in consumer-owned tables. C.3 tests the other.

### C.3 Strategy-owned modules, and the descriptor at the composition root

| Variant | Modules | Module cycles | Importers of the descriptor (foundation or reporting) | Initialization cycle with the descriptor |
| :--- | :--- | :--- | :--- | :--- |
| Baseline `main` | 163 | 0 | n/a | n/a |
| Consumer tables, consumers import the descriptor (merged design) | 170 | 0 | 19 (11) | 9 modules |
| Strategy-owned modules, consumers import the descriptor, as built naively | 190 | 1, of 23 modules | n/a | n/a |
| As above with six fixes | 192 | 0 | 12 (5) | 25 modules |
| As above, CLI functions in a second tier | 193 | 0 | 12 (5) | 15 modules |
| Descriptor at the root, single tier | 192 | 0 | 6 (0) | none |
| **Descriptor at the root, two tiers, injected (adopted)** | 193 | 0 | 6 (0) | none |
| Adopted shape with commands in strategy files, an evaluation tier, one types file and per-strategy dependency classes | 202 | 0 | 6 (0): `cli_strategy_wiring` and five evaluation modules | none |

The naive strategy-owned form first fails with `strategy_wiring` to `fcf_growth_replay` to
`reporting.fcf_earnings_growth` to `strategy_wiring`: a presenter imports the descriptor for identity
strings and the replay leaf imports the presenter. With the consumers importing the descriptor, six
fixes are each necessary; with the descriptor at the root, only the identity leaf is:

| Fix | Reintroduced edge | Consumers import descriptor | Descriptor at root |
| :--- | :--- | :--- | :--- |
| Selection classes leave `requests.py` | descriptor to `requests.py` for the parsers | cycle | no cycle |
| `ExecutionCapture` and normalizers leave `execution.py` | CLI files to `execution.py` | cycle | no cycle |
| Dependency bundle leaves `analysis_tools.py` | handler files to `analysis_tools.py` | cycle | no cycle |
| `ReplayOptions` and the error type leave `analysis_runs.py` | replay files to `analysis_runs.py` | cycle | no cycle |
| Projectors take decoded evidence, not the run | replay files to `codecs.py` | cycle | no cycle |
| Presenters read identity from a dependency-free leaf | presenters to the descriptor | cycle | cycle |
| `cli_support` reads identity from the same leaf | `cli_support` to the descriptor | cycle | cycle |

In both directions the CLI functions leave `cli_workspace.py` and the status table leaves
`evaluation/runner.py`, because those modules import the descriptor and would otherwise sit in a cycle with
it. The moves in the first five rows are still scheduled, for locality (D19), but none is needed for
acyclicity.

Package-level reach (the packages a package's modules newly reach compared with `main`): in the merged
design the foundation layers reach four dependency-free reporting leaves; with strategy-owned modules and
the consumers importing the descriptor, they reach 18 reporting modules and six CLI modules; in the adopted
shape the foundation layers and `reporting` newly reach nothing, and `evaluation` newly reaches `workspace`
and `reporting`, exactly as in the merged design.

### C.4 Initialization cycle

`src/workspace/__init__.py` imports `src.workspace.requests`. In the merged design `requests.py` imports
the descriptor and the descriptor imports `src.workspace.momentum` and the other codec modules, so the
descriptor, `src.workspace` and seven of its modules form an initialization cycle. A reproduction with the
same shape (`pkg/__init__.py` imports `pkg.req`, which imports `wiring`, which imports `pkg.codec`):
importing `wiring` first raises `ImportError: cannot import name 'BY_ALIAS' from 'wiring'`; importing
`pkg.req` or `pkg.codec` first succeeds. The failure is order-dependent. Emptying
`src/workspace/__init__.py` removes the cycle in every consumers-import variant, and the adopted shape is
immune because nothing under `workspace` imports the descriptor. D15 does both.

### C.5 Layering with the types in one file

`ToolName` cannot join the workspace types file: once `register_analysis_tools` checks its handlers against
`ToolName`, merging the two makes `orchestrator` newly reach `workspace`. `NativeEvidence`, `SelectionMember`
and `AnalysisSelection` share one workspace-layer file with no new reach and no cycle.

### C.6 One package per strategy

The adopted shape was re-modelled with every strategy-owned file at `src/strategies/<strategy>/<role>.py`
(analyzer modules, `selection`, `codec`, `execution`, `tool`, `presenter`, `envelope`, `replay`, `cli`,
`evaluation`), shared code in `_shared` and `_graham`, the three re-exporting analyzer-package
`__init__.py` files emptied (their importers resolve to the submodule that defines each name), every
`__init__.py` under `src/strategies/` empty, and `src/workspace/__init__.py` empty.

| Check | Result |
| :--- | :--- |
| Modules | 208, no module-level cycle. The graph is the layer-folder graph with new paths. |
| Initialization-aware components | Eight, all through the re-exporting `__init__.py` of `data.sec_edgar`, `data.massive`, `data.yfinance`, `schema`, `core.telemetry`, `evaluation`, `evaluation.fixtures` and `evaluation.cases`; none contains the root, a tier or any `src/strategies` module. On `main` there are twelve; emptying `workspace` and the three analyzer packages removes four. |
| Edges between strategy packages | None. |
| Role-to-role edges observed inside packages | `cli` to execution, presenter, selection and analyzer; `execution` to selection and analyzer; `replay` to presenter, selection and analyzer; `presenter` to envelope and analyzer; `tool`, `codec` and `selection` to analyzer; `evaluation` to tool and analyzer. All go from a higher rank to a lower one, so the ranks in [§4](#4-static-declaration-model) are a total order the real graph already obeys. |
| Edges from outside into `src/strategies` | Foundation, `cli_composition` and generic evaluation import analyzer and selection roles only; `cli_workspace` imports analyzer and selection; the root imports analyzer, codec, envelope, replay, selection and tool; the CLI tier imports `cli`; the evaluation tier imports `evaluation`. |
| Violations of the role rule in the real graph | None, after the Graham family package below. |

One finding changed the layout. The shared Graham replay helper imports the `calculation` modules of both
Graham strategies for its constrained type variable, so a single `_shared` package would import strategies.
The layout therefore has two homes: `_shared/profile.py`, which imports no strategy and serves three, and
the `_graham` family package, which may import only the analyzer modules of its two members and which only
they may import.

**Deliberate violations, each rejected by the role rule:**

| Violation added to the real graph | Rule that rejects it |
| :--- | :--- |
| `workspace.codecs` imports Momentum's `codec` | Outside modules import analyzer and selection roles only |
| Momentum `codec` imports Momentum `cli` | A role never imports a higher or equal rank |
| Momentum `tool` imports FCF `tool` | No strategy imports another |
| `_shared/profile` imports Momentum's analyzer | `_shared` imports no strategy |
| `reporting.analysis_runs` imports the root | No foundation or reporting module imports the root or a tier |
| The root imports Momentum's `cli` | The root imports core roles only |
| `data.repositories.watchlists` imports FCF's `cli` | Outside modules import analyzer and selection roles only |
| Momentum `presenter` imports Momentum `replay` | A role never imports a higher rank |
| Momentum `tool` imports Momentum `execution` | A role never imports an equal rank |
| The CLI tier imports an `evaluation` file | The CLI tier imports `cli` only |
| `workspace.execution` imports FCF's `presenter` | Outside modules import analyzer and selection roles only |
| FCF `replay` imports the Graham family | Only family members import it |
| The Graham family imports FCF's analyzer | A family imports its members' analyzer modules only |

Three edges the rule must still allow were accepted: Momentum `cli` to `execution`, `workspace.strategy_types`
to FCF's `selection`, and the root to Momentum's `replay`.

**Relocation cost.** Importers of the relocated modules: 101 files (33 in `src`, 68 in `tests`), of which
97 import `src.analysis.strategy.*`, 18 the adapters, 12 the presenters, 4 `graham_shared`, one the codecs
(counts overlap), and 15 tests name moved modules in patch strings. Thirteen of the 101 import names the
analyzer packages re-export, which now resolve to the defining submodule. Living documents that name the old
paths: `docs/project/ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md` and the Step 3.5 strategy specifications; the
other 37 documents that name them are historical records. Path-based tests change: the BaseAnalyzer
conformance test's boundary constants, T3's package walk (now over `src/strategies`, skipping packages
whose name starts with an underscore), and the retargeted patch strings, which the new resolution test verifies (`mypy --strict` cannot see a string
target, so a patch of a moved name would otherwise pass silently); every other path-based check reads a path
from the site data file.

## Appendix D: Current failure shapes

| Family | Where | Shape today | Codes today |
| :--- | :--- | :--- | :--- |
| Direct `--json` | `execution_errors` and `analysis_failure_document`, `schema_version` 5 | `analysis`, `method`, `ticker`, `status`, `reason_code`, `reason` (prose), `result: null`, `diagnostics`. | `execution_error`, `historical_quality`, `provider_error`, `configuration_error`, `no_eligible_observations`, `invalid_input`, and the nine `ReadinessReason` values. |
| Workspace | `_fail` | Plain text on stderr, exit 1, regardless of `--json`. | none |
| Database | `DatabaseMaintenanceReport`, `schema_version` 1 | `command`, `status` (`success` or `error`), `database_path`, `state`, `current_revision`, `expected_revision`, `reason` (code), `message` (prose). | The `ReadinessReason` values. |

Two further findings: the direct failure document's `schema_version` is 5 for every strategy while
the Graham success documents carry 6, so the field is a failure-document version and not the
analysis presentation version its docstring describes; and `DatabaseReadinessError` exposes
`expected_revision` and `database_path` as typed properties that the direct failure document renders
only inside prose.

## Appendix E: Adoption of the co-location result

Recorded for the history. Nothing here is needed to understand the design above.

After SWC.1 merged, a [co-location study](SWC_COLOCATION_STUDY.md) compared the merged design (consumer-owned
keyed tables) with strategy-owned modules in the current folders, one package per strategy, and a
descriptor at the composition root with each layer's slice injected. The project owner decided:

1. **Adopt the third form, in two tiers**, as this design now describes it.
2. **Schedule the locality moves** in the slice that owns each; none is deferred.
3. **Fix the initialization cycle in SWC.2a** and make the layering test count parent packages.
4. **Reduce the edit sites further**, adopting each reduction the import-graph model and a `mypy --strict`
   prototype support.
5. **Add contributor tooling** ([§19](#19-contributor-tooling)).
6. **Add a repetition checkpoint to Step 3.5** and a folder-layout decision to the package-rename plan.

### E.1 Reductions tested

| Edit today | Result | Evidence |
| :--- | :--- | :--- |
| The strategy's command in `src/cli.py` | **Adopted.** The command lives in the strategy's CLI file; `cli.py` iterates the closed CLI tier. A strategy file never registers itself (A12). | The model with the four commands and their helpers moved, and `_maybe_save_run` and `get_cli_run_context` in a new `cli_run_support.py`, has no cycle and no new layer reach. The prototype's command member is `Callable[..., None]`; iterating a closed tuple into a Typer app registered the real `momentum` and `fcf-growth` functions. Cost: thirteen test modules patch `src.cli.` names (76 patch strings) and are retargeted in SWC.3c. |
| Alias mentions in `USAGE.md` and `WORKSPACE.md` | **Adopted.** Marked blocks are generated from the descriptors and drift-tested (T26). The watchlist option table's per-strategy prose moves into the strategy guides; the guide filename follows a rule, and `FCF_EARNINGS_GROWTH.md` is renamed `FCF_GROWTH.md`. | The pages hold the `ian <alias> --help` lines in `USAGE.md` and the `--analysis` sentence and option table in `WORKSPACE.md`; the lists derive from `alias` and `label`, the prose does not. |
| Fixture requirement and fixture composition in `evaluation/composition.py` | **Adopted** as the evaluation tier. Fixture values, expected outcomes and case truth stay hand-written. | The model with per-strategy evaluation files, a fixture context, a fixture-identifier leaf and a tier tuple has no cycle; `evaluation` reaches only what it reached under the merged design. The prototype pairs each composition with its bundle by dependency type and rejects two mispairings. |
| Dependency-bundle fields (`AnalysisToolDependencies`) | **Adopted.** Each strategy owns a dependency class in its `<strategy>_tool.py`; a shared `ToolRuntime` carries the clock and profile resolver. | The final-form prototype builds real Momentum and FCF handlers from per-strategy bundles and rejects an FCF handler in a Momentum bundle. |
| The `AnalysisToolArguments` union | **Adopted.** The shared base class takes the name and the union is deleted. | The consumers read only `ticker`, `as_of` and `model_dump`. A descriptor typed `type[AnalysisToolArguments]` rejects a class that is not an arguments model. |
| `NativeEvidence` and `AnalysisSelection` in separate files | **Adopted** in one workspace-layer file with `SelectionMember`. | No new reach, no cycle. |
| `ToolName` in the same file | **Rejected.** | Once `register_analysis_tools` checks its handlers against `ToolName`, merging makes `orchestrator` newly reach `workspace`. The enum stays a leaf. |
| `evaluation/catalog.py` | **Rejected, in part.** The `_arguments` chain moves beside the case modules (SWC.2c). The case tuple and suite version stay. | They are reviewed evaluation truth: adding a case must bump `DETERMINISTIC_SUITE_VERSION` by hand, and a derived membership would let it change silently. |
| The three tier tuples as one | **Rejected.** | One tuple would have to import the CLI and evaluation files, which makes `evaluation` reach the CLI composition helpers, or the reverse. |
| The tuple entry in `strategy_wiring.py` | **Kept.** | It is the declaration. |

### E.2 Edit sites, before and after

| | Merged design | Co-location study's form | Adopted, with the reductions |
| :--- | :--- | :--- | :--- |
| Hand-edit sites | 23 | 24 | 18 |
| Existing files edited | 15 | 11 | 6 |
| New files | 10 | 14 | 15 |
| Distinct files | 25 | 25 | 21 |
| Directories | 11 | 11 | 11 |
| One-line restatements in generic-owned files | 11 | 6 | 5 |
| Omissions that are type errors | 0 | 7 | 8 |
| Existing-file edits made by a generator | 0 | 0 | 5 |

### E.3 Renumbering

| Before | After | Why |
| :--- | :--- | :--- |
| SWC.2a, SWC.2b | SWC.2a, SWC.2b, SWC.2c | The descriptor and handlers are one coupled change; the evaluation tier is a move-and-pair. |
| SWC.3 | SWC.3a, SWC.3b, SWC.3c | Workspace consumers, the CLI tier and the direct commands are three reviewable concerns. |
| SWC.4a to SWC.4c | unchanged | |
| (none) | SWC.5, SWC.6 | Site data, status command and generated lists; specimen and generator. |
| SWC.5 | SWC.7 | The guide's table is generated from the site data, so the guide comes last. |

Links that named SWC.5 as the contributor guide's slice (the milestone documents, the Master Plan, the
Discovery Workbook and the Step 3.5 plan) now name SWC.7.

### E.4 Final amendments before merge

Three further decisions, made while finalizing the design:

1. **The side-by-side table is built first.** It moved from the end of Step 3.5 to its first slice, 3.5.0,
   over the four existing strategies. The `headline` member therefore has a consumer before any new
   analyzer is written and is added once; that slice updates the four declarations, the generator's
   templates, the site data file, the specimen and the closed-field test together. The Step 3.5 slices
   were renumbered by adding 3.5.0 and moving the golden suite from 3.5.8 to 3.5.7.
2. **Native status is a Step 3.5 decision.** The rule this design had proposed (one headline metric
   reports its status, several report none) is removed; every Step 3.5 result carries an explicit
   result-level status that its native-status function returns, defined in the Step 3.5 shared
   definitions. Momentum's `None` is unchanged.
3. **One package per strategy, now.** The folder-layout decision the package-rename plan had left open was
   settled here because SWC.2a onward create the strategy-owned files and SWC.5 and SWC.6 build tooling
   around their locations. The adoption condition was that a role-based layering rule is enforceable and
   rejects a deliberate violation, and that the module graph shows no new cycle with every
   `__init__.py` under `src/strategies/` empty. Both held ([Appendix C.6](#c6-one-package-per-strategy)), so
   the layout is adopted. The package-rename plan records the outcome.

Slice renumbering: the existing strategy modules are relocated by a new first slice, so SWC.2a (symbol
moves) became SWC.2b, SWC.2b (descriptor) became SWC.2c and SWC.2c (evaluation tier) became SWC.2d. The
renumbering table in [E.3](#e3-renumbering) uses the numbers in force when it was written.

Directory count. The study's figure of nine directories for one package per strategy counted `docs/user`,
whose strategy lists are now generated, so no hand edit remains there; the adopted design's figure is eight,
the same as the package-rename plan's.
