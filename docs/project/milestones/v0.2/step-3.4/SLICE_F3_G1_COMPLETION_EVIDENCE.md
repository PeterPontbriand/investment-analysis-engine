# Slices F3, G1 — Completion evidence (batch 2)

**Review disposition:** implemented; pending project owner review and acceptance.
**Date:** 2026-09-19 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

Second review checkpoint under the same batching authorization as
[E3/E4/F1/F2](SLICE_E3_E4_F1_F2_COMPLETION_EVIDENCE.md): F3 (opt-in
`--save-run` on the four existing direct commands) and G1 (the sequential
refresh service, with no CLI wiring — that is G3).

## D5 extension: `BatchContext`

Both F3 and G1 need `execute()` to stamp `refresh_id`/`batch_position`/
`watchlist_id`/`watchlist_name` — fields `AnalysisRun` (B2) already defines
but D5's `execute()` never wired through, since refresh/batch identity was
explicitly out of D5's own scope. Added one new optional parameter,
`batch: BatchContext | None = None`, to the already-accepted
`src/workspace/execution.py`; omitting it (every existing caller) leaves
every batch-identity field null exactly as before. `BatchContext` bundles
all four fields together because `AnalysisRun`'s own validator requires
`refresh_id`/`batch_position` to be both set or both null, and likewise for
`watchlist_id`/`watchlist_name`. Two new tests confirm the omitted-batch
default and the stamped-batch case; all fourteen existing D5 tests pass
unchanged.

## F3 — Opt-in `--save-run` on the four direct commands

Added `--save-run` to `momentum`, `graham-number`, `graham-growth`, and
`fcf-growth`. A new shared helper, `_maybe_save_run`, wraps each command's
existing D1-D4 adapter call: when not saving, it is a pure passthrough to
the unmodified existing call (proven by the full pre-existing CLI test
suite passing unchanged — see the defect below for the one real gap this
surfaced); when saving, it checks run-storage readiness before the adapter
runs (the contract's "preflight before provider work" ordering), calls the
adapter exactly once via `execute()`, and reports the saved run's ID on
stderr only, leaving existing stdout (including JSON) untouched.

Momentum's own wiring does not use `_maybe_save_run`: its profile is
composed CLI-side (outside the D1 adapter, unlike the other three, whose
adapters compose their own profile internally), and its ticker may be
`None` (a configured default), which `--save-run` explicitly rejects with a
usage error rather than trying to persist an ambiguous identity — a
deliberate, narrow command-specific difference, not an inconsistency.

FCF's saved selection always records `provider_id="sec_edgar"` regardless
of the `--data-provider` flag's value: the command already always uses the
SEC production provider internally regardless of that flag (a pre-existing
quirk, not something F3 introduces or corrects), so the saved selection
reflects the provider actually used rather than risk a validation failure
on an arbitrary flag value that was never honored in the first place.

### A real defect found and fixed before any test was written

Building `_maybe_save_run`'s first draft passed `request=AnalysisRequest(...)`
as an eagerly-evaluated keyword argument. Python evaluates every call
argument before entering a function, so this construction ran unconditionally
— even on the default, non-saving path. Running the full existing Graham
test suite immediately surfaced 15 failures: several existing tests use a
synthetic `--data-provider fixture-synth` value (valid for the existing,
more permissive `GrahamNumberConfig`/`GrahamGrowthConfig`, used purely for
dependency injection) that the stricter workspace `GrahamNumberSelection`/
`GrahamGrowthSelection` types reject outright (B1 restricts
`security_provider_id` to `sec_edgar`/`massive`). Fixed by changing
`_maybe_save_run`'s parameter to `request_factory: Callable[[], AnalysisRequest]`,
called at most once and only when `save_run` is true — confirmed by
rerunning the full pre-existing CLI/Graham/FCF/existing-strategy-output test
suite (103 tests) with zero regressions.

### Tests

`tests/test_cli_save_run.py` (11 tests, all four commands): default calls
save nothing; `--save-run` persists and reports the ID on stderr while
leaving stdout JSON byte-parseable; a typed `not_applicable` (known-ETF)
outcome is persisted, not skipped; `--no-cache` plus `--save-run` still
saves; a storage failure (simulated `AnalysisRunConflictError`) is visible
with a nonzero exit and no raw traceback; momentum's default-ticker usage
guard; and the saved Graham Growth selection carries the exact requested
assumptions. Isolation note: `src.cli`'s own `settings` binding is
deliberately *not* added to the shared `isolated_cli_database` fixture,
because several already-accepted tests mutate the real settings singleton
directly for unrelated fields (e.g. SEC identity) via `patch.object`, and a
module-level rebind would silently defeat those patches; this test module
isolates `src.cli.settings` locally instead, preserving every other field.

## G1 — Sequential refresh service

New `src/workspace/refresh.py`: `refresh_watchlist(name, *, watchlists,
repository, executor, ...)`. Reads the named watchlist once (the frozen
snapshot the contract requires — edits afterward apply only to the next
refresh), rejects an empty membership or selection set as a usage error
before any job runs, then iterates every (ticker, selection) pair in
member-position-then-selection-position order, calling `execute()` once per
pair with a shared `refresh_id` and an incrementing `batch_position`.

`executor` is injected exactly like the D1-D4 adapters' own "borrow
dependencies, don't construct them" convention: this module owns no
provider/resolver/cache/CLI composition, so it cannot invoke a Typer
command or reparse rendered output, matching §6/§8's boundary exactly. G1
always executes strictly sequentially; `RefreshPolicy` (workers, range 1-4)
is defined now as the typed contract the eventual G2 concurrency needs, but
is deliberately not yet threaded into `refresh_watchlist` — there is
nothing for a worker count to bound until G2 exists, and adding the
parameter later is an additive, backward-compatible extension, not a
redesign.

A job's own exception — whether the adapter raises or the terminal insert
fails — is caught at that single job, recorded as a result with no `run`
and a diagnostic `error` string, and never aborts the remaining pairs.
Whether a *storage* failure specifically should stop admitting further work
is explicitly G3's "storage-failure stop" concern, not this slice's; G1
provides the uniform per-job isolation that behavior will be built on.

### Tests

`tests/workspace/test_refresh.py` (12 tests, fake dependencies only):
missing watchlist and empty-membership/empty-selection usage errors;
member-then-selection iteration order with correct `batch_position` values;
shared `refresh_id`/watchlist identity stamped on every produced run; one
job's adapter exception isolated from the others (which still execute and
persist); one job's persistence failure isolated the same way; two calls
against the same watchlist producing entirely distinct runs; an explicit
event-ordering test proving each job's insert happens before the next job's
executor runs (per-completion durability, not just eventual consistency);
`RefreshSummary.counts`; and both dataclasses' own invariant validation
(`RefreshPolicy`'s worker range, `RefreshJobResult`'s run-xor-error rule).

## Contract proof (§6, §8, §9)

| Contract requirement | Evidence |
| :--- | :--- |
| F3: default commands unchanged | Full pre-existing CLI/Graham/FCF/existing-strategy-output suite (103+ tests) passes with zero modifications to their own code. |
| F3: preflight readiness before provider work | `_maybe_save_run` checks `ensure_database_ready` before calling `run_adapter`, which is the only thing that touches a live provider. |
| F3: no-cache plus save; typed unavailable persisted | Dedicated tests: `--no-cache --save-run` still saves; a `not_applicable` outcome is persisted. |
| F3: storage errors visible, nonzero exit, never a fabricated success | Dedicated test with a simulated `AnalysisRunConflictError`; no "Saved" message, no traceback, nonzero exit. |
| G1: frozen snapshot | Watchlist read exactly once via `watchlists.get`; no re-query mid-refresh. |
| G1: independent failures | Both adapter-exception and persistence-failure isolation tests. |
| G1: saved IDs, repeated refresh distinct | Ordered `RefreshJobResult.run` values; two-call test proves distinct `refresh_id`/`analysis_run_id` each time. |
| G1: per-completion durability | Explicit interleaved event-order test (execute→insert→execute→insert, never execute→execute→insert→insert). |

## Full managed gate

Ruff, Ruff format, and strict mypy passed clean. The full pytest run:
**3,045 passed** (25 new: 2 in `test_execution.py` for `BatchContext`, 11 in
`test_cli_save_run.py`, 12 in `test_refresh.py`), combined coverage **91%**;
`src/workspace/refresh.py` and `src/workspace/execution.py` both reach 100%
line/branch coverage.

## Boundaries and review gate

G2 (bounded concurrency) and G3 (refresh CLI/interruption) are the next
batches and are not part of this checkpoint; per the earlier proposed
grouping, G2 is deliberately isolated as its own review given its distinct
risk profile (races, connection ownership, admission control) rather than
bundled with anything else. Nothing was committed, pushed, or opened as a PR.
