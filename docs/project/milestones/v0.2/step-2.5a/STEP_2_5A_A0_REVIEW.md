# Step 2.5A A0 Identity/Security-Unit Boundary Review

**Base checkpoint:** `a4001580838795a30d72f399fb4eedcb65dee9f3`<br/>
**Implementation date:** 2026-08-31 (America/Toronto)<br/>
**Status:** Implemented, verified, and approved on 2026-09-01<br/>
**Authorization:** Gate A approval recorded in the
[D0 evidence handoff](STEP_2_5A_D0_EVIDENCE_FREEZE.md)<br/>
**Execution plan:** [SEC EDGAR FPI / IFRS Slice Plan](SEC_EDGAR_FPI_IFRS_SLICE_PLAN.md)

## 1. Outcome

A0 corrects one internal SEC adapter boundary without expanding the supported
form, taxonomy, concept, calculation, or public contract surface. Exact
ticker-to-CIK resolution remains mandatory. Once that identity is established,
the adapter now distinguishes fields by the unit represented by the fact:

- operating cash flow and capital expenditure are issuer-level monetary facts,
  so another ticker row for the same CIK does not erase them; and
- diluted EPS and diluted weighted-average shares remain unavailable when the
  CIK has multiple ticker rows, because A0 does not yet provide affirmative
  evidence that the requested security and filing share unit are compatible.

Unknown tickers and a Company Facts payload whose CIK differs from the resolved
CIK still return unavailable. This preserves the approved fail-closed behavior
for every per-share path while removing an over-broad identity proxy from
issuer-level paths.

## 2. Bounded implementation

The production change is confined to
`src/data/sec_edgar/financial_facts.py`. The former all-field single-ticker set
is split into issuer-level and security-unit-sensitive completed-annual field
sets, and only the security-unit-sensitive set invokes the existing
single-ticker guard.

A0 deliberately does **not**:

- accept `20-F`, `20-F/A`, `40-F`, or `40-F/A` facts (A1 owns that change);
- add IFRS mappings or taxonomy selection (B1-A/B1-B);
- create an affirmative security-unit predicate or support ADR/ADS conversion
  (C);
- change exact ticker-to-CIK lookup, payload-CIK validation, annual candidate
  selection, provenance, method versions, calculators, or public support
  claims; or
- implement the approved resolver-spanning snapshot boundary. Gate A records
  that both analysis resolvers are owned by B1-A, where that work remains
  scheduled.

## 3. Deterministic proof

The new A0 regression module consumes only the approved D0 evidence fragments.
It rewrites the frozen ASML observations from `20-F` to an already-supported
`10-K` value in memory so the test isolates identity/unit behavior and cannot
accidentally implement or validate A1.

| Matrix boundary | Result |
| :--- | :--- |
| A0-01 — frozen single- versus multi-ticker CIK shapes | Passed |
| A0-02 — multi-ticker CIK retains issuer-level OCF and CapEx | Passed |
| A0-03 — multi-ticker CIK keeps EPS and diluted WASO unavailable | Passed |
| A0-04 — unknown ticker and Company Facts CIK mismatch remain unavailable | Passed |

The test-first run failed exactly the two new issuer-level cases and passed the
five preservation cases. After the bounded adapter correction:

- focused A0/affected adapter tests: 26 passed;
- broader SEC provider/resolver regression set: 70 passed;
- focused Ruff and formatting checks: passed;
- focused strict mypy: passed; and
- complete repository quality wrapper: Ruff passed, all 223 files were already
  formatted, strict mypy passed for 180 source files, and 1,225 tests passed at
  87% reported coverage.

No verification test made a live SEC, market-data, or LLM call.

## 4. Review decision required

Reviewers should confirm that:

- exact ticker-to-CIK and Company Facts CIK validation are unchanged;
- OCF and CapEx are correctly treated as issuer-level at this boundary;
- EPS and diluted weighted-average shares still fail closed for a multi-ticker
  CIK until affirmative unit evidence exists;
- the in-memory legacy-form mutation keeps A0 independent of A1; and
- resolver-spanning snapshot ownership remains documented for B1-A rather than
  being pulled into this slice.

A0 received explicit human approval on 2026-09-01. The mandatory review gate
is closed and A1 is authorized under the slice plan.
