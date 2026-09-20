# Slice I1 — Completion evidence (Amendment A1)

**Review disposition:** accepted (2026-09-19).
**Date:** 2026-09-19 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

First slice of [Contract Amendment A1](STEP_3_4_CONTRACT_AND_SLICE_PLAN.md#12-contract-amendment-a1--watchlist-entry-model),
authorized after H's own review of `docs/user/WORKSPACE.md` surfaced that
the original members/selections watchlist model produced poor user
experience (arbitrary default selections, no per-ticker or multi-provider
selections, a file-based configuration mechanism). This slice replaces the
data model, repository, and migration; I2 (CLI surface) and I3 (docs, full
regression, final acceptance) follow.

## Model change

`src/workspace/runs.py`: `Watchlist.members`/`Watchlist.selections` are
replaced by one `entries: tuple[WatchlistEntry, ...]` field, where
`WatchlistEntry = {ticker, selection}`. An entry's position is its index
within the tuple — mirroring how the superseded `members`/`selections`
tuples never carried an explicit position field either. The former
"distinct method_id" and "unique members" invariants are removed: the same
method may now appear more than once, whether for different tickers or the
same ticker with a different provider/configuration (the concrete
capability the amendment exists to unlock — e.g., Graham Number via SEC
EDGAR next to Graham Number via Massive, on the same watchlist).
`WatchlistSummary.member_count`/`.selection_count` become one
`entry_count`.

`src/workspace/requests.py`: `default_selections()` is removed entirely
(and its re-export from `src/workspace/__init__.py`); a freshly created
watchlist now has zero entries, full stop — there is no default set of
methods to materialize.

## Repository

`src/data/repositories/watchlists.py` is rewritten around the entry model:

- `create()` creates an empty watchlist (no seeding — I2 decides how the
  CLI exposes seeding at creation time, if at all, by composing `create()`
  with the new `add_entries()` below).
- `add_entries(name, entries)` appends one entry per given `(ticker,
  selection)` pair after the current highest position — the fan-out
  primitive I2's `add-selection` command will call for its "one method,
  many tickers" case.
- `remove_entry(name, position)` removes exactly one entry by its stored
  0-based position, raising a new `WatchlistEntryNotFoundError` if no entry
  exists there (unlike the bulk removals below, an explicit index that does
  not exist is treated as a caller error, not an idempotent no-op).
- `remove_entries_for_ticker(name, tickers)` / `remove_entries_for_method(name, method_id)`
  remove every matching entry in bulk, idempotently for an absent
  ticker/method — preserving the old `remove_members`/`disable_selection`
  bulk convenience under the new model.
- Every removal renumbers the survivors contiguously from zero (delete
  everything for the watchlist, then reinsert the survivors with fresh
  positions) rather than leaving gaps, which the superseded
  `remove_members` did allow. This is a deliberate, new requirement: the
  contract amendment fixes `displayed index = position + 1` as the
  user-facing addressing scheme, which only stays correct if stored
  positions never develop gaps.

## Persistence

New migration `0003_watchlist_entries` replaces `watchlist_members`/
`watchlist_selections` with one `watchlist_entries` table —
`(watchlist_id, position)` primary key (position uniqueness is the primary
key itself now, not a separate constraint), `ticker`, `method_id`,
`config_schema_version`, `selection_json` columns, matching the existing
schema's check-constraint conventions exactly.

Upgrade is lossless: every existing watchlist's member-position-then-
selection-position cross product becomes its entries list, in that exact
order — a watchlist created under the superseded model replays identically
after upgrade. Downgrade first verifies every watchlist's entries still
form a clean ticker x selection cross product (every ticker paired with
every selection, each method configured identically across every ticker
that has it); a watchlist that has since diverged — the defining new
capability this amendment adds — cannot be represented in the old shape at
all, so downgrade raises rather than silently dropping or corrupting data,
matching C1's own "reject rather than corrupt" convention.

## I1/I2 boundary: `cli_workspace.py`

Discussed and authorized by the project owner before implementation (see
§12's boundary-clarification note): `watchlist add`/`remove`/`configure`/
`disable` called repository methods with no coherent meaning once a ticker
only exists as part of an entry. Rather than leave them calling a deleted
method or build a throwaway interim semantic, this slice removes those four
commands outright. `create`/`list`/`show` remain, adapted to render
`.entries` (`show` numbers entries from 1, matching the amendment's
"1-based to the user, 0-based in storage" addressing rule); `_ANALYSIS_ALIASES`/
`_watchlist_alias`, `parse_selection`'s only CLI caller, and the
now-orphaned `WatchlistNotFoundError` import were removed rather than left
as dead code. `refresh_watchlist` (G1) changes by one line — the job list
is read directly from `watchlist.entries`. G2/G3/D1-D5/E1-E4 are
untouched.

## Tests

- `tests/workspace/test_runs.py`: `_base_watchlist()`/tests rewritten for
  `entries`; the two duplicate-rejection tests are replaced by
  `test_duplicate_ticker_and_method_pair_is_allowed`, proving the new
  capability directly rather than just removing the old constraint's test.
- `tests/data/repositories/test_watchlist_repository.py`: full rewrite (23
  tests) covering `create`/`list`/`add_entries`/`remove_entry`/
  `remove_entries_for_ticker`/`remove_entries_for_method`, idempotence,
  validate-before-write, position renumbering (including emptying a
  watchlist entirely), the new same-method-twice capability, reopen, and
  offline/no-network access.
- `tests/data/repositories/test_schema.py`, `test_migrations.py`: updated
  for the new table/column shape and the `0003_watchlist_entries` head
  revision; `test_watchlist_entries_enforce_order_and_cascade` proves the
  PK itself now enforces position uniqueness and cascade delete still
  works.
- `tests/workspace/test_refresh.py`: `_watchlist(members, selections)`
  helper now builds the cross product as explicit entries internally, so
  G1-G3's own 29 tests (admission, cancellation, persistence) are
  unaffected — they exercise the execution service given a job list, not
  the watchlist model.
- `tests/test_cli_workspace.py`: the add/remove/configure/disable tests are
  removed (the commands are gone); `create`/`show` tests updated for the
  new empty-by-default, entries-based behavior.
- `tests/test_cli_refresh.py`, `tests/test_workspace_integration.py`: their
  own watchlist setup switched from CLI commands to direct repository
  seeding (`SQLiteWatchlistRepository.add_entries` against the same
  isolated database `isolated_cli_database` already points the CLI at),
  since the commands they used no longer exist; the refresh/replay behavior
  each test actually exercises is unchanged.

## Full managed gate

Ruff, Ruff format, and strict mypy passed clean. The full pytest run:
**3,056 passed**, combined coverage **91%**; `src/cli_workspace.py`,
`src/data/repositories/watchlists.py`, `src/data/repositories/schema.py`,
and `src/workspace/runs.py` all reach 100% line/branch coverage.

## Boundaries

I2 (CLI surface: `add-selection`, `remove-entry`, repurposed `remove`/
`disable`, `show --group-by`) and I3 (docs, full regression, final
acceptance) are the next slices, not part of this checkpoint. Nothing was
committed, pushed, or opened as a PR.
