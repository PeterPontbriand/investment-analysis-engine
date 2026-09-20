# Slice B2 — Completion evidence

**Review disposition:** accepted on 2026-09-14 (America/Toronto). This record is the Slice B2 acceptance basis; B3 may proceed under its own handoff and review gate per contract §9.

## Revisions and scope

Verified branch: `feat/step-3.4-local-research-workspace`.
Slice B1 was accepted on 2026-09-13 against its [completion evidence](SLICE_B1_COMPLETION_EVIDENCE.md); B2 builds directly on the B1 request contracts and adds no new dependencies.

The delivered diff for this slice contains only:

- `src/workspace/models.py`
- `src/workspace/runs.py`
- `tests/workspace/test_workspace_models.py`
- `tests/workspace/test_runs.py`
- Companion evidence in this planning directory: [Slice B1](SLICE_B1_COMPLETION_EVIDENCE.md) (predecessor) and this final record.

No dependency files, existing analyzers/calculators, CLI, migrations, repositories or settings were changed. Unrelated uncommitted Step 3.5 (Piotroski) planning documents remained untouched and are outside this slice's scope. B2 changes are present in the working tree pending this acceptance; no commit was made as part of recording it.

## Interfaces and design decisions

Slice B2 adds the immutable run-envelope, watchlist, query and summary contracts named in [contract §9](STEP_3_4_CONTRACT_AND_SLICE_PLAN.md#9-fine-grained-implementation-slices). All models are frozen Pydantic (`frozen=True`, `extra="forbid"`) via a shared `_FrozenModel` base; all timestamps are timezone-aware; no field is mutable after construction. The module performs no persistence, codec, execution or adapter work.

### Supporting value types (`models.py`)

| Type | Shape / fields (name: type) |
| :--- | :--- |
| `RunOutcome(StrEnum)` | terminal only — `completed`, `unavailable`, `not_applicable`, `failed`, `cancelled`; no `running` value |
| `JsonValue` | recursive JSON primitive (`bool \| int \| float \| str \| None \| list[JsonValue] \| dict[str, JsonValue]`) with a runtime validator rejecting NaN/Inf and non-primitives |
| `StrictJsonMapping` | `dict[str, JsonValue]` |
| `EffectiveBoundary` | frozen; `start: date \| None = None`; `end: date \| None = None`; invariant `end >= start` when both present |

### Envelope (`runs.py`) — `AnalysisRun`, frozen, `extra="forbid"`

| Group | Fields (name: type) |
| :--- | :--- |
| Identity | `analysis_run_id: UUID`; `refresh_id: UUID \| None = None`; `batch_position: int \| None (ge=0) = None`; `watchlist_id: UUID \| None = None`; `watchlist_name: str \| None = None`; `telemetry_run_id: UUID \| None = None` |
| Request | `ticker: str`; `analysis_id: str`; `method_id: str`; `config_schema_version: int (ge=1)`; `requested_config: AnalysisSelection`; `effective_config: AnalysisSelection \| None = None` |
| Time | `started_at: AwareDatetime`; `completed_at: AwareDatetime`; `requested_as_of: AwareDatetime \| None = None`; `effective_boundary: EffectiveBoundary \| None = None`; `source_observation_dates: tuple[date, ...] = ()`; `source_retrieval_at: AwareDatetime \| None = None` |
| Versions | `run_schema_version: Literal[1] = 1`; `method_version: int (ge=1)`; `result_schema_version: int (ge=1)`; `evidence_codec_version: int (ge=1)`; `projection_version: Literal[1] = 1` |
| Outcome | `status: RunOutcome`; `native_status: CalculationStatus \| None = None`; `native_reason: str \| None = None`; `failure_reason_code: str \| None = None` |
| Evidence / Presentation | `result_evidence: StrictJsonMapping \| None = None`; `presentation_inputs: StrictJsonMapping \| None = None` |

### Projections and watchlist (`runs.py`)

| Type | Fields (name: type) |
| :--- | :--- |
| `AnalysisRunSummary` | `analysis_run_id: UUID`; `ticker: str`; `method_id: str`; `status: RunOutcome`; `completed_at: AwareDatetime`; `refresh_id: UUID \| None = None` — no `analysis_id`, no `started_at` (indexed columns exactly) |
| `RunQuery` | `ticker: str \| None = None`; `method_id: str \| None = None`; `status: RunOutcome \| None = None`; `refresh_id: UUID \| None = None`; `limit: int (ge=1, le=100) = 20`; `offset: int (ge=0) = 0` |
| `Watchlist` | `watchlist_id: UUID`; `display_name: str`; `normalized_name: str`; `created_at: AwareDatetime`; `updated_at: AwareDatetime \| None = None`; `members: tuple[str, ...] = ()`; `selections: tuple[AnalysisSelection, ...] = ()` |
| `WatchlistSummary` | `watchlist_id: UUID`; `display_name: str`; `member_count: int (ge=0)`; `selection_count: int (ge=0)`; `created_at: AwareDatetime`; `updated_at: AwareDatetime \| None = None` |

### Version-field semantics (spec-conformant)

Per [SLICE_B2_RUN_ENVELOPE_FIELD_SPEC.md](SLICE_B2_RUN_ENVELOPE_FIELD_SPEC.md), the two schema/projection version fields are fixed literals with defaults, while the three method/result/codec versions are strict positive integers that must be supplied explicitly:

| Field | Type | Default |
| :--- | :--- | :--- |
| `run_schema_version` | `Literal[1]` | `1` (fixed) |
| `projection_version` | `Literal[1]` | `1` (fixed) |
| `method_version` | `int` (`ge=1`) | required, no default |
| `result_schema_version` | `int` (`ge=1`) | required, no default |
| `evidence_codec_version` | `int` (`ge=1`) | required, no default |

A strict-int validator rejects `bool`, `float` and `str` for the four integer version fields. The implementation matches the spec exactly; **zero deviations** remain (an earlier draft that defaulted the three integer versions to `1` was corrected so only the two `Literal[1]` fields carry defaults).

## Acceptance criteria and tests

All named tests are in `tests/workspace/test_runs.py` (**41 cases**) and
`tests/workspace/test_workspace_models.py` (**17 cases**); **58 new test cases** total, as reported by the full gate.

| Spec rule ([field spec](SLICE_B2_RUN_ENVELOPE_FIELD_SPEC.md#validation-rules)) | Verification (named tests) |
| :--- | :--- |
| R1 `completed_at >= started_at` | `test_completed_at_before_started_rejected`; valid construction in `test_valid_completed_run_constructs_and_normalizes_ticker`, `test_one_valid_construction_per_outcome` |
| R2 `failed` ⇒ non-empty `failure_reason_code` | `test_failed_requires_failure_reason_code`; `test_failed_without_evidence_or_effective_config_constructs` |
| R3 `completed` ⇒ `result_evidence` not null; other statuses optional | `test_completed_requires_result_evidence`; `test_one_valid_construction_per_outcome`; `test_invalid_status_rejected` |
| R4 identifiers/version match embedded config(s) | `test_identifiers_must_match_requested_config`; `test_identifiers_must_match_effective_config_when_present` |
| R5 `EffectiveBoundary.end >= start` when both set | `test_effective_boundary_requires_end_on_or_after_start` (models tests) |
| R6 evidence/presentation floats finite; JSON primitives only | `test_non_finite_float_in_json_fields_rejected`; `test_json_value_rejects_non_finite_floats`, `test_json_value_rejects_nested_non_finite_floats`, `test_json_value_rejects_non_primitives`, `test_json_value_rejects_non_string_object_keys` (models tests) |
| R7 ticker normalized, non-empty | `test_valid_completed_run_constructs_and_normalizes_ticker`; `test_empty_ticker_rejected` |
| R8 `refresh_id`⟷`batch_position`, `watchlist_id`⟷`watchlist_name` both-set-or-null | `test_refresh_id_and_batch_position_must_pair`; `test_watchlist_id_and_name_must_pair` |
| R9 version fields strict int (not bool/float/string) | `test_version_fields_reject_invalid_values`; `test_required_version_fields_reject_omission` |
| W1 no duplicate `method_id` across selections | `test_duplicate_method_id_across_selections_rejected` |
| W2 members unique, order preserved | `test_valid_watchlist_preserves_member_order`; `test_duplicate_member_ticker_rejected` |
| W3 display_name non-empty after trim; normalized_name matches derived form | `test_blank_display_name_rejected`; `test_normalized_name_must_match_display_name` |
| Supporting types: terminal-only outcome, strict JSON, frozen boundary | `test_run_outcome_is_terminal_only`; `test_json_value_accepts_nested_primitives`; `test_effective_boundary_is_frozen_and_strict` (models tests) |
| Query bounds and summary projections construct | `test_run_query_defaults_and_bounds`; `test_summaries_construct` |

## Verification results

The authoritative wrapper was run from the repository root:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

The wrapper uses `uv run --no-sync`, unique repository-local temporary/cache directories, strict mypy over `src tests`, and the full pytest suite with coverage. No dependencies were synchronized.

| Final full gate | Result |
| :--- | :--- |
| Ruff check | Passed |
| Ruff format check | 345 files already formatted |
| `mypy --strict src tests` | Passed, 255 files |
| Full pytest | **2,670 passed** |
| Overall combined coverage | **90%**, above the 85% requirement |
| Slice B2 file coverage | `runs.py` **100%**; `models.py` **100%** (all lines covered) |

Environment: Windows, Python 3.14, pytest 9.x. Other Python versions were not separately exercised in this run. Isolated artifacts and HTML coverage were written to the unique ignored run directory under `.tmp/quality-runs/` for this invocation. The implementation diff passes whitespace checks; only this evidence document and the two tracking-table updates were added after the successful gate.

## Limitations and stop

Slice B2 supplies immutable run-envelope, watchlist, query and summary contracts only. Persistence (C1–C3), result codecs (B3–B6), execution adapters (D1–D5), refresh (G1–G3) and CLI file I/O remain later slices per [contract §9](STEP_3_4_CONTRACT_AND_SLICE_PLAN.md#9-fine-grained-implementation-slices). No live provider or LLM validation is claimed or required by this deterministic contract boundary. No public analyzer behavior was removed and no financial calculations were changed.

No unresolved B2 implementation or verification failures were found. **Zero deviations** from [SLICE_B2_RUN_ENVELOPE_FIELD_SPEC.md](SLICE_B2_RUN_ENVELOPE_FIELD_SPEC.md) remain; Slice B3 (Momentum codec) is unblocked subject to its own handoff and review gate. No commit, push or PR was performed. Stop for explicit B2 acceptance before B3.
