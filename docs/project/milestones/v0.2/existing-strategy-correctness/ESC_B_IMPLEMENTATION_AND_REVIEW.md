# ESC-B — Implementation and final review

**Status:** ESC-B reviewed and approved by the project owner on 2026-09-11 (Toronto), including the historical MSFT follow-up. The [ESC-C acceptance packet](ESC_C_FINAL_ACCEPTANCE.md) reconciles the final evidence; ESC-C stakeholder acceptance was granted on 2026-09-11 (Toronto). Work is uncommitted on `fix/existing-strategy-correctness`, based on approved, pushed `cb1e9ef50bcef5f549cdabba91c853629da78eed`. No database-readiness implementation, dependency change, operational database migration, commit or publication is included.

**Authority:** [Correctness plan](EXISTING_STRATEGY_CORRECTNESS_PLAN.md). Review with the [defect ledger](ESC_A_DEFECT_LEDGER.md) and [coverage reconciliation](ESC_A_COVERAGE_MATRIX.md). The original ESC-A evidence remains a historical baseline, not a description of current output.

## Result and contract changes

- Graham quotes have a separate, finite 300-second original-response reuse policy. Unknown, future or expired response evidence cannot silently reuse a quote; a failed refresh does not fall back to the rejected value. A zero setting disables quote reuse. Annual-fact cache age remains independent. Retrieval time is no longer presented as an exchange observation time.
- Verified filing listing venue is retained with filing accession and availability, separately from current identity metadata. Detailed financial evidence distinguishes inference, derivation, provider observation, cache origin and user assumptions, including recursive component notes, currencies and units.
- Momentum requires two valid SMA pairs to report a crossover event. Supplied and fetched frames both undergo quality validation. Cache hits retain original retrieval and cache provenance, and CLI diagnostics retain the resolver trace without duplicating legacy trace projections. Existing SMA and simple-average RSI formulas are preserved.
- FCF explanations identify the selected total or per-share basis. Details expose component provenance and optional-metric reasons. An additional reproduced defect, ESC-13, is repaired: the execution boundary now controls annual-input selection as well as the result timestamp.
- Runtime failures produce sanitized, versioned JSON with explicit null results and nonzero exit status. Historical numeric-quality failures retain bounded field/date evidence. Parser errors retain exit 2; a calculated FCF FAIL remains a successful execution.

Presentation schema versions are Graham **5**, Momentum **4**, and FCF **5**. FCF canonical result **3** / method **2** remain unchanged. Additive typed evidence preserves existing direct interfaces. Legacy quote keys miss and refresh under the canonical `latest_provider_quote` basis; no SQL schema migration is needed.

## Verification

The complete managed gate runs Ruff checks, formatting checks, strict mypy, and deterministic pytest with coverage through:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

The final gate, including the historical MSFT follow-up, passed **2,054 tests / 89% coverage**, with clean Ruff checks (314 formatted files) and strict mypy (240 source/test files). Final artifacts: `.tmp/quality-runs/20260911203603410-25356-68728413f2ea436faafb0f16e9f15ef5/`. The earlier 2,044-test gate and `.tmp/investor-header-gate.txt` remain historical evidence for the preceding follow-up. Tests use isolated repository temporary directories and injected transports; they do not call live providers or modify operational databases.

Permanent new regression suites are `tests/data/test_quote_freshness.py`, `tests/reporting/test_input_provenance.py`, `tests/test_existing_strategy_output_contracts.py`, and `tests/test_existing_strategy_failure_output.py`. Existing analyzer, parser, repository, presenter, CLI, evaluation and orchestrator suites exercise the unchanged and extended contracts; the ledger maps findings to their specific files.

### Dated live checks and independent arithmetic

On **2026-09-11, 11:18:26–11:18:54 UTC**, all four analyses succeeded in both details and JSON modes against isolated migrated test storage. The harness invokes the same `src.cli` entry point as `financial-agents`, with SEC EDGAR financial facts, Yahoo market data, telemetry disabled, and no operational database reuse. Local ignored evidence: `.tmp/esc-a-evidence/live-20260911T111824Z/`.

| Analysis / arguments | Verified result |
| :--- | :--- |
| `graham-number KO` | Graham Number 21.14 USD; quote 87.83 USD; 315.43% above the screening ceiling. Filing venue: New York Stock Exchange. |
| `graham-growth KO --expected-growth 5 --aaa-yield 4.4` | Growth Value 49.15 USD; quote 87.83 USD; 78.70% above the reference. |
| `momentum KO` | 1,428 daily observations through September 10; latest Close 87.83 USD; 50/200 SMAs 86.41 / 78.16; RSI 36.11; no crossover event (0). |
| `fcf-growth KO` | Calculated FAIL; 2020–2025 span; latest FCF 5,296,000,000 USD; per-share FCF 1.23 USD. |

Independent arithmetic used retained inputs and plain sums/math, without calling production calculators as the oracle. Number: `sqrt(22.5 * ((2.47+2.46+3.04)/3) * (32169000000/(7040000000-2738000000))) = 21.14186862097603`. Growth: `((2.47+2.46+3.04)/3) * (8.5+2*5) * 4.4/4.4 = 49.14833333333333`. Both unrounded price relationships agree with JSON.

All six FCF and per-share annual derivations agree with retained components. Total FCF, per-share FCF and EPS CAGRs are respectively −9.381715561220638%, −9.339733479530066%, and 11.17422496891589%. A separately retrieved historical frame independently reproduces Momentum SMAs 86.4095997619629 / 78.15899032592773, RSI 36.10823101265321 and crossover 0. Local verification script: `.tmp/esc-a-evidence/verify_live_repair.py`; source frame remains ignored. These checks verify calculations from captured evidence, not universal provider accuracy.

### Regressions caught during implementation

The first live repair run exposed a cache integration mismatch between the new quote basis and the SQLite key. No-cache succeeded while cached Graham commands failed. Canonicalizing the quote request/result key repaired it; a permanent test now runs the actual Yahoo financial adapter through real isolated SQLite storage, checking a subsequent hit. The successful dated run above followed this repair.

The final presentation review also found duplicate Momentum diagnostics when both legacy and typed traces were supplied, and loss of known market observation time for legacy direct Graham presentations. Both have focused permanent regressions.

Subsequent stakeholder smoke testing exposed ESC-14: Typer's default root-help completion options offered shell-script generation and installation to investor users. The explicitly requested follow-up disables these options and replaces the generic CLI heading with a purpose-oriented description. All existing analysis commands and `evaluate` remain available. The help regression reproduced before the fix; additional tests reject both removed options with parser exit 2. The smoke guide now checks their absence.

## Verified absences and limits

- Yahoo's quote response does not retain an upstream exchange timestamp. “Market observation time not supplied” is accurate even for a freshly retrieved response; recent retrieval is not a guarantee of a recent trade.
- The selected SEC identity does not supply a verified current venue. Historical filing venue is displayed separately; it must not be promoted to current metadata.
- Preferred-share zero is the existing guarded inference with visible lineage, not a substituted missing value or a newly assumed reported zero.
- FCF consensus EPS and market-cap-dependent metrics remain explicitly unavailable where the current provider mapping supplies no supported evidence. No new mappings or financial assumptions are introduced.
- Momentum historical dates are provider observation labels. Full exchange-session timestamps and historical adjustment vintages are not retained. Supported historical filtering excludes labels after the requested boundary; it does not certify historical publication knowability. General cache clock drift remains an insufficient-evidence quality condition under the existing policy, not a verified freshness claim; quote future-response rejection is stricter and separate.
- The earlier September 11 live Momentum failure contained invalid provider OHLC and was correctly rejected. The later valid provider response enabled the successful run; no rows were silently filled or dropped to manufacture success.

Raw live captures are local ignored evidence, not committed fixtures. Permanent synthetic regressions preserve the relevant structures and failure conditions. Testing supports the documented cases and does not prove that every possible future defect is absent.

## Reviewer decision

The heading-first follow-up (ESC-16) removes warning-level console output for individual rejected quality candidates that can recover successfully. These decisions remain in debug logs, observers and retained resolution diagnostics; genuine failures still use the explicit error path. The regression reproduced before the change, and the final **2,044-test / 89%** gate includes heading-first CLI assertions plus unchanged failure/telemetry coverage. No additional live provider calls were required for this logging-only change.

### Investor-report follow-up

Following stakeholder review of live KO details, ESC-15 was explicitly authorized: make details an investor explanation across all four analyses, while retaining complete technical provenance in diagnostics and JSON. The report now explains calculations and assumptions with compact input rows and readable magnitudes; raw taxonomy/context identifiers, recursive lineage, retrieval records and identity diagnostics remain available in technical modes. Graham's BVPS basis is consistent across views. JSON versions and financial calculations are unchanged.

The first follow-up live run exposed repeated displayed share rows whose underlying provenance differed. Deduplicating only identical displayed rows fixes the investor view without discarding source records. A permanent regression now uses differing retained notes for the same displayed component. Subsequent isolated live checks verify the final reports; paths and gate totals below supersede earlier verification for this presentation follow-up.

The source documents and smoke expectations were updated to match the new mode boundary. Earlier statements in the original ESC-A contract about recursive evidence in details are superseded by this explicit stakeholder-approved follow-up; evidence remains available in diagnostics and JSON.

Final follow-up gate: **2,044 passed / 89% coverage**, clean Ruff and strict mypy; `.tmp/quality-runs/20260911191102273-35632-45cd5ad063a8421d8d4896fe04e29f37/`. All four details and JSON commands again exited 0 in isolated live checks on **2026-09-11, 22:50 UTC**, recorded under `.tmp/esc-a-evidence/live-20260911T225023Z/`. The KO Number details now show the calculation, consistent BVPS basis, qualified preferred-zero inference, unique displayed share rows and filing link. Current provider data differs from the earlier 11:18 snapshot; the same annual valuation inputs still produce 21.14 USD. No operational database was migrated or replaced.

The schema/compatibility changes, ledger dispositions, representative live results and coverage reconciliation were accepted at ESC-C on 2026-09-11 (Toronto). Database-readiness contract planning may resume at its existing gates; ESC-D renewal on the actual Step 3.5 starting revision remains mandatory after readiness, workspace and profile changes.

### Historical Graham failure explanation follow-up

Stakeholder review of smoke command 8 explicitly authorized investigation and repair of the investor-facing failure explanation. A read-only SEC Company Facts check on 2026-09-12 confirmed the MSFT evidence shape for the requested 2025-12-31 boundary: the 2025-07-30 annual filing reports fiscal-year-end stockholders' equity and direct common shares outstanding, but the payload supplies no preferred/preference concepts and no same-period issued-minus-treasury share components. This does not meet either supported preferred-zero inference pattern. The existing `test_generic_missing_preferred_tag_with_direct_common_shares_remains_unavailable` regression protects this refusal. No new inference or financial assumption was introduced.

The Number presenter now explains the unresolved component from retained typed resolver events in the opening, qualifies missing preferred-share data, and distinguishes an unrequested quote after input failure from an attempted quote failure. Details retain that opening, omit an inapplicable share-unit comparison explanation, and describe formula precision without claiming a failed calculation completed. Raw resolver messages remain in diagnostics/JSON; schemas, exit codes, and calculation behavior are unchanged. The smoke guide now states these historical failure expectations.

The pre-change managed baseline passed 2,044 tests with 89% coverage. Focused verification passed 82 tests, including new component-specific failure and quote-attempt regressions. Live diagnostics, details and JSON runs against isolated temporary storage reproduced the conservative MSFT failure (exit 1) and verified the revised text, original EPS availability, and subsequent cache reuse. Local ignored evidence: `.tmp/msft-evidence.json` and `.tmp/msft-live-20260912T003416Z/`. Operational storage was not used or migrated. The subsequent ESC-C acceptance includes this follow-up.

The final managed gate passed **2,054 tests / 89% coverage**, with clean Ruff, formatting and strict mypy checks. Artifacts: `.tmp/quality-runs/20260911203603410-25356-68728413f2ea436faafb0f16e9f15ef5/`. The full suite caught an initial layout regression for calculated not-applicable results; the new failure opening is now limited to missing calculation results, preserving the existing applicability status/reason layout.
