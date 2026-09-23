# P2-Profiles Slice D — Production Wiring Inventory

Maps every executable consumer of live instrument-profile composition, database
availability per site, and the design forks that must be resolved before any
wiring edit. Mirrors [R2's migration-inventory method](../r2/R2_MIGRATION_INVENTORY.md).

Local sequence and status: [companion contract](P2_PROFILES_CONTRACT_AND_SLICE_PLAN.md#sequence-and-status).

## 1. Discovery and scope

Searches covered literal occurrences of `compose_instrument_profile`,
`compose_graham_profile`, `InstrumentProfile`, `instrument_profile=`, and
`profile_resolver` across `src`, `tests`, and `docs/project`. Representative
commands (repository root):

```powershell
git grep -n -I -F -e 'compose_instrument_profile'
git grep -n -I -F -e 'compose_graham_profile'
git grep -n -I -F -e 'instrument_profile=' -- src
git grep -n -I -F -e 'InstrumentProfile' -- src
git grep -n -I -F -e 'profile_resolver'
git grep -n -I -F -e 'AnalysisToolDependencies(' -e 'AnalysisToolHandlers('
```

Every finding below was confirmed by reading the actual call chain, not just
the grep hit — the raw literal count (four `compose_instrument_profile(`
sites, four `compose_graham_profile(` sites) does **not** match the true
number of independent architectural patterns, which is two, plus one
out-of-scope seam. This is exactly the correction the contract's §13.2
required a dedicated pass to find rather than assuming the draft slice's
initial four-site count was complete.

## 2. Composition-pattern map

| Pattern | Call sites | Notes |
| :--- | :--- | :--- |
| Momentum: three independently duplicated inline sites | [`src/cli.py:278`](../../../../src/cli.py) (`momentum`, `--save-run` branch); [`src/cli.py:295`](../../../../src/cli.py) (`momentum`, default branch); [`src/cli_workspace.py:772`](../../../../src/cli_workspace.py) (`_execute_momentum`, used by `_refresh_executor`) | Each constructs its own `_identity_candidate()` closure over a fresh `YFinanceClient()`, used as both the identity and kind candidate. No shared helper exists for Momentum (unlike Graham/FCF). |
| Graham Number / Graham Growth / FCF Growth: one shared site | [`src/workspace/graham_shared.py:34`](../../../../src/workspace/graham_shared.py) (`compose_graham_profile`) | Called from `graham_number_execution.execute_graham_number` (78), `graham_growth_execution.execute_graham_growth` (93), `fcf_growth_execution.execute_fcf_growth` (99). Each of those three adapters is itself called from **both** a direct CLI command (via `cli.py`'s `_run_graham_number`/`_run_graham_growth`/its FCF equivalent) **and** watchlist refresh (via `cli_workspace.py`'s `_execute_graham_number`/`_execute_graham_growth`/`_execute_fcf_growth`, dispatched from `_refresh_executor`). Confirmed by reading both call chains, not assumed from the shared module name. Wiring this one function covers six execution paths. |

## 3. Database availability per site (confirmed by reading, not inferred)

| Site | Database in scope today? | Evidence |
| :--- | :--- | :--- |
| `cli.py:278` (Momentum, `--save-run`) | **Yes** — `database = SQLiteDatabase(settings)` constructed immediately above for Analysis Run persistence. | `src/cli.py` momentum command, save branch. |
| `cli.py:295` (Momentum, default) | **No.** | Same command, non-save branch. **Decision (2026-09-21): stays live-only; no database is opened purely for caching here.** |
| `cli.py`'s Graham Number/Growth/FCF Growth, `--save-run` | **Yes** — via the single shared `_maybe_save_run` helper (`src/cli.py:189`), which opens `database = SQLiteDatabase(settings)` around `run_adapter()` (itself `execute_graham_number`/etc., which calls `compose_graham_profile`). One helper, all three methods. | `src/cli.py:144-204` (`_maybe_save_run`). |
| `cli.py`'s Graham Number/Growth/FCF Growth, default (no `--save-run`) | **No** — `_maybe_save_run` returns `run_adapter()` directly with no database. | Same function, `if not save_run: return run_adapter()`. |
| `cli_workspace.py:772` (Momentum, refresh) | **No, by explicit design**, not merely by omission. | `_refresh_executor`'s own docstring: *"Each branch composes entirely fresh provider/resolver/cache dependencies per call — job-scoped, exactly as `refresh_watchlist`'s own contract requires for safe concurrent use."* The enclosing `refresh` command does hold a `SQLiteDatabase` (`_workspace_database()`), but `refresh_watchlist`'s `executor: Callable[[str, AnalysisSelection], ExecutionCapture]` type is a narrow two-argument callable that does not carry it through, and `_refresh_executor`/`_execute_momentum`/`_execute_graham_number`/`_execute_graham_growth`/`_execute_fcf_growth` all take no database parameter. |
| `graham_shared.py:34` via refresh (`_execute_graham_number`/`_execute_graham_growth`/`_execute_fcf_growth`) | **No, same reason as above.** | Same `_refresh_executor` job-scoping contract; Graham's `_production_financial_cache` context manager (a different, existing cache) is opened per job today, not threaded from the outer refresh database either — the pattern is consistent, not an oversight specific to Momentum. |

## 4. Out of scope: the orchestrator/evaluation seam

[`src/orchestrator/analysis_tools.py`](../../../../src/orchestrator/analysis_tools.py)'s
`AnalysisToolDependencies.profile_resolver: Callable[[str], InstrumentProfile] | None`
is an already-built injection seam used by all four `analyze_*` tool handlers.
It is **not a production call site today**: `AnalysisToolDependencies(` is
constructed only in [`src/evaluation/composition.py:181`](../../../../src/evaluation/composition.py)
(the Golden-Suite evaluation harness) and in tests — confirmed by searching
every construction site, not assumed. There is no live CLI/orchestrator entry
point yet; IMPLEMENTATION_PLAN.md's own sequence table lists Step 3.6 (Light
Mode, which would add `ian analyze TICKER` per its implementation outline
item 6) as "Not started." This seam is left untouched by Slice D and is worth
noting for whoever builds Step 3.6: `profile_resolver`'s
`Callable[[str], InstrumentProfile]` shape is a narrower single-ticker
projection of `CachedInstrumentProfileResolver.resolve`'s keyword-heavy
signature, so wiring it later means supplying a thin closure over `resolve`,
not redesigning the seam.

## 5. Test/patch-target inventory (for the implementing slice)

Existing tests that patch or directly exercise a to-be-wired composition
point, collected so implementation does not have to rediscover them:

- `tests/test_cli.py:174`, `tests/test_cli_historical_cache.py:76` — patch
  `src.cli.compose_instrument_profile` (Momentum, direct command).
- `tests/workspace/test_graham_shared.py:21,43` — patch
  `src.workspace.graham_shared.compose_instrument_profile` directly (the
  shared helper's own unit tests).
- `tests/test_cli_save_run.py:216`, `tests/test_cli_financial_cache.py:93-95,168-170`,
  `tests/test_cli_refresh.py:188`, `tests/test_cli_fcf_earnings_growth.py:37,78`,
  `tests/test_cli.py:465-466`, `tests/workspace/test_fcf_growth_execution.py:166,201,223,250`,
  `tests/workspace/test_graham_growth_execution.py:108,132,145,159`,
  `tests/workspace/test_graham_number_execution.py:96,115,131` — patch
  `compose_graham_profile` at its **consumer's** module path (e.g.
  `src.workspace.graham_number_execution.compose_graham_profile`), per each
  execution adapter's own `from ... import compose_graham_profile` binding.
  Any wiring change to `compose_graham_profile`'s call signature or to the
  adapters' calls to it must update every one of these patch targets.
- `tests/test_cli_refresh.py` (Momentum jobs) mocks at
  `src.workspace.momentum_execution.MomentumAnalyzer.run_with_context`, one
  level below profile composition, and does **not** patch
  `compose_instrument_profile`/`YFinanceClient` for the refresh path — the
  real (network-blocked-in-CI) provider call is left to run and fail open
  into `PROVIDER_ERROR`/`UNAVAILABLE` diagnostics, which Momentum's
  calculation does not depend on. Wiring the cache into this path must
  preserve this fail-open tolerance; it must not turn a blocked/offline
  identity lookup into a refresh-job failure.
- No test patches `src.cli_workspace.compose_instrument_profile` directly —
  confirmed absent, not merely unsearched.

## 6. Active documentation

No active (currently-instructive) documentation describes
`compose_instrument_profile`/`compose_graham_profile`'s call sites in a way
that would go stale from wiring. The two prose mentions found —
`docs/project/milestones/v0.2/graham-comparison/GRAHAM_COMPARISON_REPAIR_PLAN.md`
and `docs/project/milestones/v0.2/step-2.5/STEP_2_5_P1_INSTRUMENT_APPLICABILITY_MAPPING_RECORD.md`
— are historical approval/evidence records for already-closed work packages,
retained per the project's R2-E precedent (historical records are not
rewritten to describe later behavior). No edit is needed there.

## 7. Decisions and open design forks

1. **Resolved 2026-09-21:** the database-free Momentum direct-command path
   (`cli.py:295`) stays live-only; no database is opened purely to consult or
   populate the durable cache there.
2. **New fork found during this reconnaissance, not yet resolved:** the
   watchlist-refresh executor (`_refresh_executor` and everything it calls)
   deliberately composes fresh, job-scoped dependencies per call, documented
   as required for safe concurrent execution under `refresh_watchlist`'s
   worker pool. Wiring the durable cache into refresh means one of:
   - **(a)** Extend `refresh_watchlist`'s `executor` callable type and every
     `_execute_*`/`execute_*` signature to also receive a
     `SQLiteInstrumentProfileRepository`/`CachedInstrumentProfileResolver`,
     built once from the refresh command's existing `SQLiteDatabase` and
     safely shared across concurrent jobs (SQLAlchemy's `NullPool`-backed
     engine hands out an independent connection per `.transaction()`/`.read()`
     call, so sharing the `SQLiteDatabase` object itself should not violate
     the job-isolation intent — but this needs a deterministic concurrent-write
     test to prove, not an assumption); or
   - **(b)** Leave watchlist refresh uncached for now, matching decision 1's
     precedent of preferring the existing architecture's isolation guarantees
     over an added caching benefit, and revisit only if repeated-refresh
     provider load is later shown to matter.

   This is a materially different question from decision 1 (that one was
   about an *ephemeral, no-database* path; this one is about *deliberately
   isolated concurrent* execution with a database already available one
   layer up) and is not resolved by generalizing decision 1's answer.
3. Momentum's three duplicated inline composition sites are a natural
   deduplication candidate (mirroring `graham_shared.py`) but doing so is not
   required to wire the cache at each site independently; recorded as a
   reasonable follow-on, not a Slice D requirement.

## 8. Final site classification — implemented 2026-09-21

Fork §7.2 resolved as (a): wire refresh through, with the concurrency-safety
proof required rather than assumed (P2-Profiles contract §13.6).

| Site | Treatment | Implemented as |
| :--- | :--- | :--- |
| `cli.py:278` (Momentum, `--save-run`) | Wired | `_production_instrument_profile_cache(database)` built locally, `.resolve()` replaces the direct `compose_instrument_profile()` call. |
| `cli.py:295` (Momentum, default) | Live-only (§7.1) | Unchanged. |
| `cli.py` Graham/FCF, `--save-run` (via `_maybe_save_run`) | Wired | `_maybe_save_run` builds the cache once and passes it into `run_adapter(profile_cache)`; all three commands' `run_adapter` lambdas forward it to `execute_*(..., profile_cache=profile_cache)`. |
| `cli.py` Graham/FCF, default | Live-only (symmetric with §7.1) | `run_adapter(None)`; `compose_graham_profile`'s `profile_cache=None` default preserves the exact prior call. |
| `cli_workspace.py` refresh, all four methods | Wired | One resolver built per `refresh` invocation over the refresh command's database, closed over by the `executor=` lambda passed to `refresh_watchlist` — its own public type is unchanged. `_refresh_executor` and every `_execute_*` adapter gained a required `profile_cache` parameter. |

See contract §13.6 for the concurrency-safety fix this wiring required (a
per-ticker lock inside `CachedInstrumentProfileResolver`) and its test
evidence.
