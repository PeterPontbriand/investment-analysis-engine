# LAY — Package Layering: Contract and Slice Plan

Makes the package graph under `src/` loop-free, and keeps it so, before Step 3.5 adds seven analyzers that would copy
the current layout. The [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status) owns its position and
work-package status. The design, the proof and the owner decisions are in [LAY_DESIGN.md](LAY_DESIGN.md).

## 1. At a glance

- **What this work does:** moves a small, fixed set of files and names so that the top-level packages form layers:
  each package imports only from packages below it. It then changes the dependency check from "no new two-way pair"
  to "no loop of any length" and adds a layered listing to
  [ARCHITECTURE §13](../../../ARCHITECTURE.md#13-module-boundaries).
- **What it does not do:** change a formula, a classification, a command output, a schema, a golden document or a stored
  value. Every move slice is a pure move. It does not regroup the strategy packages, rename `src` (PKG does that, after
  LAY), or add a registry, plugin loader or framework.
- **Today:** 15 units, ten two-way pairs and one loop that contains 14 units. After the moves: 17 units, no pair and no
  loop ([LAY_DESIGN.md §3](LAY_DESIGN.md#3-today-and-the-target)).
- **Rules every slice follows:** the moves were exactly the entries of
  `LAY_MOVE_LIST.toml`, which LAY.8 removed with the simulation script, and a slice deleted its entries in the change that made them; the
  dependency check stays green in the same change (the slice edits the §13 rows it changes); the complete managed
  gate, with the 3.14 pass; no stored shape changes, so no version bump; explicit authorization before the next slice.
- **Proof of no output change, every move slice:** `uv run python scripts/generate_schemas.py --check` passes, the
  branch changes no file under `schemas/` and none under `tests/expected_output/`, and the diff of `src/` is import
  lines, file locations and the module docstrings and comments that name a moved path.
- **Where the detail lives:** the design, the simulation output and the decisions for the project owner are in
  [LAY_DESIGN.md](LAY_DESIGN.md); the decision record is in
  [Appendix A](#appendix-a-decision-records).

## 2. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| LAY.0 | [Design, simulation script and slice plan](#lay0--design-and-slice-plan) | Complete | 2026-10-11 |
| LAY.1 | [Role rule in the dependency check](#lay1--role-rule-in-the-dependency-check) | Complete | 2026-10-12 |
| LAY.2 | [Configuration becomes a package and a base layer](#lay2--configuration-package-and-base-layer) | Complete | 2026-10-12 |
| LAY.3 | [Telemetry leaves core](#lay3--telemetry-package) | Complete | 2026-10-13 |
| LAY.4 | [Run and watchlist repositories move to the workspace side](#lay4--repositories) | Complete | 2026-10-13 |
| LAY.5 | [Selection base and run-outcome models move beside the analyzer contract](#lay5--contract-modules) | Complete | 2026-10-14 |
| LAY.6 | [Saved-run replay and workspace documents move up](#lay6--workspace-documents) | Complete | 2026-10-14 |
| LAY.7 | [Strategy settings files](#lay7--strategy-settings-files) | Complete | 2026-10-15 |
| LAY.8 | [Loop-free check, layered listing and closing](#lay8--loop-free-check-and-closing) | Complete | 2026-10-15 |

**Order with the other work packages:** LAY.4 to LAY.8, then 12B (removal of the TTM EPS basis), then PKG.1 and PKG.2,
then Step 3.5. SWC.5 to SWC.7 run after LAY.8; GR.2 runs whenever no LAY branch is open. This replaces the provisional
order of [A.5](#a5-provisional-order-with-swc-and-pkg-2026-10-11).

The order within LAY is forced by the graph, not chosen for convenience ([LAY_DESIGN.md §6](LAY_DESIGN.md#6-slice-order)):
LAY.4 must precede LAY.5 (moving the run-outcome models first would create a new two-way pair between `analysis` and
`data`), LAY.2 should precede LAY.3 (so `telemetry` never sits in a loop with `config`), and LAY.1 comes first so every
later slice is checked against the final definition of a unit.

## 3. The slices

### LAY.0 — Design and slice plan

- **Problem:** 14 of 15 packages can reach each other through imports, so no layered listing exists.
- **Decision:** the decisions L1 to L10 ([Appendix A](#appendix-a-decision-records)) fix the target; this slice proves it
  has no loop, fixes the exact moves, and plans the slices.
- **Scope:** `scripts/simulate_package_layers.py` and its tests; the move list; this plan and the design; the
  milestone-plan row; the Step 3.5 entry condition; the PKG plan. No file under `src/` changes.
- **Branch:** `docs/lay-0-layering-design`, from `main`.
- **Detail:** [LAY_DESIGN.md](LAY_DESIGN.md).

### LAY.1 — Role rule in the dependency check

- **Problem:** `cli.py`, `evaluation.py` and `execution.py` of each strategy package count today as part of
  `strategies`, which makes `cli`, `evaluation` and `workspace` each look two-way with `strategies`.
- **Decision:** for the package map, those three role files belong to `cli`, `evaluation` and `workspace`
  ([LAY_DESIGN.md §4](LAY_DESIGN.md#4-the-role-rule)). No file moves. The check resolves an import to a file, so a
  `from src.strategies.<x> import cli` is attributed correctly. The graph engine of the simulation script moves to a
  shared module, `scripts/package_graph.py`, used by the check and by the simulation script.
- **Scope:** `scripts/check_package_dependencies.py`, `scripts/package_graph.py`, `scripts/simulate_package_layers.py`
  (imports the engine), their tests, and the §13 definition sentence and rows (`cli`, `evaluation`, `strategies`,
  `workspace`). Pairs after: 8. No `src/` change.
- **Branch:** `refactor/lay-1-role-rule`, from `main`.
- **Detail:** [LAY_DESIGN.md §4](LAY_DESIGN.md#4-the-role-rule) and [§7](LAY_DESIGN.md#7-size-of-each-move).

### LAY.2 — Configuration package and base layer

- **Problem:** `config` imports `orchestrator` (`ReliabilityLimits`), `schema` (`SchemaConfig`) and `utils`
  (`paths`), and each imports `config` back.
- **Decision:** `config` becomes a package, `src/config/`, that holds the two settings shapes and the path helper
  ([decision 2](LAY_DESIGN.md#8-decisions-for-the-project-owner)); `config` then imports only `core`.
  `src/config.py` becomes `src/config/__init__.py` unchanged except that the three places that derive the project root
  from `__file__` take one more `.parent`, so every value is the same. Every `from src.config import ...` and every test
  patch target into `src.config` (`src.config.ProjectSettings.*`) keeps working with no edit.
- **Scope:** the file entries and name entries marked `serves = "L3"` in the move list; the three `__file__` sites; the
  `src/schema/__init__.py` re-export of `SchemaConfig`; the two test patch targets of `src.utils.paths.is_windows`,
  which follow the moved file; the `src/config.py` sentences in ARCHITECTURE §13 and `MASTER_PLAN.md`; §13 rows.
  `pyproject.toml` names `src/config.py` in the coverage `omit` list and needs the matching line changed, which requires
  explicit user permission before the slice edits it. Pairs after: 5.
- **Stop condition:** if the package cannot keep every `from src.config import ...` and patch target working without a
  change of behavior (a settings value, a default path, the import-time effects of loading settings), the slice stops
  and reports; it does not choose another home for the shapes.
- **Branch:** `refactor/lay-2-config-package`, from `main` after LAY.1.
- **Detail:** [LAY_DESIGN.md §7](LAY_DESIGN.md#7-size-of-each-move).

### LAY.3 — Telemetry package

- **Problem:** `core` imports `config`, `data` and `orchestrator`, only through trajectory telemetry.
- **Decision:** telemetry becomes its own package; the plain event model stays in `core`; `RecentEventSummary` moves
  with the recorder that produces it.
- **Scope:** the ten file entries and the one name entry marked `serves = "L2"`; `AGENTS.md` §6 (names
  `src/core/telemetry/`); the layering test's list of re-exporting package initializers; §13 rows including a new
  `telemetry` row. Pairs after: 2. Implementation decisions: [A.8](#a8-lay3-implementation-decisions-2026-10-13).
- **Branch:** `refactor/lay-3-telemetry`, from `main` after LAY.2.
- **Detail:** [LAY_DESIGN.md §7](LAY_DESIGN.md#7-size-of-each-move).

### LAY.4 — Repositories

- **Problem:** `data` imports `workspace` only for the analysis-run and watchlist repositories.
- **Decision:** both repositories move to the workspace side; `data` keeps provider data, its caches and the shared
  database layer. The sentence of ARCHITECTURE that places all production SQLite persistence in `src/data/repositories/`
  is rewritten in this slice.
- **Scope:** the two entries marked `serves = "L4"`; the ARCHITECTURE sentence; §13 rows. Pairs after: 1.
  Implementation decisions: [A.9](#a9-lay4-implementation-decisions-2026-10-13).
- **Branch:** `refactor/lay-4-repositories`, from `main` after LAY.3.
- **Detail:** [LAY_DESIGN.md §7](LAY_DESIGN.md#7-size-of-each-move).

### LAY.5 — Contract modules

- **Problem:** strategy core files import `workspace.selection_base` and `workspace.models`, while `workspace` imports
  the strategies.
- **Decision:** both modules import nothing from the application and move beside the analyzer contract.
- **Scope:** the two entries marked `serves = "L6"`; `scripts/strategy_conformance.py` (imports the models); §13 rows.
  Pairs after: 0; one loop of three units remains. Implementation decisions:
  [A.10](#a10-lay5-implementation-decisions-2026-10-14).
- **Branch:** `refactor/lay-5-contract-modules`, from `main` after LAY.4.
- **Detail:** [LAY_DESIGN.md §7](LAY_DESIGN.md#7-size-of-each-move).

### LAY.6 — Workspace documents

- **Problem:** `reporting` → `workspace` → `strategies` → `reporting`.
- **Decision:** saved-run replay, the refresh, runs and watchlist documents and the table of published documents
  (`json_documents.py`, which imports them) move up to a package above `workspace`.
- **Scope:** the five entries marked `serves = "L7"`; `scripts/generate_schemas.py` and
  `scripts/strategy_conformance.py` (import `json_documents`); §13 rows including a new row. Loops after: 0.
  Implementation decisions: [A.11](#a11-lay6-implementation-decisions-2026-10-14).
- **Branch:** `refactor/lay-6-workspace-documents`, from `main` after LAY.5.
- **Detail:** [LAY_DESIGN.md §7](LAY_DESIGN.md#7-size-of-each-move).

### LAY.7 — Strategy settings files

- **Problem:** Momentum's analyzer, selection and tool read its settings file from inside the strategy, at import;
  Graham Growth's file is read by the command line on every call; neither is typed, and the two strategies every Step
  3.5 strategy copies do it differently.
- **Decision:** one strategy-settings convention for every strategy: a TOML file per strategy under
  `config/strategies/`, a typed settings model in the strategy's package declared by its descriptor, one generic loader
  in `config`, and composition roots that pass the typed settings in. Replaces design decision 6
  ([A.12](#a12-lay7-strategy-settings-files-replace-design-decision-6-2026-10-14)).
- **Scope:** two slices: LAY.7a (the plan) and LAY.7b (Momentum and Graham Growth).
- **Branch:** per slice, in the slice plan.
- **Detail:** [LAY_7_STRATEGY_SETTINGS_PLAN.md](LAY_7_STRATEGY_SETTINGS_PLAN.md)

### LAY.8 — Loop-free check and closing

- **Problem:** the check still allows a loop of any length; issue #114 is open; the simulation has served its purpose.
- **Decision:** the check fails on any loop, §13 gains the layered listing, issue #114 is closed, and the simulation
  script and move list are removed (decision 7). The graph engine stays with the check.
- **Scope:** `scripts/check_package_dependencies.py`, `scripts/package_graph.py` and their tests; removal of
  `scripts/simulate_package_layers.py`, its tests and `LAY_MOVE_LIST.toml`; ARCHITECTURE §13; the layering plan's
  status and the milestone row. Implementation decisions: [A.13](#a13-lay8-implementation-decisions-2026-10-15).
- **Branch:** `refactor/lay-8-loop-free-check`, from `main` after LAY.7.
- **Detail:** ⚠ no slice plan yet

## 4. Scope limits and acceptance criteria

Scope limits:

- Any formula, classification, metric, command output, schema, golden document or stored-value change.
- Any move not in the move list; a new move is a plan change.
- The `src` package rename (PKG) and any regrouping of the strategy packages.
- A registry, plugin loader or factory on top of the layering.

Acceptance criteria:

- **No loop:** `scripts/check_package_dependencies.py` fails on a loop of any length, and passes on `main`.
- **Layered listing:** §13 lists the packages in layers, each importing only from layers before it, and the listing
  matches the check's computation.
- **No output change:** every move slice passes the proof in [§1](#1-at-a-glance).
- **Role rule:** `tests/test_strategy_import_layering.py` fails when a strategy's core file imports its `cli`, `evaluation` or
  `execution` file; the test is permanent and does not depend on the simulation script.
- **Issue #114:** closed by LAY.8.
- **Quality gate:** the complete managed gate, with the 3.14 pass, at the end of every slice.

## 5. Background and origin

**Discovered:** the package dependency map (PD) filed
[issue #114](https://github.com/PeterPontbriand/investment-analysis-engine/issues/114): ten two-way pairs and 14 of 15
packages mutually reachable. Step 3.5 had to wait for "a decision on issue #114". The project owner decided to remove the
loops, not to document them (decisions L1 to L10).

**Why before Step 3.5 and PKG:** seven new analyzers will copy the layout, and PKG rewrites every import line, so the
moves land once, under the old name, before the rewrite.

---

## Appendix A: Decision records

### A.1 Decisions L1 to L10 (2026-10-11)

Approved by the project owner before this plan was written.

| ID | Decision |
| :--- | :--- |
| L1 | Goal: no loop of any length between the units of the package map, enforced by the dependency check. The check changes from "no new two-way pair" to "no loop", and ARCHITECTURE §13 gains a layered listing. Both happen in the final LAY slice. |
| L2 | Telemetry moves out of `src/core` into its own package. The plain event model stays in `core`. The one summary type the recorder borrows from `src/orchestrator/reliability.py` moves to the telemetry package. `core` then imports nothing from the application. |
| L3 | `config` becomes a base layer that imports only `core`. The settings shapes it borrows from `orchestrator` and `schema`, and the path helper it borrows from `utils`, move below it. |
| L4 | The analysis-run and watchlist repositories move from `src/data/repositories` to the workspace side. `data` keeps provider data, its caches and the shared database layer. |
| L5 | Strategy packages stay one package per strategy. For the package map, three role files in each count as part of the layer they adapt the strategy to: `cli.py` to `cli`, `evaluation.py` to `evaluation`, `execution.py` to `workspace`. No file moves for this. |
| L6 | The modules in `src/workspace` that strategy core files depend on and that import nothing from the application (the selection base and the run-outcome models) move down beside the analyzer contract. |
| L7 | `reporting` splits. Strategy-neutral presentation helpers and shared document parts stay. Saved-run replay and the refresh, runs and watchlist documents move up to the workspace side. |
| L8 | Momentum's analyzer and selection stop reading the global settings object and receive what they need when built, as every other strategy does. This is the last LAY slice. |
| L9 | Every move slice is a pure move: no command output, schema, golden document, stored value or classification changes, proven as PH.2d proved it. L8 is the one slice that changes how something is wired, and it too changes no output. |
| L10 | LAY completes before the `src` package rename (PKG). |

### A.2 L1 and L8: two slices (2026-10-11)

L1 puts the check change in "the final LAY slice" and L8 says Momentum is "the last LAY slice". The project owner decided
two slices: LAY.7 is the Momentum wiring; LAY.8 is the loop-free check, the layered listing, the closing of issue #114
and the removal of the script and move list.

### A.3 Additions to L7 (2026-10-11)

`src/reporting/json_documents.py` imports the three documents L7 moves, so it moves with them. Nothing in `src` imports
it; `scripts/generate_schemas.py` and `scripts/strategy_conformance.py` do.

### A.4 Decisions on the questions in the design (2026-10-11)

The project owner decided the ten questions of [LAY_DESIGN.md §8](LAY_DESIGN.md#8-decisions-for-the-project-owner):
1, 3, 4, 5, 6, 7, 9 and 10 as recommended; 2 differently (`config` becomes a package, not `core`; LAY.2 stops and
reports if that cannot be done without changing behavior); 8 as two slices (A.2). The simulation was re-run with them:
17 units, no two-way pair, no loop, the same layered order.

### A.5 Provisional order with SWC and PKG (2026-10-11)

SWC.4e, SWC.4f, then LAY.1 to LAY.8, then the remaining SWC slices (SWC.5 to SWC.7), then PKG. SWC.4d is complete. Provisional
until the SWC plan is reviewed; the SWC plan is not edited by LAY.0.

### A.6 LAY.1 implementation decisions (2026-10-12)

Approved by the project owner for LAY.1.

1. A file named `cli.py`, `evaluation.py` or `execution.py` directly inside a package under `src/strategies/`
   (including `_graham`) belongs to the unit `cli`, `evaluation` or `workspace`; every other file under
   `src/strategies/` belongs to `strategies`. No file moves and nothing under `src/` changes.
2. The check attributes an import to the file it names, so `import src.strategies.x.cli` and
   `from src.strategies.x import cli` both land in `cli`.
3. The graph code of the simulation script moves to `scripts/package_graph.py`, used by both the check and the
   simulation script. The role rule is written once, as data in that module; ARCHITECTURE §13's definition sentence
   states it in words, and no test matches that prose against the code.
4. The simulation's full output is identical before and after the move, except that the "today" figures apply the
   role rule. The PR description holds the output before the first edit and after the last, with their diff.
5. The check's messages and exit codes are unchanged; only the assignment of files to units changes.
6. New tests build a small source tree in a temporary directory and show that a strategy's `cli.py`, `evaluation.py`
   and `execution.py` are attributed to `cli`, `evaluation` and `workspace` in both import forms, and that any other
   file of a strategy package, including one in `_graham`, stays in `strategies`.

### A.7 LAY.2 implementation decisions (2026-10-12)

Approved by the project owner for LAY.2.

1. `src/config.py` becomes `src/config/__init__.py`, unchanged except that the three expressions that derive a
   directory from `__file__` take one more `.parent`, so every value is the same. `ReliabilityLimits` moves to
   `src/config/reliability_limits.py`, `SchemaConfig` to `src/config/schema_config.py`, and `src/utils/paths.py` to
   `src/config/paths.py`. Afterwards `config` imports only `core`.
2. Every importer and every test patch target moves to the new home. Nothing is re-exported from an old location:
   `src/orchestrator/reliability.py` and `src/schema/config.py` import the names from the new modules, and
   `src/schema/__init__.py` drops its re-export of `SchemaConfig`. Every `from src.config import ...` and every patch
   target into `src.config.ProjectSettings.*` keeps working unedited.
3. The settings code stays whole in `src/config/__init__.py`.
4. Importing any `src.config` submodule runs `src/config/__init__.py` and loads the settings. The condition for
   every source file that imports a moved name is restated as: for every entry point, the point at which the settings
   load does not change. Importing `src.schema` or `src.orchestrator.reliability` on its own may now load the
   settings; that is accepted.
5. `src/orchestrator/reliability.py` and `src/schema/config.py` import the moved names with ordinary module-level
   imports, not `TYPE_CHECKING`. In `src/schema/config.py` the function-level `from src.config import settings`
   became a module-level import and its `noqa` comment was removed, because the loop it broke no longer exists.
6. A test shows that the directories and the default database location the settings derive from `__file__` equal the
   repository root and the paths built from it; it was run against `main` as well.
7. The four `serves = "L3"` entries left the move list in the same change, as its header requires, and `src.config`
   joined the re-exporting package initializers that the layering test allows in an import cycle (the plan already
   lists that test's allowlist among the files a layering slice changes).
8. `tests/utils/test_paths.py` moved to `tests/config/test_paths.py`. The `pyproject.toml` coverage `omit` entry
   `src/config.py` became `src/config/__init__.py`; no other line of `pyproject.toml` and no part of `uv.lock`
   changed.

Entry points, whether `src.config` is loaded once the entry point's imports finish, in a fresh interpreter:

| Entry point | On `main` | After LAY.2 |
| :--- | :--- | :--- |
| `src.main` | loaded | loaded |
| `scripts.generate_schemas` | loaded | loaded |
| `scripts.strategy_conformance` | loaded | loaded |

### A.8 LAY.3 implementation decisions (2026-10-13)

Approved by the project owner for LAY.3.

1. The moves are the entries of the move list and nothing else: the nine `src/core/telemetry/` files that stay in
   telemetry (including `sinks/`) move to `src/telemetry/`, `models.py` becomes `src/core/trajectory_events.py`, and
   `RecentEventSummary` moves from `src/orchestrator/reliability.py` to `src/telemetry/recent_events.py`. Afterwards
   `core` imports nothing from `config`, `data` or `orchestrator`.
2. One home per name. `src/telemetry/__init__.py` and `src/telemetry/sinks/__init__.py` hold only a docstring, and every
   importer and every test patch target names the module that defines what it imports. Nothing is re-exported from an
   old location. `src.core.telemetry` and `src.core.telemetry.sinks` left `_BENIGN_CYCLE_PACKAGES` and no entry was added;
   no loop through an initializer involves telemetry any more.
3. `tests/core/telemetry/` moved to `tests/telemetry/`. The existing telemetry tests changed only in their import lines
   and patch targets, with one exception the project owner approved: `tests/telemetry/test_sqlite_sink.py` finds
   `alembic.ini` with `parents[2]` instead of `parents[3]`, because the file is one directory shallower.
4. Behavior is unchanged: telemetry still fails open and never alters business execution, and recorded events are
   identical. Two-way pairs after the slice: `data` and `workspace`; `strategies` and `workspace`.

### A.9 LAY.4 implementation decisions (2026-10-13)

Approved by the project owner for LAY.4.

1. Two files move with `git mv`, and their contents are unchanged: `src/data/repositories/analysis_runs.py`
   and `src/data/repositories/watchlists.py` become `src/workspace/repositories/analysis_runs.py` and
   `src/workspace/repositories/watchlists.py`. The new `src/workspace/repositories/__init__.py` holds only a module
   docstring.
2. Table definitions, the connection, migrations and readiness stay in `data`. The moved files keep importing `schema`
   and `sqlite` from `src.data.repositories`.
3. One home per name. Nothing is re-exported from `src/data/repositories/`, whose initializer is not edited, and every
   importer and test patch target names the defining module. `_BENIGN_CYCLE_PACKAGES` is unchanged and the new package
   is not added to it.
4. `tests/data/repositories/test_analysis_runs.py` and `test_watchlist_repository.py` moved to
   `tests/workspace/repositories/`. They changed only in import lines and patch targets. No `parents[N]` changed,
   because the new folder is at the same depth.
5. ARCHITECTURE: the closing sentence of §13 and the persistence guardrail of §14 name both repository folders; the
   `data` row of the §13 table drops `workspace` from Imports and from Two-way with; the `workspace` row owns the run
   and watchlist repositories and is two-way with `strategies` only. §8 is not edited.
6. The `data` Owns text names the trajectory repository, in both §13 and the move list.
7. The link in the P2 profiles plan to the analysis-run repository points at the new path. Other mentions of the old
   paths in completed-plan and evidence documents are history and stay as they are.
8. The provisional order of A.5 is replaced by the order in §2: LAY.4 to LAY.8, then 12B, then PKG.1 and PKG.2, then
   Step 3.5; SWC.5 to SWC.7 after LAY.8; GR.2 whenever no LAY branch is open. A.5 stays verbatim.
9. The file name `watchlists.py` stays, although `src/workspace/watchlists.py` exists; the path tells them apart.
10. Behavior and stored data are unchanged: no schema change, no migration, no message change. Two-way pairs after the
    slice: `strategies` and `workspace`.

### A.10 LAY.5 implementation decisions (2026-10-14)

Approved by the project owner for LAY.5.

1. Two files move with `git mv`: `src/workspace/selection_base.py` becomes `src/analysis/selection_base.py`, and
   `src/workspace/models.py` becomes `src/analysis/run_models.py`, as design decision 3 and §7 set out. Contents are
   unchanged apart from the label in item 5.
2. No class, function or constant is renamed; `CLI_SECURITY_PROVIDERS` and `CLI_QUOTE_PROVIDERS` keep their names.
3. One home per name. Nothing is re-exported from `src/workspace/`, whose initializer is not edited; every importer
   names the new module. The `src/analysis/__init__.py` docstring becomes "The analyzer contract,
   financial-resolution helpers, selection base and run-outcome models." and the initializer stays docstring-only.
4. `tests/workspace/test_workspace_models.py` moved to `tests/analysis/test_run_models.py` and changed only in import
   lines.
5. The label "B1" is removed from the `run_models.py` module docstring ("shared with the selection snapshots"). The
   cross-reference in the `src/workspace/requests.py` module docstring names the new module path.
6. A new `tests/analysis/test_selection_base.py` gives `FrozenSelection` tests of its own: 6 cases (the integer
   version accepted; `True`, `1.0` and `"1"` each rejected; a frozen instance; an unknown extra field rejected).
7. ARCHITECTURE §13: `analysis` owns the selection base and the run-outcome models; `strategies` drops `workspace`
   from Imports and has no two-way entry; `strategy_wiring` adds `analysis` to Imports; `workspace` no longer owns the
   selection base and has no two-way entry.
8. Mentions of the old paths in completed plans and evidence documents are history and stay as they are.
9. Behavior and stored data are unchanged.
10. Result: no two-way pairs. One loop of three units (`reporting`, `strategies`, `workspace`) is left for LAY.6.

### A.11 LAY.6 implementation decisions (2026-10-14)

Approved by the project owner for LAY.6.

1. Five files move with `git mv` into the new flat package `src/workspace_documents/`: `src/reporting/analysis_runs.py`
   (renamed, item 2), `src/reporting/documents/refresh.py`, `runs.py` and `watchlist.py`, and
   `src/reporting/json_documents.py`. Contents change only in import lines and in the docstring and comment references
   to the moved modules. The new `src/workspace_documents/__init__.py` holds only a docstring.
2. The replay module is renamed `run_replay.py`. It holds only `project_run`, the saved-run replay, and the name keeps
   it apart from `src/workspace/repositories/analysis_runs.py`, the run repository. This is a third file rename beyond
   the two LAY_DESIGN §7 lists; LAY_DESIGN.md itself is not edited.
3. Since LAY.5, `refresh.py` and `runs.py` import only `analysis` and `core`, so the loop would break without them. All
   three documents still move, because they are the documents the workspace commands write and `cli_workspace.py` is
   their only `src` user.
4. One home per name. Nothing is re-exported from `src/reporting/`; every importer names the new module.
   `src/reporting/documents/__init__.py` is not edited, `_BENIGN_CYCLE_PACKAGES` is unchanged and the new package is
   not added to it.
5. `tests/reporting/test_analysis_run_replay.py` and `test_workspace_documents.py` moved to
   `tests/workspace_documents/`, changing only in import lines (and a path in one failure message).
   `tests/reporting/test_analysis_run_instrument_profile_snapshot.py` stays, with its import retargeted. No
   `parents[N]` changed. Three test files outside the original list changed only to follow the moved test module:
   `tests/analysis/graham_value/test_effective_as_of.py`, `tests/workspace/test_failure_reason_codes.py` and
   `tests/_strategy_document_output.py` import helpers from `test_analysis_run_replay`, so each import line names
   `tests.workspace_documents.test_analysis_run_replay`.
6. The synthetic strings naming `src.reporting.analysis_runs` in `tests/test_strategy_import_layering.py` are made-up
   input to the edge-check helper, not references to the module, and are left unchanged.
7. The `src/reporting/__init__.py` docstring becomes "Presentation helpers, the replay contract, the shared and failure
   JSON documents, and the failure envelope." The old text named "failure classification", which moved to
   `src/core/failure_classification.py` earlier, and "saved-run replay", which leaves now.
8. ARCHITECTURE §13: the `reporting` row owns the replay-projector contract and drops `workspace` from Imports; a new
   `workspace_documents` row follows `workspace`; the `cli` row adds `workspace_documents`. In the move list the five
   `serves = "L7"` entries are deleted, and the `owns` texts of `reporting` and `workspace_documents` match §13. The
   old `workspace_documents` text wrongly said "all published" documents; it now says the `--json` documents no single
   strategy owns.
9. The link in the P2 profiles plan to the replay module points at `src/workspace_documents/run_replay.py`. Other
   mentions of the old paths in completed plans and evidence documents are history and stay as they are.
10. Behavior and stored data are unchanged, including every published JSON schema.
11. Result: no two-way pairs and no loops. `workspace_documents` sits in the same layer as `strategy_wiring`.

### A.12 LAY.7: strategy settings files replace design decision 6 (2026-10-14)

Approved by the project owner. Design decision 6 ([LAY_DESIGN.md §8](LAY_DESIGN.md#8-decisions-for-the-project-owner))
is replaced by the strategy settings convention in
[LAY_7_STRATEGY_SETTINGS_PLAN.md](LAY_7_STRATEGY_SETTINGS_PLAN.md), whose Appendix A records the reasons and the
alternatives not taken. L9's "changes no output" holds for LAY.7 with one exception: the Momentum tool schema in the
local-model prompt. LAY.7 becomes two slices, LAY.7a and LAY.7b. LAY_DESIGN.md is not edited.
A second exception, recorded when LAY.7b was approved: the published watchlist schemas (`watchlist.schema.json` and
`watchlist-delete.schema.json`) make Momentum's `rsi_period` required
([LAY.7 plan A.2](LAY_7_STRATEGY_SETTINGS_PLAN.md#a2-lay7b-implementation-decisions-2026-10-15)).

### A.13 LAY.8 implementation decisions (2026-10-15)

Approved by the project owner for LAY.8.

1. The check builds the unit graph from the collected imports and computes its strongly connected components with
   `strongly_connected`. Each component is one finding that names the units, the shortest cycle through the first unit
   in sorted order, and one example `file:line` per edge. While any loop exists the check reports no layer or order
   finding, since layers are undefined. Exit status is 1 on any finding, as before.
2. The "Two-way with" column leaves the §13 table. `DeclaredRow.two_way`, `two_way_pairs`, `_compare_two_way` and their
   findings leave the check, and `two_way()` leaves `scripts/package_graph.py`.
3. The listing is a Layer column in the existing table, not a second list, because AGENTS.md §4 declares the package map
   once. The header is `Package | Layer | Owns | Imports`, the Layer cell is a whole number, and rows are ordered by
   layer, then by package name.
4. A unit that imports no other unit is in layer 0; any other unit is one more than the highest layer among the units it
   imports. This is `layers()` in `scripts/package_graph.py`, and the check compares each Layer cell with it.
5. New findings: a wrong layer, a Layer cell that is not a whole number, and rows out of order (only the first
   out-of-order pair is reported). The existing findings keep their wording, apart from references to the removed
   column.
6. `scripts/simulate_package_layers.py`, its tests and `LAY_MOVE_LIST.toml` are removed with `git rm`.
   `scripts/package_graph.py` keeps the role rule, `unit_of_path`, `strongly_connected`, `layers` and `shortest_cycle`.
   The two links to the move list become plain code text; other mentions of the deleted files in planning documents are
   history and stay.
7. Tests: the two-way tests and the `two_way` parameter of the test helper are removed; tests are added for a loop of two
   units, a loop of three, no layer or order finding while a loop exists, a wrong Layer cell, a Layer cell that is not a
   whole number, rows out of layer order, rows out of name order within a layer, the old four-column header, and the
   check passing on the repository itself.
8. Documentation: the ARCHITECTURE §13 introduction, the AGENTS.md §4 package-map bullet and the module docstring of the
   check describe the Layer column, the layer rule and the loop rule.
9. Issue #114 is closed by this slice.
