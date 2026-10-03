# Step 3.5 — Strategy Specifications

Owns each Step 3.5 strategy's formulas, outcomes and edge cases. Shared metrics (market cap,
EBIT, EBITDA, EV, invested capital, FCF), applicability, outcomes and ranking are defined once in
[Shared definitions](STEP_3_5_SHARED_DEFINITIONS.md) and referenced here as "SD §n". Scope,
sequencing and status live in the [contract](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status).

When a strategy is implemented, its formula semantics move into `docs/user/FINANCE_MATH.md`,
which then becomes their authority.

**Conventions**

- *t* is the selected fiscal year, *t−1* the prior fiscal year and *t−2* the year before that.
  Period selection and alignment follow SD §3.
- "Beginning-of-year" total assets for year *t* are total assets at the end of year *t−1*.
- **Gross profit** is the reported gross profit. When the filer reports none, it is sales − cost of
  revenue, if both are reported, and the result keeps both inputs' provenance. It is never taken
  from operating income. Gross margin is gross profit ÷ sales.
- Each strategy is a `BaseAnalyzer` subpackage under `src/analysis/strategy/` (for example,
  `src/analysis/strategy/piotroski/`), registered through SWC's strategy descriptor.
- Every metric follows SD §2's outcome rules.

| # | Strategy | Investor question |
| :--- | :--- | :--- |
| 1 | Piotroski F-Score | Is fundamental quality improving across nine binary tests? |
| 2 | Altman Z-Score (Z and Z″) | How far is a non-financial firm from statistical distress? |
| 3 | Beneish M-Score | Do the accounts show patterns associated with earnings manipulation? |
| 4 | Cash-Flow Valuation Multiples | How expensive is the business relative to its cash generation? |
| 5 | Greenblatt Magic Formula | Which names in a watchlist combine high return on capital with a high earnings yield? |
| 6 | Interest Coverage | How comfortably do operating earnings cover interest? |
| 7 | ROIC and Incremental ROIC | How well does management deploy capital, and do returns hold up on new capital? |

## 1. Piotroski F-Score

The nine-test structure of Piotroski (2000), under the project conventions listed
[below](#conventions-and-deviations). It is not a literal reproduction of the paper: one test is
substituted. Source evidence, a worked example and the arithmetic oracle are in the
[Piotroski evidence record](STEP_3_5_PIOTROSKI_EVIDENCE.md).

**Inputs**

- Total assets (TA) at three fiscal year-ends: *t*, *t−1* and *t−2*. The earliest is never
  replaced by a later one.
- Net income (NI), sales and gross profit for years *t* and *t−1*; operating cash flow (CFO) for
  year *t*.
- Long-term debt (LTD), current assets, current liabilities and split-adjusted common shares
  outstanding at year-ends *t* and *t−1*.

**The nine tests**

| # | Group | Test | Passes when |
| :--- | :--- | :--- | :--- |
| 1 | Profitability | Positive ROA | NIₜ ÷ TAₜ₋₁ > 0 |
| 2 | Profitability | Positive CFO | CFOₜ ÷ TAₜ₋₁ > 0 |
| 3 | Profitability | Improving ROA | NIₜ ÷ TAₜ₋₁ > NIₜ₋₁ ÷ TAₜ₋₂ |
| 4 | Profitability | Cash exceeds income | CFOₜ > NIₜ |
| 5 | Leverage and liquidity | Falling leverage | LTDₜ ÷ average(TAₜ, TAₜ₋₁) < LTDₜ₋₁ ÷ average(TAₜ₋₁, TAₜ₋₂), or LTD is zero in both years |
| 6 | Leverage and liquidity | Improving liquidity | current assetsₜ ÷ current liabilitiesₜ > the same for *t−1* |
| 7 | Leverage and liquidity | No dilution | split-adjusted sharesₜ ≤ sharesₜ₋₁ |
| 8 | Efficiency | Improving margin | gross marginₜ > gross marginₜ₋₁ |
| 9 | Efficiency | Improving turnover | salesₜ ÷ TAₜ₋₁ > salesₜ₋₁ ÷ TAₜ₋₂ |

**Comparison rules**

- Comparisons are strict and made on unrounded values, with no tolerance. An unchanged ratio earns
  no point. The two stated exceptions are test 5's zero-debt case and test 7, where an unchanged
  share count passes.
- Total assets, sales and current liabilities must be positive wherever they are a denominator;
  otherwise the test is unavailable.
- Negative net income, CFO and gross profit are valid inputs. Zero current assets and zero LTD are
  valid inputs.

**Outcomes**

- **Test outcomes:** each test is pass, fail or unavailable, with its operands, ratios and
  provenance. A test is unavailable when an input is missing or a denominator is not positive, and
  an unavailable test is never scored as a fail.
- **Score:**

  | Tests available | Score `MetricResult` | Result completeness |
  | :--- | :--- | :--- |
  | 9 | `ok`, 0–9 | complete |
  | 6 to 8 | `ok`, the number passed, shown as "*x* of *n*" | partial |
  | Fewer than 6 | `unavailable` | — |

- **Partial scores:** always shown as "*x* of *n*" with the unavailable tests named, never as a
  bare number and never as "*x* of 9". The guide's nine-point reading (high and low scores) applies
  to complete scores only.
- **Ranking:** a partial score never enters a ranking.
- **Latest year only:** if year *t*'s inputs are missing, the affected tests are unavailable. The
  analyzer never falls back to scoring an older year (SD §3).
- **Financial issuers:** applicable with a warning (SD §1). Their gross-margin and current-ratio
  tests are typically unavailable.

### Conventions and deviations

The paper leaves several definitions open or uses data items that no longer exist. Each choice
below is fixed for the method and shown in the result; none is a user option.

- **Income:** net income as reported. The paper uses income before extraordinary items; US GAAP
  removed extraordinary items in 2015, so net income is the modern equivalent. Income from
  continuing operations is not used: many filers never report it.
- **Turnover denominator:** beginning-of-year total assets, following the paper's method text. Its
  Table 1 says average assets; the two can disagree, and the oracle includes a case that tells
  them apart.
- **Long-term debt:** current portion of long-term debt + long-term debt, as the paper's "total
  long-term debt". Short-term borrowings and lease liabilities are excluded. Absent components
  follow SD §6's total-debt rule.
- **Zero debt:** a firm with no long-term debt in either year passes test 5. It cannot reduce
  leverage further, and failing it would penalize the strongest balance sheets.
- **Dilution:** test 7 uses the change in split-adjusted shares outstanding, not the paper's
  equity-issuance test.
  - Issuance proceeds include option exercises, which would fail nearly every issuer.
  - Issuance evidence is also unreliable in structured filings: Apple reports no issuance-proceeds
    concept after fiscal 2021.
  - The cost, stated in the guide: this measures net dilution. A firm can issue shares and still
    pass when buybacks exceed issuance, as Apple did in fiscal 2024.
- **How it is named:** the user guide and `FINANCE_MATH.md` open with this statement: "This
  implementation follows the Piotroski nine-test structure but substitutes the net change in
  split-adjusted shares outstanding for the original equity-issuance signal, because issuance
  cannot be established reliably from structured filings." The other conventions above are listed
  beside it.

## 2. Altman Z-Score

**Model selection (SD §1)**

- Manufacturers: the classic 1968 Z.
- Other non-financial issuers: Z″, the non-manufacturer variant.
- Financial issuers: `not_applicable`.

The result names the model used.

**Classic Z (manufacturers)**

Z = 1.2X₁ + 1.4X₂ + 3.3X₃ + 0.6X₄ + 0.999X₅

| Variable | Definition |
| :--- | :--- |
| X₁ | working capital ÷ total assets |
| X₂ | retained earnings ÷ total assets |
| X₃ | EBIT (SD §5) ÷ total assets |
| X₄ | market cap (SD §4) ÷ total liabilities |
| X₅ | sales ÷ total assets |

Zones: Safe when Z > 2.99; Grey when 1.81 ≤ Z ≤ 2.99; Distress when Z < 1.81.

**Z″ (non-manufacturers)**

Z″ = 6.56X₁ + 3.26X₂ + 6.72X₃ + 1.05X₄

- X₁ to X₃ as above.
- X₄ = book equity ÷ total liabilities.
- There is no sales term.

Zones: Safe when Z″ > 2.60; Grey when 1.10 ≤ Z″ ≤ 2.60; Distress when Z″ < 1.10.

**Edge cases**

- Negative retained earnings and negative book equity are valid inputs, not errors.
- Total assets ≤ 0 or total liabilities ≤ 0 makes the score `unavailable`.

## 3. Beneish M-Score

The eight-variable model from Beneish (1999), under the conventions listed with the edge cases
below. Where a deviation applies to a run, the result names it; the score is then a Beneish-style
score on the project's stated convention, not the canonical one.

M = −4.84 + 0.920·DSRI + 0.528·GMI + 0.404·AQI + 0.892·SGI + 0.115·DEPI − 0.172·SGAI +
4.679·TATA − 0.327·LVGI

| Index | Definition |
| :--- | :--- |
| DSRI | (receivables ÷ sales)ₜ ÷ (receivables ÷ sales)ₜ₋₁ |
| GMI | gross marginₜ₋₁ ÷ gross marginₜ |
| AQI | [1 − (current assets + net PP&E + long-term investments) ÷ total assets]ₜ ÷ the same for *t−1* |
| SGI | salesₜ ÷ salesₜ₋₁ |
| DEPI | [depreciation ÷ (depreciation + net PP&E)]ₜ₋₁ ÷ the same for *t*; see [DEPI basis](#depi-basis) |
| SGAI | (SG&A ÷ sales)ₜ ÷ (SG&A ÷ sales)ₜ₋₁ |
| LVGI | [(current liabilities + noncurrent long-term debt) ÷ total assets]ₜ ÷ the same for *t−1* |
| TATA | (income from continuing operations − CFO)ₜ ÷ total assetsₜ |

**Edge cases**

- Any index that cannot be computed makes the whole score `unavailable`. No index defaults to 1.0.
- **No partial score.** The M-Score is one regression equation whose coefficients assume all eight
  inputs, so a score over fewer indices has no meaning. Piotroski's partial score is different: it
  is an additive count of independent tests.
- Long-term investments follow the absent-component convention (SD §3).
- **LVGI debt** is the noncurrent portion only. The current portion of long-term debt is already
  inside current liabilities and is not counted twice.
- **TATA income:** income from continuing operations when the filer reports it. When the filer
  reports neither that concept nor any discontinued-operations amount for the year, net income is
  the same quantity and is used, with a diagnostic. When discontinued operations are reported
  without continuing income, TATA is `unavailable`. Many filers, Apple among them, never report a
  continuing-operations concept, so requiring it would make the score unavailable for them.
- Financial issuers: `not_applicable`.

### DEPI basis

The model defines DEPI on depreciation alone. Many filers report only combined depreciation and
amortization (D&A), so the basis is chosen in this order:

| Depreciation alone, both years | Combined D&A (SD §5), both years | DEPI basis | Result |
| :--- | :--- | :--- | :--- |
| Available | — | `depreciation` | Canonical index |
| Not available | Available | `depreciation_and_amortization` | Index computed, with a diagnostic naming the deviation |
| Not available | Not available | — | DEPI and the M-Score are `unavailable` |

- **One basis per run.** Years *t* and *t−1* always use the same basis. If depreciation alone
  exists for only one of the two years, the D&A basis is used for both.
- **The basis is part of the result.** It is recorded in provenance and shown in the details,
  diagnostics and JSON views. A score on the D&A basis is never presented as equivalent to the
  canonical model, and the guide says it may differ from published M-Scores.
- **Period expense only.** The depreciation input is the year's expense, never accumulated
  depreciation. PP&E is net, as in the original model's data item.
- **Depreciation alone requires an approved mapping.** Until 3.5.1's evidence approves one, every
  run uses the D&A basis.

**Presentation**

- Shows the numeric score and a flag when M > −1.78, worded as "above the threshold associated
  with manipulators in the original study."
- Names the DEPI basis and the TATA income basis whenever either is not the canonical one.
- Never labels a company a manipulator, and never converts the score to a stated probability.

## 4. Cash-Flow Valuation Multiples

| Metric | Definition | `not_applicable` when |
| :--- | :--- | :--- |
| EV / EBITDA | EV (SD §6) ÷ EBITDA (SD §5) | EBITDA ≤ 0 or EV ≤ 0 |
| FCF yield | SD §8, in percent | market cap ≤ 0 |

- A negative FCF yield is reported with a sign note. It is meaningful, so it is not
  `not_applicable`.
- The guide explains that FCF yield is an equity-level measure: FCF is after interest, so it is
  divided by equity value rather than EV.
- Financial issuers: `not_applicable`.
- EV/EBITDA is not comparable between US GAAP and IFRS filers with material leases (SD §6, lease
  liabilities). The guide says so.

## 5. Greenblatt Magic Formula

The analyzer computes one ticker's two metrics. Ranking is the ranked refresh view (SD §9), never
part of a single run.

| Metric | Definition | `not_applicable` when |
| :--- | :--- | :--- |
| Return on capital | EBIT (SD §5) ÷ invested capital (SD §7) | EBIT ≤ 0 or IC ≤ 0 |
| Earnings yield | EBIT ÷ EV (SD §6) | EBIT ≤ 0 or EV ≤ 0 |

- **Industry class:** financial issuers and utilities are `not_applicable` (SD §1).
- **Ranking:** the ranked refresh view ranks both metrics higher-is-better. Members whose metrics
  are not `ok` are excluded with their reason codes. The view shows each metric's rank and
  percentile, the rank sum and the final position.

## 6. Interest Coverage

- **Primary metric:** EBIT (SD §5) ÷ gross interest expense.
- **Secondary metric:** EBITDA (SD §5) ÷ gross interest expense. It has no band.
- **Gross interest only:** a filer that reports only net interest is `unavailable`. A net figure
  is never substituted for gross.
- **Financial issuers:** `not_applicable`.

**Outcomes and bands**

| Condition | Coverage `MetricResult` | Band |
| :--- | :--- | :--- |
| Interest expense zero or not reported, and total debt (SD §6) is zero | `not_applicable`, reason: no interest expense | No material interest expense |
| Interest expense not reported while total debt > 0 | `unavailable` | — |
| Coverage ≥ 8× | `ok` | Comfortable |
| 4× ≤ coverage < 8× | `ok` | Adequate |
| 1.5× ≤ coverage < 4× | `ok` | Thin |
| Coverage < 1.5×, including negative EBIT (shown with a sign note) | `ok` | Distressed |

- The band thresholds are named, documented defaults.
- The guide states plainly that the bands are heuristics, not credit ratings.

## 7. ROIC and Incremental ROIC

**Tax rate**

In this section *r* is the tax rate, to keep *t* for the fiscal year.

- When pretax income > 0: *r* = income tax expense ÷ pretax income, clamped to [0, 0.50].
- Otherwise *r* = 0.

Each fiscal year uses its own rate.

- **Why a clamp:** the rate should reflect the recurring tax burden on operating profit. A
  reported rate above 50% or below zero almost always comes from a one-off item (a valuation
  allowance, a repatriation charge, a non-deductible impairment, a settlement), and applying it to
  EBIT would distort NOPAT far more than the clamp does.
- **Why 50%:** it sits above every statutory corporate rate the covered filers face, so an
  ordinary rate is never clamped. It is a named, documented default.
- **Nothing is hidden:** the result keeps the reported (unclamped) rate beside the rate used, and
  a clamped year carries a diagnostic.
- **No tax shield, on purpose:** when pretax income is zero or negative, *r* = 0, so a loss-making
  year's NOPAT equals its EBIT. Crediting a tax benefit would assume the loss can be used. This is
  a conservative convention, and the guide says so.
- Missing income tax expense or pretax income makes ROIC `unavailable`. No rate is assumed.

**Trailing ROIC**

- NOPAT = EBIT (SD §5) × (1 − *r*).
- ROIC = NOPAT ÷ average(ICₜ, ICₜ₋₁), with IC from SD §7.
- If average IC ≤ 0, ROIC is `not_applicable`.

**Incremental ROIC (three-year span)**

- Incremental ROIC = (NOPATₜ − NOPATₜ₋₃) ÷ (ICₜ − ICₜ₋₃).
- **Requirements,** checked in this order:
  1. four annual filings (years *t* to *t−3*);
  2. baseline capital is positive: ICₜ₋₃ > 0;
  3. capital grew: ICₜ − ICₜ₋₃ > 0;
  4. reinvestment is material: ICₜ − ICₜ₋₃ ≥ 10% of ICₜ₋₃.
- If a requirement fails, incremental ROIC is `unavailable` with the first failing reason
  (insufficient history, baseline capital not positive, capital base shrank, or reinvestment too
  small). Trailing ROIC is still reported.
- The three-year span and the 10% reinvestment floor are named, documented defaults.

**Financial issuers:** `not_applicable`.

**Relationship to Magic Formula (for the guide)**

ROIC and Magic Formula's return on capital share the invested-capital definition (SD §7) on
purpose, so the two stay comparable. ROIC adds three things the Magic Formula figure lacks:

- it is after tax;
- it uses average rather than ending capital;
- through incremental ROIC, it shows whether new capital is still earning an attractive return,
  which Magic Formula's single-period figure cannot answer.

**Limitation (documented, not handled):** non-recurring items are not adjusted out; reported EBIT
is used as-is.
