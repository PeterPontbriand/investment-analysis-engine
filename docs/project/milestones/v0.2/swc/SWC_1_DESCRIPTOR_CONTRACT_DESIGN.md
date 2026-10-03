# SWC.1 — Descriptor Contract and Conformance Design

Settles the descriptor, failure-envelope and conformance contracts that SWC.2a–SWC.5 implement. The
[SWC plan](SWC_CONTRACT_AND_SLICE_PLAN.md) owns scope, sequence and status; this document owns the
design detail. Nothing under `src/`, `tests/`, `scripts/`, `config/`, `alembic/`, `pyproject.toml` or
`uv.lock` changes in SWC.1.

## 1. At a glance

- **What it settles:** the descriptor's exact fields and exclusions, where it lives and how consumers
  reach it, its relation to `BaseAnalyzer`, each generic consumer, the typing form (proved with a
  `mypy --strict` prototype), the conformance tests and their negative control, the per-slice
  migration, the framework-drift checks, the typed failure envelope and the typed model and schema for
  every `--json` document.
- **The shape in one sentence:** one frozen, non-generic `StrategyDescriptor` per strategy, declared in
  a closed tuple in `src/strategy_wiring.py`, holding identifiers, vocabulary, versions and the
  strategy-owned references that more than one layer needs; behavior that needs production
  dependencies (tool handlers, refresh executors, replay projectors, selection parsers and builders)
  stays in consumer-owned keyed tables whose keys the conformance suite checks against the descriptors.
- **What it is not:** a registry, plugin point or factory. It holds no analyzer class, config type,
  dependency or construction logic. `BaseAnalyzer[ConfigT, ResultT]`, `AnalysisContext` and every
  strategy's config and result type are untouched ([§5](#5-relation-to-baseanalyzer)).
- **Rules it follows:** no formula or classification change; fail closed with no default strategy; no
  stored-shape change is expected; no compatibility re-exports; every field has an audited consumer;
  every design question below ends in a decision.
- **Fit and cost:** the design holds for all seven Step 3.5 strategies with two changes made now
  ([§16](#16-step-35-fit-check)). Adding a strategy touches 23 hand-edited sites, each guarded by a
  named test ([§17](#17-edit-sites-for-a-new-strategy)). Findings the audit left unowned are now
  assigned ([§18](#18-findings-assigned-to-a-slice)).
- **Corrections to the plan:** [§15](#15-ir2-and-corrections-to-the-plan) lists where the audit
  disagreed with the SWC plan and what changed.
- **Where the dry material lives:** the re-verified inventory is in
  [Appendix A](#appendix-a-inventory-re-verified-at-247ecdf), the typing comparison in
  [Appendix B](#appendix-b-typing-form-comparison-and-prototype-evidence), the import-cycle evidence in
  [Appendix C](#appendix-c-import-cycle-evidence), and the current failure shapes in
  [Appendix D](#appendix-d-current-failure-shapes).

## 2. Decisions

| # | Decision | Detail |
| :--- | :--- | :--- |
| D1 | One non-generic frozen `StrategyDescriptor` per strategy, in a closed tuple `STRATEGIES` in `src/strategy_wiring.py`. | [§3](#3-descriptor-fields-and-exclusions), [§4](#4-static-declaration-model) |
| D2 | Thirteen fields, each with an audited consumer, introduced by the slice whose consumer needs it. | [§3.1](#31-fields) |
| D3 | Only the evidence codec is generic (`EvidenceCodec[ResultT: NativeEvidence]`), erased behind a `Protocol` view. | [§8](#8-typing-form) |
| D4 | `ToolName` stays a hand-written `StrEnum` (the one declaration of tool-name strings) and each descriptor binds one member. `ToolName`, the argument models and `NativeEvidence` move with no compatibility re-export; importers are updated. | [§9.1](#91-toolname) |
| D5 | Tool handlers, refresh executors, replay projectors, selection parsers and builders, native-status accessors and fixture requirements stay in consumer-owned keyed tables, not descriptor fields. | [§6](#6-generic-consumers), [Appendix C](#appendix-c-import-cycle-evidence) |
| D6 | Dispatch fails closed through one `UndeclaredStrategyError`; no strategy is a default branch anywhere. | [§9.2](#92-fail-closed-dispatch) |
| D7 | One shared `FailureEnvelope` for direct and workspace `--json` failures. `DatabaseMaintenanceReport` is a sibling that adopts the envelope's field names for the code and the prose. | [§13](#13-failure-envelope-contract) |
| D8 | Momentum profile composition becomes `compose_momentum_profile` in `src/workspace/momentum_execution.py` with its own signature. | [§14](#14-momentum-profile-composition-helper) |
| D9 | No IR.2 contract change is required. | [§15](#15-ir2-and-corrections-to-the-plan) |
| D10 | Conformance compares the descriptors to independent surfaces and includes a three-part negative control. | [§10](#10-conformance-tests-and-negative-control) |
| D11 | Every `--json` document gets a typed model and a checked-in generated schema. SWC.4 is split into SWC.4a, SWC.4b and SWC.4c. | [§11](#11-migration-from-current-declarations), [§13.6](#136-every-json-document-is-typed) |
| D12 | Per-job failures in `refresh --json` carry a `reason_code` from the same vocabulary, alongside their existing text. | [§13.4](#134-what-changes) |
| D13 | The design fits all seven Step 3.5 strategies. Two changes are made now: the command-coverage test and the keyed-table replacement of four remaining `if` chains. | [§16](#16-step-35-fit-check) |
| D14 | Every finding the audit left unowned is assigned to a slice. | [§18](#18-findings-assigned-to-a-slice) |

## 3. Descriptor fields and exclusions

### 3.1 Fields

A field exists only because a named consumer needs it, and replaces a named declaration. "Introduced"
is the slice whose consumer first reads it; a later slice adds the field, not SWC.1.

| Field | Type | Introduced | Consumers | Declarations replaced |
| :--- | :--- | :--- | :--- | :--- |
| `analysis_id` | `str` | SWC.2b | The `(analysis_id, method_id)` key of every index; conformance; later codecs, run envelope, replay, refresh, JSON builders. | Key literals in `_METHOD_VERSIONS`, `_EXPECTED_VERSIONS`, `project_run` (4 pairs), six `execution_errors(analysis=, method=)` calls, three reporting JSON builders, the string tests inside `decode_evidence`. |
| `method_id` | `str` | SWC.2b | As `analysis_id`; also `RunQuery`, watchlist alias lookup. | As above, plus the values of `ALIAS_METHOD_IDS`. |
| `tool` | `ToolName` | SWC.2b | Tool registration; evaluation routing; the local Ollama runner. | The four `ANALYZE_*_TOOL` constants; the three `_tool_name` isinstance chains. |
| `tool_arguments` | `type[BaseModel]` | SWC.2b | The argument-model view (`ANALYSIS_TOOL_ARGUMENT_MODELS`); Ollama validation, schema and parser; `tool_for_arguments`. | The literal `ANALYSIS_TOOL_ARGUMENT_MODELS` dict; the three `_tool_name` chains. |
| `tool_description` | `str` | SWC.2b | Ollama tool-schema JSON and parser registry. | `_TOOL_DESCRIPTIONS`. |
| `evidence` | `EvidenceView` | SWC.2b (type test), SWC.3 (codec) | `evaluation.runner._native_result` (type membership); `encode_evidence`; `decode_evidence`. | The `encode_evidence` and `decode_evidence` isinstance chains; four inline ticker-identity blocks; the runner's isinstance tuple. |
| `alias` | `str` | SWC.3 | `parse_selection`; `_parse_analysis`; alias-to-method lookups; `alias_for_method_id`; help text. | `method_aliases.py` (three tables); the alias tuple in `parse_selection`. |
| `label` | `str` | SWC.3 | `encode_evidence` and `decode_evidence` error text. | The two four-way label chains in `codecs.py`. |
| `config_schema_version` | `int` | SWC.3 | `decode_evidence`. | `_EXPECTED_VERSIONS`. |
| `method_version` | `int` | SWC.3 | `execute`; `decode_evidence`. | `_METHOD_VERSIONS`; `_EXPECTED_VERSIONS`. |
| `result_schema_version` | `int` | SWC.3 | `execute`; `decode_evidence`. | `_METHOD_VERSIONS`; `_EXPECTED_VERSIONS`. |
| `evidence_codec_version` | `int` | SWC.3 | `execute` (writes it); `decode_evidence` (checks it). | The literal `1` in `execute` and the `!= 1` test in `decode_evidence`. |
| `json_envelope` | `type[BaseModel]` | SWC.4c | The schema generator; the JSON builders' output-boundary validation. | Nothing today; this is the typed output contract IR.5 moved here. |

Notes:

- **Single source for FCF.** `STRATEGY_ID`, `METHOD_ID`, `METHOD_VERSION` and `SCHEMA_VERSION` already
  exist in `src/analysis/strategy/fcf_earnings_growth/models.py`. The FCF descriptor references them
  instead of re-declaring them. Momentum and Graham have no such constants, so their descriptors are the
  declaration.
- **`config_schema_version` duplicates a selection field on purpose.** Each selection class keeps its
  own `Literal[...]` identifiers and version, which type the `AnalysisSelection` discriminated union.
  Conformance test T1 compares them to the descriptor; it does not remove them.
- **No per-slice field is speculative.** `json_envelope` is the only field with no replaced
  declaration. It stays because SWC.4c's generator and conformance test both iterate it; if SWC.4c finds
  otherwise, the field is dropped in that slice and the generator keeps a consumer-side list.

### 3.2 Exclusions

The descriptor must not hold, and no field may be added for:

- config, policy or selection types (no consumer; the selection union is compared, not derived);
- analyzer classes, analyzer construction, injected dependencies, provider identifiers, clocks;
- tool handlers, refresh executors, capture types, outcome classifiers, replay projectors, presenters
  (consumer-owned, [§6](#6-generic-consumers));
- formulas, thresholds, classification, calculation status, or any strategy policy;
- envelope-wide versions (`run_schema_version`, `projection_version`) and the per-document
  `schema_version` of each JSON builder (owned by `AnalysisRun` and by the envelope models);
- a generic result supertype, a registration function, a discovery hook or a factory.

## 4. Static declaration model

- **Location:** `src/strategy_wiring.py`, one module. Four module-level constants (`MOMENTUM`,
  `GRAHAM_NUMBER`, `GRAHAM_GROWTH`, `FCF_GROWTH`) and the closed tuple
  `STRATEGIES = (MOMENTUM, GRAHAM_NUMBER, GRAHAM_GROWTH, FCF_GROWTH)`. Adding a strategy is a source
  edit to this tuple.
- **How consumers obtain it:** an ordinary module-scope import,
  `from src.strategy_wiring import STRATEGIES, BY_KEY, ...`. No decorator, no registration call, no
  side effect on import beyond building the indexes.
- **Static index:** read-only `Mapping`s derived once at import by one private helper from the tuple:
  `BY_KEY`, `BY_METHOD_ID`, `BY_ALIAS`, `BY_TOOL`, `BY_ARGUMENTS`, `BY_EVIDENCE` and (SWC.4c)
  `BY_ENVELOPE` (keyed by `(analysis_id, method_id)`, `method_id`, `alias`, `ToolName`, the
  argument-model type, the evidence result type and the envelope model type). The builder is a pure
  function of the tuple, so tests can call it on a modified copy. The helper raises at import if a key repeats, so a duplicate declaration
  cannot load. Iteration order is declaration order.
- **Lookup:** one `require(index, key)` helper raises `UndeclaredStrategyError`
  ([§9.2](#92-fail-closed-dispatch)). `find` variants return `None` for the two consumers that must
  keep their existing exception types.
- **Import direction:** consumers import the descriptor module; the descriptor module imports only
  strategy-owned leaves. Its allowed imports are `src.analysis.strategy.fcf_earnings_growth.models`,
  the four strategy codec modules (`src.workspace.momentum`, `graham_number`, `graham_growth`,
  `fcf_growth`), `src.workspace.native_evidence`, `src.orchestrator.tool_names`,
  `src.orchestrator.analysis_tool_arguments`, and from SWC.4c the four strategy envelope modules
  `src/reporting/envelopes/<strategy>.py`, which import only pydantic and `src.core`. The workspace,
  failure and database document models live in a separate package, `src/reporting/documents/`, which the
  descriptor module does not import, because `documents.watchlist` imports `workspace.requests`, and
  `requests.py` imports the descriptor module.
- **No cycles, verified.** The module-level import graph of `src` has no cycle today. Modelling the
  design, including every consumer across `orchestrator`, `workspace`, `data.repositories`,
  `reporting`, `evaluation` and the CLI, still has none (163 modules plus the fifteen the design adds). Three plausible wider designs
  do create cycles; they are why D5 exists. Evidence: [Appendix C](#appendix-c-import-cycle-evidence).
  Test T13 makes this a permanent guard.
- **Prerequisite moves, with no compatibility re-exports** (made by SWC.2a): `ToolName` to
  `src/orchestrator/tool_names.py`; the four `*ToolArguments` models, `FiniteFloat` and
  `PositiveFiniteFloat` to `src/orchestrator/analysis_tool_arguments.py`; the `NativeEvidence` union to
  `src/workspace/native_evidence.py`. After the move each has exactly one import path. The importers
  are updated in the same slice: seventeen modules import `ToolName` (ten under `src/evaluation/`,
  seven test modules); eleven import the argument models or the constants derived from them (four
  under `src/evaluation/`, seven test modules); only `src/workspace/execution.py` uses
  `NativeEvidence`. No public package export has to stay: `src/evaluation/__init__.py` exports
  `ToolName` today, but nothing imports it from the package (a search of `src/`, `tests/` and `docs/`
  finds no `from src.evaluation import`), so that export is removed. `docs/EVALUATIONS.md` and
  `docs/project/ARCHITECTURE.md` name the moved symbols and are updated in SWC.2a.

## 5. Relation to `BaseAnalyzer`

The invocation envelope is unchanged and the descriptor does not enter it.

- `src/analysis/base_analyzer.py` is not edited by any SWC slice. `BaseAnalyzer.run_analysis(self,
  ticker, config, context)` and the four `AnalysisContext` fields (`as_of`, `executed_at`,
  `use_cache`, `instrument_profile`) keep their signatures.
- No descriptor field is typed `ConfigT`, names an analyzer class, or constructs one. Handlers and
  adapters still receive dependencies at construction, build `AnalysisContext` at their execution
  boundary, and call `analyzer.run_analysis(ticker=..., config=..., context=...)`.
- The one coupling is declarative: `EvidenceCodec.result_type` must equal the `ResultT` the strategy's
  analyzer declares. Test T3 compares them against each analyzer's own `BaseAnalyzer[ConfigT, ResultT]`
  specialization, so the coupling is checked, not assumed. Test T17 pins the envelope's signature and
  `AnalysisContext` fields.

## 6. Generic consumers

"Derives" is read from the descriptor or its index. "Explicit" stays hand-written and strategy-owned.
Consumer-owned tables are keyed by `(analysis_id, method_id)`, alias, `ToolName` or result type, fail
closed on a missing key, and are checked against the descriptors by T10.

| Slice | File and symbol | Derives from the descriptor | Stays explicit |
| :--- | :--- | :--- | :--- |
| SWC.2b | `src/orchestrator/analysis_tools.py`: `register_analysis_tools` | Iterates `STRATEGIES`; tool name per entry. | The four handler methods, `AnalysisToolDependencies`, config construction, and one `ToolName`-keyed table of bound handlers. |
| SWC.2b | `analysis_tools.py`: `ANALYSIS_TOOL_ARGUMENT_MODELS`, the four `ANALYZE_*_TOOL` constants | Deleted. Consumers read `BY_TOOL`. | The argument models, moved to `analysis_tool_arguments.py` in SWC.2a. |
| SWC.2b | `src/evaluation/composition.py`, `runner.py`, `ollama_runner.py`: three `_tool_name` | One `tool_for_arguments` over `BY_ARGUMENTS`. | The `AnalysisToolArguments` union (typing; compared by T4), fixture composition, `catalog.py`, case expectations. |
| SWC.2b | `composition.py`: `_require_tool_evidence` | Table keys. | An `if`/`else` chain over `ToolName` whose last branch makes FCF the default becomes a `ToolName`-keyed table of fixture requirements; an unknown tool raises. |
| SWC.2b | `ollama_runner.py`: `_TOOL_DESCRIPTIONS`, `_tool_schemas_json`, `_tool_parser`, `_selection_observation` | Description and argument model per tool; `ToolName` lookup replaces the private `_value2member_map_`. | Prompt construction and observation evidence. |
| SWC.2b | `evaluation/runner.py`: `NativeAnalysisResult`, `_native_result`, `_native_status` | Result-type membership via `BY_EVIDENCE`; the duplicate union becomes `NativeEvidence`. | `_native_status` becomes a table keyed by result type of per-type accessors (Momentum's returns `None`, [§7](#7-strategy-specific-escape-hatches)); the chain whose last branch makes FCF the default is gone. |
| SWC.2a | `evaluation/models.py`: `ToolName`; `core/constants.py`: `AnalysisType` | `ToolName` moves; no re-export. `AnalysisType` is deleted. | The enum members. |
| SWC.3 | `workspace/codecs.py`: `encode_evidence`, `decode_evidence`, `_EXPECTED_VERSIONS` | Exact-type lookup for encode; key lookup, expected versions, label, ticker identity and codec for decode. | Each strategy's `encode_*`/`decode_*`, validation and provenance rules. |
| SWC.3 | `workspace/execution.py`: `_METHOD_VERSIONS`, `execute` | Method, result and codec versions. `getattr(selection, "as_of", None)` becomes `selection.as_of` (every union member has it). | `NativeEvidence`, `ExecutionCapture`, the four `from_*_capture` normalizers. |
| SWC.3 | `workspace/requests.py`: `parse_selection`; `workspace/method_aliases.py` | Alias membership; the alias vocabulary replaces `method_aliases.py` (deleted). | The per-alias `if` chain, whose last branch is an unconditional Momentum return, becomes an alias-keyed table of strategy-owned parsers. The four selections. |
| SWC.3 | `data/repositories/watchlists.py`: alias lookup in the unreadable-entry message | `find` by `method_id`, tolerant of an unknown stored method. | The message wording. |
| SWC.3 | `cli_workspace.py`: `_parse_analysis`, `ALIAS_METHOD_IDS` and `alias_for_method_id` uses, `--analysis` help | Alias and method-id lookups; help text from `STRATEGIES`. | `_execute_*` composition and the watchlist option set. |
| SWC.3 | `cli_workspace.py`: `_build_selection` | Table keys. | The `if method == ...` chain, whose last branch is an unconditional FCF return, becomes an alias-keyed table of strategy-owned builders over one frozen flag bundle. |
| SWC.3 | `cli_workspace.py`: `_refresh_executor` | A table keyed by `(analysis_id, method_id)` of the existing `_execute_*`; a missing key raises `UndeclaredStrategyError`. | Provider and cache composition inside each `_execute_*`. |
| SWC.3 | `cli.py` and `cli_workspace.py`: three Momentum composition copies | None. | One `compose_momentum_profile` ([§14](#14-momentum-profile-composition-helper)). |
| SWC.4a | `cli_support.py`: `execution_errors`; `reporting/presentation.py`: `analysis_failure_document`; `cli.py`: `execution_errors(analysis=, method=)` calls | Identity for the envelope (`analysis`, `method`). | Failure classification. The `analysis == "momentum"` string test becomes an explicit parameter passed by the Momentum command. |
| SWC.4a | `cli_workspace.py`: `_fail` and its `--json` call sites; `workspace/refresh.py` | None. | One exception-to-code classifier in `reporting/failure_classification.py` ([§13](#13-failure-envelope-contract)); `refresh_watchlist` receives it as a parameter. |
| SWC.4b | `cli_workspace.py` JSON builders for watchlist, delete outcome, runs list and refresh summary | Nothing per strategy; `method_id` strings stay `str`. | The documents, now typed. `entries[].selection` is typed by the `AnalysisSelection` union ([§13.6](#136-every-json-document-is-typed)). |
| SWC.4c | `reporting/analysis_runs.py`: `project_run` | A projector table keyed by `(analysis_id, method_id)`; a missing key raises `UnsupportedProjectionError`. | The four `_project_*_v1` functions and their captured-value rules. |
| SWC.4c | `reporting/{momentum,graham_number,graham_growth}.py` builders | `analysis` and `method` strings. | Builders and presenters. FCF reads its native ids; T9 compares every rendered document to the descriptor. |
| SWC.4c | Schema generator and `reporting/json_documents.py` | `json_envelope` per strategy. | The failure, workspace and database documents are listed once, outside the descriptor. |

## 7. Strategy-specific escape hatches

A strategy may legitimately differ in the following, and each is expressed by a strategy-owned
function or type that the descriptor does not model:

| Difference | How it is expressed |
| :--- | :--- |
| Config, selection and result types | Strategy-owned classes; the selection union and `NativeEvidence` union are hand-written and compared by T1 and T2. |
| Config construction from tool arguments | The strategy's handler method, which owns validation and config assembly. |
| Execution adapter shape and capture type | Strategy-owned `execute_*`/`run_*`, `*Capture` and `from_*_capture`; the refresh table points at the composing `_execute_*`. |
| Outcome classification | Strategy-owned `classify_*_outcome` inside the adapter. The descriptor has no classifier field. |
| Momentum has no native failure-status classifier | `from_momentum_capture` sets `RunOutcome.COMPLETED` and `evaluation.runner._native_status` returns `None` for `MomentumRun`. Because the descriptor carries no status or classifier field, nothing is optional or `None` in the descriptor to express the absence. |
| Evidence ticker location | `EvidenceCodec.ticker_of` (Momentum reads `run.metrics.ticker`; the others read `.ticker`). |
| Profile composition | Graham and FCF share `compose_graham_profile`; Momentum owns `compose_momentum_profile`. |
| Presentation and replay | `render_*` and `_project_*_v1`; projection stays versioned and strategy-owned. |
| Invalid-input detail in failures | A parameter on `execution_errors` set by the Momentum command, replacing the generic function's `analysis == "momentum"` test. |
| Fixture composition and expected outcomes | `compose_fixture_dependencies`, `catalog.py` and case modules stay explicit evaluation truth. |

Anything else a strategy needs outside these hooks is a plan change, not a descriptor field
([§12](#12-framework-drift-checks)).

## 8. Typing form

**Chosen:** a non-generic frozen `StrategyDescriptor` whose only typed relationship, the evidence
codec, is a small generic dataclass `EvidenceCodec[ResultT: NativeEvidence]` held through an erased
`Protocol` view. The bound ties each codec to a member of the hand-written `NativeEvidence` union, so
pairing a result type with another strategy's encoder, decoder or ticker accessor is a type error.

**Result:** the prototype (real strategy modules, all four strategies; Momentum and FCF differ in
result shape, ticker location and tool arguments) passes `mypy --strict` with no issues. Five
deliberate mispairings are each rejected, and the generic-descriptor and erased forms are shown to
need `Any` or `cast`. Full evidence: [Appendix B](#appendix-b-typing-form-comparison-and-prototype-evidence).

Essential sketch (prototype, `.tmp/` only, not committed):

```python
type NativeEvidence = MomentumRun | GrahamNumberAnalysis | GrahamGrowthAnalysis | FCFEarningsGrowthResult


class EvidenceView(Protocol):
    @property
    def result_type(self) -> type[NativeEvidence]: ...
    def encode_object(self, evidence: object) -> StrictJsonMapping: ...
    def decode_for(self, payload: StrictJsonMapping, ticker: str) -> NativeEvidence: ...


@dataclass(frozen=True)
class EvidenceCodec[ResultT: NativeEvidence]:
    result_type: type[ResultT]
    encode: Callable[[ResultT], StrictJsonMapping]
    decode: Callable[[StrictJsonMapping], ResultT]
    ticker_of: Callable[[ResultT], str]
    # encode_object: isinstance guard, then self.encode(evidence)   (rejects anything else)
    # decode_for: self.decode(payload), then verify ticker_of(result) == ticker


@dataclass(frozen=True)
class StrategyDescriptor:  # non-generic: no consumer needs ConfigT
    analysis_id: str
    method_id: str
    alias: str
    label: str
    tool: ToolName
    tool_arguments: type[BaseModel]
    tool_description: str
    config_schema_version: int
    method_version: int
    result_schema_version: int
    evidence_codec_version: int
    evidence: EvidenceView


MOMENTUM: Final = StrategyDescriptor(
    "momentum",
    "sma_crossover",
    ...,
    ToolName.ANALYZE_MOMENTUM,
    MomentumToolArguments,
    ...,
    EvidenceCodec[MomentumRun](MomentumRun, encode_momentum, decode_momentum, lambda run: run.metrics.ticker),
)
```

Two points learned from the prototype that SWC.2b must follow:

- Write the type argument explicitly (`EvidenceCodec[MomentumRun](...)`). Without it, mypy infers the
  whole union from the `Protocol` field's expected type and rejects every declaration.
- Do not use `assert isinstance` narrowing inside generic consumers. The codec's own `isinstance`
  guard narrows `object` to `ResultT` without a cast.

Consumer-owned tables (handlers, executors, projectors) hold the existing strategy functions. Each
function narrows its own input with the `assert isinstance` form `reporting/analysis_runs.py` already
uses; the table key, not the assertion, is the dispatch. The prototype's executor table type-checks
under `mypy --strict`.

## 9. ToolName, fail-closed dispatch

### 9.1 `ToolName`

**Decision:** `ToolName` stays a hand-written `StrEnum`, the single declaration of the four tool-name
strings. It moves to `src/orchestrator/tool_names.py` (a leaf with no project imports) because the
orchestrator and descriptor need it and `evaluation` must not be a dependency of production wiring.
There is no re-export: `evaluation/models.py` imports it from its new home like every other importer,
and the `src.evaluation` package export is removed ([§4](#4-static-declaration-model)). Each
descriptor binds one member in `tool`.

**Why not source the enum from descriptor strings:** the plan asks for `ToolName` values sourced from
the descriptor. That fails the type boundary: a functional `StrEnum(...)` built from descriptor
strings is rejected by `mypy --strict` (`StrEnum() must be ... literal ... to determine Enum
members`), and `ToolName.ANALYZE_MOMENTUM`, used in six case modules and pydantic field types,
becomes an attribute error. Evidence: Appendix B, form C.

**What changes in practice:** the second mapping is removed, which was the stated goal. The four
`ANALYZE_*_TOOL` constants, `ANALYSIS_TOOL_ARGUMENT_MODELS`, the three model-to-member isinstance
chains and the string-keyed `_TOOL_DESCRIPTIONS` all go. The string appears once. T4 checks the enum,
the descriptors and the registered tools against each other in both directions, so a member without a
descriptor, or the reverse, fails.

### 9.2 Fail-closed dispatch

One exception, `UndeclaredStrategyError(LookupError)`, defined in `src/strategy_wiring.py`, with a
message that names the key or type that matched nothing and the declared alternatives. No generic
consumer has a fall-through branch.

| Consumer | Undeclared input | Result |
| :--- | :--- | :--- |
| `encode_evidence` | Evidence whose exact type matches no descriptor. | `UndeclaredStrategyError`. It is a programming error, so it is not wrapped as `InvalidStoredRunError`. |
| `decode_evidence` | `(analysis_id, method_id)` with no descriptor. | Existing `UnsupportedRunVersionError`, message and `reason_code` unchanged. |
| `project_run` | A key with no projector. | Existing `UnsupportedProjectionError`, message unchanged. |
| `_refresh_executor` | A selection whose key has no executor. | `UndeclaredStrategyError`, replacing the `AssertionError` fallthrough. |
| `parse_selection` | Unknown alias. | Existing `ValueError("Unknown analysis alias: ...")`, raised when the alias-keyed table of parsers has no entry. No strategy is a fall-through. |
| `tool_for_arguments` | Arguments of an undeclared model type. | `UndeclaredStrategyError`, replacing `TypeError`. |
| Handler registration | A descriptor tool with no handler entry. | `UndeclaredStrategyError` at registration, naming the tool. |
| `evaluation.runner._native_result`, `_native_status` | A result of an undeclared type. | `UndeclaredStrategyError`, replacing today's `TypeError` and the FCF default. |

Lookup is by exact type, not `isinstance`, so a subclass of a result type cannot be silently routed.
For valid inputs every path behaves as today; T8 round-trips real evidence for every descriptor.

## 10. Conformance tests and negative control

All tests are deterministic, make no network, provider or LLM call, and live in
`tests/test_strategy_wiring_conformance.py` (new in SWC.2b, extended by later slices) unless noted. The
test code names the consumer surfaces it checks; it does not copy wiring metadata.

### 10.1 Tests

| Test | Compares the descriptors to | Independent surface | Why it is not tautological |
| :--- | :--- | :--- | :--- |
| T1 `selection_union` | `(analysis_id, method_id, config_schema_version)` of each `get_args(AnalysisSelection)` member | `Literal` field defaults on the hand-written selection classes | Selections and descriptors are separate declarations. A strategy added to one only fails. |
| T2 `native_evidence_union` | `get_args(NativeEvidence)` against the set of `evidence.result_type` | The hand-written evidence union | Same reasoning; the codec bound also fails type-checking on mismatch. |
| T3 `analyzer_generics` | `evidence.result_type` against `ResultT` of every non-abstract `BaseAnalyzer` subclass found by walking the `src.analysis.strategy` package with `pkgutil` | The analyzers' own `BaseAnalyzer[ConfigT, ResultT]` specialization | The analyzer defines its result; the descriptor must agree. Enumeration is by package walk, so a new analyzer needs no edit to the test. It also requires exactly one descriptor per analyzer and one analyzer per descriptor. |
| T4 `tool_surfaces` | `tool` and `tool_arguments` against `set(ToolName)`, the names registered by `register_analysis_tools` on a real dispatcher, `_AnalysisToolArguments.__subclasses__()` and `get_args(AnalysisToolArguments)` | Four hand-written or runtime-registered surfaces | A tool in any one surface and not the others fails and names it. |
| T5 `cases_route_to_their_tool` | `tool_for_arguments(request.arguments)` for each catalog request, against the tools its case's expectation requires | Reviewed case expectations in `src/evaluation/cases` | Case truth is written by hand against tool names, not derived from the descriptor. |
| T6 `evaluation_coverage` | Every descriptor tool against the union of tools the golden cases require; the deterministic suite runs every case | The case catalog and the suite's own dispatch | A strategy with no deterministic case, or one the fixture composition cannot serve, fails. |
| T7 `command_table` | Descriptor aliases against the top-level command names of the real Typer app | The CLI's own command table, read from `typer.main.get_command(app)` with hidden groups included; it does not depend on any option | (a) Every top-level command is a descriptor alias, a command group, or listed in the test's hand-written `NON_STRATEGY_COMMANDS` (`evaluate`, `refresh`, and the view commands later slices add); anything else fails naming the command. (b) Every alias is a top-level command. (c) An alias never equals a group or non-strategy name. (d) As a property check, each strategy command offers `--save-run` and `--json`; this checks the contract and is not how commands are discovered. A command that forgot `--save-run` therefore fails (d) instead of dropping out of the enumeration. |
| T8 `versions_and_round_trip` (SWC.3) | Run envelope versions and decoded evidence for a real result per strategy | Real analyzer output via the golden fixtures, real `AnalysisRun` validation | Behavior, not metadata: `execute` writes, `decode_evidence` reads, and `decoded == original` must hold. |
| T9 `rendered_json_ids` (SWC.4c) | `analysis_id` and `method_id` against the `analysis` and `method` keys of each strategy's rendered `--json` document | Real rendered documents from the golden fixtures: three hand-written builders and FCF's native ids | The builders are separate declarations of the same identifiers; a mismatch fails. |
| T10 `consumers_cover_every_descriptor` | The key set of each named consumer surface (tool registration, evaluation routing, native status, fixture requirements, codecs, aliases, selection parsing, watchlist builders, refresh executors, projectors, JSON ids, published schemas, as each lands) | The consumers' own tables and behavior | Fails when a descriptor is not covered by a surface, naming the surface and the strategy. |
| T11 `undeclared_inputs_fail_closed` | Every dispatcher in [§9.2](#92-fail-closed-dispatch) with an undeclared type, key, alias or arguments | The behavior of the dispatchers | Proves no consumer routes an unknown input to Momentum or FCF. |
| T12 `incomplete_consumer_negative_control` | A deliberately incomplete consumer ([§10.2](#102-negative-control)) | See below | Proves T10 can fail. |
| T13 `wiring_layering` | The module-level import graph built from `src` by AST | The source files | No cycle contains `src.strategy_wiring`, and its imports stay inside the allow-list in [§4](#4-static-declaration-model). |
| T14 `no_discovery_or_registration` | The AST of `src/strategy_wiring.py` | The source file | See [§12](#12-framework-drift-checks). |
| T15 `descriptor_is_closed` | Field names, types, frozen-ness, non-generic-ness and tuple-ness | `dataclasses.fields` | Adding a field forces a reviewed edit to the documented set. |
| T16 `no_unused_field` | Each field name against attribute reads on descriptor-typed expressions in `src/` outside the module | The source files, read with a conservative type resolver | A bare name match would be satisfied by an unrelated attribute, for example `selection.alias` or `arguments.tool`. The resolver counts `X.field` only when `X` is a loop variable over `STRATEGIES` or `BY_*.values()`, the result of `require(...)`, `find(...)` or `BY_*[...]`, a parameter annotated `StrategyDescriptor`, or one of the module's descriptor constants. A self-test with snippets (modelled on the repository's existing clock-read scan self-test) proves that `descriptor.alias` counts and `selection.alias` does not. A field read nowhere fails. |
| T17 `analyzer_envelope_unchanged` | `inspect.signature(BaseAnalyzer.run_analysis)` and `AnalysisContext` fields | The base module | The descriptor work cannot alter the envelope unnoticed. |
| T18 `failure_codes` (SWC.4a) | `FailureReasonCode` against every `ReadinessReason`, every exception `reason_code` attribute, and every code the classifier can return | The source exceptions and enums | A new source code with no envelope code fails. |
| T19 `failure_envelope_closed` (SWC.4a) | Envelope fields against the documented set; no remediation-shaped field | The model | Enforces the report-never-remediate rule. |
| T20 `published_schemas_current` (SWC.4a, extended by 4b and 4c) | Regenerated schema text against `schemas/*.json` | Checked-in files | Drift detection by byte comparison; a missing file fails naming it. |
| T21 `json_commands_are_typed` (SWC.4c) | Every command offering `--json` against the `JSON_DOCUMENTS` table and the checked-in schemas | The command tree of the real Typer app, recursed through every group including hidden ones, collecting commands that have a parameter whose option names include `--json` | The commands come from the CLI's own parameter declarations, the schemas from files on disk, and the table links them. A new `--json` command with no typed model fails with `command 'x' offers --json but has no typed document model`; one with a model but no file fails with `command 'x': schema 'schemas/y.schema.json' is not checked in`. Today it finds 12 commands. |
| T22 `save_run_through_every_direct_command` (SWC.3) | For each alias, running the real command with `--save-run` against a temporary database and that strategy's fixture providers | The CLI path, real `execute` and the repository | Exactly one stored run whose key equals the descriptor's and which `decode_evidence` accepts. The test's per-alias fixture setup is hand-written data; a missing entry fails with `no save-run fixture for alias 'x'`. |
| T23 `user_documentation` | For each alias: a guide under `docs/user/strategies/` containing it, that guide linking to `FINANCE_MATH.md#...` and `GLOSSARY.md`, and the alias appearing in `USAGE.md` and `WORKSPACE.md` | The documentation files | Anchor validity is already enforced by `check_doc_links.py`, so a link to a section that does not exist fails the doc check and a missing link fails T23. All four strategies pass today. |
| T24 `uniqueness_rules` | A copy of the tuple with one duplicated value, for each of `analysis_id`+`method_id`, `method_id`, `alias`, `tool`, `tool_arguments`, `evidence.result_type` and (SWC.4c) `json_envelope` | The index builder | Each duplicate must raise naming the rule and both descriptors. Import-time failure is the same code path. |

The existing `tests/workspace/test_method_aliases.py` is the model for T1. SWC.3 folds it into T1 and
T10 when `method_aliases.py` is deleted.

### 10.2 Negative control

Test T12 uses a test-only helper `find_wiring_gaps(descriptors, surfaces)` that asks each named
consumer surface whether it covers each descriptor. The negative control has three parts and must
produce this diagnostic, naming the strategy and each uncovered consumer:

```text
strategy ('ghost', 'ghost_method') is not wired in: tool registration; evaluation routing; evidence codecs; ...
strategy ('fcf_earnings_growth', 'reported_fcf_eps_cagr') is not wired in: refresh executors
```

1. **Missing declaration.** A copy of one descriptor with a different identity is added to the checked
   tuple. Every surface must be reported for it.
2. **Missing entry in one consumer.** One real surface is wrapped so it lacks the FCF key. Exactly one
   gap must be reported, naming `refresh executors` and the FCF key, and no other strategy.
3. **End-to-end.** A real consumer table is replaced, by `monkeypatch`, with one missing a key, and the
   production T10 body runs. It must raise `AssertionError` whose message matches the diagnostic
   above. This proves the shipped test, not only the helper, fails on a forgotten branch.

## 11. Migration from current declarations

Every slice branches from `main` after its predecessor has merged, never from the predecessor's
branch, and ends with the complete managed quality gate. Opening and merging pull requests still need
explicit approval.

| Slice | Branch | Files touched | Declarations removed | Order of work |
| :--- | :--- | :--- | :--- | :--- |
| SWC.2a | `feat/swc-2a-symbol-moves` | New: `src/orchestrator/tool_names.py`, `src/orchestrator/analysis_tool_arguments.py`, `src/workspace/native_evidence.py`. Edited: `src/orchestrator/analysis_tools.py`, `src/evaluation/{__init__,models,composition,runner,ollama_runner,evaluator,catalog}.py`, the six `src/evaluation/cases/*.py` importers, `src/workspace/execution.py` (import of `NativeEvidence` only), `src/core/constants.py`, affected tests (seventeen import `ToolName`, eleven the argument models), `docs/EVALUATIONS.md`, `docs/project/ARCHITECTURE.md`. | The old definitions of the three symbols; the `ToolName` export from `src.evaluation`; `AnalysisType`. | One symbol at a time (`ToolName`, then the argument models, then `NativeEvidence`), updating importers and running the gate after each; then `AnalysisType`. No behavior change and no descriptor. |
| SWC.2b | `feat/swc-2b-orchestration-evaluation-wiring` | New: `src/strategy_wiring.py`, conformance tests. Edited: `src/orchestrator/analysis_tools.py`, `src/evaluation/{composition,runner,ollama_runner}.py`, affected tests. | Four `ANALYZE_*_TOOL` constants; `ANALYSIS_TOOL_ARGUMENT_MODELS`; three `_tool_name`; `_TOOL_DESCRIPTIONS`; duplicate `NativeAnalysisResult`; the FCF defaults in `_require_tool_evidence` and `_native_status`; the private `_value2member_map_` use. | Add the descriptor with tests T1 (ids), T2–T7, T10–T17, T24 and the negative control, then switch consumers. |
| SWC.3 | `feat/swc-3-workspace-wiring` | `src/strategy_wiring.py`, `src/workspace/{codecs,execution,requests,momentum_execution}.py`, delete `src/workspace/method_aliases.py`, `src/data/repositories/watchlists.py`, `src/cli_workspace.py`, `src/cli.py` (Momentum composition only), tests (T1, T8, T10, T11, T22, T23 extended or added; `test_method_aliases.py` folded in). | `_METHOD_VERSIONS`; `_EXPECTED_VERSIONS`; both label chains; both codec isinstance chains; `method_aliases.py`; the `parse_selection` alias tuple and Momentum fall-through; the `_build_selection` chain; the `_refresh_executor` isinstance chain; the `getattr(selection, "as_of", None)` probe; two inline Momentum composition copies in `cli.py` and one in `cli_workspace.py`. | Momentum helper first (independent), then descriptor fields, then codecs and execution, then aliases, `parse_selection` and `_build_selection`, then the refresh table. |
| SWC.4a | `feat/swc-4a-failure-envelope` | New `src/reporting/documents/{__init__,failure,database}.py`, `src/reporting/failure_classification.py`, `scripts/generate_schemas.py`, `schemas/` (failure, database report). Edited: `src/cli_support.py`, `src/reporting/presentation.py`, `src/cli.py` (`execution_errors` call sites), `src/cli_workspace.py`, `src/cli_database.py`, `src/workspace/refresh.py`, `src/workspace/watchlists.py`, `src/data/repositories/watchlists.py`, `docs/user/DATABASE.md`, tests (T18–T20). | `analysis_failure_document`'s hand-built dict and its wrong docstring; the `analysis == "momentum"` test; the six literal id pairs in `execution_errors` calls; the duplicate `WatchlistNotFoundError` in `refresh.py`. | Failure model and classifier, then direct commands, then workspace `--json` paths, then `refresh_watchlist`'s injected classifier and per-job codes, then the database report rename, then the generator and T20. |
| SWC.4b | `feat/swc-4b-workspace-documents` | New `src/reporting/documents/{watchlist,runs,refresh}.py`; `src/cli_workspace.py` JSON builders; `schemas/` (watchlist, watchlist delete, runs list, refresh summary); tests (T20 extended). | The hand-built dicts in `_watchlist_payload`, the delete outcome and `_refresh_json`; the `model_dump` list in `runs list`. | One model per document, each proved byte-identical to the current output except the listed changes, then the schemas. |
| SWC.4c | `feat/swc-4c-strategy-json-envelopes` | `src/strategy_wiring.py`; new `src/reporting/envelopes/<strategy>.py` (four), `src/reporting/json_documents.py`; `src/reporting/{analysis_runs,momentum,graham_number,graham_growth,fcf_earnings_growth}.py`; `schemas/` (four strategy documents); tests (T9, T10, T20, T21, T24 extended). | Literal ids in three builders; the `project_run` pair chain. | Envelope models and `json_envelope`, then the builders' boundary validation, then the projector table, then `JSON_DOCUMENTS` and T21 last, when every command is covered. |
| SWC.5 | `feat/swc-5-contributor-guide` | `docs/project/ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md` moved to `docs/TOOL_DEVELOPMENT.md` and extended (including the identifier rules in [§16](#16-step-35-fit-check) and the edit-site table in [§17](#17-edit-sites-for-a-new-strategy)); every link to it; the Step 3.5 contract plan's link to the edit-site table; `AGENTS.md` §3; final conformance coverage; independent review. | None in code. | Guide, then authorization, then final conformance. |

Why SWC.4 is split: with every `--json` document typed, SWC.4 would carry four large strategy envelope
models, the failure envelope and its classifier, the refresh and database output changes, four
workspace documents, a schema generator, the replay table and a command-coverage test. That is three
reviewable concerns, so it is three slices, in the order above. SWC.4a ships the generator and drift
test with the first schemas. T21 lands last, in SWC.4c, because it can only pass once every `--json`
command is covered, and it has no exemption list.

Stored-shape version bumps expected: **none.** SWC.2a and SWC.2b touch no stored shape. SWC.3 relocates version
values unchanged and changes no selection, evidence or result shape, so no `config_schema_version`,
`method_version`, `result_schema_version` or `evidence_codec_version` changes. The `--json` output
versions that change are listed in [§13.4](#134-what-changes): the failure document `schema_version`
5 to 6 and the database report `schema_version` 1 to 2. Strategy and workspace success documents stay
byte-identical, so their versions do not change. `projection_version` stays 1. A slice that finds it
must change a stored shape bumps the version and records it.

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

The design has drifted into a registry, plugin or factory architecture if any of these is true. T13–T17,
T24 and the review checklist check them; each is concrete.

| # | Check | Drift if |
| :--- | :--- | :--- |
| A1 | `src/strategy_wiring.py` imports `importlib`, `pkgutil`, `inspect`, `entry_points`, or uses `__subclasses__`, `__init_subclass__`, `globals()`, `locals()`, `getattr` with a computed name, or `typing.get_type_hints` | Any occurrence (T14). |
| A2 | The module defines or exports a name matching `register*`, `unregister*`, `*Registry`, `*Factory`, `*Plugin`, `load_*`, `discover*`, or any function that mutates `STRATEGIES` or an index | Any occurrence (T14). |
| A3 | `STRATEGIES` is not a module-level `tuple` of module-level constants, or an index is not a read-only `Mapping` | Either (T14, T15). |
| A4 | `StrategyDescriptor` is generic (`__parameters__` is not empty), is not a frozen dataclass, or is subclassed | Any (T15). |
| A5 | A field's type mentions `BaseAnalyzer`, a config or selection type, a dependency bundle, or a `Callable` returning one of them | Any (T15). |
| A6 | The field set differs from [§3.1](#31-fields) | Always requires a reviewed test edit (T15). |
| A7 | A field is read nowhere outside the module | Dead field (T16). |
| A8 | The descriptor module is in an import cycle, or imports outside its allow-list | Either (T13). |
| A9 | `src/analysis/base_analyzer.py` differs from `main`, or `run_analysis`'s signature or `AnalysisContext` fields change | Any (T17; also a diff check in each slice review). |
| A10 | A consumer keeps an `isinstance`/`==` chain over strategies whose last branch does not raise | Reviewed per slice; T11 proves behavior for the dispatchers it lists. |
| A11 | A handler, executor, projector, capture or classifier appears as a descriptor field | Always escalates to the project owner as a plan change. |

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

**Decision:** add `compose_momentum_profile` to `src/workspace/momentum_execution.py` with a
standalone signature:

```python
def compose_momentum_profile(
    ticker: str,
    *,
    data_client: object,
    profile_cache: InstrumentProfileResolver | None = None,
) -> InstrumentProfile: ...
```

- **Where:** `momentum_execution.py`, not a new `momentum_shared.py`. `graham_shared.py` is named for
  three strategies sharing one helper; this helper has three call sites of one strategy, all of which
  already import `momentum_execution`. There is no cycle (`cli` already imports the module).
- **Why not `compose_graham_profile`'s signature:** that helper takes a primary security-fact provider
  and a separate Yahoo provider, with a precedence rule that adds Yahoo only when the primary is
  another provider. Momentum has one client that is both identity and kind candidate. Calling the
  Graham helper would need the same client passed twice and a Graham-named import in Momentum code,
  which treats Graham as the template (`AGENTS.md` §9). `graham_shared.py` is not edited.
- **Behavior preserved exactly:** one identity candidate and one kind candidate, both
  `InstrumentProfileCandidate(YFINANCE_PROVIDER_ID, data_client)`; `profile_cache.resolve(...)` when a
  cache is given, otherwise `compose_instrument_profile(...)`. The two `src/cli.py` sites and
  `src/cli_workspace.py::_execute_momentum` call it. Tests that patch
  `src.cli.compose_instrument_profile` retarget to the helper's module in SWC.3.

## 15. IR.2 and corrections to the plan

**IR.2 contract changes: none required.** IR.2 fixed three things: every strategy subclasses
`BaseAnalyzer[ConfigT, ResultT]` and is invoked as `run_analysis(ticker, config, context)`;
`AnalysisContext` carries the cross-cutting concerns; and there is no generic result supertype,
registry or factory. The design adds a closed tuple of non-generic declarations. It leaves the
invocation envelope, `AnalysisContext` and every config and result type untouched (T17, A9). The
`NativeEvidence` union already exists; the codec's bound refers to it and does not create a supertype.
The descriptor constructs nothing. The remaining tension is the one the plan already records, a
bounded exception to IR.2's "no registry" wording authorized by `AGENTS.md` §0; nothing new needs
owner review.

Where the audit disagreed with the plan, and what changed:

| # | Plan statement | Finding | Change made |
| :--- | :--- | :--- | :--- |
| 1 | B.4 and Appendix A: `encode_evidence` and `decode_evidence` both fall through to Momentum. | Only `encode_evidence` does. `decode_evidence` rejects an undeclared pair before it reaches the Momentum branch (`codecs.py`, the `expected is None` guard). | Wording corrected in the plan; both dispatchers still become table-driven and fail closed. |
| 2 | §3.2/§4: `ToolName` values are sourced from the descriptor. | A functional enum from descriptor strings fails `mypy --strict` and breaks `ToolName.X` ([§9.1](#91-toolname)). | `ToolName` stays the single hand-written declaration; the plan's §4 row is amended. |
| 3 | §3.2 permits descriptor references to execution adapters and presentation functions. | Executors, handlers and projectors need production dependencies or sit above the codecs; putting them in the descriptor creates import cycles of 2, 4 and 8 modules ([Appendix C](#appendix-c-import-cycle-evidence)). The audited consumers are still served within §3. | The design uses fewer references than §3.2 allows; those three stay in consumer-owned keyed tables. |
| 4 | SWC.4 and SWC.5 both own schema generation and the drift check. | The plan states it twice. | SWC.4a owns the generator, `schemas/` and the drift check; SWC.4b and SWC.4c add schemas to it; SWC.5 verifies per-descriptor coverage and documents. |
| 5 | Appendix A inventory. | Sites it misses ([Appendix A](#appendix-a-inventory-re-verified-at-247ecdf)), including four more default-branch patterns: `parse_selection`'s final Momentum branch, `_build_selection`'s final FCF branch, `_require_tool_evidence`'s final FCF branch and `_native_status`'s final FCF branch. | Plan Appendix A and §4 updated; SWC.2 and SWC.3 scope lines extended. |
| 6 | SWC scope lines. | SWC.2 omits `analysis_tool_arguments.py`, `tool_names.py`, `native_evidence.py` and `evaluation/models.py`; SWC.3 omits `data/repositories/watchlists.py` and the deletion of `method_aliases.py`; SWC.4 omits the `src/cli.py` call sites. | Scope lines corrected in the plan. |
| 7 | SWC.4 branch is "based on the approved SWC.1 design". | SWC.4 reads declarations SWC.2b and SWC.3 create. | Every slice branches from `main` after its predecessor merges ([§11](#11-migration-from-current-declarations)). |
| 8 | The plan makes SWC.4 one slice covering strategy envelopes and the failure envelope. | With every `--json` document typed, the refresh and database output changes and a schema generator, it is three reviewable concerns. | SWC.4 is split into SWC.4a, SWC.4b and SWC.4c ([§11](#11-migration-from-current-declarations)). |
| 9 | The plan's JSON scope is the strategies' output and the failure envelope. | The project owner's review decided that every `--json` document is typed. | The plan's At a glance, SWC.4 scope and acceptance criteria are widened ([§13.6](#136-every-json-document-is-typed)). |
| 10 | SWC.3's Decision says today `encode_evidence` and `decode_evidence` both fall through to Momentum. | Item 1 above. | The sentence is corrected in the plan. |

## 16. Step 3.5 fit check

This tests the SWC design against the seven strategies in the
[Step 3.5 contract](../step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md). It makes no production change and no Step 3.5 design
decision; identifiers are left to that step.

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

### 16.2 Assumptions tested

| Assumption | Covering test | Result and resolution |
| :--- | :--- | :--- |
| One descriptor has exactly one tool, arguments model, evidence type, alias and JSON envelope, each unique across strategies. | T24, through `BY_TOOL`, `BY_ARGUMENTS`, `BY_EVIDENCE`, `BY_ALIAS` and (SWC.4c) `BY_ENVELOPE`. | Holds for all seven. **Misfit:** the Step 3.5 slice scopes name "direct command, watchlist selection, refresh, `--json`" and do not name the orchestrator tool, arguments model, `ToolName` member, handler or dependency fields. SWC requires them for every strategy, and the golden suite (3.5.8) cannot select a strategy without them. *Design unchanged*: the rule stays; sites 3 to 7 of [§17](#17-edit-sites-for-a-new-strategy) are the handoff, and the Step 3.5 contract plan now states that every strategy slice covers them. |
| `method_id` is unique across all analyses. | T24, through `BY_METHOD_ID`. | Holds. It is a rule, not an accident, because runs, watchlist removal and CLI filters select by `method_id` alone (`RunQuery`, `remove_entries_for_method`, `--analysis`). It is stated in three places: the import-time error names both descriptors and the rule; the `strategy_wiring` module docstring; and the SWC.5 contributor guide's identifier section. A strategy with several methods needs distinct method ids, one descriptor per method, and so one tool, evidence type and alias per method. |
| One result concerns one ticker. | `ticker_of`, `decode_for(payload, ticker)`, and the failure envelope's `ticker`. | Holds for all seven analyzers (each is `run_analysis(ticker, ...)`). The ranked view and the side-by-side table concern many tickers but are views over persisted runs, store no evidence and fail with `ticker: null`. Escape hatch: they are outside the descriptor. |
| One analyzer class maps to one descriptor. | T3, now enumerating analyzers by package walk. | Holds; Altman's two models are one analyzer. **Misfit:** an enumeration by hand-written list would need an edit for each of seven analyzers; the package walk needs none. |
| Every strategy command declares `--save-run`. | T7 (d). | Holds for strategy commands. **Misfit:** the ranked view and the side-by-side table are commands without `--save-run`; and discovering strategy commands by that option would let a strategy command that forgot it drop out unnoticed. *Design changed now*: T7 enumerates the whole command table, requires every top-level command to be an alias, a group or a listed non-strategy command, and checks `--save-run` as a property, as [§10.1](#101-tests) states. |
| A strategy's chains and tables are keyed, not defaulted. | T10, T11. | **Misfit:** four `if` chains would have routed an eighth strategy to FCF or Momentum (`_require_tool_evidence`, `_native_status`, `parse_selection`, `_build_selection`). *Design changed now*: each becomes a keyed table with a T10 surface ([§6](#6-generic-consumers)). |
| A cross-strategy view needs per-strategy content. | T10 surface added by the slice. | **Misfit:** the side-by-side table shows each strategy's headline values. That is a consumer-owned table keyed by descriptor identity, listed as a T10 surface when 3.5.7 lands. Escape hatch: [§7](#7-strategy-specific-escape-hatches). |
| Dependencies stay a flat per-strategy dataclass. | mypy and T6. | Seven more analyzer fields and provider ids grow `AnalysisToolDependencies`. This is strategy-owned and stays; [§17](#17-edit-sites-for-a-new-strategy) counts it. |

## 17. Edit sites for a new strategy

Every hand-edited place, in the order a contributor meets them. "Kind": **G** is genuine
heterogeneity (per-strategy content), **R** is residual repetition (a line restating identity or a type
list), **G+R** is a strategy-owned function or class plus one table or union line. "Test" is what fails
if the site is omitted. A gate check (mypy or the doc link check) is named where it is the failing
check and a conformance test backs it.

| # | Site | Slice that creates it | Kind | Test that fails, and its diagnostic |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Analyzer package: config, result, analyzer (`src/analysis/strategy/<s>/`) | per strategy | G | T3: `analyzer X (result Y) has no descriptor`. |
| 2 | Descriptor constant and its entry in `STRATEGIES` | per strategy | G | T1: `AnalysisSelection member X has no descriptor`; T2 and T3 likewise. |
| 3 | `ToolName` member | per strategy | R | T4: `ToolName member X has no descriptor`. |
| 4 | Tool-arguments model in `analysis_tool_arguments.py` | per strategy | G | T4: `tool-argument model X has no descriptor`. |
| 5 | `AnalysisToolArguments` union (`evaluation/composition.py`) | per strategy | R | T4: `AnalysisToolArguments lacks X`. |
| 6 | Handler method and its entry in the `ToolName`-keyed handler table | per strategy | G+R | Registration raises `UndeclaredStrategyError: no handler for tool X`; T10 `tool registration`. |
| 7 | `AnalysisToolDependencies` fields (analyzer, provider ids) | per strategy | G | mypy (`no attribute`) in the handler; T6 fails when composition cannot build the dependencies. |
| 8 | `NativeEvidence` union | per strategy | R | T2: `NativeEvidence lacks X`. |
| 9 | Selection class and its `AnalysisSelection` union member | per strategy | G+R | T1: `descriptor X has no AnalysisSelection member`. |
| 10 | Parser and its entry in the alias-keyed table in `parse_selection` | per strategy | G+R | T10 `selection parsing`: `strategy X is not wired in: selection parsing`. |
| 11 | Builder and its entry in the alias-keyed table in `_build_selection`, with the watchlist options | per strategy | G+R | T10 `watchlist builders`. |
| 12 | Codec module (`encode_*`, `decode_*`) | per strategy | G | mypy (the descriptor requires them); T8 round trip. |
| 13 | Execution adapter, capture type and `from_*_capture` | per strategy | G | T22: `alias X stored no run`; T10 `refresh executors`. |
| 14 | `_execute_<s>` composition and its entry in the refresh executor table | per strategy | G+R | T10 `refresh executors`; T22. |
| 15 | Direct command in `cli.py` | per strategy | G | T7: `alias X is not a top-level command`, `command Y is not an alias`, `command Y offers no --save-run`; T22. |
| 16 | Presenter and JSON builder in `reporting/<s>.py` | per strategy | G | T9: `rendered document ids differ from descriptor X`. |
| 17 | JSON envelope model and the descriptor's `json_envelope` | per strategy | G | T21: `command X offers --json but has no typed document model`. |
| 18 | Replay projector and its entry in the projector table | per strategy | G+R | T10 `projectors`. |
| 19 | Native-status accessor and its entry in the table in `evaluation/runner.py` | per strategy | G+R | T10 `evaluation native status`. |
| 20 | Fixture-requirement entry in `evaluation/composition.py` | per strategy | G+R | T10 `fixture requirements`. |
| 21 | Fixture composition in `compose_fixture_dependencies` | per strategy | G | T6: the deterministic suite fails dispatching the strategy's cases. |
| 22 | Fixtures, evaluation cases and `catalog._arguments` | per strategy | G | T6: `tool X is required by no golden case`; T5. |
| 23 | Documentation: user guide with `FINANCE_MATH.md` and `GLOSSARY.md` links, and `USAGE.md` and `WORKSPACE.md` mentions | per strategy | G | T23: `no guide for alias X`; the doc link check for a missing anchor. |

One further step is a command, not an edit: run `scripts/generate_schemas.py`. A missing or stale
`schemas/<alias>.schema.json` fails T20 with `schema schemas/<alias>.schema.json is missing or out of
date; run scripts/generate_schemas.py`.

**Total: 23 hand-edited sites** (plus the generator run). **12 are genuine heterogeneity** (1, 2, 4, 7,
12, 13, 15, 16, 17, 21, 22, 23), **3 are residual repetition** (3, 5, 8) and **8 are genuine content
plus one repeated line** (6, 9, 10, 11, 14, 18, 19, 20). Every site has a failing check, so none is a
gap. Two gaps were closed while writing this table: four unguarded chains (`parse_selection`,
`_build_selection`, `_native_status`, `_require_tool_evidence`) that routed an unlisted strategy to Momentum
or FCF are now keyed tables with a T10 surface, and documentation now has T23.

**What SWC could still remove.** Nothing within the contract. The three residual sites (3, 5, 8) are
type-level lists that `mypy --strict` needs and that no descriptor can generate: an enum, a union
alias and a union alias. The eight repeated lines (the table or union entries in 6, 9, 10, 11, 14,
18, 19, 20) could disappear only if the descriptor referenced the handler, executor, projector,
parser, builder, accessor and requirement, and Appendix C shows that creates import cycles that
reordering does not cure. What SWC does remove is the unguarded repetition: the isinstance and `==`
chains, the two version tables, the label chains, the alias tables, the tool-name mappings and the
identifier literals. Each is now one declaration or one line with a named test.

## 18. Findings assigned to a slice

| Finding | Decision | Slice |
| :--- | :--- | :--- |
| `AnalysisType` in `src/core/constants.py` has one member (`MOMENTUM`) and no reader in `src/` or `tests/` (a repository search for the name finds only its definition). | Delete it. It is a dead per-strategy name list, and SWC.2a is where per-strategy name declarations are removed. | SWC.2a |
| Two classes named `WatchlistNotFoundError`, in `src/data/repositories/watchlists.py` and `src/workspace/refresh.py`. | One class, defined in `src/workspace/watchlists.py` next to `StoredSelectionError`; the repository and `refresh.py` import it; the duplicate and the aliased import in `cli_workspace.py` go. The classifier maps one class to `watchlist_not_found`, and no handler can miss the other. Tests in `tests/data` and `tests/workspace` import the single class. | SWC.4a |
| `analysis_failure_document`'s docstring says the failure document uses "the analysis presentation version", but its `schema_version` is 5 for every strategy while the Graham success documents carry 6. | The docstring is removed with the hand-built dict. `FailureEnvelope` documents that its `schema_version` is its own lineage, independent of every success document's. | SWC.4a |
| The failure envelope and the Graham success documents would share `schema_version` 6. | Acceptable. A `schema_version` identifies a shape only within its own schema file; consumers dispatch on `status` and `result` first, then on `analysis`. The generated schema's description says so, the contributor guide states it, and renumbering the failure lineage to avoid a coincidence would be a second, arbitrary output change. | SWC.4a, SWC.5 |
| `execute()` reads `getattr(selection, "as_of", None)`, although every `AnalysisSelection` member defines `as_of`. | Read `selection.as_of`; the probe adds no safety and hides a missing field. | SWC.3 |
| `ollama_runner._selection_observation` uses the private `ToolName._value2member_map_`. | Replace with ordinary enum lookup. | SWC.2b |
| `evaluation.runner.NativeAnalysisResult` duplicates `NativeEvidence`. | Remove it and use `NativeEvidence`. | SWC.2b |
| Each strategy's codec checks its own `method` string inside `workspace/{graham_number,graham_growth}.py`. | Kept: wire-integrity checks the descriptor cannot be imported into without a cycle. | none |
| `refresh --json` per-job `error` text is `str(exception)`. | Unchanged. The new `reason_code` is classified from the same exception. | SWC.4a |

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
| `src/workspace/method_aliases.py`: `ANALYSIS_ALIASES`, `ALIAS_METHOD_IDS`, `METHOD_ID_ALIASES`, `alias_for_method_id` | D | Alias and method-id vocabulary; replaced by `alias` and `method_id`. | SWC.3 |
| `src/workspace/requests.py::parse_selection`: alias tuple; final unconditional Momentum branch | D (tuple, chain); S (per-alias parsing) | Membership is repeated vocabulary; parsing differs by strategy; the fall-through is a default branch. Becomes an alias-keyed table of strategy-owned parsers ([§6](#6-generic-consumers)). | SWC.3 |
| `src/workspace/requests.py`: `Literal` ids and version on each selection | S | Types the discriminated union; compared by T1. | none (kept) |
| `src/data/repositories/watchlists.py`: `METHOD_ID_ALIASES.get(...)` | D | Alias lookup tolerant of an unknown stored method. | SWC.3 |
| `src/cli_workspace.py`: `_parse_analysis`, `ALIAS_METHOD_IDS[...]` (2), `alias_for_method_id(...)` (4), `--analysis` help (3) | D | Alias vocabulary. | SWC.3 |
| `src/cli_workspace.py::_build_selection` | D (chain); S (flag mapping) | The `if method == ...` chain ends in an unconditional FCF return. Becomes an alias-keyed table of strategy-owned builders over one frozen flag bundle ([§6](#6-generic-consumers)). | SWC.3 |
| `src/cli_workspace.py::_execute_*` | S | Production composition. | none (kept) |
| `src/cli.py`: `execution_errors(analysis=, method=)` ×6 | D | Literal id pairs. | SWC.4a |
| `src/reporting/{momentum,graham_number,graham_growth}.py`: `"analysis"`, `"method"` literals | D | Literal ids. FCF reads native `strategy_id`, `method_id`. | SWC.4c |
| `src/cli_support.py:226`: `analysis == "momentum"` | S | Strategy-specific behavior inside generic code; becomes a call-site parameter. | SWC.4a |
| `src/evaluation/runner.py`: `NativeAnalysisResult`, `_native_result`, `_native_status` | D (union, membership); S (status accessor) | Duplicate of `NativeEvidence`; FCF is the default branch; Momentum has no native status. | SWC.2b |
| `src/evaluation/composition.py::_require_tool_evidence` | S (requirements); D (chain) | Per-tool fixture requirement; the final `else` makes FCF the default. Becomes a `ToolName`-keyed table ([§6](#6-generic-consumers)). | SWC.2b |
| `src/evaluation/ollama_runner.py`: `_TOOL_DESCRIPTIONS`, `_tool_schemas_json`, `_tool_parser`, `_selection_observation` | D | Per-tool description and model; private `_value2member_map_` use. | SWC.2b |
| `src/evaluation/catalog.py`, `src/evaluation/cases/*.py` | S | Reviewed case arguments and `ToolConstraints`; the independent truth for T5 and T6. | none (kept) |
| `src/workspace/{graham_number,graham_growth}.py`: string checks of `method` inside the codecs | S | Each codec's own wire integrity check; the descriptor cannot be imported there without a cycle. | none (kept) |
| `src/workspace/__init__.py` re-exports | S | Public names. | none (kept) |
| `src/core/constants.py::AnalysisType` | D (dead) | A one-member per-strategy name enum with no reader in `src/` or `tests/`. | SWC.2a (deleted) |

## Appendix B: Typing form comparison and prototype evidence

Prototype files (scratch only, under the ignored `.tmp/swc1/proto/`, never committed): the chosen
form `descriptor_proto.py` and a consumer-table prototype `executor_table_proto.py`, both over the
real strategy modules; `negative_proto.py` with five deliberate mispairings; and
`rejected_forms_proto.py` with the other forms. Checked with
`mypy --strict` (mypy 2.3.1, Python 3.12 target, the repository's `mypy_path`).

### B.1 Results

| Run | Result |
| :--- | :--- |
| Chosen form plus consumer table, all four strategies, indexes, `encode_evidence`, `tool_for_arguments` | `Success: no issues found in 2 source files`. At runtime, four descriptors index, `tool_for_arguments(MomentumToolArguments(...))` returns `analyze_momentum`, and an undeclared type or key raises `UndeclaredStrategyError`. |
| Negative control N1: FCF encoder paired with `MomentumRun` | Rejected (`arg-type`). |
| N2: FCF decoder paired with `MomentumRun` | Rejected (`arg-type`). |
| N3: `int` as result type | Rejected (`type-var`: not in the `NativeEvidence` bound). |
| N4: wrong ticker accessor for the shape (`run.ticker` on Momentum) | Rejected (`attr-defined`). |
| N5: `encode_evidence(42)` | Rejected (`arg-type`). |
| Positive control in the same file (FCF correctly paired) | Accepted. |

### B.2 Options compared

| Form | Verdict | Evidence |
| :--- | :--- | :--- |
| A. `StrategyDescriptor[ConfigT, ResultT]` | Rejected. | No consumer reads `ConfigT`. A heterogeneous tuple needs `tuple[GenericDescriptor[Any, Any], ...]`; with `Any`, `registry[0].encode(FCFEarningsGrowthResult)` (an unsound call) type-checks silently. With `object` arguments, mypy rejects the tuple by invariance. |
| B. Erased `object` callables | Rejected. | `ErasedDescriptor(encode_momentum)` is rejected by parameter contravariance; each strategy function needs a `cast`, which removes the pairing check. |
| C. Dynamic `ToolName` from descriptor strings | Rejected. | `StrEnum("DynamicToolName", mapping)` errors ("must be string, tuple, list or dict literal for mypy to determine Enum members"), and `.ANALYZE_MOMENTUM` is then an attribute error. |
| D. Concrete instances with `Any` fields | Rejected on design grounds (not prototyped). | It is form A without even the type parameters, so it accepts the same unsound calls and has no pairing check. |
| E. One descriptor subclass per strategy | Rejected on design grounds (not prototyped). | It is a class hierarchy, which is the framework shape the plan prohibits. |
| F. Non-generic descriptor plus a generic `EvidenceCodec[ResultT: NativeEvidence]` behind a `Protocol` | **Chosen.** | Passes `mypy --strict`; rejects all five mispairings; no `Any`, no `cast`; one explicit type argument per declaration. |

## Appendix C: Import-cycle evidence

Method: a scratch script parsed every module under `src` with `ast` (module-scope and nested imports),
built the module graph, added the edges each design variant implies, and searched for strongly
connected components. The baseline graph (163 modules at this commit) has no cycle.

| Variant | Descriptor module imports | Consumers that import it | Cycles |
| :--- | :--- | :--- | :--- |
| V0 | nothing (identifiers and versions only) | codecs, execution, `project_run`, `analysis_tools`, evaluation, CLI, aliases | 0 |
| V1 | V0 plus the four codec modules | same | 0 |
| V2 | V1 plus `analysis_tools` for the argument models | same | 1: `analysis_tools` and the descriptor module |
| V3 | V2 plus `reporting.analysis_runs` for projectors | same | 1 of 4 modules: `analysis_tools`, `analysis_runs`, `codecs`, the descriptor module |
| V4 | V1 plus `execution` normalizers and `cli_workspace` executors | same | 1 of 8 modules: `cli_workspace`, `data.repositories.watchlists`, `analysis_runs`, `codecs`, `execution`, `method_aliases`, `refresh`, the descriptor module |
| Chosen | codec modules, FCF constants, `native_evidence`, `tool_names`, `analysis_tool_arguments`, the four strategy modules in `reporting.envelopes` | all consumers in [§6](#6-generic-consumers) across `orchestrator`, `workspace`, `data.repositories`, `reporting`, `evaluation`, `cli*`, plus the new `reporting.documents` models, `failure_classification` and `json_documents` | 0 (163 modules plus the fifteen new ones) |

V2 is fixed by moving the argument models out of `analysis_tools.py`. V3 and V4 are not fixed by
reordering: projectors sit above `codecs`, and executors need production providers and the CLI's
composition. That is why handlers, executors and projectors stay in consumer-owned keyed tables
(D5). T13 recomputes this graph in the test suite so the property cannot regress.

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
