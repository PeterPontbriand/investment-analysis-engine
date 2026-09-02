# Step 2.5A D0 Evidence Freeze and Implementation Handoff

**Base checkpoint:** `a4001580838795a30d72f399fb4eedcb65dee9f3`<br/>
**Evidence review date:** 2026-08-31 (America/Toronto)<br/>
**Status:** D0/Gate A complete; A0 implemented and verified, awaiting review<br/>
**Governing design:** [SEC EDGAR FPI / IFRS D0 Mapping Record](SEC_EDGAR_FPI_IFRS_D0_MAPPING_RECORD.md)<br/>
**Execution plan:** [SEC EDGAR FPI / IFRS Slice Plan](SEC_EDGAR_FPI_IFRS_SLICE_PLAN.md)<br/>
**A0 review:** [Step 2.5A A0 Identity/Security-Unit Boundary Review](STEP_2_5A_A0_REVIEW.md)

## 1. Outcome

D0 froze minimal deterministic evidence for the reviewed NTR, SAP, NVO, and
ASML boundaries. The checked-in candidates retain only the exact annual
observations, accession metadata, ticker rows, and security-unit evidence needed
by the approved test matrix. Full SEC payloads remain ignored research inputs
under `.tmp/`; no test or production code reads them or calls a live service.

The freeze reconfirmed the approved exact IFRS concepts, SAP exact-CapEx
absence, ASML's US-GAAP `20-F` shape, and NVO's ADR evidence. It also found two
implementation-boundary defects that require Gate A decisions before A1:

1. the current single-ticker guard blocks every approved annual SEC field for
   SAP, NVO, and ASML because each CIK has two SEC ticker rows; and
2. one immutable SEC snapshot per analysis cannot be guaranteed inside the
   adapter alone because the FCF and Graham resolvers issue separate field
   requests.

No production source or supported behavior changed in D0.

## 2. Frozen source manifest

All requests used a declared contact identity in the transient HTTP header. The
identity is not persisted in the repository. Retrieval timestamps are UTC; the
work was performed on 2026-08-31 local time.

| Source | Retrieved at (UTC) | Bytes | Raw SHA-256 |
| :--- | :--- | ---: | :--- |
| [SEC ticker mapping](https://www.sec.gov/files/company_tickers.json) | `2026-09-01T01:19:04.8711581Z` | 795,179 | `bf83a6d3c92cfd32211e60521861d7b0fb0ae8cf321284d4e66d01ef295ec051` |
| [NTR Company Facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0001725964.json) | `2026-09-01T01:16:29.4089178Z` | 510,604 | `62d95a7f16ad38fc3e27742f9f81399ed428e139cda9e6cfc6d3c4f20e6b0e5c` |
| [NTR submissions](https://data.sec.gov/submissions/CIK0001725964.json) | `2026-09-01T01:16:29.6392018Z` | 52,511 | `4fdb051aa409219ac0b59b3ad5aca7aad134d1c94433fa506d9ad04283b4dbf1` |
| [SAP Company Facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0001000184.json) | `2026-09-01T01:16:29.9067221Z` | 878,271 | `db2192295bd053afe068c587088c670429ca588a9e5b5da023e5765a2c211c15` |
| [SAP submissions](https://data.sec.gov/submissions/CIK0001000184.json) | `2026-09-01T01:16:30.0036344Z` | 109,766 | `c5e64085d9fe8647dcf29f5dbeb2f0fe3cdb47e3776ab962ee4507aacfa36564` |
| [NVO Company Facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000353278.json) | `2026-09-01T01:16:30.3469056Z` | 635,572 | `8f0c1f318ccb9d225ba52d29297717f70e56f39658411d711fe34f9209d5f23b` |
| [NVO submissions](https://data.sec.gov/submissions/CIK0000353278.json) | `2026-09-01T01:16:30.7540683Z` | 163,760 | `a601b4958c8faf1f8e33e6917b7f257199cee53f007a73470d67219eb0c12147` |
| [NVO 2025 Form 20-F](https://www.sec.gov/Archives/edgar/data/353278/000035327826000012/nvo-20251231.htm) | `2026-09-01T01:21:53.1644811Z` | 1,425,751 | `bc3b95895aa5c5ce37bbeb9b511ab60f9bfa5b9c072bbb24e58c0b093f92edd9` |
| [ASML Company Facts](https://data.sec.gov/api/xbrl/companyfacts/CIK0000937966.json) | `2026-09-01T01:16:30.9090774Z` | 1,837,771 | `28be6fd0f5608350ec396ae5d5097e45da95f4f29ad3fbd19aac328a15cce3d4` |
| [ASML submissions](https://data.sec.gov/submissions/CIK0000937966.json) | `2026-09-01T01:16:31.0054604Z` | 96,944 | `4dfe7cfb6673dc94f2f02869135ddb4a5e6632d8850ce141f77c865f32935d42` |

## 3. Deterministic fixture inventory

The fixture root is
`tests/fixtures/sec_edgar/step_2_5a_d0/`. `SHA256SUMS` records the checksum of
every checked-in candidate.

| Candidate | Retained boundary | Fixture SHA-256 |
| :--- | :--- | :--- |
| `company_tickers.json` | Exact seven NTR/SAP/SAPGF/NVO/NONOF/ASML/ASMLF rows | `d2e938a5d47a44e9fa127b2910681299f53743e1578207a7682862349f6d2f24` |
| `ntr_companyfacts.json` | FY2025 `40-F`; four exact IFRS duration concepts | `4ad3c9d921634ecfd4c1c9499c511af5f16bc9f2863568621e147c8e2ad0393c` |
| `ntr_submissions.json` | Accession `0001193125-26-081326`; accepted `2026-02-27T17:41:17Z` | `2f8cfb6e0102803c196ef7a622afe6b3561d74317ddbb7f8ae228d1701bdf23b` |
| `sap_companyfacts.json` | FY2025 `20-F`; EPS/WASO/OCF plus broader CapEx near-miss; exact physical-PP&E CapEx absent | `7388ae4e298a3603fb15ddb0a8962138cdc2c91ac1f4266571b8660e671a244c` |
| `sap_submissions.json` | Accession `0001104659-26-020058`; accepted `2026-02-26T12:01:22Z` | `57830bbd91704ac868e9a54406b77a4064b501cee5b6a57e2dacb307eb4d14f9` |
| `nvo_companyfacts.json` | FY2025 `20-F`; four exact IFRS duration concepts plus generic instant shares | `c0388c7fd74206ee6d4c57c890af99afcb71b65b5823f6560a1c0340d175b11e` |
| `nvo_submissions.json` | Accession `0000353278-26-000012`; accepted `2026-02-04T14:23:00Z` | `67c451be0c22df9b34077288d22b7f88916188e7431f6984dbe4c2cbf6f0f107` |
| `nvo_security_unit_evidence.json` | SEC filing says one NVO ADR represents one B share; deterministic USD-quote/DKK-filing mismatch remains unavailable | `7abeabe2eb43596183f7858681b108c0bb83aac5ecaa1d70503a7ec2ae933522` |
| `asml_companyfacts.json` | FY2025 `20-F`; four existing exact US-GAAP duration concepts | `207233da72a7c01f3f298e60fe8b32f6cace764a3e139f503a38854f6fee6f6e` |
| `asml_submissions.json` | Accession `0001628280-26-011378`; accepted `2026-02-25T11:06:02Z` | `b66338f35e5ecf14b70fd8b6475c1632b3684427f22ca2637d9567c0cf32eae7` |

The NVO quote currency is an explicitly labeled synthetic deterministic input;
the SEC filing supplies the ADR, underlying B-share, 1:1 ratio, ticker, and
venue evidence. The fixture does not pretend that the SEC filing is a quote
provider.

## 4. Reconfirmed evidence

| Issuer | Taxonomy/form/accession | Exact retained observations | Boundary |
| :--- | :--- | :--- | :--- |
| NTR | `ifrs-full`; `40-F`; `0001193125-26-081326` | EPS `4.66 USD/shares`; diluted WASO `486,518,000 shares`; OCF `4,007,000,000 USD`; CapEx `1,882,000,000 USD`; all FY2025 | Positive B1 exact-concept candidate. |
| SAP | `ifrs-full`; `20-F`; `0001104659-26-020058` | EPS `6.10 EUR/shares`; diluted WASO `1,175,000,000 shares`; OCF `9,156,000,000 EUR`; broader combined CapEx `739,000,000 EUR` | Exact physical-PP&E CapEx is absent; broader CapEx must not substitute. |
| NVO | `ifrs-full`; `20-F`; `0000353278-26-000012` | EPS `23.03 DKK/shares`; diluted WASO `4,447,700,000 shares`; OCF `119,102,000,000 DKK`; CapEx `60,140,000,000 DKK`; generic shares `4,444,000,000` | B1 facts are present; generic shares do not prove security-unit compatibility. The filing proves a 1:1 ADR/B-share ratio, but the deterministic USD quote still conflicts with DKK per-share facts. |
| ASML | `us-gaap`; `20-F`; `0001628280-26-011378` | EPS `24.71 EUR/shares`; diluted WASO `388,900,000 shares`; OCF `12,658,500,000 EUR`; CapEx `1,573,600,000 EUR` | Positive A1 form/concept shape, subject to the Gate A multi-ticker correction. |

## 5. Gate A findings requiring plan correction

### GA-1 — single-ticker guard conflicts with the approved FPI cases

`SecEdgarFinancialFactsAdapter` currently applies
`_SEC_FIELDS_REQUIRING_SINGLE_TICKER_IDENTITY` to EPS, diluted WASO, OCF, and
CapEx. The frozen SEC ticker source maps:

- NTR CIK `0001725964` to `NTR` only;
- SAP CIK `0001000184` to `SAP` and `SAPGF`;
- NVO CIK `0000353278` to `NVO` and `NONOF`; and
- ASML CIK `0000937966` to `ASML` and `ASMLF`.

Therefore, merely adding `20-F` to the form set cannot make the planned ASML A1
case pass through the production adapter. The same guard prevents the SAP and
NVO B1 cases from reaching their parsers. It also blocks issuer-level OCF and
CapEx, contradicting the approved rule that unit uncertainty must not erase
independently valid issuer-level facts.

**Recommended Gate A correction:** insert a bounded A0 identity/unit-boundary
slice before A1. Preserve exact ticker-to-CIK resolution, but stop treating
CIK-to-multiple-ticker evidence as universal fact unavailability. A0 must add
the minimum typed security-unit evidence/predicate needed to keep per-share and
quote-dependent use fail-closed while allowing independently valid issuer-level
OCF and CapEx. Do not simply delete the guard or assume multiple tickers are 1:1.
The original C slice then becomes enforcement/completion rather than the first
place this boundary exists.

### GA-2 — snapshot reuse crosses adapter and resolver ownership

The adapter currently fetches Company Facts and submissions inside each
`fetch_facts()` call. FCF resolves four annual fields separately; Graham also
issues separate SEC requests for EPS and balance-sheet inputs. Adapter-instance
caching would be analysis-unsafe for long-lived providers and cannot prove the
requested `as_of` scope.

**Recommended Gate A correction:** B1-A must own an explicit immutable
analysis-scoped provider/snapshot seam. Both analysis resolvers must bind their
SEC requests to the same scope. Persistent or process-global caching remains
out of scope.

## 6. Exact deterministic test matrix

| ID | Slice | Fixture/mutation | Expected assertion |
| :--- | :--- | :--- | :--- |
| A0-01 | A0 | Frozen ticker rows | NTR is single-ticker; SAP, NVO, and ASML are multi-ticker CIKs. |
| A0-02 | A0 | ASML multi-ticker + OCF/CapEx | Exact issuer-level facts are not erased solely by multiple ticker rows. |
| A0-03 | A0 | ASML multi-ticker + EPS/WASO without unit evidence | Per-share use remains unavailable; no implicit 1:1 assumption. |
| A0-04 | A0 | Unknown/mismatched ticker-to-CIK | All SEC fields remain unavailable or provider-error according to the existing missing-identity contract. |
| A1-01 | A1 | ASML `20-F` | All four existing exact US-GAAP duration parsers accept the form after A0 evidence permits the requested use. |
| A1-02 | A1 | Mutate an otherwise valid observation through `20-F/A`, `40-F`, and `40-F/A` | Each approved foreign annual form is accepted for duration fields. |
| A1-03 | A1 | Existing `10-K`/`10-K/A` fixtures | Values, provenance, availability, and method versions are unchanged. |
| A1-04 | A1 | Foreign form on stockholders equity/common/preferred shares | Balance-sheet/instant paths remain unavailable. |
| A1-05 | A1 | `6-K`, quarterly duration, non-`FY`, or instant observation | Duration fields remain unavailable. |
| B1A-01 | B1-A | One scoped adapter; four field requests | Company Facts and submissions transports are each called once and reused. |
| B1A-02 | B1-A | Frozen accession plus pre/post acceptance `as_of` | The filing is unavailable before acceptance and available afterward. |
| B1A-03 | B1-A | Synthetic older/newer accessions with different namespaces | Latest eligible annual accession at `as_of` selects the regime; lifetime namespace presence does not. |
| B1A-04 | B1-A | Synthetic mixed-regime requested span | Cross-regime span is unavailable/ambiguous unless an explicit common basis is proven. |
| B1A-05 | B1-A | Missing, malformed, or unmatched accession evidence | No filed-date optimism or cross-payload mixing; result is conservatively unavailable. |
| B1B-01 | B1-B | NTR four exact concepts | EPS, WASO, OCF, and positive-expenditure CapEx resolve with exact IFRS provenance and units. |
| B1B-02 | B1-B | NVO four exact concepts | Same four mappings resolve independently in DKK without implying quote compatibility or BVPS. |
| B1B-03 | B1-B | SAP near-miss CapEx | Exact physical-PP&E CapEx remains unavailable; broader combined concept is ignored. |
| B1B-04 | B1-B | Mutate exact IFRS CapEx to a negative raw value | Fact is rejected; no `abs()` normalization. |
| B1B-05 | B1-B | Wrong unit, short/YTD period, non-annual form, later `as_of`, or mismatched accession | Fact is unavailable under the existing conservative rule. |
| B1B-06 | B1-B | Missing preferred facts and generic shares only | No preferred-zero or IFRS BVPS inference is created. |
| C-01 | C | NVO 1:1 ADR evidence + DKK filing + synthetic USD quote | Quote/per-share comparison is unavailable because currency conversion is not approved; issuer-level FCF remains valid. |
| C-02 | C | Synthetic ordinary-share 1:1 evidence with matching currency | Unit predicate is affirmative and permits the otherwise-supported comparison. |
| C-03 | C | Unknown ratio, missing unit evidence, or multi-class ambiguity | Comparison fails closed without zero/substitution. |
| C-04 | C | Generic `NumberOfSharesOutstanding` alone | Generic shares do not prove ordinary-share, ADR, listing-unit, or quote compatibility. |

Every mutation is derived from a checked-in fragment in memory; no altered
fixture is written back over historical evidence.

## 7. Exact implementation ownership proposed for Gate A

### A0 — identity/security-unit boundary correction

Owned source files:

- `src/data/security_identity.py` for the smallest provider-neutral unit
  evidence/predicate, unless Gate A approves a dedicated
  `src/data/security_unit.py` instead;
- `src/data/instrument_profile.py` to carry request-scoped evidence without
  conflating it with instrument kind;
- `src/data/sec_edgar/financial_facts.py` to separate exact ticker-to-CIK
  identity from field-use compatibility;
- `src/data/financial/production.py` only for narrow capability routing; and
- the directly affected FCF/Graham applicability boundary, not calculator math.

Owned tests:

- `tests/data/test_instrument_profile.py` and a focused unit-evidence test file;
- `tests/data/test_provider_security_identity.py`;
- field-level SEC tests needed for A0-01 through A0-04; and
- resolver tests proving issuer-level facts survive while per-share use fails
  closed.

### A1 — foreign annual forms for existing US-GAAP duration concepts

Owned source file:

- `src/data/sec_edgar/financial_facts.py` only: introduce a duration-form set
  distinct from `_BALANCE_SHEET_FORMS` and use it in the four annual parsers.

Owned tests:

- `tests/analysis/fcf_earnings_growth/test_sec_edgar_operating_cash_flow.py`;
- `tests/analysis/fcf_earnings_growth/test_sec_edgar_capital_expenditures.py`;
- `tests/analysis/fcf_earnings_growth/test_sec_edgar_diluted_eps.py`;
- `tests/analysis/fcf_earnings_growth/test_sec_edgar_diluted_shares.py`;
- `tests/analysis/fcf_earnings_growth/test_sec_edgar_integration.py`; and
- existing Graham/provider tests only for regression coverage, not an instant-
  form expansion.

### B1-A — immutable analysis-scoped snapshot and regime lock

Owned source files:

- `src/data/sec_edgar/financial_facts.py` for the immutable SEC snapshot and
  accession/taxonomy selection;
- `src/data/financial/facts.py` only if the narrow scoping protocol must be
  provider-neutral;
- `src/data/financial/production.py` only to forward that optional scope;
- `src/analysis/fcf_earnings_growth/input_resolver.py`; and
- `src/analysis/graham_value/input_resolver.py`.

Owned tests:

- a new focused SEC snapshot/regime test file;
- `tests/analysis/fcf_earnings_growth/test_production_composition.py`;
- `tests/analysis/fcf_earnings_growth/test_sec_edgar_integration.py`; and
- focused Graham resolver tests proving one scope and historical no-look-ahead.

### B1-B — exact IFRS duration mappings

Owned source file:

- `src/data/sec_edgar/financial_facts.py`; no parallel IFRS adapter.

Owned tests:

- the four existing SEC duration-field test files;
- the new snapshot/regime test file for namespace/accession interactions; and
- integration tests using only the frozen NTR/SAP/NVO fragments.

No A0/A1/B1 slice owns calculator formulas, method-version changes, persistence,
schema migrations, a provider registry, a new strategy, Golden fixture rewrites,
or broad documentation claims.

## 8. Focused baseline

The following baseline ran from clean checkpoint
`a4001580838795a30d72f399fb4eedcb65dee9f3` before production changes:

```text
64 collected
64 passed
```

It covered the four SEC duration-field suites, SEC integration and production
composition, SEC BVPS hardening and User-Agent behavior, production provider
routing, and provider security identity. The focused run used `uv run --no-sync`
and made no live calls. Focused coverage was diagnostic only; repository-wide
coverage remains governed by the complete quality wrapper at later gates.

## 9. Gate A decision

The human approved Gate A on 2026-08-31. The approval accepts:

1. the frozen fixture scope and exact deterministic test matrix;
2. insertion of bounded A0 before A1, preserving exact ticker-to-CIK
   resolution and fail-closed per-share behavior; and
3. the documented resolver-spanning B1-A ownership.

A0 may proceed. This approval does not authorize A1, B1, user-facing support
claims, or a Step 2.5A completion status. Stop after A0 verification for its
review gate.
