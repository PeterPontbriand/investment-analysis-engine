# Step 3.5 slice 3.5.1 — Data mappings and applicability: Slice Plan

The slice plan for [slice 3.5.1](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#351--data-mappings-and-applicability) of Step 3.5.
It covers four sub-slices, written against `main` at `bcbfc80`.

Placement among other work packages: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **What this plan does:** adds the data the seven screening strategies need, in four steps: the issuer's SIC code as
  filed and the applicability rules built on it (3.5.1a); balance-sheet values at several year-ends (3.5.1b); the
  annual income-statement and cash-flow values (3.5.1c); and split history with the price basis of market
  capitalization (3.5.1d).
- **What it is not:** a strategy, a formula, a shared metric or a ranking. No field added here has a production consumer
  until 3.5.3; each is proven against captured filings first, as the contract requires. Full list:
  [Scope limits](#4-scope-limits).
- **The entry criterion is met.** A filing's SEC header keeps the `ASSIGNED-SIC` of its filing date. Two issuers whose
  code changed show it; the evidence is in the [mapping evidence record](STEP_3_5_1_MAPPING_EVIDENCE.md#3-sic-evidence).
  The current `sic` of the submissions data is still never used.
- **Rules every sub-slice follows:**
  - One mapping per field and taxonomy, approved only from captured filings. An unsupported field makes its consumers
    `unavailable`; a neighbouring concept never stands in for it.
  - Nothing missing becomes zero. An absent component stays absent in this slice; the rules that read absence as zero
    belong to the shared metrics of 3.5.2.
  - A change to a persisted shape bumps that shape's version field, with no migration or compatibility decoder
    ([AGENTS.md §4](../../../../../AGENTS.md)). Each sub-slice lists such a change among its user-visible changes.
  - The managed quality gate after every sub-slice, and explicit authorization before the next begins.
  - No registry, plugin loader or factory is added; the new code is plain functions and frozen types.
- **Where the detail lives:** the file inventories, the tests and the documentation changes are in
  [Appendix B](#appendix-b-file-inventories-tests-and-documentation); decision records are in
  [Appendix A](#appendix-a-decision-records); the live evidence is in the
  [mapping evidence record](STEP_3_5_1_MAPPING_EVIDENCE.md).

## 2. Sequence and status

Each sub-slice ends with the managed quality gate and is gated by explicit authorization before the next begins.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| 3.5.1a | [As-filed SIC code and applicability](#351a--as-filed-sic-code-and-applicability) | Complete | 2026-10-25 |
| 3.5.1b | [Balance-sheet instants](#351b--balance-sheet-instants) | Complete | 2026-10-25 |
| 3.5.1c | [Annual period fields](#351c--annual-period-fields) | Next | |
| 3.5.1d | [Split history and the market-cap price basis](#351d--split-history-and-the-market-cap-price-basis) | Planned | |

3.5.1a is implemented on the branch that carries this plan and merges as one pull request. Each later sub-slice has its
own branch off `main`, named `feat/step-3-5-1<letter>-<topic>`, after the previous pull request merges.

## 3. The sub-slices

### 3.5.1a — As-filed SIC code and applicability

- **Problem:** nothing in the codebase records an industry class, and the only SIC the SEC data offers outside a filing
  (the `sic` of the submissions JSON) is today's value, which would be look-ahead in a historical run.
- **Decision (F2, F3, F8):**
  - The class comes from the `ASSIGNED-SIC` in the SEC header of the anchor annual filing, kept as filing evidence with
    the filing's accession, filing date and acceptance time, and checked against the boundary like every other input.
  - The header is `<accession>.hdr.sgml` in the filing's archive folder. Entry criterion: **Pass**
    ([evidence §3](STEP_3_5_1_MAPPING_EVIDENCE.md#3-sic-evidence)).
  - One header request per run, for the anchor filing only, to an exact URL pattern enforced as `filing_document.py`
    enforces its own. It does not count toward the four-document limit.
  - A combined filing has one `<FILER>` block per registrant; the code is the one in the block whose `<CIK>` is the
    issuer's CIK. A filing with no such block, no code, a code that is not four digits (including `0000`), an
    accession or CIK that does not match, or an acceptance time after the boundary gives an unknown class.
  - The industry class, the `SectorGate` type and the applicability helpers are pure functions in
    `investment_analysis_engine/analysis/shared/applicability.py`, which names no strategy: which classes a strategy
    refuses is that strategy's policy, so each strategy declares its own gate as a named constant in its own package,
    in its own slice, with a test that pins it to its row of the matrix (G5). The header reading stays in
    `investment_analysis_engine/data/sec_edgar/`. Both placements fit the package table in
    [ARCHITECTURE §13](../../../ARCHITECTURE.md#13-module-boundaries) (`analysis` already imports `core` and `data`;
    `data` imports neither) and add no import between units.
  - Two new `ReasonCode` members: `industry_class_not_applicable` and `industry_class_unknown`.
  - The class is not added to the instrument profile ([Shared definitions §1](STEP_3_5_SHARED_DEFINITIONS.md#industry-class-evidence)).
  - A.8 (Momentum's provider failure) was decided and implemented in 3.5.0a; this sub-slice does not touch it.
- **Scope:** the header transport and parser; the as-filed SIC evidence type; the adapter method that resolves it for an
  analysis; `IndustryClass`, the classification function and the applicability helpers; the two reason codes; trimmed
  header fixtures; one live check; tests; the schemas that list `ReasonCode`, regenerated. The file list is in
  [B.1](#b1-351a-files).
- **Branch:** `feat/step-3-5-1a-sic-applicability` (this branch; plan and implementation are one pull request).
- **Detail:** [files](#b1-351a-files), [result shape](#b6-result-shapes), [tests](#b7-351a-tests).

### 3.5.1b — Balance-sheet instants

- **Problem:** `PeriodKind` has no instant, and balance-sheet selection returns the single latest fact, so a metric that
  needs total assets at three year-ends has no way to ask for them.
- **Decision (F5, F9):**
  - `PeriodKind` gains an `INSTANT` member; an instant is never a relabeled duration.
  - A new exact-date series request asks for named year-ends. Today's latest-only request and its behavior are
    unchanged, and Graham's balance-sheet selection is untouched.
  - The financial-fact cache's schema version is bumped. Entries stored under the older version are refused and
    fetched again; stored runs are unaffected.
  - Every instant field of [Slice inputs §3](STEP_3_5_SLICE_INPUTS.md#3-351--data-mappings-and-applicability) is added
    here, one `FinancialField` each, with an explicit currency unit, and is approved only from captured filings.
  - The resolver returns what the filing reports for each requested date and says which dates have no value. It applies
    no absent-component convention and no debt rule (3.5.2).
  - **Share-count coverage (G1).** The existing `COMMON_SHARES_OUTSTANDING` field is not covered by any evidence, and
    market cap (3.5.2), and through it EV, FCF yield, the valuation multiples and Magic Formula's earnings yield, depends
    on it. Walmart has not tagged `us-gaap:CommonStockSharesOutstanding` since 2013. This sub-slice checks the field's
    coverage across the regression issuer set of the contract's [§5](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#5-acceptance-criteria)
    plus Walmart, recording the direct concept and the fallback (`CommonStockSharesIssued` minus
    `TreasuryStockCommonShares`) separately, with a row and a disposition in the evidence record. If a large filer gets
    no count from either path, 3.5.1b stops and records it (H4, H7). The regression issuer set is named once, in the
    [mapping evidence record](STEP_3_5_1_MAPPING_EVIDENCE.md#5-field-mappings)
    ([A.1](#a1-decisions-f1-to-f10-2026-10-25), H1).
  - **Share-count gap (H7).** The check found no count at the latest year-end for Walmart, SAP and Nutrien. The
    balance-sheet paths gain an IFRS direct path (`ifrs-full:NumberOfSharesOutstanding`), and a cover-page fallback is
    added for market cap only, as its own `basis` of the existing field so that no existing resolution changes. The
    rule is in [Shared definitions §4](STEP_3_5_SHARED_DEFINITIONS.md#share-count-rule).
  - **Lists of equivalent concepts (H10).** Receivables and short-term investments map to a priority list of concepts
    the evidence shows are the same line item. One issuer uses one concept for every year of a run, and the resolved
    input names it. The absent-component zero of [Shared definitions §3](STEP_3_5_SHARED_DEFINITIONS.md#absent-component-convention)
    applies only when none of the listed concepts is tagged, never to an unsupported mapping.
  - **Net PP&E under IFRS (H11).** The plain concept where the filer reports it; the concept that includes right-of-use
    assets only where that is the filer's own single balance-sheet line; the two are never summed.
  - **IFRS debt (H12).** Only carrying amounts qualify. The structured data cannot tell a carrying amount from a nominal
    one, so the IFRS noncurrent long-term debt mapping is recorded unsupported (see D3); 3.5.2 must read an unsupported
    component as `unavailable`, never as zero.
  - **Test case for 3.5.2 (H12).** Alphabet's direct long-term-debt total (49,085 million at 2025-12-31) does not equal
    its current and noncurrent parts (48,543 million), the case for the reconciliation rule of Shared definitions §6,
    which marks the affected component `unavailable`. Honeywell is the other: it tags a direct `LongTermDebt` of 29,046
    million and neither mapped part, and the parts it tags under other concepts add to 28,687 million.
  - **Derived totals (H3).** A field may be derived only when the derivation is an exact accounting identity and every
    term is tagged at the same date in the same filing. Total liabilities is total liabilities and equity, minus total
    equity including noncontrolling interest, minus any temporary equity (redeemable noncontrolling interest or similar
    mezzanine items) where tagged. A derived value is recorded as `SourceKind` derived with its lineage and a derived
    `provider_field`, as `CommonStockSharesIssued` minus `TreasuryStockCommonShares` is. A derivation is approved only
    where the evidence shows it equals the directly tagged value for every filer of the regression set that tags both;
    one mismatch makes it unsupported. Each derivation is named in the evidence record. A derivation that is not an
    exact identity stays forbidden.
  - **Versions (H5).** The financial-fact cache version is bumped at every place that sets it. `PeriodKind` gaining
    `instant` adds an enum value to the schemas and stored evidence that list it and changes no stored shape, so the
    schemas are regenerated and no document version is bumped.
- **Scope:** the new `PeriodKind` member; the series request and its provider protocol; the SEC implementation; the
  resolver entry; the 17 fields with their us-gaap and ifrs-full mappings; the cache version; trimmed fixtures; the
  field-mapping rows of the evidence record for these fields, and the share-count coverage check and its row; tests. The
  file list is in [B.2](#b2-351b-files).
- **Branch:** `feat/step-3-5-1b-balance-sheet-instants`, off `main` after the 3.5.1a pull request merges.
- **Detail:** [files](#b2-351b-files), [fields](#b4-the-fields), [tests](#b8-351b-tests).

### 3.5.1c — Annual period fields

- **Problem:** the income-statement and cash-flow lines the strategies need are not mapped, and Beneish's depreciation
  index depends on whether depreciation alone can be read.
- **Decision (F9):**
  - The 13 annual fields of Slice inputs §3 are added as `FinancialField` members with explicit currency units, and are
    served by the existing completed-annual series request (the set `_COMPLETED_ANNUAL_SERIES_FIELDS` grows).
  - Overlapping revenue concepts are a priority list and are never summed; a segment figure is never total revenue.
  - The depreciation evidence of Slice inputs §3 is gathered here and decides the depreciation-alone mapping: approved,
    approved with a stated limit, or unsupported. If unsupported, every Beneish run uses the D&A basis.
- **Scope:** the 13 fields and their us-gaap and ifrs-full mappings; the series set; trimmed fixtures; the field-mapping
  and depreciation rows of the evidence record; tests. The file list is in [B.3](#b3-351c-files).
- **Branch:** `feat/step-3-5-1c-annual-period-fields`, off `main` after the 3.5.1b pull request merges.
- **Detail:** [files](#b3-351c-files), [fields](#b4-the-fields), [tests](#b9-351c-tests).

### 3.5.1d — Split history and the market-cap price basis

- **Problem:** the only price series the market-data boundary offers is adjusted for dividends as well as splits, and no
  split history is exposed. Market cap needs the split-adjusted close without dividend adjustment and a way to put a
  filed share count on the same basis.
- **Decision (F6, F7, F10):**
  - **Price:** the split-adjusted close without dividend adjustment, on or before `as_of`, through a new request in the
    historical market-data boundary. Without `as_of`, the current quote, as today. Yahoo supplies no unadjusted close
    ([evidence §4.1](STEP_3_5_1_MAPPING_EVIDENCE.md#41-what-close-and-adj-close-are)).
  - **Shares:** the fiscal year-end count, scaled by every split whose ex-date is after the filing date of the filing the
    count was taken from, up to the price data's adjustment date. The accession and filing date come from the count's own
    provenance; the anchor filing is not assumed. A filing restates its share counts for splits effective before it is
    issued (SEC Staff Accounting Bulletin Topic 4.C), so a count taken from a later filing is already on a later basis
    ([evidence §4.5](STEP_3_5_1_MAPPING_EVIDENCE.md#45-a-count-restated-for-a-split-before-the-filing-walmart-fy2024)).
  - **Effect:** the market cap equals the one [Shared definitions §4](STEP_3_5_SHARED_DEFINITIONS.md#4-market-capitalization)
    defines. The formula and the value are unchanged; only how it is computed is stated.
  - **One response:** the close and the splits come from one response, so the adjustment date of the prices is the
    adjustment date of the splits by construction, and a cached response stays consistent however old it is.
  - **Existing series:** the dividend-adjusted series is never used for market cap. Momentum's series is unchanged.
  - **Point-in-time exception:** splits after the boundary are used only to undo the provider's retroactive adjustment and
    never change the as-of market cap ([Shared definitions §3](STEP_3_5_SHARED_DEFINITIONS.md#3-data-sources-periods-and-point-in-time)).
  - **Stock dividends (F7):** Yahoo reports them as fractional splits (1.05, 1.03) that cannot be told from a small
    split. They scale a share count exactly as a split does and are not issuance. No code counts or labels them, and the
    limitation is stated in the guides.
  - **Limitation:** a split announced before the filing but effective just after it is assumed not to be reflected in the
    filing.
  - The market cap itself is 3.5.2. This sub-slice supplies the price, the splits and a pure function that scales a count.
- **Scope:** the split-history type and the new request in `data/market_data.py`; the yfinance implementation; the cache
  of the response; the scaling function; trimmed fixtures; one live check; tests. The file list is in
  [B.5](#b5-351d-files).
- **Branch:** `feat/step-3-5-1d-split-history`, off `main` after the 3.5.1c pull request merges.
- **Detail:** [files](#b5-351d-files), [result shapes](#b6-result-shapes), [tests](#b10-351d-tests).

## 4. Scope limits

- No strategy calculation, shared metric, ranking or presentation; no change to any existing strategy's formula,
  classification or stored output.
- No change to Graham's latest-only balance-sheet selection or to Momentum's series.
- No SIC in the instrument profile, and no use of the current `sic` of the submissions data.
- No schema migration and no compatibility decoder. Shapes that change are versioned
  ([B.11](#b11-user-visible-changes)).
- No GICS, no reading of the filing's primary document for the class, and no second source for splits.
- No persistent cache of the header (see [A.1](#a1-decisions-f1-to-f10-2026-10-25), F3).
- No dividend-adjusted price in market cap, and no count of stock dividends.
- No absent-component or total-debt rule; those are 3.5.2.
- No edit-site of `docs/TOOL_DEVELOPMENT.md` is touched ([B.12](#b12-tool_development-edit-sites)).
- A mapping the evidence does not support is recorded as unsupported, not approximated.

## 5. Acceptance criteria

**3.5.1a**

- A known bank, insurer, REIT, utility and manufacturer classify as their class from a trimmed real header; a code in
  no range is the ordinary class; an unreadable header gives an unknown class, never an error and never the current code.
- A combined filing gives the code of the issuer's own block.
- A header accepted after the boundary is rejected, including at a one-second margin.
- The full applicability matrix of Shared definitions §1 holds for every class, for a gated and an ungated strategy,
  and for an unknown class.
- One header request is made per run, it is not counted among the four documents, and a live check asserts the shape of
  the response.
- The complete managed gate passes, with at least 85% coverage and every new branch exercised.

**3.5.1b**

- Three year-ends of one issuer are returned by exact date; the newest balance sheet is never returned for an earlier
  date; a date with no value is reported absent.
- Every instant field carries an approved mapping per taxonomy or is recorded unsupported, with captured evidence.
- Existing fields, stored values and Graham's balance-sheet selection are unchanged.
- `COMMON_SHARES_OUTSTANDING` has a coverage row and a disposition in the evidence record, covering the regression issuer
  set and Walmart, with the direct concept and the issued-minus-treasury fallback recorded separately.
- The gate passes.

**3.5.1c**

- Every annual field carries an approved mapping per taxonomy or is recorded unsupported, with captured evidence.
- The depreciation evidence is complete and gives a disposition for the depreciation-alone mapping.
- The gate passes.

**3.5.1d**

- The split-adjusted close without dividend adjustment is returned for the last trading day on or before `as_of`.
- The NVIDIA and Walmart cases of [B.10](#b10-351d-tests) give the market cap the evidence shows.
- A live check asserts the shape of the split-history response.
- Momentum's output is unchanged and the gate passes.

## 6. Background

[Slice inputs §3](STEP_3_5_SLICE_INPUTS.md#3-351--data-mappings-and-applicability) was written on 2026-10-02 as a
starting point: candidate concepts, the entry criterion and the evidence each field needs. This plan was written on
2026-10-25 against the code and live data, and split the work in four because the SIC criterion, the instant
representation, the annual fields and the split history have different inputs, different risks and no dependency except
the order given. The live checks changed one starting point: Yahoo has no unadjusted close, and a filing already restates
its share counts for an earlier split, so the price basis of market cap and the scaling of the share count were decided
differently from the text of Shared definitions §4 ([A.2](#a2-the-share-count-scaling-window-2026-10-25)).

---

## Appendix A: Decision records

### A.1 Decisions F1 to F10 (2026-10-25)

Approved by the project owner. Each is stated in the sections above; this table records them.

| # | Topic | Decision |
| :--- | :--- | :--- |
| F1 | Sub-slices | Four: 3.5.1a SIC and applicability, 3.5.1b instants, 3.5.1c annual fields with the depreciation evidence, 3.5.1d split history and price basis. 3.5.1a is implemented on this branch as one pull request with the plan; each later one has its own branch off `main` after the previous merges. The contract's sequence table has rows 3.5.1a (Next) to 3.5.1d (Planned) in place of 3.5.1; 3.5.1a stays Next until its implementation starts. |
| F2 | SIC entry criterion | Pass when an older annual filing's header shows a code that differs from the current submissions `sic` and from a later filing's header; fail when the headers always show the current code; inconclusive when no issuer with a changed code is found. **Result: Pass** ([evidence §3.3](STEP_3_5_1_MAPPING_EVIDENCE.md#33-result)). |
| F3 | The header file | Read from `<accession>.hdr.sgml`. One request per run, for the anchor filing only; an exact URL pattern; outside the four-document limit; kept as filing evidence with accession, filing date and acceptance time; boundary-checked. The plan keeps it for the analysis scope, as the snapshot's other filing evidence is kept, and adds no persistent cache: an as-filed header never changes, so a persistent cache is an optimization that can be added later without changing any shape. **No persistent header cache: approved** by the project owner on review of the plan (G3). |
| F4 | Evidence storage | The evidence record; fixtures trimmed to the facts used, following the `evaluation/fixtures/sec_edgar` precedent; no full Company Facts payload is checked in; each sub-slice adds the fixtures its tests need. |
| F5 | Instants | An additional `PeriodKind` member; a new exact-date series request leaving the latest-only behavior unchanged; the financial-fact cache version bumped under the AGENTS.md §4 stored-shape rule. |
| F6 | Market-cap price basis | See [A.2](#a2-the-share-count-scaling-window-2026-10-25), which carries the project owner's refinement of the share-count window, and H7, which adds a cover-page share count and the scaling window it needs. |
| F7 | Stock dividends | Adjusted like splits where the split history shows them, never read as issuance. The history shows them as fractional splits and cannot tell them from a small split; the plan states that limit and does not guess. |
| F8 | Names and places | Reason codes `industry_class_not_applicable` and `industry_class_unknown`; helpers and the industry-class type in `analysis/shared/applicability.py`; header reading in `data/sec_edgar/`. Both placements confirmed against ARCHITECTURE §13. |
| F9 | Every field in 3.5.1 | Every field of Slice inputs §3 is added in 3.5.1b or 3.5.1c and proven against captured filings; none has a production consumer until 3.5.3. |
| F10 | Live checks | One `live_network` check for the header request (3.5.1a) and one for the split-history request (3.5.1d), in `tests/live/test_provider_response_shape.py`, under the conditions of AGENTS.md §3. |

Decided by the implementer within the plan's goals. **Approved by the project owner on review of the plan (G2).**

| Topic | Decision | Why |
| :--- | :--- | :--- |
| Unknown class | A missing block, code, mismatch or a `0000` code is an unknown class; a transport fault raises the classified provider error as for every SEC request. | An unreadable header is evidence that is not available; a network fault is not. |
| Split on the filing date | A split whose ex-date equals the filing date is not scaled. | The filing is dated the same day and is presumed to reflect it. |
| One response for close and splits | The new request returns the close and the splits together. | The two share one adjustment date by construction, so no cache can pair a close with a split list from another day. |
| Fixture folder names | Neutral names (`filing_headers`, `instant_facts`, `annual_facts`, `split_history`). | Planning labels stay out of code ([AGENTS.md §4](../../../../../AGENTS.md)). |

Added on the project owner's review of the plan:

| # | Topic | Decision |
| :--- | :--- | :--- |
| G1 | Share-count coverage | Added to 3.5.1b: a coverage check of `COMMON_SHARES_OUTSTANDING` across the regression issuer set plus Walmart, the direct concept and the issued-minus-treasury fallback recorded separately, a row and a disposition in the evidence record. If a large filer gets no count from either path, 3.5.1b stops and asks before 3.5.2 is planned. |
| G2 | Implementer decisions | The four decisions in the table above are approved. |
| G3 | Header cache | No persistent header cache is approved (F3). |
| G4 | `ReasonCode` schemas | The schemas that list `ReasonCode` values (`momentum`, `fcf-growth`, `runs-compare`) are regenerated with the two new members and no document version bump. Adding enum values changes no stored shape, so the AGENTS.md §4 rule does not apply, and existing payloads still decode. |
| G5 | Where the gates live | The per-strategy gate constants are not in `analysis/shared/applicability.py`. AGENTS.md §9 makes each strategy own its policy, which classes it refuses is policy, the shared module stays strategy-neutral like the ranking helper, and the constants had no consumer. Each strategy slice declares its `SectorGate` as a named constant in its own package with a test pinning it to its row of the matrix ([Slice inputs §1](STEP_3_5_SLICE_INPUTS.md#1-at-a-glance)). Superseded in 3.5.1a before the pull request opened. |
| H1 | The regression issuer set | Named once, in the [evidence record](STEP_3_5_1_MAPPING_EVIDENCE.md#5-field-mappings), as Step 3.5's regression set; 3.5.7 reuses it. Kept from the 3.5.1a captures: JPMorgan (bank), Prologis (REIT), Duke Energy (utility), Deere (manufacturer), SAP and Nutrien (IFRS filers), Walmart (non-manufacturer). Three more chosen from evidence: one company with negative EBIT in its latest fiscal year, one with no reported debt, one with several share classes. The record states why each fits, with its CIK and latest annual accession. |
| H2 | Evidence that approves a mapping | Presence is checked from Company Facts across the whole regression set for all 17 instant fields of [B.4](#b4-the-fields), recording concept, context, units, scale and period behavior. Values are checked against the rendered balance sheet for one US GAAP filer and one IFRS filer per field, at one year-end. Each field and taxonomy gets one disposition: approved, approved with a stated limit, or unsupported. An unsupported field makes its consumers `unavailable`; a neighboring concept never stands in for it. Request budget: about 60 EDGAR requests with the project's SEC identity, which is never printed; raw responses only under `.tmp/`, none committed. |
| H3 | Derived totals | A field may be derived only when the derivation is an exact accounting identity and every term is tagged at the same date in the same filing. Total liabilities is total liabilities and equity, minus total equity including noncontrolling interest, minus any temporary equity (redeemable noncontrolling interest or similar mezzanine items) where tagged, recorded as a derived value with lineage, following the `CommonStockSharesIssued` minus `TreasuryStockCommonShares` precedent. A derivation is approved only where the evidence shows it equals the directly tagged value for every filer of the set that tags both; one mismatch makes it unsupported, and the work stops and reports. The same rule may apply to another field where the evidence shows the same gap; each derivation is named in this plan and the evidence record. |
| H4 | When the share-count check stops the work | `COMMON_SHARES_OUTSTANDING` is checked for each regression-set issuer and Walmart at its latest year-end, through the direct concept and through the issued-minus-treasury fallback, each path recorded separately. If any of them gets no count from either path, 3.5.1b stops and reports before any implementation code: which issuers, what they tag instead, and how many of their recent year-ends are affected. The cover-page count stays forbidden. |
| H5 | Versions | The financial-fact cache version is bumped at every place that sets it (B.2 names FCF-Growth's `CACHE_SCHEMA_VERSION` and the resolver's default; the others are found and listed). `PeriodKind` gaining `instant` adds an enum value to the schemas and stored evidence that list it with no stored shape changed: the schemas are regenerated with `uv run python -m scripts.generate_schemas` and no document version is bumped. |
| H6 | Plan formatting | The G1 bullet and the **Scope** bullet of the 3.5.1b section are separate lines. |
| H7 | Share-count gap | An IFRS direct path (`ifrs-full:NumberOfSharesOutstanding`), and an issued-minus-treasury path under IFRS only if an IFRS treasury share *count* concept exists in the evidence (none does). The cover-page count (`dei:EntityCommonStockSharesOutstanding`) is allowed as a fallback for market cap only: after the balance-sheet paths, and only when the anchor filing tags it as a single non-dimensional total; its own date is the share-count date. A cover-page count is scaled by splits whose ex-date is after that date, not after the filing date. Piotroski's dilution test keeps using year-end balance-sheet counts only. A multi-class filer with per-class cover counts and no total stays `unavailable`. Where an issuer's latest annual filing tags no usable cover count, that issuer is `unavailable` for market cap, with the reason. Shared definitions §4 and the contract's Appendix A.12 carry the rule; this reverses the 2026-10-02 rule of A.6, because Walmart has tagged no balance-sheet count since 2012 and the multi-class rule already covers the other reason for the ban. F6 and A.2 are read with it. |
| H8 | IFRS total liabilities | The IFRS derivation is unsupported: rounding makes it inexact in SAP's filing (four mismatches of one million). The US GAAP derivation stays approved. No tolerance is added. |
| H9 | A second manufacturer | Deere stays as the unclassified-balance-sheet case. A manufacturer with a classified balance sheet is added to the regression set, chosen from evidence ([evidence §5.1](STEP_3_5_1_MAPPING_EVIDENCE.md#51-the-regression-issuer-set)). |
| H10 | Lists of equivalent concepts | A field may map to a priority list of concepts only where the evidence shows they are the same line item: receivables (`AccountsReceivableNetCurrent`, then `ReceivablesNetCurrent`) and short-term investments (`ShortTermInvestments`, `MarketableSecuritiesCurrent` and the equivalents the evidence shows). One issuer uses the same concept for every year of a run and the resolved input names it. The absent-component zero of Shared definitions §3 applies only when none of a field's listed concepts is tagged and never to a mapping recorded as unsupported, which stays `unavailable`. Alphabet and Moderna are the cases that motivated it. |
| H11 | Net PP&E under IFRS | The plain concept where the filer reports it; the concept that includes right-of-use assets only where that is the filer's own single balance-sheet line; never the sum of the two (Shared definitions §6). |
| H12 | Smaller points | Commercial paper belongs to short-term borrowings and is never mapped to the current portion of long-term debt; B.8's wording is corrected. IFRS debt: only carrying amounts qualify, and a concept holding nominal amounts, or combining commercial paper with the current portion, is unsupported for that field and filer. Alphabet's direct long-term-debt total that does not match its parts is recorded as a test case for 3.5.2's reconciliation rule. `evaluation/fixtures/graham.py` may be edited so its cache version follows the resolver default. H4 is a stop-and-record outcome and the work continues. |

Decided under delegation (2026-10-25), within the standing instructions of the project owner:

| # | Topic | Decision | Why |
| :--- | :--- | :--- | :--- |
| D1 | Second manufacturer | Honeywell (CIK 773840, SIC 3724; latest annual `0000773840-26-000013`, 10-K, filed 2026-02-17, year-end 2025-12-31). | It is a manufacturer whose balance sheet is classified (current assets and current liabilities are tagged), the gap Deere leaves. It also tags no `Liabilities`, so the derivation supplies its total (58,651 million). |
| D2 | Short-term investments list | US GAAP: `ShortTermInvestments`, then `MarketableSecuritiesCurrent`, then `AvailableForSaleSecuritiesDebtSecuritiesCurrent`. Deere's `MarketableSecurities` is not listed. | Alphabet's "Marketable securities" (96,135 million) and Moderna's "Investments" (3,204 million) are current lines on the face of the balance sheet. Deere's balance sheet is unclassified, so its line is not shown to be current. |
| D3 | IFRS noncurrent long-term debt | Unsupported. | SAP's `LongtermBorrowings` (4,550 million) is a nominal amount against a carrying amount of 4,194 million, and Company Facts cannot tell a nominal amount from a carrying one. Approving the concept would give SAP a wrong value, and a list of excluded issuers is a hard-coded exception. Consequence: IFRS total debt cannot be assembled until the owner decides otherwise ([evidence §5.6](STEP_3_5_1_MAPPING_EVIDENCE.md#56-findings-the-owner-decides)). |
| D4 | Total-liabilities derivation per date | A date with no tagged `Liabilities` is derived from the terms of one filing; a date with one is read directly. | The identity is exact where the evidence shows it holds, so a run that mixes the two gives the same value; it is not a priority list. |
| D5 | Instant request shape | The requested period ends must be consecutive fiscal year-ends, each gap within the existing annual-duration tolerance (335 to 395 days). | It makes the 52/53-week rule testable for an instant request and rejects quarter-ends and stub dates. |
| D6 | Cover-page fallback shape | A `basis` of the existing field (`cover_page`), not a new field or an option. | The year-end path and every consumer of it, Graham's BVPS included, are untouched. |
| D7 | New module | `data/sec_edgar/instant_series.py`. | Placement only; see B.2. |
| D8 | Absent reasons | Seven: not tagged, other concept, conflict, unsupported, basis mismatch, after the boundary, no anchor filing. | 3.5.2 needs to tell "the filer has none" from "the data cannot say". |

### A.2 The share-count scaling window (2026-10-25)

F6 as approved scaled the fiscal year-end share count by every split from that year-end up to the price data's
adjustment date. The live check found that this counts a split twice when it falls between the year-end and the filing:
Walmart's fiscal 2024 10-K (year-end 2024-01-31, 3-for-1 split effective 2024-02-23, filed in March 2024) restates every
share figure for the split ([evidence §4.5](STEP_3_5_1_MAPPING_EVIDENCE.md#45-a-count-restated-for-a-split-before-the-filing-walmart-fy2024)).
The project owner decided the same day:

- **Rule:** scale the share count by every split whose ex-date is after the filing date of the filing the count was
  actually taken from, taken from the count's own provenance (its accession and filing date), never assumed to be the
  anchor filing. A later filing's comparative balance sheet restates an earlier year-end for splits up to that later
  filing's own date, so scaling from the anchor filing's date would double-count the splits in between whenever the count
  came from a later filing. For a count from the anchor filing, as Shared definitions §4 expects, the filing date is the
  anchor's.
- **Reason:** SEC Staff Accounting Bulletin Topic 4.C requires a filing to restate for a split effective before it is
  issued.
- **Limitation, stated in the guides:** a split announced before the filing but effective just after it is assumed not to be
  reflected in the filing.
- **Worked example and tests:** the Walmart fiscal 2024 case is the worked example in the evidence record and a test of
  3.5.1d ([B.10](#b10-351d-tests)).
- **A cover-page count (H7):** it is dated by its own cover date and has no filing-date window. It is scaled by every
  split whose ex-date is after that date, up to the price data's adjustment date, because the cover count is taken
  after the fiscal year-end and the filing date is not its basis. A split between the cover date and the filing date
  is applied to a cover-page count and is not applied to a year-end count taken from the same filing.
- **Documents amended with this plan:** Shared definitions §3 and §4, the contract's Appendix A.11, and the two Slice
  inputs lines that named the unadjusted close and the split between the share-count and price dates.

---

## Appendix B: File inventories, tests and documentation

Paths are under `investment_analysis_engine/` unless they start with `tests/`, `schemas/`, `docs/` or `scripts/`.

### B.1 3.5.1a files

| Area | File | Change |
| :--- | :--- | :--- |
| Transport | `data/sec_edgar/filing_document.py` | `filing_header_url(cik, accession)` builds `https://www.sec.gov/Archives/edgar/data/<cik>/<18 digits>/<accession>.hdr.sgml` from validated identifiers; `fetch_filing_header` reads it with the same no-redirect, bounded, classified-failure transport as `fetch_filing`, under its own `FilingHeaderPolicy` (timeout 20 s, 256 KiB); the shared read is extracted so `fetch_filing` is unchanged in behavior. It does not consult `max_documents`. |
| Parser | `data/sec_edgar/filing_header.py` (new) | `parse_filing_header(text, *, cik, accession)` returns `AsFiledSic` or a reason; `AsFiledSic` is a frozen type (code, CIK, accession, filing date, acceptance time, source URL, retrieval time) |
| Adapter | `data/sec_edgar/financial_facts.py` | the snapshot gains the filing dates of its accessions; `resolve_as_filed_sic(...)` requests the anchor header once per analysis scope, applies the checks of [B.6](#b6-result-shapes) and returns `AsFiledSic` or a reason |
| Applicability | `analysis/shared/applicability.py` (new) | `IndustryClass`, `Applicability`, `industry_class_of_sic`, `SectorGate`, `ApplicabilityOutcome`, `applicability_of` (pure); no per-strategy gate |
| Reason codes | `core/metric_result.py` | `INDUSTRY_CLASS_NOT_APPLICABLE`, `INDUSTRY_CLASS_UNKNOWN` |
| Schemas | `schemas/momentum.schema.json`, `schemas/fcf-growth.schema.json`, `schemas/runs-compare.schema.json` | regenerated: each lists the `ReasonCode` values |
| Fixtures | `evaluation/fixtures/sec_edgar/filing_headers/` (new) | the header lines that matter, from the filings of [evidence §3](STEP_3_5_1_MAPPING_EVIDENCE.md#3-sic-evidence), with a checksum file as the existing fixtures have |
| Live check | `tests/live/test_provider_response_shape.py` | one `live_network` test for the header request |

Starting points confirmed on `main` (2026-10-25): `filing_url` and `fetch_filing` accept `.htm` primary documents only and
refuse redirects; `SecEdgarAnalysisSnapshot` holds acceptance times, forms and primary documents but no filing dates and
no SIC; no code reads a SIC.

### B.2 3.5.1b files

| Area | File | Change |
| :--- | :--- | :--- |
| Provenance | `data/financial/provenance.py` | `PeriodKind.INSTANT` |
| Fields | `data/financial/facts.py` | 17 new `FinancialField` members, each routed to the currency unit in `_expected_unit` (an unrouted field falls through to per-share) |
| Request | `data/financial/facts.py` | `InstantSeriesRequest` (subject, field, provider, boundary, the requested period ends), `InstantSeriesFacts` with its absences, `ProviderAmountSource` for the terms of a derivation, and the provider protocol that serves them; `FinancialFactRequest` is not extended |
| SEC | `data/sec_edgar/instant_series.py` (new) and `data/sec_edgar/financial_facts.py` | the mappings per taxonomy and the exact-date selection for a requested period end (eligible annual filings, the boundary, the taxonomy of the anchor filing, one currency, conflicts reported), kept in a module of their own because `financial_facts.py` is over two thousand lines; the adapter method and the share-count paths of H7 stay in `financial_facts.py` |
| Resolver | `data/financial/resolver.py` | an entry that resolves an `InstantSeriesRequest` into one `ResolvedInput` per date present and the dates absent, with the resolution trace; the unit routing of the new fields |
| Cache | `data/financial/resolver.py`, `strategies/fcf_growth/input_resolver.py`, `evaluation/fixtures/graham.py` | the sites that set the financial-fact cache version, bumped (H5, H12); the cache itself needs no change: an older entry is refused by its version and fetched again |
| Fixtures | `evaluation/fixtures/sec_edgar/instant_facts/` (new) | trimmed facts of the filings the evidence uses |
| Evidence | `docs/project/milestones/v0.2/step-3.5/STEP_3_5_1_MAPPING_EVIDENCE.md` | the field-mapping rows for these fields |

Starting point to confirm first: the places that set the cache schema version (`CACHE_SCHEMA_VERSION = 2` in
`strategies/fcf_growth/input_resolver.py`, and the resolver's default of 1), because the bump must reach every one that
keys a financial fact.

### B.3 3.5.1c files

| Area | File | Change |
| :--- | :--- | :--- |
| Fields | `data/financial/facts.py` | 13 new `FinancialField` members with currency units; `_COMPLETED_ANNUAL_SERIES_FIELDS` grows by the same 13 |
| SEC | `data/sec_edgar/financial_facts.py` | a candidate and parse routine per concept priority list, following the existing annual operating-cash-flow routine; revenue concepts never summed |
| Fixtures | `evaluation/fixtures/sec_edgar/annual_facts/` (new) | trimmed facts, including the filings of the depreciation evidence |
| Evidence | `STEP_3_5_1_MAPPING_EVIDENCE.md` | the field-mapping rows and the depreciation evidence |

### B.4 The fields

Candidate concepts are those of [Slice inputs §3](STEP_3_5_SLICE_INPUTS.md#3-351--data-mappings-and-applicability); the
evidence record pins each one. Existing fields reused: operating cash flow, capital expenditures, stockholders' equity,
common shares outstanding.

| Slice | Fields | Kind |
| :--- | :--- | :--- |
| 3.5.1b | total assets, total liabilities, current assets, current liabilities, cash and equivalents, short-term investments, long-term investments, net PP&E, receivables, retained earnings, short-term borrowings, current portion of long-term debt, noncurrent long-term debt, long-term debt (direct total), lease liabilities counted as debt, preferred stock, noncontrolling interest | balance at a date |
| 3.5.1c | sales, cost of revenue, gross profit, operating income, SG&A, D&A, depreciation alone, interest expense (gross), pretax income, income tax expense, net income, income from continuing operations, discontinued operations | period amount |

The fields have no production consumer until 3.5.3. Tests and the live evidence are their only users until then.

**What 3.5.2 must do with them** (decisions H7 to H12): compare the date of a year-end share count with the anchor
fiscal year-end and go to the cover-page basis when they differ, because the year-end selection returns the latest
tagged year (Nutrien's IFRS count is for the year before); read a component whose mapping is unsupported, or that is
absent for a reason other than "not tagged", as `unavailable` and never as zero; read an IFRS total debt as `unavailable`
while the noncurrent long-term debt mapping is unsupported; and use Alphabet and Honeywell as the reconciliation cases of
Shared definitions §6.

### B.5 3.5.1d files

| Area | File | Change |
| :--- | :--- | :--- |
| Types | `data/market_data.py` | `SplitEvent` (ex-date, ratio), `SplitAdjustedHistory` (close frame, the events, the context and the adjustment date), and a `SplitAdjustedHistoryProvider` protocol beside `MarketDataProvider` |
| Yahoo | `data/yfinance/client.py` | `fetch_split_adjusted_history` downloads with `auto_adjust=False` and `actions=True`, keeps `Close` and `Stock Splits`, never reads `Adj Close`; a missing column is an unexpected response; no splits is an empty list |
| Cache | `data/cached_client.py`, `data/repositories/market_data.py` | the response is cached as its own kind of entry, distinguishable from the dividend-adjusted series by its stored `price_adjustment`; an entry for the live path is accepted only on the day of the quote |
| Scaling | `analysis/shared/split_adjustment.py` (new) | `scale_share_count(count, filing_date, adjustment_date, events)` (pure) |
| Fixtures | `evaluation/fixtures/sec_edgar/split_history/` (new) | trimmed rows of the NVIDIA, Walmart and Commerce Bancshares cases |
| Live check | `tests/live/test_provider_response_shape.py` | one `live_network` test for the split-history request |

Starting point to confirm first: whether the market-data cache key already separates the two adjustment modes. If it does
not, the key gains the mode and the cache schema version is bumped.

### B.6 Result shapes

```text
AsFiledSic (frozen)                    3.5.1a
  code: int                            four digits, 0000 refused
  cik: str                             the issuer's CIK, equal to the filer block's
  accession: str                       equal to the anchor filing's
  filing_date: date                    equal to the submissions filing date
  accepted_at: datetime                aware; not after the boundary
  source_url: str                      the exact header URL
  retrieved_at: datetime               aware

AsFiledSic unavailable reasons         header missing (404), no filer block for the CIK, no or malformed code,
                                       accession or filing-date mismatch, accepted after the boundary

IndustryClass                          FINANCIAL, UTILITY, MANUFACTURER, OTHER
                                       (the absence of a class is None, never a member)
SectorGate (frozen, one per strategy)  gated: bool; not_applicable: frozenset[IndustryClass]; warn: frozenset[IndustryClass]
applicability_of(gate, class | None)   returns ApplicabilityOutcome(outcome, reason_code, industry_class)
  outcome                              APPLIES, APPLIES_WITH_WARNING, NOT_APPLICABLE, UNAVAILABLE
  reason_code                          INDUSTRY_CLASS_NOT_APPLICABLE for NOT_APPLICABLE,
                                       INDUSTRY_CLASS_UNKNOWN for UNAVAILABLE, otherwise None

SplitEvent (frozen)                    3.5.1d
  ex_date: date; ratio: float          finite and positive
SplitAdjustedHistory (frozen)
  close: frame indexed by date         Close only, split-adjusted, not dividend-adjusted
  events: tuple[SplitEvent, ...]       ordered by ex-date; stock dividends appear as fractional ratios
  context: MarketDataContext           price_adjustment names the split-only basis
  adjustment_date: date                the date of the response; the end of the scaling window
```

`applicability_of` maps an unknown class for an ungated strategy to `APPLIES` with the class unknown stated, as
Piotroski needs. `NOT_APPLICABLE` becomes `MetricStatus.NOT_APPLICABLE` and `UNAVAILABLE` becomes
`MetricStatus.UNAVAILABLE` where a strategy turns the outcome into a metric; no status is added.

### B.7 3.5.1a tests

- **Classification:** each of the bank, insurer, REIT, utility and manufacturer of the evidence classifies from its
  trimmed header; every range edge (1999 and 2000, 3999 and 4000, 4899 and 4900, 4999 and 5000, 5999 and 6000, 6799 and
  6800) lands in the right class; a code in no range is `OTHER`.
- **Matrix:** each distinct gate shape of the Shared definitions §1 table, built in the test, for every class: not
  gated with a warning for financial issuers (Piotroski's shape), not applicable for financial issuers, and not
  applicable for financial issuers and utilities (Magic Formula's); a gated gate with an unknown class is
  `UNAVAILABLE`; an ungated gate with an unknown class `APPLIES` and says so.
- **Parser:** the single-filer header; the combined filing (Prologis, Duke Energy) takes the issuer's own block whatever
  its position; a header with no block for the CIK, no `ASSIGNED-SIC`, `0000`, a three-digit code, a non-numeric code, an
  accession that differs, a filing date that differs from the submissions date; trailing and leading whitespace.
- **Boundary:** accepted at the boundary is kept; one second after is rejected; the current `sic` is never read (a
  submissions payload whose `sic` differs from the header's changes nothing).
- **Transport:** the URL pattern accepts only the archive host, a numeric CIK, 18 digits and the accession file name;
  traversal, another host, a query string and an `.htm` name are refused; a redirect is refused; a body over the limit is
  refused; a 404 is an unavailable header, a server fault is the classified provider error.
- **Request count:** one header request per analysis scope however many times the class is asked for; four filing
  documents and the header together are allowed.
- **Reason codes:** both members present; the regenerated schemas validate; existing outputs differ only in the schema
  enumerations.
- **Live check** (`live_network`, excluded from the gate): at most one request, asserts a `<ASSIGNED-SIC>` of four digits,
  an acceptance time of 14 digits and a matching accession, never a value.

### B.8 3.5.1b tests

- Each new field carries the currency unit; existing fields and stored values are unchanged.
- Exact-date selection of three year-ends; the newest balance sheet is never returned for an earlier date; a year-end the
  filing does not report is absent, not substituted.
- 52/53-week pairs accepted; quarters, year-to-date and stub years rejected.
- A filing after the boundary, a later comparative restatement, a conflicting duplicate, and a wrong CIK, taxonomy or
  currency are each rejected or reported as the rules require.
- A value from an earlier filing for a year-end the anchor filing does not report (the comparative rule of Shared
  definitions §3) passes the same boundary check and the same taxonomy and currency.
- A direct long-term-debt total is returned beside its parts and is not added to them here; commercial paper belongs to
  short-term borrowings and is never the current portion of long-term debt; a US GAAP operating-lease liability is not
  the lease field and an IFRS lease liability is.
- **Derived total liabilities (H3):** a match with the tagged value, a mismatch reported, and a missing term; temporary
  equity subtracted where tagged and never added twice; the IFRS derivation is not offered (H8).
- **Equivalent concepts (H10):** the first listed concept that is tagged is used for every date of a run and is named in
  the resolved input; a date the run's concept does not cover is absent with its own reason, not filled from another
  listed concept; a field with no listed concept tagged is absent as not tagged; an unsupported mapping is reported as
  unsupported.
- **Net PP&E under IFRS (H11) and unsupported IFRS mappings (H8, H12):** the plain concept wins, the right-of-use
  variant is used alone, the two are never summed; short-term investments, long-term investments, the direct debt
  total, noncurrent debt and preferred stock are unsupported under IFRS.
- **Cover-page fallback (H7):** a separate `basis`; used only when tagged as a single non-dimensional total in the
  anchor filing; its own date is the share-count date; a multi-class filer with per-class counts only gives none; the
  existing year-end path never returns it.
- The cache: an entry stored under the older version is refused and fetched again; a new entry round-trips.
- Graham's latest-only selection returns what it returned before, for every stored fixture.
- **Share-count coverage (G1, H4, H7):** from trimmed captured filings, `COMMON_SHARES_OUTSTANDING` resolves for each issuer
  of the regression set at its latest year-end by the direct concept, the IFRS direct concept or the issued-minus-treasury
  fallback, and the test records which path gave it. Walmart, SAP and Nutrien give no year-end count on any
  balance-sheet path; the cover-page basis gives Walmart's and SAP's count and gives Nutrien none, which is `unavailable`,
  not zero. The year-end basis never returns a cover-page count.

### B.9 3.5.1c tests

- Each new field carries the currency unit; the series set accepts them and still refuses other fields.
- Total revenue is not confused with a segment figure; overlapping revenue concepts are never summed.
- Depreciation alone is the year's expense, not accumulated depreciation; where both are reported the identity
  D&A = depreciation + amortization is checked on the captured filing.
- Pretax income, tax expense, continuing and discontinued income are read from the same fiscal period.
- A filing that reports only combined D&A, one that reports depreciation alone and one that reports both each resolve as
  the evidence record states, for us-gaap and ifrs-full.

### B.10 3.5.1d tests

- **The close:** `Close` of an `auto_adjust=False` response is used and `Adj Close` is never read; the last trading day on
  or before `as_of` is chosen, a day with no bar before it falls back to the previous bar, and an `as_of` before the first
  bar is unavailable; the dividend-adjusted series of Momentum is unchanged.
- **Scaling (`scale_share_count`):** a split with an ex-date after the filing date scales the count; one before it does
  not; one on the filing date does not; two splits compound; a fractional ratio (1.05) scales the count and is not
  issuance; a zero, negative or non-finite ratio is refused; no events means no scaling, and a response without the
  `Stock Splits` column is an unexpected response rather than "no splits".
- **NVIDIA:** the count of 2,464,000,000 from the filing of 2024-02-21 with the 10-for-1 split of 2024-06-10 is scaled to
  24,640,000,000, and 86.402 × 24,640,000,000 equals 864.02 × 2,464,000,000.
- **Walmart fiscal 2024:** the count comes from the filing made after the 3-for-1 split of 2024-02-23, which restates it;
  with the split's ex-date before the filing date the count is not scaled, and scaling from the fiscal year-end is shown to
  give a result three times larger, as the test's negative case.
- **A later filing:** the NVIDIA fiscal 2025 filing's restated comparative for 2024-01-28 (24,643,000,000, filed
  2025-02-26) is not scaled by the June 2024 split.
- **Boundary:** a split after `as_of` still scales the count, because the provider has adjusted the close for it; it never
  changes the market cap at the boundary.
- **Cache:** a cached response is returned with its original adjustment date; the live path refuses a response from another
  day; the two adjustment modes never share an entry.
- **Live check** (`live_network`, excluded from the gate): at most one request, asserts the `Close` and `Stock Splits`
  columns and finite positive ratios, never a value.

### B.11 User-visible changes

- 3.5.1a: two reason codes; the three schemas that enumerate them are regenerated. No stored run changes meaning.
- 3.5.1b: the financial-fact cache version changes, so cached facts are fetched again once. The `PeriodKind` enumeration
  gains `instant` in the schemas that list it, which the schema check regenerates.
- 3.5.1c and 3.5.1d: none expected; each pull request states any it finds.

### B.12 TOOL_DEVELOPMENT edit sites

No sub-slice adds a strategy, so none of the edit sites of
[`docs/TOOL_DEVELOPMENT.md`](../../../../TOOL_DEVELOPMENT.md#edit-sites-of-a-strategy) is touched. The `schema` site's
regeneration command is run by 3.5.1a and 3.5.1b because the schemas they regenerate list the enumerations; that is a
use of its command, not an edit of its site. The conformance tests (T7, T8, T15, T16, T20, T21) are expected to pass
unchanged; a failure would mean a strategy file was touched.

### B.13 Documentation

| Document | 3.5.1a | 3.5.1b | 3.5.1c | 3.5.1d |
| :--- | :--- | :--- | :--- | :--- |
| `STEP_3_5_1_MAPPING_EVIDENCE.md` | live-check note | field rows | field and depreciation rows | split-history live-check note |
| `STEP_3_5_SHARED_DEFINITIONS.md` | none (amended by the planning commit) | §3 (absent-component convention, H10) and §4 (share-count rule, H7) | none | none |
| `STEP_3_5_CONTRACT_AND_SLICE_PLAN.md` | none | Appendix A.12 (H7 reverses part of A.6) | none | none |
| `docs/user/GLOSSARY.md` | "industry class", "as-filed SIC code" | none | none | "split-adjusted close" |
| `docs/user/FINANCE_MATH.md` | none: no formula | none | none | none until 3.5.2 states the market cap |
| `docs/project/PROVIDER_DEBUGGING.md` | the header request, if it lists the live checks | none | none | the split-history request, if it lists the live checks |
| This plan and the contract | status rows | status rows | status rows | status rows, 3.5.1 closed |
