# PD — Package Dependency Map and Import Check: Plan

Writes down what each top-level package under `src/` owns and which packages import which, enforces it with a
check, removes Mermaid from the documentation, and files the existing two-way dependencies for a decision. The
project owner decided every question in [Appendix A](#appendix-a-decision-records). The
[milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status) owns its position and work-package status.

## 1. At a glance

- **What this work does:** replaces the package list in [ARCHITECTURE.md §13](../../../ARCHITECTURE.md#13-module-boundaries)
  with one table (`Package | Owns | Imports | Two-way with`), adds `scripts/check_package_dependencies.py` to fail
  when the table and the code disagree, corrects the one-line description in each package `__init__.py`, replaces
  the two Mermaid diagrams in the contributor guide with text and tables, and files issue
  [#114](https://github.com/PeterPontbriand/investment-analysis-engine/issues/114) for the ten two-way pairs.
- **What it is not:** a change to any import, package boundary or behavior. It does not break a two-way pair, and
  it adds no layered listing or diagram of the graph, because 14 of the 15 units are mutually reachable and no
  layering can be stated until pairs are broken.
- **Rules it follows:** the only edits under `src/` are one-line package descriptions; no planning label outside
  `docs/project/` and `.github/` planning artifacts; no new dependency; the managed gate with the 3.14 pass.
- **One slice:** PD, plan and implementation in one change.
- **Where it sits:** after the Massive provider removal and PH.2c, before issue #40, which is before PH.3.
- **Where the history lives:** [Background](#5-background-and-origin) and [Appendix A](#appendix-a-decision-records).

## 2. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| PD | [Package table, import check, no Mermaid](#pd--package-table-import-check-no-mermaid) | Complete | 2026-10-10 |

PD branches from `main`. In the [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status) the work package
is row 11B, `Complete`. The milestone table orders rows by status, so the row sits among the complete rows.

## 3. The work

### PD — Package table, import check, no Mermaid

- **Problem:** the documentation does not say what each top-level package owns or which packages may import
  which, and nothing enforces it. The contributor guide carries two Mermaid diagrams, one of which fails to parse.
- **Decision:** one table is the only declaration of the map; a standard-library check compares it with the code
  on every gate run; Mermaid is not used in documentation. Issue
  [#114](https://github.com/PeterPontbriand/investment-analysis-engine/issues/114) records the two-way pairs and
  leaves their resolution to a later decision. Step 3.5 waits for that decision
  ([entry condition](../step-3.5/STEP_3_5_CONTRACT_AND_SLICE_PLAN.md)).
- **Scope:**
  - the §13 table and one sentence under the §3 overview diagram pointing to it;
  - `scripts/check_package_dependencies.py` and `tests/scripts/test_check_package_dependencies.py`, wired into
    `scripts/run-quality-gates.sh`, `scripts/run-quality-gates.ps1`, `.github/workflows/ci.yaml`, the
    documentation-only gate in `AGENTS.md` §7 and the Quality gates section of `docs/project/README.md`;
  - the one-line description in each top-level package `__init__.py`, made to agree with its `Owns` sentence;
  - the contributor guide: the flowchart and its introducing sentence deleted, the sequence diagram replaced by
    step tables checked against the code;
  - the Mermaid rule in `AGENTS.md` and `docs/project/README.md`, and a failing check in
    `scripts/check_doc_links.py` with a test;
  - the sequencing text in the PH plans and one line in the PKG plan.
- **Branch:** `chore/package-dependency-map`, from `main`.
- **Detail:** this document.

## 4. Scope limits and acceptance criteria

Scope limits:

- No change to any import, package boundary, formula, classification, result shape or behavior.
- No layered listing and no diagram of the import graph.
- No fix for any two-way pair; issue #114 holds them.
- No new dependency and no edit to `pyproject.toml` or `uv.lock`.

Acceptance criteria:

- **Table matches code:** `python scripts/check_package_dependencies.py` passes on the change and reports, in one
  run, every undeclared import, unused declared import, missing unit or row, undeclared two-way pair and stale
  two-way declaration, each with the table change to make.
- **No Mermaid:** `python scripts/check_doc_links.py` passes and fails on a fenced `mermaid` block.
- **Descriptions agree:** every package `__init__.py` that has a description agrees with its `Owns` sentence.
- **Guide checked:** every step in the contributor guide's tables was checked against the code.
- **Issue filed:** #114 lists each pair with import counts in each direction, the causing files and a
  classification with evidence.
- **Quality gate:** the complete managed gate passes, including the 3.14 pass.

## 5. Background and origin

The two-way pairs were found while preparing issue #40, when a proposed import from `orchestrator` to
`reporting` was questioned and the existing imports between packages were counted. The sequence diagram was found to
be unparseable in the same review. The reference figures on `main` at `d06a1bb`: 15 units, 61 dependencies between
units, ten two-way pairs, 14 of 15 units mutually reachable (`tools` imports no other unit).

## Appendix A: Decision records

Kept for the record.

| # | Decision |
| :--- | :--- |
| D1 | One work package, one slice, plan and implementation in one change; row 11B of the milestone table. |
| D2 | §13 becomes one table, the single declaration of the map. |
| D3 | A standard-library, non-mutating check reads the table, computes the graph, and reports every difference in one run. |
| D4 | No layered listing and no diagram of the graph. |
| D5 | The check runs in both gate wrappers and in CI, and is on the documentation-only gate list. |
| D6 | Unit tests on temporary trees, one per finding type, plus a clean pass, a function-level import and the `cli` grouping. |
| D7 | Package descriptions have one home, the §13 table; each `__init__.py` description is corrected to agree. |
| D8 | The contributor guide's diagrams become step tables. |
| D9 | No Mermaid in documentation; the link check fails on it. |
| D10 | `ARCHITECTURE.md` §3 points to §13. |
| D11 | Issue #114 files the two-way pairs and is an entry condition of Step 3.5. |
| D12 | The order is PD, then issue #40, then PH.3; the package rename updates §13 and the check script's root. |
