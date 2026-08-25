# Step 2.3 Design: Dual-Method Graham Valuation

**Status:** Step 2.3 complete and approved; retained as the authoritative Graham design record<br/>
**Last updated:** 2026-08-25<br/>
**Scope:** Milestone v0.2, Step 2.3 only<br/>
**Completion:** Human-approved final review and complete repository gate passed on 2026-08-25; later steps may extend shared contracts only through separately approved step designs

---

## 1. Purpose and authority

This is the compact implementation specification and final design record for Step 2.3. It converts the approved milestone direction into contracts small enough to implement and review without reopening the whole architecture.

Document precedence for this step is:

1. `milestones/v0.2/IMPLEMENTATION_PLAN.md` — scope, acceptance criteria, and review gates;
2. this document — Step 2.3 method, input, CLI, fixture, and implementation contracts;
3. `docs/user/FINANCE_MATH.md` — formula definitions and financial semantics;
4. `docs/project/ARCHITECTURE.md` — component boundaries;
5. `docs/project/DISCOVERY_WORKBOOK.md` — rationale and decisions;
6. `docs/project/MASTER_PLAN.md` — milestone ordering and broader direction.

If two documents conflict, stop and surface the conflict. Do not silently combine incompatible instructions.

---

## 2. Completed implementation

Slices A through G are complete and approved. The implementation contains the two pure Graham methods; provenance, cache, resolver, and immutable resolver-trace seams; deterministic fixtures; verified production valuation adapters; the conservative SEC-backed BVPS derivation required by the Graham Number using its standard SEC financial facts; strategy-specific investor presenters for Graham and Momentum; and the unified direct-analysis CLI.

F1 established concise/details/diagnostics/JSON presentation, `schema_version = 1`, explicit separation of financial provenance from software resolution trace, temporal coherence at the presentation boundary, and explicit unavailable/null Momentum metrics rather than non-finite sentinels.

F2 closed the live direct-command gaps found after F1. `financial-agents graham TICKER` behaves as a ticker analysis rather than a legacy formula calculator, defaults to the Graham Number, requires provider-backed security evidence before authoritative output, suppresses provider/framework implementation leakage from normal failures, and presents successful concise Graham results in a result-first investor hierarchy.

The production defaults are explicit:

- default Graham Number → SEC EDGAR annual diluted EPS (three-year average) + conservative SEC-backed fiscal-year-end BVPS derivation + Yahoo Finance current quote comparison;
- default/SEC Growth → SEC EDGAR three-year-average diluted EPS + explicit expected-growth assumption + explicit AAA-yield override + Yahoo Finance current quote comparison; and
- explicitly selected Massive Growth → Massive TTM diluted EPS + explicit expected-growth assumption + explicit AAA-yield override + Massive current quote, requiring `MASSIVE_API_KEY`.

No production AAA-yield series was approved in Step 2.3. Historical `--as-of` remains a hard no-look-ahead boundary; current-only quote adapters do not masquerade as historical quote sources.

Slice G completed documentation synchronization, final cleanup, the complete repository gate, remaining-diff review, and explicit human completion approval on 2026-08-25.

The new Free Cash Flow & Earnings Growth strategy is Step 2.4 work. Golden Suite/evaluator work is Step 2.5. Neither is part of Step 2.3.

## 3. Locked decisions

| Area | Approved decision |
| :--- | :--- |
| Default method | `graham_number` |
| Secondary method | `graham_growth_value`, selected explicitly |
| Graham Number meaning | Maximum indicated price / screening ceiling, not a complete intrinsic-value conclusion |
| Graham Number EPS default | Average of three completed fiscal-year EPS observations |
| Graham Number variation | TTM EPS only when explicitly selected and labeled |
| Growth policy | `explicit_override`; no LLM estimate and no silent default |
| Growth production EPS basis | SEC/default uses `three_year_average`; explicit Massive uses `ttm` |
| AAA-yield production policy | No approved live series in Step 2.3; direct Growth requires an explicit user-supplied AAA yield |
| Provider architecture | Option A: keep `BaseDataClient` historical-price focused; use a valuation-facts boundary |
| Default security facts | SEC EDGAR |
| Default quote comparison | Yahoo Finance narrow current-price valuation adapter |
| Explicit Massive configuration | TTM EPS/current price only; requires configured Massive credentials |
| Resolution order | Explicit override → valid cache → configured provider → unavailable |
| Time policy | Requested `as_of` is a hard no-look-ahead boundary |
| Cache scope | Minimal in-memory/fixture seam in Step 2.3; durable SQLite cache in Step 3.1 |
| CLI contract | One `graham` command with an explicit method discriminator; omitted method means Graham Number |
| Subject-validation policy | Fully override-driven arithmetic does not establish ticker identity; authoritative output requires provider-backed security evidence |
| Test data | Deterministic fixtures only; no live provider or LLM calls in automated tests |
| Investor presentation | Result-first concise success view; `--details`, `--diagnostics`, and `--json` provide progressive disclosure |
| Presentation architecture | Momentum and Graham share a visual grammar, not a forced generic internal result model |
| Terminal details | Fixed labels for v0.2; table-oriented rendering is deferred pending real-user feedback |
| JSON contract | `schema_version = 1`; breaking semantic/structural changes require explicit version review |
| Diagnostics | Immutable resolver execution trace is distinct from financial provenance and records only behavior actually observed |
| Momentum unavailable metrics | SMA/crossover unavailability is `None`/JSON `null`, never `NaN`; insufficient history yields `UNKNOWN` |
| Momentum market metadata | Source/freshness/currency are supplied by execution/presentation context, not added to pure `MomentumMetrics` |
| Durable report model | Not Step 2.3; Step 3.4 persists Analysis Runs and renders views from them |
| Commit gate | Coding agents never commit automatically. A reviewed intermediate checkpoint may be committed/pushed after explicit human approval; Step 2.3 completion required the final review gate |

---

## 4. Financial methods

### 4.1 Graham Number — default

```text
maximum_indicated_price = sqrt(22.5 × EPS × BVPS)
```

`22.5 = 15 × 1.5`, combining the traditional defensive-investor P/E and P/B ceilings.

Required inputs:

- EPS on the selected basis; and
- book value per common share (BVPS).

Default EPS basis:

```text
three_year_average_eps =
    (completed_fiscal_eps_1 + completed_fiscal_eps_2 + completed_fiscal_eps_3) / 3
```

Rules:

- retain the three component periods in derived-input lineage;
- retain basic/diluted basis and split adjustments when known;
- do not mix incompatible share classes or silently substitute TTM EPS;
- a provider-reported BVPS is acceptable only with its definition and source field retained;
- derived BVPS uses common shareholders' equity divided by period-end common shares; and
- EPS ≤ 0 or BVPS ≤ 0 returns `not_applicable`.

The implemented SEC integration uses eligible annual diluted EPS observations and derives fiscal-year-end BVPS from eligible balance-sheet components. Direct same-period common shares outrank the verified issued-minus-treasury derivation. Preferred-share zero is inferred only under narrowly approved evidence rules; generic missing preferred data is not zero.

The result field is `maximum_indicated_price`. User-facing text calls it a screening ceiling or maximum indicated price, not an unqualified intrinsic value.

### 4.2 Graham growth value — explicit secondary method

```text
growth_value = normalized_eps
    × (base_pe + growth_multiplier × g)
    × baseline_aaa_yield / current_aaa_yield
```

Initial configurable convention:

```text
base_pe = 8.5
growth_multiplier = 2.0
baseline_aaa_yield = 4.4
```

Required inputs:

- EPS on an explicit supported basis;
- expected annual growth `g`, supplied by the user in percentage points; and
- current AAA corporate-bond yield, also supplied explicitly by the user in Step 2.3.

`6.5` means 6.5%, not `0.065`. Both AAA-yield values must be strictly positive.

Growth policy is `explicit_override`. The LLM, provider adapter, and resolver must not invent, infer, clip, cap, floor, or silently annualize growth.

Production EPS basis is provider-explicit: SEC/default Growth uses `three_year_average`; explicit Massive Growth uses `ttm`. Unsupported SEC+TTM and Massive+three-year-average combinations are rejected rather than silently translated.

No production AAA-yield series is approved in Step 2.3. The direct CLI requires `--aaa-yield` (with the retained legacy alias `--current-aaa-yield`) and marks that value as user-supplied rather than provider-verified.

### 4.3 Optional quote comparison

A current or point-in-time quote is optional for calculating either method but required for price comparison:

```text
margin_of_safety_percent =
    (reference_value - current_price) / reference_value × 100
```

The reference value is `maximum_indicated_price` for the Graham Number and `growth_value` for the growth method. If quote resolution fails, return the calculated method value with `current_price = None` and `margin_of_safety_percent = None` rather than discarding a valid calculation.

The Graham analyses using SEC EDGAR financial facts use the narrow Yahoo Finance valuation adapter for current quote comparison. The adapter does not claim historical valuation-quote support; historical `--as-of` may therefore produce a valid method value without a price comparison. Explicit Massive Growth uses the Massive current quote capability.

If valuation and quote currencies differ, the quote may be shown but the relationship is unavailable until an approved FX conversion mechanism exists.

---

## 5. Implemented CLI and presentation contract

Direct Graham analysis is:

```text
financial-agents graham TICKER [--method number|growth] [options]
```

`--method` defaults to `number`. Direct Momentum remains a peer command. The positional ticker is preferred; the transitional `--ticker/-t` alias remains accepted. A later Light Mode `financial-agents analyze TICKER` entry point may combine default deterministic analyses and bounded synthesis, but it was not required to finish Step 2.3.

Common Graham options include:

- `--as-of DATE_OR_TIMESTAMP`;
- `--data-provider PROVIDER_ID`;
- `--no-cache`;
- `--eps VALUE`;
- `--eps-basis BASIS`;
- `--current-price VALUE`;
- `--details`;
- `--diagnostics`; and
- `--json`.

Number-specific option: `--bvps VALUE`. Number defaults to `three_year_average` EPS.

Growth-specific options:

- `--expected-growth VALUE` (retained alias `--expected-growth-rate`, short `-g`);
- `--aaa-yield VALUE` (retained alias `--current-aaa-yield`, short `-y`); and
- provider-supported EPS basis only: SEC/default → `three_year_average`, explicit Massive → `ttm`.

Method-incompatible flags and unsupported provider/basis combinations produce clear usage errors.

### Presentation levels

The direct-analysis commands use one coherent terminal grammar while retaining strategy-specific typed results.

**Default concise success view** is result-first. Graham Number begins with the maximum indicated price; Growth begins with the Growth Value and immediately surfaces the expected-growth assumption. Current price/price relationship follow when a compatible quote is available. High-level sources/freshness, material warnings, and method limitations remain visible. Redundant `Status: ok` and `As of: current` are omitted; historical `as_of` is surfaced in the heading.

For non-success outcomes, status and a humanized reason remain prominent. A negative Graham Number input is reported as `not applicable`, not as a malformed calculation.

**`--details`** shows the financial audit trail: resolved values, accounting/measurement basis, reporting/observation periods, availability dates, original provider/source identity, derivations/component lineage, and assumptions.

**`--diagnostics`** shows software resolution behavior from the explicit resolver trace: override state, cache behavior, provider attempts, derivation steps, and classified unavailable/error outcomes. Cache state is not allowed to replace the original financial source identity, and diagnostics must not infer a more precise cache-miss/staleness cause than the cache contract actually exposes.

**`--json`** emits stable machine-readable method/result/provenance data suitable for tests and later Analysis Run persistence. `schema_version = 1`; unavailable numeric fields are emitted as JSON `null`, never non-standard `NaN`.

Operational logger output is not the investor-facing rendering mechanism. The presenter writes user results; operational logs retain execution diagnostics.

The Graham Number says **maximum indicated price** or **screening ceiling**, never unqualified “Intrinsic Value.” The Growth method makes the user-supplied growth assumption explicit and warns when the AAA yield is user-supplied rather than provider-verified.

For v0.2, details use fixed labels. Richer table-oriented terminal rendering is deliberately deferred until real-user feedback demonstrates that it is worth the additional presentation complexity.

## 6. Component boundaries

### Pure calculators

Pure functions perform validation and arithmetic only. They receive resolved numeric values, return typed method-specific results, and perform no network, cache, filesystem, settings, or clock I/O.

### Investor-facing presentation boundary

Strategy-specific presenters translate typed Momentum/Graham results into the common concise/details/diagnostics/JSON grammar. They may format and explain already-computed fields but do not fetch providers, resolve inputs, perform financial arithmetic, or invent assumptions.

Do not introduce a giant generic result object merely to share terminal formatting.

### `BaseDataClient`

Remains the existing historical-price-series boundary used by Momentum. Step 2.3 does not add fundamentals, macro series, valuation-cache policy, or synthetic one-day quote retrieval to it.

### `ValuationFactsProvider`

The provider-neutral boundary supplies or composes only the valuation facts needed by this step:

- quotes;
- completed annual EPS observations and/or a documented TTM EPS fact;
- provider-reported BVPS or the documented components needed to derive it; and
- macro observations where a specifically identified series exists.

The production façade composes narrow SEC EDGAR, Massive, and Yahoo valuation adapters. No design assumes that one upstream service provides every fact. The production macro capability remains intentionally unused for AAA yield until an approved series/integration exists.

### `GrahamInputResolver`

Resolves each field independently:

```text
override → temporally and structurally valid cache entry → provider → unavailable
```

The resolver owns precedence, validation, `as_of` eligibility, provider fallback, transformations, and provenance assembly. Calculators never invoke it.

Method-input assembly may add a semantic basis annotation only when supported by retained evidence; for example, derived BVPS is labeled `fiscal_year_end` when its complete lineage is on that basis.

### Valuation cache seam

Step 2.3 uses a small `get`/`put` abstraction and an in-memory implementation sufficient to test:

- hit and miss behavior;
- disabled-cache behavior;
- schema/version invalidation;
- staleness and temporal eligibility;
- non-finite value rejection; and
- preservation of provenance.

The cache does not fetch data. The resolver owns fallback. Durable storage, migrations, eviction policy, and SQLite integration are Step 3.1 work.

---

## 7. Resolution and provenance contract

Every method input is classified as required or optional before resolution. Required unresolved facts fail explicitly; optional quote failure only suppresses comparison fields.

Every resolved input contains:

- numeric value;
- semantic field name;
- units and currency when applicable;
- source kind: `override`, `cache`, `provider`, or `derived`;
- provider identifier plus exact source field or series identifier when applicable;
- reporting or observation period;
- filing, publication, or `available_at` time when supplied;
- requested analysis `as_of`;
- retrieval/resolution time;
- accounting basis or measurement basis;
- transformations and component lineage;
- cache state and schema version when applicable; and
- override state.

Provider facts must be finite and semantically compatible with the requested field before use. Missing facts never become zero.

An override is an explicit user assertion for the requested analysis boundary. It bypasses provider lookup for that field but remains visibly labeled `override`; it must not be presented as provider-verified historical evidence.

Fully override-driven arithmetic is also insufficient to verify a security identity. The direct CLI requires at least one provider-backed security fact or quote before presenting an authoritative ticker analysis.

### Point-in-time rule

A fact is eligible only when it was knowable on or before the requested `as_of`. A fiscal period end alone is insufficient if the filing or publication occurred later.

If a provider exposes only a current snapshot and cannot establish historical availability safely, a historical request returns unavailable. It must not silently substitute today's value.

---

## 8. Result and error semantics

Use typed, machine-readable statuses:

- `ok` — required inputs resolved and calculation completed;
- `not_applicable` — inputs are valid but the selected method is inapplicable, including non-positive EPS or BVPS for the Graham Number;
- `input_unavailable` — a required input could not be resolved under the requested time boundary;
- `invalid_input` — supplied value, unit, basis, or method/flag combination is invalid; and
- `provider_error` — the configured provider failed in a way that should be distinguished from an absent fact.

No execution branch returns NaN, infinity, a complex number, or a silent zero. Normal investor-facing errors do not leak framework tracebacks, Pydantic documentation links, provider-library implementation keys, or secrets.

Method-specific result types remain explicit. Invalid cross-method combinations are rejected before calculation, and every result identifies its method.

---

## 9. Provider evidence gate

Before coding a production field mapping, record evidence for each capability:

| Capability | Evidence required before acceptance | Step 2.3 production status |
| :--- | :--- | :--- |
| Annual EPS | Exact field(s), annual periods, basic/diluted meaning, restatement/split behavior, availability timestamp, units | SEC EDGAR annual diluted EPS accepted |
| TTM EPS | Exact field, trailing window, basic/diluted meaning, update behavior, availability timestamp | Massive current TTM diluted EPS accepted |
| BVPS | Exact field and definition, common-vs-total equity, share class, period end, units/currency; or documented derivation components | SEC-backed derivation accepted under conservative component rules; direct SEC BVPS not claimed |
| Quote | Exact field, exchange/currency, market/session semantics, observation timestamp, historical support | Yahoo current quote accepted for Graham analyses using SEC EDGAR financial facts; Massive current quote accepted for explicit Massive configuration; historical support not claimed by these valuation adapters |
| AAA yield | Exact series identifier, rating/issuer/maturity scope, frequency, units, observation and publication dates, retrieval method, licensing | No production series approved; CLI requires override |
| Historical `as_of` | Proof that the capability can reject facts published after the boundary; otherwise declare it unsupported | SEC facts enforce publication/availability boundary; current-only quote capabilities remain unavailable historically |

FRED's Moody's Seasoned Aaa Corporate Bond Yield (`AAA`) remains a candidate for future investigation, not an approved production selection. An arbitrary finance ticker is not accepted as an undocumented substitute.

If no single provider passes all rows, compose narrow adapters. Deterministic fixtures may model all capabilities without implying that a live provider has them.

---

## 10. Deterministic fixtures and tests

Fixtures include realistic values and metadata for:

- three completed annual EPS observations;
- an explicit TTM EPS observation;
- direct or derived BVPS;
- a quote;
- an AAA-yield observation;
- reporting/observation and `available_at` timestamps;
- retrieval metadata and units; and
- missing, stale, future-published, malformed, and non-finite cases.

Required/implemented test groups include:

1. both formulas against hand-calculated values;
2. default three-year-average EPS and explicit TTM selection;
3. non-positive EPS/BVPS → `not_applicable`;
4. CLI override wins without provider access;
5. valid cache hit wins over provider;
6. cache miss/stale/schema-invalid/non-finite entry falls through safely;
7. provider success and provider/missing-fact failure;
8. requested `as_of` rejects later or not-yet-published facts;
9. provenance completeness and derived lineage;
10. missing growth/AAA requirements produce clean CLI usage failures under the production policy;
11. optional quote failure preserves the method value and suppresses comparison;
12. CLI default and explicit method dispatch plus incompatible-flag validation;
13. provider/basis routing for default SEC and explicit Massive Growth;
14. provider-backed ticker verification for override-heavy requests;
15. investor-facing concise/details/diagnostics/JSON semantics; and
16. no live network or LLM calls in automated tests.

Use the repository's quality commands and coverage threshold from the active milestone plan. Do not weaken existing tests merely to accommodate the redesign.

---

## 11. Implementation sequence for a smaller-context coding model

Give the coding model one bounded prompt at a time. At the end of each slice, require a short diff summary and focused tests; do not ask it to redesign later slices. A coding model never commits unless the human explicitly authorizes that specific action.

### Slice A — reconnaissance only
Complete.

### Slice B — pure methods and typed results
Complete and approved.

### Slice C — provenance and resolver
Complete incrementally (C1/C2 family) and approved.

### Slice D — deterministic valuation fixtures
Complete and approved.

### Slice E1 — provider evidence
Complete and approved.

### Slice E2 — verified production adapters
Complete and approved. SEC EDGAR annual diluted EPS and Massive current TTM EPS/current price are implemented behind the production valuation façade; unsupported capabilities remain explicit unavailable.

### Human-approved checkpoint
The coherent foundation through E2 was approved as a durability checkpoint. This did not mark Step 2.3 complete and did not authorize later-step work.

### Slice E3 — user-viable standard Graham data configuration
Complete and approved. The production Graham Number using its standard SEC financial facts includes the conservative SEC-backed BVPS derivation with narrowly evidenced preferred-share-zero inference and full component lineage; unsupported filings remain unavailable rather than weakening the rule.

### Slice F1 — investor-facing result presentation
Complete and approved. Strategy-specific presenters implement concise, `--details`, `--diagnostics`, and `--json` views with shared grammar; `schema_version = 1`, explicit resolver trace, temporal-coherence guards, and unavailable/null Momentum metrics are established.

### Slice F2 — unified direct-analysis CLI
Complete and approved after focused quality gates and live KO validation. The direct command uses the approved method-specific validation/defaults, SEC/Yahoo default routing, explicit Massive routing, provider-backed subject validation, result-first concise output, and clean investor-facing failure semantics.

### Slice G — documentation and full gate
Complete and approved. Documentation synchronization and final cleanup were completed; the complete Ruff, format, strict-mypy, pytest, diff, and status gates passed; representative live Momentum and Graham behavior was reviewed; the final non-positive Graham Growth Value presentation correction was validated in concise and JSON output; and human review explicitly approved Step 2.3 completion on 2026-08-25. No Step 2.4 work was begun before this approval.

## 12. Out of scope

- Free Cash Flow & Earnings Growth strategy work owned by Step 2.4;
- Golden Suite/evaluator reporting owned by Step 2.5;
- durable watchlists, Analysis Run persistence/history, batch refresh, and run browsing owned by Step 3.4;
- background daemons, unattended scheduling, proactive monitoring/notifications, full-screen TUI, and executive report generation;
- durable SQLite cache and migrations owned by Step 3.1;
- LLM-generated growth estimates;
- analyst-consensus or provider growth estimates without a separately approved policy;
- a speculative general strategy registry/plugin framework;
- assuming one provider supplies prices, fundamentals, and macro series;
- complete Graham defensive-investor qualification; and
- investment recommendations.

---

## 13. Completion and review checklist

Step 2.3 completion was approved after all of the following were satisfied:

- [x] both methods are explicitly named and mathematically tested;
- [x] the Graham Number is the CLI default and labeled as a screening ceiling;
- [x] three-year-average EPS is the default and TTM is explicit;
- [x] growth requires an explicit user override;
- [x] `BaseDataClient` remains historical-price focused;
- [x] valuation provider, cache, resolver, and provenance seams are present;
- [x] all required inputs follow override → cache → provider → unavailable;
- [x] historical `as_of` behavior cannot look ahead silently;
- [x] exact live field mappings are evidenced or declared unsupported;
- [x] a representative supported production ticker completes the Graham Number using its standard SEC financial facts without a manual BVPS override;
- [x] default investor output is concise and truthful; `--details`, `--diagnostics`, and `--json` expose progressively deeper evidence;
- [x] material overrides/warnings are conspicuous and operational logs are separate from result rendering;
- [x] Momentum and Graham share presentation grammar without a forced generic result model;
- [x] fixtures and automated tests are deterministic and offline;
- [x] current-vs-target documentation is truthful and synchronized;
- [x] the complete quality gate passes; and
- [x] the remaining diff since the last approved checkpoint was presented for human review.

This completion condition was satisfied on 2026-08-25. Step 2.3 is complete and approved. Subsequent Step 2.4 work is governed by its own separately approved design and branch/review boundary.
