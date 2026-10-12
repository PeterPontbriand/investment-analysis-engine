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
- **Rules every slice follows:** the moves are exactly the entries of
  [LAY_MOVE_LIST.toml](LAY_MOVE_LIST.toml), and a slice deletes its entries in the change that makes them; the
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
| LAY.2 | [Configuration becomes a package and a base layer](#lay2--configuration-package-and-base-layer) | Next | |
| LAY.3 | [Telemetry leaves core](#lay3--telemetry-package) | Planned | |
| LAY.4 | [Run and watchlist repositories move to the workspace side](#lay4--repositories) | Planned | |
| LAY.5 | [Selection base and run-outcome models move beside the analyzer contract](#lay5--contract-modules) | Planned | |
| LAY.6 | [Saved-run replay and workspace documents move up](#lay6--workspace-documents) | Planned | |
| LAY.7 | [Momentum receives its defaults when built](#lay7--momentum-wiring) | Planned | |
| LAY.8 | [Loop-free check, layered listing and closing](#lay8--loop-free-check-and-closing) | Planned | |

**Provisional order with the other work packages:** SWC.4e, SWC.4f, then LAY.1 to LAY.8, then the remaining SWC
slices (SWC.5 to SWC.7), then PKG. SWC.4d is complete. It is provisional until the SWC plan is reviewed
([Appendix A.5](#a5-provisional-order-with-swc-and-pkg-2026-10-11)).

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
  `telemetry` row. Pairs after: 2.
- **Branch:** `refactor/lay-3-telemetry`, from `main` after LAY.2.
- **Detail:** [LAY_DESIGN.md §7](LAY_DESIGN.md#7-size-of-each-move).

### LAY.4 — Repositories

- **Problem:** `data` imports `workspace` only for the analysis-run and watchlist repositories.
- **Decision:** both repositories move to the workspace side; `data` keeps provider data, its caches and the shared
  database layer. The sentence of ARCHITECTURE that places all production SQLite persistence in `src/data/repositories/`
  is rewritten in this slice.
- **Scope:** the two entries marked `serves = "L4"`; the ARCHITECTURE sentence; §13 rows. Pairs after: 1.
- **Branch:** `refactor/lay-4-repositories`, from `main` after LAY.3.
- **Detail:** [LAY_DESIGN.md §7](LAY_DESIGN.md#7-size-of-each-move).

### LAY.5 — Contract modules

- **Problem:** strategy core files import `workspace.selection_base` and `workspace.models`, while `workspace` imports
  the strategies.
- **Decision:** both modules import nothing from the application and move beside the analyzer contract.
- **Scope:** the two entries marked `serves = "L6"`; `scripts/strategy_conformance.py` (imports the models); §13 rows.
  Pairs after: 0; one loop of three units remains.
- **Branch:** `refactor/lay-5-contract-modules`, from `main` after LAY.4.
- **Detail:** [LAY_DESIGN.md §7](LAY_DESIGN.md#7-size-of-each-move).

### LAY.6 — Workspace documents

- **Problem:** `reporting` → `workspace` → `strategies` → `reporting`.
- **Decision:** saved-run replay, the refresh, runs and watchlist documents and the table of published documents
  (`json_documents.py`, which imports them) move up to a package above `workspace`.
- **Scope:** the five entries marked `serves = "L7"`; `scripts/generate_schemas.py` and
  `scripts/strategy_conformance.py` (import `json_documents`); §13 rows including a new row. Loops after: 0.
- **Branch:** `refactor/lay-6-workspace-documents`, from `main` after LAY.5.
- **Detail:** [LAY_DESIGN.md §7](LAY_DESIGN.md#7-size-of-each-move).

### LAY.7 — Momentum wiring

- **Problem:** Momentum's analyzer and selection read the global settings object; every other strategy receives what it
  needs when built.
- **Decision:** Momentum receives a frozen `MomentumDefaults` (the two window sizes; the RSI period keeps its fixed
  default), built once at the composition root from `settings.get_momentum_analysis()` and passed where it is built: the
  selection builder and the CLI and tool defaults. `MomentumConfig` loses its settings-reading default factories. This is
  the one slice that changes how something is wired, and it changes no output.
- **Scope:** the Momentum analyzer, selection, tool and CLI files and the composition that builds them; the tests that
  patch `get_momentum_analysis` (13 test files use `MomentumConfig(`, `MomentumSelection.from_settings` or
  `MomentumAnalyzer(`).
- **Branch:** `refactor/lay-7-momentum-wiring`, from `main` after LAY.6.
- **Detail:** ⚠ no slice plan yet

### LAY.8 — Loop-free check and closing

- **Problem:** the check still allows a loop of any length; issue #114 is open; the simulation has served its purpose.
- **Decision:** the check fails on any loop, §13 gains the layered listing, issue #114 is closed, and the simulation
  script and move list are removed (decision 7). The graph engine stays with the check.
- **Scope:** `scripts/check_package_dependencies.py`, `scripts/package_graph.py` and their tests; removal of
  `scripts/simulate_package_layers.py`, its tests and `LAY_MOVE_LIST.toml`; ARCHITECTURE §13; the layering plan's
  status and the milestone row.
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
