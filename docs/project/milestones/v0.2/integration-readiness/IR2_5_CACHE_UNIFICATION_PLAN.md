# IR.2.5 — Cache Unification: Implementation Plan

Planning record only. No source or test file has been changed by this document; it is written
against the codebase as it stands after IR.2.1–2.4 and IR.4, IR.7 (verified directly, file by
file, rather than trusted from the contract's original wording). Revision 2: incorporates a
composition-time ordering fix found by explicitly tracing exception paths and call order (see §1
and the "Order-preservation fix" subsection) — the design in this revision changes today's
observable behavior less than revision 1 did.

Local sequence and status: [companion plan](IR_CONTRACT_AND_SLICE_PLAN.md#3-sequencing). Scope
origin: [§6, item 10](IR_CONTRACT_AND_SLICE_PLAN.md#6-ir2-implementation-inventory--approved-2026-09-24)
and [§6.9](IR_CONTRACT_AND_SLICE_PLAN.md#6-ir2-implementation-inventory--approved-2026-09-24).

## Decisions from review

- **D1 = A.** Wrap outside, at the existing protocol boundary: `LazyResolvedInputCache`
  (`ResolvedInputSeriesCacheProtocol`) and `LazyMarketDataProvider` (`MarketDataProvider`). Neither
  `SQLiteResolvedInputCache` nor `CachedHistoricalDataClient`'s own constructors change; none of
  their 55 combined direct-construction tests need touching.
- **D2 = A.** `run_momentum`'s `historical_client` parameter widens from `BaseDataClient` to
  `MarketDataProvider`; it constructs `MomentumAnalyzer(market_data_provider=historical_client)`
  instead of `data_client=historical_client`.
- **D3 = keep `Lazy*`.** Each wraps a real, still-in-use eager class (`SQLiteResolvedInputCache`,
  `CachedHistoricalDataClient`); the prefix distinguishes two real variants of the same capability,
  not a placeholder. Each wrapper's class docstring names the eager class it wraps and why both
  exist (the eager one for callers/tests that already have a ready database in hand and want it
  used immediately; the lazy one for composition that must not assume storage is ready or wanted).
- **D4 = B.** Add a lock. `refresh_watchlist`'s worker pool already shares the durable
  instrument-profile cache across concurrent jobs by contract (`CachedInstrumentProfileResolver`
  serializes its own per-ticker critical section); a cheap, consistent lock on the two new lazy
  wrappers matches that existing posture rather than relying on "no current caller happens to share
  one instance" as an implicit invariant.

## 1. Context

**The problem (verified against the current code):** Graham and FCF have two independent, redundant
cache controls today. `_production_financial_cache(*, enabled: bool, clock: ...)`
(`src/cli_support.py:59-79`) decides, at composition time, whether to build a durable
`SQLiteResolvedInputCache` (calling `ensure_database_ready(database)` eagerly first) or a scratch
`InMemoryResolvedInputCache` that never opens SQLite. Separately, every resolver method in
`src/data/financial/resolver.py` takes its own per-call `use_cache: bool = True` (verified at lines
212, 235, 268, 338, 373, 434, 706, 728, 847, 1100, 1233) that independently gates each read/write.
Both controls are driven by the same six call sites' local `use_cache` value (`src/cli.py:397,513,605`,
`src/cli_workspace.py:796,822,848`) — `_production_financial_cache(enabled=use_cache, ...)`
immediately followed by `resolver.resolve(..., use_cache=use_cache)` downstream. Momentum has no
control at all today: `_production_historical_client` (`cli_support.py:34-56`) unconditionally wires
and eagerly readiness-checks a durable historical cache, and `MomentumInputResolver.resolve`
(`momentum_analyzer.py:327-352`) never accepts a `use_cache` parameter to skip it.

**Order-preservation fix (found while tracing item 1/2's exception and call-order questions,
revision 2's actual design change):** a naive "always defer to first real `get`/`put`" lazy wrapper
would, for Graham Number/Growth and FCF Growth's *default* (non-`--save-run`) command path, let two
things run that today never run when storage is broken — `build_graham_resolver`'s unconditional
construction of the real SEC/Massive facts provider (`build_sec_production_provider()`), and
`compose_graham_profile`'s live SEC/Yahoo identity-provider call, which every one of
`execute_graham_number`/`execute_graham_growth`/`execute_fcf_growth` runs *before* `run_analysis`
(verified: Graham's calculation needs the composed profile as a required `AnalysisContext` field
upfront for applicability, unlike Momentum, which attaches its profile after calculation). Today,
neither runs when storage is broken, only because `_production_financial_cache.__enter__()` raises
before the `with` body ever starts. **Fix:** the composition functions take the caller's already-known
`use_cache` as a required parameter and eagerly trigger the lazy wrapper's open — call it `warm()` —
at composition time whenever `use_cache` is `True`. Every real caller today (direct commands,
`_maybe_save_run`, and each refresh job's own fresh per-job composition) already knows `use_cache`
before composing the cache, so this costs nothing and restores exact parity with today's eager
behavior for the common case, while `use_cache=False` still never touches storage (the wrapper is
built but `warm()` is never called, and the resolver's/`CachedHistoricalDataClient`'s own per-call
gate — unchanged — never calls `get`/`put` either). Momentum's `_production_historical_client` gets
the identical `use_cache`-gated `warm()` call for symmetry, even though tracing its call order
(§2 below) shows it isn't strictly required there — Momentum's cache access already precedes
instrument-profile composition in both its branches, and an explicit CLI comment
(`cli.py:276-279`) already documents this as an intended, project-wide invariant: *"Readiness is
checked before the historical-data provider call, matching every other command's 'preflight before
provider work' ordering."* This revision's design preserves that invariant for all four commands
instead of quietly breaking it for three of them.

**Net effect of this fix:** this slice is now a much more conservative refactor than revision 1
proposed. `_production_financial_cache`/`_production_historical_client` still raise
`DatabaseReadinessError` at `__enter__` time whenever `use_cache=True` (today's exact behavior,
verified against `tests/test_cli_database_readiness.py`'s parametrized readiness tests — see §3).
The change is: one flag (`use_cache`, not `enabled`) instead of two independently-settable ones; one
wired object type (`Lazy*`) in both branches instead of switching between
`InMemoryResolvedInputCache` and the real SQLite-backed class; and Momentum finally gets a real,
per-call `use_cache` gate all the way down, where before it silently had none.

**Relevant architecture (`ARCHITECTURE.md` §5, §8), and what does *not* change:** §5's three instants
and decision-clock rule are unaffected — both lazy wrappers accept and forward the same
already-computed `clock: Callable[[], datetime]` the real classes take today, captured in a closure,
never re-read; the wrappers make no time-based decision of their own (whether the real object exists
yet, or whether the remembered failure should be re-raised, are plain booleans, not clock reads), so
they need no clock and add nothing to the conformance inventory. §8's repository table
(`SQLiteResolvedInputCache`, `SQLiteMarketDataRepository`) is unchanged — this slice does not touch
either repository class. Cache **keys** (`ResolvedInputCacheKey`, `MarketDataCacheKey`) are built
entirely outside this slice's scope; live-run cache-key stability
(`tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_input_resolver.py`'s two tests, which
construct `InMemoryResolvedInputCache` directly and never go through `_production_financial_cache`)
is untouched.

## 2. Approach

### 2.1 New: `src/data/financial/cache.py` — `LazyResolvedInputCache`

Add beside `InMemoryResolvedInputCache`. Satisfies `ResolvedInputSeriesCacheProtocol` structurally.
Remembers a factory failure and re-raises the *same* exception object on every later call (item 4 —
not a retry: most `DatabaseReadinessError` reasons are structural, not transient, and a
`SQLiteResolvedInputCache.get()`/`.put()` may be called many times across one command's several
resolved fields, all of which must see the identical failure, not attempt the expensive check
again). Guarded by a `threading.Lock` (D4) since a future long-lived composition (or, defensively,
today's refresh worker pool) could in principle share one instance.

```python
class LazyResolvedInputCache:
    """Defers ``SQLiteResolvedInputCache``'s readiness check and construction.

    Wraps the same real ``SQLiteResolvedInputCache`` this project already uses; that class is
    unchanged and remains the right choice for a caller that already has a ready database and
    wants it used immediately (e.g. its own direct-construction unit tests). This wrapper exists
    for composition that must not assume storage is ready, or wanted, before the first real
    resolution needs it.
    """

    def __init__(self, open_factory: Callable[[], ResolvedInputSeriesCacheProtocol]) -> None:
        self._open_factory = open_factory
        self._real: ResolvedInputSeriesCacheProtocol | None = None
        self._failure: Exception | None = None
        self._lock = threading.Lock()

    def _opened(self) -> ResolvedInputSeriesCacheProtocol:
        if self._real is not None:
            return self._real
        if self._failure is not None:
            raise self._failure
        with self._lock:
            if self._real is None and self._failure is None:
                try:
                    self._real = self._open_factory()
                except Exception as exc:
                    self._failure = exc
                    raise
            elif self._failure is not None:
                raise self._failure
        assert self._real is not None
        return self._real

    def warm(self) -> None:
        """Force the deferred open now; a no-op once already opened or failed."""
        self._opened()

    def get(self, key): return self._opened().get(key)
    def put(self, key, resolved_input): self._opened().put(key, resolved_input)
    def get_series(self, query): return self._opened().get_series(query)
```

### 2.2 New: `src/data/cached_client.py` — `LazyMarketDataProvider`

Same shape, wrapping `CachedHistoricalDataClient`. Satisfies `MarketDataProvider` structurally.
Takes the *raw* provider separately from the open factory so `provider_id` answers immediately
without triggering the open (`CachedHistoricalDataClient.provider_id` already just delegates to
`self._provider.provider_id`, independent of the repository).

```python
class LazyMarketDataProvider:
    """Defers ``CachedHistoricalDataClient``'s readiness check and construction.

    Wraps the same real ``CachedHistoricalDataClient``; that class is unchanged. This wrapper lets
    composition decide, via ``warm()``, whether readiness is established now (matching every
    other command's preflight-before-provider-work ordering) or left for the first real fetch.
    """

    def __init__(self, provider: MarketDataProvider, open_factory: Callable[[], CachedHistoricalDataClient]) -> None:
        self._provider = provider
        self._open_factory = open_factory
        self._real: CachedHistoricalDataClient | None = None
        self._failure: Exception | None = None
        self._lock = threading.Lock()

    @property
    def provider_id(self) -> str | None:
        return self._provider.provider_id

    def _opened(self) -> CachedHistoricalDataClient:
        # Same remember-and-reraise, locked shape as LazyResolvedInputCache._opened.
        ...

    def warm(self) -> None:
        self._opened()

    def fetch_historical_data(self, ticker, start_date, end_date=None, *, use_cache: bool) -> HistoricalMarketData:
        return self._opened().fetch_historical_data(ticker, start_date, end_date, use_cache=use_cache)
```

### 2.3 `src/cli_support.py` — `_production_financial_cache` and `_production_historical_client`

Both gain a required keyword-only `use_cache: bool` parameter (replacing `enabled` on the financial
one; new on the historical one — every current Momentum caller passes a literal `True`, matching
`analysis_tools.py:183-188`'s existing "fixed until a later change" pattern).

```python
@contextmanager
def _production_financial_cache(*, use_cache: bool, clock: Callable[[], datetime]) -> Iterator[LazyResolvedInputCache]:
    database = SQLiteDatabase(settings)
    cache = LazyResolvedInputCache(open_factory=lambda: _open_financial_cache(database, clock))
    try:
        if use_cache:
            cache.warm()
        yield cache
    finally:
        database.close()

def _open_financial_cache(database: SQLiteDatabase, clock: Callable[[], datetime]) -> SQLiteResolvedInputCache:
    ensure_database_ready(database)
    seconds = settings.financial_cache_ttl_seconds
    return SQLiteResolvedInputCache(database, ttl=None if seconds is None else timedelta(seconds=seconds), clock=clock)
```

Symmetric shape for `_production_historical_client`/`_open_historical_client`. Both `_open_*` helpers
stay defined in `cli_support.py` itself (not imported pre-bound) so that
`patch("src.cli_support.ensure_database_ready", ...)` and `patch("src.cli_support.SQLiteDatabase",
...)` — both used by existing tests — keep intercepting the real calls: a closure defined in this
module resolves those names as module globals at call time, so a patch on the module attribute is
visible regardless of when the closure fires. The unconditional `finally: database.close()` is
unchanged and safe to call whether or not `warm()` ever ran (`SQLiteDatabase.__init__` never
connects, per its own docstring, and `test_cache_scope_closes_on_error` already depends on `close()`
running even when nothing touched the cache).

### 2.4 `src/data/base_client.py` — thread `use_cache` through, at the levels that need it

Only `BaseDataClient.fetch_data_with_context` and `fetch_historical_data` (`base_client.py:50,70`)
gain `use_cache: bool = True` (default kept — this is the general-purpose interface other, cache-
agnostic callers also use directly). **`fetch_data` itself is untouched** — corrected from revision
1, which incorrectly listed it: nothing in the call chain (`_ClientProviderAdapter` delegates to
`fetch_data_with_context`, never `fetch_data`) ever needs it there, and `FixtureDataClient`
(overrides only `fetch_data`) confirms no implementer needs to touch it.

### 2.5 `src/data/market_data.py` — `MarketDataProvider.fetch_historical_data`

Gains `use_cache: bool` as a **required, keyword-only** parameter (item 3) — no default. A default
here is exactly the shape of bug that let Momentum silently drop `context.use_cache` in the first
place; requiring it forces every implementer and every call site to make a conscious choice, and
`mypy --strict` catches any caller that forgets.

### 2.6 `src/data/cached_client.py` — `CachedHistoricalDataClient.fetch_data_with_context`

Also required, keyword-only, no default (item 3). When `False`: skip `self._repository.get(key)`
(always fetch live) and skip `self._repository.put(...)` (never write) — the same two-branch shape
`resolver.py`'s `if use_cache: ...` / `if use_cache and self._cache is not None: ...` already uses
conceptually (Momentum has no per-field `ResolutionTrace` to update here, so this is coarser, not a
literal copy). Because `BaseDataClient.fetch_historical_data`'s default implementation
(`base_client.py:70`) always explicitly forwards `use_cache=use_cache` to `fetch_data_with_context`
(never omits it), this override having no default of its own is safe — every caller that reaches it
through `fetch_historical_data` already supplies a real value.

### 2.7 `src/data/yfinance/client.py`, `src/evaluation/fixtures/market_data.py` — accept and ignore

`YFinanceClient.fetch_data_with_context` (`yfinance/client.py:101`) gains `use_cache: bool = True`
and ignores it (default kept — a raw provider with nothing of its own to skip).
`FixtureMarketDataProvider.fetch_historical_data` (`evaluation/fixtures/market_data.py:46`) — this
one **is required to change**, because it implements `MarketDataProvider` directly (not via
`BaseDataClient`) and is used as `market_data_provider=` in `src/evaluation/composition.py:158` and
`tests/orchestrator/test_analysis_tools.py:68` — gains `use_cache: bool = True` (default kept, so
`tests/evaluation/cases/test_momentum.py:41`'s existing bare call keeps working). `FixtureDataClient`
needs **no change** — it overrides only `fetch_data`, never `fetch_data_with_context`, so it
inherits `BaseDataClient`'s new default automatically.

### 2.8 `src/analysis/strategy/momentum/momentum_analyzer.py`

- `_ClientProviderAdapter.fetch_historical_data` (lines 414-429): required, keyword-only
  `use_cache: bool` (item 3), forwarded to `self._client.fetch_data_with_context(ticker, start_date,
  end_date, use_cache=use_cache)`.
- `MomentumInputResolver.resolve` (lines 327-352): required, keyword-only `use_cache: bool` (item 3),
  passed to `self._provider.fetch_historical_data(ticker, start_date, use_cache=use_cache)`.
- `MomentumAnalyzer.run_analysis` (lines 152-168): passes `use_cache=context.use_cache`.
  `AnalysisContext.use_cache` already exists (`base_analyzer.py:36`) and is already threaded to every
  caller — this slice makes Momentum's resolver finally *read* it, where today it is silently
  dropped.

### 2.9 Call-site signature widening (D2)

- `run_momentum` (`src/workspace/momentum_execution.py:65-84`): `historical_client: BaseDataClient` →
  `historical_client: MarketDataProvider`; constructs
  `MomentumAnalyzer(default_ticker=ticker, market_data_provider=historical_client)` instead of
  `data_client=historical_client`.
- `src/cli.py`'s two `momentum` branches (lines 285, 302) and `src/cli_workspace.py:766-772`'s
  `_execute_momentum`: no source change needed — `historical_client` is a local variable passed
  straight through; its static type comes from `_production_historical_client`'s new return type.

### 2.10 Item 3, extension not taken here: `resolver.py`'s own `use_cache: bool = True` defaults

Out of scope for this slice, listed as an option with its cost, not decided: `src/data/financial/
resolver.py`'s ~10 methods (`resolve`, `resolve_bvps`, `resolve_three_year_average_eps`, and others)
all default `use_cache` to `True`, unlike `src/analysis/shared/financial_resolution.py`'s functions,
which already require it with no default (`financial_resolution.py:81,133` — confirmed: this
consistency gap already exists independent of this slice). Extending "required, no default" to
`resolver.py` itself would complete that consistency, but its cost is real: every call site across
production *and* the test suite that currently omits `use_cache` (relying on the default) would need
an explicit value — a materially larger, more mechanical diff than this slice's four required
signatures, spanning resolver unit tests this slice otherwise never touches. Not recommended for
this slice specifically; worth a future pass once IR.2.6 or SWC needs to touch `resolver.py` anyway.

### 2.11 What this slice does **not** touch

No `--no-cache` CLI option, no `MomentumSelection.use_cache`/`MomentumToolArguments.use_cache` field
(IR.2.6). No change to any resolver's cache **key** construction. No change to
`SQLiteResolvedInputCache`, `CachedHistoricalDataClient`, or `resolver.py`'s own constructors/
defaults. No formula, classification, or calculation result change. `src/cli_composition.py`'s
`build_graham_resolver`'s `InMemoryResolvedInputCache(clock=clock)` fallback (item 6, used when no
`cache=` is passed) is **kept unchanged** — it is a wholly separate code path from
`_production_financial_cache`, has no readiness concept to defer (pure in-memory, always instantly
"ready"), and is deliberately exercised today by `tests/test_cli.py`'s two identity-focused unit
tests (`build_graham_resolver(..., data_provider=None, clock=...)`, no `cache=`) specifically to
avoid needing real SQLite for a test that isn't about caching at all.

## 3. Test changes

**New:**
- `tests/data/financial/test_lazy_resolved_input_cache.py`: `warm()`/first `get`/`put`/`get_series`
  triggers the factory exactly once; a second `warm()` or any later call reuses the same opened
  instance (factory mock's call count stays 1); a factory that raises is remembered and re-raised
  *unchanged* (same exception object, `isinstance`/`.reason` intact) on every subsequent call,
  without re-invoking the factory (item 4).
- `tests/data/test_lazy_market_data_provider.py`: same shape, plus `provider_id` never triggers the
  open.

**Changed — rename only, behavior preserved (revision 2's whole point):**
- `tests/test_cli_financial_cache.py`, `tests/test_cli_database_readiness.py`: every
  `_production_financial_cache(enabled=True, ...)` → `_production_financial_cache(use_cache=True,
  ...)`. `test_optional_telemetry_failure_does_not_control_cache_readiness`'s `incompatible=True`
  branch needs **no behavioral rewrite** — `warm()` still raises at `__enter__` time for
  `use_cache=True`, exactly matching what the test already asserts.
- Any test asserting `build_graham_resolver`'s no-clock construction, or `_production_financial_cache`'s
  old `enabled=` keyword (`tests/_cli_helpers.py` if it builds one directly): same rename.
- `tests/data/test_cached_client.py` (42+13 direct constructions of `SQLiteResolvedInputCache`/
  `CachedHistoricalDataClient`): **unchanged** (D1).
- `tests/test_cli_historical_cache.py:134,137`: these call `client.fetch_historical_data("ACME",
  "2025-01-01")` directly on what `_production_historical_client` yields — once that's a
  `LazyMarketDataProvider` requiring `use_cache`, both calls need `use_cache=True` added explicitly.

**Confirmed unaffected, verify during review rather than assume:**
- `tests/test_cli_database_readiness.py::test_typed_readiness_failure_preserves_envelope_and_closes_storage`
  and `::test_real_rejected_storage_precedes_provider_calls` (parametrized over all four commands,
  no `--no-cache`): with `use_cache=True` triggering `warm()` at composition, `ensure_database_ready`
  still raises before `build_graham_resolver`/`build_sec_production_provider`/
  `YFinanceClient.fetch_historical_data` are ever reached — same as today. This is the pair that
  revision 1's design would have broken; re-run them with extra attention, not just as part of the
  full suite.
- `tests/test_cli_financial_cache.py`'s `--no-cache` test (asserts `SQLiteDatabase` never
  constructed, file never appears): `use_cache=False` never calls `warm()`, and the resolver's own
  gate never calls `get`/`put` either — unchanged.

**Verified needing no change at all (checked, not assumed):**
- The five `_FixtureClient(FixtureDataClient)` subclasses across
  `tests/reporting/test_analysis_run_replay.py`, `tests/test_cli_workspace.py`,
  `tests/workspace/test_execution.py`, `tests/workspace/test_momentum_execution.py`,
  `tests/workspace/test_refresh.py` — none override `fetch_data_with_context`/`fetch_historical_data`
  (grepped the whole tree: only `BaseDataClient`, `CachedHistoricalDataClient`, and `YFinanceClient`
  override `fetch_data_with_context` anywhere), so they inherit the new default transparently, and
  they structurally satisfy `MarketDataProvider` for D2's widened `run_momentum` parameter without
  any change.
- `tests/analysis/momentum/test_momentum_analyzer.py` (4 `MomentumAnalyzer(data_client=...)`/`()`
  sites), `tests/analysis/test_base_analyzer_conformance.py:60`, `tests/test_cli_historical_cache.py:173`
  — all exercise `_ClientProviderAdapter` with plain `BaseDataClient` doubles that don't override
  `fetch_data_with_context`; unaffected by the required-`use_cache` change on
  `_ClientProviderAdapter.fetch_historical_data` itself, since that method's own body is what supplies
  the value downstream, not the caller of `MomentumAnalyzer`.

**New coverage for the threaded parameter:**
- Assert `use_cache=False` reaches the provider's `fetch_historical_data` call and skips repository
  `get`/`put` (a fake/mock provider or repository capturing the keyword/call count), in
  `tests/analysis/momentum/test_momentum_analyzer.py` or `test_momentum_hardening.py`.

## 4. Every caller of `run_momentum` and every implementer/caller of `MarketDataProvider.fetch_historical_data`

**`run_momentum` callers (item 5):**

| Caller | Change needed |
|---|---|
| `src/workspace/momentum_execution.py:65` (the function itself) | Yes — D2 signature + construction change |
| `src/cli.py:286,302` | No — passes `historical_client` straight through |
| `src/cli_workspace.py:772` | No — same |
| `tests/reporting/test_analysis_run_replay.py:82` | No (verified: fixture client structurally satisfies `MarketDataProvider`) |
| `tests/test_cli_workspace.py:465,529` | No |
| `tests/workspace/test_execution.py:75,223` | No |
| `tests/workspace/test_momentum_execution.py:71,84,97,103,151` | No |
| `tests/workspace/test_refresh.py:95,375` | No |

**`MarketDataProvider.fetch_historical_data` implementers:**

| Class | Change |
|---|---|
| `BaseDataClient.fetch_historical_data` (default impl, `base_client.py:70`) | Add `use_cache: bool = True`, forward to `fetch_data_with_context` |
| `CachedHistoricalDataClient` | Inherits the default above unchanged (does not override `fetch_historical_data` itself) |
| `YFinanceClient` | Inherits the default above unchanged (does not override `fetch_historical_data` itself) |
| `FixtureDataClient` | No change (same reason) |
| `_ClientProviderAdapter.fetch_historical_data` (`momentum_analyzer.py:425`) | Required, no default; forwards to `self._client.fetch_data_with_context(..., use_cache=use_cache)` |
| `FixtureMarketDataProvider.fetch_historical_data` (`evaluation/fixtures/market_data.py:46`) | Add `use_cache: bool = True` (implements the protocol directly, not via `BaseDataClient`) |
| New `LazyMarketDataProvider.fetch_historical_data` | Required, no default; forwards to the opened `CachedHistoricalDataClient` |

**Callers of `.fetch_historical_data(...)`:**

| Call site | Passes `use_cache`? |
|---|---|
| `MomentumInputResolver.resolve` → `self._provider.fetch_historical_data(...)` (`momentum_analyzer.py:339`) | Yes — becomes `use_cache=use_cache` (required, threaded from `run_analysis`) |
| `CachedHistoricalDataClient.fetch_data_with_context` → `self._provider.fetch_historical_data(...)` (`cached_client.py:101,121`) | **No** — this is the *wrapped raw provider* fetch on a cache miss/bypass; it never needed to know about outer caching intent, and doesn't gain the parameter |
| `tests/data/test_cached_client.py:169,280,281` (`client.fetch_historical_data("ABC", START)`, no `use_cache`) | No change — uses the new default |
| `tests/evaluation/cases/test_momentum.py:41` | No change — uses the new default |
| `tests/test_cli_historical_cache.py:134,137` | **Yes, needs `use_cache=True` added** — see §3 |

**Orchestrator handler and evaluation composition:** `src/orchestrator/analysis_tools.py:174-193`'s
`analyze_momentum` constructs `AnalysisContext(..., use_cache=True, ...)` directly (already
hardcoded, unaffected in shape — this slice makes the *value* finally reach the provider, not the
construction site). `src/evaluation/composition.py:155-158` passes `market_data_provider=
FixtureMarketDataProvider(...)` already (not `data_client=`), so it never goes through
`_ClientProviderAdapter` at all; only `FixtureMarketDataProvider` itself needs the accept-and-ignore
parameter (above).

## 5. Verification

1. `uv run ruff check --fix .` → `uv run ruff format .` → `uv run mypy --strict src tests`.
2. Full managed gate: `bash "$(git rev-parse --show-toplevel)/scripts/run-quality-gates.sh"`.
3. Targeted attention beyond the blanket pass:
   - `tests/test_cli_database_readiness.py`'s two parametrized "readiness precedes provider calls"
     tests, for the specific reason in §1/§3 — this is the one thing revision 1 would have silently
     broken.
   - `tests/test_cli_financial_cache.py`'s `--no-cache` test, confirming it needs no behavior change.
   - The two live-run cache-key-stability tests in
     `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_input_resolver.py`, confirming this
     slice still doesn't touch key construction.
   - New `LazyResolvedInputCache`/`LazyMarketDataProvider` tests specifically for the
     remember-and-reraise (not retry) contract (item 4).
4. Manual smoke, one live-shaped call per strategy against a throwaway SQLite path: a normal
   (cache-enabled) run returns identical output to pre-slice behavior; `--no-cache` still never
   creates the database file, for `graham-number` and `momentum`.
5. Final acceptance record (once implemented), per `IR_CONTRACT_AND_SLICE_PLAN.md` §4: which
   persisted-shape version fields changed (expected: none) and confirmation no Alembic migration was
   required.
