# Step 3.1 D0 — Field-level persistence mapping

**Prepared:** 2026-09-05  
**Status:** Gate D0 approved on 2026-09-05; Slice A authorized  
**Owner:** [SQLite slice plan](STEP_3_1_SQLITE_SLICE_PLAN.md), Slice D0  
**Scope:** Approved design record. Production work proceeds only through separately authorized slices.

The human approved this mapping and the exact five-table first-migration list
on 2026-09-05 and explicitly authorized Slice A, including edits to
`pyproject.toml` and `uv.lock`. This closes Gate D0 and accepts the proposed gap
dispositions below; it does not authorize migration creation or later slices.

## 1. Contract evidence and proposed table list

This mapping follows the current source contracts, rather than the older
illustrative telemetry vocabulary in the milestone overview:

- [`TrajectoryEvent`](../../../../../src/core/telemetry/models.py)
- [`ResolvedInputCacheKey`, `ResolvedInputCacheEntry`, and in-memory behavior](../../../../../src/data/financial/cache.py)
- [`ResolvedInput` and `ComponentLineage`](../../../../../src/data/financial/provenance.py)
- [`HistoricalMarketData` and `MarketDataContext`](../../../../../src/data/market_data.py)
- [`BaseDataClient`](../../../../../src/data/base_client.py) and
  [production historical adapter](../../../../../src/data/yfinance/client.py)

The proposed first migration creates exactly these five application tables:

| Table | Purpose | Primary key |
| :--- | :--- | :--- |
| `schema_metadata` | Application serialization version, distinct from migration revision | `metadata_key` |
| `trajectory_events` | Sanitized, ordered event envelopes | `event_id` |
| `resolved_input_cache` | Original provider/derived inputs for both security and macro subjects | `cache_key` |
| `market_data_cache_entries` | One historical request snapshot and its frame/context metadata | `entry_key` |
| `market_price_observations` | OHLCV rows owned by one request snapshot | `(entry_key, row_position)` |

Alembic owns its separate `alembic_version` table. No separate company-fact,
macro, provider, security, instrument-profile, Analysis Run, watchlist, or
evaluation tables are required. Provider/source metadata is retained on records;
the specialized slice plan excludes P2 instrument-profile persistence.

`schema_metadata` has `metadata_key TEXT NOT NULL PRIMARY KEY` and
`metadata_value INTEGER NOT NULL CHECK (metadata_value >= 1)`. Seed only
`persistence_encoding_version = 1`, governing key/JSON/frame encoding below.
Alembic remains authoritative for DDL revision; cache `schema_version` and
telemetry `schema_version` retain their independent domain meanings. Readers
must reject an unsupported encoding version, never reinterpret it as version 1.

## 2. Shared representation and integrity rules

In the tables below, `?` means SQL NULL is allowed; other columns are NOT NULL.
`UTC` means TEXT formatted exactly `YYYY-MM-DDTHH:MM:SS.ffffffZ`, converted from
a timezone-aware datetime. Reject naive datetimes; reconstruct aware UTC
datetimes. Preserve the instant, not the original timezone object's identity.
Dates use `YYYY-MM-DD` without an invented time or timezone. DataFrame index
encoding is separately specified below to retain nanoseconds and local dates.

UUIDs use lowercase hyphenated TEXT and reconstruct as UUID objects. Enums use
their existing string values and reconstruct through the declared enum type.
SQL INTEGER carries integers; REAL carries finite binary64 floats without
rounding. Missing optional values remain NULL. Validate finite values recursively
before writes, including JSON; never substitute zero or stringify NaN/Inf.

Canonical JSON is UTF-8 text using sorted object keys, compact separators,
`ensure_ascii=False`, and `allow_nan=False`; array order remains significant.
Optional absent objects use SQL NULL. No pickle, arbitrary-object deserialization,
whole DataFrame JSON blob, or raw provider response is stored. Readback validates
decoded structures and invokes existing domain constructors/Pydantic validation.
Malformed stored values raise explicit storage/validation errors, not plausible
empty results. Recorder error handling remains the telemetry fail-open boundary.

Database constraints enforce required columns, positive versions/sequences,
nonnegative counts/latencies, valid enum values, and paired/ordered key periods.
Adapters enforce datetime format/timezone, finite values, normalized-key agreement,
and domain invariants; SQL constraints do not replace domain validation.
All replacement operations are atomic transactions with rollback on failure.

## 3. TrajectoryEvent → trajectory_events

| Domain field | Column / representation | Reconstruction or rationale |
| :--- | :--- | :--- |
| `event_id` | `event_id TEXT`, PK | UUID |
| `run_id` | `run_id TEXT` | UUID; actual contract uses run, not trajectory ID |
| `session_id` | `session_id TEXT` | UUID |
| `sequence` | `sequence INTEGER`, >= 1 | Event ordering within run |
| `timestamp` | `timestamp UTC` | Aware UTC datetime; see gap G1 |
| `event_type` | `event_type TEXT` | `TrajectoryEventType` value |
| `component` | `component TEXT` | Preserve text verbatim |
| `schema_version` | `schema_version INTEGER`, >= 1 | Envelope version |
| `mode` | `mode TEXT` | `light` or `full` |
| `span_id` | `span_id TEXT` | UUID |
| `parent_span_id` | `parent_span_id TEXT?` | Optional UUID; no FK |
| `model_tag` | `model_tag TEXT?` | Preserve |
| `provider` | `provider TEXT?` | Preserve; no provider-name rewrite |
| `step_index` | `step_index INTEGER?`, >= 1 | Preserve missing |
| `tool_name` | `tool_name TEXT?` | Preserve |
| `tool_args` | `tool_args_json TEXT?` | Canonical JSON dictionary |
| `tool_result_summary` | `tool_result_summary_json TEXT?` | Canonical JSON value |
| `prompt_tokens` | `prompt_tokens INTEGER?`, >= 0 | Missing metrics stay NULL |
| `completion_tokens` | `completion_tokens INTEGER?`, >= 0 | Missing metrics stay NULL |
| `latency_ms` | `latency_ms REAL?`, >= 0 | Finite; no estimation |
| `payload` | `payload_json TEXT?` | Canonical JSON value retained by recorder |
| `payload_hash` | `payload_hash TEXT?` | Preserve recorder hash; do not hash new SQL JSON bytes |
| `error` | `error_json TEXT?` | Canonical JSON dictionary |

Unique constraint `(run_id, sequence)` also supplies ordered run lookup.
Additional index: `(session_id, timestamp)`. No FK on run/session/span identifiers:
no parent tables exist, and fail-open telemetry may contain gaps. Read in ascending
sequence; do not renumber gaps or infer missing events. Enum CHECK values are
the source's ten values: `run_start`, `step_start`, `prompt_sent`, `llm_response`,
`tool_call`, `tool_result`, `error`, `recovery_attempted`, `step_end`, `run_end`.

Duplicate `event_id` with all encoded fields equal is a no-op. A different
envelope under that ID, or another ID claiming the same run/sequence, is a
conflict: reject without updating any row. Concurrent inserts use the constraints
and transactional conflict verification. Events remain immutable.

Persist already-sanitized recorder output; sink serialization must not restore
discarded bodies or rewrite payload hashes. JSONL/SQLite equivalence means typed
equality for supported sanitized events, not identical serialized bytes. Unknown
Python objects under `Any` must not be silently converted by the SQLite sink.

## 4. Financial cache → resolved_input_cache

### 4.1 Key fields and nullable identity

| ResolvedInputCacheKey field | Column | Rule |
| :--- | :--- | :--- |
| `subject_kind` | `subject_kind TEXT` | `security` / `macro` |
| `subject_id` | `subject_id TEXT` | SECURITY strip/uppercase; MACRO strip, preserve case |
| `field_name` | `field_name TEXT` | Strip; nonempty |
| `basis` | `basis TEXT?` | Strip if present; reject blank |
| `provider_id` | `provider_id TEXT` | Strip/lowercase; nonempty |
| `analysis_as_of` | `analysis_as_of UTC?` | NULL is current, not a date sentinel |
| `schema_version` | `schema_version INTEGER`, >= 1 | Exact version identity |
| `observation_period_start` | `key_period_start UTC?` | Paired with end |
| `observation_period_end` | `key_period_end UTC?` | Both NULL or start <= end |

Add `cache_key TEXT NOT NULL PRIMARY KEY`: canonical JSON array of the nine
normalized fields in the table's order, using actual JSON null for absent values
and UTC strings for datetimes. This is a complete key, not a hash or delimiter
concatenation. For example:

```json
["security","AAPL","eps",null,"yfinance",null,1,null,null]
```

Normalize through `ResolvedInputCacheKey` first. Equal instants with different
UTC offsets encode identically. JSON null cannot collide with a literal string;
current and historical keys remain distinct. Ordinary SQLite uniqueness over
nullable columns is not used. On read, reconstruct the key and verify its encoded
form against `cache_key`. No redundant unique nullable composite constraint.

Series lookup index: `(subject_kind, subject_id, field_name, basis, provider_id,
analysis_as_of, schema_version, key_period_end, key_period_start)`. Use explicit
NULL equality for nullable query members. No foreign keys are needed.

### 4.2 Entry and complete ResolvedInput mapping

`ResolvedInputCacheEntry.key` reconstructs from section 4.1;
`resolved_input` reconstructs from this table; `cached_at` maps to
`cached_at UTC NOT NULL`, supplied by the cache's injected clock on every put.

| ResolvedInput field | Storage classification / column | Rule |
| :--- | :--- | :--- |
| `field_name` | Shared relational `field_name` | Entry constructor requires equality |
| `value` | `value REAL` | Finite |
| `source_kind` | `source_kind TEXT` | Top-level only `provider` / `derived` |
| `resolved_at` | `resolved_at UTC` | Original resolution time |
| `origin_source_kind` | Derived/non-stored: None | Both cacheable source kinds require None |
| `basis` | Shared relational `basis` | Entry constructor requires equality |
| `units` | `units TEXT?` | Preserve |
| `currency` | `currency TEXT?` | Preserve domain value, no additional normalization |
| `provider_id` | `input_provider_id TEXT?` | Separate from key: derived input may differ or lack provider |
| `provider_field` | `provider_field TEXT?` | Exact upstream field |
| `observation_period_start` | `input_period_start UTC?` | Separate: unscoped key can retain a period on the input |
| `observation_period_end` | `input_period_end UTC?` | Preserve without imposing key pairing on unscoped input |
| `observed_at` | `observed_at UTC?` | Point observation |
| `available_at` | `available_at UTC?` | Public availability, not fetch time |
| `as_of` | Shared relational `analysis_as_of` | Entry constructor requires equality |
| `retrieved_at` | `retrieved_at UTC?` | Original retrieval time; never replaced on cache hit |
| `cache_schema_version` | Derived/non-stored: None | Original provider/derived input requires None |
| `lineage` | `lineage_json TEXT?` | Recursive canonical JSON, described below |
| `notes` | `notes_json TEXT` | Ordered array, including empty array; reconstruct tuple |
| `fiscal_year` | `fiscal_year INTEGER?`, >= 1 | Preserve provider fiscal label |
| `period_kind` | `period_kind TEXT?` | Existing `PeriodKind` |
| `accounting_scope` | `accounting_scope TEXT?` | Existing `AccountingScope` |
| `capital_expenditure_sign` | `capital_expenditure_sign TEXT?` | Existing sign enum |
| `provider_fact_id` | `provider_fact_id TEXT?` | Preserve normalized source identifier |

Lineage JSON is an object with `transformation` string and ordered `components`
array. Each component stores **all 24 ResolvedInput fields**, including explicit
nulls and recursively nested lineage, using the same datetime/enum conventions.
Unlike the cacheable root, a component can carry override/cache source metadata:
do not omit `origin_source_kind` or `cache_schema_version` there. Reconstruct
components, their tuple, and `ComponentLineage` before the root. Notes and lineage
are bounded provenance structures, not additional relational query surfaces.

Validate `ResolvedInputCacheEntry` before writes and after reads. In particular,
period-scoped keys must match input periods and provider-sourced roots must match
the key provider. Do not impose that provider equality on derived roots.

### 4.3 Replacement, eligibility, and ordering

Every successful `put` replaces the complete row for its normalized key and resets
`cached_at`, even when the input is identical. This matches the in-memory cache;
it is deliberately not an immutable/idempotent event write. Last committed put
wins. No restatement archive or provider-fact-ID key extension is introduced.

`get` returns the unchanged stored entry only when eligible. For historical keys,
`available_at` must be present and <= `analysis_as_of`. With TTL enabled, reject
only when `now - cached_at > ttl`; equality is eligible, zero TTL is valid, and
a future cached time is not newly rejected. Validate the clock's timezone when
used. TTL None disables age checking. Stale reads do not delete rows.

`get_series` matches all seven `ResolvedInputSeriesCacheQuery` fields exactly
after existing normalization, excludes unscoped periods, and applies the same
eligibility checks per entry. Return a tuple sorted by period end, period start,
and `provider_fact_id or ""`, ascending, exactly as the in-memory implementation.
Query fields are request inputs, not additional persisted objects. The resolver
continues to construct cache-sourced outputs and own fallback/financial temporal
policy; storage does not rewrite provenance or add negative-result caching.

## 5. HistoricalMarketData → request snapshot and OHLCV rows

The proposals in this section were approved with gaps G2–G4 at Gate D0. The existing
dataclass does not constrain frame shape or supply request/retrieval metadata.

### 5.1 Frame and context fields

| Domain field | Storage classification | Reconstruction |
| :--- | :--- | :--- |
| `HistoricalMarketData.frame` | Relational child rows plus structural metadata | Rebuild supported frame using row positions, original index/column metadata and dtypes |
| `HistoricalMarketData.context` | Relational parent columns below | Construct `MarketDataContext`; do not enrich from live metadata |
| `MarketDataContext.provider_id` | `context_provider_id TEXT?` | Preserve exact normalized domain value, including case |
| `observation_interval` | `observation_interval TEXT?` | Preserve; no daily assumption for unknown providers |
| `data_as_of` | `data_as_of TEXT?` date | Last-data date as supplied, not request end or retrieval time |
| `currency` | `currency TEXT?` | Preserve context's uppercase value |
| `observation_count` | `observation_count INTEGER?`, >= 0 | Preserve None; distinct from actual row count |
| `price_adjustment` | `price_adjustment TEXT?` | Preserve normalized label; never merge adjusted and unadjusted values |

### 5.2 Additional market_data_cache_entries columns

These are adapter/storage metadata, not invented fields on the public dataclasses.

| Column | Type | Source and purpose |
| :--- | :--- | :--- |
| `entry_key` | TEXT PK | Canonical request identity array below |
| `ticker` | TEXT | Request symbol, strip/uppercase; preserve punctuation |
| `request_provider_id` | TEXT | Stable injected provider ID, strip/lowercase |
| `request_start` | TEXT date | Validated request start date |
| `request_end` | TEXT? date | Explicit end date; NULL retains open-ended request |
| `request_variant` | TEXT | Explicit adapter-owned configuration identity; production v1 `1d:adjusted` |
| `schema_version` | INTEGER >= 1 | Historical cache encoding version, initially 1 |
| `cached_at` | UTC | Cache write time from injected clock |
| `fetch_completed_at` | UTC? | Adapter-observed completion time on a real fetch; absent for imported payload without timing |
| `row_count` | INTEGER > 0 | Actual frame length, validated against stored rows |
| `frame_metadata_json` | TEXT | Bounded structural metadata specified below |

`entry_key` is canonical JSON array `[ticker, request_provider_id, request_start,
request_end, request_variant, schema_version]`. Index/uniqueness is the primary
key alone for initial exact-request lookup. CHECK request end is NULL or >= start.
An open-ended request cannot collide with an explicitly bounded request.
Request variant prevents one provider's differently configured clients from
sharing a snapshot. Unknown provider/configuration identity cannot produce a
reusable production-cache key; custom injection must remain usable.

Frame metadata object has `columns` (ordered labels), `dtypes` (parallel ordered
dtype strings), `columns_name`, `index_kind` (`datetime` or `date`), `index_name`,
`index_dtype`, `index_timezone` (zone identifier/fixed offset or null), and
`index_frequency` (frequency string or null). This is structural metadata only;
OHLCV values remain relational. No implicit dtype inference during readback.

Proposed v1 supported shape: nonempty single-level string columns drawn from
`Open`, `High`, `Low`, `Close`, `Adj Close`, `Volume`, with `Close` required;
finite NumPy `float64`/`int64` columns; unique ascending DatetimeIndex (naive or
aware) or unique ascending Python-date index. Preserve column order and names.
Optional OHLCV columns may be absent. Unsupported dtypes, extra columns,
MultiIndex, null/non-finite cells, duplicate/nonascending indexes, and nonempty
frame attrs are explicitly outside the approved v1 serialization shape.
Never silently strip columns, coerce missing cells, sort a materially different
frame, or claim arbitrary DataFrame round-trip support.

### 5.3 market_price_observations columns

| Column | Type | Meaning |
| :--- | :--- | :--- |
| `entry_key` | TEXT | FK → `market_data_cache_entries.entry_key`, ON DELETE CASCADE |
| `row_position` | INTEGER >= 0 | Original order; composite PK with entry key |
| `index_value` | TEXT | Datetime integer tick count as decimal text in stored index unit, or ISO date |
| `open` | REAL? | `Open` value if column exists |
| `high` | REAL? | `High` value if column exists |
| `low` | REAL? | `Low` value if column exists |
| `close` | REAL | Required `Close` value |
| `adj_close` | REAL? | `Adj Close` value if column exists |
| `volume` | NUMERIC? | Preserve INTEGER for int64, REAL for float64 |

Unique `(entry_key, index_value)` prevents duplicate observations within the
snapshot. The PK provides child lookup/order and FK indexing. NULL OHLCV columns
mean the column is absent according to frame metadata, not missing observations.
For int64 price columns, reject values that cannot round-trip exactly through
REAL; do not accept lossy writes. Volume retains signed int64 exactly. Aware
datetime ticks represent UTC instants and reconstruct in the stored timezone;
naive ticks retain wall time without UTC localization. Record the datetime unit
in `index_dtype` to avoid nanosecond truncation; date indexes reconstruct dates.

Validate all rows and metadata before atomic publication. Read parent and children
in one consistent read transaction; check count, metadata, numeric validity and
index consistency before constructing `HistoricalMarketData`.

### 5.4 Overlap and cache reuse

Replacing an exact request key replaces parent metadata and **all** its child
rows in one transaction. A repeated identical payload still updates cache timing.
Overlapping requests have separate snapshots: no global ticker/date upsert may
rewrite the provenance or adjusted prices of another cached request. This avoids
mixing retrieval vintages. Cross-request deduplication is deferred.

Initial E2 reuse is exact request/provider/variant/version only, subject to an
explicit configured TTL (same age boundary as the financial cache). Range
containment, partial hits, or differing bounds trigger a full provider refetch;
do not stitch series. A failed fetch leaves the prior snapshot untouched and does
not silently return stale data. Empty/invalid responses are not persisted.
`fetch_current_price` continues to delegate to the real quote boundary.

## 6. Contract gaps and Gate D0 decisions

| ID | Evidence / gap | Proposed disposition for human review |
| :--- | :--- | :--- |
| G1 | `TrajectoryEvent.timestamp` accepts naive datetimes; `Any` fields and nonnegative float validation do not guarantee finite, JSON-only values. | Approve SQLite acceptance of aware, finite, sanitized JSON-compatible events only; test explicit rejection/fail-open behavior. Exact equivalence is scoped to these supported events. A public model hardening change requires separate authorization. |
| G2 | `HistoricalMarketData.frame` is unrestricted, and yfinance returns its frame without validating this full storage shape. | Approve the explicit v1 frame subset above. Valid but unsupported custom frames bypass cache with a diagnostic and retain existing client behavior; invalid financial data must be reported explicitly. Alternatively authorize a broader encoding contract before B3. No silent lossy persistence. |
| G3 | Historical payload has no ticker, request bounds, requested analysis `as_of`, availability date, or retrieval timestamp. `data_as_of` is a date describing observations. | Supply request identity and locally measured fetch completion at the adapter boundary. Do not claim provider retrieval/public availability evidence or historical point-in-time eligibility. No invented `analysis_as_of` column or public model extension. |
| G4 | Client boundary has no interval/adjustment request fields or historical-cache TTL contract; provider identity can be None. | Approve explicit adapter variant identity, exact-request/full-refetch behavior, and injected TTL. Freeze the production TTL/default and settings name in Slice A review; do not infer infinite freshness for open-ended requests. Unknown identity bypasses reusable caching. |
| G5 | `.gitignore` ignores `*.db` and `*.sqlite`, but lacks general SQLite sidecar and `*.sqlite3` patterns. | Add appropriate database/sidecar patterns in authorized Slice A; D0 does not edit ignore rules. Verify representative overridden paths with `git check-ignore`. |

Gate D0 approved the exact table list, serialization/key encodings, snapshot
overlap policy, and G1–G4 dispositions on 2026-09-05. G5 is a scoped Slice A
handoff. Slice A supplies `historical_cache_ttl_seconds`, default 3,600 seconds,
for review: bounded one-hour reuse, with zero and None retaining their documented
meanings. No gap was repaired through a production edit in D0.

## 7. Verification handoff

The implementation slices must provide deterministic evidence for:

- Complete field coverage: all 23 event, 9 cache-key, 3 cache-entry,
  24 resolved-input, 2 historical-payload, and 6 context fields mapped above.
- Telemetry JSONL/SQLite typed equality, optional nulls, all event enums,
  sequence gaps, duplicate no-op versus conflict, and recorder fail-open behavior.
- Scalar/series cache parity across current versus historical keys, timezone
  offset equivalence, nullable basis/periods, normalization, unscoped input periods,
  distinct derived provider IDs, recursive lineage, TTL equality/zero/future time,
  unavailable historical facts, replacements, and stable series ordering.
- Historical frame/context equality including column order/dtypes, date and
  naive/aware datetime indexes, nanosecond precision, None context fields,
  absent columns, integer volume, overlapping request isolation, rollback, and
  unsupported-shape handling without financial-value substitution.
- Effective WAL/foreign keys/busy timeout on fresh file connections; migration
  lifecycle and exact table/index/constraint inspection; consistent concurrent
  snapshot reads and all-or-nothing writes.

D0 verification is source-field inventory, local-link checking, and documentation
diff review. No runtime behavior changed, so production tests are not claimed as
D0 evidence. Establish focused baselines before each implementation slice and
run the complete managed quality-gate wrapper at Step 3.1 closeout as planned.
