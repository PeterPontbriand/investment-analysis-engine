# SWC.7b — Independent Review of the Strategy Development Guide

Records what a reviewer who knew only [`docs/TOOL_DEVELOPMENT.md`](../../../../TOOL_DEVELOPMENT.md) found when following it
and when breaking one edit site at a time.

## At a glance

- **What this is:** the record of one independent review of the strategy development guide, with every finding, its
  severity and its outcome, and the four omission trials with the first message each tool printed.
- **What it is not:** a change to what any tool enforces. Findings that would change a tool's behaviour or a test's
  assertion are filed as issues, not fixed here.
- **How it was done:** the reviewer read the project instructions and the guide, and nothing else about the work, until
  the findings were written. The guide did not send the reviewer to any planning document, so no finding is about
  planning history leaking into the guide.
- **Where it ran:** two scratch git worktrees of `main` at `0e0c161` under `.tmp/`: one for the generator walk-through
  (throwaway strategy `dividend_yield`), one for the omission trials on `fcf_growth`.
- **Result:** 14 findings. Ten are fixed here (guide wording, one `fails` text, diagnostic text). Four (F1, F4, F7, F11)
  are fixed in the guide or in part, and their tool behaviour is filed as issues #161 to #164. Nothing in the guide was impossible to follow; the stub-filling and reviewed-site steps could be judged
  only for what they say (see [What could not be followed](#what-could-not-be-followed)).

## Findings

Severity: **blocks** = a contributor cannot proceed without outside help; **misleads** = the guide or a tool says
something false or points the wrong way; **minor** = wording or completeness.

| Id | Where | What happened | Severity | Outcome |
| :--- | :--- | :--- | :--- | :--- |
| F1 | Guide step 2 | The guide said that after the generator the reviewed sites and the sites with unfilled stubs would be missing. The status command showed `done` for `analyzer`, `tool`, `execution`, `cli`, `evaluation` and `selection` while they still called `unfilled_stub`; only `codec`, `presenter` and `replay` were `missing`, with `UnfilledStubError` naming the `evaluation` site. `done` does not mean filled. | misleads | Guide fixed here: step 2 says what `done` means and lists the sites that really show `missing`. Tool behaviour: issue [#164](https://github.com/PeterPontbriand/investment-analysis-engine/issues/164) (fixed in SWC.8). |
| F2 | Guide step 3 | "No `unfilled_stub` call is left and the type check passes" named no command for either. The test is `tests/test_no_unfilled_stubs.py`; the type check is `mypy --strict` over three folders. | misleads | Fixed here: both commands are in step 3 and in the workflow table. |
| F3 | Guide step 4 | The reviewed-sites table said what to write but not how. Three sites have stored outputs written by a command (`python -m tests._direct_command_output`, `_strategy_document_output`, `_cli_help_output`), and two need an entry in a registry (`_COMMANDS`, `CASES`) first. None of this was in the guide, and the status messages said only "does not exist". | blocks | Fixed here: the table has a "Command that writes it" column and names the registries; the status messages for the three sites end with the command. |
| F4 | Guide step 5; status messages | Status messages said `run scripts/generate_strategy_docs.py`. Running the file by its path fails with `ModuleNotFoundError: No module named 'scripts'`; only `python -m scripts.generate_strategy_docs` works, as the guide says. | misleads | Guide fixed here (it explains the two spellings). The message is built in `scripts/generate_strategy_docs.py`, outside this slice: issue [#162](https://github.com/PeterPontbriand/investment-analysis-engine/issues/162) (fixed in SWC.8). |
| F5 | Guide step 5 | The guide said the schema command writes "the strategy's published schema". It also rewrites `watchlist.schema.json` and `watchlist-delete.schema.json`. | minor | Fixed here. |
| F6 | Guide step 5 | "Both scripts report current output": with `--check` on a current tree both print nothing and exit 0; on a stale tree they print each file and exit 1. | minor | Fixed here. |
| F7 | Guide step 6 | "Each failure names the site and says how to fix it." False when a strategy file or wiring entry is missing: the package cannot be imported, the status command prints one `missing  import` line with the Python error, and pytest fails every conformance test at collection with the same error (trials 1 and 2). | misleads | Guide fixed here (it says what happens and what to do). Tool behaviour: issue [#161](https://github.com/PeterPontbriand/investment-analysis-engine/issues/161) (fixed in SWC.8). |
| F8 | Guide step 2; status | The `import` line is not a site in the edit-site table and the guide never mentions it. | minor | Fixed here: the guide explains it and the message now adds "a strategy file or a wiring entry that the descriptor needs was probably removed or renamed". |
| F9 | Guide, edit-site table | The check column uses `{module_upper}` (`site_cases`) but the placeholder list defines only `{module}`, `{alias}` and `{guide}`. | minor | Fixed here. |
| F10 | Guide, edit-site table and step 6 | The guide never says which test enforces a site. One parametrized test does: `tests/test_strategy_wiring_conformance.py::test_t25_every_site_is_done_for_every_declared_strategy[<strategy>-<site>]`. | misleads | Fixed here: step 6 names it. |
| F11 | `tests/_wiring_gaps.py`; conformance test | A stale schema fails `test_t10_the_evaluation_tier_covers_every_descriptor`, and its first assertion line has no command. The `schema` site check had no command either. | misleads | Site check fixed here (the status message and pytest's `test_t25` failure now end with `run uv run python -m scripts.generate_schemas`). The t10 test name and message: issue [#163](https://github.com/PeterPontbriand/investment-analysis-engine/issues/163) (fixed in SWC.8). |
| F12 | Status messages for `direct-output`, `strategy-documents`, `help-snapshot` | Messages said only `... does not exist` or `has no command row`, with no command. | misleads | Fixed here: each ends with `write it with <command>`. |
| F13 | `scripts/strategy_sites.toml`, `schema` row | The `fails` text said `run scripts/generate_schemas.py`; the file fails when run by path (same cause as F4). | misleads | Fixed here (`fails` text only; the row's title is unchanged). |
| F14 | Guide step 4 | For `cases`, `catalog`, `guide` and `settings` the guide gives no example of the shape of the file. A reviewer cannot tell from the guide alone what a Golden case or a catalog entry contains. | minor | Fixed here: step 4 links [`EVALUATIONS.md` §5](../../../../EVALUATIONS.md#5-golden-cases-and-fixtures) and §10, which state what a case, a fixture and a catalog entry must contain, and points to an existing strategy's file for structure. |

Messages changed by the fixes are listed in [Appendix A](#appendix-a-messages-before-and-after-the-fixes).

## Part 1 — following the guide

1. `uv run python scripts/new_strategy.py dividend_yield --label "Dividend Yield"` listed 12 created files and 5 edited
   files, as step 1 says, and ended with the exact status command to run, including `--alias dividend-yield`. The
   first `uv run` in a new worktree also created a virtual environment (about 30 seconds); the guide does not mention
   it, and it is not a defect.
2. Running the generator a second time exited with code 2 and listed 30 conflicts, as step 1 says.
3. `uv run python scripts/strategy_status.py dividend_yield` printed one line per site and exited 1. Findings F1 and F8
   come from this output.
4. `uv run python -m pytest tests/test_no_unfilled_stubs.py` failed and listed 13 `unfilled_stub` calls with file and
   line. The guide does not name this test (F2).
5. `python -m scripts.generate_schemas` and `python -m scripts.generate_strategy_docs` wrote the schema, the two
   watchlist schemas and the two document lists, and the status command then showed `schema` and `strategy-docs` as
   `done`. F4, F5 and F6 come from this step.
6. The reviewed sites could not be written without help from outside the guide (F3, F14).

## Part 2 — omission trials

Strategy: `fcf_growth` (alias `fcf-growth`) in a fresh worktree. Before any trial the status command printed `done` for
all 26 sites. Each trial broke one site, ran the status command and the named tests, and restored the file with
`git checkout`. "Names the problem / file / fix" is judged on the first message each tool printed.

### Trial 1 — new file

- **Broke:** deleted `investment_analysis_engine/strategies/fcf_growth/replay.py`; then, separately, emptied
  `presenter.py`.
- **Status, first message:**

  ```text
  missing  import  scripts/strategy_conformance.py
      the package could not be imported, so no site was checked: ModuleNotFoundError: No module named 'investment_analysis_engine.strategies.fcf_growth.replay'
  ```

  Emptied file: `ImportError: cannot import name 'render_fcf_earnings_growth' from 'investment_analysis_engine.strategies.fcf_growth.presenter'`.
- **Tests (`tests/test_strategy_wiring_conformance.py`), first message:**
  `ERROR collecting tests/test_strategy_wiring_conformance.py` with the same `ModuleNotFoundError` / `ImportError`.
- **Names the problem:** the module and, for the empty file, the missing name; not the site. **The file:** only
  through the module path. **The fix:** no. Filed as [#161](https://github.com/PeterPontbriand/investment-analysis-engine/issues/161);
  the status message now adds a hint (F8).

### Trial 2 — edit (shared file)

- **Broke:** removed the strategy's `pair_cli(...)` entry from `cli_strategy_wiring.py`; then, separately, removed the
  `ANALYZE_FCF_EARNINGS_GROWTH` member of `ToolName` in `orchestrator/tool_names.py`.
- **Status, first message** (entry removed):

  ```text
  missing  import  scripts/strategy_conformance.py
      the package could not be imported, so no site was checked: UndeclaredStrategyError: No declared strategy for CLI tier entry for strategy ('fcf_earnings_growth', 'reported_fcf_eps_cagr'); declared: ('graham_growth_value', 'graham_growth_value'), ('graham_number', 'graham_number'), ('momentum', 'sma_crossover').
  ```

  Member removed: `AttributeError: type object 'ToolName' has no attribute 'ANALYZE_FCF_EARNINGS_GROWTH'`.
- **Tests, first message:** `ERROR collecting tests/test_cli_strategy_wiring.py` (entry removed) and
  `ERROR collecting tests/test_strategy_wiring_conformance.py` (member removed), each with the error above.
- **Names the problem:** the first names the tier and the strategy, in wording that reads backwards; the second names
  only the missing member. **The file:** no. **The fix:** no. Issue [#161](https://github.com/PeterPontbriand/investment-analysis-engine/issues/161).

### Trial 3 — reviewed (hand-written artifact)

- **Broke:** deleted `docs/user/strategies/FCF_GROWTH.md`; then deleted `tests/expected_output/direct_commands/fcf-growth.json`;
  then deleted `tests/expected_output/strategy_documents/fcf-growth-success.replay.json`.
- **Status, first message** (guide deleted):

  ```text
  missing  guide  docs/user/strategies/FCF_GROWTH.md
      no guide for alias 'fcf-growth': docs/user/strategies/FCF_GROWTH.md does not exist
  ```

  Direct output deleted: `tests/expected_output/direct_commands/fcf-growth.json does not exist`.
  Replay document deleted: `tests/expected_output/strategy_documents/fcf-growth-success.replay.json does not exist`.
- **Tests, first message** (all three): `test_t25_every_site_is_done_for_every_declared_strategy[reported_fcf_eps_cagr-<site>]`
  failed with `Gap(site_id='<site>', path=..., message=...)`, the same text as the status command. Run alongside it,
  `tests/test_direct_command_output.py` and `tests/test_strategy_document_output.py` passed.
- **Names the problem and the file:** yes. **The fix:** no for the stored outputs (F12, fixed); for the guide the path
  is the fix. `scripts/check_doc_links.py` additionally reports 7 broken links to the deleted guide.

### Trial 4 — command (stale generated artifact)

- **Broke:** changed one character in `schemas/fcf-growth.schema.json`; then changed the first occurrence of an alias
  in the generated strategy list of `docs/user/USAGE.md`.
- **Status, first message** (schema):

  ```text
  missing  schema  schemas/fcf-growth.schema.json
      strategy ('fcf_earnings_growth', 'reported_fcf_eps_cagr') is not wired in: published schemas (schemas/fcf-growth.schema.json is out of date)
  ```

  List: `docs/user/USAGE.md: the generated block 'strategy-help-commands' is out of date; run scripts/generate_strategy_docs.py`.
- **Tests, first message:** schema: `FAILED tests/test_strategy_wiring_conformance.py::test_t10_the_evaluation_tier_covers_every_descriptor`
  with `strategy (...) is not wired in: published schemas`; list: `test_t25_...[sma_crossover-strategy-docs]` with the
  status message. `generate_schemas --check` and `generate_strategy_docs --check` both exited 1 and named the file.
- **Names the problem:** yes. **The file:** yes. **The fix:** the list message names the command in a form that fails
  when run (F4, [#162](https://github.com/PeterPontbriand/investment-analysis-engine/issues/162)); the schema message
  named no command (F11, F13, fixed for the status command; test name and text in [#163](https://github.com/PeterPontbriand/investment-analysis-engine/issues/163)).

## Scope limits and acceptance

- **Changed in this slice:** this record, `docs/TOOL_DEVELOPMENT.md`, the `fails` text of the `schema` row in
  `scripts/strategy_sites.toml`, diagnostic text in `scripts/strategy_status.py` and `scripts/strategy_conformance.py`,
  and the two plan tables.
- **Not changed:** production code, the generator, and what any check or test enforces. The edits to
  `strategy_conformance.py` add text to messages and one parameter to a private helper.
- **Accepted when:** the guide's generated table is current, the full gate passes on Python 3.12 and 3.14, every
  finding has an outcome, and each issue holds its evidence.

## What could not be followed

- **Step 3 (fill the stubs):** the reviewer did not write a strategy. The guide says where to start and which files
  to fill, in order, and F2 shows the proof was missing; whether the instructions are enough for the financial work
  cannot be judged from the guide, which correctly leaves that to the contributor.
- **Step 4 (reviewed sites):** after the fixes the guide says what each site needs, which command writes the stored
  output and where a Golden case and a catalog entry are specified (F14).

## Background

SWC.7a wrote the guide. The authors had built the tools it describes, so the project asked for a reviewer who has only
the guide. The reviewer used the manual-run rule of `AGENTS.md` for the throwaway checks (no `ian` command was run) and
removed the scratch worktrees under `.tmp/` when the review ended.

## Appendix A: messages before and after the fixes

| Site | Before | After |
| :--- | :--- | :--- |
| `import` | `the package could not be imported, so no site was checked: <error>` | the same, then `; a strategy file or a wiring entry that the descriptor needs was probably removed or renamed` |
| `direct-output` | `tests/expected_output/direct_commands/fcf-growth.json does not exist` | the same, then `; write it with uv run python -m tests._direct_command_output` |
| `strategy-documents` | `tests/expected_output/strategy_documents/fcf-growth-success.replay.json does not exist` | the same, then `; write it with uv run python -m tests._strategy_document_output` |
| `help-snapshot` | `tests/expected_output/cli_help/application.txt has no command row for 'fcf-growth'` | the same, then `; write it with uv run python -m tests._cli_help_output` |
| `schema` | `strategy (...) is not wired in: published schemas (schemas/fcf-growth.schema.json is out of date)` | the same, then `; run uv run python -m scripts.generate_schemas` |
