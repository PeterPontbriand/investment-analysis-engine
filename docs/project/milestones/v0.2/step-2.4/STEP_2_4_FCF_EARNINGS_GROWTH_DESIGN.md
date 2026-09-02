# Free Cash Flow & Earnings Growth Analysis Strategy

This document defines a deterministic analysis strategy for Financial Data Agents. The strategy examines a public company's historical total free cash flow, free cash flow per diluted share, and diluted earnings-per-share growth, optionally adds free-cash-flow yield and forward analyst-consensus context, and returns an explicit `PASS`, `FAIL`, or `INDETERMINATE` conclusion.

The strategy supports direct analysis from the command line and defines the typed analysis-tool contract used by runtime agents. Both entry points use the same deterministic calculations and return the same structured financial result. A language model never performs or alters the financial arithmetic.

## Decision summary

| Decision | Contract |
| :--- | :--- |
| Historical measures | Completed annual total company free cash flow, FCF per diluted share, and diluted earnings per share |
| Free-cash-flow definition | Operating cash flow minus capital expenditures |
| Default period | Longest contiguous span available: prefer 5 elapsed years, then 4, then 3 |
| Classification basis | Total-company-FCF CAGR by default; explicit `fcf_per_share` policy/CLI override |
| Default `PASS` | Controlling FCF CAGR and diluted-EPS CAGR are meaningful and greater than zero |
| Default `FAIL` | Required evidence is complete and at least one controlling historical growth rate is zero or negative |
| `INDETERMINATE` | Required evidence is insufficient, incompatible, or mathematically nonmeaningful |
| Forward estimates | Supporting information by default; selectable confirmation or hard-gate policy |
| Free-cash-flow yield | Supporting information only; no yield threshold |
| Smoothing | None; reported annual history remains canonical |
| Comparison basis | Company versus its own history, not versus peers |
| Versions | `strategy_id = fcf_earnings_growth`, `method_id = reported_fcf_eps_cagr`, amended target `method_version = 2`, `schema_version = 2` |

---

# Part I — Financial Strategy and Investor Experience

## 1. Investment question and interpretation

The strategy asks:

> Over a clearly identified historical period, did the company produce positive, measurable growth in both free cash flow and diluted earnings per share?

Growth in both measures can be evidence of strengthening cash-generation economics. It may be consistent with an advantaged business, particularly when accounting earnings are accompanied by cash generation rather than unsupported by it.

The strategy does not prove that a company has a durable competitive moat. Market opportunity, scarcity, competitive position, management quality, and durability of advantage require evidence and judgment beyond the financial series analyzed here.

The comparison is against the company's own history. It does not determine whether the company has a free-cash-flow lead over competitors. Peer selection, cross-company normalization, and relative ranking require a separate comparative strategy.

## 2. Financial measures

### 2.1 Required historical measures

The analysis uses:

- annual total company free cash flow derived from operating cash flow and capital expenditures;
- annual diluted earnings per share;
- compound annual growth in each measure over the same historical period.

Annual free cash flow is:

```text
free_cash_flow = operating_cash_flow - normalized_capital_expenditures
```

Operating cash flow means net cash provided by operating activities for the completed fiscal year. `normalized_capital_expenditures` is a positive expenditure amount produced by the data-resolution rules in Part II.

Free cash flow is a non-GAAP analytical measure. Companies and data providers may define similarly named measures differently. The detailed result therefore identifies the source components and normalization used; a provider's precomputed “free cash flow” is not accepted merely because its label matches.

The amended method shows both total company FCF and FCF per diluted share. Annual FCF/share is total company FCF divided by the compatible weighted-average diluted shares for the same completed fiscal year. It therefore reflects dilution and repurchases without changing the canonical total-company-FCF definition. Total-company-FCF CAGR controls classification by default; an explicit `fcf_per_share` policy selection makes FCF/share CAGR controlling. The selected basis is part of the typed policy/result and is never inferred by the presenter or language model.

### 2.2 Historical period

The investor may request three, four, or five elapsed years:

| Elapsed period | Annual observations | Endpoints |
| :--- | ---: | :--- |
| 3 years | 4 | `t-3` through `t` |
| 4 years | 5 | `t-4` through `t` |
| 5 years | 6 | `t-5` through `t` |

The standard `longest_available` policy prefers five elapsed years and falls back to four and then three. Fewer than three elapsed years is insufficient for classification.

An explicitly requested period is strict. If that history is unavailable, the result is `INDETERMINATE`; the strategy does not silently substitute a shorter period.

The difference between observations and elapsed years is important:

| Observation | Fiscal year | Elapsed interval from prior observation |
| ---: | :--- | ---: |
| 1 | FY2020 | — |
| 2 | FY2021 | 1 |
| 3 | FY2022 | 1 |
| 4 | FY2023 | 1 |
| 5 | FY2024 | 1 |
| 6 | FY2025 | 1 |

Six annual observations from FY2020 through FY2025 contain five elapsed annual intervals. Five observations would contain only four. Every report states both the elapsed period and observation count.

### 2.3 Compound annual growth

For a positive value observed `N` elapsed years apart:

```text
cagr_percent = ((ending / beginning) ** (1 / N) - 1) * 100
```

The beginning and ending values must be strictly positive, and the annual series must be contiguous. Zero or negative endpoints and sign changes make compound annual growth nonmeaningful under this policy. The raw history remains visible, but the growth metric is unavailable with a specific reason.

The strategy rejects absolute-value and “growth from loss” treatments because they erase economically important sign information and can turn a loss-to-profit transition into a deceptively precise percentage. Such a transition may be favorable, but it is not ordinary compound growth.

### 2.4 Optional context

Under the standard settings, free-cash-flow yield and analyst consensus are supporting information only. The headline `PASS`, `FAIL`, or `INDETERMINATE` result is determined by the selected FCF classification basis and historical diluted-earnings-per-share growth. Both total-company-FCF and FCF/share CAGRs are shown regardless of which one controls classification.

Free-cash-flow yield is:

```text
fcf_yield_percent = latest_completed_fiscal_year_fcf / current_market_capitalization * 100
```

The numerator is annual and the denominator is current. The result identifies both dates. Missing market capitalization does not prevent the historical analysis from completing, and no 6%, 8%, or other yield threshold is part of this method.

Forward evidence uses analyst-consensus diluted earnings per share for the next fiscal year (FY1) and the following fiscal year (FY2). The strategy calculates growth from the latest annual actual to FY1 and from FY1 to FY2. A prior value must be positive, and a positive estimate is not necessarily positive growth.

The investor may select:

| Forward policy | Effect on the headline result |
| :--- | :--- |
| `display_only` | Default. Show available estimates and implied growth; do not alter the historical conclusion. |
| `confirmation` | State whether both forward intervals confirm continued positive earnings growth; do not alter the historical conclusion. |
| `hard_gate` | Require both forward intervals to be available and positive for `PASS`. Missing required evidence produces `INDETERMINATE`. |

Free-cash-flow yield cannot affect classification under `method_version = 1` or `2`. Any method that introduces a yield gate requires a new method version or a different method identifier.

## 3. Classification

The headline conclusion and the software execution status are separate. A provider failure or invalid request remains identifiable and must not masquerade as an unfavorable investment result.

### 3.1 PASS

The selected policy returns `PASS` when:

- a valid contiguous historical span is available;
- the selected controlling FCF compound annual growth is greater than zero;
- diluted-earnings-per-share compound annual growth is greater than zero; and
- under `hard_gate`, both forward implied-growth rates are available and greater than zero.

### 3.2 FAIL

The selected policy returns `FAIL` when every required metric is available and meaningful, but at least one required growth rate is zero or negative.

### 3.3 INDETERMINATE

The selected policy returns `INDETERMINATE` when required evidence is missing, incompatible, or mathematically nonmeaningful. An indeterminate conclusion is not a failed financial screen. Available raw values and the exact reason remain reportable.

The result also describes the historical relationship as:

- `both_growing`;
- `fcf_growing_earnings_not`;
- `earnings_growing_fcf_not`;
- `neither_growing`;
- `insufficient_or_nonmeaningful_growth`.

These descriptions are evidence, not scores or recommendations.

## 4. Investor controls and output

### 4.1 Command

```text
financial-agents fcf-growth TICKER [options]
```

```text
--growth-years 3|4|5        # omit for automatic 5 -> 4 -> 3 selection
--classification-basis total-fcf|fcf-per-share
--forward-policy POLICY     # display-only, confirmation, or hard-gate
--as-of DATE_OR_TIMESTAMP
--data-provider PROVIDER_ID
--no-cache
--details
--diagnostics
--json
--chart
```

`--details`, `--diagnostics`, and `--json` are mutually exclusive presentation modes. `--chart`, if implemented, is allowed with the concise or detailed mode and rejected with diagnostic or JSON output. An explicit historical period never falls back; automatic fallback is disclosed.

### 4.2 Concise output contract

The concise output uses this order:

| Order | Line | Required when |
| ---: | :--- | :--- |
| 1 | Ticker and strategy name | Always |
| 2 | `PASS`, `FAIL`, or `INDETERMINATE` and primary reason | Always |
| 3 | Historical endpoints, elapsed years, observation count, and fallback notice | Always |
| 4 | Latest completed-period free cash flow | Available |
| 5 | Total-company-FCF compound annual growth or unavailable reason | Always |
| 6 | FCF-per-diluted-share compound annual growth or unavailable reason | Always |
| 7 | Diluted-earnings-per-share compound annual growth or unavailable reason | Always |
| 8 | Selected classification basis and historical relationship description | Always |
| 9 | Free-cash-flow yield | Available and requested by policy |
| 10 | Forward evidence and selected forward policy | Any forward evidence exists or the policy requires it |
| 11 | Source and freshness summary | Always |
| 12 | Material warnings | Present |
| 13 | Strategy limitation | Always |

Classification reasons appear before optional metrics. Data-quality warnings appear before the limitation. Optional-data warnings do not obscure a complete historical conclusion.

Example shape:

```text
KO — Free Cash Flow & Earnings Growth

Screen: PASS
Period: FY2020–FY2025 (5 elapsed years; 6 annual observations)
Free cash flow (FY2025):        $X.XXB
Total free cash flow CAGR:      +Y.Y% (classification basis)
FCF per diluted share CAGR:     +W.W%
Diluted EPS CAGR:               +Z.Z%
Trend: Both free cash flow and diluted EPS increased over the measured period.

FCF yield: A.A% (FY2025 FCF / current market capitalization)
Forward EPS: FY1 +B.B%; FY2 +C.C% (display only)
Source: SEC EDGAR annual filings; current market data provider
Note: Historical financial strength may be consistent with an advantaged business,
but this screen does not establish market opportunity, scarcity, or durability of moat.
```

### 4.3 Other presentation modes

All modes render the same `FCFEarningsGrowthResult`; presenters do not recalculate or reclassify it.

- `--details` adds the annual series, calculation endpoints, provider fields, availability dates, normalization, lineage, and optional-metric bases.
- `--diagnostics` adds cache behavior, provider attempts, candidate selection and rejection, derivation steps, and execution errors.
- `--json` emits investor-presentation `schema_version = 3`, retains `result_schema_version = 2`, and adds an explicit nullable `security_identity` snapshot. An unavailable number is `null` with a reason code, never `NaN`.
- `--chart` plots only the annual series already present in the result.

The runtime-agent tool returns the same typed result used by the command-line presenter. A runtime agent may summarize that result but cannot replace unavailable evidence, alter the policy, or change the classification.

## 5. Interpretation limits

This strategy does not provide:

- direct measurement of moat, scarcity, market opportunity, or management quality;
- peer grouping, relative free-cash-flow leadership, universe screening, or ranking;
- discounted-cash-flow valuation, terminal value, or cost-of-capital estimation;
- alternate, normalized, or trailing-twelve-month free-cash-flow methods;
- hidden smoothing or user-selected transformations;
- a free-cash-flow-yield pass threshold;
- user-defined combinations or weights for `PASS`;
- a broad named-investor methodology;
- a composite score or investment recommendation;
- language-model-generated financial calculations or forecasts.

---

# Part II — Normative Implementation Contract

Part II is authoritative for implementers. Field names, enum values, nullability, selection rules, and version behavior are normative. Established repository conventions govern ordinary Python organization and shared types only where they do not change this public semantic contract. Any necessary incompatibility requires an explicit amendment to this document.

## 6. Versions and evolution

Every result contains:

```text
strategy_id = "fcf_earnings_growth"
method_id = "reported_fcf_eps_cagr"
method_version = 2
schema_version = 2
```

- `strategy_id` identifies the user-selectable analysis family and remains stable.
- `method_id` identifies the financial method. An alternate free-cash-flow definition, smoothing method, or materially different gate receives a different method identifier.
- `method_version` increments when existing method semantics change. Previously emitted versions remain interpretable and must not be silently reclassified.
- `schema_version` increments when the machine-readable result shape, enum set, or field meaning changes.
- Rendering-only changes do not change either version.

Adding a new method does not redefine historical results produced by this method.

## 7. Normative typed contract

### 7.1 Enums

```text
HistoricalHorizon = longest_available | 3 | 4 | 5
FCFClassificationBasis = total_fcf | fcf_per_share
ForwardPolicy = display_only | confirmation | hard_gate
Classification = pass | fail | indeterminate
TrendClassification =
    both_growing |
    fcf_growing_earnings_not |
    earnings_growing_fcf_not |
    neither_growing |
    insufficient_or_nonmeaningful_growth
MetricStatus = ok | unavailable | not_applicable
ForwardEvidenceStatus = complete | partial | unavailable
```

Required reason codes:

```text
insufficient_history
non_contiguous_history
missing_fact
incompatible_period
incompatible_units
incompatible_currency
incompatible_scope
ambiguous_fact
not_available_as_of
nonpositive_beginning
nonpositive_ending
sign_change
fcf_not_growing
eps_not_growing
fcf_and_eps_not_growing
forward_growth_not_confirmed
consensus_unavailable
market_cap_unavailable
provider_error
invalid_request
not_requested
```

A more specific reason code may be added only with a `schema_version` increment. Human-readable reasons accompany but never replace machine-readable codes.

### 7.2 Policy

```text
FCFEarningsGrowthPolicy
    historical_horizon: HistoricalHorizon = longest_available
    classification_basis: FCFClassificationBasis = total_fcf
    forward_policy: ForwardPolicy = display_only
    include_fcf_yield: bool = true
```

The minimum automatic horizon is fixed at three elapsed years and is not configurable in `method_version = 1` or `2`. `classification_basis` is introduced in `method_version = 2`; `total_fcf` is the default.

### 7.3 Metric and forward evidence

```text
MetricResult
    status: MetricStatus
    value: float | None
    reason_code: ReasonCode | None
    reason: str | None
```

When `status = ok`, `value` is finite and both reason fields are `None`. Otherwise `value` is `None` and both reason fields are present.

```text
ForwardEvidence
    status: ForwardEvidenceStatus
    latest_actual_eps: ResolvedInput | None
    fy1_consensus_eps: ResolvedInput | None
    fy2_consensus_eps: ResolvedInput | None
    actual_to_fy1_growth: MetricResult
    fy1_to_fy2_growth: MetricResult
    confirms_positive_growth: bool | None
```

- `complete` requires all three EPS values and both growth metrics.
- `partial` means at least one consensus estimate is available but the full two-interval evaluation is not.
- `unavailable` means consensus was requested but neither usable estimate was resolved.
- `confirms_positive_growth` is `true` only when both growth metrics are positive, `false` when both are meaningful and at least one is nonpositive, and `None` otherwise.
- Under `display_only` and `confirmation`, partial or unavailable evidence does not change the historical classification.
- Under `hard_gate`, anything other than `complete` produces `INDETERMINATE` with `consensus_unavailable`.

### 7.4 Annual observation and result

```text
AnnualGrowthObservation
    fiscal_year: int
    period_start: datetime
    period_end: datetime
    operating_cash_flow: ResolvedInput
    normalized_capital_expenditures: ResolvedInput
    free_cash_flow: ResolvedInput
    weighted_average_diluted_shares: ResolvedInput | None
    free_cash_flow_per_diluted_share: ResolvedInput | None
    diluted_eps: ResolvedInput
```

```text
FCFEarningsGrowthResult
    schema_version: int = 2
    strategy_id: str = "fcf_earnings_growth"
    method_id: str = "reported_fcf_eps_cagr"
    method_version: int = 2
    ticker: str
    requested_as_of: datetime | None
    effective_as_of: datetime
    policy: FCFEarningsGrowthPolicy
    execution_status: CalculationStatus
    classification: Classification
    classification_reason_code: ReasonCode | None
    classification_reason: str | None
    selected_horizon_years: int | None
    selected_observation_count: int
    used_horizon_fallback: bool
    period_start: datetime | None
    period_end: datetime | None
    annual_observations: tuple[AnnualGrowthObservation, ...]
    fcf_cagr: MetricResult
    fcf_per_share_cagr: MetricResult
    eps_cagr: MetricResult
    trend_classification: TrendClassification
    market_capitalization: ResolvedInput | None
    fcf_yield: MetricResult
    forward_evidence: ForwardEvidence
    warnings: tuple[str, ...]
    diagnostics: ResolutionTrace
```

Result invariants:

- successful `PASS` or `FAIL` has `execution_status = ok`, the selected controlling FCF metric and EPS metric `ok`, and non-null period fields;
- both FCF CAGRs are always present as `MetricResult`; unavailable noncontrolling FCF/share evidence does not alter default total-FCF classification;
- `PASS` has no classification reason; `FAIL` and `INDETERMINATE` have both classification-reason fields;
- `selected_observation_count` equals the length of `annual_observations`;
- a selected horizon of `N` has exactly `N + 1` observations;
- `used_horizon_fallback` is true only for `longest_available` when fewer than five elapsed years are selected;
- optional-metric failure does not change `execution_status` or historical classification unless `forward_policy = hard_gate`;
- negative financial values remain in `ResolvedInput`; unavailable calculated metrics use `MetricResult` and never `NaN`.

Execution status is assigned independently:

| Condition | Execution status | Classification |
| :--- | :--- | :--- |
| Required facts resolve and calculations are meaningful | `ok` | `PASS` or `FAIL` |
| Valid facts resolve but compound growth is mathematically nonmeaningful | `ok` | `INDETERMINATE` |
| Required evidence is missing or incompatible | `input_unavailable` | `INDETERMINATE` |
| A required provider operation fails | `provider_error` | `INDETERMINATE` |
| The request or policy is invalid | `invalid_input` | `INDETERMINATE` |

When `include_fcf_yield = false`, `fcf_yield` has `status = not_applicable` and `reason_code = not_requested`.

When several conditions apply, `classification_reason_code` identifies the first applicable category in this order: invalid request, required-provider error, incompatible or missing evidence required by the selected classification basis, insufficient or non-contiguous history, nonmeaningful controlling historical growth, unavailable required consensus, then failed growth gate. More specific details remain in the affected `MetricResult`, diagnostics, and warnings. Failed gates use `fcf_not_growing`, `eps_not_growing`, `fcf_and_eps_not_growing`, or `forward_growth_not_confirmed` as applicable; the result's policy identifies whether `fcf_not_growing` refers to total FCF or FCF/share.

`CalculationStatus`, `ResolvedInput`, and `ResolutionTrace` reuse the established shared contracts. Slice C1 confirmed that the Step 2.3 `Valuation*` vocabulary is narrower than the shared boundary it now describes: operating cash flow and capital expenditures are general financial facts, and the cache stores resolved provider or derived inputs rather than valuation results. Before C2, the bounded C1R migration therefore renames provider-facing fact contracts to `Financial*` and cache-facing contracts to `ResolvedInputCache*`, without changing their behavior or invariants.

In this vocabulary, a reporting-period observation is one period-identified occurrence of a financial fact; an annual series is an ordered collection of those facts. Numeric `value` fields continue to mean the fact's numeric payload, not a company valuation. Permanent compatibility aliases are added only if a concrete external consumer is identified during review.

## 8. Deterministic data-selection algorithms

### 8.1 Analysis boundary and candidate eligibility

The resolver captures one `effective_as_of` value for the complete analysis:

```text
effective_as_of = requested_as_of if supplied, otherwise captured_analysis_time
```

Every historical fact, current-market observation, and consensus estimate is evaluated against this same boundary.

A provider fact is eligible only when:

1. it belongs to the requested security;
2. it has finite numeric value and supported units;
3. it represents a completed fiscal-year duration, not an interim, year-to-date, quarterly, or trailing-twelve-month period;
4. its period end is on or before `effective_as_of`;
5. its publication or availability timestamp is on or before `effective_as_of`;
6. its accounting basis matches the requested semantic field.

An incomplete current fiscal year and all trailing-twelve-month facts are excluded before ranking. Completed annual facts remain eligible even when a provider also supplies a trailing-twelve-month series.

### 8.2 Compatibility predicate

Operating cash flow, capital expenditures, weighted-average diluted shares when available, and diluted earnings per share form one `AnnualGrowthObservation` only when all of the following match:

- normalized security identity;
- fiscal-year label;
- exact period start and period end;
- annual duration basis;
- ISO 4217 currency for monetary facts;
- compatible unit families: currency for cash-flow components, shares for weighted-average diluted shares, and currency-per-share for FCF/share and diluted earnings per share;
- consolidated reporting scope and share class;
- diluted earnings-per-share basis and split treatment.

Unknown currency, scope, or basis does not equal a known value. If the provider cannot prove compatibility, the period is unavailable. Currency conversion is not supported by this method.

### 8.3 Capital-expenditure normalization

Each approved provider mapping declares a sign convention and one transform:

```text
positive_expenditure: normalized = raw
negative_cash_outflow: normalized = -raw
```

Rules:

- normalized capital expenditures must be finite and greater than or equal to zero;
- zero is valid and remains zero;
- a value that contradicts the declared sign convention is rejected as `ambiguous_fact`, not passed through `abs()`;
- missing capital expenditures makes that annual free-cash-flow observation unavailable;
- multiple candidate concepts follow the approved provider precedence rule;
- concepts are never summed unless the approved mapping proves that they are non-overlapping components of the project's capital-expenditure definition;
- the raw value, convention, transform, and selected concept remain in lineage.

### 8.4 Amendments, restatements, and duplicates

Selection occurs after eligibility filtering:

1. group candidates by semantic field, security, fiscal period, basis, units, currency, and scope;
2. exclude every candidate with `available_at > effective_as_of`;
3. select the eligible candidate with the latest `available_at`;
4. if equally timed candidates have the same normalized value, select deterministically by a stable provider fact identifier and record the duplicate in lineage;
5. if equally ranked candidates have different normalized values and no approved provider rule resolves them, return `ambiguous_fact` and do not choose silently.

This selects the latest restatement knowable at the analysis boundary while preventing a later amendment from leaking into an earlier analysis.

### 8.5 Series and horizon selection

After compatible annual observations are assembled:

1. sort by period end from oldest to newest;
2. reject duplicate fiscal years and any gap inside a candidate span;
3. when a horizon is explicit, select the newest exact `N + 1` contiguous observations or return `insufficient_history`;
4. for `longest_available`, attempt five, four, and three elapsed years in that order;
5. use the first valid span and record whether fallback occurred;
6. do not use fewer than four observations.

Before calculating compound annual growth, reject a selected series whose beginning or ending value is nonpositive or whose values change sign within the selected span. The result preserves the annual values and uses the applicable reason code.

## 9. Provider mapping record

No production provider mapping for operating cash flow, capital expenditures, weighted-average diluted shares, market capitalization, or FY1/FY2 consensus is approved merely by this design.

Before a provider capability is enabled, its approved mapping must be added to this document or to a companion document titled **Free Cash Flow & Earnings Growth Provider Mapping Record**. That record is part of the strategy contract and contains:

| Required field | Meaning |
| :--- | :--- |
| Provider and capability | Provider identifier and semantic field |
| Exact source concepts | Every accepted provider field or filing concept |
| Selection precedence | Deterministic priority among candidates |
| Financial meaning | Included and excluded amounts |
| Sign transform | `positive_expenditure`, `negative_cash_outflow`, or not applicable |
| Period rules | Annual-duration and fiscal-period interpretation |
| Units, currency, and scope | Compatibility evidence |
| Availability timestamp | How public knowability is established |
| Amendments and duplicates | Provider-specific deterministic selection |
| Security identity | How the ticker maps to the intended security |
| Evidence | Authoritative source, retrieval date, and reviewed examples |
| Approval | Human approval date and resulting tests |

The implementation cannot enable a production mapping until this record and its deterministic tests exist. Unsupported capabilities remain explicitly unavailable.

**Post-closeout P1 refinement:** Live FLSW behavior exposed a cross-strategy distinction that this financial-fact mapping did not own: provider-backed instrument kind and method applicability. The proposed normalized Yahoo mappings, separate kind evidence, composed profile provenance, and known-ETF `not_applicable` behavior are governed by [`STEP_2_5_P1_INSTRUMENT_APPLICABILITY_MAPPING_RECORD.md`](../step-2.5/STEP_2_5_P1_INSTRUMENT_APPLICABILITY_MAPPING_RECORD.md). P1 does not change the company-level FCF formula or any approved SEC concept in this design.

### 9.1 Evidence-gated Slice D sequence

Provider research and production implementation are deliberately separated:

1. **D0 — provider evidence:** complete the mapping record from authoritative documentation and representative payloads. Decide exact concepts, meanings, signs, units, periods, availability, amendment/duplicate handling, and security identity. Make no production changes and stop for human approval.
2. **D1 — operating cash flow:** implement only the approved operating-cash-flow mapping and its deterministic tests.
3. **D2 — capital expenditures:** implement only the approved capital-expenditure mapping, sign transform, and deterministic tests.
4. **D3 — diluted EPS:** implement only the approved annual diluted-EPS compatibility, selection, and reconciliation rules with deterministic tests.
5. **D4 — composition:** connect the approved capabilities to the annual-series resolver while preserving typed unavailability and complete provenance.
6. **D5 — closeout:** add bounded integration regressions, run the complete quality gate, and verify that this record describes production behavior exactly.

The later approved FCF/share amendment follows the same evidence rule. Slice E1 adds and approves weighted-average diluted-share mappings before E2 enables them; D0–D5 are not retroactively rewritten to imply that they reviewed evidence outside their original scope.

Implementation agents receive approved mappings as inputs; they do not decide provider accounting semantics while writing adapters. Each production-capability slice stops for review, and any shape not supported by the approved evidence remains explicitly unavailable.

## 10. Deterministic calculation boundary

Financial arithmetic resides in pure Python functions. Candidate functions are:

```text
compute_free_cash_flow(operating_cash_flow, normalized_capital_expenditures)
compute_fcf_per_diluted_share(free_cash_flow, weighted_average_diluted_shares)
compute_growth_percent(current, prior)
compute_cagr(beginning, ending, elapsed_years)
compute_fcf_yield(free_cash_flow, market_capitalization)
classify_fcf_earnings_growth(...)
```

Pure functions reject non-finite inputs, perform no provider/cache/filesystem/clock/language-model access, infer no periods or accounting bases, and return typed results rather than `NaN` or infinity. Data selection, sign normalization, and provenance assembly occur outside these functions.

## 11. Verification contract

Deterministic fixtures provide at least six compatible completed fiscal years and never fall back to live data. Automated verification covers:

1. exact total free-cash-flow, FCF-per-diluted-share, growth, and yield arithmetic;
2. each capital-expenditure sign convention, zero, missing data, contradictory signs, concept precedence, and forbidden summing;
3. compatibility across identity, period, basis, units, currency, scope, and split treatment;
4. exclusion of interim, incomplete, year-to-date, quarterly, and trailing-twelve-month facts;
5. amendment/restatement selection before and after `as_of`, including unresolved ties;
6. three-, four-, and five-year compound annual growth and the six-observation/five-interval example;
7. automatic fallback, strict explicit periods, gaps, and insufficient history;
8. positive, zero, negative, and sign-changing endpoints;
9. both classification bases, every classification, trend description, execution status, reason code, and invariant;
10. complete, partial, unavailable, and not-requested forward evidence under every forward policy;
11. optional market-capitalization failure and the prohibition on yield affecting classification;
12. complete free-cash-flow and weighted-average-diluted-share lineage and historical point-in-time behavior;
13. exact concise-output order, warning precedence, and presentation-mode combinations;
14. identical typed results across command-line, JSON, chart, and runtime-agent presentation paths;
15. schema and method version behavior;
16. clean invalid-request, missing-input, and provider-error surfaces;
17. absence of live provider and language-model calls from deterministic tests.

The completed implementation also satisfies the repository's formatting, linting, strict type-checking, coverage, documentation, and full test gates.
