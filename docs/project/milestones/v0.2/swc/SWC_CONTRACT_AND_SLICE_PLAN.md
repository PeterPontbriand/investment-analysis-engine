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
  strategy's identity, versions and typed behavior (handler, evidence codec,
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
| SWC.4c | [Typed strategy envelopes and replay dispatch](#swc4c--typed-strategy-envelopes-and-replay-dispatch) | Complete | 2026-10-07 |
| SWC.4c.1 | [Common header and tail for strategy documents](#swc4c1--common-header-and-tail-for-strategy-documents) | Complete | 2026-10-09 |
| SWC.4d | [Command validation failures and the failure envelope](#swc4d--command-validation-failures-and-the-failure-envelope) | Complete | 2026-10-11 |
| SWC.4e | [The direct Graham commands reject an unsupported provider](#swc4e--the-direct-graham-commands-reject-an-unsupported-provider) | Complete | 2026-10-12 |
| SWC.4f | [One failure message rule for the direct commands and refresh](#swc4f--one-failure-message-rule-for-the-direct-commands-and-refresh) | Complete | 2026-10-12 |
| SWC.5a | [Site data, report-mode checks and the status command](#swc5a--site-data-report-mode-checks-and-the-status-command) | Complete | 2026-10-17 |
| SWC.5b | [Generated strategy lists and the user-guide moves](#swc5b--generated-strategy-lists-and-the-user-guide-moves) | Complete | 2026-10-17 |
| SWC.6 | [Specimen strategy and generator](#swc6--specimen-strategy-and-generator) | Next | |
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
  this allowance for tool handlers, native-status functions and replay projectors in the
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
| Persisted selection and workspace execution | The CLI alias vocabulary, selection building and decoding, and method/config/result-schema/codec version metadata where currently duplicated across execution and codec tables. The refresh executor and selection builder are CLI-tier members and fail closed. | Each persisted selection/config model and conversion, in its own `<strategy>_selection.py`; the `AnalysisSelection` and `NativeEvidence` unions (one file); analyzer invocation, capture shape, and outcome classification. Adapters remain strategy-owned. |
| Evidence encoding and decoding | Result/capture type-to-codec dispatch and repeated expected version metadata derive from injected codecs and version fields. | Each strategy's encode/decode implementation, validation rules, evidence shape, ticker checks, and provenance semantics remain owned by its codec and result type. |
| Reporting, replay, and JSON output | The `(analysis_id, method_id)` route and any genuinely duplicated dispatch key, including the identifier literals in the JSON builders and `execution_errors` calls, derive from the strategy's identity leaf and the descriptor. The injected projector mapping is keyed by that identity and fails closed. Schema generation enumerates the typed strategy envelope models and the failure envelope. | Versioned projection behavior (each projector in `<strategy>_replay.py`), presentation wording, rendering, typed envelope shape, strategy result unions, and historical replay semantics remain strategy-specific and explicit. The failure envelope is one shared shape, not a descriptor field. `projection_version` remains distinct from method and result-schema versions. |
| Fixture-backed evaluation composition and direct CLI commands | Fixture composition and requirement are evaluation-tier members; each direct command is a CLI-tier member that `cli.py` adds by iterating the tier. The strategy lists in `USAGE.md` and `WORKSPACE.md` are generated from the descriptors. | Fixture values, expected outcomes, scoring, case truth, the catalog's case tuple and suite version, direct CLI command semantics, and any explicit user-facing boundary remain as they are. Momentum's profile composition in `investment_analysis_engine/cli.py` and `investment_analysis_engine/cli_workspace.py` is reduced to a single implementation by SWC.3a. |

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
  `investment_analysis_engine/workspace/__init__.py` re-exports names no module imports from the package and, once `requests.py`
  imports descriptor machinery, creates an initialization cycle ([design §4](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#4-static-declaration-model)); it is emptied here, with the layering test that counts parent packages.
- **Decision:** one package per strategy, `investment_analysis_engine/strategies/<strategy>/`, with each file named for its role,
  shared code in `investment_analysis_engine/strategies/_shared/` and the Graham family package `investment_analysis_engine/strategies/_graham/`, and every
  `__init__.py` under `investment_analysis_engine/strategies/` empty. A role-based layering test (T13) replaces the folder rule.
  Every later slice creates its files in their final place. The layout and the rule are in the
  [SWC.1 design §4](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#4-static-declaration-model); the evidence is in
  [Appendix C.6](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#c6-one-package-per-strategy).
- **Scope:** `git mv` of the 13 analyzer files from `investment_analysis_engine/analysis/strategy/<package>/` (Momentum's
  `momentum_analyzer.py` becomes `analyzer.py`; the `fcf_earnings_growth` package becomes `fcf_growth`), the
  four codecs, four adapters and four presenters, and `investment_analysis_engine/workspace/graham_shared.py` to
  `investment_analysis_engine/strategies/_shared/profile.py`; removal of `investment_analysis_engine/analysis/strategy/` and its five `__init__.py` files
  (three of them re-exporting), replaced by empty ones under `investment_analysis_engine/strategies/`; emptying
  `investment_analysis_engine/workspace/__init__.py`; the 101 importer files (33 in `investment_analysis_engine`, 68 in `tests`, among them 15 tests whose patch
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
  descriptor in a cycle: `ToolName` in `investment_analysis_engine/evaluation/models.py` (and exported from `investment_analysis_engine.evaluation`),
  the argument models and their shared base in `investment_analysis_engine/orchestrator/analysis_tools.py`, the selection classes
  and `AnalysisSelection` in `investment_analysis_engine/workspace/requests.py`, and `NativeEvidence` in
  `investment_analysis_engine/workspace/execution.py`. `AnalysisType` in `investment_analysis_engine/core/constants.py` is a per-strategy name list with
  no reader.
- **Decision:** move each symbol to its final home with one import path and no compatibility re-export;
  delete `AnalysisType`. No behavior change, no descriptor.
- **Scope:** new `investment_analysis_engine/orchestrator/tool_names.py`, `investment_analysis_engine/orchestrator/analysis_tool_arguments.py` (the shared
  base renamed `AnalysisToolArguments`, `FiniteFloat`, `PositiveFiniteFloat`), `investment_analysis_engine/strategies/<strategy>/tool.py`
  (arguments model only, four files; Momentum's `_MOMENTUM_DEFAULTS` goes with its model),
  `investment_analysis_engine/workspace/selection_base.py` (the shared selection base, public as `FrozenSelection`, and the two
  CLI provider tuples both Graham selections read, public as `CLI_SECURITY_PROVIDERS` and `CLI_QUOTE_PROVIDERS`),
  `investment_analysis_engine/strategies/<strategy>/selection.py` (four files; `FCFPolicySnapshot` goes with `FCFGrowthSelection`) and
  `investment_analysis_engine/workspace/strategy_types.py` (`NativeEvidence`, `SelectionMember`, `AnalysisSelection`);
  `investment_analysis_engine/orchestrator/analysis_tools.py`, `investment_analysis_engine/workspace/{requests,execution}.py` (`AnalysisRequest`,
  `parse_selection` and its JSON helpers were deleted 2026-10-08, [B.13](#b13-one-dispatch-path-per-job-2026-10-08));
  `investment_analysis_engine/evaluation/{__init__,models,composition,runner,ollama_runner,evaluator,catalog}.py` (the
  `investment_analysis_engine.evaluation` export of `ToolName` is removed); the six `investment_analysis_engine/evaluation/cases/*.py` importers;
  `investment_analysis_engine/core/constants.py`; every test that imports a moved symbol; and `docs/EVALUATIONS.md` and
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
- **Scope:** new `investment_analysis_engine/strategy_wiring.py`, `investment_analysis_engine/core/strategy_errors.py`, `investment_analysis_engine/orchestrator/tool_runtime.py`,
  `scripts/strategy_conformance.py` and the conformance tests; `investment_analysis_engine/orchestrator/analysis_tools.py`
  (`AnalysisToolDependencies`, `AnalysisToolHandlers`, the `ANALYZE_*_TOOL` constants and
  `ANALYSIS_TOOL_ARGUMENT_MODELS` are deleted; registration receives the injected handler mapping);
  `investment_analysis_engine/strategies/<strategy>/tool.py` (dependency class and handler);
  `investment_analysis_engine/evaluation/{composition,runner,ollama_runner}.py`; removes its twelve T13 transition entries.
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
  closed tuple `EVALUATION_STRATEGIES` in `investment_analysis_engine/evaluation/strategy_fixtures.py` pairs each with its core
  bundle by dependency type. Fixture truth stays hand-written and reviewed. The catalog's case tuple and
  suite version stay explicit.
- **Scope:** new `investment_analysis_engine/evaluation/{strategy_fixtures,fixture_context}.py` (each fixture identifier is defined in
  the fixture module of its evidence),
  `investment_analysis_engine/strategies/<strategy>/evaluation.py` and `investment_analysis_engine/strategies/_graham/evaluation.py`;
  `investment_analysis_engine/evaluation/{composition,catalog}.py`; the case modules (each case's reviewed arguments move beside
  it); tests and T10's evaluation-tier surface; removes its eight T13 transition entries. Every case module
  becomes single-strategy and is named for its strategy package: GRN-04 and GRN-05 move from
  `graham_resolution.py` into `graham_number.py`; FPI-01, FPI-02 and FPI-04 move from `sec_edgar_fpi.py`
  into `graham_growth.py` and FPI-03 into the FCF module, which is renamed `fcf_growth.py`. T13 gains the
  clause that `investment_analysis_engine.evaluation.cases.<strategy>` may import the tool role of `investment_analysis_engine.strategies.<strategy>` and
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
- **Scope:** `investment_analysis_engine/strategy_wiring.py` (the selection, codec and version members and fields),
  `investment_analysis_engine/workspace/requests.py` (`parse_selection`, deleted 2026-10-08), `investment_analysis_engine/workspace/method_aliases.py`
  (deleted; the descriptor owns the alias vocabulary), `investment_analysis_engine/workspace/execution.py`, `investment_analysis_engine/workspace/codecs.py`,
  `investment_analysis_engine/workspace/refresh.py`, the strategy execution adapters (each gains its normalizer), `investment_analysis_engine/workspace/capture.py`
  (`ExecutionCapture`), `investment_analysis_engine/workspace/selection_base.py` (the shared `config` body rules), per-strategy
  codec modules (each gains its `ticker_of` function) and selection modules,
  `investment_analysis_engine/data/repositories/watchlists.py` (alias resolver at construction, through one helper in
  `investment_analysis_engine/cli_workspace.py`), `investment_analysis_engine/cli.py` (Momentum profile composition, the `execute` calls and the normalizer
  imports), `investment_analysis_engine/cli_workspace.py` (the repository helper, the Momentum composition copy, and the alias lookups
  that read the root's `BY_ALIAS` and `BY_METHOD_ID` now that `method_aliases.py` is gone),
  `investment_analysis_engine/reporting/analysis_runs.py` (`project_run` receives the injected codecs), the `getattr(selection, "as_of",
  None)` probe in `execute`, the evaluation tier (`investment_analysis_engine/evaluation/strategy_fixtures.py` and the four strategy
  `evaluation.py` files gain the required typed `sample_selection`, [design H.8](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h8-the-evaluation-tier-holds-a-sample-selection)),
  the root-importer list in T13, `scripts/strategy_conformance.py` (T1, T8, T11, T15 and T24), and focused tests. Replace Momentum's three
  profile-composition copies (two in `investment_analysis_engine/cli.py`'s `momentum` command, one in `investment_analysis_engine/cli_workspace.py`'s
  `_execute_momentum`) with one `compose_momentum_profile` in `investment_analysis_engine/strategies/momentum/execution.py`; detail in the
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
  refresh executor is an `isinstance` chain; both are per-strategy code in `investment_analysis_engine/cli_workspace.py`.
- **Decision:** each strategy's selection builder and refresh executor move unchanged into
  `investment_analysis_engine/strategies/<strategy>/cli.py`; the closed tuple `CLI_STRATEGIES` in `investment_analysis_engine/cli_strategy_wiring.py`
  pairs them with the core bundle by selection type, and `cli_workspace.py` looks them up. A missing key
  raises `UndeclaredStrategyError`.
- **Scope:** new `investment_analysis_engine/cli_strategy_wiring.py`, `investment_analysis_engine/cli_watchlist_flags.py` (the flag bundle every builder reads) and
  four `investment_analysis_engine/strategies/<strategy>/cli.py`; `investment_analysis_engine/cli_workspace.py` (`_parse_analysis`, the `--analysis` help,
  `_build_selection`, `_refresh_executor`, the four `_execute_*` and their option converters);
  `scripts/strategy_conformance.py`; tests and T10's CLI-tier surface, including the patch strings in
  `tests/test_cli_refresh.py` and `tests/test_workspace_integration.py` that name the moved provider
  composition; removes its four T13 transition entries. T13 also gains the rule that only listed CLI modules
  import the CLI tier (`investment_analysis_engine.cli_workspace` in SWC.3b and `investment_analysis_engine.cli` in SWC.3c), with the tier's entry in the root-importer
  list, a staleness check and a negative test.
- **Branch:** `feat/swc-3b-cli-tier`, from `main` after SWC.3a has merged.
- **Detail:** [SWC.1 design §3.3, §6 and §11](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#33-behavior-members-and-the-two-tiers)
  and [Appendix H.9 to H.13](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h9-the-cli-tiers-shape-and-lookups).

#### SWC.3c — Direct commands

- **Problem:** the four direct commands and their helpers are per-strategy code in `investment_analysis_engine/cli.py`, which
  registers each with `@app.command`.
- **Decision:** each command moves into its strategy's CLI file as a plain function; `cli.py` adds the
  commands by iterating `CLI_STRATEGIES` through `add_strategy_commands`. A strategy file never registers
  itself. `_maybe_save_run` and `get_cli_run_context` move to `investment_analysis_engine/cli_run_support.py`.
- **Scope:** `investment_analysis_engine/cli.py`, new `investment_analysis_engine/cli_run_support.py`, the four `investment_analysis_engine/strategies/<strategy>/cli.py`, the
  thirteen test modules that patch `investment_analysis_engine.cli.` names (76 patch strings, retargeted), T7 and T22; removes its eight T13 transition entries.
  The new `command` member of the CLI tier and `add_strategy_commands` also change `investment_analysis_engine/cli_strategy_wiring.py`,
  `scripts/strategy_conformance.py` (T7, T14, T15, T22) and `tests/test_cli_strategy_wiring.py`; the
  help-output pin adds `tests/_cli_help_output.py`, `tests/test_cli_help_output.py` and
  `tests/expected_output/cli_help/`; T22 adds `tests/test_save_run_every_direct_command.py` and a provider
  helper in `tests/_direct_command_output.py`; the layering and conformance tests are updated; and the
  docstrings and two guides that named `investment_analysis_engine/cli.py` for moved code are corrected
  ([design H.15 to H.22](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h15-the-command-member-and-add_strategy_commands)).
  Removes `investment_analysis_engine/cli.py`'s copies of the three FCF option converters (`_historical_horizon`, `_forward_policy`,
  `_fcf_classification_basis`), which are the same code as the ones SWC.3b moved to `investment_analysis_engine/strategies/fcf_growth/cli.py`,
  and moves its Momentum window check (`_validate_momentum_windows`, which exits with code 2 and so differs from the
  builder's `BadParameter` check) into `investment_analysis_engine/strategies/momentum/cli.py`.
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
- **Scope:** `investment_analysis_engine/reporting/documents/{__init__,failure,database}.py`, `investment_analysis_engine/reporting/failure_classification.py` (since moved to `investment_analysis_engine/core`, PH.2d),
  `investment_analysis_engine/cli_support.py`, `investment_analysis_engine/reporting/presentation.py`, the `execution_errors` call sites in the strategy
  command files (the Momentum file also holds the window check), `investment_analysis_engine/cli_workspace.py` (`--json`-aware failures),
  `investment_analysis_engine/cli_database.py`, `investment_analysis_engine/workspace/refresh.py` (injected classifier and per-job code), one
  `WatchlistNotFoundError` in `investment_analysis_engine/workspace/watchlists.py` and its two importers
  (`investment_analysis_engine/data/repositories/watchlists.py`, `investment_analysis_engine/workspace/refresh.py`), `AnalysisConfigurationError` moved to the
  classifier module (since moved to `investment_analysis_engine/core/operator_errors.py`, PH.2d) with its two importers (`investment_analysis_engine/cli_composition.py`, `investment_analysis_engine/cli_health.py`),
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
- **Scope:** `investment_analysis_engine/reporting/documents/{timestamp,watchlist,runs,refresh}.py` (`timestamp.py` is the one instant type every
  document model uses), the JSON builders in `investment_analysis_engine/cli_workspace.py`, four schemas and their entries in
  `scripts/generate_schemas.py`, tests and the stored workspace scenario (`tests/_workspace_command_output.py` and
  `tests/expected_output/workspace_commands/`), and `docs/user/WORKSPACE.md`. Two output changes, listed in
  [design §13.4](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#134-what-changes) rows 6 and 7: `runs list` `completed_at` and a watchlist
  selection's `as_of` are written `+00:00`, not `Z`.
- **Known at SWC.4a:** the `refresh --json` document has no `schema_version`, so SWC.4a's new `reason_code` key on
  each result bumped no version ([design H.27](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h27-output-changes-and-the-check-that-success-output-is-unchanged-2026-10-06)).
  SWC.4b publishes the refresh summary schema and states, in the schema and the design, that the document is unversioned
  or what version it carries; adding a version is an output change it lists. (PH.2e later gave the refresh summary
  `schema_version` 1.)
- **Branch:** `feat/swc-4b-workspace-documents`, from `main` after SWC.4a has merged.
- **Detail:** [SWC.1 design §13.6](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#136-every-json-document-is-typed).

#### SWC.4c — Typed strategy envelopes and replay dispatch

- **Problem:** report construction and stored-run replay retain per-method type dispatch, and the four
  strategy documents lack the typed envelope models IR.5 intended to add.
- **Decision:** typed envelope models back the real builders and are validated at the output boundary; the
  vocabulary files hold each strategy's identity constants, which presenters and the descriptor
  read ([design H.32](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h32-one-vocabulary-file-per-strategy-2026-10-07)); the descriptor gains `json_envelope` and the `project` member; `project_run` receives the
  injected projector mapping and fails closed; the command-coverage test lands last, with no exemption list.
- **Scope:** `investment_analysis_engine/strategy_wiring.py`, `investment_analysis_engine/strategies/<strategy>/envelope.py`, `replay.py` and, by [design H.32](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h32-one-vocabulary-file-per-strategy-2026-10-07), `vocabulary.py` (identity, the stored-configuration version and shared enumerations; the four
  projectors leave `analysis_runs.py`; each `replay.py` also holds the strategy's `headline` function only
  from Step 3.5 slice 3.5.0), `investment_analysis_engine/strategies/_graham/replay.py`, `investment_analysis_engine/reporting/replay_inputs.py`
  (`ReplayOptions` and `UnsupportedProjectionError` move here), `investment_analysis_engine/reporting/json_documents.py` (the
  failure, workspace and database documents; the generator and tests add each descriptor's `json_envelope`
  from the root), `investment_analysis_engine/reporting/analysis_runs.py`, the four `presenter.py` files, four schemas, and tests
  T8 (replay), T10, T20, T21 and T24 extended; removes its four T13 transition entries. Also in scope, as
  [design H.31](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h31-typed-strategy-documents-and-replay-dispatch-2026-10-07)
  records: `investment_analysis_engine/reporting/documents/shared_parts.py` (the parts several strategy documents share),
  `scripts/generate_schemas.py` and `scripts/strategy_conformance.py`, the one-line import retargets in
  `investment_analysis_engine/cli_workspace.py` and `investment_analysis_engine/reporting/failure_classification.py` (since moved to `investment_analysis_engine/core`, PH.2d), the stored strategy-document output in
  `tests/expected_output/strategy_documents/` and its harness (captured from the hand-written builders before any
  builder changed), `docs/user/USAGE.md` and `docs/user/WORKSPACE.md`, and one line in the Step 3.5 plan's
  repetition checkpoint.
- **Branch:** `feat/swc-4c-strategy-json-envelopes`, from `main` after SWC.4b has merged.
- **Detail:** [SWC.1 design §6, §10 and §13.6](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#10-conformance-tests-and-negative-control),
  [inventory disposition](#4-inventory-disposition) and
  [audited inventory](#appendix-a-proposal-inventory-verified-against-main).

#### SWC.4c.1 — Common header and tail for strategy documents

- **Problem:** the four strategy documents named the same facts differently and in different places (`as_of` meant a
  request in one and a data date in another; `status` was a verdict in Momentum and a calculation status elsewhere;
  FCF Growth wrapped its diagnostics and had no `limitations`), so a key added to all four had to be added four times.
- **Decision:** every strategy document begins with one header and ends with one tail, each declared once in
  `investment_analysis_engine/reporting/documents/strategy_document.py` and composed into the strategy's body by inheritance
  ([design H.34](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h34-common-header-and-tail-for-strategy-documents-2026-10-09)).
  A conformance test iterates every descriptor's `json_envelope` and fails for a document that does not take them. The
  Graham evidence now carries the instant the analysis was evaluated at, so `effective_as_of` is a true value in all
  four. The failure envelope and the text output are unchanged. Landed before PH.2c, which adds `provider_failure` to
  the header, and before Step 3.5.
- **Scope:** `investment_analysis_engine/reporting/documents/strategy_document.py`; the four `envelope.py` and `presenter.py` files; the
  Momentum and Graham `replay.py` and `cli.py` files; Graham's `service.py`, `analyzer.py` and `codec.py`;
  `investment_analysis_engine/strategy_wiring.py` (the Graham `result_schema_version` and `evidence_codec_version`); four schemas; the stored
  output under `tests/expected_output/`; the affected tests; `docs/user/USAGE.md`, `docs/user/SMOKE_TESTING.md` and the
  plans that name these keys.
- **Branch:** `feat/strategy-document-common-header`, from `main` after SWC.4c.
- **Detail:** [design H.34](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h34-common-header-and-tail-for-strategy-documents-2026-10-09).

#### SWC.4d — Command validation failures and the failure envelope

- **Problem:** a validation failure that a command raises itself reaches the caller in one of two ways. Momentum's window
  check is an `invalid_parameter` failure through the envelope with exit 1 ([B.10](#b10-swc4a-momentum-window-failure-2026-10-06)),
  while the Graham and FCF parameter checks, and the other checks raised as `typer.BadParameter`, exit 2 as plain text, even
  under `--json`.
- **Decision:** every check a command raises itself moves into the failure envelope ([B.14](#b14-swc4d-command-validation-failures-2026-10-11)):
  - the strategy option checks, the shared ones (ticker, `--as-of`, `--data-provider`, the exclusive output flags), the workspace
    ones, and those on `health`, `database` and `evaluate`;
  - each reports `invalid_parameter` with exit 1; exit 2 keeps one meaning, that the parser rejected the command line and no command
    code ran ([B.12](#b12-swc4a-parser-rejected-failures-stay-usage-errors-2026-10-06)), so no check becomes a parser constraint and no
    parser error is intercepted;
  - a command with no `--json` writes the sentence to standard error and exits 1, and no command gains `--json`;
  - each sentence is kept except where it must be reworded to keep an option name that Typer's usage output carried, and every
    sentence names its option or argument;
  - a caught `ValueError` from the workspace layer is audited per site: a real check becomes an explicit check, and anything else that
    declares no code of its own reports as `execution_error` with `<command> failed unexpectedly.` ([B.16](#b16-swc4d-follow-up-the-workspace-catch-all-runs-show-and-refresh-2026-10-12));
  - the failure envelope gains `parameters`, the offending option or argument names, and its `schema_version` is bumped;
  - a test fails if any file under `investment_analysis_engine/` raises `typer.BadParameter`.
- **Scope:** set by the [SWC.4d plan](SWC_4D_COMMAND_VALIDATION_FAILURES_PLAN.md#e-file-scope-tests-and-documents-for-step-2).
- **Branch:** `feat/swc-4d-command-validation-failures`, from `main` after SWC.4c has merged. Two steps on the branch: the plan, then
  the implementation.
- **Detail:** [SWC.4d plan](SWC_4D_COMMAND_VALIDATION_FAILURES_PLAN.md).

#### SWC.4e — The direct Graham commands reject an unsupported provider

- **Problem:** the direct `graham-number` and `graham-growth` commands accept any provider id in their configuration so tests can
  inject a synthetic one. An unsupported `--data-provider` is therefore `configuration_error` on those commands (from
  `build_graham_resolver`) and `invalid_parameter` on `watchlist create` and `watchlist add-selection` (from the strict selection).
- **Decision:** remove the seam ([B.15](#b15-swc4e-the-direct-graham-commands-reject-an-unsupported-provider-2026-10-11)). The direct
  commands reject an unsupported provider with the builders' check, sentence and code. Tests pass `sec_edgar` with the resolver
  replaced, and the stored direct-command output is re-captured. The re-capture also changed the EPS basis, from TTM to the
  three-year average, because the default basis follows the provider id (approved by the project owner; recorded in B.15).
- **Scope:** the Graham direct-command configuration and its command files, and the tests listed in B.15.
- **Branch:** `feat/swc-4e-direct-graham-provider`, from `main` after SWC.4d has merged.
- **Detail:** no separate slice plan; the comparison, the output changes and the test changes are in
  [B.15](#b15-swc4e-the-direct-graham-commands-reject-an-unsupported-provider-2026-10-11).

#### SWC.4f — One failure message rule for the direct commands and refresh

- **Problem:** a failed refresh job reports the exception's own text (`RefreshJobResult.error`), while the same failure on a direct
  command reports a message written for it, and the direct commands' messages differ by strategy. Refresh can therefore show raw
  validation text or text from provider data.
- **Decision:** the failure code chooses the message, in one function in `investment_analysis_engine/cli_support.py` that the direct commands and the refresh
  job both use; no strategy declares wording and no message names the strategy
  ([B.17](#b17-swc4f-one-failure-message-rule-for-the-direct-commands-and-refresh-2026-10-12)).
- **Scope:** `investment_analysis_engine/cli_support.py`, the four strategy `cli.py` files, `investment_analysis_engine/cli_workspace.py`, `investment_analysis_engine/workspace/refresh.py`, the declaration
  of `AnalysisRunConflictError`, the `error` description of the `refresh --json` document and its schema, their tests, the stored
  output, and the user documents that show these messages; the exact list is in B.17 section D.
- **Branch:** `feat/swc-4f-failure-sentences`, from `main` after SWC.4e has merged.
- **Detail:** no separate slice plan; the failure table, the design and the file list are in
  [B.17](#b17-swc4f-one-failure-message-rule-for-the-direct-commands-and-refresh-2026-10-12).

### SWC.5a — Site data, report-mode checks and the status command

- **Problem:** a contributor learns what is missing from a strategy only by running tests, and the edit-site
  list is maintained by hand in two places.
- **Decision:** one data file lists the edit sites and feeds the guide's table; a developer script reports
  each site done or missing by running the conformance suite's site checks, so it cannot disagree with them.
  Only per-strategy site checks need a site; the suite-wide rules keep their form
  ([B.18](#b18-swc5-split-and-the-site-check-decisions-2026-10-17)).
- **Scope:**
  - New `scripts/strategy_sites.toml`, `scripts/strategy_sites.py`, `scripts/strategy_status.py` and
    `scripts/generate_strategy_docs.py`, with tests under `tests/scripts/` and T25.
  - `scripts/strategy_conformance.py` gains the site checks, each taking a strategy's names and returning
    `Gap` records.
  - `docs/project/ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md` gains the generated edit-site table and one sentence
    on the status command.
- **Branch:** `feat/swc-5a-site-data-and-status`, from `main`.
- **Order:** started after PKG.2 and PKG.3 had merged, so the import paths it writes are the final ones.
  [B.16](#b16-swc4d-follow-up-the-workspace-catch-all-runs-show-and-refresh-2026-10-12) recorded the earlier order.
- **Detail:** [SWC.1 design §19.1, §19.2 and §10](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#19-contributor-tooling);
  decisions and implementation record in [B.18](#b18-swc5-split-and-the-site-check-decisions-2026-10-17).

### SWC.5b — Generated strategy lists and the user-guide moves

- **Problem:** the strategy lists in `USAGE.md` and `WORKSPACE.md` are hand-written, the watchlist option
  prose lives outside the strategy guides, and the FCF Growth guide's file name does not follow the alias.
- **Decision:** the two pages' strategy lists are generated from the descriptors by the generator that SWC.5a
  created, and drift-tested.
- **Scope:** marked blocks in `docs/user/USAGE.md` and `docs/user/WORKSPACE.md`, added to
  `scripts/generate_strategy_docs.py`; the strategy-docs command site and its check; the watchlist option
  table moved into the strategy guides; `docs/user/strategies/FCF_EARNINGS_GROWTH.md` renamed `FCF_GROWTH.md`
  with its links, and the temporary guide-name exception in `scripts/strategy_sites.py` removed; test T26.
- **Branch:** `feat/swc-5b-generated-strategy-lists`, from `main` after SWC.5a has merged.
- **Detail:** [SWC.1 design §10 and §19.1](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#19-contributor-tooling).

### SWC.6 — Specimen strategy and generator

- **Problem:** the dispatchers and both tiers can only be exercised through the four production
  strategies, and adding a strategy is a long manual sequence.
- **Decision:** a checked-in specimen strategy, used only by tests, is wired through every layer; a
  generator writes the typed stubs and the five mechanical one-line edits, refusing to overwrite; a test
  runs the generator in a temporary copy, fills the stubs with trivial bodies, and requires the strict type
  check and the conformance suite to pass. `AGENTS.md` §3 gains one narrow exception for generator output
  that fails the gate by design.
- **Scope:** new `tests/specimen/`, `scripts/new_strategy.py`, `scripts/strategy_templates/`,
  `investment_analysis_engine/core/strategy_stub.py`, `tests/scripts/generator_fills/`, tests T27 to T29 and the negative control
  re-based on the specimen; `AGENTS.md` §3. A strategy that declares settings gets a `settings.toml` beside its
  `settings.py`, and the generator writes it.
- **Branch:** `feat/swc-6-specimen-and-generator`, from `main` after SWC.5b has merged.
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
  - **Strategy settings.** The guide's strategy-addition workflow includes the strategy settings convention
    ([LAY_7_STRATEGY_SETTINGS_PLAN.md §3](../layering/LAY_7_STRATEGY_SETTINGS_PLAN.md#3-the-convention)): when a
    strategy gets a settings file, its typed model, its descriptor field and the four entry points.
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
- **Layering:** every file a strategy owns, except its fixtures and cases, is in `investment_analysis_engine/strategies/<strategy>/`,
  named for its role, and every `__init__.py` under `investment_analysis_engine/strategies/` is empty. The role rule holds and T13
  enforces it: within a strategy only a higher-ranked role file imports a lower one; no strategy imports
  another; foundation, reporting and the other generic modules import only analyzer and selection roles and
  never the composition root, a tier or a strategy's CLI or evaluation file; no module under `investment_analysis_engine` imports
  `tests`. The layering test counts parent-package initialization, and `investment_analysis_engine/workspace/__init__.py` is empty.
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
- **Edit sites:** adding a strategy takes the 20 sites in the design's edit-site table, in 25 files across 9
  directories, nine of them existing files; five of those are edited by the generator, and the other four (the catalog,
  its test, and the two watchlist-option files of site 19, edited only by a strategy with options of its own) are
  reviewed.
- **Contributor tooling:** one site data file is the source of the guide's table, the status command, the
  generator and the specimen's completeness test; the status command and the conformance tests share their
  check bodies; the generator writes wiring only and refuses to overwrite; a test runs it in a temporary
  copy and requires the strict type check and the conformance suite to pass with trivially filled stubs;
  the specimen strategy runs through every layer and cannot reach production tuples, the user CLI or the
  published schemas; the quality gate fails while any `unfilled_stub` call remains in `investment_analysis_engine/`.
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
| Per-strategy `*ToolArguments` Pydantic models | Still present | `investment_analysis_engine/orchestrator/analysis_tools.py`: `MomentumToolArguments`, `GrahamNumberToolArguments`, `GrahamGrowthValueToolArguments`, `FCFEarningsGrowthToolArguments` | One strict model per strategy; shared `_AnalysisToolArguments` base. |
| Per-strategy `ANALYZE_*_TOOL` constants | Still present | `investment_analysis_engine/orchestrator/analysis_tools.py`: four `ANALYZE_*_TOOL` constants | Each method still has its own name constant. |
| `ANALYSIS_TOOL_ARGUMENT_MODELS` entries | Still present | `investment_analysis_engine/orchestrator/analysis_tools.py`: `ANALYSIS_TOOL_ARGUMENT_MODELS` | Mapping remains consumed by the local Ollama runner. |
| Flat strategy-specific dependency fields | Changed | `investment_analysis_engine/orchestrator/analysis_tools.py`: `AnalysisToolDependencies` | Still strategy-specific analyzer/provider fields, but IR.2 standardized invocation and injected context; `profile_resolver` is shared/optional. |
| Per-strategy handler methods | Still present | `investment_analysis_engine/orchestrator/analysis_tools.py`: `AnalysisToolHandlers.analyze_momentum`, `.analyze_graham_number`, `.analyze_graham_growth_value`, `.analyze_fcf_earnings_growth` | All validate strategy arguments, build owned config and invoke the shared analyzer envelope. |
| Per-strategy registration calls | Still present | `investment_analysis_engine/orchestrator/analysis_tools.py`: `register_analysis_tools` | Four explicit `register_tool` calls remain. |
| Per-strategy persisted selection models | Still present | `investment_analysis_engine/workspace/requests.py`: `MomentumSelection`, `GrahamNumberSelection`, `GrahamGrowthSelection`, `FCFGrowthSelection` | Strategy-specific config persistence remains; shared base is `_FrozenSelection`. |
| `AnalysisSelection` discriminated union | Still present | `investment_analysis_engine/workspace/requests.py`: `AnalysisSelection` | Union has four strategy members and remains the request/watchlist/run boundary. |
| Per-selection `to_*_config()` methods | Still present | `investment_analysis_engine/workspace/requests.py`: `to_momentum_config`, `to_graham_number_config`, `to_graham_growth_config`, `to_fcf_config` | Each typed selection converts to its own analyzer config. |
| One workspace execution adapter per strategy | Still present | `investment_analysis_engine/strategies/momentum/execution.py`: `MomentumCapture`, `run_momentum`; `graham_number_execution.py`: `GrahamNumberCapture`, `execute_graham_number`; `graham_growth_execution.py`: `GrahamGrowthCapture`, `execute_graham_growth`; `fcf_growth_execution.py`: `FCFGrowthCapture`, `execute_fcf_growth` | Files also retain strategy-specific outcome classification where applicable. Momentum has no native failure status classifier. |
| `NativeEvidence` result union | Still present | `investment_analysis_engine/workspace/execution.py`: `NativeEvidence` | Four heterogeneous native results remain explicitly unioned. |
| Per-strategy capture normalizers | Still present | `investment_analysis_engine/workspace/execution.py`: `from_momentum_capture`, `from_graham_number_capture`, `from_graham_growth_capture`, `from_fcf_growth_capture` | Still normalize strategy capture fields into `ExecutionCapture`. |
| `_METHOD_VERSIONS` metadata | Still present | `investment_analysis_engine/workspace/execution.py`: `_METHOD_VERSIONS` | One pair per method; IR changed persisted envelope versions and added `config_schema_version` alignment. |
| Refresh `isinstance` dispatch | Changed | `investment_analysis_engine/cli_workspace.py`: `_refresh_executor` | Still four explicit selection branches; current function is at a different location and composes per-method adapters. |
| `encode_evidence` isinstance chain | Changed | `investment_analysis_engine/workspace/codecs.py`: `encode_evidence` | FCF/Graham branches remain; Momentum is now the unconditional fallback rather than an explicit final branch, so unknown evidence is routed as Momentum. This is the live fall-through. |
| Decoder version membership and expected versions | Changed | `investment_analysis_engine/workspace/codecs.py`: `_EXPECTED_VERSIONS`, `decode_evidence` | Now one mapping entry stores `(config_schema_version, method_version, result_schema_version)`; `decode_evidence` validates run-schema, codec and projection versions too. |
| Per-method `decode_evidence` dispatch | Changed | `investment_analysis_engine/workspace/codecs.py`: `decode_evidence` | Explicit branches remain for FCF, Graham Growth and Graham Number, with Momentum as the final branch; ticker identity is checked per result shape. An undeclared pair is already rejected earlier by the version-table lookup, so only the structure, not the behavior, is a default branch. |
| Momentum instrument-profile composition | Still present | `investment_analysis_engine/cli.py`: `momentum` command (`--save-run` and default branches); `investment_analysis_engine/cli_workspace.py`: `_execute_momentum` | Three independent inline copies of one composition pattern; Graham and FCF Growth already share `compose_graham_profile`. Owned by SWC.3a ([Momentum profile composition note](MOMENTUM_PROFILE_COMPOSITION_DEDUPLICATION.md)). |
| Per-strategy evidence codec modules | Still present | `investment_analysis_engine/workspace/momentum.py`, `graham_number.py`, `graham_growth.py`, `fcf_growth.py`: `encode_*`, `decode_*` | One pair remains per strategy. |
| Per-strategy report construction functions | Changed | `investment_analysis_engine/reporting/analysis_runs.py`: `_project_momentum_v1`, `_project_graham_number_v1`, `_project_graham_growth_v1`, `_project_fcf_growth_v1` | Projection is now explicit versioned replay over persisted Analysis Runs, decodes stored evidence and retains type assertions; original line references no longer apply. |
| Strategy presentation modules | Still present | `investment_analysis_engine/reporting/momentum.py`, `graham_number.py`, `graham_growth.py`, `fcf_earnings_growth.py` | Each retains method-specific presentation and rendering. |
| `ToolName` enum | Still present | `investment_analysis_engine/evaluation/models.py`: `ToolName` | One enum member per tool remains. |
| Evaluation `AnalysisToolArguments` union | Still present | `investment_analysis_engine/evaluation/composition.py`: `AnalysisToolArguments` | Four model union remains for typed fixture dispatch. |
| Fixture dependency composition per strategy | Still present | `investment_analysis_engine/evaluation/composition.py`: `compose_fixture_dependencies` | Independently builds Momentum, Graham Number, Graham Growth and FCF analyzers/resolvers and assembles `AnalysisToolDependencies`. |
| Evaluation `_tool_name` isinstance dispatch | Still present | `investment_analysis_engine/evaluation/composition.py`: `_tool_name`; also `investment_analysis_engine/evaluation/runner.py` and `investment_analysis_engine/evaluation/ollama_runner.py`: `_tool_name` | Current main repeats argument-type mapping in three modules, not only the single location listed in the proposal. |

The proposal's prose also mentions one CLI command per strategy but does not inventory it as a
separate row. Direct command wiring remains in `investment_analysis_engine/cli.py`: `momentum`, `graham_number`,
`graham_growth` and `fcf_growth`; workspace job composition remains in `investment_analysis_engine/cli_workspace.py`:
`_execute_momentum`, `_execute_graham_number`, `_execute_graham_growth`, `_execute_fcf_growth` and
`_refresh_executor`. The proposal is therefore a useful starting inventory, not a complete list of
all current consumer surfaces. Any consolidated dispatch must also account for
`investment_analysis_engine/reporting/analysis_runs.py`'s `project_run` `(analysis_id, method_id)` replay selection and the
repeated evaluation `_tool_name` mappings above.

The `encode_evidence` and `parse_selection` rows describe the code as it stood before SWC.3a; neither function exists any
more, and production never called either after SWC.3a ([B.13](#b13-one-dispatch-path-per-job-2026-10-08)).

SWC.1's re-verification found further per-strategy sites that this table does not list. Each is
classified, with its owning slice, in the [SWC.1 design](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#a2-sites-missing-from-the-plans-appendix-a):

| Additional wiring point | Current file and symbol(s) | Owner |
| :--- | :--- | :--- |
| Alias vocabulary | `investment_analysis_engine/workspace/method_aliases.py`; `investment_analysis_engine/cli_workspace.py` alias uses; `investment_analysis_engine/data/repositories/watchlists.py` alias lookup | SWC.3a (`method_aliases.py`, the repository and the `cli_workspace.py` alias lookups, which now read the root's `BY_ALIAS` and `BY_METHOD_ID`); SWC.3b (the `--analysis` help text and the CLI tier's own use of the vocabulary) |
| Alias membership and a final unconditional Momentum branch | `investment_analysis_engine/workspace/requests.py`: `parse_selection` | SWC.3a |
| Identifier literals in failure calls and JSON builders | `investment_analysis_engine/cli.py`: six `execution_errors(analysis=, method=)` calls; `investment_analysis_engine/reporting/{momentum,graham_number,graham_growth}.py` | SWC.4a (`cli.py` calls), SWC.4c (builders) |
| Strategy name tested inside generic failure handling | `investment_analysis_engine/cli_support.py`: `analysis == "momentum"` | SWC.4a |
| A second `NativeEvidence`-shaped union, and an FCF default branch | `investment_analysis_engine/evaluation/runner.py`: `NativeAnalysisResult`, `_native_result`, `_native_status` | SWC.2c |
| An FCF default branch in the fixture capability check | `investment_analysis_engine/evaluation/composition.py`: `_require_tool_evidence` | SWC.2d |
| A one-member per-strategy name enum with no reader | `investment_analysis_engine/core/constants.py`: `AnalysisType` | SWC.2b (deleted) |
| An unconditional FCF return after a chain of method tests | `investment_analysis_engine/cli_workspace.py`: `_build_selection` | SWC.3b |
| A probe for a field every selection defines | `investment_analysis_engine/workspace/execution.py`: `getattr(selection, "as_of", None)` | SWC.3a |
| Tool descriptions, schemas and parser registry keyed by tool name | `investment_analysis_engine/evaluation/ollama_runner.py`: `_TOOL_DESCRIPTIONS`, `_tool_schemas_json`, `_tool_parser` | SWC.2c |

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
- **Fix the package-initialization cycle** in SWC.2a by emptying `investment_analysis_engine/workspace/__init__.py`, and make the
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
  strategy in `investment_analysis_engine/cli_workspace.py` and carried by the new `WatchlistFlags` bundle in `investment_analysis_engine/cli_watchlist_flags.py`.
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

- **One check, one code.** A single function in `investment_analysis_engine/strategies/momentum/cli.py` raises `InvalidParameterError`,
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

### B.13 One dispatch path per job (2026-10-08)

The project owner decided, after a review of what production calls:

- **Selection parsing.** `parse_selection`, the descriptor `parse` member and `parse_for`, `parsers_by_alias`, the
  per-strategy parse functions and the JSON helpers they used are deleted. Production builds a selection from command-line
  options (the CLI tier's `build`) and reads a stored entry with `decode_selection`. Omitted-key defaulting and
  duplicate-key rejection were rules of a path production never ran and were removed with it; a repeated key in a stored
  row is still accepted, last value winning, and is left as is.
- **Evidence encoding.** `encode_evidence` and `evidence_by_type` are deleted. Production encodes through
  `run_spec_for(selection).encode`.
- **Edit sites.** Unchanged at 20 sites in 25 files; the SWC.3a scope above no longer lists a parser. Detail:
  [SWC.1 design H.33](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#h33-one-dispatch-path-per-job-2026-10-08).

### B.14 SWC.4d: command validation failures (2026-10-11)

The project owner decided, for SWC.4d (the open question of [B.12](#b12-swc4a-parser-rejected-failures-stay-usage-errors-2026-10-06)):

1. **Every check a command raises itself moves into the failure envelope in this slice:** the strategy option checks, the shared ones
   (ticker, `--as-of`, `--data-provider`, the exclusive output flags), the workspace ones, and those on `health`, `database` and `evaluate`.
2. **A test fails if any file under `investment_analysis_engine/` raises `typer.BadParameter`.**
3. **These failures exit 1 with `reason_code` `invalid_parameter`.** Exit 2 keeps one meaning: the parser rejected the command line and no
   command code ran ([B.12](#b12-swc4a-parser-rejected-failures-stay-usage-errors-2026-10-06), unchanged). No check becomes a
   parser-declared constraint, and no parser error is intercepted.
4. **A command with no `--json` writes the sentence to standard error and exits 1.** No command gains `--json` in this slice.
5. **Each existing sentence is kept.** Reword only where the option name was carried by Typer's usage output (a `param_hint`, or the usage
   box) and would otherwise be lost. Every sentence names its option or argument. A sentence reports; it does not tell the user what to do
   next unless the existing sentence already does.
6. **The places that catch any `ValueError` from the workspace layer and re-raise it as a usage error are not relabelled wholesale.** For
   each, find what it can actually catch. A real option or argument check moves into the command as an explicit check. Anything else is
   reported under the code the classifier already gives it.
7. **The failure envelope gains a `parameters` field:** the list of offending option or argument names exactly as typed on the command
   line (for example `["--short-window", "--long-window"]`), and null for every failure that is not `invalid_parameter`. Momentum's
   existing checks supply it too. The failure schema version is bumped. Nothing is migrated.
8. **The slice runs in two steps on one branch.** The first writes the [slice plan](SWC_4D_COMMAND_VALIDATION_FAILURES_PLAN.md) and stops.

Rulings on the slice plan's findings, made before step 2 (the plan's "Rulings on the findings" table holds them all):

- `parameters` holds each option's declared primary long spelling and each argument's upper-case name as the sentences use it; this
  replaces "exactly as typed" in decision 7.
- `watchlist create` checks every seed ticker before it creates the watchlist. A name that already exists together with a blank ticker
  now reports the blank ticker.
- A private-memory `db` target reports `invalid_parameter` with `["--database-url"]` when the option was supplied and
  `configuration_error` with the existing sentence when the target came from the settings.
- The direct Graham commands keep `configuration_error` for an unsupported `--data-provider` here; that moved to
  [SWC.4e](#swc4e--the-direct-graham-commands-reject-an-unsupported-provider) ([B.15](#b15-swc4e-the-direct-graham-commands-reject-an-unsupported-provider-2026-10-11)).
- `config_usage_errors` uses a strict lookup and drops pydantic's `Value error, ` prefix; exit 2 is documented as "the parser rejected
  the command line".

The plan lists every check, the audit of each caught `ValueError`, the shared reporting path and the findings for the project owner.
Resulting output changes, by command (rows are the checks of the
[plan's section A](SWC_4D_COMMAND_VALIDATION_FAILURES_PLAN.md#a-the-check-table)). "Before" is the usage box on standard error with
exit 2 and, even under `--json`, no JSON, unless stated. "After" is the sentence on standard error with exit 1 and, for a command with
`--json`, the failure envelope on standard output with nothing on standard error; `parameters` names the offending options and arguments.

| Command | Checks | After (sentence changes only where listed) |
| :--- | :--- | :--- |
| Every failure envelope | all | New key `parameters` (`null` unless `invalid_parameter`); `schema_version` 9 to 10. Momentum's window and period failures (already exit 1) gain `parameters` only. |
| `momentum` | ticker (`TICKER`/`--ticker`), `--details`/`--diagnostics`/`--json`, `--as-of`, `--save-run` | Exit 1. A blank ticker reads `TICKER must be a non-empty symbol.` or `--ticker must be a non-empty symbol.`. |
| `graham-number`, `graham-growth` | ticker, output flags, `--as-of`, `--data-provider` (blank), `--eps-basis`, the SEC basis rule | Exit 1. A blank ticker is worded as for `momentum`. A pydantic message loses its `Value error, ` prefix. Changed by [SWC.4e](SWC_CONTRACT_AND_SLICE_PLAN.md#swc4e--the-direct-graham-commands-reject-an-unsupported-provider): an unsupported `--data-provider`, a non-finite override and `--eps-basis ttm` now report the watchlist path's sentences and `invalid_parameter`. |
| `fcf-growth` | ticker, output flags, `--as-of`, `--data-provider` (blank), `--growth-years`, `--forward-policy`, `--classification-basis`, `--currency` | Exit 1. A blank ticker is worded as for `momentum`. |
| `watchlist create` | `--analysis`, seed tickers, name, every strategy option | Exit 1. A blank name reads `NAME must not be blank.` (it was a pydantic block with `input_value`). A blank seed ticker reads `TICKER must not be empty.` and is checked before the watchlist is created, so none is left behind; a name that exists together with a blank ticker now reports the blank ticker. A missing `--expected-growth` or `--aaa-yield` reads `--expected-growth is required when --analysis is graham-growth.` (and the same for `--aaa-yield`). Momentum's windows were already exit 1. |
| `watchlist add-selection` | `--analysis`, tickers, strategy options | Exit 1; wording as for `create`. A watchlist holding an unreadable entry is no longer a usage error: it reports `stored_selection_unreadable`, exit 1, with the same sentence. |
| `watchlist remove-entry`, `remove-ticker`, `remove-method` | `INDEX`, tickers, `--analysis` | Exit 1; `remove-ticker` reads `TICKER must not be empty.`. |
| `watchlist delete` | `--yes` without a terminal | Exit 1; under `--json` the envelope (nothing was written before). The `Invalid value for --yes:` prefix is gone. |
| `watchlist rename` | blank new name | Exit 1; `NEW_NAME must not be blank.`; under `--json` the envelope. |
| `watchlist show` | `--group-by` | Exit 1; under `--json` the envelope. |
| `runs list` | `--ticker`, `--analysis`, `--status`, `--refresh-id`, `--limit`, `--offset` | Exit 1; under `--json` the envelope. `--ticker` reads `--ticker must not be empty.`; `--refresh-id` reads `--refresh-id 'x' is not a valid Analysis Run ID. ...`; `--limit` and `--offset` read `--limit must be between 1 and 100.` and `--offset must be 0 or greater.` (they were pydantic blocks), and only the first failing one is reported. |
| `runs show` | output flags, `RUN_ID` | Exit 1; under `--json` the envelope. `RUN_ID 'x' is not a valid Analysis Run ID. ...`. |
| `refresh` | `--workers` | Exit 1; under `--json` the envelope; reads `--workers must be between 1 and 4.`. |
| `health` | `--provider` | Exit 1; under `--json` the envelope, not the health document; reads `Unknown --provider 'x'; valid providers are: ...`. |
| `db status`, `db upgrade` | `--database-url`, private-memory target | Exit 1; under `--json` the envelope, not a maintenance report. Reads `Select a valid local SQLite database URL for --database-url: ...` and `Database maintenance requires a file-backed target for --database-url; ...`. A private-memory target that came from the settings is `configuration_error` with the old sentence. |
| `evaluate` | `--report` (partly anchored path, existing file), `--case`, `--mode` | Exit 1, sentence only. `--case` reads `Unknown Golden case ID 'x' for --case. Available IDs: ...`; an existing report reads `--report target already exists: <path>. Use --overwrite to replace it.`. |

### B.15 SWC.4e: the direct Graham commands reject an unsupported provider (2026-10-11)

The project owner decided, when SWC.4d step 2 found the cause of the difference between the direct Graham commands and the watchlist
builders:

- **What was found.** Both support exactly one security-fact provider, `sec_edgar` (`CLI_SECURITY_PROVIDERS`; `build_graham_resolver`). The
  direct commands validate a permissive `GrahamNumberConfig` / `GrahamGrowthConfig` that accepts any provider id, by design, so tests can
  inject a synthetic one with the resolver builder patched; an unsupported id is then rejected later, as `configuration_error`. The
  builders validate the strict selection and report `invalid_parameter`.
- **SWC.4d keeps today's behavior** and does not touch the permissive configuration or the tests that use it.
- **SWC.4e removes the seam.** The direct commands reject an unsupported provider with the builders' check, sentence and code, at the
  position in the command's check order where the configuration is validated today. Tests pass `sec_edgar` with the resolver replaced.
  The stored direct-command output is re-captured; the only stored-output difference permitted is the provider id.
- **Affected, found with** `grep -rn '"--data-provider"' tests --include=*.py` and a count of the occurrences followed by the
  synthetic constant (`PROVIDER_ID`, `"fixture-synth"`, defined in `investment_analysis_engine/evaluation/fixtures/graham.py`): 19 invocation sites, all
  through the direct `graham-number` and `graham-growth` commands.

  | File | Sites using `fixture-synth` |
  | :--- | ---: |
  | `tests/test_cli.py` | 14 |
  | `tests/test_cli_graham_commands.py` | 2 (one is parametrized over both commands and the output modes) |
  | `tests/test_cli_graham_nonpositive_growth.py` | 1 |
  | `tests/_direct_command_output.py` | 2 (the stored-output harness) |

  Stored output carrying the id: `tests/expected_output/direct_commands/graham-number.json`, `graham-number.txt`,
  `graham-growth.json`, `graham-growth.txt`. Other `--data-provider` values in tests are `sec_edgar` (including `" SEC_EDGAR "`),
  `not-a-provider` (`tests/test_cli.py`, expects the unsupported-provider failure) and `unapproved` (`fcf-growth`, which never rejects
  a provider id).

#### B.15 implementation record (2026-10-12)

The project owner approved the slice's work and, when the re-capture changed more than the provider id, approved the full re-capture to
the three-year-average result. No separate slice plan was written.

**Field-by-field comparison** of `GrahamNumberConfig` / `GrahamGrowthConfig` (before) with `GrahamNumberSelection` /
`GrahamGrowthSelection` (after), for every input the command line supplies:

| Input | Configuration | Selection | Difference |
| :--- | :--- | :--- | :--- |
| `--data-provider` | trimmed, lower-cased, not blank; any id accepted | the same, then restricted to `CLI_SECURITY_PROVIDERS` (`sec_edgar`) | **1.** The provider id. |
| `--eps`, `--current-price`, `--bvps` (Number), `--expected-growth`, `--aaa-yield` (Growth) | `StrictFloat`, no finiteness check | `StrictFloat` plus a finiteness check | **2.** Non-finite overrides. |
| `--eps-basis` | trimmed, lower-cased; Number `three_year_average` or `ttm`, Growth `three_year_average`, `ttm` or `fiscal_year`; the SEC rule then rejects `ttm` | trimmed, lower-cased; Number `three_year_average`, Growth `three_year_average` or `fiscal_year` | **3.** The bases the selection excludes: `ttm`, and the allowed-values list that a rejected value (`bogus`) now prints. |
| default basis, quote provider | `default_eps_basis_for_provider`, `validate_method` | the selection builds its configuration with the same `validate_method` | none |
| `--as-of`, `--no-cache` | not part of the configuration | `as_of` (aware datetime) and `use_cache`, taken from the values the command already parsed | none; no new input |
| unknown fields | `extra="forbid"` | `extra="forbid"` | none |

The differences are exactly the three expected. The only consequence beyond them: when a rejected provider is combined with another
rejected value, the provider is reported, because its field is validated first; before, the other value was reported at this point and
the provider failed later in the resolver builder. The order of the command's checks is otherwise unchanged: ticker, output flags,
`--as-of`, blank provider, then the configuration (now selection) validation, then composition. Only `--save-run` read the selection
late; the command now builds it once, and `--save-run` uses that object. The Golden suite does not go through these commands:
`investment_analysis_engine/evaluation` imports no CLI module, and its Graham cases call the tool handlers, which still build the permissive configuration.
`tool.py`, `execution.py` and the analyzers still use the configuration; nothing on those paths changed.

**Output changes, by command** (the same for `graham-number` and `graham-growth` unless stated):

| Input | Before | After |
| :--- | :--- | :--- |
| `--data-provider bogus` | `configuration_error`, `Unsupported valuation data provider 'bogus'; supported provider is 'sec_edgar'.` | `invalid_parameter`, `Invalid --data-provider: Unsupported security provider 'bogus'; supported provider is 'sec_edgar'.`, `parameters` `["--data-provider"]`, exit 1, in text and under `--json` |
| `--eps`, `--current-price`, `--bvps`, `--expected-growth`, `--aaa-yield` with `nan`, `inf`, `-inf` | exit 1 with a strategy document, `status` `invalid_input`, `Unable to analyze SYNTH: the requested inputs are invalid.` | `invalid_parameter`, `Invalid --eps: Financial override must be a finite number.` (and the equivalents), exit 1, the failure envelope under `--json` |
| `--eps-basis ttm` | Number: `SEC EDGAR requires --eps-basis to be one of (three_year_average) (received 'ttm').`; Growth: `... (fiscal_year, three_year_average) ...` | Number: `Invalid --eps-basis: Input should be 'three_year_average'`; Growth: `Invalid --eps-basis: Input should be 'three_year_average' or 'fiscal_year'` |
| `--eps-basis bogus` | Number: `... 'three_year_average' or 'ttm'`; Growth: `... 'three_year_average', 'ttm' or 'fiscal_year'` | the same sentences as for `ttm` above |

**Stored direct-command output.** The default EPS basis follows the provider id: `sec_edgar` defaults to the three-year average, and any
other id (only a test or fixture can supply one) to TTM. Invoking the commands with `sec_edgar`, the only supported provider, therefore
changes the basis and not only the provider id. The previous files recorded a TTM result that a real run cannot produce.

| Command | Item | Before | After |
| :--- | :--- | :--- | :--- |
| `graham-number` | EPS basis and value | TTM, 4.80 (provider fact) | three-year average, 3.2333 (derived from fiscal years 2022 to 2024: 2.10, 3.40, 4.20) |
| `graham-number` | Result (maximum indicated price) | 44.70 USD | 36.69 USD |
| `graham-growth` | EPS basis and value | TTM, 4.80 (provider fact) | three-year average, 3.2333 (derived) |
| `graham-growth` | Result (growth value) | 86.83 USD | 58.49 USD |

The kinds of difference in the four files (`graham-number.txt`, `.json`, `graham-growth.txt`, `.json`):

1. Provider id strings: `fixture-synth` becomes `sec_edgar` for the security facts and `yfinance` for the quote (the relabelling in
   the shared helper answers each request with its own provider id).
2. The EPS basis, value and `source_kind` (`provider` to `derived`), with the retained lineage of three fiscal-year components in the JSON.
3. The result values above, and the text lines that carry the basis (`Basis:`, `EPS (...)`) and the sources (`derived from SEC EDGAR`).
4. The EPS notes and the resolver trace messages, which describe the three-year-average derivation instead of a single TTM fact.

No other field changed.

**Tests.** One helper, `tests/_sec_labeled_graham.py`, replaces the copies in `tests/test_cli_save_run.py`, `tests/test_cli_refresh.py`,
`tests/test_workspace_integration.py` and the relabelling in `tests/_direct_command_output.py`. Direct-command tests pass
`--data-provider sec_edgar`. The tests that asserted a TTM result on the direct commands now assert the three-year average. The test
that asserted a non-finite override reaches the analysis was removed; the rejections are table rows `SUP-9` in
`tests/test_command_validation_failures.py` (every option and value, both commands, text and `--json`), with a parity test that runs
one set of inputs through the direct command and `watchlist create` and compares the result and the sentence.

**The TTM basis is now reachable only from tests** ([issue 126](https://github.com/PeterPontbriand/investment-analysis-engine/issues/126)).
The selections exclude it, so the direct commands, the watchlist and refresh cannot run it; the tool path that the Golden suite uses is
composed only from the evaluation fixtures, with a fixture provider id. The TTM code is not changed in this slice. Tests below the
command level still exercise it: `tests/analysis/graham_value/test_resolver.py`, `test_facts.py`, `test_resolution_trace.py`,
`test_cache.py`, `test_provenance.py`, `test_analyzer_config.py`, `test_fixture_provider.py` (`test_ttm_eps_returns_single_fact`,
`test_growth_value_assembly_ttm_eps`), `tests/analysis/shared/test_financial_resolution.py`, `tests/reporting/test_graham_presenter.py`,
`tests/reporting/test_display_labels.py` (`test_basis_display_name_ttm`), and the Golden cases `tests/evaluation/cases/test_graham_number.py`
and `test_graham_g3.py`.

### B.16 SWC.4d follow-up: the workspace catch-all, `runs show` and refresh (2026-10-12)

The project owner decided, on review of PR #125:

- **`runs show`.** Both ways the run repository's `get` fails to read a stored run (the envelope fails validation; the envelope disagrees
  with its own row) report `reason_code` `invalid_stored_run` with one sentence: `Analysis Run <full run ID> could not be read: its
  stored record is malformed or does not match its summary.` The exception detail goes to the log with its traceback. This resolves
  issue 113.
- **The catch-all in `_workspace_database`.** An exception that declares its own code keeps its own sentence. Every other exception raised
  inside the block, not only `ValueError`, is an `execution_error` with the sentence `<command> failed unexpectedly.`, where
  `<command>` is the command as typed after `ian` (for example `watchlist show failed unexpectedly.`); the detail goes to the log with
  its traceback and `typer.Exit` passes through. `invalid_input` is not used there.
- **`evaluate`** keeps its raw error text by decision: it is a developer command whose readers need the detail.
- **Refresh job error text** (`investment_analysis_engine/workspace/refresh.py`, the `error` field) is not changed in SWC.4d; it becomes
  [SWC.4f](#swc4f--one-failure-message-rule-for-the-direct-commands-and-refresh).
- **Order of work.** SWC.4e, SWC.4f, then LAY.1 to LAY.8, then SWC.5 to SWC.7, then PKG.

What can reach `_failed` (and so the `error` text, in the text summary and the `refresh --json` document) today, found by reading
`investment_analysis_engine/workspace/refresh.py` and the refresh executors in each strategy's `cli.py`:

| Path | Exceptions that reach it |
| :--- | :--- |
| `--no-save`, sequential | anything the executor raises (the call to `executor(ticker, selection)`) |
| saved, sequential | the executor's exceptions, and anything `execute` raises: a run-spec or codec error, an undeclared-strategy error, and the repository's insert errors (storage errors, an existing-run conflict) |
| concurrent | a worker's executor exception, passed to the coordinator, then the same `execute` exceptions on the coordinator thread |
| inside an executor | a provider failure (`DataFetchError`, `FinancialProviderError`, with provider text), a historical-quality or no-eligible-observations error, `AnalysisConfigurationError` (a missing SEC identity), a `pydantic.ValidationError` from building a configuration from a stored selection, a blank-ticker `ValueError`, a database-readiness error from the cache or run storage, and any other exception from provider libraries |

The first three rows are the paths in `refresh.py`; each ends in `_failed(..., exception, ...)`, which stores `str(exception)` as the
job's `error` and the classifier's code as `reason_code`.

### B.17 SWC.4f: one failure message rule for the direct commands and refresh (2026-10-12)

The project owner approved decisions 1, 4 and 5 below before the slice was designed, and replaced decisions 2 and 3 after reading
the failure table in A (the rulings, below).

**Decisions that stand.**

1. One function in `investment_analysis_engine/cli_support.py` produces a failure's code and message. The direct commands and refresh both use it. Refresh
   receives it by injection from the `refresh` command, as it received `classify`; nothing under `investment_analysis_engine/workspace/` imports from the
   command layer.
4. Wherever a fixed message replaces the exception's text, the detail goes to the log with its traceback. Direct provider failures
   therefore now log a traceback, and the function has no guard if it raises; a test runs every row of the table through it.
5. The refresh document and the failure document are not versioned again: `error` and `reason` keep their types and meaning.

**Rulings that replace decisions 2 and 3.** The failure code chooses the message. No strategy declares any wording and no message
names the strategy: the strategy is already identified beside every message (the command typed, the `analysis` and `method` fields of
the failure document, the method column and field in refresh). The ticker is included because it may come from configuration rather than
the command line. The message is identical on the direct commands and refresh:

| Code | Message |
| :--- | :--- |
| `provider_unreachable`, `provider_rate_limited`, `provider_unexpected_response`, `provider_no_data`, `provider_error` | unchanged: `provider_failure_sentence` |
| `historical_quality`, `no_eligible_observations`, every `database_*` code, `invalid_parameter`, `configuration_error` | the exception's own text, as written by the application |
| `invalid_input` | `Unable to analyze <T>: invalid analysis inputs or provider data.` |
| `execution_error` | `Unable to analyze <T>: the analysis failed unexpectedly.` |
| any failure after the analysis finished, while its result is saved (refresh's `execute` stage; the direct commands' `--save-run`) | `<T> was analyzed, but the result could not be saved.` |

`<T>` is the ticker the job or command resolved. For a failure while saving, the code is the one the failure classifies to, on both
paths. Four code corrections, on both paths:

1. Graham's analysis stage reports a plain `ValueError` as `invalid_input`, as its resolver stage and the other strategies do.
2. A failure only a defect can cause is `execution_error`: a stored selection that no longer converts to a configuration (row 9), a
   blank ticker inside an executor (row 10), and a run ID that already exists (row 16). Each such exception declares its code itself;
   `classify_failure` still names no exception type.
3. The direct commands' `--save-run` stop folding a saving failure's code into `invalid_input` or `execution_error`; they report the
   code it classifies to, as refresh does.
4. A selection with no declared strategy (rows 13 and 14) is `execution_error` with the `execution_error` message.

#### A. The failure table

Every kind of exception that can reach `_failed` in `investment_analysis_engine/workspace/refresh.py`, found by reading `refresh.py`, the four refresh
executors, `execute` and the run repository. The paths are the three of [B.16](#b16-swc4d-follow-up-the-workspace-catch-all-runs-show-and-refresh-2026-10-12):
`--no-save`, saved and concurrent. An exception raised inside the executor reaches all three; an exception raised by `execute` after
the executor returned (rows 15 to 17, and a run that fails validation in row 11) reaches only saved and concurrent, because `--no-save`
never calls `execute`. Row 14 is raised by the run-spec lookup, which `refresh.py` makes before the executor runs on the sequential path
and after it on the concurrent path; the rule treats it as a failure of the analysis step on both, and step 2 gives the lookup its
own step so that it is never a failure while saving.
Under concurrent admission `_failed` runs on the coordinator thread in every case.

The "today" columns were confirmed by running (below). Letters: **M** Momentum, **G** Graham Number and Graham Growth, **F** FCF Growth.
`T` is the ticker. The last column flags every row whose code or message changes: **R** on refresh, **D** on a direct command (the
by-command table below lists the direct changes), **N** the exception has no direct-command counterpart. The `--save-run` counterpart
of a row exists when the exception can arise on the direct path.

| # | Exception and where it is raised | Refresh today: code and `error` | Direct command today: code and `reason` | Under the rule: code and message | Flags |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `DataFetchError` with a kind: the Yahoo historical client (Momentum's executor); inside the executor | the kind's code (`provider_unreachable`, `provider_rate_limited`, `provider_unexpected_response`, `provider_no_data`); the provider's own text | the same code; `Unable to analyze AAPL: yfinance did not serve the request.` (one message per kind) | the same code; the direct message | R (message) |
| 2 | `DataFetchError` without a kind; same sites | `provider_error`; the provider's own text | `provider_error`; `Unable to analyze AAPL: a data provider failed; the failure was not classified.` | `provider_error`; the direct message | R (message) |
| 3 | `FinancialProviderError` with a kind: the SEC provider, where the Graham and FCF resolvers do not capture it; inside the executor | the kind's code; the provider's own text | the same code; `Unable to analyze KO: sec_edgar is limiting requests.` | the same code; the direct message | R (message) |
| 4 | `FinancialProviderError` without a kind; same sites | `provider_error`; the provider's own text | `provider_error`; the unclassified message of row 2 | `provider_error`; the direct message | R (message) |
| 5 | `HistoricalDataQualityError`: the cached historical client (Momentum); inside the executor | `historical_quality`; the exception's text | the same code and text | unchanged | none |
| 6 | `NoEligibleObservationsError`: market data (Momentum); inside the executor | `no_eligible_observations`; the exception's text | the same code and text | unchanged | none |
| 7 | `AnalysisConfigurationError`: `build_sec_production_provider` (no SEC identity) in the Graham and FCF executors, and `build_graham_resolver` (an unsupported provider, which a validated selection no longer produces) | `configuration_error`; the text (`SEC EDGAR access is not configured. ...`) | the same code. F: `Unable to start FCF & earnings-growth analysis: <text>`. G at the resolver build: `Unable to start Graham analysis: <text>`; G at the analysis stage: `<text>`. M: `Unable to complete momentum analysis for AAPL: the returned price history could not be analyzed.` | `configuration_error`; the exception's text | D (M, F, G at the resolver build) |
| 8 | `DatabaseReadinessError`, nine `database_*` codes: `ensure_database_ready` in the cache and historical-client helpers; inside the executor | the `database_*` code; the exception's text | the same code and text | unchanged | none |
| 9 | `pydantic.ValidationError`: `selection.to_*_config()` at the start of the Graham and FCF executors, for a stored selection that no longer converts to a configuration; inside the executor | `invalid_input`; Pydantic's multi-line text | none: the direct commands validate their options first and report `invalid_parameter` | `execution_error`; `Unable to analyze T: the analysis failed unexpectedly.` | R (code and message), N |
| 10 | `ValueError("A nonblank ticker is required.")`: `require_ticker` in Momentum's executor, and the analyzers of the others; inside the executor | `invalid_input`; `A nonblank ticker is required.` | none: the direct commands reject a blank ticker first, as `invalid_parameter` | `execution_error`; the `execution_error` message | R (code and message), N |
| 11 | any other `ValueError`, including a `ValidationError` while `execute` builds the run: provider libraries, pandas, Pydantic; inside the executor, or in `execute` | `invalid_input`; the exception's text | M: `invalid_input`; the price-history message. F: `invalid_input`; `Invalid analysis inputs or provider data.` G at the analysis stage: `execution_error`; `Graham analysis failed unexpectedly for KO.` G at the resolver build: `invalid_input`; `Invalid analysis inputs or provider data.` | `invalid_input`; `Unable to analyze T: invalid analysis inputs or provider data.`; while saving, `T was analyzed, but the result could not be saved.` | R (message), D (message on all four commands; G's analysis-stage code) |
| 12 | any other `Exception` (`RuntimeError`, `KeyError`, library errors); anywhere in an executor | `execution_error`; the exception's text | `execution_error`. M: `Momentum analysis failed unexpectedly for AAPL.` F: `FCF & earnings-growth analysis failed unexpectedly for KO.` G: `Graham analysis failed unexpectedly for KO.` | `execution_error`; the `execution_error` message | R (message), D (message) |
| 13 | `UndeclaredStrategyError`: `refresh_executor_for` in `_refresh_executor`, a selection with no CLI-tier entry; as the executor's exception | `execution_error`; `No declared strategy for refresh executor (...)` | none: a direct command is the strategy | `execution_error`; the `execution_error` message | R (message), N |
| 14 | `UndeclaredStrategyError`: `_spec_for`, a selection with no run spec; in `refresh.py`, before the result is saved | `execution_error`; `No declared strategy for run spec (...)` | none | `execution_error`; the `execution_error` message | R (message), N |
| 15 | `InvalidStoredRunError`: `encode_with` in `execute`, evidence that does not encode; while saving | `invalid_stored_run`; `Invalid Momentum evidence.` | through `--save-run`, the code is folded: M and F `invalid_input`, G `execution_error`, each with its strategy message | `invalid_stored_run`; `T was analyzed, but the result could not be saved.` | R (message), D (code and message) |
| 16 | `AnalysisRunConflictError`: `repository.insert`, the run ID exists (a `ValueError` that declares no code today); while saving | `invalid_input`; `Analysis run <id> already exists.` | through `--save-run`: M and F `invalid_input`, G `execution_error`, each with its strategy message | `execution_error` (the exception declares it); the save message | R (code and message), D (message; code for M and F) |
| 17 | `sqlalchemy.exc.SQLAlchemyError` subclasses (`OperationalError` and others): `repository.insert`; while saving | `execution_error`; the driver's text, including the SQL statement | `execution_error`; the strategy's "failed unexpectedly" message | `execution_error`; the save message | R (message), D (message) |

17 rows. The code or message changes on refresh in 13 rows (1 to 4, 9 to 17); the code itself changes in three of them (9, 10, 16). It
changes on a direct command in six rows (7, 11, 12, 15, 16, 17); the code itself changes in rows 11 (Graham), 15 and 16. Rows 9, 10, 13
and 14 have no direct counterpart. Rows 5, 6 and 8 do not change on either path.

Exceptions that never reach `_failed`: `WatchlistNotFoundError` and `EmptyRefreshTargetError` (raised before any job), `StoredSelectionError`
(raised when the watchlist's snapshot is read), `InvalidParameterError` (no executor raises it), `UnsupportedRunVersionError` (raised only
when decoding), and `typer.Exit` and `KeyboardInterrupt` (not caught).

**Confirmed by running (step 1).** A throwaway probe under the ignored `.tmp/` folder (removed afterwards, not committed) ran through
`typer.testing.CliRunner` with a disposable migrated database, the suite's socket guard and `--no-provider-check`, so no network and no
real database were touched. It built 16 exceptions that stand for the 17 rows (one `UndeclaredStrategyError` serves rows 13 and 14; row
11 by a plain `ValueError`) and raised each at the executor boundary, patching `_refresh_executor`, through `refresh --workers 1
--no-save`, `refresh --workers 1` and `refresh --workers 2`. It raised the exceptions of rows 8, 11 (a `ValidationError`), 14, 15, 16
and 17 again at the persistence boundary, patching `investment_analysis_engine.workspace.refresh.execute`, through the saved and concurrent paths. Every
"Refresh today" cell was identical on the paths that reach it. The same exceptions were raised in each of the four direct commands at the
point where the analysis runs, and the resolver-build block of both Graham commands was probed separately: 68 direct results, from
which every "Direct command today" cell comes. The probe raises exceptions at the boundaries and does not reproduce their real origins,
so the "where it is raised" cells come from reading the code. Row 12 is also pinned from a real origin by the stored output
`refresh-failed-job`.

#### By command: every direct-command change

Providers, `historical_quality`, `no_eligible_observations`, `database_*`, `invalid_parameter` and the messages of rows 5, 6 and 8 do
not change on any command. Graham Number and Graham Growth change identically, so they share rows; "G (resolver build)" is the second
`execution_errors` block of both Graham commands.

| Command | Failure | Before: code; `reason` | After: code; `reason` |
| :--- | :--- | :--- | :--- |
| `momentum` | `configuration_error` | same code; `Unable to complete momentum analysis for AAPL: the returned price history could not be analyzed.` | same code; the exception's text |
| `momentum` | plain `ValueError` | `invalid_input`; the price-history message above | `invalid_input`; `Unable to analyze AAPL: invalid analysis inputs or provider data.` |
| `momentum` | any other exception | `execution_error`; `Momentum analysis failed unexpectedly for AAPL.` | `execution_error`; `Unable to analyze AAPL: the analysis failed unexpectedly.` |
| `momentum --save-run` | `InvalidStoredRunError` while saving | `invalid_input`; the price-history message | `invalid_stored_run`; `AAPL was analyzed, but the result could not be saved.` |
| `momentum --save-run` | run ID exists while saving | `invalid_input`; the price-history message | `execution_error`; the save message |
| `momentum --save-run` | driver error while saving | `execution_error`; `Momentum analysis failed unexpectedly for AAPL.` | `execution_error`; the save message |
| `momentum --save-run` | `ValidationError` building the run | `invalid_input`; the price-history message | `invalid_input`; the save message |
| `graham-number`, `graham-growth` | `configuration_error` at the analysis stage | same code; the exception's text | unchanged |
| `graham-number`, `graham-growth` | `configuration_error`, G (resolver build) | same code; `Unable to start Graham analysis: <text>` | same code; the exception's text |
| `graham-number`, `graham-growth` | plain `ValueError` at the analysis stage | `execution_error`; `Graham analysis failed unexpectedly for KO.` | `invalid_input`; `Unable to analyze KO: invalid analysis inputs or provider data.` |
| `graham-number`, `graham-growth` | plain `ValueError`, G (resolver build) | `invalid_input`; `Invalid analysis inputs or provider data.` | `invalid_input`; `Unable to analyze KO: invalid analysis inputs or provider data.` |
| `graham-number`, `graham-growth` | any other exception | `execution_error`; `Graham analysis failed unexpectedly for KO.` | `execution_error`; `Unable to analyze KO: the analysis failed unexpectedly.` |
| `graham-number --save-run`, `graham-growth --save-run` | `InvalidStoredRunError` while saving | `execution_error`; `Graham analysis failed unexpectedly for KO.` | `invalid_stored_run`; `KO was analyzed, but the result could not be saved.` |
| `graham-number --save-run`, `graham-growth --save-run` | run ID exists while saving | `execution_error`; the "failed unexpectedly" message | `execution_error`; the save message |
| `graham-number --save-run`, `graham-growth --save-run` | driver error while saving | `execution_error`; the "failed unexpectedly" message | `execution_error`; the save message |
| `graham-number --save-run`, `graham-growth --save-run` | `ValidationError` building the run | `execution_error`; the "failed unexpectedly" message | `invalid_input`; the save message |
| `fcf-growth` | `configuration_error` | same code; `Unable to start FCF & earnings-growth analysis: <text>` | same code; the exception's text |
| `fcf-growth` | plain `ValueError` | `invalid_input`; `Invalid analysis inputs or provider data.` | `invalid_input`; `Unable to analyze KO: invalid analysis inputs or provider data.` |
| `fcf-growth` | any other exception | `execution_error`; `FCF & earnings-growth analysis failed unexpectedly for KO.` | `execution_error`; `Unable to analyze KO: the analysis failed unexpectedly.` |
| `fcf-growth --save-run` | `InvalidStoredRunError` while saving | `invalid_input`; `Invalid analysis inputs or provider data.` | `invalid_stored_run`; `KO was analyzed, but the result could not be saved.` |
| `fcf-growth --save-run` | run ID exists while saving | `invalid_input`; the generic input message | `execution_error`; the save message |
| `fcf-growth --save-run` | driver error while saving | `execution_error`; `FCF & earnings-growth analysis failed unexpectedly for KO.` | `execution_error`; the save message |
| `fcf-growth --save-run` | `ValidationError` building the run | `invalid_input`; the generic input message | `invalid_input`; the save message |

#### B. The design

**The function.** `investment_analysis_engine/cli_support.py`, beside `provider_failure_sentence`:

```text
describe_failure(exception: BaseException, ticker: str | None, *, saving: bool) -> FailureDescription

FailureDescription(code: FailureReasonCode, message: str)
```

It classifies the exception with `classify_failure` and then applies the rule. When `saving` is true the message is the save message and
the code is the classified one. Otherwise the code selects the message: a provider code gives `provider_failure_sentence` (when the
exception is a provider failure); the codes shown as raised give `str(exception)`; `invalid_input` and `execution_error` give their
fixed messages; any other code (none arises on a supported path before the result is saved) is reported as `execution_error`, so both
paths always agree. A `None` ticker is spelled `the requested instrument`, as `provider_failure_sentence` already does. Every branch
that shows a fixed message logs the exception with its traceback (`logger.error(..., exc_info=exception)`, so a traceback survives on the
concurrent path, where the function runs on the coordinator thread outside any `except` block). No strategy supplies wording; the
`unexpected`, `invalid` and `invalid_detail` parameters of `execution_errors` are removed.

**Marking the saving step.** `maybe_save_run` runs the analysis and the save in one call, and `investment_analysis_engine/cli_run_support.py` is outside this
slice's file scope, so the strategy `cli.py` files mark the step. `investment_analysis_engine/cli_support.py` gains `SaveStage` (a flag that is set when the
wrapped `normalize` of `maybe_save_run` returns, that is, when the analysis has finished) and the context manager `saving_failures`,
which re-raises an exception from its block as `SavingFailureError` when the flag is set. `execution_errors` unwraps `SavingFailureError` and
passes `saving=True` and the original exception, which stays the `cause` of the envelope. Graham and FCF wrap only their call of
`maybe_save_run`; Momentum has already analyzed when it calls `save_run_execution`, so it wraps that call with the flag already set.
The readiness check that precedes the analysis is outside the marked step, so it keeps its own code and text.

**Defects declare their code.** `investment_analysis_engine/cli_support.py` gains `InternalDefectError`, which declares `execution_error`, and two helpers the
refresh executors call: one converts a stored selection to its configuration and turns a `ValidationError` into that error, and one
rejects a blank ticker before the analysis starts. `AnalysisRunConflictError` declares `execution_error` where it is defined in
`investment_analysis_engine/data/repositories/analysis_runs.py`. `classify_failure` is unchanged.

**How `refresh_watchlist` receives it.** One keyword parameter replaces `classify`:
`describe: Callable[[BaseException, str, bool], JobFailure]`, where `JobFailure(reason_code: str, error: str)` is defined in
`investment_analysis_engine/workspace/refresh.py`. `_failed` stores both fields and takes the `saving` flag: the sequential path sets it when the executor has
returned (`captured` is not empty), the concurrent path when the worker produced a capture and the run spec was found. `_settle` looks up
the spec in its own step first, so a missing spec is not a saving failure on either path. The `refresh` command builds the callable
from `describe_failure`; `investment_analysis_engine/workspace/` imports nothing from the command layer.

**How the direct commands are fed.** `execution_errors` calls `describe_failure(exc, scope.ticker, saving=...)` and builds the
envelope and output it builds now. The four commands drop their callbacks. The CLI tier is unchanged: no wording travels through it.

#### C. Findings of step 1, resolved by the rulings

1. **Rows 9 and 10 (a stored selection that does not convert, a blank ticker).** Resolved by correction 2: `execution_error` with the
   `execution_error` message, on refresh.
2. **Row 11 for Graham.** Resolved by correction 1 and the message table: `invalid_input` with the `invalid_input` message at both Graham
   stages.
3. **Rows 15 and 16 (a save-step failure described as an analysis failure).** Resolved by the save message and correction 3.
4. **Row 7 for Momentum.** Resolved: `configuration_error` shows the exception's text on every command.
5. **Rows 13 and 14 (an undeclared strategy).** Resolved by correction 4; no generic wording is needed because the message names no
   strategy.
6. **Graham's two direct messages for one exception.** Resolved: no message depends on where the command raised it.
7. **Text that still reaches `error` and `reason` as written (rows 5, 6, 8).** Unchanged by the rulings: the exception's text is shown
   for the codes the table lists, on both paths.
8. **Direct commands gain log records.** Accepted.
9. **`_failed` has no guard if the function raises.** Accepted; a test runs every row through the function.

#### D. Files and tests

**Source.**

- `investment_analysis_engine/cli_support.py`: `FailureDescription`, `describe_failure`, `SaveStage`, `SavingFailureError`, `saving_failures`, `InternalDefectError`
  and its two helpers; `execution_errors` loses its wording parameters.
- `investment_analysis_engine/strategies/momentum/cli.py`, `fcf_growth/cli.py`, `graham_number/cli.py`, `graham_growth/cli.py`: drop the callbacks; mark the
  saving step; the refresh executors call the defect helpers.
- `investment_analysis_engine/workspace/refresh.py`: `JobFailure`, the `describe` parameter in place of `classify`, the `saving` flag, the spec lookup as its
  own step.
- `investment_analysis_engine/cli_workspace.py`: build `describe` from `describe_failure` and pass it.
- `investment_analysis_engine/data/repositories/analysis_runs.py`: `AnalysisRunConflictError` declares `execution_error`.
- `investment_analysis_engine/reporting/documents/refresh.py` and `schemas/refresh-summary.schema.json`: the `error` description (a description only; no
  version change). `docs/user/WORKSPACE.md`, `docs/user/USAGE.md` and this plan.

**Tests added.** One table-driven test over every row of A (`tests/test_failure_messages.py`): for each refresh path that reaches the row and
each direct command that has a counterpart, the code and message match the "under the rule" column, in text and under `--json`, and the
exception is in the log with its traceback. A test that no message on either path contains a strategy name, `input_value`,
`validation error for`, `errors.pydantic.dev` or an SQL statement. A test that the same exception gives the same code and message from a
direct command and from a refresh job. Tests of `describe_failure` over every row and of `saving_failures`; tests that
`AnalysisRunConflictError` and `InternalDefectError` declare their codes while `classify_failure` names no exception type.

**Existing tests and stored output that change.** The `refresh_watchlist(` calls that pass `classify=` (25 in
`tests/workspace/test_refresh.py`, and `test_refresh_provider_failure.py`, `test_failure_reason_codes.py`, `test_workspace_fail_closed.py`,
`test_not_applicable_calculation.py` and `tests/data/repositories/test_watchlist_repository.py`) pass `describe=` through a helper in
`tests/_wiring.py`; `tests/test_cli_support.py`; `tests/test_cli.py` (two assertions on the old messages);
`tests/utils/test_operational_logging.py` (the stderr message and the log line); the classification table `tests/_failure_code_table.py`
(the conflict error's code); `tests/test_cli_refresh.py`; the schema drift test; and the stored output
`tests/expected_output/workspace_commands/refresh-failed-job.txt` and `refresh-failed-job-json.txt` (`fixture provider failure` becomes
`Unable to analyze BAD: the analysis failed unexpectedly.`).

#### E. Implemented as designed, with these differences (2026-10-12)

- `SavingFailure` is named `SavingFailureError` (the project's lint rule requires the suffix).
- `investment_analysis_engine/cli_support.py` attaches a `logging.NullHandler` to its logger. With `--no-logging` no handler is configured, and Python's
  last-resort handler would write the logged traceback to standard error; the null handler keeps standard error to the message.
- The direct commands' failure log line is `Failure reported to the user as: <message>` for every fixed message; the earlier
  `Unexpected failure reported to the user as:` line is gone.
- The sequential refresh path needed no restructuring for row 14 (its lookup already runs before the executor); only `_settle` gained a
  separate lookup step.

### B.18 SWC.5 split and the site-check decisions (2026-10-17)

Approved by the project owner on 2026-10-17.

- **Split.** SWC.5 became SWC.5a (site data, report-mode checks, the status command and the generator) and
  SWC.5b (generated strategy lists in `docs/user/USAGE.md` and `docs/user/WORKSPACE.md` with T26, the
  watchlist option table moved into the strategy guides, and the `FCF_EARNINGS_GROWTH.md` to
  `FCF_GROWTH.md` rename).
- **Where the generated edit-site table lives until SWC.7 moves the guide.** In a marked block in
  `docs/project/ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md`; SWC.7's move carries it. The design's verbatim copy
  of the table is dropped. The design's §17 table stays as design history, with a one-line pointer to the
  generated table as the current list, and the design's §19.1 is corrected to match.
- **Which checks need a site.** Only per-strategy site checks. A site check takes a strategy's names and
  returns `Gap(site_id, path, message)` records. Suite-wide rules (closedness, uniqueness, import layering,
  the analyzer envelope, failure codes and the like) keep their current form and need no site. The two kinds
  are told apart by signature, never by a list of names: a site check is a function of one `StrategyNames`
  parameter that returns `list[Gap]`. T25's "every check is named by a site" applies to site checks only.
- **Undeclared strategies.** Site checks work from the module name and alias, and use the descriptor only
  when one is declared. If the package cannot be imported, the status command reports the import error as
  its first gap and exits 1.
- **New-file sites.** Done means the file exists and defines the names that site requires. The status command
  does not run mypy; the managed gate does.
- **Markers.** A generated block sits between an HTML-comment begin and end pair. The begin comment names
  `scripts/generate_strategy_docs.py` and says the block is generated and must not be edited by hand.
- **One generator** for generated documentation blocks, `scripts/generate_strategy_docs.py`. SWC.5a creates it
  with the guide table as its only block; SWC.5b adds the user-doc lists. A stale block fails T25 with a
  message naming the file and telling the reader to run the script.

#### Implementation record (2026-10-17)

- **The existing bidirectional checks stay as they were.** Checks such as T1 to T6, the tier checks, T8, T10
  and T21 compare a surface with the whole closed tuple in both directions; making them per-strategy would
  lose the orphan direction (a selection class, tool, argument model or tier entry with no descriptor). They
  are classed as suite-wide and keep their signatures and messages. Each site check is a new function of the
  strategy's names. Where a suite-wide check had a per-strategy part, that part is one helper that both forms
  call, and the orphan direction stays suite-wide only: `_selection_gaps_for` (T1), `_evidence_gaps_for` (T2),
  `_analyzer_gaps_for` (T3), `_argument_gaps_for` (T4), `_tool_required_gaps_for` and `_dispatch_gaps_for` (T6),
  `_tier_gaps_for` (T10 for both tiers), `_strategy_flag_gaps_for` (T7), `_round_trip_entry_gaps` and
  `_replay_entry_gaps` (T8), and `evaluation_fixture_id_gaps` and `published_schema_gaps`, which already took a
  single descriptor.
- **Site coverage by row.** The site data file has one site per row of the design's §17 (1a and 1 to 19) and
  one for the schema-generation command. Rows 2 to 5, 10 and 15 work from the declared descriptor and the
  type-level lists; an undeclared strategy is reported at each of them, naming the file to edit.
- **Row 16 and row 17.** Row 16's path is the cases file (`evaluation/cases/{module}.py`) because the
  fixtures are shared files whose names do not follow the strategy (`graham.py`, `market_data.py`); its check
  also requires a golden case for the tool and that the fixtures serve it. Row 17 requires the catalog to
  import the case module and the catalog test to pin each case id. Whether the suite version was bumped is
  reviewed truth that no check can establish for one strategy.
- **Row 19.** A strategy has watchlist options of its own exactly when its selection builder reads a
  `WatchlistFlags` field. The check reads the builder's source, and requires each flag it reads to be a
  `WatchlistFlags` field and a parameter of both `watchlist create` and `watchlist add-selection`. A strategy
  that reads only shared flags has nothing to add.
- **Row 8.** The execution site is done when the file defines the capture type and the `from_*_capture`
  function; the save-run test (T22) remains the check that a run is stored, because it needs a database.
- **Temporary guide-name exception.** The FCF Growth guide is still `FCF_EARNINGS_GROWTH.md`, so
  `scripts/strategy_sites.py` maps the alias `fcf-growth` to that name until SWC.5b renames the file and
  removes the entry.

#### SWC.5b implementation record (2026-10-17)

- **Blocks.** `USAGE.md` holds the `strategy-help-commands` block (one `uv run ian <alias> --help` line per
  strategy, in the order of the closed tuple) and `WORKSPACE.md` the `strategy-table` block (alias, strategy
  name, stored method id, link to the guide's "Watchlist options" section). Both are written by
  `scripts/generate_strategy_docs.py`; a stale or missing block fails T26 naming the file and the script.
- **Rename.** `FCF_EARNINGS_GROWTH.md` is `FCF_GROWTH.md`; the temporary guide-name exception is removed. Mentions
  of the old file name that are not links stay as written.
- **Command site.** `strategy-docs` (`site_strategy_docs`). A site names one path, so every gap carries the
  site's path (`USAGE.md`) and the message names the document the gap is in.
- **Moved facts.** The `fcf-growth` row of the former flags table listed only the four FCF flags, although its
  selection builder also reads `--as-of`, `--data-provider` and `--no-cache`. The row moved unchanged and is
  reported to the project owner.
