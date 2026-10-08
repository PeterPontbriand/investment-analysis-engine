# R3 – Repository-wide Dead Code Audit – Close-out

## 1. Scope and method

The audit covered potentially unreachable branches, functions, modules, and files across all of
`src/`. A full tree of `src/` and `tests/`, plus known execution roots, was supplied to a locally
hosted language model under a conservative system prompt focused on reachability
evidence. Live roots included the `ian` entry point through `src.main:main` to `src.cli.app`,
evaluation runners, and workspace, reporting, and other production execution paths.

Static checks ran first: Vulture at minimum confidence 80, followed by Ruff's unused-import and
unused-variable checks. Model-proposed candidates were then checked against direct import searches
and reviewed against their callers and use paths. The model was used to suggest candidates; source
and import evidence determined disposition.

## 2. Findings

No high-confidence unreachable modules, functions, branches, or files were found. Ruff's
unused-import and unused-variable report was empty. Vulture reported only the unused exception
parameters `exc_val` and `exc_tb` in `src/utils/logger_util.py`'s `__exit__`; these parameters are
cosmetic and do not constitute dead code. They were left unchanged.

## 3. Evidence summary

- The known entry points and the full source and test trees were included when assessing reachability.
- Direct import searches falsified every initial model candidate: each had active use from
  production paths, evaluation, workspace execution, reporting, or tests.
- The final disposition relied on those source-level checks and review, not on the model's
  suggestions alone.

## 4. Disposition and status

**Work package status:** Complete — 2026-10-01.

There are no required residual actions. Renaming the unused exception parameters is an optional
cosmetic cleanup and can be handled separately. Repeat a repository-wide audit after the Step 3.5
expansion adds its quantitative-screen analyzers.

## 5. Second pass: confidence 60 triage and deliberately kept items

A second pass ran Vulture at minimum confidence 60 (the first pass used 80) and sorted every finding into
a mechanism false positive (Pydantic fields, validators and `model_config`, Typer commands, enum members
read by value, protocol and standard-library overrides), a test-only item, a dead item, or an unsure
item. Dead items and approved test-only items were deleted together with the code and tests that existed
only for them. The items below were reviewed and **deliberately kept**.

| Item | Reason kept |
|---|---|
| `workspace.codecs.encode_evidence`, `workspace.requests.parse_selection` | Read by `scripts/strategy_conformance.py` and tests; no production caller. |
| `InstrumentProfileRecord.superseded_reason` | Mirrors a stored column that the repository writes and reads back. |
| `FCF_GROWTH_YEARS`, `FCF_GROWTH_EPS_VALUES`, `FCF_GROWTH_CAPEX`, `FCF_GROWTH_DILUTED_SHARES`, `GOLDEN_EXPECTED_GROWTH` | Reviewed evaluation fixture truth that tests compare against. |
| `provider_checks.MAX_REQUESTS_PER_CHECK` | A provider-check test asserts the request budget against it. |
| `SQLiteMarketDataRepository.list_keys`, `SQLiteResolvedInputCache.list_keys`, `SQLiteInstrumentProfileRepository.get_by_id` | Listed as repository interface in `docs/project/ARCHITECTURE.md`. |
| `strategies.fcf_growth.calculators.compute_fcf_yield` | Step 3.5's FCF-yield screen either uses it or deletes it (see the Step 3.5 contract's shared-definitions slice). |
| `RunOutcome.CANCELLED` and the `'cancelled'` value in the analysis-run outcome check constraint | Nothing produces it; removal changes the database schema. |
| `strategy_wiring.evidence_by_type`, `strategy_wiring.parsers_by_alias` | Built by `scripts/strategy_conformance.py` and the test helpers; no production layer reads these views. |
| `StrategyIndexes.by_key`, `StrategyIndexes.by_envelope` | Building them enforces key and envelope uniqueness at import; only the conformance tests read them. |
| `AccountingScope.SEGMENT` | Member of a closed vocabulary; removing it changes a generated schema. |
| `exc_val`, `exc_tb` in `LoggerContext.__exit__` | Required context-manager signature (recorded in the first pass). |

## 6. References

- [R3 audit plan](R3_DEAD_CODE_AUDIT_PLAN.md)
- [Milestone v0.2 Implementation Plan sequencing](../IMPLEMENTATION_PLAN.md#sequence-and-status)
- [Master Plan sequencing note](../../../MASTER_PLAN.md#8-ordered-implementation-steps--release-milestones)
- Close-out date: 2026-10-01
