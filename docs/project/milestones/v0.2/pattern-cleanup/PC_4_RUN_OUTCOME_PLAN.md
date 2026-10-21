# PC.4 — One Shared Mapping from Statuses to a Run Outcome: Slice Plan

Gives the run outcome one rule, `RunOutcome.from_status`, and one exit-code rule, `exit_code_of`, so that no strategy
decides an outcome and no Step 3.5 strategy copies a per-strategy mapping
([#111](https://github.com/PeterPontbriand/investment-analysis-engine/issues/111)).

Parent plan: [PC contract and slice plan](PC_CONTRACT_AND_SLICE_PLAN.md#pc4--one-shared-mapping-from-statuses-to-a-run-outcome).

## 1. At a glance

- **What this slice does:** a strategy reports one fact, its native status (`CalculationStatus | None`). The type
  `RunOutcome` turns that status into the workspace outcome, `ExecutionCapture` derives the outcome, the failure code
  and the kept provider failure from it, and one function, `exit_code_of`, turns the outcome into a command's exit
  code. The three `classify_*_outcome` functions, the `outcome` field of each strategy's capture type, the three
  `capture_provider_failure` and three `_failure_code` functions, and Momentum's fixed `RunOutcome.COMPLETED` are
  removed.
- **What it is not:** a formula or classification change, a change to any command's exit code, standard-stream choice
  or rendered output, a stored-shape change, or a change to a recorded telemetry value. The one change in a mapping is
  in a path no calculation produces ([Decision 6](#unreachable-states)).
- **Rules it follows:** a consolidation package under `AGENTS.md` §0. Each guard is proved to bite on a deliberate
  breakage that is then reverted. The complete managed gate, with the extra interpreter, runs on the final commit.
- **Decisions:** approved by the project owner on 2026-10-19 and amended on 2026-10-21
  ([A.1](#a1-approved-decisions-2026-10-19-amended-2026-10-21)).

## 2. Sequence and status

| Unit | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| Slice plan | [This document](#3-the-work-units) and the parent-plan updates | In progress | |
| Typed native status | [Native status as a `CalculationStatus`](#typed-native-status) | Planned | |
| The rule | [`RunOutcome.from_status`, `ExecutionCapture`, removals, guards](#the-rule-and-the-capture) | Planned | |
| Exit codes | [`exit_code_of` and the four commands](#exit-codes) | Planned | |
| Documents | [Contributor guide, Step 3.5 documents](#documents) | Planned | |
| Completion | [Plan rows and the final gate](#completion) | Planned | |

## 3. The work units

### Typed native status

- **Problem:** `StrategyBehavior.native_status` returns a string, so the status a strategy reports cannot feed a
  mapping. Graham Number and Graham Growth read `result.result.status` in their codec while `analysis.native_status`
  (the assembly's status, or the calculation's when the assembly succeeded) already exists beside it.
- **Decision:** `StrategyBehavior.native_status` and `native_status_of` return `CalculationStatus | None`. Graham
  Number and Graham Growth return `analysis.native_status`; FCF Growth returns `result.execution_status`; Momentum
  returns `None`. The evaluation runner records `.value`, or `None`, at its one call site, so the recorded telemetry
  value is the same. Where the assembly is not `ok`, a Graham result is built with the assembly's own status, so
  `analysis.native_status` and `result.result.status` are equal in every state the services produce.
- **Scope:** the changes in the table below.
- **Branch:** `refactor/pc-4-run-outcome`
- **Detail:** the table below.

| File | Change |
| :--- | :--- |
| `investment_analysis_engine/strategy_wiring.py` | `native_status_of` (protocol and `StrategyBehavior`) and the `native_status` member return `CalculationStatus \| None`; import `CalculationStatus` |
| `investment_analysis_engine/strategies/graham_number/codec.py` | `graham_number_native_status` returns `result.native_status` (type `CalculationStatus`) |
| `investment_analysis_engine/strategies/graham_growth/codec.py` | `graham_growth_native_status` returns `result.native_status` |
| `investment_analysis_engine/strategies/fcf_growth/codec.py` | `fcf_growth_native_status` returns `result.execution_status` |
| `investment_analysis_engine/strategies/momentum/codec.py` | `momentum_native_status` returns `None`, annotated `CalculationStatus \| None` through the shared member type |
| `investment_analysis_engine/evaluation/runner.py` | `_native_status` returns `str \| None`: `.value` of the status, or `None` |
| `scripts/strategy_templates/codec.py.tmpl` | `${module}_native_status` returns `CalculationStatus \| None`; docstring says the strategy reports its status and the shared rule maps it |
| `scripts/strategy_conformance.py` | the `native_status_of` probes accept the typed value; the `ExecutionCapture` it builds takes a native status, not an outcome |
| `tests/specimen/codec.py`, `tests/specimen/behavior.py`, `tests/scripts/generator_fills/codec.py.fill` | the same typed return |
| `tests/test_strategy_wiring.py` | `test_native_status_comes_from_each_strategys_own_function` compares the typed statuses |

### The rule and the capture

- **Problem:** each strategy decides an outcome in its own `classify_*_outcome`, and `ExecutionCapture` trusts the
  strategy to pass a matching code and provider failure and rejects a mismatch in `__post_init__`. ESC-29 was a slip in
  one of the three copies; every Step 3.5 strategy would write another.
- **Decision:**
  - **The rule, on the type.** `RunOutcome.from_status(status: CalculationStatus | None) -> RunOutcome` in
    `investment_analysis_engine/analysis/run_models.py`. It replaces the `run_outcome_of` named in the parent plan.

    | Status | Outcome |
    | :--- | :--- |
    | `ok` | `completed` |
    | `not_applicable` | `not_applicable` |
    | `input_unavailable` | `unavailable` |
    | `invalid_input` | `failed` |
    | `provider_error` | `failed` |
    | `None` | `completed` |

    `None` is Momentum's place in the rule. A.8 of the Step 3.5 contract may later change Momentum's status, but not
    the rule.
  - **What `ExecutionCapture` takes and derives.** It takes the strategy's native evidence and profile, its native
    status, its presentation inputs and the provider failure it recorded, if any. It derives `outcome` through
    `RunOutcome.from_status`, `failure_reason_code` through `failure_reason_code` of
    `core/failure_classification.py` (set only when the outcome is failed), and keeps `provider_failure` only when the
    outcome is failed. Derivation replaces the invariant checks of `__post_init__`.
  - **Each `from_*_capture` passes the facts above and nothing else.** The commands read the provider failure from the
    normalized capture.
- **Scope:** the changes in the tables below.
- **Branch:** `refactor/pc-4-run-outcome`
- **Detail:** the tables below.

#### Functions, fields and call sites that change

| File | Change |
| :--- | :--- |
| `investment_analysis_engine/analysis/run_models.py` | add `RunOutcome.from_status` |
| `investment_analysis_engine/workspace/capture.py` | `ExecutionCapture` fields: `native_evidence`, `profile`, `native_status`, `presentation_inputs`, `provider_failure` are given; `outcome` and `failure_reason_code` are `init=False` and derived in `__post_init__`; `provider_failure` is cleared unless the outcome is failed. The two `ValueError` checks are removed |
| `investment_analysis_engine/strategies/graham_number/execution.py` | remove `classify_graham_number_outcome`, `capture_provider_failure`, `_failure_code` and the `outcome` field of `GrahamNumberCapture`; `execute_graham_number` builds the capture without an outcome; `from_graham_number_capture` passes `analysis.native_status` and `provider_failure_of((analysis.assembly.provider_failure,))`; the module docstring no longer describes a mapping |
| `investment_analysis_engine/strategies/graham_growth/execution.py` | the same for Graham Growth |
| `investment_analysis_engine/strategies/fcf_growth/execution.py` | the same; the native status is `result.execution_status` and the recorded failure is `provider_failure_of((result.provider_failure,))` |
| `investment_analysis_engine/strategies/momentum/execution.py` | remove `RunOutcome.COMPLETED` and the `RunOutcome` import; `from_momentum_capture` passes `native_status=None` |
| `investment_analysis_engine/strategies/graham_number/cli.py`, `graham_growth/cli.py`, `fcf_growth/cli.py` | read the provider failure from the normalized capture (`from_*_capture(capture).provider_failure`) in place of `capture_provider_failure`; imports follow |
| `scripts/strategy_templates/execution.py.tmpl` | drop `outcome: RunOutcome` and the `RunOutcome` import; `from_${module}_capture` is an unfilled stub that names the facts it passes |
| `scripts/strategy_conformance.py` | `_capture_of` builds `ExecutionCapture(native_evidence=result, profile=None, native_status=None)` |
| `tests/specimen/execution.py`, `tests/specimen/cli.py`, `tests/specimen/site_context.py`, `tests/scripts/generator_fills/execution.py.fill` | the specimen and the generator's fill follow the same shape |

#### Unreachable states

The shared rule maps one native status, where the two Graham strategies mapped an assembly status and then a
calculation status. The mapping agrees in every state the services produce. It differs in three states that no
calculation produces:

| State | Today | After |
| :--- | :--- | :--- |
| Graham Growth, assembly `ok`, calculation `not_applicable` | failed | not applicable |
| Graham Number and Graham Growth, assembly `ok`, calculation `input_unavailable` | failed | unavailable |
| Graham Number and Graham Growth, assembly `ok`, calculation `provider_error` | failed | failed (no change) |

`compute_graham_number` returns only `ok`, `not_applicable` and `invalid_input`, and `compute_graham_growth_value`
returns only `ok` and `invalid_input`, so the first two states cannot occur; ESC-29 settled the outcome of the first.
Neither is a classification change. The slice pins the first through `RunOutcome.from_status`.

#### Tests and guards

| Test | Where | What it asserts |
| :--- | :--- | :--- |
| `test_run_outcome_from_status_is_total_and_matches_the_table` | `tests/test_documented_conventions.py` | `RunOutcome.from_status` covers every `CalculationStatus` member and `None`, with the table above; a new status without an entry fails |
| `test_no_strategy_module_or_template_names_a_run_outcome_member` | the same | An AST scan of every module under `investment_analysis_engine/strategies/` and every file under `scripts/strategy_templates/` fails on an attribute access to `COMPLETED`, `UNAVAILABLE`, `NOT_APPLICABLE` or `FAILED` on `RunOutcome`, and names the file and line. It parses a `.tmpl` file after substituting its placeholders |
| `test_the_outcome_scan_reports_a_member_and_accepts_the_rest` | the same | The scan itself, on text built for the test |
| `test_a_not_applicable_calculation_is_a_not_applicable_run_for_graham_growth` | `tests/workspace/test_graham_growth_execution.py` | The unreachable state above maps to `NOT_APPLICABLE` through `RunOutcome.from_status`, and `from_graham_growth_capture` derives the same outcome with no failure code |
| `test_graham_number_outcome_follows_the_native_status` and the Graham Growth and FCF Growth equivalents | the strategies' execution tests | Replace the `classify_*` tests: the rows of today's tests that are reachable, asserted on `from_*_capture(...).outcome` |
| `test_execution_capture_derives_outcome_code_and_provider_failure` | `tests/workspace/test_capture.py` | For each status: the outcome; the failure code only for a failed outcome (the mapped provider code, or `invalid_input`); the provider failure kept only for a failed outcome |
| `test_exit_code_of_is_one_exactly_for_unavailable_and_failed` | `tests/test_cli_support.py` | One assertion per `RunOutcome` member |

### Exit codes

- **Problem:** each command computes its own exit code: the Graham commands from the calculation status (and 1 from
  their failure-output function), FCF Growth from the execution status, Momentum not at all.
- **Decision:** `exit_code_of(outcome: RunOutcome) -> int` in `investment_analysis_engine/cli_support.py` returns 1
  exactly for unavailable and failed, and 0 otherwise. The four strategy commands take their exit code from it, applied
  to the normalized capture's outcome. Rendering, and the choice between standard output and standard error, stay as
  they are. The CLI template's command body is an unfilled stub, so the contributor guide names `exit_code_of`.
- **Scope:** `cli_support.py`, the four `strategies/*/cli.py` files.
- **Branch:** `refactor/pc-4-run-outcome`
- **Detail:** the tables below.

| File | Change |
| :--- | :--- |
| `investment_analysis_engine/cli_support.py` | add `exit_code_of` |
| `investment_analysis_engine/strategies/graham_number/cli.py` | `_run_graham_number` normalizes the capture once and returns `exit_code_of(outcome)`; `_number_failure_output` returns the rendered text only |
| `investment_analysis_engine/strategies/graham_growth/cli.py` | the same for `_run_graham_growth` and `_growth_failure_output` |
| `investment_analysis_engine/strategies/fcf_growth/cli.py` | `exit_code = exit_code_of(outcome)` replaces the status test |
| `investment_analysis_engine/strategies/momentum/cli.py` | the command normalizes its capture and raises `typer.Exit` when `exit_code_of(outcome)` is non-zero (never, today) |

#### Exit codes per command

"Today" is read from the code at `6bf7677`; "after" follows from the table. No exit code of a reachable state changes.
Each Graham row is the same for `graham-number` and `graham-growth`, and its first column is the native status
(`analysis.native_status`).

| Command | Native status | Outcome today | Outcome after | Exit today | Exit after |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `graham-number`, `graham-growth` | `ok` | completed | completed | 0 | 0 |
| the same | `not_applicable` (assembly: an ETF; calculation: Graham Number only) | not applicable | not applicable | 0 | 0 |
| the same | `input_unavailable` (assembly) | unavailable | unavailable | 1 | 1 |
| the same | `invalid_input` (assembly or calculation) | failed | failed | 1 | 1 |
| the same | `provider_error` (assembly) | failed | failed | 1 | 1 |
| `fcf-growth` | `ok` | completed | completed | 0 | 0 |
| the same | `not_applicable` | not applicable | not applicable | 0 | 0 |
| the same | `input_unavailable` | unavailable | unavailable | 1 | 1 |
| the same | `invalid_input` | failed | failed | 1 | 1 |
| the same | `provider_error` | failed | failed | 1 | 1 |
| `momentum` | `None` | completed | completed | 0 | 0 |

The unreachable states of [Unreachable states](#unreachable-states) are outside this table: an assembly `ok` with a
calculation `input_unavailable` or `provider_error` exits 0 today and would exit 1 after, and no calculation produces
either.

### Documents

- **Decision:** the documents that said an adapter maps a status to an outcome say that the strategy reports its status
  and the shared rule produces the outcome.
- **Scope:**
  - `docs/TOOL_DEVELOPMENT.md`: the `codec` and `execution` rows of the edit-site table, the `cli` row (it names
    `exit_code_of`), steps 12 and 14 of the FCF walkthrough, and the paragraph on `execute_fcf_growth`. The table is
    generated from `scripts/strategy_sites.toml`, so the three rows change there and the guide is regenerated with
    `uv run python -m scripts.generate_strategy_docs`.
  - `STEP_3_5_SHARED_DEFINITIONS.md` §2, "Result-level status".
  - The Step 3.5 contract: A.9 and its pre-3.5.0 decision list record that PC.4 implemented the rule; the rest of the
    appendix stays verbatim.
  - The PC plan: PC.4's Decision, Branch and Detail, and appendix record A.5.
- **Branch:** `refactor/pc-4-run-outcome`
- **Detail:** the PC plan updates are in the first commit; the rest follow the code.

### Completion

- In the [PC plan](PC_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status), PC.4 is Complete with its date.
- In the [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status), row `14B` is Complete with the date and row 15
  (Step 3.5) is Next; rows keep sequence-table order.
- `AGENTS.md` §0 stays; slice 3.5.0 removes it.
- The complete managed gate runs on the final commit, with the extra interpreter.

## 4. Scope limits

- No formula, classification or calculation result changes. No command's exit code, standard-stream choice or rendered
  output changes. No stored shape, published schema, golden or evaluation expectation, or recorded telemetry value
  changes.
- The work stops for the project owner when: a command needs a provider failure from somewhere other than the
  normalized capture; `RunOutcome.from_status` cannot live in `analysis/run_models.py` without breaking the
  package-dependency check; or the generator end-to-end test exceeds its 2-minute budget on either Python version.

## 5. Acceptance criteria

- `RunOutcome.from_status` is total over `CalculationStatus` and `None`, and no module under
  `investment_analysis_engine/strategies/` or file under `scripts/strategy_templates/` names a `RunOutcome` member.
- `classify_graham_number_outcome`, `classify_graham_growth_outcome`, `classify_fcf_growth_outcome`, the three
  `capture_provider_failure` and the three `_failure_code` functions, and the `outcome` field of the three capture
  types do not exist.
- `ExecutionCapture` derives its outcome, failure code and kept provider failure; it has no invariant check that a
  strategy could trip.
- Every strategy command takes its exit code from `exit_code_of`; the table above holds.
- Both guards fail on their deliberate breakages (proved and reverted, and reported with the slice).
- The complete managed gate passes with the extra interpreter.

## 6. Background: origin of this slice

[Appendix A.9 of the Step 3.5 contract](../step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a9-one-shared-mapping-from-statuses-to-a-run-outcome-question-from-esc-29-2026-10-10)
raised the question after ESC-29, a slip in one of three per-strategy mappings. The project owner decided yes on
2026-10-19 and amended the design on 2026-10-21. See [PC §6](PC_CONTRACT_AND_SLICE_PLAN.md#6-background-origin-of-this-work-package).

## Appendix A: Decision records

### A.1 Approved decisions (2026-10-19, amended 2026-10-21)

Decisions of the project owner; the 2026-10-21 amendments are marked.

- **The rule:** `RunOutcome.from_status(status: CalculationStatus | None) -> RunOutcome`, total, with `None` as
  Momentum's place (amended: a class method, replacing `run_outcome_of`).
- **Native status (amended):** `StrategyBehavior.native_status` and `native_status_of` return
  `CalculationStatus | None`; each strategy's codec function provides it; the evaluation runner records `.value` or
  `None`; the generator template and the conformance script follow.
- **`ExecutionCapture` (amended):** built from native evidence, profile, native status, presentation inputs and the
  recorded provider failure; derives outcome, failure code (failed only) and provider failure (failed only).
- **Removals (amended):** the three `classify_*_outcome` functions, the `outcome` field of each capture type, the
  three `capture_provider_failure` and three `_failure_code` functions, and Momentum's fixed `COMPLETED`. The commands
  read the provider failure from the normalized capture.
- **Exit codes (amended):** `exit_code_of(outcome)` in `cli_support.py`; 1 exactly for unavailable and failed; no
  command's exit code changes.
- **Graham Growth:** a calculation `not_applicable` maps to not applicable; unreachable today; ESC-29 settled the
  outcome.
- **Guards:** an AST scan for `RunOutcome` members in strategies and templates, and a totality test of the rule.
- **Commits:** the slice plan; the typed native status; the rule, the capture, the removals, the template and the
  guards; `exit_code_of` and the commands; the documents; the completion commit.
