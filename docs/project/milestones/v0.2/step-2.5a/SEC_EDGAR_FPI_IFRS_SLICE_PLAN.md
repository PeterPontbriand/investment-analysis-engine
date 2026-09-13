# SEC EDGAR FPI / IFRS Slice Plan

Organizes foreign-filing support around bounded mappings and regression evidence.

Work-package order and status: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## Sequence and status

| Order | Scope | Local gate |
| :--- | :--- | :--- |
| D0 → A0 → A1 | Evidence; identity/unit boundary; US-GAAP annual forms | Accepted |
| B1-A → B1-B → C | Snapshot/regime lock; IFRS concepts; compatibility | Accepted |
| D → E | Benchmark extension; documentation/verification | Accepted |

## 1. Objective

Step 2.5A extends the existing SEC annual financial-fact adapter to a narrow,
auditable foreign-private-issuer surface without weakening the Step 2.3/2.4
financial rules.

## 2. Fixed decisions

- A1 expands annual forms for already-approved US-GAAP duration concepts only.
- B1 adds only the four exact IFRS duration concepts approved in the mapping
  record.
- One immutable SEC snapshot supplies all Company Facts and submission evidence
  for an analysis.
- Accounting regime is selected from the latest eligible annual accession at
  effective `as_of`; lifetime namespace presence is not a taxonomy lock.
- Existing availability, period, currency, duplicate, restatement, sign,
  provenance, and no-look-ahead semantics remain in force.
- Per-share/quote results require proven security-unit compatibility. The first
  implementation supports only affirmative ordinary-share / 1:1 shapes.
- IFRS BVPS, dimensional share-capital analysis, preferred-zero inference,
  ADR/ADS conversion, currency conversion, and custom extensions are deferred.
- Missing or ambiguous evidence remains unavailable. No broad fallback, fuzzy
  matching, summation, or zero substitution is permitted.
- Production persistence remains owned by Step 3.1; telemetry never controls
  fact selection.

## 3. Component contracts

### D0 — evidence freeze and implementation handoff

**Owned artifacts**

- this mapping record and slice plan;
- minimized deterministic fixture candidates derived from the reviewed NTR,
  SAP, NVO, and ASML evidence; and
- an explicit field/form/regime/security-unit test matrix.

**Required work**

1. Reconfirm the exact provider shapes against the checked-in evidence fragments.
2. Remove unrelated issuer data and retain source URL, retrieval date, accession,
   taxonomy, form, period, unit, and checksum metadata.
3. Identify the smallest existing adapter/contracts that A1 and B1 must touch.
4. Establish the relevant focused test baseline.

### A0 — identity/security-unit boundary correction

**Required work**

1. Preserve exact ticker-to-CIK resolution and existing missing/mismatched
   identity behavior.
2. Classify annual SEC fields explicitly by issuer-level versus per-share unit
   scope.
3. Allow exact issuer-level OCF and CapEx facts for a CIK with multiple ticker
   rows; do not treat multiple rows alone as fact ambiguity.
4. Keep EPS and weighted-average diluted shares unavailable for a multi-ticker
   CIK until later affirmative security-unit evidence exists.
5. Prove A0-01 through A0-04 from the approved D0 matrix without accepting
   foreign annual forms or changing calculator, method-version, or public
   support behavior.

### A1 — US-GAAP foreign-annual-form duration support

**Required work**

1. Add `20-F`, `20-F/A`, `40-F`, and `40-F/A` to the shared annual-duration form
   eligibility for the existing approved US-GAAP OCF, CapEx, diluted EPS, and
   weighted-average diluted-share paths.
2. Leave balance-sheet/instant-form eligibility unchanged.
3. Add ASML-positive and form/scope-negative deterministic tests.
4. Prove existing `10-K`/`10-K/A` behavior and method versions are unchanged.

Do not begin IFRS
mapping until A1 is approved.

### B1-A — analysis-scoped SEC snapshot and regime lock

**Required work**

1. Introduce the smallest immutable request-scoped snapshot/composition seam that
   prevents separate fields from fetching different Company Facts or submission
   states.
2. Resolve the latest eligible annual accession/taxonomy at effective `as_of`.
3. Require a homogeneous requested observation span and explicit ambiguity on an
   unproved regime transition.
4. Preserve current dependency injection, fail-open metadata behavior, and
   provider-neutral fact/result contracts.

### B1-B — exact IFRS duration concepts

**Required work**

1. Add exact mappings for diluted EPS, adjusted weighted-average shares,
   operating cash flow, and physical-PP&E CapEx.
2. Reuse existing annual-period, currency, availability, duplicate/restatement,
   and provenance logic; do not create a parallel IFRS provider framework.
3. Enforce `positive_expenditure` without `abs()` for IFRS CapEx.
4. Preserve exact missing-concept behavior, including the SAP CapEx negative
   fixture.
5. Keep all instant/share-capital/BVPS concepts outside the supported mapping.

### C — security-unit compatibility

**Required work**

1. Add the minimum typed evidence/predicate needed to affirm that filing per-share
   facts and quoted security units are compatible.
2. Support only affirmative ordinary-share / 1:1 cases in the initial slice.
3. Make ADR/ADS, unknown ratio, multi-class, or currency-mismatched quote
   comparisons explicitly unavailable while preserving supported issuer-level
   FCF outcomes.
4. Add NVO-style negative and 1:1 positive deterministic cases.

No ADR conversion may be added as a convenience correction.

### D — Golden Suite extension

1. Version the case/fixture set deliberately; do not rewrite existing Golden
   cases or historical fixtures.
2. Add only high-signal cases that prove behavior not already covered by adapter
   tests, including at least one US-GAAP `20-F` success, one IFRS duration-fact
   success, one exact-concept negative, and one security-unit negative.
3. Preserve deterministic `not_measured` strategy selection unless a separately
   authorized empirical run is used.
4. Run the canonical suite and record old-versus-new denominators and results.

A failure is reported,
not removed or retuned merely to maintain the aggregate target.

### E — documentation, full gate, and closeout

1. Update current provider support tables, financial conventions, strategy/user
   guides, and examples only to the verified implemented surface.
2. Retain explicit unsupported language for IFRS BVPS, ADR/ADS conversion,
   custom extensions, and unsupported concepts.
3. Run the complete repository quality-gate wrapper and canonical deterministic
   Golden Suite.
4. Reconcile Step 2.5A acceptance criteria and stop for final human approval.

No completion claim, commit, push, PR, merge, or Step 2.6 start is implied by a
green automated gate.

## 4. Anticipated code/test ownership

The exact file list must be confirmed at Gate A, but implementation should remain
within the existing boundaries, normally:

- SEC EDGAR financial-fact adapter and its existing submissions/Company Facts
  helpers;
- provider-neutral financial-fact/provenance models only where the approved
  snapshot or unit evidence cannot be represented today;
- deterministic evaluation fixtures/composition and focused provider, resolver,
  strategy, and Golden tests; and
- directly affected planning, architecture, mapping, evaluation, and user docs.

Do not add a generic provider registry, a parallel IFRS adapter hierarchy, a new
strategy, SQLite schema, migrations, external dependencies, or unrelated
refactors.

## 5. Acceptance criteria

- Reviewed evidence fragments are deterministic, minimal, sourced, dated,
  checksummed, and free of live-test dependencies.
- Exact ticker-to-CIK resolution remains required; multi-ticker CIKs retain
  issuer-level OCF and CapEx while per-share fields remain fail-closed.
- Existing exact US-GAAP duration facts accept approved foreign annual forms
  without broadening balance-sheet/instant forms.
- The four exact IFRS duration concepts map with correct units, sign, period,
  currency, availability, and provenance.
- Missing or ambiguous exact concepts remain unavailable.
- Every field in one analysis uses one immutable SEC snapshot.
- Latest-eligible-accession taxonomy selection and cross-regime rejection are
  proven at historical `as_of` boundaries.
- Per-share/quote outputs require affirmative security-unit compatibility;
  unknown or ADR/ADS shapes fail closed without erasing valid issuer-level facts.
- IFRS BVPS and preferred-zero inference remain unsupported.
- Existing `10-K` behavior and all approved financial formulas remain
  unchanged.
- Golden additions are versioned and existing case IDs/fixtures are not
  rewritten.
- No deterministic test makes a real SEC, quote-provider, or LLM call.
- Focused checks, the complete repository gate, and the canonical Golden
  Suite pass and are recorded honestly.

## 6. Deferred Phase B2 entry requirements

IFRS BVPS work may be proposed later only with authoritative evidence for:

- dimensional ordinary/common and preference share-capital facts;
- preferred-equity deduction semantics rather than absence-based zero inference;
- exact period-end denominator alignment;
- ordinary-share, ADR/ADS, and listing-unit ratios over time;
- filing and quote currency compatibility/conversion policy; and
- deterministic positive, absent, multi-class, dimensional, and restatement
  fixtures.

That proposal requires a new mapping review and explicit authorization. It is not
an implied continuation of this plan.
