# Step 2.5A B1-B Exact IFRS Duration-Fact Review

Documents exact IFRS duration mappings, lineage and verification.

Local sequence and status: [companion plan](SEC_EDGAR_FPI_IFRS_SLICE_PLAN.md#sequence-and-status).

Evidence baseline: `6e9019e40df13277fac9353e53446da44d1b26c3`.

## 1. Outcome

| Project field | Accepted provider field |
| :--- | :--- |
| Diluted EPS | `ifrs-full:DilutedEarningsLossPerShare` |
| Diluted weighted-average shares | `ifrs-full:AdjustedWeightedAverageShares` |
| Operating cash flow | `ifrs-full:CashFlowsFromUsedInOperatingActivities` |
| Physical-PP&E capital expenditure | `ifrs-full:PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities` |

The implementation selects those concepts only when B1-A locks the snapshot to
`ifrs-full`. It reuses the existing annual-form, FY, duration, currency,
availability, duplicate/restatement, provenance, and reconciliation behavior.
Provider fields and fact identifiers retain the exact accepted IFRS concept.

IFRS capital expenditure uses the existing `positive_expenditure` convention:
a non-negative raw payment is preserved, while a negative raw value is rejected
without `abs()`. No broader concept is substituted or summed. IFRS instant
facts, BVPS, preferred-zero inference, and security-unit compatibility remain
unsupported.

## 2. Raw-to-normalized lineage review

The approved minimized NTR fixture proves all four exact concepts from one
`40-F` accession. Tests assert normalized values, exact provider fields,
provider fact identifiers, accession notes, fiscal year, and the CapEx sign
contract.

Negative boundaries prove that:

- negative raw IFRS CapEx is unavailable rather than made positive;
- SAP's broader combined asset-purchase concept is not accepted as physical-
  PP&E CapEx, while its exact IFRS operating cash flow remains available;
- IFRS mapping does not enable stockholders-equity or other instant/BVPS paths;
  and
- existing US-GAAP mappings and B1-A regime behavior remain covered by the
  complete regression suite.

No verification test makes a live SEC, quote-provider, or LLM call.

## 3. Verification

- Focused exact-IFRS mapping tests: 8 passed.
- Canonical PowerShell quality wrapper: passed.
- Complete Ruff: passed.
- Complete Ruff format check: all 228 files formatted.
- Complete strict mypy: passed for 183 source files.
- Complete pytest: 1,278 passed at 88% reported coverage.
- Isolated artifacts:
  `.tmp/quality-runs/20260901222208858-20088-5c11e6a5010d42d2a457d53e48b65e0f/`.

Dependencies and lock files were not changed.
