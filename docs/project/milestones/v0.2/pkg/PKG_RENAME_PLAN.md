# PKG — `src` to Real Top-Level Package Rename

Renames the project's import package from the collision-prone `src` to `investment_analysis_engine`,
before Step 3.5 adds seven analyzers that would otherwise be written under the old path. The
[milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status) owns its position and work-package status.

## 1. At a glance

- **What this work does:** in two slices. PKG.1 empties the package initializers that re-export their
  children, so every name has one import path. PKG.2 moves the `src/` package to
  `investment_analysis_engine/`, rewrites every absolute import and every dotted patch target to the new
  name, and updates `pyproject.toml`, `AGENTS.md` and any document that names an import path literally.
- **What it is not:** a restructuring of the package's internal layout beyond PKG.1's change to the
  initializers, or any change of behavior, formula, presentation contract or public CLI surface. `ian` stays the CLI command name; it is
  independent of the import name. The strategy folder layout is already settled by SWC
  ([§6](#6-folder-layout-outcome)); PKG renames it and does not regroup it.
- **Rules it follows:** the managed quality gate at the end; no new dependency without explicit user
  permission; scope and contract review before implementation, as for any nontrivial work package.
- **Where it sits:** after IR (milestone row 10), R3 (row 11), SWC (row 12) and LAY (row 12A), and before Step 3.5. Seven
  new analyzers land in Step 3.5 and every one will use the `from <package>.xxx import ...` pattern this
  rename changes, so doing the rename first means those files are written once, under the final import
  path.
- **Where the history lives:** why the work package exists and why it is called PKG are in
  [Background](#5-background-and-origin); decisions are in
  [Appendix A](#appendix-a-decision-records).

## 2. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| PKG.1 | [One import path per name and one repository root](#pkg1--one-import-path-per-name-and-one-repository-root) | Complete | 2026-10-16 |
| PKG.2 | [Rename the src package](#pkg2--rename-the-src-package) | Planned | |

## 3. The slices

### PKG.1 — One import path per name and one repository root

- **Problem:** package initializers that re-export their children give each name two import paths, and they create
  the initializer loops that `tests/test_strategy_import_layering.py` must allow in `_BENIGN_CYCLE_PACKAGES`.
  Tests and a few source files also find the repository root by counting folders up from `__file__`, and a moved
  test broke on its count (LAY.3).
- **Decision:** each initializer holds only a docstring, and every importer names the defining module, as LAY.2
  and LAY.3 did. Nothing is re-exported from an old location. `_BENIGN_CYCLE_PACKAGES` ends holding only
  `src.config`: its initializer holds the settings code itself ([LAY decision A.7.3](../layering/LAY_CONTRACT_AND_SLICE_PLAN.md#a7-lay2-implementation-decisions-2026-10-12)),
  not a re-export, so its entry stays with that explanation. One module, `src/core/repository_root.py`, holds the
  only folder count; every other file imports `REPOSITORY_ROOT`. The decisions are recorded in [A.6](#a6-pkg1-decisions-2026-10-16).
- **Scope:**
  - the six re-exporting initializers: `src/data/repositories/`, `src/data/sec_edgar/`, `src/data/yfinance/`,
    `src/evaluation/` (its descriptive docstring stays), `src/evaluation/fixtures/` and `src/schema/`, and every
    importer of a name they re-export in `src/`, `tests/` and `scripts/`, including string patch targets;
  - the same defect outside initializers: `src/data/financial/providers.py` is deleted and its importers name
    `src/data/financial/production.py`, `src/data/sec_edgar/financial_facts.py` or the yfinance module that defines
    each name; `src/strategies/fcf_growth/models.py` stops exporting `MetricResult`, `MetricStatus` and `ReasonCode`
    and its importers take them from `src/core/metric_result.py`; `"settings"` leaves `__all__` in
    `src/cli_workspace.py`, whose module-level binding stays as the seam tests patch;
  - `_BENIGN_CYCLE_PACKAGES`;
  - `src/core/repository_root.py` with `REPOSITORY_ROOT`, and every folder count from `__file__` in `tests/`,
    `src/` and `scripts/` replaced by it. The one other count stays: the `sys.path.insert` line in
    `scripts/check_package_dependencies.py`, which runs before `src` is importable. Before the slice `tests/`
    held 51 `parents[N]` lines in 41 files and 15 `.parent.parent` lines (one of them not a count from
    `__file__`), `src/` held six and `scripts/` three;
  - `tests/test_one_home_per_name.py`: every initializer under `src/` holds only a docstring, except
    `src/config/__init__.py`; no module under `src/` lists in `__all__` a name it does not define; no file
    counts folders up from `__file__` except in the two places above; `REPOSITORY_ROOT / "pyproject.toml"`
    exists. An `AGENTS.md` §5 bullet states the rule;
  - the `core` row of the [§13 package table](../../../ARCHITECTURE.md#13-module-boundaries) adds the repository root;
  - a GitHub issue, "Tests repeat the Alembic migration setup", lists the tests that build an Alembic `Config` and
    upgrade a test database and asks whether one shared helper should replace them. The tests change only by D4's
    root replacement.
- **Branch:** `refactor/pkg-1-one-home-per-name`, from `main` after 12B, before PKG.2.
- **Detail:** this section's bullets and [A.6](#a6-pkg1-decisions-2026-10-16) are the slice plan; no further plan
  document.

### PKG.2 — Rename the `src` package

- **Problem:** `pyproject.toml`'s `[tool.setuptools.packages.find]` (`where = ["."]`,
  `include = ["src*"]`) packages the literal directory `src` as the project's distributed module, and every
  absolute import is `from src.xxx import ...`. Installing the project alongside another that also
  distributes `src` itself collides on `import src`. This does not affect running the project through
  `uv run` or `ian` today, but it is a real defect for the "safely consumable by an external harness" goal
  the IR work package serves: a Python-based harness would import this project's modules directly.
- **Decision:** the new top-level package is `investment_analysis_engine`, the conventional choice (a
  distribution name, already `investment-analysis-engine`, normalizes into its import name) and
  self-describing. Test patch targets are rewritten by the same mechanical rewrite and verified by the
  patch-target resolution test that SWC.2a adds, which resolves every string patch target in `tests/` to an
  existing attribute, so none silently points at a name that no longer exists.
- **Scope:**
  - move `src/` to `investment_analysis_engine/`;
  - update every absolute import (`from src.xxx import ...` and `import src.xxx`) across the package,
    `tests/`, `scripts/` and any document that names an import path literally;
  - update `pyproject.toml`: the `include` of `[tool.setuptools.packages.find]`, the entry point
    (`ian = "src.main:main"` becomes `ian = "investment_analysis_engine.main:main"`) and any other literal
    `src` reference;
  - update the [§13 package table](../../../ARCHITECTURE.md#13-module-boundaries) and the root name in
    `scripts/check_package_dependencies.py`;
  - update `AGENTS.md`'s `uv run ...` examples and the layering test's package name;
  - run the SWC.2a patch-target resolution test unchanged against the new package name; PKG adds no check
    of its own.
- **Branch:** `feat/pkg-rename`, from `main` after PKG.1 has merged, before SWC.5. LAY moves files and rewrites imports under the
  old name, so the rename must follow it ([LAY decision L10](../layering/LAY_CONTRACT_AND_SLICE_PLAN.md#a1-decisions-l1-to-l10-2026-10-11)).
  LAY.8 removes `scripts/simulate_package_layers.py`; the graph engine that stays with the dependency check carries a
  root name that this rename updates, as it does in `check_package_dependencies.py`.
- **Open question for the slice plan:** the application reads files outside the package: `alembic/`,
  `RUNTIME_AGENTS.md`, `logs/` and `data/`, `config/` (`config/strategies/` and
  `config/general_analysis_settings.toml`), and `tests/fixtures/` (through the Golden SEC EDGAR fixture in
  `src/evaluation/fixtures/sec_edgar_fpi.py`), all located through `REPOSITORY_ROOT`. The acceptance criterion
  "`ian` runs from the installed package" cannot hold for a wheel installed outside the repository until
  PKG.2's plan decides how each is found or packaged.
- **Detail:** ⚠ no slice plan yet

## 4. Scope limits and acceptance criteria

Scope limits:

- Any restructuring of the package's internal module layout beyond the rename itself and PKG.1's change to the
  package initializers.
- Any change of behavior, formula, presentation contract or public CLI surface.
- Any change to the `ian` command name.

Acceptance criteria:

- **No stale import path:** no `src.` import or dotted string target remains in the package, `tests/`,
  `scripts/`, `pyproject.toml` or the living documents.
- **Patch targets resolve:** the SWC.2a patch-target resolution test passes for every target string.
- **Entry point works:** `ian` runs from the installed package.
- **Layering rule intact:** the SWC layering test, renamed to the new package, passes unchanged.
- **Quality gate:** the complete managed quality gate passes, including the link check.

## 5. Background and origin

**Discovered:** 2026-09, during the same integration-readiness review that produced
[IR](../integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md); split out from IR into its own work package
because of its scale relative to IR's other, smaller fixes.

**Why not `R4`:** the obvious code for "one more refactor-shaped work package" would extend the existing
`R1`/`R2`/`R3` refactor-code series, but `R4` is already used as a document-local requirement/test-ID label
in `issue-17/ISSUE_17_TELEMETRY_CLOSEOUT_PLAN.md` and `step-3.4/SLICE_B2_COMPLETION_EVIDENCE.md`. Reusing it
as a project-wide work-package code would recreate the exact `R1`/`R2`/`R3` collision with
`graham-comparison/GRAHAM_COMPARISON_REPAIR_PLAN.md` that `MASTER_PLAN.md` now has to explicitly
disambiguate. `PKG` (short for "package rename") is unused anywhere in the repository.

**Why before Step 3.5:** the same reason `R3` and `IR` run first. Seven new analyzers land in 3.5, and doing
the rename first means those new files are written once.

## 6. Folder layout outcome

The strategy folder layout was an open question here. SWC settled it, because its first slices create the
strategy-owned files and its later slices build tooling around their locations. The outcome:

- every file a strategy owns, except its fixtures and cases, lives in `src/strategies/<strategy>/`, named
  for its role, with shared code in `src/strategies/_shared/` and the Graham family package
  `src/strategies/_graham/`, and every `__init__.py` under `src/strategies/` empty;
- a role-based layering test replaces the folder rule;
- SWC.2a relocates the existing analyzers, codecs, adapters and presenters, and retargets 101 importer
  files, before PKG rewrites every import line again. The second touch is accepted: the files had to be in
  their final place before the slices after SWC.2a could create theirs.

PKG therefore renames `src/strategies/` along with everything else and regroups nothing. The
[SWC design](../swc/SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#4-static-declaration-model) states the layout and the rule;
[its Appendix C.6](../swc/SWC_1_DESCRIPTOR_CONTRACT_DESIGN.md#c6-one-package-per-strategy) records the evidence.

---

## Appendix A: Decision records

### A.1 Package name

`investment_analysis_engine`, decided before this plan was written: the conventional normalization of the
distribution name, self-describing to a reader who has never seen the project, and independent of the `ian`
entry point name.

### A.2 Test patch targets

Previously left to PKG planning. Decided here: rewrite them mechanically with the import rewrite, and prove
none dangles with a resolution test, because `mypy --strict` cannot see a string target and a patch of an
unexercised path would otherwise pass silently.

### A.3 Folder layout (2026-10-03)

Previously a decision item for PKG planning, with the study's figures: about 29 modules to relocate, 76
importer files beyond the 29 that SWC already rewrites, three re-exporting `__init__.py` files to empty,
eleven directories per new strategy against eight with a package per strategy, and the cost of one diff
that is both a move and a rename. The project owner adopted one package per strategy inside SWC on the
condition that a role-based layering rule be enforceable and the module graph show no new cycle; both held,
so the question is closed ([§6](#6-folder-layout-outcome)). The study counted nine directories for one
package per strategy because it included `docs/user`, whose strategy lists are now generated; the adopted
design's eight matches this plan's earlier figure.

### A.4 Patch-target check moves to SWC.2a (2026-10-03)

The resolution test is built in SWC.2a, not here, because SWC.2a relocates modules across 101 importer files
and carries the same risk of a string target left pointing at a moved name. PKG reuses the test and adds none.

### A.5 Package initializers become docstring-only (2026-10-12)

The project owner decided, during LAY.3, to add a slice before the rename. LAY.2 and LAY.3 each removed a re-exporting
initializer, and each time the layering test's list of allowed initializer loops shrank. PKG.1 does the same for the
initializers that remain, so that no name has two import paths and the list ends empty, apart from `src.config`, which
holds the settings code and is not a re-export. The rename follows as PKG.2 and rewrites each import line once, under
its final path.

### A.6 PKG.1 decisions (2026-10-16)

The project owner decided:

- **D0, order.** PKG.1 and PKG.2 run before SWC.5 to SWC.7. SWC.6 and SWC.7 write import paths (generator
  templates, `src/core/strategy_stub.py`, the contributor guide), which should be written once, under the final
  package name. Nothing in SWC.5 to SWC.7 is a prerequisite for PKG.
- **D2, the same defect outside initializers.** `src/data/financial/providers.py` is deleted;
  `src/strategies/fcf_growth/models.py` stops re-exporting the shared metric types; `"settings"` leaves `__all__`
  in `src/cli_workspace.py`.
- **D4, one repository root.** `src/core/repository_root.py` holds the only folder count, and every other root
  lookup imports `REPOSITORY_ROOT`. The `core` row of the package table owns it.
