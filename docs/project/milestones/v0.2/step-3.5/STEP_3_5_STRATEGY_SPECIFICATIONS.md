# Step 3.5 — Strategy Specifications

Owns each Step 3.5 strategy's formulas, outcomes and edge cases. Shared metrics (market cap,
EBIT, EBITDA, EV, invested capital, FCF), applicability, outcomes and ranking are defined once in
[Shared definitions](STEP_3_5_SHARED_DEFINITIONS.md) and referenced here as "SD §n". Scope,
sequencing and status live in the [contract](STEP_3_5_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status).

When a strategy is implemented, its formula semantics move into `docs/user/FINANCE_MATH.md`,
which then becomes their authority.

**Conventions**

- *t* is the selected fiscal year and *t−1* is the prior fiscal year.
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

The nine tests from Piotroski (2000). ROA uses beginning-of-year total assets.

| Group | A test passes when |
| :--- | :--- |
| Profitability | ROA > 0; CFO > 0; ΔROA > 0; CFO > net income |
| Leverage and liquidity | Δ(long-term debt ÷ average total assets) < 0, or long-term debt is zero in both years; Δcurrent ratio > 0; split-adjusted shares outstanding did not increase |
| Efficiency | Δgross margin > 0; Δasset turnover (sales ÷ beginning total assets) > 0 |

- **Test outcomes:** each test is pass, fail or unavailable, with provenance. A test is
  unavailable when an input is missing or a denominator is zero, and an unavailable test is never
  scored as a fail.
- **Score:**

  | Tests available | Score `MetricResult` | Result completeness |
  | :--- | :--- | :--- |
  | 9 | `ok`, 0–9 | complete |
  | 6 to 8 | `ok`, the number passed, shown as "*x* of *n*" | partial |
  | Fewer than 6 | `unavailable` | — |

- **Ranking:** a partial score never enters a ranking.
- **Financial issuers:** applicable with a warning (SD §1). Their gross-margin and current-ratio
  tests are typically unavailable.
- **Documented deviation:** the dilution test uses the change in split-adjusted share count, not
  the original issuance-proceeds test. Proceeds include option exercises, which would fail nearly
  every issuer.

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

The eight-variable model from Beneish (1999):

M = −4.84 + 0.920·DSRI + 0.528·GMI + 0.404·AQI + 0.892·SGI + 0.115·DEPI − 0.172·SGAI +
4.679·TATA − 0.327·LVGI

| Index | Definition |
| :--- | :--- |
| DSRI | (receivables ÷ sales)ₜ ÷ (receivables ÷ sales)ₜ₋₁ |
| GMI | gross marginₜ₋₁ ÷ gross marginₜ |
| AQI | [1 − (current assets + net PP&E + long-term investments) ÷ total assets]ₜ ÷ the same for *t−1* |
| SGI | salesₜ ÷ salesₜ₋₁ |
| DEPI | [depreciation ÷ (depreciation + net PP&E)]ₜ₋₁ ÷ the same for *t* |
| SGAI | (SG&A ÷ sales)ₜ ÷ (SG&A ÷ sales)ₜ₋₁ |
| LVGI | [(current liabilities + long-term debt) ÷ total assets]ₜ ÷ the same for *t−1* |
| TATA | (income from continuing operations − CFO)ₜ ÷ total assetsₜ |

**Edge cases**

- Any index that cannot be computed makes the whole score `unavailable`. No index defaults to 1.0.
- Long-term investments follow the absent-component convention (SD §3).
- Financial issuers: `not_applicable`.

**Presentation**

- Shows the numeric score and a flag when M > −1.78, worded as "above the threshold associated
  with manipulators in the original study."
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

- When pretax income > 0: *t* = income tax expense ÷ pretax income, clamped to [0, 0.50].
- Otherwise *t* = 0, and no tax shield is credited.

Each fiscal year uses its own rate.

**Trailing ROIC**

- NOPAT = EBIT (SD §5) × (1 − *t*).
- ROIC = NOPAT ÷ average(ICₜ, ICₜ₋₁), with IC from SD §7.
- If average IC ≤ 0, ROIC is `not_applicable`.

**Incremental ROIC (three-year span)**

- Incremental ROIC = (NOPATₜ − NOPATₜ₋₃) ÷ (ICₜ − ICₜ₋₃).
- **Requirements:** four annual filings; ICₜ − ICₜ₋₃ > 0; and ICₜ − ICₜ₋₃ ≥ 10% of ICₜ₋₃.
- If any requirement fails, incremental ROIC is `unavailable` with the specific reason
  (insufficient history, capital base shrank, or reinvestment too small). Trailing ROIC is still
  reported.
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
