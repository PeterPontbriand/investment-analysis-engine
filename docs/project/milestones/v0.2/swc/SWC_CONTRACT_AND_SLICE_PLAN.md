# SWC — Strategy Wiring Consolidation: Contract and Slice Plan

Consolidates repeated strategy wiring before Step 3.5 adds seven analyzers, completes the
typed JSON envelope and schema scope moved from IR.5, and gives failures a typed envelope. The [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status)
owns its position and work-package status.

## 1. At a glance

- **What this work does:** reduce repeated per-strategy wiring across orchestration, workspace
  selection and execution, evidence codecs, reporting, CLI integration and deterministic
  evaluation through a closed, statically declared wiring descriptor; give every `--json` document
  (strategy, workspace, database and failure) a typed model and a generated schema; give failures a
  typed envelope on direct and workspace commands, per-job refresh failures a stable code and the
  database report the envelope's field names; replace Momentum's three profile-composition copies with one; document the
  contributor workflow.
- **What the descriptor means:** one authoritative infrastructure declaration for repeated wiring
  metadata. It is not a representation of strategy behavior. Generic consumers derive their
  dispatch metadata from it; independent conformance tests verify complete consumption.
- **What it does not do:** change analyzer formulas, classifications, result semantics, or the
  `BaseAnalyzer[ConfigT, ResultT]` invocation envelope; add a common result type, dynamic discovery,
  plugins, self-registration, or a general strategy framework. Full list: [Scope limits](#6-scope-limits).
- **Decision:** a closed descriptor is authorized only to consolidate the duplicated wiring in
  Appendix A. SWC applies the existing AGENTS.md §0 allowance for an explicit, statically declared list with shared generic wiring. This does not create a registry in the architectural sense prohibited by IR.2. See [§3](#3-architectural-contract).
- **Rules every slice follows:** preserve strategy-owned config and result types, retain explicit
  provenance and outcomes, bump affected stored-shape versions without migrations during the
  consolidation period, and run the complete managed gate at each slice end. Each next slice waits
  for explicit project-owner authorization.
- **Where detail lives:** the audited inventory is in
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
| SWC.2 | [Declare and consume wiring in orchestration and evaluation](#swc2--orchestration-and-evaluation-wiring) | Next | |
| SWC.3 | [Consume wiring in workspace execution and codecs](#swc3--workspace-selection-execution-and-codecs) | Planned | |
| SWC.4a | [Typed failure envelope and schema generator](#swc4a--failure-envelope-and-schema-generator) | Planned | |
| SWC.4b | [Typed workspace documents](#swc4b--typed-workspace-documents) | Planned | |
| SWC.4c | [Typed strategy envelopes and replay dispatch](#swc4c--typed-strategy-envelopes-and-replay-dispatch) | Planned | |
| SWC.5 | [Generate schemas, document contribution, and complete conformance](#swc5--schemas-contributor-guide-and-final-conformance) | Planned | |

## 3. Architectural contract

### 3.1 Decision and relationship to IR.2

SWC uses a closed, statically declared descriptor as the single authoritative declaration of
duplicated strategy-wiring metadata identified by the audited inventory. Generic infrastructure
consumes that declaration. Independent structural conformance tests verify that every supported
strategy is declared and that each required generic consumer derives its wiring from the descriptor.
The descriptor and tests together prevent forgotten wiring without runtime discovery.

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

The descriptor is an infrastructure declaration of wiring metadata, not a universal representation
of strategy behavior. The contract slice will authorize only fields needed by audited consumers:

- stable analysis and method identifiers, tool name, and tool-argument/configuration model types
  where generic wiring requires them, plus result/evidence model types only where a generic
  consumer genuinely needs them for dispatch or codec selection;
- per-strategy configuration, method, result-schema, codec, or projection version metadata where
  the inventory shows repeated declarations that must stay aligned;
- references to strategy-owned encoding, decoding, presentation, selection-conversion, or execution
  functions when a generic consumer needs to dispatch to that strategy-owned behavior; and
- construction or dependency-wiring information only where the audit proves it removes repeated
  composition while preserving injected strategy dependencies.

It must not contain calculation logic, financial formulas, strategy policy, generic strategy
behavior, a generic result supertype, plugin lifecycle, dynamic discovery, self-registration, or a
speculative factory hierarchy. It adds no strategy abstraction beyond the existing
`BaseAnalyzer[ConfigT, ResultT]` invocation envelope. A descriptor reference may route to a
strategy-owned function; it does not absorb or generalize that function's behavior.

### 3.3 Static declaration, typing, and conformance

The supported strategy declarations are closed and source-declared. Generic consumers use or derive
their wiring from those declarations; consumers do not independently repeat the same identifiers,
types, versions, or dispatch cases. No runtime package scanning, registration side effects, plugin
loading, reflection-based probing, dynamic lookup, or discovery is introduced merely to connect the
descriptor to its consumers. Consumers may iterate the closed declarations or use a statically
constructed index derived from them.

SWC.1 will settle the actual Python typing form only after inspecting the audited consumers. It must
compare generic parameters, erased/existential representations, typed callables, concrete instances,
and other minimal options without presupposing `StrategyDescriptor[ConfigT, ResultT]`. Choose the
simplest structure that passes `mypy --strict` and keeps each strategy's config, result, and
evidence contracts distinct.

Focused conformance tests are required safety nets around the descriptor, not alternatives to it.
They must verify that:

1. every supported strategy at the existing explicit strategy boundaries has a descriptor;
2. every descriptor has all required metadata and required strategy-owned function references;
3. every generic wiring consumer identified in §4 actually derives its supported entries from the
   descriptor;
4. an intentionally incomplete consumer or dispatch fixture fails a focused test and identifies
   the missing consumer and, where practical, the strategy; and
5. strategy-specific calculations, configuration meaning, classification, evidence shape and
   presentation remain owned by their strategy implementations rather than inferred from descriptor
   fields.

Do not make these checks tautological by deriving both the descriptor and the independently checked
strategy set from the same unchecked list. SWC.1 will identify existing explicit contract surfaces
that independently define or expose supported strategies and compare their coverage with the
descriptor. The test code may name the required consumer surfaces, but it must not become a second
copy of the strategy wiring metadata.

The intended data flow is static; the tests inspect and challenge it rather than registering or
discovering strategies:

```text
closed static strategy declarations
              |
              v
      strategy wiring descriptor
              |
      +-------+-------+-------+
      |       |       |       |
      v       v       v       v
  generic  generic  generic  generic
  wiring   wiring   wiring   wiring
              |
              v
       conformance tests
```

## 4. Inventory disposition

Appendix A is the audited basis for SWC scope, including surfaces missed by the original proposal.
The descriptor replaces repeated infrastructure declarations, not every strategy-specific branch
or type that mentions a strategy.

| Inventory area | Descriptor-authoritative information and generic consumption | Remains strategy-specific or explicit |
| :--- | :--- | :--- |
| Orchestration tools and evaluation mappings | Stable analysis/method/tool identifiers, tool-argument model references, tool-argument-to-tool routing, and the repeated evaluation `_tool_name` mappings. Tool registration and generic routing consume descriptor metadata. `ToolName` remains the single hand-written declaration of tool-name strings and each descriptor binds one member, so no second model-to-name mapping exists (settled in SWC.1; a descriptor-built enum fails `mypy --strict`). | Analyzer/provider dependency fields, analyzer construction, argument validation details, and config construction remain typed and strategy-owned. The tool-handler table remains typed and strategy-owned. |
| Persisted selection and workspace execution | The CLI alias vocabulary, selection-to-executor dispatch keys, and method/config/result-schema/codec version metadata where currently duplicated across execution and codec tables. The refresh executor table is keyed by the descriptor's identity and fails closed. | `AnalysisSelection`, `AnalysisToolArguments`, `NativeEvidence`, each persisted selection/config model, conversion semantics, analyzer invocation, capture shape, and outcome classification remain explicit heterogeneous contracts. Adapters remain strategy-owned even when dispatch to them is generic. |
| Evidence encoding and decoding | Result/capture type-to-codec dispatch and repeated expected version metadata derive from descriptor references and version fields. | Each strategy's encode/decode implementation, validation rules, evidence shape, ticker checks, and provenance semantics remain owned by its codec and result type. |
| Reporting, replay, and JSON output | The `(analysis_id, method_id)` route and any genuinely duplicated dispatch key, including the identifier literals in the JSON builders and `execution_errors` calls, derive from the descriptor. The projector table is keyed by that identity and fails closed. Schema generation enumerates the typed strategy envelope models and the failure envelope. | Versioned projection behavior, presentation wording, rendering, typed envelope shape, strategy result unions, and historical replay semantics remain strategy-specific and explicit. The failure envelope is one shared shape, not a descriptor field. `projection_version` remains distinct from method and result-schema versions. |
| Fixture-backed evaluation composition and direct CLI commands | Only repeated metadata or dispatch keys proven by Appendix A to be wiring duplication may derive from the descriptor. | Fixture values, expected outcomes, scoring, dependency composition, direct CLI command semantics, and any explicit user-facing boundary remain as they are. The one exception is Momentum's profile composition in `src/cli.py` and `src/cli_workspace.py`, which SWC.3 reduces to a single implementation. A strategy mention alone does not justify changing a site. |

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

### SWC.2 — Orchestration and evaluation wiring

- **Problem:** each strategy currently has its own tool-argument model, handler, dependency fields,
  registration call and evaluation argument/tool mapping; an omitted branch can silently remove a
  strategy from production or deterministic evaluation.
- **Decision:** establish the closed declaration and focused metadata/coverage checks, then consume
  descriptor-owned tool and evaluation routing. Keep analyzer config creation, injected dependencies,
  and fixture composition strategy-specific.
- **Scope:** the new `src/strategy_wiring.py`; `src/orchestrator/{analysis_tools,tool_names,analysis_tool_arguments}.py`
  (`ToolName` and the argument models move out of their current modules); `src/workspace/native_evidence.py`
  (the `NativeEvidence` union moves; `src/workspace/execution.py` changes its import only); and
  `src/evaluation/{__init__,models,composition,runner,ollama_runner,evaluator,catalog}.py`, the six
  `src/evaluation/cases/*.py` importers, the tests that import the moved symbols, `src/core/constants.py`
  (the unused `AnalysisType` is deleted) and the docs that name the moved symbols. `ToolName`, the argument
  models and `NativeEvidence` move with no compatibility re-export; every importer is updated, and the
  `ToolName` export from `src.evaluation` is removed. `_require_tool_evidence` and `_native_status` become
  keyed tables instead of defaulting to FCF. Replace only descriptor-authoritative metadata and dispatch in Appendix
  A. Add conformance checks for descriptor completeness and each changed consumer, including an
  incomplete-consumer negative control. Do not change evaluation fixture truth, scoring, formula
  semantics or external-call behavior.
- **Branch:** `feat/swc-2-orchestration-evaluation-wiring`, from `main` after SWC.1 has merged.
- **Detail:** [SWC.1 design §6 and §11](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#11-migration-from-current-declarations),
  [inventory disposition](#4-inventory-disposition) and [audited inventory](#appendix-a-proposal-inventory-verified-against-main).

### SWC.3 — Workspace selection, execution and codecs

- **Problem:** persisted selections, selection-to-config conversion, method adapters, native result
  unions, version metadata, refresh dispatch and evidence codecs each repeat strategy-specific
  wiring. Version tuples must stay aligned across capture, storage and decoding.
- **Decision:** consume descriptor dispatch and version metadata where the inventory marks it
  duplicated. Retain explicit typed selection/config/result boundaries, strategy-owned execution
  adapters and codecs. Any stored-shape change increments its relevant version; no migration or
  compatibility code is added during the consolidation period. Dispatch fails closed: evidence or a
  stored run that matches no declared strategy is rejected with an error naming it. No strategy is
  the default branch. Today only `encode_evidence` falls through to Momentum; `decode_evidence` already
  rejects an undeclared pair before its Momentum branch, and both become table-driven.
- **Scope:** `src/strategy_wiring.py`, `src/workspace/requests.py` (`parse_selection`: alias membership from the
  descriptor and an alias-keyed table of parsers in place of the chain that ends in an unconditional
  Momentum return), `src/workspace/method_aliases.py` (deleted; the
  descriptor owns the alias vocabulary), strategy execution adapters, `src/workspace/execution.py`,
  `src/workspace/codecs.py`, per-strategy codec modules, `src/data/repositories/watchlists.py` (alias lookup),
  `src/cli_workspace.py` (including `_build_selection`, whose chain ends in an unconditional FCF return and
  becomes an alias-keyed table), `src/cli.py` (Momentum profile composition only), the
  `getattr(selection, "as_of", None)` probe in `execute`, and focused tests.
  Replace Momentum's three profile-composition copies (two in `src/cli.py`'s `momentum` command,
  one in `src/cli_workspace.py`'s `_execute_momentum`) with one `compose_momentum_profile` in `src/workspace/momentum_execution.py`; detail in the
  [Momentum profile composition note](MOMENTUM_PROFILE_COMPOSITION_DEDUPLICATION.md) and
  [SWC.1 design §14](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#14-momentum-profile-composition-helper). Move only selection-to-executor routing and repeated version/codec dispatch metadata identified in
  §4. Preserve the `AnalysisSelection` union, conversion methods, adapter behavior, `NativeEvidence`
  union, `AnalysisRun` replay guarantees and refresh isolation. No financial or outcome
  classification changes. Add tests that an undeclared evidence type and an undeclared
  `(analysis_id, method_id)` are rejected rather than handled as Momentum; every valid input
  encodes and decodes exactly as before.
- **Branch:** `feat/swc-3-workspace-wiring`, from `main` after SWC.2 has merged; its scope and review gate are
  recorded in the implementation record.
- **Detail:** [SWC.1 design §6 and §11](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#11-migration-from-current-declarations),
  [inventory disposition](#4-inventory-disposition), [audited inventory](#appendix-a-proposal-inventory-verified-against-main),
  and the [Momentum profile composition note](MOMENTUM_PROFILE_COMPOSITION_DEDUPLICATION.md).

### SWC.4 — Reporting and typed JSON envelopes

Every `--json` document gets a typed model and a checked-in schema, and failures get one envelope. That
is three reviewable concerns, so it is three slices, in this order. The contract, the document list,
the schema layout and the output changes are in the
[SWC.1 design §11 and §13](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#13-failure-envelope-contract). Keep `projection_version`, method
version and result-schema version distinct and do not silently reinterpret historical runs. See the
[IR.5 schema decision](#b3-ir5-schemas).

#### SWC.4a — Failure envelope and schema generator

- **Problem:** failures reach callers in three unrelated shapes, per-job refresh failures have no
  stable code, and no schema generator or drift check exists.
- **Decision:** one `FailureEnvelope` and one classifier serve the direct and workspace commands;
  `refresh --json` jobs carry a `reason_code`; `DatabaseMaintenanceReport` adopts the envelope's field
  names. Failures are reported, never self-remediated.
- **Scope:** `src/reporting/documents/{failure,database}.py`, `src/reporting/failure_classification.py`,
  `src/cli_support.py`, `src/reporting/presentation.py`, the `execution_errors` call sites in `src/cli.py`,
  `src/cli_workspace.py` (`--json`-aware failures), `src/cli_database.py`, `src/workspace/refresh.py`
  (injected classifier and per-job code), one `WatchlistNotFoundError` in `src/workspace/watchlists.py`,
  `docs/user/DATABASE.md`, a new `scripts/generate_schemas.py`, `schemas/` (failure, database report),
  and tests T18 to T20.
- **Branch:** `feat/swc-4a-failure-envelope`, from `main` after SWC.3 has merged.
- **Detail:** [SWC.1 design §13 and §18](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#13-failure-envelope-contract) and the
  [structured error reporting note](STRUCTURED_ERROR_REPORTING.md).

#### SWC.4b — Typed workspace documents

- **Problem:** the watchlist, delete-outcome, `runs list` and refresh-summary documents are built from
  hand-written dictionaries with no typed model or schema.
- **Decision:** one model per document, byte-identical to today's output apart from the changes listed in
  the design. Selections inside watchlist documents are typed by the `AnalysisSelection` union.
- **Scope:** `src/reporting/documents/{watchlist,runs,refresh}.py`, the JSON builders in
  `src/cli_workspace.py`, four schemas, and tests.
- **Branch:** `feat/swc-4b-workspace-documents`, from `main` after SWC.4a has merged.
- **Detail:** [SWC.1 design §13.6](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#136-every-json-document-is-typed).

#### SWC.4c — Typed strategy envelopes and replay dispatch

- **Problem:** report construction and stored-run replay retain per-method type dispatch, and the four
  strategy documents lack the typed envelope models IR.5 intended to add.
- **Decision:** typed envelope models back the real builders and are validated at the output boundary;
  the descriptor gains `json_envelope`; the projector table is keyed by the descriptor's identity and
  fails closed; the command-coverage test lands last, with no exemption list.
- **Scope:** `src/strategy_wiring.py`, `src/reporting/envelopes/<strategy>.py`,
  `src/reporting/json_documents.py`, `src/reporting/{analysis_runs,momentum,graham_number,graham_growth,fcf_earnings_growth}.py`,
  four schemas, and tests T9, T10, T20, T21 and T24 extended.
- **Branch:** `feat/swc-4c-strategy-json-envelopes`, from `main` after SWC.4b has merged.
- **Detail:** [SWC.1 design §6, §10 and §13.6](SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#10-conformance-tests-and-negative-control),
  [inventory disposition](#4-inventory-disposition) and
  [audited inventory](#appendix-a-proposal-inventory-verified-against-main).

### SWC.5 — Schemas, contributor guide, and final conformance

- **Problem:** consumers and contributors need discoverable schemas and a complete, tested account
  of which wiring is automatic and which work remains strategy-specific.
- **Decision:** verify the published schemas that SWC.4a to SWC.4c generate from typed models and document the approved
  strategy-addition workflow in one guide. Make the descriptor's authorization permanent before the
  temporary rule that permits it is removed. Challenge the structural checks with independent
  end-to-end review.
- **Scope:**
  - **One contributor guide.** Move `docs/project/ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md` to
    `docs/TOOL_DEVELOPMENT.md` and extend it with the strategy-addition workflow. Keep its existing
    content, update every link to it, and leave no second guide behind.
  - **Permanent authorization.** Amend `AGENTS.md` §3 so that the closed, statically declared
    strategy descriptor is permitted in its own right, with dynamic discovery, plugins,
    self-registration and factory hierarchies still prohibited. Step 3.5.1 removes `AGENTS.md` §0,
    which is the descriptor's only authorization today.
  - Verify that every descriptor has a current published schema (SWC.4a owns generation and the drift
    check), and verify conformance across all current strategies and generic consumers. Use an independent implementation review or a
    deliberately incomplete consumer fixture to prove that omission fails with a useful diagnostic.
  - Do not pull Step 3.5 strategy implementation into SWC; a later Piotroski addition may exercise
    the documented path when that strategy is implemented.
- **Branch:** `feat/swc-5-contributor-guide`, from `main` after SWC.4c has merged.
- **Detail:** [acceptance criteria](#7-acceptance-criteria) and [conformance design](#33-static-declaration-typing-and-conformance).

## 6. Scope limits

- Any formula, metric, classification, status or strategy-selection change.
- A common result supertype, dynamic discovery, analyzer self-registration, plugin system, or
  speculative factory hierarchy.
- Changes to Step 3.5 strategy calculations, financial fixtures, independent expected values,
  Golden truth, or ranking behavior.
- Rewriting presentation semantics or historical projection versions beyond changes specifically
  needed to type and dispatch their existing JSON envelopes.
- Storage migrations or backward-compatibility support for local persisted data during the
  consolidation period.
- A general purpose serialization framework beyond typed JSON envelopes and the schema outputs
  required here.

## 7. Acceptance criteria

- **Wiring completeness:** the approved source of truth for supported strategies is checked against
  every owned consumer: tool name and argument model, registration/handler, evaluation enum and
  argument mapping, fixture-backed composition, persisted selection parsing and config conversion,
  execution adapter and outcome classification, refresh dispatch, run method/result/config versions,
  evidence encode/decode, report and replay dispatch, typed JSON envelope, and published schema.
  Adding a supported strategy while deliberately omitting any one required consumer registration or
  dispatch must fail a focused conformance test with the missing wiring point identified. This
  directly covers the proposal's “forgotten branch” failure; a test that only checks descriptor
  construction is insufficient.
- **Static strategy set:** no runtime discovery, auto-registration, plugin loader, or speculative
  factory hierarchy. Each analyzer keeps its own typed config and complete result evidence type.
- **Strategy ownership:** each strategy keeps its own `AnalysisSelection` and
  `AnalysisToolArguments`/`NativeEvidence` union members where applicable, plus its codec, adapter
  behavior, outcome classification, and presentation/projection semantics. The descriptor only
  routes generic infrastructure to those contracts.
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
- **Contributor guide:** `docs/TOOL_DEVELOPMENT.md` is the only contributor guide for adding a
  strategy. It replaces `docs/project/ANALYSIS_STRATEGY_CONTRIBUTOR_GUIDE.md`, keeps that guide's
  content, and identifies what the shared wiring owns and what remains strategy-specific, including
  calculator, source fixtures, presentation semantics and Golden cases. No link to the old path
  remains.
- **Fail-closed dispatch:** no generic consumer treats one strategy as the default. Undeclared
  evidence and undeclared stored runs are rejected, and tests prove it.
- **Lasting authorization:** `AGENTS.md` §3 permits the closed static descriptor without relying on
  §0, so the descriptor remains authorized when Step 3.5.1 removes §0.
- **Quality gate:** the complete managed quality gate passes at the end of every implementation
  slice, including ≥85% coverage and new meaningful branch coverage; any new deterministic tests
  make no real provider, network or LLM calls. The final link check passes.
- **Step 3.5 readiness:** Piotroski can be added using the documented contract without an
  unplanned per-consumer dispatch edit, or the relevant conformance test fails clearly and points
  to the omitted wiring contract.

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
not the code wiring observations. SWC.1 re-verified the inventory at `247ecdf`.

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
| One workspace execution adapter per strategy | Still present | `src/workspace/momentum_execution.py`: `MomentumCapture`, `run_momentum`; `graham_number_execution.py`: `GrahamNumberCapture`, `execute_graham_number`; `graham_growth_execution.py`: `GrahamGrowthCapture`, `execute_graham_growth`; `fcf_growth_execution.py`: `FCFGrowthCapture`, `execute_fcf_growth` | Files also retain strategy-specific outcome classification where applicable. Momentum has no native failure status classifier. |
| `NativeEvidence` result union | Still present | `src/workspace/execution.py`: `NativeEvidence` | Four heterogeneous native results remain explicitly unioned. |
| Per-strategy capture normalizers | Still present | `src/workspace/execution.py`: `from_momentum_capture`, `from_graham_number_capture`, `from_graham_growth_capture`, `from_fcf_growth_capture` | Still normalize strategy capture fields into `ExecutionCapture`. |
| `_METHOD_VERSIONS` metadata | Still present | `src/workspace/execution.py`: `_METHOD_VERSIONS` | One pair per method; IR changed persisted envelope versions and added `config_schema_version` alignment. |
| Refresh `isinstance` dispatch | Changed | `src/cli_workspace.py`: `_refresh_executor` | Still four explicit selection branches; current function is at a different location and composes per-method adapters. |
| `encode_evidence` isinstance chain | Changed | `src/workspace/codecs.py`: `encode_evidence` | FCF/Graham branches remain; Momentum is now the unconditional fallback rather than an explicit final branch, so unknown evidence is routed as Momentum. This is the live fall-through. |
| Decoder version membership and expected versions | Changed | `src/workspace/codecs.py`: `_EXPECTED_VERSIONS`, `decode_evidence` | Now one mapping entry stores `(config_schema_version, method_version, result_schema_version)`; `decode_evidence` validates run-schema, codec and projection versions too. |
| Per-method `decode_evidence` dispatch | Changed | `src/workspace/codecs.py`: `decode_evidence` | Explicit branches remain for FCF, Graham Growth and Graham Number, with Momentum as the final branch; ticker identity is checked per result shape. An undeclared pair is already rejected earlier by the version-table lookup, so only the structure, not the behavior, is a default branch. |
| Momentum instrument-profile composition | Still present | `src/cli.py`: `momentum` command (`--save-run` and default branches); `src/cli_workspace.py`: `_execute_momentum` | Three independent inline copies of one composition pattern; Graham and FCF Growth already share `compose_graham_profile`. Owned by SWC.3 ([Momentum profile composition note](MOMENTUM_PROFILE_COMPOSITION_DEDUPLICATION.md)). |
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
| Alias vocabulary | `src/workspace/method_aliases.py`; `src/cli_workspace.py` alias uses; `src/data/repositories/watchlists.py` alias lookup | SWC.3 |
| Alias membership and a final unconditional Momentum branch | `src/workspace/requests.py`: `parse_selection` | SWC.3 |
| Identifier literals in failure calls and JSON builders | `src/cli.py`: six `execution_errors(analysis=, method=)` calls; `src/reporting/{momentum,graham_number,graham_growth}.py` | SWC.4a (`cli.py` calls), SWC.4c (builders) |
| Strategy name tested inside generic failure handling | `src/cli_support.py`: `analysis == "momentum"` | SWC.4a |
| A second `NativeEvidence`-shaped union, and an FCF default branch | `src/evaluation/runner.py`: `NativeAnalysisResult`, `_native_result`, `_native_status` | SWC.2 |
| An FCF default branch in the fixture capability check | `src/evaluation/composition.py`: `_require_tool_evidence` | SWC.2 |
| A one-member per-strategy name enum with no reader | `src/core/constants.py`: `AnalysisType` | SWC.2 (deleted) |
| An unconditional FCF return after a chain of method tests | `src/cli_workspace.py`: `_build_selection` | SWC.3 |
| A probe for a field every selection defines | `src/workspace/execution.py`: `getattr(selection, "as_of", None)` | SWC.3 |
| Tool descriptions, schemas and parser registry keyed by tool name | `src/evaluation/ollama_runner.py`: `_TOOL_DESCRIPTIONS`, `_tool_schemas_json`, `_tool_parser` | SWC.2 |

## Appendix B: Decision records and history

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
handlers, executors and projectors stay in consumer-owned keyed tables because a wider descriptor
creates import cycles; schema generation is owned by SWC.4a; every slice branches from `main`
after its predecessor merges. No IR.2 contract change is required. The project owner's review of
the design then decided that every `--json` document is typed, that per-job refresh failures carry
a `reason_code`, that `DatabaseMaintenanceReport` uses the envelope's field names, and that moved
symbols keep no compatibility re-export; SWC.4 was split into SWC.4a to SWC.4c to keep each slice
reviewable.
