# Step 3.5 — Piotroski Evidence Record

Source evidence, a worked example and the arithmetic oracle behind the Piotroski F-Score
specification. Formulas and rules are owned by
[Strategy specifications §1](STEP_3_5_STRATEGY_SPECIFICATIONS.md#1-piotroski-f-score); nothing here
overrides them. Scope and status live in the
[contract](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status).

> **This document is not a test fixture and holds no executable expected data.** It records
> research observations used to design the specification and to choose fixtures. No test may take
> an expected value from it. Slice 3.5.3 re-fetches, captures and independently checks whatever it
> uses.

## 1. At a glance

- **What this is:** evidence gathered in September 2026, kept because it is costly to recreate.
- **What it shows:**
  - The balance-sheet, income and cash-flow concepts Piotroski needs are present and stable for two
    large filers.
  - A direct long-term-debt total equals its current and noncurrent parts for both.
  - Equity-issuance evidence is not reliably available in structured filings. This is why the
    dilution test uses share counts.
  - Income from continuing operations is not reported by Apple at all. This is why ROA uses net
    income, and why Beneish's TATA has a stated alternative.
- **What it does not show:** coverage across the market. Two filers were checked. The gaps are
  listed in [§3](#3-not-yet-verified).
- **How to use it:** as fixture and Golden-case source material for slices 3.5.1 and 3.5.3, after
  re-fetching and capturing the values. The accession numbers are quoted for that purpose.

## 2. Sources

1. Piotroski (2000), *Value Investing: The Use of Historical Financial Statement Information to
   Separate Winners from Losers*:
   <https://www.ivey.uwo.ca/media/3775523/value_investing_the_use_of_historical_financial_statement_information.pdf>.
   Variable definitions are on printed pp. 7–9, the Table 1 notes on p. 14 and the equity-offering
   footnote on p. 26.
2. SEC EDGAR XBRL `companyconcept` and `companyfacts` JSON endpoints at `data.sec.gov`, queried on
   2026-09-19.
3. Apple fiscal 2024 Form 10-K, accession `0000320193-24-000123`, financial statements and Note 10.
4. Microsoft fiscal 2024 annual report, cash-flow and equity statements.

**What the paper leaves open**

- Turnover: the method text divides sales by beginning-of-year assets; Table 1 says average assets.
- Income: "before extraordinary items", a category US GAAP no longer has.
- Equity issuance: not defined precisely. Other implementations disagree on whether employee
  issuance counts, usually without saying so.

## 3. Not yet verified

- Microsoft's sales, gross profit, current assets and current liabilities concepts.
- A filer with no debt at all, to exercise the "no reported debt" outcome.
- A filer whose comparative values were restated, to exercise the conflict rule. Apple's
  comparatives are identical across its fiscal 2022, 2023 and 2024 filings.
- A classified financial issuer (bank, insurer or REIT) and its SIC code.
- Filing acceptance timestamps for any value below. Retrieval time is not filing availability.
- Any IFRS filer.

## 4. Arithmetic oracle

Invented inputs that isolate each formula. They are not issuer data. Units are arbitrary and
consistent. Expected values are written as fractions so a test can check them without calling the
calculator.

**Base case: all nine pass, score 9 (complete)**

| Input | *t−2* | *t−1* | *t* |
| :--- | ---: | ---: | ---: |
| Total assets | 80 | 100 | 120 |
| Net income | — | 4 | 8 |
| CFO | — | — | 10 |
| Sales | — | 80 | 120 |
| Gross profit | — | 24 | 42 |
| Long-term debt | — | 20 | 18 |
| Current assets | — | 40 | 54 |
| Current liabilities | — | 20 | 24 |
| Split-adjusted shares | — | 100 | 100 |

| Test | Prior | Current | Outcome |
| :--- | ---: | ---: | :--- |
| 1 Positive ROA | — | 2/25 | pass |
| 2 Positive CFO | — | 1/10 | pass |
| 3 Improving ROA | 1/20 | 2/25 | pass |
| 4 Cash exceeds income | — | 10 > 8 | pass |
| 5 Falling leverage | 2/9 | 9/55 | pass |
| 6 Improving liquidity | 2 | 9/4 | pass |
| 7 No dilution | 100 | 100 | pass |
| 8 Improving margin | 3/10 | 7/20 | pass |
| 9 Improving turnover | 1 | 6/5 | pass |

**Variations on the base case**

| Change | Expected |
| :--- | :--- |
| Total assets at *t* = 200 | Still 9. Turnover on beginning assets rises 1 → 6/5; on average assets it would fall 8/9 → 4/5. A calculator using average assets fails this case. |
| Shares at *t* = 101 | Test 7 fails. Score 8, complete. |
| Total assets at *t−2* missing | Tests 3, 5 and 9 unavailable. Six available, six pass: "6 of 6", partial, never ranked. |
| Total assets at *t−2* and gross profit at *t* both missing | Five available. Score `unavailable`. |

**Equality case: score 3 (complete)**

Total assets 100 at all three dates; net income 10 and 10; CFO 10; sales 100 and 100; gross profit
30 and 30; long-term debt 20 and 20; current assets 40 and 40; current liabilities 20 and 20;
shares 100 and 100. Only tests 1, 2 and 7 pass. With long-term debt 0 and 0 instead, test 5 also
passes: score 4.

**All-fail case: score 0 (complete, a successful run)**

Total assets 100 at all three dates; net income −1 (*t−1*) and −2 (*t*); CFO −3; sales 100 and 90;
gross profit 30 and 18; long-term debt 10 and 20; current assets 40 and 30; current liabilities 20
and 20; shares 100 and 101.

**Also required:** a zero and a negative denominator for each ratio, a non-finite intermediate
value, a duplicated test, and shuffled input order.

## 5. Apple: recorded values and worked example

CIK 0000320193. Values in US dollars, read from the `data.sec.gov` endpoints on 2026-09-19. All
appear in the fiscal 2024 Form 10-K, accession `0000320193-24-000123`. The fiscal 2022 and 2023
values are identical in the fiscal 2022 (`0000320193-22-000108`) and fiscal 2023
(`0000320193-23-000106`) filings.

| Concept | FY2022 | FY2023 | FY2024 |
| :--- | ---: | ---: | ---: |
| `Assets` | 352,755,000,000 | 352,583,000,000 | 364,980,000,000 |
| `NetIncomeLoss` | 99,803,000,000 | 96,995,000,000 | 93,736,000,000 |
| `NetCashProvidedByUsedInOperatingActivities` | 122,151,000,000 | 110,543,000,000 | 118,254,000,000 |
| `RevenueFromContractWithCustomerExcludingAssessedTax` | 394,328,000,000 | 383,285,000,000 | 391,035,000,000 |
| `GrossProfit` | 170,782,000,000 | 169,148,000,000 | 180,683,000,000 |
| `AssetsCurrent` | 135,405,000,000 | 143,566,000,000 | 152,987,000,000 |
| `LiabilitiesCurrent` | 153,982,000,000 | 145,308,000,000 | 176,392,000,000 |
| `LongTermDebtCurrent` | 11,128,000,000 | 9,822,000,000 | 10,912,000,000 |
| `LongTermDebtNoncurrent` | 98,959,000,000 | 95,281,000,000 | 85,750,000,000 |
| `LongTermDebt` (direct total) | 110,087,000,000 | 105,103,000,000 | 96,662,000,000 |

**Findings**

- **Debt reconciles.** The direct total equals current plus noncurrent in all three years.
- **Gross profit is reported directly.** No derivation is needed for this filer.
- **No continuing-operations income.** `IncomeLossFromContinuingOperations` returned HTTP 404: the
  concept appears nowhere in Apple's filing history.
- **Issuance evidence is stale.**

  | Concept | Last nonzero entry |
  | :--- | :--- |
  | `ProceedsFromIssuanceOfCommonStock` | FY2021, 1,105,000,000, accession `0000320193-21-000105` |
  | `StockIssuedDuringPeriodSharesStockOptionsExercised` | FY2014 |
  | `StockIssuedDuringPeriodValueShareBasedCompensation` | FY2009 |
  | `StockIssuedDuringPeriodValueNewIssues`, `StockIssuedDuringPeriodSharesNewIssues` | Never used (HTTP 404) |

- **Shares fell while shares were issued.** The fiscal 2024 share roll-forward (Note 10) shows
  shares outstanding going from 15,550,061 thousand to 15,116,786 thousand, with 66,097 thousand
  shares issued net of employee tax withholding. A falling count does not show that nothing was
  issued.
- **Short-term borrowings are separate.** The balance sheet reports commercial paper apart from
  current and noncurrent term debt.
- **Debt issuance.** `ProceedsFromIssuanceOfLongTermDebt` is present and explicitly zero for fiscal
  2024. That is zero issuance, not a zero balance.

**Worked example, *t* = FY2024**

Computed from the table above under the current specification. Treat it as a Golden-case candidate
to confirm against captured fixtures in slice 3.5.3, not as an accepted expected value.

| Test | Prior | Current | Outcome |
| :--- | ---: | ---: | :--- |
| 1 Positive ROA | — | 0.2659 | pass |
| 2 Positive CFO | — | 0.3354 | pass |
| 3 Improving ROA | 0.2750 | 0.2659 | fail |
| 4 Cash exceeds income | — | 118,254 > 93,736 (millions) | pass |
| 5 Falling leverage | 0.2980 | 0.2694 | pass |
| 6 Improving liquidity | 0.9880 | 0.8673 | fail |
| 7 No dilution | 15,550,061 | 15,116,786 (thousands) | pass |
| 8 Improving margin | 0.4413 | 0.4621 | pass |
| 9 Improving turnover | 1.0865 | 1.1091 | pass |

Score: 7, complete.

## 6. Microsoft: recorded values

CIK 0000789019, read on 2026-09-19.

| Fiscal year end | `ProceedsFromIssuanceOfCommonStock` | `StockIssuedDuringPeriodSharesNewIssues` | Accession |
| :--- | ---: | ---: | :--- |
| 2023-06-30 | 1,866,000,000 | 37,000,000 | `0000950170-24-087843` |
| 2024-06-30 | 2,002,000,000 | 34,000,000 | `0000950170-24-087843` |
| 2025-06-30 | 2,056,000,000 | 31,000,000 | `0000950170-25-100235` |

- Issuance proceeds are reported every year, alongside repurchases. Under an issuance-proceeds
  test Microsoft would fail the dilution test every year on option and employee-plan proceeds.
- `LongTermDebt` equals `LongTermDebtCurrent` + `LongTermDebtNoncurrent` in every year checked. For
  fiscal 2024: 2,249,000,000 + 42,688,000,000 = 44,937,000,000.
- `Assets` and `NetIncomeLoss` are present and current.

## 7. How the evidence was gathered

- **2026-09-13:** the paper and the rendered Apple and Microsoft filings were read. The structured
  endpoints could not be reached, so no concept, context or unit was confirmed that day.
- **2026-09-19:** the structured endpoints were reachable. Every figure in §5 and §6 was read from
  a `companyconcept` or `companyfacts` response, not transcribed from a rendered filing. The share
  roll-forward figures in §5 are the exception: they come from the rendered Note 10.
- Nothing was captured to the repository. The values are a record of what was observed, not test
  fixtures; slice 3.5.3 re-fetches and captures what it uses.
