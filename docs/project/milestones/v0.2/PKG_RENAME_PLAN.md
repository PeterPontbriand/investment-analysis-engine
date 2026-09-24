# PKG — `src` to Real Top-Level Package Rename

**Status:** next after IR; not yet started; scope/contract review required before implementation,
matching this project's convention for any nontrivial work package.
**Discovered:** 2026-09, during the same integration-readiness review that produced
[IR](integration-readiness/IR_CONTRACT_AND_SLICE_PLAN.md); split out from IR into its own work
package because of its scale relative to IR's other, smaller fixes.
**Why not `R4`:** the obvious code for "one more refactor-shaped work package" would extend the
existing `R1`/`R2`/`R3` refactor-code series, but `R4` is already used as a document-local
requirement/test-ID label in `issue-17/ISSUE_17_TELEMETRY_CLOSEOUT_PLAN.md` and
`step-3.4/SLICE_B2_COMPLETION_EVIDENCE.md` — reusing it as a project-wide work-package code would
recreate the exact `R1`/`R2`/`R3` collision with `graham-comparison/GRAHAM_COMPARISON_REPAIR_PLAN.md`
that `MASTER_PLAN.md` now has to explicitly disambiguate. `PKG` (short for "package rename") is
unused anywhere in the repository at the time of writing.
**Sequenced before Step 3.5**, for the same reason `R3` and `IR` are: five new analyzers land in
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

## Out of scope for this note

This is not a request to restructure the package's internal module layout beyond the rename
itself, or to change any behavior, formula, presentation contract, or public CLI surface. `ian`
remains the CLI command name regardless of which internal package name is chosen (the two are
independent: the CLI entry point name and the internal import path do not have to match).
