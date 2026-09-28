# IR.2.5 — Cache Unification: Implementation Plan

Planning record only. No source or test file has been changed by this document; it is written
against the codebase as it stands after IR.2.1–2.4 and IR.4, IR.7. Revision 3: drops the lazy
wrapper classes revision 2 proposed, after confirming none of the three real classes they would
have wrapped actually touch the database. This revision is smaller and lower-risk than either prior
one.

Local sequence and status: [companion plan](IR_CONTRACT_AND_SLICE_PLAN.md#3-sequencing). Scope
origin: [§6, item 10](IR_CONTRACT_AND_SLICE_PLAN.md#6-ir2-implementation-inventory--approved-2026-09-24)
and [§6.9](IR_CONTRACT_AND_SLICE_PLAN.md#6-ir2-implementation-inventory--approved-2026-09-24).

## Revision 3: the lazy wrappers are gone

**Do `SQLiteResolvedInputCache`, `SQLiteMarketDataRepository`, and `CachedHistoricalDataClient`'s
constructors touch the database?** No, none of them — verified directly:

- `SQLiteResolvedInputCache.__init__` (`repositories/resolved_input_cache.py:145-157`): "Configure
  the cache without opening connections or changing schema" — stores `database`/`clock`/`ttl` only.
- `SQLiteMarketDataRepository.__init__` (`repositories/market_data.py:292-295`): "Retain a
  caller-owned database without opening it or migrating" — stores `database`/`clock` only.
- `CachedHistoricalDataClient.__init__` (`cached_client.py:43-61`): stores `provider`, `repository`,
  `variant`, `ttl`, `clock`, `quality_policy` — no I/O.
- `SQLiteDatabase.__init__` itself (`repositories/sqlite.py:25-34`) is also lazy by its own
  docstring — building it never connects; `create_engine` doesn't connect until first use.

**The only thing that touches the database is the explicit `ensure_database_ready(database)` call**
— a separate, deliberate step every composition function already calls on its own. Revision 2's lazy
wrappers existed to defer *that specific call*, but with `use_cache` now known at composition time
(the whole point of the order-preservation fix in revision 2 was to trigger the open immediately
whenever `use_cache=True` anyway), a wrapper class adds no capability — it would open at exactly the
same instant a plain `if use_cache: ensure_database_ready(database)` does. **Dropped entirely:**
`LazyResolvedInputCache`, `LazyMarketDataProvider`, D1, D3, D4, the failed-open remember-and-reraise
mechanism and its dedicated tests, and (since `_production_historical_client` now simply keeps
returning `CachedHistoricalDataClient` unchanged) D2's widening of `run_momentum`'s parameter type.

**One real constraint this surfaces, and how it's handled:** `test_cli_financial_cache.py`'s
`--no-cache` test mocks `src.cli_support.SQLiteDatabase` itself to raise, not just
`ensure_database_ready` — because *today's* `enabled=False` branch returns early with
`InMemoryResolvedInputCache` before `SQLiteDatabase(settings)` is ever called at all
(`cli_support.py:68-70`). Two ways to keep that guarantee:

- **Keep the early-return shape** (recommended, smallest diff): `_production_financial_cache`
  keeps its two-branch structure — `if not use_cache: yield InMemoryResolvedInputCache(clock=clock);
  return`, else construct `SQLiteDatabase`, conditionally-always-true-here call
  `ensure_database_ready`, yield the real cache. This is a straight rename of `enabled` to
  `use_cache` plus nothing else changing in the financial-cache composition; the existing `--no-cache`
  test needs **no change at all**.
- **Alternative:** always construct `SQLiteDatabase(settings)` and always yield
  `SQLiteResolvedInputCache`, skipping only `ensure_database_ready` when `use_cache=False` — this is
  closer to the original contract's literal "always wired" phrasing (one object type in both
  branches), but requires updating that one test's mock target from `SQLiteDatabase` to
  `ensure_database_ready` (the file-never-created assertion, `assert not path.exists()`, is unchanged
  and remains the real proof either way).

Recommendation: the first option. It changes nothing beyond a parameter rename for the financial
side, touches zero tests, and the "two independent controls" problem item 10 actually cared about
(composition-time `enabled` and per-call `use_cache` able to silently disagree) is still fully
closed — because the *value* is now the same `use_cache` flag consulted at both points, not two
separately-named, separately-settable parameters. Whether the object type still differs between
branches is a much smaller concern than that, and not worth an existing test's mock-target churn to
close.

## Decisions carried over from the prior review

- **D2 = moot.** `_production_historical_client` keeps returning `CachedHistoricalDataClient`
  unchanged; `run_momentum`'s parameter stays `BaseDataClient`.
- **Item 3 (this message): extend "required, no default" to `resolver.py`'s own `use_cache`
  parameters — see the count below. Included in this slice.**

## 1. Context

Graham and FCF have two independent, redundant cache controls today.
`_production_financial_cache(*, enabled: bool, clock: ...)` (`src/cli_support.py:59-79`) decides, at
composition time, whether to build a durable `SQLiteResolvedInputCache` (eager
`ensure_database_ready`) or a scratch `InMemoryResolvedInputCache`. Separately, `resolver.py`'s own
methods take an independent per-call `use_cache: bool = True`. Both are driven by the same value at
all six call sites (`src/cli.py:397,513,605`, `src/cli_workspace.py:796,822,848`) — structurally two
parameters that happen to always agree, not one. Momentum has no control at all today:
`_production_historical_client` (`cli_support.py:34-56`) unconditionally wires and eagerly
readiness-checks the historical cache, and `MomentumInputResolver.resolve` never accepts a
`use_cache` parameter to skip it — the exact defaulting bug class item 3 (below) is about to be
found and closed a second time if `resolver.py`'s own defaults are left alone.

**Order-preservation (from the prior review, unchanged by this revision):**
`build_graham_resolver`'s unconditional construction of the real financial-facts provider, and
`compose_graham_profile`'s live SEC/Yahoo identity-provider call — which every one of
`execute_graham_number`/`execute_graham_growth`/`execute_fcf_growth` runs *before* `run_analysis`,
since Graham's calculation needs the composed profile as a required `AnalysisContext` field upfront
— both currently never run when storage is broken, only because `_production_financial_cache`'s
`enabled=True` branch raises at `__enter__` before the `with` body starts. Keeping the early-return
composition shape (above) preserves this exactly: `ensure_database_ready` still raises at `__enter__`
whenever `use_cache=True`, before `build_graham_resolver` is ever reached. Momentum's own two command
branches already call the historical cache before instrument-profile composition either way
(`cli.py:275-308`) — unaffected.

**Relevant architecture, unchanged:** `ARCHITECTURE.md` §5's three instants and decision-clock rule
are untouched — nothing new reads a clock in this revision, since there are no wrapper objects left
to need one. §8's repository table is untouched. Cache **keys** are built entirely outside this
slice's scope; live-run cache-key stability is untouched.

## 2. Approach

### 2.1 `src/cli_support.py` — `_production_financial_cache` and `_production_historical_client`

```python
@contextmanager
def _production_financial_cache(*, use_cache: bool, clock: Callable[[], datetime]) -> Iterator[ResolvedInputSeriesCacheProtocol]:
    """Own one invocation's durable cache; schema upgrades remain explicit."""
    if not use_cache:
        yield InMemoryResolvedInputCache(clock=clock)
        return
    database = SQLiteDatabase(settings)
    try:
        ensure_database_ready(database)
        seconds = settings.financial_cache_ttl_seconds
        yield SQLiteResolvedInputCache(database, ttl=None if seconds is None else timedelta(seconds=seconds), clock=clock)
    finally:
        database.close()
```

This is identical to today's implementation with `enabled` renamed to `use_cache` — no other change.

```python
@contextmanager
def _production_historical_client(
    provider: YFinanceClient, *, use_cache: bool, clock: Callable[[], datetime]
) -> Iterator[CachedHistoricalDataClient]:
    """Borrow the Yahoo client and own historical storage for one analysis."""
    database = SQLiteDatabase(settings)
    try:
        if use_cache:
            ensure_database_ready(database)
        seconds = settings.historical_cache_ttl_seconds
        yield CachedHistoricalDataClient(
            provider,
            SQLiteMarketDataRepository(database),
            request_variant=f"{YFINANCE_HISTORICAL_INTERVAL}:{YFINANCE_PRICE_ADJUSTMENT}",
            ttl=None if seconds is None else timedelta(seconds=seconds),
            clock=clock,
            quality_policy=HistoricalQualityPolicy(expected_adjustment=YFINANCE_PRICE_ADJUSTMENT),
        )
    finally:
        database.close()
```

New required `use_cache` parameter; every current caller passes a literal `True` (matching
`analysis_tools.py:183-188`'s existing "fixed until IR.2.6" pattern) — zero behavior change for any
current caller, since `ensure_database_ready` already ran unconditionally before. No early-return
branch needed here: unlike the financial side, there is no existing test asserting
`SQLiteMarketDataRepository`/`CachedHistoricalDataClient` are never constructed for a disabled case
(Momentum has no disable surface yet), and both classes are confirmed non-touching to construct, so
always building them and conditionally skipping only `ensure_database_ready` is safe and simpler.

Both stay defined with their `_open_*`-equivalent logic inline in `cli_support.py` itself (not a
separate helper this time — there's no factory closure to isolate), so existing
`patch("src.cli_support.ensure_database_ready", ...)` / `patch("src.cli_support.SQLiteDatabase",
...)` targets are completely unaffected by this revision.

### 2.2 `src/data/base_client.py`, `src/data/market_data.py`, `src/data/cached_client.py`,
`src/data/yfinance/client.py`, `src/evaluation/fixtures/market_data.py`,
`src/analysis/strategy/momentum/momentum_analyzer.py` — unchanged from revision 2

All of the per-call `use_cache` threading below is orthogonal to the composition-function
simplification above and still needed — this is what actually makes Momentum's cache-skip real,
which is the slice's other half of scope:

- `MarketDataProvider.fetch_historical_data` (`market_data.py:44`): required, keyword-only
  `use_cache: bool` — no default (item 3's original finding: a default here is exactly how Momentum
  silently dropped `context.use_cache`).
- `CachedHistoricalDataClient.fetch_data_with_context` (`cached_client.py:93`): required, keyword-only
  `use_cache: bool`. `False` skips `self._repository.get(key)` and `self._repository.put(...)`.
- `BaseDataClient.fetch_data_with_context`/`fetch_historical_data` (`base_client.py:50,70`): keep
  `use_cache: bool = True` (default) — the general-purpose interface other, cache-agnostic callers
  also use directly. `fetch_data` itself is untouched (nothing in the chain ever calls it with
  `use_cache`).
- `YFinanceClient.fetch_data_with_context` (`yfinance/client.py:101`): `use_cache: bool = True`,
  ignored (default kept).
- `FixtureMarketDataProvider.fetch_historical_data` (`evaluation/fixtures/market_data.py:46`):
  `use_cache: bool = True`, ignored (default kept — implements the protocol directly, used as
  `market_data_provider=` in `src/evaluation/composition.py:158` and
  `tests/orchestrator/test_analysis_tools.py:68`; default preserves
  `tests/evaluation/cases/test_momentum.py:41`'s existing bare call). `FixtureDataClient` needs no
  change (overrides only `fetch_data`).
- `_ClientProviderAdapter.fetch_historical_data` (`momentum_analyzer.py:414-429`): required, keyword-
  only `use_cache: bool`, forwarded to `self._client.fetch_data_with_context(..., use_cache=use_cache)`.
- `MomentumInputResolver.resolve` (`momentum_analyzer.py:327-352`): required, keyword-only
  `use_cache: bool`, passed to `self._provider.fetch_historical_data(ticker, start_date,
  use_cache=use_cache)`.
- `MomentumAnalyzer.run_analysis` (`momentum_analyzer.py:152-168`): passes
  `use_cache=context.use_cache` — `AnalysisContext.use_cache` already exists and is already threaded
  to every caller; this slice makes Momentum's resolver finally *read* it.
- `run_momentum` (`src/workspace/momentum_execution.py:65-84`): **unchanged** — D2 dropped, parameter
  stays `historical_client: BaseDataClient`, construction stays `MomentumAnalyzer(default_ticker=
  ticker, data_client=historical_client)`.

### 2.3 `src/data/financial/resolver.py` — item 3, now included

**Count (verified by grep, not estimated):** `resolve` (line 207), `_resolve` (line 230, private —
called only internally by `resolve`, already always passed explicitly), `resolve_bvps` (line 333),
and `resolve_three_year_average_eps` (line 369) currently default `use_cache: bool = True`.
`_derive_bvps_from_components` (724) and `_resolve_provider` (1097) already require it with no
default — this gap is pre-existing and partial, not something this slice introduces.

Every production call site of `resolve`/`resolve_bvps`/`resolve_three_year_average_eps` already
passes `use_cache=` explicitly (`src/analysis/shared/financial_resolution.py:100,123,143`,
`src/analysis/strategy/graham_growth/calculation.py:302`,
`src/analysis/strategy/graham_number/calculation.py:214`, and `resolver.py`'s own three internal
calls at lines 360, 739, 749, 759) — **zero production changes needed.**

Test call sites, counted directly (not estimated): **120 total calls to these three methods across 6
test files, of which 3 already pass `use_cache=` explicitly and 117 rely on the default:**

| File | `.resolve(` | `.resolve_bvps(` | `.resolve_three_year_average_eps(` |
| :--- | :--- | :--- | :--- |
| `tests/analysis/graham_value/test_fixture_provider.py` | 15 | 0 | 2 |
| `tests/analysis/graham_value/test_resolution_trace.py` | 5 | 1 | 0 |
| `tests/analysis/graham_value/test_resolver.py` | 46 (1 already explicit) | 0 | 30 (1 already explicit) |
| `tests/analysis/graham_value/test_production_providers.py` | 0 | 4 | 0 |
| `tests/analysis/graham_value/test_sec_bvps_hardening.py` | 0 | 3 | 0 |
| `tests/data/test_quote_freshness.py` | 14 (1 already explicit) | 0 | 0 |
| **Total** | **80** | **8** | **32** |

**Recommendation: include it in this slice**, despite the count. All 117 are the same one-line,
zero-risk mechanical edit (`use_cache=True`, preserving current behavior exactly — the 3 already-
explicit sites already show what the edit looks like), concentrated in one file
(`test_resolver.py` alone is 76 of the 117), and it closes precisely the defaulting pattern this
slice already exists to close for Momentum — leaving `resolver.py` itself inconsistent with
`financial_resolution.py`'s already-required parameters (and with the rest of this slice) would be a
strange place to stop. Not a design decision, just a larger mechanical diff than the rest of this
slice combined — flagging the size honestly rather than folding it in silently.

### 2.4 What this slice does **not** touch

No `--no-cache` CLI option, no `MomentumSelection.use_cache`/`MomentumToolArguments.use_cache` field
(IR.2.6). No change to any resolver's cache **key** construction. No change to
`SQLiteResolvedInputCache`, `SQLiteMarketDataRepository`, or `CachedHistoricalDataClient`'s own
constructors. No formula, classification, or calculation result change.
`src/cli_composition.py`'s `build_graham_resolver`'s `InMemoryResolvedInputCache(clock=clock)`
fallback (item 6) is kept unchanged — a wholly separate code path, no readiness concept, deliberately
exercised by `tests/test_cli.py`'s two identity-focused unit tests that call it without `cache=`.

## 3. Test changes

**Unchanged (revision 3's whole point):**
- `tests/test_cli_financial_cache.py`'s `--no-cache` test: no change (the early-return shape means
  `SQLiteDatabase` still is never constructed for `use_cache=False`).
- `tests/test_cli_database_readiness.py`'s two parametrized "readiness precedes provider calls"
  tests: no change — `ensure_database_ready` still raises at `__enter__` for `use_cache=True`.
- `tests/data/test_cached_client.py` (all direct `SQLiteMarketDataRepository`/
  `CachedHistoricalDataClient` constructions): no change.
- The five `_FixtureClient(FixtureDataClient)` subclasses: no change (confirmed no override of
  `fetch_data_with_context`/`fetch_historical_data` anywhere outside `BaseDataClient`,
  `CachedHistoricalDataClient`, `YFinanceClient`).

**Rename only:**
- `tests/test_cli_financial_cache.py`, `tests/test_cli_database_readiness.py`, `tests/_cli_helpers.py`
  (if applicable): `_production_financial_cache(enabled=...)` → `_production_financial_cache(
  use_cache=...)`.

**New required parameter, needs an explicit value added:**
- `tests/test_cli_historical_cache.py:133,136,144,158` (all four direct calls to
  `_production_historical_client`): add `use_cache=True`.
- `tests/test_cli_historical_cache.py:134,137` (`client.fetch_historical_data(...)`, once
  `use_cache` is required on `MarketDataProvider`/inherited via `BaseDataClient`'s new default): no
  change needed — `BaseDataClient`'s default covers these.

**Mechanical, per §2.3:** 117 call sites across the 6 files in the table above, each gaining
`use_cache=True`.

**New coverage for the threaded parameter:** assert `use_cache=False` reaches the provider's
`fetch_historical_data` call and skips repository `get`/`put`, in
`tests/analysis/momentum/test_momentum_analyzer.py` or `test_momentum_hardening.py`.

## 4. Verification

1. `uv run ruff check --fix .` → `uv run ruff format .` → `uv run mypy --strict src tests`.
2. Full managed gate: `bash "$(git rev-parse --show-toplevel)/scripts/run-quality-gates.sh"`.
3. Targeted re-confirmation (not just full-suite green): `tests/test_cli_database_readiness.py`'s two
   readiness-order tests and `tests/test_cli_financial_cache.py`'s `--no-cache` test, specifically
   confirming they needed no behavioral edits — only the `enabled`→`use_cache` rename where
   applicable.
4. Manual smoke, one live-shaped call per strategy against a throwaway SQLite path: normal
   (cache-enabled) output unchanged; `--no-cache` still never creates the database file, for
   `graham-number` and `momentum`.
5. Final acceptance record (once implemented), per `IR_CONTRACT_AND_SLICE_PLAN.md` §4: which
   persisted-shape version fields changed (expected: none) and confirmation no Alembic migration was
   required.
