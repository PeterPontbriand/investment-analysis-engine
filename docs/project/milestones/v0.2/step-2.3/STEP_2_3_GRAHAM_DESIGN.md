# Dual-Method Benjamin Graham Valuation Analysis Strategy

This document defines the deterministic Benjamin Graham valuation analysis strategy in Financial Data Agents. The strategy contains two explicitly distinct methods: the Graham Number and the Graham growth-value formula. Investors run either method directly from the command line, and both methods return typed, auditable results derived from resolved financial inputs.

The Graham Number is the default. It produces a screening ceiling from earnings per share and book value per share. The growth-value method is selected explicitly and produces a forecast-dependent estimate from normalized earnings per share, a user-supplied growth assumption, and a user-supplied AAA corporate-bond yield. Neither method constitutes a complete investment recommendation.

## Decision summary

| Decision | Contract |
| :--- | :--- |
| Default method | Graham Number: `graham_number` |
| Secondary method | Graham growth-value method: `graham_growth_value`, selected explicitly |
| Graham Number meaning | Maximum indicated price or screening ceiling, not a complete intrinsic-value conclusion |
| Default earnings basis | Average of three completed fiscal-year diluted earnings-per-share observations |
| Optional earnings basis | Trailing-twelve-month diluted earnings per share only when explicitly selected and supported |
| Growth assumption | Explicit user override; never inferred by a language model, provider, or resolver |
| AAA corporate-bond yield | Explicit user override; no live production series is approved |
| Default financial-fact provider | U.S. Securities and Exchange Commission EDGAR filing data |
| Explicit Massive configuration | Massive trailing-twelve-month diluted earnings per share and current quote; requires `MASSIVE_API_KEY`. The Graham Number can also use this route when book value per share is supplied explicitly. |
| Resolution order | Provider-resolvable fields use explicit override → valid cache → configured provider → unavailable. Expected growth is override-only. |
| Historical boundary | Requested `as_of` is a strict no-look-ahead boundary |
| JSON version | Public investor-presentation `schema_version = 2`; version 2 adds the explicit nullable security-identity snapshot without changing either Graham calculation method |

---

# Part I — Financial Methods and Investor Experience

## 1. Strategy identity and interpretation

The command-line interface exposes one Benjamin Graham valuation analysis strategy with two methods:

```text
financial-agents graham TICKER [--method number|growth] [options]
```

`--method` defaults to `number`.

The existing Momentum analysis strategy remains a separate peer command.

The two methods answer different questions:

| Method | Investor question | Principal limitation |
| :--- | :--- | :--- |
| Graham Number | What maximum price is indicated by a traditional earnings-and-book-value screen? | It is a screening ceiling, not a complete intrinsic valuation. |
| Graham growth-value method | What value does the configured growth formula produce from explicit earnings, growth, and bond-yield assumptions? | It depends directly on a user-supplied forecast and yield. |

The methods remain separate in calculation, input requirements, result types, validation, and presentation. A result always identifies the method used.

## 2. Graham Number method

### 2.1 Formula and meaning

```text
maximum_indicated_price = sqrt(22.5 × EPS × BVPS)
```

`22.5 = 15 × 1.5`, combining the traditional defensive-investor price-to-earnings and price-to-book ceilings.

Required inputs are:

- earnings per share on the selected basis; and
- book value per common share.

The result field is `maximum_indicated_price`. Investor-facing output calls it a **maximum indicated price** or **screening ceiling**, never an unqualified intrinsic value.

If earnings per share or book value per share is zero or negative, the method returns `not_applicable`. The inputs remain financially meaningful; the method is simply unsuitable for them.

### 2.2 Default earnings basis

The default uses the arithmetic mean of three completed fiscal-year diluted earnings-per-share observations:

```text
three_year_average_eps =
    (completed_fiscal_eps_1 + completed_fiscal_eps_2 + completed_fiscal_eps_3) / 3
```

The derived value retains:

- all three component periods;
- the exact diluted-earnings provider field used for every component;
- units, currency, provider fields, and availability dates; and
- complete component lineage.

The resolver accepts the three observations only when one explicit compatibility predicate establishes the same provider concept, diluted/basic EPS basis, units, currency, and fiscal basis across distinct completed fiscal years. Provider-exposed `share_class=` and `split_treatment=` provenance tags must also agree. Duplicate candidates for one selected fiscal period are treated as ambiguous restatement evidence and make the series unavailable; the resolver does not guess which filing to use or perform silent split normalization. The accepted derivation retains components plus a compatibility-policy note. Trailing-twelve-month diluted earnings per share is used only when the investor selects it explicitly and the chosen provider supports it.

### 2.3 Book value per common share

A provider-reported book value per share is acceptable only when its definition and exact source field are retained.

The default derives fiscal-year-end book value per common share from eligible U.S. Securities and Exchange Commission filing facts:

```text
book_value_per_common_share =
    stockholders_equity / period_end_common_shares
```

The derivation is allowed only when preferred shares outstanding resolve to zero under the evidence rules in Section 10.2, so total stockholders' equity can be treated as common equity for this purpose. Equity and share counts must describe the same reporting period. Direct common-share and preferred-share facts outrank approved inferences; missing preferred-share information is not treated as zero. Ambiguous or incompatible evidence makes book value per common share unavailable, and every accepted derivation retains its components.

The approved future Step 2.5A foreign-private-issuer extension does not broaden
this BVPS contract. Its first IFRS phase covers annual duration facts only.
Entity-level Company Facts and a generic outstanding-share value do not prove
ordinary/common share capital, preferred equity of zero, a compatible period-end
denominator, or ADR/ADS unit equivalence. IFRS-derived BVPS therefore remains
unsupported unless a later dimensional/share-class mapping passes a separate
evidence review. See the [SEC EDGAR FPI / IFRS D0 Mapping
Record](../step-2.5a/SEC_EDGAR_FPI_IFRS_D0_MAPPING_RECORD.md).

## 3. Graham growth-value method

### 3.1 Formula and assumptions

```text
growth_value = normalized_eps
    × (base_pe + growth_multiplier × g)
    × baseline_aaa_yield / current_aaa_yield
```

The configured convention is:

```text
base_pe = 8.5
growth_multiplier = 2.0
baseline_aaa_yield = 4.4
```

Required inputs are:

- earnings per share on an explicitly supported basis;
- expected annual growth `g`, supplied by the investor in percentage points; and
- current AAA corporate-bond yield, also supplied by the investor in percentage points.

`6.5` means 6.5%, not `0.065`. The current and baseline AAA corporate-bond yields must be strictly positive.

The expected-growth policy is `explicit_override`. A language model, provider adapter, or resolver does not invent, infer, clip, cap, floor, or silently annualize the growth assumption.

A worked example makes the percentage-point convention explicit:

| Input or intermediate value | Amount |
| :--- | ---: |
| Normalized earnings per share | USD 5.00 per share |
| Expected annual growth, `g` | 6.5 percentage points |
| Current AAA corporate-bond yield | 5.25 percentage points |
| Formula price-to-earnings factor | `8.5 + (2.0 × 6.5) = 21.5` |
| Yield adjustment | `4.4 / 5.25` |
| Growth value | `5.00 × 21.5 × (4.4 / 5.25) = USD 90.10 per share` |

The yield ratio is dimensionless because both yields use percentage points. The method accepts any finite expected-growth value for which the resulting price-to-earnings factor and final value remain finite and the price-to-earnings factor remains strictly positive. It does not impose an arbitrary growth cap. With the configured constants, `g = -4.25` percentage points is invalid because it produces a zero price-to-earnings factor; more negative values are also invalid.

### 3.2 Supported provider and earnings combinations

The following production routing matrix is normative:

| Method and provider | Earnings basis | Outcome | Current quote |
| :--- | :--- | :--- | :--- |
| Graham growth-value method; default or explicit SEC EDGAR | Three-year average annual diluted earnings per share | Accepted; this is the default growth configuration | Yahoo Finance |
| Graham growth-value method; default or explicit SEC EDGAR | Trailing-twelve-month diluted earnings per share | Usage error | Not attempted |
| Graham growth-value method; explicit Massive | Trailing-twelve-month diluted earnings per share | Accepted | Massive |
| Graham growth-value method; explicit Massive | Three-year average annual diluted earnings per share | Usage error | Not attempted |

The Graham Number defaults to SEC EDGAR three-year-average earnings. The deliberate Massive route requires trailing-twelve-month Massive earnings plus an explicit book-value-per-share override; it may then use a Massive quote. SEC/TTM, Massive/three-year-average, and Massive Graham Number without the book-value override are rejected before provider work begins. Massive does not acquire an undocumented book-value-per-share capability merely because it can supply trailing-twelve-month earnings.

No production AAA corporate-bond-yield series is approved. Direct analysis therefore requires `--aaa-yield`, retains `--current-aaa-yield` as a compatibility alias, and labels the value as user-supplied rather than provider-verified.

## 4. Optional current-price comparison

A quote is optional for either calculation but required for price comparison:

```text
margin_of_safety_percent =
    (reference_value - current_price) / reference_value × 100
```

`reference_value` is `maximum_indicated_price` for the Graham Number method and `growth_value` for the Graham growth-value method.

If a provider quote is unavailable or the provider reports an error, the method result remains available while `current_price` and `margin_of_safety_percent` are null. An invalid explicit quote override instead makes input assembly fail with `invalid_input`, so the calculation is not performed. SEC-backed analyses use Yahoo Finance quotes; analyses explicitly configured for Massive use Massive quotes. This includes a Graham Number analysis that combines Massive trailing-twelve-month earnings with an explicit book-value-per-share override. Both quote adapters are current-only, so a historical analysis may have a valid valuation without a price comparison.

A successfully resolved finite quote is displayed even when no comparison can be made. The price relationship is unavailable when both valuation and quote currencies are known and differ, the reference value is non-positive, or the comparison percentage is otherwise unavailable. An explicit quote override may omit currency and is accepted on that basis. Both Yahoo Finance and Massive classify a provider quote with missing required currency as `input_unavailable`. In either provider case, the valuation can still succeed without a quote. No foreign-exchange conversion is attempted.

## 5. Investor controls

Common options are:

- `--as-of DATE_OR_TIMESTAMP`;
- `--data-provider PROVIDER_ID`;
- `--no-cache`;
- `--eps VALUE`;
- `--eps-basis BASIS`;
- `--current-price VALUE`;
- `--details`;
- `--diagnostics`; and
- `--json`.

The Graham Number method additionally accepts `--bvps VALUE` and defaults to the three-year-average earnings basis.

The Graham growth-value method accepts:

- `--expected-growth VALUE`, with retained aliases `--expected-growth-rate` and `-g`;
- `--aaa-yield VALUE`, with retained aliases `--current-aaa-yield` and `-y`; and
- only an earnings basis supported by the selected provider.

The positional ticker is preferred. The transitional `--ticker` and `-t` aliases remain accepted. Method-incompatible options and unsupported provider/basis combinations produce clear usage errors.

Fully override-driven arithmetic does not establish that the ticker identifies a real security. Authoritative ticker output requires at least one provider-backed security fact or quote.

## 6. Investor-facing output

The direct-analysis commands share a coherent visual grammar while retaining method-specific typed results. `--details`, `--diagnostics`, and `--json` are mutually exclusive presentation modes.

### 6.1 Concise output

Successful concise output is result-first:

| Order | Graham Number method | Graham growth-value method |
| ---: | :--- | :--- |
| 1 | Maximum indicated price | Growth value and expected-growth assumption |
| 2 | Current price and price relationship, when compatible | Current price and price relationship, when compatible |
| 3 | Earnings/book-value basis, then headline earnings per share and book value per share | High-level sources, freshness, and assumption provenance |
| 4 | High-level sources and freshness | Material warnings, including user-supplied AAA yield |
| 5 | Material warnings | Method limitation |
| 6 | Method limitation | — |

Redundant `Status: ok` and `As of: current` lines are omitted. A historical `as_of` appears in the heading.

When calculation has begun and returns a non-success result, the presenter shows a status and reason. Every `CalculationStatus` has an exhaustive plain-English label (`ok`, `not applicable`, `invalid input`, `input unavailable`, or `provider error`). Required-input, provider, and ticker-verification failures use the same typed presentation boundary: concise mode renders its friendly one-line error from that typed state, while detailed mode shows the plain-English status and reason and diagnostic/JSON modes retain machine identifiers. Non-positive Graham Number inputs therefore produce a clear not-applicable result, not a malformed calculation.

### 6.2 Detailed, diagnostic, and JSON output

Every view consumes the same typed presentation assembled from the resolved inputs and optional calculation result. `--details` exposes values, bases, periods, availability, sources, derivations, lineage, assumptions, and typed failure state. `--diagnostics` exposes only resolver events actually observed; it does not invent the reason for an opaque cache miss. `--json` emits the result envelope in Section 8.4, using null rather than `NaN`. Financial provenance remains distinct from software-resolution diagnostics, and cache use never replaces original source identity.

## 7. Interpretation limits

The strategy is neither complete Benjamin Graham defensive-investor qualification nor an investment recommendation. It does not generate growth estimates, approve analyst-consensus or provider growth without a separate policy, verify the AAA yield, convert currencies, or turn current-only quotes into historical quotes. It also does not assume one provider supplies every data class or force this strategy and the existing Momentum analysis strategy into one generic result type.

---

# Part II — Normative Implementation Contract

Part II defines the calculation, data-resolution, provenance, provider, presentation, and verification behavior required by the financial strategy above. Established repository conventions govern Python organization and shared types only where they preserve these financial and user-facing semantics.

## 8. Normative calculation and public-result contracts

### 8.1 Method identity and pure result types

The method discriminator contains exactly:

```text
graham_number
graham_growth_value
```

Method-specific result types remain explicit. Invalid cross-method combinations are rejected before calculation, and every result identifies its method.

```text
GrahamNumberResult
    method = graham_number
    status: CalculationStatus
    maximum_indicated_price: float | None
    reason: str | None

GrahamGrowthValueResult
    method = graham_growth_value
    status: CalculationStatus
    growth_value: float | None
    reason: str | None
```

For either result, model validation requires the method value and a null reason when `status = ok`. Every non-success status requires a null method value and a non-empty reason.

### 8.2 Execution status

Results use the shared typed statuses:

| Status | Meaning |
| :--- | :--- |
| `ok` | Required inputs resolved and calculation completed. |
| `not_applicable` | Inputs are valid, but the selected method is unsuitable; this includes non-positive earnings or book value for the Graham Number method. |
| `input_unavailable` | A required fact cannot be resolved within the requested information boundary. |
| `invalid_input` | A supplied value, unit, basis, method, or option combination is invalid. |
| `provider_error` | The configured provider failed in a way distinct from an absent fact. |

No branch returns `NaN`, infinity, a complex number, or a silent zero. Normal failures do not expose framework tracebacks, Pydantic documentation links, provider-library implementation keys, or secrets.

### 8.3 Pure calculation boundary

Pure calculators validate resolved numeric values, apply the method formulas, and return method-specific typed results. They perform no provider, network, cache, filesystem, settings, clock, presentation, or language-model work.

The calculation layer receives no authority to choose a provider, substitute an earnings basis, infer growth, fetch a quote, or interpret missing values.

The Graham Number calculator requires finite earnings per share and book value per share. A zero or negative value returns `not_applicable`; otherwise the square root and result must be finite.

The Graham growth-value calculator applies these exact predicates:

- normalized earnings per share and expected growth must be finite;
- current and baseline AAA corporate-bond yields must be finite and strictly positive;
- the base price-to-earnings constant must be finite and strictly positive;
- the growth multiplier must be finite and non-negative;
- the computed price-to-earnings factor must be finite and strictly positive; and
- the final growth value must be finite.

Negative normalized earnings and negative expected growth are not independently rejected. The formula may therefore return a non-positive finite growth value, but a non-positive reference value cannot support a percentage price comparison. The calculator performs no clipping, range coercion, or absolute-value transformation.

### 8.4 Public JSON result envelope

The JSON document is the normative machine-readable public surface, implemented from one source of truth in `src/reporting/graham.py`. Both method documents contain `schema_version: 2`, `analysis: "graham"`, uppercase `ticker`, an explicit nullable `security_identity` snapshot, ISO-8601 `as_of` or null, machine-readable `status`, nullable `reason`, `quote`, ordered `warnings`, one method-specific `limitations` entry, and ordered `diagnostics`.

`security_identity` always contains `ticker` plus nullable `instrument_name`, `listing_venue`, `issuer_identifier`, `instrument_identifier`, `provider_id`, and `resolved_at`. It is current descriptive metadata, not financial input and not proof of historical identity at `as_of`. Failure to resolve it does not alter the calculation result.

| Method | `method` | `result` | `inputs` | Additional object |
| :--- | :--- | :--- | :--- | :--- |
| Graham Number | `graham_number` | nullable `maximum_indicated_price`; nullable `margin_of_safety_percent` | nullable `eps`, `bvps`, `current_price` | None |
| Graham growth-value method | `graham_growth_value` | nullable `growth_value`; nullable `margin_of_safety_percent` | nullable `eps`, `expected_growth`, `current_aaa_yield`, `current_price` | `method_assumptions` with numeric `base_pe`, `growth_multiplier`, and `baseline_aaa_yield` |

Each non-null input is a `ResolvedInputDocument` with the following complete field set:

| Required fields | Nullable fields | Collection or recursive fields |
| :--- | :--- | :--- |
| `field_name: string`; `value: number`; `source_kind: override \| cache \| provider \| derived`; `resolved_at: ISO-8601 timestamp` | `origin_source_kind: provider \| derived`; `basis: string`; `units: string`; `currency: string`; `provider_id: string`; `provider_field: string`; `observation_period_start: ISO-8601 timestamp`; `observation_period_end: ISO-8601 timestamp`; `observed_at: ISO-8601 timestamp`; `available_at: ISO-8601 timestamp`; `as_of: ISO-8601 timestamp`; `retrieved_at: ISO-8601 timestamp`; `cache_schema_version: integer` | `notes: string[]`; nullable `lineage` containing `transformation: string` and recursive `components: ResolvedInputDocument[]` |

All nullable fields remain present as JSON `null`. `quote` contains `status: CalculationStatus | "not_attempted"` and nullable `reason`. Each diagnostic contains string fields `field_name`, `stage`, `outcome`, and `message`. The one-element limitation arrays contain these exact strings:

```text
The Graham Number is a maximum indicated price / screening ceiling, not a complete intrinsic-value conclusion or investment recommendation.
The Graham growth value is forecast-dependent and sensitive to the user-supplied growth assumption; it is not an investment recommendation.
```

Warnings are human-readable strings ordered as emitted by the presenter. Graham Number warnings cover earnings-per-share and book-value-per-share overrides, followed by an unavailable-quote warning only when the overall effective status is `ok`. Growth-method warnings cover an earnings-per-share override, then any non-positive growth-value warning, a user-supplied AAA-yield warning, and an unavailable-quote warning. The expected-growth assumption is displayed explicitly but does not produce a separate override warning; neither method warns merely because current price came from an override. Concise output humanizes `not_applicable`, but other presenter-rendered non-success statuses retain their machine spelling.

## 9. Data architecture and resolution

### 9.1 Data boundaries

`BaseDataClient` remains the historical-price-series boundary for the existing Momentum analysis strategy; it does not absorb financial facts or cache policy. `FinancialFactsProvider` supplies or composes the current quotes, annual or trailing earnings, reported book value per share or derivation components, and any specifically approved macroeconomic observations required by the Benjamin Graham valuation methods. Its production façade composes narrow SEC EDGAR, Massive, and Yahoo Finance adapters. The macroeconomic capability remains unused until an AAA series is approved.

### 9.2 Input resolution

`GrahamInputResolver` resolves provider-resolvable financial fields independently:

```text
explicit override
    → temporally and structurally valid cache entry
    → configured provider
    → unavailable
```

The resolver owns precedence, validation, historical eligibility, provider fallback, transformations, and provenance assembly. Calculators never invoke it. Expected growth is an exception to the provider-resolution sequence: it is required as an explicit override, validated as finite, and never read from cache or a provider. The current AAA yield follows the normal resolution machinery at the resolver boundary, but the direct command supplies it through the required user override because no production series is approved.

Required and optional inputs are identified before resolution. An unresolved required input fails explicitly. An unresolved optional quote suppresses only the comparison fields.

For three-year-average earnings, the resolver selects exactly one eligible observation for each of the three latest distinct completed fiscal-year period ends. Multiple candidates for a selected period are an ambiguity error. All three observations must have the same provider field, units, currency, and accounting basis. This prevents mixing different named earnings concepts, but the current resolver does not implement an independent share-class compatibility predicate or split normalization. SEC filing selection retains the exact diluted-earnings concept and chooses the latest eligible restatement knowable at the analysis boundary.

Method-input assembly adds a semantic basis only when retained evidence supports it. Derived book value per common share is labeled `fiscal_year_end` only when stockholders' equity, preferred shares outstanding, and common shares outstanding share one non-null reporting-period end; equity is a currency amount with a known currency; both share counts use share units; preferred shares are non-negative; and common shares are strictly positive. A positive preferred-share count makes this derivation unavailable because total stockholders' equity cannot be treated as common shareholders' equity.

A finite resolved quote is retained for display. A price relationship requires a strictly positive reference value and a finite comparison percentage, and is suppressed when both currencies are known and differ. A production quote without known currency is not retained: Yahoo Finance reports that condition as unavailable, while Massive reports it as a provider error. An explicit quote override can omit currency and is not rejected solely for that omission. If the comparison predicate fails, the quote remains visible and the relationship is null.

### 9.3 Cache seam

The cache key contains subject kind and identifier, field, basis, provider, analysis `as_of`, and a positive cache-schema version. A different version is a miss, not an implicit migration. Only finite provider or derived inputs may be cached; overrides and cache-labelled inputs are rejected. The key must agree with the input, and hits preserve original provenance.

An optional non-negative time to live controls staleness: `None` disables it, and an entry is stale only when its age is greater than the configured duration. A historical hit also requires non-null `available_at <= analysis_as_of`. The cache never fetches; the resolver owns fallback. Because `get` exposes only hit or miss, diagnostics do not guess whether a miss was absent, stale, or historically ineligible. No universal age is specified because the time to live is injected policy. Durable storage, migrations, and eviction remain outside this design.

## 10. Provenance and point-in-time behavior

### 10.1 Resolved-input evidence

Every resolved input conforms to Section 8.4 and retains the financial, temporal, provider, cache, and derivation evidence applicable to it. Provider facts must be finite and semantically compatible with the requested field. Missing facts never become zero.

An override is an explicit user assertion for the requested analysis boundary. It bypasses provider lookup for that field but remains labeled `override`; it is not presented as provider-verified historical evidence.

A fact is historically eligible only when it was knowable on or before requested `as_of`. Fiscal-period end alone is insufficient when filing or publication occurred later.

If a provider exposes only a current snapshot and cannot establish historical availability safely, a historical request returns unavailable rather than substituting the current value.

For SEC EDGAR facts, `available_at` uses the filing acceptance timestamp when available and otherwise the end of the filed date. A fact is eligible only when both its reporting-period end and `available_at` are no later than the analysis boundary. For each annual earnings period, the latest restatement knowable at that boundary is selected. For a balance-sheet period, the latest knowable version is selected only when all observations in that version agree on value and currency; conflicting dimensional observations are unavailable rather than guessed or summed.

### 10.2 Common-share and preferred-share predicates

The SEC-backed book-value-per-common-share derivation applies these exact evidence rules:

1. Direct same-period `CommonStockSharesOutstanding` evidence outranks derivation. If direct evidence is unavailable, common shares may be derived only from one eligible `CommonStockSharesIssued` observation minus one eligible `TreasuryStockCommonShares` observation for the same period. Issued shares must be positive, treasury shares non-negative, and the result positive. A cover-date share count is not substituted.
2. Direct eligible `PreferredStockSharesOutstanding` evidence outranks inference. A positive value prevents the book-value-per-common-share derivation; a negative value makes the derivation unavailable.
3. Zero preferred shares may be inferred only after eligible same-period stockholders' equity and common shares have been resolved. The SEC concept-name classifier examines eligible annual observations at that reporting-period end and analysis boundary. Labels and descriptions do not affect this classification.
4. The only neutral preferred-share concepts are the U.S. GAAP concepts `PreferredStockSharesAuthorized` and `PreferredStockParOrStatedValuePerShare`. Any other eligible concept whose name contains `preferred` or `preference` blocks zero inference.
5. If no such preferred-share concepts exist, zero inference requires the issued-shares-minus-treasury-shares common-share derivation. If neutral concepts exist, `PreferredStockSharesAuthorized` must be present; par value alone is insufficient.
6. The inferred value's `available_at` is the latest availability timestamp among the equity, common-share, and qualifying neutral evidence. Its provider field is `inferred:sec-company-facts:no-issued-preferred-equity`, and its notes state that the value is inferred rather than an explicit preferred-share fact.

Generic missing preferred-share information, future evidence, period mismatch, or ambiguity returns unavailable. These rules constitute the narrowly approved zero-inference policy referenced in the investor explanation.

## 11. Approved production mappings

Production field mappings require evidence rather than plausible field names. The following identifiers and transformations are part of the normative contract:

| Capability | Provider and exact field | Approved semantics |
| :--- | :--- | :--- |
| Annual diluted earnings per share | SEC EDGAR Company Facts `us-gaap:EarningsPerShareDiluted` from 10-K or 10-K/A fiscal-year observations | Three latest distinct completed fiscal years, with latest knowable restatement per period |
| Trailing-twelve-month diluted earnings per share | Massive `diluted_earnings_per_share` with provider timeframe `trailing_twelve_months` | Current four-quarter trailing value; historical requests unavailable |
| Stockholders' equity | SEC EDGAR `us-gaap:StockholdersEquity` | Equity attributable to the parent; subject to the preferred-share guard |
| Common shares outstanding | SEC EDGAR `us-gaap:CommonStockSharesOutstanding` | Same-period direct fact, or `CommonStockSharesIssued - TreasuryStockCommonShares` under the rules in Section 10.2 |
| Preferred shares outstanding | SEC EDGAR `us-gaap:PreferredStockSharesOutstanding` | Same-period direct fact, or the exact zero-inference rules in Section 10.2 |
| Book value per common share | Derived, not claimed as a direct SEC field | `StockholdersEquity / CommonStockSharesOutstanding` only when preferred shares resolve to zero and all component predicates pass |
| Current quote for SEC-backed analysis | Yahoo Finance `fast_info.last_price` | Current quote with a known currency; retrieval time is the conservative observation and availability time |
| Current quote for an analysis explicitly configured for Massive | Massive latest trade `results.p` | Current latest-trade price with provider currency and trade timestamp; used by either method when its other required inputs can be assembled |
| AAA corporate-bond yield | No approved production field or series | Explicit user override required |

FRED's Moody's Seasoned Aaa Corporate Bond Yield (`AAA`) is a candidate for future investigation, not an approved production selection. An arbitrary finance ticker is not an acceptable undocumented substitute.

The growth-method routing matrix in Section 3.2 and this mapping table are tested contracts. For the Graham Number, explicitly selecting Massive with the trailing-twelve-month earnings basis selects Massive for earnings and quote resolution; because Massive supplies no book value per share, direct command-line execution also requires a book-value-per-share override. A mapping change requires documented provider evidence, corresponding deterministic fixtures, and routing and provenance tests. If no provider satisfies all capabilities, the implementation composes narrow adapters. Deterministic fixtures may model every capability without implying that a live provider supplies it.

## 12. Presentation architecture

Momentum, Graham, and Free Cash Flow & Earnings Growth share a concise, detailed, diagnostic, and JSON visual grammar without sharing a forced generic result object. Graham presenters only format and explain supplied typed assemblies and calculation results: they perform no financial arithmetic, input resolution, provider or cache access, or assumption generation. Presentation-model validation requires each retained input's `as_of` to equal the presentation `as_of`; it does not impose an additional cross-input age or freshness rule. Presenters preserve source provenance across cache use and render only resolver events actually observed. Required-input, provider, ticker-verification, and calculation failures use the same typed presentation boundary as success.

Best-effort security identity is resolved outside the presenter and passed as nullable presentation metadata. A resolved name produces `Instrument Name (TICKER) — Analysis`; unavailable or failed identity resolution falls back to ticker-only output and cannot change financial semantics.

JSON uses the Section 8.4 contract. Operational logs are separate from investor output; detailed terminal output uses fixed labels rather than tables.

The existing Momentum analysis strategy retains `None` and JSON `null` for unavailable moving-average or crossover metrics, never `NaN`; insufficient history retains an `UNKNOWN` signal. Its market source, freshness, and currency remain execution/presentation context rather than fields added to the pure `MomentumMetrics` result.

## 13. Evolution and compatibility

The identifiers `graham_number` and `graham_growth_value` are stable. A materially different formula receives a new method identifier and result type; it does not redefine either method. An approved AAA-yield series changes routing and provenance, not the method or JSON version, if public shape and meaning are unchanged.

Breaking public JSON changes increment `schema_version`. Version 2 adds the nullable security-identity snapshot deliberately; it does not change either Graham formula or result type. New enum values require compatibility review and exhaustive dispatch handling. Cache-schema versions evolve independently. Recorded outputs retain their original method, assumptions, provenance, and versions.

## 14. Deterministic fixtures and current verification

The implemented deterministic suite uses fixtures rather than live provider or language-model calls. Its coverage includes:

- both formulas and their principal finite, non-positive, boundary, and invalid-input cases;
- override, cache, and provider resolution, including historical eligibility and provenance lineage;
- cache schema isolation, time-to-live behavior, and rejection of unsuitable cached values;
- the command-line method and provider/basis routes, missing assumptions, incompatible options, and provider-backed ticker verification;
- direct and derived common shares, approved zero-preferred-share inference shapes, and blocking, conflicting, future, and ambiguous SEC evidence;
- optional quote failure and cross-currency comparison suppression; and
- concise hierarchy, detailed and diagnostic rendering, JSON schema version and null handling, and selected warning and limitation behavior.

The pre-Golden hardening suite locks result invariants, status labels, typed failure paths, quote behavior, supported routing, compatibility handling, presentation order, warnings, and limitations. Slice F-1 adds deterministic coverage for available/unavailable/non-company identity, provider failure, all strategy presentation modes, explicit JSON null/version behavior, and preservation of calculation semantics.

At the completion checkpoint, the implementation passed the repository's formatting, linting, strict type-checking, test, coverage, and documentation gates.

## 15. Scope boundaries

This design excludes the Free Cash Flow & Earnings Growth analysis strategy; strategy evaluation; durable watchlists, Analysis Runs, batch refresh, cache storage and migrations; background or proactive operation; full-screen interfaces and executive reports; generated or unapproved third-party growth estimates; speculative generic strategy frameworks; complete defensive-investor qualification; and investment recommendations.

A future unified `financial-agents analyze TICKER` command may combine default deterministic analyses with bounded language-model synthesis. Durable Analysis Runs may later preserve and render these typed results. Neither capability changes the contracts defined here.
