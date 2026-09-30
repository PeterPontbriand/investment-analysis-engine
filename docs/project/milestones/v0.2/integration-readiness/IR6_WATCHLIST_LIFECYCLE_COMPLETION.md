# IR.6 — Watchlist Lifecycle Completion

Closes the watchlist lifecycle gap that Step 3.4 Amendment A1 deferred
([`STEP_3_4_CONTRACT_AND_SLICE_PLAN.md`](../step-3.4/STEP_3_4_CONTRACT_AND_SLICE_PLAN.md) §12,
"Deferred, not included in this amendment"). Scope and decisions approved by the project owner
2026-09-27; branching revised 2026-09-29 (see [Appendix B](#appendix-b-decision-records)).
Implementation is not yet authorized.

## 1. At a glance

- **What IR.6 is:** a complete watchlist lifecycle for agentic and human CLI callers: delete, rename,
  unambiguous removal verbs, and one method vocabulary (the hyphenated aliases) in human-readable text
  and command input.
- **What it is not:** no schema change or Alembic migration, no analysis formula, classification,
  result or run-envelope change, and no `--json` payload change (`method_id` stays canonical there).
- **Rules it follows:** the full managed gate and at least 85% coverage after each sub-slice, explicit
  authorization before the next sub-slice, and `AGENTS.md` §0 (old command names are removed outright,
  with no aliases or shims).
- **It depends on IR.2.** IR.2.6 changed the watchlist removal commands, their error handling and
  their confirmation text, so IR.6 branches off `main` after `feat/ir-integration-readiness` has
  merged, not before.
- **Decisions:** D1 to D5 are recorded verbatim in [Appendix B](#appendix-b-decision-records), and D6
  (mutations commit without decoding stored entries) follows them there.

## 2. Sequence and status

Three sub-slices on one branch, in this order. Vocabulary goes first, so delete and rename are
written once, in final command names and final text vocabulary.

| Slice | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| IR.6.1 | [Command vocabulary](#ir61--command-vocabulary) | Planned | |
| IR.6.2 | [Delete](#ir62--delete) | Planned | |
| IR.6.3 | [Rename](#ir63--rename) | Planned | |

## 3. The slices

### IR.6.1 — Command vocabulary

- **Problem:** `watchlist remove` removes tickers and `watchlist disable` removes a method's entries,
  which is ambiguous beside a future `delete`; `runs list --method` needs the canonical `method_id`
  while watchlist commands use aliases; and text output prints canonical ids.
- **Decision:** D1 and D4. `remove` becomes `remove-ticker`, `disable` becomes `remove-method`,
  `runs list --method` becomes `runs list --analysis ALIAS`, and human-readable text prints aliases.
  This includes the removal confirmation lines and the retired-selection error IR.2.6 added.
- **Scope:** `src/cli_workspace.py` commands and text renderers, the repository's
  `StoredSelectionError` builder, `WORKSPACE.md`, `GLOSSARY.md`, and their tests.
- **Branch:** `fix/ir6-watchlist-lifecycle`, off `main` after `feat/ir-integration-readiness` merges.
- **Detail:** [A.1](#a1-ir61--command-vocabulary).

### IR.6.2 — Delete

- **Problem:** neither `ian watchlist` nor `SQLiteWatchlistRepository` can delete a watchlist, so a
  scratch watchlist can never be cleaned up.
- **Decision:** D2 and D3. `ian watchlist delete NAME [--yes] [--missing-ok] [--json]`, with a prompt
  when interactive, a usage error when not and `--yes` is absent, and `--missing-ok` for idempotent
  cleanup. Per D6, delete commits without decoding any stored entry.
- **Scope:** repository `delete`, the CLI command, `WORKSPACE.md`, and tests.
- **Branch:** as IR.6.1.
- **Detail:** [A.2](#a2-ir62--delete).

### IR.6.3 — Rename

- **Problem:** a watchlist's display name is fixed at creation.
- **Decision:** `ian watchlist rename NAME NEW_NAME [--json]`, without confirmation because it is not
  destructive. Per D6, rename commits without decoding any stored entry.
- **Scope:** repository `rename`, the CLI command, `WORKSPACE.md`, and tests.
- **Branch:** as IR.6.1.
- **Detail:** [A.3](#a3-ir63--rename).

## 4. Out of scope

- Any analysis, formula, classification, result, run-envelope or persisted-schema change.
- Any `--json` payload change, and any change to canonical `method_id` values.
- Renaming `watchlist remove-entry`, which IR.2.6's retired-selection error names by its current name.
- Changes to saved Analysis Runs; delete and rename never touch them.

## 5. Acceptance criteria

- No change to any analysis formula, classification, result, run envelope, persisted schema, or
  `--json` payload. No Alembic migration; the head revision is unchanged.
- Human-readable workspace text changes only as A.1 specifies, and the change is recorded in the
  [IR contract](IR_CONTRACT_AND_SLICE_PLAN.md) §4.
- `delete` and `rename` commit even when other stored entries cannot be read, and any display that needs
  those entries reports the unreadable one with the existing one-line error (D6).
- The complete managed gate (`scripts/run-quality-gates.ps1` / `.sh`), at least 85% coverage, after
  each sub-slice.
- Step 3.4 §12's deferral note points here, so no document still describes watchlist rename,
  delete, or the alias/`method_id` inconsistency as open.
- A completion record appended to this document, analogous to IR.4's.

## 6. Background: the problem and the facts the design relies on

### 6.1 Problem

1. **No delete.** Neither `ian watchlist` nor `SQLiteWatchlistRepository` can delete a watchlist.
   A human or agentic caller that creates a scratch watchlist cannot clean it up, and the
   workspace grows without bound.
2. **No rename.** A watchlist's display name is fixed at creation.
3. **Ambiguous removal verbs.** `watchlist remove NAME TICKER...` removes *tickers* from a
   watchlist, and `watchlist disable NAME --analysis METHOD` removes a *method's* entries. Adding
   `delete` for the whole watchlist beside a `remove` that means something narrower is an
   ambiguity hazard, especially for agentic callers that pick commands by name.
4. **Two method vocabularies.** Watchlist commands accept the hyphenated aliases (`momentum`,
   `graham-number`, `graham-growth`, `fcf-growth` — the same names as the direct analysis
   commands), while `runs list --method` requires the canonical `method_id` (`sma_crossover`,
   `graham_number`, `graham_growth_value`, `reported_fcf_eps_cagr`). Text output mixes them too:
   `watchlist show`, `runs list`, and `refresh` print the canonical `method_id`.

Items 1, 2, and 4 are the items §12 of the Step 3.4 plan recorded as deferred. Under `AGENTS.md`'s
current rule that open items are not an acceptable outcome in this period, they are scheduled
here.

### 6.2 Verified facts

Originally checked against `feat/ir-integration-readiness` at `b871b62`, and revised 2026-09-29 for
IR.2.6's watchlist changes:

1. **No schema change or migration.** `watchlist_entries.watchlist_id` already declares
   `ON DELETE CASCADE` to `watchlists.watchlist_id` (`schema.py`), and `SQLiteDatabase` enables
   `PRAGMA foreign_keys` on every connection (`sqlite.py`).
2. **Saved Analysis Runs are unaffected by delete or rename.** `analysis_runs` has no foreign keys
   (already asserted by Step 3.4 C3's completion evidence). A run's `watchlist_id` and
   `watchlist_name` exist only inside its `envelope_json`, as a snapshot; the B2 field spec
   already specifies that this snapshot "survives later rename/delete." `runs list` has no
   watchlist filter, so no read path goes through a deleted watchlist.
3. **Name reuse is safe.** A watchlist recreated under a deleted one's name gets a fresh
   `watchlist_id`; runs from the deleted one stay distinguishable by ID.
4. **A refresh in progress is safe.** `refresh_watchlist` freezes the entries with one `get()`
   before executing anything, so a concurrent delete or rename cannot change a running refresh.
   Its summary reports the name captured at that `get()`.
5. **Canonical `method_id`s are persisted identity.** They are stored in `watchlist_entries` and
   inside every run envelope, and `reporting/analysis_runs.py` dispatches replay on them. They
   must not change; only the CLI's *input* and *human-readable text* vocabulary changes.
6. **The alias map already exists in one place.** `_ANALYSIS_ALIASES` / `_ALIAS_METHOD_IDS` in
   `src/cli_workspace.py` is the only alias-to-`method_id` mapping.
7. **IR.2.6 changed the watchlist removal path** (its plan's B.3 item 4). The repository's
   `remove_entry`, `remove_entries_for_ticker` and `remove_entries_for_method` return the number of
   entries removed and decode no survivors. The three CLI removal commands print a confirmation line,
   then the watchlist; if another entry cannot be read they still print the confirmation, then a one-line
   `StoredSelectionError` naming the entry and the `watchlist remove-entry` command that removes it, and
   exit 1. `SQLiteWatchlistRepository.get()` raises `StoredSelectionError` for a watchlist holding an
   entry stored by an earlier version, so `watchlist show` and `refresh` fail for the whole watchlist.
8. **Which paths decode every entry** (checked 2026-09-29 for D6). `get()`, `add_entries` and the
   aggregate-returning methods decode every entry of the watchlist. `list()` does not: it counts stored
   rows. `runs list` reads the `analysis_runs` table, never watchlist entries. The removal methods decode
   nothing (7 above). `delete` and `rename` as first planned would decode, because each returned the
   loaded aggregate; D6 removes that.

---

## Appendix A: Slice detail

### A.1 IR.6.1 — Command vocabulary

- Rename the Typer commands: `remove` → `remove-ticker`, `disable` → `remove-method`. Arguments,
  options, behavior, and exit codes are unchanged.
- `runs list`: replace `--method` with `--analysis` / `-a`, parsed by the existing
  `_parse_analysis` (same accepted values and error text as the watchlist commands), mapped to
  `method_id` through `_ALIAS_METHOD_IDS` before building `RunQuery`. `RunQuery` itself is
  unchanged.
- Add the reverse mapping (`method_id` → alias), derived from `_ALIAS_METHOD_IDS` rather than
  hand-written, with a test that the mapping is a bijection covering every selection type's
  `method_id` literal. An unmapped `method_id` in the text renderers is a programming error, not a
  silent fallback to the canonical id.
- Human-readable text shows aliases wherever it currently shows `method_id`: `_selection_summary`
  (`watchlist show` entry lines), `--group-by method` group headings, `_run_summary_line`
  (`runs list`), the `refresh` text summary lines, and the error printed when a stored watchlist
  entry can no longer be read (`StoredSelectionError`, built in
  `SQLiteWatchlistRepository._decode_entry`, which names the entry's `method_id`).
  `--group-by` keeps its `ticker|method` values, since "method" is the grouping axis and not a
  method name.
- The removal confirmation lines IR.2.6 added are part of that text and are asserted by the tests:
  `Removed 1 entry from watchlist 'NAME'.` (`remove-entry`),
  `Removed N entries for TICKER from watchlist 'NAME'.` and `No entries for TICKER in watchlist 'NAME'.`
  (`remove-ticker`), and `Removed N entries for ALIAS from watchlist 'NAME'.` and
  `No entries for ALIAS in watchlist 'NAME'.` (`remove-method`). The method lines already print the
  alias the caller typed and must keep doing so, never the canonical id. The retired-selection error
  keeps naming `watchlist remove-entry`, which this slice does not rename.
- `--json` payloads (`watchlist show`, `runs list`, `runs show`, `refresh`) are unchanged.
- The alias vocabulary adds no dependency on decoding entries: `runs list --analysis` maps an alias to a
  `method_id` before querying `analysis_runs`, and the reverse mapping is applied to run rows and to
  already-decoded entries only (D6).
- Docs: `WORKSPACE.md` (removal section, `runs list` filter example, any sample output showing
  canonical ids) and `GLOSSARY.md` where it names these commands. Historical completion-evidence
  documents are not rewritten.
- Tests: update the existing `remove`/`disable`/`--method` invocations and help checks to the new
  names; assert that the old command names and `--method` are now rejected (Typer usage error); add
  an alias-filter test for `runs list`; add text-output assertions showing aliases, including the
  confirmation lines and the retired-selection error; add a JSON assertion that `method_id` is still
  canonical.
- This changes human-readable workspace text output. It is recorded as an accepted exception to
  IR §4's "presentation output does not change" criterion, in the same way IR.2.2's wording change
  was.

### A.2 IR.6.2 — Delete

Repository (`src/data/repositories/watchlists.py`):

- `delete(name: str) -> DeletedWatchlist` resolves `name` with the existing trim/casefold convention
  and deletes its entries and then its watchlist row **in one transaction**, without decoding any entry
  (D6). It returns the watchlist's ID, display name and stored entry count, plus the decoded aggregate
  as it was immediately before deletion **when every entry could be decoded**, or the
  `StoredSelectionError` for the first unreadable entry when not (`DeletedWatchlist` holds one or the
  other). Decoding happens inside the same transaction, before the rows are removed, and a failure
  never rolls the deletion back.
- Entries are deleted explicitly, not only through the cascade. This matches IR's
  verify-at-both-boundaries approach. A separate test proves the cascade alone also leaves no
  orphans, so neither mechanism is untested.
- Unknown name raises the existing `WatchlistNotFoundError`. `--missing-ok` is a CLI concern
  handled by catching that error, not a repository flag.

CLI (`src/cli_workspace.py`), `ian watchlist delete NAME [--yes] [--missing-ok] [--json]`:

1. If `--yes` is absent and stdin is not interactive: usage error (exit 2) naming `--yes`, before
   opening the database. Interactivity is checked through one small helper, so tests can control
   it instead of depending on the test runner's stdin.
2. If `--yes` is absent and stdin is interactive: look up the watchlist row (applying the not-found
   rule below), show its name, ID, and stored entry count, taken from the row and a count of its stored
   entries with no decoding (D2's content is unchanged), and prompt. Declining exits 1 with nothing
   deleted.
3. Delete. Text output names the deleted watchlist and its ID and states that saved Analysis
   Runs are kept; it needs no entry, so it succeeds (exit 0) whatever the entries' state.
4. Not found: exit 1 via `_fail`, or with `--missing-ok`, exit 0 and a message that nothing was
   deleted.

`--json` output, one shape for all outcomes:

```text
{"requested_name": "Core Holdings", "deleted": true,  "watchlist": <the watchlist show --json document>}
{"requested_name": "Core Holdings", "deleted": false, "watchlist": null}
```

The second form appears only under `--missing-ok`. Without it, not-found is exit 1 on stderr, the
same as every other watchlist command.

If an entry cannot be decoded, `--json` cannot build the `watchlist` document. The deletion still
commits; stdout stays empty, stderr carries the confirmation
(`Deleted watchlist 'NAME' (ID, N entries). Saved Analysis Runs are kept.`) and then the existing
one-line `StoredSelectionError` naming the first unreadable entry, and the command exits 1, as the
removal commands do.

Tests:

- Repository: returns the pre-delete aggregate; the watchlist and all its entries are gone;
  case-insensitive match; not-found raises; other watchlists untouched; a saved run carrying the
  deleted `watchlist_id` still loads and replays; the name can be reused and gets a new ID;
  deleting the parent row by raw SQL alone leaves no orphan entries; a watchlist holding one or more
  entries stored by an earlier version is deleted, with the entry count reported and no decoding
  attempted, and the result carries the `StoredSelectionError` instead of the aggregate.
- CLI: `--yes` success (text and `--json`); interactive confirm and decline; non-interactive without
  `--yes` is exit 2 and the database file is byte-for-byte unchanged; not-found is exit 1;
  `--missing-ok` not-found is exit 0 (text and `--json`); `--missing-ok` on an existing watchlist
  deletes normally; `watchlist list` no longer shows it; a watchlist with unreadable entries is deleted
  by `--yes` in text mode (exit 0), the interactive prompt shows the entry count without decoding, and
  `--json` on such a watchlist deletes it, prints nothing on stdout, and prints the confirmation and the
  one-line error on stderr with exit 1.
- Docs: a "Deleting a watchlist" subsection in `WORKSPACE.md`, covering run retention, `--yes`,
  and `--missing-ok`.

### A.3 IR.6.3 — Rename

- Repository `rename(name: str, new_display_name: str) -> None` decodes no entry (D6) and applies the same trim/blank
  validation as `create` and raises `WatchlistConflictError` if the new normalized name belongs to
  a *different* watchlist. Renaming to a different casing of its own name (`core holdings` →
  `Core Holdings`) is allowed and changes only `display_name`. Renaming to the identical display
  name is a no-op that does not bump `updated_at`. Any real change bumps `updated_at`.
  `watchlist_id` never changes.
- CLI `ian watchlist rename NAME NEW_NAME [--json]`: not destructive, so no confirmation. Not
  found is exit 1; conflict is exit 1; a blank new name is a usage error (exit 2). After the rename
  commits, the command prints `Renamed watchlist 'OLD' to 'NEW'.` and then the renamed watchlist, read
  back with `get()` and rendered as `watchlist show` renders it. If `get()` raises
  `StoredSelectionError`, the confirmation stands, the existing one-line error follows, and the command
  exits 1. With `--json`, the document is the only stdout on success; on an unreadable entry stdout is
  empty and stderr carries the confirmation and the error.
- Docs: a "Renaming a watchlist" subsection, stating that saved runs keep the name the watchlist
  had when they ran, by design (§6.2 item 2), so `runs show` may display a name that no longer
  exists.
- Tests: success; case-only rename; identical-name no-op; conflict; blank; not found; a saved run's
  snapshot name is unchanged after rename; `updated_at` behavior; a watchlist holding unreadable entries
  is renamed (the row changes, the confirmation and one-line error print, exit 1, and `--json` leaves stdout
  empty), and the same watchlist can then be brought back to a readable state with `remove-entry`.

---

## Appendix B: Decision records

### B.1 Decisions (project owner, 2026-09-27)

- **D1 — Removal verbs.** `watchlist remove` → `watchlist remove-ticker`; `watchlist disable` →
  `watchlist remove-method`. Every entry-removal command reads `remove-*`, and `delete` means only
  the whole watchlist. The old names are removed outright, with no aliases or deprecation shims,
  since there are no users to migrate (`AGENTS.md` §0).
- **D2 — Delete confirmation.** Interactive terminal: prompt, showing name, ID, and entry count.
  `--yes` skips the prompt. A non-interactive stdin without `--yes` is a usage error (exit 2)
  checked before the database is opened, so the command never hangs waiting for input.
- **D3 — Missing watchlist.** Deleting an unknown name is exit 1, consistent with every other
  watchlist command. `--missing-ok` turns that case into exit 0 with nothing deleted, for
  idempotent agentic cleanup. Delivered in this work package, not deferred.
- **D4 — One method vocabulary.** The hyphenated aliases are the only method vocabulary the CLI
  accepts and prints in human-readable text. `runs list --method METHOD_ID` becomes
  `runs list --analysis ALIAS`. `--json` output keeps the canonical `method_id` unchanged,
  since it is persisted identity (§6.2 item 5). JSON is the machine contract; the aliases are the
  human and command-line contract.
- **D5 — Placement.** This is an amendment to IR (§2 item 8 and §3 row IR.6 of the
  [IR contract](IR_CONTRACT_AND_SLICE_PLAN.md)). It is justified by agentic callers driving `ian`
  through its CLI, IR's target consumer. Numbered IR.6, not IR.5, because "IR.5" still labels the
  JSON-envelope scope that moved to `SWC`, and reusing it would recreate the ambiguity the IR.4
  reuse needed a note to resolve.

### B.2 D6 — Unreadable stored entries (project owner, 2026-09-29)

- **D6 — Mutations commit without decoding.** An entry stored by an earlier version cannot be decoded,
  and `get()` fails for the whole watchlist. IR.2.6 fixed the removal commands so each removal commits
  without decoding any survivor. Every command IR.6 adds or changes follows the same rule. `delete`
  builds its confirmation summary (name, ID, entry count) from the watchlist row and a count of its
  stored entries, and deletes without decoding; D2's decision about what the prompt shows is unchanged.
  `rename` commits without decoding. The alias-vocabulary paths (`runs list --analysis` and the
  renderers) add no dependency on decoding entries. Any display after a mutation that needs the decoded
  entries reports an unreadable one with the existing one-line `StoredSelectionError` message, after a
  confirmation of what was done, and exits 1. Recorded so a sub-slice cannot reintroduce an
  aggregate-returning mutation that rolls back because an unrelated entry cannot be read.

### B.3 Branching history

**Revised 2026-09-29 (current).** IR.6 branches `fix/ir6-watchlist-lifecycle` off `main` after
`feat/ir-integration-readiness` has merged. IR.2.6 changed the watchlist removal commands, their error
handling and their confirmation text, and IR.6.1 rewrites the same commands and text, so IR.6 now
depends on IR.2 and can no longer be merged first. Merging that branch to `main` still needs its own
approval (`AGENTS.md` §11).

**Original (2026-09-27), superseded by the revision above; kept verbatim.**

Following IR.4's precedent: **its own branch, `fix/ir6-watchlist-lifecycle` off `main`, merged
to `main` independently once accepted.** IR.6 has no dependency on IR.2.4–IR.2.6, and binding it
to IR.2's "nothing merges until the last sub-slice" rule would keep a known lifecycle gap on
`main` for as long as those take. After IR.6 merges, `feat/ir-integration-readiness` merges `main`
back in. The expected conflict surface is small: IR.2.5 and IR.2.6 touch `cli_workspace.py`'s
execution helpers and Momentum selection flags, and IR.6 touches its watchlist and `runs list`
commands and text renderers.

Three sub-slices on that branch. Each ends with the managed gate and is gated by explicit
authorization. Vocabulary goes first, so delete and rename are written once, in final command
names and final text vocabulary.
