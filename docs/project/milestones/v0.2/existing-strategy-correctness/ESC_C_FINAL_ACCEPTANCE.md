# ESC-C — Final existing-analysis acceptance

**Status:** ESC-C final existing-analysis acceptance approved by the project owner on 2026-09-11 (Toronto), following ESC-B approval. The project owner explicitly instructed: “ESC-C final existing-analysis acceptance is approved. Record and provide draft commit message, PR Title, PR Description, and PR comment.” Approval accepts the reviewed four-analysis implementation, ESC-01–17 dispositions, evidence and documented limits. Database-readiness planning may resume at its existing gates; implementation and publication are not started by this record.

**Review target:** The uncommitted working tree on `fix/existing-strategy-correctness`, based on `cb1e9ef50bcef5f549cdabba91c853629da78eed`, including the approved historical MSFT follow-up. No production/test changes followed the final gate; this reconciliation updates planning records only. Publication remains separate.

**Authority:** [Execution and review gates](EXISTING_STRATEGY_CORRECTNESS_PLAN.md#4-execution-and-review-gates). Supporting records: [implementation and verification](ESC_B_IMPLEMENTATION_AND_REVIEW.md), [defect ledger](ESC_A_DEFECT_LEDGER.md), and [coverage matrix](ESC_A_COVERAGE_MATRIX.md).

## Acceptance evidence

| Requirement | Reconciled evidence |
| :--- | :--- |
| Defect accounting | ESC-01–17 have implemented dispositions and permanent regression anchors. ESC-17 records the final MSFT follow-up rather than leaving it only in narrative review notes. No known unresolved correctness defect is recorded. |
| Four-analysis coverage | Matrix reconciliation covers text/JSON, cache lifecycle, supported time boundaries, invalid/missing inputs, arithmetic, source/composition and public compatibility for Number, Growth, Momentum and FCF. Original ESC-A requirements remain historical; the closing reconciliation supplies their current dispositions. |
| Complete gate | Ruff check and format check clean; strict mypy clean; **2,054 tests passed, 89% coverage**. Command: `& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')`. Artifacts: `.tmp/quality-runs/20260911203603410-25356-68728413f2ea436faafb0f16e9f15ef5/`. This is the already completed gate on the approved production/test state, not a newly claimed run. |
| Independent arithmetic | The implementation record documents recomputation from unrounded captured inputs for Number, Growth, Momentum SMAs/RSI/crossover and annual FCF/per-share/EPS growth. Permanent boundary tests complement the dated live oracles. |
| Representative live success | All four details and JSON routes succeeded against isolated storage on 2026-09-11 at 11:18 UTC and again at 22:50 UTC. Latest all-four evidence: `.tmp/esc-a-evidence/live-20260911T225023Z/`. Market prices are dated observations, not fixed expected values. |
| Historical refusal | MSFT at 2025-12-31 resolved eligible EPS but could not establish preferred-share evidence under the supported SEC inference rules. Live details/diagnostics/JSON verified exit 1 and the revised explanation; `.tmp/msft-live-20260912T003416Z/` and `.tmp/msft-evidence.json`. Missing data was not converted to zero. |
| Compatibility and documentation | Graham presentation schema 5, Momentum 4, FCF 5; FCF canonical result 3/method 2 unchanged. Existing direct/tool/CLI suites pass. User documentation and smoke expectations reflect investor-readable details and full technical diagnostics/JSON. No persistence migration or dependency change is required. |

## Limits retained for acceptance

- Yahoo quote retrieval time is known; an upstream exchange observation timestamp is not supplied. Current quote adapters cannot provide historical quotes.
- Filing venue is historical evidence, not independently verified current listing metadata.
- Preferred-share zero remains a guarded inference. The MSFT direct-common/absent-preferred shape remains unavailable.
- Historical adjusted-price observation filtering does not certify adjustment vintages or exchange-session publication knowledge. General cache clock-drift evidence remains distinct from strict quote freshness.
- Optional FCF consensus and market-cap metrics lack approved production mappings. No new mapping, conversion or financial assumption is implied.

These are documented evidence/capability limits, not deferred known repairs. Live checks do not certify universal upstream data accuracy or the absence of all future defects.

## Decision and next handoff

**Decision:** ESC-C accepted. The changed contracts, ESC-01–17 dispositions, matrix reconciliation, representative outputs and evidence limits are approved. The existing-analysis readiness deferral is released.

The next authorized handoff is to resume [Step 3.3A](../step-3.3a/STEP_3_3A_CONTRACT_AND_SLICE_PLAN.md) at its existing contract/planning gate; production implementation still requires that plan's approval. Then preserve Step 3.4 → P2-Profiles → ESC-D renewed acceptance → Step 3.5 → Step 3.6. Readiness/workspace/profile changes must retain the four-analysis regressions. This packet authorizes no commit, push, PR or migration against user data.
