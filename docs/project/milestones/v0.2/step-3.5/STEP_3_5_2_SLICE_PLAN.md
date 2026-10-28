# Step 3.5 slice 3.5.2 — Shared metrics and ranking helper: Slice Plan

The slice plan for [slice 3.5.2](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#352--shared-metrics-and-ranking-helper) of Step 3.5.
It covers five sub-slices. It was written against `main` at `3305ec3`; 3.5.2c was split in two at `b650c3b`
([A.5](#a5-decisions-at-the-start-of-352c-2026-10-26)); 3.5.2d began from `main` at `8397dee`
([A.7](#a7-decisions-at-the-start-of-352d-2026-10-27)).

Placement among other work packages: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **What this plan does:** defines the metrics every screening strategy shares, once, and the code that feeds them, in
  five steps: the ranking helper (3.5.2a); the pure shared metrics (3.5.2b); the listing check for market cap (3.5.2c);
  the shared input assembly (3.5.2d); and FCF-Growth's adoption of the shared market cap (3.5.2e).
- **What it is not:** a strategy, a ranked view, a valuation multiple or a threshold. No new strategy is added, and the
  FCF and FCF-yield formulas do not change. Full list: [Scope limits](#4-scope-limits).
- **Rules every sub-slice follows:**
  - One definition per shared metric, in [Shared definitions](STEP_3_5_SHARED_DEFINITIONS.md), with no per-strategy
    variant. No strategy imports another strategy's calculators.
  - Every calculated number is a `MetricResult` with an explicit `ReasonCode`. Nothing missing becomes zero, neutral or
    `NaN`; the absent-component rules of Shared definitions §3 and §6 are the only cases in which an absence yields a
    number.
  - A change to a persisted shape bumps that shape's version field, with no migration or compatibility decoder
    ([AGENTS.md §4](../../../../../AGENTS.md)). Each sub-slice lists such a change among its user-visible changes.
  - Where a sub-slice meets a data case no decision covers, it stops and asks the project owner (K17). The one
    delegation is the title vocabulary of the listing check (K5″b), with the document it reads and its `10-K/A` rule;
    its decisions are recorded in [A.6](#a6-decided-under-delegation-during-352c-2026-10-26).
  - The managed quality gate after every sub-slice, and explicit authorization before the next begins.
  - No registry, plugin loader or factory is added; the new code is plain functions and frozen types.
- **Where the detail lives:** the file inventories, result shapes, tests and documentation changes are in
  [Appendix B](#appendix-b-file-inventories-tests-and-documentation); decision records are in
  [Appendix A](#appendix-a-decision-records); the evidence is in the
  [mapping evidence record](STEP_3_5_1_MAPPING_EVIDENCE.md) and the
  [listing evidence record](STEP_3_5_2_LISTING_EVIDENCE.md).

## 2. Sequence and status

Each sub-slice ends with the managed quality gate and is gated by explicit authorization before the next begins.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| 3.5.2a | [Slice plan and ranking helper](#352a--slice-plan-and-ranking-helper) | Complete | 2026-10-26 |
| 3.5.2b | [Pure shared metrics](#352b--pure-shared-metrics) | Complete | 2026-10-26 |
| 3.5.2c | [Listing check for market capitalization](#352c--listing-check-for-market-capitalization) | Complete | 2026-10-26 |
| 3.5.2d | [Shared input assembly](#352d--shared-input-assembly) | Complete | 2026-10-28 |
| 3.5.2e | [FCF-Growth adopts the shared market cap](#352e--fcf-growth-adopts-the-shared-market-cap) | Next | |

3.5.2a is implemented on the branch that carries this plan and merges as one pull request, as 3.5.1a did. Each later
sub-slice has its own branch off `main`, named `feat/step-3-5-2<letter>-<topic>`, after the previous pull request merges.

## 3. The sub-slices

### 3.5.2a — Slice plan and ranking helper

- **Problem:** Magic Formula (3.5.6) is the first strategy that ranks across members, and any later multi-metric ranking
  would otherwise re-implement tie handling, percentiles and missing-data exclusion.
- **Decision (K13):**
  - A pure function over frozen types in `investment_analysis_engine/analysis/shared/ranking.py`, with no knowledge of
    strategies, runs or persistence, and no registry, base class or weights parameter.
  - Each member carries a ticker, an opaque issuer key and one `MetricResult` per requested metric. A result that is not
    `ok` excludes the member and carries its own reason code and reason.
  - Behavior is exactly Shared definitions §9: deduplicate by issuer, then decide eligibility, then enforce the minimum,
    then average ranks, display percentile, equal-weight rank sum and competition positions.
  - The minimum of 10 eligible members is the module constant `MINIMUM_ELIGIBLE_MEMBERS`, not a parameter. Ranks are
    compared exactly, with no tolerance.
  - A caller error (no metrics, repeated metric names, repeated tickers after upper-casing, a member without an entry
    for a requested metric) raises `ValueError`; an unavailable value is not an error.
- **Scope:** this plan and the document amendments listed in [B.14](#b14-documentation); `ranking.py`; its tests; the
  ranking entry of `FINANCE_MATH.md`. The file list is in [B.1](#b1-352a-files).
- **Branch:** `feat/step-3-5-2a-ranking-helper` (this branch; plan and implementation are one pull request).
- **Detail:** [files](#b1-352a-files), [result shape](#b6-result-shapes), [tests](#b7-352a-tests).

### 3.5.2b — Pure shared metrics

- **Problem:** market cap, gross profit, EBIT, D&A, EBITDA, total debt, EV and invested capital are defined in prose
  only, and FCF and FCF yield live in FCF-Growth's own package, where a second strategy would have to import them.
- **Decision (K5″ to K8, K12, K14, K16, L1 to L7):**
  - Each metric is a pure function over resolved facts, with no I/O, that returns a `MetricResult` plus the operands and
    provenance it used, in the module K14 names.
  - Market cap is available only for a 10-K or 10-K/A anchor filing, equal known quote and filing currencies, a listing check
    that affirms the ticker and the share-count rule for several classes (K5″, which supersedes K5). The pure
    function only takes the listing check's outcome (K5″a). Gross profit is reported, else sales minus cost of
    revenue (K6). Short-term investments are zero-if-absent only on a classified balance sheet (K7).
  - The functions take the types 3.5.1 already returns: a balance-sheet value is a `ResolvedInput` or an
    `InstantAbsence`, and an annual value is a `ResolvedInput` or `None` (L1). One table maps an absence reason to a
    reason code (L2). Market cap and EV each have their own frozen result type; every other metric shares one
    (L3, M3).
  - `compute_free_cash_flow` and `compute_fcf_yield` move to `analysis/shared/cash_flow.py` unchanged in behavior; the
    copies in FCF-Growth are deleted and FCF-Growth imports them from there (K8).
  - Two reason codes are added: `unsupported_mapping` and `debt_not_visible`. `nonpositive_denominator` is added by
    the first slice that produces it, because invested capital at or below zero is an `ok` value here (L5, which
    amends K12). The schemas that list `ReasonCode` are regenerated with no document version bump (G4 of the 3.5.1
    plan).
  - The planning labels in `strategies/fcf_growth/calculators.py`'s module docstring are replaced by durable wording
    (K16).
- **Scope:** the modules of [B.2](#b2-352b-files), the moved FCF functions and their tests, the two reason codes and
  the regenerated schemas, and the `FINANCE_MATH.md` entry of every shared metric.
- **Branch:** `feat/step-3-5-2b-shared-metrics`, off `main` after the 3.5.2a pull request merged.
- **Detail:** [files](#b2-352b-files), [result shapes](#b6-result-shapes), [tests](#b8-352b-tests).

### 3.5.2c — Listing check for market capitalization

- **Problem:** market cap is available only for a share of the issuer (K5″), and the structured data cannot say whether a
  ticker is a share, a depositary share, a unit, a warrant or a preferred security. The anchor 10-K's cover can.
  3.5.2b made the check's outcome an input of the pure market-cap function; nothing yet produces it.
- **Decision (K5″, K5″a, K5″b, M2, N2 to N4, P1 to P21):**
  - **The check reads one document of the anchor filing:** the rendered cover (`R1.htm`), requested directly (or, when
    that page is not a cover, the report the filing summary marks as the cover, P19), once per
    analysis scope and for the requested ticker, under the existing bounded, no-redirect transport with a policy of its
    own (P1 to P3). It is outside the four-document limit, and it works with `as_of`, because the cover of a filing
    accepted on or before the boundary is historical evidence.
  - **The data layer returns typed listing evidence,** not a `ListingCheck` (the data layer cannot import `analysis`):
    the requested ticker's title as filed, its kind, the CIK, the accession and form read and the source URL; or the
    reason no cover could be read. The new module `data/sec_edgar/cover_listing.py` sits beside `security_unit.py`;
    Graham's parser, verifier and rule are unchanged (P14).
  - **One pure function in `analysis/shared/market_cap.py`** turns that evidence into the `ListingCheck` the market-cap
    function takes: a share of the issuer is affirmed; a depositary share, unit, warrant or preferred security is
    refused with `incompatible_units`; a ticker the cover does not list, a title outside the vocabulary and a cover
    that cannot be read are `missing_fact`.
  - **The title vocabulary, the document and the `10-K/A` rule were decided from captured covers** under the delegation
    and are recorded in [A.6](#a6-decided-under-delegation-during-352c-2026-10-26); the captured evidence is in the
    [listing evidence record](STEP_3_5_2_LISTING_EVIDENCE.md).
  - **The capability is routed** through `ProductionFinancialFactsProvider` as an optional capability, so 3.5.2d can call
    it. Nothing calls it in production yet.
- **Scope:** the cover module, the adapter method, the production routing, the pure function, the trimmed covers and
  their tests, one live check, and the documents of [B.14](#b14-documentation). The file list is in
  [B.3](#b3-352c-files).
- **Branch:** `feat/step-3-5-2c-listing-check`, off `main` at `b650c3b` (the 3.5.2b pull request had merged).
- **Detail:** [files](#b3-352c-files), [result shapes](#b6-result-shapes), [tests](#b9-352c-tests),
  [decisions](#a6-decided-under-delegation-during-352c-2026-10-26),
  [evidence](STEP_3_5_2_LISTING_EVIDENCE.md).

### 3.5.2d — Shared input assembly

- **Problem:** the shared metrics need the anchor year-end, a share count, a price, the split history and balance-sheet
  and annual inputs at one year-end. Left to each consumer, seven strategies would assemble them seven ways. Two gaps on
  `main` also block it: the production financial-facts provider does not route the balance-sheet series, and the
  split-history provider protocol cannot carry the arguments the cached client takes.
- **Decision (K3, K4, K15, N5 to N8, S1 to S6):**
  - One assembly in `analysis/shared/metric_inputs.py` finds the anchor year-end *t*, resolves the share-count path
    (year-end count, else the cover-page count; Shared definitions §4), the price with or without `as_of`, the split
    history, and the balance-sheet and annual inputs at *t*, and calls the listing check of 3.5.2c through the
    production provider.
  - **One function per input family (N5):** the anchor year-end; the market-cap inputs; balance-sheet values at *t* for
    named fields; annual values at *t* for named fields. A provider failure is returned as a typed failure carrying its
    provider-failure record, never raised.
  - **Currency (N6):** the filing currency of market cap is the currency of the monetary facts the consumer resolved at
    *t*, never the currency requested in a configuration. The quote currency comes from the resolved quote on the live
    path, and from the split-history response with `as_of`. Market cap takes only the quote currency from the quote
    path (N8).
  - **Split history (N7):** the request starts at the date the count is scaled from, minus a named margin of 10
    calendar days.
  - **Identity:** the assembly relies on the identity rule of issue #190: a ticker names the registrant it maps to today, and every input is that registrant's evidence as filed or priced at the boundary ([Architecture](../../../ARCHITECTURE.md#which-registrant-a-ticker-names)); the listing check applies P22 to a renamed ticker.
  - **Year-end *t* is found once,** from the `reportDate` the submissions data already gives the anchor filing. No
    new request is made: the column is in the recent block and on the extra pages, and for all eleven regression
    issuers it equals the period end of the anchor filing's own facts ([A.7](#a7-decisions-at-the-start-of-352d-2026-10-27)).
  - **Dependencies (S1):** a consumer's analyzer receives the `InputResolver`, the split-history client and the
    cover-listing capability at construction. The assembly functions take them as arguments and hold no state.
  - **The live path (S2)** also reads the split history, with `adjusted_on` set to the quote's date, so the count is
    scaled by every split after its source date up to the quote: two market-data requests per live run.
  - **Share count (S4):** the year-end count is used when its date is *t*. Only when it differs, or none exists, is the
    cover-page count requested. The pure market-cap function keeps its own date check as a second guard.
  - **Two typed outcomes (S6),** never exceptions out of the assembly. An annual report that came only after the
    boundary is returned once, as unavailable with `not_available_as_of` and the adapter's message, and nothing more is
    requested. A registrant with no annual report at all is a provider failure raised when the analysis scope opens,
    and is returned as the typed failure of N5 with its provider-failure record.
  - **Tests (S3)** use price frames and quotes built in the tests, the captured split histories and the captured SEC
    fixtures served through the real adapter. No new live capture is made for the tests.
  - FCF yield requires FCF-Growth's latest observation to end at *t*; otherwise it is `unavailable` with
    `incompatible_period` and never computed from an older year (Shared definitions §3).
  - A run with `as_of` takes its close by Momentum's existing rule: a date-only `--as-of` includes that day's close, and
    sessions are read by exchange-local date. The guides state the limitation (K15).
  - `ProductionFinancialFactsProvider` routes `fetch_instant_series`, and a split-history provider protocol that
    declares `as_of` and `adjusted_on` is added beside the existing one (D20 and D23 of the 3.5.1 plan).
  - **Review corrections ([A.9](#a9-review-decisions-2026-10-28)).** The snapshot finds the anchor on the extra
    submissions pages when the recent block holds no annual filing at or before the boundary (T1), and annual values
    come through a new resolver entry, `InputResolver.resolve_annual_series`, not from the provider directly (T2).
- **Scope:** the assembly module, the two gaps, the two review corrections, fixtures and tests. The file list is in
  [B.4](#b4-352d-files). It is one sub-slice (S5).
- **Branch:** `feat/step-3-5-2d-input-assembly`, off `main` after the 3.5.2c pull request merged.
- **Detail:** [files](#b4-352d-files), [result shapes](#b6-result-shapes), [tests](#b10-352d-tests).

### 3.5.2e — FCF-Growth adopts the shared market cap

- **Problem:** FCF-Growth's optional FCF yield is always unavailable, because no market-cap evidence exists. Its stored
  `market_capitalization` is a bare resolved input that cannot hold a share count, a price and the splits applied.
- **Decision (K9, K10, K11, K16):**
  - `market_capitalization` becomes the shared market-cap type: value, share count with its basis (year-end or cover
    page) and date, the filing date of the count's source, price and price date, the splits applied, and provenance.
  - `SCHEMA_VERSION` goes from 5 to 6, with the codec and document versions as `AGENTS.md` §4 requires.
    `METHOD_VERSION` stays 2: the contract calls this evidence becoming available, not a formula change.
  - A market-data failure makes the yield `unavailable` with `provider_error` and a warning. The run's
    `execution_status` and the classification do not change, because the yield is informational only; the run
    succeeds, so no automatic provider check fires. The valuation strategy decides its own mapping in 3.5.5.
  - The success fixture gains a share-count fixture and a split-history fixture so one golden case has the yield `ok`;
    a test asserts every other expected value is unchanged.
  - `FINANCE_MATH.md`'s "current market capitalization" becomes "market capitalization at the boundary", and the stale
    version docstrings in `strategies/fcf_growth/models.py` are corrected (K16).
  - **Open decision for this sub-slice (T2, [A.9](#a9-review-decisions-2026-10-28)):** whether FCF-Growth's own annual
    reader (`_resolve_field` in `strategies/fcf_growth/input_resolver.py`, which calls the provider directly and keeps
    its own cache of the series) moves onto `InputResolver.resolve_annual_series`. For it: one set of provider-response
    checks and one trace for every consumer of the series. Against it: its cache, its alignment of periods across
    fields and its stored shape are its own, and a move that changed any stored output would need the version bump of
    `AGENTS.md` §4. It is decided with the stored-shape change of this sub-slice, and by the project owner if it would
    change a stored output.
- **Scope:** the composition sites, the analyzer and result, the stored shape and its versions, fixtures and tests. The
  file list is in [B.5](#b5-352e-files).
- **Branch:** `feat/step-3-5-2e-fcf-market-cap`, off `main` after the 3.5.2d pull request merges.
- **Detail:** [files](#b5-352e-files), [result shapes](#b6-result-shapes), [tests](#b11-352e-tests).

## 4. Scope limits

- No new strategy, ranked view, valuation multiple, threshold or presentation. The ranked refresh view is 3.5.6 and the
  valuation strategy is 3.5.5.
- No change to the FCF or FCF-yield formulas, and no change to any other existing strategy's formula, classification or
  stored output. Momentum's series is unchanged.
- No weights, persistence, registry, plugin loader or factory, and no knowledge of strategies or runs in the ranking
  helper.
- No lease normalization, no non-recurring adjustment to EBIT, no tolerance in the reconciliation of debt totals.
- No supported IFRS noncurrent long-term debt: IFRS total debt and EV stay `unavailable` while that mapping is
  unsupported ([Shared definitions §6](STEP_3_5_SHARED_DEFINITIONS.md#total-debt)).
- No migration or compatibility decoder. Shapes that change are versioned ([B.12](#b12-user-visible-changes)).
- No delegation of data-mapping decisions to the implementer (K17), except the listing check's title vocabulary
  (K5″b), the document it reads and its `10-K/A` rule.

## 5. Acceptance criteria

**3.5.2a**

- The helper returns the ranks, percentiles, rank sums and positions the tests write out by hand, for either
  direction, ties, tied sums and all values tied.
- The output is identical for every permutation of a small set and for shuffles of a ten-member set.
- Nine eligible members return values and a diagnostic with no ranks; ten return ranks. This holds after deduplication
  and exclusions.
- A kept share class that lacks a metric excludes the issuer and the diagnostic names both classes.
- Every number in the result is finite; each validation error is raised.
- The complete managed gate passes, with at least 85% coverage and every branch of `ranking.py` exercised.

**3.5.2b**

- Each shared metric returns the value, status and reason the tests state for every case of
  [B.8](#b8-352b-tests), including the named issuers.
- FCF-Growth imports FCF and FCF yield from `analysis/shared/cash_flow.py`; no copy remains in its package and no
  strategy imports another strategy's calculators.
- The regenerated schemas list the two new reason codes and nothing else changes in them.
- The gate passes.

**3.5.2c**

- The listing check affirms the requested ticker on a real 10-K cover, including each class of Alphabet, and refuses a
  depositary share on a real 10-K filer's cover with `incompatible_units`. A unit, a warrant and a preferred security
  are refused the same way. A ticker the cover does not list, a title outside the vocabulary, a missing cover, a
  cover without a registration table, a cover under another CIK or form, and a filing accepted after the boundary
  each give `missing_fact` through the pure function.
- The requested ticker's own row decides whatever the other rows hold, and the check reads the cover once per analysis
  scope, outside the four-document limit, with and without `as_of`.
- A transport fault raises the classified provider error. The capability is reachable through the production provider
  and is not called by any production path.
- Graham's security-unit tests pass unchanged. The gate passes.

**3.5.2d**

- One assembly returns, for an issuer and a boundary, the inputs the shared metrics need, or the reason each is
  unavailable. Year-end *t* is found once and every input is taken at it.
- The balance-sheet series is reachable through the production provider, and the split-history protocol carries `as_of`
  and `adjusted_on`.
- A run with and without `as_of` gives the price the rules above state. The gate passes.

**3.5.2e**

- The success golden case has the FCF yield `ok`; every other expected value of every existing case is unchanged.
- A market-data failure leaves the run's status and classification unchanged and the yield `unavailable` with
  `provider_error`.
- Stored runs under result schema 5 are refused by version, never misread. The gate passes.

## 6. Background

[Slice inputs §4](STEP_3_5_SLICE_INPUTS.md#4-352--shared-metrics-and-ranking-helper) described 3.5.2 as one slice in
2026-10-02, with FCF-Growth's market-cap wiring as one line. This plan was written on 2026-10-26 against `main` after
3.5.1 closed. The code showed three things the single slice did not allow for: the share-count, price and split-history
evidence needs an assembly of its own; the production provider and the split-history protocol each lacked a capability
the assembly needs; and FCF-Growth's stored result cannot hold a market cap's evidence without a version change. The
project owner decided the four-way split and the points below the same day
([A.1](#a1-decisions-k1-to-k17-2026-10-26)). Issue #186, a CI-only test failure found on the way, was fixed first as its
own pull request (K1). At the start of 3.5.2c the listing check was separated from the assembly, which made five
sub-slices ([A.5](#a5-decisions-at-the-start-of-352c-2026-10-26)); the records of A.1 to A.4 keep the lettering they
were written under.

---

## Appendix A: Decision records

### A.1 Decisions K1 to K17 (2026-10-26)

Approved by the project owner. Each is stated in the sections above; this table records them.

| # | Topic | Decision |
| :--- | :--- | :--- |
| K1 | Issue #186 | The fix went first as its own pull request. Done: #187, merged 2026-10-26. |
| K2 | Sub-slices | Four, each with its own branch, managed gate and authorization: 3.5.2a the slice plan and the ranking helper, as one pull request; 3.5.2b the pure shared metrics, with no I/O; 3.5.2c shared input assembly; 3.5.2d FCF-Growth adopts the shared market cap. |
| K3 | Shared input assembly | Built in 3.5.2 (3.5.2c), not by each consumer. It covers finding the anchor year-end *t*; the share-count path (year-end count, else the cover-page count; Shared definitions §4); the price, with or without `as_of`, and the split history; and the balance-sheet and annual inputs at *t* that the shared metrics need. It also closes two gaps found on `main`: `ProductionFinancialFactsProvider` (`data/financial/production.py`) does not route `fetch_instant_series`, so production balance-sheet series are refused today; and `SplitAdjustedHistoryProvider` (`data/market_data.py`) declares neither `as_of` nor `adjusted_on`, which the cached client takes (D20 and D23 of the 3.5.1 plan), so 3.5.2c declares a protocol that has them. |
| K4 | Year-end *t* | One shared way to find it, added by 3.5.2c. Its first step checks what the SEC snapshot already exposes about the anchor filing's fiscal year-end, and stops and asks if a new kind of provider request is needed. FCF yield requires FCF-Growth's latest observation to end at *t*; otherwise the yield is `unavailable` with `incompatible_period`, never computed from an older year (Shared definitions §3). |
| K5 | Security unit and currency | Market cap uses the existing fail-closed security-unit rule, `evaluate_security_unit_compatibility` in `data/security_unit.py`, as Graham does: it is available only when the quote currency equals the filing currency and the evidence affirms an ordinary share at 1:1. Consequence: SAP's market cap is `unavailable` (EUR filer, USD ADR). Shared definitions §4 states the rule. |
| K6 | Gross profit | A shared metric (3.5.2b): the reported gross profit; otherwise sales minus cost of revenue when both are reported, keeping both inputs' provenance; never taken from operating income (Strategy specifications, Conventions). Piotroski and Beneish both use it; the mapping evidence's `GROSS_PROFIT` row already assigns it to 3.5.2. |
| K7 | Short-term investments | The absent-component zero applies only when current assets are tagged at that date (a classified balance sheet). Otherwise short-term investments are `unavailable`. Deere's EV is therefore `unavailable` (mapping evidence §5.6). |
| K8 | FCF and FCF yield | They move to `analysis/shared/cash_flow.py` (3.5.2b): `compute_free_cash_flow` and `compute_fcf_yield` move there unchanged in behavior; FCF-Growth imports them from there and its copies in `strategies/fcf_growth/calculators.py` are deleted; no strategy imports another strategy's calculators. |
| K9 | FCF-Growth's result shape | In 3.5.2d, `market_capitalization` becomes the shared market-cap type: value, share count with its basis (year-end or cover page) and date, the filing date of the count's source, price and price date, the splits applied, and provenance. `SCHEMA_VERSION` goes from 5 to 6, with the codec and document versions as `AGENTS.md` §4 requires. `METHOD_VERSION` stays 2, because the contract's §4 calls this evidence becoming available, not a formula change. `FINANCE_MATH.md`'s "current market capitalization" becomes "market capitalization at the boundary". |
| K10 | Market-data failure in FCF-Growth | The yield is `unavailable` with `provider_error` and a warning. The run's `execution_status` and the classification are unchanged, because the yield is informational only. The run succeeds, so no automatic provider check fires. The valuation strategy decides its own mapping in 3.5.5. |
| K11 | Evaluation fixture | FCF-Growth's evaluation success fixture gains a share-count fixture and a split-history fixture, so that one golden case has the yield `ok`. A test asserts that every other expected value is unchanged. |
| K12 | Reason codes | Reused: `missing_fact`, `ambiguous_fact` (a conflict, or a direct total that does not reconcile with its parts), `not_available_as_of`, `incompatible_currency`, `provider_error`, `market_cap_unavailable`. Added in 3.5.2b: `unsupported_mapping`, `debt_not_visible` (a related concept is tagged, or interest expense is positive with no mapped debt) and `nonpositive_denominator` (invested capital ≤ 0, and later EV/EBITDA). The schemas that list `ReasonCode` are regenerated with no document version bump (G4 in the 3.5.1 plan). |
| K13 | Ranking-helper details | The minimum of 10 eligible members is a named module constant, not a parameter (`AGENTS.md` §9); Shared definitions §9's "named, documented default" is reworded to say so. Ranks are compared exactly, with no tolerance, because they are multiples of one half. The issuer key is an opaque string the caller supplies. Tickers sort by ordinal comparison after upper-casing. Deduplication happens before eligibility, as Shared definitions §9 orders it; when the kept share class lacks a metric, the issuer is excluded even if another class has the value, and the diagnostic names both classes. Each member's value per metric is a `MetricResult`; a non-`ok` result excludes the member, carrying its reason code and reason message. |
| K14 | Placement | Under `analysis/shared/`: `ranking.py`; `market_cap.py`; `operating_metrics.py` (gross profit, EBIT, D&A, EBITDA); `enterprise_value.py` (total debt, EV); `invested_capital.py`; `cash_flow.py` (FCF, FCF yield); `metric_inputs.py` (the assembly). |
| K15 | Close with `as_of` | A run with `as_of` takes its close by Momentum's existing rule: a date-only `--as-of` includes that day's close, and sessions are read by exchange-local date. The guides state the limitation. |
| K16 | Stale text | Fixed in the sub-slice that touches its file, not filed for later: `strategies/fcf_growth/models.py`'s version docstrings ("fixed at 1") and its comment "method_version = 2 / schema_version = 4", in 3.5.2d; the planning labels "Slice B" and "Slice C" in `strategies/fcf_growth/calculators.py`'s module docstring (`AGENTS.md` §4), in 3.5.2b. |
| K17 | Data-mapping decisions | The delegation of data-mapping decisions to the implementer stays paused for 3.5.2. Where a sub-slice meets an undecided data case, it stops and asks the project owner. |

### A.2 Wording the plan settles (3.5.2a)

Points where a decision above needed a more exact statement. They add no behavior; the project owner can reverse any.

| Topic | Wording |
| :--- | :--- |
| Exclusion reasons | An excluded member lists one reason per metric that excluded it, in the order of the requested metrics, each with the result's own status (`unavailable` or `not_applicable`), reason code and reason message. The exclusion also carries the member's values, `None` where a metric was not `ok`, so that a result below the minimum carries every member's values. |
| Ticker form | The ticker is stripped and upper-cased when the member is built, so the helper returns tickers in that form. A blank ticker or issuer key is refused when the member is built. The issuer key is opaque and is compared exactly. |
| Naming diagnostic | When the kept class lacks a metric another class has, the helper reports it as its own diagnostic (`kept_class_lacks_metric`) naming both tickers, in addition to the ordinary exclusion and the deduplication diagnostic. If no other class has the value, no naming diagnostic is added. |
| Result fields | The result lists the eligible members in ticker order whether or not ranks exist, and the ranked members in display order (position, then ticker) only when the minimum is met. Ranks, percentiles, sums and positions are typed fields; none is a `MetricResult`. |

### A.3 Decisions at the start of 3.5.2b (2026-10-26)

Approved by the project owner. K5″ supersedes the K5 row of A.1, which is left as recorded.

| # | Topic | Decision |
| :--- | :--- | :--- |
| K5″ (supersedes K5) | Market-cap availability | Market cap does not use `evaluate_security_unit_compatibility`. That rule's evidence (`resolve_security_unit` in `data/sec_edgar/financial_facts.py`) refuses every run with `as_of`, every filer other than a us-gaap 10-K filer, and any cover with more than one class title (Alphabet). Market cap is available only when all four hold: (1) the anchor annual filing is a 10-K, because a 20-F or 40-F filer is a foreign private issuer whose US listing may be a depositary receipt at a ratio the structured data cannot show; (2) the quote currency equals the filing currency, and when either is unknown market cap is `unavailable`; (3) a listing check on the anchor 10-K's cover affirms the requested ticker, which must appear there under this CIK on a registered title that is a share of the issuer (class designations and "ordinary shares" are accepted; depositary shares, units, warrants and preferred securities are refused; a missing or unreadable cover is `unavailable`; the check works with `as_of`, because the cover of a filing on or before the boundary is historical evidence); (4) the existing count rule for several classes (Alphabet's single combined count is valued at the requested ticker's price, and per-class counts with no total are `unavailable`). Graham's security-unit verifier and its rule are unchanged. A ticker renamed after the anchor filing is affirmed only by the rename rule of P22 (decided by the project owner, 2026-10-27); every other renamed ticker does not match the cover and is `unavailable`, a limitation the guides state. |
| K5″a | Placement of the listing check | The listing check (cover reading, parser rule, captured covers and the refusal case) is the first step of 3.5.2c, before the assembly. In 3.5.2b the pure market-cap function only takes its outcome. |
| K5″b | Title vocabulary | Which registered titles count as a share of the issuer, and which are refused, is delegated to the implementer of 3.5.2c. It is decided from captured covers, under the standing delegation for data-mapping judgment, and recorded in this plan. That step stops and asks if it cannot show the depositary-share refusal on a real 10-K filer. K17 is otherwise unchanged. |
| L1 | Operand types | The pure functions take the types 3.5.1 already returns, and no new operand type duplicates one. A balance-sheet value at year-end *t* is a `ResolvedInput` or an `InstantAbsence`. An annual value at *t* is a `ResolvedInput`, or `None` for "reported none for year *t*"; the assembly passes `None` only for a real absence and never calls a metric after a provider error. Market cap additionally takes the price and its date, the split events and adjustment date, the anchor filing's form, the filing and quote currencies, and the listing check's outcome. An input unavailable for another reason (no share count, conflicting or per-class counts, no price) arrives as a typed absence carrying a reason code and a reason message: one small frozen type, `InputUnavailable`. |
| L2 | Absence reason codes | One table maps an absence reason to a reason code, used by every metric: `not_tagged`, `other_concept` and `no_anchor_filing` give `missing_fact`; `conflict` gives `ambiguous_fact`; `unsupported` gives `unsupported_mapping`; `after_boundary` gives `not_available_as_of`; `basis_mismatch` gives `incompatible_scope`. The absent-component zero applies only to `not_tagged`. |
| L3 (amended by M3) | Result types | Market cap and EV each have their own frozen result type; market cap's is the one FCF-Growth stores in 3.5.2d. Every other metric shares one frozen type: the `MetricResult`, the named operands, the components taken as zero, and diagnostic messages. A module not named in K14, `metric_evidence.py`, holds the shared type and the table of L2. |
| L4 | Issuer test inputs | The issuer cases (Alphabet, Honeywell, Monster, Nutrien, Deere, Walmart, SAP) take their inputs from the real SEC adapter serving the captured 3.5.1 fixtures, through `tests/_sec_instants.py` and the resolver; numbers are never retyped from the evidence record. NVIDIA has no SEC fixture and stays synthetic, with the figures of the 3.5.1 plan's B.10. Edge rows of the rules use synthetic inputs. |
| L5 | `nonpositive_denominator` | Not added in 3.5.2b; it is added by the first slice that produces it (a ratio over invested capital, or EV/EBITDA, in 3.5.5 or 3.5.6). 3.5.2b adds only `unsupported_mapping` and `debt_not_visible`. Invested capital ≤ 0 is returned as an `ok` value. This amends K12. |
| L6 | File scope | Authorized up front, beyond the files of B.2: the `analysis` row's description in `docs/project/ARCHITECTURE.md`, `docs/user/GLOSSARY.md`, `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_calculators.py` and `tests/workspace/test_fcf_growth_codec.py`. |
| L7 | Moved tests | The tests of the two moved FCF functions move to `tests/analysis/shared/test_cash_flow.py` with their expected values unchanged. FCF-Growth's calculator test file keeps its other tests. |
| M1 | Direct long-term-debt total (review correction, 2026-10-26; replaces the A.4 row "Direct total beside absent parts") | When the direct total is present, each of its two parts (current portion, noncurrent long-term debt) that is absent as `not_tagged` with no related concept counts as zero, and the parts must then equal the total exactly. A mismatch is `unavailable`: `ambiguous_fact` when at least one part is present, with the parts named as the affected components; `debt_not_visible` when neither part is present. A part absent for any other reason, or with a related concept, keeps its existing outcome. The total is still never used as a value or added to the parts. The check comes before the other component rules, so a filer that tags only the direct total never gets zero debt. |
| M2 | Amended annual report (review correction, 2026-10-26) | `10-K/A` qualifies with `10-K`, as the domestic forms; 20-F, 40-F and their amendments are refused (`incompatible_scope`). The form rule is a named set, not a single value. When the anchor filing is a `10-K/A` whose cover lacks the registration table, the listing check decides how to proceed, for example by reading the cover of the original 10-K for the same fiscal year; that decision falls under K5″b and is recorded in this plan by 3.5.2c. |
| M3 | Enterprise value keeps its evidence (review correction, 2026-10-26; amends L3) | `compute_enterprise_value` takes the `MarketCapEvidence` and the total-debt `MetricEvidence`, not bare `MetricResult`s, and returns its own frozen type, defined in `enterprise_value.py`: its `MetricResult`, the market-cap evidence and the total-debt evidence it used, its own operands (cash, preferred stock, noncontrolling interest, short-term investments), the components it took as zero and diagnostic messages. A consumer can then show every debt component, every component taken as zero (debt's and EV's own) and the share count and price behind the market cap. L3 now reads: market cap and EV each have their own type; every other metric shares one. `compute_market_cap` also raises `ValueError` when a price is given without its `price_date`, because the price date stays visible (Shared definitions §4). |

### A.4 Wording the plan settles (3.5.2b)

Points where a decision above needed a more exact statement. They add no behavior beyond the decision; the project owner can reverse any.

| Topic | Wording |
| :--- | :--- |
| Order of market-cap checks | Form first (`incompatible_scope`), then currency (`incompatible_currency`), then the listing check (its own code), then the share count and the price (the input's own code), then the year-end count's date (`incompatible_period`). A 20-F filer in a foreign currency is therefore `incompatible_scope`. The forms `10-K` and `10-K/A` qualify (M2); 20-F, 40-F and their amendments are refused. |
| Several failing debt components | With at least one component present, an unsupported mapping decides; otherwise the first failing component in the order short-term borrowings, current portion, noncurrent long-term debt, lease liabilities. The message names that component. |
| Nothing present, other absences | With no component present, precedence is: an unsupported mapping, then a tagged related concept, then interest expense that is not zero (both `debt_not_visible`), then any other absence that cannot say there is no debt (`other_concept`, `conflict`, `after_boundary`, `basis_mismatch`, `no_anchor_filing`) with the code of the L2 table. Only when none applies is total debt zero. Interest expense of any nonzero value, not only a positive one, counts as visible interest. |
| Direct total | Decision M1 replaces the earlier wording. With the direct total present, a part absent as `not_tagged` with no related concept is zero and the parts must equal the total exactly; the check comes before the other component rules. A part absent for another reason, or with a related concept, keeps its existing outcome, so Honeywell (related concepts beside a direct total) is `debt_not_visible`, not a reconciliation case, and Alphabet is the reconciliation case. A direct total beside two clean absences gives `debt_not_visible` whatever else is reported, and a zero total beside two clean absences reconciles to zero. |
| Affected components | When the direct total does not equal its parts and at least one part is present, the result is `unavailable` with `ambiguous_fact`; the present parts are its operands and a diagnostic names both long-term parts as the affected components. With neither part present the result is `debt_not_visible` and has no operands. |
| EV and the other metrics' propagation | EV takes the `MarketCapEvidence` and the total-debt `MetricEvidence` (M3); when either result is not `ok` EV is `unavailable` with that result's own code and still carries both pieces of evidence, and the order of the other checks is cash, preferred stock, noncontrolling interest, short-term investments. |
| Short-term investments and Honeywell | The classified-balance-sheet zero is shown with Walmart's real inputs, which tag current assets and no short-term investments. Honeywell tags current assets and a short-term investments line (443 million), so its case shows the line subtracted; with the line absent the same current assets give zero. |
| Reason message | Every non-`ok` result carries a non-empty reason; an overflow of the finite range is `not_applicable` with `invalid_request`, as the moved FCF functions do. |

### A.5 Decisions at the start of 3.5.2c (2026-10-26)

Approved by the project owner. A.1 to A.4 are records and keep the sub-slice lettering they were written under: in them,
"3.5.2c" is the shared input assembly (now 3.5.2d) and "3.5.2d" is FCF-Growth's adoption (now 3.5.2e), apart from
K5″a, K5″b and M2, which name the listing check that is now 3.5.2c.

| # | Topic | Decision |
| :--- | :--- | :--- |
| N1 | Sub-slices | Renamed and split: 3.5.2c is the listing check alone; 3.5.2d is the shared input assembly (everything else the plan put in 3.5.2c); 3.5.2e is FCF-Growth's adoption of the shared market cap (the plan's former 3.5.2d). Branches: `feat/step-3-5-2c-listing-check`, `feat/step-3-5-2d-input-assembly`, `feat/step-3-5-2e-fcf-market-cap`. |
| N2 | Document the check reads | Delegated. The document is part of the anchor filing as filed; it is read under the existing bounded, no-redirect transport; it is the smallest document that carries the cover facts (`Security12bTitle` or its rendered equivalent, `TradingSymbol`, `SecurityExchangeName`, and the registrant's CIK); and it holds for the regression issuer set, Alphabet and the depositary-share case. Candidates were the rendered "Cover" report found through `FilingSummary.xml`, and the primary document Graham's verifier reads, of up to 8 MiB. Decided in P1 of [A.6](#a6-decided-under-delegation-during-352c-2026-10-26). |
| N3 | Cache | No persistent cache of the listing outcome. There is one read per analysis scope, kept for the scope as the SEC header is (F3 of the 3.5.1 plan). An as-filed cover never changes, so a cache can be added later without changing any stored shape. |
| N4 | Live captures | About 30 EDGAR requests in total, with the project's SEC identity, which is never printed or committed; raw responses only under `.tmp/`, never committed; fixtures trimmed to what the tests read, with a checksum file, following the existing `evaluation/fixtures/sec_edgar` folders. More than 40 requests needs the project owner's approval. |
| N5 | Assembly shape (built in 3.5.2d) | One function per input family: the anchor year-end; the market-cap inputs; balance-sheet values at *t* for named fields; annual values at *t* for named fields. A provider failure is returned as a typed failure carrying its provider-failure record, never raised. |
| N6 | Currency (built in 3.5.2d) | The filing currency of market cap is the currency of the monetary facts the consumer resolved at *t*, never the currency requested in a configuration. The quote currency comes from the resolved quote on the live path, and from the split-history response with `as_of`. |
| N7 | Split-history start (built in 3.5.2d) | The split-history request starts at the date the count is scaled from, minus a named margin of 10 calendar days. |
| N8 | Assembly starting point (4) (now under 3.5.2d) | Market cap takes only the quote currency from the quote path. The reference to Graham's security-unit evidence is removed, because K5″ removed it. |

### A.6 Decided under delegation during 3.5.2c (2026-10-26)

Decided by the implementer from captured covers (22 at first, 49 more in the review that followed), within the limits of the delegation: from captured evidence only, failing
closed, with an explicit list of title forms, classifying only the requested ticker's own row, and leaving Graham's
behavior unchanged. Every filing named below is in the [listing evidence record](STEP_3_5_2_LISTING_EVIDENCE.md), which
gives the CIK, accession and form of each. The project owner can reverse any row.

| # | Topic | Decision | Why |
| :--- | :--- | :--- | :--- |
| P1 | Document read (N2) | The rendered cover of the anchor filing, `R1.htm` in the filing's archive folder, requested directly. It is the only read for a filing whose first report is the cover; when it is not, P19 applies. | Smallest document that carries all four cover facts and holds for every case: 22 covers read, 34 to 136 KB each, against primary documents of 2.6 MB (Alphabet) and 4.1 MB (Adaptimmune), which are 25 and 58 times the cover of the same filing, and Graham's bound of 8 MiB. In the widened sample 48 of 49 first reports were covers; Disney's was the audit information, which P2 refuses and P19 reads through the summary. About a third of each page is the report table and the rest is hidden definitions. The first report of the filing was the cover in all three `FilingSummary.xml` files read (Alphabet, Annaly, Medtronic fiscal 2019), so that second request would add 55 to 87 KB and show nothing the page does not; it is made only when the first page is not a cover (P19). |
| P2 | A page that is not the cover | `R1.htm` is accepted as a cover only if its report table has a `Document Type` row and a registrant-key row, found by XBRL concept. A page that fails either is not a cover; P19 looks for the cover through the filing summary, and when it finds none the outcome is `cover_unreadable`, which is a refusal. | Fail closed. If a filing ever places its cover elsewhere, the outcome is `missing_fact`, never a wrong affirmation. |
| P3 | Transport policy | One request per analysis scope for a filing whose first report is the cover (P19 adds two when it is not), kept for the adapter's life; timeout 20 s; size limit 512 KiB for a report and 512 KiB for `FilingSummary.xml` (the largest captured, Disney's, is 86,703 bytes); exact URL patterns (`R<n>.htm` and `FilingSummary.xml` of the filing), no redirect, UTF-8 only; outside the four-document limit. A 404 is `cover_missing` (a refusal); every other fault raises the classified provider error. | The size limit is 3.8 times the largest cover captured (a combined filing of eight registrants). The rest mirrors the header request (F3 and H2 of the 3.5.1 plan). |
| P4 | Rows are read by concept, not label | A row is identified by the XBRL element in its first cell (`dei:Security12bTitle`, `Security12gTitle`, `TradingSymbol`, `SecurityExchangeName`, `NoTradingSymbolFlag`, `EntityCentralIndexKey`, `DocumentType`), never by its label. | Annaly labels the same rows "Title of Each Class" and "Name of Each Exchange on Which Registered"; Honeywell writes "Entity central index key". The concept names were the same on all 22 covers. |
| P5 | Whose securities are whose | A cover with one registrant key lists the issuer's securities. A combined cover assigns each security to the nearest key above it, and a security above every key makes the cover `cover_unreadable`. A security under another key is not the issuer's. | Prologis lists Prologis, Inc. (common stock) and Prologis, L.P. (notes) with a key before each group; Duke Energy lists its own securities and then seven registrants that list none. A ticker under another key is `not_listed` for this issuer. |
| P6 | Matching the ticker | The cover's `TradingSymbol` must equal the requested ticker after trimming and upper-casing, with `.`, `-` and `/` read as one separator (P17). Nothing else is normalized: a separator is never removed or added, and a space is not a separator. Only the issuer's own rows are compared, and a matching row must have an exchange row. A preferred ticker whose form differs beyond the separator (`NLY-PF` and the cover's `NLY.F`) is not listed (`missing_fact`); market cap is refused for a preferred security either way. | Covers print `JPM PR D`, `ALDF.U`, `NLY.F`, `MDT/27` and `BRK.B` as their own symbols. Apart from the separator, no rewrite was shown by a capture. |
| P7 | Titles that are a share of the issuer | Explicit designations: "common stock", "common shares", "class a common stock", "class b common stock", "class a ordinary shares", "class c capital stock" and "ordinary shares", compared after lower-casing and collapsing whitespace, alone or with one of twelve clauses: five par-value forms (`, $X par value`; `, par value $X per share`; `, $X par value per share`; `, par value $X`; ` $X par value`) and seven more (`, without par value`; ` (no par value)`; ` ($X par value)`; ` (par value $X per share)`; `, par value N-N/N cents per share`; `, par value CHF X per share`; ` (€X nominal value per share)`). An amount `$X` is a decimal or a mixed fraction such as `$1-2/3`. | Each is backed by a captured cover ([listing evidence record](STEP_3_5_2_LISTING_EVIDENCE.md) §6): the regression set, Alphabet's two classes, Medtronic and the blank-check company ("ordinary shares"), a SPAC ("class a ordinary shares"), five amended filings for the first clauses, and from the widened sample of 49 covers: Berkshire Hathaway (class B, `BRK.B`), Procter & Gamble and Exxon Mobil (without par value), Eli Lilly (no par value), Caterpillar and Merck (parenthesized par value), AT&T and American Express (parenthesized `Par Value $X Per Share`), Wells Fargo (`$1-2/3`), PepsiCo (cents), Chubb (CHF) and Linde (euro nominal value). |
| P8 | Titles that are refused as incompatible | A title beginning "depositary shares", "american depositary shares" or "dep shs" is a depositary share; one beginning "units", a unit; one beginning "warrants", a warrant; one ending "preferred stock" or "preferred stock, series X" (X letters), a preferred security. They are checked in that order, before the share list, and refused with `incompatible_units`. | Captured: Adaptimmune's "American Depositary Shares" (a real 10-K filer, ticker `ADAP`), the depositary shares of JPMorgan, Duke Energy, Albemarle and, in the widened sample, Oracle, Boeing, AT&T, Goldman Sachs, Bank of America and Wells Fargo, Citigroup's "Dep Shs", the blank-check company's `Units` and `Warrants`, a SPAC's units, Annaly's preferred stock, and the series-lettered preferred stock of Bank of America (`BAC PrL`) and Wells Fargo (`WFC.PRL`). A title that mentions preferred stock but begins "depositary shares" is a depositary share. |
| P9 | A title outside the vocabulary | The kind is `other`, which is a refusal with `missing_fact`, never an affirmation. This kind is added to the six the delegation named. | Debt, guarantees and rights have tickers on the covers (`WMT26`, `MDT/27`, `DUKB`, `PGACR`, and notes, debentures, guarantees, medium-term notes and trust-preferred securities on twenty more covers of the widened sample). A class designation other than A, B and C appears on no cover as a listed security: Visa's Class B-1, B-2 and C rows carry no symbol. |
| P10 | Not listed, and a cover with no table | A cover whose table lists the issuer's securities but not the ticker is `not_listed` (`missing_fact`). A cover with no registration table at all is the reason `no_registration_table`. | International Media Acquisition's cover lists only Section 12(g) titles with no symbol, so its ticker is `not_listed`. Medtronic's fiscal 2019 cover, before cover-page tagging, has a document type and a key and no table; a run with an early `as_of` meets such covers. |
| P11 | Form and registrant | The cover's `Document Type` must equal the form the submissions data gives the anchor filing (`form_mismatch`), and the issuer's CIK must be among the cover's keys (`cik_mismatch`). The acceptance time is the submissions data's, because a cover carries none. | The market-cap function already refuses forms other than `10-K` and `10-K/A` before it looks at the check. Document types agreed with the form on all 22 covers. |
| P12 | A `10-K/A` (decision c, M2) | An amended anchor filing is read as itself. A `10-K/A` whose cover lacks the registration table gives `no_registration_table`, which is `missing_fact`. The cover of the original 10-K is not read. | No `10-K/A` without the table was found among the seven read (Albemarle, IPG Photonics, VAALCO, OFG Bancorp, Innoviva, Pantages Capital Acquisition and International Media Acquisition), so failing closed was the rule the delegation set. Reading the original needs a second request and a link from the amendment to the original that the snapshot does not hold until the year-end is found (3.5.2d). |
| P13 | Ambiguity refuses | One ticker listed under two different titles (`ambiguous_listing`; the one exception is P21), a row whose columns disagree, a symbol row that belongs to no title (P20), a title with two different symbols, a malformed key, and a listed ticker with no exchange row are each `cover_unreadable` or `ambiguous_listing`, never resolved by choosing. The same title listed twice, as Albemarle's cover does, is one listing. | Fail closed. |
| P14 | Graham's parser | `parse_unit_document` is not reused. Graham's verifier, its rule and its outputs are unchanged. | The parser raises on any registered title that is not Graham's single common class, and needs a us-gaap filing's financial facts and contexts, so it cannot classify a depositary share or a second class; reusing it would change Graham's behavior. |
| P15 | Boundary | A filing accepted after the boundary is refused (`accepted_after_boundary`); accepted at the boundary it is kept. The check is made on every call. | The cover carries no acceptance time, so the submissions data's is used, as the header request uses the header's own. |
| P16 | Kinds and reasons | Kinds: share, depositary share, unit, warrant, preferred security, other, not listed. Reasons a cover is unavailable: provider unsupported, no analysis scope, subject mismatch, no anchor filing, form or acceptance time unavailable, accepted after the boundary, cover missing, cover unreadable, no registration table, form mismatch, CIK mismatch, ambiguous listing. All reasons map to `missing_fact`. | One typed vocabulary in the data layer; the pure function maps it, so the data layer never imports `analysis`. |
| P17 | Ticker separators (amends P6) | `.`, `-` and `/` are the same separator when the requested ticker is compared with a cover's symbol: both are trimmed and upper-cased, and `.` and `/` are read as `-`. A separator is never removed or added (`BRKB` does not match `BRK.B`). The comparison stays within the issuer's own rows, so it cannot join two issuers, and two rows that become equal with different titles are `ambiguous_listing` (P13). `ListingEvidence.ticker` keeps the requested ticker as given, upper-cased. | Berkshire Hathaway's cover prints `BRK.B` (Class B Common Stock), while the SEC's ticker file writes `BRK-B`; the two differ only in the separator. No captured cover lists two symbols that collide after the comparison. |
| P18 | Covers whose rows cannot be taken in order | A cover whose cover page cannot be found (P19) or whose rows cannot be assigned to securities by the one rule of P20 stays `cover_unreadable` (`missing_fact`). | Fail closed. Of the 71 covers captured, none is in that state: the three that were (Disney's first report, BlackRock's and Microsoft's symbol-first rows) are read by P19 and P20. |
| P19 | The cover is not the first report (amends P1, P2) | When `R1.htm` is not a cover (P2's test), the filing's `FilingSummary.xml` is read once and the report it marks as the cover is read. A report is marked as the cover when its menu category is `Cover` and its short name is "Cover" or "Cover Page", in any case. A summary that marks no report, marks more than one, names a file other than `R<n>.htm`, or is missing (a 404) leaves the first page, which is `cover_unreadable`. A fault raises the classified provider error. The first read stays `R1.htm`, so other filings make no extra request. The summary is read under the same bounded, no-redirect transport, with its own limit of 512 KiB (`CoverReaderPolicy.max_summary_bytes`). | Disney's `R1.htm` is the audit information and its cover is `R2.htm` (accession `0001744489-25-000155`, CIK 1744489). The menu category `Cover` alone marks two reports on the captured summaries of Disney, Alphabet and Annaly (the cover and the audit information), so the short name decides; "Cover" (Disney), "Cover Page" (Alphabet) and "COVER PAGE" (Annaly) are the three forms captured. Medtronic's fiscal 2019 summary marks one report, "Document and Entity Information", whose page is a cover, so no summary is read for it. |
| P20 | One rule for the rows of a security (replaces the order of rows) | A security starts at its title row. A symbol, exchange or no-symbol row belongs to the nearest title above it within its block, a block being the rows between two member headers (the rows whose first cell names an axis member, such as "Common Stock [Member]"); a row above every title of its block belongs to the first title of the block. The exchange row of a block with no title is the registrant's own and belongs to no security. A symbol row with no title is `cover_unreadable`. | Three orders occur on the 71 covers: title, symbol, exchange after a header (most); symbol, title, exchange after a header (BlackRock, Microsoft); and no headers at all (single-security covers such as Amazon). The one rule reads every one of them. Every cover that was readable gives the same securities, symbols and exchanges as before (compared row for row on the 71 raw covers and the committed fixtures); the two that were `cover_unreadable`, BlackRock's and Microsoft's, are read. Dow's second registrant has an exchange row and no title in its block, which the rule leaves unassigned. |
| P21 | A ticker shared with debt (amends P13) | When the requested ticker matches several rows of the issuer's own cover under different titles, it is affirmed only if exactly one title is a share and every other title is a debt title of the explicit form "N% Notes due YYYY" (any decimal for N). The share's title is the evidence. Any other combination is `ambiguous_listing`: a share with a depositary share, a preferred security, a unit or another class; two share titles; debt only; or a debt title outside the form. | Microsoft's cover lists the symbol `MSFT` against "Common stock, $0.00000625 par value per share" and against "3.125% Notes due 2028" and "2.625% Notes due 2033" (CIK 789019, accession `0001193125-26-323660`). BlackRock's notes carry their own symbol (`BLK 35`). The form is the one on the captured cover. |

| P22 | A renamed ticker (amends K5″ item 3 and the listing check; decided by the project owner, 2026-10-27) | When the requested ticker is not on the anchor cover, the check reads the cover of the registrant's latest 10-K or 10-K/A (latest at run time, from the submissions data the adapter already holds). It affirms only when both hold: the anchor cover lists exactly one share line under this CIK, with a symbol, and no depositary share; and the latest cover lists the requested ticker as that registrant's only share line. The one listed share line is then renamed, not replaced. Every other case stays `missing_fact`. The result records both accessions, both forms and both symbols as filed. Without `as_of` the anchor is the latest filing, so this path never runs. The extra cover request is made only when the ticker is absent from the anchor cover, and is kept for the analysis scope. | Meta Platforms (CIK 1326801): the fiscal 2020 10-K (`0001326801-21-000014`) lists `FB` and the latest (`0001628280-26-003942`) lists `META`, each as the only share line ([listing evidence §5.8](STEP_3_5_2_LISTING_EVIDENCE.md#58-a-renamed-ticker)). The refusals are shown on Alphabet's real cover (two share lines) and JPMorgan's (a depositary share), with synthetic latest covers. The rule rests on the identity rule of [Architecture](../../../ARCHITECTURE.md#which-registrant-a-ticker-names). |

### A.7 Decisions at the start of 3.5.2d (2026-10-27)

Approved by the project owner. N5 to N8 and K3, K4, K15 stand as recorded.

| # | Topic | Decision |
| :--- | :--- | :--- |
| S1 | Dependencies | The assembly's dependencies are received by a consumer's analyzer at construction (`AGENTS.md` §9): the `InputResolver` (financial facts and instant series), the split-history client (the new protocol), and the cover-listing capability. The assembly functions take them as arguments and hold no state. |
| S2 | The live path | The live path (no `as_of`) also reads the split history, with `adjusted_on` set to the quote's date (D20 of the 3.5.1 plan), so the count is scaled by every split after its source date up to the quote. Two market-data requests per live run. |
| S3 | Tests | Tests use synthetic price frames and quotes built in the tests, the captured split histories (NVIDIA, Walmart, Commerce Bancshares), and the captured SEC fixtures served through the real adapter (as L4). No new live captures. |
| S4 | The share-count path | The assembly compares the year-end share count's date with *t*. Only when it differs, or no year-end count exists, does it request the cover-page count (the B.4 note of the 3.5.1 plan). The pure market-cap function keeps its own date check as a second guard. |
| S5 | Sub-slices | One sub-slice. |
| S6 | Two typed outcomes of #190 | Never exceptions out of the assembly. **Case (b)** (the registrant's annual filings all came after the boundary) arrives as `FactsNotAvailableAsOf` on fact paths and as `AFTER_BOUNDARY` absences on balance-sheet paths. The assembly returns it once, as unavailable with `not_available_as_of` and the adapter's message, and makes no further request for that run. **Case (a)** (no annual report at all) is a provider failure raised when the analysis scope opens, returned as the typed failure of N5 with its provider-failure record. |

**Evidence for the year-end (K4), read on 2026-10-28.** The first step of 3.5.2d compared the `reportDate` of the anchor
annual filing, from SEC's submissions data, with the period end of that filing's own balance-sheet facts (the us-gaap
and ifrs-full instant facts of its accession in the captured Company Facts). The project owner approved one read-only
request per regression issuer whose fixture lacked the column, and the extra pages of JPMorgan's fixture, within a
budget of 15; 13 requests were made, with the project's SEC identity, and the raw responses stay under `.tmp/`. The
`reportDate` column was then added to the trimmed submissions of the instant-fact and annual-fact fixtures, aligned with
the filings they already list, and their checksum files were refreshed. Nothing else in a fixture changed.

| Issuer | Form | Anchor accession | `reportDate` | Period end of the filing's facts |
| :--- | :--- | :--- | :--- | :--- |
| JPM | 10-K | 0001628280-26-008131 | 2025-12-31 | 2025-12-31 |
| PLD | 10-K | 0001193125-26-051453 | 2025-12-31 | 2025-12-31 |
| DUK | 10-K | 0001326160-26-000014 | 2025-12-31 | 2025-12-31 |
| DE | 10-K | 0001104659-25-122321 | 2025-11-02 | 2025-11-02 (a 52/53-week year) |
| SAP | 20-F | 0001104659-26-020058 | 2025-12-31 | 2025-12-31 |
| NTR | 40-F | 0001193125-26-081326 | 2025-12-31 | 2025-12-31 |
| WMT | 10-K | 0000104169-26-000055 | 2026-01-31 | 2026-01-31 |
| MRNA | 10-K | 0001682852-26-000033 | 2025-12-31 | 2025-12-31 |
| MNST | 10-K | 0001104659-26-020831 | 2025-12-31 | 2025-12-31 |
| GOOGL | 10-K | 0001652044-26-000018 | 2025-12-31 | 2025-12-31 |
| HON | 10-K | 0000773840-26-000013 | 2025-12-31 | 2025-12-31 |

All eleven agree. The extra pages carry the same column (on JPMorgan's two pages that hold a filing, the 10-K filed
2025-02-14 gives 2024-12-31 and the one filed 2024-02-16 gives 2023-12-31). The anchor filing was first chosen from the recent block of
the submissions data only, so a boundary older than the recent block had no anchor filing and no year-end. The review
correction T1 ([A.9](#a9-review-decisions-2026-10-28)) lifts that: the snapshot looks for the anchor on the extra pages
as well.

### A.8 Wording the plan settles (3.5.2d)

Points where a decision above needed a more exact statement. They add no behavior beyond the decision; the project owner
can reverse any.

| Topic | Wording |
| :--- | :--- |
| Where the year-end is read | The snapshot keeps the `reportDate` of each filing of the recent block and, since T1, of the extra pages it read for the anchor. The adapter gives the anchor filing's year-end, form, filing date and the filing dates of the recent block through an optional capability, `resolve_anchor_year_end`, routed by the production provider like the cover listing. The filing dates let the assembly date the source of a year-end count without another request. |
| One scope, one year-end | `anchor_year_end_scope` opens the analysis scope and yields the year-end, so case (a), which is raised when the scope opens, can be returned typed. A consumer calls the other three functions inside the block with the yielded value. A function that needs the year-end takes it as an argument, so none can be called for a registrant that has none. |
| Case (b) | It is decided once, at the year-end, from the adapter's own message, because the resolver turns `FactsNotAvailableAsOf` into an unavailable result without a code. The balance-sheet and annual functions also return it, once and with no further request, if their provider says it: an `after_boundary` absence, or `FactsNotAvailableAsOf`. |
| The cover is not read for a form market cap refuses | For an anchor filing other than a 10-K or 10-K/A the cover is not requested, and the listing check says it was not read; the pure function refuses by form first. The share count and the price are still resolved, so the 20-F and 40-F cases show their paths. |
| A year-end count of another year | It is passed on, with the basis `year_end`, when no cover-page count exists, so the pure function refuses it as `incompatible_period`. It is never replaced by an older year's count. |
| The quote's date | The quote carries no market time, so its date is its retrieval date, in UTC. A split history adjusted on another day is refused as `incompatible_period`. A boundary after the history's last day, or before its first session, is `not_available_as_of`. |
| Annual values | The completed-annual fields are a series, so the function asks the resolver for the series (`resolve_annual_series`, T2), keeps the observations that end at *t* and, as FCF-Growth does, the latest-available version of the period. Conflicting latest versions are an `InputUnavailable` of `ambiguous_fact`, never a choice. The resolver's single-observation entry refuses a series, which is why the series has an entry of its own. |
| Failures | A provider failure on any one input returns a `MetricInputsFailure` and no later input of that function is requested. An answer the resolver rejected is the same type with no record. |

### A.9 Review decisions (2026-10-28)

Approved by the project owner after review of the 3.5.2d branch.

| # | Topic | Decision |
| :--- | :--- | :--- |
| T1 | Anchor selection reads the extra submissions pages | When the recent block holds no eligible annual filing at or before the boundary, the snapshot looks for the anchor in the extra pages: only pages whose `filingFrom`–`filingTo` range overlaps the 400 days before the boundary, newest first; each page read once per adapter (D11 and D17 of the 3.5.1 plan); the search stops at the first page that holds an eligible annual filing; a page name must be the issuer's own; no page is read when the recent block suffices. The anchor's form, `reportDate`, filing date, acceptance time and taxonomy come from that page, so `resolve_anchor_year_end`, the cover listing (3.5.2c) and the SIC header (3.5.1a) all see it. The filing date of a share count's source is looked up the same way. If no page in the window holds an annual filing, the existing outcome stands. |
| T2 | Annual values go through the resolver | `InputResolver.resolve_annual_series` is added, uncached like `resolve_instant_series`. It applies the existing provider-response checks and records a resolution trace. `resolve_annual_values` calls it instead of `resolver.provider.fetch_facts` and no longer builds `ResolvedInput`s in the analysis layer. Whether FCF-Growth's own annual reader moves onto this entry is an open decision of 3.5.2e. |

**How T1 is built.** The snapshot reads the recent block, and only when it holds no annual filing accepted at or before
the boundary does it read pages: those whose range ends no earlier than 400 days before the boundary and starts no
later than the boundary, newest first, at most twelve (the bound of D11). Every filing on a page read is added to the
snapshot's form, filing-date, report-date, acceptance-time and primary-document columns, and the anchor is chosen over
the merged columns by the rule that chose it before: the newest annual filing accepted at or before the boundary. The
400 days are a named constant of the adapter: an issuer files an annual report every year, so the newest one at the
boundary was filed within a year and the slack of a late filer; an older page cannot hold the anchor. T1 amends D11 of
the 3.5.1 plan, which said that only the balance-sheet series reads the pages: the snapshot now reads them too, under
the same bounds. The non-snapshot path of the adapter, which has no analysis scope, is unchanged.

**What T1 changes for a run.** A run with `as_of` before a frequent filer's newest annual filing used to find no anchor
when that earlier annual filing was off the recent block, so the share count, the cover check, the SIC header and every
fact that reads the anchor were unavailable. They now use the correct anchor. A run whose recent block holds the anchor
reads no more than before. The pull request lists this as a user-visible change for frequent filers' historical runs.

**Where T2's selection lives.** `resolve_annual_series` returns every observation that passed the checks, oldest period
first and, within a period, earliest available first, with no selection. The choice of the observation that ends at *t*,
of the latest-available version of it, and of `ambiguous_fact` for a conflict stays in `resolve_annual_values`. The
reason is that the choice is the shared metrics' rule: it needs *t* and the shared reason codes, neither of which the
provider-neutral resolver knows, and FCF-Growth, which aligns periods across fields, would choose differently. The
resolver's checks are: the answer must be for the requested subject, field, provider and basis, and each observation
must be a completed annual period with both ends, or the whole answer is rejected as a provider failure of kind
`unexpected_response`; an observation that is not available at the boundary or fails the quality checks is left out and
the others stand. A provider's `FactsNotAvailableAsOf` is flagged on the result (`not_available_as_of`), because the
resolver result carries no reason code and case (b) must stay distinguishable from an absent field.

---

## Appendix B: File inventories, tests and documentation

Paths are under `investment_analysis_engine/` unless they start with `tests/`, `schemas/`, `docs/` or `scripts/`. The
inventories for 3.5.2b to 3.5.2e were confirmed against `main` at `3305ec3`; each names a starting point to confirm first,
because the code can move before the sub-slice begins.

### B.1 3.5.2a files

| Area | File | Change |
| :--- | :--- | :--- |
| Helper | `analysis/shared/ranking.py` (new) | `rank_members`, `MINIMUM_ELIGIBLE_MEMBERS`, the frozen member, metric, result and diagnostic types |
| Tests | `tests/analysis/shared/test_ranking.py` (new) | [B.7](#b7-352a-tests) |
| Finance math | `docs/user/FINANCE_MATH.md` | the ranking entry: eligibility, average ranks, display percentile, rank sum, competition positions, minimum universe |
| Planning | the documents of [B.14](#b14-documentation) | this plan and the amendments |

### B.2 3.5.2b files

| Area | File | Change |
| :--- | :--- | :--- |
| Shared type | `analysis/shared/metric_evidence.py` (new) | the result type every metric but market cap and EV shares (L3), `InputUnavailable`, and the one table that maps an absence reason to a reason code (L2) |
| Market cap | `analysis/shared/market_cap.py` (new) | the shared market-cap type and the pure function: share count (with basis and date), the filing date of its source, the splits applied through `scale_share_count`, the price and its date, the form, the currencies and the listing check's outcome (K5″); the outcome's small frozen type is defined here and produced by 3.5.2c |
| Operating | `analysis/shared/operating_metrics.py` (new) | gross profit (K6), EBIT, D&A, EBITDA |
| Debt and EV | `analysis/shared/enterprise_value.py` (new) | total debt (the table of Shared definitions §6, the reconciliation rule of M1, related concepts, the unsupported IFRS component) and EV (K7) with its own evidence type (M3), each component returned with the absent ones taken as zero |
| Capital | `analysis/shared/invested_capital.py` (new) | invested capital; IC ≤ 0 is an `ok` value (L5) |
| Cash flow | `analysis/shared/cash_flow.py` (new) | `compute_free_cash_flow` and `compute_fcf_yield`, moved |
| FCF-Growth | `strategies/fcf_growth/calculators.py`, `strategies/fcf_growth/input_resolver.py` | the two functions deleted from the first; the second imports `compute_free_cash_flow` from `analysis/shared/cash_flow.py`; the planning labels in the module docstring replaced (K16) |
| Reason codes | `core/metric_result.py` | `UNSUPPORTED_MAPPING`, `DEBT_NOT_VISIBLE` |
| Schemas | `schemas/momentum.schema.json`, `schemas/fcf-growth.schema.json`, `schemas/runs-compare.schema.json` | regenerated (`uv run python -m scripts.generate_schemas`): each lists the `ReasonCode` values |
| Existing tests | `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_calculators.py`, `tests/workspace/test_fcf_growth_codec.py` | the FCF tests move beside the functions; the codec test patches `strategies.fcf_growth.calculators.compute_free_cash_flow` and `compute_fcf_yield` by name (lines 404 and 407 on `main`), so its patch targets are updated. Both files are in 3.5.2b's scope only if its authorization names them (`AGENTS.md` §4) |
| New tests | `tests/analysis/shared/test_metric_evidence.py`, `test_market_cap.py`, `test_operating_metrics.py`, `test_enterprise_value.py`, `test_invested_capital.py`, `test_cash_flow.py`, and the helper `_issuer_inputs.py` (new) | [B.8](#b8-352b-tests); the helper reads the issuers' inputs through the SEC adapter (L4) |
| Finance math | `docs/user/FINANCE_MATH.md` | an entry for every shared metric; the market-cap wording of K9 waits for 3.5.2d |
| Glossary and architecture | `docs/user/GLOSSARY.md`, `docs/project/ARCHITECTURE.md` | market capitalization, EBITDA, enterprise value, total debt and invested capital; the `analysis` row's description (L6) |

Starting points to confirm first: (1) every importer of the two FCF functions, which on `main` are the FCF-Growth input
resolver (`compute_free_cash_flow`, line 49) and its tests and the codec test above; `compute_fcf_yield` has no
production caller; (2) the operand types the pure functions take, against `ResolvedInput`
(`data/financial/provenance.py`) and the instant-series absence reasons (`data/financial/facts.py`), so that no new
operand type duplicates one; (3) that `analysis` may import `data` and `core` for these modules, and that `strategies`
importing `analysis/shared/cash_flow.py` adds no import between units
([ARCHITECTURE §13](../../../ARCHITECTURE.md#13-module-boundaries)); the table's "Owns" cell for `analysis` may need a
mention of the shared metrics; that edit needs authorization when 3.5.2b is authorized.

### B.3 3.5.2c files

| Area | File | Change |
| :--- | :--- | :--- |
| Listing check (P1 to P21) | `data/sec_edgar/cover_listing.py` (new) | `CoverReaderPolicy`, `cover_url`, `fetch_cover` (the request); `classify_title` (the vocabulary); `read_cover_listing` (the cover reader); `ListingEvidence`, `ListingResolution`, `SecurityKind`, `CoverUnavailableReason` (the typed evidence); `CoverListingRequest` and the `CoverListingProvider` protocol (the optional capability) |
| Adapter | `data/sec_edgar/financial_facts.py` | the constructor gains `cover_fetcher` and `cover_policy`; `resolve_cover_listing`, modelled on `resolve_as_filed_sic`: one cover read per analysis scope for the active snapshot's anchor filing, the acceptance time checked against the boundary, outside the four-document limit, a transport fault raised as the classified provider error |
| Bounded read | `data/sec_edgar/filing_document.py` | the bounded no-redirect read is public as `read_bounded`, used by `fetch_filing`, the header read and the cover read; no behavior change |
| Production provider | `data/financial/production.py` | `resolve_cover_listing` routed by `request.provider_id` as `resolve_security_identity` is; a provider without the capability gives `provider_unsupported` |
| Pure function | `analysis/shared/market_cap.py` | `listing_check_from_resolution`: listing evidence to the `ListingCheck` the market-cap function takes |
| Fixtures | `evaluation/fixtures/sec_edgar/cover_pages/` | 37 trimmed covers, each keeping the rows the reader uses and at most the first six registered securities, one trimmed `FilingSummary.xml` (Disney's), and `SHA256SUMS` |
| Tests | `tests/data/test_sec_cover_listing.py`, `tests/analysis/shared/test_listing_check.py`, `tests/live/test_provider_response_shape.py` | [B.9](#b9-352c-tests); one `live_network` check of the cover request |
| Documentation | [B.14](#b14-documentation) | the evidence record, the decisions of A.5 and A.6, Shared definitions §4 item 3, the provider debugging guide, the status rows |

Confirmed at the start: `parse_unit_document` raises on any registered title that is not a single common class, so it is
not the cover parser (P14); `resolve_as_filed_sic` and its cache are the model for the adapter method; the optional
capabilities of the production provider are routed by `request.provider_id` with a `runtime_checkable` protocol, which
the new capability follows. Its request type carries the ticker and the provider, so the adapter reads the active
analysis scope's snapshot as `resolve_security_unit` does, and no snapshot type crosses the protocol.

### B.4 3.5.2d files

| Area | File | Change |
| :--- | :--- | :--- |
| Assembly | `analysis/shared/metric_inputs.py` (new) | one function per input family (N5): `anchor_year_end_scope`; `resolve_market_cap_inputs` (the share-count path of S4; the price with or without `as_of` (K15); the split history from the date the count is scaled from minus 10 calendar days (N7) and, without `as_of`, adjusted on the quote's date (S2); the filing currency passed in from the monetary facts resolved at *t* and the quote currency from the quote or the split-history response (N6); the listing check of 3.5.2c through the production provider); `resolve_balance_sheet_values`; `resolve_annual_values`. A provider failure is a typed failure carrying its provider-failure record, never raised (N5, S6) |
| Year-end *t* | `data/sec_edgar/financial_facts.py` | the snapshot keeps the `reportDate` of each filing it already reads; `AnchorYearEnd`, `AnchorYearEndRequest`, `AnchorYearEndResolution`, `AnchorYearEndUnavailableReason`, the `AnchorYearEndProvider` capability and the adapter's `resolve_anchor_year_end`. No new request |
| Production provider | `data/financial/production.py` | `fetch_instant_series` routed by `request.provider_id`, as `fetch_facts` is (a provider that does not serve it gives every year-end as an `unsupported` absence), and `resolve_anchor_year_end` routed like the cover listing |
| Split protocol | `data/market_data.py` | `DatedSplitAdjustedHistoryProvider`, beside `SplitAdjustedHistoryProvider`, declares `as_of` and `adjusted_on`, which `CachedHistoricalDataClient.fetch_split_adjusted_history` takes (`data/cached_client.py`, unchanged). The existing protocol, which the Yahoo client implements, and the client's check against it are unchanged |
| Anchor on the pages (T1) | `data/sec_edgar/financial_facts.py` | the snapshot adds the filings of the pages that can hold the anchor, when the recent block holds none, before it chooses the anchor ([A.9](#a9-review-decisions-2026-10-28)) |
| Annual series (T2) | `data/financial/resolver.py` | `AnnualSeriesResolution` and `InputResolver.resolve_annual_series`; the construction of a resolved input from a fact is shared with the single-fact path |
| Fixtures | `evaluation/fixtures/sec_edgar/instant_facts/`, `annual_facts/` | the `reportDate` column added to the trimmed submissions, and the checksum files refreshed ([A.7](#a7-decisions-at-the-start-of-352d-2026-10-27)); no other fixture is added |
| Tests | `tests/analysis/shared/test_metric_inputs.py`, `tests/analysis/shared/_metric_input_rig.py`, `tests/data/test_anchor_year_end.py`, `tests/data/test_anchor_pages.py`, `tests/data/test_annual_series_resolver.py` (new); `tests/data/test_sec_ticker_identity.py` (one test: its "no page is read" check now covers only the second snapshot, and the first is asserted to read the page once; authorized by the project owner on 2026-10-28) | [B.10](#b10-352d-tests) |

Starting points confirmed: (1) the snapshot held no report date; the submissions payload carries `reportDate` per
filing in the recent block and on the extra pages, `_submission_strings` reads such a column, and no new request was
needed ([A.7](#a7-decisions-at-the-start-of-352d-2026-10-27)). (2) `ProductionFinancialFactsProvider` had `fetch_facts` and no `fetch_instant_series`; the
resolver calls it at `resolver.py:305`. (3) `CachedHistoricalDataClient` checks `isinstance(provider,
SplitAdjustedHistoryProvider)` on the wrapped provider, which the Yahoo client passes and which is unchanged. (4) Momentum
keeps the bars whose UTC instant is at or before the boundary, reading a zoned daily index by its local trading dates
(`MomentumInputResolver`, `_observation_instants`), so a session is included when its date is on or before the
boundary's UTC date; the assembly uses that rule through `split_adjusted_close_on_or_before`. Market cap takes only the
quote currency from the quote path (N8); Graham's security-unit evidence is not used (K5″). The assembly relies on the
identity rule of issue #190 and on the renamed-ticker rule P22.

### B.5 3.5.2e files

| Area | File | Change |
| :--- | :--- | :--- |
| Result | `strategies/fcf_growth/models.py` | `market_capitalization` becomes the shared type; `SCHEMA_VERSION` 5 to 6; the stale version docstrings and the "method_version = 2 / schema_version = 4" comment corrected (K16) |
| Analyzer | `strategies/fcf_growth/analyzer.py`, `strategies/fcf_growth/input_resolver.py` | the market cap resolved through the assembly; the yield computed with `compute_fcf_yield`, `unavailable` with `provider_error` and a warning on a market-data failure (K10) |
| Stored shape | `strategies/fcf_growth/envelope.py`, `strategies/fcf_growth/presenter.py`, the codec and document models, `schemas/fcf-growth.schema.json` | the new part in the evidence, the presenter and the document; the codec and document versions bumped with the result version |
| Composition | `strategies/fcf_growth/cli.py` (the command, line 121, and `refresh`, line 192), `strategies/fcf_growth/execution.py` (line 89), `strategies/fcf_growth/evaluation.py` (line 65) | each builds `ProductionAnnualGrowthSeriesResolver` or the analyzer, and gains the market-data dependency |
| Fixtures | `evaluation/fixtures/fcf_earnings_growth.py` | the success fixture gains a share-count fixture and a split-history fixture (K11) |
| Tests that construct the analyzer | `tests/analysis/test_instrument_applicability.py` (lines 135, 227, 240), `tests/analysis/test_base_analyzer_conformance.py` (104), `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_analyzer.py` (39), `tests/analysis/fcf_earnings_growth/test_production_composition.py` (32, 60), `tests/analysis/fcf_earnings_growth/test_sec_edgar_integration.py` (110), `tests/reporting/test_security_identity_presenters.py` (163), `tests/test_existing_strategy_output_contracts.py` (40, 65), `tests/workspace/test_fcf_growth_execution.py` (49, 54) | updated to the new composition; the line numbers are those of `main` at `3305ec3` |
| Finance math and guide | `docs/user/FINANCE_MATH.md`, `docs/user/strategies/FCF_GROWTH.md` | "market capitalization at the boundary"; the guide states the limitations of K15 and Shared definitions §4 |

Starting points to confirm first: (1) every place FCF-Growth's composition is built, which on `main` are
`strategies/fcf_growth/cli.py` in the command (line 121) and in `refresh` (line 192), `execution.py`, `evaluation.py`,
and the tool dependency class in `tool.py`, and that no other site (for example the orchestrator handler) builds the
analyzer; (2) every test that constructs the analyzer, listed above and re-found with a search before the sub-slice
begins; (3) where the stored evidence of a run decodes `market_capitalization` (`tests/workspace/test_fcf_growth_codec.py`
and the evidence codec), to list every version that must change with `SCHEMA_VERSION`.

### B.6 Result shapes

```text
RankingResult (frozen)                 3.5.2a
  metrics: tuple[RankMetric, ...]      name and direction (higher or lower is better)
  eligible: tuple[EligibleMember, ...] ticker order; ticker, issuer key, one finite value per metric
  ranked: tuple[RankedMember, ...]     display order (position, then ticker); empty below the minimum
  exclusions: tuple[RankExclusion, ...]  ticker, issuer key, values (None where not ok), one reason per metric
  diagnostics: tuple[RankDiagnostic, ...]  duplicate issuer, kept class lacks a metric, below the minimum
RankedMember (frozen)
  ranks, percentiles: tuple[float, ...]  per metric, in the order of the requested metrics
  rank_sum: float; position: int       competition position (1, 1, 3)

MetricEvidence (frozen)                3.5.2b, every metric but market cap and EV
  result: MetricResult                 status, finite value, reason code and reason
  operands: tuple[Operand, ...]        every resolved input used, under its name, with its provenance
  zero_components: tuple[str, ...]     the components taken as zero because the filing reports none
  diagnostics: tuple[str, ...]         why a component is zero, what is affected, how a total was derived
EnterpriseValueEvidence (frozen)       3.5.2b, defined in enterprise_value.py
  result: MetricResult                 status, finite value, reason code and reason
  market_cap: MarketCapEvidence        the evidence EV was given, whatever its outcome
  total_debt: MetricEvidence           the evidence EV was given, whatever its outcome
  operands: tuple[Operand, ...]        cash, preferred stock, noncontrolling interest, short-term investments
  zero_components, diagnostics         EV's own terms taken as zero, and notes (debt's are in total_debt)
MarketCapEvidence (frozen)             3.5.2b, stored by FCF-Growth in 3.5.2d
  result: MetricResult                 status, finite value, reason code and reason
  share_count: ResolvedInput | None    the count as filed, with its provenance
  share_count_basis, share_count_date  year-end or cover page; the fiscal year-end or the date of the cover
  share_count_filing_date              the filing date of the count's source
  scaled_share_count, splits_applied   the count on the price's basis, and the splits that scaled it
  price, price_date                    the split-adjusted close and its date
  form, filing_currency, quote_currency  the anchor filing's form and the two currencies
  listing_check: ListingCheck | None   affirmed (with the accession read) or refused (reason code and reason)
InputUnavailable (frozen)              an input unavailable for a reason other than a balance-sheet absence
  reason_code, reason                  the code the dependent metric reports, and a non-empty explanation

ListingEvidence (frozen)               3.5.2c, data layer
  ticker, kind, title                  kind: share, depositary share, unit, warrant, preferred, other, not listed
  cik, accession, form, accepted_at    the filing read, with source_url and retrieved_at
ListingResolution (frozen)             the evidence or one CoverUnavailableReason, never both
ListingCheck (frozen)                  3.5.2b type, produced by 3.5.2c from a ListingResolution

AnchorYearEnd (frozen)                 3.5.2d, defined in data/sec_edgar/financial_facts.py
  year_end: date                       t: the anchor filing's reportDate
  accession, form, filing_date         the anchor filing
  filing_dates: Mapping                the filing date of each filing of the recent block, by accession
anchor_year_end_scope(...)             yields AnchorYearEnd | InputUnavailable | MetricInputsFailure
  InputUnavailable                     not_available_as_of with the adapter's message (case b), or missing_fact
  MetricInputsFailure                  case (a) or a provider failure while the scope opens
MetricInputs failure (frozen)          3.5.2d
  input_name, reason                   the input that failed and a non-empty explanation
  provider_failure                     the record with its input name, or None when the adapter did not classify it
  reason_code                          provider_error
MarketCapInputs (frozen)               3.5.2d: the arguments of compute_market_cap
  year_end, form, filing_currency, quote_currency, listing_check
  share_count: ResolvedInput | InputUnavailable; share_count_basis; share_count_filing_date
  price: float | InputUnavailable; price_date; split_events; adjustment_date
  market_cap()                         calls compute_market_cap with them
resolve_balance_sheet_values(...)      Mapping[FinancialField, ResolvedInput | InstantAbsence], or InputUnavailable or MetricInputsFailure
resolve_annual_values(...)             Mapping[FinancialField, ResolvedInput | None | InputUnavailable], or InputUnavailable or MetricInputsFailure
                                       (no effective-time argument: the resolver gives the boundary to the provider)
DatedSplitAdjustedHistoryProvider      3.5.2d, protocol: fetch_split_adjusted_history(ticker, start_date, *, use_cache, adjusted_on, as_of)

FCF-Growth result                      3.5.2e
  market_capitalization: shared type   replaces the bare resolved input; SCHEMA_VERSION 6
```

### B.7 3.5.2a tests

`tests/analysis/shared/test_ranking.py`, on synthetic members only. Expected ranks, percentiles and positions are written
out by hand, never produced by the code under test.

- **Every case of [Slice inputs §4](STEP_3_5_SLICE_INPUTS.md#4-352--shared-metrics-and-ranking-helper)'s ranking list:**
  any input order gives the same output; duplicate issuers keep the alphabetically first ticker and report the rest with
  the canonical-representative diagnostic; a member missing any metric is excluded with its reason; nine eligible
  members return no ranks and ten return ranks; tied values share the average rank; tied sums share a position and the
  next skips (1, 1, 3); higher-is-better and lower-is-better.
- **Order:** every permutation of a small member set, and several seeded shuffles of a ten-member set, give the same
  result.
- **Percentile:** rank 1 gives 100 and rank *N* gives 0.
- **Ties:** all values tied; tied sums of different ranks; tied members display in ordinal ticker order after
  upper-casing.
- **Exclusion:** a `not_applicable` metric and an `unavailable` one each exclude the member with their own reason code;
  every reason of a multiply-excluded member is listed; excluded members carry their values.
- **Deduplication (K13):** the ordinal-first ticker is kept whatever the case or order; the kept class lacking a metric
  excludes the issuer and the diagnostic names both classes; a dropped class lacking a metric changes nothing.
- **Minimum:** exactly 9 and exactly 10 eligible members, after deduplication and after exclusions.
- **Validation:** no metrics; repeated metric names; tickers repeated after upper-casing; a member without an entry for
  a requested metric; a blank ticker; a blank issuer key; a result that lost its reason.
- **Finite:** every value, rank, percentile and sum in a ranked result is finite.

### B.8 3.5.2b tests

Tests are in `tests/analysis/shared/`, one file per module. Expected values are written by hand or read from the
captured fixtures for the issuer cases (L4); the code under test never produces them.

- **Market cap (K5″):** [Slice inputs §4](STEP_3_5_SLICE_INPUTS.md#4-352--shared-metrics-and-ranking-helper)'s cases
  (count at year-end *t* only; no count; conflicting counts; a split after the filing date of the count's source scales
  and one before does not; per-class counts with no total). Each K5″ refusal gives its code: a filing other than a 10-K or 10-K/A
  (20-F, 20-F/A, 40-F, 40-F/A) is `incompatible_scope` and a 10-K/A qualifies (M2); a currency mismatch or an unknown currency is `incompatible_currency`, a refused listing
  gives the check's own code (`incompatible_units`, `missing_fact`), and no count or price gives the input's code.
  **SAP** is `incompatible_scope` (20-F), not through the security-unit rule. **Alphabet**'s combined count is valued at
  a synthetic GOOGL price. **Nutrien**'s IFRS year-end count is dated before *t* and is `incompatible_period`. **Walmart
  and NVIDIA** are the scaling cases of the 3.5.1 plan's B.10, now through the market cap: NVIDIA's 2,464,000,000 shares
  from the filing of 2024-02-21, scaled by the 10-for-1 split of 2024-06-10, give 24,640,000,000, and 86.402 ×
  24,640,000,000 equals 864.02 × 2,464,000,000; Walmart's count taken after its 3-for-1 split is not scaled again, and
  scaling from the year-end gives a result three times larger as the negative case. A cover-page count dated after the
  filing's split date is scaled from its own date.
- **Gross profit (K6):** the reported figure is used; sales minus cost of revenue when no figure is reported, with both
  provenances; one of the two missing is `unavailable`; operating income is never used. Monster reports it, Walmart
  derives it.
- **EBIT, D&A, EBITDA:** reported operating income only, never rebuilt from pretax income; absent D&A makes EBITDA
  `unavailable`; a negative EBIT is a valid number.
- **Total debt and EV:** each row of the total-debt table, and the precedence of `unsupported_mapping`; a missing cash
  is `unavailable`; negative EV is a valid number. **Alphabet** is `ambiguous_fact` (its direct total of 49,085 million
  does not equal 1,996 + 46,547 million); Alphabet is the reconciliation case. **Honeywell** is not a reconciliation
  case: it is `debt_not_visible` (its current portion and noncurrent debt are tagged only as debt with finance
  leases, related concepts beside a direct total). The direct total (M1) is tested with synthetic inputs: both parts
  absent and clean is `debt_not_visible`; one part present and equal to the total reconciles and the clean part is
  zero; the same with an unequal total is `ambiguous_fact`; a zero total with both parts clean reconciles to zero.
  EV keeps the market-cap and total-debt evidence it used (M3). A price without its date raises `ValueError`. **Monster** is zero debt: it tags `InterestPaidNet`, not interest
  expense, and no debt concept. **Nutrien**'s IFRS total debt is `unsupported_mapping`. **Deere** is `debt_not_visible`
  (its combined current debt is a related concept).
- **Short-term investments (K7):** absent on a classified balance sheet is zero with a diagnostic (Walmart's real
  inputs); absent where current assets are not tagged is `unavailable`, so Deere's EV is `unavailable`.
- **Invested capital:** IC ≤ 0 is an `ok` value; a missing critical input is `unavailable`.
- **The absence table (L2):** every member of `InstantAbsenceReason` has its code, and a new member fails a test until it
  is mapped.
- **Every result:** finite numbers only; a non-`ok` result carries a reason code and a non-empty reason.
- **FCF and FCF yield:** the moved functions pass the tests that exercised them in FCF-Growth, unchanged in expected
  value, in `tests/analysis/shared/test_cash_flow.py` (L7); FCF-Growth's behavior is unchanged.
- **Reason codes:** the two members exist and the regenerated schemas validate.

### B.9 3.5.2c tests

Offline throughout: trimmed covers captured from EDGAR, served through the adapter and the cover reader. The default run
makes no live request.

- **Each captured case:** the widened sample of 49 large filers (the listing evidence record, §5.6), with the covers that add a title form or a refusal committed as fixtures: Berkshire Hathaway's class B, Procter & Gamble's `without par value`, PepsiCo's cents, Caterpillar's parenthesized par value, Linde's euro nominal value, Chubb's Swiss-franc par value, Eli Lilly's `no par value`, AT&T's parenthesized `Par Value`, Wells Fargo's `$1-2/3` and its series-lettered preferred stock, Citigroup's `Dep Shs`, and Bank of America's preferred stock; Disney's first report (not a cover) and BlackRock's symbol-first rows are `cover_unreadable`. Earlier: the regression issuer set's 10-K filers (JPMorgan, Prologis, Duke Energy, Deere, Walmart,
  Moderna, Monster, Alphabet and Honeywell) affirm their common stock; Alphabet affirms GOOGL and GOOG on class titles;
  Medtronic's and a blank-check company's ordinary shares are affirmed; Adaptimmune's (ADAP), JPMorgan's, Duke
  Energy's and Albemarle's depositary shares are refused with `incompatible_units`; the blank-check company's units
  and warrants and a SPAC's units are refused the same way; Annaly's preferred security is refused; notes, debentures
  and rights are `missing_fact`; five `10-K/A` covers are affirmed on their share titles.
- **Grouping (P20):** title-first, symbol-first and headerless covers give each symbol and exchange to the same title; BlackRock's and Microsoft's covers are read; a block's rows never go to the title before it; the exchange row of a block with no title is ignored and a symbol row with no title is unreadable.
- **A ticker shared with debt (P21):** Microsoft is affirmed; a share with notes of the explicit form is the share's; a share with a depositary share, a preferred security, a unit or another class, a debt title outside the form, or two debt titles alone is ambiguous.
- **The cover found through the summary (P19):** Disney's first report is not a cover and its summary marks `R2.htm`; the requests are the first report, the summary and the cover, once per scope; a filing whose first report is the cover makes one request; a missing summary, one marking none or several, or one naming a bad file leaves the first page unreadable; a fault or a missing marked report raises; the summary is read under its own limit and type.
- **Separators (P17):** `BRK-B`, `BRK.B` and `BRK/B` each match the cover's `BRK.B`; `BRKB` and `BRK B` do not; `NLY-PF` does not match `NLY.F`; two rows that collide after the comparison with different titles are `ambiguous_listing`, and with one title are one listing; a separator never joins two registrants' securities; the evidence keeps the requested ticker, upper-cased.
- **The requested ticker's row decides:** JPM is affirmed beside depositary shares of preferred stock, and ALDF beside
  its units and warrants; the ticker match is exact; a ticker absent from the cover is not listed; a security under
  another registrant's key is not the issuer's.
- **Refusals:** a cover under another CIK, another form, no registration table (Medtronic fiscal 2019, and an amended
  cover stripped of its table), a page that is not a cover, a ticker under two titles, a row with two values, a symbol
  with no title, a listed ticker with no exchange, and a combined cover with a security above every key.
- **Boundary:** accepted at the boundary it is kept; one second after, it is refused, in the reader and in the adapter;
  a filing not yet accepted at `as_of` is not an anchor.
- **One read per scope:** the cover is requested once however many times the check is asked for, with and without
  `as_of`, and outside the four-document limit.
- **Transport:** another host, a plain `http` URL, another report, a redirect (the opener refuses it), a body over the
  size limit, a non-UTF-8 body, a 404 (`missing_fact` through the evidence), a server fault (the classified provider
  error), an unaddressable accession, and the exact URL pattern.
- **The title vocabulary:** an explicit list; a class designation that is on no captured cover is `other`.
- **The pure function:** each kind gives its outcome; every unavailable reason gives `missing_fact` with an
  explanation; only a share is affirmed.
- **Production routing:** the façade routes to the SEC adapter and refuses a provider without the capability.
- **Fixtures:** checksums match; no identity and none of the hidden definitions.
- **Graham:** the security-unit tests pass unchanged.
- **Live (excluded from the gate):** one `live_network` check requests one cover and asserts the shape of its rows,
  never a value.

### B.10 3.5.2d tests

Offline throughout (S3): the real SEC adapter, production provider and resolver serve the captured fixtures; the quote,
the split-history client and the listing capability of the synthetic cases are stubs built in the tests.

- **Year-end *t* (K4):** the anchor filing's `reportDate` is the period end of its own facts for each of the eleven
  regression issuers; it follows the anchor filing of a boundary; every filing of the fixtures, in the recent block and on
  the extra pages, carries one; a filing without one gives no year-end and none is taken from the facts; the year-end is
  found once per scope (one set of SEC documents however many inputs are read); an annual observation that does not end
  at *t* is never returned as *t*'s. FCF yield with an FCF observation ending before *t* stays the pure function's
  `incompatible_period`.
- **Share-count path (S4):** a year-end count dated *t* is used and no cover-page count is requested; Walmart and SAP use
  the cover-page count; Nutrien's count for the year before *t* is passed on and the pure function refuses it as
  `incompatible_period`; Alphabet's combined year-end count is used; per-class cover counts with no total give none; a
  count whose source filing is not dated is unavailable.
- **Price (K15, S2, N7):** with `as_of`, the split-adjusted close of the last session on or before it, a date-only
  boundary including that day's close and a closed day taking the last session; without it, the current quote and a
  split history adjusted on the quote's date; a one-day download is never a quote; a response that ends before `as_of`
  is refused; the margin keeps the last session before a weekend filing date in range; a history adjusted on another
  day than the quote is refused; the quote currency with `as_of` is the response's.
- **Provider gaps (K3):** the production provider returns an instant series through the SEC adapter and refuses it for an
  unrouted provider and for one that does not serve it; it routes the year-end; the dated protocol carries `as_of` and
  `adjusted_on`, the cached client has the signature, and the existing protocol and the Yahoo client are unchanged.
- **End to end:** Walmart (a cover-page count taken after its 3-for-1 split, not scaled again) and NVIDIA (2,464,000,000
  shares from the filing of 2024-02-21 scaled by the 10-for-1 split of 2024-06-10) through the assembly into
  `compute_market_cap`.
- **Refusals and issuer shapes:** SAP refused by form (K5″) with its cover not read; a currency mismatch; Alphabet's
  listing check affirming GOOGL; a renamed ticker (P22) reached through the assembly; Deere's unclassified balance sheet,
  Monster's empty debt and Walmart's debt reaching `compute_total_debt` and `compute_enterprise_value` through the
  balance-sheet function.
- **S6:** case (b) is one unavailable result with `not_available_as_of` and the adapter's message, the same message the
  fact path and the balance-sheet path carry, and nothing more is requested; a balance-sheet answer after the boundary and
  an annual `FactsNotAvailableAsOf` are each returned once; case (a) is the typed failure with its provider-failure
  record.
- **Provider failure on each input family:** the share count, the listing check, the quote, the split history (with and
  without `as_of`), the balance-sheet and annual functions and the scope itself each return the typed failure and
  raise nothing.
- **Point-in-time:** nothing filed, priced or classified after the boundary is taken, apart from the splits that undo the
  provider's adjustment.
- **Anchor on the pages (T1):** JPMorgan with `as_of` before its 2026-02-13 10-K finds the prior 10-K
  (`0000019617-25-000270`) through its captured pages 004 to 008, newest first, and the snapshot carries that filing's
  form, report date, filing date, acceptance time, primary document and taxonomy; the cover listing and the SIC header
  are requested for it; the assembly's share count is dated from the page; the search stops at the first page that holds
  an annual filing; no page is read when the recent block suffices; a page is read once per adapter; the window bounds
  the pages read (a page that starts after the boundary or ends before the 400 days is not read); a page that is not the
  issuer's own is ignored; a page whose annual filing was accepted after the boundary is not the anchor; when no page in
  the window holds an annual filing the existing outcome stands; a page that cannot be read is the classified provider
  failure.
- **Annual series (T2):** every observation that passes the checks is a resolved input, oldest first; the trace records
  the request and the outcome; the series is not cached; a basis other than the fiscal year is `invalid_input`;
  `FactsNotAvailableAsOf` is flagged, an empty answer is not; a provider failure keeps its record; an answer for another
  subject, field, provider or basis, or one that is not a completed annual period, is rejected as a whole; an
  observation not available at the boundary or failing the quality checks is left out; the SEC adapter's series passes
  the checks on a captured issuer.
- **Unchanged:** every existing strategy's output; the tests of the changed fixtures pass unchanged.

### B.11 3.5.2e tests

- **Golden case (K11):** the success fixture's FCF yield is `ok` with its share count, price and splits visible; every
  other expected value of every FCF-Growth case is unchanged, asserted by a test.
- **Failure (K10):** a market-data failure gives the yield `unavailable` with `provider_error` and a warning; the run's
  `execution_status` and the classification equal those of the same run without a market cap; no automatic provider
  check fires.
- **Stored shape:** a run stored under schema 5 is refused by version (`UnsupportedRunVersionError`); a schema-6 run
  round-trips through the codec and replays with provider, cache, clock and calculator disabled; the checked-in schema
  is regenerated.
- **Composition:** the command, `refresh`, the execution adapter and the evaluation fixture each build the analyzer with
  the market-data dependency.
- **Output contracts:** the existing strategy output-contract tests pass unchanged apart from the market-cap part.

### B.12 User-visible changes

- 3.5.2a: none.
- 3.5.2b: two reason codes (`unsupported_mapping`, `debt_not_visible`); the three schemas that enumerate them
  (`momentum`, `fcf-growth` and `runs-compare`) are regenerated, with no document version bump. No stored run changes
  meaning.
- 3.5.2c: none. The capability is routed and called by no production path; no stored shape, command, option or output
  changes.
- 3.5.2d: the snapshot of the SEC adapter finds the anchor annual filing on the extra submissions pages when the
  recent block holds none at or before the boundary (T1). For a frequent filer's historical run (`--as-of` before its
  newest annual filing, when the earlier one is off the recent block) the anchor, and so everything that reads it, is
  now the correct earlier filing instead of unavailable; at most twelve extra requests are made, once per adapter. No
  stored shape, command or option changes. Nothing else is reached by a production path: nothing calls the assembly, and
  the production provider's routing of the balance-sheet series and `resolve_annual_series` have no production caller.
- 3.5.2e: FCF-Growth's stored result changes shape (`SCHEMA_VERSION` 5 to 6, with the codec and document versions), so a
  run stored before it is refused by version when read. FCF yield is shown where it was always unavailable. The text,
  `--json` and checked-in schema of FCF-Growth gain the market-cap evidence.

### B.13 TOOL_DEVELOPMENT edit sites

No sub-slice adds a strategy, so none of the edit sites of
[`docs/TOOL_DEVELOPMENT.md`](../../../../TOOL_DEVELOPMENT.md#edit-sites-of-a-strategy) is expected to be touched. 3.5.2b
and 3.5.2e regenerate schemas, which is a use of the `schema` site's command, not an edit of the site. 3.5.2e changes an
existing strategy's own files; the conformance tests are expected to pass unchanged, and a failure would mean a
descriptor or wiring file was touched.

### B.14 Documentation

| Document | 3.5.2a | 3.5.2b | 3.5.2c | 3.5.2d | 3.5.2e |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `STEP_3_5_CONTRACT_AND_SLICE_PLAN.md` | §2 rows, §3, Appendix A.13 | status rows | §2 rows (the renaming), §3.5.2, status rows | status rows | status rows, 3.5.2 closed |
| `STEP_3_5_SHARED_DEFINITIONS.md` | §3 (K7), §4 (K5), §5 (K6), §9 (K13) | §2 (the two reason codes and the absence table), §4 (K5″) | §4 item 3: the vocabulary's outcome in one sentence, linking to the evidence | §4: the price rule of K15, the live path's split history (S2), the filing currency (N6) and the year-end count's date (S4) | none |
| `STEP_3_5_2_LISTING_EVIDENCE.md` | none | none | new: the captured covers, the sizes, the requests | none | none |
| `STEP_3_5_SLICE_INPUTS.md` | §4 tests (K4 to K7, K11, gross profit), §8 Glossary line | §4 (K5″, invested capital), §7 and §8 (L5) | line 197 names the sub-slices by their new letters (review correction) | none | none |
| `docs/project/PROVIDER_DEBUGGING.md` | none | none | the cover request, where the live checks are listed | none | none |
| `docs/user/FINANCE_MATH.md` | the ranking entry | an entry for every shared metric | none | none | "market capitalization at the boundary" |
| `docs/user/GLOSSARY.md` | none: ranking terms arrive with the ranked view in 3.5.6 | market capitalization, EBITDA, enterprise value, total debt and invested capital | none: "listing check" arrives with the user-facing text of 3.5.2e, if that text needs it | none | "listing check", if needed |
| `docs/user/strategies/FCF_GROWTH.md` | none | none | none | none | the yield and its limitations (K15) |
| `docs/project/ARCHITECTURE.md` | none | the `analysis` row's description (authorized by L6) | none | none | none |
| `docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md` | none: its sequence table lists Step 3.5 as one row, not 3.5.2 | none | none | none | none |
| This plan | status rows | status rows | A.5, A.6, the renaming, status rows | A.7, A.8, A.9, B.4, B.6, B.10, B.12, status rows | status rows |
