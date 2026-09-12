# Immediate Graham Price Comparison Repair — Contract and Review Plan

**Superseding acceptance scope:** The project owner expanded this repair into the [Existing Strategy Correctness Audit](../existing-strategy-correctness/EXISTING_STRATEGY_CORRECTNESS_PLAN.md). Graham R2/R3 final acceptance is reopened and folded into ESC-C; this historical repair record does not independently release database readiness. The branch is now `fix/existing-strategy-correctness`; prior branch/workflow statements below describe predecessor work.

**Status:** R1 accepted; R2 implementation and verification complete on 2026-09-10 (2,004 tests, 89% coverage, complete managed gate). Paused for final R2/R3 review. See [R2 implementation and verification](R2_IMPLEMENTATION_AND_VERIFICATION.md) for authorization, scope, evidence, and limitations.

**Priority and authority:** The [active milestone](../IMPLEMENTATION_PLAN.md) schedules this repair immediately before Step 3.3A, then Step 3.4 → P2-Profiles → Step 3.5 → Step 3.6. It is an immediate corrective work item, not a deferred issue or the full P2-Profiles implementation. Step 3.4's prior authorization remains recorded with its existing deferral.

**Branch workflow:** Implementation is on `fix/graham-price-comparison`, including the small README audit correction that exposed the defect. Preserve the shared-checkout commit and remaining working-tree changes for combined review. Database-readiness implementation stays separate. Use descriptive standard branch prefixes; do not use `codex/`. No new commit, push, or PR is authorized by this completion.

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

## 4. Execution and approval gates

| Stage | Deliverables | Review gate |
| :--- | :--- | :--- |
| R0 — Planning review | This bounded scope, priority, and intended acceptance criteria. | Accepted on 2026-09-09 with two caveats: descriptive standard branch prefixes and inclusion of the small README audit correction. Proceed to R1 design/reconnaissance; R2 implementation authorization is not implied. |
| R1 — Evidence and concrete contract | Provider/source mapping, compatibility and time policy, caller inventory, exact interfaces/files, reason precedence and JSON contract, existing-test mapping, fresh managed baseline and a deterministic regression reproducing normal CLI composition failure. | Design/evidence and baseline completed on 2026-09-09; R1 was accepted and R2 explicitly authorized. See the R1 companion and its subsequent lineage approval record. |
| R2 — Repair and verification | Production evidence integration plus structured failure reasons, both Graham methods, preservation tests, user-doc corrections, and complete managed gate. Executed as sequential sub-slices S0–S6 (see §4.1). | For this run, the execution clarification below authorizes completion toward final review. Final R2 acceptance requires the S6 full gate. Do not start readiness implementation as a side effect. |
| R3 — Acceptance and handoff | Reconcile all acceptance criteria, remaining limitations, branch/publication state, and current-work documents. | Explicit final acceptance closes repair; resume Step 3.3A at its existing planning/approval gate. |

Planning approval does not authorize user-database migrations, dependencies, commits, or PRs. If review combines R0/R1 authorization explicitly, record it accurately without skipping the concrete evidence contract or baseline before implementation.

### 4.1 R2 sub-slices (review organization)

**Execution clarification:** The S0–S6 distribution text was committed in the shared checkout while R2 implementation was already underway. After this conflict was surfaced, the user instructed continuation. For this execution, S0–S6 organize the final review; separate intermediate slice approvals are not claimed. R3 acceptance remains mandatory. This clarification supersedes the intermediate-stop requirements below for this run only.

R2 is decomposed into the following ordered sub-slices so that work can be distributed across multiple strong models under continuous stakeholder (or second-model) review. Each later slice assumes the preceding slices have been reviewed and accepted. Parallelism is limited: S1 and S2 may be prepared in parallel after S0; everything after S2 is strictly sequential. No sub-slice may expand the R1 allowlist, weaken fail-closed behavior, infer 1:1 units, introduce new dependencies, or mutate operational storage.

**S0 – Contract freeze & scaffolding (read-only + pure types)**  
- Re-state the approved R1 contracts in code comments / docstrings only.  
- Add the new typed shapes (`SecurityUnitRequest`, `SecurityUnitResolution`, `SecurityUnitProvenance`, `PriceComparison`, reader policy) to `src/data/security_unit.py` and the profile completion signature, with zero behavioral change.  
- Add the schema-4 shape skeleton (still unused).  
- Write the corresponding type-only / contract tests.  
- No production logic, no parser, no service changes.  
Gate: mypy + focused unit tests green; no existing test broken.

**S1 – Bounded filing-document reader**  
- Implement `src/data/sec_edgar/filing_document.py` (injectable text transport, strict SEC URL construction, size/timeout/document-count limits, no retries beyond the policy).  
- Synthetic fixture support only.  
- Unit tests that exercise the limits and rejection paths.  
Gate: reader tests pass; no network in CI; no other files touched.

**S2 – Pure mapping / Inline-XBRL parser**  
- Implement the pure functions in `src/data/sec_edgar/security_unit.py` for the single mapping `sec_domestic_single_common_class_v1`.  
- Handle the exact title forms, context joining, nested numerics, namespace resolution, debt-title recognition, and verification of existing numerical inputs.  
- Synthetic reduced Inline XBRL fixtures that capture the observed KO shapes and the required negative cases (multi-class, ADR, unknown title, mismatched CIK/symbol, etc.).  
- No profile or service integration yet.  
Gate: pure parser tests (positive + all fail-closed cases) pass; fixtures labeled synthetic.

**S3 – Evidence acquisition seam & profile completion**  
- Wire `SecurityUnitProvider` protocol, SEC adapter implementation (using the snapshot + reader), production provider delegation, and `complete_security_unit_profile`.  
- Preserve caller-supplied evidence; attach resolution + diagnostic; keep identity/kind untouched.  
- Tests that exercise the completion path with synthetic providers only.  
Gate: composition tests for the seam pass; legacy no-profile / supplied-profile behavior unchanged.

**S4 – Shared comparison result + Graham service integration**  
- Add `evaluate_price_comparison` / `PriceComparison` and keep the old `margin_of_safety` wrapper.  
- Make both Graham services complete the profile (once, after successful assembly) and populate both the legacy percentage and the new structured field.  
- Return the enriched profile on the analysis result.  
- Preserve all existing financial-failure and override semantics.  
Gate: service-level tests (both methods) show comparison only when the acquisition path succeeds; null + reason when it does not; no arithmetic regressions.

**S5 – CLI, reporting, schema-4, and presentation**  
- CLI handlers render the post-completion profile.  
- Reporting shows concise reasons, details/diagnostics expose sanitized evidence, JSON emits schema 4 with the additive `price_comparison` object while keeping the old percentage field identical.  
- Update only the documentation surfaces listed in the plan (including the small README audit correction).  
Gate: CLI / reporting tests (both methods, all presentation modes) match the acceptance matrix; schema assertions updated.

**S6 – End-to-end composition regressions + full gate**  
- Replace the characterization reproduction with positive production-composition tests that go through the real facade, SEC adapter, synthetic fetchers, profile completion, services, and renderers.  
- Cover the full required matrix (KO-shaped success, all fail-closed boundaries, cache lineage, four-document bound, legacy callers, mathematical percentage from unrounded values, etc.).  
- Run the complete managed quality gate; record results.  
Gate: full gate green; every acceptance-matrix row has deterministic proof; no permanent test that requires the old defect.

Distribution guidance: hand each sub-slice to a strong model together with the frozen R1 contract and the reviewed artifacts of all preceding slices. Require the model to restate the exact allowlist and safety boundaries before writing code. Insert a stakeholder review checkpoint after every sub-slice.

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

## 6. R1 handoff

[R1 Evidence and Concrete Contract](R1_EVIDENCE_AND_CONTRACT.md) freezes the proposed SEC filing reader/context mapping, request-scoped evidence completion after financial input resolution, additive typed comparison result, schema 4 proposal, exact file scope, and test matrix. These decisions were approved for R2; the subsequent source-lineage extension is recorded in the R1 companion. [Deterministic reproduction](reproduce_comparison.py) now runs the production-composition success regressions; the original defect characterization remains in Git history. The current planning branch and root README audit correction are preserved.

R2 authorization was granted; the execution clarification in §4.1 governs this run. Stop for final review before R3 acceptance or database-readiness implementation.
