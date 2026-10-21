# PC.3 — Help Encoding: Slice Plan

Writes standard output and standard error as UTF-8 from the entry point, so no command crashes on a redirected Windows
console ([#147](https://github.com/PeterPontbriand/investment-analysis-engine/issues/147)); writes every JSON text with
its characters as they are; and removes planning labels and markup from command help.

Parent plan: [PC contract and slice plan](PC_CONTRACT_AND_SLICE_PLAN.md#pc3--help-encoding).

## 1. At a glance

- **What this slice does:** fixes the cause of #147 instead of one help text. When output is redirected on Windows,
  Python 3.12 to 3.14 encodes it with the ANSI code page (cp1252), and any character outside it crashes the command: the
  `→` in the `--growth-years` help of `fcf-growth`, the Unicode minus in `fcf-growth --details`, and provider data in
  JSON output. The entry point now switches both streams to UTF-8 before it writes anything. Two rules and their guards
  keep the area clean: one JSON rule (`ensure_ascii=False` everywhere) and help text free of planning labels and
  markup.
- **What it is not:** a rule that help is ASCII (`→`, `−`, `×` and `—` stay); a formula, classification or calculation
  change; a change to any option, default or behaviour; a change to a published schema.
- **Rules it follows:** a consolidation package under `AGENTS.md` §0. Stored data has no compatibility value, so a
  changed cache key or telemetry digest for a non-ASCII payload is accepted. The complete managed gate, with the extra
  interpreter, runs on the final commit. Each guard is proved to bite on a deliberate breakage that is then reverted.
- **Decisions:** all approved by the project owner on 2026-10-21 ([A.1](#a1-approved-decisions-2026-10-21)).

## 2. Sequence and status

| Unit | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| Slice plan | [This document](#3-the-work-units) and the parent-plan updates | In progress | |
| Stream fix | [UTF-8 standard streams](#utf-8-standard-streams) | Planned | |
| JSON rule | [One JSON rule everywhere](#one-json-rule-everywhere) | Planned | |
| Help cleanup | [Plain help](#plain-help) | Planned | |
| Completion | [Plan rows and the final gate](#completion) | Planned | |

## 3. The work units

### UTF-8 standard streams

- **Problem:** `main.py` leaves both streams on the encoding Python chose. On Windows, with output redirected, that is
  cp1252, and a character outside it raises `UnicodeEncodeError` mid-render (standard output) or is written as a
  `\uXXXX` escape (standard error, whose error handler is `backslashreplace`). The settings-error message is printed
  while the module is imported, before any stream setup could run.
- **Decision:** `main()` reconfigures standard output and standard error to UTF-8 as its first act. This is the
  behaviour Python 3.15 makes the default (PEP 686). A program that reads redirected output as cp1252 sees garbled
  non-ASCII characters instead of a crash; the user documentation says so where output redirection and `--json` are
  described.
- **Scope:** `investment_analysis_engine/main.py`, the three tests that patch its module attributes, the new tests, and
  the user documentation.
- **Branch:** `fix/pc-3-help-encoding`
- **Detail:** the sections below.

#### How `main.py` starts up

| Order | Step | Before | After |
| :--- | :--- | :--- | :--- |
| 1 | Switch standard output and standard error to UTF-8 | none | `use_utf8_output(sys.stdout, sys.stderr)` |
| 2 | Import the engine settings; a bad variable is one message, exit 2, before any other project import | when the module is imported | first block of `main()`, after step 1 |
| 3 | Open the run context | `main()` | `main()` |
| 4 | Install logging; a failure is exit 1 | `main()` | `main()` |
| 5 | Import the commands; a strategy-settings error is one message, exit 2 | `main()` | `main()` |
| 6 | Run the app; log an unhandled exception; tear logging down | `main()` | `main()` |

- Importing `investment_analysis_engine.main` has no side effect: it reconfigures no stream and reads no settings. Its
  only project import is `core.settings_error`, which defines the two error classes.
- `use_utf8_output(*streams)` reconfigures each stream that is an `io.TextIOWrapper` and ignores any other object, so a
  test double, a captured stream and a missing stream (`None`) are left alone. It sets the encoding only; the error
  handler of each stream stays.
- Exit codes, the order of steps 2 to 6, and what is logged do not change. The names `RunContext`,
  `set_current_run_context`, `setup_global_logging` and `teardown_global_logging` are imported inside `main()`, after
  step 2, because a project import before step 2 would break the rule above. Three tests that patched them on
  `investment_analysis_engine.main` patch them in the defining module instead (`tests/test_startup_strategy_settings.py`
  twice, `tests/utils/_logging_command_driver.py` once).
- Rich draws a table with box-drawing characters when the stream is UTF-8 and with ASCII lines when it is not. Redirected
  help on Windows therefore changes from `+---+` lines to box-drawing characters. This is the output a console shows.

#### Tests

| Test | Where | What it asserts |
| :--- | :--- | :--- |
| `test_the_stream_setup_makes_a_cp1252_stream_write_utf8` | `tests/test_main_output_encoding.py` | After `use_utf8_output`, a cp1252 stream holds `→` as UTF-8 bytes |
| `test_the_stream_setup_ignores_a_stream_it_cannot_reconfigure` | the same | `None` and an object that is not a text wrapper are accepted |
| `test_importing_the_entry_point_leaves_the_streams_alone` | the same | An import of the module in a subprocess leaves the standard streams on their encoding |
| `test_every_command_renders_its_help_as_utf8_into_a_cp1252_stream` | the same | Walks the root command and every group to every command (`tests/_command_tree.py`), so a new command needs no edit. For each: the stream setup is applied to a cp1252 stream, `--help` is rendered into it, the exit code is 0 and the bytes decode as UTF-8 |
| `test_fcf_growth_help_is_utf8_when_redirected_under_cp1252` | `tests/test_main_output_encoding_end_to_end.py` | A subprocess with `PYTHONIOENCODING=cp1252` and output captured: exit 0, UTF-8 output containing `→` |
| `test_a_settings_error_with_a_character_cp1252_cannot_encode_is_utf8_on_stderr` | the same | A subprocess with `IAN_CONFIG_DIR` set to a relative path containing `→` and the same encoding: exit 2 and the message, with `→`, as UTF-8 on standard error |

Both end-to-end cases fail on `main` before the fix: the first exits 1 with the `UnicodeEncodeError` of #147; the second
exits 2 as it should, but its standard error holds `→` in place of `→`, because the stream replaces what cp1252
cannot encode. The slice shows each failure on `main` before the fix is applied.

#### Workarounds for the same defect

Three files set `PYTHONUTF8=1` or `PYTHONIOENCODING=utf-8` for a child process.

| Site | The child | Decision | Reason |
| :--- | :--- | :--- | :--- |
| `scripts/check_installed_package.py`, `clean_environment` | `uv build`, `uv venv`, `uv pip`, `python -c` (prints a path the parent decodes as UTF-8), the installed `ian`, `uv run ian` | keep | One environment serves children that are not the entry point. The `python -c` children print a path with no entry point to set up their output, and the parent decodes it as UTF-8. Splitting the environment for the `ian` children would add structure for no gain. `tests/scripts/test_check_installed_package.py` keeps asserting the variable |
| `tests/scripts/test_new_strategy_end_to_end.py`, `_environment` | `scripts.strategy_status`, `mypy`, `ruff`, `pytest`, `scripts.new_strategy` | keep | Every child is another program, none the `ian` entry point. The variable also sets the encoding these tools read and write files with |
| `tests/utils/test_operational_logging.py`, `_run` | `tests.utils._logging_command_driver`, which runs `investment_analysis_engine.main.main` | remove | The child is the entry point, which now handles its own output; the test then checks the real behaviour |

### One JSON rule everywhere

- **Problem:** the project writes JSON in two ways. 13 call sites pass `ensure_ascii=False`, four pass `True` and 25 pass
  nothing, which defaults to `True`: a non-ASCII character is written as a `\uXXXX` escape. Output a user reads, and
  a digest or cache key that depends on the text, then depend on which call wrote it.
- **Decision:** every `json.dumps` and `json.dump` call under `investment_analysis_engine/`, `scripts/` and `tests/`
  passes `ensure_ascii=False`. Pydantic's `model_dump_json` already writes this way. A cache key or telemetry digest
  that changes for a non-ASCII payload is accepted under `AGENTS.md` §0.
- **Scope:** the call sites below, and the guard test.
- **Branch:** `fix/pc-3-help-encoding`
- **Detail:** the sections below.

#### Call sites

Taken from an AST scan at `a150463`. Line numbers are those of that commit.

| Call | `ensure_ascii` now | Change |
| :--- | :--- | :--- |
| `investment_analysis_engine/cli_database.py:155` | `True` | change `True` to `False` |
| `investment_analysis_engine/cli_database.py:158` | `True` | change `True` to `False` |
| `investment_analysis_engine/cli_workspace.py:243` | `False` | unchanged |
| `investment_analysis_engine/data/repositories/instrument_profiles.py:41` | `False` | unchanged |
| `investment_analysis_engine/data/repositories/market_data.py:117` | `False` | unchanged |
| `investment_analysis_engine/data/repositories/readiness.py:101` | `True` | change `True` to `False` |
| `investment_analysis_engine/data/repositories/resolved_input_cache.py:85` | `False` | unchanged |
| `investment_analysis_engine/data/repositories/trajectory.py:52` | `False` | unchanged |
| `investment_analysis_engine/evaluation/ollama_runner.py:464` | `(absent)` | add `ensure_ascii=False` |
| `investment_analysis_engine/orchestrator/loop.py:208` | `(absent)` | add `ensure_ascii=False` |
| `investment_analysis_engine/reporting/documents/strategy_document.py:113` | `False` | unchanged |
| `investment_analysis_engine/reporting/presentation.py:158` | `False` | unchanged |
| `investment_analysis_engine/strategies/fcf_growth/codec.py:66` | `(absent)` | add `ensure_ascii=False` |
| `investment_analysis_engine/strategies/graham_growth/codec.py:97` | `(absent)` | add `ensure_ascii=False` |
| `investment_analysis_engine/strategies/graham_number/codec.py:92` | `(absent)` | add `ensure_ascii=False` |
| `investment_analysis_engine/strategies/momentum/codec.py:62` | `(absent)` | add `ensure_ascii=False` |
| `investment_analysis_engine/telemetry/recorder.py:239` | `True` | change `True` to `False` |
| `investment_analysis_engine/workspace/repositories/analysis_runs.py:61` | `False` | unchanged |
| `investment_analysis_engine/workspace/watchlists.py:71` | `False` | unchanged |
| `scripts/generate_schemas.py:48` | `False` | unchanged |
| `tests/_strategy_document_output.py:152` | `False` | unchanged |
| `tests/_workspace_command_output.py:163` | `(absent)` | add `ensure_ascii=False` |
| `tests/_workspace_command_output.py:163` | `(absent)` | add `ensure_ascii=False` |
| `tests/data/test_transport_failure_kinds.py:60` | `(absent)` | add `ensure_ascii=False` |
| `tests/evaluation/test_ollama_runner.py:370` | `(absent)` | add `ensure_ascii=False` |
| `tests/evaluation/test_ollama_runner.py:378` | `(absent)` | add `ensure_ascii=False` |
| `tests/evaluation/test_ollama_runner.py:381` | `(absent)` | add `ensure_ascii=False` |
| `tests/orchestrator/test_tool_failure_codes.py:182` | `(absent)` | add `ensure_ascii=False` |
| `tests/orchestrator/test_tool_failure_codes.py:183` | `(absent)` | add `ensure_ascii=False` |
| `tests/reporting/test_strategy_document_shape.py:263` | `(absent)` | add `ensure_ascii=False` |
| `tests/reporting/test_strategy_documents.py:81` | `(absent)` | add `ensure_ascii=False` |
| `tests/schema/test_native_enforcement.py:27` | `(absent)` | add `ensure_ascii=False` |
| `tests/schema/test_validator.py:83` | `(absent)` | add `ensure_ascii=False` |
| `tests/scripts/test_generate_schemas.py:28` | `False` | unchanged |
| `tests/test_cli_database_readiness.py:127` | `(absent)` | add `ensure_ascii=False` |
| `tests/test_cli_refresh.py:178` | `(absent)` | add `ensure_ascii=False` |
| `tests/workspace/repositories/test_watchlist_repository.py:396` | `(absent)` | add `ensure_ascii=False` |
| `tests/workspace/test_momentum_codec.py:137` | `(absent)` | add `ensure_ascii=False` |
| `tests/workspace/test_requests.py:547` | `(absent)` | add `ensure_ascii=False` |
| `tests/workspace/test_requests.py:531` | `(absent)` | add `ensure_ascii=False` |
| `tests/workspace/test_watchlists.py:86` | `(absent)` | add `ensure_ascii=False` |
| `tests/workspace_documents/test_workspace_documents.py:211` | `False` | unchanged |

Of the 42 calls, 29 change and 13 stay. A test that compared production output with its own `json.dumps` text changes
with it.

#### Guard

| Test | Where | What it asserts |
| :--- | :--- | :--- |
| `test_every_json_dumps_and_dump_call_passes_ensure_ascii_false` | `tests/test_json_conventions.py` | An AST scan of the three roots fails on any `json.dumps` or `json.dump` call without `ensure_ascii=False`, and names the file and line. It resolves `import json as alias` and `from json import dumps` |
| `test_the_json_scan_reports_a_call_without_the_argument_and_accepts_the_rest` | the same | The scan itself: it reports a missing argument, a `True` value and a bare imported name, and accepts `ensure_ascii=False` |

### Plain help

- **Problem:** three help texts cite planning documents ("Amendment A1, §12") and three show reStructuredText markup
  literally (a double backtick), because Typer prints a docstring as the help.
- **Decision:** the help is rewritten in plain user language. A detail that is for a maintainer, not a user, is a comment
  in the function body, not help. No option, default or behaviour changes.
- **Scope:** the docstrings below, and the guard test.
- **Branch:** `fix/pc-3-help-encoding`
- **Detail:** the sections below.

#### Help texts to rewrite

| Command | Defect | Rewritten |
| :--- | :--- | :--- |
| `watchlist` (command list) | shows the first line of `remove-entry`, with "(Amendment A1, §12)" | fixed by the `remove-entry` line |
| `watchlist create` | "(Amendment A1, §12's "Creation")"; double backticks around `--analysis METHOD TICKER...` | Plain text: seeds one entry per ticker for the method in the same command; the flags are those of the method's own command, including which are required; a missing required flag is a usage error as it is for that command; omit `--analysis` for an empty watchlist |
| `watchlist add-selection` | "(Amendment A1, §12's "Editing")"; double backticks around `create` | Plain text: adds one entry per ticker for one method to an existing watchlist, like seeding with `--analysis` in `watchlist create`; the flags are those of the method's own command |
| `watchlist remove-entry` | "(Amendment A1, §12)" | "Remove exactly one entry by its displayed 1-based index." |
| `refresh` | double backticks around `--no-save`, `provider_check`, `--json` and `--no-provider-check`; lines broken at odd places | Plain text with the same content: nothing is printed until the refresh ends or is interrupted; Ctrl+C stops new jobs, lets running ones finish and exits 130; `--no-save` runs every entry and writes nothing; a provider failure is followed by one test request per provider, shown before the summary, or as `provider_check` in the `--json` summary; `--no-provider-check` turns it off |

#### Guard

| Test | Where | What it asserts |
| :--- | :--- | :--- |
| `test_no_command_help_contains_a_planning_label_or_markup` | `tests/test_help_conventions.py` | Walks every command as above and fails on help (the command's text and each option's and argument's) that contains `§`, "Amendment", "Slice", "Step" followed by a digit, or a double backtick. The message names the command and the offending text |
| `test_the_help_scan_reports_each_forbidden_form_and_accepts_plain_help` | the same | The scan itself, on text built for the test |

### Completion

- In [PC contract and slice plan](PC_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status), PC.3 is Complete with its date
  and PC.4 is Next.
- The complete managed gate runs on the final commit, with the extra interpreter. The real-console check of
  `ian fcf-growth --help > <file>` with `PYTHONUTF8` and `PYTHONIOENCODING` unset runs before and after the fix, and
  both exit codes are reported.

## 4. Scope limits

- No formula, classification or calculation result changes. No option, default or behaviour of a command changes.
- No published schema, golden or evaluation expectation changes. If `ensure_ascii=False` changes one, the work stops for
  the project owner.
- The ASCII-only rule is not adopted: `→`, `−`, `×`, `—` and similar typography stay where they are.
- The work stops for the project owner when: a change to `main.py` would alter an exit code, the order of startup steps
  or what is logged, beyond writing UTF-8; a help rewrite would change an option, its default or its behaviour; the
  purpose of a `PYTHONUTF8` or `PYTHONIOENCODING` workaround is unclear; or the generator end-to-end test exceeds its
  2-minute budget on either Python version.

## 5. Acceptance criteria

- `ian fcf-growth --help > file` exits 0 on a Windows console with `PYTHONUTF8` and `PYTHONIOENCODING` unset, and the
  file holds UTF-8.
- Every command renders its help into a cp1252 stream, after the entry point's stream setup, as UTF-8 with exit 0.
- No `json.dumps` or `json.dump` call under the three roots lacks `ensure_ascii=False`.
- No command's help contains a planning label or reStructuredText markup.
- The two guards and the in-process test fail on their deliberate breakages (proved and reverted, and reported with the
  slice).
- The user documentation says that redirected output is UTF-8.
- The complete managed gate passes.

## 6. Background: origin of this slice

Issue #147 reported one help text. Its cause is the stream, so the fix is in the entry point; the JSON rule and the help
cleanup remove the other two patterns a new strategy would copy from this area. See
[PC §6](PC_CONTRACT_AND_SLICE_PLAN.md#6-background-origin-of-this-work-package).

## Appendix A: Decision records

### A.1 Approved decisions (2026-10-21)

Decisions of the project owner, 2026-10-21.

- **Streams:** `main.py` reconfigures standard output and standard error to UTF-8 before it writes anything, the
  settings-error message included. A bad engine variable is still reported before any other project import, as one
  message with exit 2; a strategy-settings error still exits 2. Importing the module reconfigures nothing.
- **No ASCII-only rule.**
- **Tests:** an in-process walk of every command into a cp1252 stream; two end-to-end subprocess cases under
  `PYTHONIOENCODING=cp1252`, each shown failing on `main`.
- **Help:** planning labels and markup rewritten in plain user language; a guard test.
- **JSON (amended):** every `json.dumps` and `json.dump` call under `investment_analysis_engine/`, `scripts/` and
  `tests/` passes `ensure_ascii=False`; an AST guard.
- **Workarounds:** removed where the child is the `ian` entry point, kept where it is another program, with the reason.
- **Commits:** the slice plan; the stream fix and its tests; the JSON rule and its guard; the help cleanup and its guard;
  the completion commit.
