# Graham Comparison Repair — R1 Evidence and Concrete Contract

**Date:** 2026-09-09.<br/>
**Revision inspected:** `e20f6f7c818bce37c39dafceb80ea80bbceaf6d1` on `docs/database-readiness-planning`.<br/>
**Status:** R1 accepted and R2 authorized. This document preserves the reviewed design and baseline; section 7 records the approved lineage extension. See [R2 implementation and verification](R2_IMPLEMENTATION_AND_VERIFICATION.md) for the completed implementation awaiting final review.<br/>
**Authority:** [Accepted repair plan](GRAHAM_COMPARISON_REPAIR_PLAN.md). The pre-existing root README correction is preserved and belongs with this repair. Database-readiness implementation remains excluded.

## 1. Findings and verification

The Step 2.5A [security-unit review](../step-2.5a/STEP_2_5A_C_REVIEW.md) deliberately required affirmative ordinary-share 1:1 evidence while deferring production composition. Current composition never fills `InstrumentProfile.security_unit_evidence`, but both Graham services require it whenever a profile exists. The shared helper returns `None`, and the renderer cannot distinguish missing unit evidence from other unavailable comparisons. Legacy callers without profiles retain the old numeric behavior.

The existing CLI success tests in `tests/test_cli.py` and `tests/test_cli_graham_commands.py` check calculation/method/provenance, not a non-null price relationship. Predicate tests inject an already-complete `SecurityUnitEvidence`. Neither proves the production evidence acquisition chain.

### Fresh baseline

The complete `scripts/run-quality-gates.ps1` wrapper passed against the inspected revision and unchanged production code:

- Ruff: passed; formatting: 296 files already formatted.
- Strict mypy: no issues in 230 source files.
- Pytest: 1,944 passed in 33.06 seconds; reported aggregate coverage 89%.
- Runtime reported Python 3.14.7, pytest 9.1.1; no dependency synchronization or installation.
- Artifacts: `.tmp/quality-runs/20260909203317748-39208-04be69c080b248cea74aa3b5a78a3537/`.

The first sandboxed attempt could not query the interpreter (access denied). The same non-mutating wrapper succeeded with elevated execution, retaining repository-local isolated artifacts. No operational database was migrated.

[Reproduction](reproduce_comparison.py) runs both real CLI commands, real profile composition, resolvers, services, and rendering with synthetic financial data; only provider construction and Yahoo metadata are stubbed. Network and operational SQLite construction raise immediately if attempted. Focused verification passed Ruff, formatting, strict mypy (one file), and both pytest cases in 1.26 seconds. Artifacts: `.tmp/quality-runs/graham-r1-4ee20f48f40b47c9bff0e975f8540c86/`. An initial Ruff compound-assertion finding was corrected and the focused checks rerun successfully. Both cases passed their characterization assertions: positive reference/quote, matching USD, null comparison, generic unavailable message. This demonstrates the defect, not successful repair. The reproduction must be superseded by positive production-composition regression tests in R2; do not add permanent tests that require the defect to remain.

Explicit reproduction command (use a unique repository-local temp/cache directory):

```powershell
uv run --no-sync pytest -o addopts= -p no:cacheprovider --basetemp=<unique-repository-temp-directory> docs/project/milestones/v0.2/graham-comparison/reproduce_comparison.py
```

## 2. Provider evidence reconnaissance

Sources inspected on 2026-09-09:

- [SEC Company Facts/API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces): Company Facts aggregates standard-taxonomy, entity-wide facts; it is not a complete security-class/context inventory.
- [SEC EDGAR XBRL Guide, February 2026](https://www.sec.gov/files/edgar/filer-information/specifications/xbrl-guide-2026-02-17.pdf), section 3.2.4, pages 53–56: security titles, stock-class dimensions, and exchange contexts must be interpreted together. Do not associate symbols/titles by list position.
- [KO fiscal-2025 10-K](https://www.sec.gov/Archives/edgar/data/21344/000162828026010047/ko-20251231.htm) and [filing index](https://www.sec.gov/Archives/edgar/data/21344/000162828026010047/0001628280-26-010047-index.html), accession `0001628280-26-010047`, filed 2026-02-20.
- [Issuer-hosted copy of that filing](https://investors.coca-colacompany.com/filings-reports/all-sec-filings/content/0001628280-26-010047/ko-20251231.htm), inspected as raw markup after SEC direct download rejected an undeclared automated request. This mirror is reconnaissance evidence only, not a new production fallback domain.

The issuer copy was retained only in ignored `.tmp/graham-r1-evidence/ko-20251231.htm`; SHA-256 `ba1e9e6364b8b1a0d438dcadd1e184aabc5e8b6a494611193befce2822aa75c0`. It uses lowercased HTML tag/attribute spelling. No raw filing or operational logs are added to Git.

Observed structured evidence: context `c-2` identifies CIK `0000021344` and stock-class member `ko:CommonStock0.25ParValueMember`. Its title is common stock, its symbol is KO, and its exchange is NYSE. Context `c-3` instead identifies a note security and symbol KO26. Diluted EPS for the three reported years appears in entity-wide contexts; common-stock issued/value facts use entity-wide balance-sheet contexts. These observations support a narrow domestic single-common-class mapping proposal; they do not prove that ticker metadata or all EQUITY instruments are 1:1.

| Existing input | Valid use | Insufficient for |
| :--- | :--- | :--- |
| SEC ticker → CIK/title | Establish requested issuer; detect inconsistent identity | Ordinary-share classification or unit ratio |
| SEC submissions metadata | Select accession, acceptance time, form, primary document; confirm current symbol/issuer | Relating per-share facts to a stock class |
| SEC Company Facts, including units and `provider_fact_id` | Identify exact inputs/accessions and reporting units | Full dimension/class inventory |
| Yahoo current quote | Ticker-scoped quoted amount and known currency | Proving ordinary-share/ADR ratio from `fast_info` alone |
| Yahoo descriptive metadata/`quoteType` | Preserve name and instrument kind | Affirmative share-unit evidence |
| Filing Inline XBRL | Context-linked title/symbol/exchange plus financial/share contexts | Universal corporate-action normalization or unrestricted historical identity |

**Material design consequence:** Existing JSON/metadata adapters cannot safely supply the missing evidence alone. R2 needs a small SEC filing-document reader and context-aware parser. This is the explicit scope addition proposed for approval; no generic XBRL engine or new dependency is proposed.

## 3. Exact supported mapping and temporal policy

Proposed mapping identifier: `sec_domestic_single_common_class_v1`.

1. Support SEC-sourced US-GAAP completed-annual inputs from domestic 10-K filings, with Yahoo ticker-scoped current quotes. Other providers, IFRS/FPI forms, and TTM inputs receive an explicit unsupported-evidence reason; do not change their standalone calculations.
2. Use the request's existing SEC snapshot and the original accession IDs of every non-override EPS/BVPS lineage leaf. Parse those IDs using the adapter's existing colon-separated `provider_fact_id` format. Cached leaves retain original IDs. Missing IDs, conflicting issuers, or unresolved accession metadata fail closed; never substitute the latest filing for an older cached input.
3. Resolve primary documents through submissions accession metadata, not guessed filenames or arbitrary URLs. Require matching CIK and recognized SEC document origin, form, and availability. Inspect at most four distinct filings per request: the current eligible annual filing plus up to three source filings. If more are needed, report unsupported evidence rather than truncate. This bound covers the current three-year EPS default and latest annual BVPS without an unbounded crawl.
4. Join `dei:Security12bTitle`, `dei:TradingSymbol`, and `dei:SecurityExchangeName` by context identity, CIK, period, and dimensions. Require the requested exact symbol to identify one unambiguous ordinary common-stock class. Normalize case and whitespace only. Accept exactly `Common Stock`, `Common Stock, $N Par Value`, or `Common Stock, Par Value $N Per Share`, where N is a nonnegative decimal literal (no currency inference from par value); do not classify by fuzzy title/member-name substring. Class A/B designations, ordinary-shares variants, ADR/ADS, units, preferred securities, conflicting duplicate facts, and unrecognized title forms fail closed until separately mapped.
5. Inventory all registered class contexts, including 12(g) titles, and relevant share/EPS contexts in each source document. One positive common-stock class plus entity-wide common-stock/EPS facts is the narrow reviewed inference linking issuer per-share inputs to that listed common share. A second equity class, unexplained class dimensions in financial inputs, unrecognized registered security, or ambiguous association rejects it. For this mapping, recognize debt titles only as `N% Notes Due YYYY` (decimal N and four-digit year); unknown debt-title forms reject the mapping rather than being silently ignored. Recognized note/debt registrations are distinct securities, not additional common classes; never confuse KO26 with KO. Require positive common-stock evidence; absence of ADR tags alone never suffices.
6. Confirm each original financial fact's concept, period, units, and value/scale against its filing context before affirming the relationship. Resolve XML namespace names, not assumed prefixes; match exact contexts and reject conflicting duplicates. Existing calculators and Company Facts remain the numerical source of truth; the parser validates evidence and does not replace or recompute financial inputs.
7. Set the ratio to 1 only as a derived statement that the positively identified quoted common share is the same single common-share unit used by those inputs. Record the mapping identifier, source accession(s), contexts, normalized class title, CIK, and provenance. This is an explicit policy inference requiring review, not an upstream ratio field or a universal claim about domestic stocks.
8. Limit the initial production acquisition mapping to `as_of=None`. Explicit historical boundaries receive `unsupported_temporal_evidence` unless a caller already supplies separately reviewed compatible evidence. Do not use a current name/classification snapshot to affirm a historical relationship. Keep current quote freshness policy unchanged and retain filing acceptance/retrieval timestamps separately.
9. For current runs, require consistent class identity across input filings and the current eligible annual filing, plus current SEC issuer/symbol confirmation. Document that this establishes the relationship from the inspected evidence, not exhaustive detection of every intervening corporate action. Contrary evidence rejects comparison; no automatic split/ADR/FX adjustment. Review must explicitly accept this evidence scope before implementation.
10. Explicit numeric overrides do not establish share identity. Resolve issuer/class evidence anyway; an override with unknown currency remains comparison-unavailable under the existing strict profile guard. Supplied complete profile evidence retains existing programmatic semantics. Fully override-driven unverified securities remain rejected as before.

Parser boundary: standard-library `HTMLParser` for bounded Inline XBRL markup plus explicit context/unit capture, supporting case-normalized HTML and nested text. Whitelist the above concepts and the numeric concepts needed to verify existing inputs. Detect continuation/exclude/nil/unsupported transformations and reject rather than silently concatenate incorrectly. Handle the observed nested numeric tags with a stack. Do not evaluate scripts, external entities, schema imports, or remote links. Resource policy: one document fetch per accession per invocation; 20-second transport timeout; 8 MiB maximum per document; four documents maximum; no new automatic retries. Define these defaults in a typed reader policy with documentation, not magic calculation constants. The observed issuer filing is about 3.8 MB; bounds are proposed engineering limits, not provider guarantees.

## 4. Interfaces and execution placement

Proposed additive contracts in `src/data/security_unit.py`:

- `SecurityUnitRequest(ticker, provider_id, as_of, inputs: tuple[ResolvedInput, ...], quote: ResolvedInput)`; validate normalized identifiers and explicit temporal/subject association. Financial values are borrowed immutable evidence; do not persist them anew.
- `SecurityUnitResolution(status, reason, evidence: SecurityUnitEvidence | None, provenance: SecurityUnitProvenance | None)`; reasons include provider unsupported/error, missing evidence, unsupported temporal evidence, source mismatch, and ambiguous class. Existing predicate enums/behavior stay compatible.
- `SecurityUnitProvenance(mapping_id, cik, accession_ids, document_urls, context_ids, class_title, filing_available_at, retrieved_at)` with immutable per-document records when timestamps differ. No secret/raw-document fields.
- `SecurityUnitProvider.resolve_security_unit(request) -> SecurityUnitResolution`, a runtime-checkable optional protocol; no registry.

Keep `compose_instrument_profile` responsible for pre-analysis identity/kind. Add `complete_security_unit_profile(profile, provider, request) -> InstrumentProfile` in the same module: preserve identity/kind, attach resolved unit evidence and its structured resolution, append one unit-capability diagnostic. This deliberately happens **after input resolution, within the existing financial-facts analysis scope**, so it can reference the actual source accessions and reuse the SEC snapshot. Extending the early metadata composition with a blind ticker-only lookup would repeat the defect at a different layer.

`InstrumentProfile` gains optional `security_unit_resolution` with default `None`; existing `security_unit_evidence` remains supported. Validate ticker/provider/CIK linkage and reject contradictory supplied blocks. If compatible caller-supplied evidence is present, preserve it without a new provider request. If the profile is absent, retain legacy semantics without new acquisition. If the profile exists but lacks evidence, the two Graham services complete it once after a successful assembly and before comparison. Return the enriched profile on the analysis result.

`ProductionFinancialFactsProvider.resolve_security_unit` delegates only to the requested provider's optional capability. The SEC adapter implements it using its active snapshot; unsupported adapters report unsupported without making unexpected calls. Preserve dependency injection. Extend the SEC snapshot with immutable accession→primary-document metadata and reuse request-local document reads; do not introduce a durable schema/cache. An evidence-only read failure suppresses comparison with a reason, not valid EPS/BVPS/quote results.

Add `PriceComparison(status, reason, percent, security_unit_resolution)` and `evaluate_price_comparison(...)` in shared financial resolution. Keep `margin_of_safety(...) -> float | None` as a compatibility wrapper using the same deterministic math. Add an optional defaulted `price_comparison` field to each analysis and presentation dataclass; keep `margin_of_safety_percent`. Production populates both consistently. Existing callers that construct presentation objects without the new field keep legacy rendering; no new evidence is invented for them.

CLI `_run_graham_number`/`_run_graham_growth` must render `analysis.instrument_profile` after completion, rather than the pre-analysis local profile. Use the same enriched profile for identity diagnostics and details. FCF/Momentum composition remains unchanged. The orchestrator's two Graham handlers already call these services: preserve injected no-profile behavior and verify enriched results reach its existing serialization path; no new orchestration framework or tool argument is needed.

## 5. Reasons, output, and schema contract

Deterministic precedence: unavailable/invalid/not-applicable calculation → missing quote → non-positive reference → known currency mismatch → evidence acquisition/temporal/subject failure → existing security-unit predicate reasons → finite deterministic percentage. The existing predicate's internal precedence remains unchanged for its direct callers. No reason may overwrite the overall valid calculation status merely because comparison is unavailable.

Public examples: `Price comparison: unavailable (share-unit evidence is missing)`; `(filing and quoted share classes could not be matched)`; `(historical share-unit evidence is unsupported)`; `(valuation and quote currencies differ)`. Provider errors use a sanitized capability message, not raw transport exceptions. Successful wording and rounding remain `Price relationship: ...% above/below ...`; zero retains existing wording.

Details show class/unit relationship, provider, mapping, accession and evidence timing. Diagnostics add stable status/reason and context identifiers; no provider HTML. No logging migration.

Current Graham presentation schema is 3. Propose schema **4**, following the existing explicit presentation-version convention, with all existing keys and number meanings preserved plus a top-level `price_comparison` object: `{status, reason, percent, security_unit_evidence, provenance}`. Unavailable `percent` is null; the legacy result percentage is the same null/value. Evidence/provenance are nullable typed projections. Update schema assertions and document the version change; do not label a version bump backwards compatible for consumers pinned to 3. No database/result-storage migration is part of this repair. R1 approval explicitly approves this versioned output extension.

## 6. Exact file scope and tests

Production allowlist (R2 only):

- `src/data/security_unit.py`, `src/data/instrument_profile.py` — additive request/resolution/provenance and profile completion.
- New `src/data/sec_edgar/security_unit.py` — pure mapping/parser and typed reader policy; new `src/data/sec_edgar/filing_document.py` — bounded injectable text transport, strict SEC URL construction and document reading. No new dependency.
- `src/data/sec_edgar/financial_facts.py` — snapshot document metadata and optional capability; `src/data/financial/production.py` — delegate it.
- `src/analysis/shared/financial_resolution.py`; both `src/analysis/strategy/graham_number/service.py` and `src/analysis/strategy/graham_growth/service.py` — comparison result, within-scope evidence completion, legacy preservation.
- `src/cli.py`, `src/reporting/graham.py` — enriched result propagation, reasons, schema 4.

Test allowlist: new `tests/data/test_sec_security_unit.py` and `tests/test_graham_comparison_composition.py`; existing `tests/data/test_security_unit.py`, `test_instrument_profile.py`, `test_provider_security_identity.py`, `test_production_quote_routing.py`; `tests/analysis/graham_value/test_security_unit_compatibility.py`, `test_production_providers.py`, `test_method_analyzers.py`; `tests/test_cli.py`, `test_cli_graham_commands.py`, `test_cli_graham_nonpositive_growth.py`; reporting Graham tests whose version/output contracts change. Add synthetic reduced Inline XBRL fixtures under `tests/fixtures/security_unit/`; label them synthetic and include exact observed shapes without storing the full filing. If another consumer actually requires edits, identify it and review the allowlist expansion before changing unrelated code.

Documentation: root README correction plus `docs/user/strategies/GRAHAM.md`, `docs/user/USAGE.md`, `docs/user/FINANCE_MATH.md` only where comparison scope/version needs clarification; project architecture and repair/milestone records. Preserve the supplied README audit diff until reviewed against final behavior. No readiness implementation/user-guide rewrite here.

Required R2 proof:

- End-to-end positive cases for both methods through production facade, SEC adapter, synthetic JSON/Inline XBRL fetchers, real profile completion and rendering. No test may get a passing comparison only by prebuilding unit evidence or mocking the comparison result.
- Cover KO-shaped common-stock and multiple-note contexts; distinguish debt symbols. Match nested numeric tags, class dimensions, namespace aliases, scales, duplicate/continuation failures, and unsupported contexts. Class A/B, ADR/ADS, unknown title/ratio, multiple common classes and currency mismatch must remain unavailable with reasons.
- Original-accession lineage on cache hits, four-document bound, unavailable primary document, mismatched CIK/symbol, provider failure, no-network fixtures, explicit historical requests, and unsupported provider inputs. Prove no evidence exception discards a valid standalone value/quote.
- Missing/invalid quote and non-positive Growth reference; supplied-profile/no-profile legacy callers; mathematical percentage from unrounded values; JSON 4 plus old field equality; all presentation modes retain identity/provenance.
- Typed source contracts, focused regression checks and full managed gate. Existing 1,944-test baseline is not acceptance evidence for new implementation.

## 7. Review decision requested

**Subsequent approval record:** The user accepted R1 and explicitly authorized
R2. During implementation, source inspection established that derived common
shares and inferred zero preferred shares did not retain verifiable source
accessions. The user approved extending the repair to preserve typed lineage
for those existing outputs without changing their calculations or assumptions.
The production allowlist therefore also includes `src/data/financial/facts.py`
and `src/data/financial/resolver.py`. Raw share-count sources use a separate
type so zero treasury shares remain valid without weakening the positive
shares-outstanding contract. Legacy cache entries without lineage remain
comparison-unavailable; `--no-cache` resolves fresh inputs but does not rewrite
those existing entries. The decision request below is retained as the original
R1 review record, not a pending authorization gate.

Approve the proposed narrow filing-document evidence acquisition, single-common-class policy inference, current-only automatic acquisition, bounded transport, additive service/profile contracts, and presentation schema 4. These are concrete changes beyond simply forwarding an existing field. Review should assess the deliberately limited security/provider coverage and evidence-timing limitation. If those boundaries are rejected, revise the mapping before R2; never bypass the guard to force the README example to pass.

At the original R1 checkpoint, no production fix, branch switch, commit, push, or database operation had been performed. R2 subsequently proceeded on `fix/graham-price-comparison` with the small README audit correction and accepted planning context; database-readiness implementation remains separate.
