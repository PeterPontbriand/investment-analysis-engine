# Step 3.5 — Slice 3.5.1 Mapping Evidence Record

Live source evidence behind the 3.5.1 slice plan: where a filing's as-filed SIC code comes from, how Yahoo adjusts its
price history, and (filled in by the later sub-slices) the field mappings and depreciation evidence. Rules and
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
- **Field mappings and depreciation evidence:** empty. 3.5.1b and 3.5.1c fill them ([§5](#5-field-mappings),
  [§6](#6-depreciation-evidence)).
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

Empty. Slices 3.5.1b (balance-sheet instants) and 3.5.1c (annual period fields) fill it, one row per field and
taxonomy, for every field of [Slice inputs §3](STEP_3_5_SLICE_INPUTS.md#3-351--data-mappings-and-applicability). Each
row records:

| Column | Content |
| :--- | :--- |
| Field | The `FinancialField` name |
| Taxonomy | `us-gaap` or `ifrs-full` |
| Concept | The exact element, or the priority list of elements |
| Units and scale | The XBRL unit, and the scale the filer applies |
| Kind | A period amount or a balance at a date |
| Reported by | The filer populations that report it, and what the others report instead |
| Disposition | Approved, approved with a stated limit, or unsupported |

## 6. Depreciation evidence

Empty. Slice 3.5.1c fills it with the evidence [Slice inputs §3](STEP_3_5_SLICE_INPUTS.md#3-351--data-mappings-and-applicability)
requires for Beneish's depreciation index.

## 7. Not yet verified

- The header of a filing before 2001, and of a filer whose assigned code is blank. No filer checked lacked a code.
- That a filing in an amended form (10-K/A) carries the code of the original. Annual originals were used throughout.
- That Yahoo's list of stock dividends is complete (Commerce Bancshares, §4.2).
- That a split effective after a filing and announced before it is never reflected in that filing (§4.5).
- Any non-US exchange ticker. Only US listings were queried.

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

**Yahoo: 8 chart requests** (one per `Ticker.history` or `Ticker.splits` call): NVIDIA history unadjusted and adjusted,
Apple history, and `Ticker.splits` for NVIDIA, Apple, Commerce Bancshares, Tootsie Roll and Walmart. The library's own
internal requests were not counted separately. Not above the budget of about 10.
