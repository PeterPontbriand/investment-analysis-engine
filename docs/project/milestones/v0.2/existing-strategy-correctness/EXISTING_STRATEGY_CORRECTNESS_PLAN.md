# Existing Strategy Correctness — Audit, Repair, and Acceptance

**Status:** ESC-B reviewed and approved by the project owner on 2026-09-11 (Toronto), including the historical MSFT explanation follow-up. Implementation remains in the working tree based on pushed `cb1e9ef`. The [ESC-C acceptance packet](ESC_C_FINAL_ACCEPTANCE.md), [implementation record](ESC_B_IMPLEMENTATION_AND_REVIEW.md), [defect ledger](ESC_A_DEFECT_LEDGER.md) and [coverage matrix](ESC_A_COVERAGE_MATRIX.md) reconcile 2,054 passing tests / 89% coverage, all-four live checks, and the historical MSFT case. ESC-C final acceptance is approved on 2026-09-11 (Toronto); ESC-D renewal remains pending.

**Approval record:** Following review of the expanded planning documents, the project owner instructed: “Record approval and propose a docs-only checkpoint commit description.” Approval covers the four-analysis scope, defect accounting, execution/review structure, readiness deferral, and renewed acceptance before Step 3.5. After pushing checkpoint `8d7fba0`, the project owner authorized ESC-A. After reviewing C1–C6 and pushing `cb1e9ef50bcef5f549cdabba91c853629da78eed`, the project owner explicitly authorized ESC-B. The project owner subsequently approved ESC-C final existing-analysis acceptance on 2026-09-11 (Toronto), closing the current correctness acceptance gate. ESC-D renewal remains pending.

**Authority:** [Active milestone](../IMPLEMENTATION_PLAN.md). This work supersedes the Graham-only acceptance boundary. Complete it before resuming database readiness; no further strategy development may start while known correctness defects remain unresolved.

**ESC-B approval and continuation:** The project owner instructed, “ESC-B is now reviewed and approved. Proceed.” This closes ESC-B and authorizes ESC-C reconciliation and preparation of its final acceptance packet. ESC-C was subsequently explicitly approved; see the acceptance packet. Publication remains separate, and Step 3.3A may resume only at its existing planning gates. ESC-D approval is not implied.

**Branch:** `fix/existing-strategy-correctness`, renamed by the project owner. The prior Graham repair and README correction are checkpointed in `e8f4a95`. Preserve that history. Use focused commits by diagnosed defect, separate from planning commits and database-readiness implementation. No commit, push, PR, dependency change, migration against user data, or destructive operation is authorized by this documentation checkpoint.

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

## 4. Execution and review gates

| Stage | Deliverables and gate |
| :--- | :--- |
| ESC-A — Evidence and concrete repair contracts | Inventory the actual four pipelines and consumers; reproduce findings; establish a fresh managed baseline; populate the matrix/ledger; propose exact policy, interfaces, files and schema changes. Review the concrete contract before expanded production edits. This document alone does not select quote TTLs or approve changed financial assumptions. |
| ESC-B — Repairs and regressions | After contract approval, implement focused repairs and realistic regressions. Continue authorized work toward one final review; do not require a new approval for each routine file/test change. Surface material scope or policy changes before dependent implementation. Preserve unrelated behavior and record regressions caught during repair. |
| ESC-C — Final existing-analysis acceptance | Reconcile every matrix cell and ledger entry; perform independent arithmetic checks and dated representative live smoke checks; pass the full managed gate with at least 85% overall coverage. Present one review packet covering all four analyses. Explicit stakeholder acceptance is required; no unresolved known output-correctness defect or unverified required cell may be left to a backlog. |
| ESC-D — Pre-Step-3.5 renewal | After Step 3.3A, Step 3.4 and P2-Profiles, rerun affected lifecycle/composition checks and the complete managed gate on the actual proposed Step 3.5 starting revision. Review accumulated changes, new defects, output examples and freshness evidence. Explicit renewed acceptance is required before any Step 3.5 strategy implementation. |

The same complete non-mutating gate applies at baseline and acceptance:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

Record revision, date, commands, totals, coverage and isolated artifact paths. Use synthetic reduced fixtures that preserve observed structural complexity, including negative cases. Live checks supplement deterministic proof: document provider configuration without secrets, timing, command, result and limitations. If a required check is blocked, record the blocker and keep acceptance open; do not assert success or bypass a safeguard. Use isolated migrated test storage for lifecycle tests; existing-data migrations require separate approval.

One implementation owner maintains coherent changes. An optional independent Cline review should be bounded and read-only: inspect the contract, outputs, tests and source; report discrepancies without editing the checkout. It is useful additional scrutiny, not a substitute for acceptance, and is not automatically dispatched or a mandatory tool dependency.

## 5. Sequencing and preservation

**Existing-strategy audit/repair → ESC-C acceptance → Step 3.3A at its existing gates → Step 3.4 at its existing gates → P2-Profiles → ESC-D renewed acceptance → Step 3.5 → Step 3.6.**

ESC-C acceptance releases the database-readiness deferral; resume Step 3.3A contract planning at its existing gates, with production implementation still separately gated. Step 3.4's prior start authorization is retained with the revised deferral; it does not bypass the prerequisites. Step 3.5's existing plan approval does not waive ESC-D.

After readiness changes, rerun all four analysis regressions plus relevant cold-database/cache lifecycle tests. Carry the same regression obligation through workspace/profile changes. Newly discovered correctness defects in any existing analysis block further strategy development until repaired and reviewed, including defects discovered after ESC-C. Shared cache/profile/presentation changes must not invalidate the earlier acceptance silently.

Before closing ESC-C, publish the completed matrix/ledger, changed-contract and compatibility notes, fresh test/live evidence, remaining documented limitations, and a concise reviewer checklist. The policy and architecture references should change only when actual behavior/policies are approved and implemented; this checkpoint does not rewrite user-facing behavior as though repairs already exist.
