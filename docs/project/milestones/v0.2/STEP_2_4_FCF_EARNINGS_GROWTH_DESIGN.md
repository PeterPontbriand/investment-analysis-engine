# Step 2.4 Design: Free Cash Flow & Earnings Growth Analysis

**Status:** Initial design draft; product-policy review required before implementation beyond reconnaissance<br/>
**Prepared:** 2026-08-25<br/>
**Scope:** Milestone v0.2, Step 2.4 only<br/>
**Entry condition:** Step 2.3 is complete and approved; Step 2.4 production work begins only after the Step 2.3 closeout PR is merged or an equivalent explicit human branch boundary is established<br/>
**Next step:** Step 2.5 Golden-Test Suite & Strategy Evaluation

---

## 1. Purpose and authority

Step 2.4 adds a third materially different deterministic investor analysis before the Golden Suite.

The immediate product motivation is concrete: a prospective Real-User has expressed interest in having Financial Data Agents handle **“FCF (free cash flow) and earnings growth.”** The architectural motivation is equally useful: Step 2.3 just established provider-neutral financial-fact resolution, provenance, strict point-in-time behavior, deterministic fixtures, strategy-specific investor presentation, and a unified direct-analysis CLI. A cash-flow/growth strategy is a good opportunity to prove that those foundations generalize beyond Graham before they are frozen into the Golden Suite.

This document deliberately does **not** treat the phrase “FCF and earnings growth” as authority to invent a broad investing methodology. The initial implementation target is a transparent historical screen using reported cash-flow and earnings data.

Document precedence for Step 2.4 should be:

1. `docs/project/MASTER_PLAN.md` — milestone intent and ordering;
2. `docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md` — active milestone scope, gates, and sequencing;
3. this document — Step 2.4 financial/data/CLI/presentation contract;
4. `docs/user/FINANCE_MATH.md` — formula and financial semantics;
5. `docs/project/ARCHITECTURE.md` — component boundaries;
6. `docs/project/DISCOVERY_WORKBOOK.md` — rationale.

If implementation evidence conflicts with this design, stop and surface the conflict rather than silently widening scope.

---

## 2. Product-policy checkpoint before coding

The phrase “FCF and earnings growth” is enough to select this roadmap direction but not enough to lock every investor-facing metric.

Before implementation proceeds beyond repository/provider reconnaissance, obtain a human decision on these questions:

1. Does the prospective Real-User primarily mean **historical actuals**, **forward/analyst estimates**, or both?
2. Is the desired output mainly:
   - current FCF plus earnings growth;
   - FCF growth plus earnings growth;
   - P/FCF / FCF yield plus growth;
   - or a particular screening rule?
3. What historical horizon is most useful: 3 years, 5 years, or another period?
4. Does the user expect a pass/fail threshold or ranking, or simply transparent metrics/trends?
5. Is TTM analysis important for the first version, or are completed fiscal years sufficient?

### Baseline if no additional detail is available

Until those questions are answered, the approved baseline is:

- completed fiscal-year actuals;
- latest annual free cash flow;
- latest annual diluted EPS;
- year-over-year FCF change where mathematically meaningful;
- year-over-year EPS change where mathematically meaningful;
- **3-year FCF CAGR**, requiring four compatible completed fiscal-year observations;
- **3-year diluted-EPS CAGR**, requiring four compatible completed fiscal-year observations;
- plain-language trend comparison;
- no forecast/consensus growth;
- no P/FCF or FCF yield in the required core;
- no DCF;
- no composite score or investment recommendation.

The baseline is intentionally useful without requiring forecast assumptions or arbitrary thresholds.

---

## 3. Strategy identity and meaning

Proposed stable strategy identifier:

```text
fcf_earnings_growth
```

Proposed direct CLI command:

```text
financial-agents fcf-growth TICKER [options]
```

Investor-facing name:

```text
Free Cash Flow & Earnings Growth
```

This strategy is a **historical fundamental screen / trend analysis**. It is not:

- an intrinsic-value model;
- a discounted-cash-flow model;
- a replacement for P/FCF valuation multiples;
- a complete quality-of-business assessment;
- a complete “Druckenmiller” or other named-investor methodology;
- an investment recommendation.

---

## 4. Canonical financial semantics

### 4.1 Free cash flow

For the initial project implementation:

```text
free_cash_flow = operating_cash_flow - capital_expenditures
```

Where:

- `operating_cash_flow` means net cash provided by operating activities for the selected reporting period;
- `capital_expenditures` is normalized by the provider/resolution layer to a **positive expenditure amount** before subtraction;
- the derived FCF retains complete component lineage.

Example:

```text
Operating cash flow:       1,000
Reported CapEx cash flow:   -250
Normalized expenditure:      250
Free cash flow:              750
```

FCF is a project-defined non-GAAP analytical measure. Provider/company presentations may define similarly named measures differently. The output must therefore show the project's definition in details/JSON and must not silently consume a provider's precomputed “free cash flow” field unless its definition is proven compatible.

### 4.2 Earnings basis

The baseline earnings measure is **completed fiscal-year diluted EPS**.

Rules:

- preserve basic/diluted basis explicitly;
- do not mix annual EPS observations with TTM observations in one historical growth series;
- do not mix incompatible share classes;
- preserve split/restatement evidence where available;
- use only observations knowable by the requested `as_of`.

A later explicit variation may support another earnings basis, but it must be named and cannot silently replace diluted annual EPS.

### 4.3 Period alignment

An annual FCF observation is valid only when operating cash flow and capital expenditures refer to the same compatible fiscal period and currency.

Do not combine:

- year-to-date CFO with full-year CapEx;
- different fiscal-year ends;
- different currencies without an approved conversion policy;
- values from incompatible consolidated scopes;
- facts not yet published/available by the requested `as_of`.

If compatible component facts cannot be established, that FCF period is unavailable.

---

## 5. Growth semantics

### 5.1 Year-over-year change

For a metric `x`:

```text
yoy_growth_percent = (current - prior) / prior * 100
```

Percentage growth is meaningful only when the project policy permits the prior-period denominator.

Baseline rule:

- if `prior > 0`, percentage growth may be calculated;
- if `prior <= 0`, percentage growth is `None` with a structured reason;
- retain the raw current/prior values so the investor can still see the economic change.

Do not emit infinity, an enormous pseudo-growth percentage from a zero denominator, or silently reinterpret a loss-to-profit transition as ordinary percentage growth.

### 5.2 CAGR

For a positive metric observed `N` years apart:

```text
cagr_percent = ((ending / beginning) ** (1 / N) - 1) * 100
```

For the default 3-year CAGR, four compatible completed fiscal-year observations are required: beginning at fiscal year `t-3` and ending at fiscal year `t`.

Baseline CAGR rules:

- beginning and ending values must both be strictly positive;
- periods must represent the requested year span without silent gaps;
- negative/zero endpoints, sign changes, or incompatible periods make CAGR unavailable with a structured reason;
- raw history remains visible;
- no clipping, flooring, absolute-value transformation, or sign erasure.

The same mathematical policy applies independently to FCF CAGR and diluted-EPS CAGR.

### 5.3 Trend interpretation

The deterministic layer may provide a small typed comparison only when the required growth metrics are valid:

- `both_growing`;
- `fcf_growing_earnings_not`;
- `earnings_growing_fcf_not`;
- `neither_growing`;
- `insufficient_or_nonmeaningful_growth`.

“Growing” means the selected valid growth metric is greater than zero. This is a descriptive classification, not a recommendation or quality score.

Do not add weighted scoring or threshold optimization in Step 2.4.

---

## 6. Typed result contract

Prefer a strategy-specific typed result rather than adding fields to Graham or Momentum result models.

Illustrative result shape:

```text
FCFEarningsGrowthResult
    strategy = fcf_earnings_growth
    status
    ticker / subject
    requested_as_of
    growth_years
    latest_period
    latest_operating_cash_flow
    latest_capital_expenditures
    latest_free_cash_flow
    latest_diluted_eps
    fcf_yoy_growth_percent | None
    eps_yoy_growth_percent | None
    fcf_cagr_percent | None
    eps_cagr_percent | None
    trend_classification
    resolved_inputs / derived lineage
    warnings
```

Exact Python names should follow repository conventions after reconnaissance.

### Status behavior

Use existing project status vocabulary where it fits. Do not invent a new broad error hierarchy without need.

At minimum distinguish:

- `ok` — the analysis produced the required latest-period values; some growth submetrics may still be unavailable for mathematically explicit reasons;
- `input_unavailable` — required financial facts or history could not be resolved;
- `invalid_input` — invalid requested horizon/configuration or incompatible explicit input;
- `provider_error` — provider failure distinct from absent evidence.

Negative FCF or negative EPS is not automatically a software error. It is economically meaningful data. Percentage-growth/CAGR submetrics may become unavailable under the rules above while the raw series and latest values remain reportable.

---

## 7. Data and resolution boundary

### 7.1 Reuse Step 2.3 foundations

Step 2.4 should reuse the existing provider-neutral financial-fact, cache, resolver, provenance, fixture, and presentation patterns established in Step 2.3.

Do **not** create:

- a parallel FCF-only provider framework;
- a new strategy registry/plugin system;
- a second provenance model;
- a second cache hierarchy;
- a second CLI presentation framework.

The new strategy is allowed to prove that a current Step 2.3 name is too narrow, but a rename/generalization must be justified by concrete incompatibility rather than aesthetics.

### 7.2 Minimum new financial facts

The baseline requires provider-neutral support for:

- operating cash flow / net cash provided by operating activities;
- capital expenditures;
- completed annual diluted EPS history.

EPS should reuse the existing annual EPS capability where semantically compatible.

Likely new semantic fields:

```text
OPERATING_CASH_FLOW
CAPITAL_EXPENDITURES
```

Do not add revenue, market capitalization, debt, enterprise value, analyst estimates, or other fields unless the approved product-policy checkpoint requires them.

### 7.3 Derived FCF lineage

FCF is derived per fiscal period.

Each derived FCF observation must retain lineage sufficient to reconstruct:

```text
FCF
├── operating cash flow
└── normalized capital expenditures
```

Lineage must preserve:

- source/provider;
- exact provider concepts/fields;
- fiscal period start/end;
- filing/publication/availability timestamp;
- units/currency;
- retrieved/resolved timestamps;
- capex sign normalization;
- any duplicate/restatement selection rule.

### 7.4 `as_of` policy

Step 2.3's no-look-ahead rule remains authoritative.

For every annual fact used:

- fiscal period end alone is insufficient;
- the fact must be published/filed/available on or before requested `as_of`;
- later restatements are not eligible for an earlier historical analysis unless they were already available by that boundary;
- current snapshots may not masquerade as historical evidence.

The resolver captures the analysis boundary once per deterministic assembly operation where the existing clock contract requires a single coherent execution time.

---

## 8. Provider evidence gate

Begin production integration with evidence, not field-name guessing.

SEC EDGAR is the natural first candidate because Step 2.3 already established SEC financial-fact infrastructure, but no cash-flow concept mapping is approved merely by this document.

Before accepting a production mapping, record evidence for:

| Capability | Evidence required |
| :--- | :--- |
| Operating cash flow | Exact SEC/provider concept(s), cash-flow-statement semantics, units, annual-period behavior, amended/restated filing behavior, availability timestamp |
| Capital expenditures | Exact concept(s), what expenditures are included/excluded, reported sign convention, units, period behavior, availability timestamp |
| Annual diluted EPS | Confirm reuse of the Step 2.3 evidence-approved annual diluted-EPS path or document any necessary difference |
| Period alignment | Proof that CFO and CapEx can be paired for the same completed fiscal period without mixing cumulative/interim/full-year values |
| Historical `as_of` | Proof that filing/availability time prevents look-ahead |
| Ticker/security identity | Preserve the Step 2.3 provider-backed subject-validation principle |

If SEC filings expose multiple plausible CapEx concepts, do not guess. Define and test a conservative selection rule only after evidence review.

---

## 9. Deterministic fixtures

Add deterministic fixture evidence representing at least four compatible completed fiscal years so the default 3-year CAGR can be tested.

Fixture coverage should include:

- four annual operating-cash-flow facts;
- four annual CapEx facts;
- four annual diluted-EPS facts;
- compatible currencies/units;
- filing/availability timestamps;
- capex reported with provider-native sign and normalized expenditure lineage;
- one duplicate/restatement scenario;
- one future-published fact excluded by `as_of`;
- one missing CapEx period;
- one mismatched-period case;
- one zero/negative prior value causing percentage growth to be unavailable;
- one negative FCF or EPS case;
- one provider-error path.

No fixture execution may silently fall back to live network data.

---

## 10. Pure calculation responsibilities

Keep deterministic arithmetic independent from data access.

Candidate pure functions:

```text
compute_free_cash_flow(operating_cash_flow, capital_expenditures)
compute_growth_percent(current, prior)
compute_cagr(beginning, ending, years)
classify_fcf_earnings_growth(...)
```

The exact public surface may be smaller if a cleaner existing pattern is available.

Pure functions must:

- reject non-finite numeric inputs;
- never perform provider/cache/filesystem/clock I/O;
- never infer periods;
- never invent missing values;
- return explicit unavailable/invalid semantics rather than NaN or infinity.

CapEx sign normalization belongs at the provider/resolution boundary, not hidden inside a generic subtraction formula, so the pure FCF calculator receives a positive expenditure amount.

---

## 11. Direct CLI contract

Proposed command:

```text
financial-agents fcf-growth TICKER [options]
```

Initial options:

```text
--growth-years INTEGER      # default 3
--as-of DATE_OR_TIMESTAMP
--data-provider PROVIDER_ID
--no-cache
--details
--diagnostics
--json
```

Rules:

- positional ticker remains the preferred identity style established in Step 2.3;
- `--growth-years 3` requires four completed compatible fiscal-year observations;
- unsupported horizons or insufficient history fail truthfully;
- do not add awkward unperiodized repeated numeric override flags merely to mimic Graham;
- if series overrides are later needed, design an explicit period-tagged representation rather than accepting ambiguous ordered floats;
- normal failure output must not expose provider-library implementation details or framework tracebacks.

---

## 12. Investor-facing presentation

Reuse the Step 2.3 progressive-disclosure grammar with a strategy-specific presenter.

### Default concise view

Recommended information order:

1. ticker + `Free Cash Flow & Earnings Growth`;
2. latest completed fiscal period;
3. latest free cash flow;
4. diluted-EPS growth over the selected horizon;
5. FCF growth over the selected horizon;
6. short deterministic trend comparison;
7. high-level source/freshness line;
8. material warnings / unavailable-growth explanation;
9. short limitation.

Example shape only:

```text
KO — Free Cash Flow & Earnings Growth

Free cash flow (FY2025):        $X.XXB
Diluted EPS 3-year CAGR:        +Y.Y%
Free cash flow 3-year CAGR:     +Z.Z%
Trend: Both free cash flow and diluted EPS increased over the measured period.

Source: SEC EDGAR annual filings
Note: FCF = operating cash flow - capital expenditures.
```

Do not hard-code this exact formatting before presenter tests; preserve the common visual grammar rather than exact whitespace.

### `--details`

Show:

- annual CFO, normalized CapEx, derived FCF, and diluted-EPS series;
- fiscal periods;
- provider concepts/fields;
- availability dates;
- capex normalization;
- derived lineage;
- growth endpoints and year count;
- warnings.

### `--diagnostics`

Show software resolution behavior only:

- cache behavior;
- provider attempts;
- selection/rejection reasons;
- derivation steps;
- unavailable/error classification.

Do not confuse cache state with financial source provenance.

### `--json`

Use the existing machine-readable presentation conventions and explicit schema versioning policy. Unavailable growth metrics are JSON `null` with a structured reason, never `NaN`.

---

## 13. Testing requirements

At minimum test:

1. exact FCF arithmetic;
2. capex sign normalization outside the pure calculator;
3. exact YoY growth;
4. exact 3-year CAGR from four annual observations;
5. zero/negative prior denominator → percentage growth unavailable;
6. zero/negative CAGR endpoint → CAGR unavailable;
7. negative latest FCF remains reportable;
8. incompatible periods are rejected;
9. incompatible units/currencies are rejected;
10. missing CapEx makes the affected FCF period unavailable;
11. strict `as_of` excludes later filings/restatements;
12. eligible duplicate/restatement selection is deterministic;
13. annual diluted EPS reuse preserves basis/provenance;
14. cache/provider/derived lineage remains truthful;
15. insufficient history is explicit;
16. concise/details/diagnostics/JSON presentation semantics;
17. invalid/missing ticker and provider errors produce one clean user-facing failure surface;
18. no live provider or LLM calls in automated tests.

After implementation, run the complete repository quality gate required by the milestone plan.

---

## 14. Proposed implementation slices

### Slice A — reconnaissance and product-policy lock

Inspect the current post-Step-2.3 repository and answer:

- which Step 2.3 fact/resolver/provenance types can be reused unchanged;
- which enums/requests need minimal extension;
- whether `ValuationFactsProvider` naming is tolerable for the new strategy or a concrete incompatibility exists;
- which SEC/provider concepts plausibly represent CFO and CapEx;
- how annual period pairing/restatement selection currently works;
- what presenter/CLI patterns are reusable;
- the exact files likely to change.

Make no production changes.

**Stop for human review and resolve the product-policy checkpoint before Slice B.**

### Slice B — pure FCF/growth math and typed result semantics

Implement:

- pure FCF calculation;
- percentage-growth helper;
- CAGR helper;
- typed strategy result / metric-status semantics;
- deterministic unit tests.

No provider or CLI work.

### Slice C — financial-fact extension, resolution, and fixtures

Minimally extend the existing provider-neutral fact/resolution system for CFO and CapEx, add period-aligned FCF derivation with lineage, and add deterministic multi-year fixtures.

No production provider guessing.

### Slice D — provider evidence and production integration

Evidence and implement the minimum safe production path, preferably reusing SEC EDGAR infrastructure if proven compatible.

Unsupported filings remain unavailable.

### Slice E — investor CLI and presentation

Add `fcf-growth` direct execution plus concise/details/diagnostics/JSON output using the approved shared grammar.

Perform representative live validation only after deterministic tests are green.

### Slice F — documentation and full gate

Synchronize documentation, run full Ruff/format/strict-mypy/pytest/diff gates, review the complete Step 2.4 diff, and stop for explicit human completion approval before Step 2.5 Golden work begins.

---

## 15. Acceptance criteria

Step 2.4 is complete only when:

- [ ] the prospective-user policy question has been explicitly resolved or the historical baseline has been explicitly approved;
- [ ] the strategy is named and typed independently from Momentum and Graham;
- [ ] the canonical initial FCF definition is explicit and tested;
- [ ] CapEx provider sign conventions are normalized transparently;
- [ ] annual CFO and CapEx are paired only across compatible fiscal periods;
- [ ] annual diluted-EPS growth uses an explicit documented basis;
- [ ] 3-year CAGR uses four completed annual observations and rejects mathematically nonmeaningful endpoints;
- [ ] negative/zero values are represented truthfully without NaN/infinity or fabricated fallbacks;
- [ ] strict `as_of` prevents look-ahead;
- [ ] derived FCF retains full component lineage;
- [ ] the Step 2.3 provider/cache/resolver/provenance architecture is reused or minimally extended rather than duplicated;
- [ ] deterministic fixtures cover success, missing data, period mismatch, negative/zero growth, restatement, and historical-boundary cases;
- [ ] a representative supported production ticker can run the analysis without manual financial-statement arithmetic;
- [ ] concise/details/diagnostics/JSON output follows the established investor-facing grammar;
- [ ] automated tests make no live network or LLM calls;
- [ ] full repository quality gates pass;
- [ ] documentation matches implemented semantics;
- [ ] the final Step 2.4 diff receives explicit human approval.

After approval, stop. Step 2.5 Golden-Suite implementation begins only as a separately reviewed step.

---

## 16. Explicit non-goals

Step 2.4 does not include:

- discounted cash-flow valuation;
- terminal-value modeling;
- cost-of-capital estimation;
- analyst-consensus or LLM-generated growth forecasts;
- P/FCF or P/CF as required core metrics unless separately approved after the product-policy checkpoint;
- a broad named-investor methodology;
- arbitrary composite scoring/ranking;
- investment recommendations;
- Golden Suite/evaluator implementation;
- durable SQLite persistence/migrations;
- watchlists or Analysis Run persistence;
- a generic strategy/plugin registry;
- unrelated refactoring.

The purpose is to add one useful, auditable strategy and prove the existing architecture can accommodate it cleanly.
