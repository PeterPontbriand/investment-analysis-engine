# Step 3.5 — Slice 3.5.3b2 Input Evidence Record

Captured evidence behind the year-end discovery and the share-count series of
[slice 3.5.3b2](STEP_3_5_3_SLICE_PLAN.md#353b2--year-end-discovery-share-count-series-and-captured-evidence): which
completed-annual fields give the start date of a fiscal year, how a common share count is found at a named year-end, how
often the counts of two year-ends come from one filing, and the inputs of Apple's Piotroski worked example as now
captured. The rules are owned by [Shared definitions §3 and §4](STEP_3_5_SHARED_DEFINITIONS.md#period-alignment); the
decisions drawn from this record are D1 to D3 of [A.6](STEP_3_5_3_SLICE_PLAN.md#a6-decided-under-delegation-during-353b2).
Nothing here overrides either.

> **This document is not a test fixture and holds no executable expected data.** It records research observations used to
> choose the field list and the share-count design. The tests read the trimmed documents under
> `investment_analysis_engine/evaluation/fixtures/sec_edgar/` and state their own expected values.

## 1. At a glance

- **Field list: net income, sales and operating cash flow.** On 12 issuers and every captured fiscal year, the start
  dates of all three agree with each other and with four other completed-annual fields ([§4](#4-start-dates-by-field)).
- **Monster tags no net income** and still gets both earlier year-ends from the other two fields.
- **Year-ends found** for all 12 issuers: the 52- and 53-week years of Deere, Walmart and Apple give 364- to 371-day
  years, inside the 335 to 395 day bounds.
- **Share counts: one path per year-end.** Nine issuers have a balance-sheet count at both *t* and *t−1*; all nine are on
  the direct path. Eight of the nine have both counts from one filing (89%). Deere's *t−1* count is from its previous
  annual report ([§5](#5-share-counts-at-the-last-two-year-ends)).
- **Three issuers have no count at *t*:** SAP and Walmart tag none at any year-end; Nutrien tags its IFRS count to
  2024-12-31 and not at 2025-12-31.
- **Apple's inputs match the September record** to the dollar, and its share counts to the thousand
  ([§6](#6-apples-inputs-as-captured)).
- **What it does not show:** coverage across the market. Twelve issuers were read ([§7](#7-not-yet-verified)).

## 2. Sources

1. SEC EDGAR Company Facts and submissions for the 11 regression issuers, as already committed under
   `investment_analysis_engine/evaluation/fixtures/sec_edgar/instant_facts/` and `annual_facts/`
   ([the mapping evidence](STEP_3_5_1_MAPPING_EVIDENCE.md#51-the-regression-issuer-set) lists their accessions).
2. SEC EDGAR Company Facts (`data.sec.gov/api/xbrl/companyfacts/`) and submissions (`data.sec.gov/submissions/`) for Apple
   (CIK 320193), requested on 2026-10-30 and kept under the ignored `.tmp/` folder. The committed copies are trimmed to
   three annual filings and to the concepts the year-end discovery, the share-count series and the Piotroski inputs read.
3. The [Piotroski evidence record](STEP_3_5_PIOTROSKI_EVIDENCE.md#5-apple-recorded-values-and-worked-example), read on
   2026-09-19, for the comparison of [§6](#6-apples-inputs-as-captured).

Apple is captured as of a boundary after its fiscal 2024 annual report (`0000320193-24-000123`, accepted
2024-11-01): only that filing and the two before it are kept, and the tests use the boundary 2024-11-15.

## 3. The issuers

| Issuer | Ticker | Anchor accession (form) | *t* | *t−1* | *t−2* |
| :--- | :--- | :--- | :--- | :--- | :--- |
| JPMorgan Chase | JPM | `0001628280-26-008131` (10-K) | 2025-12-31 | 2024-12-31 | 2023-12-31 |
| Prologis | PLD | `0001193125-26-051453` (10-K) | 2025-12-31 | 2024-12-31 | 2023-12-31 |
| Duke Energy | DUK | `0001326160-26-000014` (10-K) | 2025-12-31 | 2024-12-31 | 2023-12-31 |
| Deere | DE | `0001104659-25-122321` (10-K) | 2025-11-02 | 2024-10-27 | 2023-10-29 |
| SAP | SAP | `0001104659-26-020058` (20-F) | 2025-12-31 | 2024-12-31 | 2023-12-31 |
| Nutrien | NTR | `0001193125-26-081326` (40-F) | 2025-12-31 | 2024-12-31 | 2023-12-31 |
| Walmart | WMT | `0000104169-26-000055` (10-K) | 2026-01-31 | 2025-01-31 | 2024-01-31 |
| Moderna | MRNA | `0001682852-26-000033` (10-K) | 2025-12-31 | 2024-12-31 | 2023-12-31 |
| Monster Beverage | MNST | `0001104659-26-020831` (10-K) | 2025-12-31 | 2024-12-31 | 2023-12-31 |
| Alphabet | GOOGL | `0001652044-26-000018` (10-K) | 2025-12-31 | 2024-12-31 | 2023-12-31 |
| Honeywell | HON | `0000773840-26-000013` (10-K) | 2025-12-31 | 2024-12-31 | 2023-12-31 |
| Apple (boundary 2024-11-15) | AAPL | `0000320193-24-000123` (10-K) | 2024-09-28 | 2023-09-30 | 2022-09-24 |

The year-ends *t−1* and *t−2* are those the function finds; each is the day before the start of the period that follows
it ([§4](#4-start-dates-by-field)). The IFRS filer is SAP. Nutrien, the other IFRS filer, is in the set, so no further
capture was needed; the IFRS direct path is shown on Nutrien in [§5](#5-share-counts-at-the-last-two-year-ends).

## 4. Start dates by field

The start date of the completed annual period that ends at *t* and at *t−1*, for each field the adapter serves as a
completed-annual series. A dash is a field the issuer does not tag as a completed-annual amount (a bank has no gross
profit or operating income; Deere has no pretax income in the captured concepts).

| Issuer | Year | Net income | Sales | Operating cash flow | Gross profit | Tax | Pretax | Operating income |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| JPM | *t* | 2025-01-01 | 2025-01-01 | 2025-01-01 | – | 2025-01-01 | 2025-01-01 | – |
| JPM | *t−1* | 2024-01-01 | 2024-01-01 | 2024-01-01 | – | 2024-01-01 | 2024-01-01 | – |
| PLD | *t* | 2025-01-01 | 2025-01-01 | 2025-01-01 | – | 2025-01-01 | 2025-01-01 | 2025-01-01 |
| PLD | *t−1* | 2024-01-01 | 2024-01-01 | 2024-01-01 | – | 2024-01-01 | 2024-01-01 | 2024-01-01 |
| DUK | *t* | 2025-01-01 | 2025-01-01 | 2025-01-01 | – | 2025-01-01 | 2025-01-01 | 2025-01-01 |
| DUK | *t−1* | 2024-01-01 | 2024-01-01 | 2024-01-01 | – | 2024-01-01 | 2024-01-01 | 2024-01-01 |
| DE | *t* | 2024-10-28 | 2024-10-28 | 2024-10-28 | – | 2024-10-28 | – | – |
| DE | *t−1* | 2023-10-30 | 2023-10-30 | 2023-10-30 | – | 2023-10-30 | – | 2023-10-30 |
| SAP | *t* | 2025-01-01 | 2025-01-01 | 2025-01-01 | 2025-01-01 | 2025-01-01 | 2025-01-01 | 2025-01-01 |
| SAP | *t−1* | 2024-01-01 | 2024-01-01 | 2024-01-01 | 2024-01-01 | 2024-01-01 | 2024-01-01 | 2024-01-01 |
| NTR | *t* | 2025-01-01 | 2025-01-01 | 2025-01-01 | 2025-01-01 | 2025-01-01 | 2025-01-01 | 2025-01-01 |
| NTR | *t−1* | 2024-01-01 | 2024-01-01 | 2024-01-01 | 2024-01-01 | 2024-01-01 | 2024-01-01 | 2024-01-01 |
| WMT | *t* | 2025-02-01 | 2025-02-01 | 2025-02-01 | – | 2025-02-01 | 2025-02-01 | 2025-02-01 |
| WMT | *t−1* | 2024-02-01 | 2024-02-01 | 2024-02-01 | – | 2024-02-01 | 2024-02-01 | 2024-02-01 |
| MRNA | *t* | 2025-01-01 | 2025-01-01 | 2025-01-01 | – | 2025-01-01 | 2025-01-01 | 2025-01-01 |
| MRNA | *t−1* | 2024-01-01 | 2024-01-01 | 2024-01-01 | – | 2024-01-01 | 2024-01-01 | 2024-01-01 |
| **MNST** | *t* | **–** | 2025-01-01 | 2025-01-01 | 2025-01-01 | 2025-01-01 | 2025-01-01 | 2025-01-01 |
| **MNST** | *t−1* | **–** | 2024-01-01 | 2024-01-01 | 2024-01-01 | 2024-01-01 | 2024-01-01 | 2024-01-01 |
| GOOGL | *t* | 2025-01-01 | 2025-01-01 | 2025-01-01 | – | 2025-01-01 | 2025-01-01 | 2025-01-01 |
| GOOGL | *t−1* | 2024-01-01 | 2024-01-01 | 2024-01-01 | – | 2024-01-01 | 2024-01-01 | 2024-01-01 |
| HON | *t* | 2025-01-01 | 2025-01-01 | 2025-01-01 | – | 2025-01-01 | 2025-01-01 | 2025-01-01 |
| HON | *t−1* | 2024-01-01 | 2024-01-01 | 2024-01-01 | – | 2024-01-01 | 2024-01-01 | 2024-01-01 |
| AAPL | *t* | 2023-10-01 | 2023-10-01 | 2023-10-01 | 2023-10-01 | 2023-10-01 | 2023-10-01 | 2023-10-01 |
| AAPL | *t−1* | 2022-09-25 | 2022-09-25 | 2022-09-25 | 2022-09-25 | 2022-09-25 | 2022-09-25 | 2022-09-25 |

- **No disagreement.** Wherever two fields report a year, they give the same start date, across every version of the
  observation in the captured filings. No field disagrees with the others on any issuer.
- **Presence.** Sales and operating cash flow are present for all 12 issuers and both years. Net income is present for 11;
  Monster tags none. Gross profit and operating income are present for only some issuers.
- **The fiscal calendars.** Deere's years end on the Sunday nearest 31 October (2024-10-27, 2025-11-02), Walmart's on 31
  January, Apple's on the last Saturday of September. The longest year found is Apple's fiscal 2023, from 2022-09-25 to
  2023-09-30, which is 371 days. The derived year-end lies 335 to 395 days before the later one in every case.
- **Decision D1:** the list is net income, sales and operating cash flow, in that order. Sales and operating cash flow
  alone would already give every captured issuer a start date, but two fields are the least that lets a disagreement
  between them be seen, and a third keeps the year-end available when one field is not tagged.

## 5. Share counts at the last two year-ends

The common share count at the named year-ends, found by the series the slice adds, with the accession of the one filing
each count came from and its path. A count is shares.

| Issuer | Count at *t* | Filing at *t* | Count at *t−1* | Filing at *t−1* | Same filing | Path |
| :--- | ---: | :--- | ---: | :--- | :--- | :--- |
| JPM | 2,696,200,000 | `0001628280-26-008131` | 2,797,600,000 | `0001628280-26-008131` | yes | direct, direct |
| PLD | 929,153,000 | `0001193125-26-051453` | 926,283,000 | `0001193125-26-051453` | yes | direct, direct |
| DUK | 778,000,000 | `0001326160-26-000014` | 776,000,000 | `0001326160-26-000014` | yes | direct, direct |
| DE | 270,400,000 | `0001104659-25-122321` | 271,800,000 | `0001558370-24-016169` | **no** | direct, direct |
| MRNA | 394,000,000 | `0001682852-26-000033` | 386,000,000 | `0001682852-26-000033` | yes | direct, direct |
| MNST | 978,113,000 | `0001104659-26-020831` | 973,079,000 | `0001104659-26-020831` | yes | direct, direct |
| GOOGL | 12,088,000,000 | `0001652044-26-000018` | 12,211,000,000 | `0001652044-26-000018` | yes | direct, direct |
| HON | 635,300,000 | `0000773840-26-000013` | 649,800,000 | `0000773840-26-000013` | yes | direct, direct |
| AAPL | 15,116,786,000 | `0000320193-24-000123` | 15,550,061,000 | `0000320193-24-000123` | yes | direct, direct |
| NTR | none | | 491,025,446 | `0001193125-25-041502` | | (IFRS direct) |
| SAP | none | | none | | | |
| WMT | none | | none | | | |

- **The measurement.** Nine issuers have a count at both *t* and *t−1*. Eight of the nine, 89%, have both from one
  filing, against the threshold of three-quarters ([A.5, U3](STEP_3_5_3_SLICE_PLAN.md#a5-decisions-u1-to-u6-2026-10-29)).
  All nine pairs are on the direct path, so no issuer's two counts come by different paths. The threshold is not crossed.
- **Deere** is the one pair from two filings. Its fiscal 2025 annual report does not repeat the fiscal 2024 count, so the
  latest filing to report it is the fiscal 2024 report. The dilution test is unavailable for it (`ambiguous_fact`), as
  [Q5](STEP_3_5_3_SLICE_PLAN.md#a1-decisions-q1-to-q17-2026-10-29) states.
- **Apple's pair** is from the fiscal 2024 report. Its count at the year-end before *t−1*, 15,943,425,000 at 2022-09-24,
  is from the fiscal 2023 report; the dilution test does not read it.
- **Nutrien** tags `ifrs-full:NumberOfSharesOutstanding` at 2023-12-31 (494,551,730) and 2024-12-31 (491,025,446), both
  in `0001193125-25-041502`, and not at 2025-12-31, so the IFRS direct path works and the latest year-end has no count.
- **SAP and Walmart** tag no balance-sheet count at any year-end. SAP's `ifrs-full:NumberOfSharesIssued` is not a count of
  shares outstanding and there is no IFRS treasury share count, so issued less treasury is not offered under IFRS.
- **Issued less treasury** is not the chosen path for any issuer here, because every one that has a count tags it
  directly. It agrees with the direct count for Monster (1,132,906,000 less 154,793,000 is 978,113,000) and differs for
  JPMorgan (2,696,272,576 against 2,696,200,000), which is why the direct count is tried first and the paths are never
  mixed in one comparison.
- **Multi-class.** Company Facts hold one non-dimensional count per filing and date. Alphabet's is one combined count for
  its three classes. Two different values for one filing and date are refused as a conflict, and the derived path is not
  tried after one.

## 6. Apple's inputs as captured

The inputs of the worked example in the [Piotroski evidence record](STEP_3_5_PIOTROSKI_EVIDENCE.md#5-apple-recorded-values-and-worked-example),
read from the committed fixtures through the assembly functions, with the boundary 2024-11-15. Dollars, except the count.
No score is computed here.

| Input | 2022-09-24 | 2023-09-30 | 2024-09-28 |
| :--- | ---: | ---: | ---: |
| Total assets | 352,755,000,000 | 352,583,000,000 | 364,980,000,000 |
| Net income | 99,803,000,000 | 96,995,000,000 | 93,736,000,000 |
| Operating cash flow | 122,151,000,000 | 110,543,000,000 | 118,254,000,000 |
| Sales | 394,328,000,000 | 383,285,000,000 | 391,035,000,000 |
| Gross profit | 170,782,000,000 | 169,148,000,000 | 180,683,000,000 |
| Current assets | 135,405,000,000 | 143,566,000,000 | 152,987,000,000 |
| Current liabilities | 153,982,000,000 | 145,308,000,000 | 176,392,000,000 |
| Current portion of long-term debt | 11,128,000,000 | 9,822,000,000 | 10,912,000,000 |
| Noncurrent long-term debt | 98,959,000,000 | 95,281,000,000 | 85,750,000,000 |
| Long-term debt, direct total | 110,087,000,000 | 105,103,000,000 | 96,662,000,000 |
| Common shares outstanding (shares) | 15,943,425,000 | 15,550,061,000 | 15,116,786,000 |

- **Difference from the September record: none in a value.** Every figure of the record's table is the same, and the
  record's share counts in thousands (15,550,061 and 15,116,786) are the same counts.
- **Where a value now comes from.** The balance-sheet values at 2022-09-24 and 2023-09-30 are taken from the report that
  repeats them as comparatives (the fiscal 2023 and fiscal 2024 reports), because the series uses the latest filing that
  reports a year-end. The September record read them from the fiscal 2022 and 2023 reports. Their values are equal.
- **Short-term borrowings** (commercial paper) are 9,982,000,000, 5,985,000,000 and 9,967,000,000, tagged apart from the
  term debt, and finance lease liabilities are 941, 1,024 and 896 million. Neither enters long-term debt.
- **Interest expense** is tagged for fiscal 2022 and 2023 (2,931 and 3,933 million) and not for fiscal 2024. Apple has debt
  at every year-end, so the no-reported-debt rule does not read it.
- **Gross profit** is tagged directly for all three years, as the record found.

## 7. Not yet verified

- **Coverage.** Twelve issuers were read: ten US filers and the two IFRS filers of the regression set. A field
  that disagrees on some issuer outside them would make that year-end `ambiguous_fact`; it would not be wrong.
- **Transition periods.** No captured issuer has one. The behavior (a missing earlier period, then `missing_fact`) is
  tested on synthetic periods only.
- **Issuers that tag no share count.** Walmart and SAP show the case. How many issuers outside the set do is not known.
- **The fraction of issuers whose *t−1* count is from the anchor filing.** Eight of nine here; Deere shows that it is not
  always so.
- **A filing that restates a count for a split** is not in the set; the same-filing rule of Q5 relies on the restated
  filing being the one that reports both counts.

---

## Appendix A: Requests made

All on 2026-10-30. The identity the project configures was sent on every SEC request and is not recorded here; no captured
file contains it. No raw response is committed; the responses are under the ignored `.tmp/step-3-5-3b2/` folder.

**SEC EDGAR: 2 requests, both answered 200.** A pause of 0.5 s separated them.

| Pattern | Count |
| :--- | ---: |
| `data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json` (3,789,099 bytes) | 1 |
| `data.sec.gov/submissions/CIK0000320193.json` (163,586 bytes; its older page was not needed) | 1 |

The committed fixtures `instant_facts/aapl.json` and `annual_facts/aapl.json` keep the filings `0000320193-22-000108`,
`0000320193-23-000106` and `0000320193-24-000123`, and the concepts listed in the plan's file inventory. Their checksums
are in the `SHA256SUMS` file of each folder. The 11 other issuers were not requested again.
