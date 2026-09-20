# Slice B4 — Completion evidence

**Review disposition:** B4 accepted by the project owner on 2026-09-15 (America/Toronto); B5 implementation authorized.
**Date:** 2026-09-14 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

B3 was explicitly accepted in the task conversation before its checkpoint commit.
The user corrected the subsequent slice request to B4. The
[slice contract](STEP_3_4_CONTRACT_AND_SLICE_PLAN.md#9-fine-grained-implementation-slices)
requires B4 acceptance before B5.

## Delivered scope

- `src/workspace/graham_number.py`: finite, strict JSON serialization and typed
  reconstruction of `GrahamNumberAnalysis`, including its complete assembly,
  result, comparison, quote freshness, provenance, trace, profile and unit evidence.
- `src/workspace/codecs.py`: explicit Graham Number dispatch alongside Momentum;
  shared six-version guard and classified invalid/unsupported errors.
- `tests/workspace/test_graham_number_codec.py`: 33 deterministic tests.
- `tests/workspace/test_momentum_codec.py`: one assertion now explicitly narrows
  the decoded union to `MomentumRun`; existing preservation assertions remain.
- This planning evidence record.

The Number wire shape is `{"analysis": <GrahamNumberAnalysis fields>}` inside
the existing envelope. Method/result/codec versions are 1, independent of public
presenter JSON. The method pair is explicitly `graham` / `graham_number`.

Native assembly/result `method` fields use `init=False`. The decoder verifies both
persisted identifiers before omitting them from constructor input; native
constructors restore the fixed Number enum. Missing or Growth identifiers fail.
Copied mappings protect caller-owned evidence. Reconstruction remains strict
JSON-mode validation, preserving enums, datetimes and ordered tuples without
coercing numeric strings/booleans. No universal serializer or method registry was added.

## Focused verification

The pre-edit workspace baseline passed **361 tests**. After implementation,
the workspace suite passed **394 tests**, including all **33** Number codec tests.

| Contract proof | Evidence |
| :--- | :--- |
| Complete typed round trip | Native → mapping → envelope JSON → native equality; re-encoded mapping equality; trace checked separately because native assembly equality excludes it. |
| Provenance and unit fidelity | Derived EPS with ordered components/notes, BVPS override, cached quote, quote freshness, identity/kind, share ratio and document context IDs retained. |
| Non-success outcomes | Input unavailable, not applicable, invalid input and provider error preserve reasons and partial inputs; ETF and absent-profile fixtures retained. |
| Optional comparison | Valid valuation survives missing quote with its reason/status and null comparison percentage. |
| All version fields | Each of the six fields independently changed to 99; typed unsupported error occurs before a failing decoder stub can run. |
| Corrupt evidence | Wrong/missing method, mismatched ticker, foreign fields, invalid status, missing required input, nonfinite/string/bool result values and inconsistent comparison rejected. |
| Time validation | Naive analysis boundary, quote freshness and share-unit document timestamps rejected. |
| Pure decoding | Calculator, service, comparison and profile-completion functions replaced with failing stubs; stored result and percentage restored without calls or payload mutation. |
| Native validation | Invalid native nonfinite result rejected at encoding. |

## Complete quality gate

The managed wrapper passed Ruff, formatting (351 files), strict mypy (260 files),
and **2,732 tests** in **90.94 seconds**. Combined repository coverage is **90%**
(11,464 statements, 864 missed). Codec dispatch has 100% combined coverage;
the Number codec has 96%.

Artifacts: `.tmp/quality-runs/20260914202009623-40100-468925ccbdff4bbdbcb2d4f2972575b1/`.

Implementation is complete. Stop for B4 review before starting B5.

## Boundaries

No execution integration, financial recalculation, status mapping adapter, report
projection, database migration, provider call or Growth codec was added. Dependency
files and existing financial implementations remain unchanged. Unrelated Step 3.5
planning edits were preserved. No commit, push or PR was made.

Verification commands used the existing Windows interpreter outside the managed
sandbox through `require_escalated`, subject to automatic approval review, because
the sandbox previously could not access that interpreter. Commands used
`uv run --no-sync`; the full wrapper isolates caches and temporary artifacts below
the repository. No dependency installation or user-data migration was performed.
