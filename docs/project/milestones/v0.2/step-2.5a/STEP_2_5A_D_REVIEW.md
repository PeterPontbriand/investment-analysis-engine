# Step 2.5A Slice D — Gate F Review Record

**Date:** 2026-09-01  
**Status:** approved at mandatory Gate F

## Versioned benchmark delta

| Measure | Previous | Slice D | Delta |
|---|---:|---:|---:|
| Suite version | `h1-v2` | `h1-v3` | deliberate version increment |
| Fixture-set version | `step-2.5-h1-v2` | `step-2.5-h1-v3` | deliberate version increment |
| Cases | 15 | 19 | +4 |
| Passed | 15 | 19 | +4 |
| Failed | 0 | 0 | 0 |
| Deterministic pass rate | 100% | 100% | unchanged |
| Strategy selection | `not_measured` | `not_measured` | unchanged |

No prior case ID, case definition, or historical fixture was removed or
rewritten to obtain this result.

## Added cases

- `FPI-01`: frozen ASML exact US-GAAP diluted EPS filed on Form `20-F` reaches
  the existing single-fiscal-year Graham growth-value path successfully.
- `FPI-02`: frozen NTR exact IFRS diluted-EPS duration fact reaches that path
  successfully with its SEC provenance.
- `FPI-03`: frozen SAP evidence remains `input_unavailable` because its broader
  combined investing concept is not substituted for exact physical-PP&E CapEx.
- `FPI-04`: frozen NVO ADR evidence leaves the quote comparison unavailable;
  no ADR ratio or currency conversion is applied.

The deterministic fixture composer uses the checked-in D0 fragments and an
injected SEC transport. It performs no real SEC, quote-provider, or LLM call.
The Graham tool argument schema now exposes `fiscal_year`, which was already a
supported single-observation resolver basis, so the two success cases exercise
the production handler rather than bypassing it.

## Verification

Focused Golden checks passed with 19/19 cases. The complete repository wrapper
also passed:

- Ruff and format check (`235` files);
- strict mypy (`188` source files); and
- `1,288` tests with `88%` reported coverage.

Isolated artifacts:
`.tmp/quality-runs/20260901225556738-31284-89662d32584c46f6980ea203af66833d/`.

## Gate F checklist

- [x] Approve the deliberate suite and fixture-set version increments.
- [x] Approve the denominator change from 15 to 19 and the four case outcomes.
- [x] Confirm no failure was removed, retuned, or hidden.
- [x] Confirm strategy selection remains honestly `not_measured`.
- [x] Authorize Slice E only after this review is complete.

Gate F received explicit human approval on 2026-09-01.
