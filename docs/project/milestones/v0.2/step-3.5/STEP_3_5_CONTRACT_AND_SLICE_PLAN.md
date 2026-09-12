# Step 3.5: Deterministic Quantitative Screening Strategies

**Mandatory implementation entry gate:** The [Existing Strategy Correctness Plan](../existing-strategy-correctness/EXISTING_STRATEGY_CORRECTNESS_PLAN.md) requires ESC-C acceptance before database readiness resumes and explicit ESC-D renewed acceptance after readiness, workspace and P2-Profiles changes, on the actual Step 3.5 starting revision. No new strategy implementation may begin with unresolved known correctness defects in Graham Number, Graham Growth, Momentum or FCF/Earnings Growth. Earlier approval of this plan does not waive that requirement.

**Milestone Context:** v0.2 – Reliability, Observability, Strategy Generalization, Data Persistence & Investor Workflow  
**Placement:** After Step 3.4 (Local Research Workspace & Analysis Run Library) and before Step 3.6 (Light Mode Support). Required before Milestone v0.2.5 Real-User Validation Checkpoint.  
**Dependencies:**  
- Step 3.3 (Data Quality & Cache Invalidation Pipeline) – complete and approved.  
- Step 3.4 (Local Research Workspace & Analysis Run Library) – complete so that new strategies can be selected on watchlists, produce durable Analysis Runs, and be inspected via existing run-browsing commands.  
- Existing financial-fact / InputResolver / provenance / point-in-time contracts established in Steps 2.3–2.4 and hardened in Step 2.5A.  

**Primary Objective:**  
Add a bounded suite of classic, independently typed, fully deterministic quantitative screening strategies that operate exclusively on free/public data (SEC EDGAR XBRL primary, `yfinance` fallback). The strategies expand the investor toolkit with quality, solvency, earnings-integrity, valuation-multiple, and capital-efficiency screens while preserving every core project principle: pure-Python arithmetic, method explicitness, progressive disclosure, provenance, fail-closed behaviour, and heterogeneous strategy independence.

---

## 1. Strategy Selection & Justification

Five strategies are selected. The set is deliberately small so that each can receive proper data-mapping, edge-case handling, documentation, Golden-Suite coverage, and investor-facing presentation before Light Mode validation begins. All five are mathematically well-specified in the public literature, complementary to the existing Momentum / Graham / FCF-Growth suite, and feasible with the project’s current data boundaries.

| # | Strategy | Primary Investor Question | Why Selected |
|---|----------|---------------------------|--------------|
| 1 | Piotroski F-Score | Does the company show improving fundamental quality on nine binary tests? | Highest signal-to-noise classic quality screen; purely binary and therefore easy to present and test; works well as a watchlist filter. |
| 2 | Altman Z-Score | What is the statistical distance from financial distress for a non-financial firm? | Complements Graham’s margin-of-safety thinking with an explicit solvency model; clear Safe / Grey / Distress zones map cleanly to progressive disclosure. |
| 3 | Beneish M-Score | Is there elevated probability of earnings manipulation? | Unique risk-detection capability absent from the current library; forces rigorous multi-year accrual and receivables handling. |
| 4 | Unlevered Valuation Multiples (EV/EBITDA + FCF Yield) | How expensive is the operating business relative to cash generation? | Natural, low-duplication extension of the Step 2.4 FCF definition; provides the two most widely used cash-flow valuation multiples. |
| 5 | Greenblatt Magic Formula Ranking | Which names simultaneously rank high on capital efficiency and earnings yield? | Introduces deterministic cross-sectional ranking over a user- or watchlist-defined universe—the first true batch/ranking capability in the product. |

**Explicitly deferred (not part of this step):**  
ROIC / incremental ROIC, P/E or PEG screens, interest-coverage ratios, gross-margin stability, and any composite “super-score.” These remain candidates for Milestone v0.3 Step 4 once the five selected models have proven their data and presentation contracts under real-user validation.

---

## 2. Strategy-Specific Technical & Conceptual Notes

### 2.1 Piotroski F-Score (`src/analysis/strategy/piotroski.py`)
- **Scope:** Full original 9-point binary model (4 profitability + 3 leverage/liquidity + 2 efficiency).  
- **Key calculations:** Positive NI, positive CFO, ΔROA > 0, CFO > NI, ΔLong-term debt ratio < 0, ΔCurrent ratio > 0, no share dilution, ΔGross margin > 0, ΔAsset turnover > 0.  
- **Data notes:** Requires clean year-over-year alignment of the same fiscal periods; share-count handling must distinguish issuance from splits/buybacks; long-term debt classification can be noisy for financials (strategy remains usable but should surface a sector applicability warning).  
- **Edge cases:** Missing prior-year line item → that binary test is scored 0 and a warning is emitted; zero total assets or zero current liabilities → test marked unavailable rather than division-by-zero.  
- **Output:** Integer score 0–9 plus the nine component booleans, each carrying provenance.

### 2.2 Altman Z-Score (`src/analysis/strategy/altman_z.py`)
- **Scope:** Classic 1968 five-factor model for non-financial public firms.  
- **Formula:**  
  \( Z = 1.2X_1 + 1.4X_2 + 3.3X_3 + 0.6X_4 + 0.999X_5 \)  
  where \( X_1 = \) Working Capital / Total Assets, \( X_2 = \) Retained Earnings / Total Assets, \( X_3 = \) EBIT / Total Assets, \( X_4 = \) Market Value of Equity / Total Liabilities, \( X_5 = \) Sales / Total Assets.  
- **Classification:** Safe Zone (Z > 2.99), Grey Zone (1.81 ≤ Z ≤ 2.99), Distress Zone (Z < 1.81).  
- **Applicability gate:** Hard-fail or return an explicit “inapplicable – financial issuer” result for banks, insurers, and REITs; do not silently produce a number.  
- **Edge cases:** Negative equity or zero total liabilities → component marked unavailable; market-cap must be point-in-time consistent with the balance-sheet date.

### 2.3 Beneish M-Score (`src/analysis/strategy/beneish_m.py`)
- **Scope:** Eight-variable model detecting aggressive accruals / revenue inflation.  
- **Variables:** DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA.  
- **Cutoff:** M-Score > −1.78 flags elevated manipulation probability (presented as a probability flag + numeric score, never a binary “manipulator” label).  
- **Data intensity:** Most demanding of the five; requires consistent multi-year receivables, gross margin, depreciation, SG&A, and accrual series.  
- **Edge cases:** Missing depreciation or SG&A → those indices treated as 1.0 (neutral) with a warning, or the whole score marked unavailable if too many components are missing; restated financials must follow the project’s deterministic amendment-selection rules.

### 2.4 Unlevered Valuation Multiples (`src/analysis/strategy/valuation_multiples.py`)
- **Scope:** Two closely related methods under one strategy package:  
  - Enterprise Value / EBITDA  
  - Free Cash Flow Yield (FCF / Market Cap or FCF / Enterprise Value – both reported, primary is FCF / Market Cap for consistency with common screening practice).  
- **FCF definition:** Strict reuse of the Step 2.4 canonical definition `FCF = Operating Cash Flow − CapEx` (CapEx sign-normalized). No competing FCF calculation is introduced.  
- **EV construction:** Market Cap + Total Debt − Cash & Cash Equivalents, with explicit reconciliation of lease liabilities and short-term investments when the balance-sheet disclosures permit.  
- **Edge cases:** Negative EBITDA or negative FCF → multiples reported with clear sign warnings; missing CapEx → FCF Yield marked unavailable rather than substituting zero.

### 2.5 Greenblatt Magic Formula Ranking (`src/analysis/strategy/magic_formula.py`)
- **Scope:** Dual-factor ranking:  
  - Return on Capital ≈ EBIT / (Net Working Capital + Net Fixed Assets)  
  - Earnings Yield ≈ EBIT / Enterprise Value  
- **Aggregation:** Deterministic percentile ranks within a caller-supplied universe (watchlist or explicit ticker list). Final rank is the average of the two percentile ranks (lower number = more attractive).  
- **Universe policy:** Ranking is never performed against an implicit market-wide universe; the comparison set must be explicit and point-in-time consistent. Missing data for a name removes it from the ranking rather than imputing values.  
- **Edge cases:** Negative EBIT or negative invested capital → that name is excluded from the ranking with a diagnostic; very small denominators are guarded.

---

## 3. Key Requirements & Constraints

1. **Data sources only:** SEC EDGAR XBRL (10-K / 10-Q and reviewed foreign annual forms) primary; `yfinance` strictly as fallback with full provenance tagging. No paid fundamentals APIs.  
2. **Deterministic architecture:** Pure numeric or binary outputs; zero stochasticity or LLM involvement in the arithmetic.  
3. **Architectural fit:** Each strategy is a first-class `BaseAnalyzer` implementation under `src/analysis/strategy/`. No new plugin registry or generic result supertype.  
4. **Contracts reused:** InputResolver, financial-fact models, point-in-time `as_of`, provenance, Analysis Run persistence, progressive disclosure (concise / details / diagnostics / JSON).  
5. **Fail-closed & explicit applicability:** Missing critical inputs or sector mismatch produce structured unavailable / inapplicable results, never silent zeros or invented values.  
6. **Documentation:** Every strategy receives its own user-facing guide under `docs/user/strategies/` following the established Graham / FCF-Growth template (what it does, formula, assumptions, data sources, limitations, why other calculators may disagree).

---

## 4. Component Breakdown & Sub-Tasks

### 4.1 Shared Data-Mapping Extensions
- Extend the existing SEC EDGAR concept dictionary with the additional line items required by the five strategies (long-term debt components, working capital pieces, depreciation, SG&A, receivables, etc.).  
- Define deterministic yfinance fallback mappings with provenance tags.  
- Sector / SIC / GICS applicability helpers for Altman and any future sector-sensitive screens.

### 4.2 Core Strategy Implementations
- One module per strategy (or tightly coupled method group for valuation multiples).  
- Full type annotations, Pydantic result models, and explicit component-level provenance.

### 4.3 CLI & Presentation
- Individual commands following the established pattern:  
  `uv run financial-agents piotroski TICKER`, `altman-z`, `beneish-m`, `valuation-multiples`, `magic-formula`.  
- Optional multi-strategy and ranking-batch flags that write durable Analysis Runs.  
- Presenters that obey progressive disclosure and the coherent visual grammar already used by Graham and FCF-Growth.

### 4.4 Testing & Quality
- Unit tests with mocked EDGAR and yfinance fixtures covering the edge cases listed above.  
- Golden-Suite extension so that the new strategies participate in the deterministic benchmark before Step 3.6 close-out.  
- Coverage target consistent with project policy (≥ 85 % aggregate; meaningful branch coverage on new financial code).  
- Full repository quality gate (ruff, mypy --strict, pytest) must pass.

### 4.5 Documentation
- Five new strategy guides + updates to `docs/user/FINANCE_MATH.md` and `docs/user/GLOSSARY.md`.  
- Brief mention in the root README and the Analysis Strategy Guides index.

---

## 5. Implementation Sequence
Step 3.4 (Workspace) complete
│
▼
┌──────────────────────────────────────────────────────┐
│ 3.5.1 Shared concept-dictionary & applicability      │
│       helpers + yfinance fallback mappings           │
└──────────────────────────┬───────────────────────────┘
│
▼
┌──────────────────────────────────────────────────────┐
│ 3.5.2 Core analyzers (Piotroski → Altman → Beneish → │
│       Valuation Multiples → Magic Formula)           │
└──────────────────────────┬───────────────────────────┘
│
▼
┌──────────────────────────────────────────────────────┐
│ 3.5.3 CLI commands, presenters, Analysis Run wiring  │
└──────────────────────────┬───────────────────────────┘
│
▼
┌──────────────────────────────────────────────────────┐
│ 3.5.4 Tests, Golden-Suite extension, documentation,  │
│       full quality gate                              │
└──────────────────────────────────────────────────────┘


---

## 6. Exit Criteria

- All five strategies produce reproducible, provenance-tagged results for a representative set of non-financial issuers (and correctly signal inapplicability for financials where required).  
- Each strategy has a complete user-facing guide, Finance Math entries, and Glossary terms.  
- Unit + Golden-Suite coverage is green; repository quality gate passes.  
- Strategies are selectable on watchlists and appear in the Light Mode investor workflow documented for Step 3.6.  
- No paid data sources, no LLM arithmetic, no silent imputation of missing financial values.

---

## 7. Relationship to Later Work

Milestone v0.3 Step 4 remains the home for residual multiples (P/CF, additional ROIC variants, estimate-revision screens, etc.), technical-indicator expansion, and any future composite or universe-level ranking methods that require additional product-policy gates. The five strategies introduced here are considered stable exemplars once Step 3.5 is closed; they are not reopened for redesign in v0.3.

---

*This plan is written so that, once the corresponding Master Plan revision is approved, it can be committed into the project documentation set with only mechanical path and status updates.*