# Step 3.3A — Slice C Composition and Maintenance Review

**Status:** Acceptance evidence complete on 2026-09-12 (Toronto); Slice C approval is pending. Stop for explicit C review before Slice D. Authorization to add/revise acceptance tests and related changes was granted in the current review task. Authorization is granted for C acceptance, permission to push, and permission to begin D.

## Reviewed state and scope

- Production implementation: `868f2f6a710027631328e52db3affb6f03e6023f` on local branch `feat/step-3.3a-data-readiness`, one commit ahead of its tracking branch at review time.
- Final verification covers that commit plus the uncommitted acceptance-test changes listed below and the owner's `.gitignore` addition, `*.readiness.lock`. It is not a claim that the added tests belong to the existing commit.
- No production source, schema revision, dependency, financial semantics, provider behavior or configuration default changed during acceptance completion. No staging, commit, push, PR, or operational-database migration was performed.
- Tests use disposable temporary databases, fixture providers and mocked transports. No operational database contents were inspected or imported as fixtures. Process coordination uses spawned Windows processes and pipe handshakes, without timing sleeps in the test orchestration.

Authority: [approved concrete contract](SLICE_A_CONTRACT_AND_VERIFICATION.md), [maintenance amendment](SLICE_C_MAINTENANCE_AMENDMENT.md), and [contract/slice plan](STEP_3_3A_CONTRACT_AND_SLICE_PLAN.md).

## Acceptance evidence

| Requirement | Evidence |
| :--- | :--- |
| First use and durable reuse across all four commands | `tests/test_cli_financial_cache.py` and `tests/test_cli_historical_cache.py` now run against both pre-migrated and missing targets. Real cache, repository, readiness and analyzer paths initialize fresh storage, close/reopen it, reuse persisted facts/history without refetch, and reject any attempted second initialization. Successful JSON remains parseable with empty stderr. |
| Safe analysis failures and closure | New `tests/test_cli_database_readiness.py` exercises every stable readiness reason for Momentum, Graham Number, Graham Growth and FCF Growth in concise/details/diagnostics/JSON modes. Exit 1, exact authored errors, version 4/5 envelopes, `status=error`, `result=null`, empty inappropriate streams, cause sanitization, and closed storage are asserted. |
| Real rejection before provider calls | The same file exercises corrupt, incompatible and recognized-older temporary files through real CLI readiness. Files remain byte-identical, provider methods are not called, and only older-schema failures suggest an upgrade with the selected target identified. |
| Storage independence | Help for all analysis and maintenance commands rejects any database construction. Fresh-process CLI import blocks SQLite connection attempts and leaves the target parent absent. Financial `--no-cache` succeeds without DB or sidecar creation. `tests/evaluation/test_cli.py` explicitly blocks readiness/storage while the 19-case deterministic evaluation succeeds. |
| Optional telemetry | An unmigrated disposable telemetry sink fails open without readiness or a sidecar. Analysis storage still initializes successfully or retains its own invalid-file error independently. Existing recorder, sink, and quality-observer fail-open tests remain in the complete gate. |
| Maintenance visibility, targets, status and streams | `tests/test_cli_database.py` covers hidden top-level help, explicit maintenance help, missing/fresh/current/incompatible status, fresh initialization and ready no-op, configured/overridden targets, relative paths after cwd change, JSON/text streams, sanitized invalid URLs, private-memory usage errors and unavailable resources before target creation. |
| Coherent status and real SQLite busy failures | New `tests/data/repositories/test_maintenance_acceptance.py` commits an unknown revision from a second connection after the reader establishes its snapshot: the first inspection stays ready and the next reports incompatible with no untrusted revision. A real exclusive SQLite lock produces `database_busy` without creating a readiness sidecar. |
| Structural older-schema validation | A disposable synthetic migration graph extends the frozen base schema with a legacy table, then removes it at the synthetic head. Status recognizes the valid ancestor and explicit upgrade reaches the verified current structure. Additional structural drift is rejected unchanged. Production migration files remain untouched. |
| Existing-storage protection | Maintenance rejects empty/multiple/unknown version rows, missing required tables and inconsistent metadata without data mutation. Existing Slice B signature, malformed-file, permission and I/O tests remain green. |
| Atomic upgrade and recovery | Existing synthetic migration-failure tests verify DDL rollback and unchanged revision/file bytes. New post-head-verification failure evidence verifies rollback of both DDL and revision, followed by a successful ready no-op proving ownership release. Existing fresh migration interruption/recovery tests remain green. |
| Process ownership | `tests/data/repositories/test_readiness_concurrency.py` covers all nine automatic/manual/explicit owner-and-waiter combinations. The owner commits initialization, peers observe ready, and automatic/explicit peers must not initialize again. Existing real timeout and interrupted-process tests remain included. |
| Regression | Complete repository, manual migrations, four-analysis, reporting, financial semantics, evaluation, orchestration, cache and telemetry suites pass. |

The synthetic successful no-op upgrade tests are retained alongside the stronger structural-upgrade evidence; they are not the sole proof of older-schema support. The current production bundle still contains only `0001_persistence`, so no real older production revision is advertised as supported.

## Full managed gates

Both gates used the repository PowerShell wrapper, with `uv run --no-sync`, unique ignored temporary/cache/coverage directories, and the already synchronized environment. Platform: Windows, Python 3.14.7, pytest 9.1.1.

| Gate | Ruff / format / strict mypy | Pytest | Coverage | Isolated artifact directory |
| :--- | :--- | :--- | :--- | :--- |
| Fresh baseline, implementation commit plus owner's ignore rule | Passed; 324 formatted files; 246 typed source/test files | 2,131 passed; 1 warning | 90% combined line/branch report | `.tmp/quality-runs/20260912150451382-21580-6e5d965fdd5d4c4ca07d1722850a5e57` |
| Final acceptance tree | Passed; 326 formatted files; 248 typed source/test files | 2,338 passed; no warnings; 86.92s | 90% combined line/branch; 92.16% line coverage | `.tmp/quality-runs/20260912151753436-40532-5a6de1970784449b874f1b8eef6007db` |

Coverage exceeds the required 85% threshold. HTML reports and coverage data are local ignored artifacts, not material to commit. The gate record binds the final evidence to the reviewed production commit plus the named uncommitted changes; no successor commit exists yet.

During test development, lint/format/strict-typing checks caught test-only issues, which were corrected before the final gate. The first expanded suite passed 2,337 tests and exposed the same unclosed SQLite connection warning seen in the baseline. The incompatible-storage maintenance test used `with sqlite3.connect(...)`, which commits/rolls back but does not close the connection. It now uses `closing(...)` with explicit autocommit. The final gate reports no warnings.

## Local data hygiene and remaining gate

The owner added `*.readiness.lock`; `git check-ignore -v` confirms the readiness sidecar matches it. Existing `*.sqlite3`, `*-wal` and `*-shm` rules already protect the other observed artifacts. No `data/` files are tracked. The persistent lock must not be deleted as stale, because its stable pathname is part of process coordination. This was an immediate Git-hygiene follow-up, now resolved in the uncommitted working tree, rather than evidence of a Slice C database leak. Moving the configured database is not required to fix that issue.

**Recommendation:** Slice D must deliver durable user-facing maintenance/initialization documentation and reconcile final readiness acceptance before Step 3.4 resumes.

Retained boundaries: this evidence is for Windows/source-checkout installation. It does not newly verify POSIX locking, relocated wheels, network filesystems, hard-link aliases or external file replacement. No operational migration or live provider/LLM run was performed.
