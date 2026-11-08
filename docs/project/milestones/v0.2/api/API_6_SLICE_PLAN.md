# API.6 — Slice Plan: Term References and Help Endpoints

Splits [API.6](API_CONTRACT_AND_SLICE_PLAN.md#api6a--term-references) in two ([T1](#t1-api6-is-split-in-two-2026-11-07)).
The first gives every label, status and code the API returns a glossary term and a conformance test that fails the gate
when one is missing. The second serves the help content over HTTP and chooses the locale.

## 1. At a glance

- **What this plan does:**
  - API.6a names, for every value of every closed code set in `schemas/openapi.json`, for every headline cell, strategy
    and selection field, the glossary term that explains it, and tests that fail on a value with no term;
  - API.6b serves the help bundle (`GET /v1/help`, `GET /v1/help/terms/{id}`, `GET /v1/help/documents/{id}`), serves the
    tables as `GET /v1/help/references`, lists the locales in the information document and negotiates `Accept-Language`.
- **What it does not do:** add a financial rule, change a stored shape, a formula or a classification, change existing
  command-line text, or add a dependency.
- **Rules every slice follows:**
  - a value maps to exactly one term, and a value gets its own term when what the person should conclude or do differs
    ([T3](#t3-how-values-map-to-terms-2026-11-07));
  - the tables sit beside the code sets they explain and `help` stays at layer 0 with no imports
    ([T4](#t4-where-the-tables-live-2026-11-07));
  - the managed quality gate, with the Python 3.14 second pass, after each slice, and the project owner's approval before
    the next slice starts.
- **Where the history lives:** decisions T1 to T15 are in [Appendix A](#appendix-a-decision-records), approved by the
  project owner on 2026-11-07. API.6a implements T1 to T10 and the parts of T15 its changes touch; API.6b implements T11
  to T14 and the rest of T15.

## 2. Sequence and status

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| API.6a | [Term references](#api6a--term-references) | Complete | 2026-11-07 |
| API.6b | [Help endpoints and locales](#api6b--help-endpoints-and-locales) | Next | |

## 3. The slices

### API.6a — Term references

- **Problem:** no API document says which term explains a label, status or code, so a GUI cannot explain what it shows,
  and a new strategy could add an unexplained column.
- **Decision:**
  - every value of every closed code set, and every label, names a term, with four exemptions and a test that walks
    `openapi.json` ([T2](#t2-what-must-name-a-term-2026-11-07), [T3](#t3-how-values-map-to-terms-2026-11-07));
  - the tables are declared beside their code sets ([T4](#t4-where-the-tables-live-2026-11-07)) and every user-facing
    inline literal becomes a named component ([T5](#t5-how-the-tables-are-served-2026-11-07));
  - headline cells, strategies and selection fields carry a term
    ([T6](#t6-headline-cells-2026-11-07), [T7](#t7-strategies-2026-11-07), [T8](#t8-selection-fields-2026-11-07));
  - "glossary terms" is an edit site ([T9](#t9-edit-site-2026-11-07)), new entries follow the entry rules, and an orphan
    check keeps every served term reachable ([T10](#t10-new-entries-and-the-orphan-check-2026-11-07)).
- **Scope:** the term tables in `core`, `analysis`, `data`, `api` and each strategy's `vocabulary.py`; the descriptor's
  `term`, `headline_terms` and `code_terms`; `HeadlineCell.term`; the runs-compare and strategies documents; `x-term` on
  every selection field; named components for the inline literals; the glossary entries and the regenerated bundle; the
  conformance tests and the edit site; the generator and its tests; Architecture §13; this plan and the contract.
- **Branch:** `feat/api-term-references`.
- **Detail:** [Implementation record](#31-api6a-implementation-record) and [the T3 mapping](#32-the-t3-mapping).

### API.6b — Help endpoints and locales

- **Problem:** the help bundle is packaged but nothing serves it, a client cannot ask which term a value maps to, and
  engine text has one language.
- **Decision:**
  - three read endpoints over the bundle and the tables, answering an unknown id with a 404
    ([T11](#t11-api6b-help-endpoints-2026-11-07), [T5](#t5-how-the-tables-are-served-2026-11-07));
  - the information document lists the locales, the bundle has one file per locale, and `api` negotiates
    `Accept-Language` itself ([T12](#t12-api6b-2026-11-07), [T13](#t13-api6b-bundle-per-locale-2026-11-07),
    [T14](#t14-api6b-negotiation-2026-11-07));
  - the client reference gains help, references and locale sections, and §13 changes with the `api` import of `help`
    ([T15](#t15-docs-2026-11-07)).
- **Scope:** the help endpoints and their documents; `GET /v1/help/references`, built from the tables API.6a declares;
  `InfoDocument.locales`; `LOCALES`, `help_bundle.en.json` and `load_help_bundle(locale)`; `Accept-Language` negotiation
  and the `Content-Language` and `Vary` headers; `docs/user/API.md`; Architecture §13; `openapi.json`.
- **Branch:** `feat/api-help`.
- **Detail:** ⚠ no slice plan yet

### 3.1 API.6a implementation record

What changed, by area:

- **Descriptor ([T1](#t1-api6-is-split-in-two-2026-11-07), [T7](#t7-strategies-2026-11-07)):** `StrategyDescriptor` gains
  `term`, `headline_terms` and `code_terms`, filled for every declared strategy from its `vocabulary.py`. The two mappings
  are left out of the descriptor's hash, so a descriptor stays usable as a dictionary key. Nothing discovers or registers
  anything.
- **Term tables ([T4](#t4-where-the-tables-live-2026-11-07)):** each table is a read-only mapping from a value to a term id,
  declared beside its code set: calculation status, metric status, reason code, failure code, failure category, provider
  failure kind, provider-check verdict and trend status in `core`; run outcome and the industry-class, share-count and
  split-adjustment sets, and the price-comparison status, in `analysis`; the input-source, reporting-period,
  accounting-scope, capital-expenditure-sign, instrument-kind and quote-freshness sets in `data`; the refresh event kind in
  `api`; the headline-unavailable reasons in `workspace_documents`; and the cell status in `reporting`, built from the
  two status tables. Each strategy's own sets are in its `vocabulary.py` under `CODE_TERMS`, keyed by component name.
- **Named components ([T5](#t5-how-the-tables-are-served-2026-11-07)):** the inline literals the walk found are now `type`
  aliases, which Pydantic emits as components: the cell status, the reasons a headline is unavailable, the failure
  category, the price-comparison status, the quote-freshness status, the refresh event kind and the Graham Growth EPS basis.
  `scripts/strategy_conformance.py` accepts a type alias as a form type. `openapi.json` and the schemas are regenerated.
- **Headline cells ([T6](#t6-headline-cells-2026-11-07)):** `HeadlineCell.term` is required and rejects a blank term. Each
  headline function takes the term of each cell from its strategy's `HEADLINE_TERMS`. `CompareCellDocument.term` and
  `CompareStrategyDocument.term` are added, the latter null for a strategy that is no longer declared, and the document's
  `schema_version` is 3. The text rendering is unchanged. The stored expected output of `runs compare --json` changes by
  the added fields and the version only.
- **Strategies document ([T7](#t7-strategies-2026-11-07)):** `StrategyItem.term` is added and the document's
  `schema_version` is 2.
- **Selection fields ([T8](#t8-selection-fields-2026-11-07)):** every selection field, the fields of a nested model
  included, carries `json_schema_extra={"x-term": ...}`. The selection schema keeps the term on `as_of`, which it
  rebuilds. The persisted selection shape is unchanged, so no version moves. The Graham Growth EPS basis is now a `$ref`
  in the selection schemas, which only changes how its two values are described.
- **Conformance ([T2](#t2-what-must-name-a-term-2026-11-07), [T9](#t9-edit-site-2026-11-07)):**
  `tests/test_term_references.py` walks `openapi.json`, resolves each enumeration to its table through the hand-written
  `SHARED_CODE_TERMS` in `tests/_term_tables.py` and the descriptors' `code_terms`, and fails on a value with no term, a
  term the bundle does not hold, a table that names a component the description does not hold, and an enumeration that
  is neither named nor exempt. The four exemptions are a constant with a reason each. The same file checks each
  strategy's headline against its `headline_terms` and the bundle, each strategy term and selection `x-term` against the
  bundle, the shared meaning of the two status types, and the orphan rule. The "glossary terms" site (`glossary-terms`,
  kind `reviewed`) has its check, `site_glossary_terms`, in `scripts/strategy_conformance.py`.
- **Glossary ([T3](#t3-how-values-map-to-terms-2026-11-07), [T10](#t10-new-entries-and-the-orphan-check-2026-11-07)):** 61
  new entries: the new section "Outcomes, statuses and reasons" holds 42, and 19 are in the
  sections of the concept they explain. Fourteen existing entries gained a paragraph: the Crossover entry names its three
  states, and thirteen gained a "Related terms" paragraph so that no served term is an orphan. The help bundle is
  regenerated.
- **Generator:** the generated descriptor carries `term="<alias>-strategy"`, `headline_terms` and `code_terms`; the
  generated `vocabulary.py` declares both as empty; the generated selection carries the two `x-term` values; the
  end-to-end test writes the throwaway strategy's term, its headline term and its glossary entry by patch.
- **Architecture:** the "Owns" cells of `core`, `analysis`, `data`, `reporting`, `strategies`, `strategy_wiring` and `api`
  say they hold term tables. No import between units is added, so the Imports cells are unchanged.
- **Edit sites:** the "glossary terms" site is in `scripts/strategy_sites.toml` and the edit-site table is regenerated.
  "Changing what every strategy provides" in `docs/TOOL_DEVELOPMENT.md` missed two files that this change had to touch,
  and now lists them: `DESCRIPTOR_FIELDS` in `scripts/strategy_conformance.py`, and the specimen's `vocabulary.py` and
  `selection.py`. The workflow table of reviewed sites gains a `glossary-terms` row.

Judgment calls, each a place where the decisions left a choice:

- **Entries reused.** A value is mapped to an existing entry when that entry already explains it: the trend status to
  `momentum-states`, the FCF classification to `fcf-classification`, the classification basis, forward policy, completeness
  and unavailable test to their entries, the industry class to `industry-class`, and the crossover states to `crossover`,
  whose body now names the three. This follows T3's reading that values which differ only in detail share an entry that
  explains each.
- **`not_applicable` has one term.** The run outcome, the calculation status and the metric status each map `not_applicable`
  to the existing `not-applicable` entry. A provider failure code, a verdict and a failure kind share the term of the
  provider failure kind, and the failure codes `provider_error` and `invalid_input` share the status terms of the same names.
- **Grouped reasons.** The 27 reason codes map to 14 terms and the 36 failure codes to 20. The grouping is in the table
  of [the mapping](#32-the-t3-mapping); `database_*` share `failure-database`, and the request-check codes share
  `failure-request-refused`.
- **Some sets keep one entry for all values.** The values of the input source, reporting period, accounting scope,
  capital-expenditure sign, instrument kind, share-count basis, split-adjustment window, price-comparison status,
  quote-freshness, refresh event, headline-unavailable, growth trend, price basis and trend relationship differ in detail
  of one concept, so each set has one entry that explains each value.
- **Cells.** The FCF Growth CAGR cell maps to `cagr` whichever basis its label names, because a cell's term is by key and
  the label changes with the basis. `policy` names the strategy's term, `currency` has the new `reporting-currency` entry,
  and the three overrides name `override`.
- **Named components by alias.** `type` aliases keep the runtime values as plain strings and add a component name, so no
  stored or serialized value changes. The alternative, an enumeration class, would change the types of fields that other
  code compares with strings.
- **The site check reads the glossary.** `served_term_ids` parses the user glossary of the context's root, outside excluded
  sections, instead of loading the packaged bundle, so the generator's copy of the repository is checked against its own
  glossary. `SiteContext.terms` lists terms a context treats as served though the glossary lacks them, which only the
  specimen uses.
- **Where the tables are assembled.** The hand-written mapping from component name to shared table is test support
  (`tests/_term_tables.py`). API.6b needs it at run time for `GET /v1/help/references` and moves it into `api`.
- **Orphans.** Forty-one served terms were neither named by a table, cell, strategy or selection field nor linked from
  served content. Each is now linked from the entry of the concept it belongs to, in a "Related terms" paragraph, and no
  claim about how the terms relate was added.
- **Date.** The sequence tables date API.6a with the day the branch was finished, 2026-11-07; the pull request, when
  opened, keeps that date unless it opens later.

Noticed for later slices:

- `TrendStatus` in `core/constants.py` carries French display names beside the English ones. It is a locale producer of the
  kind [A.5](API_CONTRACT_AND_SLICE_PLAN.md#a5-locale-choice-2026-11-07) lists in its precondition.
- A headline cell's label, a presenter's text and every failure message are English constants today. API.6b adds
  `Content-Language`, which is true only while they stay so.
- 21 served terms have no body, only a definition, so a client must render an empty `body` as nothing.
- A term table cannot yet say which terms a value's entry shares; `GET /v1/help/references` returns the term id and the
  client groups equal ids if it wants to.
- `SHARED_CODE_TERMS` must gain a row whenever a shared code set is added to the API; the walk fails until it does.

### 3.2 The T3 mapping

Every value of every closed code set in `schemas/openapi.json` maps to exactly one term. Component names are the
OpenAPI components that carry the set; the Graham Growth and FCF Growth selection sets appear twice because the
description names them both as a document component and inside the selection schema.

| Code set (component) | Value | Term |
| :--- | :--- | :--- |
| `AccountingScope` | `consolidated` | `accounting-scope` |
| `AccountingScope` | `parent` | `accounting-scope` |
| `AccountingScope` | `segment` | `accounting-scope` |
| `AdjustmentWindow` | `count_to_price` | `split-adjustment-window` |
| `AdjustmentWindow` | `price_to_adjustment` | `split-adjustment-window` |
| `CalculationStatus` | `ok` | `status-ok` |
| `CalculationStatus` | `not_applicable` | `not-applicable` |
| `CalculationStatus` | `invalid_input` | `status-invalid-input` |
| `CalculationStatus` | `input_unavailable` | `status-input-unavailable` |
| `CalculationStatus` | `provider_error` | `status-provider-error` |
| `CapitalExpenditureSign` | `positive_expenditure` | `capex-sign-convention` |
| `CapitalExpenditureSign` | `negative_cash_outflow` | `capex-sign-convention` |
| `CellStatusValue` | `ok` | `status-ok` |
| `CellStatusValue` | `not_applicable` | `not-applicable` |
| `CellStatusValue` | `invalid_input` | `status-invalid-input` |
| `CellStatusValue` | `input_unavailable` | `status-input-unavailable` |
| `CellStatusValue` | `provider_error` | `status-provider-error` |
| `CellStatusValue` | `unavailable` | `status-unavailable` |
| `CheckOutcome` | `pass` | `test-result` |
| `CheckOutcome` | `fail` | `test-result` |
| `CheckOutcome` | `unavailable` | `unavailable-test` |
| `Classification` | `pass` | `fcf-classification` |
| `Classification` | `fail` | `fcf-classification` |
| `Classification` | `indeterminate` | `fcf-classification` |
| `Completeness` | `complete` | `complete-and-partial-score` |
| `Completeness` | `partial` | `complete-and-partial-score` |
| `CrossoverState` | `bullish_crossover` | `crossover` |
| `CrossoverState` | `bearish_crossover` | `crossover` |
| `CrossoverState` | `no_new_crossover` | `crossover` |
| `FCFClassificationBasis` | `total_fcf` | `classification-basis` |
| `FCFClassificationBasis` | `fcf_per_share` | `classification-basis` |
| `FCFGrowthSelection.FCFClassificationBasis` | `total_fcf` | `classification-basis` |
| `FCFGrowthSelection.FCFClassificationBasis` | `fcf_per_share` | `classification-basis` |
| `FCFGrowthSelection.ForwardPolicy` | `display_only` | `forward-policy` |
| `FCFGrowthSelection.ForwardPolicy` | `confirmation` | `forward-policy` |
| `FCFGrowthSelection.ForwardPolicy` | `hard_gate` | `forward-policy` |
| `FCFGrowthSelection.HistoricalHorizon` | `longest_available` | `historical-horizon` |
| `FCFGrowthSelection.HistoricalHorizon` | `3` | `historical-horizon` |
| `FCFGrowthSelection.HistoricalHorizon` | `4` | `historical-horizon` |
| `FCFGrowthSelection.HistoricalHorizon` | `5` | `historical-horizon` |
| `FailureReasonCode` | `execution_error` | `failure-execution-error` |
| `FailureReasonCode` | `historical_quality` | `failure-historical-quality` |
| `FailureReasonCode` | `provider_error` | `status-provider-error` |
| `FailureReasonCode` | `provider_unreachable` | `provider-unreachable` |
| `FailureReasonCode` | `provider_rate_limited` | `provider-rate-limited` |
| `FailureReasonCode` | `provider_unexpected_response` | `provider-unexpected-response` |
| `FailureReasonCode` | `provider_no_data` | `provider-no-data` |
| `FailureReasonCode` | `configuration_error` | `failure-configuration-error` |
| `FailureReasonCode` | `no_eligible_observations` | `failure-no-eligible-observations` |
| `FailureReasonCode` | `invalid_input` | `status-invalid-input` |
| `FailureReasonCode` | `invalid_parameter` | `failure-invalid-parameter` |
| `FailureReasonCode` | `database_upgrade_required` | `failure-database` |
| `FailureReasonCode` | `database_incompatible_schema` | `failure-database` |
| `FailureReasonCode` | `database_busy` | `failure-database` |
| `FailureReasonCode` | `database_permission_denied` | `failure-database` |
| `FailureReasonCode` | `database_invalid_file` | `failure-database` |
| `FailureReasonCode` | `database_io_error` | `failure-database` |
| `FailureReasonCode` | `database_resources_unavailable` | `failure-database` |
| `FailureReasonCode` | `database_initialization_failed` | `failure-database` |
| `FailureReasonCode` | `database_migration_failed` | `failure-database` |
| `FailureReasonCode` | `invalid_stored_run` | `failure-stored-data-unreadable` |
| `FailureReasonCode` | `unsupported_run_version` | `failure-unsupported-run-version` |
| `FailureReasonCode` | `watchlist_not_found` | `failure-not-found` |
| `FailureReasonCode` | `watchlist_entry_not_found` | `failure-not-found` |
| `FailureReasonCode` | `watchlist_empty` | `failure-watchlist-empty` |
| `FailureReasonCode` | `watchlist_name_conflict` | `failure-name-conflict` |
| `FailureReasonCode` | `analysis_run_not_found` | `failure-not-found` |
| `FailureReasonCode` | `stored_selection_unreadable` | `failure-stored-data-unreadable` |
| `FailureReasonCode` | `unsupported_projection` | `failure-stored-data-unreadable` |
| `FailureReasonCode` | `not_authenticated` | `failure-request-refused` |
| `FailureReasonCode` | `host_not_allowed` | `failure-request-refused` |
| `FailureReasonCode` | `origin_not_allowed` | `failure-request-refused` |
| `FailureReasonCode` | `endpoint_not_found` | `failure-not-found` |
| `FailureReasonCode` | `refresh_job_not_found` | `failure-not-found` |
| `FailureReasonCode` | `refresh_job_running` | `failure-refresh-running` |
| `FailureReasonCode` | `port_unavailable` | `failure-port-unavailable` |
| `FailureStatus` | `error` | `failure-category-error` |
| `FailureStatus` | `input_unavailable` | `status-input-unavailable` |
| `ForwardEvidenceStatus` | `complete` | `forward-evidence-status` |
| `ForwardEvidenceStatus` | `partial` | `forward-evidence-status` |
| `ForwardEvidenceStatus` | `unavailable` | `forward-evidence-status` |
| `ForwardPolicy` | `display_only` | `forward-policy` |
| `ForwardPolicy` | `confirmation` | `forward-policy` |
| `ForwardPolicy` | `hard_gate` | `forward-policy` |
| `GrahamGrowthSelection.GrahamGrowthSelectionEPSBasis` | `three_year_average` | `eps-basis` |
| `GrahamGrowthSelection.GrahamGrowthSelectionEPSBasis` | `fiscal_year` | `eps-basis` |
| `GrahamGrowthSelectionEPSBasis` | `three_year_average` | `eps-basis` |
| `GrahamGrowthSelectionEPSBasis` | `fiscal_year` | `eps-basis` |
| `HeadlineUnavailable` | `unsupported_version` | `headline-unavailable` |
| `HeadlineUnavailable` | `strategy_not_declared` | `headline-unavailable` |
| `HeadlineUnavailable` | `no_result_stored` | `headline-unavailable` |
| `HistoricalHorizon` | `longest_available` | `historical-horizon` |
| `HistoricalHorizon` | `3` | `historical-horizon` |
| `HistoricalHorizon` | `4` | `historical-horizon` |
| `HistoricalHorizon` | `5` | `historical-horizon` |
| `IndustryClass` | `financial` | `industry-class` |
| `IndustryClass` | `utility` | `industry-class` |
| `IndustryClass` | `manufacturer` | `industry-class` |
| `IndustryClass` | `other` | `industry-class` |
| `InstrumentKind` | `equity` | `instrument-kind` |
| `InstrumentKind` | `etf` | `instrument-kind` |
| `InstrumentKind` | `cryptocurrency` | `instrument-kind` |
| `MetricStatus` | `ok` | `status-ok` |
| `MetricStatus` | `unavailable` | `status-unavailable` |
| `MetricStatus` | `not_applicable` | `not-applicable` |
| `PeriodKind` | `completed_annual` | `period-kind` |
| `PeriodKind` | `quarterly` | `period-kind` |
| `PeriodKind` | `ttm` | `period-kind` |
| `PeriodKind` | `instant` | `period-kind` |
| `PriceBasis` | `latest_adjusted_historical_close` | `price-basis` |
| `PriceBasis` | `latest_historical_close` | `price-basis` |
| `PriceComparisonStatus` | `available` | `price-comparison-status` |
| `PriceComparisonStatus` | `unavailable` | `price-comparison-status` |
| `ProviderCheckVerdict` | `healthy` | `provider-healthy` |
| `ProviderCheckVerdict` | `unreachable` | `provider-unreachable` |
| `ProviderCheckVerdict` | `rate_limited` | `provider-rate-limited` |
| `ProviderCheckVerdict` | `unexpected_response` | `provider-unexpected-response` |
| `ProviderCheckVerdict` | `no_data` | `provider-no-data` |
| `ProviderCheckVerdict` | `not_checked` | `provider-not-checked` |
| `ProviderFailureKind` | `unreachable` | `provider-unreachable` |
| `ProviderFailureKind` | `rate_limited` | `provider-rate-limited` |
| `ProviderFailureKind` | `unexpected_response` | `provider-unexpected-response` |
| `ProviderFailureKind` | `no_data` | `provider-no-data` |
| `QuoteFreshnessStatus` | `recent_retrieval` | `quote-freshness` |
| `QuoteFreshnessStatus` | `expired` | `quote-freshness` |
| `QuoteFreshnessStatus` | `unknown_retrieval_time` | `quote-freshness` |
| `QuoteFreshnessStatus` | `future_timestamp` | `quote-freshness` |
| `QuoteFreshnessStatus` | `user_supplied` | `quote-freshness` |
| `QuoteFreshnessStatus` | `historical` | `quote-freshness` |
| `ReasonCode` | `insufficient_history` | `reason-insufficient-history` |
| `ReasonCode` | `non_contiguous_history` | `reason-insufficient-history` |
| `ReasonCode` | `missing_fact` | `reason-missing-input` |
| `ReasonCode` | `incompatible_period` | `reason-incompatible-inputs` |
| `ReasonCode` | `incompatible_units` | `reason-incompatible-inputs` |
| `ReasonCode` | `incompatible_currency` | `reason-incompatible-inputs` |
| `ReasonCode` | `incompatible_scope` | `reason-incompatible-inputs` |
| `ReasonCode` | `ambiguous_fact` | `reason-ambiguous-fact` |
| `ReasonCode` | `not_available_as_of` | `reason-not-available-as-of` |
| `ReasonCode` | `nonpositive_beginning` | `reason-growth-not-meaningful` |
| `ReasonCode` | `nonpositive_ending` | `reason-growth-not-meaningful` |
| `ReasonCode` | `sign_change` | `reason-growth-not-meaningful` |
| `ReasonCode` | `fcf_not_growing` | `reason-not-growing` |
| `ReasonCode` | `eps_not_growing` | `reason-not-growing` |
| `ReasonCode` | `fcf_and_eps_not_growing` | `reason-not-growing` |
| `ReasonCode` | `forward_growth_not_confirmed` | `reason-forward-not-confirmed` |
| `ReasonCode` | `consensus_unavailable` | `reason-missing-input` |
| `ReasonCode` | `market_cap_unavailable` | `reason-missing-input` |
| `ReasonCode` | `provider_error` | `status-provider-error` |
| `ReasonCode` | `invalid_request` | `reason-invalid-request` |
| `ReasonCode` | `instrument_kind_not_applicable` | `reason-security-not-applicable` |
| `ReasonCode` | `industry_class_not_applicable` | `reason-security-not-applicable` |
| `ReasonCode` | `industry_class_unknown` | `reason-industry-class-unknown` |
| `ReasonCode` | `unsupported_mapping` | `reason-debt-not-visible` |
| `ReasonCode` | `debt_not_visible` | `reason-debt-not-visible` |
| `ReasonCode` | `nonpositive_denominator` | `reason-growth-not-meaningful` |
| `ReasonCode` | `insufficient_tests` | `reason-insufficient-tests` |
| `RefreshEventKind` | `started` | `refresh-event` |
| `RefreshEventKind` | `finished` | `refresh-event` |
| `RunOutcome` | `completed` | `outcome-completed` |
| `RunOutcome` | `unavailable` | `outcome-unavailable` |
| `RunOutcome` | `not_applicable` | `not-applicable` |
| `RunOutcome` | `failed` | `outcome-failed` |
| `ShareCountBasis` | `year_end` | `share-count-basis` |
| `ShareCountBasis` | `cover_page` | `share-count-basis` |
| `SourceKind` | `override` | `source-kind` |
| `SourceKind` | `cache` | `source-kind` |
| `SourceKind` | `provider` | `source-kind` |
| `SourceKind` | `derived` | `source-kind` |
| `TrendClassification` | `both_growing` | `growth-trend` |
| `TrendClassification` | `fcf_growing_earnings_not` | `growth-trend` |
| `TrendClassification` | `earnings_growing_fcf_not` | `growth-trend` |
| `TrendClassification` | `neither_growing` | `growth-trend` |
| `TrendClassification` | `insufficient_or_nonmeaningful_growth` | `growth-trend` |
| `TrendRelationship` | `short_above_long` | `trend-relationship` |
| `TrendRelationship` | `short_below_long` | `trend-relationship` |
| `TrendRelationship` | `short_equal_long` | `trend-relationship` |
| `TrendStatus` | `BULLISH` | `momentum-states` |
| `TrendStatus` | `BEARISH` | `momentum-states` |
| `TrendStatus` | `UNKNOWN` | `momentum-states` |

## 4. Scope limits and acceptance criteria

- API.6a changes no stored shape, formula, classification, dependency or command-line text. The only change to
  `runs compare --json` is the added `term` fields and the version, and the existing text tests pass unmodified.
- API.6a adds no endpoint, no `api` import of `help`, no locale handling and no bundle file rename.
- Every enumeration of more than one value in `openapi.json` has a term table that names a served term for each of its
  values, except the four exemptions, and the gate fails on one that does not.
- Every headline cell, strategy and selection field names a term the bundle holds.
- A shared value of the two status types maps to the same term in both.
- Every served term is named by a table, a headline cell, a strategy or a selection field, or is linked from served
  content.
- The "glossary terms" site fails a strategy with a missing or unknown term, and the generator's end-to-end test passes
  with the new site.
- API.6b: the three help endpoints and the references endpoint return their documents, an unknown id answers 404, every
  `/v1` response carries `Content-Language` and `Vary: Accept-Language`, and the bundle has exactly one file for each
  declared locale.

## 5. Background

The contract ([A.4](API_CONTRACT_AND_SLICE_PLAN.md#a4-help-content-in-the-gui-2026-10-30)) makes the engine the owner of
every explanation a GUI shows. API.5 gave the glossary stable ids and a packaged bundle; this plan makes every value the API
returns point at one of those ids, and then serves the bundle. API.6 was one slice with a conformance half and an endpoint
half; the conformance half touches every strategy, every code set and the generator, so the two are separate pull requests.

## Appendix A: Decision records

T1 to T15 were approved by the project owner on 2026-11-07 and are recorded here as given.

### T1 API.6 is split in two (2026-11-07)

- API.6 is split into two slices:
  - API.6a, term references, on branch `feat/api-term-references`;
  - API.6b, help endpoints and locales, on branch `feat/api-help`.
  API.6a writes the slice plan `docs/project/milestones/v0.2/api/API_6_SLICE_PLAN.md`.

### T2 What must name a term (2026-11-07)

- Every value of every closed code set (every `enum` with more than one value) in `schemas/openapi.json` names a glossary
  term, and so does every label: headline cells, strategies and selection fields.
- An explicit exemption list, with a reason for each entry, holds exactly these: `schema_version`, the headline cell
  `kind`, the replay text `mode`, and the `method_id` path parameter (the strategy's own term covers it).
- A test walks `openapi.json` and fails on any value that has no term and is not exempt.
- The contract's API.6 Decision bullet is reworded to this rule. A strategy document's field names and rendered text are
  explained through the strategy's term and its guide, not field by field.

### T3 How values map to terms (2026-11-07)

- Every value maps to exactly one term.
- A value gets its own term when what the person should conclude or do differs. Each run outcome, each status and each
  provider failure kind therefore gets its own term.
- Values that differ only in detail share one entry, and that entry explains each of them. Examples are the `database_*`
  failure codes and the request-check codes.
- The slice plan lists the full mapping, from code set and value to term id.

### T4 Where the tables live (2026-11-07)

- Each code set's term table sits in the module that defines the code set. Core enums' tables go in `core`, `RunOutcome`'s
  goes in `analysis`, and the refresh event kind's goes in `api`.
- Strategy-specific code sets' tables go in the strategy's `vocabulary.py`, reached through a descriptor field.
- `help` stays layer 0 with no imports.

### T5 How the tables are served (2026-11-07)

- API.6b serves them as `GET /v1/help/references`, keyed by OpenAPI component name and then by value, giving a term id.
- In 6a, every user-facing code set that is an inline literal today becomes a named component. This includes
  `headline_unavailable` and the refresh event `kind`, and any other inline set the walk finds.
- A label carries an inline `term`. A code never does.

### T6 Headline cells (2026-11-07)

- `HeadlineCell.term` is required and set by each strategy's headline function.
- `CompareCellDocument.term` and `CompareStrategyDocument.term` are added; the strategy one is null for a strategy that is
  no longer declared.
- The runs-compare document's `schema_version` goes from 2 to 3.
- Nothing stored changes.

### T7 Strategies (2026-11-07)

- An explicit `StrategyDescriptor.term` is added, because a glossary id can't be derived from an alias (`graham-growth`
  maps to `graham-growth-value-strategy`).
- `StrategyItem` in the strategies document gains `term`, and the document's `schema_version` goes from 1 to 2.
- `scripts/new_strategy.py` writes `<alias>-strategy`.

### T8 Selection fields (2026-11-07)

- Every selection `Field` carries `json_schema_extra={"x-term": "<term id>"}`, so the term appears in `schemas/selections/`
  and in the selection form.
- The persisted selection shape is unchanged, so there is no version bump.
- `as_of` maps to `as-of-date`, `use_cache` to `cache`, and the overrides to `override`.

### T9 Edit site (2026-11-07)

- One new site, "glossary terms", of kind `reviewed`, covers the strategy's glossary entry, its headline cell terms, its
  selection-field terms and its code-set tables.
- Its check function in `scripts/strategy_conformance.py` fails on a missing or unknown term.
- The edit-site table in `docs/TOOL_DEVELOPMENT.md` is regenerated with `uv run python -m scripts.generate_strategy_docs`.
- Follow "Changing what every strategy provides" in `docs/TOOL_DEVELOPMENT.md`, and record any file it missed in the
  implementation record.

### T10 New entries and the orphan check (2026-11-07)

- Shared outcome, status and reason entries go in a new level-2 section of `docs/user/GLOSSARY.md`, "Outcomes, statuses and
  reasons".
- Strategy-specific entries go in that strategy's own section.
- Every entry follows the entry rules in `docs/project/README.md`: an `<a id>` line; a first paragraph that is the short
  definition, at most 200 characters and two sentences, plain text with no link or code; interface-neutral, with no
  command, flag or closed list of strategies.
- The orphan check is a pytest test. Every served term must be named by a table, a cell term, a strategy term or a
  selection `x-term`, or be linked from served content.

### T11 API.6b help endpoints (2026-11-07)

- `GET /v1/help` returns an index: groups with each term's id, name and definition, and documents with id and title.
- `GET /v1/help/terms/{id}` and `GET /v1/help/documents/{id}` return single items.
- All are JSON documents with a `schema_version`, and Markdown in string fields.
- An unknown id returns 404 with `help_term_not_found` or `help_document_not_found`.

### T12 API.6b (2026-11-07)

- `InfoDocument` gains `locales`, a list of `{tag, name}` items, and its `schema_version` goes from 1 to 2.

### T13 API.6b bundle per locale (2026-11-07)

- `LOCALES` is declared in `help`.
- The bundle file becomes `help_bundle.en.json`, and the loader becomes `load_help_bundle(locale)`.
- A test requires exactly one bundle file per declared locale.

### T14 API.6b negotiation (2026-11-07)

- `api` parses `Accept-Language` itself, with no new dependency.
- It honours q-values and excludes `q=0`.
- It matches by tag truncation, so `en-CA` falls back to `en`.
- `*`, an absent header and a malformed header fall back to `en`. It never answers 406.
- Every `/v1` response carries `Content-Language` and `Vary: Accept-Language`.
- A.5 records a precondition for adding a locale: every producer of labels, rendered text and messages must take the
  locale first.

### T15 Docs (2026-11-07)

- `docs/user/API.md` gains help, references and locale sections (6b).
- Architecture §13 in `docs/project/ARCHITECTURE.md` changes in the same change that adds an import between units (6a and 6b
  each).
