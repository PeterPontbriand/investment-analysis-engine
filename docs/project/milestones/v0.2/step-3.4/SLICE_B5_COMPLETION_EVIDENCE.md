# Slice B5 — Completion evidence

**Review disposition:** B5 accepted by the project owner on 2026-09-15 (America/Toronto).
**Date:** 2026-09-15 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

The project owner explicitly accepted B4 and authorized B5 implementation in the
task conversation. B4 acceptance is recorded in its completion evidence and the
active planning status. The uncommitted Step 3.5 planning work was preserved.

## Delivered scope

- `src/workspace/graham_growth.py`: strict version-one finite JSON encoding and
  typed reconstruction of the independent `GrahamGrowthAnalysis`, including
  assembly, result, effective calculation policy, explicit growth/AAA assumptions,
  provenance, trace, quote comparison/freshness, profile and security-unit evidence.
- `src/workspace/codecs.py`: explicit Growth dispatch and expanded typed union;
  existing six-version rejection and safe error classifications remain intact.
- `tests/workspace/test_graham_growth_codec.py`: 48 deterministic tests after review.
- `tests/workspace/test_graham_number_codec.py`: corrected a corruption-case label
  under the project owner's direct review instruction; no test behavior changed.
- B4 acceptance/status updates in the Step 3.4 contract, B4 evidence and active
  implementation plan; this B5 completion record.

The wire shape is `{"analysis": <GrahamGrowthAnalysis fields>}`. Canonical identity
is `graham` / `graham_growth_value`; method, result and evidence codec versions
are 1, independent of public presentation versions. Constructor-excluded native
method fields are verified before reconstruction. Number identifiers and fields
are rejected; Growth is never coerced through Number types.

## Authorization and review clarifications

The B4 completion-record acceptance update followed the direct instruction to
"Record this and proceed with B5 implementation." Updating status in the active
implementation plan and Step 3.4 contract was the agent's judgment about keeping
planning consistent, rather than a direct request naming those documents. The
original record should have stated that distinction explicitly; listing edits in
delivered scope does not itself establish authorization.

The subsequent review directly authorized changes to both codec test files and
these evidence clarifications. Future completion records will explicitly identify
direct instructions versus agent judgment for edits beyond the slice's new files;
the repository's separate file-scope authorization rule still applies.

Both context-corruption cases now use `analysis_ticker` for the top-level analysis
ticker mutation. Genuine instrument-profile ticker corruption is already covered
in each suite's `test_corrupt_nested_evidence_is_classified`.

Growth has no BVPS field or requirement. Its successful assembly requires EPS,
expected growth and current AAA yield. The BVPS corruption fixture adds a foreign
Number field with a null value; strict extra-field rejection is the intended
failure, documented in a one-line test comment. No validator change was needed.

`GrahamGrowthAnalysis`, `GrahamNumberAnalysis` and `MomentumRun` are independent
frozen dataclasses with no declared bases and no mutual inheritance. Their only
common base is `object`, so the current `isinstance` ordering cannot capture an
instance belonging to another supported evidence type.

The new pairing regression uses `momentum` / `graham_growth_value`: each identifier
is supported individually, but the combination is rejected with
`UnsupportedRunVersionError` before a failing decoder stub can run.

## Verification

The original pre-edit workspace baseline passed **394 tests**. Before review fixes,
the Number/Growth baseline passed **80 tests**. The revised focused workspace suite
passed **442 tests**, including all **48** Growth tests.

| Contract proof | Evidence |
| :--- | :--- |
| Independent full round trip | Native → mapping → envelope JSON → native equality and re-encoding equality; trace equality checked separately because native assembly equality excludes it. |
| Policy and assumptions | Nondefault policy, explicit percentage-point growth and AAA yield, units, notes and ordered EPS lineage retained. |
| Signed semantics | Zero/negative growth and negative EPS/results retained without clipping; successful input assembly may retain an invalid calculation with its reason. |
| Non-success and partial evidence | Unavailable, not-applicable, invalid-input and provider-error outcomes; ETF/missing profile and optional quote unavailability retained. |
| Version and corruption rejection | All six version fields rejected before decoder invocation; foreign/missing methods, Number fields, absent required inputs, invalid policy, extra fields, nonfinite/string/bool numeric values and contradictory comparisons rejected. |
| Identity and time | Envelope/profile ticker mismatches and naive analysis, quote freshness and security-unit document timestamps rejected. |
| Pure reconstruction | Calculator, service, comparison and profile-completion functions replaced with failing stubs; stored values restored without calls or caller payload mutation. |

The original complete managed wrapper passed Ruff, formatting (**354 files**), strict mypy
(**262 source/test files**) and **2,779 tests in 94.87 seconds**. Combined coverage
is **90%** (11,535 statements, 864 missed); Growth codec coverage is **96%** and
shared dispatch coverage is **100%**.

Artifacts:
`.tmp/quality-runs/20260915184912073-37828-eb2afbac4e8b4c15a6e7d5d82d0d3b14/`.

After review fixes, the complete managed wrapper passed Ruff, formatting
(**355 files**), strict mypy (**262 source/test files**) and **2,780 tests in
90.08 seconds**. Combined coverage remains **90%** (11,535 statements, 864 missed);
Growth codec coverage remains **96%** and shared dispatch **100%**. The initial
review gate stopped on mixed line endings in the edited Growth test file; scoped
Ruff formatting corrected them before the successful rerun.

Review artifacts:
`.tmp/quality-runs/20260915191158486-34224-8d95de322b544a74bffb6e04df05a184/`.

The sandbox could not query the existing Python interpreter. Focused verification
and the full wrapper subsequently used `require_escalated`, approved by automatic
review, with `uv run --no-sync` and repository-local cache/temporary paths. No
dependencies were installed or synchronized.

## Boundaries and review gate

The prior Number test file was changed under direct review instruction, in addition
to the approved shared dispatch and new Growth files. Financial math, direct CLI
behavior, execution capture, report replay,
database schemas and later codecs remain unchanged. No provider/LLM calls or
user-data migration occurred. No commit, push or PR was made.

B5 acceptance is recorded under the direct user instruction to record that fact. Updating the active implementation plan and Step 3.4 planning status is the agent's judgment about keeping those records consistent. B6 is the next slice; its implementation has not been started in this task.
