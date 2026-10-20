# SWC.8 Acceptance Review

## At a glance

- **What this is:** an independent acceptance review of the contributor guide, generator, status command, and omission diagnostics.
- **What this is not:** a strategy implementation or a change to financial formulas, test behavior, or production behavior.
- **Rules:** use isolated scratch worktrees, restore every omission between trials, record exact tool output, and keep status changes conditional on a pass.
- **Outcome: Pass (after re-check).** The 2026-10-19 re-check found the follow-up fix clears F1.
- **Initial outcome (2026-10-19): Fail.** The original post-generation type check failed in a shared workspace test helper; that result and its output remain recorded below.
- Original review: every required omission trial produced a status report identifying the relevant site and its path or remedy, and no SWC or PC status changed. The F1 re-check completed SWC; PC is now Next.

| Work | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| SWC.8 acceptance review | [Findings and trials](#findings-and-trials) | Complete | 2026-10-19 |

## Review

- **Problem:** Determine whether a contributor following `docs/TOOL_DEVELOPMENT.md` can generate a strategy, use its diagnostics, and identify every required edit site.
- **Decision:** The initial review failed because the strict type check failed immediately after generation; after the 2026-10-19 F1 re-check passed, the overall acceptance outcome is Pass.
- **Scope:** The original review followed the guide in scratch worktrees and performed its omission trials. This follow-up re-ran only the generator and strict type check for F1; the already-passing omission trials were not repeated.
- **Branch:** `chore/swc-8-acceptance-review`.
- **Detail:** See [findings and trials](#findings-and-trials).

## Findings and trials

### Findings

| ID | Where | What happened | Severity | Outcome |
| :--- | :--- | :--- | :--- | :--- |
| F1 | Guide §3, strict type check; `tests/workspace/test_requests.py:508` | Initial review: after generating `swc8_probe`, the strict check failed because `Swc8ProbeSelection` was included in a union that the test helper treated as `FCFGrowthSelection`. Re-check (2026-10-19): generated `swc8_probe` on current `main`; the strict check passed with only the generated stubs in place, with no errors in files the generator did not write. | blocks | Fixed (2026-10-19). The former documented invocation `uv run mypy --strict investment_analysis_engine tests scripts` hit `error: uv trampoline failed to canonicalize script path` in the managed Windows environment. `uv run python -m mypy --strict investment_analysis_engine tests scripts` completed with `Success: no issues found in 522 source files`; `docs/TOOL_DEVELOPMENT.md` now documents that working form. |

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
- The omission trials passed their diagnostic criterion in the original review and were not repeated. F1 passed its 2026-10-19 re-check, so SWC.8 and SWC are complete.

## Background and origin

The original review was run from the repository root on 2026-10-19. Its throwaway strategy was generated in `.tmp/swc8-acceptance`; omission experiments used a separate `.tmp/swc8-trials` worktree. Windows asyncio self-pipe creation was blocked by the managed sandbox, so the requested diagnostic and test commands were run with approved elevated execution against the isolated worktrees. Every omission mutation was restored. The F1 re-check was run on 2026-10-19 in `.tmp/swc8-f1-recheck`, a detached worktree of current `main`; that scratch worktree was removed after the check. The documented `uv run mypy` console entry point could not launch because of a uv trampoline canonicalization error, so the same MyPy check was run as a Python module using the already-synchronized project environment.

## Appendix — Exact command outcomes

- Generator: `uv run python -m scripts.new_strategy swc8_probe --label "SWC8 Probe"` completed and listed each created/edited file, followed by the documented reminder to fill stubs and run status.
- Status after generation: exited 1 and printed every site in table order; expected missing stubs/reviewed sites were named, and `schema` and `strategy-docs` diagnostics included their regeneration commands.
- Stub test: `uv run python -m pytest tests/test_no_unfilled_stubs.py` — 1 failed, 2 passed; the failure listed all generated unfilled bodies.
- Type check: `uv run mypy --strict investment_analysis_engine tests scripts` — failed at `tests/workspace/test_requests.py:508` as recorded under F1.
- F1 re-check generator: `uv run python -m scripts.new_strategy swc8_probe --label "SWC8 Probe"` — completed in the detached `.tmp/swc8-f1-recheck` worktree based on `main` at `a29474f`.
- F1 re-check documented type-check command: `uv run mypy --strict investment_analysis_engine tests scripts` — did not launch; last line: `error: uv trampoline failed to canonicalize script path`.
- F1 re-check successful type-check command: `uv run python -m mypy --strict investment_analysis_engine tests scripts` — exit 0; last line: `Success: no issues found in 522 source files`.
- Generated-output checks: `uv run python -m scripts.generate_schemas --check` and `uv run python -m scripts.generate_strategy_docs --check` — exited 1 with stale generated-file paths and commands.
- The three reviewed-output writer commands all exited 0 in the scratch copy.
