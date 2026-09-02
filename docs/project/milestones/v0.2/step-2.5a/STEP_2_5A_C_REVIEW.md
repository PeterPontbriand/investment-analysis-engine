# Step 2.5A Slice C — Gate E Review Record

**Date:** 2026-09-01  
**Status:** approved at mandatory Gate E

## Outcome

Slice C adds a provider-neutral, typed security-unit evidence contract and a
fail-closed compatibility predicate. The initial predicate affirms a quote
comparison only when all of the following are explicit:

- filing unit is an ordinary share;
- quoted unit is an ordinary share;
- underlying-share ratio is exactly 1:1;
- neither unit relationship nor class mapping is ambiguous; and
- filing and quote currencies are both known and equal.

Missing evidence, unknown ratio, multi-class ambiguity, ADR/ADS units, non-1:1
ratios, and currency mismatch return a typed unavailable result. No conversion,
ratio adjustment, fuzzy inference, generic-share inference, or zero substitution
was introduced.

## Enforcement boundary

`SecurityUnitEvidence` is carried separately on the existing request-scoped
`InstrumentProfile`; it is not conflated with descriptive identity or instrument
kind. Graham quote comparisons consume the evidence when an instrument profile
is present. A missing or non-affirmative profile evidence block suppresses only
the margin-of-safety comparison. It does not alter calculator math or erase SEC
issuer-level OCF, CapEx, or derived FCF facts.

Legacy analysis calls that do not yet compose an instrument profile retain their
existing behavior. This keeps the change bounded to the reviewed request-scoped
evidence path while production composition is completed by its owning workflow.

## Deterministic evidence

- C-01 loads the frozen NVO evidence: one ADR represents one B share, but DKK
  filing currency and synthetic USD quote currency make the comparison
  unavailable. The predicate does not perform either ADR or currency conversion.
- C-02 proves a synthetic ordinary-share 1:1 relationship with matching USD
  currencies is affirmative and permits the otherwise-supported comparison.
- C-03 proves missing evidence, unknown ratios, multi-class ambiguity, ADR
  units, and non-1:1 ratios fail closed.
- C-04 is represented by the missing-evidence case: a generic shares fact is not
  accepted as `SecurityUnitEvidence` and therefore cannot affirm compatibility.

## Focused verification

The focused Slice C command set passed:

- Ruff on the five directly affected source/test files;
- strict mypy on those files; and
- 30 tests across the unit predicate, instrument profile, and Graham comparison
  boundary.

The complete canonical repository wrapper also passed:

- Ruff check and format check (`233` files already formatted);
- strict mypy (`186` source files); and
- `1,288` tests with `88%` reported coverage.

Isolated artifacts:
`.tmp/quality-runs/20260901224436330-10108-6342d7e5f17043c3b208b60455708765/`.

## Gate E review checklist

- [x] Approve the evidence fields and exact ordinary-share 1:1 predicate.
- [x] Approve fail-closed precedence for the NVO currency mismatch.
- [x] Confirm ADR/ADS and currency conversion remain deferred.
- [x] Confirm issuer-level financial facts remain independent of quote-unit
  compatibility.
- [x] Authorize Slice D only after this review is complete.

Gate E received explicit human approval on 2026-09-01.
