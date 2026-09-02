# Step 2.5 Golden-Suite Expected Values

**Status:** Slice B1 approved; Slice B2 FCF/Earnings Growth expectations pending human review  
**Fixture schema:** `step-2.5-b2-v1`  
**Authority:** [`IMPLEMENTATION_PLAN.md`](../IMPLEMENTATION_PLAN.md),
[`STEP_2_5_GOLDEN_SUITE_SLICE_PLAN.md`](STEP_2_5_GOLDEN_SUITE_SLICE_PLAN.md), and
[`docs/user/FINANCE_MATH.md`](../../../../user/FINANCE_MATH.md)

## 1. Scope and derivation policy

This dossier defines the proposed minimum Momentum, Graham, and FCF/Earnings Growth benchmark truth before executable
Golden cases or evaluators consume it. The reviewed Slice B1 Momentum and Graham values remain unchanged; Slice B2
adds only the three minimum FCF/Earnings Growth cases.

All arithmetic below was derived directly from the listed fixture values and documented formulas. Production strategy
calculators were not invoked to generate any expected value. Square roots, divisions, and fractional powers were
cross-checked with at least 40-digit decimal arithmetic. Status strings, identifiers, source kinds, and missing values
are exact expectations and have no numerical tolerance.

Unless a case states otherwise:

- exact fixture inputs are synthetic, deterministic, USD-denominated evidence;
- Graham numerical comparisons use absolute tolerance `1e-9` and no relative tolerance;
- Momentum moving averages, prices, crossover, and RSI use absolute tolerance `1e-12` and no relative tolerance;
- FCF/Earnings Growth values and CAGRs use absolute tolerance `1e-12` and no relative tolerance;
- unavailable numerical fields are expected to be JSON `null`, never NaN or infinity;
- the requested tool and Graham method are exact selection expectations; and
- no case permits live provider access, a different strategy, fabricated inputs, or automatic strategy substitution.

## 2. Fixture inventory

### 2.1 Momentum price evidence

Both Momentum frames are returned as fresh pandas objects with a monotonic UTC `Timestamp` index beginning
`2026-01-02`. The calculation configuration is:

| Input | Value |
|---|---:|
| Short SMA window | 2 observations |
| Long SMA window | 3 observations |
| RSI period | 3 changes, requiring at least 4 prices |
| Success closes | `100.0, 101.0, 102.0, 103.0, 104.0` |
| Boundary closes | `100.0, 101.0` |

The frame is synthetic fixture evidence from `fixture_market`; it is not historical data for a real security.

### 2.2 Graham financial evidence

The common security subject is synthetic `SYNTH`, from provider `fixture-synth`, unless a case names another subject.
All provider facts retain their observation, availability, retrieval, basis, currency, and field metadata in
`src/evaluation/fixtures/graham.py`.

| Fact | Value | Basis / observation | Available at |
|---|---:|---|---|
| FY2022 diluted EPS | 2.10 | fiscal year ended 2022-06-30 | 2022-09-15 UTC |
| FY2023 diluted EPS | 3.40 | fiscal year ended 2023-06-30 | 2023-09-14 UTC |
| FY2024 diluted EPS | 4.20 | fiscal year ended 2024-06-30 | 2024-09-13 UTC |
| TTM diluted EPS | 4.80 | twelve months ended 2025-06-30 | 2025-06-30 12:00 UTC |
| BVPS | 18.50 | period ended 2024-12-31 | 2025-02-10 UTC |
| Current quote | 52.30 USD | observed 2025-06-30 16:00 UTC | same timestamp |
| Current AAA yield | 4.15 percentage points | observed 2025-06-27 | 2025-06-27 UTC |

Additional reviewed inputs are:

| Input | Value |
|---|---:|
| Growth expectation `g` | 6.5 percentage points |
| Growth base P/E | 8.5 |
| Growth multiplier | 2.0 |
| Baseline AAA yield | 4.4 percentage points |
| Precedence-case EPS override | 5.00 |
| Precedence-case cached BVPS | 20.00 |
| Historical publication boundary | 2024-08-01 12:00 UTC |

`MISSING_QUOTE` has the same three annual EPS facts and BVPS, rewritten only to retain the correct synthetic subject,
but returns no current-price fact. It distinguishes optional quote absence from missing required company facts.

### 2.3 Instrument-kind evidence

The cross-strategy applicability case uses current provider-backed profile evidence:

| Field | Value |
|---|---|
| Ticker | `FLSW` |
| Instrument name | `Franklin FTSE Switzerland ETF` |
| Normalized kind | `etf` |
| Raw Yahoo classification | `ETF` |
| Kind provider | `yfinance` |
| Resolved at | 2026-08-30 18:00 UTC |

ETF status is established only by this affirmative profile evidence. It is not inferred from the ticker, name,
missing company facts, or Momentum success.

## 3. Proposed Momentum cases

### MOM-01 — straightforward rising trend

**Purpose and signal:** Proves successful deterministic Momentum arithmetic and distinguishes a valid rising-price
analysis from unavailable history. Expected tool: `analyze_momentum`.

Exact closes are `100, 101, 102, 103, 104` with windows `2`, `3`, and RSI period `3`.

```text
current_price = 104
short_sma = (103 + 104) / 2 = 103.5
long_sma  = (102 + 103 + 104) / 3 = 103.0
signal[t] = 1 because 103.5 > 103.0

prior short_sma = (102 + 103) / 2 = 102.5
prior long_sma  = (101 + 102 + 103) / 3 = 102.0
signal[t-1] = 1
crossover = 1 - 1 = 0

trailing changes = 1, 1, 1
average gain = 1
average loss = 0
RSI = 100
```

Expected structured outcome:

| Field | Expected value | Tolerance |
|---|---:|---:|
| `metrics.status` | `BULLISH` | exact |
| `metrics.current_price` | 104.0 | abs `1e-12` |
| `metrics.short_sma_val` | 103.5 | abs `1e-12` |
| `metrics.long_sma_val` | 103.0 | abs `1e-12` |
| `metrics.crossover_signal` | 0.0 | abs `1e-12` |
| `metrics.rsi_result.status` | `ok` | exact |
| `metrics.rsi_result.value` | 100.0 | abs `1e-12` |

### MOM-02 — one observation short of the long window

**Purpose and signal:** Proves boundary behavior: an available short SMA does not justify a trend or crossover when
the long window is unavailable. Expected tool: `analyze_momentum`.

Exact closes are `100, 101`; this is exactly `long_window - 1` observations.

```text
current_price = 101
short_sma = (100 + 101) / 2 = 100.5
long_sma = unavailable because 2 < 3
crossover = unavailable because both SMAs are required
RSI = unavailable because period 3 requires at least 4 prices
```

Expected structured outcome:

| Field | Expected value | Tolerance |
|---|---:|---:|
| `metrics.status` | `UNKNOWN` | exact |
| `metrics.current_price` | 101.0 | abs `1e-12` |
| `metrics.short_sma_val` | 100.5 | abs `1e-12` |
| `metrics.long_sma_val` | `null` | exact |
| `metrics.crossover_signal` | `null` | exact |
| `metrics.rsi_result.status` | `unavailable` | exact |
| `metrics.rsi_result.reason_code` | `insufficient_history` | exact |
| `metrics.rsi_result.value` | `null` | exact |

## 4. Proposed Graham Number cases

The Graham Number formula is:

```text
maximum_indicated_price = sqrt(22.5 × EPS × BVPS)
margin_of_safety_percent = (maximum_indicated_price - current_price)
                           / maximum_indicated_price × 100
```

### GRN-01 — default three-year-average EPS

**Purpose and signal:** Freezes the standard three-completed-fiscal-year earnings convention and derived EPS lineage.
Expected tool/method: `analyze_graham_number` / `graham_number`.

```text
three_year_average_eps = (2.10 + 3.40 + 4.20) / 3
                       = 9.70 / 3
                       = 3.233333333333333333...

radicand = 22.5 × (9.70 / 3) × 18.50
          = 1,345.875

maximum_indicated_price = sqrt(1,345.875)
                        = 36.686169055926240...

margin = (36.686169055926240... - 52.30) / 36.686169055926240... × 100
       = -42.560538060736871...%
```

| Field | Expected value | Tolerance |
|---|---:|---:|
| `result.status` | `ok` | exact |
| `assembly.eps.value` | 3.2333333333333333 | abs `1e-15` |
| `result.maximum_indicated_price` | 36.68616905592624 | abs `1e-9` |
| `margin_of_safety_percent` | -42.56053806073687 | abs `1e-9` |

The negative margin means the fixture quote is above the screening ceiling; it is not converted to a positive
percentage in the typed result.

### GRN-02 — explicitly selected TTM EPS variation

**Purpose and signal:** Proves that the explicit TTM variation uses the retained TTM fact rather than silently
averaging fiscal-year observations. Expected tool/method: `analyze_graham_number` / `graham_number` with
`eps_basis = ttm`.

```text
radicand = 22.5 × 4.80 × 18.50 = 1,998.0
maximum_indicated_price = sqrt(1,998.0) = 44.698993277254019...
margin = (44.698993277254019... - 52.30) / 44.698993277254019... × 100
       = -17.004872292311572...%
```

| Field | Expected value | Tolerance |
|---|---:|---:|
| `result.status` | `ok` | exact |
| `assembly.eps.value` | 4.80 | exact fixture value |
| `assembly.eps.basis` | `ttm` | exact |
| `result.maximum_indicated_price` | 44.69899327725402 | abs `1e-9` |
| `margin_of_safety_percent` | -17.00487229231157 | abs `1e-9` |

### GRN-03 — required inputs present, optional quote absent

**Purpose and signal:** Proves a missing current quote omits only price comparison; it does not erase a valid Graham
Number or turn an optional input into a required one. Subject: `MISSING_QUOTE`. Expected tool/method:
`analyze_graham_number` / `graham_number`.

The three-year EPS and BVPS arithmetic is identical to GRN-01, so the independently derived screening ceiling remains
`36.68616905592624`. No current price enters a margin formula.

| Field | Expected value | Tolerance |
|---|---:|---:|
| `assembly.status` | `ok` | exact |
| `result.status` | `ok` | exact |
| `result.maximum_indicated_price` | 36.68616905592624 | abs `1e-9` |
| `assembly.current_price` | `null` | exact |
| `margin_of_safety_percent` | `null` | exact |

## 5. Graham growth value and method discrimination

### GRG-01 — explicit TTM growth assumptions and AAA yield

**Purpose and signal:** Proves the forecast-dependent growth method, explicit assumptions, yield adjustment, and
selection discrimination from the Graham Number. Expected tool/method: `analyze_graham_growth_value` /
`graham_growth_value` with TTM EPS.

```text
valuation_pe = 8.5 + 2.0 × 6.5 = 21.5

growth_value = 4.80 × 21.5 × 4.4 / 4.15
             = 109.416867469879518...

margin = (109.416867469879518... - 52.30) / 109.416867469879518... × 100
       = 52.201153981677237...%
```

| Field | Expected value | Tolerance |
|---|---:|---:|
| `result.status` | `ok` | exact |
| `assembly.eps.value` | 4.80 | exact fixture value |
| `assembly.eps.basis` | `ttm` | exact |
| `assembly.expected_growth.value` | 6.5 | exact assumption |
| `assembly.current_aaa_yield.value` | 4.15 | exact assumption |
| `policy.base_pe` | 8.5 | exact |
| `policy.growth_multiplier` | 2.0 | exact |
| `policy.baseline_aaa_yield` | 4.4 | exact |
| `result.growth_value` | 109.41686746987952 | abs `1e-9` |
| `margin_of_safety_percent` | 52.20115398167724 | abs `1e-9` |

Selecting the TTM Graham Number instead would produce `44.69899327725402`, a materially different result. Therefore
this case independently detects Graham-method mis-selection; plausible prose cannot make the wrong method pass.

## 6. Applicability case

### GRA-ETF-01 — provider-confirmed ETF across Momentum and both Graham methods

**Purpose and signal:** Freezes the P1 strategy-applicability contract. The affirmative `FLSW` ETF profile is shared
as evidence; company facts are neither requested nor manufactured.

Expected outcomes:

- Momentum remains applicable. With the MOM-01 synthetic price frame it has the same `BULLISH`, SMA, crossover, and
  RSI values documented in MOM-01.
- Graham Number returns `result.status = not_applicable`, no screening ceiling, and no margin.
- Graham growth value returns `result.status = not_applicable`, no growth value, and no margin.
- Both Graham reasons identify the selected company-level method, state that it does not apply directly to an ETF,
  and state that no constituent-level or aggregate ETF valuation was performed.
- The ETF is not classified as an invalid ticker, `input_unavailable`, or `provider_error`; no future aggregate
  strategy is selected automatically.

This case uses exact status/text constraints and no Graham numerical tolerance because no Graham calculation applies.

## 7. Resolution semantics cases

### GRN-04 — override, cache, then provider precedence

**Purpose and signal:** Proves all three resolution levels without allowing lower-precedence values to alter the
result. Expected method: Graham Number at `as_of = 2025-07-01 12:00 UTC`.

Expected resolved inputs:

- EPS = `5.00`, source `override`; the provider's three-year average `3.233333...` must not win.
- BVPS = `20.00`, source `cache`, retaining provider origin; provider BVPS `18.50` must not win.
- current price = `52.30`, source `provider`, because neither override nor cache supplies it.

```text
radicand = 22.5 × 5.00 × 20.00 = 2,250.0
maximum_indicated_price = sqrt(2,250.0) = 47.434164902525690...
margin = (47.434164902525690... - 52.30) / 47.434164902525690... × 100
       = -10.258081084537493...%
```

| Field | Expected value | Tolerance |
|---|---:|---:|
| `result.status` | `ok` | exact |
| `assembly.eps.source_kind` | `override` | exact |
| `assembly.bvps.source_kind` | `cache` | exact |
| `assembly.current_price.source_kind` | `provider` | exact |
| `result.maximum_indicated_price` | 47.43416490252569 | abs `1e-9` |
| `margin_of_safety_percent` | -10.258081084537493 | abs `1e-9` |

### GRN-05 — historical `as_of` rejects unpublished evidence

**Purpose and signal:** Detects look-ahead bias and distinguishes unavailable historical evidence from zero or an
invalid ticker. Expected method: default three-year-average Graham Number at `as_of = 2024-08-01 12:00 UTC`.

At that boundary:

- FY2022 EPS was available on 2022-09-15;
- FY2023 EPS was available on 2023-09-14;
- FY2024 EPS is ineligible because it was not available until 2024-09-13;
- the 2024-12-31 BVPS and 2025 quote are also later evidence.

Only two of the required three completed annual EPS observations are eligible. Expected status is
`input_unavailable`; EPS, BVPS, screening ceiling, current-price comparison, and margin are absent. The case must not
substitute zero, use the later publication, or advise that the ticker is invalid.

## 8. Slice B1 approval record

Slice B1's nine cases were reviewed and approved on 2026-08-31: two Momentum, five Graham Number/resolution, one
Graham growth-value, and one cross-strategy ETF applicability case. GRG-01 supplies the required Graham-method
discrimination signal. Slice B2 does not alter any approved Slice B1 fixture value, calculation, status, or tolerance.

## 9. FCF/Earnings Growth fixture inventory

The common subject is synthetic security `ACME`, provider `annual-fixture`, in USD. All facts represent completed,
consolidated fiscal years. Periods use exact-touching boundary intervals, and CapEx uses the explicit
`positive_expenditure` sign convention. Weighted-average diluted shares are constant, so total FCF and FCF/share have
the same percentage growth whenever both CAGRs are meaningful.

| Fiscal year | Period start | Period end | Available at | OCF | CapEx | Derived FCF | Diluted shares | FCF/share | Diluted EPS |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 2020 | 2019-01-01 | 2020-01-01 | 2020-02-01 UTC | 100.0 | 20.0 | 80.0 | 100.0 | 0.80 | 2.0 |
| 2021 | 2020-01-01 | 2021-01-01 | 2021-02-01 UTC | 110.0 | 20.0 | 90.0 | 100.0 | 0.90 | 2.5 |
| 2022 | 2021-01-01 | 2022-01-01 | 2022-02-01 UTC | 120.0 | 20.0 | 100.0 | 100.0 | 1.00 | 3.0 |
| 2023 | 2022-01-01 | 2023-01-01 | 2023-02-01 UTC | 130.0 | 20.0 | 110.0 | 100.0 | 1.10 | 3.5 |
| 2024 | 2023-01-01 | 2024-01-01 | 2024-02-01 UTC | 140.0 | 20.0 | 120.0 | 100.0 | 1.20 | 4.0 |
| 2025 | 2024-01-01 | 2025-01-01 | 2025-02-01 UTC | 150.0 | 20.0 | 130.0 | 100.0 | 1.30 | 4.5 |

For every row:

```text
free_cash_flow = operating_cash_flow - normalized_capital_expenditures
free_cash_flow_per_diluted_share = free_cash_flow / weighted_average_diluted_shares
```

FCF-02 changes only FY2022 OCF from `120.0` to `15.0`, producing FCF `-5.0` and FCF/share `-0.05`.
FCF-03 retains the table's values but changes only FY2023 diluted EPS period start to `2022-01-02`; OCF and CapEx
retain `2022-01-01`. Its historical boundary is `2025-01-15 00:00 UTC`, before every FY2025 fact's publication on
`2025-02-01`.

## 10. Proposed FCF/Earnings Growth cases

The historical CAGR formula is:

```text
cagr_percent = ((ending / beginning) ** (1 / elapsed_years) - 1) * 100
```

All three cases expect tool `analyze_fcf_earnings_growth`, default total-company-FCF classification basis, and no
forward hard gate. Numerical comparisons use absolute tolerance `1e-12` and no relative tolerance. Statuses, reason
codes, classifications, year counts, and unavailable values are exact.

### FCF-01 — straightforward five-year historical growth

**Purpose and signal:** Proves aligned annual derivation, the difference between six observations and five elapsed
years, both reported FCF bases, and the positive historical classification. It also discriminates the requested
FCF/Earnings Growth strategy from Momentum: passing requires annual OCF, CapEx, diluted-share, and EPS evidence plus
FCF/EPS CAGRs, not price-trend metrics.

```text
elapsed_years = 2025 - 2020 = 5
observation_count = 6

total_fcf_cagr = ((130 / 80) ** (1 / 5) - 1) * 100
               = 10.197228772148014667...%

fcf_per_share_cagr = ((1.30 / 0.80) ** (1 / 5) - 1) * 100
                   = 10.197228772148014667...%

diluted_eps_cagr = ((4.5 / 2.0) ** (1 / 5) - 1) * 100
                 = 17.607902252467357258...%
```

| Field | Expected value | Tolerance |
|---|---:|---:|
| `execution_status` | `ok` | exact |
| `selected_horizon_years` | 5 | exact |
| `selected_observation_count` | 6 | exact |
| `used_horizon_fallback` | `false` | exact |
| `fcf_cagr.status` | `ok` | exact |
| `fcf_cagr.value` | 10.197228772148015 | abs `1e-12` |
| `fcf_per_share_cagr.status` | `ok` | exact |
| `fcf_per_share_cagr.value` | 10.197228772148015 | abs `1e-12` |
| `eps_cagr.status` | `ok` | exact |
| `eps_cagr.value` | 17.607902252467357 | abs `1e-12` |
| `classification` | `pass` | exact |
| `trend_classification` | `both_growing` | exact |
| `classification_reason_code` | `null` | exact |

### FCF-02 — interior FCF sign change makes CAGR nonmeaningful

**Purpose and signal:** Proves that positive endpoints cannot hide a sign change inside the selected span. The raw
history remains valid evidence, but compound growth is not meaningful and must not be calculated from endpoints alone.

```text
FCF history = 80, 90, -5, 110, 120, 130
FCF/share history = 0.80, 0.90, -0.05, 1.10, 1.20, 1.30
elapsed_years = 5
observation_count = 6

80 > 0 and 130 > 0, but 90 × -5 < 0 and -5 × 110 < 0
therefore total FCF CAGR and FCF/share CAGR are unavailable: sign_change

diluted_eps_cagr = ((4.5 / 2.0) ** (1 / 5) - 1) * 100
                 = 17.607902252467357258...%
```

The endpoint-only value `10.197228772148015%` is explicitly forbidden for either FCF CAGR in this case because it
would conceal the intervening negative observation.

| Field | Expected value | Tolerance |
|---|---:|---:|
| `execution_status` | `ok` | exact |
| `selected_horizon_years` | 5 | exact |
| `selected_observation_count` | 6 | exact |
| `fcf_cagr.status` | `unavailable` | exact |
| `fcf_cagr.reason_code` | `sign_change` | exact |
| `fcf_cagr.value` | `null` | exact |
| `fcf_per_share_cagr.status` | `unavailable` | exact |
| `fcf_per_share_cagr.reason_code` | `sign_change` | exact |
| `fcf_per_share_cagr.value` | `null` | exact |
| `eps_cagr.status` | `ok` | exact |
| `eps_cagr.value` | 17.607902252467357 | abs `1e-12` |
| `classification` | `indeterminate` | exact |
| `trend_classification` | `insufficient_or_nonmeaningful_growth` | exact |
| `classification_reason_code` | `sign_change` | exact |

### FCF-03 — strict period alignment at a historical publication boundary

**Purpose and signal:** Detects both incompatible period joining and look-ahead bias in one minimum case. Policy
requests an explicit four-year horizon, which is strict and requires five aligned, contiguous observations.

At `as_of = 2025-01-15 00:00 UTC`:

- all four FY2025 facts are ineligible because their `available_at` is `2025-02-01`;
- FY2023 EPS spans `2022-01-02` through `2023-01-01`, while FY2023 OCF and CapEx span `2022-01-01` through
  `2023-01-01`, so they cannot be joined as one annual observation;
- the exact common periods are therefore FY2020, FY2021, FY2022, and FY2024; and
- those four observations contain a FY2023 gap and cannot satisfy a strict four-elapsed-year request.

No selected elapsed period or CAGR exists. If an implementation incorrectly ignored the gap, its endpoint arithmetic
would be:

```text
invalid total_fcf_cagr = ((120 / 80) ** (1 / 4) - 1) * 100
                       = 10.668191970032159240...%

invalid diluted_eps_cagr = ((4.0 / 2.0) ** (1 / 4) - 1) * 100
                         = 18.920711500272106671...%
```

Those values are rejection sentinels, not expectations. Producing either one would prove that the implementation
silently bridged a non-contiguous period or used evidence outside the historical boundary.

| Field | Expected value | Tolerance |
|---|---:|---:|
| `execution_status` | `input_unavailable` | exact |
| `selected_horizon_years` | `null` | exact |
| `selected_observation_count` | 0 | exact |
| `used_horizon_fallback` | `false` | exact |
| `fcf_cagr.status` | `unavailable` | exact |
| `fcf_cagr.reason_code` | `non_contiguous_history` | exact |
| `fcf_cagr.value` | `null` | exact |
| `fcf_per_share_cagr.status` | `unavailable` | exact |
| `fcf_per_share_cagr.reason_code` | `non_contiguous_history` | exact |
| `eps_cagr.status` | `unavailable` | exact |
| `eps_cagr.reason_code` | `non_contiguous_history` | exact |
| `classification` | `indeterminate` | exact |
| `trend_classification` | `insufficient_or_nonmeaningful_growth` | exact |
| `classification_reason_code` | `non_contiguous_history` | exact |

## 11. Slice B2 review checklist and Slice C gate

The complete proposed minimum dossier now contains twelve stable cases: nine approved Slice B1 cases and three Slice
B2 FCF/Earnings Growth cases. No executable Golden case, evaluator, runner, or production calculation behavior is
introduced by Slice B2.

Before Slice C consumes the FCF expectations, review must confirm:

1. the common annual values, units, sign convention, period bounds, and publication timestamps;
2. the distinction between six observations and five elapsed years;
3. the independently derived FCF, FCF/share, and diluted-EPS CAGRs and absolute tolerance `1e-12`;
4. `pass` for FCF-01 and `indeterminate` with `sign_change` for FCF-02;
5. exact-period intersection and FY2025 look-ahead rejection in FCF-03; and
6. the strict-horizon `non_contiguous_history` outcome and rejection-sentinel CAGRs.

Stop for human expectation review before Slice C. The approved Slice B1 values remain frozen unless a later explicit
review record authorizes a change.
