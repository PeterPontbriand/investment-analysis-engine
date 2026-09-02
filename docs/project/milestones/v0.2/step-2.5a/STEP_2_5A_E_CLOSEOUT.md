# Step 2.5A Slice E — Closeout Verification Record

**Date:** 2026-09-01  
**Status:** complete and approved

## Implemented surface

- Existing exact US-GAAP annual duration mappings accept reviewed `10-K`,
  `10-K/A`, `20-F`, `20-F/A`, `40-F`, and `40-F/A` forms.
- Exact IFRS annual duration mappings cover diluted EPS, adjusted diluted
  weighted-average shares, operating cash flow, and physical-PP&E CapEx.
- One immutable SEC snapshot owns Company Facts, submissions, accession
  availability, and taxonomy selection for an analysis.
- Historical taxonomy selection is latest-eligible-accession based and rejects
  unproved cross-regime spans.
- Quote comparison requires affirmative matching-currency ordinary-share 1:1
  evidence and otherwise fails closed.
- Golden versions `h1-v3` / `step-2.5-h1-v3` add four reviewed cases without
  changing historical case IDs or fixtures.

## Explicitly unsupported

- IFRS BVPS and IFRS preferred-zero inference;
- ADR/ADS ratio conversion and currency conversion;
- custom taxonomy extensions, fuzzy concept matching, broader-concept
  substitution, and summation fallbacks; and
- inference that a generic outstanding-share fact proves an ordinary-share or
  quoted-security unit.

Missing or ambiguous evidence remains unavailable. Issuer-level OCF, CapEx,
and derived FCF are not erased solely because per-share/quote compatibility is
unavailable.

## Canonical deterministic evaluation

Command: `uv run --no-sync financial-agents evaluate --report
.tmp/step-2.5a-h1-v3-closeout.json`

- Suite version: `h1-v3`
- Fixture-set version: `step-2.5-h1-v3`
- Passed: 19
- Failed: 0
- Skipped: 0
- Strategy selection: `not_measured`
- Live SEC, quote-provider, and LLM calls: none

The generated report is an ignored local artifact and is not intended for
commit.

## Complete repository gate

The canonical wrapper passed:

- Ruff and format check (`236` files);
- strict mypy (`188` source files); and
- `1,288` tests with `88%` reported coverage.

Isolated artifacts:
`.tmp/quality-runs/20260901230426203-22836-8a35c5db516b40d7a3b095e4a493985f/`.

## Final approval checklist

- [x] Provider support and user documentation match the verified surface.
- [x] Required unsupported boundaries remain explicit.
- [x] The canonical deterministic suite passes and records its versioned
  denominator honestly.
- [x] The complete repository quality gate passes.
- [x] The final implementation/documentation diff receives explicit human
  approval.

Final human approval was received on 2026-09-01. Step 2.5A is complete; Step
2.6 has not started.

No commit, push, PR, merge, completion claim, or Step 2.6 start is implied by
these automated results.
