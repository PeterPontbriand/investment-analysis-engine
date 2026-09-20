# Slice G2 — Completion evidence (batch 3)

**Review disposition:** implemented; pending project owner review and acceptance.
**Date:** 2026-09-19 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

Third review checkpoint under the same batching authorization as
[E3/E4/F1/F2](SLICE_E3_E4_F1_F2_COMPLETION_EVIDENCE.md) and
[F3/G1](SLICE_F3_G1_COMPLETION_EVIDENCE.md), isolated on its own per the
originally proposed grouping given its distinct risk profile (races,
connection ownership, admission control) rather than bundled with anything
else.

## Design

`src/workspace/refresh.py`'s `refresh_watchlist` gained one new parameter,
`policy: RefreshPolicy`, selecting between two admission strategies over the
exact same per-job contract G1 already established:

- `policy.workers == 1` — the function's own default — runs the unmodified
  G1 sequential loop, refactored only to iterate a pre-built `jobs` list
  instead of nested `for` loops (identical member-then-selection order,
  identical behavior). This default is deliberately `RefreshPolicy(workers=1)`,
  distinct from `RefreshPolicy`'s own class-level default of `workers=2`, so
  that no existing G1 caller's behavior changes merely because this
  parameter was added; a caller opts into concurrency explicitly.
- `policy.workers > 1` runs the new `_refresh_concurrently` bounded-admission
  algorithm.

### Bounded concurrent admission

At most `workers` jobs are ever in flight, via a `ThreadPoolExecutor` whose
own job queue is never pre-loaded with more than `workers` submissions at a
time: an initial batch of `min(workers, len(jobs))` jobs is submitted, and
each subsequent job is submitted only after an in-flight job's slot has been
freed *and* its outcome has already been persisted (or its failure recorded)
— never eagerly ahead of that.

**Connection ownership / "the coordinator is the only run writer":** a
worker's only responsibility is calling the injected `executor` and
reporting back a raw `_JobOutcome` (its own measured `started_at`/
`completed_at`, plus either a capture or a caught exception). This
function's own calling thread — the coordinator, never a worker thread — is
the only thread that ever calls `execute()`, and therefore the only thread
that ever calls `repository.insert`. `test_g2_repository_insert_always_runs_on_the_calling_thread_not_a_worker`
proves this directly by recording `threading.get_ident()` on both sides.

**Worker-measured timing, not coordinator time:** since the coordinator
calls `execute()` with an already-computed capture, `execute()`'s own two
`clock()` calls (around `capture()`) would otherwise record a near-zero
window around nothing but handing that capture off — not the real work
time measured in the worker thread. A small `_replay_clock(started_at,
completed_at)` helper replays the worker's own two measured instants
through `execute()`'s existing two-call clock contract, requiring zero
changes to the already-accepted D5 `execute()` itself.
`test_g2_persists_worker_measured_timing_via_replay_clock` proves the
persisted run's `started_at`/`completed_at` are exactly the worker's own
measured values.

**Snapshot order preserved regardless of completion order:** each job's
`batch_position` is fixed at admission time (its position in the watchlist's
own member-then-selection snapshot order), never at completion time.
Results are collected into a dict keyed by position and reassembled in
position order before returning, so the final `RefreshSummary.results` is
always in snapshot order even when a later-admitted job finishes first.
`test_g2_preserves_snapshot_order_despite_out_of_order_completion` proves
this with a deliberately slow first job and a fast second job.

**Job isolation preserved under concurrency:** exactly the same per-job
isolation G1 already provided — an adapter exception or a persistence
failure is caught at that one job and recorded as a result with no `run`,
never aborting the batch — carries over unchanged to the concurrent path
(`test_g2_isolates_one_jobs_executor_exception`,
`test_g2_isolates_one_jobs_persistence_failure`).

**Shared egress budget:** this module still owns no provider/resolver/cache
composition; `executor` is caller-supplied exactly as in G1. Bounding
concurrent admission to `workers` in-flight jobs is what prevents this
service from ever calling `executor` more than `workers` times
concurrently, so whatever egress budget, rate limit, or shared client the
caller's own `executor` implementation holds is never multiplied per
worker beyond that bound — job-scoping the underlying provider/resolver
resources themselves remains the caller's own responsibility, exactly as
already documented on `executor`.

**Immediate save visible to another connection:** proved against real
SQLite storage, not fakes.
`test_g2_concurrent_refresh_saves_are_visible_to_another_connection_before_the_batch_finishes`
gates one job so the refresh cannot finish, releases the other, waits
(via an explicit signaling repository wrapper, not a sleep) for that job's
insert to complete, and — while the batch is still provably running —
opens a brand-new `SQLiteDatabase`/`SQLiteAnalysisRunRepository` and
confirms the run is already visible.

## No changes to D5's `execute()`

Unlike the G1 checkpoint, which added `BatchContext` to `execute()`, G2
required no further changes to the already-accepted D5 `execute()` at all —
the replay-clock technique above reuses its existing `clock` parameter
exactly as designed.

## Tests

`tests/workspace/test_refresh.py` grew from 12 to 21 tests (all 12 original
G1 tests pass unchanged against the refactored sequential branch). New G2
tests, all using event/barrier coordination rather than timing guesses:

- `test_g2_bounds_admission_and_gates_replacement_on_persisted_completion` —
  proves at most `workers` jobs are ever admitted, and that a replacement is
  only admitted after the freed slot's job is persisted (via a shared
  causal-ordering log, not inference from timing).
- `test_g2_preserves_snapshot_order_despite_out_of_order_completion`
- `test_g2_repository_insert_always_runs_on_the_calling_thread_not_a_worker`
- `test_g2_persists_worker_measured_timing_via_replay_clock`
- `test_g2_isolates_one_jobs_executor_exception`
- `test_g2_isolates_one_jobs_persistence_failure`
- `test_g2_workers_greater_than_job_count_runs_every_job_without_error`
- `test_g2_concurrent_refresh_saves_are_visible_to_another_connection_before_the_batch_finishes`
  (real SQLite database, two independent connections)
- `test_job_outcome_requires_exactly_one_of_capture_or_error` (the new
  private `_JobOutcome` dataclass's own invariant)

## Contract proof (§8)

| Contract requirement | Evidence |
| :--- | :--- |
| Typed `RefreshPolicy`, default workers 2, range 1-4 | Unchanged from G1; `refresh_watchlist`'s own default is the distinct, explicitly-documented `workers=1`. |
| Bounded admission, not eager submission of the whole list | `test_g2_bounds_admission_and_gates_replacement_on_persisted_completion`. |
| Coordinator is the only run writer; persists before admitting replacement | Same test (causal log) plus `test_g2_repository_insert_always_runs_on_the_calling_thread_not_a_worker`. |
| Providers/resolvers/cache connections job-scoped | Documented as the caller's responsibility on `executor`, exactly as G1 already required; this slice adds no provider/resolver composition of its own. |
| Provider failure affects only its job; no automatic retry | `test_g2_isolates_one_jobs_executor_exception`; no retry logic exists anywhere in this module. |
| Immediate save visible to another connection/process | `test_g2_concurrent_refresh_saves_are_visible_to_another_connection_before_the_batch_finishes`. |
| Tests use event/barrier coordination, not timing guesses | Every new concurrency test synchronizes via `threading.Event` and a causal-ordering log; none sleep to assert an absence. |

Graceful Ctrl+C / interruption semantics are explicitly G3's scope, not
this slice's, per the contract's own G2/G3 split.

## Full managed gate

Ruff, Ruff format, and strict mypy passed clean. The full pytest run:
**3,054 passed** (9 new), combined coverage **91%**; `src/workspace/refresh.py`
reaches 100% line/branch coverage. The new concurrency tests were also run
three consecutive times in isolation with no flakiness observed.

## Boundaries and review gate

G3 (refresh CLI wiring / interruption / storage-failure stop) is the next
and final batch, not part of this checkpoint. Nothing was committed, pushed,
or opened as a PR.
