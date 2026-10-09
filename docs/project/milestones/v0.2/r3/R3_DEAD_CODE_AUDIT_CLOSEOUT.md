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

The rule applied: code read only by its own tests is dead; code read by the schema generator or the conformance script is in use.

| Item | Reason kept |
|---|---|
| `InstrumentProfileRecord.superseded_reason` | Mirrors a stored column that the repository writes and reads back. |
| `FCF_GROWTH_YEARS`, `FCF_GROWTH_EPS_VALUES`, `FCF_GROWTH_CAPEX`, `FCF_GROWTH_DILUTED_SHARES`, `GOLDEN_EXPECTED_GROWTH` | Reviewed evaluation fixture truth that tests compare against. |
| `provider_checks.MAX_REQUESTS_PER_CHECK` | A provider-check test asserts the request budget against it. |
| `SQLiteMarketDataRepository.list_keys`, `SQLiteResolvedInputCache.list_keys`, `SQLiteInstrumentProfileRepository.get_by_id` | Listed as repository interface in `docs/project/ARCHITECTURE.md`. |
| `strategies.fcf_growth.calculators.compute_fcf_yield` | Step 3.5's FCF-yield screen either uses it or deletes it (see the Step 3.5 contract's shared-definitions slice). |
| `StrategyIndexes.by_key`, `StrategyIndexes.by_envelope` | Building them enforces key and envelope uniqueness at import; only the conformance tests read them. |
| `StrategyDescriptor.json_envelope` | Read by the schema generator and the schema drift check. |
| `EvaluationStrategy.sample_selection` | Read by the conformance script's stored-run probe; each strategy must supply one. |
| `AccountingScope.SEGMENT` | Member of a closed vocabulary; removing it changes a generated schema. |

A third pass (2026-10-08) deleted the two dispatch routes that only tests and the conformance script ran: `parse_selection`, the descriptor `parse` member, `parse_for` and `parsers_by_alias`, and `encode_evidence` with `evidence_by_type`. Production builds a selection from command-line options and reads a stored one with `decode_selection`, and encodes through the run spec of the run's own strategy. They are no longer on the kept list.

A fourth pass (2026-10-08) made logging reach the log file and deleted what it left without a role: `worker.py`, `setup_logger`, `LoggerContext`, `ContextualAdapter` (with its `context_data` branch) and the console handler with its colour formatter. Nothing from the logging utility is on the kept list.

A fifth pass (2026-10-09) removed `RunOutcome.CANCELLED` and the `'cancelled'` value in the analysis-run outcome check constraint. Nothing produced it: a run's outcome is chosen by each strategy's outcome mapping, which never returns it, and the only other places an outcome is built from text are the stored-row decoder and the `--status` filter. An interrupted run stores nothing, or the refresh finishes the jobs already running and saves them with their own outcome, so a cancelled run is not a state the project has. Removal changes the database schema, so it ships as the revision `0005_remove_cancelled_outcome`. It is no longer on the kept list.

## 6. References

- [R3 audit plan](R3_DEAD_CODE_AUDIT_PLAN.md)
- [Milestone v0.2 Implementation Plan sequencing](../IMPLEMENTATION_PLAN.md#sequence-and-status)
- [Master Plan sequencing note](../../../MASTER_PLAN.md#8-ordered-implementation-steps--release-milestones)
- Close-out date: 2026-10-01
