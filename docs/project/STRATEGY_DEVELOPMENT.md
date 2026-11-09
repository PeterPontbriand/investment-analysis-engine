# Analysis Strategy Development Guide

How to add a deterministic financial analysis strategy to the engine, and how the code a strategy plugs into is organized.

**Start here:** read [Quick orientation](#quick-orientation), then follow the six steps of [the workflow](#add-a-strategy-the-workflow). The status command and the quality gate tell you how far you are. You do not need [Background](#background-how-a-strategy-fits-into-the-code) to add a strategy; read a part of it when a step sends you there or something fails that you want to understand.

## At a glance

- **What this is:** the one contributor guide for adding an analysis strategy. It is the only place the workflow, the list of edit sites and the settings convention are written down.
- **What the tooling does:** a generator writes the typed wiring and leaves every unfilled body failing the test suite; a status command lists which edit sites are done and which are missing; conformance tests and the quality gate fail, naming the missing site, if any is left out.
- **What stays yours:** the financial rules. A strategy owns its configuration, its inputs, its calculation and its result type. The generator writes no formula, classification, presentation text or settings file, and copies nothing from another strategy.
- **What no strategy does:** register itself, load as a plugin or be discovered at run time. The set of strategies is one closed, statically declared tuple that the generator extends and a reviewer reads (`investment_analysis_engine/strategy_wiring.py`).
- **Commands run from the repository root** through `uv run`, as [`AGENTS.md`](../../AGENTS.md) describes.

## Quick orientation

### Words this guide uses

The workflow uses these project terms. Each is explained in more depth under [Background](#background-how-a-strategy-fits-into-the-code), but one line is enough to follow the steps.

| Term | What it means here |
| :--- | :--- |
| Descriptor | The strategy's one entry in `STRATEGIES` (`investment_analysis_engine/strategy_wiring.py`): its identifiers, versions, types and references to its functions. The generator writes it. |
| Behavior | The bundle of the strategy's own functions that the descriptor carries (encode, decode, render, replay, headline and the like), so shared code can call the strategy without naming it. |
| Tier | A small table that pairs each strategy with the functions one layer needs but cannot import by name: the CLI tier (`cli_strategy_wiring.py`), the application tier (`application/tier.py`) and the evaluation tier (`evaluation/strategy_fixtures.py`). The generator adds the strategy's row to each. |
| Tool, tool name | Each strategy is also exposed to a local model as a tool; the tool name identifies it there and in the Golden cases. |
| Selection | The stored, typed record of the parameters a run used (the `as_of` boundary, the cache choice and any strategy parameter). A watchlist entry holds one. |
| Stored run, replay | A run saved with `--save-run` or by a watchlist refresh; replaying shows it again from the saved result, with no provider call or recalculation. |
| Native status | The calculation status the strategy's own result reports (`ok`, `not_applicable`, `input_unavailable` and so on), which the shared code turns into the run's outcome. |
| Envelope | The typed model of the strategy's `--json` document, with a published schema. |
| Headline | The few cells the strategy contributes to the side-by-side table of stored runs. |
| Golden case, fixture, catalog | A Golden case is a reviewed test of the strategy over fixtures (captured, offline evidence); the catalog lists every case in a fixed order under a suite version. |
| Conformance test | A test that checks every declared strategy has every required piece; the status command runs the same checks for one strategy. |
| Served content, help bundle | The parts of the user guides and glossary the engine serves to its clients (for example the desktop application), packed into a generated help bundle. Served sections may not contain command lines. |

### What you write and what is supplied

| You write | The generator or shared code supplies |
| :--- | :--- |
| The financial question, the formulas, the classifications and any policy | The identifiers, the tool name and the entries in the existing wiring files |
| The result's own fields, after its common ones | The result's common fields: ticker, requested and effective boundaries, instrument profile, execution status, reason code and reason, input failure, warnings and diagnostics |
| The analyzer's body, `compose_<module_name>`, the codec, the presenter, the replay projectors and headline function, and the evaluation `compose` | The direct command, `run`, the tool handler, the execution adapter and its normalizer, and run persistence |
| The vocabulary's enumerations, the reason messages and the investor-facing guide | The shared document header and tail and the shared presentation helpers |
| The settings model and its `settings.toml`, when the strategy has user-tunable defaults | Nothing: the generator writes no settings |
| The Golden cases, fixtures and catalog entries, and a reading of every stored output | The status command, the conformance tests, the schema and list generators and the quality gate |

### Role files the generator creates

The generator writes these files into `investment_analysis_engine/strategies/<module_name>/`. Every function you must write calls `unfilled_stub(...)` until you replace it, and the test suite fails while any such call remains.

| File | What it is for | What you do |
| :--- | :--- | :--- |
| `vocabulary.py` | The strategy's identifiers and its own enumerations | Keep the identifiers; add the enumerations the strategy needs, such as its classifications |
| `analyzer.py` | The result type and the analyzer, and the configuration when there is one | Write the analyzer's body, and add the result's own fields after the common ones |
| `evaluation.py` | How the evaluation tier builds the strategy over fixture data, and a sample selection | Write `compose` and choose the fixture ids. Do this early: see [step 3](#3-fill-the-stubs) |
| `codec.py` | Saving a result and reading it back | Write the encoder, the decoder and the native-status function |
| `application.py` | Building the analyzer and its providers (`compose_<module_name>`), and `run` | Write `compose_<module_name>`; leave `run` as generated |
| `presenter.py` | The text output in each mode, and the `--json` document | Write both |
| `replay.py` | Showing a stored run again, and the headline cells | Write the projectors and the headline function |
| `envelope.py` | The `--json` document model and its version | Add the strategy's fields to its body |
| `selection.py`, `tool.py`, `cli.py` | The stored parameters, the tool and the commands | Leave as generated; change them only to [add a selection parameter](#when-a-strategy-gains-a-selection-parameter) |
| `workspace.py` | The execution adapter that runs the analyzer and hands its result to shared code | Leave as generated |

### Copy structure, not rules

Do not invent a file layout. Pick the existing strategy closer to yours and keep its files open beside yours while you fill the stubs. Take its shape and naming, never its financial rules.

- **Piotroski** (`strategies/piotroski/`) has no configuration, which is the form the generator writes, and builds wholly on the shared SEC inputs.
- **FCF & Earnings Growth** (`strategies/fcf_growth/`) has a configuration a user selects, and a resolver of its own for its annual series.

| What you are writing | Open in Piotroski | Open in FCF & Earnings Growth |
| :--- | :--- | :--- |
| Result and analyzer | `analyzer.py` | `models.py` (result, configuration, policy) and `analyzer.py` |
| The calculation | `calculation.py` | `calculators.py` |
| Inputs | The shared assembly in `analysis/shared/metric_inputs.py`, called from `analyzer.py` | `input_resolver.py`, plus the shared market capitalization |
| Building the analyzer | `compose_piotroski` in `application.py`, the generated form | `run` in `application.py`, which composes in place |
| Saving, showing and replaying | `codec.py`, `presenter.py`, `replay.py` | The same three files |
| The `--json` document | `envelope.py` | `envelope.py` |
| Evaluation and Golden cases | `evaluation.py` and `evaluation/cases/piotroski.py` | `evaluation.py` and `evaluation/cases/fcf_growth.py` |
| A selection parameter | (none) | `selection.py`, `cli.py` and `tool.py` |
| The investor guide | `docs/user/strategies/PIOTROSKI.md` | `docs/user/strategies/FCF_GROWTH.md` |

Neither has settings; for a `settings.toml`, open `strategies/momentum/settings.py` and `settings.toml`. [Existing strategy reference](#existing-strategy-reference-fcf--earnings-growth-and-piotroski) maps the two strategies concept by concept.

### Decide early: shared metrics

Before writing a resolver of the strategy's own, read [Shared metrics and SEC inputs](#shared-metrics-and-sec-inputs); its table is short. A strategy that needs SEC facts, a market capitalization or a common metric such as EBITDA calls the shared functions in `analysis/shared/`; a resolver of its own is only for evidence no shared entry supplies. Deciding this before you write the analyzer saves rewriting it.

## Add a strategy: the workflow

Do the steps in this order. Each one ends with something you can check.

| Step | Do | You know it worked when |
| :--- | :--- | :--- |
| 1 | [Run the generator](#1-run-the-generator) | it lists the files it wrote and edited |
| 2 | [Check the status command](#2-check-the-status-command) | it prints a line per site and lists what is missing |
| 3 | [Fill the stubs](#3-fill-the-stubs) | `tests/test_no_unfilled_stubs.py` passes and the strict type check passes |
| 4 | [Write the reviewed sites](#4-write-the-reviewed-sites) | the status command shows no missing site |
| 5 | [Regenerate the schemas and the lists](#5-regenerate-the-schemas-and-the-generated-lists) | both scripts report current output |
| 6 | [Run the complete gate](#6-run-the-complete-gate) | every step in its closing summary passes |

### 1. Run the generator

**Code written before the generator runs.** The generator refuses a package that already exists, and a conformance test (`test_t14_wiring_files_declare_no_discovery_or_registration`) requires an `evaluation.py` in every strategy folder, so code that must land first cannot live in the future package.

- Put it in one module directly under `investment_analysis_engine/strategies/` (Piotroski's was `strategies/piotroski_calculation.py`), with no `__init__.py` and no `<module_name>/` directory. Only its tests import it.
- Move it into the generated package as the first step after the generator runs.
- That placement was approved for Piotroski ([3.5.3 slice plan A.3](milestones/v0.2/step-3.5/STEP_3_5_3_SLICE_PLAN.md#a3-authorization-of-the-calculators-location-2026-10-29)); ask before using it for another strategy, and if it breaks another check, stop and ask rather than adjust the check.

```bash
uv run python -m scripts.new_strategy <module_name> --label "<Label>" [--alias <alias>]
```

- `<module_name>` is the snake-case package name. It gives the analysis identifier, the method identifier and the tool name. The alias defaults to the hyphenated module name.
- It writes typed stubs for the role files into `investment_analysis_engine/strategies/<module_name>/`: `vocabulary`, `analyzer`, `tool`, `selection`, `codec`, `workspace`, `application`, `cli`, `presenter`, `envelope`, `replay` and `evaluation`.
- It makes one insertion in each of six existing files: the descriptor in `strategy_wiring.py`, the tool name in `orchestrator/tool_names.py`, the type lists in `workspace/strategy_types.py`, and the strategy's row in the CLI tier (`cli_strategy_wiring.py`), the application tier (`application/tier.py`) and the evaluation tier (`evaluation/strategy_fixtures.py`). You do not edit these by hand.
- A label is at most 40 characters and a module name at most 40 (`MAX_LABEL_LENGTH` and `MAX_MODULE_NAME_LENGTH` in `scripts/new_strategy.py`), the lengths at which no generated line passes 120 characters, proven by `tests/scripts/test_new_strategy_label_limits.py`. A longer one is a usage error: the generator exits with code 2 and writes nothing. The longest name in the Step 3.5 specifications, "Cash-Flow Valuation Multiples", has 29.
- It refuses to overwrite. If a target file exists, or the module name, alias, tool or method identifier is already used, it writes nothing and exits with code 2, listing the conflicts.
- Every unfilled body calls `unfilled_stub(...)`. The generated files type-check as written, and the test suite fails while any such call remains under `investment_analysis_engine/`.
- The generated descriptor has `settings_type=None` and `selection_settings_fields=()`; see [Strategy settings](#strategy-settings).
- The analyzer stub is the form with no configuration, `BaseAnalyzer[<Name>Result]`. **If the strategy needs a parameter a user selects, read [When a strategy gains a selection parameter](#when-a-strategy-gains-a-selection-parameter) before filling the analyzer.**
- It writes these bodies in full, from the helpers in [Execution capture and durable persistence](#execution-capture-and-durable-persistence), as Piotroski's files do:
  - `execute_<module_name>` composes the instrument profile with `compose_production_profile`, so an ETF is recognized, builds the context from the selection and calls the analyzer;
  - the direct command in `cli.py`, with `--details`, `--diagnostics`, `--json`, `--save-run` and `--no-provider-check`, which calls the direct-analysis operation, and, in `application.py`, `run`, which calls `compose_<module_name>` and serves a refresh job as well as a direct analysis;
  - `SELECTION_OPTIONS` and `add_selection` beside the direct command, which carry the shared `as_of` and `use_cache` options only;
  - the tool handler's `__call__`, which validates the arguments, builds the context with `tool_context` and calls the analyzer;
  - the result's common fields: the analyzer module declares `<Name>Result` with the names, types and checks of Piotroski's result for the ticker, the requested and effective boundaries, the instrument profile, the execution status, the reason code and reason, the input failure and the warnings and diagnostics, which the shared document header and tail and the normalizer read. Add the strategy's own fields after them;
  - `from_<module_name>_capture`, which passes the evidence, the profile, the status and the recorded provider failure, as `from_piotroski_capture` does.
- It leaves these as stubs, because each is the strategy's own:
  - `compose_<module_name>(context, executed_at)` in `application.py`, which builds the analyzer and the provider the profile is composed from; `executed_at` is the run's single reading of the current time, never the `--as-of` boundary;
  - the analyzer's body;
  - the presenter;
  - the evaluation `compose`.

After the generator, these three commands are your day-to-day feedback loop: the status command, the test that lists every remaining stub, and the strict type check. The gate in step 6 runs all of them and more.

```bash
uv run python -m scripts.strategy_status <module_name>
uv run python -m pytest tests/test_no_unfilled_stubs.py -q
uv run python -m mypy --strict
```

### 2. Check the status command

```bash
uv run python -m scripts.strategy_status <module_name> [--alias <alias>]
```

- It prints `done` or `missing` for each site in the [edit-site table](#edit-sites-of-a-strategy), in table order, and a diagnostic under each missing one. It exits with code 1 while any site is missing.
- It runs the same check functions as the conformance tests, so the two cannot disagree.
- It does not run the type checker; the gate does.
- `done` means the site exists, has the required names and calls no `unfilled_stub`. A new-file site whose file still calls `unfilled_stub` is `missing`, and its diagnostic names the file and the line of each call.
- Right after the generator, expect `missing` on every site whose file has an unfilled body (`analyzer`, `codec`, `application`, `presenter`, `replay` and `evaluation`; `workspace`, `cli` and `tool` are `done`), on the reviewed sites you have not yet written, and on `schema` and `strategy-docs` until step 5. The checks of `codec`, `presenter` and `replay` save a sample run and replay it, and that sample is built from the `evaluation` file; until that is written their diagnostic ends `not checked: depends on unfilled evaluation (<file>:<line>)`. Fill the site it names first.
- If a strategy file was deleted or emptied, or a wiring entry removed, the package cannot be imported and no other site can be checked. The command matches the failing module or file against the site files and prints one `missing <site-id>` line with the file to change, and the original Python error on the next line; restore or write that site, and run the command again. An error that matches no site is printed as `missing  import` with the Python error.

### 3. Fill the stubs

Work in this order:

1. Write down the financial question and the evidence it needs.
2. Fill `vocabulary`, the models, `analyzer` and any resolver, after checking [Shared metrics and SEC inputs](#shared-metrics-and-sec-inputs).
3. Fill `evaluation`: choose the fixture ids and write `compose`, which builds the analyzer over fixture data. Do it now, because the status command cannot check `codec`, `presenter` or `replay` until it exists: their checks save and replay a sample run built from this file.
4. Fill the files that package the result: `codec`, `compose_<module_name>` in `application`, `presenter` and `replay`.
5. Add the fields `envelope` needs for what the result reports.

`selection`, `tool`, `workspace`, `cli` and the rest of `application` are complete as generated; edit them only when the strategy gains a parameter, as [When a strategy gains a selection parameter](#when-a-strategy-gains-a-selection-parameter) describes.

- The status command lists every `unfilled_stub` call that remains in a site's file, with file and line, and `uv run python -m pytest tests/test_no_unfilled_stubs.py` lists them all. The strict type check is `uv run python -m mypy --strict`, which checks the folders listed in the `[tool.mypy]` section of `pyproject.toml`.
- Financial math is deterministic Python. The authority for formula semantics is [Financial Math & Data Conventions](../user/FINANCE_MATH.md); add the strategy's definitions there and in the [Glossary](../user/GLOSSARY.md).
- Keep missing, unavailable and not-applicable evidence explicit (`MetricResult`, reason codes, retained provenance). Never substitute zero.
- Write a reason message in plain words: name an operand in words with its year-end ("Net income for 2025-12-31 is unavailable: ..."), never by its stored key (`net_income_t`). Piotroski's calculation receives the three year-ends in `PiotroskiInputs` for this purpose and spells any underscore-joined name in a provider's reason as words; the operand keys in the stored result are unchanged.
- Write tests for the rules, the unavailable-evidence cases and the edge cases as you go; see [Testing and quality expectations](#testing-and-quality-expectations).

### 4. Write the reviewed sites

The generator cannot write these. Each holds content a reviewer must judge, and its check shows only that the content exists. The kind of each site is in the [edit-site table](#edit-sites-of-a-strategy). A stored output is written by a command from the current code, so an intended change shows up as a diff to review; read each written file before committing it.

| Site | What you write | Command that writes it |
| :--- | :--- | :--- |
| `settings` | A `settings.toml` and its model, only if the strategy has user-tunable defaults ([Strategy settings](#strategy-settings)) | none; written by hand |
| `cases` | Fixtures (under `investment_analysis_engine/evaluation/fixtures/`) and reviewed Golden cases against the tool name, in `evaluation/cases/<module_name>.py` | none; written by hand |
| `catalog` | The case-module import, the case entries and the suite version bump in `evaluation/catalog.py`, and the pinned id list in `tests/evaluation/test_catalog.py` | none; written by hand |
| `direct-output` | An entry for the alias in `_COMMANDS` of `tests/_direct_command_output.py` (the command's fixed arguments), then its stored text and JSON output | `uv run python -m tests._direct_command_output` |
| `strategy-documents` | A `<alias>-success` entry in `CASES` of `tests/_strategy_document_output.py`, then its stored direct and replayed documents | `uv run python -m tests._strategy_document_output` |
| `help-snapshot` | The strategy's command row in the stored application help, and the stored help of its own command (`<alias>.txt`, which `tests/test_cli_help_output.py` requires of every declared strategy) | `uv run python -m tests._cli_help_output` |
| `guide` | The investor-facing guide under `docs/user/strategies/`, with Finance Math and Glossary links | none; written by hand |
| `glossary-terms` | The strategy's entry in its own section of `docs/user/GLOSSARY.md` (the id is `<alias>-strategy` unless the descriptor's `term` says otherwise), an entry for each headline cell and each value of each code set it defines that no entry explains yet, the cell terms in `HEADLINE_TERMS` and the value terms in `CODE_TERMS` of the strategy's `vocabulary.py`, and an `x-term` in the `Field` of each selection field that the generated selection does not already carry | `uv run python -m scripts.generate_help`, which regenerates the help bundle |

**The minimum bar for the hand-written sites**

- **A Golden case** (`cases`) runs the strategy's tool over named fixtures at a fixed `as_of` boundary and asserts its outcome and its key numbers within a stated tolerance. The strategy needs at least one case that requires its tool. The expected values are worked out independently of the code under test, by hand from the captured filings or by a separate reference calculation, never by running the strategy's own calculator. Piotroski's `PIO-01` in `evaluation/cases/piotroski.py` is a model.
- **The catalog** (`evaluation/catalog.py`) lists every case in a fixed order and carries the suite version and the fixture-set version that every evaluation report records. A new case changes what the suite measures, so give the suite version a new value (and the fixture-set version too when you add a fixture), so reports from before and after cannot be confused. `tests/evaluation/test_catalog.py` pins the exact list of case ids, so a case added, dropped or renamed without review fails.
- **The investor guide** (`guide`) tells an investor what question the method answers, what its results mean, what evidence it needs and where it stops, and links the formulas in Finance Math and the terms in the Glossary. Class names, files and how the code computes things stay in the code and its docstrings. Its served sections contain no command lines; command-line material goes in a final excluded "On the command line" subsection ([`docs/project/README.md`](README.md#served-documents) has the rules, and `scripts/check_help_content.py` enforces them).
- **Settings** (`settings`) exist only for a default a user may reasonably tune without changing what the method is, such as a window length. A settings file is wrong for a value that defines the method (Graham's 22.5), for a data-eligibility rule, and for a field that could only ever hold one value; those stay documented constants in code. [Strategy settings](#strategy-settings) has the full rule.

What a Golden case, a fixture and a catalog entry must contain in full, and how their expected values are established, is in [Evaluations & Golden Suite](../EVALUATIONS.md#5-golden-cases-and-fixtures) and its [maintenance rules](../EVALUATIONS.md#10-maintenance-rules). For the shape of a `cases` module, a catalog entry, a guide or a settings file, open the file named in the edit-site table for an existing strategy (replace `{module}` with its package name); take the structure, not its rules.

A data file that the evaluation tier reads must be listed, as an explicit path, in `[tool.setuptools.package-data]` of `pyproject.toml`, or the installed package lacks it; `tests/evaluation/test_package_data_coverage.py` fails naming any file that is not.

**Notes on the reviewed sites**

- `direct-output`: a strategy that builds its own provider reaches Yahoo (identity and instrument kind) unless the harness replaces the provider's Yahoo adapter. Patch the strategy's names in `enter_fixture_providers` of `tests/_direct_command_output.py`, as it does for Piotroski (its `ProductionFinancialFactsProvider`, given `_FixtureYahoo`) and for the others (their `YFinanceClient`). Otherwise regeneration calls the live service and stores its answer.
- `catalog`: the patches in `tests/scripts/generator_fills/patches.toml` anchor on structural text (the end of a tuple and the definition after it), never on a strategy, a case id, a version or a count, and the generator's end-to-end test bumps the suite version and the case counts itself from the files as they stand. Adding a strategy or a Golden case therefore needs no `patches.toml` edit. A Golden case still moves the suite and fixture-set versions in `evaluation/catalog.py`, [`EVALUATIONS.md`](../EVALUATIONS.md) and the case counts in `tests/evaluation/test_catalog.py` together; edit them by hand.
- A new failure: a class that declares a `reason_code` must be pinned in `tests/_failure_code_table.py`, which is written by hand and is not derived from the code.
- The smoke test: a new strategy adds its own direct command to [`docs/user/SMOKE_TESTING.md`](../user/SMOKE_TESTING.md), with that command's expectations, in the same pull request. No test checks it; the reviewer does.

**Regeneration commands**

| Command | Rewrites | Provider-check switch |
| :--- | :--- | :--- |
| `uv run python -m tests._direct_command_output` | `tests/expected_output/direct_commands/` | Needed; it runs inside `provider_check_switched_off()` |
| `uv run python -m tests._strategy_document_output` | `tests/expected_output/strategy_documents/` | Needed; the same context manager |
| `uv run python -m tests._cli_help_output` | `tests/expected_output/cli_help/` | Not needed; it runs `--help` only |
| `uv run python -m tests._workspace_command_output` | `tests/expected_output/workspace_commands/` | Not needed; its fixtures cannot fail on a provider |

- The provider-check switch matters because these commands run outside pytest, where `tests/conftest.py` does not apply: a command that fails on a provider would otherwise send a real test request while its output was being stored. A new entry point that runs a command wraps its work in `provider_check_switched_off()` from `tests/_direct_command_output.py`.
- A new workspace command needs the last command, and the scenario's steps (`_STEPS` in `tests/_workspace_command_output.py`) are edited by hand.

Each command rewrites every stored file of its kind, not only the new strategy's. Run `git diff --stat` afterwards and confirm that no existing strategy's file changed. The status command shows when a site is `done`.

### 5. Regenerate the schemas and the generated lists

```bash
uv run python -m scripts.generate_schemas
uv run python -m scripts.generate_strategy_docs
```

- Why: the published schemas and the generated lists are derived from the descriptors and the models, so any change to a descriptor, a selection, a result or a document model makes them stale. Run both after any such change, not only once.
- The first writes the strategy's published schema under `schemas/` and rewrites the two watchlist schemas, which list every strategy. The second rewrites the strategy lists in `docs/user/USAGE.md` and `docs/user/WORKSPACE.md` and the edit-site table in this guide.
- Add `--check` to either command to report what is out of date without writing. A current tree prints nothing and exits 0; a stale one prints each file and exits 1. Drift tests in the suite fail on stale output.
- Run both as `uv run python -m scripts.<name>` from the repository root, the form every diagnostic and generated-block comment gives. Running `generate_schemas.py` or `generate_strategy_docs.py` by its file path fails with `ModuleNotFoundError: No module named 'scripts'`.

### 6. Run the complete gate

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

```bash
bash "$(git rev-parse --show-toplevel)/scripts/run-quality-gates.sh"
```

- Why: the day-to-day loop checks your strategy; the gate checks the whole repository. It catches what the status command and the type check cannot: a stored output of another strategy or command that your change altered, a conformance failure in another strategy, stale generated files, the help bundle and its served-content rules, Ruff lint and formatting, and coverage.
- Run the wrapper that matches your shell; [`AGENTS.md`](../../AGENTS.md) §10 makes PowerShell the primary environment. It runs Ruff, the strict type check and the full test suite with coverage, and keeps its complete output in `gate-output.txt`; the last line it prints is that file's path. [`AGENTS.md`](../../AGENTS.md) §10 has the details.
- The gate fails while any `unfilled_stub` call remains, while any site is missing, and while a schema or generated list is stale. The conformance tests (one per site and strategy) are in `tests/test_strategy_wiring_conformance.py`, one test per site and strategy, named `test_t25_every_site_is_done_for_every_declared_strategy[<strategy>-<site>]`; the pytest failure repeats the status command's diagnostic for that site.
- If a strategy file is deleted or a wiring entry removed, pytest cannot collect the conformance test modules and reports the Python error (for example `ModuleNotFoundError` or `UndeclaredStrategyError`), followed by a line that says to run the status command. Run it: it names the site and the file to change, as in step 2.
- A stale published schema fails the schema drift test, `tests/scripts/test_generate_schemas.py::test_published_schemas_are_current`, and the `schema` site; both end with `run uv run python -m scripts.generate_schemas`. The tier coverage test checks only that each strategy has a schema file.

## Definition of done

A strategy is ready for review when the tooling and a reader both agree.

**The tooling checks:**

- [ ] The status command reports no missing site.
- [ ] The complete gate passes ([step 6](#6-run-the-complete-gate)). It fails on any `unfilled_stub` call, a strict type-check error, a missing site, a stale schema, generated list or help bundle, a served-content problem in the guide, a data file missing from package-data, and a failure class whose code is not pinned in `tests/_failure_code_table.py`.

**You check, because no test can:**

- [ ] Every stored output the regeneration commands wrote has been read, and `git diff --stat` shows no other strategy's file changed.
- [ ] The Golden cases, fixtures and catalog entries follow [Evaluations & Golden Suite](../EVALUATIONS.md#5-golden-cases-and-fixtures), with expected values established as it describes.
- [ ] The strategy's formulas are in [Financial Math & Data Conventions](../user/FINANCE_MATH.md) and its terms in the [Glossary](../user/GLOSSARY.md).
- [ ] The strategy guide explains what the method shows and where it stops, with no command lines in its served sections ([the minimum bar](#4-write-the-reviewed-sites)).
- [ ] Every reason message names its operands in plain words ([step 3](#3-fill-the-stubs)).
- [ ] [`SMOKE_TESTING.md`](../user/SMOKE_TESTING.md) has the strategy's direct command and its expectations.

## Common pitfalls

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| The status command reports `not checked: depends on unfilled evaluation` for `codec`, `presenter` or `replay` | Those checks run a stored run, which needs the evaluation file's sample selection | Fill `evaluation.py` first |
| Regenerating `direct-output` or `strategy-documents` reaches the live service | The harness does not replace the new strategy's provider | Patch its names in `enter_fixture_providers` of `tests/_direct_command_output.py` ([notes on the reviewed sites](#4-write-the-reviewed-sites)) |
| Running a generator script fails with `ModuleNotFoundError: No module named 'scripts'` | It was run by its file path | Run it as `uv run python -m scripts.<name>` from the repository root |
| `tests/evaluation/test_package_data_coverage.py` fails | A data file the evaluation tier reads is not in package-data | Add its explicit path under `[tool.setuptools.package-data]` in `pyproject.toml` |
| The generator exits with code 2 | The name is too long, or the module name, alias, tool, method identifier or a target file is already taken | Choose a free, shorter name; the generator wrote nothing |
| Every site is unchecked after a file or wiring entry was removed | The package cannot be imported | Run the status command; it names the site and the file to restore |
| `test_every_exception_that_declares_a_code_is_in_the_pinned_table` fails | A new failure class declares a `reason_code` | Add its row by hand to `tests/_failure_code_table.py` |
| A preliminary calculation module breaks another check | Code written before the generator runs ([step 1](#1-run-the-generator)) | Stop and ask; do not adjust the check |

## Edit sites of a strategy

A strategy touches the places below. Run the [status command](#2-check-the-status-command) to see which are `done` and which are `missing` for one strategy, with the diagnostic for each missing one.

- **Kind:** `new_file` is a new Python file the strategy owns, with required module-level names. `edit` is an entry added to an existing file. `reviewed` is hand-written content that a reviewer checks. `command` is a script whose output must be regenerated.
- **Generated:** `yes` means the generator makes the change in step 1.
- **Placeholders in a path or a check:** `{module}` is the strategy's package name, `{module_upper}` the same name in upper case, `{alias}` its hyphenated command alias and `{guide}` its upper-case guide name.

<!-- BEGIN GENERATED edit-sites: written by uv run python -m scripts.generate_strategy_docs; generated, do not edit by hand. -->
| Site | Edit | File | Kind | Generated | Check |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `vocabulary` | Vocabulary: the strategy's identity constants and the enumerations several of its files use. Every other file of the strategy reads its identifiers from this leaf, so it imports nothing from its package. | `investment_analysis_engine/strategies/{module}/vocabulary.py` | new_file | yes | `site_vocabulary`: the file is missing, or defines no `ANALYSIS_ID`, `METHOD_ID`, `CONFIG_SCHEMA_VERSION`; the file imports from its own package |
| `analyzer` | Analyzer module: result and analyzer, and the configuration when the strategy has one. The analyzer defines the strategy's result type, which the descriptor must agree with. | `investment_analysis_engine/strategies/{module}/analyzer.py` | new_file | yes | `site_analyzer`: the file is missing, or defines no `.+Analyzer`; analyzer X (result Y) has no descriptor |
| `settings` | Settings: the shipped settings file beside the model, only when the strategy has user-tunable defaults. A strategy's tunable defaults live in a settings.toml beside the model that validates them, and the descriptor names the model; a strategy with none has no settings.py and nothing to add. | `investment_analysis_engine/strategies/{module}/settings.toml` | reviewed | no | `site_settings`: the package has a settings.py but no settings.toml beside it, or the descriptor's settings_type is not the model that file defines |
| `descriptor` | Descriptor constant, StrategyBehavior declaration and STRATEGIES entry. The closed tuple of descriptors is what every generic consumer iterates. | `investment_analysis_engine/strategy_wiring.py` | edit | yes | `site_descriptor`: no descriptor in STRATEGIES carries the strategy's alias or package |
| `tool-name` | ToolName member. The tool enumeration is a type-level list that mypy needs and no descriptor can generate. | `investment_analysis_engine/orchestrator/tool_names.py` | edit | yes | `site_tool_name`: ToolName member X has no descriptor |
| `tool` | Arguments model, dependency class, handler. The model-facing tool surface of the strategy. | `investment_analysis_engine/strategies/{module}/tool.py` | new_file | yes | `site_tool`: the file is missing, or defines no `.+ToolArguments`, `.+ToolDependencies`, `.+ToolHandler`; tool-argument model X has no descriptor |
| `unions` | NativeEvidence and SelectionMember entries. Both unions are type-level lists that the descriptor's bounds are checked against. | `investment_analysis_engine/workspace/strategy_types.py` | edit | yes | `site_unions`: the descriptor's selection class or result type is not in the union |
| `selection` | Selection class. The stored, typed choice of this strategy's parameters. | `investment_analysis_engine/strategies/{module}/selection.py` | new_file | yes | `site_selection`: the file is missing, or defines no `.+Selection`; descriptor X has no selection member |
| `codec` | Codec and native-status function. A stored run is encoded and decoded by the strategy's own functions, and the native-status function returns the `CalculationStatus` the strategy reports. | `investment_analysis_engine/strategies/{module}/codec.py` | new_file | yes | `site_codec`: the file is missing, or defines no `encode_.+`, `decode_.+`, `.+_native_status`, `.+_ticker`; the stored run does not decode to the result execute stored |
| `workspace` | Workspace adapter, capture type, normalizer. The adapter runs the analyzer and the normalizer hands `ExecutionCapture` the evidence, the profile, the native status and the provider failure it recorded. It never names a `RunOutcome`: `RunOutcome.from_status` produces the outcome and `ExecutionCapture` derives it. | `investment_analysis_engine/strategies/{module}/workspace.py` | new_file | yes | `site_workspace`: the file is missing, or defines no `.+Capture`, `from_.+_capture` |
| `application` | Application file: run function. The strategy composes its own providers and settings, and its run function returns the run with the means to present it as a document and as text, so no caller needs the strategy's presentation. | `investment_analysis_engine/strategies/{module}/application.py` | new_file | yes | `site_application`: the file is missing, or defines no `run` |
| `cli` | CLI file: direct command, add-selection command and the table of selection options. The strategy's command-line behavior lives in its own package, and the command takes its exit code from `exit_code_of` in `application/analysis.py`. | `investment_analysis_engine/strategies/{module}/cli.py` | new_file | yes | `site_cli`: the file is missing, or defines no `SELECTION_OPTIONS`, `add_selection`, `command` |
| `cli-tier` | CLI-tier entry. A lower layer cannot import the command file, so the tier pairs it with the descriptor's behavior. | `investment_analysis_engine/cli_strategy_wiring.py` | edit | yes | `site_cli_tier`: strategy X is not wired in: CLI tier |
| `application-tier` | Application-tier entry. The application operations cannot import the strategy by name, so the tier pairs its run function with the descriptor's behavior. | `investment_analysis_engine/application/tier.py` | edit | yes | `site_application_tier`: strategy X is not wired in: application tier |
| `presenter` | Presenter and JSON builder. The strategy renders its own result in every presentation mode. | `investment_analysis_engine/strategies/{module}/presenter.py` | new_file | yes | `site_presenter`: the file is missing, or defines no `render_.+`, `build_.+_document`; the replayed JSON does not validate as X |
| `envelope` | Envelope model and document version. Every --json document is a typed model with a published schema. | `investment_analysis_engine/strategies/{module}/envelope.py` | new_file | yes | `site_envelope`: the file is missing, or defines no `DOCUMENT_SCHEMA_VERSION`; command X offers --json but has no typed document model |
| `replay` | Replay projector and headline function. A stored run is replayed through the strategy's own text projector and document projector, and the same file holds the strategy's headline function, which supplies its cells to the side-by-side refresh table. | `investment_analysis_engine/strategies/{module}/replay.py` | new_file | yes | `site_replay`: the file is missing, or defines no `project_.+`, `project_.+_document`, `headline_.+`; replay in X mode raised or is empty, or the replayed document is not X's document |
| `evaluation` | Evaluation file: fixture composition, requirement, the fixture ids it understands and a sample selection. The evaluation tier composes the strategy's fixtures from this file. | `investment_analysis_engine/strategies/{module}/evaluation.py` | new_file | yes | `site_evaluation`: the file is missing, or defines no `FIXTURE_IDS`, `REQUIREMENT`, `SAMPLE_SELECTION`, `compose`; strategy X requires fixture ids that its evaluation tier entry and the context do not declare |
| `evaluation-tier` | Evaluation-tier entry. The tier pairs the strategy's bundle with its requirement, ids, sample selection and composition. | `investment_analysis_engine/evaluation/strategy_fixtures.py` | edit | yes | `site_evaluation_tier`: strategy X is not wired in: evaluation tier |
| `cases` | Fixtures with their fixture ids, and cases with their reviewed arguments table. Reviewed case truth is written by hand against tool names; the fixtures live in the evaluation fixtures package. | `investment_analysis_engine/evaluation/cases/{module}.py` | new_file | no | `site_cases`: the file is missing, or defines no `{module_upper}_ARGUMENTS`, `{module_upper}_CASES`; tool X is required by no golden case |
| `catalog` | Catalog: the case-module import, the case tuple entries and the suite version bump; the pinned id list in the catalog test. The case tuple, the suite version and the pinned ids are reviewed evaluation truth; the check cannot tell whether the suite version was bumped. | `investment_analysis_engine/evaluation/catalog.py` | reviewed | no | `site_catalog`: the catalog does not import the case module, or a case id is not pinned in the catalog test |
| `direct-output` | Direct command expected output: the command's fixed arguments and its stored text and JSON output. The direct command's text and JSON output are compared byte for byte with reviewed files, and the failure-message and save-run tests run the command from its fixed arguments. | `tests/expected_output/direct_commands/{alias}.txt` | reviewed | no | `site_direct_output`: tests/_direct_command_output.py has no entry for the alias in _COMMANDS, or the stored .txt or .json output does not exist |
| `strategy-documents` | Stored strategy document: the success case and its stored direct and replayed documents. The typed document is compared byte for byte with a reviewed file, direct and replayed, and the provider-check and envelope-version tests start from the strategy's cases. | `tests/expected_output/strategy_documents/{alias}-success.direct.json` | reviewed | no | `site_strategy_documents`: tests/_strategy_document_output.py has no case named <alias>-success, or the stored .direct.json or .replay.json document does not exist |
| `help-snapshot` | Help snapshots: the strategy's row in the application help and the help of its direct and add-selection commands. The application's help is compared byte for byte with a reviewed snapshot that lists every command in the order it is added, and each strategy command's help with a snapshot of its own. | `tests/expected_output/cli_help/application.txt` | reviewed | no | `site_help_snapshot`: the application snapshot has no command row for the alias, or tests/expected_output/cli_help/<alias>.txt or watchlist-add-selection-<alias>.txt does not exist |
| `guide` | User guide with FINANCE_MATH.md and GLOSSARY.md links. Each strategy has an investor-facing guide, which the help bundle serves: its explanatory sections are interface-neutral, and command-line material goes in excluded sections (whole sections, or a final 'On the command line' subsection), which scripts/check_help_content.py and tests/scripts/test_served_content.py enforce. The help bundle is regenerated after a guide changes (uv run python -m scripts.generate_help). | `docs/user/strategies/{guide}.md` | reviewed | no | `site_guide`: no guide for alias X |
| `glossary-terms` | Glossary terms: the strategy's own entry, and the terms of its headline cells, selection fields and code sets. A client explains every label, status and code the API returns through the glossary, so the strategy names the term of its own entry (the descriptor's term), of each headline cell (headline_terms), of each selection field (an x-term in its Field) and of each value of each code set it defines (code_terms, with the tables beside the enumerations in vocabulary.py), and each term is an entry the help bundle serves. A new entry goes in the strategy's section of docs/user/GLOSSARY.md, and the help bundle is regenerated (uv run python -m scripts.generate_help). | `docs/user/GLOSSARY.md` | reviewed | no | `site_glossary_terms`: the descriptor's term, a headline_terms or code_terms term or a selection field's x-term is missing, or names an entry that is not in the glossary's served sections, or a headline cell carries a term other than its headline_terms entry |
| `schema` | Published schema (run uv run python -m scripts.generate_schemas). Every strategy document has a checked-in schema. | `schemas/{alias}.schema.json` | command | no | `site_schema`: schema schemas/<alias>.schema.json is missing or out of date; run uv run python -m scripts.generate_schemas |
| `strategy-docs` | Generated strategy lists (run uv run python -m scripts.generate_strategy_docs). The strategy lists in USAGE.md and WORKSPACE.md are generated from the descriptors, one entry per strategy. | `docs/user/USAGE.md` | command | no | `site_strategy_docs`: the strategy is missing from the generated block of USAGE.md or WORKSPACE.md, or a block is out of date; run uv run python -m scripts.generate_strategy_docs |
<!-- END GENERATED edit-sites -->

## Strategy settings

A strategy gets a settings file only when it has defaults a user may reasonably tune without changing what the method is, such as window lengths, look-back periods or a history start date. Values that define the method (for example Graham's 22.5) and data-eligibility rules stay in code as documented constants. A strategy with nothing to tune has no `settings.py` and no `settings.toml`, and its descriptor has `settings_type=None`. The generator writes no settings file: it cannot know the settings, and a model that can hold only one value is not allowed.

When a strategy does get settings, add these, in this order:

| # | Add | Rule |
| :--- | :--- | :--- |
| 1 | `settings.py` in the strategy package with a `<Strategy>Settings` model | Frozen, forbids unknown keys, strict types and **no defaults**; validators enforce invariants (for example short window < long window); each field's docstring documents its key |
| 2 | `settings.toml` beside `settings.py` | The shipped file is the single source of every default value: flat keys, each with a one-line comment |
| 3 | The model on the descriptor | Set `settings_type` to the model in `strategy_wiring.py` |
| 4 | The entry points below | The strategy never reads settings; composition loads them and passes them in |

Users override any subset of the keys in `strategies/<alias>.toml` in their settings folder. The loader merges the two files per key, and a missing, invalid or unknown key stops every command, including `--help`, with exit code 2.

**Entry points**

| Entry point | How the settings arrive |
| :--- | :--- |
| Direct command | A loader function in the strategy's `application.py`, such as `momentum_settings`, takes the application context and supplies the command's option defaults, so `--help` shows the configured values |
| Workspace selection | The configured values are copied into the selection when it is created; a later edit to the file never changes a saved entry, and replay never reads settings |
| Calculation constants | Passed to the analyzer when it is built |
| Local-model tool | The handler receives the settings in its dependencies; a tool argument with a configured default is optional, `None` means "use the configured value", and the field description says so |

Golden evaluation never reads a settings file: its composition passes fixed settings, so editing a file cannot change Golden results or the model prompt.

The `settings` site is reviewed. It is done when the package has no `settings.py`, and when it has one only if a `settings.toml` sits beside it and the descriptor's `settings_type` is the model that file defines. A conformance test also checks that every declared model has a shipped file that validates, that every shipped file belongs to a descriptor, and that every model is frozen, forbids unknown keys and has no defaults. The [Architecture](ARCHITECTURE.md#6-analysis-strategies-the-boundary) gives the rationale.

### When a strategy gains a selection parameter

The generator writes the form with no configuration. When the strategy gets a parameter a user selects (a window length, a horizon), move to the configured form, as FCF & Earnings Growth did. The names below are FCF-Growth's.

1. In `analyzer.py`, change `BaseAnalyzer[XResult]` to `BaseAnalyzer[XResult, XConfig]`.
2. Add the `config` parameter to `run_analysis`, after `context`: `run_analysis(self, ticker, context, config)`.
3. Add `<Name>Config` (`FCFEarningsGrowthConfig` in `models.py`) and `to_<name>_config()` on the selection (`to_fcf_config()` in `selection.py`), and the parameter itself as a field of the selection.
4. Pass the config through every caller: the tool handler builds it from the validated arguments (`tool.py`), `execute_<name>` takes it as a parameter, and the direct command builds it from its options. `run` builds it from the selection with `stored_configuration(selection.to_<name>_config)`, for a refresh job as for a direct analysis.
5. Bump `CONFIG_SCHEMA_VERSION` in `vocabulary.py`, because the persisted selection changed shape: runs stored under the older version are refused when read, with no migration, and the pull request lists the change among its user-visible changes ([`AGENTS.md`](../../AGENTS.md) §4).
6. Add the option as an `Annotated` alias in `cli.py` that both the direct command and `add_selection` use, a row for it in `SELECTION_OPTIONS`, and the argument to the tool arguments model; give the field a description in the selection; then regenerate the schemas and the stored outputs as in steps 4 and 5 of the workflow. A selection field that the strategy's settings supply is also named in the descriptor's `selection_settings_fields`.

## Testing and quality expectations

Test the method's own meaning and boundaries: valid calculations, policy branches, time-boundary behavior, missing or incompatible evidence, and provenance. Deterministic tests should use fixtures or provider fakes rather than real external API or LLM calls. Test adapter outcome mapping and workspace persistence at their respective boundaries when those areas are touched.

Follow the repository's established static checks and pytest practices described in the [project instructions](../../AGENTS.md).

### Where tests and fixtures live

| What | Where | Notes |
| :--- | :--- | :--- |
| A strategy's tests | `tests/analysis/<folder>/` | One folder per method, named for the method: `piotroski`, `momentum`, `fcf_earnings_growth` (package `fcf_growth`) and `graham_value` (both Graham packages) |
| Shared-metric tests | `tests/analysis/shared/` | Helpers `_issuer_inputs.py` and `_metric_input_rig.py` serve captured issuers to the assembly functions |
| Captured balance-sheet documents | `evaluation/fixtures/sec_edgar/instant_facts/` | One trimmed Company Facts and submissions document per issuer; a `SHA256SUMS` file lists the folder, and a test fails when a file and its sum differ |
| Captured annual documents | `evaluation/fixtures/sec_edgar/annual_facts/` | The same issuers' annual concepts; the same `SHA256SUMS` rule |
| Captured filing headers | `evaluation/fixtures/sec_edgar/filing_headers/` | The as-filed SIC code of an issuer's anchor filing (`<issuer>_fy<year>.hdr.sgml`); the same `SHA256SUMS` rule |
| Frozen foreign-private-issuer documents | `evaluation/fixtures/sec_edgar_fpi.py`, documents in `evaluation/fixtures/sec_edgar/step_2_5a_d0/` | Four fixed issuers (ASML, Nutrien, SAP, Novo Nordisk) for the Golden cases of the foreign-filer boundaries |

- **Which to use:** use the captured folders for a regression test of a shared metric or a strategy over real filings, and the frozen foreign-private-issuer documents when the case is the foreign-filer boundary itself (Form 20-F or 40-F, IFRS, the security unit).
- **Merging:** a test that needs both the balance-sheet and the annual concepts of an issuer has to merge the two documents. `fixture_statements_adapter(fixture_id, clock_at=...)` in `evaluation/fixtures/sec_edgar_statements.py` does it: it merges the two Company Facts documents and the filings of both, serves the issuer's filing header, and returns the real SEC adapter, so Golden cases and tests run its own year-end discovery and series resolution with no network access.
- **Point-in-time trimming:** a capture as of a past boundary keeps only the filings accepted by that boundary. Apple's keeps its fiscal 2024 report and the two before it, and its tests use the boundary 2024-11-15 ([input evidence](milestones/v0.2/step-3.5/STEP_3_5_3_INPUT_EVIDENCE.md#2-sources)).
## Background: how a strategy fits into the code

**You are here:** past the workflow. Nothing below is needed to add an ordinary strategy; each section explains code a workflow step relies on, for when you want to understand it or a check fails in a way the diagnostic does not explain. [Shared metrics and SEC inputs](#shared-metrics-and-sec-inputs) is the exception: read it before writing the analyzer. The [Architecture](ARCHITECTURE.md) documents the boundaries and the rationale.

### What an analysis strategy is

An analysis strategy is a named, deterministic method that resolves the evidence it needs, applies explicit financial rules in Python, and returns a typed result. Strategies may have different inputs, policies, calculations, and result models while sharing application infrastructure.

The [user-facing strategy guides](../user/strategies/README.md) explain the behavior and limitations of implemented strategies. This guide focuses on how they fit into the code.

### The current analyzer contract

[`BaseAnalyzer`](../../investment_analysis_engine/analysis/base_analyzer.py) is one abstract generic class, `BaseAnalyzer[ResultT, *ConfigT]`. `ResultT` is the complete evidence type the strategy returns. `ConfigT` holds zero or one type; a class that gives more than one raises a `TypeError` naming it, and a configuration is never added to hold a single value. The argument order is `(ticker, context, config)` everywhere.

| Specialization | Method | Example |
| :--- | :--- | :--- |
| `BaseAnalyzer[XResult]`, no configuration; the form the generator writes | `run_analysis(self, ticker, context)` | `PiotroskiAnalyzer(BaseAnalyzer[PiotroskiResult])` |
| `BaseAnalyzer[XResult, XConfig]`, one typed configuration | `run_analysis(self, ticker, context, config)` | `FCFEarningsGrowthAnalyzer(BaseAnalyzer[FCFEarningsGrowthResult, FCFEarningsGrowthConfig])` |

The configuration may be a Pydantic model, a frozen dataclass or another typed shape. `analyzer_result_type` and `analyzer_config_type` in the same module read the types a class declares, and the second returns `None` for the form with no configuration. The base contract does not implement input resolution, provider access, presentation, or persistence.

Every analyzer inherits from `BaseAnalyzer` with its own result type; Momentum, Graham Number, Graham Growth and FCF & Earnings Growth also have a configuration type and Piotroski has none. The common interface does not make their calculation semantics or result models interchangeable. To move a strategy from the first form to the second, follow [When a strategy gains a selection parameter](#when-a-strategy-gains-a-selection-parameter).

`AnalysisContext` is the frozen per-run value object for cross-cutting execution concerns:

- `as_of` is the requested point-in-time boundary, or `None` when the caller did not request one. It is not replaced with a fabricated historical date.
- `executed_at` is the timezone-aware execution clock captured once by the caller for the analysis run.
- `effective_as_of` is a derived property: the requested `as_of` when present, otherwise `executed_at`. Analysis-layer data must respect this cutoff.
- `use_cache` is the run-wide permission governing cache reads and writes used by the analysis.
- `instrument_profile` carries the run's identity evidence. It is retained in results even when the calculation does not consult it.

For the full clock model — which instant each kind of check compares against, the decision-clock/event-clock distinction, `utc_now()`, and why frozen-clock skew is tolerated only for live runs — see ARCHITECTURE.md's [*Time and the analysis boundary*](ARCHITECTURE.md#5-time-and-the-analysis-boundary) rather than this guide; duplicating those rules here would let the two drift.

The workspace selections expose `to_analysis_context(executed_at, instrument_profile)` alongside method-specific config conversion. Direct execution adapters and orchestrator handlers construct this context at their execution boundary. See [`AnalysisSelection`](../../investment_analysis_engine/workspace/strategy_types.py) and each strategy's `selection.py` under `investment_analysis_engine/strategies/` for its method-specific request model, and [`AnalysisRequest`](../../investment_analysis_engine/workspace/requests.py) for the workspace request boundary. The [Architecture](ARCHITECTURE.md) documents broader boundaries and rationale.

### How a strategy runs

An invocation begins in the CLI, the API or the orchestrator, which validates the method-specific selection. The direct-analysis operation (`analyze` in `investment_analysis_engine/application/analysis.py`) finds the strategy's run function in the application tier, which composes the provider, cache, resolver, and adapter dependencies from the application context. The adapter in the strategy's `workspace.py` prepares the run's config and `AnalysisContext`, invokes the analyzer, and packages the native result with its profile and normalized execution outcome. The strategy's `application.py` builds the document and the text of that result; the operation returns them in an `AnalysisOutcome`, and a direct command writes them. In the workspace flow, a capture callable returns a normalized capture to common `workspace.execute()`, which records envelope timing, encodes native evidence, constructs an `AnalysisRun`, and inserts it through the run repository.

The adapter connects a method to execution capture; it does not duplicate its financial rules. Common workspace execution owns the shared run envelope and persistence boundary; it does not calculate strategy metrics or reclassify the financial result.

#### Strategy integration architecture

The strategy supplies its own configuration (when it has one), inputs, calculations, and result; composition supplies the context and shared infrastructure. Persistence is conditional, not automatic: `analyze` (`investment_analysis_engine/application/analysis.py`) is the one place that decides, from its `save` argument (the `--save-run` option), whether a run reaches `workspace.execute()` at all. Every direct command calls it. A watchlist refresh reaches the same `execute()` through its own composition in `investment_analysis_engine/workspace/refresh.py` instead, running each job through the same run function.

**What the contributor owns:** strategy policy/configuration where there is any, required input semantics, deterministic calculations, typed result, tests, user-facing presentation where needed, and its execution-adapter integration. **What is shared:** provider/cache contracts, provenance values, the shared metrics and input assembly of [Shared metrics and SEC inputs](#shared-metrics-and-sec-inputs), the `analyze`/refresh persistence decision, workspace execution, run persistence, and shared financial conventions. Reuse the shared boundaries instead of rebuilding them inside a strategy.

#### What happens during an FCF & Earnings Growth run

*Optional reference: read this only to trace a configured strategy end to end, for example while debugging a run. Adding a strategy does not need it.*

`analyze` (`investment_analysis_engine/application/analysis.py`) runs the strategy's run function from the application tier, marking the save stage so that a failure after the analysis finished is reported as a failure while saving. When `save` is false (no `--save-run`) the run function is called directly — the default direct-command path never touches `workspace.execute()`, opens no database, and builds no durable profile cache. Only when `save` is true does it open a database, build the capture closure, and call `execute()`. A watchlist refresh never goes through `analyze`; it reaches `workspace.execute()` through its own composition in `investment_analysis_engine/workspace/refresh.py`, following the same adapter/normalize contract.

The steps below follow one `fcf-growth` command. The shared table gives the order; steps 4 and 13 differ by whether `--save-run` is set, and the two short tables after it give those steps for each branch.

**Shared steps**

| Step | Who | Does what |
| --- | --- | --- |
| 1 | User | Invokes `fcf-growth`. |
| 2 | CLI | Resolves the ticker and the presentation mode with `resolve_command_target`, parses the options and builds the `FCFGrowthSelection`. |
| 3 | CLI | Calls `analyze_for_command`, which calls `analyze` with the application context, the ticker, the selection, `save_run` and the provider-check choice. |
| 4 | `analyze` | Reads `executed_at` once, finds FCF Growth's run function in the application tier, and reaches it: steps 4a, or 4b to 4d. The run function composes the cache, the provider (`build_sec_production_provider`), the `ProductionAnnualGrowthSeriesResolver` and the market-data dependencies, and calls the adapter, `execute_fcf_growth(...)`. |
| 5 | Adapter | Composes the instrument profile, through the profile cache when one was supplied. |
| 6 | Adapter | Constructs the `AnalysisContext` from `as_of`, `executed_at`, `use_cache`, and the profile. |
| 7 | Adapter | Calls `FCFEarningsGrowthAnalyzer.run_analysis(ticker, context, config)`. |
| 8 | Analyzer | Reads `effective_as_of`, `use_cache`, and the profile from the context and calls the resolver with `as_of` and `effective_as_of` separately. |
| 9 | Resolver | Looks up the resolved-input cache when it is enabled and, on a miss, reads each annual field through `InputResolver.resolve_annual_series` from the `FinancialFactsProvider`. |
| 10 | Resolver | Returns the resolved observations and their provenance trace to the analyzer. |
| 11 | Analyzer | Calculates the growth metrics and classification; when the FCF yield is requested, takes its market capitalization from `anchor_year_end_scope` and `resolve_market_cap_inputs` in `analysis/shared/metric_inputs.py`; returns a `FCFEarningsGrowthResult`. |
| 12 | Adapter | Returns an `FCFGrowthCapture` holding the result and the profile. The normalizer `from_fcf_growth_capture` passes the result's `execution_status` and the recorded provider failure to `ExecutionCapture`, which derives the outcome through `RunOutcome.from_status`. |
| 13 | `analyze` | Hands the capture back: step 13a, or 13b to 13d. After a failure it runs the provider check once, and it returns an `AnalysisOutcome` holding the document, the saved run's ID, the run's outcome and the means to render the text modes. |
| 14 | CLI | Calls `analysis_output` on the outcome, which takes the exit code from `exit_code_of` of its outcome (1 for unavailable and failed, 0 otherwise) and writes the document in the `--json` mode or the outcome's text in the other modes. It then calls `emit_output`, which writes the text and exits with that code. |

**Branch: `--save-run` not set (default)**

| Step | Who | Does what |
| --- | --- | --- |
| 4a | `analyze` | Calls the run function directly with no profile cache. |
| 13a | `analyze` | Keeps the run as it is. |

**Branch: `--save-run` set**

| Step | Who | Does what |
| --- | --- | --- |
| 4b | `analyze` | Builds the request, opens the database, checks that it is ready, and builds the durable profile cache. |
| 4c | `analyze` | Calls `workspace.execute(request, capture)`. |
| 4d | `workspace.execute()` | Calls `capture()` once. `capture()` calls the run function with the profile cache, which calls the adapter and normalizes the adapter's capture with `from_fcf_growth_capture()` into an `ExecutionCapture`. |
| 13b | `workspace.execute()` | Inserts the `AnalysisRun` into the repository and returns it. |
| 13c | `analyze` | Returns the saved run's ID in the outcome; the command writes it to stderr before the result. |
| 13d | `analyze` | Keeps the run it made, with the means to present it. |

`FCFEarningsGrowthAnalyzer` implements `BaseAnalyzer[FCFEarningsGrowthResult, FCFEarningsGrowthConfig]`; the steps above show the per-run interactions after composition. Presentation always renders the adapter's own capture — `--save-run` changes only whether that capture is also persisted, never what the user sees.

**For a new strategy's SEC inputs, start from `analysis/shared/metric_inputs.py`** ([Shared metrics and SEC inputs](#shared-metrics-and-sec-inputs)), not from FCF-Growth's `ProductionAnnualGrowthSeriesResolver`. That resolver exists for FCF-Growth's own annual growth series and its checks and selection; the FCF analyzer itself already takes its market capitalization from the shared entry (step 11). Piotroski, the form with no configuration, shows a strategy built wholly on the shared inputs.

The direct command and watchlist-refresh paths reuse the same method adapter, but the common persistence wrapper (`workspace.execute()`) is only involved when an Analysis Run is being recorded. A financially negative screen can still have a completed execution outcome; the strategy's classification and software run status answer different questions.

### Where financial data comes from

The strategy determines which financial capability its semantics require. FCF growth uses a `FinancialFactsProvider` through its production annual-series resolver, currently backed by SEC EDGAR for the required completed annual cash-flow and EPS facts; a strategy that needs other SEC evidence starts from the shared assembly functions in [Shared metrics and SEC inputs](#shared-metrics-and-sec-inputs). The resolution layer can use an optional cache and returns typed inputs with source, period, availability, retrieval, and transformation lineage. Historical prices, company financial facts, quotes, and macro observations are distinct capabilities; do not treat one as a substitute for another.

`use_cache` controls whether the resolver can use its configured resolved-input cache. Provider and cache composition belongs at the application boundary. Detailed financial definitions, conventions, and data limitations belong in [Financial Math & Data Conventions](../user/FINANCE_MATH.md) and the relevant [strategy guide](../user/strategies/FCF_GROWTH.md).

### How inputs and provenance are handled

An input resolver turns provider evidence into strategy-appropriate typed observations. For FCF growth, `ProductionAnnualGrowthSeriesResolver` selects compatible, contiguous annual evidence under the requested `as_of`, records a `ResolutionTrace`, and returns annual observations whose component values retain `ResolvedInput` provenance. The analyzer consumes the resolved assembly; it does not fetch from providers itself.

Keep missing, unavailable, and not-applicable evidence explicit. Preserve source and time metadata, transformations, cache/override state, and diagnostics at the boundary that resolves the value. Do not silently substitute zero or hide a provider limitation.

### Shared metrics and SEC inputs

**On the critical path:** read this before writing the analyzer.

Before writing a private resolver, check whether a shared function already supplies the input. The shared code is under [`investment_analysis_engine/analysis/shared/`](../../investment_analysis_engine/analysis/shared); a strategy calls it and does not rebuild it.

| Entry point | Home | Call it when | Instead of |
| :--- | :--- | :--- | :--- |
| Pure shared metrics | Modules of `analysis/shared/`: `cash_flow`, `enterprise_value` (`compute_total_debt`, `compute_long_term_debt`, `compute_enterprise_value`), `invested_capital`, `market_cap` (`compute_market_cap`), `operating_metrics` (`compute_gross_profit`, `compute_ebit`, `compute_ebitda`), `split_adjustment` and `applicability` | The strategy needs a metric another strategy may share | Writing the formula again |
| Assembly functions | [`analysis/shared/metric_inputs.py`](../../investment_analysis_engine/analysis/shared/metric_inputs.py): `anchor_year_end_scope`, `resolve_market_cap_inputs`, `resolve_year_ends`, `resolve_balance_sheet_values` and `resolve_balance_sheet_values_at`, `resolve_annual_values` and `resolve_annual_values_at`, `resolve_share_count_series`, `resolve_industry_class` | The metric's inputs are needed at the anchor year-end or at several year-ends | A private resolver that fetches from the provider |
| Scope-bound source protocol | `AsFiledSicSource` in `metric_inputs.py` | The input is tied to the analysis scope, such as the industry class from the as-filed SIC code. The SEC adapter implements the protocol | Passing the resolver, which reaches the adapter only through the production provider |
| Adapter builder | `build_sec_edgar_adapter` in [`application/providers.py`](../../investment_analysis_engine/application/providers.py) | Composition needs the SEC adapter itself. It checks the declared identity and applies the ticker overrides | Constructing `SecEdgarFinancialFactsAdapter` by hand |

- **Composition:** build the adapter once. `compose_piotroski` in `strategies/piotroski/application.py` wraps it in a `ProductionFinancialFactsProvider` for the resolver and passes the same adapter as the analyzer's `AsFiledSicSource`, so the industry class and the inputs are read from the same analysis scope.
- **Failures:** the assembly functions never raise a provider failure. They return a `MetricInputsFailure` that carries the provider-failure record, and a strategy calls no metric after one. An input that is merely unavailable is returned as its reason, so the metric can report it.
- **A new optional provider capability is still forwarded by hand.** `ProductionFinancialFactsProvider` in `data/financial/production.py` has one method per optional capability, answers with its own typed result when the adapter lacks the capability, and checks the capability's protocol, so a new request type needs an edit there. A conformance test (`tests/data/test_production_capability_forwarding.py`) finds every runtime-checkable capability protocol that a production adapter implements and fails, naming the protocol and the adapter, when the production provider does not implement it too. Extending the instant series avoided a new capability for the share counts, and the adapter as `AsFiledSicSource` avoids it for the SIC code; that protocol is not runtime-checkable, so the test does not cover it.

### How calculations produce a typed result

Calculations are deterministic Python operations. The FCF strategy derives free cash flow and free cash flow per diluted share from admissible annual evidence, computes its growth metrics, and classifies the result using its explicit policy. `FCFEarningsGrowthResult` retains the metrics, classification, selected horizon, observations, warnings, instrument profile, and resolution diagnostics. Its financial `PASS`, `FAIL`, or `INDETERMINATE` classification is distinct from `CalculationStatus` and from the workspace's run outcome.

Do not make the LLM responsible for financial calculations. Avoid copying formulas into a contributor guide when the financial authority already documents them.

### How results become user-visible

Direct analysis commands send a native typed result to the strategy's presentation function. FCF uses `render_fcf_earnings_growth`, with concise, details, diagnostics, and JSON modes built around the strategy's own model. Shared formatting utilities in [`investment_analysis_engine/reporting/presentation.py`](../../investment_analysis_engine/reporting/presentation.py) provide common vocabulary; they do not homogenize strategy result types. Saved-run views project from the persisted evidence rather than rerunning providers or calculations.

Provide presentation behavior that makes the result, limitations, and relevant provenance understandable. Keep presentation-only wording out of financial calculations.

### Execution capture and durable persistence

The FCF-specific `execute_fcf_growth` adapter composes the profile and `AnalysisContext`, and invokes the analyzer. It returns an `FCFGrowthCapture` with the native result and profile; the caller normalizes that capture to the common `ExecutionCapture`, which takes the result's `execution_status` and derives the `RunOutcome` through `RunOutcome.from_status`, the one rule every strategy shares. The common [`workspace.execute()`](../../investment_analysis_engine/workspace/execution.py) invokes a capture callable, records its own `started_at` and `completed_at` envelope timestamps, encodes the native evidence, assembles the common run record, and inserts it into the provided repository. These persistence-envelope timestamps are separate from the analysis context's `executed_at`. [`AnalysisRun`](../../investment_analysis_engine/workspace/runs.py) is the durable domain record for the request/configuration snapshot, timing, versions, status, result evidence, presentation inputs, and profile.

The adapter is strategy-specific integration work. The workspace execution service is shared infrastructure and must not become a second implementation of a strategy's semantics. Do not assume every adapter has the same signature or that `BaseAnalyzer` is a unified execution interface.

The helpers that the 3.5.3 repetition review extracted are functions, not a base class or mixin ([review](milestones/v0.2/step-3.5/STEP_3_5_3_SLICE_PLAN.md#b4-repetition-review-353e1)). Use them in a strategy's files:

| Helper | Home | What it does |
| :--- | :--- | :--- |
| `snapshot_by_revalidation` | `analysis/run_models.py` | Codec: dumps the evidence model to JSON, decodes the dump and returns it |
| `validate_wire` | `analysis/run_models.py` | Codec: strict JSON validation of the wire object, refusing a non-finite number |
| `decode_with_native_identifiers` | `analysis/run_models.py` | Codec: checks the identifiers and versions of a stored result against the declared ones, then validates (FCF-Growth, Piotroski) |
| `decode_with_method_sections` | `analysis/run_models.py` | Codec: checks each method section of a stored analysis carries the declared method, then validates (the Graham strategies) |
| `resolve_command_target` | `cli_support.py` | Command: resolves the ticker and the presentation mode and records each on the failure scope |
| `analysis_output` | `cli_support.py` | Command: the exit code of the outcome and the text to write, the document in the `--json` mode and the outcome's rendering in the others |
| `analyze_for_command` | `cli_support.py` | Command: calls the direct-analysis operation with the command's application context and reports the saved run's ID |
| `emit_output` | `cli_support.py` | Command: writes the output (standard error for a failure in the concise and details modes) and exits with the code |
| `AS_OF_OPTION`, `SAVE_RUN_OPTION`, `NO_PROVIDER_CHECK_OPTION` | `cli_support.py` | Command: the three option declarations that read the same in every command |
| `analyze` | `application/analysis.py` | Operation: runs the strategy's run function, saves the run when asked, runs the provider check after a failure and returns the outcome |
| `tool_context` | `strategies/_shared/tool.py` | Tool handler: validates the clock, resolves the profile once, builds the `AnalysisContext` |
| `run_analyzer_with_profile` | `strategies/_shared/invocation.py` | Execution: composes the profile, builds the context and runs the analyzer (the Graham strategies) |
| `compose_production_profile` | `strategies/_shared/profile.py` | Execution: the instrument profile composition |

The `use_cache` field is declared once, in `AnalysisToolArguments` (`orchestrator/analysis_tool_arguments.py`), which every tool arguments model subclasses. `from_<name>_capture`, the evidence validators, `build_selection` and `run` stay in each strategy: each reads, builds or composes something different.

### Strategy-specific responsibilities and shared infrastructure

| Strategy-specific work | Shared infrastructure to reuse |
| --- | --- |
| Configuration or policy and its semantic rules, when the strategy has any | `BaseAnalyzer[ResultT, *ConfigT]`, `AnalysisContext`, workspace request selections |
| Strategy analyzer and typed result | `ResolvedInput`, `ResolutionTrace`, provider contracts |
| Input requirements and calculations; a resolver of its own only for evidence no shared entry supplies | The shared metrics and input assembly of `analysis/shared/` ([Shared metrics and SEC inputs](#shared-metrics-and-sec-inputs)), financial-fact providers, historical-price providers, and caches where applicable |
| Focused tests for rules, unavailable evidence, and edge cases | Common `workspace.execute()`, `AnalysisRun`, repositories, and evidence codecs |
| Investor-facing rendering and strategy guide | Shared presentation vocabulary and financial conventions |
| Strategy-specific execution adapter integration | CLI/workspace composition and persistence boundaries |

This is a responsibility map. A strategy's analyzer, codec, execution adapter and presenter live in `investment_analysis_engine/strategies/<strategy>/`, in files named for their role. Keep method semantics in the strategy layer, provider composition at application boundaries, and common execution capture/persistence in the workspace layer.

### Existing strategy reference: FCF & Earnings Growth and Piotroski

FCF growth is a useful end-to-end example of the configured form because its resolver, calculation, presentation, adapter, and workspace capture are separately visible. Piotroski is the example of the config-free form with shared SEC inputs. Current names and locations, under `investment_analysis_engine/strategies/`:

| Generic concept | FCF & Earnings Growth (configured form) | Piotroski (config-free form, shared SEC inputs) |
| --- | --- | --- |
| Strategy configuration | `FCFEarningsGrowthConfig` in [`models.py`](../../investment_analysis_engine/strategies/fcf_growth/models.py), built from `FCFGrowthSelection.to_fcf_config()` in [`selection.py`](../../investment_analysis_engine/strategies/fcf_growth/selection.py) | None; `PiotroskiSelection` in [`selection.py`](../../investment_analysis_engine/strategies/piotroski/selection.py) holds `as_of` and `use_cache` only |
| Strategy policy | `FCFEarningsGrowthPolicy` in [`models.py`](../../investment_analysis_engine/strategies/fcf_growth/models.py), held by the config | The nine tests, fixed in code in [`calculation.py`](../../investment_analysis_engine/strategies/piotroski/calculation.py) |
| Strategy analyzer | `FCFEarningsGrowthAnalyzer(BaseAnalyzer[FCFEarningsGrowthResult, FCFEarningsGrowthConfig])` in [`analyzer.py`](../../investment_analysis_engine/strategies/fcf_growth/analyzer.py) | `PiotroskiAnalyzer(BaseAnalyzer[PiotroskiResult])` in [`analyzer.py`](../../investment_analysis_engine/strategies/piotroski/analyzer.py) |
| Strategy result | `FCFEarningsGrowthResult` in [`models.py`](../../investment_analysis_engine/strategies/fcf_growth/models.py) | `PiotroskiResult` in [`analyzer.py`](../../investment_analysis_engine/strategies/piotroski/analyzer.py) |
| Input resolution | `ProductionAnnualGrowthSeriesResolver` in [`input_resolver.py`](../../investment_analysis_engine/strategies/fcf_growth/input_resolver.py) for the annual series, and the shared `anchor_year_end_scope` and `resolve_market_cap_inputs` for the market capitalization | The shared assembly functions of [`metric_inputs.py`](../../investment_analysis_engine/analysis/shared/metric_inputs.py) over an `InputResolver`, with the SEC adapter as the `AsFiledSicSource`; no resolver of its own |
| Execution adapter | `execute_fcf_growth` and `FCFGrowthCapture` in [`workspace.py`](../../investment_analysis_engine/strategies/fcf_growth/workspace.py) | `execute_piotroski` and `PiotroskiCapture` in [`workspace.py`](../../investment_analysis_engine/strategies/piotroski/workspace.py) |
| Common execution context | `AnalysisContext` from [`base_analyzer.py`](../../investment_analysis_engine/analysis/base_analyzer.py), constructed by the adapter from the run boundary, cache choice, and profile | The same, built by `PiotroskiSelection.to_analysis_context` |
| Common request boundary | `AnalysisRequest` in [`requests.py`](../../investment_analysis_engine/workspace/requests.py); `FCFGrowthSelection` and `to_fcf_config()` | `AnalysisRequest`; `PiotroskiSelection` |
| Common execution and persistence | [`workspace.execute()`](../../investment_analysis_engine/workspace/execution.py), [`AnalysisRun`](../../investment_analysis_engine/workspace/runs.py), and the Analysis Run repository | The same |
| Strategy presentation | `render_fcf_earnings_growth` in [`presenter.py`](../../investment_analysis_engine/strategies/fcf_growth/presenter.py) | `render_piotroski` in [`presenter.py`](../../investment_analysis_engine/strategies/piotroski/presenter.py) |

The policy remains strategy-owned. `FCFGrowthSelection` is the validated, persisted/request-facing snapshot and converts to the analyzer's `FCFEarningsGrowthConfig`; the adapter supplies the separate common `AnalysisContext`. Piotroski's selection converts to no configuration, only to the context. See the [FCF & Earnings Growth user guide](../user/strategies/FCF_GROWTH.md) and the [Piotroski F-Score user guide](../user/strategies/PIOTROSKI.md) for method semantics and limitations.

### Ready to add a strategy?

Start from the strategy's financial question and required evidence. Read the relevant financial conventions, identify the narrow provider and provenance needs, define strategy-owned policy and result semantics, then integrate through the existing composition and execution boundaries. Use the FCF example to trace those responsibilities in code for the configured form and the Piotroski example for the form with no configuration.

## Changing what every strategy provides

> **Not part of adding a strategy.** This is the checklist for a platform change, which changes what every strategy must provide. If you are adding one strategy, you are done with this guide.

This section is for a change to the strategy contract itself: a new member of the behavior bundle, a new edit site or a new required name in a strategy's file. A single strategy never makes such a change. Take the rows that apply, then run the [status command](#2-check-the-status-command) and the generator's end-to-end test.

| File | What changes |
| :--- | :--- |
| `investment_analysis_engine/strategy_wiring.py` | The `StrategyBehavior` member and its exact-type accessor, the accessor of `BehaviorView`, a `..._by_key` function with its `..._BY_KEY` constant when generic code reads the member by key (as `headlines_by_key` does), and the member in each production behavior declaration |
| The generic code that reads the member (for example `application/runs.py` for `headline_for`) | It calls the view's accessor, never a strategy's module |
| `scripts/strategy_conformance.py` | The closed sets `DESCRIPTOR_FIELDS`, `BEHAVIOR_MEMBERS` and `VIEW_ACCESSORS` (and `EVAL_COMPOSITION_MEMBERS` or `CLI_COMPOSITION_MEMBERS` for a tier's member), the exact-type probes of the behavior check, and the file site's check for a new required name. A member that replays a stored run also changes `StoredRun` (its replay functions) and check T8, which replays every stored run through each projection |
| `scripts/strategy_sites.toml` | The owning site's `title`, `why`, `defines` and `fails` for a new required name, or a new `[[site]]` for a new edit site |
| This guide's edit-site table | Regenerate it with `uv run python -m scripts.generate_strategy_docs` after the sites file changes; it is not edited by hand |
| `tests/scripts/test_strategy_sites.py` | The pinned list of site ids, for a new edit site |
| `scripts/strategy_status.py` and `tests/scripts/test_strategy_status.py` | The status command reads the sites file, so a new site needs no edit there; change it only when a site must report its state another way, and update the test that pins its output |
| `scripts/new_strategy.py` | The generated behavior declaration and its import in the composition-root edit; `STUB_ROLES` or `EDITS` for a new file or a new edit of an existing file |
| `scripts/strategy_templates/*.py.tmpl` | The generated file or function for the new name, calling `unfilled_stub` where the body is strategy-specific |
| `tests/scripts/test_new_strategy.py` | The map of stubbed functions per template and the tests parametrized over the template files |
| `tests/scripts/generator_fills/*.py.fill` and `tests/scripts/test_new_strategy_end_to_end.py` | A `#: body` section in the fill for each new stub; a new fill and `STUB_FILL_ROLES` for a new file; `patches.toml` only for an edit of an existing file |
| `tests/specimen/` | `vocabulary.py` and `selection.py` (a new descriptor name or selection metadata), `behavior.py` (the specimen implements the erased view by hand), the specimen file that defines the member's function (for example `replay.py` or `codec.py`), `wiring.py` for the descriptor, and, for a member that replays a stored run, `runs.py` (the specimen's own replay functions) and `site_context.py` (its `StoredRun` entry) |
| The generic replay: `investment_analysis_engine/workspace_documents/run_replay.py` and `investment_analysis_engine/reporting/replay_inputs.py` | A member that replays a stored run adds its projector type to `replay_inputs.py` and its path to `run_replay.py`, which stays strategy-free |
| Tests of the replay contract: `tests/workspace_documents/test_analysis_run_replay.py`, `tests/workspace_documents/test_run_replay_documents.py`, `tests/test_specimen_strategy.py`, and any test that calls `project_run`, `project_run_document` or a strategy's projector directly (search for those names) | They call the replay functions directly, so a change to a projection's signature or to the modes it accepts changes them. A test of an `ian` command and its output does not, and must pass unedited |

- A fill holds only bodies, so a template's signature has one copy; a new parameter that a body does not use still needs a `del` in the body.
- The conformance checks T15 and T16 and the generator's end-to-end test fail one file at a time. The list above is the whole set; work through it before running them.
- A file this list lacks belongs in the list. Add the row in the same change.

## Deeper references

- [Architecture](ARCHITECTURE.md) — system boundaries and rationale.
- [Financial Math & Data Conventions](../user/FINANCE_MATH.md) — shared financial semantics.
- [Glossary](../user/GLOSSARY.md) — project and finance terminology.
- [Analysis Strategy Guides](../user/strategies/README.md) — investor-facing strategy behavior.
