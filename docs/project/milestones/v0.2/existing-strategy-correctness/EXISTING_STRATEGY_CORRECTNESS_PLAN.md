# Existing Strategy Correctness — Audit, Repair, and Acceptance

Defines the audit coverage, repair boundaries and acceptance requirements for existing analyses.

Work-package order and status: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## Sequence and status

| Order | Scope | Local gate |
| :--- | :--- | :--- |
| ESC-A → ESC-B → ESC-C | Evidence/contracts; repairs; initial acceptance | Accepted |
| ESC-D | Refresh lifecycle/output evidence and full gate on proposed starting revision | Pending explicit renewed acceptance; cross-package placement is in the milestone table |

## 1. Scope and outcomes

Audit the four existing public analyses: Graham Number (`graham-number`), Graham Growth (`graham-growth`), Momentum (`momentum`), and FCF/Earnings Growth (`fcf-growth`). Graham's two methods remain distinct analyses within one strategy family; this work does not change the strategy architecture.

Trace evidence from provider adapters through cache, resolution, calculations, classification, service results, CLI/orchestrator composition, and all supported presentation modes. Find and fix every discovered output-correctness defect, including defects in underlying data or calculations that cause misleading output. Include undocumented defects discovered during the audit; do not limit investigation to the known Graham findings.

Completion means systematic documented coverage, no unresolved known correctness defects, independently checked calculations, and demonstrated agreement between outputs and their supporting evidence. It is not a claim that testing proves the absence of every possible defect. Legitimate data unavailability is acceptable only when its cause and wording are verified; it cannot be used to reclassify a reproducible defect as intended behavior.

Excluded: new strategies/algorithms, speculative architecture rewrites, database-readiness implementation, new persistence schemas, universal provider coverage, automatic currency/ADR/split conversions, and unrelated documentation cleanup. Necessary financial-policy changes must be made explicit and reviewed before implementation; preserve existing assumptions until that decision is approved.

## 2. Known findings and defect accounting

Maintain a ledger during investigation with: ID, affected analyses/modes, severity and impact, source revision, reproduction, expected contract, actual output, root cause, proposed policy/API/files, repair commit, regression and live evidence, and acceptance disposition. A linked issue is not closure. Every new discrepancy enters the ledger. An intentionally unavailable case needs supporting evidence and an approved disposition, not a silent waiver.

Initial entries (verified findings, not completed repairs):

| ID | Finding | Required resolution evidence |
| :--- | :--- | :--- |
| ESC-01 | A cached quote retrieved 13h51 before the pasted run was labelled current; financial-cache reuse defaults to unlimited. Exchange observation time is not retained. | Design quote-specific freshness independently from annual-fact age; define quote age, retrieval age, cache residence, historical boundaries, unknown timestamps, refresh/error behavior, configuration and headline wording. Prove expired/unknown evidence cannot silently imply a current-market comparison. |
| ESC-02 | Listing venue is absent from the selected identity although the inspected filing supplies exchange evidence. | Define source/time-aware metadata enrichment or display the filing exchange separately. Do not silently relabel historical registration evidence as verified current listing metadata. Test partial identity and provider disagreement. |
| ESC-03 | Generic unavailable/n/a/unspecified labels conflate missing evidence, inapplicable fields, and unpopulated metadata. | Inventory each occurrence in every mode; distinguish these states. Derived fields and point-in-time values need accurate labels, not fabricated timestamps or provider fields. |
| ESC-04 | Inferred preferred-share zero is rendered as derived; component notes and deeper lineage are omitted in details. | Expose inference versus observation and supporting assumptions/lineage. Verify zero guards and units across all analyses; missing inputs must never become zero by default. |
| ESC-05 | Original Graham fixtures omitted ordinary dimensioned equity disclosures; parsing a real filing without verifying its source values missed a production failure. | Retain the corrected regression and require representative provider-shaped composition tests and dated live checks for all four analyses. Record limits of fixtures and live evidence. |

The existing [Graham implementation record](../graham-comparison/R2_IMPLEMENTATION_AND_VERIFICATION.md) contains the comparison repair and follow-up evidence (2,004 tests, 89% reported coverage). That is historical evidence for the checkpoint, not the baseline or acceptance of this expanded audit. Graham R2/R3 final acceptance is reopened and folded into the broader final review.

## 3. Required audit matrix

For each analysis, enumerate actual flags, provider routes, outputs and programmatic consumers from source and documentation. Record applicable cells, actual test/evidence links, gaps, and justified non-applicability. Do not mechanically require unsupported features or use test count alone as evidence.

| Dimension | Required cases and assertions |
| :--- | :--- |
| Presentation | Concise, details, diagnostics, JSON; successful and unsuccessful results; consistent status, values, rounding, units, reasons, warnings, identity and provenance. Verify documented examples against dated actual behavior. |
| Data lifecycle | Cold isolated cache, hit, bypass, supported refresh, expired/stale/future entries, legacy metadata, missing/corrupt entries, and provider failure during refresh. Distinguish provider snapshots from immutable derived-input lineage. Do not reuse operational data as fixtures. |
| Time | Current and supported historical requests, timezone/date boundaries, availability versus observation versus retrieval, restatements, fiscal-period alignment, market sessions and quote versus historical close. Future/unavailable information cannot silently enter historical results. |
| Inputs and applicability | Defaults and supported overrides; zero, negative, missing, NaN/Inf, insufficient history, unknown currency/units, currency mismatch, unsupported instrument/provider/class, conflicting identity and share evidence. Confirm optional-data failure versus fatal required-input failure. |
| Financial claims | Recalculate from unrounded retained inputs using an independent expected-value oracle. Check classifications, boundary conditions, signs, denominator/basis, precision and limiting assumptions; never generate expected values by calling the production calculator under test. |
| Composition | Real adapters/facades/resolvers/services/presenters with injected provider-shaped fixtures; supported orchestration paths must preserve the same typed semantics. Mock transport, not the decision being verified. Block network/LLMs in deterministic tests. |
| Public contracts | Existing programmatic consumers, CLI exit status, JSON schema/version/null semantics, sanitized failures, provenance completeness and documentation. Review additive versus breaking changes explicitly. |

Analysis-specific coverage must include:

- **Graham Number:** annual diluted EPS averaging, BVPS equity/share definitions, inferred preferred zero, original source lineage, positive-input applicability, share-unit compatibility, current-quote freshness and price relationship.
- **Graham Growth:** selected EPS basis/provider routing, user-supplied growth and AAA yield, formula defaults/units, zero and negative growth/value semantics, nonpositive-reference comparison, and the same quote/security evidence boundaries.
- **Momentum:** historical adjusted-price basis, intervals/order/duplicates/gaps, SMA windows and insufficient history, crossover state versus event, trend/classification boundaries, and distinction between latest historical close and live quote. Preserve current formula semantics unless a diagnosed defect warrants an approved change.
- **FCF/Earnings Growth:** operating cash flow/CapEx sign and units, exact concept/taxonomy/form support, FCF definition, fiscal alignment and restatements, historical horizons and growth calculations, zero/negative denominators, classifications, forward assumptions and missing-component propagation.

Audit all uses of unavailable, N/A, unspecified, unknown, null, zero and inferred values. A text search is an inventory aid; source-to-output tracing is the proof. Retained filing dates can legitimately be identical across prior-year comparative observations; precision and dates must be explained, not guessed.

## 4. Verification and review requirements

Use a coverage matrix and defect ledger spanning every supported consumer and
presentation mode. Repair contracts must define the exact policy, interfaces,
files and schema effects before production changes. Material scope or financial
policy changes need review.

Acceptance evidence includes independent arithmetic, realistic regressions,
dated representative live checks, and the complete managed gate with at least
85% coverage. Every required cell and known correctness defect must have a
verified disposition. Renewal reviews accumulated changes, lifecycle behavior,
output examples and freshness on the actual proposed starting revision.

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

Record revision, commands, results and isolated artifact paths. Synthetic tests
remain offline; live checks supplement them without secrets. Use disposable
storage for lifecycle tests. An independent read-only review is optional.
