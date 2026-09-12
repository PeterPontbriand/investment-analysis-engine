# ESC-A — Evidence and proposed repair contract

**Status:** C1–C6 reviewed and approved by the project owner after pushing `cb1e9ef50bcef5f549cdabba91c853629da78eed`. ESC-B implementation and verification are recorded in the [final review packet](ESC_B_IMPLEMENTATION_AND_REVIEW.md). ESC-C final acceptance was granted on 2026-09-11 (Toronto); ESC-D remains a separate future renewal gate. The original evidence below is historical; the ledger and matrix contain current repair dispositions.

**Authority:** [Approved correctness plan](EXISTING_STRATEGY_CORRECTNESS_PLAN.md). Companion records: [defect ledger](ESC_A_DEFECT_LEDGER.md) and [coverage matrix](ESC_A_COVERAGE_MATRIX.md).

**Revision examined:** `8d7fba0` on `fix/existing-strategy-correctness`, including the earlier Graham repair `e8f4a95`. Evidence collected 2026-09-11 UTC (evening of September 10 in Toronto). No production source, dependency, operational database, or existing test was changed during this investigation.

## 1. Evidence and limits

The fresh managed baseline passed: **2,004 tests; 89% reported coverage; Ruff check, Ruff format check, and strict mypy passed**. Command:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

Isolated baseline artifacts: `.tmp/quality-runs/20260910213740452-33520-3d7354d9c2ae48029915ee2ef93b9e26/`. Passing existing tests does not close the new findings.

Offline characterization used the installed environment through `uv run --no-sync python`, with socket connections blocked for the calculation/composition reproductions. Local scripts are retained under ignored `.tmp/esc-a-evidence/`: `reproduce.py`, `composition_probe.py`, and `arithmetic.py`. Reproduction inputs and observed results are recorded in the ledger so these temporary files are not the sole durable record. They characterize defects in the examined revision; ESC-B must add permanent tests asserting repaired behavior, not preserve assertions that bugs exist.

Live CLI details and JSON were captured separately for each of these commands against a newly created, explicitly migrated **isolated test database**, using existing configured SEC EDGAR and Yahoo adapters; no LLM or new provider was involved:

```powershell
uv run --no-sync financial-agents graham-number KO --details
uv run --no-sync financial-agents graham-number KO --json
uv run --no-sync financial-agents graham-growth KO --expected-growth 5 --aaa-yield 4.4 --details
uv run --no-sync financial-agents graham-growth KO --expected-growth 5 --aaa-yield 4.4 --json
uv run --no-sync financial-agents momentum KO --details
uv run --no-sync financial-agents momentum KO --json
uv run --no-sync financial-agents fcf-growth KO --details
uv run --no-sync financial-agents fcf-growth KO --json
```

The capture harness invoked the equivalent installed entry module, `python -m src.cli`, with these arguments and an isolated `database_url`. Captures are ignored operational evidence, not fixtures: `.tmp/esc-a-evidence/live-20260911T014514Z/`. Run starts ranged from 01:45:15 to 01:45:44 UTC. An initial capture attempt failed on Windows subprocess text decoding; the successful capture explicitly set `PYTHONIOENCODING=utf-8`. That harness problem is not an application finding.

| Analysis | Observed result | Independent check |
| :--- | :--- | :--- |
| Graham Number | Exit 0 in both modes; 21.14 USD; quote 87.83 USD; 315.43% above | Average EPS `(2.47 + 2.46 + 3.04) / 3`; BVPS `32,169,000,000 / (7,040,000,000 - 2,738,000,000)`; square root of `22.5 × EPS × BVPS` = **21.14186862097603**. Comparison recomputed from unrounded JSON quote. |
| Graham Growth | Exit 0; 49.15 USD; 78.70% above | EPS average × `(8.5 + 2 × 5)` × `4.4 / 4.4` = **49.14833333333333**. Assumptions are user supplied, not forecasts obtained from a provider. |
| FCF/Earnings Growth | Exit 0; total-FCF screen FAIL; FY2020–2025 | Each of six FCF values independently checked as OCF minus normalized CapEx, and each per-share value as FCF divided by diluted shares. Endpoint CAGR checks: total FCF **−9.381715561220638%**, per-share FCF **−9.339733479530066%**, EPS **+11.17422496891589%**. |
| Momentum | Exit 1 in both modes; JSON stdout empty | Direct provider inspection returned 1,428 rows from 2021-01-04 through 2026-09-10. Last row had NaN in Close/High/Low/Open and volume 11,800,688. Rejecting it is correct. The error does not expose the failing field/date and JSON does not represent the failure. No successful live Momentum acceptance is claimed. |

Graham/FCF calculations agree with their retained inputs; this does not independently certify every upstream financial fact. Existing realistic SEC fixture coverage and dated source verification must be extended at ESC-B/C. A live price is not an immutable expected value. KO filing evidence refers to accession `0001628280-26-010047`, available 2026-02-20 14:46 UTC. Several prior-year comparative EPS observations legitimately have that same filing availability date.

## 2. Actual pipelines and consumer boundary

| Analysis | Production pipeline | Public consumers and distinctions |
| :--- | :--- | :--- |
| Graham Number | `src/cli.py` → `graham_number/config.py`, `calculation.py`, `service.py` → shared financial resolver/facade → SEC financial facts, Yahoo quote, isolated/durable resolved-input cache → security-unit completion → `src/reporting/graham.py` | CLI, direct analyzer/service and `AnalysisToolHandlers.analyze_graham_number`; averaging and BVPS are distinct from Growth. |
| Graham Growth | CLI → `graham_growth/config.py`, `calculation.py`, `service.py` → shared resolver/facade → configured security facts, Yahoo quote, cache, security-unit completion → Graham presenter | CLI, direct analyzer/service and `analyze_graham_growth_value`; explicit growth/yield, SEC default three-year EPS, supported alternative provider/basis routing retained. |
| Momentum | CLI → Yahoo historical client → `CachedHistoricalDataClient` / `SQLiteMarketDataRepository` → `MomentumInputResolver` → `MomentumAnalyzer` → `MomentumPresentation` | CLI, direct `run_analysis(df=...)`, `run_with_context`, `analyze_momentum`. Orchestrator retains `MomentumRun`; CLI drops its trace. Historical close is adjusted daily data, not the quote capability. |
| FCF/Earnings Growth | CLI → SEC production facade → `ProductionAnnualGrowthSeriesResolver` / annual-series cache → field/period selection and derivation → analyzer/classification → FCF presenter | CLI, direct resolver/analyzer and `AnalysisToolHandlers`; company FCF and diluted-share FCF remain distinct. Optional consensus/market cap have no approved production mapping. |

All strategy paths above are under `src/analysis/strategy/`; shared entry points are `src/analysis/shared/financial_resolution.py`, `src/data/financial/{resolver,production,quality,cache,provenance}.py`, `src/data/instrument_profile.py`, `src/cli_support.py`, and `src/orchestrator/analysis_tools.py`. Evaluation cases and fixture expectations are additional consumers of typed results, not alternative production calculations.

### CLI capability inventory

| Capability | Number | Growth | Momentum | FCF |
| :--- | :--- | :--- | :--- | :--- |
| Concise/details/diagnostics/JSON | All four | All four | All four; failure gap ESC-11 | All four |
| Historical boundary | `--as-of` | `--as-of` | Service/tool `as_of`; no CLI flag | `--as-of` |
| Cache bypass | `--no-cache` | `--no-cache` | No CLI flag; injected client and cache policy support tests | `--no-cache` |
| Financial inputs | EPS, EPS basis, BVPS, current-price overrides | EPS/basis, required growth and AAA yield, current price | Short/long SMA and RSI periods | Growth years 3/4/5 or automatic; classification basis, forward policy, currency/provider |
| Provider selection | `--data-provider` | `--data-provider` | Configured historical Yahoo provider | `--data-provider`, only approved SEC annual mapping |

Do not add missing CLI flags merely to fill a matrix cell. Retain existing aliases and required-argument behavior. CLI parser errors remain exit 2. Analysis/infrastructure failures remain nonzero; a valid FCF screen FAIL remains a successfully computed result, not a process failure.

## 3. Proposed contracts for approval

### C1 — Quote freshness without changing annual-fact age

Add `src/data/financial/quote_freshness.py` containing frozen `QuoteFreshnessPolicy` and `QuoteFreshnessEvidence`, and a pure evaluator with an injected aware evaluation time. Policy: `max_retrieval_age: timedelta = timedelta(minutes=5)`. Add `ProjectSettings.quote_cache_ttl_seconds`, finite and nonnegative, default **300**, with no unlimited option. This is an engineering bound on reuse of a provider response, not a claim that an exchange trade is less than five minutes old. Existing financial-cache TTL remains unchanged and can impose a stricter bound.

Evidence fields: `status` (`recent_retrieval`, `expired`, `unknown_retrieval_time`, `future_timestamp`, `user_supplied`, `historical`), `evaluated_at`, `retrieved_at`, `retrieval_age_seconds`, `max_retrieval_age_seconds`, and nullable `market_observed_at`. Preserve original retrieval time through cache hits; cache insertion/resolution time must not reset age. Exactly 300 seconds is eligible; greater age refreshes. Zero disables cached quote reuse. Missing/future retrieval evidence rejects reuse. Annual facts are not expired by this quote policy.

Apply the evaluator at `InputResolver` for `FinancialField.CURRENT_PRICE`, for both in-memory and SQLite results, before accepting a cached value. Add an optional keyword policy argument to its constructor; production CLI and orchestrator composition inject settings, direct construction receives the finite default. Provider refresh follows the existing provider resolution once, with no new retries or stale-on-error fallback. If refresh fails, retain valid financial calculations but make quote/comparison unavailable with a refresh-failure reason. An existing general TTL can discard an entry before the resolver sees it; do not invent a specific expiry diagnostic for an undifferentiated cache miss.

Carry nullable `quote_freshness` on `InputResolutionResult`, both Graham assemblies and presentation context, and on `PriceComparison` so direct services/tool consumers retain the same evidence. This is transient analysis evidence, not a persisted `ResolvedInput` field. Cache schema and Alembic revisions do not change.

Yahoo `fast_info.last_price` currently lacks a retained exchange observation timestamp. Correct the adapter to retain actual retrieval time and leave `observed_at`/`available_at` unknown rather than copying retrieval into them; set a descriptive latest-provider-quote basis. The presenter must use **“Latest available quote”** with retrieval age/time and **“market observation time not supplied”**. A recent provider response can support a comparison explicitly described as a relationship to that latest available quote; it cannot claim verified live-market freshness. This preserves useful Graham comparisons without fabricating market timestamps or requiring a new quote API. Legacy Yahoo quotes with the old synthetic timestamp note must not be presented as independently timed trades.

No exchange calendar, market-session inference, weekend exception, or invented maximum trade age is introduced. If a future provider supplies an actual observation time, show it; reject future observation evidence, but do not certify market freshness merely from retrieval. Historical requests retain existing availability requirements and may not fall back to today's quote. User price overrides remain permitted and clearly marked user-supplied; they are not provider-freshness verified.

### C2 — Keep filing exchange evidence separate from current identity

Retain verified exchange text from `ParsedUnitDocument` and add optional `listing_venue` to each `SecurityUnitDocument`. The existing document accession, URL, contexts, availability and retrieval time provide its provenance. Require the same verified common-class association used by the parser; do not collect arbitrary exchange text elsewhere in the filing.

Show **“Filing listing venue: NYSE (filing available …)”** separately from **“Current listing venue: not supplied by selected identity provider”**. Do not overwrite current identity with historical evidence or introduce cross-provider field merging. Preserve distinct values per document if filings disagree; make the disagreement visible. This bounded repair applies where the existing Graham evidence acquisition actually obtains a verified filing. FCF/Momentum do not fetch additional filings solely for display. Their absent current venue remains honestly explained. Identity conflicts must not weaken the security-unit comparison checks.

### C3 — Explain absent values and preserve inferred lineage

Introduce `src/reporting/input_provenance.py` for shared, narrowly scoped financial-input detail rendering and source descriptions, not a generic presentation framework. Render recursively retained lineage, component units/currency, source identity, original/cache origin, notes, derivation, provider field and financial periods. An inferred zero must say inferred and retain its guarded-absence rationale; it must not become an observed zero or disappear because it is falsy. Cache wrapping must not erase that distinction. Use existing typed provenance and recognized adapter inference identifiers; do not infer financial semantics from arbitrary free-form prose.

Required wording rules:

| State | Required interpretation |
| :--- | :--- |
| Derived EPS/BVPS without a direct provider field | “Not applicable — derived from the listed components”; retain component concept IDs. |
| Point quote without fiscal start/end | “Not applicable — point quote”; market observation time remains separately unknown. |
| Annual financial statement without a point-observation timestamp | Show fiscal period and filing availability; point observation is not applicable. |
| User assumption without provider/freshness | “User supplied; not provider verified”; no implication that a provider lookup failed. |
| Missing metadata | State what the selected provider did not supply; never invent a date, venue, currency or basis. |
| Unavailable calculation | Typed reason, required input or history count, and meaningful remedy when one exists. |
| Numeric zero | Preserve it where mathematically or evidentially valid; never use truthiness as missing-data detection. |

JSON retains numeric `null` for absence and existing source identifiers. Explanatory presentation metadata is additive; no replacement of nullable numbers with strings. FCF detail rows must show USD (or the actual currency), readable units, cache origin and component assumptions instead of only `currency`/`currency_per_share`. Show optional forward/yield status and its reason in details/JSON even when no value exists. Their missing approved mappings are not repaired by speculative provider additions.

### C4 — Momentum transition, validation and provenance

Keep SMA and existing simple trailing-average RSI formulas, configured defaults (50/200 SMA; RSI 14), adjusted-price basis, and equality-as-bearish trend rule. A crossover requires valid short and long SMAs at **both** the current and preceding observation. First valid long-SMA observation can have a classified trend but an unavailable crossover. Add optional `crossover_result: MetricResult` to `MomentumMetrics`; preserve `crossover_signal: float | None` as its compatibility projection. Reason remains `INSUFFICIENT_HISTORY`, with explicit two-observation wording. Zero means a verified absence of transition; +1/−1 mean the existing directional transitions. An absent crossover does not make valid SMAs unavailable.

Move the existing historical-frame validation to a common boundary used by both fetched and supplied frames. Reject nonfinite, unordered/duplicate and otherwise invalid required observations before calculating; do not silently drop, fill, reorder or trim bad rows. Do not introduce positivity/session policies without a separately evidenced defect and review. Preserve valid preloaded-frame callers and test their compatibility.

Add optional `resolution: HistoricalDataResolution | None = None` to `HistoricalMarketData`. The frozen transient record carries `source_kind`, `retrieved_at`, `cached_at`, `resolved_at`, and `cache_schema_version`. Populate cache hits from existing `MarketDataCacheEntry.fetch_completed_at` and `cached_at`; preserve unknown retrieval when absent. Provider retrieval can be established by the adapter/cache boundary at actual completion, never by later resolver execution. SQLite storage schema stays unchanged: the cache wrapper reconstructs this record from existing columns, and persistence explicitly ignores the transient field.

`MomentumInputResolver` consumes that record for `ResolvedInput` origin and timestamps and retains cache/provider stages in its trace. It must not mark cache hits as fresh provider retrievals. Add optional `resolution_trace` and `data_resolution` to `MomentumPresentation`; CLI passes the actual run trace and resolution record. Preserve legacy `diagnostics` arguments without duplicating events. Orchestrator results retain the same evidence through `MomentumRun`.

Historical `as_of` remains a filter on observation labels, not a guarantee that today's adjusted prices were knowable then. Expose that limitation in service/tool evidence and documentation. Naive daily date labels must not be described as verified exchange close timestamps; do not claim a market calendar or point-in-time adjustment history that the provider does not retain. Before ESC-C, test same-day timezone boundaries and post-boundary adjustment limitations explicitly; a discovered look-ahead defect must be recorded and resolved, not waived by a generic warning.

### C5 — FCF explanation follows selected basis

Select the explanatory noun from `result.classification_basis` for trend and classification reasons: total company free cash flow versus free cash flow per diluted share. Preserve all CAGR values, classification enums and financial formulas. Test rising total FCF with falling FCF/share and the converse, under both selected bases and all forward policies. Correct stale schema/method comments while touching the corresponding model/presenter declarations; current FCF result schema is **3**, method version **2**, presentation schema **4**.

### C6 — Actionable, structured analysis failures

Add a bounded failure payload/presenter in `src/reporting/presentation.py`, used by all four CLI commands for post-parse execution failures. Fields: `schema_version`, `analysis`, `method`, `ticker`, `status`, `reason_code`, `reason`, `result: null`, `diagnostics`. Preserve exit 1 for execution failures and exit 2 for parser/usage failures. JSON mode must emit one parseable JSON document on stdout; no stack trace/provider payload/secrets. Text diagnostics should retain sanitized quality rule, affected input, field and observation date when known.

Add typed `HistoricalDataQualityError` carrying the existing `QualityDecision` tuple plus bounded invalid-field/date descriptors; use it at the historical validation boundary. Missing KO OHLC must remain a rejected input. No fallback to an older last close or row deletion is authorized. Unexpected exceptions still receive a generic sanitized reason; do not expose exception text wholesale. Database-readiness-specific diagnosis/initialization remains deferred; this change only makes existing failure output coherent.

## 4. Files, schemas and compatibility

The following is the proposed production allowlist, grouped by contract. Files may be omitted when existing interfaces suffice. A material policy/scope expansion requires review; routine implementation choices inside these interfaces do not require another per-file approval.

| Contract | Existing files eligible for focused changes | New file |
| :--- | :--- | :--- |
| C1 | `src/config.py`; `src/data/financial/resolver.py`; `src/data/yfinance/financial_facts.py`; `src/analysis/shared/financial_resolution.py`; both `src/analysis/strategy/graham_{number,growth}/{calculation,service}.py`; `src/cli.py`; `src/orchestrator/analysis_tools.py`; `src/reporting/graham.py` | `src/data/financial/quote_freshness.py` |
| C2 | `src/data/sec_edgar/security_unit.py`; `src/data/security_unit.py`; `src/data/instrument_profile.py`; `src/reporting/graham.py` | None |
| C3/C5 | `src/reporting/{presentation,graham,fcf_earnings_growth,momentum}.py`; `src/analysis/strategy/fcf_earnings_growth/{models,calculators}.py` for basis-specific reason wording and stale contract comments only | `src/reporting/input_provenance.py` |
| C4/C6 | `src/data/{market_data,cached_client,quality}.py`; `src/data/yfinance/client.py`; `src/data/repositories/market_data.py` for transient serialization handling only; `src/analysis/strategy/momentum/momentum_analyzer.py`; `src/reporting/{momentum,presentation}.py`; `src/cli.py`; `src/cli_support.py`; `src/orchestrator/analysis_tools.py` | None |

Brace notation above enumerates existing files, not new packages. Do not change Alembic migrations, relational schema, dependency manifests, database-readiness implementation, or introduce a strategy framework.

Version proposal: Graham presentation **4 → 5**, Momentum presentation **3 → 4**, FCF presentation **4 → 5**, because structured evidence/failure contracts change. FCF canonical result schema **3** and method version **2** stay unchanged for wording-only repairs. Momentum crossover semantics change as a bug fix; explicitly document the first-valid-window difference. Existing keys/numeric meanings, aliases and direct-call entry points remain. Additional dataclass fields have defaults. Consumers that require exact JSON schemas must update; this is not advertised as byte-for-byte compatibility. Do not add a cache-schema version merely because the presentation version changed.

Update focused existing tests in `tests/analysis/{momentum,graham_value,fcf_earnings_growth}/`, `tests/data/`, `tests/reporting/`, `tests/orchestrator/test_analysis_tools.py`, the four command/cache/composition suites and evaluation fixtures/expectations affected by these contracts. Add `tests/data/test_quote_freshness.py`, `tests/reporting/test_input_provenance.py`, `tests/test_existing_strategy_failure_output.py`, and `tests/test_existing_strategy_output_contracts.py` for missing cross-layer evidence. Network blocking and isolated storage are mandatory for deterministic cases; fixtures must preserve relevant source structure rather than mock the decision under test.

Durable documentation targets: `README.md`, `docs/user/{FINANCE_MATH,GLOSSARY}.md` and the existing CLI/setup references identified during implementation. Update current behavior only after implementation. Date live examples, label quote timing honestly, document cache refresh/bypass, simple RSI semantics, crossover history, optional FCF capability limits and JSON versions. Milestone progress/IDs remain in `docs/project/`.

## 5. Execution after approval and final review

Implement in focused groups: quote timing/comparison; provenance and metadata explanations; Momentum calculation/validation/cache/diagnostics; FCF basis wording; consistent failure output and documentation. Add the failing regression for each finding before its repair, then run focused checks. Shared changes must exercise every affected consumer, including direct APIs and orchestrator handlers.

Before ESC-C, reconcile every ledger entry and matrix cell, independently recalculate all four analyses, run real composition fixtures and dated live cases (including a successful valid Momentum history), then the complete managed gate with at least 85% coverage. The current live KO history issue remains visible until valid evidence or an explicitly reviewed provider limitation is established. Do not declare the whole repair complete merely because the error becomes clearer.

The final review must show repair commits or the reviewed uncommitted revision, regression names, live commands/times, compatibility changes, legitimate absences/zeros and all remaining limitations. No known defect is deferred to a backlog. ESC-C acceptance is required before database readiness resumes; ESC-D renewal still blocks Step 3.5.

**Requested review:** Approve or amend C1–C6, especially the five-minute retrieval-reuse bound, separately labelled filing venue, honest unknown market timestamp, first-valid-window crossover rule, strict rejection of invalid history and versioned failure JSON. Approval does not authorize commits, pushes, PRs or migrations against user data.
