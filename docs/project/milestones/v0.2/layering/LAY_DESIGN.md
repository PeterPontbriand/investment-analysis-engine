# LAY — Package Layering Design

Fixes exactly which files and names move, proves the target has no loop, and sizes the slices. The sequence and status
are in the [contract and slice plan](LAY_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status). Every figure below is output
of `scripts/simulate_package_layers.py` on the move list [LAY_MOVE_LIST.toml](LAY_MOVE_LIST.toml); reproduce it with the
commands in [§9](#9-reproducing-the-figures).

## 1. At a glance

- **Result:** with every move applied there are 17 units, no two-way pair and no loop. The layered order is the one
  the project owner's simulation gave, with no difference in any layer.
- **What the simulation adds to that earlier one:** it resolves imports through package index files and models the three
  single-name moves exactly. That found one index edit, one extra file to move (`json_documents.py`), one ordering
  constraint (LAY.4 before LAY.5) and one gap in the test that guards the role rule ([§4](#4-the-role-rule)).
- **No move changes behavior:** a move rewrites import lines, file locations and the comments that name a path
  ([plan §1](LAY_CONTRACT_AND_SLICE_PLAN.md#1-at-a-glance)).
- **Decisions for the project owner:** [§8](#8-decisions-for-the-project-owner), each with a recommendation. The move
  list uses the recommended names.

## 2. Assumptions checked

| # | Assumption | Result |
| :--- | :--- | :--- |
| 1 | Today: 15 units, ten two-way pairs, one loop of 14 units | **True.** 61 unit dependencies and 663 import statements. The script's unit dependencies equal those of `scripts/check_package_dependencies.py` exactly. |
| 2 | Reference result: no loop, one layer order | **True, with one count error.** The reference says 18 units and names 17; the target has 17. Layers match exactly. |
| 3 | Core role files never import `cli.py`, `evaluation.py` or `execution.py`; a test enforces it | **True today; the test is complete for two of the three.** See [§4](#4-the-role-rule). `execution.py` is imported only by its own package's `cli.py` today. |
| 4 | Loop `reporting` → `workspace` → `strategies` → `reporting` | **True.** It is the shortest cycle through `reporting`. |
| 5 | No import cycle tolerated only by import order or a function-level import | **False, two cases.** See [§5](#5-import-order-hazards). |

## 3. Today and the target

Today, by unit (imports in the code):

| Unit | Imports |
| :--- | :--- |
| `analysis` | `core`, `data` |
| `cli` | `config`, `core`, `data`, `evaluation`, `llm`, `reporting`, `strategies`, `strategy_wiring`, `utils`, `workspace` |
| `config` | `core`, `orchestrator`, `schema`, `utils` |
| `core` | `config`, `data`, `orchestrator` |
| `data` | `config`, `core`, `workspace` |
| `evaluation` | `core`, `data`, `llm`, `orchestrator`, `schema`, `strategies`, `strategy_wiring`, `tools`, `workspace` |
| `llm` | `config` |
| `orchestrator` | `config`, `core`, `data`, `llm`, `schema`, `tools` |
| `reporting` | `analysis`, `core`, `data`, `workspace` |
| `schema` | `config` |
| `strategies` | `analysis`, `cli`, `config`, `core`, `data`, `evaluation`, `orchestrator`, `reporting`, `workspace` |
| `strategy_wiring` | `core`, `orchestrator`, `reporting`, `strategies`, `workspace` |
| `tools` | |
| `utils` | `config` |
| `workspace` | `core`, `data`, `strategies` |

Two-way pairs (10): `cli`/`strategies`, `config`/`core`, `config`/`orchestrator`, `config`/`schema`,
`config`/`utils`, `core`/`data`, `core`/`orchestrator`, `data`/`workspace`, `evaluation`/`strategies`,
`strategies`/`workspace`. One loop holds 14 units: every unit except `tools`.

Target package table, in the form of ARCHITECTURE §13 without the `Two-way with` column, lower layers first
(script option `--table`):

| Package | Owns | Imports |
| --- | --- | --- |
| `core` | The shared clock, result and status types, strategy errors, constants, stable failure codes and their classifier, the trajectory event model, the reliability-limits and schema-configuration shapes, and path validation. |  |
| `tools` | The tool registry, tool-argument schema generation, and parsing of tool calls from model output. |  |
| `config` | The application settings object and its environment and profile loading. | `core` |
| `data` | Provider contracts and adapters, financial-fact provenance and resolution, instrument identity and profiles, and the SQLite database layer with the provider-data and cache repositories. | `config`, `core` |
| `llm` | The local-model client. | `config` |
| `schema` | The structured-output schema constraint and its validation of model output. | `config`, `core` |
| `utils` | Logging setup. | `config` |
| `analysis` | The analyzer and analysis-context contract, the strategy-neutral financial-resolution helpers, the selection base and the run-outcome models. | `core`, `data` |
| `telemetry` | Trajectory telemetry: the recorder, its sinks, redaction, run context and data-quality events. | `config`, `core`, `data` |
| `orchestrator` | The LLM tool-selection loop, the tool dispatcher and reliability policy, the registration of analysis-tool handlers, and the shared base for tool arguments and handlers. | `config`, `core`, `data`, `llm`, `schema`, `telemetry`, `tools` |
| `reporting` | The presentation helpers the strategy presenters share, the typed models of the shared and failure `--json` documents, and the failure envelope. | `analysis`, `core`, `data` |
| `strategies` | One package per analysis strategy with its analyzer, configuration, result, selection, tool, presenter, codec, replay projector and document model, plus shared strategy code. The `cli`, `evaluation` and `execution` files of each package belong to the `cli`, `evaluation` and `workspace` units. | `analysis`, `config`, `core`, `data`, `orchestrator`, `reporting` |
| `workspace` | The closed selection and native-evidence unions, analysis requests, run capture, watchlists, refresh, the run and watchlist repositories, and each strategy's `execution` file. | `analysis`, `core`, `data`, `strategies` |
| `strategy_wiring` | The closed, statically declared list of supported strategies and their shared wiring. | `analysis`, `core`, `orchestrator`, `reporting`, `strategies`, `workspace` |
| `workspace_documents` | Saved-run replay and the typed refresh, runs and watchlist documents, with the table of all published `--json` documents. | `analysis`, `core`, `reporting`, `workspace` |
| `evaluation` | The Golden case catalog, deterministic evaluator, fixtures and evaluation reporting, plus each strategy's `evaluation` file. | `config`, `core`, `data`, `llm`, `orchestrator`, `strategies`, `strategy_wiring`, `telemetry`, `tools`, `workspace` |
| `cli` | The Typer commands, their production wiring and the process entry point, plus each strategy's `cli` file. | `analysis`, `config`, `core`, `data`, `evaluation`, `llm`, `reporting`, `strategies`, `strategy_wiring`, `telemetry`, `utils`, `workspace`, `workspace_documents` |

Target layered listing (script output; each layer imports only from the layers before it):

| Layer | Units |
| :--- | :--- |
| 0 | `core`, `tools` |
| 1 | `config` |
| 2 | `data`, `llm`, `schema`, `utils` |
| 3 | `analysis`, `telemetry` |
| 4 | `orchestrator`, `reporting` |
| 5 | `strategies` |
| 6 | `workspace` |
| 7 | `strategy_wiring`, `workspace_documents` |
| 8 | `evaluation` |
| 9 | `cli` |

Differences from the earlier simulation: none in the layers. The unit count is 17, not 18. The index file
`src/schema/__init__.py` re-exports `SchemaConfig` and must drop that re-export. `json_documents.py` moves with the
L7 documents. LAY.4 must land before LAY.5.

## 4. The role rule

**Rule (L5).** For the package map, a file named `cli.py`, `evaluation.py` or `execution.py` directly inside a package
under `src/strategies/` (including `_graham`) belongs to the unit `cli`, `evaluation` or `workspace` respectively.
Every other file under `src/strategies/` belongs to `strategies`. No file moves.

**What makes it safe.** It is safe when no other file of a strategy package imports one of the three, because then each
adapter depends on its core and the core depends on no adapter.

| File | Who may import it | Enforced by |
| :--- | :--- | :--- |
| `cli.py` | `src/cli_strategy_wiring.py` only | `tests/test_strategy_import_layering.py`: rank 5, so no same-package file may import it, and only the CLI tier may import it from outside |
| `evaluation.py` | `src/evaluation/strategy_fixtures.py`, and a member's `evaluation.py` for `_graham/evaluation.py` | the same test: rank 5, with the evaluation tier the only outside importer |
| `execution.py` | its own package's `cli.py` | **not fully.** The test ranks `execution` 2, so `presenter.py` (rank 3) and `replay.py` (rank 4) may import it. None does today. |

**The gap and its closure.** `tests/scripts/test_simulate_package_layers.py` adds
`test_no_core_file_of_a_strategy_imports_its_cli_evaluation_or_execution_file`, which fails on any import from a
core file of a strategy to one of the three, so `execution.py` is covered too. LAY.1 keeps the test when the check takes
over the rule.

In the target no strategy core file imports a role file (0 imports; the script's last report line).

## 5. Import-order hazards

Python tolerates these only by order. A move slice must keep them working or remove them.

| Where | What | Effect of the moves |
| :--- | :--- | :--- |
| `src/core/telemetry/sinks/sqlite.py:7` | `from src.data.repositories import trajectory` while `trajectory.py` imports the telemetry event model through the telemetry package initializer: a 19-module loop through two initializers | removed: the event model moves to `core` and leaves the package, so the loop ends (LAY.3) |
| `src/schema/config.py:44` | function-level `from src.config import settings`, because `src.config` imports this module at load time | the reason disappears in LAY.2; the import may stay |
| initializer loops in `data.sec_edgar`, `data.yfinance`, `evaluation`, `evaluation.fixtures`, `schema` | a package initializer that re-exports its children, which the import system executes first | unchanged; the layering test's list of such packages loses `src.core.telemetry*` entries in LAY.3 |

There is no import-time loop between ordinary modules today or in the target. Every one of the 224 modules imports
successfully as the first import in a fresh interpreter today.

## 6. Slice order

Each slice is one cause. The constraints come from simulating the 120 orders of the five slices that follow LAY.1 and rejecting any order
that creates a pair that does not exist today:

| Constraint | Reason |
| :--- | :--- |
| LAY.1 first | every later slice is checked against the final definition of a unit; it removes two pairs by itself |
| LAY.4 before LAY.5 | moving the run-outcome models first makes the repositories (still in `data`) import `analysis`: a new `analysis`/`data` pair |
| LAY.2 before LAY.3 | `telemetry` imports `config`; while `config` still imports `orchestrator`, which imports `telemetry`, there is a three-unit loop |
| LAY.6 after LAY.5 | replay reads the run models; it may move earlier but then imports them from `workspace` |

The chosen order and the state after each slice (pairs, size of the largest loop; script `--moves` with subsets):

| After | Two-way pairs | Largest loop (units) |
| :--- | :--- | :--- |
| today | 10 | 14 |
| LAY.1 (role rule) | 8 | 11 |
| LAY.2 (config) | 5 | 10 |
| LAY.3 (telemetry) | 2 | 7 |
| LAY.4 (repositories) | 1 | 3 |
| LAY.5 (contract modules) | 0 | 3 |
| LAY.6 (workspace documents) | 0 | none |

**How the dependency check stays green.** The check compares the §13 table with the code. A move slice edits the rows
it changes, adds a row for a new unit (`telemetry` in LAY.3, `workspace_documents` in LAY.6) and removes a
`Two-way with` entry when its pair disappears, in the same change. No slice adds a pair. LAY.7 changes the check itself.

## 7. Size of each move

Counts are files importing the moved file or name (script `--importers`): source files that stay, source files that move
themselves, test files, files outside `src` and `tests`, and test files that name it in a string (patch targets).

| Slice | Entry | Src staying | Src moving | Tests | Other | Strings |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| LAY.2 | `orchestrator/reliability.py::ReliabilityLimits` | 2 | 0 | 3 | 0 | 0 |
| LAY.2 | `schema/config.py::SchemaConfig` | 4 | 0 | 7 | 0 | 0 |
| LAY.2 | `utils/paths.py` | 3 | 0 | 1 | 0 | 2 |
| LAY.3 | `core/telemetry/__init__.py` | 0 | 0 | 0 | 0 | 2 |
| LAY.3 | `core/telemetry/recorder.py` | 5 | 2 | 15 | 0 | 0 |
| LAY.3 | `core/telemetry/quality.py` | 2 | 0 | 1 | 0 | 1 |
| LAY.3 | `core/telemetry/redaction.py` | 0 | 1 | 1 | 0 | 0 |
| LAY.3 | `core/telemetry/run_context.py` | 5 | 3 | 15 | 0 | 0 |
| LAY.3 | `core/telemetry/sinks/__init__.py` | 0 | 0 | 0 | 0 | 1 |
| LAY.3 | `core/telemetry/sinks/base.py` | 0 | 3 | 2 | 0 | 0 |
| LAY.3 | `core/telemetry/sinks/jsonl.py` | 0 | 3 | 4 | 0 | 0 |
| LAY.3 | `core/telemetry/sinks/sqlite.py` | 0 | 2 | 4 | 0 | 1 |
| LAY.3 | `core/telemetry/models.py` (stays in `core`, renamed) | 4 | 6 | 17 | 0 | 0 |
| LAY.3 | `orchestrator/reliability.py::RecentEventSummary` | 0 | 1 | 1 | 0 | 0 |
| LAY.4 | `data/repositories/analysis_runs.py` | 3 | 0 | 11 | 0 | 1 |
| LAY.4 | `data/repositories/watchlists.py` | 1 | 0 | 5 | 0 | 0 |
| LAY.5 | `workspace/selection_base.py` | 6 | 0 | 0 | 0 | 0 |
| LAY.5 | `workspace/models.py` | 16 | 3 | 24 | 1 | 0 |
| LAY.6 | `reporting/analysis_runs.py` | 1 | 0 | 3 | 1 | 1 |
| LAY.6 | `reporting/documents/refresh.py` | 1 | 1 | 2 | 0 | 0 |
| LAY.6 | `reporting/documents/runs.py` | 1 | 1 | 1 | 0 | 0 |
| LAY.6 | `reporting/documents/watchlist.py` | 1 | 1 | 1 | 0 | 0 |
| LAY.6 | `reporting/json_documents.py` | 0 | 0 | 0 | 2 | 0 |

Totals by slice: LAY.1 touches no `src` file; LAY.2 moves two names and one file (about 9 importing source files, 11
tests); LAY.3 moves ten files and one name (about 14 importing source files, about 20 test files, plus the tests of the
moved files); LAY.4 moves two files (4 importing source files, 16 tests); LAY.5 moves two files (about 22 importing
source files, 24 tests, one script); LAY.6 moves five files (4 importing source files, 7 tests, two scripts).
Test files for moved sources move with them, mirroring the source layout.

Moves of whole files rename no class and no function, with two exceptions that are file renames only:
`core/telemetry/models.py` becomes `core/trajectory_events.py` and `workspace/models.py` becomes
`analysis/run_models.py`, because a generic `models.py` beside other modules would no longer say what it holds.

Documents that name a moved path and are edited by the slice that moves it: `AGENTS.md` §6 and
`docs/project/DISCOVERY_WORKBOOK.md` (telemetry), `docs/project/ARCHITECTURE.md` (the persistence sentence and the
rows), `docs/user/USAGE.md` (settings shape names), and the plans that name a moved file as an edit site.

## 8. Decisions for the project owner

Not decided here. Each lists the recommendation and the alternative; the simulation confirms both are loop-free.

| # | Question | Recommendation | Alternative |
| :--- | :--- | :--- | :--- |
| 1 | Name of the telemetry package | `telemetry` (`src/telemetry/`): the term the code, tests and AGENTS §6 already use | `trajectory`, which names what is recorded but not the concern |
| 2 | Where the settings shapes (`ReliabilityLimits`, `SchemaConfig`) and the path helper go, and whether `config` becomes a package | `core`, as three small modules; `config` stays one file. They import nothing from the application, and `config` then imports only `core` | into `config` (needs `config` to become a package, which puts the `src.config` patch targets in tests at risk) |
| 3 | Where the selection base and the run-outcome models go | `analysis`, beside the analyzer contract, as `selection_base.py` and `run_models.py` (L6 says "beside the analyzer contract") | a new package (for example `contracts`); it would sit at layer 0 and `reporting` and `strategies` would import it directly |
| 4 | Upper half of L7: inside `workspace` or its own package, and its name | its own package, `workspace_documents`: the check can then enforce that `workspace` never imports replay or the documents; inside `workspace` is also loop-free (16 units) but loses that guard | inside `src/workspace/` |
| 5 | Where the two repositories sit in the workspace side | a subpackage `src/workspace/repositories/`, keeping the file names and mirroring `src/data/repositories/` | flat files `analysis_run_repository.py` and `watchlist_repository.py` in `src/workspace/` |
| 6 | What Momentum receives under L8, and from where | a frozen `MomentumDefaults` (the two window sizes; the RSI period keeps its fixed default), built once at the composition root from `settings.get_momentum_analysis()` and passed where it is built: the selection builder and the CLI and tool defaults. `MomentumConfig` loses its settings-reading default factories | the whole momentum settings mapping passed through (looser typing) |
| 7 | The simulation script and move list after LAY | remove both in LAY.7; the graph engine stays with the check. They describe a state that no longer exists, and PKG would have to rename them | keep the script as a reporting tool |
| 8 | Whether LAY.7 carries both Momentum and the loop-free check | yes, so L1 and L8 both hold literally ([plan A.2](LAY_CONTRACT_AND_SLICE_PLAN.md#a2-reading-of-l1-and-l8-2026-10-11)) | two slices: the check first, Momentum last |
| 9 | `json_documents.py` moves with L7 | yes: it imports the three documents | split the table, leaving the failure, database and health entries behind |
| 10 | `refresh` and `runs` documents import only the run models and could stay in `reporting` once L6 moves | follow L7 as approved and move all three | keep them in `reporting`; fewer files move but the three documents are no longer together |

## 9. Reproducing the figures

From the repository root:

```text
py -3 -m scripts.simulate_package_layers
py -3 -m scripts.simulate_package_layers --only target --table
py -3 -m scripts.simulate_package_layers --importers
py -3 -m scripts.simulate_package_layers --only target --relabel workspace_documents=workspace
py -3 -m scripts.simulate_package_layers --only today --cycle-through reporting
```

The target is today's code with every entry of the move list applied, so each slice deletes its entries and the report
shrinks to the remaining moves. A test fails if an entry names a source that no longer exists, or if the target has a
loop.

## 10. Interaction with SWC and PKG

| Next work | Interaction | Recommended order |
| :--- | :--- | :--- |
| SWC.4d (command validation failures; next SWC slice, no plan yet) | touches strategy `cli.py` files, `cli_support.py` and the failure envelope; none of them moves under LAY, and `json_documents.py` moves only in LAY.6 | SWC.4d first: it is authorized and independent; any import line it adds is retargeted by the LAY slice that moves the target |
| SWC.5 to SWC.7 | build tooling around file locations: the edit-site data file, `scripts/strategy_conformance.py` (imports `workspace.models`, `reporting.analysis_runs`, `json_documents`), the generator, the contributor guide | after LAY, so those paths and the guide are written once against the final layout |
| PKG | rewrites every `src.` import and the check's root name; LAY moves must not follow it | after LAY (L10); the PKG plan records it |

Recommended sequence: SWC.4d, LAY.1 to LAY.7, SWC.5 to SWC.7, PKG, Step 3.5.
