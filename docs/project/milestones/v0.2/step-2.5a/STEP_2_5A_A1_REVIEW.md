# Step 2.5A A1 US-GAAP Foreign Annual-Form Review

**Implementation date:** 2026-09-01 (America/Toronto)<br/>
**Status:** Implemented, verified, and approved at Gate B on 2026-09-01<br/>
**Authorization:** A0 approval recorded in the
[A0 review](STEP_2_5A_A0_REVIEW.md)<br/>
**Execution plan:** [SEC EDGAR FPI / IFRS Slice Plan](SEC_EDGAR_FPI_IFRS_SLICE_PLAN.md)

## 1. Outcome

A1 adds `20-F`, `20-F/A`, `40-F`, and `40-F/A` to the completed-annual
duration-form eligibility already used by the exact US-GAAP operating cash
flow, PP&E capital expenditure, diluted EPS, and diluted weighted-average share
paths. Existing `10-K` and `10-K/A` eligibility is unchanged.

Balance-sheet/instant facts retain their separate `10-K`/`10-K/A` form set.
A1 does not add IFRS concepts, snapshot/regime selection, security-unit
compatibility, ADR/ADS conversion, new formulas, or method-version changes.

## 2. Deterministic proof

The A1 regression module uses only the approved minimized ASML D0 evidence and
an injected fetcher. It proves:

- all four duration fields accept `10-K`, `10-K/A`, `20-F`, `20-F/A`, `40-F`,
  and `40-F/A`;
- `6-K` and `8-K` remain ineligible for those paths;
- a non-`FY` observation remains ineligible; and
- a `20-F` stockholders-equity observation remains unavailable, proving that
  instant-form eligibility was not broadened.

No verification test made a live SEC, quote-provider, or LLM call.

## 3. Verification

- Focused Ruff and formatting checks: passed.
- Focused strict mypy: passed for the changed source and A1 regression module.
- Focused A1 plus A0 preservation tests: 44 passed.
- Complete Ruff: passed; all 224 files were already formatted.
- Complete strict mypy: passed for 181 source files.
- Complete pytest: 1,262 passed at 88% reported coverage.
- `git diff --check`: passed; Git emitted only existing line-ending notices.

The repository wrapper could not start because `uv` is absent from the managed
shell PATH and this checkout's `.venv` points to a missing
`C:\Python314\python.exe`. The same non-mutating Ruff, strict-mypy, and pytest
gates were therefore run directly, using the working synchronized environment
from the adjacent preserved checkout for Python-based commands. No dependency
installation or lockfile change was made.

## 4. Review decision required

Reviewers should confirm that the shared completed-annual duration form set is
the correct boundary, balance-sheet forms remain unchanged, negative scope
tests are sufficient, and no B1 or C behavior entered A1.

A1 received explicit human approval at Gate B on 2026-09-01. The review gate is
closed and B1-A is authorized under the slice plan.
