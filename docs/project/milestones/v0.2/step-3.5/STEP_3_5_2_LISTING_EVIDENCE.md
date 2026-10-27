# Step 3.5 — Slice 3.5.2c Listing Evidence Record

Live source evidence behind the listing check of [slice 3.5.2c](STEP_3_5_2_SLICE_PLAN.md#352c--listing-check-for-market-capitalization):
which document of an annual filing carries the registered securities, how its rows are laid out, what each captured
cover lists for a ticker, and the title vocabulary those covers support. The rules are owned by
[Shared definitions §4](STEP_3_5_SHARED_DEFINITIONS.md#4-market-capitalization); the decisions drawn from this record are
P1 to P18 of [A.6](STEP_3_5_2_SLICE_PLAN.md#a6-decided-under-delegation-during-352c-2026-10-26). Nothing here overrides
either.

> **This document is not a test fixture and holds no executable expected data.** It records research observations used to
> design the slice and to choose fixtures. The tests read the trimmed covers under
> `investment_analysis_engine/evaluation/fixtures/sec_edgar/cover_pages/` and state their own expected values.

## 1. At a glance

- **Document chosen: the filing's rendered cover, `R1.htm`.** It is 34 to 136 KB across 22 captures. The primary document
  is 2.6 MB (Alphabet) and 4.1 MB (Adaptimmune), 25 and 58 times the cover of the same filing ([§3](#3-which-document)).
- **The depositary-share refusal is shown on a real 10-K filer:** Adaptimmune Therapeutics (`ADAP`, CIK 1621227,
  accession `0001558370-25-003544`, Form 10-K) lists "American Depositary Shares" and nothing else
  ([§5.3](#53-depositary-shares-refused)).
- **Alphabet's two classes are both affirmed,** `GOOGL` on "Class A Common Stock" and `GOOG` on "Class C Capital
  Stock" ([§5.1](#51-the-regression-issuer-set)).
- **Units, warrants and a preferred security are refused** on a blank-check company's cover and on Annaly's
  ([§5.4](#54-units-warrants-and-preferred-securities-refused)).
- **No `10-K/A` without a registration table was found** among seven amended covers, so decision (c) is the
  fail-closed rule ([§7](#7-amended-annual-reports)).
- **Nothing contradicts K5″, M2 or the limits of the delegation.**
- **A widened sample of 49 more covers** (the latest 10-K of large filers) raised the share tickers affirmed from 33 of
  50 to 47 of 50; the other three are unreadable covers, and none is `other` ([§5.6](#56-the-widened-sample)).
- **`.`, `-` and `/` are one separator** when a ticker is compared with a cover's symbol, shown by Berkshire Hathaway's
  `BRK.B` ([§5.6](#56-the-widened-sample), P17).
- **Three covers cannot be read:** Disney's first report is not the cover, and BlackRock's and Microsoft's rows run
  symbol before title (P18).
- **What it does not show:** coverage across the market. Seventy-one covers were read, and a title form not on one of
  them is not in the vocabulary ([§8](#8-not-yet-verified)).

## 2. Sources

1. SEC EDGAR rendered reports in a filing's archive folder at `www.sec.gov/Archives/edgar/data/`: `R1.htm` (the cover)
   and `FilingSummary.xml` (the list of reports).
2. SEC EDGAR submissions JSON at `data.sec.gov/submissions/`, for the accessions of Medtronic, Adaptimmune and Annaly.
3. SEC EDGAR full-text search at `efts.sec.gov/LATEST/search-index`, to find a blank-check company's 10-K and
   `10-K/A` filings. Its hits are leads only; every cover was then read from the archive.
4. The regression issuer set and its accessions come from
   [the 3.5.1 mapping evidence §5.1](STEP_3_5_1_MAPPING_EVIDENCE.md#51-the-regression-issuer-set).

All requests were made on 2026-10-26 and are listed in [Appendix A](#appendix-a-requests-made).

## 3. Which document

The check needs four facts of the anchor filing as filed: the registered title (`Security12bTitle`), the trading symbol,
the exchange and the registrant's CIK. Two documents of the accession folder carry them.

| Document | Size observed | Carries the facts | Notes |
| :--- | :--- | :--- | :--- |
| Rendered cover, `R1.htm` | 34,156 to 135,601 bytes over 22 covers (median about 77 KB) | Yes, as table rows named by their XBRL element | About a third of a page is the report table; the rest is hidden definitions. |
| Primary document (inline XBRL) | 2,616,620 bytes (Alphabet, fiscal 2025); 4,094,188 bytes (Adaptimmune, fiscal 2024) | Yes, as tagged facts with contexts | What Graham's verifier reads, under a bound of 8 MiB. |
| `FilingSummary.xml` | 55,785 (Alphabet), 60,504 (Annaly), 72,211 (Medtronic fiscal 2019) | No | Lists the reports; the cover was the first report, `R1.htm`, with category "Cover" and position 1, in all three. |

- **R1 was the cover in every capture.** All 22 pages have a report table with a `Document Type` row and an
  `Entity Central Index Key` row; 19 also have `Security12bTitle`, `TradingSymbol` and `SecurityExchangeName` rows.
  International Media Acquisition's two covers have `Security12gTitle` rows and no symbol, and Medtronic's fiscal 2019
  cover has no registration rows at all.
- **The page title differs** ("Cover", "Cover Page", "Document and Entity Information", "COVER PAGE", "Cover Page - USD
  ($)"), so the page is recognized by its rows, not its title.
- **Largest cover:** Duke Energy's combined filing of eight registrants, 135,601 bytes. The size limit is 512 KiB.
- **The page is delivered as it is served:** the response began with an SGML document wrapper around the HTML, which the
  reader ignores.

## 4. How a cover's rows are laid out

- **Each row names its concept.** The first cell links the XBRL element (`showAR( this, 'defref_dei_TradingSymbol', ...)`),
  and the label beside it is the filer's own. Annaly's covers label the title row "Title of Each Class" and the exchange
  row "Name of Each Exchange on Which Registered", Honeywell labels the key "Entity central index key", and the element
  is the same as on the other 20.
- **Values sit in the first period column,** and the other two (the cover date and the public-float date) are empty on
  the registration rows.
- **Row order varies.** Most covers give title, symbol and exchange in that order; Adaptimmune gives title, exchange and
  symbol. The registrant's key comes before the securities on some covers (Deere, Prologis, Duke Energy), after them on
  others (Moderna, Monster, Medtronic, Adaptimmune, IPG Photonics).
- **One security per group, one group per security.** Alphabet, JPMorgan, Walmart and Medtronic list a flat series of
  groups; Deere, Duke Energy, Honeywell and the blank-check company put a member label before each. Albemarle's
  amended cover lists each of its two securities twice, with identical values.
- **A combined filing** (Prologis, Duke Energy) gives each registrant a block with its own key. Prologis, Inc.'s block
  holds the common stock and Prologis, L.P.'s block holds its notes; Duke Energy's first block holds its own securities
  and the seven that follow list none. A nested table inside a cell (Walmart) does not add rows.
- **Cover-page tagging is recent.** Medtronic's fiscal 2019 cover (filed 2019-06-21) has a document type, a key and a
  share count, and no registered securities.

## 5. The captured cases

Every row is a cover read from the archive on 2026-10-26. "Title" is the registered title as filed, with its whitespace
collapsed. Accessions and keys are those of the filing read.

### 5.1 The regression issuer set

The 10-K filers of [the 3.5.1 mapping evidence §5.1](STEP_3_5_1_MAPPING_EVIDENCE.md#51-the-regression-issuer-set). SAP
(20-F) and Nutrien (40-F) file no 10-K and have no cover here; the market-cap function refuses them by form.

| Issuer | Ticker | CIK | Accession (form) | Title as filed | Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| JPMorgan Chase | JPM | 19617 | `0001628280-26-008131` (10-K) | Common stock | Share, affirmed |
| Prologis | PLD | 1045609 | `0001193125-26-051453` (10-K) | Common Stock, $0.01 par value | Share, affirmed |
| Duke Energy | DUK | 1326160 | `0001326160-26-000014` (10-K) | Common Stock, $0.001 par value | Share, affirmed |
| Deere | DE | 315189 | `0001104659-25-122321` (10-K) | Common stock, $1 par value | Share, affirmed |
| Walmart | WMT | 104169 | `0000104169-26-000055` (10-K) | Common Stock, par value $0.10 per share | Share, affirmed |
| Moderna | MRNA | 1682852 | `0001682852-26-000033` (10-K) | Common stock, par value $0.0001 per share | Share, affirmed |
| Monster Beverage | MNST | 865752 | `0001104659-26-020831` (10-K) | Common Stock, $0.005 par value per share | Share, affirmed |
| Alphabet | GOOGL | 1652044 | `0001652044-26-000018` (10-K) | Class A Common Stock, $0.001 par value | Share, affirmed |
| Alphabet | GOOG | 1652044 | `0001652044-26-000018` (10-K) | Class C Capital Stock, $0.001 par value | Share, affirmed |
| Honeywell | HON | 773840 | `0000773840-26-000013` (10-K) | Common Stock, par value $1 per share | Share, affirmed |

- **The requested ticker's row decides.** JPMorgan's cover lists the common stock beside six series of depositary shares
  of preferred stock (`JPM PR D`, `JPM PR C`, `JPM PR J`, `JPM PR K`, `JPM PR L`, `JPM PR M`, among 10 registered
  titles); `JPM` is a share and `JPM PR D` is a depositary share. Alphabet's cover lists eleven series of senior notes
  beside the two classes.
- **Other registered securities on these covers are not shares:** Walmart's notes (`WMT26`), Deere's debentures
  (`DE28`), Duke Energy's junior subordinated debentures (`DUKB`) and depositary shares (`DUK PR A`).
- **Prologis:** `PLD/29` (Prologis, L.P.'s 2.250% notes) is under another registrant's key, so it is not listed for
  Prologis, Inc.

### 5.2 Ordinary shares

| Issuer | Ticker | CIK | Accession (form) | Title as filed | Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Medtronic plc | MDT | 1613103 | `0001628280-26-044354` (10-K, filed 2026-06-18) | Ordinary shares, par value $0.0001 per share | Share, affirmed |
| Aldel Financial II (blank check) | ALDF | 2031561 | `0001104659-26-033988` (10-K, filed 2026-03-25) | Ordinary Shares | Share, affirmed |
| Annaly Capital Management | NLY | 1043219 | `0001043219-26-000013` (10-K, filed 2026-02-12) | Common Stock, par value $0.01 per share | Share, affirmed |

Medtronic's cover also lists 19 series of senior notes (`MDT/27` and others), which are not shares.

### 5.3 Depositary shares refused

| Issuer | Ticker | CIK | Accession (form) | Title as filed | Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Adaptimmune Therapeutics** | ADAP | 1621227 | `0001558370-25-003544` (10-K, filed 2025-03-24) | American Depositary Shares, each representing | Depositary share, `incompatible_units` |
| JPMorgan Chase | JPM PR D | 19617 | `0001628280-26-008131` (10-K) | Depositary Shares, each representing a one-four hundredth interest in a share of 5.75% Non-Cumulative Preferred Stock, Series DD | Depositary share, `incompatible_units` |
| Duke Energy | DUK PR A | 1326160 | `0001326160-26-000014` (10-K) | Depositary Shares | Depositary share, `incompatible_units` |
| Albemarle (10-K/A) | ALB PR A | 915913 | `0000915913-26-000060` (10-K/A, filed 2026-03-31) | DEPOSITARY SHARES, each representing a 1/20th interest in a share of 7.25% Series A Mandatory Convertible Preferred Stock | Depositary share, `incompatible_units` |

- **Adaptimmune is the real 10-K filer whose listed security is a depositary share.** It is a UK company that filed a Form
  10-K for fiscal 2024; its cover registers the American Depositary Shares as its only security under Section 12(b), with
  symbol `ADAP` on Nasdaq. Its submissions data lists today's ticker as `ADAPY`, which does not match the cover of the
  anchor filing: a renamed ticker is `not_listed`, the limitation K5″ states.
- **The brief's other candidate, Mereo BioPharma, was not needed.**

### 5.4 Units, warrants and preferred securities refused

| Issuer | Ticker | CIK | Accession (form) | Title as filed | Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Aldel Financial II (blank check) | ALDF.U | 2031561 | `0001104659-26-033988` (10-K) | Units | Unit, `incompatible_units` |
| Aldel Financial II (blank check) | ALDF.W | 2031561 | `0001104659-26-033988` (10-K) | Warrants | Warrant, `incompatible_units` |
| Pantages Capital Acquisition (blank check) | PGACU | 2030829 | `0001213900-26-049303` (10-K/A, filed 2026-04-29) | Units, consisting of one Class A ordinary share, $0.0001 par value, and one Right to acquire one-fifth of one Class A ordinary share | Unit, `incompatible_units` |
| Annaly Capital Management | NLY.F | 1043219 | `0001043219-26-000013` (10-K) | 6.95% Series F Fixed-to-Floating Rate Cumulative Redeemable Preferred Stock | Preferred, `incompatible_units` |

- **The blank-check company's share ticker (`ALDF`) is affirmed** on "Ordinary Shares" ([§5.2](#52-ordinary-shares)).
- **Pantages** lists its Class A ordinary shares (`PGAC`) as a share, its rights (`PGACR`, "Rights, each whole right to
  acquire one-fifth of one Class A ordinary share") outside the vocabulary, and its units (`PGACU`) as units.
- **The brief's "redeemable warrants" title** does not appear on a captured cover: the blank-check company's title is
  "Warrants". Titles beginning "Redeemable warrants" are outside the vocabulary (`other`, `missing_fact`).
- **Annaly lists four preferred series** (`NLY.F`, `NLY.G`, `NLY.I`, `NLY.J`), each ending "Preferred Stock". Its
  submissions data lists the tickers as `NLY-PF`, `NLY-PG` and `NLY-PJ`. P17 reads `.`, `-` and `/` as one separator,
  but `NLY-PF` and `NLY.F` also differ in the `P`, so they do not match and `NLY-PF` is `not_listed` (`missing_fact`);
  market cap is refused for a preferred security either way.

### 5.5 Not listed, and no table

| Issuer | Ticker | CIK | Accession (form) | What the cover holds | Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| International Media Acquisition | IMAQ | 1846235 | `0001213900-26-072115` (10-K, filed 2026-06-25) | Four Section 12(g) titles (common stock, warrants, rights, units), no symbol, no exchange | Not listed, `missing_fact` |
| Medtronic plc (fiscal 2019) | MDT | 1613103 | `0001613103-19-000028` (10-K, filed 2019-06-21) | Document type, key, a share count; no registered securities | No registration table, `missing_fact` |

### 5.6 The widened sample

The review that followed asked for the rendered cover of the latest 10-K of about 50 more large US filers, among
those whose titles were expected to differ. 49 covers were captured (the latest 10-K in each issuer's submissions data,
read on 2026-10-27); Berkshire Hathaway, Procter & Gamble, Exxon Mobil, PepsiCo, Caterpillar and Nike are among them.
Every row below is a registered security with a symbol whose title names common stock, common shares, ordinary shares or
capital stock; its outcome is the one the check gives with the vocabulary of P7.

- **Before the widening: 33 of 50 share tickers affirmed (66%).** The other 17 were 14 titles outside the vocabulary
  (class B common stock, "without par value", "no par value", a parenthesized par value, par value in cents, in Swiss
  francs, as a mixed fraction, and a euro nominal value) and 3 unreadable covers.
- **After: 47 of 50 affirmed (94%).** Each added form is explicit and backed by the cover named in [§6](#6-the-title-vocabulary).
- **Still not affirmed: three share tickers, all unreadable covers, none `other`.** `MSFT` (rows run symbol, title,
  exchange), `BLK` (the same) and `DIS` (the first report is the audit information, not the cover).
- **Exxon Mobil's cover is under CIK 34088,** while the SEC's ticker file maps `XOM` to CIK 2115436, which holds no 10-K
  yet. A run that resolves `XOM` to the newer key would meet `cik_mismatch` on that cover.

| Issuer | Ticker | CIK | Accession (10-K) | Title as filed | Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- |
| Berkshire Hathaway | BRK.A | 1067983 | `0001193125-26-083899` | Class A Common Stock | Share, affirmed |
| Berkshire Hathaway | BRK.B | 1067983 | `0001193125-26-083899` | Class B Common Stock | Share, affirmed (form added) |
| Procter & Gamble | PG | 80424 | `0000080424-26-000103` | Common Stock, without Par Value | Share, affirmed (form added) |
| PepsiCo | PEP | 77476 | `0000077476-26-000007` | Common Stock, par value 1-2/3 cents per share | Share, affirmed (form added) |
| Caterpillar | CAT | 18230 | `0000018230-26-000008` | Common Stock ($1.00 par value) | Share, affirmed (form added) |
| Nike | NKE | 320187 | `0000320187-26-000088` | Class B Common Stock | Share, affirmed (form added) |
| Accenture | ACN | 1467373 | `0001467373-26-000049` | Class A ordinary shares, par value $0.0000225 per share | Share, affirmed |
| Linde | LIN | 1707925 | `0001628280-26-011430` | Ordinary shares (€0.001 nominal value per share) | Share, affirmed (form added) |
| Chubb | CB | 896159 | `0000896159-26-000005` | Common Shares, par value CHF 0.50 per share | Share, affirmed (form added) |
| Apple | AAPL | 320193 | `0000320193-25-000079` | Common Stock, $0.00001 par value per share | Share, affirmed |
| Microsoft | MSFT | 789019 | `0001193125-26-323660` | Common stock, $0.00000625 par value per share | Unreadable cover (symbol row before its title), `missing_fact` |
| Amazon | AMZN | 1018724 | `0001018724-26-000004` | Common Stock, par value $.01 per share | Share, affirmed |
| Meta Platforms | META | 1326801 | `0001628280-26-003942` | Class A Common Stock, $0.000006 par value | Share, affirmed |
| NVIDIA | NVDA | 1045810 | `0001045810-26-000021` | Common Stock, $0.001 par value per share | Share, affirmed |
| Tesla | TSLA | 1318605 | `0001628280-26-003952` | Common stock | Share, affirmed |
| Coca-Cola | KO | 21344 | `0001628280-26-010047` | Common Stock, $0.25 Par Value | Share, affirmed |
| Johnson & Johnson | JNJ | 200406 | `0000200406-26-000016` | Common Stock, Par Value $1.00 | Share, affirmed |
| Visa | V | 1403161 | `0001403161-25-000089` | Class A Common Stock, par value $0.0001 per share | Share, affirmed |
| Mastercard | MA | 1141391 | `0001141391-26-000013` | Class A Common Stock, par value $0.0001 per share | Share, affirmed |
| UnitedHealth | UNH | 731766 | `0000731766-26-000062` | Common Stock, $.01 par value | Share, affirmed |
| Home Depot | HD | 354950 | `0001628280-26-019436` | Common Stock, $0.05 Par Value Per Share | Share, affirmed |
| Chevron | CVX | 93410 | `0000093410-26-000078` | Common stock, par value $.75 per share | Share, affirmed |
| Eli Lilly | LLY | 59478 | `0000059478-26-000013` | Common Stock (no par value) | Share, affirmed (form added) |
| Merck | MRK | 310158 | `0000310158-26-000063` | Common Stock ($0.50 par value) | Share, affirmed (form added) |
| Costco | COST | 909832 | `0000909832-26-000093` | Common Stock, $.005 Par Value | Share, affirmed |
| Broadcom | AVGO | 1730168 | `0001730168-25-000121` | Common Stock, $0.001 par value | Share, affirmed |
| Oracle | ORCL | 1341439 | `0001193125-26-277521` | Common Stock, par value $0.01 per share | Share, affirmed |
| Cisco | CSCO | 858877 | `0000858877-26-000132` | Common Stock, par value $0.001 per share | Share, affirmed |
| GE Aerospace | GE | 40545 | `0000040545-26-000008` | Common stock, par value $0.01 per share | Share, affirmed |
| Lockheed Martin | LMT | 936468 | `0001628280-26-004195` | Common Stock, $1 par value | Share, affirmed |
| Boeing | BA | 12927 | `0001628280-26-004357` | Common Stock, $5.00 Par Value | Share, affirmed |
| United Parcel Service | UPS | 1090727 | `0001628280-26-008432` | Class B common stock, par value $0.01 per share | Share, affirmed (form added) |
| Walt Disney | DIS | 1744489 | `0001744489-25-000155` | Audit information, not the cover (first report) | Unreadable cover, `missing_fact` |
| Comcast | CMCSA | 1166691 | `0001628280-26-004994` | Class A Common Stock, $0.01 par value | Share, affirmed |
| Verizon | VZ | 732712 | `0000732712-26-000007` | Common Stock, par value $0.10 | Share, affirmed |
| AT&T | T | 732717 | `0000732717-26-000120` | Common Shares (Par Value $1.00 Per Share) | Share, affirmed (form added) |
| McDonald's | MCD | 63908 | `0000063908-26-000035` | Common Stock, $0.01 par value | Share, affirmed |
| American Express | AXP | 4962 | `0000004962-26-000080` | Common Shares (par value $0.20 per Share) | Share, affirmed (form added) |
| Goldman Sachs | GS | 886982 | `0000886982-26-000091` | Common stock, par value $0.01 per share | Share, affirmed |
| Bank of America | BAC | 70858 | `0000070858-26-000157` | Common Stock, par value $0.01 per share | Share, affirmed |
| Citigroup | C | 831001 | `0000831001-26-000011` | Common Stock, par value $.01 per share | Share, affirmed |
| Wells Fargo | WFC | 72971 | `0000072971-26-000133` | Common Stock, par value $1-2/3 | Share, affirmed (form added) |
| BlackRock | BLK | 2012383 | `0001193125-26-071966` | Common Stock, $.01 par value | Unreadable cover (symbol row before its title), `missing_fact` |
| T-Mobile US | TMUS | 1283699 | `0001283699-26-000010` | Common Stock, par value $0.00001 per share | Share, affirmed |
| Ford | F | 37996 | `0000037996-26-000015` | Common Stock, par value $.01 per share | Share, affirmed |
| General Motors | GM | 1467858 | `0001467858-26-000013` | Common Stock, $0.01 par value | Share, affirmed |
| FedEx | FDX | 1048911 | `0001048911-26-000105` | Common Stock, par value $0.10 per share | Share, affirmed |
| Dow | DOW | 1751788 | `0001751788-26-000018` | Common Stock, par value $0.01 per share | Share, affirmed |
| AbbVie | ABBV | 1551152 | `0001551152-26-000008` | Common Stock, par value $0.01 per share | Share, affirmed |
| Exxon Mobil | XOM | 34088 | `0000034088-26-000045` | Common Stock, without par value | Share, affirmed (form added) |

### 5.7 Other securities on the widened covers

Across the 46 readable covers whose rows the reader takes in order, the check classifies 316 registered securities: 48
shares, 26 depositary shares (Oracle, Boeing, AT&T, Goldman Sachs, Bank of America and Wells Fargo among them,
refused with `incompatible_units`), 2 preferred securities (`BAC PrL` and `WFC.PRL`, each "Preferred Stock, Series L",
refused) and 240 others, all `missing_fact`.

- **Others are debt and hybrids:** notes, senior notes, debentures, guarantees of a subsidiary's notes (Chubb, Wells
  Fargo), medium-term notes (Goldman Sachs, Bank of America), trust-preferred securities and hybrid income term
  securities (Citigroup, Goldman Sachs, Bank of America), and Citigroup's "Dividend Equalization Preferred Shares", which
  has no symbol.
- **Visa's Class B-1, B-2 and C common stock** have no trading symbol on the cover, so no ticker reaches them.
- **Citigroup's "Dep Shs, represent 1/1,000th interest in a share of 6.250% Noncum Pref Stk, Ser II" (`C PR R`)** is a
  depositary share by its first words, and is refused as one.

## 6. The title vocabulary

The vocabulary is an explicit list. A designation is a title, lower-cased with its whitespace collapsed, optionally
followed by one par-value clause; the list below gives the cover that backs each form.

| Form | Backing cover (ticker, CIK, accession) |
| :--- | :--- |
| "common stock" alone | JPM, 19617, `0001628280-26-008131` |
| "common stock, $X par value" | PLD, 1045609, `0001193125-26-051453`; DE, 315189, `0001104659-25-122321`; ALB (10-K/A), 915913, `0000915913-26-000060` ("$.01") |
| "common stock, par value $X per share" | WMT, 104169, `0000104169-26-000055`; MRNA, 1682852, `0001682852-26-000033`; HON, 773840, `0000773840-26-000013`; NLY, 1043219, `0001043219-26-000013`; IPGP (10-K/A), 1111928, `0001111928-26-000068` |
| "common stock, $X par value per share" | MNST, 865752, `0001104659-26-020831` |
| "common stock, par value $X" | EGY (10-K/A), 894627, `0000894627-26-000017` |
| "common stock $X par value" (no comma) | INVA (10-K/A), 1080014, `0001193125-26-128939` |
| "common shares, par value $X per share" | OFG (10-K/A), 1030469, `0001030469-26-000019` |
| "ordinary shares, par value $X per share" | MDT, 1613103, `0001628280-26-044354` |
| "ordinary shares" alone | ALDF, 2031561, `0001104659-26-033988` |
| "class a common stock, $X par value" | GOOGL, 1652044, `0001652044-26-000018` |
| "class c capital stock, $X par value" | GOOG, 1652044, `0001652044-26-000018` |
| "class a ordinary shares, par value $X per share" | PGAC (10-K/A), 2030829, `0001213900-26-049303` |
| "class b common stock" alone | BRK.B, 1067983, `0001193125-26-083899`; NKE, 320187, `0000320187-26-000088` |
| "class b common stock, par value $X per share" | UPS, 1090727, `0001628280-26-008432` |
| "common stock, without par value" | PG, 80424, `0000080424-26-000103`; XOM, 34088, `0000034088-26-000045` |
| "common stock (no par value)" | LLY, 59478, `0000059478-26-000013` |
| "common stock ($X par value)" | CAT, 18230, `0000018230-26-000008`; MRK, 310158, `0000310158-26-000063` |
| "common shares (par value $X per share)" | T, 732717, `0000732717-26-000120`; AXP, 4962, `0000004962-26-000080` |
| "common stock, par value $X" with a mixed fraction (`$1-2/3`) | WFC, 72971, `0000072971-26-000133` |
| "common stock, par value N-N/N cents per share" | PEP, 77476, `0000077476-26-000007` |
| "common shares, par value CHF X per share" | CB, 896159, `0000896159-26-000005` |
| "ordinary shares (€X nominal value per share)" | LIN, 1707925, `0001628280-26-011430` |

- **Affirmed (a share of the issuer):** a title in the list above.
- **Refused as `incompatible_units`:** a title beginning "depositary shares" or "american depositary shares" (ADAP, JPM
  PR D, DUK PR A, ALB PR A); beginning "dep shs" (C PR R); beginning "units" (ALDF.U, PGACU); beginning "warrants" (ALDF.W); ending
  "preferred stock" (NLY.F); or ending "preferred stock, series" and a letter (BAC PrL, WFC.PRL).
- **Refused as `missing_fact`:** a title outside both lists (notes, debentures, guarantees, rights, and any class
  designation not in the list, such as "Class B-1 common stock"), a ticker the cover does not list, and a cover that
  cannot be read.
- **A par-value amount** is a dollar sign followed by digits with an optional decimal part (`$1`, `$0.0001`, `$.01`) or
  by a mixed fraction (`$1-2/3`). A par value in Swiss francs, in cents, or as a euro nominal value is one explicit
  clause each (CB, PEP, LIN); "no par value" without parentheses is outside the vocabulary.
- **Ticker comparison:** a cover's symbol and the requested ticker are compared with `.`, `-` and `/` read as one
  separator (P17); a separator is never removed (`BRKB` is not `BRK.B`).

## 7. Amended annual reports

Decision (c) of the delegation asked what to do when the anchor filing is a `10-K/A` whose cover lacks the registration
table. Seven amended covers were read.

| Issuer | CIK | Accession (filed) | What the amended cover holds |
| :--- | :--- | :--- | :--- |
| Albemarle | 915913 | `0000915913-26-000060` (2026-03-31) | The full table: common stock and depositary shares, each twice |
| IPG Photonics | 1111928 | `0001111928-26-000068` (2026-03-06) | The full table: common stock |
| VAALCO Energy | 894627 | `0000894627-26-000017` (2026-03-20) | The full table: common stock |
| OFG Bancorp | 1030469 | `0001030469-26-000019` (2026-03-05) | The full table: common shares |
| Innoviva | 1080014 | `0001193125-26-128939` (2026-03-27) | The full table: common stock |
| Pantages Capital Acquisition | 2030829 | `0001213900-26-049303` (2026-04-29) | The full table: units, Class A ordinary shares, rights |
| International Media Acquisition | 1846235 | `0001213900-26-072601` (2026-06-26) | Four Section 12(g) titles, no symbol; the original filed one day earlier is identical |

- **All seven carry a registration section,** so none shows the case. The seven came from two full-text searches (533 hits for
  `10-K/A` filings of 2026, 247 for blank-check filings), of which the first 100 hits of each were listed; the reading
  stopped at the budget.
- **Decision:** an amended anchor filing is read as itself, and an amended cover without the table is
  `no_registration_table`, which is `missing_fact`. The original 10-K's cover is not read: the snapshot holds no link from
  an amendment to its original, and a second request would be a guess about which filing it is.

## 8. Not yet verified

- **Coverage.** Seventy-one covers were read: 22 first and 49 in the widened sample. A title form on none of them is
  outside the vocabulary, and the outcome for it is a refusal.
- **Class designations other than A, B and C.** Visa's Class B-1, B-2 and C common stock appear on its cover without a
  symbol; no listed security carries them.
- **Preference shares, "shares of beneficial interest", ADS of a 10-K filer with a different phrasing** and other forms
  common outside the captured covers.
- **Ticker forms.** Covers print `JPM PR D`, `ALDF.U`, `NLY.F` and `MDT/27`, while data vendors write `NLY-PF` or
  `ALDFU`. Only the separator is read as the same (P17); a ticker that differs in more is `not_listed`.
- **Covers before cover-page tagging.** One was read (Medtronic fiscal 2019). A run with an early `as_of` meets more of
  them and gets `no_registration_table`.
- **An anchor filing whose first report is not the cover.** One was found in the widened sample (Disney); the reader
  refuses it (P2, P18). How often it happens among all filers is not known.
- **A cover whose symbol row precedes its title.** Two were found (BlackRock, Microsoft); the reader refuses them (P18).

---

## Appendix A: Requests made

All on 2026-10-26. The identity the project configures was sent on every SEC request and is not recorded here. No raw
response is committed; the responses are under the ignored `.tmp/` folder.

**SEC EDGAR: 37 requests, 36 answered 200 and 1 answered 500 and was not repeated.** Above the "about 30" of the
approval and under the limit of 40.

| Pattern | Count |
| :--- | ---: |
| `www.sec.gov/Archives/edgar/data/<cik>/<accession, no dashes>/R1.htm`: nine regression-set covers, thirteen others, and the one request of the live check | 23 |
| `.../FilingSummary.xml` (Alphabet, Annaly, Medtronic fiscal 2019) | 3 |
| `data.sec.gov/submissions/CIK<cik>.json` (Medtronic, Adaptimmune, Annaly) | 3 |
| `efts.sec.gov/LATEST/search-index` full-text search: a blank-check company's 10-K (one answered 500, one 200) and `10-K/A` filings (one 200) | 3 |
| Primary documents, for their sizes: three `HEAD` requests, which gave no length, and two full reads of Alphabet's and Adaptimmune's | 5 |

The `HEAD` requests returned no `Content-Length`, which is why two documents were read in full to count their bytes.
A pause of 0.5 s separated each request from the last.

**The widened sample, 2026-10-27: 100 requests, all answered 200.** Under the review's limit of 110.

| Pattern | Count |
| :--- | ---: |
| `www.sec.gov/files/company_tickers.json`, for the ticker to CIK map | 1 |
| `data.sec.gov/submissions/CIK<cik>.json`, one per issuer; the first Exxon Mobil request used the key the ticker file gives, which holds no 10-K, and the second the key its 10-K is filed under | 50 |
| `www.sec.gov/Archives/edgar/data/<cik>/<accession, no dashes>/R1.htm`, the latest 10-K of each of 49 issuers | 49 |

The identity the project configures was sent on every request and is not recorded here. A pause of 0.25 s separated each
request from the last. No raw response is committed; the responses are under the ignored `.tmp/` folder, and the
committed fixtures are trimmed to the 13 covers that add a title form, a refusal or a cover that cannot be read.
