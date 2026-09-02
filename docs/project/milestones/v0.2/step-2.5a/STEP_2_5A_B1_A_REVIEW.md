# Step 2.5A B1-A SEC Snapshot and Regime-Lock Review

**Base checkpoint:** `6e9019e40df13277fac9353e53446da44d1b26c3`<br/>
**Implementation date:** 2026-09-01 (America/Toronto)<br/>
**Status:** Implemented, verified, and approved at Gate C on 2026-09-01<br/>
**Authorization:** Gate B approval recorded in the
[A1 review](STEP_2_5A_A1_REVIEW.md)<br/>
**Execution plan:** [SEC EDGAR FPI / IFRS Slice Plan](SEC_EDGAR_FPI_IFRS_SLICE_PLAN.md)

## 1. Outcome

B1-A adds an optional provider-neutral analysis-scope capability and routes it
through production provider composition. The production FCF resolver and both
Graham execution paths enter that scope for one requested security and
effective `as_of`. Providers without the capability retain their existing
behavior.

The SEC implementation fetches one Company Facts/submissions pair, recursively
freezes the payload, and records retrieval time, normalized ticker, CIK,
effective `as_of`, accession availability, accession-to-taxonomy evidence,
latest eligible annual accession, selected taxonomy, and stable SHA-256 payload
identifiers. A context-local snapshot makes concurrent analysis scopes
independent while every SEC field in one analysis reuses the same evidence.

The latest annual accession publicly available at `as_of` selects the regime.
Missing or ambiguous accession/taxonomy evidence fails closed. Existing US-GAAP
duration paths accept facts only under a `us-gaap` lock, and a requested span
that reaches an unproved taxonomy transition is unavailable. B1-A adds no IFRS
concept mapping and does not change security-unit policy.

## 2. Deterministic proof

The Gate C matrix proves:

- one immutable Company Facts/submissions pair is reused across SEC fields;
- snapshot identity, retrieval boundary, taxonomy, accession, and checksums are
  retained and the payload cannot be mutated;
- historical `as_of` selects the then-latest annual accession/taxonomy and later
  filings do not leak backward;
- an accession observed under both supported namespaces is ambiguous;
- a requested span crossing an unproved regime transition is unavailable;
- missing/malformed accession evidence cannot establish a regime;
- the Graham execution boundary enters the same optional analysis scope; and
- the production FCF integration uses explicit deterministic submissions
  evidence and preserves its previous calculation result.

No test makes a live SEC, quote-provider, or LLM call.

## 3. Verification

- Focused B1-A/A1/A0 tests: 52 passed.
- Complete Ruff: passed.
- Complete Ruff format check: all 227 files formatted.
- Complete strict mypy: passed for 182 source files.
- Complete pytest: 1,270 passed at 88% reported coverage.
- `git diff --check`: passed, subject only to existing line-ending notices.

The canonical PowerShell quality wrapper subsequently passed on 2026-09-01
after using the installed `uv` executable and the rebuilt project `.venv`.
It passed Ruff, format verification, strict mypy for 182 source files, and all
1,270 tests at 88% reported coverage. Isolated artifacts were written beneath
`.tmp/quality-runs/20260901220838424-33668-284faa19dcc64045b4aa6da258b07091/`.
Dependencies and lock files were not changed.

## 4. Review decision required

Reviewers should confirm the optional provider capability is sufficiently
narrow, both approved analysis families own the scope, snapshot evidence and
immutability are adequate, historical regime selection fails closed, and no
B1-B exact IFRS mapping or C security-unit behavior entered this slice.

B1-A received explicit human approval at Gate C on 2026-09-01. The review gate
is closed and B1-B is authorized under the slice plan.
