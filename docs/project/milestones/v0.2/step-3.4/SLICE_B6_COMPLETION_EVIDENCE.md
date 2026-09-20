# Slice B6 — Completion evidence

**Review disposition:** B6 reviewed and accepted by the project owner on 2026-09-15 (America/Toronto).
**Date:** 2026-09-15 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

B5 acceptance was recorded and committed at the starting revision. The project
owner directly authorized B6 implementation in the task conversation and required
preservation of the uncommitted Step 3.5 planning work.

## Delivered scope and authorization

- `src/workspace/fcf_growth.py`: strict finite JSON encoding and reconstruction of
  the complete native `FCFEarningsGrowthResult`.
- `src/workspace/codecs.py`: explicit FCF dispatch, expanded return/input unions
  and method-specific native version validation.
- `tests/workspace/test_fcf_growth_codec.py`: 48 deterministic tests.
- This completion record, prepared under the slice's evidence protocol.

The shared dispatch change is expressly included in the B6 contract and authorized
by the direct implementation request. No prior slice evidence or planning status
document was changed as an agent judgment call. No existing implementation/test
file outside that approved dispatch was edited. Step 3.5 planning work was untouched.

## Wire and reconstruction contract

The wire shape is `{"result": <FCFEarningsGrowthResult fields>}`. The canonical
pair is `fcf_earnings_growth` / `reported_fcf_eps_cagr`. Native method version **2**
and result schema **3** are retained; evidence codec, configuration, run and
projection versions remain **1**. FCF is not routed through Graham or Momentum
types. The four dispatched types are independent dataclasses with no mutual
inheritance, so `isinstance` ordering does not overlap their instances.

The decoder checks all four native constructor-excluded identifiers/version
fields before removing them from a copied mapping; the declared native constructor
restores them. Missing or contradictory native metadata is `invalid_stored_run`;
unsupported envelope method/version tuples are `unsupported_run_version` before
payload decoding, including attempts with no evidence. There is no version fallback.

Reconstruction uses strict Pydantic JSON validation of declared native dataclasses,
enums, aware dates, finite numbers, optional values and ordered tuples. Native
constructor invariant validation still runs, including component FCF/share
identities and forward completeness. It does not resolve inputs or recompute
stored growth/yield/classification metrics through analyzers or calculators.
Caller-owned payloads remain unchanged. Encoding revalidates through JSON so
invalid already-constructed native instances cannot bypass validation.

## Focused proof

The pre-edit workspace baseline passed **442 tests**. The final focused workspace
suite passed **490 tests**, including all **48** FCF codec tests.

| Contract proof | Evidence |
| :--- | :--- |
| Native versions and full typed round trip | Native → mapping → envelope JSON → native equality; re-encoding equality and separate diagnostics equality; method/result versions retained as 2/3. |
| Annual observations and provenance | Ordered annual observations, component lineage, units, notes, availability/retrieval timestamps, diluted shares and derived FCF/share retained. Cached input origin/version preserved. |
| Heterogeneous per-share classification | Per-share policy and valid per-share metric retained even when total FCF growth is unavailable; no forced shared financial field bag. |
| Optional/unavailable evidence | Missing shares/per-share evidence, absent profile/market capitalization and disabled yield remain explicit nulls or typed unavailable/not-requested metrics. |
| Forward evidence | Unavailable, partial and complete consensus blocks retain estimates, interval metrics, reasons and confirmation values. |
| Profile and outcomes | Identity, classification, security-unit provenance/document context IDs retained; unavailable, provider-error, invalid-input and ETF not-applicable fixtures preserved. A financial FAIL remains native execution OK. |
| Version rejection | All six envelope fields independently changed to 99; failing decoder stub proves rejection before decoding. Legacy 1/1 FCF native versions and boolean/float version lookalikes rejected. |
| Corrupt storage | Missing/wrong native metadata, extra fields, invalid enums, nonfinite/string/bool metrics, inconsistent annual FCF/share data, empty lineage, mismatched ticker/profile, naive dates and inconsistent forward confirmation rejected. |
| Pure reconstruction | Analyzer and all public metric/classification calculator functions replaced with failing stubs; decoding restores stored metrics and preserves the complete payload. |
| Native revalidation | Explicit low-level corruption of a frozen native timestamp rejected during encoding. |

## Complete managed gate

The required wrapper passed Ruff, formatting (**357 files**), strict mypy
(**264 source/test files**) and **2,828 tests in 93.21 seconds**. Combined coverage
is **90%** (11,586 statements, 863 missed). FCF codec combined coverage is **90%**;
shared dispatch coverage is **100%**.

Artifacts:
`.tmp/quality-runs/20260915193254849-35668-59ef430b74ad4042920c691f6bf351ae/`.

Verification used the existing interpreter through automatically approved
`require_escalated` access because the managed sandbox previously could not query
it. Commands used `uv run --no-sync`; caches and full-gate temporary files remained
repository-local. No dependency installation or synchronization occurred.

## Boundaries and review gate

No execution capture, report projection, schema migration, database access,
provider/LLM call, financial algorithm change or direct CLI behavior change was
introduced. No user-data migration, commit, push or PR was made.

B6 acceptance is recorded under the direct user instruction to record that fact.
C1 schema implementation is the next slice and has not been started in this task.
