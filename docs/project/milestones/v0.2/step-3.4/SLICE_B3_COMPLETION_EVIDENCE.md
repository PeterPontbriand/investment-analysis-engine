# Slice B3 — Completion evidence

**Review disposition:** implementation complete; awaiting B3 acceptance.
**Date:** 2026-09-14 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

B2 acceptance was verified against its [evidence record](SLICE_B2_COMPLETION_EVIDENCE.md).
The user authorized B3 implementation. The [slice contract](STEP_3_4_CONTRACT_AND_SLICE_PLAN.md#9-fine-grained-implementation-slices)
requires review before proceeding to B4.

## Delivered scope

- `src/workspace/momentum.py`: a fixed Pydantic JSON schema for `MomentumRun`,
  reconstructing its declared dataclasses/enums, dates, optional metrics,
  historical context, price provenance/lineage, trace, profile and share-unit evidence.
- `src/workspace/codecs.py`: explicit Momentum/version dispatch, detached encoding,
  envelope ticker validation, and stable `unsupported_run_version` /
  `invalid_stored_run` error classifications with safe outer messages.
- `tests/workspace/test_momentum_codec.py`: 29 deterministic preservation and
  corruption tests.
- This completion record.

The evidence wire shape is `{"run": <typed MomentumRun fields>}` inside
`AnalysisRun.result_evidence`. The envelope owns the independent method, result,
codec, run, configuration and projection versions; all supported versions here
are 1. This does not change existing public presentation JSON versions.
`decode_evidence` returns `MomentumRun | None`; failed-before-resolution records
may retain no evidence. Unsupported methods/versions fail before decoding.

Strict JSON validation rejects non-finite values, numeric strings/booleans in
numeric fields, unknown fields, invalid enum values, naive timestamps and
inconsistent profile/ticker evidence. Encoding revalidates through JSON so native
dataclass instances cannot bypass nested validation. No arbitrary class loading,
pickle, financial recalculation, provider lookup or presentation derivation occurs.
The codec uses existing Pydantic support; it introduces no generic serializer framework.

## Verification

| Proof | Result |
| :--- | :--- |
| Full native evidence → mapping → envelope JSON → native evidence | Equal typed result; tuple order, nulls, units, enums, timestamps and lineage retained. |
| Missing profile/retrieval context and optional metrics | Explicit absence preserved; retained unavailable metrics retain reason/status. |
| Identity, classification, diagnostics and share-unit documents | Retained exactly, including unavailable capability and resolved document provenance. |
| Unsupported versions | Each of `run_schema_version`, `config_schema_version`, `method_version`, `result_schema_version`, `evidence_codec_version`, and `projection_version` is independently corrupted to 99; each raises `UnsupportedRunVersionError` before the evidence decoder is called. |
| Unsupported method | Mismatched method raises `UnsupportedRunVersionError`. |
| Corrupt metrics, nested evidence and ticker mismatch | Typed `InvalidStoredRunError` with stable safe message. |
| Existing regression baseline | 2,670 tests passed before the new tests were collected. |
| Focused codec suite | 29 passed. |
| Final managed full gate | Ruff check, format check (349 files), strict mypy (258 files), 2,699 tests passed in 93.57 seconds. |
| Coverage | 90% combined repository coverage; 11,391 statements, 862 missed (92.43% line coverage). Codec dispatch 100%; Momentum codec 96% combined. |

Final artifacts:
`.tmp/quality-runs/20260914200745645-28760-3a0c564f134e45c99ffdf5ac869febf0/`.

The initial managed focused command could not access the existing interpreter.
Verification subsequently ran outside the managed sandbox, using the tool's
`require_escalated` option after automatic approval review. This permitted access
to the existing Windows Python interpreter; it was not sudo, a separate runner,
or a dependency installation. Commands used `uv run --no-sync` and repository-local
temporary/cache paths. The baseline wrapper
started before edits; its coverage enumeration also saw the newly created codec
files, so its coverage percentage is not a pristine pre-edit baseline.

Review follow-up expanded the original three-version test to all six decoder
version fields. It deliberately uses `model_copy(update=...)` to bypass envelope
validation and test the decoder guard itself, including fields normally rejected
by literal-version or configuration-consistency validation. A failing decoder
stub proves that unsupported versions are rejected before payload decoding.

## Boundaries and review gate

Execution capture/status mapping, display-derived values, report replay, other
method codecs and SQLite persistence remain assigned to their later slices.
No dependencies, calculators, CLI behavior, migrations or existing interfaces were
changed. The uncommitted Step 3.5 planning work was preserved. No operational data
was migrated and no real provider/LLM calls were part of verification.

No commit, push or PR was made. Stop here for B3 review; B4 remains unauthorized
until acceptance is granted.
