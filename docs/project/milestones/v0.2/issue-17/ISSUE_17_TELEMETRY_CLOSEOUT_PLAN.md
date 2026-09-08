# Issue #17 — Telemetry Closeout Plan

**Status:** Complete and approved on 2026-09-07. Contract and final acceptance reviews are closed; publication and GitHub issue closure remain outstanding.

**Authority:** The [milestone implementation plan](../IMPLEMENTATION_PLAN.md) owns sequencing and scope. This companion defines the bounded implementation and acceptance contract for [Issue #17](https://github.com/PeterPontbriand/financial-data-agents/issues/17).

**Sequencing:** The project owner requested that Issue #17 be addressed next, after completed Step 3.2 and before Step 3.3. This is a prioritization decision, not a new technical prerequisite for data quality. Step 3.3, P2-Profiles, Step 3.4, and Step 3.5 retain their existing review gates. This document does not reopen completed Steps 2.1, 2.6, or 3.2.

**Authorization:** On 2026-09-07 the project owner stated, “Reviewed and accepted. Record and proceed.” This accepted the bounded contract, linked-error-context interpretation, file scope, and verification matrix and authorized implementation and verification without intermediate slice approvals. The subsequent instruction, “Final review complete and approved,” closes final acceptance. The project owner clarified the next-step authorization as “Authorize Step 3.3 next”; Step 3.3 is authorized to begin within its existing scope and gates. Step 2.4 remains complete and is not reopened. Commit, push, PR creation, issue comments, and issue closure require explicit authorization and are not implied by these approvals.

## 1. Source reconciliation and baseline

The review examined local commit `d07a709` and the open issue, which has no comments and was last updated on 2026-08-25. Paths below are repository-relative.

| Requirement | Current evidence | Remaining work |
| :--- | :--- | :--- |
| Recovery emission | `src/orchestrator/loop.py` emits `RECOVERY_ATTEMPTED` before transport retries and schema repairs. Step 2.6 implemented this after the issue was written. | Preserve hooks; prove ordering and metadata rather than implement duplicate events. |
| Recovery context | Events contain component, step index, span/parent linkage, failure category, retry number, and maximum retries. Detailed sanitized context is in preceding span-linked `ERROR` events. | Verify this linked-event contract explicitly. |
| Retry coverage | `tests/orchestrator/test_reliability_enforcement.py` covers transport recovery, exhaustion, and schema repair. | Add causal-order, linkage, sanitization, and recovery-specific sink-failure assertions. |
| Payload hash | `src/core/telemetry/recorder.py` redacts payloads before canonical JSON/SHA-256 hashing; null produces null. | Add direct regression coverage of retained, omitted, null, stable, and sanitized payload semantics. |
| Tracking | Issue #17 and the milestone's Step 2.1 follow-ups still describe recovery emission as outstanding. | Reconcile records with implementation and acceptance evidence. |

The review ran the existing telemetry primitive, orchestrator telemetry, and reliability-enforcement test files: **18 passed in 1.28 seconds**. This is a focused baseline, not a new complete quality gate. Step 3.2's accepted full gate recorded 1,853 tests and 89% reported coverage. Obtain a fresh baseline before implementation; do not present historical results as fresh verification.

## 2. Bounded contract

- Retain one recovery event for each actual retry in the existing transport and schema-repair paths. Do not emit recovery events for initial attempts, nonrecoverable failures, or retries rejected by the existing reliability limits.
- Preserve existing retry budgets, timeout behavior, counters, parser fallback, result semantics, and event vocabulary.
- A recovery event identifies the failure category and attempt metadata. Its preceding sanitized `ERROR` event supplies detailed error context through the same run, step, span, and parent span. This explicitly interprets the issue's error-context requirement as a linked trajectory contract; it does not require duplicating exception text on the recovery event. Contract approval accepts this interpretation.
- Hash the exact retained sanitized payload using the existing canonical serialization and SHA-256 behavior. Omitted or explicit null payloads yield null hashes; empty objects, empty lists, false, zero, and empty strings are retained non-null values and must hash.
- Preserve fail-open sink behavior: a sink recording failure during recovery must not change the retry count, dispatch result, or terminal business outcome.
- No new dependencies, schema migrations, database changes, sink redesign, logging migration, financial calculations, real provider/LLM calls, public-interface removal, or generic retry framework.
- Production edits are conditional on a regression test exposing a defect in this bounded contract. Wider serialization/redaction redesign or reliability-policy changes return to scope review.

## 3. Implementation and verification matrix

| ID | Required deterministic evidence |
| :--- | :--- |
| H1 | Retained non-null payloads have hashes, including falsy/empty values; omitted and explicit null payloads have null hashes. |
| H2 | Repeated equivalent retained payloads hash identically, including reordered nested mapping keys. A changed safe value changes the hash. Verify canonical bytes against an independently stated expected digest/serialization. |
| H3 | Secret-bearing inputs are redacted before retention and hashing. Inputs differing only in redacted secret values produce the same retained payload/hash; the expected digest corresponds to sanitized material. No raw secret survives persisted JSONL evidence. Use synthetic credentials only. |
| R1 | For transport retries, assert the failed request/error → recovery → next request ordering, consecutive sequence numbers, shared run/step/span/parent metadata, and retry category/count/budget. Cover multiple retries and exhaustion without a phantom extra recovery. |
| R2 | For schema repair, assert invalid response/error → recovery → next request/response ordering and metadata. Exercise native and prompt enforcement modes using configured capability or mocked responses; verify successful repair preserves counters and tool result behavior. |
| R3 | Initial success, nonrecoverable errors, and exhausted/disabled repair budgets do not emit recovery without a retry. Reuse existing test fixtures and extend relevant assertions. |
| R4 | Synthetic error secrets are absent from linked retained error/recovery events and persisted trajectory output. Detailed sanitized error context remains linked to the recovery. |
| R5 | A sink that raises on recovery recording leaves execution equivalent to a working-sink run: same LLM attempt count, tool outcome, and terminal result. Exercise transport and schema repair paths. |

Prefer assertions at the recorder/orchestrator public behavior boundary. Reuse existing in-memory sinks, mock LLMs, and JSONL integration fixtures; do not introduce a parallel test framework. Existing SQLite tests already cover persistence hash preservation; no duplicate SQLite implementation work is required.

### Expected file scope

- `tests/core/telemetry/test_telemetry.py`: payload/hash coverage.
- `tests/orchestrator/test_reliability_enforcement.py`: recovery behavior and failure isolation.
- `tests/core/telemetry/test_orchestrator_telemetry.py`: ordered persisted trajectory evidence where existing fixtures are suitable.
- `src/orchestrator/loop.py` and `src/core/telemetry/recorder.py`: only if bounded defects are demonstrated by tests.
- This companion and `docs/project/milestones/v0.2/IMPLEMENTATION_PLAN.md`: acceptance evidence and tracking. `docs/project/MASTER_PLAN.md`: sequencing/status synchronization only.

## 4. Execution and review gates

1. **Contract review:** Approved on 2026-09-07, including the linked-error-context interpretation and file scope; implementation was then authorized.
2. **Baseline and implementation:** Recheck the worktree and current commit; run the complete managed gate. Add focused regressions, observe meaningful failures where coverage exposes a defect, and make only required bounded corrections. Coverage-only tests may pass against already-correct behavior.
3. **Acceptance verification:** Run the relevant focused suites and the complete non-mutating repository gate from the repository root:

   ```powershell
   & (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
   ```

   Use the existing synchronized environment and unique ignored run directory supplied by the wrapper. Record Ruff, format, strict mypy, test counts, coverage, and any bounded corrections. Do not install dependencies or use real model/provider endpoints.
4. **Documentation and final review:** Map H1–H3 and R1–R5 to concrete tests and results. Update the milestone follow-ups and draft the issue-resolution text locally. Present the diff and evidence for final acceptance; passing tests alone does not mark the closeout approved.
5. **Publication:** Following explicit authorization, perform the agreed commit/PR and issue-update workflow. Do not close Issue #17 before the accepted changes are merged and its acceptance criteria are reconciled. Resume later milestone work only under its own gates.

## 5. Completion record

- Contract review: approved on 2026-09-07.
- Implementation: completed on 2026-09-07; test changes only, with no demonstrated production defect.
- Fresh complete baseline: passed on 2026-09-07, 1,853 tests in 34.97 seconds, 89% reported coverage, clean Ruff/format (286 files) and strict mypy (224 source files).
- Final quality gate: passed on 2026-09-07, **1,870 tests in 37.72 seconds**, **89% reported coverage**, clean Ruff/format (286 files), and strict mypy (224 source files).
- Acceptance matrix and final review: approved on 2026-09-07; Issue #17 implementation closeout is complete.
- Next-step authorization: Step 3.3 authorized to begin on 2026-09-07; implementation has not begun in this closeout task. Later work retains its own scope and gates.
- Commit/PR/merge and issue closure: not performed for this work item.

Baseline artifacts: `.tmp/quality-runs/20260907203145990-32920-84f74dcec2974471ba135488ed779fdf/` (ignored). The managed wrapper used the existing Python interpreter without dependency synchronization.

Final artifacts: `.tmp/quality-runs/20260907203619693-31712-80c3cec0daea4a4ca27c6413b78aaaac/` (ignored). Both complete runs used the section 4 wrapper. The source coverage denominator is unchanged at 9,422 statements and 2,980 branches; missing statements decreased from 776 to 775 and partial branches from 497 to 496. Reported combined coverage remains 89%. The 17 added cases account for the entire test-count increase. No raw trajectory or quality-run artifacts are included in the change.

## 6. Acceptance evidence

The implementation extends two existing test modules. It reuses the existing JSONL sink in the reliability tests for persisted causal-order and redaction evidence; `test_orchestrator_telemetry.py` remains unchanged and is included in the focused suite. No source, dependencies, migrations, public interfaces, or financial behavior changed.

| ID | Concrete regression evidence |
| :--- | :--- |
| H1 | `test_retained_payload_hash_includes_empty_values` (six cases) and `test_omitted_and_null_payloads_have_no_hash` in `tests/core/telemetry/test_telemetry.py`. |
| H2 | `test_payload_hash_is_stable_across_nested_mapping_order`: repeated payloads, nested key reordering, changed safe value, and independently specified canonical bytes including Unicode escaping. |
| H3 | `test_persisted_payload_hash_uses_only_redacted_material`: differing synthetic secrets, nested redaction, sanitized canonical digest, and JSONL readback with no raw secrets. |
| R1 | `test_transient_llm_failures_retry_with_recovery_telemetry` and `test_transient_llm_retry_exhaustion_trips_after_exact_budget` in `tests/orchestrator/test_reliability_enforcement.py`: causal event ordering, contiguous sequences, run/session/step/span/parent linkage, categories, budgets, and exact attempt counts. |
| R2 | `test_schema_repair_emits_recovery_and_valid_response_resets_counter` (native/prompt cases): linked persisted trajectory, correct request formatting, successful tool result, and reset schema counter. |
| R3 | `test_schema_recovery_events_match_actual_attempts` (initial success, disabled enforcement/repair, exhaustion, and circuit rejection), existing transport exhaustion, and extended `test_nonrecoverable_http_error_is_not_retried`. |
| R4 | Transport and schema-repair tests persist synthetic secret-bearing error paths through JSONL, assert absence of raw secrets, and verify sanitized linked error type/message context. |
| R5 | `test_recovery_sink_failure_preserves_execution` (transport, native schema, prompt schema): paired working/failing sinks preserve two LLM calls, one successful tool result, and the same configured terminal step-limit outcome; exactly one recovery write fails. |

Focused verification: **35 passed in 1.19 seconds**, comprising the two modified modules and unchanged orchestrator telemetry integration module. This adds 17 collected cases over the 18-test review baseline; no tests were removed. Initial new-fixture failures were configuration conflicts, corrected to honor the existing `max_validation_retries = max_consecutive_schema_violations - 1` contract. These were not production defects. Formatting corrections were confined to the two modified test files.

## 7. Draft issue-resolution text

Local draft only; not posted. Use after final acceptance and merge, with the actual PR/merge reference supplied during the authorized publication workflow:

> Recovery emission was implemented in Step 2.6 for transport retries and schema repairs. The follow-up regression coverage now verifies ordered recovery trajectories, step/span linkage, sanitized linked error context, retry boundaries, and fail-open recovery recording in transport and native/prompt schema paths. Recovery events retain category/attempt metadata; preceding span-linked ERROR events supply detailed sanitized context, as accepted in the closeout contract.
>
> Payload-hash tests cover retained values including empty/falsy payloads, omitted/null payloads, stable canonical hashing across nested key order, changed safe values, and hashing only redacted retained material. JSONL readback confirms synthetic secrets are absent. Production behavior remains unchanged.
>
> Verification: 35 focused tests and the complete managed gate passed, including 1,870 tests, 89% reported coverage, Ruff, formatting, and strict mypy.

Final stakeholder review approved this closeout on 2026-09-07, including the linked-error-context interpretation and the full verification evidence. Step 3.3 is authorized to begin. Issue #17 should close when this accepted change merges; approval here does not assert that the PR is already merged.
