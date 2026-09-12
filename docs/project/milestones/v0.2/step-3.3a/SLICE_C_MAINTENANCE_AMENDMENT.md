# Step 3.3A — Slice C Hidden Database Maintenance Amendment

**Status:** Authorized on 2026-09-12 (Toronto). The project owner requested this amendment, approved Slice B and authorized Slice C: “Proceed with recording your recommended small contract amendment. As well, record my approval of Slice B and my authorization to proceed with Slice C.” The [Slice C review record](SLICE_C_COMPOSITION_REVIEW.md) now records implementation and completed verification. Slice C approval remains pending; do not begin D yet.

**Authority:** This amendment extends the [concrete contract](SLICE_A_CONTRACT_AND_VERIFICATION.md) for Slice C only. It supplements the existing composition/error work and preserves the [remaining C/D review gates](STEP_3_3A_CONTRACT_AND_SLICE_PLAN.md#6-slices-and-review-gates). The [Slice B review record](SLICE_B_READINESS_REVIEW.md) remains the accepted implementation evidence.

## Commands and visibility

Register a hidden Typer `db` group, omitted from ordinary top-level help. Explicit `financial-agents db --help` exposes its maintenance commands. Hiding is a discoverability choice, not access control. Keep normal analysis help and presentation unchanged; document these commands in the database operations guide during Slice D.

| Command | Contract |
| :--- | :--- |
| `financial-agents db status` | Inspect the selected file without initialization or upgrades. Report the resolved target, observed revision when safely readable, expected bundled revision and readiness state. |
| `financial-agents db upgrade` | Explicitly initialize verified fresh storage or migrate a recognized, supported older schema to the bundled head. Already-ready storage is a successful no-op. |
| `--json` | Available on both commands; emit exactly one versioned maintenance document without migration chatter. |
| `--database-url` | Optional command-level target override on both commands, validated through existing settings/SQLite rules. Otherwise use configured settings. |

Resolve settings and the database target once per invocation. Relative paths retain `base_dir` semantics. Reuse the same target for inspection, migration and post-verification; never fall back to a default path. Display the normalized local path rather than the supplied URL or other configuration. Reject private in-memory targets as a usage error for these standalone maintenance commands: a newly created per-process database cannot inspect or maintain another invocation's memory. Existing same-instance library support is unchanged.

## Inspection and migration semantics

Add a typed inspection boundary separate from `ensure_database_ready()`. Status must not call an initializer, enable WAL, create a database, parent directory or ownership sidecar, or write application/schema data. Inspect an existing file through a read-only connection and one consistent read transaction; an absent path yields `missing`. SQLite may require its normal journal/shared-memory access; inability to obtain a safe read is a classified storage failure, never a repair attempt. Do not use SQLite `immutable` to bypass live locking. Status is a snapshot, not a reservation or guarantee that a subsequent operation will succeed.

Report `ready`, `missing`, `fresh`, `upgrade_required` or `incompatible` distinctly. Empty or multiple version rows, unknown revisions and schema drift are incompatible. Malformed files, lock contention, permission/I/O failures and unavailable migration resources retain the existing stable reason categories. Do not expose untrusted revision text, SQL, driver messages or row contents; report only recognized revision identifiers, otherwise null with the incompatible reason.

Upgrade uses the existing bounded ownership sidecar before checking the target and before normal connection setup, then rechecks authoritatively. Fresh initialization uses Alembic and the accepted atomic verification lifecycle. Existing upgrades require both recognized ancestor history and structural compatibility with that supported revision; a known revision stamp alone is insufficient. Validate against the frozen migration-derived schema for that revision using disposable memory, or an explicitly maintained revision-specific signature, without adding production fixture/cache data. The current bundle has only `0001_persistence`, so no production older-schema upgrade is presently available; exercise that path using a synthetic migration graph. Do not relax head-schema checks to pretend an older schema matches current metadata.

Run a supported upgrade through the shared borrowed-connection Alembic seam in one transaction, verify head revision/schema before commit, and roll back on failure. Distinguish migration failure from fresh-initialization failure with a stable `database_migration_failed` reason and authored text. Reuse existing storage error categories where applicable. Unknown/newer, unversioned nonempty, corrupt and inconsistent storage must be refused without automatic repair, stamping, deletion or downgrade. Existing direct Alembic commands remain available with their established behavior and override precedence.

The explicit `db upgrade` invocation requests the migration; do not add an interactive confirmation that blocks automation. Help and the operator guide instruct users to stop other application processes and back up existing data first. Implementing/tests exercising this command does not authorize the agent to migrate an operational database.

## Output and verification

Use a dedicated typed maintenance report, independent of analysis-result models: `schema_version=1`, `command` (`db status` or `db upgrade`), `status` (`success` or `error`), `database_path`, `state`, `current_revision`, `expected_revision`, `reason` and a sanitized `message`. Use null for unavailable fields. Upgrade success states are `initialized`, `upgraded` or `ready`; status states are as defined above. A successful inspection of a non-ready state remains a successful report, with a nonzero readiness exit code.

Exit 0 means ready or successfully initialized/upgraded. Exit 1 means a completed inspection found storage not ready, or a classified operational failure occurred. Exit 2 means invalid usage/configuration. Text reports go to stdout; operational failures go to stderr. JSON operational reports use stdout only, with no Alembic chatter or duplicate text error; parser-level usage errors retain normal CLI behavior. Analysis commands retain their already approved error envelope and exit contract. Any upgrade remediation text must target the inspected database and must not suggest upgrading incompatible storage.

Extend Slice C's file scope to `src/cli.py` (hidden group registration), new `src/cli_database.py` (maintenance routing/reporting), `src/data/repositories/readiness.py`, `migrations.py` and repository exports (shared inspection/explicit-upgrade seams), plus new `tests/test_cli_database.py` and focused repository tests. Reuse existing settings and lock ownership. No schema revision, dependency, configuration-default, financial-model or provider changes are authorized.

Verification adds hidden top-level help and explicit maintenance help; status without target/parent/sidecar creation or migration; coherent inspection and busy failures; configured/overridden targets; text/JSON schemas and exit codes; fresh/current/synthetic-older upgrades; rejection and preservation of incompatible storage; failed-upgrade rollback; and coordination with manual/automatic owners. Test same-target remediation and absence of provider/LLM calls. Keep the original Slice C composition, bypass, telemetry and four-analysis regressions. Run the full managed gate, record evidence and stop for Slice C review before D.
