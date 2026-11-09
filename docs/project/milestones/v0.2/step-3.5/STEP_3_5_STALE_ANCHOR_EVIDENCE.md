# Step 3.5 — Stale Anchor Evidence Record

Captured evidence behind the stale-anchor rule ([A.17](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#a17-stale-anchor-filing-and-the-anchor-rule-2026-11-09),
[Shared definitions §3](STEP_3_5_SHARED_DEFINITIONS.md#stale-anchor)): one real registrant whose newest annual report went
overdue and was never filed, and a check that the anchor rule leaves every other captured filing history as it was. The
rules are owned by Shared definitions; nothing here overrides them.

> **This document is not a test fixture and holds no executable expected data.** The tests read the captured documents
> under `investment_analysis_engine/evaluation/fixtures/sec_edgar/stale_anchor/` and state their own expected values.

## 1. At a glance

- **The filer:** WeWork Inc. (CIK 1813756). Its newest annual report is the 10-K for the fiscal year ended 2022-12-31,
  filed 2023-03-29. For the fiscal year ended 2023-12-31 it filed a notice of late filing (NT 10-K) on 2024-03-19, never
  filed the 10-K, and deregistered with a Form 15 (15-12G) on 2024-06-11.
- **Why it qualifies:** an NT 10-K is filed when an annual report will not be filed on time, and here the report was never
  filed. The registrant's anchor annual filing therefore stays the 2022 10-K at every later boundary, and the rule has to
  call it stale from the day after the next report was due, 2024-04-21, onward ([§3](#3-what-the-rule-gives)).
- **Anchor rule check:** no captured filing history of the 29 under `evaluation/fixtures/sec_edgar/` changes its anchor
  under the anchor rule, and in none do the original annual reports fail to come in fiscal-year order ([§4](#4-the-anchor-rule-against-the-captured-histories)).
- **What it does not show:** a deadline for any form but the 10-K. The captured filer is a 10-K filer, so the 20-F and
  40-F allowances rest on the instruments cited in [Shared definitions §3](STEP_3_5_SHARED_DEFINITIONS.md#stale-anchor)
  and on the tests of the rule's arithmetic.

## 2. The capture

Captured on 2026-11-09 from SEC EDGAR's public JSON, with the SEC identity the project's settings declare. The documents
are written with sorted keys and no insignificant whitespace; their content is as the SEC served it.

| File | Source | SHA-256 |
| :--- | :--- | :--- |
| `wework_submissions.json` | `https://data.sec.gov/submissions/CIK0001813756.json` | `fa13cd09de82a8277e0f5bc54359115f45d5ac6e1a248032be204fdccfc34241` |
| `wework_companyfacts.json` | `https://data.sec.gov/api/xbrl/companyfacts/CIK0001813756.json` | `87da4fdea64d919bc5f9a3d47589fcacd876fdccd5d8747905b674f90a71942c` |

The SEC now lists the registrant under the name "20230930-DK-Butterfly-1, Inc." with no ticker, so the tests reach it
through a ticker override (`WE`), as a user would.

The filings that matter, from the submissions document:

| Form | Filed | Fiscal year ended | Accession |
| :--- | :--- | :--- | :--- |
| 10-K | 2022-03-17 | 2021-12-31 | 0001813756-22-000003 |
| NT 10-K | 2023-03-17 | 2022-12-31 | 0001193125-23-073442 |
| 10-K | 2023-03-29 | 2022-12-31 | 0001813756-23-000016 |
| NT 10-K | 2024-03-19 | 2023-12-31 | 0001193125-24-070358 |
| 15-12G | 2024-06-11 | | 0001193125-24-159169 |

## 3. What the rule gives

The anchor is the 2023-03-29 10-K at every boundary from its acceptance on. Its next report was due by 2024-04-21: the
fiscal year-end 2022-12-31, plus one year, plus 7 days, plus 105 days.

| Boundary | Anchor | Next report due | Stale |
| :--- | :--- | :--- | :--- |
| 2024-04-21 | 10-K, fiscal year ended 2022-12-31 | 2024-04-21 | No |
| 2024-04-22 | 10-K, fiscal year ended 2022-12-31 | 2024-04-21 | Yes |
| 2024-06-01 | 10-K, fiscal year ended 2022-12-31 | 2024-04-21 | Yes |
| 2026-11-09 | 10-K, fiscal year ended 2022-12-31 | 2024-04-21 | Yes |

The registrant did file a notice on 2024-03-19. The rule does not read it: a notice of late filing extends the 10-K
deadline by 15 calendar days at most, and that extension is already in the 105 days. The registrant missed the extended
deadline as well, and never filed.

## 4. The anchor rule against the captured histories

For each of the 29 captured submissions documents under `investment_analysis_engine/evaluation/fixtures/sec_edgar/`
(including the paged ones) the anchor was computed under the old choice (the newest annual accession by acceptance time,
amendments included) and under the anchor rule, at the acceptance time of every annual filing in the history. An anchor
can change only at such a time.

- **No anchor differs.** In every captured history the newest annual filing is an original or an amendment of the newest
  fiscal year, so the two choices agree at every boundary.
- **Originals are in fiscal-year order.** In none of the 29 histories is an original annual report accepted before one
  for an earlier fiscal year, which the anchor rule rests on.
- **The tests that built an amendment-only history changed.** The synthetic issuers of
  `tests/data/test_sec_cover_listing.py` that held a 10-K/A and nothing else now hold the 10-K it amends first, because an
  amendment alone has no original to fix its fiscal year.

## 5. Not yet verified

- The fiscal-year order of original annual reports in the whole market. Twenty-nine histories were read.
- The 20-F and 40-F allowances against a captured foreign private issuer's late filing.
