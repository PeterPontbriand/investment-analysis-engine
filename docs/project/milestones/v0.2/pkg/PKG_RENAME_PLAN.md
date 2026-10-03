# PKG — `src` to Real Top-Level Package Rename

**Status:** next in sequence per `IMPLEMENTATION_PLAN.md` row 13, after IR (row 10), SWC (row 11),
and R3 (row 12); not yet started; scope/contract review required before implementation, matching
this project's convention for any nontrivial work package.
**Discovered:** 2026-09, during the same integration-readiness review that produced
[IR](../integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md); split out from IR into its own work
package because of its scale relative to IR's other, smaller fixes.
**Why not `R4`:** the obvious code for "one more refactor-shaped work package" would extend the
existing `R1`/`R2`/`R3` refactor-code series, but `R4` is already used as a document-local
requirement/test-ID label in `issue-17/ISSUE_17_TELEMETRY_CLOSEOUT_PLAN.md` and
`step-3.4/SLICE_B2_COMPLETION_EVIDENCE.md` — reusing it as a project-wide work-package code would
recreate the exact `R1`/`R2`/`R3` collision with `graham-comparison/GRAHAM_COMPARISON_REPAIR_PLAN.md`
that `MASTER_PLAN.md` now has to explicitly disambiguate. `PKG` (short for "package rename") is
unused anywhere in the repository at the time of writing.
**Sequenced before Step 3.5**, for the same reason `R3` and `IR` are: seven new analyzers land in
3.5, and every one of them will use the same `from src.xxx import ...` pattern this rename
changes, so doing the rename first means those new files are written once, under the final
import path, instead of being written once and then touched again by the rename.

## Trigger

`pyproject.toml`'s `[tool.setuptools.packages.find]` (`where = ["."]`, `include = ["src*"]`)
packages the literal directory `src` as this project's distributed module. Every absolute import
in the codebase is `from src.xxx import ...`. Installing this project alongside any other project
that uses the common "src layout" convention — where `src/` is a directory that is *not* itself a
package, and the actually-distributed package lives one level under it — is fine; installing it
alongside a project that (like this one currently does) distributes `src` itself as the package
name collides on `import src`.

## Problem

This project's own `pyproject.toml` already declares a real project name
(`investment-analysis-engine`) and a real CLI entry point (`ian`), but the Python import surface
underneath both is the generic, collision-prone `src`. This doesn't affect running the project
via `uv run` or the `ian` command today, and nothing currently installs this project alongside
another `src`-named package — but it is a real defect for the "safely consumable by an external
harness" goal the IR work package exists to serve, since a Python-based harness would need to
`pip install` or otherwise import this project's modules directly, not just shell out to `ian`.

## Likely scope, once picked up

- **Decided:** the new top-level package name is `investment_analysis_engine` — the conventional
  choice (Python packaging convention normalizes a distribution name, already
  `investment-analysis-engine`, into its import name), and self-describing to a reader who has
  never seen this project before. `ian` remains the separate CLI entry point name, unaffected by
  this choice.
- Move `src/` to the chosen package directory name.
- Update every absolute import (`from src.xxx import ...` / `import src.xxx`) across `src/`,
  `tests/`, and any scripts or docs that reference import paths literally.
- Update `pyproject.toml`: `[tool.setuptools.packages.find]`'s `include`, `[project.scripts]`'s
  entry point target (`ian = "src.main:main"` → `ian = "investment_analysis_engine.main:main"`),
  and any other literal `src` reference.
- Update `AGENTS.md`'s own `uv run ...` examples and any other documentation that names the
  package path literally.
- Decide whether test patch targets (`patch("src.cli_support.typer.echo")`-style strings
  throughout the test suite) are mechanically rewritten or need individual review — a rename of
  this scale risks a patch target silently pointing at a name that no longer resolves to
  anything, which `mypy --strict` will not catch (`unittest.mock.patch` targets are strings) but
  the test suite itself will, if the patched code path is actually exercised.

## Decision for PKG planning: folder layout

**Question.** SWC (design adopted 2026-10-03) leaves each strategy's files in the layer folders they
already belong to: a new strategy is 21 files across 11 directories, of which 15 are new and strategy-named.
Those files could be regrouped into one package per strategy (analyzer, arguments, handler, selection,
codec, adapter, replay, presenter, envelope, CLI and evaluation files together) as a pure move. PKG rewrites
every import line anyway. **PKG planning must decide whether to combine the regrouping with the rename.**
This note does not decide it.

**Evidence for the decision** (from the [co-location study](../swc/SWC_COLOCATION_STUDY.md), Appendix H, and the
adopted design):

| Figure | Value |
| :--- | :--- |
| Existing modules that would relocate | About 29 (17 analyzer files across four packages, four codecs, four adapters, four presenters), plus the new strategy files |
| Importer files whose import lines change because of the move (`src` and `tests`) | 76 beyond the 29 that SWC already rewrites (105 in all: 35 in `src`, 70 in `tests`) |
| Package `__init__.py` files that would have to be emptied | Three analyzer packages (`fcf_earnings_growth`, `graham_growth`, `graham_number`), with 13 importer files of their re-exports |
| Directories a new strategy touches | 11 today; 8 with a package per strategy (fixtures and cases stay in `evaluation`) |
| Saving if combined with PKG | Each of the 76 additional importer files is edited once instead of twice |
| Cost if combined | One diff that is both a move and a rename, which cannot be reviewed as either; test patch strings (this plan's named risk) change in one pass |

**Layering rule the decision must respect.** SWC's design establishes that no module under `data`,
`workspace`, `orchestrator`, `reporting`, `analysis`, `core` or `config` imports the composition-root
descriptor, a tier or a strategy-owned CLI or evaluation file, including through a parent package. A package
per strategy spans layers, so folder names would stop encoding layers; the layering test (T13) states its
rule by folder and would have to state it by module role. Shared Graham code (profile composition, the
two-selection provider tuples, replay helper) would need a family package. Package `__init__.py` files must
stay empty. The decision must say how each of these is handled, or keep the layer folders.

## Out of scope for this note

This is not a request to restructure the package's internal module layout beyond the rename
itself, apart from the folder-layout decision recorded above, which PKG planning decides, or to change any behavior, formula, presentation contract, or public CLI surface. `ian`
remains the CLI command name regardless of which internal package name is chosen (the two are
independent: the CLI entry point name and the internal import path do not have to match).
