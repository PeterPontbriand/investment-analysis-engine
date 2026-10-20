# SWC.8 Acceptance Review

## At a glance

- **What this is:** an independent acceptance review of the contributor guide, generator, status command, and omission diagnostics.
- **What this is not:** a strategy implementation or a change to financial formulas, test behavior, or production behavior.
- **Rules:** use isolated scratch worktrees, restore every omission between trials, record exact tool output, and keep status changes conditional on a pass.
- **Outcome: Fail.** Generating the throwaway strategy makes the guide's strict MyPy command fail in a shared workspace test helper.
- Every required omission trial produced a status report identifying the relevant site and its path or remedy; no SWC or PC status was changed.

| Work | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| SWC.8 acceptance review | [Findings and trials](#findings-and-trials) | Complete | 2026-10-19 |

## Review

- **Problem:** Determine whether a contributor following `docs/TOOL_DEVELOPMENT.md` can generate a strategy, use its diagnostics, and identify every required edit site.
- **Decision:** Fail acceptance because the documented strict type check fails immediately after generation on an existing test helper whose type assumption does not support the generated selection union.
- **Scope:** Follow the guide in a scratch worktree; run its named generator, status, stub, type-check, output-generation and drift-check commands; perform the required production-strategy omission trials in a second scratch worktree.
- **Branch:** `chore/swc-8-acceptance-review`.
- **Detail:** See [findings and trials](#findings-and-trials).

## Findings and trials

### Findings

| ID | Where | What happened | Severity | Outcome |
| :--- | :--- | :--- | :--- | :--- |
| F1 | Guide §3, strict type check; `tests/workspace/test_requests.py:508` | After generating `swc8_probe`, `uv run mypy --strict investment_analysis_engine tests scripts` fails because `Swc8ProbeSelection` is included in a union that the test helper treats as `FCFGrowthSelection`. The generated strategy skeleton itself is typed, but the documented repository-wide check is blocked by this shared assumption. | blocks | Filed [issue #167](https://github.com/PeterPontbriand/investment-analysis-engine/issues/167) with the exact MyPy evidence; no test behavior was changed in this review. |

### Part 1 — Follow the guide

The generator created the strategy package, its eleven role files, and all five documented wiring entries. The status command reported the expected missing generated bodies and reviewed sites, and deferred the codec, presenter, and replay checks on the unfilled evaluation body. The unfilled-stub test failed on the generated bodies as described.

The documented strict type check returned:

```text
tests\workspace\test_requests.py:508: error: Item "Swc8ProbeSelection" of "FCFGrowthSelection | Swc8ProbeSelection" has no attribute "to_fcf_policy"  [union-attr]
Found 1 error in 1 file (checked 522 source files)
```

The three output commands (`tests._direct_command_output`, `tests._strategy_document_output`, and `tests._cli_help_output`) exited successfully. The help command updated the scratch copy's stored application snapshot. Both generated-output checks reported the expected drift: the schema check named the two watchlist schemas and the new strategy schema, and the strategy-docs check named the two generated documentation files. No strategy implementation was written.

In a fresh generator worktree, the actual regeneration commands then wrote the new schema and both generated documentation blocks. Re-running both `--check` commands exited 0, and the status command changed `schema` and `strategy-docs` to `done` while continuing to report the unfilled and unwritten sites as missing.

### Part 2 — Omission trials

Each omission was restored before the next trial. “Status first line” and “test first line” reproduce the first non-empty line printed by each tool. For the rows whose first status line is a preceding `done` entry, the relevant `missing` line and its diagnostic are recorded in the next column.

| Trial | Status first line (exact) | Relevant status site and remedy | Enforcing test first line (exact) | Result |
| :--- | :--- | :--- | :--- | :--- |
| Delete `momentum/analyzer.py` | `missing  analyzer  investment_analysis_engine/strategies/momentum/analyzer.py` | `missing  analyzer  investment_analysis_engine/strategies/momentum/analyzer.py`; says the package could not be imported and to restore or write this site, then rerun status. | `ERROR: found no collectors for E:\Source\investment-analysis-engine\.tmp\swc8-trials\tests\test_strategy_wiring_conformance.py::test_t25_every_site_is_done_for_every_declared_strategy` | Status names the site and file; pytest reports the import failure and directs the contributor to status, as the guide says. |
| Empty `momentum/analyzer.py` | `missing  analyzer  investment_analysis_engine/strategies/momentum/analyzer.py` | Same site and file; the diagnostic says to restore or write the analyzer site and rerun status. | `ERROR: found no collectors for E:\Source\investment-analysis-engine\.tmp\swc8-trials\tests\test_strategy_wiring_conformance.py::test_t25_every_site_is_done_for_every_declared_strategy` | Status identifies the empty analyzer; pytest cannot collect and directs the contributor to status. |
| Remove `ANALYZE_MOMENTUM` from `ToolName` | `missing  tool-name  investment_analysis_engine/orchestrator/tool_names.py` | Names `tool-name` and `orchestrator/tool_names.py`; says to restore or write the `ToolName member` and rerun status. | `ERROR: found no collectors for E:\Source\investment-analysis-engine\.tmp\swc8-trials\tests\test_strategy_wiring_conformance.py::test_t25_every_site_is_done_for_every_declared_strategy` | Status identifies the member's site and file; pytest cannot collect and directs the contributor to status. |
| Remove Momentum from the CLI tier | `missing  cli-tier  investment_analysis_engine/cli_strategy_wiring.py` | Names `cli-tier` and `cli_strategy_wiring.py`; says to restore or write the CLI-tier entry and rerun status. | `ERROR: found no collectors for E:\Source\investment-analysis-engine\.tmp\swc8-trials\tests\test_strategy_wiring_conformance.py::test_t25_every_site_is_done_for_every_declared_strategy` | Status identifies the tier site and file; pytest reports `UndeclaredStrategyError` and directs the contributor to status. |
| Remove Momentum from the evaluation tier | `done     vocabulary  investment_analysis_engine/strategies/momentum/vocabulary.py` | Later reports `missing  evaluation-tier  investment_analysis_engine/evaluation/strategy_fixtures.py`; the diagnostic says the codec check could not run and to restore or write the evaluation-tier entry, then rerun status. | `F                                                                        [100%]` | Status identifies the evaluation-tier site and file; its focused conformance test fails for that site. |
| Delete `docs/user/strategies/MOMENTUM.md` | `done     vocabulary  investment_analysis_engine/strategies/momentum/vocabulary.py` | Later reports `missing  guide  docs/user/strategies/MOMENTUM.md` and says no guide exists at that path. | `F                                                                        [100%]` | Status identifies the guide site and exact file to create; its focused conformance test fails for that site. |
| Make `schemas/momentum.schema.json` stale | `done     vocabulary  investment_analysis_engine/strategies/momentum/vocabulary.py` | Later reports `missing  schema  schemas/momentum.schema.json` and says to run `uv run python -m scripts.generate_schemas`. | `F                                                                        [100%]` | Status identifies the schema site and regeneration command; the schema drift test fails and repeats the command in its assertion. |

### Scope limits and acceptance criteria

- Required trials: delete and empty a strategy-owned file; remove a tool-name member; remove each tier entry independently; delete a reviewed user guide; and stale a published schema.
- A trial passes the diagnostic criterion when the status output names the affected site and a file to change or a concrete fix/command.
- Acceptance also requires that following the guide does not leave a contributor blocked by an undocumented repository check failure.
- The omission trials pass their diagnostic criterion. F1 fails the overall acceptance criterion, so SWC.8 and parent statuses remain unchanged.

## Background and origin

This review was run from the repository root on 2026-10-19. The throwaway strategy was generated in `.tmp/swc8-acceptance`; omission experiments used a separate `.tmp/swc8-trials` worktree. Windows asyncio self-pipe creation was blocked by the managed sandbox, so the requested diagnostic and test commands were run with approved elevated execution against the isolated worktrees. Every omission mutation was restored; both scratch worktrees are scheduled for removal after verification.

## Appendix — Exact command outcomes

- Generator: `uv run python -m scripts.new_strategy swc8_probe --label "SWC8 Probe"` completed and listed each created/edited file, followed by the documented reminder to fill stubs and run status.
- Status after generation: exited 1 and printed every site in table order; expected missing stubs/reviewed sites were named, and `schema` and `strategy-docs` diagnostics included their regeneration commands.
- Stub test: `uv run python -m pytest tests/test_no_unfilled_stubs.py` — 1 failed, 2 passed; the failure listed all generated unfilled bodies.
- Type check: `uv run mypy --strict investment_analysis_engine tests scripts` — failed at `tests/workspace/test_requests.py:508` as recorded under F1.
- Generated-output checks: `uv run python -m scripts.generate_schemas --check` and `uv run python -m scripts.generate_strategy_docs --check` — exited 1 with stale generated-file paths and commands.
- The three reviewed-output writer commands all exited 0 in the scratch copy.
