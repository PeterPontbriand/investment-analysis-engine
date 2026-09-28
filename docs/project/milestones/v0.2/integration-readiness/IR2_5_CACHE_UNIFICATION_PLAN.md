# IR.2.5 — Cache Unification: Implementation Plan

Planning record only. No source or test file has been changed by this document; it is written
against the codebase as it stands after IR.2.1–2.4 and IR.4, IR.7 (verified directly, file by
file, rather than trusted from the contract's original wording — the contract predates IR.2.1–2.4
and several of its call-site details have already moved).

Local sequence and status: [companion plan](IR_CONTRACT_AND_SLICE_PLAN.md#3-sequencing). Scope
origin: [§6, item 10](IR_CONTRACT_AND_SLICE_PLAN.md#6-ir2-implementation-inventory--approved-2026-09-24)
and [§6.9](IR_CONTRACT_AND_SLICE_PLAN.md#6-ir2-implementation-inventory--approved-2026-09-24).

## Open design choices

These need a decision before or during implementation; none has a single obviously-correct
answer. Recommendations are marked, but every one is a real choice, not a formality.

**D1 — Where does "lazy open" live: a new wrapper class, or inside the existing cache/client
classes?**

- **Option A (recommended): wrap outside, at the existing protocol boundary.** Add
  `LazyResolvedInputCache` (satisfies `ResolvedInputSeriesCacheProtocol`) and
  `LazyMarketDataProvider` (satisfies `MarketDataProvider`) as new, small classes. Composition
  functions build one of these instead of the real cache/client, and defer constructing the real
  thing until first `get`/`put`/`fetch_historical_data`. `SQLiteResolvedInputCache` and
  `CachedHistoricalDataClient` are untouched — their constructors, their own unit tests (42 direct
  constructions of `SQLiteResolvedInputCache` across 4 test files; 13 of `CachedHistoricalDataClient`
  in `tests/data/test_cached_client.py`), and every other caller keep working exactly as today.
- **Option B: make the existing classes lazy internally**, by changing
  `SQLiteResolvedInputCache.__init__`'s `database: SQLiteDatabase` and
  `CachedHistoricalDataClient.__init__`'s `repository: SQLiteMarketDataRepository` into
  factory-typed parameters (`Callable[[], ...]`), memoized on first real access. No new classes.
  But it changes two already-accepted, heavily-tested public constructors, and all 55 direct
  constructions above would need mechanical rewriting to pass a factory instead of a value — for no
  behavioral benefit over Option A.

Recommendation: **A**. It isolates the new behavior in its own small, independently testable
classes and leaves the existing, already-verified classes and their tests completely alone. The
cost is two new files' worth of tests and (for the historical side only) a parameter-type widening
at three call sites — see D2.

**D2 — Historical side: does `run_momentum` keep taking a `BaseDataClient`, or a `MarketDataProvider`?**

Under D1/Option A, the historical composition functions hand back a `LazyMarketDataProvider`
(satisfying `MarketDataProvider`), not a `BaseDataClient`. `run_momentum`
(`src/workspace/momentum_execution.py:65`) currently declares
`historical_client: BaseDataClient` and passes it to `MomentumAnalyzer(data_client=historical_client)`.
`MomentumAnalyzer.__init__` already accepts either `data_client: BaseDataClient | None` or
`market_data_provider: MarketDataProvider | None` (`momentum_analyzer.py:129-131`), so:

- **Option A (recommended):** widen `run_momentum`'s parameter to `MarketDataProvider` and call
  `MomentumAnalyzer(market_data_provider=historical_client)` instead. Three call sites move
  (`run_momentum`'s own signature; `src/cli.py`'s two `momentum` branches; `src/cli_workspace.py`'s
  `_execute_momentum`), all in this same slice, all already passing through a local variable, not a
  stored/persisted type.
- **Option B:** give `LazyMarketDataProvider` a `fetch_current_price` method too so it can also
  satisfy `BaseDataClient` structurally... except `BaseDataClient` is an `ABC`, not a `Protocol` —
  satisfying it means subclassing it, which reintroduces the abstract-method boilerplate this slice
  is trying to avoid, for a method Momentum's own path never calls (`_ClientProviderAdapter`, the
  thing Momentum actually consumes today, only ever exposes `provider_id`/`fetch_historical_data` —
  `momentum_analyzer.py:414-429` — never `fetch_current_price`).

Recommendation: **A**. Option B fights the type system to preserve a parameter name
(`data_client`) nothing downstream needs to keep.

**D3 — Naming.** `LazyResolvedInputCache` / `LazyMarketDataProvider` are working names, chosen to
read as "the lazy variant of the thing this composes," matching no existing naming collision. Not
load-bearing; change freely during review.

**D4 — Thread-safety of the memoized open.** Both lazy wrappers do a classic
"open on first access, remember the result" check. Today, every composition path
(`_production_financial_cache`, `_production_historical_client`) is entered fresh per CLI
invocation or per refresh job (`cli_workspace.py:766-772`'s `_execute_momentum` builds one per
ticker, not once for the whole batch) — no current caller shares one instance across concurrent
threads. The only long-lived, potentially-shared composition (`AnalysisToolDependencies` in
`src/evaluation/composition.py:197`) is evaluation-only and single-threaded today.
- **Option A (recommended): no lock.** Match actual current usage; add one later if a future
  daemon/long-lived orchestrator composition ever shares one instance across concurrent calls.
- **Option B: add a trivial lock now** (a few lines, e.g. guarding the check-and-set with
  `threading.Lock`) as defensive insurance against that future case.

Recommendation: **A**, but this is cheap enough that **B** is a reasonable, low-cost alternative if
the project owner would rather not rely on "no current caller shares this" as an implicit
invariant.

## 1. Context

**The problem (verified against the current code, not assumed from the contract):**

Graham and FCF have two independent, redundant cache controls today.
`_production_financial_cache(*, enabled: bool, clock: ...)` (`src/cli_support.py:59-79`) decides,
at composition time, whether to build a durable `SQLiteResolvedInputCache` (calling
`ensure_database_ready(database)` eagerly first) or a scratch `InMemoryResolvedInputCache` that
never opens SQLite at all. Separately, every resolver method in `src/data/financial/resolver.py`
takes its own per-call `use_cache: bool = True` (verified: lines 212, 235, 268, 338, 373, 434, 706,
728, 847, 1100, 1233) that independently gates each read/write against whichever cache object was
composed. Both controls are driven by the same six call sites' local `use_cache` value
(`src/cli.py:397,513,605`, `src/cli_workspace.py:796,822,848` — six confirmed, matching the
contract's count) — `_production_financial_cache(enabled=use_cache, ...)` immediately followed by
`resolver.resolve(..., use_cache=use_cache)` downstream.

Removing the `enabled` switch naively — always eagerly calling `ensure_database_ready(database)` at
composition time — would be a real regression, confirmed against
`tests/test_cli_financial_cache.py`'s `test_...--no-cache...` case (line ~189): today, `--no-cache`
mocks `SQLiteDatabase` to raise if constructed and asserts the database file never appears, because
`enabled=False` skips opening SQLite entirely. An eager "always wired" cache would make `--no-cache`
newly *fail* on a machine where storage is broken, when today it silently succeeds by never looking.

**The fix:** the cache is always wired at composition (same object reference every time — no more
in-memory substitute), but it opens storage lazily, on the first actual `get`/`put` call, not at
composition time. Since the resolver's existing `if use_cache: ...` gates already skip calling the
cache at all when `use_cache=False` (unchanged by this slice), a lazily-opening cache object means
`use_cache=False` still never touches storage — matching today's behavior exactly. The "always
wired" part is the object reference; the connection/readiness check is what becomes deferred.

Momentum gets the identical treatment for symmetry, even though it has no existing regression risk
today (verified: `_production_historical_client`, `src/cli_support.py:34-56`, has no `enabled`
parameter at all — Momentum's historical cache is unconditionally wired, with no bypass anywhere).
Unlike Graham/FCF, Momentum's cache-skip becomes a genuine **per-call** parameter from this slice
onward, never a composition-time enabled/disabled choice — closing the two-controls problem before
it can ever arise for Momentum, rather than creating it first and unifying it later (as happened
for Graham/FCF). This slice builds that mechanism only; every current caller still passes a fixed
`use_cache=True` for Momentum (verified: `src/orchestrator/analysis_tools.py:183-188`'s own comment,
and `src/workspace/requests.py:139-144`'s `MomentumSelection.to_analysis_context` docstring, both
say so explicitly) until IR.2.6 adds the real `--no-cache` CLI/`MomentumSelection`/
`MomentumToolArguments` surface.

**Relevant architecture (`ARCHITECTURE.md` §5, §8), and what does *not* change:**

- §5's three instants (`executed_at`, `as_of`, the analysis boundary) and the decision-clock rule
  (a required constructor parameter, no default, fed from `context.executed_at`) are unaffected.
  Both lazy wrappers accept and forward the *same* already-computed `clock: Callable[[], datetime]`
  the real classes take today — the clock is captured in a closure, never re-read, and the lazy
  wrappers themselves make no time-based decision (whether the real object has been built yet is a
  plain boolean, not a clock read), so they need no clock of their own and add no new decision
  clock to inventory.
- §8's repository table (`SQLiteResolvedInputCache`, `SQLiteMarketDataRepository`) is unchanged:
  this slice does not touch either repository class, only what composes them and when.
- Cache **keys** (`ResolvedInputCacheKey`, `MarketDataCacheKey`) are built entirely outside this
  slice's scope, by callers unaffected by it. Live-run cache-key stability
  (`tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_input_resolver.py`'s two tests
  around line 415/455, which construct `InMemoryResolvedInputCache` directly and never go through
  `_production_financial_cache`) is untouched by this slice — nothing here changes what a key
  contains or when two runs' keys agree or differ.

## 2. Approach

### 2.1 New: `src/data/financial/cache.py` — `LazyResolvedInputCache`

Add beside `InMemoryResolvedInputCache`. Satisfies `ResolvedInputSeriesCacheProtocol`
structurally (no inheritance needed — it is a `Protocol`).

```python
class LazyResolvedInputCache:
    def __init__(self, open_factory: Callable[[], ResolvedInputSeriesCacheProtocol]) -> None:
        self._open_factory = open_factory
        self._real: ResolvedInputSeriesCacheProtocol | None = None

    def _opened(self) -> ResolvedInputSeriesCacheProtocol:
        if self._real is None:
            self._real = self._open_factory()
        return self._real

    def get(self, key): return self._opened().get(key)
    def put(self, key, resolved_input): self._opened().put(key, resolved_input)
    def get_series(self, query): return self._opened().get_series(query)
```

### 2.2 New: `src/data/cached_client.py` — `LazyMarketDataProvider`

Add beside `CachedHistoricalDataClient`. Satisfies `MarketDataProvider` structurally. Takes the
*raw* provider separately from the open factory, so `provider_id` answers immediately without
triggering the lazy open (verified this is safe: `CachedHistoricalDataClient.provider_id` already
just delegates to `self._provider.provider_id`, `cached_client.py:78-81`, independent of the
repository).

```python
class LazyMarketDataProvider:
    def __init__(self, provider: MarketDataProvider, open_factory: Callable[[], CachedHistoricalDataClient]) -> None:
        self._provider = provider
        self._open_factory = open_factory
        self._real: CachedHistoricalDataClient | None = None

    @property
    def provider_id(self) -> str | None:
        return self._provider.provider_id

    def fetch_historical_data(self, ticker, start_date, end_date=None) -> HistoricalMarketData:
        if self._real is None:
            self._real = self._open_factory()
        return self._real.fetch_historical_data(ticker, start_date, end_date)
```

### 2.3 `src/cli_support.py` — `_production_financial_cache` and `_production_historical_client`

- `_production_financial_cache`: drop the `enabled: bool` parameter entirely (signature becomes
  `(*, clock: Callable[[], datetime])`). Build `database = SQLiteDatabase(settings)` eagerly as
  today (this remains cheap — `SQLiteDatabase.__init__` never connects, per its own docstring,
  `src/data/repositories/sqlite.py:25-26`); yield
  `LazyResolvedInputCache(open_factory=lambda: _open_financial_cache(database, clock))` where a new
  small module-level helper `_open_financial_cache` calls `ensure_database_ready(database)` then
  returns `SQLiteResolvedInputCache(database, ttl=..., clock=clock)`. Keep the `finally:
  database.close()` unconditional, exactly as today — closing an unopened lazy engine is safe, and
  `test_cache_scope_closes_on_error` (`tests/test_cli_financial_cache.py`) already depends on close
  happening even when nothing in the block touched the cache.
- `_production_historical_client`: same shape. Remove the eager `ensure_database_ready(database)`
  call from the function body; yield
  `LazyMarketDataProvider(provider, open_factory=lambda: _open_historical_client(database, provider, clock))`
  where `_open_historical_client` does today's `ensure_database_ready` +
  `SQLiteMarketDataRepository(database)` + `CachedHistoricalDataClient(...)` construction.
  Both new helpers are defined in `cli_support.py` itself (not imported pre-bound) so that
  `patch("src.cli_support.ensure_database_ready", ...)` and `patch("src.cli_support.SQLiteDatabase",
  ...)` — both used by existing tests — keep intercepting the real calls: a closure defined in this
  module resolves `ensure_database_ready`/`SQLiteDatabase` as module globals at call time, so a
  patch on the module attribute is visible to the closure regardless of when it fires.

### 2.4 `src/data/base_client.py`, `src/data/market_data.py` — thread `use_cache` through the fetch surface

- `BaseDataClient.fetch_data`, `fetch_data_with_context`, `fetch_historical_data`
  (`base_client.py:34,50,70`) each gain `use_cache: bool = True`.
- `MarketDataProvider.fetch_historical_data` (`market_data.py:44`, a `Protocol` method) gains the
  same parameter.

### 2.5 `src/data/cached_client.py` — `CachedHistoricalDataClient.fetch_data_with_context`

Read `use_cache`: when `False`, skip `self._repository.get(key)` (always fetch live) and skip
`self._repository.put(...)` (never write) — mirroring `resolver.py`'s existing
`if use_cache: ...` / `if use_cache and self._cache is not None: ...` shape conceptually (Momentum
has no per-field `ResolutionTrace` to update, so this is a coarser two-branch gate, not a literal
copy of that trace-emitting code).

### 2.6 `src/data/yfinance/client.py`, `src/evaluation/fixtures/market_data.py` — accept and ignore

`YFinanceClient.fetch_data`/`fetch_data_with_context` (`yfinance/client.py:67,101`) and
`FixtureMarketDataProvider.fetch_historical_data` / `FixtureDataClient.fetch_data`
(`evaluation/fixtures/market_data.py:46,65`) each gain `use_cache: bool = True` and ignore it —
none of them have a cache of their own to skip.

### 2.7 `src/analysis/strategy/momentum/momentum_analyzer.py`

- `_ClientProviderAdapter.fetch_historical_data` (lines 414-429): accept `use_cache: bool = True`
  and pass it through to `self._client.fetch_data_with_context(ticker, start_date, end_date,
  use_cache=use_cache)`.
- `MomentumInputResolver.resolve` (lines 327-352): gains `use_cache: bool = True`, passed to
  `self._provider.fetch_historical_data(ticker, start_date, use_cache=use_cache)`.
- `MomentumAnalyzer.run_analysis` (lines 152-168): passes `use_cache=context.use_cache` into
  `resolver.resolve(...)`. `AnalysisContext.use_cache` already exists (`base_analyzer.py:36`) and is
  already threaded to every caller — this slice just makes Momentum's resolver finally *read* it,
  where today it is accepted but silently dropped.

### 2.8 Call-site signature widening (D2)

- `run_momentum` (`src/workspace/momentum_execution.py:65-84`): `historical_client: BaseDataClient`
  → `historical_client: MarketDataProvider`; construct
  `MomentumAnalyzer(default_ticker=ticker, market_data_provider=historical_client)` instead of
  `data_client=historical_client`.
- `src/cli.py`'s two `momentum` command branches (lines 285, 302) and
  `src/cli_workspace.py:766-772`'s `_execute_momentum`: no change needed beyond what
  `_production_historical_client`'s new return type already provides — the `with ... as
  historical_client:` binding keeps working since `historical_client` is just passed straight
  through to `run_momentum`.

### 2.9 What this slice does **not** touch

No `--no-cache` CLI option, no `MomentumSelection.use_cache`/`MomentumToolArguments.use_cache`
field (IR.2.6). No change to any resolver's cache **key** construction. No change to
`SQLiteResolvedInputCache` or `CachedHistoricalDataClient`'s own constructors (D1/Option A). No
formula, classification, or calculation result change.

## 3. Test changes

**New:**
- `tests/data/financial/test_lazy_resolved_input_cache.py` (or alongside
  `tests/data/repositories/test_resolved_input_cache.py`): open factory is not called at
  construction; first `get`/`put`/`get_series` triggers it exactly once; a second call reuses the
  same opened instance (assert the factory mock's call count); a factory that raises propagates the
  real exception unchanged (so a `DatabaseReadinessError` still surfaces as itself, not wrapped).
- `tests/data/test_lazy_market_data_provider.py`: `provider_id` never triggers the factory; first
  `fetch_historical_data` triggers it exactly once; subsequent calls reuse it; factory-raised
  exceptions propagate unchanged.

**Changed — call-site signature only, behavior preserved:**
- `tests/test_cli_financial_cache.py`, `tests/test_cli_database_readiness.py`: every
  `_production_financial_cache(enabled=True, ...)` → `_production_financial_cache(clock=...)` (the
  `enabled=False` cases were already covered by dedicated `--no-cache` tests whose *assertions*
  don't change, only need confirming still pass — see below).
- Any `build_graham_resolver`/cache-composition test asserting the old `enabled=` keyword exists on
  `_production_financial_cache`'s signature (`tests/_cli_helpers.py` if it builds one directly) —
  update the same way.
- `tests/data/test_cached_client.py`, direct `SQLiteResolvedInputCache`/`SQLiteMarketDataRepository`
  constructions (42 + 13 sites): **unchanged** — D1/Option A means these classes' own constructors
  don't move.

**Changed — genuine behavior difference, needs a new assertion shape:**
- `tests/test_cli_database_readiness.py::test_optional_telemetry_failure_does_not_control_cache_readiness`
  (the `incompatible=True` branch, around line 150): today asserts
  `DatabaseReadinessError` is raised by *entering* `with _production_financial_cache(...)`. Under the
  lazy design, entering never raises — the error only surfaces on the first `get`/`put`. **This test
  must call an actual cache operation inside the `with` block** (e.g. `cache.get(a_key)`, or reuse
  whatever key-construction helper the surrounding test file already has) for the
  `pytest.raises(DatabaseReadinessError)` to still observe it. Flagged explicitly because this is
  the one existing test whose current shape actively assumes the eager behavior this slice removes.
- `tests/test_cli_financial_cache.py`'s `--no-cache` test (~line 165-179, asserting `SQLiteDatabase`
  is never constructed and the file never appears): **must keep passing unchanged** — confirms the
  design didn't regress the exact case this slice exists to protect. If it doesn't, the design is
  wrong, not the test.
- `tests/test_cli_database_readiness.py::test_typed_readiness_failure_preserves_envelope_and_closes_storage`
  and `::test_real_rejected_storage_precedes_provider_calls` (both parametrized over all four
  commands including `momentum`, no `--no-cache`): assert a readiness failure precedes every
  provider call. This still holds under the lazy design *only if* the cache's `get` is always
  attempted before the provider fallback — verified true today in both
  `src/data/financial/resolver.py` (cache lookup before `_resolve_provider`) and
  `CachedHistoricalDataClient.fetch_data_with_context` (`self._repository.get(key)` before
  `self._provider.fetch_historical_data(...)`, `cached_client.py:113-121`). No test change expected,
  but call out explicitly as the one thing this slice must not silently break — run these
  parametrized cases with extra attention during review, not just as part of the full suite.

**New coverage for the threaded parameter:**
- `tests/analysis/momentum/test_momentum_analyzer.py` /
  `tests/analysis/momentum/test_momentum_hardening.py`: assert `use_cache=False` reaches the
  provider's `fetch_historical_data` call (a fake/mock provider capturing the keyword it received),
  and `use_cache=True` (today's only real value) is unaffected.

## 4. Verification

1. `uv run ruff check --fix .` → `uv run ruff format .` → `uv run mypy --strict src tests`.
2. Full managed gate: `bash "$(git rev-parse --show-toplevel)/scripts/run-quality-gates.sh"` (per
   `AGENTS.md` §10 — this slice touches Python source and tests, no exemption applies).
3. Targeted attention beyond the blanket gate pass, per the flagged items above:
   - `tests/test_cli_financial_cache.py` and `tests/test_cli_database_readiness.py` in isolation,
     confirming the rewritten `incompatible=True` case and the unchanged `--no-cache` case both
     pass for the *reason* described above, not merely green.
   - The two live-run cache-key-stability tests in
     `tests/analysis/fcf_earnings_growth/test_fcf_earnings_growth_input_resolver.py` pass unchanged
     (confirms this slice truly didn't touch key construction).
4. Manual smoke, one live-shaped call per strategy against a throwaway SQLite path: confirm a
   normal (cache-enabled) run still returns identical output to pre-slice behavior, and
   `--no-cache` still never creates the database file, for at least `graham-number` and `momentum`.
5. Final acceptance record (once implemented), per `IR_CONTRACT_AND_SLICE_PLAN.md` §4: which
   persisted-shape version fields changed (expected: none — this slice touches no `Selection`/tool-
   argument schema) and confirmation no Alembic migration was required.
