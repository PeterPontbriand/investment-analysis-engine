# Listing Venue Mapping Record

Records the captured specimen behind every value in the three listing-venue tables of
`investment_analysis_engine/data/listing_venue.py`, and what was found about the values the tables leave out. Decisions
are in [A.19](API_CONTRACT_AND_SLICE_PLAN.md#a19-listing-venue-codes-2026-11-23); the slice is
[API.22](API_CONTRACT_AND_SLICE_PLAN.md#api22--listing-venue-codes).

A value is mapped only when it was captured from its source, and a code means exactly what the source asserts. Every
capture below was made on 2026-11-22 or 2026-11-23, read-only, from the live source. Yahoo values come from the
repository's installed `yfinance` through `Ticker.info`; the filing covers are the `ix:nonNumeric` facts named
`dei:SecurityExchangeName` of the filing's main document; SEC's file is the real
`https://www.sec.gov/files/company_tickers_exchange.json`.

## 1. The codes

| Code | Means | Named by |
| :--- | :--- | :--- |
| `nasdaq` | The Nasdaq Stock Market, any of its tiers | all three sources |
| `nyse` | The New York Stock Exchange | Yahoo, the cover |
| `nyse_group` | One exchange of the NYSE group, which the source does not name | SEC's file, the cover's bare `NYSE` |
| `nyse_arca` | NYSE Arca | Yahoo, the cover |
| `nyse_american` | NYSE American | Yahoo, the cover |
| `cboe` | One of the Cboe group's U.S. equities exchanges, which the source does not name | SEC's file, Yahoo |
| `cboe_bzx` | Cboe BZX Exchange | the cover |
| `txse` | The Texas Stock Exchange | SEC's file, Yahoo |
| `otc` | The over-the-counter market | SEC's file, Yahoo |

A code is exchange-level when the source names one exchange and group-level when it names only the group
([A.19](API_CONTRACT_AND_SLICE_PLAN.md#a19-listing-venue-codes-2026-11-23), V4 as amended).

## 2. SEC's ticker file

The file held 10,399 rows with these exchanges: `Nasdaq` 4357, `NYSE` 3257, `OTC` 2572, `CBOE` 44, `TXSE` 14 and
`null` 155. The `null` rows have no venue and map to no part.

| SEC value | Code | Specimen |
| :--- | :--- | :--- |
| `Nasdaq` | `nasdaq` | AAPL, NVDA, MSFT |
| `NYSE` | `nyse_group` | KO, SPY, GLD, BTG, UEC (see below) |
| `OTC` | `otc` | CYATY, RTNTF, DTEGY, HTHIY |
| `CBOE` | `cboe` | FBTC, HODL, VXX, CBOE |
| `TXSE` | `txse` | ET, SUN, DDS, TXCP, CFR |

### 2.1 SEC's `NYSE` names a group

Yahoo's `fullExchangeName` for tickers SEC lists as `NYSE`:

| Ticker | SEC | Yahoo `exchange` | Yahoo `fullExchangeName` |
| :--- | :--- | :--- | :--- |
| KO | `NYSE` | `NYQ` | `NYSE` |
| SPY, GLD | `NYSE` | `PCX` | `NYSEArca` |
| BTG, UEC, UUUU, IDR, URG, CVU | `NYSE` | `ASE` | `NYSE American` |

SEC's `NYSE` therefore covers the New York Stock Exchange, NYSE American and NYSE Arca, and the file says which only by
ticker. It maps to the group-level `nyse_group`.

### 2.2 SEC's `CBOE`

FBTC, VXX and ARKB are `Cboe US` at Yahoo and their covers name Cboe BZX. Neither SEC's file nor Yahoo says which Cboe
U.S. equities exchange, so both map to the group-level `cboe`.

## 3. Yahoo

`fullExchangeName` is used when present; `exchange` is the identity's fallback, so both are mapped.

| `fullExchangeName` | `exchange` | Code | Specimen |
| :--- | :--- | :--- | :--- |
| `NasdaqGS` | `NMS` | `nasdaq` | AAPL, NVDA, MSFT |
| `NasdaqGM` | `NGM` | `nasdaq` | BITF, LUNR |
| `NasdaqCM` | `NCM` | `nasdaq` | SNDL, RGTI, MARA |
| `NYSE` | `NYQ` | `nyse` | KO, UAMY, IONQ |
| `NYSEArca` | `PCX` | `nyse_arca` | SPY, GLD |
| `NYSE American` | `ASE` | `nyse_american` | BTG, UEC, UUUU, IDR, URG, CVU |
| `Cboe US` | `BTS` | `cboe` | FBTC, VXX, ARKB, CBOE |
| `TXSE` | `TEX` | `txse` | ET, SUN, DDS, TXCP |
| `OTC Markets OTCPK` | `PNK` | `otc` | TCEHY |
| `OTC Markets OTCID` | `OID` | `otc` | NSRGY |
| `OTC Markets OTCQX` | `OQX` | `otc` | OTCM |

### 3.1 Values left unmapped

- `CCC` (BTC-USD and ETH-USD, both fields). No source was found for what Yahoo means by `CCC`. A web search found only
  that Yahoo's cryptocurrency data comes from CoinMarketCap, and nothing about the code. It is unmapped (`code: null`),
  and the Listing Venue term says a cryptocurrency's venue text may name where its price comes from.
- Non-US venues, which no strategy has evidence of using: `Toronto` (SHOP.TO), `LSE` (VOD.L) and `Tokyo` (7203.T) were
  observed and are unmapped.
- Any other value Yahoo writes, such as an OTC tier not listed above, until it is captured.

### 3.2 A venue is as the provider reports it

ET, SUN and DDS are `TXSE` at Yahoo, and SEC's file also lists them as `TXSE`, so the two sources agree on these
tickers. This capture found no ticker whose Yahoo venue disagrees with SEC's, but a provider's venue can name a
secondary listing rather than the primary one, so the Listing Venue term says only that the venue is as the provider
reports it.

## 4. The filing cover

The cover's `SecurityExchangeName` is the text the filing displays; the filer's tagging format transforms it. It is
open-ended, and varies by filer.

| Cover text | Code | Specimen filing |
| :--- | :--- | :--- |
| `The Nasdaq Stock Market LLC` | `nasdaq` | AAPL 10-K 0000320193-26-000026 |
| `New York Stock Exchange` | `nyse` | KO 10-Q 0001628280-26-067844 |
| `NYSE` | `nyse_group` | GLD 10-Q 0001437749-26-025680, UEC 10-K 0001437749-26-031414, IDR 10-Q 0001654954-26-009817, UAMY 10-Q 0001104659-26-126202 |
| `NYSE American` | `nyse_american` | UUUU 10-Q 0001385849-26-000037, URG, CVU, BRN |
| `NYSE Arca, Inc.` | `nyse_arca` | BITB 10-Q 0001193125-26-451777 |
| `Cboe BZX Exchange, Inc` | `cboe_bzx` | FBTC 10-Q 0001193125-26-451451 |
| `CboeBZX` | `cboe_bzx` | CBOE 10-Q 0001628280-26-068447 |

A bare `NYSE` on a cover is written by filers listed on the New York Stock Exchange, NYSE American and NYSE Arca alike:
GLD is `NYSEArca` at Yahoo and UEC and IDR are `NYSE American` at Yahoo, yet their covers say `NYSE`. It maps to
`nyse_group`, as SEC's `NYSE` does.

### 4.1 `NONE`

A cover value of `NONE`, in any letter case, is the filer stating that it has no exchange. It gives a null
`listing_venue` part, as a source that gave no venue does. Energy Transfer (ET) was checked, because SEC's file and Yahoo
list it as `TXSE`: its 10-Q of 2026-11-05 (0001276187-26-000070) says `NONE` for both registered securities (the common
units, symbol `ET`, and the Series I preferred units, `ETprI`), in the context of the requested ticker's own row, while
its 10-Qs of 2026-08-06 and 2026-05-07 say `New York Stock Exchange` for both. The most recent cover's `NONE` is the row
of the requested ticker, not another security. Whether the filer tagged `NONE` because the cover's list of exchange
names has no entry for the Texas Stock Exchange was not established.

### 4.2 Joined values

When one filing registers more than one class on exchanges, the engine joins the distinct values with `; ` and the joined
text is not in the table, so it is unmapped: `code` is null and `provider_value` keeps the whole text. A value of a
filer that no specimen covers (for example `NASDAQ` in capitals, or a cover naming `TXSE`) is unmapped until captured.

## 5. Market identifier codes in the glossary

The glossary entries name each venue's ISO 10383 market identifier code (MIC). Every MIC was checked on 2026-11-23
against the official list, the file `ISO10383_MIC.csv` that the registration authority publishes at
`https://www.iso20022.org/sites/default/files/ISO10383_MIC/ISO10383_MIC.csv` (2,893 rows; its most recent row update is
dated 2026-11-23, the list carries no other publication date). A MIC is kept only where that list confirms it for that
market. All ten were confirmed and none was removed:

| MIC | The list's entry | Status | Used for |
| :--- | :--- | :--- | :--- |
| `XNAS` | NASDAQ - ALL MARKETS (NASDAQ, INC.) | active | Nasdaq Stock Market |
| `XNYS` | NEW YORK STOCK EXCHANGE, INC. | active | New York Stock Exchange |
| `ARCX` | NYSE ARCA (segment of XNYS) | active | NYSE Arca |
| `XASE` | NYSE AMERICAN LLC (segment of XNYS) | active | NYSE American |
| `BATS` | CBOE BZX U.S. EQUITIES EXCHANGE (segment of XCBO) | active | Cboe BZX Exchange |
| `BATY` | CBOE BYX U.S. EQUITIES EXCHANGE (segment of XCBO) | active | Cboe group entry |
| `EDGX` | CBOE EDGX U.S. EQUITIES EXCHANGE (segment of XCBO) | active | Cboe group entry |
| `EDGA` | CBOE EDGA U.S. EQUITIES EXCHANGE (segment of XCBO) | active | Cboe group entry |
| `TXSE` | TEXAS STOCK EXCHANGE (TEXAS STOCK EXCHANGE LLC), created 2025-11-24 | active | Texas Stock Exchange |
| `OTCM` | OTC LINK ATS - OTC MARKETS (OTC MARKETS GROUP INC.) | active | the over-the-counter quotation system of OTC Markets Group |

`PINX` (OTC Pink Marketplace) is on the list as expired, so no entry names it.

## 6. Keeping the tables current

- The live suite's SEC check requests the ticker file once and fails, naming each exchange, when the file lists one that
  the SEC table does not know. Yahoo's set is open-ended and has no such check.
- A new value is added only with a captured specimen recorded here, and a new code is an addition inside `/v1`.
