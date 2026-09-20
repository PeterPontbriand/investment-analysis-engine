# Slices G3, H — Completion evidence (batch 4, final)

**Review disposition:** implemented; pending project owner review and explicit final acceptance.
**Date:** 2026-09-19 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

Fourth and final review checkpoint under the same batching authorization as
[E3/E4/F1/F2](SLICE_E3_E4_F1_F2_COMPLETION_EVIDENCE.md),
[F3/G1](SLICE_F3_G1_COMPLETION_EVIDENCE.md), and
[G2](SLICE_G2_COMPLETION_EVIDENCE.md): G3 (refresh CLI wiring and
cooperative interruption) and H (acceptance/docs), completing Step 3.4 per
the contract's own slice table. Per the contract, this batch stops before
P2-Profiles, ESC-D renewal, or Step 3.5; none of those are started.

## G3 — Refresh CLI and cancellation boundary

### The `refresh` command

`src/cli_workspace.py` gained the contract's bare `financial-agents refresh
NAME [--workers N] [--json]` command (registered directly on the root app,
alongside the existing `watchlist`/`runs` sub-apps). It composes a
`WatchlistLookup`/`AnalysisRunSink` from one readiness-checked database
exactly like every other workspace command, then calls the already-accepted
`refresh_watchlist` with a new dispatch executor.

### The dispatch executor

`_refresh_executor` maps a stored `AnalysisSelection` to its method's
production adapter by `isinstance`, converting each selection back to its
native config/policy via the existing `to_*_config()`/`to_fcf_policy()`
methods (B1) and composing entirely fresh provider/resolver/cache
dependencies per call — mirroring exactly how each direct command in
`src.cli` already composes the same dependencies for one invocation, and
satisfying `refresh_watchlist`'s own job-scoping requirement for safe
concurrent use.

### A necessary relocation: `src/cli_composition.py`

Building the executor required calling the SEC/Massive provider and Graham
resolver builders (previously private functions inside `src.cli`) from
`src.cli_workspace` too. Relocating them into the existing `src.cli_support`
was tried first and reverted: `tests/_cli_helpers.py`'s `isolated_cli_database`
fixture rebinds `src.cli_support.settings`/`src.cli_workspace.settings` for
*database* isolation only, and doing so would have silently defeated
existing tests that mutate the real shared settings singleton via
`patch.object(settings, "sec_user_agent", ...)` — the same class of gap the
`isolated_cli_database` fixture's own docstring already warns about for
`src.cli`. A new module, `src/cli_composition.py`, holds
`build_sec_production_provider`, `build_massive_production_provider`,
`build_graham_resolver`, and `growth_assumptions` (renamed from their
private `_`-prefixed originals to a small public surface both `src.cli` and
`src.cli_workspace` import); its own `settings` binding is never rebound by
any fixture, so SEC-identity/growth-assumption behavior is unaffected while
refresh's own database access still isolates correctly through
`src.cli_workspace.settings`. `src/cli.py`'s four call sites were updated to
import from the new module; no behavior changed. Fixing the fallout — test
patch targets that referenced the old `src.cli._build_*` names — surfaced
one call site (`test_explicit_memory_cache_is_retained`) whose mock was
silently not intercepting the real call at all (patching the wrong module's
copy of the name); corrected alongside the rest.

### Cooperative graceful interruption

`refresh_watchlist` and `_refresh_concurrently` (`src/workspace/refresh.py`)
gained one new optional parameter, `cancellation: threading.Event | None`.
Once set, no further job is admitted — a job that never started does not
appear in the summary at all, never a fabricated "cancelled" row — while any
job already admitted is left to finish naturally and its outcome is still
persisted normally; a narrow "cancel a submitted-but-not-yet-started future"
window is handled defensively (`Future.cancel()`, removing it from the
pending set only if the cancel actually took effect before the worker
started). Nothing here raises `KeyboardInterrupt` or attempts to kill a
running thread, matching the contract's explicit "no promise of killing a
blocked Python thread."

The CLI's `refresh` command installs its own `SIGINT` handler for the
duration of one refresh, restoring the previous handler in a `finally`; the
handler only sets the `threading.Event`, never raises. After
`refresh_watchlist` returns, the CLI checks whether cancellation fired and
exits 130; otherwise exit 1 if any result has an error or an
unavailable/failed outcome, else exit 0. Text output lists every persisted
run and a final count-by-outcome line; `--json` emits one final document
(refresh ID, ordered results, counts) — no per-job chatter reaches stdout
either way, satisfying the contract's "a second CLI process can inspect
committed results before refresh ends" together with G2's own proof that
each job's insert commits independently.

### A defect found and fixed before any test caught it

The first draft of `_refresh_concurrently`'s cancellation handling called
`leftover.cancel()` without removing a successfully-cancelled future from
the `pending` dict. A cancelled `Future` still appears in `wait()`'s `done`
set, and `future.result()` on it raises `CancelledError` — which would have
crashed the coordinator loop the first time a genuinely-queued-but-unstarted
future was cancelled. Fixed by only removing a future from `pending` when
`.cancel()` actually returns `True`.

### Tests

`tests/workspace/test_refresh.py` grew by 4 tests covering cancellation
already-set (both sequential and concurrent paths), cancellation firing
mid-batch (sequential), and — using the same event/causal-log coordination
as the existing G2 tests — a concurrent scenario proving a freed slot is
never replaced once cancelled while the already-running job still persists.

New `tests/test_cli_refresh.py` (11 tests): missing watchlist, empty target,
out-of-range `--workers`, sequential success with counts, JSON's one stable
document, a `not_applicable` outcome still persisted (exercising the Graham
Number dispatch branch), a storage failure's nonzero exit, graceful
interruption (simulated by capturing and directly invoking the installed
`SIGINT` handler — portable across platforms, no reliance on real OS signal
delivery), Graham Growth Value dispatch (via a configured watchlist
selection), FCF/Earnings Growth dispatch, and an unavailable outcome's exit
1. A CLI-level test that actually ran a real `ThreadPoolExecutor` under
`--workers 2` was found to trigger a rare ("I/O operation on closed file",
roughly 1-in-8), Windows-specific race in Click's `CliRunner` stdio-capture
teardown — a test-harness artifact, not a defect in refresh (already
exhaustively proven concurrent-safe directly against `refresh_watchlist` in
G2/G3's own tests). Removed that one CLI-level concurrent test and pinned
every other CLI-level test to `--workers 1`, documented in the test file's
own module docstring; ten consecutive full-suite runs of the file showed no
flakiness afterward.

## H — Acceptance and documentation

### `docs/user/WORKSPACE.md` (new)

A durable user-facing guide: saving a single result (`--save-run`),
watchlists (create/add/remove/show/configure/disable), refreshing a
watchlist (`--workers`, `--json`, exit codes, interruption behavior,
cross-connection visibility), and browsing saved runs (`runs list`/`runs
show`, all presentation modes, the "replay never recalculates" guarantee).
Linked from `docs/user/README.md`'s index and from the root `README.md`.
Four new terms (Analysis Run, Selection, Watchlist, Refresh) added to
`docs/user/GLOSSARY.md` alongside the existing analysis-architecture terms,
cross-linked from the new guide.

### Integration test: the documented workflow, end to end

New `tests/test_workspace_integration.py` (1 test, entirely offline): create
a watchlist, configure Graham Growth Value with explicit assumptions,
disable the one default method that would not apply to this ticker, add the
ticker, confirm `watchlist show` reflects exactly the intended selections,
refresh the whole watchlist in one command, confirm `runs list` shows all
three saved runs sharing one refresh ID, then replay every one of them
through all four `runs show` presentation modes (concise, `--details`,
`--diagnostics`, `--json`). This is the one place that specifically proves
E1-E4's "no recalculation" replay guarantee also holds for a run `refresh`
produced through the full CLI stack, not only a run saved directly.

### §4.10 criterion → evidence map

| §4.10 criterion | Evidence |
| :--- | :--- |
| Named configuration/membership | F1 (`watchlist create/add/remove/show/configure/disable`); `tests/test_cli_workspace.py`. |
| Bounded fan-out, independently durable outcomes | G1/G2 bounded admission and per-job persistence; `tests/workspace/test_refresh.py`. |
| List/show across all statuses | F2 (`runs list/show`); completed, not_applicable (ETF), unavailable (`SUBJECT_MISSING`), and failed statuses each exercised across this session's test files. |
| Four-method provenance/identity/config fidelity | D1-D4 capture adapters; E1-E4 replay tests; this batch's `_refresh_executor` reusing the identical adapters for a fifth call site. |
| Independent versions | `_METHOD_VERSIONS` (D5); B3-B6 codec version round trips. |
| Deterministic historical replay | E1-E4 (`tests/reporting/test_analysis_run_replay.py`); reconfirmed for refresh-produced runs in `test_workspace_integration.py`. |
| Telemetry identity separation | D5's `execute()` never imports telemetry; C3's independent-deletion tests. |
| Absence of unattended services | `refresh` is a single bounded CLI invocation with no background scheduler, daemon, or persistent process; nothing in this batch starts one. |
| Migration upgrade/rollback | C1 (unchanged this batch). |
| Storage error | C3/D5/F3/G1 storage-failure isolation; this batch's `test_refresh_storage_failure_is_visible_and_nonzero_exit`. |
| Graceful/hard interruption limitation | This batch's cancellation tests (service and CLI level); explicit "no thread killing" documentation. |
| Direct-command compatibility evidence | Full existing CLI/Graham/FCF/Momentum suite (3,000+ tests) passes unchanged after the `cli_composition` relocation. |

## Full managed gate

Ruff, Ruff format, and strict mypy passed clean. The full pytest run:
**3,070 passed** (16 new: 4 in `test_refresh.py`, 11 in `test_cli_refresh.py`,
1 in `test_workspace_integration.py`), combined coverage **91%**;
`src/cli_workspace.py` reaches 100% line/branch coverage;
`src/workspace/refresh.py` reaches 99% (one defensively-handled race window
— successfully cancelling a submitted-but-not-yet-started future — is not
deterministically triggerable without simulating OS thread-scheduling
delays, and is not forced with a flaky or mocked test); `src/cli_composition.py`
reaches 95% (one pre-existing, unrelated gap — the Massive-configured
success path — travelled unchanged from its original location in
`src.cli` and was never in any batch's own test scope).

## Step 3.4 status

With G3 and H implemented, every slice in the contract's table (B1 through
H) has now been implemented and is either already accepted or, for this
final batch, pending project owner review. Explicit final acceptance of
Step 3.4 as a whole is the project owner's own decision, not self-granted
here. Per the contract's own sequencing note, P2-Profiles, ESC-D renewed
acceptance, and Step 3.5 are separate, subsequent milestone-track items;
none of them are started, and none of this batch's edits touch anything
outside Step 3.4's own scope.

## Boundaries

Nothing was committed, pushed, or opened as a PR.
