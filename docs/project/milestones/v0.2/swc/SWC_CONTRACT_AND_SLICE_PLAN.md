# SWC — Strategy Wiring Consolidation: Contract and Slice Plan

Consolidates repeated strategy wiring before Step 3.5 adds seven analyzers, completes the
typed JSON envelope and schema scope moved from IR.5, and gives failures a typed envelope. The [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status)
owns its position and work-package status.

## 1. At a glance

- **What this work does:** reduce repeated per-strategy wiring across orchestration, workspace
  selection and execution, evidence codecs, reporting, CLI integration and deterministic
  evaluation through a closed, statically declared descriptor per strategy; put each strategy's code in
  strategy-owned modules; give every `--json` document (strategy, workspace, database and failure) a typed
  model and a generated schema; give failures a typed envelope on direct and workspace commands,
  per-job refresh failures a stable code and the database report the envelope's field names; replace
  Momentum's three profile-composition copies with one; give contributors a status command, a
  generator and a specimen strategy; document the contributor workflow.
- **What the descriptor means:** one authoritative declaration, at the composition root, of each
  strategy's identity, versions and typed behavior (handler, selection parser, evidence codec,
  native-status function, replay projector). A CLI tier and an evaluation tier add the functions only those
  layers can import. Generic consumers below the root never import any of them; the root passes each layer
  its slice by injection, and independent conformance tests verify complete coverage.
- **What it does not do:** change analyzer formulas, classifications, result semantics, or the
  `BaseAnalyzer[ConfigT, ResultT]` invocation envelope; add a common result type, dynamic discovery,
  plugins, self-registration, or a general strategy framework. Full list: [Scope limits](#6-scope-limits).
- **Decision:** closed descriptors are authorized only to consolidate the duplicated wiring in
  Appendix A. SWC applies the existing AGENTS.md §0 allowance for an explicit, statically declared list with shared generic wiring. This does not create a registry in the architectural sense prohibited by IR.2. See [§3](#3-architectural-contract).
- **Rules every slice follows:** preserve strategy-owned config and result types, retain explicit
  provenance and outcomes, bump affected stored-shape versions without migrations during the
  consolidation period, make each slice's moves in the same change as the consumer they serve, and run
  the complete managed gate at each slice end. Each next slice waits for explicit project-owner
  authorization.
- **Where detail lives:** the settled contracts and their evidence are in the
  [SWC.1 design](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md); the audited inventory is in
  [Appendix A](#appendix-a-proposal-inventory-verified-against-main); its scope disposition is in
  [§4](#4-inventory-disposition); the decision record is in
  [Appendix B](#appendix-b-decision-records-and-history).

## 2. Sequence and status

Every slice ends with the complete managed quality gate. The next slice begins only after explicit
project-owner authorization. Any slice that changes executable code, tests, or parsed configuration
uses the managed wrapper from `AGENTS.md`; prose-only documentation changes follow the repository's
document-link check and applicable documentation checks.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| SWC.1 | [Settle descriptor contract and conformance design](#swc1--descriptor-contract-and-conformance-design) | Complete | 2026-10-03 |
| SWC.2a | [Relocate the existing strategy modules into one package per strategy](#swc2a--strategy-packages) | Complete | 2026-10-04 |
| SWC.2b | [Move the symbols the descriptor and tiers will reference](#swc2b--symbol-moves) | Complete | 2026-10-04 |
| SWC.2c | [Declare the descriptor; wire orchestration and evaluation routing](#swc2c--descriptor-and-orchestration-wiring) | Complete | 2026-10-04 |
| SWC.2d | [Move fixture composition into the evaluation tier](#swc2d--evaluation-tier) | Complete | 2026-10-04 |
| SWC.3a | [Inject the descriptor into workspace consumers](#swc3a--workspace-consumers) | Complete | 2026-10-06 |
| SWC.3b | [CLI tier: selection builders and refresh executors](#swc3b--cli-tier) | Complete | 2026-10-06 |
| SWC.3c | [Move the direct commands into strategy files](#swc3c--direct-commands) | Complete | 2026-10-06 |
| SWC.4a | [Typed failure envelope and schema generator](#swc4a--failure-envelope-and-schema-generator) | Complete | 2026-10-06 |
| SWC.4b | [Typed workspace documents](#swc4b--typed-workspace-documents) | Complete | 2026-10-07 |
| SWC.4c | [Typed strategy envelopes and replay dispatch](#swc4c--typed-strategy-envelopes-and-replay-dispatch) | Next | |
| SWC.4d | [Command validation failures and the failure envelope](#swc4d--command-validation-failures-and-the-failure-envelope) | Planned | |
| SWC.5 | [Site data, status command and generated lists](#swc5--site-data-status-command-and-generated-lists) | Planned | |
| SWC.6 | [Specimen strategy and generator](#swc6--specimen-strategy-and-generator) | Planned | |
| SWC.7 | [Document contribution and complete conformance](#swc7--contributor-guide-and-final-conformance) | Planned | |

## 3. Architectural contract

### 3.1 Decision and relationship to IR.2

SWC uses a closed, statically declared descriptor as the single authoritative declaration of
duplicated strategy-wiring metadata identified by the audited inventory, plus a typed behavior bundle
for the strategy-owned functions that mention a strategy's selection or result type. Two further closed
tuples, one in the CLI layer and one in the evaluation layer, pair the functions only those layers can
import. Generic infrastructure receives its slice by injection. Independent structural conformance tests
verify that every supported strategy is declared and that each required generic consumer is covered. The
descriptor and tests together prevent forgotten wiring without runtime discovery.

IR.2 established: “No new framework: no generic result supertype, registry or factory. Each
strategy keeps its own `ConfigT` and `ResultT`.” SWC preserves the substance of that contract:
strategies retain distinct configs, results, evidence, calculations, and invocation through
`BaseAnalyzer[ConfigT, ResultT]`. SWC introduces only the narrow closed wiring declaration needed to
consolidate the audited per-strategy duplication. This is the specific shared-generic-wiring
allowance in the temporary consolidation rule in `AGENTS.md` §0. It is a bounded exception to IR.2's
“no registry” wording for this consolidation purpose; it does not supersede IR.2 or authorize a
general strategy registry, dynamic discovery, plugin lifecycle, self-registration, or factory
architecture.

If contract design finds that the audited consumers cannot use this bounded declaration without a
new public or internal contract that changes IR.2's approved invocation or evidence boundaries, the
design must identify that exact change and its necessity for project-owner review before code uses
it. Do not silently expand the exception.

### 3.2 Descriptor responsibilities and exclusions

The descriptor is an infrastructure declaration of wiring metadata and of references to strategy-owned
functions, not a universal representation of strategy behavior. The contract slice authorizes only
fields needed by audited consumers:

- stable analysis and method identifiers, tool name, and tool-argument/configuration model types
  where generic wiring requires them, plus result/evidence model types only where a generic
  consumer genuinely needs them for dispatch or codec selection;
- per-strategy configuration, method, result-schema, codec, or projection version metadata where
  the inventory shows repeated declarations that must stay aligned;
- references to strategy-owned encoding, decoding, presentation, selection-conversion, or execution
  functions when a generic consumer needs to dispatch to that strategy-owned behavior; the design uses
  this allowance for tool handlers, selection parsers, native-status functions and replay projectors in the
  core bundle, and for selection builders, refresh executors, direct commands, fixture composition and
  fixture requirements in the two tiers; and
- construction or dependency-wiring information only where the audit proves it removes repeated
  composition while preserving injected strategy dependencies. Each strategy owns its dependency class;
  no shared dataclass grows with the strategy count.

It must not contain calculation logic, financial formulas, strategy policy, generic strategy
behavior, a generic result supertype, plugin lifecycle, dynamic discovery, self-registration, or a
speculative factory hierarchy. It adds no strategy abstraction beyond the existing
`BaseAnalyzer[ConfigT, ResultT]` invocation envelope. A descriptor reference may route to a
strategy-owned function; it does not absorb or generalize that function's behavior.

### 3.3 Static declaration, typing, and conformance

The supported strategy declarations are closed and source-declared. Generic consumers receive their
wiring from those declarations; consumers do not independently repeat the same identifiers, types,
versions, or dispatch cases. No runtime package scanning, registration side effects, plugin loading,
reflection-based probing, dynamic lookup, or discovery is introduced merely to connect the descriptor to
its consumers. The composition root iterates the closed declarations to build statically constructed
indexes and narrow per-layer views, and passes them in. No module below the composition root imports a
descriptor module.

SWC.1 settled the Python typing form after inspecting the audited consumers, comparing generic
parameters, erased/existential representations, typed callables, concrete instances, and other minimal
options without presupposing `StrategyDescriptor[ConfigT, ResultT]`. It chose the simplest structure that
passes `mypy --strict` and keeps each strategy's config, result, and evidence contracts distinct.

Focused conformance tests are required safety nets around the descriptor, not alternatives to it.
They must verify that:

1. every supported strategy at the existing explicit strategy boundaries has a descriptor;
2. every descriptor has all required metadata and required strategy-owned function references;
3. every tier and generic wiring surface identified in §4 covers every descriptor;
4. an intentionally incomplete strategy or dispatch fixture fails a focused test and identifies
   the missing surface and, where practical, the strategy; and
5. strategy-specific calculations, configuration meaning, classification, evidence shape and
   presentation remain owned by their strategy implementations rather than inferred from descriptor
   fields.

Do not make these checks tautological by deriving both the descriptor and the independently checked
strategy set from the same unchecked list. SWC.1 identified existing explicit contract surfaces
that independently define or expose supported strategies and compared their coverage with the
descriptor. The test code may name the required surfaces, but it must not become a second
copy of the strategy wiring metadata.

The intended data flow is static; the tests inspect and challenge it rather than registering or
discovering strategies:

```text
strategy-owned modules (per layer)
              |
              v
 closed tuples at the composition root and in two upper layers
   (descriptors, CLI tier, evaluation tier)
              |
              v
 composition root builds indexes and narrow views, passes them in
              |
      +-------+-------+-------+
      |       |       |       |
      v       v       v       v
  generic  generic  generic  generic
  consumers (receive, never import)
              |
              v
       conformance tests (independent surfaces, specimen strategy)
```

## 4. Inventory disposition

Appendix A is the audited basis for SWC scope, including surfaces missed by the original proposal.
The descriptor replaces repeated infrastructure declarations; strategy-specific behavior moves into
strategy-owned modules that the descriptor and tiers reference.

| Inventory area | Descriptor-authoritative information and generic consumption | Remains strategy-specific or explicit |
| :--- | :--- | :--- |
| Orchestration tools and evaluation mappings | Stable analysis/method/tool identifiers, tool-argument model references, tool-argument-to-tool routing, and the repeated evaluation `_tool_name` mappings. Handler binding is a `behavior` member; registration receives the injected mapping. `ToolName` remains the single hand-written declaration of tool-name strings and each descriptor binds one member, so no second model-to-name mapping exists (settled in SWC.1; a descriptor-built enum fails `mypy --strict`). The four-model `AnalysisToolArguments` union is replaced by the shared base class. | Each strategy's arguments model, dependency class, handler and config construction, in its own `<strategy>_tool.py`. The shared `ToolRuntime` carries only the clock and profile resolver. |
| Persisted selection and workspace execution | The CLI alias vocabulary, selection parsing, and method/config/result-schema/codec version metadata where currently duplicated across execution and codec tables. The refresh executor and selection builder are CLI-tier members and fail closed. | Each persisted selection/config model and conversion, in its own `<strategy>_selection.py`; the `AnalysisSelection` and `NativeEvidence` unions (one file); analyzer invocation, capture shape, and outcome classification. Adapters remain strategy-owned. |
| Evidence encoding and decoding | Result/capture type-to-codec dispatch and repeated expected version metadata derive from injected codecs and version fields. | Each strategy's encode/decode implementation, validation rules, evidence shape, ticker checks, and provenance semantics remain owned by its codec and result type. |
| Reporting, replay, and JSON output | The `(analysis_id, method_id)` route and any genuinely duplicated dispatch key, including the identifier literals in the JSON builders and `execution_errors` calls, derive from the strategy's identity leaf and the descriptor. The injected projector mapping is keyed by that identity and fails closed. Schema generation enumerates the typed strategy envelope models and the failure envelope. | Versioned projection behavior (each projector in `<strategy>_replay.py`), presentation wording, rendering, typed envelope shape, strategy result unions, and historical replay semantics remain strategy-specific and explicit. The failure envelope is one shared shape, not a descriptor field. `projection_version` remains distinct from method and result-schema versions. |
| Fixture-backed evaluation composition and direct CLI commands | Fixture composition and requirement are evaluation-tier members; each direct command is a CLI-tier member that `cli.py` adds by iterating the tier. The strategy lists in `USAGE.md` and `WORKSPACE.md` are generated from the descriptors. | Fixture values, expected outcomes, scoring, case truth, the catalog's case tuple and suite version, direct CLI command semantics, and any explicit user-facing boundary remain as they are. Momentum's profile composition in `src/cli.py` and `src/cli_workspace.py` is reduced to a single implementation by SWC.3a. |

SWC.1 must confirm this mapping against the named symbols and update it if a surface is no longer
present or if further duplication is found. It may narrow descriptor fields when a consumer does not
need them. Expanding scope beyond audited wiring requires a documented reason and owner review.

## 5. The slices

### SWC.1 — Descriptor contract and conformance design

- **Problem:** the audited surfaces mix genuinely duplicated wiring with legitimate heterogeneous
  strategy contracts, and the original proposal inventory missed consumers.
- **Decision:** use the bounded closed descriptor and independent conformance approach in §3. Define
  precisely which duplicated facts have one descriptor declaration and which functions/types stay
  strategy-owned or explicit.
- **Scope:** inspect Appendix A symbols and settle (1) descriptor responsibility/exclusions, (2) the
  static declaration model, (3) relation to `BaseAnalyzer`, (4) exact generic consumers, (5)
  strategy-specific escape hatches, (6) simplest strict typing form, (7) independent conformance
  tests and negative-control failure, (8) migration from current declarations, and (9) acceptance
  checks against a general framework, and (10) the typed failure-envelope contract: its shape, the
  stable `reason_code` values, and whether `DatabaseMaintenanceReport` is the shared shape. Identify
  any required IR.2 public/internal contract change explicitly. No production source changes occur
  in this design slice.
- **Branch:** one review branch from `main`, as for every SWC slice.
- **Detail:** [SWC.1 design](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md) (the settled contract and its
  evidence), [architectural contract](#3-architectural-contract),
  [inventory disposition](#4-inventory-disposition),
  [audited inventory](#appendix-a-proposal-inventory-verified-against-main), and the
  [structured error reporting note](STRUCTURED_ERROR_REPORTING.md).

### SWC.2 — Strategy packages, symbols, descriptor and evaluation tier

Split in four so each is reviewable: SWC.2a relocates the existing strategy modules into one package per
strategy as pure moves; SWC.2b is every mechanical symbol move and the layering fix, with no behavior change
and no descriptor; SWC.2c is the descriptor, the handlers and the routing consumers; SWC.2d moves fixture
composition into the evaluation tier.

#### SWC.2a — Strategy packages

- **Problem:** each strategy's files are spread across `analysis`, `workspace`, `reporting`,
  `orchestrator`, the CLI and `evaluation`, and the slices that follow create more of them. The layout has to
  be settled before they do, because SWC.5 and SWC.6 build tooling around file locations.
  `src/workspace/__init__.py` re-exports names no module imports from the package and, once `requests.py`
  imports descriptor machinery, creates an initialization cycle ([design §4](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#4-static-declaration-model)); it is emptied here, with the layering test that counts parent packages.
- **Decision:** one package per strategy, `src/strategies/<strategy>/`, with each file named for its role,
  shared code in `src/strategies/_shared/` and the Graham family package `src/strategies/_graham/`, and every
  `__init__.py` under `src/strategies/` empty. A role-based layering test (T13) replaces the folder rule.
  Every later slice creates its files in their final place. The layout and the rule are in the
  [SWC.1 design §4](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#4-static-declaration-model); the evidence is in
  [Appendix C.6](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#c6-one-package-per-strategy).
- **Scope:** `git mv` of the 13 analyzer files from `src/analysis/strategy/<package>/` (Momentum's
  `momentum_analyzer.py` becomes `analyzer.py`; the `fcf_earnings_growth` package becomes `fcf_growth`), the
  four codecs, four adapters and four presenters, and `src/workspace/graham_shared.py` to
  `src/strategies/_shared/profile.py`; removal of `src/analysis/strategy/` and its five `__init__.py` files
  (three of them re-exporting), replaced by empty ones under `src/strategies/`; emptying
  `src/workspace/__init__.py`; the 101 importer files (33 in `src`, 68 in `tests`, among them 15 tests whose patch
  strings name moved modules); `tests/analysis/test_base_analyzer_conformance.py`, whose boundary constants
  name the strategy package; the living guide `docs/project/ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md`; the
  layering test with the role rule and parent-package initialization; and the patch-target resolution test,
  a test that every string patch target in `tests/` (the dotted target of `patch(...)`, `patch.object` by name and `monkeypatch.setattr(...)`) resolves to an existing attribute, which proves the
  retargeted strings point at moved names and which the package-rename plan reuses; and the
  direct-command output test, which runs `momentum`, `graham-number`, `graham-growth` and `fcf-growth` (text
  and `--json`) against fixtures and compares byte for byte with stored output generated from `main`
  (`tests/expected_output/direct_commands/`, regenerated with `uv run python -m tests._direct_command_output`,
  normalizing only four wall-clock JSON fields and line endings). T13 records the exact
  24-edge transition allowlist and its owner counts in [SWC.1 design §4](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#4-static-declaration-model).
  No behavior change and
  no new symbol except that test.
- **Branch:** `feat/swc-2a-strategy-packages`, from `main` after SWC.1 has merged.
- **Detail:** [SWC.1 design §4 and §11](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#11-migration-from-current-declarations).

#### SWC.2b — Symbol moves

- **Problem:** the symbols the descriptor and tiers will reference sit in modules that would put the
  descriptor in a cycle: `ToolName` in `src/evaluation/models.py` (and exported from `src.evaluation`),
  the argument models and their shared base in `src/orchestrator/analysis_tools.py`, the selection classes
  and `AnalysisSelection` in `src/workspace/requests.py`, and `NativeEvidence` in
  `src/workspace/execution.py`. `AnalysisType` in `src/core/constants.py` is a per-strategy name list with
  no reader.
- **Decision:** move each symbol to its final home with one import path and no compatibility re-export;
  delete `AnalysisType`. No behavior change, no descriptor.
- **Scope:** new `src/orchestrator/tool_names.py`, `src/orchestrator/analysis_tool_arguments.py` (the shared
  base renamed `AnalysisToolArguments`, `FiniteFloat`, `PositiveFiniteFloat`), `src/strategies/<strategy>/tool.py`
  (arguments model only, four files; Momentum's `_MOMENTUM_DEFAULTS` goes with its model),
  `src/workspace/selection_base.py` (the shared selection base, public as `FrozenSelection`, and the two
  CLI provider tuples both Graham selections read, public as `CLI_SECURITY_PROVIDERS` and `CLI_QUOTE_PROVIDERS`),
  `src/strategies/<strategy>/selection.py` (four files; `FCFPolicySnapshot` goes with `FCFGrowthSelection`) and
  `src/workspace/strategy_types.py` (`NativeEvidence`, `SelectionMember`, `AnalysisSelection`);
  `src/orchestrator/analysis_tools.py`, `src/workspace/{requests,execution}.py` (`AnalysisRequest`,
  `parse_selection` and its JSON helpers stay in `requests.py`);
  `src/evaluation/{__init__,models,composition,runner,ollama_runner,evaluator,catalog}.py` (the
  `src.evaluation` export of `ToolName` is removed); the six `src/evaluation/cases/*.py` importers;
  `src/core/constants.py`; every test that imports a moved symbol; and `docs/EVALUATIONS.md` and
  `docs/project/ARCHITECTURE.md`. The four-model `AnalysisToolArguments` union in `composition.py` is
  replaced by the shared base here, so one name never denotes two things; every consumer reads only
  `ticker` and `model_dump` and dispatches by `isinstance`. The `ANALYZE_*_TOOL` constants and
  `ANALYSIS_TOOL_ARGUMENT_MODELS` stay until SWC.2c. The move adds twenty entries to T13's transition
  allowlist, one for each import of a strategy's `tool` file by `analysis_tools.py`, `runner.py` and
  `ollama_runner.py` (SWC.2c removes them) and by `composition.py` and `catalog.py` (SWC.2d removes them);
  [design §4](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#4-static-declaration-model) lists them.
- **Branch:** `feat/swc-2b-symbol-moves`, from `main` after SWC.2a has merged.
- **Detail:** [SWC.1 design §4 and §11](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#11-migration-from-current-declarations).

#### SWC.2c — Descriptor and orchestration wiring

- **Problem:** each strategy currently has its own handler, dependency fields, registration call and
  evaluation argument/tool mapping; an omitted branch can silently remove a strategy from production or
  deterministic evaluation.
- **Decision:** establish the closed declaration at the composition root and focused metadata/coverage
  checks, then give the orchestration and evaluation routing consumers their slice by injection. Each
  strategy owns its dependency class and handler. Keep analyzer config creation and injected analyzers
  strategy-specific.
- **Scope:** new `src/strategy_wiring.py`, `src/core/strategy_errors.py`, `src/orchestrator/tool_runtime.py`,
  `scripts/strategy_conformance.py` and the conformance tests; `src/orchestrator/analysis_tools.py`
  (`AnalysisToolDependencies`, `AnalysisToolHandlers`, the `ANALYZE_*_TOOL` constants and
  `ANALYSIS_TOOL_ARGUMENT_MODELS` are deleted; registration receives the injected handler mapping);
  `src/strategies/<strategy>/tool.py` (dependency class and handler);
  `src/evaluation/{composition,runner,ollama_runner}.py`; removes its twelve T13 transition entries.
  `NativeAnalysisResult` is replaced by
  `NativeEvidence`; `_native_status` becomes each behavior's `native_status` (Momentum's returns `None`) and
  stops defaulting to FCF. Fixture composition stays in `composition.py` as per-strategy functions until
  SWC.2d. Do not change evaluation fixture truth, scoring, formula semantics or external-call behavior.
- **Branch:** `feat/swc-2c-descriptor-orchestration-wiring`, from `main` after SWC.2b has merged.
- **Detail:** [SWC.1 design §3, §6 and §11](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#11-migration-from-current-declarations),
  [inventory disposition](#4-inventory-disposition) and [audited inventory](#appendix-a-proposal-inventory-verified-against-main).

#### SWC.2d — Evaluation tier

- **Problem:** fixture composition and the fixture-capability check are per-strategy code inside one
  generic module, and the golden suite's argument builder is one chain keyed by case id.
- **Decision:** a strategy-owned `evaluation.py` per strategy holds its `compose` and `requirement`; a
  closed tuple `EVALUATION_STRATEGIES` in `src/evaluation/strategy_fixtures.py` pairs each with its core
  bundle by dependency type. Fixture truth stays hand-written and reviewed. The catalog's case tuple and
  suite version stay explicit.
- **Scope:** new `src/evaluation/{strategy_fixtures,fixture_context}.py` (each fixture identifier is defined in
  the fixture module of its evidence),
  `src/strategies/<strategy>/evaluation.py` and `src/strategies/_graham/evaluation.py`;
  `src/evaluation/{composition,catalog}.py`; the case modules (each case's reviewed arguments move beside
  it); tests and T10's evaluation-tier surface; removes its eight T13 transition entries. Every case module
  becomes single-strategy and is named for its strategy package: GRN-04 and GRN-05 move from
  `graham_resolution.py` into `graham_number.py`; FPI-01, FPI-02 and FPI-04 move from `sec_edgar_fpi.py`
  into `graham_growth.py` and FPI-03 into the FCF module, which is renamed `fcf_growth.py`. T13 gains the
  clause that `src.evaluation.cases.<strategy>` may import the tool role of `src.strategies.<strategy>` and
  of no other strategy, because the moved arguments make that import permanent. Case ids, the order of
  `DETERMINISTIC_CASES`, the suite version and the fixture modules do not change. No fixture value,
  expected outcome or score changes. T13 also gains the rule that only generic evaluation modules import the
  evaluation tier, with the tier module's entry in the root-importer list, a staleness check and a negative test.
- **Branch:** `feat/swc-2d-evaluation-tier`, from `main` after SWC.2c has merged.
- **Detail:** [SWC.1 design §3.3 and §11](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#33-behavior-members-and-the-two-tiers).

### SWC.3 — Workspace, CLI tier and direct commands

Split in three: the workspace consumers, the CLI tier, and the direct commands, which carry patch-target
changes in thirteen test modules.

#### SWC.3a — Workspace consumers

- **Problem:** persisted selections, selection-to-config conversion, method adapters, native result
  unions, version metadata and evidence codecs each repeat strategy-specific wiring. Version tuples must
  stay aligned across capture, storage and decoding.
- **Decision:** give each consumer its slice by injection and read version metadata from the descriptor.
  Retain explicit typed selection/config/result boundaries, strategy-owned execution adapters and codecs.
  Any stored-shape change increments its relevant version; no migration or compatibility code is added during
  the consolidation period. Dispatch fails closed: evidence or a stored run that matches no declared
  strategy is rejected with an error naming it. No strategy is the default branch. Today only
  `encode_evidence` falls through to Momentum; `decode_evidence` already rejects an undeclared pair before
  its Momentum branch, and both become injected lookups.
- **Scope:** `src/strategy_wiring.py` (the selection, parse, codec and version members and fields),
  `src/workspace/requests.py` (`parse_selection(alias, config_json, parsers)`), `src/workspace/method_aliases.py`
  (deleted; the descriptor owns the alias vocabulary), `src/workspace/execution.py`, `src/workspace/codecs.py`,
  `src/workspace/refresh.py`, the strategy execution adapters (each gains its normalizer), `src/workspace/capture.py`
  (`ExecutionCapture`), `src/workspace/selection_base.py` (the shared `config` body rules), per-strategy
  codec modules (each gains its `ticker_of` function) and selection modules (each gains its parser),
  `src/data/repositories/watchlists.py` (alias resolver at construction, through one helper in
  `src/cli_workspace.py`), `src/cli.py` (Momentum profile composition, the `execute` calls and the normalizer
  imports), `src/cli_workspace.py` (the repository helper, the Momentum composition copy, and the alias lookups
  that read the root's `BY_ALIAS` and `BY_METHOD_ID` now that `method_aliases.py` is gone),
  `src/reporting/analysis_runs.py` (`project_run` receives the injected codecs), the `getattr(selection, "as_of",
  None)` probe in `execute`, the evaluation tier (`src/evaluation/strategy_fixtures.py` and the four strategy
  `evaluation.py` files gain the required typed `sample_selection`, [design H.8](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h8-the-evaluation-tier-holds-a-sample-selection)),
  the root-importer list in T13, `scripts/strategy_conformance.py` (T1, T8, T11, T15 and T24), and focused tests. Replace Momentum's three
  profile-composition copies (two in `src/cli.py`'s `momentum` command, one in `src/cli_workspace.py`'s
  `_execute_momentum`) with one `compose_momentum_profile` in `src/strategies/momentum/execution.py`; detail in the
  [Momentum profile composition note](MOMENTUM_PROFILE_COMPOSITION_DEDUPLICATION.md) and
  [SWC.1 design §14](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#14-momentum-profile-composition-helper). Preserve
  the `AnalysisSelection` union, conversion methods, adapter behavior, `NativeEvidence` union,
  `AnalysisRun` replay guarantees and refresh isolation. No financial or outcome classification changes.
  Add tests that an undeclared evidence type and an undeclared `(analysis_id, method_id)` are rejected
  rather than handled as Momentum; every valid input encodes and decodes exactly as before. Removes its eight
  T13 transition entries.
- **Branch:** `feat/swc-3a-workspace-consumers`, from `main` after SWC.2d has merged.
- **Detail:** [SWC.1 design §6 and §11](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#11-migration-from-current-declarations),
  [inventory disposition](#4-inventory-disposition), [audited inventory](#appendix-a-proposal-inventory-verified-against-main),
  and the [Momentum profile composition note](MOMENTUM_PROFILE_COMPOSITION_DEDUPLICATION.md).

#### SWC.3b — CLI tier

- **Problem:** the watchlist selection builder is one chain ending in an unconditional FCF return, and the
  refresh executor is an `isinstance` chain; both are per-strategy code in `src/cli_workspace.py`.
- **Decision:** each strategy's selection builder and refresh executor move unchanged into
  `src/strategies/<strategy>/cli.py`; the closed tuple `CLI_STRATEGIES` in `src/cli_strategy_wiring.py`
  pairs them with the core bundle by selection type, and `cli_workspace.py` looks them up. A missing key
  raises `UndeclaredStrategyError`.
- **Scope:** new `src/cli_strategy_wiring.py`, `src/cli_watchlist_flags.py` (the flag bundle every builder reads) and
  four `src/strategies/<strategy>/cli.py`; `src/cli_workspace.py` (`_parse_analysis`, the `--analysis` help,
  `_build_selection`, `_refresh_executor`, the four `_execute_*` and their option converters);
  `scripts/strategy_conformance.py`; tests and T10's CLI-tier surface, including the patch strings in
  `tests/test_cli_refresh.py` and `tests/test_workspace_integration.py` that name the moved provider
  composition; removes its four T13 transition entries. T13 also gains the rule that only listed CLI modules
  import the CLI tier (`src.cli_workspace` in SWC.3b and `src.cli` in SWC.3c), with the tier's entry in the root-importer
  list, a staleness check and a negative test.
- **Branch:** `feat/swc-3b-cli-tier`, from `main` after SWC.3a has merged.
- **Detail:** [SWC.1 design §3.3, §6 and §11](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#33-behavior-members-and-the-two-tiers)
  and [Appendix H.9 to H.13](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h9-the-cli-tiers-shape-and-lookups).

#### SWC.3c — Direct commands

- **Problem:** the four direct commands and their helpers are per-strategy code in `src/cli.py`, which
  registers each with `@app.command`.
- **Decision:** each command moves into its strategy's CLI file as a plain function; `cli.py` adds the
  commands by iterating `CLI_STRATEGIES` through `add_strategy_commands`. A strategy file never registers
  itself. `_maybe_save_run` and `get_cli_run_context` move to `src/cli_run_support.py`.
- **Scope:** `src/cli.py`, new `src/cli_run_support.py`, the four `src/strategies/<strategy>/cli.py`, the
  thirteen test modules that patch `src.cli.` names (76 patch strings, retargeted), T7 and T22; removes its eight T13 transition entries.
  The new `command` member of the CLI tier and `add_strategy_commands` also change `src/cli_strategy_wiring.py`,
  `scripts/strategy_conformance.py` (T7, T14, T15, T22) and `tests/test_cli_strategy_wiring.py`; the
  help-output pin adds `tests/_cli_help_output.py`, `tests/test_cli_help_output.py` and
  `tests/expected_output/cli_help/`; T22 adds `tests/test_save_run_every_direct_command.py` and a provider
  helper in `tests/_direct_command_output.py`; the layering and conformance tests are updated; and the
  docstrings and two guides that named `src/cli.py` for moved code are corrected
  ([design H.15 to H.22](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h15-the-command-member-and-add_strategy_commands)).
  Removes `src/cli.py`'s copies of the three FCF option converters (`_historical_horizon`, `_forward_policy`,
  `_fcf_classification_basis`), which are the same code as the ones SWC.3b moved to `src/strategies/fcf_growth/cli.py`,
  and moves its Momentum window check (`_validate_momentum_windows`, which exits with code 2 and so differs from the
  builder's `BadParameter` check) into `src/strategies/momentum/cli.py`.
- **Branch:** `feat/swc-3c-direct-commands`, from `main` after SWC.3b has merged.
- **Detail:** [SWC.1 design §6, §11 and §12](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#12-framework-drift-checks).

### SWC.4 — Reporting and typed JSON envelopes

Every `--json` document gets a typed model and a checked-in schema, and failures get one envelope. That
is three reviewable concerns, so it is three slices, in this order; SWC.4d follows them to decide one failure-reporting
question the first three leave open. The contract, the document list,
the schema layout and the output changes are in the
[SWC.1 design §11 and §13](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#13-failure-envelope-contract). Keep `projection_version`, method
version and result-schema version distinct and do not silently reinterpret historical runs. See the
[IR.5 schema decision](#b3-ir5-schemas).

#### SWC.4a — Failure envelope and schema generator

- **Problem:** failures reach callers in three unrelated shapes, per-job refresh failures have no
  stable code, and no schema generator or drift check exists.
- **Decision:** one `FailureEnvelope` and one classifier serve the direct and workspace commands;
  `refresh --json` jobs carry a `reason_code`; `DatabaseMaintenanceReport` adopts the envelope's field
  names. Failures are reported, never self-remediated. Momentum's window validation, which exited with code 2
  on the direct command and raised a parameter error on the watchlist commands, reports one
  `invalid_parameter` failure through the envelope on both ([B.10](#b10-swc4a-momentum-window-failure-2026-10-06)).
- **Scope:** `src/reporting/documents/{__init__,failure,database}.py`, `src/reporting/failure_classification.py`,
  `src/cli_support.py`, `src/reporting/presentation.py`, the `execution_errors` call sites in the strategy
  command files (the Momentum file also holds the window check), `src/cli_workspace.py` (`--json`-aware failures),
  `src/cli_database.py`, `src/workspace/refresh.py` (injected classifier and per-job code), one
  `WatchlistNotFoundError` in `src/workspace/watchlists.py` and its two importers
  (`src/data/repositories/watchlists.py`, `src/workspace/refresh.py`), `AnalysisConfigurationError` moved to the
  classifier module with its two importers (`src/cli_composition.py`, `src/cli_health.py`),
  `docs/user/DATABASE.md`, `docs/user/USAGE.md` and `docs/user/WORKSPACE.md` (prose that described the
  old failure output), `refresh` of an empty watchlist as a `watchlist_empty` failure
  ([B.11](#b11-swc4a-an-empty-watchlist-is-a-refresh-failure-2026-10-06)), a new `scripts/generate_schemas.py`, `schemas/` (failure, database report), tests T18 to
  T20 and the existing tests whose expectations the listed output changes alter
  ([design H.23 to H.27](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h23-failure-model-classifier-and-module-homes-2026-10-06)).
- **Branch:** `feat/swc-4a-failure-envelope`, from `main` after SWC.3c has merged.
- **Detail:** [SWC.1 design §13 and §18](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#13-failure-envelope-contract) and the
  [structured error reporting note](STRUCTURED_ERROR_REPORTING.md).

#### SWC.4b — Typed workspace documents

- **Problem:** the watchlist, delete-outcome, `runs list` and refresh-summary documents are built from
  hand-written dictionaries with no typed model or schema.
- **Decision:** one model per document, byte-identical to today's output apart from the changes listed in
  the design. Selections inside watchlist documents are typed by the `AnalysisSelection` union.
- **Scope:** `src/reporting/documents/{timestamp,watchlist,runs,refresh}.py` (`timestamp.py` is the one instant type every
  document model uses), the JSON builders in `src/cli_workspace.py`, four schemas and their entries in
  `scripts/generate_schemas.py`, tests and the stored workspace scenario (`tests/_workspace_command_output.py` and
  `tests/expected_output/workspace_commands/`), and `docs/user/WORKSPACE.md`. One output change, listed in
  [design §13.4](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#134-what-changes) row 6: `runs list` `completed_at` is written `+00:00`, not `Z`.
- **Known at SWC.4a:** the `refresh --json` document has no `schema_version`, so SWC.4a's new `reason_code` key on
  each result bumped no version ([design H.27](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h27-output-changes-and-the-check-that-success-output-is-unchanged-2026-10-06)).
  SWC.4b publishes the refresh summary schema and states, in the schema and the design, that the document is unversioned
  or what version it carries; adding a version is an output change it lists.
- **Branch:** `feat/swc-4b-workspace-documents`, from `main` after SWC.4a has merged.
- **Detail:** [SWC.1 design §13.6](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#136-every-json-document-is-typed).

#### SWC.4c — Typed strategy envelopes and replay dispatch

- **Problem:** report construction and stored-run replay retain per-method type dispatch, and the four
  strategy documents lack the typed envelope models IR.5 intended to add.
- **Decision:** typed envelope models back the real builders and are validated at the output boundary; the
  envelope modules hold each strategy's identity constants, which presenters read instead of the
  descriptor; the descriptor gains `json_envelope` and the `project` member; `project_run` receives the
  injected projector mapping and fails closed; the command-coverage test lands last, with no exemption list.
- **Scope:** `src/strategy_wiring.py`, `src/strategies/<strategy>/envelope.py` and `replay.py` (the four
  projectors leave `analysis_runs.py`; each `replay.py` also holds the strategy's `headline` function only
  from Step 3.5 slice 3.5.0), `src/strategies/_graham/replay.py`, `src/reporting/replay_inputs.py`
  (`ReplayOptions` and `UnsupportedProjectionError` move here), `src/reporting/json_documents.py` (the
  failure, workspace and database documents; the generator and tests add each descriptor's `json_envelope`
  from the root), `src/reporting/analysis_runs.py`, the four `presenter.py` files, four schemas, and tests
  T9, T10, T20, T21 and T24 extended; removes its four T13 transition entries.
- **Branch:** `feat/swc-4c-strategy-json-envelopes`, from `main` after SWC.4b has merged.
- **Detail:** [SWC.1 design §6, §10 and §13.6](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#10-conformance-tests-and-negative-control),
  [inventory disposition](#4-inventory-disposition) and
  [audited inventory](#appendix-a-proposal-inventory-verified-against-main).

#### SWC.4d — Command validation failures and the failure envelope

- **Problem:** a validation failure that a command raises itself reaches the caller in one of two ways. Momentum's window
  check is an `invalid_parameter` failure through the envelope with exit 1 ([B.10](#b10-swc4a-momentum-window-failure-2026-10-06)),
  while the Graham and FCF parameter checks, and the other checks raised as `typer.BadParameter`, exit 2 as plain text, even
  under `--json`.
- **Decision:** SWC.4d decides whether those validation failures move into the failure envelope, starting with the Graham and
  FCF parameter checks, and which of the rest follow. It does not revisit failures the parser rejects before a command runs,
  which are decided ([B.12](#b12-swc4a-parser-rejected-failures-stay-usage-errors-2026-10-06)). SWC.4d lists its own output
  changes, by command, when it is planned. No behavior changes until it runs.
- **Scope:** to be set by the SWC.4d plan; the question and the current behavior are in
  [design §13.3](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#which-option-values-are-invalid-parameter-today).
- **Branch:** `feat/swc-4d-command-validation-failures`, from `main` after SWC.4c has merged.
- **Detail:** ⚠ no slice plan yet.

### SWC.5 — Site data, status command and generated lists

- **Problem:** a contributor learns what is missing from a strategy only by running tests, the edit-site
  list is maintained by hand in two places, and the strategy lists in `USAGE.md` and `WORKSPACE.md` are
  hand-written.
- **Decision:** one data file lists the edit sites and feeds the guide's table; a developer script reports
  each site done or missing by running the conformance checks in report mode, so it cannot disagree with
  them; the two pages' strategy lists are generated from the descriptors and drift-tested.
- **Scope:** new `scripts/strategy_sites.toml`, `scripts/strategy_sites.py`, `scripts/strategy_status.py`,
  `scripts/generate_strategy_docs.py`; `scripts/strategy_conformance.py` (every check returns gaps);
  marked blocks in `docs/user/USAGE.md` and `docs/user/WORKSPACE.md`; the watchlist option prose moves into
  the strategy guides; `docs/user/strategies/FCF_EARNINGS_GROWTH.md` renamed `FCF_GROWTH.md` with its links;
  tests T25 and T26.
- **Branch:** `feat/swc-5-site-data-and-status`, from `main` after SWC.4c has merged.
- **Detail:** [SWC.1 design §19.1, §19.2 and §10](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#19-contributor-tooling).

### SWC.6 — Specimen strategy and generator

- **Problem:** the dispatchers and both tiers can only be exercised through the four production
  strategies, and adding a strategy is a long manual sequence.
- **Decision:** a checked-in specimen strategy, used only by tests, is wired through every layer; a
  generator writes the typed stubs and the five mechanical one-line edits, refusing to overwrite; a test
  runs the generator in a temporary copy, fills the stubs with trivial bodies, and requires the strict type
  check and the conformance suite to pass. `AGENTS.md` §3 gains one narrow exception for generator output
  that fails the gate by design.
- **Scope:** new `tests/specimen/`, `scripts/new_strategy.py`, `scripts/strategy_templates/`,
  `src/core/strategy_stub.py`, `tests/scripts/generator_fills/`, tests T27 to T29 and the negative control
  re-based on the specimen; `AGENTS.md` §3.
- **Branch:** `feat/swc-6-specimen-and-generator`, from `main` after SWC.5 has merged.
- **Detail:** [SWC.1 design §19.3 to §19.6](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#19-contributor-tooling).

### SWC.7 — Contributor guide and final conformance

- **Problem:** contributors need one guide for adding a strategy and a complete, tested account of which
  wiring is automatic and which work remains strategy-specific. Schemas ship in SWC.4.
- **Decision:** verify the published schemas that SWC.4a to SWC.4c generate from typed models and document
  the approved strategy-addition workflow in one guide, whose edit-site table is generated from the site
  data file. Make the descriptor's authorization permanent before the temporary rule that permits it is
  removed. Challenge the structural checks with independent end-to-end review.
- **Scope:**
  - **One contributor guide.** Move `docs/project/ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md` to
    `docs/TOOL_DEVELOPMENT.md` and extend it with the strategy-addition workflow, the status command and
    the generator. Keep its existing content, update every link to it, and leave no second guide behind.
  - **Permanent authorization.** Amend `AGENTS.md` §3 so that the closed, statically declared
    strategy descriptor is permitted in its own right, with dynamic discovery, plugins,
    self-registration and factory hierarchies still prohibited. Step 3.5.0 removes `AGENTS.md` §0,
    which is the descriptor's only authorization today.
  - **Discovery Workbook.** Close open question 3 in `docs/project/DISCOVERY_WORKBOOK.md` (whether more
    strategies justify a registry mechanism), recording that the closed static descriptor is the answer and
    why discovery, plugins and self-registration remain excluded.
  - Verify that every descriptor has a current published schema (SWC.4a owns generation and the drift
    check), and verify conformance across all current strategies and generic consumers. Use an independent
    implementation review to prove that omission fails with a useful diagnostic.
  - Point the Step 3.5 contract plan's link to the edit-site table at the table's new home in
    `docs/TOOL_DEVELOPMENT.md`.
  - Do not pull Step 3.5 strategy implementation into SWC; Piotroski exercises the documented path when
    that strategy is implemented.
- **Branch:** `feat/swc-7-contributor-guide`, from `main` after SWC.6 has merged.
- **Detail:** [acceptance criteria](#7-acceptance-criteria) and [conformance design](#33-static-declaration-typing-and-conformance).

## 6. Scope limits

- Any formula, metric, classification, status or strategy-selection change.
- A common result supertype, dynamic discovery, analyzer self-registration, a registering decorator,
  plugin loading, a descriptor subclass hierarchy, or a speculative factory hierarchy.
- A module below the composition root importing a descriptor, a tier or a strategy-owned CLI or
  evaluation file.
- Changes to Step 3.5 strategy calculations, financial fixtures, independent expected values,
  Golden truth, or ranking behavior.
- Rewriting presentation semantics or historical projection versions beyond changes specifically
  needed to type and dispatch their existing JSON envelopes.
- Storage migrations or backward-compatibility support for local persisted data during the
  consolidation period.
- A general purpose serialization framework beyond typed JSON envelopes and the schema outputs
  required here.
- A generator that writes calculation, formula, classification or presentation content, or copies from an
  existing strategy's analysis.

## 7. Acceptance criteria

- **Wiring completeness:** the approved source of truth for supported strategies is checked against
  every owned surface: tool name and argument model, handler, evaluation enum and argument routing,
  fixture composition and requirement (evaluation tier), persisted selection parsing and config conversion,
  selection builder and refresh executor (CLI tier), execution adapter and outcome classification, run
  method/result/config versions, evidence encode/decode, report and replay dispatch, typed JSON envelope,
  published schema and generated strategy lists. Adding a supported strategy while deliberately omitting
  any one required entry must fail, with the missing wiring point identified: by `mypy --strict` where the
  entry is a typed member, and by a focused conformance test where it is a tier entry, a file or a
  generated list. This directly covers the proposal's “forgotten branch” failure; a test that only checks
  descriptor construction is insufficient.
- **Static strategy set:** no runtime discovery, auto-registration, registering decorator, plugin loader,
  or speculative factory hierarchy. A strategy file never registers itself. Each analyzer keeps its own
  typed config and complete result evidence type.
- **Strategy ownership:** each strategy keeps its own `AnalysisSelection` and `NativeEvidence` union
  members, its arguments model, handler, codec, adapter behavior, outcome classification, projector and
  presentation semantics, in strategy-owned modules. The descriptor only routes generic infrastructure to
  those contracts.
- **Layering:** every file a strategy owns, except its fixtures and cases, is in `src/strategies/<strategy>/`,
  named for its role, and every `__init__.py` under `src/strategies/` is empty. The role rule holds and T13
  enforces it: within a strategy only a higher-ranked role file imports a lower one; no strategy imports
  another; foundation, reporting and the other generic modules import only analyzer and selection roles and
  never the composition root, a tier or a strategy's CLI or evaluation file; no module under `src` imports
  `tests`. The layering test counts parent-package initialization, and `src/workspace/__init__.py` is empty.
- **Transition closure:** the exact T13 transition allowlist in SWC.1 design §4 grew once, in SWC.2b, by the
  twenty edges to the new `tool` files; from then on it shrinks only when its owning slice removes the
  corresponding import edge, and it is empty when SWC.4c merges. SWC.7's final conformance verifies that it
  remains empty.
- **Invocation contract:** production callers continue to invoke analyzers only through
  `BaseAnalyzer[ConfigT, ResultT].run_analysis(ticker, config, context)` with dependencies injected
  at construction and cross-cutting concerns carried in `AnalysisContext`.
- **Outcome and provenance:** metrics remain `MetricResult`; unavailable and inapplicable states
  remain explicit; provenance is retained. No silent defaults, `NaN` or `Inf` are introduced.
- **JSON contract:** every `--json` document (strategy, workspace, database and failure) has a typed
  model backing its builder and a checked-in generated schema; a drift check detects stale output; and a
  conformance test enumerates every command offering `--json` from the CLI's own command tree and fails,
  naming the command, if it lacks either. Existing payload meaning and projection versioning remain
  explicit except for the output changes the design lists.
- **Failure envelopes:** direct and workspace commands report failures through typed envelopes with
  stable `reason_code` values, `--json`-aware on the workspace commands; per-job failures in `refresh --json`
  carry a `reason_code`; the database report uses the same `reason_code` and `reason` field names;
  schemas and a drift check cover them. No command self-remediates (for example by running `db upgrade`).
- **Momentum profile composition:** exactly one implementation remains, used by the direct
  `momentum` command, its `--save-run` branch and the workspace refresh.
- **Persistence:** any changed stored config/evidence/result shape bumps the relevant version. No
  migration or compatibility layer is added during this period.
- **No semantic change:** no analyzer formula, classification, result meaning, or evaluation
  expectation changes. Report/CLI output may change only where specifically identified and approved
  in the slice contract.
- **Patch targets resolve:** after SWC.2a, a test resolves every string patch target in `tests/` to an
  existing attribute, and it keeps passing in every later slice.
- **No output change:** the direct-command output test passes unchanged in every later slice that claims no
  output change. A slice that changes output regenerates the stored files in the same change, and the diff to
  them is what the review approves.
- **Edit sites:** adding a strategy takes the 19 sites in the design's edit-site table, in 24 files across 9
  directories, nine of them existing files; five of those are edited by the generator, and the other four (the catalog,
  its test, and the two watchlist-option files of site 19, edited only by a strategy with options of its own) are
  reviewed.
- **Contributor tooling:** one site data file is the source of the guide's table, the status command, the
  generator and the specimen's completeness test; the status command and the conformance tests share their
  check bodies; the generator writes wiring only and refuses to overwrite; a test runs it in a temporary
  copy and requires the strict type check and the conformance suite to pass with trivially filled stubs;
  the specimen strategy runs through every layer and cannot reach production tuples, the user CLI or the
  published schemas; the quality gate fails while any `unfilled_stub` call remains in `src/`.
- **Generated lists:** the strategy lists in `USAGE.md` and `WORKSPACE.md` are generated from the
  descriptors and a drift test fails when they are stale.
- **Contributor guide:** `docs/TOOL_DEVELOPMENT.md` is the only contributor guide for adding a
  strategy. It replaces `docs/project/ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md`, keeps that guide's
  content, and identifies what the shared wiring owns and what remains strategy-specific, including
  calculator, source fixtures, presentation semantics and Golden cases. No link to the old path
  remains.
- **Fail-closed dispatch:** no generic consumer treats one strategy as the default. Undeclared
  evidence and undeclared stored runs are rejected, and tests prove it.
- **Lasting authorization:** `AGENTS.md` §3 permits the closed static descriptor without relying
  on §0, so the descriptor remains authorized when Step 3.5.0 removes §0.
- **Quality gate:** the complete managed quality gate passes at the end of every implementation
  slice, including ≥85% coverage and new meaningful branch coverage; any new deterministic tests
  make no real provider, network or LLM calls. The final link check passes.
- **Step 3.5 readiness:** Piotroski can be added using the documented contract, the status command and
  the generator without an unplanned per-consumer dispatch edit, or the relevant conformance test fails
  clearly and points to the omitted wiring contract.

## 8. Background and origin

SWC was accepted on 2026-09-24 after an inventory pass during IR.2. The accepted proposal argues
that four existing strategies each repeat orchestration, workspace, codec, reporting and evaluation
wiring, and that Step 3.5's seven strategies would multiply the risk of a missed branch. IR.5's
typed JSON envelope and schema scope moved into SWC because it is another per-strategy consumer
contract. SWC follows R3 (which followed IR) and precedes PKG and Step 3.5 as recorded in the
milestone plan.

The original proposal's claims are not taken as a current inventory: Appendix A records a fresh
symbol-level comparison after IR.2–IR.8 and PR #53. The code inventory baseline is `main` at
`8edbff4`; later `main` commit `3375a77` records the R3 close-out and changes documentation only,
not the code wiring observations. SWC.1 re-verified the inventory at `247ecdf`. After SWC.1 merged,
a co-location study led the project owner to adopt strategy-owned modules, a descriptor at the
composition root with injected consumers, and contributor tooling; [B.7](#b7-co-location-adoption-2026-10-03)
records the decisions and the renumbering.

---

## Appendix A: Proposal inventory verified against main

Baseline: `main` at `8edbff4` (`Add sequence table quality check`, 2026-10-01), which includes PR
#53's ESC-E renewal and PR #52's revised Step 3.5 contract. SWC.1 re-verified every row at
`247ecdf` (2026-10-02); no code changed between the two commits. The
[SWC.1 design](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#appendix-a-inventory-re-verified-at-247ecdf) classifies every site, including
those listed after this table. “Still present” means the named
per-strategy wiring remains; “Changed” means its shape, location or behavior differs from the
proposal; “Gone” means the named wiring no longer exists. These classifications do not imply that a
row is in scope for removal; they identify what the implementation plan must account for.

| Original wiring point | Status | Current file and symbol(s) | Verification note |
| :--- | :--- | :--- | :--- |
| Per-strategy `*ToolArguments` Pydantic models | Still present | `src/orchestrator/analysis_tools.py`: `MomentumToolArguments`, `GrahamNumberToolArguments`, `GrahamGrowthValueToolArguments`, `FCFEarningsGrowthToolArguments` | One strict model per strategy; shared `_AnalysisToolArguments` base. |
| Per-strategy `ANALYZE_*_TOOL` constants | Still present | `src/orchestrator/analysis_tools.py`: four `ANALYZE_*_TOOL` constants | Each method still has its own name constant. |
| `ANALYSIS_TOOL_ARGUMENT_MODELS` entries | Still present | `src/orchestrator/analysis_tools.py`: `ANALYSIS_TOOL_ARGUMENT_MODELS` | Mapping remains consumed by the local Ollama runner. |
| Flat strategy-specific dependency fields | Changed | `src/orchestrator/analysis_tools.py`: `AnalysisToolDependencies` | Still strategy-specific analyzer/provider fields, but IR.2 standardized invocation and injected context; `profile_resolver` is shared/optional. |
| Per-strategy handler methods | Still present | `src/orchestrator/analysis_tools.py`: `AnalysisToolHandlers.analyze_momentum`, `.analyze_graham_number`, `.analyze_graham_growth_value`, `.analyze_fcf_earnings_growth` | All validate strategy arguments, build owned config and invoke the shared analyzer envelope. |
| Per-strategy registration calls | Still present | `src/orchestrator/analysis_tools.py`: `register_analysis_tools` | Four explicit `register_tool` calls remain. |
| Per-strategy persisted selection models | Still present | `src/workspace/requests.py`: `MomentumSelection`, `GrahamNumberSelection`, `GrahamGrowthSelection`, `FCFGrowthSelection` | Strategy-specific config persistence remains; shared base is `_FrozenSelection`. |
| `AnalysisSelection` discriminated union | Still present | `src/workspace/requests.py`: `AnalysisSelection` | Union has four strategy members and remains the request/watchlist/run boundary. |
| Per-selection `to_*_config()` methods | Still present | `src/workspace/requests.py`: `to_momentum_config`, `to_graham_number_config`, `to_graham_growth_config`, `to_fcf_config` | Each typed selection converts to its own analyzer config. |
| One workspace execution adapter per strategy | Still present | `src/strategies/momentum/execution.py`: `MomentumCapture`, `run_momentum`; `graham_number_execution.py`: `GrahamNumberCapture`, `execute_graham_number`; `graham_growth_execution.py`: `GrahamGrowthCapture`, `execute_graham_growth`; `fcf_growth_execution.py`: `FCFGrowthCapture`, `execute_fcf_growth` | Files also retain strategy-specific outcome classification where applicable. Momentum has no native failure status classifier. |
| `NativeEvidence` result union | Still present | `src/workspace/execution.py`: `NativeEvidence` | Four heterogeneous native results remain explicitly unioned. |
| Per-strategy capture normalizers | Still present | `src/workspace/execution.py`: `from_momentum_capture`, `from_graham_number_capture`, `from_graham_growth_capture`, `from_fcf_growth_capture` | Still normalize strategy capture fields into `ExecutionCapture`. |
| `_METHOD_VERSIONS` metadata | Still present | `src/workspace/execution.py`: `_METHOD_VERSIONS` | One pair per method; IR changed persisted envelope versions and added `config_schema_version` alignment. |
| Refresh `isinstance` dispatch | Changed | `src/cli_workspace.py`: `_refresh_executor` | Still four explicit selection branches; current function is at a different location and composes per-method adapters. |
| `encode_evidence` isinstance chain | Changed | `src/workspace/codecs.py`: `encode_evidence` | FCF/Graham branches remain; Momentum is now the unconditional fallback rather than an explicit final branch, so unknown evidence is routed as Momentum. This is the live fall-through. |
| Decoder version membership and expected versions | Changed | `src/workspace/codecs.py`: `_EXPECTED_VERSIONS`, `decode_evidence` | Now one mapping entry stores `(config_schema_version, method_version, result_schema_version)`; `decode_evidence` validates run-schema, codec and projection versions too. |
| Per-method `decode_evidence` dispatch | Changed | `src/workspace/codecs.py`: `decode_evidence` | Explicit branches remain for FCF, Graham Growth and Graham Number, with Momentum as the final branch; ticker identity is checked per result shape. An undeclared pair is already rejected earlier by the version-table lookup, so only the structure, not the behavior, is a default branch. |
| Momentum instrument-profile composition | Still present | `src/cli.py`: `momentum` command (`--save-run` and default branches); `src/cli_workspace.py`: `_execute_momentum` | Three independent inline copies of one composition pattern; Graham and FCF Growth already share `compose_graham_profile`. Owned by SWC.3a ([Momentum profile composition note](MOMENTUM_PROFILE_COMPOSITION_DEDUPLICATION.md)). |
| Per-strategy evidence codec modules | Still present | `src/workspace/momentum.py`, `graham_number.py`, `graham_growth.py`, `fcf_growth.py`: `encode_*`, `decode_*` | One pair remains per strategy. |
| Per-strategy report construction functions | Changed | `src/reporting/analysis_runs.py`: `_project_momentum_v1`, `_project_graham_number_v1`, `_project_graham_growth_v1`, `_project_fcf_growth_v1` | Projection is now explicit versioned replay over persisted Analysis Runs, decodes stored evidence and retains type assertions; original line references no longer apply. |
| Strategy presentation modules | Still present | `src/reporting/momentum.py`, `graham_number.py`, `graham_growth.py`, `fcf_earnings_growth.py` | Each retains method-specific presentation and rendering. |
| `ToolName` enum | Still present | `src/evaluation/models.py`: `ToolName` | One enum member per tool remains. |
| Evaluation `AnalysisToolArguments` union | Still present | `src/evaluation/composition.py`: `AnalysisToolArguments` | Four model union remains for typed fixture dispatch. |
| Fixture dependency composition per strategy | Still present | `src/evaluation/composition.py`: `compose_fixture_dependencies` | Independently builds Momentum, Graham Number, Graham Growth and FCF analyzers/resolvers and assembles `AnalysisToolDependencies`. |
| Evaluation `_tool_name` isinstance dispatch | Still present | `src/evaluation/composition.py`: `_tool_name`; also `src/evaluation/runner.py` and `src/evaluation/ollama_runner.py`: `_tool_name` | Current main repeats argument-type mapping in three modules, not only the single location listed in the proposal. |

The proposal's prose also mentions one CLI command per strategy but does not inventory it as a
separate row. Direct command wiring remains in `src/cli.py`: `momentum`, `graham_number`,
`graham_growth` and `fcf_growth`; workspace job composition remains in `src/cli_workspace.py`:
`_execute_momentum`, `_execute_graham_number`, `_execute_graham_growth`, `_execute_fcf_growth` and
`_refresh_executor`. The proposal is therefore a useful starting inventory, not a complete list of
all current consumer surfaces. Any consolidated dispatch must also account for
`src/reporting/analysis_runs.py`'s `project_run` `(analysis_id, method_id)` replay selection and the
repeated evaluation `_tool_name` mappings above.

SWC.1's re-verification found further per-strategy sites that this table does not list. Each is
classified, with its owning slice, in the [SWC.1 design](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#a2-sites-missing-from-the-plans-appendix-a):

| Additional wiring point | Current file and symbol(s) | Owner |
| :--- | :--- | :--- |
| Alias vocabulary | `src/workspace/method_aliases.py`; `src/cli_workspace.py` alias uses; `src/data/repositories/watchlists.py` alias lookup | SWC.3a (`method_aliases.py`, the repository and the `cli_workspace.py` alias lookups, which now read the root's `BY_ALIAS` and `BY_METHOD_ID`); SWC.3b (the `--analysis` help text and the CLI tier's own use of the vocabulary) |
| Alias membership and a final unconditional Momentum branch | `src/workspace/requests.py`: `parse_selection` | SWC.3a |
| Identifier literals in failure calls and JSON builders | `src/cli.py`: six `execution_errors(analysis=, method=)` calls; `src/reporting/{momentum,graham_number,graham_growth}.py` | SWC.4a (`cli.py` calls), SWC.4c (builders) |
| Strategy name tested inside generic failure handling | `src/cli_support.py`: `analysis == "momentum"` | SWC.4a |
| A second `NativeEvidence`-shaped union, and an FCF default branch | `src/evaluation/runner.py`: `NativeAnalysisResult`, `_native_result`, `_native_status` | SWC.2c |
| An FCF default branch in the fixture capability check | `src/evaluation/composition.py`: `_require_tool_evidence` | SWC.2d |
| A one-member per-strategy name enum with no reader | `src/core/constants.py`: `AnalysisType` | SWC.2b (deleted) |
| An unconditional FCF return after a chain of method tests | `src/cli_workspace.py`: `_build_selection` | SWC.3b |
| A probe for a field every selection defines | `src/workspace/execution.py`: `getattr(selection, "as_of", None)` | SWC.3a |
| Tool descriptions, schemas and parser registry keyed by tool name | `src/evaluation/ollama_runner.py`: `_TOOL_DESCRIPTIONS`, `_tool_schemas_json`, `_tool_parser` | SWC.2c |

## Appendix B: Decision records and history

Entries B.1 to B.6 use the slice numbers in force when they were written; [B.7](#b7-co-location-adoption-2026-10-03) records the renumbering.

### B.1 Closed descriptor decision and IR.2 boundary

The descriptor is the single source of truth for duplicated infrastructure wiring metadata
identified in Appendix A. It may declare identifiers, tool and model types, applicable version
metadata, and references to strategy-owned functions needed for generic routing. It does not encode
strategy behavior, calculations, policy, a universal result type, or plugin/factory lifecycle. Its
static declaration is limited to this consolidation purpose under `AGENTS.md` §0.

IR.2's “no generic result supertype, registry or factory” decision remains operative for general
architecture. This plan authorizes only a narrow closed wiring declaration to remove the audited
duplication, while preserving each strategy's `ConfigT`, `ResultT`, evidence contract and
`BaseAnalyzer` invocation. That is a bounded exception to the earlier no-registry wording, not a
general strategy-registry authorization.

### B.2 Conformance decision

Option 2 in the former §3 sought independent evidence that a strategy or required wiring path had
not been forgotten. It was not selected as the primary architecture because a separately maintained
strategy inventory would preserve the repeated wiring knowledge SWC is meant to consolidate. Its
strongest safeguard is retained: focused conformance tests independently compare the descriptor
against existing supported-strategy boundaries, verify descriptor consumption by each required
generic surface, and include an incomplete-consumer negative control with a useful failure.

### B.3 IR.5 schemas

Typed envelope models back the actual `--json` payloads, preserve each strategy's evidence shape,
and generate checked-in schemas in a discoverable `schemas/` directory. Models are authoritative;
generation and drift checks are deterministic. Exact schema identifiers, filenames, and whether
publication uses per-envelope files or a top-level discriminated schema depend on the final model
shape and are settled during contract/implementation design, not left as an architectural choice. SWC.1 settled them: one file per document, listed in the design's section 11.

### B.4 Pre-implementation review (2026-10-02)

A review before SWC.1 found three gaps in this plan. Each was decided:

- **Momentum as the default branch.** Appendix A records that `encode_evidence` and
  `decode_evidence` route anything unrecognized to Momentum, but no slice owned the repair. SWC.3
  now makes dispatch fail closed. This is not a semantic change for any valid input. SWC.1 narrowed
  the claim: only `encode_evidence` falls through today; `decode_evidence` rejects an undeclared pair
  before its Momentum branch. Both still become table-driven.
- **Two contributor guides.** SWC.5 planned a new `docs/TOOL_DEVELOPMENT.md` while
  `docs/project/ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md` already covered the same ground. The
  project owner decided on one guide, named `docs/TOOL_DEVELOPMENT.md`. SWC.5 moves and extends the
  existing guide; the move happens in SWC.5 because that slice owns the document.
- **Authorization that expires.** The descriptor is permitted only by `AGENTS.md` §0, which Step
  3.5.1 removes, leaving §3's prohibition on registries as the only rule an agent would see. SWC.5
  now amends §3.

### B.5 Deferred items absorbed (2026-10-02)

The project owner decided that two items recorded as deferred belong to SWC:

- **Structured error reporting.** SWC.1 settles the typed failure-envelope contract (shape, stable
  `reason_code` values, whether `DatabaseMaintenanceReport` is the shared shape) and SWC.4a
  implements it for direct and workspace commands with generated schemas. The note's non-goal
  stands: failures are reported, never self-remediated. Detail: the [structured error reporting note](STRUCTURED_ERROR_REPORTING.md).
- **Momentum profile composition.** SWC.3 replaces the three duplicated composition sites with one
  implementation. This is a maintainability change, not a correctness defect. Detail: the [Momentum profile composition note](MOMENTUM_PROFILE_COMPOSITION_DEDUPLICATION.md).

The `Deferred` rows for both items leave the milestone sequence table.

### B.6 SWC.1 design decisions (2026-10-02)

The [SWC.1 design](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md) settles the descriptor, failure-envelope and conformance contracts. Where
it corrected this plan, the corrections are applied above and listed in
[the design's section 15](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#15-ir2-and-corrections-to-the-plan): `ToolName` stays hand-written;
handlers, executors and projectors stayed in consumer-owned keyed tables because a wider descriptor
imported by the foundation layers creates import cycles (reversed in [B.7](#b7-co-location-adoption-2026-10-03)); schema generation is owned by SWC.4a; every slice branches from `main`
after its predecessor merges. No IR.2 contract change is required. The project owner's review of
the design then decided that every `--json` document is typed, that per-job refresh failures carry
a `reason_code`, that `DatabaseMaintenanceReport` uses the envelope's field names, and that moved
symbols keep no compatibility re-export; SWC.4 was split into SWC.4a to SWC.4c to keep each slice
reviewable.

### B.7 Co-location adoption (2026-10-03)

After SWC.1 merged, a [co-location study](SWC_COLOCATION_STUDY.md) tested the question the merged design's
import-cycle evidence left open: whether strategy behavior could move into strategy-owned modules that a
descriptor references. It found that the cycles come from the direction (consumers import the descriptor),
not from where the functions live, and that a descriptor at the composition root with each layer's slice
injected is acyclic and changes no layering rule. The project owner decided:

- **Adopt the composition-root form in two tiers.** Core bundle at the root; selection builders, refresh
  executors and direct commands in a CLI tier; fixture composition and requirements in an evaluation tier.
  The design now describes it and does not depend on the study.
- **Schedule the locality moves** in the slice that owns each; none is deferred.
- **Fix the package-initialization cycle** in SWC.2a by emptying `src/workspace/__init__.py`, and make the
  layering test count parent packages.
- **Reduce the edit sites** to 18, in 22 files of which seven already exist: commands in strategy files, an
  evaluation tier, per-strategy dependency classes, one types file and the shared arguments base class in
  place of the union. The catalog's case tuple and suite version stay by hand because they are reviewed
  truth; `ToolName` stays a separate leaf for layering.
- **Add contributor tooling:** one site data file, a status command, a generator, a specimen strategy and a
  generator end-to-end test ([design §19](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#19-contributor-tooling)).
- **Add a repetition checkpoint to Step 3.5** after its first strategy slice, and a folder-layout decision
  to the package-rename plan.
- **Renumber:** SWC.2 became SWC.2a to SWC.2c, SWC.3 became SWC.3a to SWC.3c, the tooling is SWC.5 and
  SWC.6, and the guide (formerly SWC.5) is SWC.7.

### B.8 Final amendments before merge (2026-10-03)

Three decisions made while finalizing the design, recorded in the [design's Appendix E.4](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#e4-final-amendments-before-merge):

- **The side-by-side table is built first,** as Step 3.5 slice 3.5.0, over the four existing strategies, so
  the `headline` behavior member has a consumer before any new analyzer is written and is added once.
- **Native status is a Step 3.5 decision.** Every Step 3.5 result carries an explicit result-level status;
  the SWC design keeps only a pointer.
- **One package per strategy is adopted now,** and a new first slice, SWC.2a, relocates the existing
  strategy modules. The earlier SWC.2a to SWC.2c became SWC.2b to SWC.2d. The package-rename plan records the
  outcome and no longer holds an open layout decision.
- **Step 3.5 renumbering:** the side-by-side table is Step 3.5 slice 3.5.0, so Step 3.5.0 (the first
  implementation slice) removes `AGENTS.md` §0, and the golden suite is 3.5.7.

### B.9 SWC.3b audit: the watchlist-option site (2026-10-06)

- The SWC.3b audit found a per-strategy edit site the earlier audits missed: the watchlist options, declared per
  strategy in `src/cli_workspace.py` and carried by the new `WatchlistFlags` bundle in `src/cli_watchlist_flags.py`.
  It is row 19 of the design's edit-site table.
- Adding a strategy now takes 19 sites in 24 files, nine of them existing, across 9 directories; the figures in
  B.7 are the count at that date.
- The project owner confirmed the `WatchlistFlags` exception to §3.2 ([design Appendix
  H.10](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h10-the-watchlist-flag-bundle-an-approved-exception-to-the-no-growing-shared-class-rule)).

### B.10 SWC.4a: Momentum window failure (2026-10-06)

The project owner approved a scope extension to SWC.4a. Momentum's window validation reached a caller in two
unrelated ways: the direct command echoed a message and exited with code 2 (and wrote no JSON under `--json`),
and the watchlist builder raised a parameter error, a usage error rendered with a usage box. Both are now one
failure:

- **One check, one code.** A single function in `src/strategies/momentum/cli.py` raises `InvalidParameterError`,
  and the shared classifier maps it to the new stable `reason_code` `invalid_parameter` with status `error`. The
  code names a command option value rejected before any work, so it is not Momentum-specific and adds no
  per-strategy entry to generic tooling.
- **One sentence.** Both commands use the direct command's investor-readable wording, and it names the offending
  option (`--short-window`, `--long-window`, `--rsi-period`); Momentum's own check supplies the names, not generic
  tooling. The watchlist builder's earlier wording is removed.
- **One report.** The failure is reported through the envelope on the direct command (`--json`: the envelope on
  standard output; otherwise the sentence on standard error) and as the sentence on standard error from
  `watchlist create` and `watchlist add-selection`, which have no `--json`. The exit code is 1.
- **Order kept.** The check still runs before the `--as-of` check, and the other usage errors of the command stay
  usage errors (exit 2).

Resulting output change, in addition to [design §13.4](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#134-what-changes):

| Command | Before | After |
| :--- | :--- | :--- |
| `momentum` with an invalid window or RSI period | Message on standard error, exit 2, no JSON under `--json` | Envelope (`--json`) or the same message on standard error, exit 1, `reason_code` `invalid_parameter` |
| `watchlist create` and `watchlist add-selection` with the same values | Usage error naming the option, exit 2 | The same sentence on standard error, exit 1 |

The sentence changed from the direct command's earlier wording only by naming the option (`--short-window` for "short window"
and so on). The reason `invalid_parameter` is not `invalid_input` is in [design §13.3](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#133-reason-codes-and-stability).

### B.11 SWC.4a: an empty watchlist is a refresh failure (2026-10-06)

The project owner decided, during the SWC.4a review:

- **`refresh` of a watchlist with no entries is a failure, not a usage error.** It reports the new stable `reason_code`
  `watchlist_empty` through the envelope and exits 1, in text and with `--json` (the envelope on standard output and
  nothing on standard error). It was a usage error with exit 2. The code is added by addition only; the classifier maps
  `EmptyRefreshTargetError` to it. Detail: [design H.29](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h29-an-empty-watchlist-is-a-refresh-failure-2026-10-06).
- **Every other usage error and the declined confirmation of `watchlist delete` stay as they are.** The design's §13.3
  states exactly which rejected option values are `invalid_parameter` today and which remain exit-2 usage errors.

Resulting output change, in addition to [B.10](#b10-swc4a-momentum-window-failure-2026-10-06):

| Command | Before | After |
| :--- | :--- | :--- |
| `refresh` of a watchlist with no entries | Usage error on standard error, exit 2, with or without `--json` | `watchlist_empty`: envelope on standard output (`--json`) or the sentence on standard error, exit 1 |

### B.12 SWC.4a: parser-rejected failures stay usage errors (2026-10-06)

The project owner decided, during the SWC.4a review:

- **A failure the parser rejects before a command runs remains an exit-2 usage error in plain text, including under
  `--json`.** This covers what Typer and Click reject while parsing the command line: an unknown option, a value of the wrong
  type, a missing argument, a value outside a declared choice. No command code has run, so there is no failure to classify
  and no envelope. This is decided, not open.
- **Validation failures that a command raises itself are a separate question,** which is not decided. They are a check the
  command's own code makes after parsing and raises as `typer.BadParameter`, for example the Graham and FCF parameter checks,
  which exit 2 as text, against Momentum's window check, which reports `invalid_parameter` with exit 1. The new slice SWC.4d
  owns that question ([SWC.4d](#swc4d--command-validation-failures-and-the-failure-envelope)). Until it runs, no behavior changes.
