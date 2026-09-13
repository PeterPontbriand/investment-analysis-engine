# Step 2.5A A1 US-GAAP Foreign Annual-Form Review

Documents US-GAAP foreign annual-form support and its verification.

Local sequence and status: [companion plan](SEC_EDGAR_FPI_IFRS_SLICE_PLAN.md#sequence-and-status).

## 1. Outcome

 Existing `10-K` and `10-K/A` eligibility is unchanged.

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
