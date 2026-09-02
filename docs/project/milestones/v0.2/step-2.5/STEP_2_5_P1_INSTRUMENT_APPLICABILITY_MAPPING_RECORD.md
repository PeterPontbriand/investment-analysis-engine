# P1 Instrument Applicability Mapping Record

**Status:** P1-A through P1-C complete and approved; consumed by the Step 2.5 Golden implementation<br/>
**Prepared:** 2026-08-30  
**Governing plan:** [Milestone v0.2 Implementation Plan](../IMPLEMENTATION_PLAN.md#450-p1--pre-golden-instrument-applicability-hardening)  
**Slice plan:** [Step 2.5 Golden Suite Slice Plan](STEP_2_5_GOLDEN_SUITE_SLICE_PLAN.md#5a-approved-prerequisite--p1-instrument-applicability-hardening)  
**Predecessor identity contract:** [Step 2.4 provider mapping record](../step-2.4/STEP_2_4_PROVIDER_MAPPING_RECORD.md#31-security-identity)

## 1. Approval and current decision

The human approved the provider mapping and contract shape on 2026-08-30, then approved the focused P1-B contracts and authorized P1-C. The current decision is whether to approve the completed P1-C strategy, presentation, CLI/handler, schema, and regression work summarized in Section 13 before Golden Case model implementation begins.

The proposal deliberately separates three questions:

1. **Security identity:** What current descriptive name, venue, and stable identifiers did a provider return?
2. **Instrument kind:** What raw instrument classification did a provider return, and which normalized project kind—if any—does the reviewed mapping establish?
3. **Strategy applicability:** Given affirmative normalized kind evidence, does one named analytical method apply?

Missing facts, missing identity, unknown kind, provider failure, and an invalid ticker are not interchangeable states.

## 2. Evidence base

### 2.1 Authoritative implementation sources

The project currently pins `yfinance == 1.6.0`. The following upstream yfinance sources were reviewed on 2026-08-30:

1. [`Ticker.info` public API](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Ticker.info.html) exposes the general metadata dictionary used by the existing `YFinanceClient.resolve_security_identity(...)` adapter.
2. [yfinance quote-summary module declarations](https://github.com/ranaroussi/yfinance/blob/1.6.0/yfinance/const.py) list `quoteType` as a supported Yahoo quote-summary module.
3. [yfinance 1.6.0 quote scraper](https://github.com/ranaroussi/yfinance/blob/1.6.0/yfinance/scrapers/quote.py) requests `financialData`, `quoteType`, `defaultKeyStatistics`, `assetProfile`, and `summaryDetail`, merges the additional quote response, and flattens the returned metadata into `Ticker.info`.
4. The same source implements `FastInfo.quote_type` from history metadata `instrumentType`. P1 does not select that second path because the current identity adapter already calls `Ticker.info`; using both would create another metadata path and may add network work without improving the evidence required here.
5. [yfinance FundsData documentation](https://ranaroussi.github.io/yfinance/reference/api/yfinance.scrapers.funds.FundsData.html) explicitly describes ETF and mutual-fund data as using the `quoteType` module, corroborating its role as instrument classification rather than a financial calculation input.

Yahoo Finance is the underlying upstream data source, but this project consumes the yfinance adapter contract. The raw provider value and yfinance version therefore remain visible in the mapping record and deterministic fixtures. This evidence does not turn Yahoo metadata into permanent identity or historical `as_of` proof.

### 2.2 Installed-source observations

The installed `yfinance 1.6.0` source confirms:

- `Ticker.info` is cached only on the lifetime of that `Ticker`/quote object after its first fetch;
- the project's current adapter constructs a new `yf.Ticker(...)` for each identity request and therefore has no project-owned request cache;
- `Ticker.info` can perform both a quote-summary request and an additional quote request;
- `info["symbol"]` is set to the requested symbol during yfinance response assembly and is not independent ticker-validity evidence; and
- `quoteType` is a metadata field, not proof that required financial facts exist.

P1-B should therefore reuse one YFinance metadata dictionary per client/ticker during one analysis run and must not use the returned `symbol` field as an independent validation result.

### 2.3 Representative live observations

A read-only live check was run on 2026-08-30 through the repository's installed `yfinance 1.6.0`, using a repository-local temporary yfinance cache. Only identity/classification fields were retained for this record:

| Requested symbol | `quoteType` | `longName` | `fullExchangeName` | Interpretation |
| :--- | :--- | :--- | :--- | :--- |
| `FLSW` | `ETF` | `Franklin FTSE Switzerland ETF` | `NYSEArca` | Affirmative ETF evidence and a non-company instrument name |
| `AAPL` | `EQUITY` | `Apple Inc.` | `NasdaqGS` | Affirmative Yahoo equity evidence |
| `BTC-USD` | `CRYPTOCURRENCY` | `Bitcoin USD` | `CCC` | Affirmative non-company/non-ETF evidence already supported by Momentum presentation |

These observations are research evidence, not Golden fixtures or production cache data. P1-B tests must use minimal deterministic metadata dictionaries and make no live request.

## 3. Proposed normalized vocabulary

Add a provider-neutral string enum with only the kinds supported by the reviewed evidence:

| Normalized `InstrumentKind` | Exact Yahoo `quoteType` | P1 applicability consequence |
| :--- | :--- | :--- |
| `equity` | `EQUITY` | No new shortcut; continue the selected strategy's existing resolution/calculation path |
| `etf` | `ETF` | Momentum remains applicable; both Graham methods and company-level FCF Growth are `not_applicable` |
| `cryptocurrency` | `CRYPTOCURRENCY` | No new P1 shortcut; continue existing behavior, which may resolve usable Momentum data or classified financial-input unavailability |

Do not add an `unknown` enum member. Absence of normalized evidence is represented by `None`, preserving the distinction between “not measured/resolved” and an affirmative provider category.

For any other nonblank Yahoo `quoteType`, retain the exact whitespace-normalized provider value but leave normalized kind as `None`. Expanding the mapping requires another evidence review; it is not achieved by adding a broad `other` bucket. A missing, non-string, or blank `quoteType` produces no kind evidence.

Mapping uses the exact reviewed provider strings after surrounding-whitespace normalization. It does not infer kind from `longName`, `shortName`, `displayName`, exchange, ticker punctuation, SEC fact availability, or another provider's result.

## 4. Proposed provider-neutral contracts

### 4.1 Preserve `SecurityIdentity`

Keep the existing `SecurityIdentity` value as one provider's descriptive snapshot. Do not attach Yahoo kind fields directly to an SEC identity or rewrite its `provider_id`; doing so would falsely imply that one provider supplied all fields.

### 4.2 Add `InstrumentKindEvidence`

Add one immutable value containing:

- normalized ticker;
- `kind: InstrumentKind | None`;
- nonblank raw `provider_value`;
- provider ID; and
- timezone-aware `resolved_at`.

`kind=None` with a nonblank raw value is valid and means the provider returned an unreviewed classification. A normalized kind requires the exact raw provider value approved in Section 3 for that provider.

### 4.3 Add an optional provider capability

Keep `SecurityIdentityProvider` unchanged and add a narrow optional `InstrumentKindProvider` capability. YFinance implements both capabilities from the same request-scoped metadata retrieval. SEC continues to provide descriptive ticker-title/CIK identity only; P1 does not claim that an SEC ticker entry establishes operating-company equity or ETF kind.

Provider errors are classified and retained as diagnostics. They do not produce kind evidence and do not alter otherwise usable analysis semantics.

### 4.4 Compose an `InstrumentProfile`

Compose, rather than merge, the independently sourced evidence:

- normalized ticker;
- best available `SecurityIdentity | None` under explicit candidate precedence;
- `InstrumentKindEvidence | None`; and
- ordered resolution diagnostics sufficient to distinguish unsupported capability, unavailable metadata, and provider error.

The profile may legitimately contain an SEC identity and Yahoo kind evidence. Each nested value retains its own provider and resolution time. This field-level provenance is the stable seam that P2 can later persist without relabeling evidence or changing strategy calculators.

## 5. Request-scoped composition and cost policy

Production composition for Graham and company-level FCF Growth uses explicit candidates:

1. retain identity from the selected financial-fact provider when available;
2. consult the injected YFinance profile capability for normalized instrument kind and for identity only when no higher-precedence identity is available;
3. call each capability/provider at most once during one analysis run; and
4. ensure YFinance identity and kind access share one lazily fetched metadata dictionary for that client/ticker.

P1 intentionally accepts one current Yahoo metadata retrieval per direct Graham/FCF run when the injected production classifier is enabled. That lookup establishes applicability before expensive company-fact resolution and prevents known ETFs from being processed as operating companies. It remains fail-open: when Yahoo is unavailable or returns no reviewed kind, the selected strategy follows its existing resolution path.

There is no cross-process or durable cache in P1. P2 after Step 3.1 owns persistent instrument profiles, freshness, invalidation, disagreement, and ticker-reuse policy behind the same provider-neutral profile seam.

Deterministic fixture composition supplies profile evidence directly and never constructs the live YFinance provider.

## 6. Strategy applicability mapping

| Strategy/method | `etf` | `equity` | `cryptocurrency` or unknown |
| :--- | :--- | :--- | :--- |
| Momentum | Continue existing market-history analysis | Continue | Continue existing behavior |
| Graham Number | Native `not_applicable` | Continue existing input resolution | Continue existing input resolution |
| Graham growth value | Native `not_applicable` | Continue existing input resolution | Continue existing input resolution |
| Company-level FCF Growth | Native `not_applicable` | Continue existing annual-fact resolution | Continue existing annual-fact resolution |

Only the `etf` column changes P1 control flow. No absent/unknown kind is interpreted as equity. No P1 path automatically invokes the future ETF aggregate FCF strategy.

## 7. Result, presentation, and process semantics

P1-B/P1-C should preserve strategy-native results:

- Graham returns its existing method-specific result/status vocabulary with `CalculationStatus.NOT_APPLICABLE` and a nonblank ETF applicability reason. It performs no Graham calculation and does not request a current quote.
- FCF Growth returns its existing typed result with `execution_status=not_applicable`, `classification=indeterminate`, an explicit ETF applicability reason/code, no annual observations, and coherent unavailable/not-applicable metric states. It performs no annual company-fact resolution.
- Momentum is unchanged except that the composed profile may be passed through its presentation boundary consistently.

A successfully established `not_applicable` result returns direct-CLI exit code zero. Invalid arguments, unresolved required inputs, and provider/execution failures remain non-zero.

Every concise/details/diagnostics/JSON path retains an available identity heading. Graham concise failure paths must no longer bypass that heading. Generic `input_unavailable` and `provider_error` text must not instruct the user to verify the ticker; P1 approves no provider shape as affirmative invalid-ticker evidence.

## 8. Presentation schema proposal

Keep the existing `security_identity` object and its field meanings unchanged. Add a sibling nullable `instrument_kind` evidence object containing:

- `kind` (normalized string or null);
- `provider_value`;
- `provider_id`; and
- `resolved_at`.

Increment investor-presentation schema versions deliberately:

- Momentum: 2 → 3;
- Graham Number and Graham growth value: 2 → 3; and
- FCF Growth presentation: 3 → 4.

The FCF typed-result schema advances from 2 to 3 because P1-C adds a new machine-readable `instrument_kind_not_applicable` reason and retains the composed profile on the native result. Its method version remains 2 because no financial formula changes. The investor-presentation versions advance exactly as proposed: Momentum and both Graham methods from 2 to 3, and FCF Growth from 3 to 4.

Step 3.4 persists both evidence blocks used by the Analysis Run. P2 may introduce a repository record that composes them, but historical views continue to render the stored snapshots rather than current provider state.

## 9. Deterministic evidence required in P1-B/P1-C

At minimum, tests must prove:

- exact mappings for `ETF`, `EQUITY`, and `CRYPTOCURRENCY`;
- raw retention plus normalized `None` for an unreviewed nonblank kind;
- missing/blank/malformed kind remains absent;
- timestamps and provider/ticker identity are validated;
- SEC identity and Yahoo kind coexist without provenance rewriting;
- candidate precedence and one call per provider/capability;
- one shared YFinance metadata retrieval supplies identity and kind during a run;
- provider error leaves kind unknown and analysis fail-open;
- known ETF short-circuits both Graham methods and company-level FCF before financial-fact/quote calls;
- unknown kind follows existing resolution behavior;
- Momentum ETF behavior remains unchanged;
- all presentation modes and JSON schemas retain identity/kind evidence coherently;
- successful `not_applicable` uses exit code zero; and
- deterministic tests make no live provider or LLM calls.

## 10. Explicit exclusions

P1 does not approve:

- any additional Yahoo kind mapping;
- ticker validity based on `Ticker.info`, its injected `symbol`, or missing metadata;
- SEC ticker membership as instrument-kind evidence;
- durable caching, SQLite, TTL, invalidation, or provider-disagreement policy;
- ETF holdings retrieval or look-through calculation;
- automatic substitution of an aggregate ETF strategy;
- changes to Momentum, Graham, or FCF financial formulas; or
- use of production provider responses as Golden fixture truth.

Those persistence and aggregate-strategy concerns remain P2 after Step 3.1.

## 11. P1-A approval gate

Human approval should confirm or amend:

1. the three-value normalized vocabulary and exact Yahoo mappings in Section 3;
2. separate `SecurityIdentity`, `InstrumentKindEvidence`, and composed `InstrumentProfile` provenance;
3. ordered SEC/Yahoo identity precedence and one request-scoped Yahoo metadata fetch;
4. ETF-only applicability control flow in Section 6;
5. native result, exit-code, and investor-message behavior in Section 7; and
6. the presentation schema-version proposal in Section 8.

**Decision:** Approved by the human on 2026-08-30 without amendment. P1-B was authorized; the expanded mappings and P2 concerns remain excluded.

## 12. P1-B focused contract review

P1-B implements the approved provider-neutral seam without changing strategy, CLI, result, or presentation behavior:

- `src/data/instrument_profile.py` adds the reviewed three-value `InstrumentKind`, separate immutable raw/normalized `InstrumentKindEvidence`, its narrow optional provider capability, stable nullable evidence serialization, an immutable composed `InstrumentProfile`, and ordered classified diagnostics;
- `compose_instrument_profile(...)` accepts an explicit ordered identity-candidate tuple plus one optional kind candidate, rejects duplicate identity provider IDs, stops identity resolution at the first success, resolves kind independently, and converts unsupported, unavailable, mismatched, and failed optional evidence into diagnostics;
- YFinance maps only exact whitespace-normalized `EQUITY`, `ETF`, and `CRYPTOCURRENCY` values, retains an unreviewed nonblank raw value with normalized kind `None`, and returns no evidence for missing, blank, or malformed `quoteType`;
- one lazy YFinance metadata snapshot, including a failed lookup, is retained per client/ticker and supplies both identity and kind so profile composition does not duplicate `Ticker.info` retrieval; and
- the YFinance financial-facts adapter and production façade expose the narrow kind capability while SEC remains identity-only.

Deterministic focused tests cover exact and unknown mappings, absent/malformed evidence, timezone and mapping validation, frozen serialization, SEC/Yahoo provenance coexistence, identity precedence, unsupported and provider-error diagnostics, duplicate-candidate rejection, one Yahoo metadata retrieval on success and failure, and production-façade delegation. They make no network or LLM calls.

P1-B deliberately does **not** wire the profile into Graham, FCF Growth, Momentum, CLI, tool handlers, typed results, report presenters, JSON schema versions, or exit-status behavior. Those changes and the complete repository quality gate remain P1-C work after explicit P1-B approval.

**Decision:** Approved by the human on 2026-08-30. P1-C strategy, presentation, CLI/handler, and full-gate work was authorized.

## 13. P1-C implementation and final review

P1-C applies the approved profile seam without changing financial formulas:

- direct CLI requests and dependency-injected production handlers resolve one request-scoped profile and pass it through each strategy's existing service/analyzer boundary;
- affirmative ETF evidence short-circuits both Graham methods before company inputs or current quotes and short-circuits company-level FCF Growth before annual fact resolution;
- Graham returns its native `CalculationStatus.NOT_APPLICABLE`; FCF returns `execution_status=not_applicable`, `classification=indeterminate`, the new `instrument_kind_not_applicable` reason code, empty company history, and coherent not-applicable metrics;
- Momentum calculation behavior is unchanged and merely retains the same composed profile for presentation;
- equity, unreviewed kind, absent kind, and classifier provider-error profiles remain fail-open and continue through the established resolver path;
- concise output retains the available instrument name for successful and unsuccessful results, details/diagnostics retain separate identity and kind provenance, and JSON exposes nullable sibling `security_identity` and `instrument_kind` evidence;
- a successfully established `not_applicable` result returns direct-CLI exit code zero, while input/provider failures remain non-zero; and
- generic unavailability messages no longer advise users to verify a ticker without affirmative invalid-symbol evidence.

The version decisions are FCF native result schema 3 with unchanged method version 2, Momentum/Graham presentation schema 3, and FCF presentation schema 4. Deterministic fixtures provide profile evidence directly; tests perform no live provider or LLM calls.

Focused verification covers exact profile behavior, ETF short-circuiting, supported-equity/unknown/provider-error fail-open behavior, production-handler consistency, unchanged Momentum output, all affected presentation evidence, CLI status and headings, and absence of unsupported ticker-verification advice. The focused P1-C selection passed Ruff, formatting, strict mypy, and 89 deterministic tests. The complete repository gate then passed on 2026-08-30: repository-wide Ruff and format checks, strict mypy over 151 source/test files, and all 972 tests with 86% line coverage. Final P1 approval remains required before Slice A1.
