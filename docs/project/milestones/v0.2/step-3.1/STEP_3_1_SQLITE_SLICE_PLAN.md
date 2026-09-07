# Step 3.1 SQLite Persistence Slice Plan

**Milestone:** v0.2 — Step 3.1  
**Prepared:** 2026-09-03  
**Status:** Gate D0, Slices A/B1/B2/B3/C1/C2/D1/D2/E1/E2/F1/F2/G, and Gates B/C/D/E/G approved; Step 3.1 complete and approved
**Owning plan:** [`../IMPLEMENTATION_PLAN.md`](../IMPLEMENTATION_PLAN.md), Section 4.7

## 1. Goal

Establish one migration-controlled SQLite database for production market-data
cache records and trajectory telemetry while preserving the provider-neutral
contracts created in Steps 2.1–2.5A. Step 3.1 supplies infrastructure and
adapters; it does not move financial calculations, provider selection, cache
eligibility, or orchestration policy into SQLite.

## 2. Entry gate and scope

Step 2.6 is complete and no longer blocks this work. Documentation and the
explicitly authorized dependency preparation may proceed before production-code
implementation. Before each implementation slice, record a clean focused-test
baseline and the current `git status --short`; unrelated user changes remain
out of scope.

### In scope

- an Alembic migration environment and initial SQLite schema;
- a narrow connection/transaction boundary with WAL, foreign keys, and bounded
  busy waiting enabled on every connection;
- a `SQLiteTrajectorySink` satisfying the existing synchronous
  `TrajectorySink` protocol;
- a SQLite implementation of `ResolvedInputCacheProtocol` and
  `ResolvedInputSeriesCacheProtocol`;
- durable historical OHLCV caching behind the existing `BaseDataClient`
  boundary;
- preservation of source identity, observation/availability dates, retrieval
  time, requested `as_of`, schema version, and lineage;
- deterministic tests using temporary databases and no external calls; and
- operator documentation for migration and fresh-database verification.

### Explicit non-goals

- Step 3.2's general-purpose repository/DAO expansion;
- Step 3.3 freshness/invalidation policy beyond the already approved cache
  contract and configurable TTL;
- Step 3.4 watchlists, Analysis Runs, or run browsing;
- P2 durable instrument profiles or ETF aggregate FCF growth;
- changing the semantics of Momentum, Graham, or FCF/Earnings Growth;
- storing secrets, `.env` content, databases, raw live-provider payloads, or
  Golden fixtures in Git; and
- async database access, a service process, a generic ORM framework, or a
  speculative registry/factory hierarchy.

## 3. Decisions to freeze before implementation

### 3.1 Persistence technology

Use SQLAlchemy 2.x Core plus Alembic. Core gives Alembic a supported schema and
transaction layer without introducing ORM entities that compete with the
project's typed domain models. SQLite remains the only Step 3.1 database.

This requires explicit human permission to add `sqlalchemy` and `alembic` to
`pyproject.toml` and refresh `uv.lock`. The dependency change is Slice A and
must not be smuggled into a later code slice.

### 3.2 Database location and URL

Replace the test-like default `sqlite:///./test.db` with a production default
under the configured data directory, while retaining an environment override.
Resolve relative SQLite paths from the repository/application base directory,
not from an arbitrary caller working directory. Tests always inject a temporary
absolute database path.

The database file, SQLite sidecars (`-wal`, `-shm`), migration test databases,
and quality-run artifacts must remain ignored and untracked.

### 3.3 Connection policy

Every application and migration connection must establish and verify:

- `PRAGMA foreign_keys = ON`;
- `PRAGMA journal_mode = WAL` for file-backed databases;
- a bounded `busy_timeout` configured in typed settings; and
- explicit transaction ownership, rollback on failure, and deterministic
  close/disposal.

Do not claim WAL from a one-time setup call alone. A focused integration test
must query the effective journal mode from a fresh connection. In-memory
SQLite is not used for the WAL assertion because it cannot represent the
file-backed production behavior.

### 3.4 Serialization boundary

Persist losslessly reconstructable domain data. Use canonical JSON only for
bounded nested values that do not benefit from relational querying (for
example telemetry payloads and immutable notes). Store timestamps in a single
documented UTC representation and reconstruct timezone-aware values. Store
enums by stable string value. Reject non-finite numeric values before writes;
never coerce missing data to zero.

### 3.5 Ownership of cache semantics

SQLite storage implements the approved cache protocols. The resolver continues
to own precedence and temporal eligibility. The durable cache may enforce its
configured TTL exactly as the in-memory implementation does, but it must not
invent provider fallback, rewrite provenance, or relabel stored provider or
derived inputs as cache-sourced results.

### 3.6 Initial schema groups

The first migration creates only tables required by Step 3.1:

1. `schema_metadata` for application schema/version metadata where Alembic's
   revision table alone is insufficient;
2. `trajectory_events`, keyed by event identity and uniquely ordered by
   `(run_id, sequence)`;
3. `resolved_input_cache`, keyed by the complete normalized cache identity,
   including nullable `as_of` and optional period bounds without collapsing
   current and historical requests;
4. `market_price_observations` for normalized OHLCV observations; and
5. `market_data_cache_entries` for request/provider/retrieval/context metadata
   describing a cached historical series.

Instrument-profile tables, Analysis Runs, watchlists, and evaluation reports
are intentionally absent. If exact SQLite uniqueness with nullable key members
cannot express the cache contract safely, freeze an explicit normalized-key
encoding in the design test before authoring the migration; do not rely on
SQLite treating `NULL` values as equal in a unique constraint.

## 4. Slice design principles for a local implementation model

Each slice is a fresh Cline task and has one primary behavior, a small explicit
file allowlist, focused tests, and a hard stop. The model must first inspect the
named contracts, restate the files it intends to change, and wait for approval
before Act mode. After editing it must reread every changed file, run the named
checks, show `git status --short`, and report command output accurately.

No slice may commit, push, install packages, weaken tests, edit unrelated files,
or begin the next slice. A claimed success is not evidence: the project owner or reviewer
inspects the diff and independently reruns the gate. If a slice needs a public
contract change not stated here, it stops and reports the mismatch.

Keep individual implementation tasks below roughly four production files and
two focused test files. Prefer extending an already reviewed narrow module over
creating abstractions in anticipation of later steps.

## 5. Implementation slices

### Slice D0 — contract and schema mapping freeze

**Status:** Complete and approved on 2026-09-05. The project owner approved the mapping
and exact five-table first migration, and separately authorized Slice A with
permission to edit `pyproject.toml` and `uv.lock`. Migration creation remains a
later slice.

**Purpose:** Convert the approved domain objects into a field-level persistence
mapping before migration code exists.

**Artifacts:** This document plus, if useful, one adjacent mapping record. No
production code, dependency, or lock-file changes.

**Approved mapping:** [Field-level persistence mapping](STEP_3_1_D0_PERSISTENCE_MAPPING.md)
was prepared and approved on 2026-09-05 from the current source contracts. It defines the
exact first-migration table list, field encodings, cache identity and replacement
rules, historical snapshot policy, and accepted contract-gap dispositions.

**Required work:**

- enumerate every persisted field from `TrajectoryEvent`,
  `ResolvedInputCacheKey`, `ResolvedInputCacheEntry`, `ResolvedInput`,
  `HistoricalMarketData`, and `MarketDataContext`;
- classify each field as relational column, canonical JSON, derived/non-stored,
  or excluded with rationale;
- define primary keys, uniqueness, foreign keys, indexes, timestamp encoding,
  enum encoding, nullable-key normalization, and reconstruction rules;
- define overwrite/idempotency behavior for duplicate telemetry events, cache
  puts, and overlapping OHLCV observations; and
- identify any contract gap. Contract gaps stop at Gate D0 rather than being
  repaired opportunistically.

**Gate D0:** Human approves the mapping and exact first-migration table list.

### Slice A — dependency and configuration boundary

**Authorization:** Explicit human permission granted on 2026-09-05 to implement
Slice A and edit `pyproject.toml` / `uv.lock`. No later slice is authorized.

**Verification / review status:** Slice A approved by the project owner on 2026-09-05,
with explicit authorization to proceed to B1. The complete managed wrapper passed: Ruff check and format,
strict mypy, and 1,360 tests (including 30 configuration cases), 88% coverage.
Artifacts: `.tmp/quality-runs/20260905083439184-19068-0fdc40eafed44e50bdd708f1e819aa76/`.
Representative `.sqlite3`, WAL, SHM, and rollback-journal paths passed
`git check-ignore`; no dependency-file diff was needed. No checkpoint commit was
required before B1; the approved work remains in the working tree.

**Baseline:** Complete managed wrapper passed before source edits: 1,332 tests,
88% coverage, Ruff check/format, and strict mypy. Initial working changes were
only the D0 mapping and slice-plan link from this task. The first sandboxed
attempt could not access the existing interpreter; approved elevated execution
passed with caches and temporary artifacts still isolated under `.tmp/quality-runs/`.

**Dependency evidence:** The repository already declared `sqlalchemy>=2.0,<3`
and `alembic>=1.13,<2`, locked to 2.0.52 and 1.19.1 respectively. Authorized
`uv add --offline "sqlalchemy>=2.0,<3" "alembic>=1.13,<2"` resolved 76 packages
and checked 61; both dependency files remained unchanged. Existing pins were
preserved, with no unrelated upgrades. The API boundary uses SQLAlchemy's
[documented URL helpers](https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls);
Alembic remains the [migration dependency](https://alembic.sqlalchemy.org/en/latest/front.html).

**Settings delivered for review:** Environment variable names are case-sensitive,
lowercase, matching the existing settings convention.

| Setting | Default / contract |
| :--- | :--- |
| `database_url` | Absolute SQLite URL for `<data_dir>/financial-data-agents.sqlite3`; explicit relative database paths resolve against `base_dir` |
| `base_dir` / `data_dir` | Relative base anchors to application root; data defaults to `<base_dir>/data`, with relative data overrides anchored to base |
| `database_busy_timeout_ms` | 5,000 milliseconds; positive integer bounded by SQLite's signed 32-bit timeout parameter |
| `historical_cache_ttl_seconds` | 3,600 seconds: conservative bounded reuse within an hour; finite nonnegative seconds, zero permits no positive age, Python None disables TTL |
| `telemetry_sink` | Accept `jsonl` or `sqlite`; default remains `jsonl`; runtime SQLite selection is deferred to C2 |

Only synchronous `sqlite` / `sqlite+pysqlite` URLs are accepted. Explicit memory
URLs remain available for tests; URL credentials, host/port, query parameters,
and SQLite file URIs are rejected to keep path and connection policy unambiguous.
Constructing settings opens no connection and creates no database. Existing
import-time data/log-directory creation remains unchanged in purpose. Database,
WAL/SHM, and rollback-journal ignore patterns cover overridden locations.
Busy timeout and historical TTL are configuration only until the owning adapters
are implemented. No engine, migration environment, schema, or sink is created.

**Prerequisite:** explicit permission to edit `pyproject.toml` and `uv.lock`.

**Purpose:** Add only the supported migration/database dependencies and typed
settings needed by later slices.

**Likely files:** `pyproject.toml`, `uv.lock`, `src/config.py`,
`tests/test_config.py`, and ignore rules if the D0 audit proves they are
incomplete.

**Required work:**

- add bounded compatible SQLAlchemy 2.x and Alembic dependencies through `uv`;
- define the production database URL/path and a positive busy-timeout setting;
- allow `telemetry_sink="sqlite"` without changing the runtime default until
  the SQLite sink is integrated and tested;
- test defaults, environment overrides, invalid timeout values, and path
  resolution; and
- prove no database file is created merely by importing settings.

**Focused gate:** Ruff, format check, strict mypy for changed source/tests, and
focused configuration tests. Stop for review.

### Slice B1 — SQLite engine and transaction policy

**Authorization:** Slice A approved and B1 explicitly authorized on 2026-09-05.
Baseline complete wrapper: 1,360 tests, 88% coverage, Ruff/format and strict mypy
passed before B1 edits. Existing working changes were the approved D0/A work;
they are preserved without a checkpoint commit.

**Verification:** Complete managed wrapper passed on 2026-09-05: 1,372 tests
(12 new B1 cases), 88% coverage, Ruff/format and strict mypy. Artifacts:
`.tmp/quality-runs/20260905085227957-30712-3c42b8c189bc4844b900b87a7269045e/`.
Tests prove fresh-connection pragmas, FK enforcement, durable commit, DML/DDL
rollback, snapshot reads during a committed write, rejected read-scope writes,
writer contention, lifecycle guards, sequential memory reuse, lazy construction,
and Windows file-handle release. Initial lint/format and typed Row comparison
findings were corrected before this green run. The project owner approved B1 on
2026-09-05 and explicitly authorized B2. No commit, migration, or dependency
change was made in B1.

**Implementation:** `SQLiteDatabase` in `src/data/repositories/sqlite.py`,
exported by the package, owns a lazy SQLAlchemy engine. File operations use
`NullPool` so each scope gets a fresh physical connection that is closed on exit.
The connector applies and verifies busy timeout, foreign keys, and WAL before
switching to Python 3.12+ modern transaction control. This follows the
[SQLAlchemy SQLite transaction guidance](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#enabling-non-legacy-sqlite-transactional-modes-with-the-sqlite3-or-aiosqlite-driver).
Parent directories are created on first connection, not construction.

`transaction()` owns commit/rollback, including DDL; `read()` owns a query-only
snapshot and rollback. Callers must not manually finish transactions or change
connection policy. `close()` is idempotent, rejects active scopes, and prevents
later reuse. File scopes may overlap; lock waiting is bounded by the typed
timeout. No provider/financial fallback or retry policy is added here.

Explicit in-memory URLs use `StaticPool`, report `memory` journal mode rather
than WAL, and reject overlapping scopes. These are sequential test helpers;
file-backed tests are the evidence for production concurrency. No application
tables, migration environment, schema metadata, repository methods, or sink
were added. Tables appearing in tests are disposable test-only fixtures.

**Purpose:** Establish one small reusable SQLite connection boundary.

**Likely files:** `src/data/repositories/sqlite.py`,
`src/data/repositories/__init__.py`, and
`tests/data/repositories/test_sqlite.py`.

**Required work:**

- construct/dispose the SQLAlchemy engine from typed settings;
- apply foreign-key, WAL, and busy-timeout policy to every connection;
- expose bounded transaction/read helpers rather than raw global connections;
- distinguish file-backed behavior from test-only SQLite edge cases; and
- test rollback, persistence across connections, effective pragmas, and clean
  resource release with a temporary file-backed database.

**Non-goal:** no tables, Alembic environment, repository, or sink.

**Focused gate:** targeted Ruff/format/mypy/pytest. Stop for review.

### Slice B2 — Alembic environment and empty bootstrap

**Authorization:** B1 approved and B2 explicitly authorized on 2026-09-05.
The complete baseline gate passed before edits: 1,372 tests, 88% coverage,
Ruff/format and strict mypy. Existing uncommitted D0/A/B1 changes were preserved.

**Implementation:** Repository-rooted `alembic.ini`, thin `alembic/env.py`,
revision template, documented empty `alembic/versions/`, and the typed
`src/data/repositories/migrations.py` helper. Migration connections use B1's
`SQLiteDatabase.transaction()` and its verified connection policy. No logging
configuration is installed. URL precedence is CLI `-x database_url=...`,
programmatic `sqlalchemy.url`, then `ProjectSettings`; all URLs undergo the
approved settings validation. Offline SQL generation is explicitly rejected.

**Verification:** Complete managed wrapper passed on 2026-09-05: 1,378 tests,
88% coverage, Ruff/format and strict mypy. Artifacts:
`.tmp/quality-runs/20260905085925456-11880-f62d7b7ba0804221a5b1e600037c448d/`.
Six new tests cover real CLI upgrade/repeated-upgrade/downgrade/re-upgrade,
environment/programmatic/CLI URL selection, percent-bearing paths and independent
cwd, preserved logging, effective migration pragmas, rollback on failure, resource
release, and offline-mode rejection. All databases are disposable test files.

**Review status:** The project owner approved B2 on 2026-09-05 and explicitly authorized
B3. At the B2 checkpoint there were no revision scripts or application tables;
`head` equaled `base`. The bootstrap created only an empty Alembic revision
table. Actual schema upgrade/downgrade belongs to B3 evidence. No commit or
dependency edit was made in B2.

Operator commands and restrictions are in the [migration README](../../../../../alembic/README.md).
The environment follows Alembic's [tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
and [connection-sharing guidance](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-with-a-series-of-migration-commands-and-environments).

**Purpose:** Make migrations use the reviewed URL and connection policy without
yet encoding the production schema.

**Likely files:** `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`,
`alembic/versions/`, a small migration helper if required, and focused tests.

**Required work:**

- create a non-interactive Alembic environment rooted in the repository;
- obtain the URL from project configuration while allowing CLI/test override;
- prevent logging configuration from overwriting application logging;
- prove `upgrade head`, `downgrade base`, and repeated `upgrade head` work on a
  temporary database; and
- document that migration commands run from the repository root.

**Non-goal:** no production tables beyond Alembic's own revision table.

**Focused gate:** migration lifecycle test plus targeted quality checks. Stop.

### Slice B3 — initial schema migration

**Authorization:** B2 approved and B3 explicitly authorized on 2026-09-05.
Complete baseline before edits: 1,378 tests, 88% coverage, Ruff/format and strict
mypy. Approved uncommitted D0/A/B1/B2 work is preserved.

**Verification:** Complete managed wrapper passed on 2026-09-05: 1,406 tests
(28 new schema cases), 88% coverage, Ruff check/format, and strict mypy. The
Alembic environment and revision also passed an explicit strict mypy check
outside the wrapper's `src`/`tests` roots. Artifacts:
`.tmp/quality-runs/20260905093316616-33372-779748655c9941418bbcda80a24bfc07/`.
Tests inspect metadata/migration equivalence (columns/types/nullability/defaults,
PKs, unique/FK/check constraints, indexes), exact D0 column/table inventory, and
the encoding seed. Actual CLI upgrade/repeated-upgrade/downgrade/re-upgrade
is covered, along with invalid-row rejection, duplicate identities, current
versus historical cache identities, snapshot isolation/cascade, exact integer
volume binding, and full rollback of a failed initial revision.

**Review status:** The project owner approved Slice B3 and Gate B on 2026-09-05,
closing the review of the D0 mapping, Core metadata, and frozen revision.
C1 has not started and may begin once the checkpoint commit is pushed.
No commit, dependency edit, or migration against user data was performed in B3.

**Implementation:** `src/data/repositories/schema.py` defines the five approved
Core tables; `alembic/versions/0001_persistence.py` independently freezes the
same columns, nullability, named constraints, and indexes. The revision never
imports mutable application metadata. The migration environment now receives
the Core metadata for schema comparison. Upgrade seeds only
`persistence_encoding_version = 1`; downgrade drops child tables before parents
and leaves Alembic's own empty version table at base.

Database checks cover positive integer versions/sequences, nonnegative integer
counts/positions, required nonempty identifiers, enum values, timestamp/date
storage shape and SQLite-recognized dates, paired ordered cache periods, and
request bounds. Full calendar/UTC validation, canonical JSON/key coherence,
finite numeric validation, and domain reconstruction remain adapter work as
approved in D0. No sink, cache implementation, or additional table is included.

**E1 precision handoff:** SQLite's approved NUMERIC volume column preserves
signed integers, but SQLAlchemy's default NUMERIC bind processor converts them
through float. E1 must explicitly select BigInteger versus Float bind parameters
from the retained frame dtype (and preserve native values on reads). B3 tests
the BigInteger binding path using `2**60 + 1`; do not use untyped NUMERIC insert
binding for integer volume. This is a binding requirement, not a schema change.

**Purpose:** Implement exactly the Gate D0-approved tables and indexes.

**Likely files:** one Alembic revision, one centralized SQLAlchemy Core metadata
module, and schema-focused tests.

**Required work:**

- define tables once in Core metadata and mirror them exactly in the revision;
- include database-level checks for positive sequences/schema versions,
  required identifiers, and valid cache timestamps where SQLite can enforce
  them safely;
- test table/index/constraint presence through inspection;
- test upgrade from empty, downgrade to empty, and upgrade again; and
- assert that unapproved Step 3.2–3.4/P2 tables do not appear.

**Gate B:** Human compares D0 mapping, metadata, and migration before adapter
work begins.

**Gate B outcome:** Approved on 2026-09-05. Commit and push the reviewed
checkpoint before starting C1; Step 3.1 remains in progress.

### Slice C1 — SQLite trajectory writes

**Authorization / baseline:** The project owner authorized C1 on 2026-09-05 after
checkpoint `1a59399` and comment cleanup `1117054` were committed and pushed.
The working tree was clean. The complete baseline passed with 1,406 tests,
88% coverage, Ruff/format, and strict mypy. Managed interpreter access required
elevated execution; caches and artifacts remained isolated in the repository.

**Implementation:** Added `SQLiteTrajectorySink` and its sink-package export.
The sink borrows an already-migrated `SQLiteDatabase`, commits each event
atomically, stores canonical nested JSON and aware UTC timestamps, preserves
every envelope field and sequence, and rejects unsupported/non-finite values.
Identical encoded event-ID retries are no-ops; conflicting identities fail
without modifying stored events. A write-first transaction handles concurrent
retries. Close is idempotent, rejects subsequent writes, and leaves disposal of
the shared database to its owner. Recorder sanitization and fail-open behavior
remain unchanged.

**Verification:** Complete managed wrapper passed on 2026-09-05: 1,420 tests
(14 new C1 cases), 88% coverage, Ruff/format, and strict mypy. Tests cover all
fields, UTC/canonical JSON encoding, sequence gaps, optional NULLs, immutable
conflicts, concurrent retries, invalid values, lifecycle/ownership, missing
schema failures, and recorder redaction/hash preservation and fail-open handling.
Artifacts: `.tmp/quality-runs/20260905142157175-30008-613046c86e334af6b7e6ec0884a72b2b/`.

**Review status:** The project owner approved C1 on 2026-09-05 and explicitly authorized
C2. No runtime selection, read/query API, dependency change, commit, push, or
migration against user data was performed in C1.

**Purpose:** Add the smallest sink that persists each validated event atomically.

**Likely files:** `src/core/telemetry/sinks/sqlite.py`, sink exports, and
`tests/core/telemetry/test_sqlite_sink.py`.

**Required work:**

- satisfy `TrajectorySink.record`, `flush`, and `close` structurally;
- preserve every `TrajectoryEvent` field and event order;
- reject or idempotently handle duplicate event IDs according to D0;
- make `close` idempotent and post-close writes explicit errors; and
- keep telemetry failure behavior fail-open at the recorder boundary.

**Non-goal:** read/query API or runtime configuration wiring.

### Slice C2 — trajectory reconstruction and runtime selection

**Authorization / baseline:** The project owner approved C1 and authorized C2 on
2026-09-05. Approved uncommitted C1 work was preserved. The complete managed
baseline passed with 1,420 tests, 88% coverage, Ruff/format, and strict mypy.

**Implementation:** Added `read_trajectory(database, run_id)` alongside the
SQLite sink and exported it from the sink package. It uses a consistent read
snapshot, checks persistence encoding version 1, reconstructs typed events in
ascending sequence, preserves gaps and NULLs, and rejects malformed encodings
instead of returning plausible partial results. The existing recorder
`from_settings` now selects SQLite when `telemetry_sink="sqlite"`; JSONL remains
the default. Runtime composition transfers ownership of its dedicated database
to the sink for disposal on close; injected databases remain borrowed by default.
SQLite construction is lazy, and the operator must migrate the database before
use. No automatic migrations, fallback sink, or SQLite retention/purge policy
was introduced. `telemetry_level="OFF"` creates no database file.

**Verification:** The complete managed wrapper passed on 2026-09-05: 1,436
tests (16 new C2 cases), 88% coverage, Ruff/format, and strict mypy. Equivalence
tests cover all ten event types in both Light and Full modes, out-of-order
arrival, sequence gaps, run isolation, and exact typed JSONL/SQLite equality.
Additional tests cover optional fields, unknown/missing encoding versions,
malformed JSON/UUIDs, non-finite values, default/runtime selection, resource
ownership, and lazy/OFF behavior. A real SQLite write lock proves fail-open
recording and successful subsequent persistence without renumbering the gap.
Artifacts: `.tmp/quality-runs/20260905143102609-39412-fe3ac32e266441878060a9764b65ab29/`.

**Review status:** The project owner approved C2 and explicitly authorized D1 on
2026-09-05, closing Gate C with the equivalence evidence and retained JSONL
default. No dependency edits, commit, push, or migration against user data was
performed in C2.

**Purpose:** Prove JSONL/SQLite equivalence and make the sink selectable.

**Likely files:** one trajectory readback helper/repository, telemetry
composition/settings wiring, and focused integration tests.

**Required work:**

- reconstruct a run in ascending sequence with exact typed equality;
- demonstrate representative JSONL and SQLite round trips yield the same event
  sequence;
- select JSONL or SQLite from typed settings without changing orchestration;
- verify recorder fail-open behavior for SQLite operational failures; and
- keep retention/purge policy out of this slice unless separately approved.

**Gate C:** Human reviews the equivalence evidence and runtime default.

### Slice D1 — scalar resolved-input cache

**Authorization / baseline:** The project owner approved C2 and authorized D1 on
2026-09-05. Approved uncommitted C1/C2 work was preserved. The complete managed
baseline passed with 1,436 tests, 88% coverage, Ruff/format, and strict mypy.

**Implementation:** Added `SQLiteResolvedInputCache` and its repository-package
export. Scalar `get`/`put` use the complete nine-member normalized key and the
approved relational mapping. Canonical lineage JSON preserves every component
field recursively, including cache/override metadata, ordered notes, enums,
and UTC timestamps. Existing domain constructors validate keys, inputs, and
entries through typed Pydantic adapters before writes and after reads; canonical
readback verification rejects corrupted or inconsistent encodings. Each put
atomically replaces the full row and resets `cached_at`. Historical availability
and injected-clock TTL eligibility match the in-memory implementation, including
boundary equality, zero/disabled TTL, and future cached times. Reads neither
delete stale rows nor relabel original provider/derived provenance. The database
is borrowed and must be migrated by its owner; storage failures remain explicit.

**Verification:** The complete managed wrapper passed on 2026-09-05: 1,478
tests (42 new D1 cases), 88% coverage, Ruff/format, and strict mypy. Tests cover
full provenance and recursive lineage, reopen durability, normalized identity
dimensions, current/historical separation, period identity, macro case,
replacement/NULL clearing, TTL and availability parity, rejected source kinds
and incoherent inputs, invalid clocks and non-finite values, corrupt storage,
encoding-version rejection, and rollback after a failing update trigger.
Artifacts: `.tmp/quality-runs/20260905145606922-39584-22cba3ff33144706a51a5b4b672514c6/`.

**Review status:** The project owner approved D1 and authorized D2 on 2026-09-05.
No series query, resolver/CLI composition, dependency change, commit, push,
or migration against user data was performed in D1.

**Purpose:** Implement `get`/`put` for complete scalar cache identities.

**Likely files:** `src/data/repositories/resolved_input_cache.py`, exports, and
one focused repository test file.

**Required work:**

- round-trip every `ResolvedInput` provenance field losslessly;
- preserve current versus historical `as_of` identity;
- implement deterministic replace/idempotency semantics from D0;
- enforce timezone, finite-number, key/input-coherence, source-kind, and TTL
  behavior through existing domain constructors; and
- prove instances sharing one database observe durable writes.

**Non-goal:** resolver or CLI composition.

### Slice D2 — period-series cache queries

**Authorization / baseline:** The project owner approved D1 and authorized D2 on
2026-09-05. Approved uncommitted C1/C2/D1 work was preserved. The complete
managed baseline passed with 1,478 tests, 88% coverage, Ruff/format, and strict
mypy before the cache extension.

**Implementation:** Added `SQLiteResolvedInputCache.get_series` using all seven
normalized query fields, SQL NULL equality, and period-scoped rows only. Reads
use a consistent database snapshot and the existing validated decoding path;
results are tuples ordered by period end, period start, and provider fact ID
(missing IDs sort as empty strings). Scalar and series reads share one
historical-availability/TTL eligibility helper. Original provenance and zero
values remain intact; empty/ineligible series return an empty tuple, and
corrupted storage raises an explicit error without returning partial results.

**Verification:** The complete managed wrapper passed on 2026-09-05: 1,528
tests (50 new D2 cases), 88% coverage, Ruff/format, and strict mypy. The shared
contract/resolver suite runs 24 cases against each of memory and SQLite,
covering query identity, normalization/UTC offsets, macro case, NULLs, ordering,
gaps, unscoped exclusion, replacement, scalar preservation, TTL boundaries,
per-entry age, historical availability, and naive clocks. Deterministic annual
resolver scenarios prove complete-cache hits avoid providers and partial/stale
caches refresh all required fields. Two SQLite-specific tests reject corrupt
series rows and unsupported encoding versions without partial results.
Artifacts: `.tmp/quality-runs/20260905221445472-31604-b008f276cdf544d088c4d43e49a5697f/`.

**Review status:** The project owner completed Gate D review, approved D2, and authorized
E1 on 2026-09-05. No production resolver/CLI composition, dependency change,
commit, push, or migration against user data was performed in D2.

**Purpose:** Add `ResolvedInputSeriesCacheProtocol.get_series` without changing
scalar behavior.

**Required work:**

- match the existing query normalization and eligibility semantics;
- return the same deterministic ordering as `InMemoryResolvedInputCache`;
- cover provider, basis, period-bound, `as_of`, schema-version, and TTL edges;
- add a contract test parametrized over in-memory and SQLite implementations;
  and
- demonstrate no silent zero/default substitution.

**Gate D:** Run the focused resolver/cache suite against both implementations.

### Slice E1 — historical-series schema adapter

**Authorization / baseline:** The project owner completed Gate D review, approved D2,
and authorized E1 on 2026-09-05. Approved uncommitted C1/C2/D1/D2 work was
preserved. The complete managed baseline passed with 1,528 tests, 88% coverage,
Ruff/format, and strict mypy before implementation.

**Implementation:** Added `MarketDataCacheKey`, `MarketDataCacheEntry`, and
`SQLiteMarketDataRepository` with repository-package exports. Request identity
normalizes ticker/provider, retains calendar bounds and explicit variant/version,
and distinguishes open-ended and overlapping snapshots. Writes validate the
approved finite OHLCV frame shape and its reconstruction before atomically
replacing parent metadata and all child rows. Reads validate parent and children
from one database snapshot. Context, cache/fetch timing, column order/dtypes,
axis names, date/datetime index semantics, timezone, frequency, and datetime
units are retained. Axis-name encoding supports finite JSON scalars or None;
unsupported custom names raise explicitly. Optional columns remain absent,
and absent fetch timing is not invented. Integer prices must survive REAL
storage exactly; volume uses explicit BigInteger/Float binding so signed int64
values are never routed through SQLAlchemy's default NUMERIC float conversion.
Unsupported shapes raise `UnsupportedHistoricalDataError`; invalid observations
and corrupted storage raise explicit errors. The database remains caller-owned.

**Verification:** The complete managed wrapper passed on 2026-09-05: 1,580
tests (52 new E1 cases), 88% coverage, Ruff/format, and strict mypy. Tests cover
all context fields, reopen durability, signed int64 volume extrema and
`2**60 + 1`, exact integer prices, float volume, optional columns, Python dates,
naive/named-zone/fixed-offset datetime indexes in s/ms/us/ns, nanosecond/DST and
frequency retention, request identity, replacement and overlap isolation,
unsupported/invalid frames, corrupt metadata/rows, timing/version validation,
and rollback after a child insert fails. A deterministic concurrent replacement
between parent and child reads proves snapshot consistency.
Artifacts: `.tmp/quality-runs/20260905224451744-40724-ccabc0246a16416ea51e40ebe77e6480/`.

**Review status:** The project owner completed the E1 review, described as Gate E review,
approved E1, and authorized E2 on 2026-09-05. E2 acceptance evidence is recorded
below for review before F1.

**Purpose:** Round-trip one `HistoricalMarketData` series without provider
fetching or fallback.

**Likely files:** one market-data repository module and one focused test file.

**Required work:**

- normalize ticker/provider/request bounds and persist OHLCV observations plus
  `MarketDataContext` metadata;
- preserve index timezone/date semantics, column names/order, numeric values,
  observation count, adjustment basis, currency, interval, data `as_of`, and
  retrieval metadata where available;
- define overlap/upsert behavior from D0; and
- reconstruct an equivalent DataFrame with deterministic ordering/dtypes.

**Non-goal:** no live yfinance call and no `BaseDataClient` decorator.

### Slice E2 — cache-backed historical client

**Authorization and baseline:** E1 approved and E2 authorized on 2026-09-05.
The complete baseline passed: 1,580 tests, 88% coverage, Ruff/format, and strict
mypy. Approved uncommitted work was preserved.
Baseline artifacts: `.tmp/quality-runs/20260905230027064-38288-18c4304619ef4f5d8ec009bd98269da5/`.

**Implementation:** `CachedHistoricalDataClient` borrows an injected provider
and repository. Exact normalized request keys reuse eligible snapshots with
an explicitly injected TTL (equality eligible, zero valid, None disables expiry,
future timestamps retained). Other ranges refetch in full. Provider context and
local fetch-completion timing are preserved; failed refreshes leave prior
snapshots untouched without stale fallback. Empty/non-finite/nonnumeric financial
observations raise explicit errors, including for unsupported frames. Unknown
provider/configuration identities and valid unsupported frames bypass storage
with diagnostics. All historical entry points share caching; quotes delegate
directly to the provider. Production composition remains for F1/F2.

**Verification:** The complete managed gate passed on 2026-09-05: 1,599 tests
(19 new E2 cases), 88% coverage, Ruff/format, and strict mypy. Deterministic
fake-provider tests prove miss/hit across all historical boundaries, reopen
reuse, context/timing retention, TTL equality/zero/disabled/future boundaries,
range/provider/variant isolation, failed-refresh snapshot preservation,
empty/missing/non-finite/nonnumeric rejection, diagnostic bypasses, independent
quotes with closed storage, and invalid TTL/clock rejection.
Artifacts: `.tmp/quality-runs/20260905230656847-35944-15fa5ebb82c645e592d6d4af952f85a2/`.

**Review status:** The project owner reviewed and approved E2 on 2026-09-06, closing
Gate E, and authorized F1. No dependency
change, live provider call, commit, push, or migration against user data.

**Purpose:** Put durable caching behind `BaseDataClient` without pretending a
historical observation is a current quote.

**Required work:**

- compose a narrow cache-backed client/decorator around an injected provider;
- use a valid eligible cached range without an external refetch;
- fetch on miss, persist only validated results, and preserve provider context;
- specify partial-range behavior explicitly (initially a full refetch is safer
  than silently stitching incompatible series); and
- keep `fetch_current_price` delegated to the real quote boundary, never the
  historical cache.

**Gate E:** deterministic fake-provider tests prove hit, miss, provider error,
empty/invalid data, and current-quote separation.

### Slice F1 — production financial-cache composition

**Authorization and baseline:** E2 approved and F1 authorized on 2026-09-06,
closing Gate E. The baseline passed: 1,599 tests, 89% coverage, Ruff/format,
and strict mypy. Approved uncommitted work was preserved.
Baseline artifacts: `.tmp/quality-runs/20260906070555410-28864-8d72d314061649f180135e58bf5f546f/`.

**Implementation:** CLI Graham and FCF analyses inject a scoped
`SQLiteResolvedInputCache` using configured database settings. The invocation
owns and closes the database on success and exception. Financial cache TTL
remains disabled, preserving the existing policy and resolver temporal checks.
`--no-cache` bypasses reads/writes without opening SQLite. Explicit in-memory
injection remains supported; deterministic CLI fixtures opt into that path.
Schema upgrades remain explicit; production never creates or migrates tables.
Provider selection, fact validation, lineage, and resolver rules are unchanged.

**Verification:** The complete managed gate passed on 2026-09-06: 1,605 tests
(six new F1 cases), 88% coverage, Ruff/format, and strict mypy. New deterministic
tests exercise two fresh CLI compositions against a migrated temporary file
database, reuse without provider fact access for Graham and FCF, preserved
provenance and cache-hit traces, no-cache behavior without a database, explicit
memory-cache injection, and ownership on success/error. Optional instrument-profile
lookup is stubbed independently; fact-cache reuse does not claim that live
profile enrichment is cached.
Artifacts: `.tmp/quality-runs/20260906071108663-24392-7b30314dd06e47cdb9f7239fd2c2815a/`.

**Review status:** The project owner reviewed and approved F1 on 2026-09-06 and
authorized F2. No dependency changes, live provider calls, commit, push, or
migrations against user data were performed.

**Purpose:** Select the durable resolved-input cache in production composition
without changing resolver rules.

**Required work:**

- inject the SQLite cache at existing Graham and FCF resolver construction
  seams;
- retain explicit in-memory/test injection paths;
- prove a first deterministic fake-provider analysis populates the cache and a
  second process-equivalent composition reuses it without provider access; and
- verify all result provenance and resolution traces remain truthful.

### Slice F2 — production historical-cache composition

**Authorization and baseline:** The project owner approved F1 and authorized F2 on
2026-09-06. The complete baseline passed: 1,605 tests, 88% coverage,
Ruff/format, and strict mypy. Approved uncommitted work was preserved.
Baseline artifacts: `.tmp/quality-runs/20260906071818161-41780-a5d70acc0f8e41b4976c000e8535d779/`.

**Implementation:** The Momentum CLI injects `CachedHistoricalDataClient`
around its existing Yahoo client. A scoped database/repository closes after
analysis on success or error. Request variant is the provider's daily adjusted
configuration; TTL comes from `historical_cache_ttl_seconds` (default one hour,
None disables expiry, zero permits no positive age). Profile enrichment retains
the original Yahoo client. Direct analyzer/custom-provider injection and the
financial-fact composition remain unchanged. Migrations remain explicit.

**Verification:** The complete managed gate passed on 2026-09-06: 1,614 tests
(nine new F2 cases), 88% coverage, Ruff/format, and strict mypy. Tests cover repeated CLI
analysis with one historical fetch, equivalent results/context, original-client
profile enrichment, configured TTL boundaries, direct quote delegation after
storage closes, exception cleanup, and unchanged custom-client injection.

Artifacts: `.tmp/quality-runs/20260906072116390-7072-dd7bccc7110a44cd98492b1312468e2e/`.

**Review status:** The project owner approved F2 and authorized G on 2026-09-06.
No dependency changes, live provider calls, commit, push, or migrations against
user data were performed.

**Purpose:** Select the cache-backed historical client for Momentum.

**Required work:**

- wire only the existing production construction seam;
- keep direct custom/test client injection unchanged;
- prove miss-then-hit behavior with deterministic fake data; and
- confirm current-price and fundamental provider paths are unaffected.

### Slice G — operator workflow, integration proof, and closeout

**Authorization and baseline:** F2 approved and G authorized on 2026-09-06.
The complete baseline passed: 1,614 tests, 88% coverage, Ruff/format, and
strict mypy. Approved uncommitted work was preserved.
Baseline artifacts: `.tmp/quality-runs/20260906072424398-33008-34ebfea7161543bba36eac9526b16068/`.

**Implementation:** `docs/user/DATABASE.md` documents locked dependency sync,
explicit migration upgrade/current/history and destructive downgrade, database
URL precedence/overrides, historical and financial cache policy, telemetry
selection, WAL-aware backup/restore, failed-migration recovery, and managed
offline verification. Installation, quick-start, user index, and smoke-test
instructions link the required workflow; FCF cache-option wording is corrected.
No planning labels were added to user guides or test code.

The integrated persistence smoke test creates a fresh temporary database,
upgrades twice, writes representative telemetry, a resolved financial fact,
and a historical frame, closes/reopens storage, proves exact context/provenance
and frame readback, checks integrity/foreign keys, and downgrades/re-upgrades
to empty stores. Socket connections are blocked during this smoke test.

**Verification:** The complete managed gate passed on 2026-09-06: 1,615 tests
(one new integrated smoke case), 88% coverage, Ruff/format, and strict mypy.
Artifacts: `.tmp/quality-runs/20260906072749753-34980-3589043429f44d90bb4c82893bb0f00b/`.
Existing migration tests also
cover CLI upgrade/repeat/downgrade/re-upgrade and failed-DDL rollback. No live
provider or LLM checks were performed; the deterministic tests use synthetic
fixtures and mocks. Git's tracked-file audit found no databases, SQLite sidecars,
JSONL logs, or environment files. Representative database/sidecar/log paths are
ignored. Documentation and patch whitespace were inspected.

**Review status:** The project owner approved Slice G on 2026-09-06, closing Gate G
and completing Step 3.1. The subsequent shared-documentation generalization is
included in the closeout. P2, Step 3.2, and all other subsequent planning work
remain unstarted; this approval does not authorize starting them. No dependencies
were installed, no user database was migrated, and no commit or push was made.

**Purpose:** Complete the fresh-database workflow and Step 3.1 evidence.

**Required work:**

- document dependency synchronization, migration upgrade/downgrade, database
  location override, backup implications of WAL sidecars, and recovery from a
  failed local migration;
- add a fresh-database smoke test covering migration, representative telemetry,
  resolved financial input, and historical series round trips;
- verify no network/LLM call occurs in tests and no database artifact is tracked;
- run the complete managed-agent quality-gate wrapper; and
- update the implementation plan/status only from reviewed evidence.

**Gate G:** Human reviews the complete diff, migration lifecycle, smoke-test
output, coverage, and full quality-gate output. Do not begin P2 or Step 3.2.

## 6. Verification matrix

| Concern | Minimum evidence |
| :--- | :--- |
| Migration lifecycle | Clean upgrade, repeated upgrade, downgrade, re-upgrade |
| SQLite policy | Fresh file connection reports WAL, foreign keys on, configured busy timeout |
| Atomicity | Forced write failure rolls back the whole operation |
| Telemetry | Typed event equality and ordered JSONL/SQLite reconstruction |
| Financial cache | Shared contract tests for scalar and series behavior, including TTL/as-of |
| Historical cache | DataFrame/context round trip; hit avoids provider; miss persists |
| Provenance | Provider, source kind, dates, lineage, cache schema, and notes preserved |
| Isolation | Temporary file databases; no live provider, Ollama, or user database |
| Repository health | Focused checks per slice and complete wrapper at Gate G |

## 7. Local-model execution protocol

The Step 2.5 experiment showed that Qwen3-Coder 30B could pass a tool smoke test
yet still omit required artifacts and falsely report successful checks. For
Step 3.1, local-model output is therefore treated as an untrusted draft until
independently verified.

For every slice:

1. Start a fresh task in Plan mode and supply only the slice, named contracts,
   file allowlist, and stop condition.
2. Require a read-only plan listing exact files, tests, and assumptions. Approve
   before Act mode.
3. Enable automatic approval only for bounded read/search and explicitly named
   non-mutating checks. Keep edits and commands that mutate dependencies,
   migrations, Git, or external state under manual approval.
4. Require post-edit read-back of every changed file and an explicit checklist
   matching each requested artifact to a path and test.
5. Independently inspect the diff and rerun the focused gate. Ignore prose claims
   that are not supported by files and command output.
6. Reject the slice if it changes files outside the allowlist, invents a
   dependency, creates a second abstraction, weakens an assertion, or skips a
   required test.
7. Begin the next slice only after human approval; use a new task so stale
   context cannot contaminate the next change.

### 7.1 Current model recommendation review (2026-09-03)

There is no evidence-based reason to promote a new local model directly into
the Step 3.1 implementation role without a bakeoff:

- Cline's current local-model guide still recommends Qwen3-Coder 30B, and
  Ollama reports improved tool calling for that model. Repository evidence on
  this host is nevertheless stronger for this workflow: the tested model
  repeatedly produced incomplete work and false success reports. It is not the
  default Step 3.1 implementer.
- Qwen3-Coder-Next is a newer agentic-coding candidate with tool support and a
  256K native context, but Ollama's Q4_K_M artifact is about 52 GB. It is not a
  drop-in replacement for the previously documented 24–28 GB GPU target.
- Ollama now lists `glm-4.7-flash`, Qwen3-Coder, and `gpt-oss:20b` among local
  coding candidates and estimates about 23 GB VRAM for GLM-4.7-Flash at 64K.
  These are candidates, not project recommendations, until they complete the
  same repository-specific slice and verification protocol.

**Step 3.1 primary bakeoff model:** Use the exact local Ollama model tag
`glm-4.7-flash`. This is the intended model wherever this plan instructs the
operator to pull, load, run, or configure the Step 3.1 local implementation
model. It is a bakeoff candidate, not an approved implementation model. Do not
substitute the historical `financial-data-agents-step-2-5` alias, the
application runtime alias `financial-data-agents`, or a cloud model. Promote
`glm-4.7-flash` only after it completes two consecutive independently verified
micro-slices under Section 7.

If local-model implementation is desired, run a disposable bakeoff using Slice
B1 or another comparably bounded, independently specified task. Test at most
two candidates against the identical prompt, clean starting state, context,
and checks. Score artifact completeness, forbidden-file changes, test accuracy,
and truthfulness of the completion report—not prose quality. Promote a model
only after two consecutive accepted micro-slices.

Primary references:

- [Cline local-model overview](https://docs.cline.bot/running-models-locally/overview)
- [Ollama coding-tool recommendations](https://ollama.com/blog/launch)
- [Ollama Qwen3-Coder-Next model record](https://ollama.com/library/qwen3-coder-next)
- [Ollama context and K/V cache guidance](https://docs.ollama.com/faq)

### 7.2 Current Cline recommendation

- Use the native Ollama provider URL without `/v1` and match Cline's advertised
  context exactly to the context Ollama actually allocates.
- Use a fresh task per slice, Plan then Act, checkpoints enabled, web/MCP/hooks
  disabled unless the slice explicitly requires them.
- Enable compact prompts if the installed Cline version exposes a functioning
  control. If it does not, do not chase a stale setting; fresh tasks and narrow
  file reads remain the prompt-size control.
- Do not auto-approve project edits, dependency changes, migrations, or Git
  operations. Auto-approve may cover bounded reads/searches and named
  non-mutating checks only.
- A smoke task must include one edit, file read-back, and a deliberately failing
  focused check whose failure the model must report accurately. Read/command
  tool syntax alone does not establish implementation reliability.

### 7.3 Current Ollama recommendation

Keep the proven conservative operating shape for a coding-agent bakeoff. The
names below describe environment variables; they are not commands that can be
entered as `NAME=value` in PowerShell.

For the normal Ollama Windows desktop installation, use this complete procedure
on the machine that runs the Ollama server:

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_CONTEXT_LENGTH", "65536", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_FLASH_ATTENTION", "1", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_KV_CACHE_TYPE", "q8_0", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_NUM_PARALLEL", "1", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_MAX_LOADED_MODELS", "1", "User")
[Environment]::SetEnvironmentVariable("OLLAMA_NO_CLOUD", "1", "User")
```

Then:

1. In the Windows notification area/system tray, right-click Ollama and choose
   **Quit Ollama**. `ollama stop` is not a server-stop command; it requires a
   model name and only unloads that model.
2. Confirm that no process owns the Ollama port:

```powershell
Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue
```

3. If the command still returns a listener, inspect it before stopping anything:

```powershell
$ollamaListener = Get-NetTCPConnection -LocalPort 11434 -State Listen | Select-Object -First 1
$ollamaProcess = Get-Process -Id $ollamaListener.OwningProcess
$ollamaProcess | Format-List Id, ProcessName, Path
```

   Only if the displayed process is Ollama, stop that exact process and confirm
   the port is free:

```powershell
Stop-Process -Id $ollamaProcess.Id
Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue
```

4. Start Ollama from the Windows Start menu. This is the server; do not also run
   `ollama serve`, because a second server cannot bind the same port.
5. Open a new PowerShell window and verify that the API is available:

```powershell
Invoke-RestMethod http://localhost:11434/api/version
ollama list
```

6. Pull and load the Step 3.1 primary bakeoff model, whose exact model tag is
   `glm-4.7-flash`:

```powershell
ollama pull glm-4.7-flash
ollama run glm-4.7-flash "Reply only with OK."
```

7. While `glm-4.7-flash` remains loaded, verify the effective context and
   processor placement in another terminal:

```powershell
ollama ps
```

The `ollama ps` row for `glm-4.7-flash` must report a 65,536-token context and
the intended GPU placement before the bakeoff begins. Configure Cline's Ollama
provider with model ID `glm-4.7-flash`, context window `65536`, and the server's
base URL without an OpenAI `/v1` suffix. Do not infer success from idle GPU
memory or from `ollama list`; `ollama ps` must be sampled while this model is
loaded.

### 7.4 Step 3.1 local-model preflight record

| Date | Model tag and ID | Allocation | Processor | Context | Result |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-09-03 | `glm-4.7-flash:latest` / `4475827791a2` | 21 GB | 100% GPU | 65,536 | Ollama placement/context pass; Cline edit-and-report preflight passed; D0 authorized |

This row proves only server allocation. Before D0 or Slice A is delegated, the
same model must pass the Cline preflight below in a fresh task:

1. Read `AGENTS.md` and report its first heading exactly.
2. Create the ignored file `.tmp/cline-step-3-1-preflight/artifact.txt` with the
   exact single line `step-3.1 preflight`.
3. Read the file back and report its exact content.
4. Run `git status --short` and report the result without claiming the ignored
   preflight file is tracked.
5. Run `git rev-parse --verify refs/heads/definitely-not-a-real-branch`, which
   is intentionally expected to fail, and report the non-zero result as an
   expected failure rather than claiming all commands passed.
6. Stop without changing any tracked file, installing anything, committing, or
   beginning a Step 3.1 slice.

The project owner confirmed on 2026-09-03 that the Cline preflight passed: the ignored
artifact was created and read back, tracked-file status remained accurate, and
the intentionally failing Git command was reported truthfully. This permits D0
planning only; it does not yet promote the model or authorize production code.

For a temporary manual server instead of the desktop application, first quit
the tray application and confirm port 11434 is free. Then set the same values
with `$env:NAME = "value"` in one PowerShell window and run `ollama serve` in
that window. Leave it open; closing it stops that manual server.

Already-running processes do not receive changed environment values. If Cline
connects to a different LAN machine, perform this procedure on that server,
not on the Cline workstation. Omit `OLLAMA_NO_CLOUD` if that installation
should retain access to Ollama cloud models.

`q8_0` remains Ollama's recommended lower-memory K/V cache alternative to
`f16`. Do not configure numeric `CUDA_VISIBLE_DEVICES`, experimental Vulkan, or
hard-coded `num_gpu` merely to force placement. First confirm that the current
server discovers the intended GPU(s), then sample `ollama ps` while generation
is active. Accept the preflight only when the allocated context matches Cline
and the intended processor placement is shown. If 64K does not remain resident,
reduce both sides together to 49,152 and then 32,768; do not let Cline advertise
more context than the server supplies.

## 8. Environment preparation (human-run)

Dependency changes require explicit authorization. Installing the dependencies
does not create an Alembic migration environment; `alembic upgrade head` and
`alembic current` become valid only after Slice B2 has added and verified
`alembic.ini` and the migration script directory.

From the repository root in PowerShell:

```powershell
git status --short
uv add "sqlalchemy>=2.0,<3" "alembic>=1.13,<2"
```

Use `uv add` so `pyproject.toml` and `uv.lock` change together. Review both
files before accepting the dependency slice. Never install with ad-hoc global
`pip`, and never commit the generated SQLite database.

After Slice B2 is implemented and approved, initialize a temporary database
through the repository's reviewed Alembic configuration:

```powershell
uv run alembic upgrade head
uv run alembic current
```

For a temporary smoke database, set the eventual environment variable only for
the current PowerShell process, using the exact variable name introduced in
Slice A, then run the migration and smoke command documented by Slice G. Do not
reuse the production database for migration tests.

## 9. Completion criteria

Step 3.1 is complete only when all slices and Gates D0–G are approved, the full
quality gate passes, the fresh-database workflow is reproducible, JSONL and
SQLite trajectory reconstruction are equivalent, cache hits preserve temporal
and provenance semantics, and no later-step schema or behavior has leaked into
the implementation.
