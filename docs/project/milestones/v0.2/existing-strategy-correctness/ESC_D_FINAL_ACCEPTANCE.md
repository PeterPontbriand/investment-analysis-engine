# ESC-D — Existing-analysis renewal final acceptance

Collects the final renewal evidence and limitations for the existing analysis methods on the
current revision, mirroring `ESC_C_FINAL_ACCEPTANCE.md`'s structure for the renewed review.

Local sequence and status: [companion plan](EXISTING_STRATEGY_CORRECTNESS_PLAN.md#sequence-and-status).
Renewal scope, sequencing, and per-slice evidence: [ESC-D renewal plan](ESC_D_RENEWAL_PLAN.md).

## Acceptance evidence

| Requirement | Reconciled evidence |
| :--- | :--- |
| Defect accounting | ESC-18 was corrected in the ledger: the branch it described (a `DataQualityError` reclassification in `src/data/cached_client.py`) was confirmed unreachable dead code both before and after P2-Profiles, so no real regression ever occurred; the harmless defensive fix already made was kept, and the dead-code discovery was escalated into a new **R3** work package rather than folded into this audit. ESC-19 (Graham Number's JSON failure reason was less specific than text modes for the same blocker) was found during ESC-D.2's live testing and repaired. No other new discrepancy was found across ESC-D.1-D.5. No known unresolved correctness defect is recorded. |
| Four-analysis coverage | Full seven-dimension audit-matrix re-run (Presentation, Data lifecycle, Time, Inputs and applicability, Financial claims, Composition, Public contracts) completed for Graham Number (ESC-D.2), Graham Growth (ESC-D.3), Momentum (ESC-D.4), and FCF/Earnings Growth (ESC-D.5), each on the current revision rather than reusing ESC-C's evidence unverified. ESC-D.1 separately verified the cross-cutting layer shared by all four (the `workspace/*` execution adapters, `--save-run`/Analysis Run persistence, replay, and the durable instrument-profile cache) preserves prior default-path behavior. |
| Complete gate | Ruff check and format check clean; strict mypy clean; **3,127 tests passed, 91% coverage**. Command: `bash "$(git rev-parse --show-toplevel)/scripts/run-quality-gates.sh"`. Artifacts: `.tmp/quality-runs/20260923221856-1973-4277/`. |
| Independent arithmetic | Recomputed independently of the production calculator for all four analyses using live, dated evidence: Graham Number's three-year-average EPS, BVPS, and `sqrt(22.5 × EPS × BVPS)` (ESC-D.2); Graham Growth's `EPS × (base_pe + growth_multiplier × g) × baseline_yield/current_yield` (ESC-D.3); Momentum's SMA/RSI/crossover against a constructed fixture via the real production analyzer (ESC-D.4, live network data was unusable for this at verification time — see limits below); FCF's `operating_cash_flow − normalized_capital_expenditures` and CAGR formula across both a FAIL and a PASS case (ESC-D.5). Every recomputation matched the production output exactly and matched `docs/user/FINANCE_MATH.md`'s documented formulas. |
| Representative live success | All four analyses were live-checked against an isolated disposable SQLite database (`.tmp/esc-d2-evidence/`, never the developer's real local database) on 2026-09-23 UTC: Graham Number and Graham Growth for KO (concise/details/diagnostics/JSON, success and failure cases); FCF for KO across FAIL, PASS (via a historical `--as-of` boundary), and INDETERMINATE outcomes. Momentum's live check exercised the failure path only (see limits below); its success path and new replay mechanism were verified through the real, unmodified production adapter and replay functions against a constructed fixture. |
| Historical refusal | Reproduced ESC-17's original MSFT `--as-of 2025-12-31` scenario on the current revision: EPS resolved (11.71 USD), BVPS correctly unavailable with the specific preferred-share-evidence explanation, exit 1, both text and JSON now reporting the identical specific reason (ESC-19's fix). Missing data was not converted to zero. |
| Compatibility and documentation | Graham presentation schema 5, Momentum 4, FCF schema 5 / result schema 3 — all unchanged from ESC-C's recorded values. `--save-run`, Analysis Run persistence, and replay (new since ESC-C) were verified additive: every default (non-`--save-run`) call site is byte-identical in sequence to the ESC-C-accepted baseline for all four analyses (ESC-D.1-D.5), and replay never recomputes a financial value it can instead read from stored evidence (proven for Momentum's `use_captured_spread`, ESC-D.4). No persistence migration or dependency change was required by this renewal. |

## Limits retained for acceptance

- Carried forward from ESC-C, still accurate and unchanged by this renewal: Yahoo quote retrieval time is known but an upstream exchange observation timestamp is not supplied; filing venue is historical evidence, not independently verified current listing metadata; preferred-share zero remains a guarded inference; historical adjusted-price observation filtering does not certify adjustment vintages or exchange-session publication knowledge; optional FCF consensus/market-capitalization metrics still lack approved production mappings.
- New to this renewal: at verification time (2026-09-23), live upstream historical price data had a genuine, reproducible cross-ticker data-quality rejection on the most recent trading day (non-finite OHLC for 2026-09-22 across every ticker tried). This correctly triggered the existing sanitized `historical_quality` failure path — itself valuable, dated, current-revision evidence that the guard works — but prevented a live, network-sourced success-path check for Momentum specifically. The success path and the new replay mechanism were instead verified against the real, unmodified production analyzer, adapter, and replay functions with a constructed fixture, per this project's own established convention for exactly this constraint (`ESC_A_DEFECT_LEDGER.md`'s ESC-06/12 reproduction recipe). This is a live-environment observation at the time of testing, not a code limitation, and does not reduce confidence in the verified calculation or replay correctness.
- The dead code identified while correcting ESC-18 (`src/data/cached_client.py`'s two unreachable `DataQualityError` branches) is deliberately not removed here; it is tracked as motivating evidence for the separate **R3** repository-wide dead code audit, scheduled before Step 3.5.

These are documented evidence/capability limits, not deferred known repairs. Live checks do not
certify universal upstream data accuracy or the absence of all future defects.

## Final acceptance

Final acceptance for ESC-D was granted by the project owner on 2026-09-23, clearing
`IMPLEMENTATION_PLAN.md` row 9 to "Complete and accepted" and unblocking row 10
(repository-wide dead code audit, R3), which is no longer required to wait on this renewal.
