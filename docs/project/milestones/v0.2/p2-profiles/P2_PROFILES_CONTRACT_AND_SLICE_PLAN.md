# P2-Profiles — Durable Instrument Profiles: Contract and Slice Plan

Defines the identity key, provider-precedence, freshness/invalidation, refresh,
and historical-snapshot rules for durable instrument profiles, and folds in the
Issue #33 `DataQualityError` hierarchy per
[IMPLEMENTATION_PLAN.md item 8](../IMPLEMENTATION_PLAN.md#47a-p2--durable-instrument-profiles--etf-aggregate-fcf-growth).

Work-package order and status: [milestone plan](../IMPLEMENTATION_PLAN.md#sequence-and-status).

**Status: Complete and accepted.** Gate A accepted 2026-09-21; Slices B–G
implemented and verified ([Slice D inventory](P2_PROFILES_SLICE_D_INVENTORY.md);
evidence in §13.6, §7.1, §14, and §15). **Final acceptance for the P2-Profiles
work package as a whole was granted 2026-09-22** — see §15.4.

## Sequence and status

| Order | Scope | Local gate |
| :--- | :--- | :--- |
| A | This contract: identity key, precedence, freshness/refresh, historical-snapshot design, `DataQualityError` hierarchy | Accepted 2026-09-21 |
| B | Durable schema, migration and repository for instrument profiles | Implemented and verified 2026-09-21 (§11) |
| C | Cache precedence, TTL/refresh and ticker-reuse behavior over the Gate B repository | Implemented and verified 2026-09-21 (§12) |
| D | Wire `CachedInstrumentProfileResolver` into every production instrument-profile composition site | Implemented and verified 2026-09-21 (§13.6). |
| E | `DataQualityError` hierarchy implementation (Issue #33) | Implemented and verified 2026-09-21 (§7 evidence) |
| F | Analysis Run historical-snapshot integration (Step 3.4 boundary) | Implemented and verified 2026-09-22 (§14) |
| G | Fixtures, documentation and final acceptance | Implemented and accepted 2026-09-22 (§15) |

## 1. Problem and decision

[`src/data/instrument_profile.py`](../../../../src/data/instrument_profile.py)
today only composes **request-scoped, live** identity and instrument-kind
evidence (`compose_instrument_profile`): every analysis re-resolves the same
descriptive/classification lookups from providers, with no persisted identity,
no cache key, and no freshness policy. Step 3.4's implementation outline
already anticipates the fix it needs: *"Persist the exact request-scoped
instrument-profile snapshot used during execution and replay it without
mutable metadata reads. P2-Profiles follows this step."* That snapshot
boundary cannot be built until the durable side — identity key, precedence,
freshness and ticker-reuse rules — is decided.

Separately, quality-decision failures are inconsistently typed across the
repository/data-quality boundary:

- [`src/data/quality.py:66`](../../../../src/data/quality.py) defines
  `HistoricalDataQualityError(DataFetchError)` — a genuine quality-rule
  rejection is raised as a *fetch* error.
- [`src/data/cached_client.py:103,124`](../../../../src/data/cached_client.py)
  raises bare `DataFetchError(error)` where `error` is itself a quality-decision
  reason string produced by `evaluate_historical_quality`/`evaluate_freshness`,
  not a provider/network failure.
- [`src/analysis/strategy/momentum/momentum_analyzer.py:198,333`](../../../../src/analysis/strategy/momentum/momentum_analyzer.py)
  raises `HistoricalDataQualityError` for the same reason, inheriting the same
  mis-based hierarchy.
- `src/data/financial/quality.py`'s `financial_quality_error` already returns a
  classified reason string that resolver call sites turn into
  `CalculationStatus.INPUT_UNAVAILABLE` results rather than exceptions — this
  path is **not** part of the defect; it is the pattern the exception hierarchy
  should not disturb.

An orchestrator cannot distinguish "the provider could not be reached" from
"the data was fetched but rejected on quality/freshness grounds" without
inspecting message text. Item 8 standardizes this under one
`DataQualityError` hierarchy, scoped to the two exception call sites above.

## 2. Identity key

Ticker alone is not a permanent identity (delisting/reuse, dual venues,
provider-specific suffixes). Proposed durable key design:

| Field | Source | Role |
| :--- | :--- | :--- |
| `profile_id` | Minted UUID4 at first durable resolution | Stable primary key; never recomputed from mutable evidence |
| `ticker` | Normalized, uppercased request ticker (existing `_normalized_required` convention) | Current lookup/display key; may point at a different `profile_id` after a supersession |
| `identity_anchor` | `SecurityIdentity.issuer_identifier` (e.g. SEC CIK), required for persistence | Durable cross-ticker anchor; the sole trigger for supersession detection |

**Decision (§9-4): only anchored profiles are durable.** A ticker whose
identity cannot be resolved to a provider-backed anchor is never written to
the durable table — it continues to resolve live on every request, exactly as
`compose_instrument_profile` does today. This avoids persisting, refreshing,
and TTL-tracking evidence that may never earn an anchor, and avoids ever
needing to compare "is this the same unanchored ticker" — a comparison with
no reliable answer. There is accordingly no `identity_confidence` column;
every durable row is, by construction, anchored.

Resolution rule: look up the current `profile_id` for `ticker`. If none
exists, attempt live resolution and persist only if an `identity_anchor`
resolves. If a fresh resolution's `identity_anchor` **matches** the stored
anchor, update the existing row in place. If it **disagrees**, this is a
ticker-reuse event: mint a new `profile_id`, mark the prior row
`superseded_at` with the disagreement reason, and repoint `ticker` at the new
row. A superseded row is retained, never deleted — historical Analysis Runs
may still reference it (§5).

`profile_id` — not `ticker` — is therefore the only value that may appear as a
foreign key from durable Analysis Run storage.

## 3. Provider precedence and disagreement

Reuse the ordering already established in `compose_instrument_profile`:
identity resolution stops at the first resolved candidate in caller-supplied
precedence order; instrument-kind resolution is attempted independently per
candidate. Extend this — unchanged — to the durable path:

- Persist each provider's **raw** evidence (`InstrumentKindEvidence`,
  `SecurityIdentity`) alongside the normalized consensus value actually
  adopted. Never overwrite raw evidence in place; a later disagreeing provider
  observation is appended, not substituted.
- Disagreement between two already-persisted providers on the *same* capability
  (e.g., yfinance says `ETF`, a later-reviewed provider says `EQUITY`) is
  recorded as an `InstrumentProfileDiagnostic`-shaped row and does not
  silently flip the adopted classification; precedence order (§2's table,
  extended per capability) decides, exactly as the in-memory composer does
  today.
- No new provider is added by this work package. Reviewed provider/value
  mappings (`reviewed_instrument_kind`) remain the only source of normalized
  classification; unreviewed values remain unclassified rather than guessed.

## 4. Freshness, TTL, invalidation and refresh

Reuse `FreshnessPolicy` / `evaluate_freshness` from `src/data/quality.py`
rather than building a second freshness engine. Proposed rules:

| Observed state | Required behavior |
| :--- | :--- |
| No stored profile for `ticker` | Resolve live; persist only if an `identity_anchor` resolves (§2, §9-4) — otherwise resolve live again next time |
| Stored profile within TTL | Reuse without a live provider call |
| Stored profile past TTL | Refresh live; apply §2's match/disagreement rule before persisting |
| `--no-cache` / explicit refresh request | Bypass reuse unconditionally, still apply §2 on write |
| Provider error on refresh, prior entry present | Fail open to the stale entry with an explicit staleness warning; never raise a hard failure solely because refresh could not reach a provider (mirrors the existing fail-open telemetry principle, applied here to non-critical descriptive metadata) |
| Provider error on refresh, no prior entry | Surface `InstrumentProfileResolutionStatus.PROVIDER_ERROR` / `UNAVAILABLE` exactly as the live composer does today; profile capability failures must never become `DataQualityError` (§7) — they are absence of evidence, not rejected evidence |

TTL is an explicit, named, documented default in typed configuration (not a
magic constant embedded in calculation bodies), consistent with AGENTS.md §3:
a new `instrument_profile_ttl_seconds: float | None` field alongside the
existing `historical_cache_ttl_seconds` (3,600s), `financial_cache_ttl_seconds`
(`None`, unbounded) and `quote_cache_ttl_seconds` (300s) in `src/config.py`.
**Decision (§9-1): default 2,592,000 seconds (30 days).** Rationale in §9.

## 5. Ticker reuse and historical-snapshot contract

Two distinct records must never be conflated:

1. **Current profile** (mutable, refreshable) — keyed by `profile_id`, looked
   up by `ticker`, subject to §4's TTL/refresh rules.
2. **Analysis Run profile snapshot** (immutable) — the exact identity/kind
   evidence, `profile_id`, and diagnostics actually used at execution time,
   persisted with the Analysis Run and never re-read from the mutable current
   table on replay.

A completed Analysis Run stores its snapshot inline (its `envelope_json`,
matching the pattern already used for other Analysis Run evidence in
`src/data/repositories/schema.py`) rather than a live foreign key to the
mutable profile row. This guarantees Step 3.4's replay purity requirement:
*"never relabel a historical run from mutable current metadata."* A
superseded `profile_id` (§2) therefore never invalidates or changes a
previously persisted Analysis Run's rendered identity, even though the
*current* profile for that ticker has moved on.

Reopening a ticker after supersession must show the investor which entity the
historical run described (the frozen snapshot) versus what the ticker
currently resolves to (the live profile) without conflating the two in a
single rendered view.

## 6. Repository and schema sketch

Modeled directly on the accepted `market_data_cache_entries` /
`market_price_observations` pattern in
[`src/data/repositories/schema.py`](../../../../src/data/repositories/schema.py):

- `instrument_profiles` — one row per `profile_id`: `ticker`, `identity_anchor`
  (required, non-null — §2's decision means every row is anchored), `cached_at`,
  `refreshed_at`, `superseded_at` (nullable), `superseded_reason` (nullable),
  `schema_version`, and a JSON evidence/diagnostics column (mirrors
  `analysis_runs.envelope_json`) rather than exploding every provider field
  into its own column.
- **Decision (§9-3): no separate alias table.** `ticker` is a plain,
  non-unique column on `instrument_profiles` with an ordinary btree index
  (`ix_instrument_profiles_ticker`) for lookup. **Correction found during
  Slice B implementation:** the partial unique index
  (`WHERE superseded_at IS NULL`) originally sketched here is not usable —
  `src/data/repositories/readiness.py` reflects and byte-compares every
  table's index DDL against `schema.py` at startup and explicitly rejects any
  index carrying `dialect_options` (which is exactly how SQLAlchemy surfaces a
  SQLite partial index) as "not interchangeable with this schema's indexes."
  Building one here would have broken the already-accepted Step 3.3A
  readiness contract. "At most one current row per ticker" is instead enforced
  entirely by `SQLiteInstrumentProfileRepository.put`, which reads the current
  row and writes its resolution (mint / update-in-place / supersede-and-mint)
  inside one transaction, so two overlapping refreshes cannot both observe "no
  current row" and mint competing profiles. Revisit only if a real ticker-reuse
  case demands querying the full alias history more efficiently than
  `ticker = ? AND superseded_at IS NULL`.
- Alembic migration `0004_instrument_profiles.py`, following the existing
  numbered-revision convention in `alembic/versions/`. No changes to
  `analysis_runs`, `watchlists`, or other existing tables were required; the
  Analysis Run snapshot (§5) is left for Slice F to carry in the existing
  `envelope_json` column.

Implemented in Slice B:
[`src/data/repositories/schema.py`](../../../../src/data/repositories/schema.py)
(`instrument_profiles` table),
[`alembic/versions/0004_instrument_profiles.py`](../../../../alembic/versions/0004_instrument_profiles.py),
and
[`src/data/repositories/instrument_profiles.py`](../../../../src/data/repositories/instrument_profiles.py)
(`SQLiteInstrumentProfileRepository`, `InstrumentProfileRecord`).

## 7. `DataQualityError` hierarchy (Issue #33 / item 8)

**Decision (§9-2): `src/data/quality.py`, not a new `src/data/errors.py`.**
This work adds exactly one new class over two call sites; a dedicated module
is unwarranted absent an expected increase in the number of data-quality
error types. Revisit only if a later work package demonstrably grows this
family beyond `quality.py`'s existing scope.

Hierarchy, added to `src/data/quality.py` where `HistoricalDataQualityError`
already lives:

```
DataFetchError(ValueError)        # unchanged: provider/network/absence failures
DataQualityError(ValueError)      # new: evidence was retrieved but rejected
└── HistoricalDataQualityError    # re-based from DataFetchError; unchanged fields/message
```

Changes are limited to the two call sites identified in §1:

- `src/data/cached_client.py:103,124` — replace `raise DataFetchError(error)`
  with a typed `DataQualityError` carrying the originating `QualityDecision`
  tuple (matching `HistoricalDataQualityError`'s existing shape), since
  `error` here is always a quality-decision reason, never a provider-call
  failure. The surrounding `fetch_historical_data` call itself continues to
  raise/propagate provider errors unchanged.
- `src/data/quality.py:66` — re-base `HistoricalDataQualityError` onto
  `DataQualityError` instead of `DataFetchError`.

`DataQualityError` remains a `ValueError` subclass, so existing bare
`except ValueError` handling continues to catch it — this is an additive
narrowing, not a breaking change to control flow. Every test that currently
asserts `pytest.raises(DataFetchError)` around a quality-rejection path (the
Momentum analyzer and `CachedHistoricalDataClient` quality-failure tests) must
be updated to assert `DataQualityError`/`HistoricalDataQualityError`; tests
asserting genuine fetch failures are unaffected. `financial_quality_error`
and its `CalculationStatus.INPUT_UNAVAILABLE` resolver path (§1) are
explicitly out of scope — they are not exceptions today and this work does not
turn them into one.

### 7.1 Evidence (2026-09-21)

Implemented exactly the hierarchy above: `DataQualityError(ValueError)` added
to `src/data/quality.py`; `HistoricalDataQualityError` re-based onto it
(`class HistoricalDataQualityError(DataQualityError)`); the now-unused
`DataFetchError` import removed from that module. `cached_client.py`'s two
call sites raise `DataQualityError(error)` — a plain string-reason
construction, not a reconstructed `QualityDecision` tuple, because both sites
are provably unreachable dead code: `_quality_error(data, input_id)` is
always called there with `cached_at=None`, and for `cached_at=None` it
*already* raises `HistoricalDataQualityError` internally the moment any
decision fails, before the caller's own `if error is not None: raise ...`
check can ever see a non-`None` value. The fix is still correct and required
(the branch's exception type was wrong even though unreachable), but
literally duplicating `HistoricalDataQualityError`'s constructor shape for a
value that can never be raised would mean fabricating evidence that was
never produced; the plain string form is preserved instead. Momentum's own
`HistoricalDataQualityError(decisions, df)` raises (`momentum_analyzer.py:198,333`)
needed no code change at all — only their already-correct class's base
changed underneath them.

**Verified before touching anything, not assumed:** `cli_support.py`'s
`execution_errors` classifies failures by a chain of `isinstance` checks, and
`elif isinstance(exc, HistoricalDataQualityError):` is matched *before* the
`DataFetchError` branch — a concrete-type check, independent of which class
`HistoricalDataQualityError` inherits from. The CLI's user-facing error
classification (`code = "historical_quality"` vs `"provider_error"`) is
therefore completely unaffected by the re-basing; only code that specifically
relied on catching a quality rejection via a bare `except DataFetchError`
would change behavior, and a full search of the production tree found
exactly one such catch site (`src/data/yfinance/financial_facts.py`), which
handles a fundamentals-fetch failure unrelated to historical quality
evaluation and was confirmed unaffected.

**Tests updated**, all in `tests/data/test_cached_client.py`: two tests
asserting `pytest.raises(DataFetchError, match=...)` around what is actually
a quality rejection now assert `HistoricalDataQualityError`
(`test_bypass_enforces_quality_even_with_broken_observer`,
`test_failed_quality_refresh_never_replaces_stored_snapshot`). The
parametrized `test_failed_refresh_preserves_prior_snapshot` covers *both*
kinds in one test (`"provider"` is a genuine `DataFetchError`; the other five
cases are quality rejections), so it now asserts a per-case expected type
instead of one shared exception class. Every other `pytest.raises(DataFetchError)`
site found repository-wide (`test_cli_historical_cache.py`,
`test_momentum_analyzer.py`, `test_fixture_client.py`, `test_yfinance_client.py`)
was individually confirmed to test a genuine provider-level failure — the
provider itself raises `DataFetchError` directly, before any quality
evaluation runs — and needed no change.

**New direct test**: `tests/data/test_quality.py::test_data_quality_error_is_distinct_from_data_fetch_error`
asserts the hierarchy shape itself (`DataQualityError` is a `ValueError`;
`HistoricalDataQualityError` is a `DataQualityError`; neither direction
between `DataQualityError` and `DataFetchError` is a subclass relationship).

Verification: full managed quality gate passes — `ruff check`/`format --check`
clean, `mypy --strict` over 296 source files, 3,121 tests passing, 91%
aggregate coverage.

## 8. Non-goals

Inherited from IMPLEMENTATION_PLAN.md's P2 non-goals (no ETF holdings
ingestion/aggregation, no LLM-based aggregation, no coupling of strategy
calculators directly to SQLite), plus, specific to this contract:

- No new generic provider-registry/plugin framework; §3 reuses the existing
  ordered-candidate pattern.
- No cross-provider entity-resolution service beyond the two already-approved
  providers (yfinance, SEC EDGAR).
- No schema change to `analysis_runs`, `watchlists`, or other existing tables
  unless Gate A review concludes the `envelope_json` sketch in §6 is
  insufficient.
- No change to `financial_quality_error`'s resolver-side status-based pattern.

## 9. Gate A decisions (resolved 2026-09-21)

1. **Default freshness TTL: 2,592,000 seconds (30 days).** Instrument
   identity/classification metadata (equity-vs-ETF kind, issuer name, venue)
   changes far less often than the quantities the codebase already assigns a
   TTL to — `quote_cache_ttl_seconds` (300s) and `historical_cache_ttl_seconds`
   (3,600s) track genuinely time-sensitive market data, while
   `financial_cache_ttl_seconds` (`None`) leaves fundamentals unbounded because
   their own fiscal-period/`available_at` fields already gate re-use (§1's
   `financial_quality_error` path). Instrument profiles have neither
   characteristic: they rarely change, but — unlike fundamentals — carry no
   natural period boundary that would force a re-check. An unbounded TTL would
   let a stale classification (or an anchor mismatch that should have
   triggered supersession, §2) persist indefinitely with nothing to surface
   it; a short TTL close to the price/quote end would defeat item 1's stated
   goal of *replacing* repeated live lookups. 30 days sits deliberately
   between those two poles: long enough that durable profiles do their job,
   short enough that a real-world change surfaces within one typical
   monthly-cadence review rather than never. Revisit with evidence if 30 days
   proves too short or too long in practice; it is a named config default, not
   a magic constant, so revision is a one-line change.
2. `DataQualityError` lives in `src/data/quality.py` (§7); no new
   `src/data/errors.py`. No material growth in data-quality error types is
   expected, so a dedicated module would be premature structure.
3. No `instrument_profile_identifiers` alias table (§6). Current-ticker lookup
   uses a plain index plus a repository-enforced invariant instead of a
   partial unique index — see §6's correction, found during Slice B, that a
   partial index is incompatible with the accepted Step 3.3A readiness
   contract. Add the alias table later only if a real ticker-reuse case
   demonstrates this approach is insufficient.
4. Only anchored (identity-verified) profiles are persisted (§2, §4). A ticker
   that never resolves an `identity_anchor` keeps resolving live on every
   request, unchanged from `compose_instrument_profile`'s current behavior —
   no unverified row, no TTL plumbing, no supersession bookkeeping for
   evidence with no reliable basis for comparison.

## 10. Draft acceptance matrix (finalized at Gate A)

| Area | Required proof |
| :--- | :--- |
| Identity key | Deterministic tests: first resolution mints a profile; matching-anchor re-resolution updates in place; disagreeing-anchor re-resolution supersedes and mints a new `profile_id`; superseded rows are never deleted. |
| Precedence | Deterministic tests reusing `InstrumentProfileCandidate` ordering fixtures; disagreement between two providers never silently overwrites raw evidence. |
| Freshness/refresh | Within/past-TTL reuse and refresh paths; `--no-cache` bypass; fail-open-to-stale on provider error with prior entry; hard failure only when no prior entry exists. |
| Historical snapshot | An Analysis Run's rendered identity is provably unaffected by a later supersession of the same ticker's current profile; replay reads only the persisted snapshot, never the mutable table. |
| `DataQualityError` | `cached_client` and the Momentum analyzer raise `DataQualityError`/`HistoricalDataQualityError` for quality rejections and `DataFetchError` only for genuine fetch failures; updated tests assert the corrected type; `financial_quality_error` resolver behavior is unchanged. |
| Production wiring | Every enumerated production instrument-profile composition site (§13) either resolves through `CachedInstrumentProfileResolver` or is explicitly, reviewably classified as intentionally database-free; a repeated CLI/refresh invocation for the same ticker within TTL does not re-call the identity/kind providers; presented profile fields, provenance and applicability are unchanged for every caller. |
| Regression | Full managed quality gate (Ruff, `mypy --strict`, pytest ≥85% coverage) passes; existing Momentum/Graham/FCF/Step-3.4 behavior and persisted-data contracts are unchanged. |

Use the managed non-mutating quality-gate wrapper for every implementation
gate, per AGENTS.md §10:

```powershell
& (Join-Path (git rev-parse --show-toplevel) 'scripts/run-quality-gates.ps1')
```

```bash
bash "$(git rev-parse --show-toplevel)/scripts/run-quality-gates.sh"
```

Gate A's four open questions are resolved (§9) and the contract is accepted
in full.

## 11. Slice B evidence (2026-09-21)

Gate A was accepted in full and Slice B authorized. Implemented: the
`instrument_profiles` table in `src/data/repositories/schema.py`, migration
`alembic/versions/0004_instrument_profiles.py`, and
`SQLiteInstrumentProfileRepository` in
`src/data/repositories/instrument_profiles.py` (get / get_by_id / put, with
put implementing §2's mint / update-in-place / supersede-and-mint resolution
atomically). The partial-unique-index sketch in §6 was corrected during
implementation — see §6 — after discovering it would have broken the accepted
Step 3.3A readiness contract; no other Gate A decision changed.

Added/updated tests: `tests/data/repositories/test_instrument_profiles.py`
(minting, in-place refresh preserving `cached_at`, disagreeing-anchor
supersession, retained superseded rows, blank-input and naive-clock rejection,
and reopen-preserves-state); `tests/data/repositories/test_schema.py` (new
table's column inventory, check-constraint rejections, and index presence);
and hard-coded head-revision assertions updated from `0003_watchlist_entries`
to `0004_instrument_profiles` in `tests/data/repositories/test_migrations.py`,
`tests/data/repositories/test_readiness.py`, and `tests/test_cli_database.py`.

Verification: the managed non-mutating quality-gate wrapper
(`scripts/run-quality-gates.ps1`) passes end-to-end — `ruff check .`,
`ruff format --check .`, `mypy --strict` (294 source files), and the full
suite (3,109 tests, 91% aggregate coverage; project target ≥85%), with
`src/data/repositories/instrument_profiles.py` itself at 98% (one uncovered
defensive branch, consistent with equivalent unreachable-guard branches in
sibling repository modules). An unrelated pre-existing environment defect —
this machine's `.venv/Scripts/mypy.exe`/`pytest.exe` launcher shims failing
with "uv trampoline failed to canonicalize script path" — was found during
this slice and fixed by reinstalling the virtual environment from `uv.lock`
(`uv sync --locked` after removing `.venv`); no dependency versions changed.

## 12. Slice C evidence (2026-09-21)

Implemented `CachedInstrumentProfileResolver` in
`src/data/instrument_profile_cache.py`, layered over the Gate B repository and
`compose_instrument_profile` unchanged (§3: precedence stays entirely owned by
the composer). `resolve()` mirrors `compose_instrument_profile`'s
identity/kind-candidate signature plus `force_refresh`, and implements §4's
observed-state table exactly: fresh reuse skips the live call; a stale or
missing entry refreshes live and applies §2's mint/update/supersede rule via
`repository.put` when an anchor resolves; a refresh that yields no anchor
never writes, and falls open to the last durable entry (with an explicit
`InstrumentProfileCapability.CACHE` diagnostic) when one exists, or returns
the live (evidence-absent) profile unchanged when it does not.

Two small additive changes to existing shared modules were required and are
narrow enough to fold into this slice rather than requesting a separate
authorization: `src/config.py` gained `instrument_profile_ttl_seconds`
(default `2_592_000`, the §9-1 decision) alongside the three existing cache-TTL
fields; `src/data/instrument_profile.py`'s `InstrumentProfileCapability` enum
gained a `CACHE` member so the resolver's provenance diagnostics reuse the
existing diagnostic shape instead of inventing a parallel one. Neither change
alters any existing behavior, call site, or serialized value.

The evidence codec (`_encode_profile`/`_decode_profile`) persists exactly what
`compose_instrument_profile` returns (identity, kind evidence, diagnostics)
and deliberately excludes security-unit evidence, which is completed by a
later, separate step (`complete_security_unit_profile`) after a profile is
obtained regardless of whether it came from cache or a live call.

Tests: `tests/data/test_instrument_profile_cache.py` covers first-resolution
persistence, fresh reuse without a provider call, TTL-expiry-triggered
refresh-in-place (`cached_at` preserved, `refreshed_at` advanced), disagreeing-
anchor supersession, never-persisting an unanchored ticker, fail-open reuse of
a stale entry on refresh failure (with the CACHE diagnostic and an untouched
durable record), `current_record`'s no-live-call read, and naive-clock
rejection. Full managed quality gate: `ruff check`/`format --check` clean,
`mypy --strict` over 296 source files, 3,118 tests passing, 91% aggregate
coverage.

**Not in this slice:** `compose_instrument_profile` is still called directly
(uncached) from every production site. Building the cache primitive without
wiring it into production would leave the milestone's stated goal ("replace
repeated live descriptive/classification lookups with durable, time-aware
instrument profiles") unmet in practice, so this is not optional polish left
to a future convenience pass — it is required for P2-Profiles acceptance.
Section 13 formalizes it as Slice D, and
[IMPLEMENTATION_PLAN.md's P2-Profiles acceptance criteria](../IMPLEMENTATION_PLAN.md#47a-p2--durable-instrument-profiles--etf-aggregate-fcf-growth)
were updated accordingly on 2026-09-21.

## 13. Slice D — Wire the durable cache into production instrument-profile composition

**Status: not started; scoped for review.** Added 2026-09-21 after Slice C's
evidence (§12) surfaced that the cache primitive alone does not achieve
IMPLEMENTATION_PLAN.md's stated P2-Profiles goal until production call sites
actually use it.

### 13.1 Consumer audit — complete

The required reconnaissance (§13.2) is done; its full findings, discovery
commands, and per-site evidence live in the companion
[Slice D inventory](P2_PROFILES_SLICE_D_INVENTORY.md), which is now this
section's source of truth rather than duplicated here. Headline correction
from the draft version of this table: the literal four
`compose_instrument_profile`/`compose_graham_profile` call sites collapse into
two architectural patterns (Momentum's three duplicated inline sites; one
shared Graham/FCF helper reached from six execution paths), and the original
claim that watchlist refresh "already holds a database for the whole
command's lifetime" was **wrong in the particular that matters**: the
refresh job executor deliberately does not receive that database, by
documented concurrency-safety design, not by oversight (inventory §3, §7.2).

### 13.2 Required first activity: a complete consumer audit — done 2026-09-21

Completed as the [Slice D inventory](P2_PROFILES_SLICE_D_INVENTORY.md):
every `InstrumentProfile` composition/consumption path, database availability
per site (confirmed by reading each call chain, not inferred), existing test
patch targets, and the out-of-scope orchestrator/evaluation seam
(`AnalysisToolDependencies.profile_resolver`, unused by any production caller
pending Step 3.6).

### 13.3 Design questions for review before implementation

1. **Resolved 2026-09-21:** the database-free Momentum direct-command path
   (`cli.py:295`) stays live-only; no database is opened purely to consult or
   populate the durable cache there. This contract's non-goal list already
   forbade forcing database creation for genuinely storage-free operations
   (§8, inherited from Step 3.3A); this confirms that principle applies here.
2. **Resolved 2026-09-21: (a) — wire it through**, with a proof of
   concurrency safety, not an assumption of it. Rationale: a watchlist exists
   specifically for repeated, recurring use over time, so the same ticker is
   more likely to be refreshed repeatedly across a 30-day TTL window there
   than through a one-off single-command invocation — the caching benefit is
   larger where the risk (concurrent worker threads) also lives, not smaller.
   Investigation while resolving this (§13.6) found that `refresh_watchlist`'s
   own public `executor` type does not need to change at all: a resolver can
   be built once in `cli_workspace.py`'s `refresh` command and closed over by
   the `executor` callable, so `src/workspace/refresh.py` is untouched. It
   also found a real, previously-undetected race — two concurrent `put()`
   calls for the same never-before-seen ticker could both observe "no current
   row" and mint two competing current rows, since dropping the partial-index
   approach (§6) removed the only mechanism that would have caught this at
   the database level. §13.6 records the fix.

### 13.4 Scope and non-goals

**In scope:** wiring `CachedInstrumentProfileResolver.resolve()` in place of
`compose_instrument_profile()` at every site classified as database-available
per §13.3; threading a `SQLiteInstrumentProfileRepository`/database dependency
through the CLI/workspace composition layers to the sites that need it;
deterministic tests proving no behavioral change to presented profile fields,
provenance, or applicability, and proving repeated calls within TTL stop
re-invoking identity/kind providers.

**Non-goals:** deduplicating the three Momentum call sites into a shared
helper (a reasonable follow-on, not required here); changing provider
precedence, identity/kind semantics, or Analysis Run persisted evidence
shape (Slice F); forcing database creation for a call site classified
database-free per §13.3; any change to `graham_shared.py`'s public
`compose_graham_profile` signature beyond what threading a resolver requires.

### 13.5 Acceptance criteria

- The inventory (§13.2) is complete and reviewed before any production file
  is edited.
- Every enumerated call site is either wired to `CachedInstrumentProfileResolver`
  or explicitly classified database-free with a recorded reason (§13.3);
  no site is left in an unreviewed, inconsistent state.
- Deterministic tests prove: a second invocation for the same ticker within
  TTL, through each wired site, does not re-call the identity/kind providers;
  a disagreeing-anchor re-resolution still supersedes correctly when reached
  through production wiring, not just through direct repository/cache tests;
  presented CLI/refresh output (concise, details, diagnostics, JSON) is
  byte-for-byte unchanged for callers, since `resolve()` is a drop-in return
  shape for `compose_instrument_profile()`.
- Full managed quality gate passes; existing Momentum/Graham/FCF/Step-3.4
  behavioral and persisted-data-contract regressions are covered.

### 13.6 Slice D evidence (2026-09-21)

Fork §13.3-2 resolved as **(a) wire it through**: a watchlist exists for
repeated, recurring use, so the same ticker is more likely to be refreshed
repeatedly across the 30-day TTL there than through a one-off command — the
caching benefit is larger exactly where the concurrency risk lives.

**Wired, per the inventory's classification:**

- `cli.py`'s Momentum `--save-run` branch and the single shared `_maybe_save_run`
  helper (covering Graham Number/Growth/FCF Growth's `--save-run`) now build a
  `CachedInstrumentProfileResolver` from their already-open database
  (`_production_instrument_profile_cache`, added to `cli_support.py` alongside
  the existing `_production_historical_client`/`_production_financial_cache`
  helpers) and resolve through it.
- `cli_workspace.py`'s `refresh` command builds **one** resolver from the
  refresh command's own database and shares it across every concurrent job via
  a closure passed as `executor=`, so `refresh_watchlist`'s own public type
  (`Callable[[str, AnalysisSelection], ExecutionCapture]`) needed no change at
  all — contrary to the inventory's speculation that the executor's type might
  need extending. `_refresh_executor` and all four `_execute_*` adapters gained
  a `profile_cache` parameter instead.
- `compose_graham_profile` (`graham_shared.py`) gained an optional
  `profile_cache` parameter; when supplied it calls `resolve()` instead of
  `compose_instrument_profile()` directly, with identical candidate
  construction either way. `execute_graham_number`/`execute_graham_growth`/
  `execute_fcf_growth` thread it through unchanged otherwise.
- **Left live-only, unchanged:** `cli.py`'s Momentum default (non-`--save-run`)
  branch and the Graham/FCF default branch inside `_maybe_save_run` — both
  call `run_adapter(None)`/`compose_instrument_profile()` directly, per
  §13.3-1's resolved decision, generalized symmetrically to Graham/FCF since
  the same "no database opened solely for caching" reasoning applies to both.

**Design addition beyond the original sketch:** introduced
`InstrumentProfileResolver`, a `@runtime_checkable Protocol` in
`instrument_profile_cache.py` exposing only `resolve()`. Every wired call site
depends on this narrow Protocol, not the concrete `CachedInstrumentProfileResolver`
class, matching this project's existing convention (`SecurityIdentityProvider`,
`InstrumentKindProvider`) and decoupling `graham_shared.py`/the execution
adapters from SQLite entirely. This was not in the original slice sketch; it
fell out of trying to unit-test `compose_graham_profile`'s new dispatch branch
without a database fixture.

**Concurrency correctness — a real bug found and fixed, not merely audited:**
sharing one `CachedInstrumentProfileResolver` across refresh's worker threads
exposed exactly the race predicted in §6/§13.3-2: two threads resolving the
same never-before-seen ticker could both read "no current row" before either
committed, each minting a competing current row, since the partial-unique-index
approach was already ruled out and nothing at the SQLite level serializes a
read-then-conditionally-write sequence across independent transactions.
Fixed with an in-process per-ticker `threading.Lock` inside
`CachedInstrumentProfileResolver` (a `dict[str, Lock]` guarded by one meta-lock,
keyed by normalized ticker so different tickers proceed in parallel).

The fix was verified empirically, not just reasoned about: a new test
(`test_concurrent_resolutions_for_the_same_new_ticker_never_mint_two_current_rows`)
runs eight real OS threads against one shared resolver with an artificially
slow identity provider, and asserts the provider is called **exactly once**
across all eight — a standalone reproduction script confirmed 1 call with the
lock in place. Writing that test surfaced a second, unrelated bug in the test
itself (not the production code): a shared `_identity()` test helper hardcoded
`ticker="KO"`, which under a `"NEWCO"` request tripped `compose_instrument_profile`'s
existing ticker-mismatch guard and produced `PROVIDER_ERROR` for every thread
regardless of the lock — every thread took the live path because nothing was
ever successfully anchored, not because serialization failed. Corrected by
constructing the identity/kind evidence with the matching ticker directly.

Tests added/updated: `tests/data/test_instrument_profile_cache.py` (the
concurrency test above); `tests/workspace/test_graham_shared.py` (a new test
proving the `profile_cache` dispatch branch calls `resolve()` instead of
`compose_instrument_profile()`, using a `_FakeProfileCache` that only needs to
satisfy the `InstrumentProfileResolver` Protocol structurally). No existing
test required behavioral changes — every wired call site's default parameter
value (`profile_cache=None`) preserves the exact prior call shape.

Verification: full managed quality gate
(`scripts/run-quality-gates.ps1`) passes — `ruff check`/`format --check` clean,
`mypy --strict` over 296 source files, 3,120 tests passing, 91% aggregate
coverage.

## 14. Slice F evidence (2026-09-22)

**Finding, not assumption:** Step 3.4's existing Analysis Run design already
satisfies §5's historical-snapshot contract by construction, with no
production code change required. Verified by reading the actual chain rather
than trusting the plan:

- [`src/workspace/execution.py`](../../../../src/workspace/execution.py)'s
  `execute()` builds `AnalysisRun(..., instrument_profile=result.profile, ...)`
  from the `InstrumentProfile` *value* the capture callable already produced
  — whether that value came from a live `compose_instrument_profile()` call
  or (after Slice D) `CachedInstrumentProfileResolver.resolve()` makes no
  difference, since either way it is a plain immutable dataclass value by the
  time `execute()` sees it.
- [`src/data/repositories/analysis_runs.py`](../../../../src/data/repositories/analysis_runs.py)
  persists the *entire* `AnalysisRun` — including `instrument_profile`, with
  its identity/kind evidence and diagnostics — verbatim as `envelope_json` via
  `model_dump(mode="json")`, and `get()` only ever re-validates and returns
  that same stored value. Nothing about a later durable-cache supersession
  can reach an already-inserted row.
- [`src/reporting/analysis_runs.py`](../../../../src/reporting/analysis_runs.py)'s
  `project_run()` reads `run.instrument_profile` exclusively — its own module
  docstring already states it "must never call ... profile resolvers ...
  mutable caches" — so replay was already immune to Slice D's wiring before
  this slice began. The §5 requirement to show a reopened run's frozen
  snapshot "without conflating" it with the ticker's current profile is
  satisfied by there being no code path where both appear in one rendered
  view: `project_run()` never reads the durable cache, and the durable
  cache's own `current_record()`/`get()` never reads a stored Analysis Run.

Because this held before Slice D and is structurally insulated from it, the
open question for this slice was empirical, not architectural: does the
*combination* — durable cache wired into production execution, feeding a
real persisted Analysis Run, reopened and replayed — actually hold together,
including across a ticker-reuse supersession? No test exercised that
specific combination before this slice (Step 3.4's replay tests predate the
durable cache; the durable-cache tests predate Analysis Run persistence).

**New tests**, `tests/reporting/test_analysis_run_instrument_profile_snapshot.py`,
exercising the real chain with no mocks on the persistence or replay path:

- `test_a_ticker_reuse_supersession_never_relabels_a_previously_persisted_run`:
  resolves a profile for "RENU" (anchor `0000011111`, "Generation A Inc."),
  persists an Analysis Run from it; past the TTL, resolves the same ticker
  again with a disagreeing anchor (`0000099999`, "Generation B Corp."),
  triggering supersession, and persists a second Analysis Run. Asserts the
  durable cache's current record now shows Generation B, while reopening and
  replaying the *first* run still renders "Generation A Inc." and never
  "Generation B Corp." (and vice versa for the second run against the first).
- `test_repeated_execution_within_ttl_reuses_the_cache_and_each_run_keeps_its_own_snapshot`:
  two Analysis Runs for the same ticker within the TTL window call the
  identity provider exactly once between them (the durable cache absorbs the
  second lookup), and both persisted runs still carry their own correct,
  identical snapshot.

Both tests use Graham Number's minimal direct-construction pattern (mirroring
the existing `tests/reporting/test_analysis_run_replay.py` style) rather than
a full Momentum price-history fixture, since only the profile/persistence/
replay interaction is in scope here — Momentum's own replay correctness is
already covered by the existing Step 3.4 suite untouched by this slice.

Verification: full managed quality gate passes — `ruff check`/`format --check`
clean, `mypy --strict` over 297 source files, 3,123 tests passing, 91%
aggregate coverage.

## 15. Slice G evidence and final acceptance

### 15.1 Fixtures (IMPLEMENTATION_PLAN.md item 6, profile-specific portion)

**Verified, no gap found — no new fixture code was needed.**
`src/evaluation/fixtures/instrument_profiles.py`'s existing
`fixture_instrument_profile`/`fixture_known_etf_profile` already provide
deterministic `InstrumentProfile` values for the Golden-Suite/evaluation
harness and the Step 3.4 replay tests, and remain sufficient: the durable
repository/cache built in Slices B–D is deliberately excluded from Golden
fixture truth (IMPLEMENTATION_PLAN.md item 6: "Live providers and mutable
caches remain excluded from deterministic tests and Golden fixture truth"),
and a repository-wide search confirmed `src/evaluation/` never references
`CachedInstrumentProfileResolver`/`SQLiteInstrumentProfileRepository`. The
orchestrator's own `AnalysisToolDependencies.profile_resolver` seam (inventory
§4) already resolves against these same fixtures via
`src/evaluation/composition.py`'s `_profile_resolver`, unaffected by anything
built in this contract.

### 15.2 Documentation

- [`docs/project/ARCHITECTURE.md`](../../ARCHITECTURE.md): the "Durable
  instrument profiles and ETF aggregate FCF" section described a *planned*
  extension; rewritten to describe the implemented repository/cache/identity-
  anchor/ticker-reuse design (with a link to this contract) while leaving ETF
  aggregate FCF explicitly marked planned/deferred. Added
  `instrument_profile.py`, `instrument_profile_cache.py`, and
  `repositories/instrument_profiles.py` to the module-layout tree and a
  `SQLiteInstrumentProfileRepository` row to the repository table, matching
  the existing entries' format.
- [`docs/user/GLOSSARY.md`](../../../user/GLOSSARY.md): added an "Instrument
  Profile" entry next to the existing "Security Identity" entry, explaining
  durable caching and ticker reuse in the glossary's plain-language,
  investor-facing style.
- [`docs/project/DISCOVERY_WORKBOOK.md`](../../DISCOVERY_WORKBOOK.md): added
  two Decision Log rows (identity-anchored persistence keyed by `profile_id`;
  the per-ticker-lock correction over the ruled-out partial index) and a
  "Durable instrument profiles" lessons-learned section in the same style as
  the existing "Fresh database readiness"/"Graham comparison evidence"/
  "Independent correctness verification" entries, naming both design
  corrections found only once the primitive was wired into a real concurrent
  caller.

No other active documentation needed a change: `docs/user/FINANCE_MATH.md` is
scoped to calculation semantics, which nothing here touches; no other guide
referenced `compose_instrument_profile`/the durable cache in a way this work
made stale (confirmed by the same searches recorded in the Slice D inventory
§6). Historical planning records that mention P2-Profiles' position in the
work sequence (e.g. Step 3.4's contract) are left untouched per this
project's established precedent of not rewriting historical approval records
after later steps complete.

### 15.3 Milestone summary

| Slice | Scope | Evidence |
| :--- | :--- | :--- |
| A | Contract: identity key, precedence, freshness/refresh, historical-snapshot design, `DataQualityError` hierarchy | Accepted 2026-09-21 (§9) |
| B | Durable schema, migration, repository | §11 |
| C | Freshness/refresh/ticker-reuse cache | §12 |
| D | Production wiring across every composition site | §13.6, [inventory](P2_PROFILES_SLICE_D_INVENTORY.md) |
| E | `DataQualityError` hierarchy (Issue #33) | §7.1 |
| F | Analysis Run historical-snapshot integration | §14 |
| G | Fixtures verification, documentation | §15.1–15.2 |

Across all slices: two production correctness issues were found and fixed
before they shipped, not after — the partial-unique-index design that the
project's own readiness contract would have rejected (§6, caught in Slice B),
and the concurrent-mint race exposed by actually wiring the cache into
watchlist refresh's worker pool (§13.6, caught in Slice D). One scope
correction was made transparently: the original draft slice sequence assumed
watchlist refresh already had a database available to its job executor; it
did not, and the user's explicit call to wire it through anyway (rather than
leaving refresh live-only) is what surfaced the concurrency issue in the
first place. Every slice's evidence includes the actual quality-gate numbers
(ruff/mypy/pytest/coverage) at the time it was verified, not merely a
completion claim.

### 15.4 Final acceptance

Every acceptance criterion IMPLEMENTATION_PLAN.md's P2-Profiles entry names is
met: migrated storage (§11); deterministic reopen/reuse and ticker-reuse
tests, at both the repository level (§11, §12) and end-to-end through a real
persisted Analysis Run (§14); truthful retained provenance (evidence and
diagnostics persisted verbatim in the Analysis Run envelope, §14); an
immutable execution snapshot suitable for Analysis Runs (§14); the unified
`DataQualityError` hierarchy (§7.1); and production composition sites
actually resolving through the durable cache rather than an unused primitive
(§13.6).

**Final acceptance granted 2026-09-22.** The stakeholder confirmed the work
is complete and self-consistent and cleared IMPLEMENTATION_PLAN.md's row 8 to
"Complete and accepted," unblocking row 9 (Existing-analysis renewal, ESC-D)
as the next work package in sequence.
