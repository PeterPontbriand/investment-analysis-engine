# IR.2.5 — Cache Unification: Implementation Plan

Revision 4 (final before implementation). Resolves the mypy/LSP conflict revision 3 left open and
unifies both composition functions to the same shape, per review. Sections below describe the
implementation as built.

Local sequence and status: [companion plan](IR_CONTRACT_AND_SLICE_PLAN.md#2-sequence-and-status). Scope
origin: [§6, item 10](IR2_ANALYZER_ENVELOPE_PLAN.md#6-ir2-implementation-inventory--approved-2026-09-24)
and [§6.9](IR2_ANALYZER_ENVELOPE_PLAN.md#6-ir2-implementation-inventory--approved-2026-09-24).

## Revision 4 decisions

**1. `BaseDataClient.fetch_data_with_context`/`fetch_historical_data` also become required,
keyword-only `use_cache: bool` (no default).** `CachedHistoricalDataClient` overrides
`fetch_data_with_context` to require the parameter; mypy --strict rejects an override that narrows an
optional base parameter to required, so the base must require it too. Every caller of
`BaseDataClient.fetch_data_with_context`/`fetch_historical_data`, found exhaustively (grepped both
method names across the whole tree, not just one):

| Caller | Kind | Change |
| :--- | :--- | :--- |
| `_ClientProviderAdapter.fetch_historical_data`/`fetch_data_with_context` (`momentum_analyzer.py:428-429`) | Momentum path | Already threads `use_cache` explicitly (§2.2) |
| `BaseDataClient.fetch_historical_data`'s own body calling `fetch_data_with_context` (`base_client.py:77`) | Interface-internal | Forwards `use_cache` explicitly |
| `CachedHistoricalDataClient.fetch_data`'s own body calling `fetch_data_with_context` (`cached_client.py:91`) | Class-internal | `fetch_data`'s own signature has no `use_cache` (untouched, §2.2) — hardcodes a literal `use_cache=True` when delegating, since this legacy no-cache-concept entry point has no caller preference to forward. Documented in the method's docstring. |
| `CachedHistoricalDataClient.fetch_data_with_context`'s two calls to `self._provider.fetch_historical_data(...)` (`cached_client.py:101,121`) | Class-internal | `self._provider: BaseDataClient` — now also required. These fetch the *wrapped raw provider* on a cache miss/bypass; its own caching stance is irrelevant, so both pass a literal `use_cache=True`. |
| `tests/data/test_yfinance_client.py:43,61` | Test | No change — calls the concrete `YFinanceClient` directly, which keeps its own `use_cache: bool = True` override |
| `tests/data/test_cached_client.py:169,171,280,281` | Test | Add `use_cache=True` — these call `CachedHistoricalDataClient` (inherits the now-required base default) |
| `tests/data/test_cached_client.py`'s local `FakeProvider(BaseDataClient)` overriding `fetch_historical_data` directly (`test_cached_client.py:137`) | Test-only implementer, found by re-grepping every `def fetch_historical_data` in the tree, not only `def fetch_data_with_context` (revision 3's search was incomplete) | Add `use_cache: bool = True`, ignored — it is the wrapped raw provider passed into `CachedHistoricalDataClient(provider=FakeProvider(), ...)`, called with a literal `True` per the row above |

No genuine cache-agnostic production caller exists outside the Momentum path — confirmed
exhaustively. `YFinanceClient` and the fixtures (`FixtureMarketDataProvider`, and now `FakeProvider`)
accept-and-ignore the parameter with their own concrete-class defaults, so every test that calls one
of *those* concretely, rather than through `BaseDataClient`, needs no change.

**2. Both composition functions unified to the same shape.** `_production_financial_cache` drops the
`InMemoryResolvedInputCache` early return entirely: it always constructs `SQLiteDatabase` and always
yields the real `SQLiteResolvedInputCache`, skipping only `ensure_database_ready` when
`use_cache=False` — identical shape to `_production_historical_client`. `tests/test_cli_financial_cache.py`'s
`--no-cache` test changes its mock target from `src.cli_support.SQLiteDatabase` to
`src.cli_support.ensure_database_ready`; its `assert not path.exists()` check — the real proof — is
unchanged. (`cli_composition.py`'s own `InMemoryResolvedInputCache(clock=clock)` default, used for
evaluation/identity-only tests with no `cache=` argument, is untouched — separate code path, no
readiness concept, decided already.)

**3. New test:** `_production_historical_client(use_cache=False, ...)` never calls
`ensure_database_ready`.

**4. Commit structure:** (a) composition + Momentum threading + required parameters, with their
tests; (b) the 117 mechanical `resolver.py` test edits alone; (c) the final acceptance record.

## 1. Context

Graham and FCF have two independent, redundant cache controls today.
`_production_financial_cache(*, enabled: bool, clock: ...)` (`src/cli_support.py:59-79`) decides, at
composition time, whether to build a durable `SQLiteResolvedInputCache` (eager
`ensure_database_ready`) or a scratch `InMemoryResolvedInputCache`. Separately, `resolver.py`'s own
methods take an independent per-call `use_cache: bool = True`. Both are driven by the same value at
all six call sites (`src/cli.py:397,513,605`, `src/cli_workspace.py:796,822,848`). Momentum has no
control at all today: `_production_historical_client` unconditionally wires and eagerly
readiness-checks the historical cache, and `MomentumInputResolver.resolve` never accepts a
`use_cache` parameter to skip it.

**Order-preservation (unchanged since the prior review):** `build_graham_resolver`'s unconditional
construction of the real financial-facts provider, and `compose_graham_profile`'s live SEC/Yahoo
identity-provider call — which every one of `execute_graham_number`/`execute_graham_growth`/
`execute_fcf_growth` runs *before* `run_analysis` — both currently never run when storage is broken,
only because `_production_financial_cache` raises before the `with` body starts. This still holds
under the unified shape: `ensure_database_ready` still raises immediately whenever `use_cache=True`,
before `build_graham_resolver` is ever reached — only *which mock* proves it changes (§ revision 4
decision 2), not the behavior itself. Momentum's own two command branches already call the historical
cache before instrument-profile composition either way (`cli.py:275-308`) — unaffected.

**Relevant architecture, unchanged:** `ARCHITECTURE.md` §5's three instants and decision-clock rule
are untouched. §8's repository table is untouched. Cache **keys** are built entirely outside this
slice's scope; live-run cache-key stability is untouched.

## 2. Approach

### 2.1 `src/cli_support.py` — `_production_financial_cache` and `_production_historical_client`

```python
@contextmanager
def _production_financial_cache(
    *, use_cache: bool, clock: Callable[[], datetime]
) -> Iterator[ResolvedInputSeriesCacheProtocol]:
    """Own one invocation's durable cache; schema upgrades remain explicit unless caching is disabled."""
    database = SQLiteDatabase(settings)
    try:
        if use_cache:
            ensure_database_ready(database)
        seconds = settings.financial_cache_ttl_seconds
        yield SQLiteResolvedInputCache(
            database, ttl=None if seconds is None else timedelta(seconds=seconds), clock=clock
        )
    finally:
        database.close()


@contextmanager
def _production_historical_client(
    provider: YFinanceClient, *, use_cache: bool, clock: Callable[[], datetime]
) -> Iterator[CachedHistoricalDataClient]:
    """Borrow the Yahoo client and own historical storage for one analysis unless caching is disabled."""
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

`InMemoryResolvedInputCache` is no longer imported/used by either function. Both remain defined
inline in `cli_support.py`, so `patch("src.cli_support.ensure_database_ready", ...)` /
`patch("src.cli_support.SQLiteDatabase", ...)` targets keep working unchanged.

Six call sites rename `enabled=` to `use_cache=` (`cli.py:397,513,605`,
`cli_workspace.py:796,822,848`); four call sites gain a literal `use_cache=True`
(`cli.py:285,302`, `cli_workspace.py:771`, plus `analysis_tools.py`'s momentum context stays
hardcoded `True` as already documented there).

### 2.2 Per-call `use_cache` threading

- `MarketDataProvider.fetch_historical_data` (`market_data.py:44`): required, keyword-only.
- `BaseDataClient.fetch_data_with_context`/`fetch_historical_data` (`base_client.py:50,70`): also
  required, keyword-only (revision 4 decision 1). `fetch_data` itself untouched.
- `CachedHistoricalDataClient.fetch_data_with_context` (`cached_client.py:93`): required,
  keyword-only. `False` skips `self._repository.get(key)`/`.put(...)`. Its own `fetch_data`
  (`cached_client.py:89-91`) and its two calls to `self._provider.fetch_historical_data(...)`
  (`cached_client.py:101,121`) each pass a literal `use_cache=True` — see the table in the revision 4
  decision above for why.
- `YFinanceClient.fetch_data_with_context` (`yfinance/client.py:101`): `use_cache: bool = True`,
  ignored.
- `FixtureMarketDataProvider.fetch_historical_data` (`evaluation/fixtures/market_data.py:46`):
  `use_cache: bool = True`, ignored.
- `_ClientProviderAdapter.fetch_historical_data` (`momentum_analyzer.py:414-429`): required,
  forwarded to `self._client.fetch_data_with_context(..., use_cache=use_cache)`.
- `MomentumInputResolver.resolve` (`momentum_analyzer.py:327-352`): required, passed to
  `self._provider.fetch_historical_data(ticker, start_date, use_cache=use_cache)`.
- `MomentumAnalyzer.run_analysis` (`momentum_analyzer.py:152-168`): passes
  `use_cache=context.use_cache`.
- `run_momentum` (`src/workspace/momentum_execution.py:65-84`): unchanged — parameter stays
  `historical_client: BaseDataClient`, construction stays `MomentumAnalyzer(data_client=
  historical_client)`.

### 2.3 `src/data/financial/resolver.py` — item 3

`resolve` (207), `_resolve` (230, private), `resolve_bvps` (333), `resolve_three_year_average_eps`
(369) drop their `= True` default (already keyword-only). Every production call site already passes
`use_cache=` explicitly — zero production changes. **120 test call sites total across 6 files; 3
already explicit; 117 need `use_cache=True` added** (76 of the 117 in `test_resolver.py` alone):

| File | `.resolve(` | `.resolve_bvps(` | `.resolve_three_year_average_eps(` |
| :--- | :--- | :--- | :--- |
| `tests/analysis/graham_value/test_fixture_provider.py` | 15 | 0 | 2 |
| `tests/analysis/graham_value/test_resolution_trace.py` | 5 | 1 | 0 |
| `tests/analysis/graham_value/test_resolver.py` | 46 (1 explicit) | 0 | 30 (1 explicit) |
| `tests/analysis/graham_value/test_production_providers.py` | 0 | 4 | 0 |
| `tests/analysis/graham_value/test_sec_bvps_hardening.py` | 0 | 3 | 0 |
| `tests/data/test_quote_freshness.py` | 14 (1 explicit) | 0 | 0 |

### 2.4 What this slice does **not** touch

No `--no-cache` CLI option, no `MomentumSelection.use_cache`/`MomentumToolArguments.use_cache` field
(IR.2.6). No change to any resolver's cache **key** construction. No change to
`SQLiteResolvedInputCache`, `SQLiteMarketDataRepository`, or `CachedHistoricalDataClient`'s own
constructors. No formula, classification, or calculation result change.

## 3. Test changes

**Behavior-preserving mock-target update:**
- `tests/test_cli_financial_cache.py`'s `--no-cache` test: mock `ensure_database_ready` instead of
  `SQLiteDatabase`; `assert not path.exists()` unchanged.

**No change:**
- `tests/test_cli_database_readiness.py`'s two parametrized "readiness precedes provider calls"
  tests — `ensure_database_ready` still raises at `__enter__` for `use_cache=True`, unaffected by
  which branch structure yields the cache.
- The five `_FixtureClient(FixtureDataClient)` subclasses.

**Rename only:** `_production_financial_cache(enabled=...)` → `(use_cache=...)` across
`tests/test_cli_financial_cache.py`, `tests/test_cli_database_readiness.py`, `tests/_cli_helpers.py`
(if applicable).

**New required parameter:**
- `tests/test_cli_historical_cache.py:133,136,144,158` (direct `_production_historical_client`
  calls): add `use_cache=True`.
- `tests/data/test_cached_client.py:169,171,280,281`: add `use_cache=True`.
- `tests/data/test_cached_client.py`'s `FakeProvider.fetch_historical_data`: add
  `use_cache: bool = True` to its signature (ignored).

**New:**
- `_production_historical_client(use_cache=False, ...)` never calls `ensure_database_ready` (mirrors
  the financial side's existing readiness-skip test).
- `use_cache=False` reaches the provider's `fetch_historical_data` call and skips repository
  `get`/`put`, in `tests/analysis/momentum/test_momentum_analyzer.py` or `test_momentum_hardening.py`.

**Mechanical, per §2.3:** 117 call sites across the 6 files in the table above.

## 4. Verification

1. `uv run ruff check --fix .` → `uv run ruff format .` → `uv run mypy --strict src tests`.
2. Full managed gate: `bash "$(git rev-parse --show-toplevel)/scripts/run-quality-gates.sh"`.
3. Manual smoke, one live-shaped call per strategy against a throwaway SQLite path: normal
   (cache-enabled) output unchanged; `--no-cache` still never creates the database file, for
   `graham-number` and `momentum`.
4. Final acceptance record: which persisted-shape version fields changed (expected: none) and
   confirmation no Alembic migration was required.

## 5. Final acceptance record

**Implemented as planned in §2**, across three commits: composition unification + Momentum
threading + required parameters with their own tests; the 117 mechanical `resolver.py` test edits
alone; this record.

**Gate:** `scripts/run-quality-gates.sh` passed clean — 3191 tests, 91% line coverage, `ruff check`/
`ruff format --check`/`mypy --strict` all clean on both `src` and `tests`.

**Manual smoke (live network, throwaway SQLite paths, cleaned up after):**
- `ian momentum KO` (cache enabled, no CLI flag exists for disabling it yet): identical output to
  pre-slice behavior; `analysis.sqlite3` and its readiness lock were created.
- `ian graham-number KO` (cache enabled): identical output to pre-slice behavior (same Graham
  Number, EPS, BVPS values as the `--no-cache` run below); `graham.sqlite3` and its readiness lock
  were created.
- `ian graham-number KO --no-cache`: succeeded with the same result values; **no database file was
  created** (directory listing empty afterward).
- `ian fcf-growth KO --no-cache`: succeeded (real FCF/EPS CAGR result, screen FAIL for KO on its
  own financial merits, not an error); **no database file was created**. Traced separately from
  Graham/Momentum because FCF's cache reaches the composed cache through a different path
  (`ProductionAnnualGrowthSeriesResolver.resolve` → `resolve_annual_growth_series` →
  `_resolve_field`'s own `if use_cache and cache is not None:` gate,
  `fcf_earnings_growth/input_resolver.py`) — confirmed this was always a genuine per-call gate, not
  a reliance on the removed `InMemoryResolvedInputCache` substitution, so removing that substitution
  could not have broken it. `test_no_cache_does_not_open_database` (parametrized over all three
  commands including `fcf-growth`) re-run in isolation: 3 passed.
- Momentum has no `--no-cache` CLI surface yet (IR.2.6), so its disabled-cache path was exercised
  directly at the composition-function level: `_production_historical_client(provider,
  use_cache=False, clock=...)` followed by a real `fetch_data_with_context(..., use_cache=False)`
  call against Yahoo Finance succeeded (39 rows returned) with **no database file created** —
  matching the new `test_disabled_cache_never_checks_readiness` unit test's assertion.

**Review fix folded into the composition/threading commit:**
`CachedHistoricalDataClient.fetch_data_with_context`'s three internal calls to
`self._provider.fetch_historical_data(...)` now forward the caller's own `use_cache` value instead
of a literal `True`. The wrapped raw provider still has nothing of its own to skip today, but an
outer caller's explicit "use no cache anywhere" must never be silently overridden by an inner layer,
including a future one — forwarding the real value closes that off structurally rather than by
convention. `fetch_data` (the legacy entry point with no `use_cache` parameter of its own) still
hardcodes `use_cache=True` when delegating internally, unchanged; checked for production callers of
`CachedHistoricalDataClient.fetch_data` specifically and found none — every call site reaches the
client through `fetch_data_with_context`/`fetch_historical_data` instead.

**Persisted-shape version fields changed:** none. No `Selection`/tool-argument/config schema
touched by this slice — `use_cache` was already a real field everywhere it's persisted
(`AnalysisContext.use_cache`, `GrahamNumberSelection.use_cache`, etc.); this slice only made the
*data-client* layer finally honor the value Momentum already carried and dropped.

**Alembic migration:** none required or added. No repository, schema, or table definition changed.

**Scope check against §2.4 ("what this slice does not touch"):** confirmed — no `--no-cache` CLI
option or `MomentumSelection.use_cache`/`MomentumToolArguments.use_cache` field was added (IR.2.6
still owns that); no cache key construction changed; no formula, classification, or calculation
result changed.
