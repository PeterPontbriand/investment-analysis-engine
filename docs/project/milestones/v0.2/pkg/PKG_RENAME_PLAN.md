# PKG — `src` to Real Top-Level Package Rename

Renames the project's import package from the collision-prone `src` to `investment_analysis_engine`,
before Step 3.5 adds seven analyzers that would otherwise be written under the old path. The
[milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status) owns its position and work-package status.

## 1. At a glance

- **What this work does:** moves the `src/` package to `investment_analysis_engine/`, rewrites every
  absolute import and every dotted patch target to the new name, and updates `pyproject.toml`,
  `AGENTS.md` and any document that names an import path literally.
- **What it is not:** a restructuring of the package's internal layout, or any change of behavior,
  formula, presentation contract or public CLI surface. `ian` stays the CLI command name; it is
  independent of the import name. The strategy folder layout is already settled by SWC
  ([§6](#6-folder-layout-outcome)); PKG renames it and does not regroup it.
- **Rules it follows:** the managed quality gate at the end; no new dependency without explicit user
  permission; scope and contract review before implementation, as for any nontrivial work package.
- **Where it sits:** after IR (milestone row 10), R3 (row 11) and SWC (row 12), and before Step 3.5. Seven
  new analyzers land in Step 3.5 and every one will use the `from <package>.xxx import ...` pattern this
  rename changes, so doing the rename first means those files are written once, under the final import
  path.
- **Where the history lives:** why the work package exists and why it is called PKG are in
  [Background](#5-background-and-origin); decisions are in
  [Appendix A](#appendix-a-decision-records).

## 2. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| PKG | [Rename the src package](#pkg--rename-the-src-package) | Planned | |

## 3. The work

### PKG — Rename the `src` package

- **Problem:** `pyproject.toml`'s `[tool.setuptools.packages.find]` (`where = ["."]`,
  `include = ["src*"]`) packages the literal directory `src` as the project's distributed module, and every
  absolute import is `from src.xxx import ...`. Installing the project alongside another that also
  distributes `src` itself collides on `import src`. This does not affect running the project through
  `uv run` or `ian` today, but it is a real defect for the "safely consumable by an external harness" goal
  the IR work package serves: a Python-based harness would import this project's modules directly.
- **Decision:** the new top-level package is `investment_analysis_engine`, the conventional choice (a
  distribution name, already `investment-analysis-engine`, normalizes into its import name) and
  self-describing. Test patch targets are rewritten by the same mechanical rewrite, and a check resolves
  every dotted `patch(...)` and `monkeypatch.setattr(...)` target string to an importable object, so none
  silently points at a name that no longer exists.
- **Scope:**
  - move `src/` to `investment_analysis_engine/`;
  - update every absolute import (`from src.xxx import ...` and `import src.xxx`) across the package,
    `tests/`, `scripts/` and any document that names an import path literally;
  - update `pyproject.toml`: the `include` of `[tool.setuptools.packages.find]`, the entry point
    (`ian = "src.main:main"` becomes `ian = "investment_analysis_engine.main:main"`) and any other literal
    `src` reference;
  - update `AGENTS.md`'s `uv run ...` examples and the layering test's package name;
  - the patch-target resolution check above.
- **Branch:** `feat/pkg-rename`, from `main` after SWC.7 has merged.
- **Detail:** ⚠ no slice plan yet

## 4. Scope limits and acceptance criteria

Scope limits:

- Any restructuring of the package's internal module layout beyond the rename itself.
- Any change of behavior, formula, presentation contract or public CLI surface.
- Any change to the `ian` command name.

Acceptance criteria:

- **No stale import path:** no `src.` import or dotted string target remains in the package, `tests/`,
  `scripts/`, `pyproject.toml` or the living documents.
- **Patch targets resolve:** the check in the decision above passes for every target string.
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
none dangles with a resolution check, because `mypy --strict` cannot see a string target and a patch of an
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
