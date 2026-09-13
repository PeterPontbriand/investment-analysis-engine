# Immediate Graham Price Comparison Repair — Contract and Review Plan

Defines the evidence and compatibility rules needed for safe Graham price comparisons.

Work-package order and status: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## Sequence and status

| Order | Scope | Local gate |
| :--- | :--- | :--- |
| R1 → R2 → R3 | Evidence; implementation; verification | Evidence incorporated into the correctness audit; no independent acceptance gate |

## 1. Defect and evidence

The reported `graham-number KO --details` output contains a positive Graham Number, a positive current quote, and USD currencies for both, yet says only `Price comparison: unavailable`.

Source inspection establishes the broken production composition:

- `src/data/instrument_profile.py` defines optional `security_unit_evidence`, but `compose_instrument_profile` populates only identity, instrument kind, and diagnostics.
- Both Graham Number and Graham Growth services require security-unit evidence when a profile exists and pass the profile's unset evidence into the comparison helper.
- `src/data/security_unit.py` correctly rejects missing evidence under the narrow ordinary-share 1:1 contract.
- `src/analysis/shared/financial_resolution.py` returns only a nullable percentage, losing the compatibility reason at the service boundary.
- `src/reporting/graham.py` renders that null value as generic unavailability, without explaining the share-unit requirement.

This is a production evidence-integration defect plus a reason-propagation defect. The supplied terminal output and local source inspection are evidence; no live reproduction was performed for this plan. The valid Graham calculation and quote must remain available when comparison cannot safely be established.

## 2. Required outcome and safety boundary

Restore the price relationship for supported ordinary-share securities when actual provider evidence establishes that the filing per-share unit and quoted unit match at 1:1. Carry the evidence through the normal production CLI composition, not only fixtures or direct service calls. For unsupported or unverified relationships, retain fail-closed comparison behavior and explain the specific reason.

Do not remove the compatibility guard, set `require_security_unit_evidence=False` as a workaround, omit an otherwise valid profile, infer 1:1 from ticker/name/currency/EQUITY alone, hardcode KO, or treat missing ADR/class information as affirmative ordinary-share evidence. Do not introduce ADR/ADS conversion, FX conversion, split normalization, multi-class aggregation, or new valuation mathematics. Preserve profile identity, financial provenance, override behavior, historical boundaries, and current-quote semantics.

The provider evidence mapping is a required design deliverable, not an assumption that existing provider payloads already suffice. Inventory available SEC/Yahoo evidence and the earlier security-unit design, establish source/field semantics and subject/share-class linkage, and freeze a narrow defensible predicate. Respect existing egress/cache/reliability boundaries. Any bounded live evidence reconnaissance must be separately identified from deterministic verification and must not mutate operational storage or add dependencies. If no defensible supported mapping can be established, return for review with the precise gap; do not declare the repair complete merely because the unavailable message improved.

Current descriptive identity or instrument-kind timestamps do not automatically establish historical share-unit compatibility. Define temporal applicability and reject unsupported historical or ambiguous relationships explicitly. Do not import benchmark fixture evidence into production.

## 3. Bounded implementation contract

1. Add the minimum typed provider/composition seam needed to obtain validated request-scoped `SecurityUnitEvidence` with source provenance and security identity linkage. Reuse the existing profile and compatibility types; do not build a registry or full durable profile repository.
2. Preserve the structured compatibility outcome through service execution and presentation, with stable reason categories and public wording. Reuse `SecurityUnitCompatibility` where sufficient. Keep the existing nullable percentage/public interfaces compatible unless an explicit reviewed additive change is required.
3. Cover both Graham Number and Graham Growth because they share the failing requirement. Inventory legacy/programmatic callers and preserve documented behavior; do not silently tighten or bypass other callers as incidental cleanup.
4. Keep deterministic comparison math in Python and preserve `docs/user/FINANCE_MATH.md` semantics and existing rounding. Presentation must consume calculated results rather than independently recalculate them.
5. Show a concise reason whenever comparison is unavailable, including missing share-unit evidence, unknown ratio, unsupported unit kind, non-unit ratio, multi-class ambiguity, currency mismatch, missing quote, and non-positive reference where applicable. Define deterministic reason precedence.
6. Details/diagnostics must expose the relevant sanitized evidence and compatibility decision. JSON must retain the existing percentage field and receive a reviewed compatible representation of status/reason/evidence; inspect schema/version conventions before changing it. Do not leak raw provider payloads.
7. Update affected README/usage/Graham/finance documentation only where needed to match verified behavior, including the existing small README audit correction in the same review. Do not normalize the defect into the intended contract or claim all equities support comparisons. Runtime documentation changes ship with implementation; this planning checkpoint changes project documents only.

Initial source scope: instrument profile/security-unit modules, relevant existing SEC/Yahoo provider boundaries, shared financial comparison helper, both Graham services, CLI composition, Graham reporting, and focused tests. Freeze exact file/interface scope and the provider mapping before production edits. Database migrations, Step 3.3A behavior, P2 persistence, unrelated documentation expansion, and other financial strategies are outside this repair.

## 4. Verification organization

Separate provider evidence, implementation and end-to-end verification. The
concrete provider/unit contract is in [R1 evidence](R1_EVIDENCE_AND_CONTRACT.md);
implementation and regression details are in [R2 evidence](R2_IMPLEMENTATION_AND_VERIFICATION.md).

## 5. Deterministic acceptance matrix

| Case | Required evidence |
| :--- | :--- |
| Ordinary-share success | Provider-shaped synthetic evidence traverses actual profile composition → each Graham service → CLI renderer; matching 1:1 units produce the expected percentage. A fixture that prebuilds a complete profile alone is insufficient. |
| Reported KO workflow | A reproducible fixture representing reviewed KO evidence exercises the default command and details rendering with positive value/quote and supported compatibility. Values are fixture inputs, not a current-market promise. Verify percentage from unrounded reference/quote under existing formula semantics. |
| Fail-closed boundaries | Missing evidence, unknown/non-unit ratio, ADR/ADS, multi-class ambiguity, currency mismatch, mismatched subject, provider failure, and unsupported temporal evidence suppress comparison with the correct explicit reason. No inferred 1:1 fallback. |
| Existing financial failures | Missing quote, non-positive Growth reference, invalid/unavailable calculation, and overridden inputs retain valid analytical results and existing statuses; no new arithmetic exceptions or NaN/Inf propagation. |
| Output contracts | Concise/details/diagnostics/JSON agree on comparison status; JSON remains valid and backwards compatible under reviewed conventions; identity, provenance, and available quote remain visible. |
| Integration/preservation | Cache hit/miss/bypass cases do not drop evidence; identity enrichment cannot itself suppress an otherwise affirmatively compatible comparison. Existing programmatic/legacy interfaces, unrelated strategies, security-unit tests, and Golden cases remain valid. |

Use synthetic fixtures, mocked providers/LLMs, and unique temporary storage; block real network calls in deterministic tests. No user database or raw operational captures become fixtures. Run the complete managed non-mutating gate before refactoring and at implementation acceptance:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

```bash
bash "$(git rev-parse --show-toplevel)/scripts/run-quality-gates.sh"
```

Record revision, date, lint/format/strict typing, test totals, coverage (at least 85% overall), and isolated artifact location. An optional bounded live smoke check may supplement but never replace deterministic proof; disclose its date and evidence limitations. This documentation-only checkpoint requires link, diff, sequencing, and approval-state verification, not a claimed implementation test pass.
