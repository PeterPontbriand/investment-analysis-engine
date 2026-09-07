# R2 migration inventory and R2-A checkpoint evidence

**Prepared:** 2026-09-07. **Source revision:** `fb1821965a846b61417bb22e905385aae9ca64c9` (clean working tree before this documentation work).
**Current status:** R2 complete and approved on 2026-09-07, including final Gate R2-E. Earlier sections preserve chronological evidence; final approval in handoff section 14 supersedes pending-gate snapshots.
**Contract:** [R2 handoff](R2_CONTRACT_AND_SLICE_PLAN.md). Inventory entries authorize no execution independently of its slice gates. Refresh the audit against the actual starting revision before each slice; reconcile new necessary files before editing.

## 1. Discovery and scope

Enumerated tracked files with `git ls-files`, including `.github/`, `.claude/`, `scripts/`, root configuration, source, tests, and documentation. The starting tree had no untracked files. Searches excluded Git internals, ignored virtual environments, caches, and generated artifacts. Literal searches covered dotted source and test imports, slash/backslash paths, short package names in Markdown directory trees, removed names, constructor dependencies, and private helper references. Dynamic import and parent-package import searches found no additional executable migration consumer.

Representative discovery commands (repository root):

```powershell
git ls-files
git grep -l -I -F -e 'analysis.graham_value' -e 'analysis.momentum' -e 'analysis.fcf_earnings_growth' -e 'analysis/graham_value' -e 'analysis/momentum' -e 'analysis/fcf_earnings_growth' -e 'analysis\graham_value' -e 'analysis\momentum' -e 'analysis\fcf_earnings_growth'
git grep -n -I -F -e 'graham_value' -e 'momentum_analyzer' -e 'fcf_earnings_growth/' -- '*.md'
git grep -l -I -F -e 'GrahamInputResolver' -e 'graham_resolver' -e 'AnalysisToolDependencies' -- src tests
git grep -n -I -F -e 'GrahamValueAnalyzer' -e 'GrahamValueConfig' -e 'GrahamValueMetrics'
git grep -n -I -F -e '_margin_of_safety' -e '_common_currency' -e '_resolve_eps' -e '_resolve_optional_quote' -e '_is_known_etf' -e '_validate_profile_ticker' -- tests
git grep -n -I -F -e 'from src.analysis import' -e 'import_module' -e 'graham_value_analyzer' -- src tests .github .claude scripts pyproject.toml
git --no-pager show --format=short --name-status 685221d
git --no-pager diff --name-status 685221d HEAD
```

## 2. R1 checkpoint reconciliation

Commit `685221d832e431f3b310e9eccbc26982761f9960` exists locally. Its parent is the R1-B checkpoint `36b8dbf`; its R1-C diff contains 21 files:

| Category | Actual files and reconciliation |
| :--- | :--- |
| Production (2) | `src/cli.py`, `src/cli_support.py`; exactly the R1-C production allowlist |
| Existing tests (7) | `tests/test_cli.py`, `tests/test_cli_financial_cache.py`, `tests/test_cli_historical_cache.py`, `tests/test_cli_graham_nonpositive_growth.py`, `tests/test_cli_graham_slice_f_routing.py`, `tests/test_graham_growth_default_policy.py`, `tests/data/test_massive_cli_configuration.py`; exactly R1 section 9 |
| New tests (2) | `tests/test_cli_support.py`, `tests/test_cli_graham_commands.py`; exactly R1 section 9 |
| Active guides (7) | `README.md`, `docs/user/USAGE.md`, `docs/user/QUICKSTART.md`, `docs/user/INSTALLATION.md`, `docs/user/SMOKE_TESTING.md`, `docs/user/strategies/GRAHAM.md`, `docs/user/GLOSSARY.md`; exactly R1 section 9 |
| Planning (3) | `docs/project/MASTER_PLAN.md`, `docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md`, `docs/project/milestones/v0.2/r1/R1_CONTRACT_AND_SLICE_PLAN.md`; roadmap/completion evidence, within planning synchronization scope |

The two tests identified for execution without edits (`tests/test_cli_fcf_earnings_growth.py`, `tests/evaluation/test_cli.py`) were not changed. No production files outside the CLI modules, dependencies, database migrations, or scratch files appear in the commit. R1 section 11 records final approval and section 10 records 1,809 tests/89% coverage. The sole intervening commit `fb18219` adds the R2 plan and updates only Master Plan/milestone planning; source and tests are identical to the R1 completion checkpoint. No unexplained R1 file-scope discrepancy was found.

## 3. R2-B deletion inventory

Delete only `src/analysis/graham_value/graham_value_analyzer.py` and `tests/analysis/graham_value/test_graham_value_analyzer.py` after Gate R2-A execution approval. Removed symbols: `GrahamValueAnalyzer`, `GrahamValueConfig`, `GrahamValueMetrics`. Searches find executable uses only in these two files; the package does not export them. Retain historical planning mentions under section 7. Existing retirement approval is recorded in the handoff and need not be requested again.

Exact collected legacy node IDs (44 cases, including parameterizations):

```text
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValueConfigDefaults::test_classic_defaults_from_toml
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValueConfigDefaults::test_non_positive_eps_rejected
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValueConfigDefaults::test_negative_eps_rejected
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValueConfigDefaults::test_zero_aaa_yield_rejected
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValueConfigGrowthHandling::test_no_upper_cap_on_growth_rate
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValueConfigGrowthHandling::test_negative_growth_collapse_rejected
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValueConfigGrowthHandling::test_negative_growth_within_band_allowed
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationComputation::test_intrinsic_value_formula
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationComputation::test_margin_of_safety_with_explicit_price
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationComputation::test_margin_of_safety_resolved_from_client_quote
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationComputation::test_quote_failure_yields_none_price_and_margin
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationComputation::test_zero_margin_of_safety
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationConfigurableConstants::test_configurable_constants
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationConfigurableConstants::test_zero_growth_multiplier_is_accepted
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValueConfigConstantConstraints::test_invalid_constants[base_pe-0.0]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValueConfigConstantConstraints::test_invalid_constants[base_pe--1.0]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValueConfigConstantConstraints::test_invalid_constants[growth_multiplier--0.5]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValueConfigConstantConstraints::test_invalid_constants[baseline_aaa_yield-0.0]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValueConfigConstantConstraints::test_invalid_constants[baseline_aaa_yield--4.4]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationEdgeCases::test_explicit_non_positive_price_rejected
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationEdgeCases::test_explicit_negative_price_rejected
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationEdgeCases::test_overvalued_price_produces_negative_margin
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationEdgeCases::test_explicit_nan_price_rejected
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationEdgeCases::test_explicit_inf_price_rejected
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationErrorPropagation::test_unexpected_quote_client_error_propagates
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationErrorPropagation::test_data_fetch_error_still_degrades_to_none_price
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteInputs::test_non_finite_numeric_inputs_rejected[eps-nan]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteInputs::test_non_finite_numeric_inputs_rejected[eps-inf]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteInputs::test_non_finite_numeric_inputs_rejected[eps--inf]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteInputs::test_non_finite_numeric_inputs_rejected[expected_growth_rate-nan]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteInputs::test_non_finite_numeric_inputs_rejected[expected_growth_rate-inf]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteInputs::test_non_finite_numeric_inputs_rejected[current_aaa_yield-nan]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteInputs::test_non_finite_numeric_inputs_rejected[current_aaa_yield-inf]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteInputs::test_non_finite_numeric_inputs_rejected[base_pe-nan]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteInputs::test_non_finite_numeric_inputs_rejected[base_pe-inf]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteInputs::test_non_finite_numeric_inputs_rejected[growth_multiplier-nan]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteInputs::test_non_finite_numeric_inputs_rejected[growth_multiplier-inf]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteInputs::test_non_finite_numeric_inputs_rejected[baseline_aaa_yield-nan]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteInputs::test_non_finite_numeric_inputs_rejected[baseline_aaa_yield-inf]
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteOutputs::test_oversized_eps_infinite_intrinsic_value_rejected
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteOutputs::test_oversized_growth_rate_infinite_intrinsic_value_rejected
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationFiniteOutputs::test_non_finite_margin_of_safety_rejected
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationMetadata::test_utc_timestamp
tests/analysis/graham_value/test_graham_value_analyzer.py::TestGrahamValuationMetadata::test_ticker_behavior
```

Collection used `uv run --no-sync pytest -o addopts= -p no:cacheprovider --collect-only -q tests/analysis/graham_value/test_graham_value_analyzer.py` with unique repository-local TEMP/TMP/UV_CACHE_DIR. Artifact: `.tmp/quality-runs/r2-a-collection-a3f5cd84487544ec86534992e1006684/legacy-nodeids.txt`. No tests were removed. With no other changes, the expected post-R2-B suite count is 1,765 (1,809 minus 44); later additions must be accounted for separately.

## 4. R2-C exact edit inventory

Production: `src/analysis/graham_value/input_resolver.py`, `src/analysis/graham_value/service.py`, `src/analysis/fcf_earnings_growth/analyzer.py`.

New files: `src/analysis/shared/__init__.py`, `src/analysis/shared/financial_resolution.py`, `tests/analysis/shared/test_financial_resolution.py`.

Existing tests to update/add assertions: `tests/analysis/test_instrument_applicability.py`, `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_analyzer.py`, `tests/analysis/graham_value/test_security_unit_compatibility.py`.

The last file directly imports `_margin_of_safety` from Graham service (line 8) and calls it at lines 39, 54, 64, and 74. Change that import and call spelling to shared `margin_of_safety`, preserving every argument/assertion. This is a direct private-symbol consumer adaptation, not permission to weaken expectations. No other test consumer of the extracted private implementations was found. No Momentum edit, other source edit, or data-resolver edit is required in this slice.

## 5. R2-D exact source and consumer inventory

Existing strategy files below are redistributed per the handoff's symbol map. The legacy module is already deleted in R2-B; all other source files receive their specified new destinations. Momentum/FCF filenames remain unchanged; no test directories are physically moved in this inventory.

- `src/analysis/fcf_earnings_growth/__init__.py`
- `src/analysis/fcf_earnings_growth/analyzer.py`
- `src/analysis/fcf_earnings_growth/calculators.py`
- `src/analysis/fcf_earnings_growth/input_resolver.py`
- `src/analysis/fcf_earnings_growth/models.py`
- `src/analysis/graham_value/__init__.py`
- `src/analysis/graham_value/analyzer_config.py`
- `src/analysis/graham_value/analyzers.py`
- `src/analysis/graham_value/calculators.py`
- `src/analysis/graham_value/graham_value_analyzer.py`
- `src/analysis/graham_value/input_resolver.py`
- `src/analysis/graham_value/models.py`
- `src/analysis/graham_value/service.py`
- `src/analysis/momentum/__init__.py`
- `src/analysis/momentum/momentum_analyzer.py`

Production consumers outside the relocated packages (imports and approved resolver dependency construction/types only):

- `src/cli.py`
- `src/evaluation/catalog.py`
- `src/evaluation/composition.py`
- `src/evaluation/runner.py`
- `src/orchestrator/analysis_tools.py`
- `src/reporting/fcf_earnings_growth.py`
- `src/reporting/graham.py`
- `src/reporting/momentum.py`

Create `src/analysis/strategy/__init__.py`, `src/analysis/shared/graham_contracts.py`, and each Graham destination package's `__init__.py`, `config.py`, `calculation.py`, `service.py`, `analyzer.py`. Momentum/FCF destinations are listed in the handoff. The shared `__init__.py` may receive export adjustments only. Preserve the public export lists from existing Graham/FCF `__init__.py`; Momentum's current `__init__.py` contains no exports. Preserve common enum object identities and serialized values. No `src/analysis/__init__.py` re-export migration is needed.

The combined dependency field changes in `src/orchestrator/analysis_tools.py`; method calls select the corresponding new resolver. `src/evaluation/composition.py` constructs both wrappers over the same borrowed provider/cache/clock. CLI method entry points instantiate their respective resolver. Retain service functions, argument models, tool identifiers, policy/result values, and resource ownership.

Tests requiring source import/patch target, resolver construction, or dependency-field migration:

- `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_analyzer.py`
- `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_calculators.py`
- `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_classification.py`
- `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_input_resolver.py`
- `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_models.py`
- `tests/analysis/fcf_earnings_growth/test_production_composition.py`
- `tests/analysis/fcf_earnings_growth/test_sec_edgar_analysis_snapshot.py`
- `tests/analysis/fcf_earnings_growth/test_sec_edgar_integration.py`
- `tests/analysis/graham_value/test_analyzer_config.py`
- `tests/analysis/graham_value/test_bvps_basis_semantics.py`
- `tests/analysis/graham_value/test_calculators.py`
- `tests/analysis/graham_value/test_fixture_provider.py`
- `tests/analysis/graham_value/test_method_analyzers.py`
- `tests/analysis/graham_value/test_production_providers.py`
- `tests/analysis/graham_value/test_resolution_trace.py`
- `tests/analysis/graham_value/test_resolver.py`
- `tests/analysis/graham_value/test_sec_bvps_hardening.py`
- `tests/analysis/graham_value/test_security_unit_compatibility.py`
- `tests/analysis/momentum/test_momentum_analyzer.py`
- `tests/analysis/momentum/test_momentum_hardening.py`
- `tests/analysis/test_instrument_applicability.py`
- `tests/data/repositories/test_series_cache.py`
- `tests/evaluation/cases/test_fcf_earnings_growth.py`
- `tests/evaluation/cases/test_graham_g3.py`
- `tests/evaluation/cases/test_graham_number.py`
- `tests/evaluation/cases/test_momentum.py`
- `tests/evaluation/test_composition.py`
- `tests/orchestrator/test_analysis_tools.py`
- `tests/reporting/test_display_labels.py`
- `tests/reporting/test_graham_concise_hierarchy.py`
- `tests/reporting/test_graham_nonpositive_growth_presentation.py`
- `tests/reporting/test_graham_number_basis_summary.py`
- `tests/reporting/test_graham_presenter.py`
- `tests/reporting/test_momentum_presenter.py`
- `tests/reporting/test_security_identity_presenters.py`
- `tests/test_cli_financial_cache.py`
- `tests/test_cli_graham_commands.py`
- `tests/test_cli_graham_nonpositive_growth.py`
- `tests/test_cli_graham_slice_f_routing.py`
- `tests/test_cli_historical_cache.py`
- `tests/test_cli.py`
- `tests/test_graham_growth_default_policy.py`

Retain all existing test functions/parameterizations except section 3's explicit deletion. Mixed Graham test modules remain at their current test paths and import both new strategies as needed. Preserve test fixture imports under `tests.analysis.graham_value`; that directory is not a removed production path.

Verified no required edits: `src/cli_support.py`; `tests/data/test_provider_security_identity.py` (only a retained `tests.analysis.graham_value.conftest` import); `.claude/commands/{analyze-momentum,refactor-modernize,run-tests}.md`; `.github/pr_formatter.ps1`; `.github/workflows/ci.yaml`; `scripts/run-quality-gates.ps1`; `scripts/run-quality-gates.sh`; `pyproject.toml`; `uv.lock`. No dynamic registration or module-path configuration consumer was found. Root README and active user guides contain no old source paths requiring migration. Run the full suite, including unaffected integration/composition tests; the edit list is not a reduced test gate.

## 6. R2-E active documentation inventory

- `docs/project/ARCHITECTURE.md`, section 5: update the current analysis directory tree to the accepted shared/strategy layout. Its `base.py` label is already stale; use actual `base_analyzer.py` while updating this exact tree. Do not expand into unrelated architecture cleanup.
- `docs/project/DISCOVERY_WORKBOOK.md`, module tree around lines 225–229: update analysis paths and the same stale base filename, preserving unrelated historical rationale. The general statement about analyzers under `src/analysis/` remains true.
- `docs/project/MASTER_PLAN.md`, `docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md`, this inventory, and the R2 handoff: update evidence/status only as each gate actually passes.

No runnable old-path documentation example was found outside historical records, so no additional executable documentation edit is required in R2-D. Active `docs/EVALUATIONS.md` describes stable tool names and the unchanged orchestration module path; retain it.

## 7. Exact retained-reference classifications

| File | Reason for retention |
| :--- | :--- |
| `docs/project/milestones/v0.2/r1/R1_CONTRACT_AND_SLICE_PLAN.md` | Completed R1 scope/approval and original source/test locations; historical evidence |
| `docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md` | Historical R1 preservation decision and current explicit R2 migration map; do not erase the old approval |
| `docs/project/milestones/v0.2/step-2.2/MOMENTUM_DESIGN.md` | Historical Momentum design and original test locations |
| `docs/project/milestones/v0.2/step-2.4/STEP_2_4_SLICE_A_RECONNAISSANCE.md` | Completed reconnaissance's original source/fixture inventory |
| `docs/project/milestones/v0.2/step-2.5/STEP_2_5_GOLDEN_SUITE_SLICE_PLAN.md` | Completed Golden work's original service-path scope |
| `docs/project/milestones/v0.2/step-2.5a/STEP_2_5A_D0_EVIDENCE_FREEZE.md` | Frozen prior source/test evidence; never rewrite as if gathered at new paths |
| `docs/project/milestones/v0.2/r2/R2_CONTRACT_AND_SLICE_PLAN.md` | Explicit old-to-new contract and named retirement explanation |
| `docs/project/milestones/v0.2/r2/R2_MIGRATION_INVENTORY.md` | This audit's exact old-path/node-ID evidence and migration instructions |

These historical/migration mentions and retained `tests.analysis.*` fixture imports are not obsolete executable production references. Stable tool/strategy IDs containing `fcf_earnings_growth` or `graham_growth_value` are not module paths and must not be renamed. Reference classification is reviewed here; final sweep must confirm actual implementation dispositions.

## 8. Fresh managed baseline and gate disposition

Managed gate passed on 2026-09-07 against `fb1821965a846b61417bb22e905385aae9ca64c9`, before these documentation edits:

- Ruff check passed; format check: 275 files already formatted.
- Strict mypy: no issues in 216 source files.
- Pytest: 1,809 passed in 34.21 seconds; Python 3.14.7.
- Coverage report: 9,398 statements, 788 missing (8,610 covered); 2,990 branches, 499 partial branches; 89% combined reported coverage. Statement coverage is approximately 91.6%, above the 85% line-coverage target. Preserve these distinctions when comparing later reports.
- Artifacts: `.tmp/quality-runs/20260907085055458-31808-b5deeff64485470fa6c88689f4b3d8f2/`, including `.coverage` and `htmlcov/`.

Command: `& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')`. The initial sandbox attempt failed before checks with Python interpreter access denied (artifact directory `.tmp/quality-runs/20260907085029922-9404-2e8b55d86f23411ebe06019e7de6ecf7/`). The same unchanged wrapper then passed with approved escalated interpreter access. Both attempts kept temp/cache/coverage paths under the repository; no dependency synchronization or installation occurred.

Section 9.3 evidence is complete. No new financial or resolver-design decision is required. This audit refines the already permitted private-consumer adaptation and exact file allowlists; it does not implement them. Gate R2-A stakeholder review remains pending; no R2-B execution, commit, push, or PR has occurred.

## 9. R2-B disposition (2026-09-07)

Gate R2-A review completed and R2-B execution was explicitly authorized. The two section 3 files are now deleted; all 44 itemized cases are retired, with no other production/test edits. A fresh pre-deletion baseline passed 1,809 tests; the post-deletion full gate passed 1,765 tests at 89% reported coverage. Retained statement coverage is unchanged on a per-file basis. See [handoff section 10](R2_CONTRACT_AND_SLICE_PLAN.md#10-gate-r2-a-approval-and-r2-b-execution-record) for both artifact directories and detailed coverage accounting. Executable references are absent; historical exceptions remain. Gate R2-B review is pending; no later slice has started.

## 10. R2-C disposition (2026-09-07)

Gate R2-B was approved and R2-C explicitly authorized. Every section 4 production/test edit is implemented, including the direct margin-helper import/name migration. No other production/test file was edited by this slice. The 46 new cases and pre/post managed gate evidence are recorded in [handoff section 11](R2_CONTRACT_AND_SLICE_PLAN.md#11-gate-r2-b-approval-and-r2-c-implementation-evidence). Final gate: 1,811 tests, 89% reported coverage, all shared-module statements/branches covered, Ruff/formatting/strict mypy passed. Gate R2-C review remains pending; section 5 package relocation has not started.

## 11. R2-D refreshed inventory (2026-09-07)

The clean pushed checkpoint is `fa6c2c9addbda4c36c1dd133f1b404eb00f4e9b6`. R2-D execution is explicitly authorized. The source/test consumer list remains applicable after R2-C. CLI `_build_graham_resolver` must accept the requested resolver type, so both command call sites and the existing builder tests migrate together. Mixed-method fixtures select the corresponding concrete resolver without retaining a combined class. Existing test paths stay fixed. No new production file outside the approved packages/consumer list is needed. The fresh full baseline passed 1,811 tests at 89% reported coverage; artifacts: `.tmp/quality-runs/20260907093925994-28964-9e4c6bff4eb747b59b1106ad32d6e35c/`.

## 12. R2-D disposition (2026-09-07)

All section 5 production package/consumer migrations are complete within the refreshed scope. The old Graham, Momentum, and FCF source directories are removed; every new strategy package is importable. Existing test locations and fixture namespaces remain unchanged. `tests/analysis/graham_value/test_security_unit_compatibility.py` needed no further edit because R2-C already migrated its only affected import; all other inventoried affected test consumers were updated. No executable documentation/configuration consumer was discovered. Section 6 active architecture/discovery tree updates remain pending R2-E.

The complete managed gate passed 1,811 tests, Ruff/formatting, and strict mypy at 89% reported coverage. See [handoff section 12](R2_CONTRACT_AND_SLICE_PLAN.md#12-gate-r2-c-approval-and-r2-d-implementation-evidence) for final artifact paths, retained-case audit, exact coverage reconciliation, and scope review. Gates R2-A/R2-B/R2-C are approved; R2-D implementation is verified and awaits Gate R2-D review. R2-E is not authorized.

## 13. R2-E refreshed scope (2026-09-07)

Gate R2-D is approved and R2-E is explicitly authorized from clean pushed checkpoint `9e42867d1fb1dc4ebdbc8daa4559640c5cdda6f3`. Refreshing section 6 found additional obsolete active references within its already inventoried documents: ARCHITECTURE section 3 input-resolution heading and section 6 data-flow diagram, plus DISCOVERY_WORKBOOK section 8 flow diagram and section 24 glossary entry. These need the two method-resolver names in addition to the directory-tree updates. This documentation scope reconciliation precedes those edits; no executable consumer was discovered.

Additional retained historical reference: `docs/project/milestones/v0.2/step-2.3/STEP_2_3_GRAHAM_DESIGN.md`, section 9.2, records the original combined resolver design. Retain its original wording as historical implementation evidence, like the other completed milestone designs in section 7; current resolver ownership is defined by the active architecture and R2 handoff. No new file outside the six inventoried active/planning documents requires editing.

## 14. Final reference and scope disposition

All active documentation entries in section 6 and the section 13 additions are reconciled. Architecture and discovery now match the implemented strategy directories and method-specific resolver ownership. Package exports and source paths were checked against the actual files; the combined resolver and old source directories are absent. The executable source/test/script/configuration sweep found no old dotted paths, filesystem paths, or retired symbols. No production/test repair or R2-D scope amendment is required.

Remaining old-name references occur only in the eight historical/migration files classified in section 7 and the original Graham design added in section 13. These are retained as historical evidence or explicit migration instructions, not active import guidance. Existing `tests.analysis.graham_value` fixture imports and stable serialized strategy/tool identifiers are preserved. Historical gate snapshots in this record remain chronological evidence; the current-status header and final disposition supersede their pending-gate wording.

Only six files changed in R2-E: ARCHITECTURE, DISCOVERY_WORKBOOK, MASTER_PLAN, the v0.2 IMPLEMENTATION_PLAN, this inventory, and the R2 handoff. The full baseline and final managed gates passed with unchanged test counts and coverage. See handoff section 13 for exact artifacts and reconciliation. Gate R2-E review remains pending; R2 is not yet marked complete.

## 15. Final approval

Final R2 approval was granted on 2026-09-07. All reference dispositions and verification evidence are accepted; Gate R2-E is closed and R2 is complete. See [handoff section 14](R2_CONTRACT_AND_SLICE_PLAN.md#14-final-approval-and-r2-completion).
