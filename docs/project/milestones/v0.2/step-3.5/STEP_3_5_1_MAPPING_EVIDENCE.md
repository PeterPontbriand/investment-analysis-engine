# Step 3.5 — Slice 3.5.1 Mapping Evidence Record

Live source evidence behind the 3.5.1 slice plan: where a filing's as-filed SIC code comes from, how Yahoo adjusts its
price history, the regression issuer set, the balance-sheet field mappings, the derived-total reconciliation and the
share-count coverage, and (filled in by 3.5.1c) the annual field mappings and depreciation evidence. Rules and
formulas are owned by [Shared definitions](STEP_3_5_SHARED_DEFINITIONS.md); nothing here overrides them. Scope and
status live in the [slice plan](STEP_3_5_1_SLICE_PLAN.md#2-sequence-and-status).

> **This document is not a test fixture and holds no executable expected data.** It records research observations
> used to design the slice and to choose fixtures. No test may take an expected value from it. Each sub-slice
> re-fetches, trims and independently checks whatever it uses.

## 1. At a glance

- **SIC verdict: Pass.** A filing's SEC header keeps the `ASSIGNED-SIC` of its filing date. Two issuers whose code
  changed show an older annual filing with a code that differs from today's `sic` and from a later filing's header
  ([§3](#3-sic-evidence)).
- **Price finding:** Yahoo's `Close` is split-adjusted after the fact and not dividend-adjusted; `Adj Close` is both.
  The split history is complete for the issuers checked and shows a stock dividend as a fractional split, which cannot
  be told apart from a small split ([§4](#4-price-and-split-evidence)).
- **One finding changes a decision:** a filing restates its share counts for a split effective before the filing is
  issued, so a share count must be scaled only by splits after the filing it came from, not after its fiscal year-end
  ([§4.5](#45-a-count-restated-for-a-split-before-the-filing-walmart-fy2024)).
- **Balance-sheet field mappings (3.5.1b):** the regression issuer set is named in [§5.1](#51-the-regression-issuer-set);
  the 17 instant fields have a disposition per taxonomy in [§5.3](#53-the-field-mappings); total liabilities has a
  derivation that holds for US GAAP and fails for IFRS ([§5.4](#54-derived-totals)).
- **Share-count coverage fails** for three of the ten issuers checked: Walmart, SAP and Nutrien get no
  `COMMON_SHARES_OUTSTANDING` from either existing path ([§5.5](#55-share-count-coverage)). The sub-slice stops there.
- **Annual field mappings and depreciation evidence:** empty until 3.5.1c ([§6](#6-depreciation-evidence)).
- **What it does not show:** coverage across the market. Nine issuers were checked for the SIC, five for
  Yahoo. The gaps are in [§7](#7-not-yet-verified).

## 2. Sources

1. SEC EDGAR filing index files at `www.sec.gov/Archives/edgar/data/`, the `.hdr.sgml` header of a filing.
2. SEC EDGAR submissions JSON at `data.sec.gov/submissions/`, for the issuer's current `sic`, its former names and its
   filing list.
3. SEC EDGAR `companyconcept` JSON and two annual-report documents (NVIDIA fiscal 2024, Walmart fiscal 2024).
4. Yahoo Finance through yfinance 1.6.0, `Ticker.history` and `Ticker.splits`.
5. SEC Staff Accounting Bulletin Topic 4.C (Equity Accounts, Changes in Capital Structure), which the Walmart filing
   follows when it restates for a split that took effect before it was issued.

All requests were made on 2026-10-25 and are listed in [Appendix A](#appendix-a-requests-made).

## 3. SIC evidence

### 3.1 Header source

The file is `<accession>.hdr.sgml` in the filing's archive folder:

```text
https://www.sec.gov/Archives/edgar/data/<cik, no leading zeros>/<accession without dashes>/<accession>.hdr.sgml
```

- It exists and carries `ASSIGNED-SIC` for every one of the 14 filings fetched (annual reports on Forms 10-K, 20-F and
  40-F, filed from 2016 to 2026). The `-index-headers.html` alternative was not needed.
- A request for an accession that does not exist returns HTTP 404 with an empty body.
- The files are small: 0.8 to 1.6 KB for a single filer, 6.5 KB for Duke Energy's combined filing.
- The fields that matter, quoted from the Riot Platforms fiscal 2015 header:

```text
<ACCEPTANCE-DATETIME>20160323163316
<ACCESSION-NUMBER>0001079973-16-000870
<TYPE>10-K
<PERIOD>20151231
<FILING-DATE>20160323
<CONFORMED-NAME>Venaxis, Inc.
<CIK>0001167419
<ASSIGNED-SIC>2835
```

- **A combined filing has one `<FILER>` block per registrant.** The header of the Prologis fiscal 2025 annual report
  holds Prologis, Inc. (`6798`) and Prologis, L.P. (`6500`); Duke Energy's holds eight registrants with codes from
  `4911` to `4931`. The reader must take the code of the block whose `<CIK>` is the issuer's CIK, never the first
  block and never a block chosen by position.

### 3.2 How the candidates were found

Issuers whose business changed enough to change a SIC were chosen from knowledge of the issuers, then confirmed from
the former names in their submissions JSON: Riot Platforms (formerly Venaxis and Bioptix, a diagnostics company) and
MARA Holdings (formerly Marathon Patent Group, a patent licensor). Both now file under SIC `6199`.

### 3.3 Result

| Issuer (CIK) | Filing | Filed | Header `ASSIGNED-SIC` | Current submissions `sic` |
| :--- | :--- | :--- | ---: | ---: |
| Riot Platforms (1167419), then Venaxis | 10-K, `0001079973-16-000870` | 2016-03-23 | 2835 | 6199 |
| Riot, then Bioptix | 10-K, `0001079973-17-000206` | 2017-03-31 | 2835 | 6199 |
| Riot, then Riot Blockchain | 10-K, `0001079973-19-000197` | 2019-04-02 | 2835 | 6199 |
| Riot Platforms | 10-K, `0001558370-23-002704` | 2023-03-02 | 6199 | 6199 |
| MARA Holdings (1507605), then Marathon Patent Group | 10-K, `0001104659-16-108696` | 2016-03-30 | 6794 | 6199 |
| Marathon Patent Group | 10-K, `0001493152-19-003868` | 2019-03-25 | 6794 | 6199 |
| Marathon Digital Holdings | 10-K, `0001493152-23-007879` | 2023-03-16 | 7374 | 6199 |

**Verdict: Pass.** Riot's fiscal 2015 header shows 2835, which differs from today's 6199 and from the fiscal 2022
header's 6199. MARA's fiscal 2015 header shows 6794, which differs from today's 6199 and from its fiscal 2022 header's
7374. MARA also shows that the header is not the current code even for a recent filing: the 2023 header says 7374 while
the submissions record says 6199. The header is a record of the filing date, so the as-filed code can be used for a
historical run.

### 3.4 Classification spot checks

Classes follow [Shared definitions §1](STEP_3_5_SHARED_DEFINITIONS.md#1-applicability): financial 6000–6799, utility
4900–4999, manufacturer 2000–3999, anything else an ordinary non-financial, non-manufacturing issuer.

| Kind | Issuer | Filing (annual report) | Header code | Class |
| :--- | :--- | :--- | ---: | :--- |
| Bank | JPMorgan Chase | 10-K, `0001628280-26-008131`, filed 2026-02-13 | 6021 | Financial |
| Insurer | Travelers | 10-K, `0000086312-26-000065`, filed 2026-02-12 | 6331 | Financial |
| REIT | Prologis, Inc. | 10-K, `0001193125-26-051453`, filed 2026-02-13 | 6798 | Financial |
| Utility | Duke Energy | 10-K, `0001326160-26-000014`, filed 2026-02-26 | 4931 | Utility |
| Manufacturer | Deere | 10-K, `0001104659-25-122321`, filed 2025-12-18 | 3523 | Manufacturer |
| IFRS filer | SAP SE | 20-F, `0001104659-26-020058`, filed 2026-02-26 | 7372 | Ordinary (none of the three) |
| IFRS filer | Nutrien | 40-F, `0001193125-26-081326`, filed 2026-02-27 | 2870 | Manufacturer |

- **No header lacked `ASSIGNED-SIC`.** Pre-2001 filings and filers with a blank code were not checked
  ([§7](#7-not-yet-verified)).
- **A registrant's code can sit outside its parent's range.** Prologis, L.P. is `6500`, still financial; Duke Energy
  Carolinas is `4911`, still a utility. Neither changes a class, but only the filer's own block may be used.
- **An IFRS filer is classified by the same codes.** SAP falls in no range and Nutrien is a manufacturer, so Altman's
  model selection (Z for manufacturers) applies to a foreign private issuer too.

### 3.5 Fixtures and the live check

Slice 3.5.1a keeps the header lines its reader uses (the accession, filing date and acceptance time, and each
registrant's CIK and `ASSIGNED-SIC`) from the headers above, under
`investment_analysis_engine/evaluation/fixtures/sec_edgar/filing_headers/`, with a checksum file. Nothing else of a
header is kept.

| Fixture | Accession |
| :--- | :--- |
| `riot_fy2015`, `riot_fy2022` | `0001079973-16-000870`, `0001558370-23-002704` |
| `mara_fy2015`, `mara_fy2022` | `0001104659-16-108696`, `0001493152-23-007879` |
| `jpm_fy2025`, `trv_fy2025` | `0001628280-26-008131`, `0000086312-26-000065` |
| `pld_fy2025` (two registrants), `duk_fy2025` (eight registrants) | `0001193125-26-051453`, `0001326160-26-000014` |
| `de_fy2025`, `sap_fy2025`, `ntr_fy2025` | `0001104659-25-122321`, `0001104659-26-020058`, `0001193125-26-081326` |

One `live_network` check, `test_sec_edgar_filing_header_response_shape` in `tests/live/test_provider_response_shape.py`,
requests one header and asserts the shape of the fields the reader uses, never a code.

## 4. Price and split evidence

Throwaway script under `.tmp/`, yfinance 1.6.0, `Ticker.history(..., auto_adjust=False, actions=True)` and
`Ticker.splits`.

### 4.1 What `Close` and `Adj Close` are

NVIDIA split 10 for 1 on 2024-06-10. Downloaded after the split, with `auto_adjust=False`:

| Date | `Close` | `Adj Close` | Note |
| :--- | ---: | ---: | :--- |
| 2023-07-28 | 46.75 | 46.607 | |
| 2024-04-30 | 86.402 | 86.1563 | |
| 2024-06-07 | 120.888 | 120.5443 | The last session before the split; traded near 1,208 |
| 2024-06-10 | 121.79 | 121.4437 | First split-adjusted session |

- **`Close` is split-adjusted after the fact.** The 2024-06-07 value is one tenth of the price at which the shares
  traded that day. It is not dividend-adjusted: `Close` and `Adj Close` differ by the dividends paid later.
- **`Adj Close` is adjusted for splits and dividends.** With `auto_adjust=True` the frame has no `Adj Close` column
  and `Close` equals the `Adj Close` of the unadjusted request to the digit, for every date shown. The existing
  Momentum series uses `auto_adjust=True` (`data/yfinance/client.py`) and so is dividend-adjusted.
- **No download returns the price as it traded.** An unadjusted historical close cannot be had from Yahoo. The split-adjusted
  close and the split history together recover it ([§4.4](#44-the-arithmetic)).
- Apple's 4 for 1 split of 2020-08-31 shows the same dividend effect on a series with no dividend in the window:
  `Adj Close` / `Close` is 0.969 on every day of 2020-08-24 to 2020-09-03, the later dividends' cumulative factor.

### 4.2 The split history

`Ticker.splits` returns one row per event, dated at 09:30 exchange time, with the ratio as a float (new shares per old
share). It is built from the actions of the maximum-range history, so it is one request per ticker.

| Issuer | Events | Earliest | Latest events |
| :--- | ---: | :--- | :--- |
| NVIDIA | 6 | 2000-06-27 | 2007-09-11 1.5; 2021-07-20 4.0; 2024-06-10 10.0 |
| Apple | 5 | 1987-06-16 | 2005-02-28 2.0; 2014-06-09 7.0; 2020-08-31 4.0 |
| Walmart | 4 | 1990-07-09 | 1999-04-20 2.0; 2024-02-26 3.0 |
| Commerce Bancshares | 27 | 1986-05-27 | the last twelve are all 1.05, from 2007-11-27 to 2025-12-02 |
| Tootsie Roll | 29 | 1986-07-11 | the last twelve are all 1.03, from 2013-03-01 to 2026-03-05 |

- **It reaches back far beyond any share-count date a strategy needs** (at most four fiscal year-ends).
- **The splits that were checked are right.** NVIDIA's 2:1, 2:1, 2:1, 3:2, 4:1 and 10:1, Apple's four 2:1 and 7:1 and
  4:1, and Walmart's 3:1 match the issuers' announced splits. Yahoo dates the event on the first split-adjusted session
  (Walmart's filing says the split was effected on 2024-02-23; Yahoo has 2024-02-26).
- **Completeness was not verified for stock dividends.** Commerce Bancshares' list has gaps in some years (none between 2007 and 2025 in
  2010, 2011, 2016, 2017, 2019, 2022 or 2023) that may be missing events or years without a dividend; no second source was
  consulted ([§7](#7-not-yet-verified)).

### 4.3 Stock dividends

A stock dividend appears as a fractional split: 1.05 for Commerce Bancshares' 5% dividends and 1.03 for Tootsie Roll's
3% dividends. Nothing in the row marks it as a dividend, and a genuine small split would look the same. For share-count
adjustment this does not matter: a 5% stock dividend and a 21-for-20 split both raise the share count and lower the
price by the same factor, and neither is capital raised. The limitation is only that the two cannot be told apart, so
no consumer may count the fractional events or label them.

### 4.4 The arithmetic

Worked example, NVIDIA, requested `as_of` 2024-04-30 (before the split), run today.

| Input | Value | Source |
| :--- | ---: | :--- |
| Anchor filing | fiscal 2024 10-K, `0001045810-24-000029`, filed 2024-02-21 | companyconcept provenance |
| Common shares outstanding at 2024-01-28 | 2,464,000,000 | `us-gaap:CommonStockSharesOutstanding`, in that filing |
| Splits with an ex-date after 2024-02-21 | 10 for 1 on 2024-06-10 | `Ticker.splits` |
| Split-adjusted `Close` on 2024-04-30 | 86.402 | `Ticker.history`, `auto_adjust=False` |

- **Price as it traded:** 86.402 × 10 = 864.02 (undoing the split that came after the date).
- **Market cap from the traded price and the unscaled count:** 864.02 × 2,464,000,000 = 2,128,945,280,000.
- **Market cap from the adjusted price and the scaled count:** 86.402 × (2,464,000,000 × 10) = 86.402 × 24,640,000,000
  = 2,128,945,280,000.

The two are equal, because the factor of 10 cancels. The identity needs the count and the price to be on the same side of
every split. The traded price of 864.02 is not an independent observation: Yahoo is the only price source, and the
factor is read from the same split table. The cancellation is checked, the price is not.

- **The dividend-adjusted series would be wrong.** `Adj Close` on 2024-04-30 is 86.1563, so using it gives
  86.1563 × 24,640,000,000 = 2,122,891,232,000, which is 0.28% low, and by an amount that depends on today's date.
- **Later filings restate the same year-end.** The fiscal 2025 10-K (`0001045810-25-000023`, filed 2025-02-26) reports
  the count at 2024-01-28 as 24,643,000,000: split-adjusted (and rounded to millions differently), as a comparative.
  The filing that is the source of a count therefore decides how it is scaled ([§4.5](#45-a-count-restated-for-a-split-before-the-filing-walmart-fy2024)).

### 4.5 A count restated for a split before the filing: Walmart FY2024

The share counts of a filing are restated for a split that took effect before the filing was issued. SEC Staff
Accounting Bulletin Topic 4.C requires the retroactive effect when a split occurs after the balance-sheet date but
before the financial statements are issued. Walmart's fiscal 2024 10-K shows it:

- Fiscal year-end: 2024-01-31. The filing, accession `0000104169-24-000056`, was filed in March 2024.
- The split: "On February 23, 2024, the Company effected a 3-for-1 forward split of its common stock ... All share and
  per share information ... throughout this Annual Report on Form 10-K has been retroactively adjusted to reflect the
  stock split."
- Yahoo's split table has the event, 3.0 on 2024-02-26.

A count at 2024-01-31 taken from that filing is already on the post-split basis. Scaling it by every split after the
fiscal year-end would apply the 3-for-1 split a second time and report a market cap three times too large. Scaling it
only by splits after the filing's own filing date, which includes no split here, is correct. A later filing's
comparative restates an earlier year-end the same way (NVIDIA, [§4.4](#44-the-arithmetic)), so the starting point of the
scaling is the filing date of the filing the count was taken from, found in the count's own provenance.

- **Limitation:** a split announced before the filing but effective just after it is assumed not to be reflected in the
  filing. The assumption is the standard's: the restatement is required only for a split effective before issuance.
- **Not machine-checked:** Walmart's `CommonStockSharesOutstanding` is not tagged after 2013 in the non-dimensional
  concept, so the restated value could not be read from structured data. The statement is read from the rendered
  filing.

## 5. Field mappings

Slice 3.5.1b fills the balance-sheet fields; 3.5.1c fills the annual fields. Every row records the columns below.

| Column | Content |
| :--- | :--- |
| Field | The `FinancialField` name proposed for it |
| Taxonomy | `us-gaap` or `ifrs-full` |
| Concept | The exact element, or the priority list of elements |
| Units and scale | The XBRL unit, and the scale the filer applies |
| Kind | A period amount or a balance at a date |
| Reported by | The filer populations that report it, and what the others report instead |
| Value check | The rendered statement or note the value was compared with |
| Disposition | Approved, approved with a stated limit, or unsupported |

### 5.1 The regression issuer set

This is Step 3.5's regression issuer set. The 3.5.7 golden suite reuses it. "Latest annual" is the newest annual report
filed on or before 2026-10-25.

| Issuer | Ticker | CIK | Latest annual accession (form, filed, year-end) | Taxonomy | Why it fits |
| :--- | :--- | :--- | :--- | :--- | :--- |
| JPMorgan Chase | JPM | 19617 | `0001628280-26-008131` (10-K, 2026-02-13, 2025-12-31) | us-gaap | Bank; SIC 6021 ([§3.4](#34-classification-spot-checks)) |
| Prologis | PLD | 1045609 | `0001193125-26-051453` (10-K, 2026-02-13, 2025-12-31) | us-gaap | REIT; SIC 6798; combined filing with Prologis, L.P. |
| Duke Energy | DUK | 1326160 | `0001326160-26-000014` (10-K, 2026-02-26, 2025-12-31) | us-gaap | Utility; SIC 4931; combined filing of eight registrants |
| Deere | DE | 315189 | `0001104659-25-122321` (10-K, 2025-12-18, 2025-11-02) | us-gaap | Manufacturer; SIC 3523; 52/53-week year |
| SAP | SAP | 1000184 | `0001104659-26-020058` (20-F, 2026-02-26, 2025-12-31) | ifrs-full | IFRS filer in EUR; SIC 7372 |
| Nutrien | NTR | 1725964 | `0001193125-26-081326` (40-F, 2026-02-27, 2025-12-31) | ifrs-full | IFRS filer in USD; SIC 2870 |
| Walmart | WMT | 104169 | `0000104169-26-000055` (10-K, 2026-03-13, 2026-01-31) | us-gaap | Non-manufacturer; tags no share count since 2013 |
| Moderna | MRNA | 1682852 | `0001682852-26-000033` (10-K, 2026-02-20, 2025-12-31) | us-gaap | Negative EBIT: `OperatingIncomeLoss` is -3,074 million for fiscal 2025 |
| Monster Beverage | MNST | 865752 | `0001104659-26-020831` (10-K, 2026-02-27, 2025-12-31) | us-gaap | No reported debt: no debt concept is tagged at 2025-12-31 and the balance sheet's long-term debt line is empty (373.951 million a year earlier) |
| Alphabet | GOOGL | 1652044 | `0001652044-26-000018` (10-K, 2026-02-05, 2025-12-31) | us-gaap | Several share classes (A, B and C); Company Facts holds one combined count of 12,088 million |
| Honeywell | HON | 773840 | `0000773840-26-000013` (10-K, 2026-02-17, 2025-12-31) | us-gaap | Manufacturer (SIC 3724) with a classified balance sheet: `AssetsCurrent` 30,387 million and `LiabilitiesCurrent` 23,414 million are tagged. Added under decision H9 beside Deere, whose balance sheet is unclassified |

- **Chosen from evidence, not from the issuers' names.** Moderna, Monster and Alphabet were the only candidates fetched
  for the three slots; each met its criterion on the first check. The negative-EBIT firm is not also the no-debt firm:
  Moderna tags a noncurrent long-term debt line of 590 million.
- **Monster's interest.** It tags `InterestPaidNet` (5.337 million, a cash-flow amount) and no interest expense, so the
  zero-debt rule of [Shared definitions §6](STEP_3_5_SHARED_DEFINITIONS.md#total-debt) is for 3.5.2 to apply.
- **Honeywell** tags no `Liabilities` at any year-end, so the derivation of [§5.4](#54-derived-totals) is its only source
  of total liabilities. Its fiscal year is the calendar year, so it adds no 52/53-week case; Deere remains that case.
- **Prologis and Duke Energy** are combined filings; their Company Facts hold the parent issuer's values only.

### 5.2 Method and limits

- **Presence:** the Company Facts of the ten issuers, read for the anchor annual filing's year-end *t*, for *t−1*, and
  for *t−2* from the same or an earlier annual filing. All values are in whole units of the reported currency; a value
  is an instant (it has an `end` and no `start`). The scale is the rounding the filer applies: thousands (Prologis,
  Monster), millions (the others). A year-end repeats in the next filing as a comparative and may differ there by a
  restatement (SAP, Alphabet, JPMorgan, Deere); the newest filing's value is the restated one.
- **Values:** one US GAAP filer and one IFRS filer per field, at the anchor year-end, against the filing's rendered
  statement (the SEC's `R<n>.htm` page): Walmart, Monster and Prologis for US GAAP, Nutrien and SAP for IFRS. Where a line
  is a note disclosure and not on the face, the note's page is the check; a field no checked filer shows is marked
  "not checked".
- **Request budget:** 59 EDGAR requests of about 60 ([Appendix A](#appendix-a-requests-made)). Raw responses are under
  `.tmp/` and are not committed.
- **Honeywell and the later checks** (decisions H7 to H12) were read from Company Facts for presence only, with the
  rendered balance sheets of Alphabet and Moderna added to establish which tagged concepts are the same line item.

### 5.3 The field mappings

The `FinancialField` names are the ones the implementation proposes. In the "Value check" column a tick means the Company
Facts value equals the rendered value to the filer's own rounding.

| Field | Taxonomy | Concept | Units and scale | Reported by | Value check | Disposition |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `TOTAL_ASSETS` | us-gaap | `Assets` | USD, instant; millions (thousands: PLD, MNST) | All eight US filers | WMT, MNST, PLD ✓ | Approved |
| `TOTAL_ASSETS` | ifrs-full | `Assets` | EUR or USD, instant; millions | SAP, NTR | SAP, NTR ✓ | Approved |
| `TOTAL_LIABILITIES` | us-gaap | `Liabilities`, else the derivation of [§5.4](#54-derived-totals) | USD, instant | Direct: JPM, PLD, DE, GOOGL, MRNA. Not tagged: DUK, WMT, MNST | PLD ✓; WMT's face has no total-liabilities line | Approved; the derivation is approved with a stated limit (every term must be tagged) |
| `TOTAL_LIABILITIES` | ifrs-full | `Liabilities` | EUR or USD, instant | SAP, NTR | SAP, NTR ✓ | Approved; the derivation is unsupported |
| `CURRENT_ASSETS` | us-gaap | `AssetsCurrent` | USD, instant | DUK, WMT, GOOGL, MRNA, MNST. Unclassified balance sheets: JPM, PLD, DE | WMT ✓ | Approved with a stated limit: an unclassified balance sheet has none |
| `CURRENT_ASSETS` | ifrs-full | `CurrentAssets` | instant | SAP, NTR | SAP, NTR ✓ | Approved |
| `CURRENT_LIABILITIES` | us-gaap | `LiabilitiesCurrent` | USD, instant | Same filers as `CURRENT_ASSETS` | WMT, MNST ✓ | Approved with a stated limit: same as above |
| `CURRENT_LIABILITIES` | ifrs-full | `CurrentLiabilities` | instant | SAP, NTR | SAP, NTR ✓ | Approved |
| `CASH_AND_EQUIVALENTS` | us-gaap | `CashAndCashEquivalentsAtCarryingValue` | USD, instant | PLD, DUK, DE, WMT, GOOGL, MRNA, MNST, HON. Not JPM (a bank) | WMT, MNST, PLD ✓ | Approved with a stated limit: banks tag other cash concepts |
| `CASH_AND_EQUIVALENTS` | ifrs-full | `CashAndCashEquivalents` | instant | SAP, NTR | SAP, NTR ✓ | Approved |
| `SHORT_TERM_INVESTMENTS` | us-gaap | Priority list: `ShortTermInvestments`, `MarketableSecuritiesCurrent`, `AvailableForSaleSecuritiesDebtSecuritiesCurrent` (decisions H10, D2) | USD, instant | MNST and HON (443 million) tag the first. GOOGL tags the second (96,135 million), MRNA the third (3,204). DE tags `MarketableSecurities` (1,411), which is not listed | MNST ✓. GOOGL's face shows "Marketable securities" 96,135 and MRNA's "Investments" 3,204, both in current assets ✓ | Approved with a stated limit: one concept for every year of a run; Deere's unclassified balance sheet does not show its line to be current, so Deere shows none |
| `SHORT_TERM_INVESTMENTS` | ifrs-full | none | none | Neither SAP nor NTR tags a short-term-investments concept; NTR's `ShorttermInvestmentsClassifiedAsCashEquivalents` is part of cash and SAP's `OtherCurrentFinancialAssets` is broader | not applicable | Unsupported |
| `LONG_TERM_INVESTMENTS` | us-gaap | `LongTermInvestments` | USD, instant | MNST only. GOOGL tags `OtherLongTermInvestments` (68,687 million), MRNA `AvailableForSaleSecuritiesDebtSecuritiesNoncurrent` (2,336) | MNST ✓ | Approved with a stated limit: the other two concepts are not this field |
| `LONG_TERM_INVESTMENTS` | ifrs-full | none | none | No concept in either filer is long-term investments; SAP's `InvestmentsInAssociates` and NTR's equity-method investment are narrower | not applicable | Unsupported |
| `NET_PPE` | us-gaap | Priority list: `PropertyPlantAndEquipmentNet`, then `PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization` (decision D12) | USD, instant | PLD, DUK, WMT, MNST tag the first. HON (4,629 million) and MRNA (2,134) tag only the second, and GOOGL tags the first to fiscal 2024 and the second at 2025-12-31 (246,597). JPM and DE tag neither | WMT, MNST ✓. MRNA's face "Property, plant and equipment, net" is the second concept (2,134 ✓), and GOOGL's "Property and equipment, net" is the first at 2024 (171,036) and the second at 2025 (246,597) ✓: one line, two concepts | Approved with a stated limit: one concept for every year of a run, so a filer that changed concept (Alphabet) has the years the chosen concept covers and the others absent as another concept; unclassified manufacturers (DE) and banks show none |
| `NET_PPE` | ifrs-full | Priority list: `PropertyPlantAndEquipment`, then `PropertyPlantAndEquipmentIncludingRightofuseAssets` (decision H11) | instant | Neither filer tags the first; both tag the second | SAP ✓ (4,497, of which right-of-use 1,477), NTR ✓ | Approved with a stated limit: the second concept is used alone, only where it is the filer's own single balance-sheet line (the face of both filers reports right-of-use assets inside it), and is never added to the first |
| `RECEIVABLES` | us-gaap | Priority list: `AccountsReceivableNetCurrent`, then `ReceivablesNetCurrent` (decision H10) | USD, instant | DUK, GOOGL, MRNA, MNST, HON (7,621 million) tag the first. WMT tags the second (11,172 million) and `AccountsReceivableNet` (4,900, not listed). DE and PLD tag only `AccountsReceivableNet` | MNST ✓. WMT's face shows "Receivables, net" 11,172 in current assets ✓ | Approved with a stated limit: one concept for every year of a run; Deere and Prologis show none; an issuer that reports variable-interest-entity receivables on a line of its own shows the other line only (Duke Energy, below) |
| `RECEIVABLES` | ifrs-full | `CurrentTradeReceivables` | instant | SAP, NTR | SAP ✓ in the note (5,790; the face shows trade and other receivables, 6,675); NTR not checked (5,080 in a note; the face shows 5,675) | Approved with a stated limit: a note-level figure, not the face line |
| `RETAINED_EARNINGS` | us-gaap | `RetainedEarningsAccumulatedDeficit` | USD, instant | All eight US filers | WMT, MNST, PLD ✓ | Approved |
| `RETAINED_EARNINGS` | ifrs-full | `RetainedEarnings` | instant | SAP, NTR | SAP, NTR ✓ | Approved |
| `SHORT_TERM_BORROWINGS` | us-gaap | Priority list: `ShortTermBorrowings`, then `CommercialPaper` (decisions H12, D9) | USD, instant | JPM, DUK, WMT, HON (5,893 million) tag the first. Alphabet tags only the second (0) | WMT ✓ | Approved with a stated limit: commercial paper belongs to short-term borrowings, is read only where `ShortTermBorrowings` is not tagged, is never added to it and is never the current portion of long-term debt; Deere's `DebtCurrent` is a related concept, not a value |
| `SHORT_TERM_BORROWINGS` | ifrs-full | `ShorttermBorrowings` | instant | NTR. SAP tags `CommercialPapersIssued` (498 million) and a combined current-borrowings concept | NTR ✓ | Approved with a stated limit: a filer that combines it with the current portion shows none |
| `CURRENT_PORTION_OF_LONG_TERM_DEBT` | us-gaap | `LongTermDebtCurrent` | USD, instant | DUK, WMT, GOOGL. DE tags `DebtCurrent` (13,796 million), which includes short-term borrowings; HON tags `LongTermDebtAndCapitalLeaseObligationsCurrent` (1,546 million), which includes finance leases; MRNA and MNST have none | WMT ✓ | Approved with a stated limit: `DebtCurrent` and the lease-inclusive concept are not mapped |
| `CURRENT_PORTION_OF_LONG_TERM_DEBT` | ifrs-full | `CurrentPortionOfLongtermBorrowings` | instant | NTR. SAP tags `CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings` (1,600 million), which includes commercial paper | NTR ✓ | Approved with a stated limit: SAP's combined concept is not mapped |
| `NONCURRENT_LONG_TERM_DEBT` | us-gaap | `LongTermDebtNoncurrent` | USD, instant | DUK, WMT, GOOGL, MRNA (590 million); MNST only at the prior year-end (373.951) | WMT ✓; MNST prior year ✓ | Approved with a stated limit: a filer that tags another noncurrent debt concept shows none |
| `NONCURRENT_LONG_TERM_DEBT` | ifrs-full | none (`LongtermBorrowings` rejected; decisions H12, H14) | none | SAP (4,550 million, nominal), NTR (9,350, carrying) | NTR ✓. SAP's 4,550 is the nominal amount; its carrying amount is 4,194 (note) | Unsupported for every filer, decided by the project owner (H14): only carrying amounts qualify, Company Facts cannot tell a carrying amount from a nominal one, and one of the two filers tags a nominal amount under the concept |
| `LONG_TERM_DEBT_TOTAL` | us-gaap | `LongTermDebt` | USD, instant | PLD, DUK, WMT, GOOGL | PLD ✓ (the face's "Debt"); DUK and WMT equal current plus noncurrent; GOOGL (49,085 million) does not (48,543) | Approved with a stated limit: a reconciliation-only field; a total that does not reconcile is a finding for 3.5.2, never repaired here |
| `LONG_TERM_DEBT_TOTAL` | ifrs-full | none | none | `Borrowings` is 9,863 million for NTR (long-term only; the 873 of short-term debt is outside it) and 6,150 for SAP (nominal, including commercial paper) | not applicable | Unsupported: the two filers use it for different quantities |
| `LEASE_LIABILITIES_AS_DEBT` | us-gaap | `FinanceLeaseLiability` | USD, instant | DUK, DE, WMT, GOOGL, MRNA. `OperatingLeaseLiability` (tagged by JPM, PLD, DUK, DE, WMT, GOOGL, MRNA) is never this field | WMT ✓ (856 + 5,905 = 6,761 on the face) | Approved with a stated limit: finance leases only, as Shared definitions §6 requires |
| `LEASE_LIABILITIES_AS_DEBT` | ifrs-full | `LeaseLiabilities` | instant | SAP (1,684 million), NTR (1,283) | SAP ✓ (254 + 1,430 in the note), NTR ✓ (346 + 937 on the face) | Approved: all IFRS 16 lease liabilities count |
| `PREFERRED_STOCK` | us-gaap | `PreferredStockValue` | USD, instant | PLD (64 million), MRNA (0) | PLD ✓ (63.948) | Approved with a stated limit: a filer with none tags no value |
| `PREFERRED_STOCK` | ifrs-full | none | none | Neither filer reports preference shares, so no concept can be shown to carry them | not applicable | Unsupported |
| `NONCONTROLLING_INTEREST` | us-gaap | `MinorityInterest` | USD, instant | PLD, DUK, DE, WMT | WMT ✓ (6,270 nonredeemable) | Approved with a stated limit: redeemable noncontrolling interest (WMT 293 million, DE 51) is a mezzanine item reported on its own and is not in this field |
| `NONCONTROLLING_INTEREST` | ifrs-full | `NoncontrollingInterests` | instant | SAP (488 million), NTR (42) | SAP, NTR ✓ | Approved |

**Honeywell** (decision H9) was read for presence at 2025-12-31 and was not compared with its rendered statement. It tags
`Assets` 73,681 million, `AssetsCurrent` 30,387, `LiabilitiesCurrent` 23,414, cash 12,487, `ShortTermInvestments` 443,
`AccountsReceivableNetCurrent` 7,621, retained earnings 50,964, `ShortTermBorrowings` 5,893, `FinanceLeaseLiability` 64,
`MinorityInterest` 1,126, and no preferred stock, `LongTermDebtCurrent`, `LongTermDebtNoncurrent` or `Liabilities`. It
tags a direct `LongTermDebt` of 29,046 million beside `LongTermDebtAndCapitalLeaseObligations` (27,141) and
`LongTermDebtAndCapitalLeaseObligationsCurrent` (1,546); neither of the last two is a mapped part. That is a second test
case for the reconciliation rule of Shared definitions §6, with Alphabet.

#### Related concepts of the debt fields

A related concept is tagged by a filer for part of the same quantity and is never a
value. The balance-sheet series reports it beside an absent date (`related_concept`) and as a note on a present value, and
[Shared definitions §6](STEP_3_5_SHARED_DEFINITIONS.md#total-debt) reads that report.

| Field | Taxonomy | Related concepts | Seen in |
| :--- | :--- | :--- | :--- |
| `SHORT_TERM_BORROWINGS` | us-gaap | `DebtCurrent` | Deere (13,796 million, with the current portion) |
| `SHORT_TERM_BORROWINGS` | ifrs-full | `CommercialPapersIssued`, `CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings` | SAP (498 and 1,600 million) |
| `CURRENT_PORTION_OF_LONG_TERM_DEBT` | us-gaap | `DebtCurrent`, `LongTermDebtAndCapitalLeaseObligationsCurrent` | Deere; Honeywell (1,546 million, with finance leases) |
| `CURRENT_PORTION_OF_LONG_TERM_DEBT` | ifrs-full | `CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings` | SAP |
| `NONCURRENT_LONG_TERM_DEBT` | us-gaap | `LongTermDebtAndCapitalLeaseObligations` | Honeywell (27,141 million) |
| `NONCURRENT_LONG_TERM_DEBT` | ifrs-full | none: the mapping is unsupported, so the field is `unavailable` and no related concept is read | Nutrien, SAP |
| `LEASE_LIABILITIES_AS_DEBT` | us-gaap | `FinanceLeaseLiabilityCurrent`, `FinanceLeaseLiabilityNoncurrent` | Honeywell (the parts of its 64 million) |
| `RECEIVABLES` | us-gaap | `AccountsAndOtherReceivablesNetCurrent` | Duke Energy (receivables of variable interest entities) |

Result for the four cases of the review, from the trimmed filings: Deere's short-term borrowings and current portion are
absent with `DebtCurrent` tagged; Honeywell's current portion and noncurrent debt are absent with their lease-inclusive
concepts tagged and its short-term borrowings (5,893 million) are present; Nutrien's noncurrent debt is unsupported and
SAP's current portion and short-term borrowings are absent with their combined concepts tagged; Alphabet's three
components are present (commercial paper 0, current portion 1,996 million, noncurrent 46,547 million), with no related
concept to report.

**Duke Energy's receivables (checked against its rendered balance sheet, R6 of `0001326160-26-000014`).** The face shows
"Receivables (net of allowance for doubtful accounts)" of 16 million at 2025-12-31 and 1,889 million at 2024-12-31, and
"Receivables of VIEs" of 4,214 and 2,170 million on a separate line. `AccountsReceivableNetCurrent` equals the first line
for both years ✓, and the second line is `AccountsAndOtherReceivablesNetCurrent`. The fall to 16 million is real: the receivables
moved into the variable interest entities. The mapping is therefore limited: **for an issuer that reports receivables of
variable interest entities on a line of their own, the field is the other line only**, and the related concept is reported
beside the value so that a consumer can see it. It is not summed.

**Extra submissions pages.** A frequent filer's older filings are not in the `recent` block of its submissions data but in
the extra pages `filings.files` lists (JPMorgan's recent block starts 2025-10-24 and 71 pages of about a month each hold
the rest). The balance-sheet series reads those pages, newest first and at most twelve, only when no annual filing made
after the oldest requested year-end and within two years of it is in the recent block. For JPMorgan, 2023-12-31 then
resolves from the fiscal 2024 report (`0000019617-25-000270`, in page 008, filed 2025-02-14); pages 001 to 007 hold no
annual filing, which the company facts confirm (no annual report between 2025-02-25 and 2025-10-23).

**Period behavior, all rows.** Every observation is an instant at a fiscal year-end (52/53-week ends such as Deere's
2025-11-02 and Walmart's 2026-01-31 included). No row is a duration. A comparative year-end the anchor filing does not
report is found in an earlier annual filing for most fields (Alphabet's net PP&E at 2024-12-31 and 2023-12-31, Walmart's
finance leases at 2025-01-31). A year-end can carry two values from two filings when the later one restated it (SAP at
2023-12-31, Alphabet's `LongTermDebt`); these are the conflicts the selection rule resolves by taking the newest eligible
filing's value.

### 5.4 Derived totals

**Total liabilities.** The identity is total liabilities and equity, minus total equity including noncontrolling interest,
minus any temporary equity tagged at the same date: `LiabilitiesAndStockholdersEquity` −
`StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest` − the temporary equity, which is
`TemporaryEquityCarryingAmountIncludingPortionAttributableToNoncontrollingInterests` if tagged, else
`RedeemableNoncontrollingInterestEquityCarryingAmount` if tagged, else none. Deere tags both at the same value (51
million at 2025-11-02), which is why the first takes precedence and the two are never added. Under IFRS the identity is
`EquityAndLiabilities` − `Equity`.

Reconciliation against the directly tagged `Liabilities`, over every annual year-end in the filer's Company Facts at which
the direct value and every derivation term are tagged. Each check is one year-end in one annual filing, so a year-end that
two filings report counts twice.

| Filer | Taxonomy | Checks | Year-ends | Mismatches |
| :--- | :--- | ---: | :--- | ---: |
| JPMorgan | us-gaap | 13 | 2008-12-31 to 2015-12-31 | 0 |
| Prologis | us-gaap | 28 | 2010-12-31 to 2025-12-31 | 0 |
| Deere | us-gaap | 36 | 2008-10-31 to 2025-11-02; temporary equity of 14, 92, 97, 82 or 51 million enters 15 of the checks | 0 |
| Nutrien | ifrs-full | 16 | 2017-12-31 to 2025-12-31 | 0 |
| SAP | ifrs-full | 18 | 2016-12-31 to 2025-12-31 | **4** |

- **US GAAP: 77 checks, no mismatch.** The derivation equals the tagged value to the dollar for every filer that tags both.
  JPMorgan after 2015, Alphabet and Moderna tag `Liabilities` and no total equity including noncontrolling interest, so
  the derivation cannot be evaluated for them and the direct value is used. Duke Energy, Walmart and Monster tag no
  `Liabilities`. Moderna tags `TemporaryEquityCarryingAmountAttributableToParent` in three years; it is outside the
  identity above and no filer in the set tags it beside the other terms.
- **IFRS: four mismatches, all by one million, all SAP.** At 2025-12-31 SAP tags total liabilities of 25,288 and total
  equity of 45,073, and total equity and liabilities of 70,362; the derived value is 25,289. The rendered statement of
  financial position shows the same three figures, so the filing's lines do not add because each is rounded to millions.
  The other three mismatches are 2017-12-31 in the 2018 filing, 2018-12-31 in the 2020 filing and 2023-12-31 in the 2024
  filing.
- **Disposition:** the US GAAP derivation is approved with a stated limit. The IFRS derivation is **unsupported**: one
  mismatch makes it so, as H3 states. SAP and Nutrien both tag `Liabilities` directly, so no IFRS issuer in the set needs it.
- **Honeywell** tags no `Liabilities` at any year-end and tags total equity including noncontrolling interest
  (15,030 million at 2025-12-31). The derivation gives 58,651 million (73,681 − 15,030; no temporary equity tagged). No
  reconciliation is possible for it.
- **What the derivation supplies:** Duke Energy 142,717 million at 2025-12-31 (195,736 − 53,019) and Walmart 178,488 million
  at 2026-01-31 (284,668 − 105,887 − 293), neither of which tags `Liabilities`. Monster tags neither `Liabilities` nor
  total equity including noncontrolling interest, so its total liabilities stay unavailable.

No other field has an exact accounting identity that fills the same kind of gap, so no other derivation is named.

### 5.5 Share-count coverage

`COMMON_SHARES_OUTSTANDING` at the latest year-end, by the two paths the existing resolver reads: the direct
`us-gaap:CommonStockSharesOutstanding`, and `CommonStockSharesIssued` minus `TreasuryStockCommonShares` at the same date.
Counts are shares. The cover-page count (`dei:EntityCommonStockSharesOutstanding`) is not used.

| Issuer | Year-end | Direct | Issued | Treasury | Issued minus treasury | Result |
| :--- | :--- | ---: | ---: | ---: | ---: | :--- |
| JPMorgan | 2025-12-31 | 2,696,200,000 | 4,104,933,895 | 1,408,661,319 | 2,696,272,576 | Direct |
| Prologis | 2025-12-31 | 929,153,000 | 929,153,000 | not tagged | not available | Direct |
| Duke Energy | 2025-12-31 | 778,000,000 | not tagged | not tagged | not available | Direct |
| Deere | 2025-11-02 | 270,400,000 | 536,431,204 | 266,079,164 | 270,352,040 | Direct |
| Moderna | 2025-12-31 | 394,000,000 | 394,000,000 | not tagged | not available | Direct |
| Monster | 2025-12-31 | 978,113,000 | 1,132,906,000 | 154,793,000 | 978,113,000 | Direct, and the fallback agrees |
| Alphabet | 2025-12-31 | 12,088,000,000 | 12,088,000,000 | not tagged | not available | Direct (one combined count for the three classes) |
| **Walmart** | 2026-01-31 | **not tagged** | **not tagged** | not tagged | not available | **No count** |
| **SAP** | 2025-12-31 | not tagged | not tagged (`ifrs-full:NumberOfSharesIssued`, 1,229,000,000, is read by neither path) | not tagged (`ifrs-full:TreasuryShares` is a EUR amount, 6,948 million) | not available | **No count** |
| **Nutrien** | 2025-12-31 | not tagged | not tagged | not tagged | not available | **No count** |

- **Walmart:** the last year-end with a `CommonStockSharesOutstanding` or `CommonStockSharesIssued` fact is 2012-01-31.
  The balance sheet tags `CommonStockValue` (797 million, a dollar amount) and authorized shares only. Every year-end
  from 2013-01-31 to 2026-01-31, fourteen, has no count; all of the latest five are affected. The cover-page count is
  tagged each year and is forbidden.
- **SAP:** both existing paths read us-gaap concepts only, and SAP reports under ifrs-full. It tags the number of shares
  issued (1,229 million at 2025-12-31, at eleven year-ends) but no treasury share count, so issued minus treasury is not
  available under IFRS either. All of the latest five year-ends are affected.
- **Nutrien:** the existing paths read us-gaap only. Nutrien tags `ifrs-full:NumberOfSharesOutstanding` at the year-ends
  2018 to 2024 (491,025,446 at 2024-12-31) and not at 2025-12-31, so an IFRS direct path would cover four of the latest
  five year-ends and not the latest. All of the latest five are affected today.
- **Disposition of the first check: failed.** Three of the ten regression issuers got no count from either path at their
  latest year-end. This stopped 3.5.1b under [A.1](STEP_3_5_1_SLICE_PLAN.md#a1-decisions-f1-to-f10-2026-10-25), H4, and
  the project owner decided the outcome in H7. The paths below are the ones H7 adds. Honeywell, added by H9, tags a
  direct count of 635,300,000 and issued 957,600,000 with no treasury count: **Direct**.

#### Paths added by decision H7

| Issuer | Year-end | IFRS direct path (`ifrs-full:NumberOfSharesOutstanding`) | Cover-page count (`dei:EntityCommonStockSharesOutstanding`, non-dimensional) | Result |
| :--- | :--- | ---: | :--- | :--- |
| Walmart | 2026-01-31 | not applicable (us-gaap) | 7,972,402,501 at 2026-03-11, in `0000104169-26-000055` | **Cover-page count** |
| SAP | 2025-12-31 | not tagged | 1,228,504,232 at 2025-12-31, in `0001104659-26-020058`; unchanged in the two earlier filings | **Cover-page count** |
| Nutrien | 2025-12-31 | tagged to 2024-12-31 (491,025,446) and not at 2025-12-31 | **not tagged**: the cover page of `0001193125-26-081326` (rendered `R1`) has no share count, and Company Facts holds a cover count for the filings of 2019 to 2021 only | **None: `unavailable` for market cap** |
| Alphabet | 2025-12-31 | not applicable | per-class counts only, none in Company Facts | Not needed: the balance sheet tags a combined count |

- **Nutrien** is `unavailable` for market cap. Its IFRS direct count is for the year-end before the latest; an older
  year's count is never substituted, so the consumer must compare the count's date with the fiscal year-end. Of its
  latest five year-ends, four have an IFRS direct count and none has a cover count after 2020.
- **Cover counts of the other issuers** (all non-dimensional, in the latest annual filing): JPMorgan 2,697,032,375 at
  2026-01-31, Prologis 929,559,000 at 2026-02-11, Duke Energy 777,670,866 at 2026-01-31, Moderna 394,939,424 at
  2026-02-13, Monster 978,270,734 at 2026-02-13, Deere 270,445,437 at 2025-11-28, Honeywell 635,675,701 at
  2026-01-23. They are not used, because each has a balance-sheet count.
- **The two counts differ in date.** Walmart's cover count is dated 38 days after its year-end; a share repurchase or an
  issuance between the two dates is in it. That is the limitation Shared definitions §4 states.
- **No IFRS issued-minus-treasury path:** SAP tags `ifrs-full:NumberOfSharesIssued` (1,229,000,000) and
  `ifrs-full:TreasuryShares` as a euro amount (6,948 million), and no treasury share count; Nutrien tags neither. No
  concept in the evidence is a count of treasury shares, so the path is not added.

### 5.6 Findings the owner decides

Each finding of the first pass was decided by the project owner (H7 to H12) or by the implementer under delegation; the
decision is named beside it.

- **The share-count gap** (§5.5): decided by H7. The IFRS derivation (§5.4): unsupported, H8.
- **Deere cannot supply the inputs of two strategies.** Its balance sheet is unclassified: no current assets, no current
  liabilities and no net PP&E. Altman Z (a manufacturer's model), Beneish's asset-quality index and invested capital
  are `unavailable` for it. Honeywell, with a classified balance sheet, is added by H9 so that the regression set has a
  manufacturer that can supply them (its net PP&E is tagged to fiscal 2022 and, for later years, only as the
  finance-lease variant, so invested capital stays `unavailable` for it too).
- **Walmart's receivables:** decided by H10 (the priority list).
- **Absent versus unsupported:** decided by H10. The convention applies only when none of the listed concepts is tagged and
  never to an unsupported mapping. The IFRS short-term and long-term investments and preferred stock are unsupported, so
  they are `unavailable` under IFRS, not zero. Deere's `MarketableSecurities` is not a listed concept, so Deere's
  short-term investments would read as not tagged although it holds 1,411 million; 3.5.2 must treat the issuer's
  unclassified balance sheet as a reason not to read the absence as zero.
- **IFRS debt:** decided by H12 and, for every filer, by the project owner (H14). Only carrying amounts qualify, so the
  IFRS noncurrent long-term debt mapping is unsupported and so is the IFRS direct total. **Consequence for the project owner:** total debt, and through it EV, the
  valuation multiples, Interest Coverage's zero-debt outcome and Magic Formula's earnings yield, cannot be assembled for
  any IFRS filer, Nutrien included. The rule 3.5.2 needs: a component whose mapping is unsupported makes total debt
  `unavailable` and is never read as zero. Supporting a filer such as Nutrien needs either a verified carrying-amount
  concept or an evidence list of issuers, both outside this slice.
- **Alphabet's `LongTermDebt`** (49,085) does not equal its current plus noncurrent parts (48,543): a test case for the
  reconciliation of Shared definitions §6 (H12). Honeywell's direct total beside unmapped parts is the second.

### 5.7 Annual field mappings (slice 3.5.1c)

The 13 completed-annual fields of [Slice inputs §3](STEP_3_5_SLICE_INPUTS.md#3-351--data-mappings-and-applicability), read
from the Company Facts of the eleven issuers of [§5.1](#51-the-regression-issuer-set) for the anchor filing's fiscal year and the
two before it (a duration of 335 to 395 days, fiscal period `FY`, an annual form; quarters, year-to-date periods and stub years
are rejected). Rules that apply to every row:

- **One concept per series.** A field maps to a priority list only where the evidence shows the concepts are the same line
  item. The series uses the first listed concept that reports the newest fiscal year any listed concept reports. A year that
  concept does not report is absent; no other listed concept fills it. Overlapping concepts are never summed.
- **Values** were compared with the rendered income statement and cash-flow statement of the filings: Walmart (`R3`, `R8`),
  Alphabet (`R5`, `R10`), Moderna (`R5`), Monster (`R4`, `R7`) and Honeywell (`R3`, `R7`) for US GAAP, SAP (`R2`, `R6`) and
  Nutrien (`R2`, `R4`) for IFRS. A tick means the Company Facts value equals the rendered value to the filer's own rounding.
  A concept no checked filer shows on a face statement is "not checked".
- **Order differs from Slice inputs for revenue.** `Revenues` is listed before `RevenueFromContractWithCustomerExcludingAssessedTax`:
  Walmart tags both, net sales (706,413 million) as the second and total revenues (713,163) as the first, and the face total is the first.

| Field | Taxonomy | Concept list | Reported by (fiscal year of the anchor filing, millions) | Value check | Disposition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `SALES` | us-gaap | `Revenues`; `RevenueFromContractWithCustomerExcludingAssessedTax`; `RevenueFromContractWithCustomerIncludingAssessedTax` | First: JPM 182,447, PLD 8,790, DE 45,684, WMT 713,163, GOOGL 402,836. Second: MRNA 1,944, MNST 8,294, HON 37,442. Third: DUK 31,741 | WMT, GOOGL, MRNA, MNST, HON ✓ | Approved with a stated limit: the third concept (Duke Energy) and the first for JPM, PLD and DE were not rendered-checked |
| `SALES` | ifrs-full | `Revenue`; `RevenueFromContractsWithCustomers` | First: SAP 36,800. Second: NTR 26,885 (face "Sales") | SAP, NTR ✓ | Approved |
| `COST_OF_REVENUE` | us-gaap | `CostOfRevenue`; `CostOfGoodsAndServicesSold` | First: WMT 535,395, GOOGL 162,535. Second: MRNA 868, MNST 3,662, HON 23,613. Banks, PLD, DUK and DE tag neither | WMT, GOOGL, MRNA, MNST, HON ✓ | Approved with a stated limit: filers that report no cost line show none |
| `COST_OF_REVENUE` | ifrs-full | `CostOfSales` | SAP 9,986, NTR 17,602 | SAP, NTR ✓ | Approved |
| `GROSS_PROFIT` | us-gaap | `GrossProfit` | MNST 4,632 only | MNST ✓ | Approved with a stated limit: most filers report none, and gross profit is then sales less cost of revenue (computed by 3.5.2, never here) |
| `GROSS_PROFIT` | ifrs-full | `GrossProfit` | SAP 26,814, NTR 8,347 | SAP, NTR ✓ | Approved |
| `OPERATING_INCOME` | us-gaap | `OperatingIncomeLoss` | PLD 4,358, DUK 8,626, WMT 29,825, MRNA −3,074, MNST 2,419, GOOGL 129,039, HON 8,127; DE to fiscal 2024; JPM none | WMT, GOOGL, MRNA, MNST ✓; HON's has no face line (a note figure), not checked | Approved with a stated limit: a bank shows none |
| `OPERATING_INCOME` | ifrs-full | `ProfitLossFromOperatingActivities` | SAP 9,617, NTR 3,736 | SAP ✓; NTR ✓ against "Earnings before finance costs and income taxes", which includes other items | Approved with a stated limit: Nutrien's line is its earnings before finance costs |
| `SELLING_GENERAL_ADMINISTRATIVE` | us-gaap | `SellingGeneralAndAdministrativeExpense` | DE 4,663, WMT 147,943, HON 5,450. GOOGL reports sales and marketing (28,693) and general and administrative (21,482) apart; MRNA tags its "Selling, general and administrative" line (1,018) as general and administrative | WMT ✓ (face "Operating, selling, general and administrative expenses"), HON ✓ | Approved with a stated limit: a filer that reports the lines apart, or under another concept, shows none |
| `SELLING_GENERAL_ADMINISTRATIVE` | ifrs-full | none | SAP reports sales and marketing (8,879) and general and administration (1,633); NTR selling expenses (3,320) and general and administrative (600) | not applicable | Unsupported: no concept is the combined line, and the sum of two lines is not a reported figure. IFRS Beneish is therefore unavailable until the owner decides otherwise (SGAI has no value) |
| `DEPRECIATION_AND_AMORTIZATION` | us-gaap | `DepreciationDepletionAndAmortization`; `DepreciationAndAmortization`; `DepreciationAmortizationAndAccretionNet` | First: DUK 7,704, DE 2,229, MRNA 211, MNST 114, HON 1,388. Second: PLD 2,626. Third: JPM 8,821, WMT 14,203. GOOGL tags none (depreciation alone) | WMT ✓ (third concept = the face line), MNST ✓, HON ✓ (identity below) | Approved with a stated limit: the three are the cash-flow line of different filers; the third concept's name includes accretion and was checked only for Walmart |
| `DEPRECIATION_AND_AMORTIZATION` | ifrs-full | `DepreciationAndAmortisationExpense`; `AdjustmentsForDepreciationAndAmortisationExpense` | First: NTR 2,369 (tags both names at one value). Second: SAP 1,311 | SAP ✓, NTR ✓ | Approved |
| `DEPRECIATION` | us-gaap | `Depreciation` | GOOGL 21,136 ("Depreciation of property and equipment"), HON 546 | GOOGL ✓, HON ✓ | Approved with a stated limit: two of eleven issuers report it; Beneish's DEPI also needs net PP&E at the same dates ([§6](#6-depreciation-evidence)) |
| `DEPRECIATION` | ifrs-full | none | SAP tags depreciation of right-of-use assets only (275). NTR tags property, plant and equipment (1,633) and right-of-use assets (427) apart, and intangible amortization (242) apart; their sum is 2,302, not its 2,369 | not applicable | Unsupported: no concept is the year's depreciation, and parts that do not add to the combined figure are not a derivation. Every IFRS Beneish run uses the D&A basis |
| `INTEREST_EXPENSE` | us-gaap | `InterestExpense`; `InterestExpenseNonoperating` | First: DUK 3,634, DE 3,170, PLD 1,002 (PLD tags both with one value), JPM to 2023. Second: GOOGL 736. WMT's `InterestExpenseDebt` (2,318, with finance leases 481 apart) and HON's `InterestAndDebtExpense` (1,344, "Interest and other financial charges") are not this field | not on a face statement for the checked filers (GOOGL's is in a note): not checked | Approved with a stated limit: a filer that reports interest as debt interest and lease interest apart, or with other charges, shows none |
| `INTEREST_EXPENSE` | ifrs-full | `InterestExpense` | SAP 492 (of finance costs 1,377), NTR 746 (finance costs 687 after 71 of capitalized borrowing costs) | note-level, not checked | Approved with a stated limit: a gross interest figure from the notes, not the face's finance costs |
| `PRETAX_INCOME` | us-gaap | `IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest` | JPM 72,595, PLD 3,769, DUK 5,712, WMT 29,469, MRNA −2,768, MNST 2,483, GOOGL 158,826, HON 5,476. DE tags a longer concept that includes equity-method results (6,257) | WMT, GOOGL, MRNA, MNST, HON ✓ | Approved with a stated limit: Deere shows none |
| `PRETAX_INCOME` | ifrs-full | `ProfitLossBeforeTax` | SAP 10,270, NTR 3,049 | SAP, NTR ✓ | Approved |
| `INCOME_TAX_EXPENSE` | us-gaap | `IncomeTaxExpenseBenefit` | Nine of the eleven: JPM, PLD, DUK, DE, WMT, MRNA, MNST, GOOGL, HON | WMT, GOOGL, MRNA, MNST, HON ✓ | Approved |
| `INCOME_TAX_EXPENSE` | ifrs-full | `IncomeTaxExpenseContinuingOperations` | SAP 2,944, NTR 752 | SAP, NTR ✓ | Approved |
| `NET_INCOME` | us-gaap | `NetIncomeLoss` (attributable to the parent) | JPM 57,048, PLD 3,328, DUK 4,968, DE 5,027, WMT 21,893, MRNA −2,822, GOOGL 132,170, HON 4,729. MNST tags only `ProfitLoss` (1,905) | WMT, GOOGL, MRNA, HON ✓ | Approved with a stated limit: `ProfitLoss` includes the noncontrolling share (Walmart 22,270 against 21,893, Honeywell 4,772 against 4,729) and is not a stand-in, so a filer that tags only it (Monster, which has no noncontrolling interest) shows none |
| `NET_INCOME` | ifrs-full | `ProfitLossAttributableToOwnersOfParent` | SAP 7,161, NTR 2,267 | SAP, NTR ✓ | Approved |
| `INCOME_FROM_CONTINUING_OPERATIONS` | us-gaap | `IncomeLossFromContinuingOperations` (attributable to the parent) | DUK 4,911, HON 4,461 | HON by arithmetic: net income 4,729 less the parent's share of the discontinued result (268) is 4,461; the face's 4,468 includes the noncontrolling share | Approved with a stated limit: only two of eleven tag it, and the figure is the parent's share |
| `INCOME_FROM_CONTINUING_OPERATIONS` | ifrs-full | `IncomeFromContinuingOperationsAttributableToOwnersOfParent` | SAP 7,161 | SAP ✓ | Approved with a stated limit: only SAP tags it; Nutrien reports neither this nor a discontinued result |
| `DISCONTINUED_OPERATIONS` | us-gaap | `IncomeLossFromDiscontinuedOperationsNetOfTax` | DUK 1, HON 304 | HON ✓ (face "Net income from discontinued operations") | Approved with a stated limit: it includes the noncontrolling share; the parent's share (268) is another concept and is not mapped |
| `DISCONTINUED_OPERATIONS` | ifrs-full | `ProfitLossFromDiscontinuedOperations` | SAP 0 | SAP ✓ | Approved |

**What the new fields leave unavailable, by filer.** Bank (JPMorgan): cost of revenue, gross profit, operating income, SG&A. Alphabet: gross profit,
SG&A, and net PP&E for fiscal 2025 under the first concept. Walmart: gross profit, interest expense, continuing and discontinued income.
Moderna: SG&A. Monster: net income and interest expense. Deere: pre-tax income. Honeywell: interest expense and gross profit. Nutrien and SAP: SG&A and depreciation alone.

## 6. Depreciation evidence

The evidence [Slice inputs §3](STEP_3_5_SLICE_INPUTS.md#3-351--data-mappings-and-applicability) requires for Beneish's depreciation
index. The values are in [§5.7](#57-annual-field-mappings-slice-351c).

| Case | US GAAP | IFRS |
| :--- | :--- | :--- |
| A filing reporting depreciation alone | Alphabet, fiscal 2025: "Depreciation of property and equipment" 21,136 million (`Depreciation`) and no combined D&A concept | none: SAP tags only right-of-use depreciation (275), Nutrien tags property, plant and equipment (1,633) and right-of-use assets (427) apart |
| A filing reporting only combined D&A | Walmart 14,203, Monster 114, Moderna 211, Deere 2,229, Duke Energy 7,704, Prologis 2,626, JPMorgan 8,821 | SAP 1,311 (cash-flow adjustment) |
| A filing reporting both | Honeywell, fiscal 2023 to 2025: depreciation 490, 493 and 546 million and amortization (`AdjustmentForAmortization`) 514, 659 and 842 | Nutrien: D&A 2,369 beside depreciation of property, plant and equipment 1,633, of right-of-use assets 427 and amortization of intangibles 242 |

- **The identity D&A = depreciation + amortization** holds to the dollar for Honeywell in fiscal 2023 (490 + 514 = 1,004) and fiscal 2025
  (546 + 842 = 1,388); in fiscal 2024 the lines the filer rounds to millions differ by one million (493 + 659 = 1,152 against 1,153). The
  concepts mean what the table assumes. Under IFRS it does not close for Nutrien (1,633 + 427 + 242 = 2,302 against 2,369), so no IFRS
  depreciation concept is shown to be the year's depreciation.
- **The year's expense, not the accumulated balance.** `Depreciation` is a duration of a fiscal year in both filers (Alphabet 21,136 for
  2025; Honeywell 546 against an accumulated depreciation of 7,431 million at 2025-12-31). The accumulated balance is a different concept and is
  an instant.
- **Net PP&E for the same dates.** Honeywell tags only the finance-lease-inclusive concept (4,629 million at 2025-12-31, 4,457 at
  2024-12-31), and so does Moderna; Alphabet tags the plain concept to 2024 and the inclusive one at 2025. Both concepts are the filer's own
  face line, and the net PP&E mapping of 3.5.1b is extended to the pair (decision D12). With it, net PP&E is obtainable at the two year-ends
  for every filer that reports depreciation alone except Alphabet, whose concept changed between them (one concept per run: one year absent).
- **The DEPI algebra, by hand, against Honeywell's fiscal 2025 filing** (`0000773840-26-000013`). DEPI = [depreciation ÷ (depreciation +
  net PP&E)] of the prior year ÷ the same for the year = [493 ÷ (493 + 4,457)] ÷ [546 ÷ (546 + 4,629)] = 0.09960 ÷ 0.10551 = 0.944. A test
  repeats it from the captured facts.
- **Outcome.** The US GAAP depreciation-alone mapping is **approved with a stated limit**: two of eleven issuers tag it, and the index also
  needs net PP&E at both dates. The IFRS mapping is **unsupported**: every IFRS Beneish run uses the D&A basis, and an IFRS Beneish run is
  unavailable anyway while IFRS SG&A is unsupported ([§5.7](#57-annual-field-mappings-slice-351c)).

## 7. Not yet verified

- The header of a filing before 2001, and of a filer whose assigned code is blank. No filer checked lacked a code.
- That a filing in an amended form (10-K/A) carries the code of the original. Annual originals were used throughout.
- That Yahoo's list of stock dividends is complete (Commerce Bancshares, §4.2).
- That a split effective after a filing and announced before it is never reflected in that filing (§4.5).
- Any non-US exchange ticker. Only US listings were queried.
- Balance-sheet instants of a filer outside the ten of [§5.1](#51-the-regression-issuer-set): presence was read for ten
  issuers, and the value check for five filers' rendered statements.
- Filings before 2008 for the derived-total reconciliation, and the many US filers that tag no total equity including
  noncontrolling interest (the identity cannot be evaluated for them).
- A balance sheet where temporary equity is tagged under a concept other than the two named in
  [§5.4](#54-derived-totals); none was found in the set.

## Appendix A: Requests made

All on 2026-10-25. The identity the project configures was sent on every SEC request and is not recorded here. No raw
response is committed; the responses are under the ignored `.tmp/` folder.

**SEC EDGAR: 27 requests, 25 answered 200 and 2 answered 404.** Not above the budget of about 40.

| Pattern | Count |
| :--- | ---: |
| `data.sec.gov/submissions/CIK<cik>.json` (Riot, MARA, JPMorgan, Travelers, Prologis, Duke, Deere) | 7 |
| `www.sec.gov/Archives/edgar/data/<cik>/<accession, no dashes>/<accession>.hdr.sgml`, 14 answered 200 and 1 answered 404 (an accession that does not exist) | 15 |
| `data.sec.gov/api/xbrl/companyconcept/CIK<cik>/us-gaap/CommonStockSharesOutstanding.json` (NVIDIA, Walmart, Mastercard; Mastercard answered 404) | 3 |
| Annual-report primary document (NVIDIA fiscal 2024, Walmart fiscal 2024) | 2 |

The SAP and Nutrien accessions came from the checked-in fixture submissions, not from a request. A pause of 0.4 s separated each
request from the last.

**Slice 3.5.1b, 2026-10-25: 44 SEC requests, 43 answered 200 and 1 answered 503 and was repeated.** Under the budget of
about 60. A pause of 0.4 s separated each request from the last.

| Pattern | Count |
| :--- | ---: |
| `data.sec.gov/submissions/CIK<cik>.json` and `data.sec.gov/api/xbrl/companyfacts/CIK<cik>.json`, for the ten issuers of [§5.1](#51-the-regression-issuer-set) | 20 |
| `www.sec.gov/Archives/edgar/data/<cik>/<accession, no dashes>/FilingSummary.xml` (WMT, PLD, MNST, SAP, NTR) | 5 |
| The same folder's `R<n>.htm` rendered statements: Walmart (4), Monster (2), Prologis (2), Nutrien (1) | 9 |
| SAP's rendered statements and notes (`R2`, `R4`, `R94`, `R95`, `R146`, `R147`, `R161`, `R163`, and `R164` twice) | 10 |

**Yahoo: 8 chart requests** (one per `Ticker.history` or `Ticker.splits` call): NVIDIA history unadjusted and adjusted,
Apple history, and `Ticker.splits` for NVIDIA, Apple, Commerce Bancshares, Tootsie Roll and Walmart. The library's own
internal requests were not counted separately. Not above the budget of about 10.

**Slice 3.5.1b, decisions H7 to H12, 2026-10-25: 12 further SEC requests, all answered 200.** With the 44 above, 56 of
about 60. A pause of 0.4 s separated each request from the last.

| Pattern | Count |
| :--- | ---: |
| `data.sec.gov/submissions/CIK<cik>.json` and `data.sec.gov/api/xbrl/companyfacts/CIK<cik>.json`, Honeywell | 2 |
| `www.sec.gov/Archives/edgar/data/<cik>/<accession, no dashes>/R1.htm`, Nutrien's cover page | 1 |
| The same folders' rendered pages looked for the balance sheets of Alphabet and Moderna: Alphabet `R2`, `R5`, `R7`, `R8`, `R3`; Moderna `R2`, `R5`, `R7`, `R3`. Only Alphabet `R3` and Moderna `R3` were balance sheets | 9 |

The cover-page counts of the other issuers were read from the Company Facts already held under `.tmp/`.

**Review of the pull request, 2026-10-26: 3 further SEC requests, all answered 200.** With the 56 above, 59 of about 60. A
pause of 0.4 s separated each request from the last.

| Pattern | Count |
| :--- | ---: |
| `www.sec.gov/Archives/edgar/data/<cik>/<accession, no dashes>/FilingSummary.xml` and `R6.htm`, Duke Energy | 2 |
| `data.sec.gov/submissions/CIK0000019617-submissions-008.json`, JPMorgan | 1 |

**Slice 3.5.1c, 2026-10-26: 13 SEC requests, all answered 200.** Under the budget of about 60. A pause of 0.4 s separated each request from the
last.

| Pattern | Count |
| :--- | ---: |
| `www.sec.gov/Archives/edgar/data/<cik>/<accession, no dashes>/R<n>.htm` rendered statements: Walmart `R3` and `R8`, SAP `R6`, Nutrien `R2` and `R4`, Monster `R4` and `R7`, Alphabet `R9` (an equity page, read in error) and `R10`, Honeywell `R3` and `R7` | 11 |
| `.../FilingSummary.xml`, Honeywell | 1 |
| `data.sec.gov/submissions/CIK0000019617-submissions-018.json`, JPMorgan (the page of its fiscal 2023 report) | 1 |

The Company Facts, submissions and statements already held under `.tmp/` were read again without a request.
