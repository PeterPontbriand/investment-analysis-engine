# Deferred — Structured Error Reporting for Programmatic/Agentic CLI Consumers

**Status:** deferred; not started; scope/contract review required before implementation.
**Discovered:** 2026-09-20 (America/Toronto), during Step 3.4 review of the
`DatabaseReadinessError` message a human sees from
`financial-agents graham-number ... --save-run` when the local database needs
a schema upgrade.
**Not a blocker:** this does not block Step 3.4 acceptance or any other
active v0.2 work package. It is recorded here so it is not lost, not to
claim priority over anything already sequenced.

## Trigger

The 2026-09-20 rewrite of `ReadinessReason.UPGRADE_REQUIRED`'s message fixed
what a human reads. Checking whether that fix also serves a programmatic or
agentic caller (an MCP tool wrapper, a coding agent, or any future
orchestrator-exposed persistence tool shelling out to this CLI) surfaced
that it only partly does, and that the underlying gap is older and broader
than that one message.

## Problem

The CLI's JSON error shapes are inconsistent depending on which command
family raises the failure, and none of them expose everything a caller
already has typed access to internally:

- **Direct commands** (`graham-number`, `graham-growth`, `fcf-growth`,
  `momentum`) with `--json`: `execution_errors()`
  (`src/cli_support.py`) catches `DatabaseReadinessError` and emits
  `analysis_failure_document()` (`src/reporting/presentation.py`), which
  carries a stable `reason_code` (e.g. `"database_upgrade_required"`, from
  `ReadinessReason`) and a free-text `reason` string. That `reason_code` is
  already safe for a caller to branch on. But `DatabaseReadinessError` also
  carries `expected_revision` and `database_path` as typed properties, and
  neither is a field in this envelope — only the free-text `reason` sentence
  (a sentence written for a person to read) carries the revision now, after
  2026-09-20's wording fix. A caller wanting the revision programmatically
  would have to parse it out of prose written for a human, which is exactly
  the kind of brittle coupling this project avoids everywhere else with
  typed evidence and discriminated unions.
- **Workspace commands** (`watchlist`, `refresh`, `runs`, all in
  `src/cli_workspace.py`): `_fail()` always writes a plain-text line to
  stderr and exits 1, regardless of whether `--json` was requested. There is
  no structured error envelope here at all — strictly less than the direct
  commands provide.
- **The existing good precedent**: `financial-agents db status --json`
  (`src/cli_database.py`, `DatabaseMaintenanceReport`) already does this
  correctly — `state`, `current_revision`, `expected_revision`, and `reason`
  (a stable code) are separate typed fields from `message` (the free-text
  sentence). That shape is what the other two paths should grow toward, not
  a new design.

This is not specific to `UPGRADE_REQUIRED`; it applies to any
`ReadinessReason` surfaced through either command family, and to any other
sanitized exception `execution_errors()`/`_fail()` translate today.

## Explicit non-goal

The fix here is a caller being able to *recognize and cleanly report* a
condition like "database schema upgrade required" — not to let an agent
*silently self-remediate* it by running `db upgrade` on its own. Separately
from this note, `AGENTS.md` already requires explicit user confirmation
before a database migration for agents working on this repo; the same
reasoning should extend to any agent *operating* this CLI as a tool against
a user's real data. Whatever comes out of this work should make "stop and
tell the user" easy, not make "upgrade and continue" easy.

## Likely scope, once picked up

- `src/reporting/presentation.py`: extend `analysis_failure_document()` (or
  add a sibling) to carry typed fields for a `DatabaseReadinessError`
  specifically — at minimum `expected_revision`/`database_path` — rather
  than only `reason_code`/`reason`/`diagnostics`.
- `src/cli_support.py`: `execution_errors()`'s `DatabaseReadinessError`
  branch would need to pass those fields through.
- `src/cli_workspace.py`: `_fail()` (and its callers) would need a `--json`-
  aware structured error path for `watchlist`/`refresh`/`runs`, mirroring
  whatever shape is settled on for the direct commands rather than
  inventing a second one.
- Decide whether `DatabaseMaintenanceReport` (`src/cli_database.py`)
  should become the one shared error-envelope shape across all three
  command families, or whether direct/workspace commands need their own
  shape for other reasons already present in `analysis_failure_document`
  (`analysis`, `method`, `ticker`, `diagnostics`) that `db status` has no
  equivalent for.
- Whatever ships needs its own contract note (request/response shape,
  stability guarantees on `reason_code` values) before implementation,
  following this project's existing contract-then-slices practice rather
  than growing the shape ad hoc.

## Out of scope for this note

Adding an MCP server, exposing `watchlist`/`refresh`/persistence as an
orchestrator tool, or any change to `src/orchestrator/`. Today, the
in-process orchestrator (`src/orchestrator/analysis_tools.py`) never calls
`ensure_database_ready` or anything `--save-run`-shaped — it only runs pure,
non-persisting analysis — so this gap cannot occur there yet. It becomes
directly relevant the moment persistence is exposed as an orchestrator-
callable capability, which `MASTER_PLAN.md`'s Light Mode workflow
(watchlist → refresh → stored run) anticipates but has not scheduled.
