# PC — Pattern Cleanup before Step 3.5: Contract and Slice Plan

Removes the patterns that the Step 3.5 strategies would otherwise copy, while the consolidation period still allows
interface changes.

Placement among other work packages: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **What this work package does:** removes a small, fixed set of patterns that a contributor adding a Step 3.5
  strategy would copy from existing code: an option that can hold only one value, a word the project no longer uses
  for user-facing text, test helpers that hide their own setup, and a help screen that cannot be printed on a Windows
  console.
- **Why now:** `AGENTS.md` §0 still permits public interface and signature changes. Once Step 3.5 starts, seven
  strategies copy whatever is there, and §0 is removed.
- **What it is not:** a formula or classification change, a new strategy, or a sweep over code no Step 3.5 strategy
  would copy. The one stored-shape change is PC.1's: it changes three selection shapes under `AGENTS.md` §0, with
  version bumps and no migration. The excluded issues and the reason for each are in [Out of scope](#4-out-of-scope).
- **Rules every slice follows:** this is a consolidation package under `AGENTS.md` §0, so it follows §0's rules: no
  formula or classification change, no NaN or Inf, no network or LLM calls in tests outside `live_network`, the full
  managed quality gate on every slice, and no AI or tool attribution. A slice's open decisions go to the project
  owner before implementation ([decision rule](#decision-rule)).
- **Where the history lives:** why this work package exists is in
  [Background](#6-background-origin-of-this-work-package); the decision record is in
  [Appendix A](#appendix-a-decision-records-and-history).

## 2. Sequence and status

Each slice ends with the managed quality gate and is gated by explicit authorization before the next begins.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| PC.1 | [Interfaces and names](#pc1--interfaces-and-names) | Complete | 2026-10-20 |
| PC.2 | [Test helpers](#pc2--test-helpers) | Complete | 2026-10-20 |
| PC.3 | [Help encoding](#pc3--help-encoding) | Complete | 2026-10-21 |
| PC.4 | [One shared mapping from statuses to a run outcome](#pc4--one-shared-mapping-from-statuses-to-a-run-outcome) | Next | |

PC starts after SWC.8 completes and finishes before Step 3.5 begins. PC.4 follows PC.3: the project owner decided
[issue #111](https://github.com/PeterPontbriand/investment-analysis-engine/issues/111) in favour of a shared mapping on
2026-10-19 ([A.2](#a2-pc1-and-pc4-decisions-2026-10-19)).

## 3. The slices

### PC.1 — Interfaces and names

- **Problem:** two patterns a new strategy would copy. `--data-provider` is an option that accepts only `sec_edgar`
  ([#143](https://github.com/PeterPontbriand/investment-analysis-engine/issues/143)); `AGENTS.md` §9 already records it
  as a known exception. User-facing failure text is called a "sentence" in names and docs, where the project's word is
  "message" ([#140](https://github.com/PeterPontbriand/investment-analysis-engine/issues/140)); the inventory in that
  issue predates the package rename and must be refreshed first.
- **Decision:** approved by the project owner on 2026-10-19 ([A.2](#a2-pc1-and-pc4-decisions-2026-10-19)). For #143,
  remove the option and the strategy-owned chain behind it, including `quote_provider_id`, a stored field that can hold
  only `yfinance`; each strategy uses its fixed provider as a named constant. For #140, rename "sentence" to "message"
  by the refreshed inventory, guarded by a word scan.
- **Scope:** the option, the stored fields behind it, their tests and their documentation (#143); every name, test and
  document in the refreshed inventory (#140). PC.1 changes three selection shapes (Graham Number, Graham Growth and
  FCF Growth) under `AGENTS.md` §0, with `CONFIG_SCHEMA_VERSION` bumps and no migration.
- **Branch:** `refactor/pc-1-interfaces-and-names`
- **Detail:** [PC.1 slice plan](PC_1_INTERFACES_AND_NAMES_PLAN.md)

### PC.2 — Test helpers

- **Problem:** two test patterns a new strategy's tests would copy. CLI test isolation is switched on by an import that
  looks unused ([#148](https://github.com/PeterPontbriand/investment-analysis-engine/issues/148)). The Alembic setup is
  repeated across tests ([#145](https://github.com/PeterPontbriand/investment-analysis-engine/issues/145)), which is also
  item 3 of [#156](https://github.com/PeterPontbriand/investment-analysis-engine/issues/156).
- **Decision:** approved by the project owner on 2026-10-20 ([A.3](#a3-pc2-decisions-2026-10-20)). For #148, the CLI
  isolation fixtures become non-autouse, are registered in `tests/conftest.py` and are opted into with `pytestmark`;
  the two database fixtures become one, `isolated_cli_settings`; an import guard and a session-database guard keep
  the pattern removed. For #145, a helper migrates one template database per test process and each test copies it;
  every test upgrade to head uses the helper, and a guard scan keeps it so.
- **Scope:** the test helpers and the tests that use them. No production code.
- **Branch:** `refactor/pc-2-test-helpers`
- **Detail:** [PC.2 slice plan](PC_2_TEST_HELPERS_PLAN.md)

### PC.3 — Help encoding

- **Problem:** `fcf-growth --help` crashes on a console that uses the cp1252 code page
  ([#147](https://github.com/PeterPontbriand/investment-analysis-engine/issues/147)). The cause is the output stream,
  not one help text: when output is redirected on Windows, Python encodes it with cp1252, so the `→` of the
  `--growth-years` help, the Unicode minus of `fcf-growth --details` and provider data in JSON output all crash. Every
  strategy command is generated with the same help pattern, so each Step 3.5 command would inherit the defect. Two
  neighbouring patterns would be copied as well: JSON written with and without `ensure_ascii=False`, and help text with
  planning labels and literal markup.
- **Decision:** approved by the project owner on 2026-10-21 ([A.4](#a4-pc3-decisions-2026-10-21)). The entry point
  reconfigures standard output and standard error to UTF-8 before it writes anything; there is no ASCII-only rule.
  Every `json.dumps` and `json.dump` call passes `ensure_ascii=False`. The help of five commands (the `watchlist` list among them) is rewritten in plain
  user language. Tests walk every command, and two guards keep the JSON rule and the help clean.
- **Scope:** production code in `investment_analysis_engine/main.py`, the JSON call sites under
  `investment_analysis_engine/`, `scripts/` and `tests/`, and the help of `watchlist create`,
  `watchlist add-selection`, `watchlist remove-entry` (and so the `watchlist` command list) and `refresh`; the new tests;
  the three child-process workarounds, classified; and the user documentation of redirected output. No option, default
  or behaviour changes.
- **Branch:** `fix/pc-3-help-encoding`
- **Detail:** [PC.3 slice plan](PC_3_HELP_ENCODING_PLAN.md)

### PC.4 — One shared mapping from statuses to a run outcome

- **Problem:** each strategy writes its own function from its statuses to a `RunOutcome`, and every Step 3.5 strategy
  would write another copy. ESC-29 was a slip in one of them ([#111](https://github.com/PeterPontbriand/investment-analysis-engine/issues/111), and
  [Appendix A.9 of the Step 3.5 contract](../step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a9-one-shared-mapping-from-statuses-to-a-run-outcome-question-from-esc-29-2026-10-10)).
- **Decision:** yes, approved by the project owner on 2026-10-19 and amended on 2026-10-21
  ([A.5](#a5-pc4-decisions-2026-10-21)). PC.1 records the decision and implements none of it.
  - **The rule.** `RunOutcome.from_status(status: CalculationStatus | None) -> RunOutcome`, a class method in
    `investment_analysis_engine/analysis/run_models.py`, replaces the separate `run_outcome_of`. `ok` maps to
    completed, `not_applicable` to not applicable and `input_unavailable` to unavailable. `invalid_input` and
    `provider_error` map to failed. `None` maps to completed; that is Momentum's place in the rule, and A.8 of the
    Step 3.5 contract may later change Momentum's status, but not the rule.
  - **Native status.** `StrategyBehavior.native_status` and `native_status_of` return `CalculationStatus | None`
    instead of a string. Each strategy's codec function provides it: Graham Number and Graham Growth return
    `analysis.native_status`, so there is one way to get that status; FCF Growth returns `result.execution_status`;
    Momentum returns `None`. The evaluation runner records `.value`, or `None`, so recorded telemetry values stay the
    same. The generator's `codec.py.tmpl` and `scripts/strategy_conformance.py` follow.
  - **`ExecutionCapture` derives the rest.** It takes the native evidence and profile, the native status, the
    presentation inputs and the provider failure the strategy recorded. It derives `outcome` through
    `RunOutcome.from_status`, `failure_reason_code` (failed only) and `provider_failure` (kept for failed only).
    Derivation replaces the invariant checks in its `__post_init__`.
  - **Removals.** The three `classify_*_outcome` functions, the `outcome` field of each strategy's capture type, the
    three `capture_provider_failure` and three `_failure_code` functions, and Momentum's fixed `RunOutcome.COMPLETED`.
    Each `from_*_capture` passes the facts above and nothing else, and the commands read the provider failure from
    the normalized capture. The generator's `execution.py.tmpl` follows the same shape.
  - **Exit codes.** A shared `exit_code_of(outcome: RunOutcome) -> int` in `investment_analysis_engine/cli_support.py`
    returns 1 exactly for unavailable and failed, and 0 otherwise. The four strategy commands take their exit code from
    it, and no command's exit code changes. The CLI template's command body is an unfilled stub, so the contributor
    guide names `exit_code_of`.
  - **Graham Growth.** A calculation `not_applicable`, unreachable today, becomes not applicable instead of failed.
    This is a change in an unreachable path, not a classification change (ESC-29 settled the outcome); a test pins it
    through `RunOutcome.from_status`.
  - **Guard tests**, in `tests/test_documented_conventions.py`: an AST scan proving that no module under
    `investment_analysis_engine/strategies/` and no file under `scripts/strategy_templates/` names a `RunOutcome`
    member; and a test that `RunOutcome.from_status` covers every `CalculationStatus` member and `None`.
- **Scope:** the shared rule and exit-code function, `ExecutionCapture`, the strategies' codec, execution and command
  modules, the evaluation runner, the generator templates and conformance script, the two guard tests, and the
  documents that described the per-strategy mapping. No formula or classification changes.
- **Branch:** `refactor/pc-4-run-outcome`
- **Detail:** [PC.4 slice plan](PC_4_RUN_OUTCOME_PLAN.md)

### Decision rule

- Each slice's open decisions go to the project owner before implementation. An open item is not an acceptable outcome
  of a design decision in the consolidation period (`AGENTS.md` §0): the slice decides, or escalates.

## 4. Out of scope

- [#156](https://github.com/PeterPontbriand/investment-analysis-engine/issues/156) except item 3 (which is #145 and is in
  PC.2): the other items reduce gate run time and change no pattern a strategy copies.
- [#112](https://github.com/PeterPontbriand/investment-analysis-engine/issues/112) and
  [#116](https://github.com/PeterPontbriand/investment-analysis-engine/issues/116): both wait for the evidence that GR.3
  collects.
- [#149](https://github.com/PeterPontbriand/investment-analysis-engine/issues/149): a v0.3 decision about how the engine
  connects to a language model.
- Any formula, classification or strategy change, any stored-shape change other than PC.1's three selection shapes,
  and any new framework, registry or factory.

## 5. Acceptance criteria

- **No formula or classification change.** A calculation believed incorrect is reported, not fixed here.
- **Quality gate:** the complete managed gate, with at least 85% line coverage, after every slice.
- **Each slice** removes the pattern it names and adds the test that keeps it removed; the slice's plan names that
  test.
- **Completion record:** each slice's row is updated to Complete with its date in the same change, and the next row is
  set to Next.

## 6. Background: origin of this work package

The SWC.7b independent review and the preparation for Step 3.5 listed the open issues a first Step 3.5 strategy
would hit or copy. Most describe a pattern, not a defect: a strategy author reads existing code to learn the
conventions and reproduces what is there. On 2026-10-19 the project owner chose to clean these up in one work package
placed after SWC and before Step 3.5, while `AGENTS.md` §0 still allows interface changes.

## Appendix A: Decision records and history

### A.1 PC created and its first slices (2026-10-19)

Decision of the project owner, 2026-10-19; this plan records it and implements nothing.

- **New work package PC**, a consolidation package under `AGENTS.md` §0, with slices PC.1 (interfaces and names:
  #143 and #140), PC.2 (test helpers: #148 and #145) and PC.3 (help encoding: #147).
- **#111** is decided by the project owner before PC starts; yes makes it PC.4, no leaves it with Step 3.5.0.
- **Placement.** Its row in the milestone plan is numbered `14B` so the other rows keep their numbers, and it sits
  after SWC and before Step 3.5.
- **Out of scope**, with reasons: #156 except #145, #112 and #116, and #149 ([§4](#4-out-of-scope)).

### A.2 PC.1 and PC.4 decisions (2026-10-19)

Decisions of the project owner, 2026-10-19; this plan records them, and PC.1 implements the first two.

- **#143:** remove `--data-provider` from `graham-number`, `graham-growth`, `fcf-growth`, `watchlist create` and
  `watchlist add-selection`, with the strategy-owned chain behind it. Also remove `quote_provider_id` and
  `CLI_QUOTE_PROVIDERS`. Each strategy uses its fixed provider as a named constant. Keep the `provider_id` parameters of
  shared code and the provenance fields. The three selection shapes change under `AGENTS.md` §0, with
  `CONFIG_SCHEMA_VERSION` bumps and no migration.
- **#140:** rename "sentence" to "message" for user-facing failure text, by the refreshed inventory, with a word-scan
  guard test. Text counting actual sentences, the plain-English-answer text of `MASTER_PLAN.md` and
  `DISCOVERY_WORKBOOK.md`, and everything under `docs/project/milestones/` stay.
- **#111:** yes. It is slice PC.4, planned after PC.3, with the design in [PC.4](#pc4--one-shared-mapping-from-statuses-to-a-run-outcome). This replaces the
  "Decision pending: #111" section, which stated that yes makes it PC.4.

### A.3 PC.2 decisions (2026-10-20)

Decisions of the project owner, 2026-10-20; the [PC.2 slice plan](PC_2_TEST_HELPERS_PLAN.md#a1-approved-decisions-2026-10-20)
holds them in full.

- **#148:** the CLI isolation fixtures are non-autouse, defined in a helper module, registered in `tests/conftest.py`
  and opted into with `pytestmark`. `isolated_cli_database` is folded into `isolated_cli_settings`, which also patches
  `cli_run_support`. An import guard and a session-database guard are added. The leftover telemetry file is fixed if
  one line does it, otherwise filed.
- **#145:** `migrated_database_url` and `migrated_database` in a helper module; one template migrated per process and
  copied; every test upgrade to head uses the helper; migration tests keep their own Alembic calls; a guard scan under
  `tests/`.
- **Commits:** the slice plan, then #148, then #145, then the completion commit.

### A.4 PC.3 decisions (2026-10-21)

Decisions of the project owner, 2026-10-21; the [PC.3 slice plan](PC_3_HELP_ENCODING_PLAN.md#a1-approved-decisions-2026-10-21)
holds them in full.

- **#147:** fix the output streams, not one help text. `main.py` reconfigures standard output and standard error to
  UTF-8 before it writes anything, the settings-error message included, keeping the one-message exit 2 for a bad engine
  variable (before any other project import) and for a strategy-settings error. Importing the module reconfigures
  nothing. This is the behaviour Python 3.15 makes the default (PEP 686); a program that reads redirected output as
  cp1252 sees garbled non-ASCII characters instead of a crash, which the user documentation says.
- **No ASCII-only rule:** `→`, `−`, `×`, `—` and similar typography stay.
- **Tests:** an in-process walk of every command into a cp1252 stream, and two end-to-end subprocess cases under
  `PYTHONIOENCODING=cp1252`, each shown failing on `main`.
- **Help:** planning labels and reStructuredText markup in the help of `watchlist create`, `watchlist add-selection`,
  `watchlist remove-entry` and `refresh` are rewritten in plain user language; a guard test walks every command.
- **JSON (amended the same day):** every `json.dumps` and `json.dump` call under `investment_analysis_engine/`,
  `scripts/` and `tests/` passes `ensure_ascii=False`, including command output, internal forms and test helpers; an
  AST guard enforces it. Changed cache keys or telemetry digests for non-ASCII payloads are accepted under
  `AGENTS.md` §0.
- **Workarounds:** the three `PYTHONUTF8` and `PYTHONIOENCODING` settings for child processes are removed where the
  child is the `ian` entry point and kept, with the reason, where it is another program.
- **Commits:** the slice plan, then the stream fix and its tests, then the JSON rule and its guard, then the help
  cleanup and its guard, then the completion commit.

### A.5 PC.4 decisions (2026-10-21)

Decisions of the project owner, 2026-10-21, amending the 2026-10-19 design; the
[PC.4 slice plan](PC_4_RUN_OUTCOME_PLAN.md#a1-approved-decisions-2026-10-19-amended-2026-10-21) holds them in full.

- **The rule is a class method:** `RunOutcome.from_status`, replacing the separate `run_outcome_of`.
- **One native-status function per strategy:** the descriptor member and `native_status_of` return
  `CalculationStatus | None`; the codec functions provide it; the evaluation runner records `.value` or `None`.
- **`ExecutionCapture` derives** the outcome, the failure code and the kept provider failure from facts the strategy
  supplies, replacing its `__post_init__` checks.
- **Removals:** the three `classify_*_outcome` functions, the capture types' `outcome` field, the three
  `capture_provider_failure` and three `_failure_code` functions, and Momentum's fixed `COMPLETED`.
- **Exit codes:** `exit_code_of` lives in `cli_support.py`; no command's exit code changes.
- **Closing PC:** the completion commit sets PC.4 and row `14B` of the milestone plan to Complete and row 15 (Step 3.5)
  to Next. `AGENTS.md` §0 stays until slice 3.5.0.
- **Commits:** the slice plan, then the typed native status, then the rule with the capture, the removals, the template
  and the guards, then `exit_code_of` and the commands, then the documents, then the completion commit.
