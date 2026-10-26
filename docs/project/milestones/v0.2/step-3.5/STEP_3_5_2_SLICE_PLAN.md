# Step 3.5 slice 3.5.2 — Shared metrics and ranking helper: Slice Plan

The slice plan for [slice 3.5.2](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#352--shared-metrics-and-ranking-helper) of Step 3.5.
It covers four sub-slices, written against `main` at `3305ec3`.

Placement among other work packages: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

## 1. At a glance

- **What this plan does:** defines the metrics every screening strategy shares, once, and the code that feeds them, in
  four steps: the ranking helper (3.5.2a); the pure shared metrics (3.5.2b); the shared input assembly (3.5.2c); and
  FCF-Growth's adoption of the shared market cap (3.5.2d).
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
  - Where a sub-slice meets a data case no decision covers, it stops and asks the project owner (K17).
  - The managed quality gate after every sub-slice, and explicit authorization before the next begins.
  - No registry, plugin loader or factory is added; the new code is plain functions and frozen types.
- **Where the detail lives:** the file inventories, result shapes, tests and documentation changes are in
  [Appendix B](#appendix-b-file-inventories-tests-and-documentation); decision records are in
  [Appendix A](#appendix-a-decision-records); the evidence is in the
  [mapping evidence record](STEP_3_5_1_MAPPING_EVIDENCE.md).

## 2. Sequence and status

Each sub-slice ends with the managed quality gate and is gated by explicit authorization before the next begins.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| 3.5.2a | [Slice plan and ranking helper](#352a--slice-plan-and-ranking-helper) | Complete | 2026-10-26 |
| 3.5.2b | [Pure shared metrics](#352b--pure-shared-metrics) | Next | |
| 3.5.2c | [Shared input assembly](#352c--shared-input-assembly) | Planned | |
| 3.5.2d | [FCF-Growth adopts the shared market cap](#352d--fcf-growth-adopts-the-shared-market-cap) | Planned | |

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
- **Scope:** this plan and the document amendments listed in [B.9](#b12-documentation); `ranking.py`; its tests; the
  ranking entry of `FINANCE_MATH.md`. The file list is in [B.1](#b1-352a-files).
- **Branch:** `feat/step-3-5-2a-ranking-helper` (this branch; plan and implementation are one pull request).
- **Detail:** [files](#b1-352a-files), [result shape](#b5-result-shapes), [tests](#b6-352a-tests).

### 3.5.2b — Pure shared metrics

- **Problem:** market cap, gross profit, EBIT, D&A, EBITDA, total debt, EV and invested capital are defined in prose
  only, and FCF and FCF yield live in FCF-Growth's own package, where a second strategy would have to import them.
- **Decision (K5 to K8, K12, K14, K16):**
  - Each metric is a pure function over resolved facts, with no I/O, that returns a `MetricResult` plus the operands and
    provenance it used, in the module K14 names.
  - Market cap applies the fail-closed security-unit rule (K5). Gross profit is reported, else sales minus cost of
    revenue (K6). Short-term investments are zero-if-absent only on a classified balance sheet (K7).
  - `compute_free_cash_flow` and `compute_fcf_yield` move to `analysis/shared/cash_flow.py` unchanged in behavior; the
    copies in FCF-Growth are deleted and FCF-Growth imports them from there (K8).
  - Three reason codes are added: `unsupported_mapping`, `debt_not_visible` and `nonpositive_denominator` (K12). The
    schemas that list `ReasonCode` are regenerated with no document version bump (G4 of the 3.5.1 plan).
  - The planning labels in `strategies/fcf_growth/calculators.py`'s module docstring are replaced by durable wording
    (K16).
- **Scope:** the six modules of [B.2](#b2-352b-files), the moved FCF functions and their tests, the reason codes and the
  regenerated schemas, and the `FINANCE_MATH.md` entry of every shared metric.
- **Branch:** `feat/step-3-5-2b-shared-metrics`, off `main` after the 3.5.2a pull request merges.
- **Detail:** [files](#b2-352b-files), [result shapes](#b5-result-shapes), [tests](#b7-352b-tests).

### 3.5.2c — Shared input assembly

- **Problem:** the shared metrics need the anchor year-end, a share count, a price, the split history and balance-sheet
  and annual inputs at one year-end. Left to each consumer, seven strategies would assemble them seven ways. Two gaps on
  `main` also block it: the production financial-facts provider does not route the balance-sheet series, and the
  split-history provider protocol cannot carry the arguments the cached client takes.
- **Decision (K3, K4, K15):**
  - One assembly in `analysis/shared/metric_inputs.py` finds the anchor year-end *t*, resolves the share-count path
    (year-end count, else the cover-page count; Shared definitions §4), the price with or without `as_of`, the split
    history, and the balance-sheet and annual inputs at *t*.
  - **Year-end *t* is found once.** The first step checks what the SEC snapshot already exposes about the anchor
    filing's fiscal year-end ([B.3](#b3-352c-files)). If a new kind of provider request is needed, the sub-slice stops
    and asks.
  - FCF yield requires FCF-Growth's latest observation to end at *t*; otherwise it is `unavailable` with
    `incompatible_period` and never computed from an older year (Shared definitions §3).
  - A run with `as_of` takes its close by Momentum's existing rule: a date-only `--as-of` includes that day's close, and
    sessions are read by exchange-local date. The guides state the limitation (K15).
  - `ProductionFinancialFactsProvider` routes `fetch_instant_series`, and a split-history provider protocol that
    declares `as_of` and `adjusted_on` is added beside the existing one (D20 and D23 of the 3.5.1 plan).
- **Scope:** the assembly module, the two gaps, fixtures and tests. The file list is in [B.3](#b3-352c-files).
- **Branch:** `feat/step-3-5-2c-input-assembly`, off `main` after the 3.5.2b pull request merges.
- **Detail:** [files](#b3-352c-files), [result shapes](#b5-result-shapes), [tests](#b8-352c-tests).

### 3.5.2d — FCF-Growth adopts the shared market cap

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
- **Scope:** the composition sites, the analyzer and result, the stored shape and its versions, fixtures and tests. The
  file list is in [B.4](#b4-352d-files).
- **Branch:** `feat/step-3-5-2d-fcf-market-cap`, off `main` after the 3.5.2c pull request merges.
- **Detail:** [files](#b4-352d-files), [result shapes](#b5-result-shapes), [tests](#b9-352d-tests).

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
- No migration or compatibility decoder. Shapes that change are versioned ([B.10](#b10-user-visible-changes)).
- No delegation of data-mapping decisions to the implementer (K17).

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
  [B.7](#b7-352b-tests), including the named issuers.
- FCF-Growth imports FCF and FCF yield from `analysis/shared/cash_flow.py`; no copy remains in its package and no
  strategy imports another strategy's calculators.
- The regenerated schemas list the three new reason codes and nothing else changes in them.
- The gate passes.

**3.5.2c**

- One assembly returns, for an issuer and a boundary, the inputs the shared metrics need, or the reason each is
  unavailable. Year-end *t* is found once and every input is taken at it.
- The balance-sheet series is reachable through the production provider, and the split-history protocol carries `as_of`
  and `adjusted_on`.
- A run with and without `as_of` gives the price the rules above state. The gate passes.

**3.5.2d**

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
own pull request (K1).

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
| Ticker form | The helper returns tickers upper-cased. A blank ticker or issuer key is refused when the member is built. |
| Naming diagnostic | When the kept class lacks a metric another class has, the helper reports it as its own diagnostic (`kept_class_lacks_metric`) naming both tickers, in addition to the ordinary exclusion and the deduplication diagnostic. If no other class has the value, no naming diagnostic is added. |
| Result fields | The result lists the eligible members in ticker order whether or not ranks exist, and the ranked members in display order (position, then ticker) only when the minimum is met. Ranks, percentiles, sums and positions are typed fields; none is a `MetricResult`. |

---

## Appendix B: File inventories, tests and documentation

Paths are under `investment_analysis_engine/` unless they start with `tests/`, `schemas/`, `docs/` or `scripts/`. The
inventories for 3.5.2b to 3.5.2d were confirmed against `main` at `3305ec3`; each names a starting point to confirm first,
because the code can move before the sub-slice begins.

### B.1 3.5.2a files

| Area | File | Change |
| :--- | :--- | :--- |
| Helper | `analysis/shared/ranking.py` (new) | `rank_members`, `MINIMUM_ELIGIBLE_MEMBERS`, the frozen member, metric, result and diagnostic types |
| Tests | `tests/analysis/shared/test_ranking.py` (new) | [B.6](#b6-352a-tests) |
| Finance math | `docs/user/FINANCE_MATH.md` | the ranking entry: eligibility, average ranks, display percentile, rank sum, competition positions, minimum universe |
| Planning | the documents of [B.9](#b12-documentation) | this plan and the amendments |

### B.2 3.5.2b files

| Area | File | Change |
| :--- | :--- | :--- |
| Market cap | `analysis/shared/market_cap.py` (new) | the shared market-cap type and the pure function: share count (with basis and date), the filing date of its source, the splits applied through `scale_share_count`, the price and its date, and the security-unit outcome |
| Operating | `analysis/shared/operating_metrics.py` (new) | gross profit (K6), EBIT, D&A, EBITDA |
| Debt and EV | `analysis/shared/enterprise_value.py` (new) | total debt (the table of Shared definitions §6, the reconciliation rule, related concepts, the unsupported IFRS component) and EV (K7), each component returned with the absent ones taken as zero |
| Capital | `analysis/shared/invested_capital.py` (new) | invested capital; IC ≤ 0 is `nonpositive_denominator` for a dependent ratio |
| Cash flow | `analysis/shared/cash_flow.py` (new) | `compute_free_cash_flow` and `compute_fcf_yield`, moved |
| FCF-Growth | `strategies/fcf_growth/calculators.py`, `strategies/fcf_growth/input_resolver.py` | the two functions deleted from the first; the second imports `compute_free_cash_flow` from `analysis/shared/cash_flow.py`; the planning labels in the module docstring replaced (K16) |
| Reason codes | `core/metric_result.py` | `UNSUPPORTED_MAPPING`, `DEBT_NOT_VISIBLE`, `NONPOSITIVE_DENOMINATOR` |
| Schemas | `schemas/momentum.schema.json`, `schemas/fcf-growth.schema.json`, `schemas/runs-compare.schema.json` | regenerated (`uv run python -m scripts.generate_schemas`): each lists the `ReasonCode` values |
| Existing tests | `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_calculators.py`, `tests/workspace/test_fcf_growth_codec.py` | the FCF tests move beside the functions; the codec test patches `strategies.fcf_growth.calculators.compute_free_cash_flow` and `compute_fcf_yield` by name (lines 404 and 407 on `main`), so its patch targets are updated. Both files are in 3.5.2b's scope only if its authorization names them (`AGENTS.md` §4) |
| Finance math | `docs/user/FINANCE_MATH.md` | an entry for every shared metric; the market-cap wording of K9 waits for 3.5.2d |

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
| Assembly | `analysis/shared/metric_inputs.py` (new) | year-end *t*; the share-count path (year-end count when its date is *t*, else the cover-page count, else `unavailable`); the price with or without `as_of` (K15) and the split history; the balance-sheet and annual inputs at *t*; each input or the reason it is unavailable |
| Year-end *t* | `data/sec_edgar/financial_facts.py` (only if the first step shows the snapshot lacks it) | expose the anchor filing's fiscal year-end from data the adapter already fetches |
| Production provider | `data/financial/production.py` | `fetch_instant_series` routed by `request.provider_id`, as `fetch_facts` is |
| Split protocol | `data/market_data.py` | a provider protocol beside `SplitAdjustedHistoryProvider` that declares `as_of` and `adjusted_on`, which `CachedMarketDataClient.fetch_split_adjusted_history` takes (`data/cached_client.py`); the existing protocol, which the Yahoo client implements, is unchanged |
| Fixtures | `evaluation/fixtures/` (as the tests need) | trimmed share-count, price and split-history cases for the issuers of [B.8](#b8-352c-tests) |

Starting points to confirm first: (1) **what the SEC snapshot exposes for the anchor filing's year-end (K4).**
`SecEdgarAnalysisSnapshot` (`data/sec_edgar/financial_facts.py`) holds acceptance times, forms, taxonomies, primary
documents and filing dates, and no report date. The submissions payload the adapter already fetches carries a
`reportDate` per filing next to `filingDate` and `acceptanceDateTime` (the fixtures of
`evaluation/fixtures/sec_edgar/step_2_5a_d0` show it), and `_submission_strings` reads such a column, so reading it is
expected to need no new kind of request. The step confirms that for the recent block and for the extra pages, and stops
and asks if it does not hold. (2) `ProductionFinancialFactsProvider` has `fetch_facts` and no `fetch_instant_series`
(`FinancialFactsProvider` is the routed protocol); the resolver calls `fetch_instant_series` at `resolver.py:305`.
(3) the `isinstance(provider, SplitAdjustedHistoryProvider)` check in the cached client, so the new protocol does not
break the check the Yahoo client passes. (4) where Momentum selects the close for a date-only `--as-of` (K15), and how
`analysis/shared/financial_resolution.py:70` obtains the quote currency and the security-unit evidence for Graham,
which market cap reuses.

### B.4 3.5.2d files

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

### B.5 Result shapes

```text
RankingResult (frozen)                 3.5.2a
  metrics: tuple[RankMetric, ...]      name and direction (higher or lower is better)
  eligible: tuple[EligibleMember, ...] ticker order; ticker, issuer key, one finite value per metric
  ranked: tuple[RankedMember, ...]     display order (position, then ticker); empty below the minimum
  exclusions: tuple[RankExclusion, ...]  ticker, issuer key, values (None where not ok), one reason per metric
  diagnostics: tuple[RankDiagnostic, ...]  duplicate issuer, kept class lacks a metric, below the minimum
  minimum_eligible_members: int        MINIMUM_ELIGIBLE_MEMBERS, 10
RankedMember (frozen)
  ranks, percentiles: tuple[float, ...]  per metric, in the order of the requested metrics
  rank_sum: float; position: int       competition position (1, 1, 3)

Shared metric                          3.5.2b
  result: MetricResult                 status, finite value, reason code and reason
  operands, provenance                 every input used, with its source, date and filing
  market cap adds                      share count, basis (year-end or cover page), share-count date, filing date of
                                       the count's source, price, price date, splits applied
  total debt and EV add                each component, and which absent components were taken as zero

Metric inputs                          3.5.2c
  year_end: date (t) or reason         one anchor year-end for every input
  share count, price, splits           or the reason each is unavailable
  balance-sheet and annual inputs      at t, or the reason each is unavailable

FCF-Growth result                      3.5.2d
  market_capitalization: shared type   replaces the bare resolved input; SCHEMA_VERSION 6
```

### B.6 3.5.2a tests

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

### B.7 3.5.2b tests

- **Market cap:** [Slice inputs §4](STEP_3_5_SLICE_INPUTS.md#4-352--shared-metrics-and-ranking-helper)'s cases (count at
  year-end *t* only; no count; conflicting counts; a split after the filing date of the count's source scales and one
  before does not; per-class counts with no total; a one-day download is never a quote). **SAP** is `unavailable`
  through the security-unit rule (K5), and a currency mismatch gives `incompatible_currency`. **Nutrien** has no share
  count and is `unavailable`. **Walmart and NVIDIA** are the scaling cases of the 3.5.1 plan's B.10, now through the
  market cap: NVIDIA's 2,464,000,000 shares scaled by the 10-for-1 split give 24,640,000,000 and the market cap of the
  unadjusted price and unscaled count; Walmart's count taken after its 3-for-1 split is not scaled again, and scaling
  from the year-end gives a result three times larger as the negative case.
- **Gross profit (K6):** the reported figure is used; sales minus cost of revenue when no figure is reported, with both
  provenances; one of the two missing is `unavailable`; operating income is never used. Monster reports it, Walmart
  derives it.
- **EBIT, D&A, EBITDA:** reported operating income only, never rebuilt from pretax income; absent D&A makes EBITDA
  `unavailable`; a negative EBIT is a valid number.
- **Total debt and EV:** each row of the total-debt table; a missing cash is `unavailable`; negative EV is a valid
  number. **Alphabet and Honeywell** are the reconciliation cases of Shared definitions §6 (a direct total that does not
  equal its parts is `ambiguous_fact`). **Monster** is the zero-debt case: it tags `InterestPaidNet`, not interest
  expense, and no debt concept, so total debt is zero with a diagnostic. **Nutrien**'s IFRS total debt is `unavailable`
  with `unsupported_mapping`. A related concept tagged, or positive interest expense with no mapped debt, gives
  `debt_not_visible`.
- **Short-term investments (K7):** absent on a classified balance sheet (Honeywell) is zero with a diagnostic; absent
  where current assets are not tagged (**Deere**) is `unavailable`, so Deere's EV is `unavailable`.
- **Invested capital:** IC ≤ 0 gives `nonpositive_denominator` for a dependent ratio; a missing critical input gives
  `unavailable`.
- **FCF and FCF yield:** the moved functions pass the tests that exercised them in FCF-Growth, unchanged in expected
  value; FCF-Growth's behavior is unchanged.
- **Reason codes:** the three members exist and the regenerated schemas validate.

### B.8 3.5.2c tests

- **Year-end *t* (K4):** found from the anchor filing once; an input at another date is not taken; FCF yield with an FCF
  observation ending before *t* is `unavailable` with `incompatible_period`.
- **Share-count path:** a year-end count dated *t* is used; Nutrien's count for the year before *t* is not, and with no
  cover count the share count is `unavailable`; Walmart and SAP use the cover-page count; Alphabet uses its combined
  count; per-class cover counts with no total give none.
- **Price:** with `as_of`, the split-adjusted close on the last session on or before it, a date-only `--as-of`
  including that day's close and sessions read by exchange-local date (K15); without it, the current quote; a one-day
  download is never a quote; a response that ends before `as_of` is refused.
- **Provider gaps (K3):** the production provider returns an instant series through the SEC adapter and refuses it for an
  unrouted provider; the new split protocol carries `as_of` and `adjusted_on` and the cached client satisfies it.
- **Issuer cases:** Walmart and NVIDIA through the assembly with the split rules; SAP's currency mismatch; Deere's
  unclassified balance sheet; Monster's empty debt.
- **Point-in-time:** nothing filed, priced or classified after the boundary is taken, apart from the splits that undo
  the provider's adjustment.

### B.9 3.5.2d tests

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

### B.10 User-visible changes

- 3.5.2a: none.
- 3.5.2b: three reason codes; the three schemas that enumerate them are regenerated. No stored run changes meaning.
- 3.5.2c: none expected; the pull request states any it finds.
- 3.5.2d: FCF-Growth's stored result changes shape (`SCHEMA_VERSION` 5 to 6, with the codec and document versions), so a
  run stored before it is refused by version when read. FCF yield is shown where it was always unavailable. The text,
  `--json` and checked-in schema of FCF-Growth gain the market-cap evidence.

### B.11 TOOL_DEVELOPMENT edit sites

No sub-slice adds a strategy, so none of the edit sites of
[`docs/TOOL_DEVELOPMENT.md`](../../../../TOOL_DEVELOPMENT.md#edit-sites-of-a-strategy) is expected to be touched. 3.5.2b
and 3.5.2d regenerate schemas, which is a use of the `schema` site's command, not an edit of the site. 3.5.2d changes an
existing strategy's own files; the conformance tests are expected to pass unchanged, and a failure would mean a
descriptor or wiring file was touched.

### B.12 Documentation

| Document | 3.5.2a | 3.5.2b | 3.5.2c | 3.5.2d |
| :--- | :--- | :--- | :--- | :--- |
| `STEP_3_5_CONTRACT_AND_SLICE_PLAN.md` | §2 rows, §3, Appendix A.13 | status rows | status rows | status rows, 3.5.2 closed |
| `STEP_3_5_SHARED_DEFINITIONS.md` | §3 (K7), §4 (K5), §5 (K6), §9 (K13) | as the code requires | as the code requires | none |
| `STEP_3_5_SLICE_INPUTS.md` | §4 tests (K4 to K7, K11, gross profit), §8 Glossary line | none | none | none |
| `docs/user/FINANCE_MATH.md` | the ranking entry | an entry for every shared metric | none | "market capitalization at the boundary" |
| `docs/user/GLOSSARY.md` | none: ranking terms arrive with the ranked view in 3.5.6 | market cap, EBITDA, EV and invested capital terms, if absent | none | none |
| `docs/user/strategies/FCF_GROWTH.md` | none | none | none | the yield and its limitations (K15) |
| `docs/project/ARCHITECTURE.md` | none | the `analysis` row's "Owns" text, if it needs it (authorize first) | none | none |
| `docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md` | none: its sequence table lists Step 3.5 as one row, not 3.5.2 | none | none | none |
| This plan | status rows | status rows | status rows | status rows |
