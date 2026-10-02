# SWC — Strategy Wiring Consolidation: Contract and Slice Plan

Consolidates repeated strategy wiring before Step 3.5 adds seven analyzers, and completes the
typed JSON envelope and schema scope moved from IR.5. Placement among the milestone work packages
is in the [milestone plan](IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **What this work does:** reduce repeated per-strategy wiring across orchestration, workspace
  selection and execution, evidence codecs, reporting, CLI integration and deterministic
  evaluation; give each strategy's JSON output a typed contract and generated schema; document the
  resulting contributor workflow.
- **What it does not do:** change analyzer formulas, classifications, result semantics, or the
  shared `BaseAnalyzer[ConfigT, ResultT]` invocation envelope; add discovery, plugins, or a
  speculative framework. Full list: [Scope limits](#6-scope-limits).
- **Decision required before implementation:** the proposal's descriptor list has registry-like
  behavior, while IR.2 explicitly says “no generic result supertype, registry or factory.” The
  conflict and two possible resolutions are in [§3](#3-design-conflict-requiring-a-decision).
- **Rules every slice follows:** preserve strategy-owned config and result types, retain explicit
  provenance and outcomes, bump affected stored-shape versions without migrations during the
  consolidation period, and run the complete managed gate at each slice end. Each next slice waits
  for explicit project-owner authorization.
- **Where detail lives:** inventory verification is in [Appendix A](#appendix-a-proposal-inventory-verified-against-main); design decisions and history belong in [Appendix B](#appendix-b-decision-records-and-history).

## 2. Sequence and status

Every slice ends with the complete managed quality gate. The next slice begins only after explicit
project-owner authorization. Any slice that changes executable code, tests, or parsed configuration
uses the managed wrapper from `AGENTS.md`; prose-only documentation changes follow the repository's
document-link check and applicable documentation checks.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| SWC.1 | [Resolve the wiring contract and prove inventory coverage](#swc1--wiring-contract-and-coverage) | Planned | |
| SWC.2 | [Orchestration and evaluation wiring](#swc2--orchestration-and-evaluation-wiring) | Planned | |
| SWC.3 | [Workspace selections, execution and codecs](#swc3--workspace-selection-execution-and-codecs) | Planned | |
| SWC.4 | [Reporting and typed JSON envelopes](#swc4--reporting-and-typed-json-envelopes) | Planned | |
| SWC.5 | [Generated schemas, contributor guide and final conformance](#swc5--generated-schemas-contributor-guide-and-final-conformance) | Planned | |

## 3. Design conflict requiring a decision

The accepted SWC proposal §4 illustrates a `StrategyDescriptor[ConfigT, ResultT]` and a central
`STRATEGIES` tuple, then proposes using that tuple to replace per-strategy dispatch and lookup
structures. That is registry-like in purpose and operation. IR.2's accepted contract says “no
generic result supertype, registry or factory,” while `AGENTS.md` §0 temporarily permits an explicit,
statically declared list with shared generic wiring, and §9 says not to build registries, plugin
loaders, or factories speculatively. Both rules apply: the §0 permission does not silently erase
IR.2's narrower contract, and a descriptor cannot be treated as harmless merely by avoiding the word
“registry.”

**Project-owner decision required before SWC.1 implementation.** The proposed choices are:

1. **Narrow static descriptor exception (recommended for decision):** explicitly amend the IR.2
   contract for SWC to allow one closed, source-declared descriptor list solely for eliminating the
   audited duplicated wiring. Keep strategy configs/results heterogeneous; use no discovery,
   self-registration, plugin API, factory hierarchy, or generic result type. Record the exception
   in the SWC decision appendix and, if the project owner approves, make any corresponding planning
   update required by the IR.2 contract's change-control rule.
2. **No descriptor registry:** retain explicit per-layer declarations and dispatch, but add static
   completeness checks generated from an independently maintained strategy inventory. This avoids
   changing IR.2's no-registry rule but may retain duplicated declarations and needs a concrete
   design showing that it actually prevents forgotten branches.

This plan does not choose between the options. SWC.1 cannot be authorized for implementation until
the project owner decides. If option 2 is selected, SWC.1 must demonstrate that its independent
inventory catches an omitted consumer branch without merely recreating the same registry under a
different name.

## 4. The slices

### SWC.1 — Wiring contract and coverage

- **Problem:** the original inventory predates IR.2–IR.8, omits some current dispatch sites, and
  describes a descriptor design that conflicts with the accepted IR.2 boundary.
- **Decision:** settle the design conflict above before implementation; establish one verified,
  symbol-level wiring inventory and an executable conformance strategy that can detect an omitted
  strategy at every owned consumer.
- **Scope:** approve the descriptor exception or select a non-registry alternative; update this
  contract as required by that decision; specify how the declared supported strategy set is compared
  with tool arguments, evaluation, selection, execution, version metadata, codecs, replay and schema
  outputs. No production source changes are part of this planning slice.
- **Branch:** the planning contract is prepared on `docs/swc-contract-plan` from `main` after PR #53
  merged. The future implementation slice branches follow the accepted decision and the milestone's
  per-slice review practice.
- **Detail:** [design conflict](#3-design-conflict-requiring-a-decision) and [verified inventory](#appendix-a-proposal-inventory-verified-against-main).

### SWC.2 — Orchestration and evaluation wiring

- **Problem:** each strategy currently has its own tool-argument model, handler, dependency fields,
  registration call and evaluation argument/tool mapping; an omitted branch can silently remove a
  strategy from production or deterministic evaluation.
- **Decision:** use only the approved SWC.1 representation to remove repeated invocation plumbing;
  preserve each analyzer's own typed config/result and `run_analysis(ticker, config, context)` call.
- **Scope:** `src/orchestrator/analysis_tools.py` and the relevant `src/evaluation/` composition,
  runner and model modules, including every strict argument-to-tool mapping and fixture-backed
  dependency composition identified in Appendix A. Do not change evaluation fixture truth, scoring,
  formula semantics or external-call behavior.
- **Branch:** one implementation branch for this slice, from the post-acceptance base selected by
  the approved implementation plan.
- **Detail:** [verified inventory](#appendix-a-proposal-inventory-verified-against-main).

### SWC.3 — Workspace selection, execution and codecs

- **Problem:** persisted selections, selection-to-config conversion, method adapters, native result
  unions, version metadata, refresh dispatch and evidence codecs each repeat strategy-specific
  wiring. Version tuples must stay aligned across capture, storage and decoding.
- **Decision:** consolidate only the dispatch and metadata duplication allowed by SWC.1; retain
  explicit typed selection/config/result boundaries and each strategy's own evidence codec. Any
  stored-shape change increments its relevant version; no migration or compatibility code is added
  during the consolidation period.
- **Scope:** `src/workspace/requests.py`, strategy execution adapters, `src/workspace/execution.py`,
  `src/workspace/codecs.py`, per-strategy codec modules, `src/cli_workspace.py`, and focused tests.
  Preserve `AnalysisRun` replay guarantees and refresh isolation. No financial or outcome
  classification changes.
- **Branch:** one implementation branch for this slice, with its scope and review gate recorded in
  the implementation record.
- **Detail:** [verified inventory](#appendix-a-proposal-inventory-verified-against-main).

### SWC.4 — Reporting and typed JSON envelopes

- **Problem:** report construction and stored-run replay retain per-method type dispatch, while JSON
  presentation payloads lack the typed envelope models that IR.5 intended to add.
- **Decision:** introduce real typed models that back the existing JSON payload builders and
  preserve their investor-visible meaning. A one-time schema snapshot detached from those models is
  not sufficient. Schema publication details are proposed in [§5](#5-ir5-typed-json-envelopes-and-schemas).
- **Scope:** `src/reporting/analysis_runs.py`, strategy presentation modules where dispatch changes
  are necessary, and the JSON-mode builders and tests. Include both direct/report rendering and the
  stored Analysis Run projection path. Keep `projection_version`, method version and result-schema
  version distinct; do not silently reinterpret historical runs.
- **Branch:** one implementation branch for this slice, based on the approved SWC.1 design.
- **Detail:** [verified inventory](#appendix-a-proposal-inventory-verified-against-main) and
  [IR.5 scope](#5-ir5-typed-json-envelopes-and-schemas).

### SWC.5 — Generated schemas, contributor guide and final conformance

- **Problem:** consumers and contributors need discoverable schemas and a complete, tested account
  of which wiring is automatic and which work remains strategy-specific.
- **Decision:** generate the published schemas from the typed models and document the approved
  strategy-addition workflow, then use an independent end-to-end wiring audit to challenge the
  completeness checks.
- **Scope:** add the developer guide proposed as `docs/TOOL_DEVELOPMENT.md`, link it from
  `docs/project/README.md`, generate/check schemas using the approach selected in §5, and verify
  conformance across all current strategies. Use a representative new strategy, preferably
  Piotroski from Step 3.5, as a wiring-completeness exercise only if it can be done without pulling
  Step 3.5 implementation into SWC; otherwise use a deliberately minimal test fixture/type to
  demonstrate the omitted-branch failure.
- **Branch:** one implementation branch for this slice, with generated schema updates reviewed
  alongside their source models.
- **Detail:** [acceptance criteria](#7-acceptance-criteria).

## 5. IR.5: typed JSON envelopes and schemas

IR.5's moved scope is part of SWC: define typed envelope models backing `--json` payloads and publish
generated JSON Schemas. Models must describe actual runtime output, retain each strategy's distinct
evidence shape, reject malformed output at the appropriate boundary, and stay aligned with the
documented JSON contract. Do not add a generic result supertype to obtain a uniform schema.

Two questions travelled from IR.5. Proposed answers for project-owner review:

- **Schema-generation approach:** generate JSON Schema directly from the typed Pydantic v2 envelope
  models using their supported schema API (`model_json_schema` or `TypeAdapter.json_schema` as
  appropriate). Provide a deterministic repository command and a check mode that fails on drift;
  do not hand-maintain schemas or take a disconnected one-time snapshot. Confirm the precise API and
  generation invocation against the final model form during implementation planning.
- **Checked-in `schemas/` directory:** yes. Check in generated schemas in a clearly named
  `schemas/` directory, version or identify each public envelope schema, and require regeneration
  drift checks in the quality gate. This makes the consumer contract reviewable and distributable
  without requiring consumers to import the Python package. The checked-in files remain generated
  outputs; the typed models are authoritative.

These are proposed resolutions, not implementation authorization. If approved, the exact filenames,
schema identifiers and whether schemas are per-strategy or a discriminated top-level envelope are
settled in SWC.1/SWC.4 detail before code is written.

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
- **Invocation contract:** production callers continue to invoke analyzers only through
  `BaseAnalyzer[ConfigT, ResultT].run_analysis(ticker, config, context)` with dependencies injected
  at construction and cross-cutting concerns carried in `AnalysisContext`.
- **Outcome and provenance:** metrics remain `MetricResult`; unavailable and inapplicable states
  remain explicit; provenance is retained. No silent defaults, `NaN` or `Inf` are introduced.
- **JSON contract:** typed models back the real JSON builders; generated schemas correspond to the
  models and a drift check detects stale checked-in output. Existing payload meaning and projection
  versioning remain explicit.
- **Persistence:** any changed stored config/evidence/result shape bumps the relevant version. No
  migration or compatibility layer is added during this period.
- **No semantic change:** no analyzer formula, classification, result meaning, or evaluation
  expectation changes. Report/CLI output may change only where specifically identified and approved
  in the slice contract.
- **Contributor guide:** `docs/TOOL_DEVELOPMENT.md` identifies what the shared wiring owns and what
  remains strategy-specific, including calculator, source fixtures, presentation semantics and
  Golden cases.
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
contract. SWC follows IR and precedes R3, PKG and Step 3.5 as recorded in the milestone plan.

The original proposal's claims are not taken as a current inventory: Appendix A records a fresh
symbol-level comparison against `main` at `8edbff4` (2026-10-01), after IR.2–IR.8 and PR #53.

---

## Appendix A: Proposal inventory verified against main

Baseline: `main` at `8edbff4` (`Add sequence table quality check`, 2026-10-01), which includes PR
#53's ESC-E renewal and PR #52's revised Step 3.5 contract. “Still present” means the named
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
| `encode_evidence` isinstance chain | Changed | `src/workspace/codecs.py`: `encode_evidence` | FCF/Graham branches remain; Momentum is now the unconditional fallback rather than an explicit final branch, so unknown evidence could be routed as Momentum. |
| Decoder version membership and expected versions | Changed | `src/workspace/codecs.py`: `_EXPECTED_VERSIONS`, `decode_evidence` | Now one mapping entry stores `(config_schema_version, method_version, result_schema_version)`; `decode_evidence` validates run-schema, codec and projection versions too. |
| Per-method `decode_evidence` dispatch | Changed | `src/workspace/codecs.py`: `decode_evidence` | Explicit branches remain for FCF, Graham Growth and Graham Number, with Momentum as fallback; ticker identity is checked per result shape. |
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

## Appendix B: Decision records and history

### B.1 IR.5 scope carried into SWC

Typed JSON envelope models backing the `--json` payloads and generated JSON Schemas remain in scope.
The IR.5 questions are carried forward with proposals in [§5](#5-ir5-typed-json-envelopes-and-schemas):
generate from the runtime typed models and check generated schema files into a discoverable
`schemas/` directory with drift verification. These proposals require project-owner review before
implementation.

### B.2 Descriptor and IR.2 contract tension

The proposal's descriptor tuple was illustrative and explicitly deferred typing design; IR.2 later
landed an accepted “no generic result supertype, registry or factory” constraint. SWC planning has
therefore surfaced the tension instead of treating §0's temporary allowance as automatic approval
for the descriptor shape. The project owner must select or revise the option in [§3](#3-design-conflict-requiring-a-decision)
before implementation sequencing is authorized.
