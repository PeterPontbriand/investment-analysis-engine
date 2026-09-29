# IR.6 — Watchlist Lifecycle Completion

Closes the watchlist lifecycle gap that Step 3.4 Amendment A1 deferred
([`STEP_3_4_CONTRACT_AND_SLICE_PLAN.md`](../step-3.4/STEP_3_4_CONTRACT_AND_SLICE_PLAN.md) §12,
"Deferred, not included in this amendment"): a watchlist can be created but never deleted or
renamed, and the workspace CLI mixes two vocabularies for naming an analysis method. Scope and
decisions approved by the project owner 2026-09-27; implementation not yet authorized.

## 1. Problem

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

## 2. Verified facts the design relies on

Checked against `feat/ir-integration-readiness` at `d2a7be9` (the watchlist code is unchanged from
`main` at `af0a222`, except for IR.2's selection/execution changes, which this slice does not touch):

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

## 3. Decisions (project owner, 2026-09-27)

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
  since it is persisted identity (§2 item 5). JSON is the machine contract; the aliases are the
  human and command-line contract.
- **D5 — Placement.** This is an amendment to IR (§2 item 8 and §3 row IR.6 of the
  [IR contract](IR_CONTRACT_AND_SLICE_PLAN.md)). It is justified by agentic callers driving `ian`
  through its CLI, IR's target consumer. Numbered IR.6, not IR.5, because "IR.5" still labels the
  JSON-envelope scope that moved to `SWC`, and reusing it would recreate the ambiguity the IR.4
  reuse needed a note to resolve.

## 4. Branch and sequencing

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

| Slice | Scope |
| :--- | :--- |
| IR.6.1 | Command vocabulary (D1, D4): `remove-ticker`, `remove-method`, `runs list --analysis`, alias-only human-readable text. |
| IR.6.2 | Delete (D2, D3): repository `delete`, `ian watchlist delete NAME [--yes] [--missing-ok] [--json]`. |
| IR.6.3 | Rename: repository `rename`, `ian watchlist rename NAME NEW_NAME [--json]`. |

## 5. Slice scope

### IR.6.1 — Command vocabulary

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
- `--json` payloads (`watchlist show`, `runs list`, `runs show`, `refresh`) are unchanged.
- Docs: `WORKSPACE.md` (removal section, `runs list` filter example, any sample output showing
  canonical ids) and `GLOSSARY.md` where it names these commands. Historical completion-evidence
  documents are not rewritten.
- Tests: update the existing `remove`/`disable`/`--method` invocations and help checks to the new
  names; assert that the old command names and `--method` are now rejected (Typer usage error); add
  an alias-filter test for `runs list`; add text-output assertions showing aliases; add a JSON
  assertion that `method_id` is still canonical.
- This changes human-readable workspace text output. It is recorded as an accepted exception to
  IR §4's "presentation output does not change" criterion, in the same way IR.2.2's wording change
  was.

### IR.6.2 — Delete

Repository (`src/data/repositories/watchlists.py`):

- `delete(name: str) -> Watchlist` resolves `name` with the existing trim/casefold convention,
  loads the full aggregate, and deletes its entries and then its watchlist row **in one
  transaction**. It returns the aggregate as it was immediately before deletion.
- Entries are deleted explicitly, not only through the cascade. This matches IR's
  verify-at-both-boundaries approach. A separate test proves the cascade alone also leaves no
  orphans, so neither mechanism is untested.
- Unknown name raises the existing `WatchlistNotFoundError`. `--missing-ok` is a CLI concern
  handled by catching that error, not a repository flag.

CLI (`src/cli_workspace.py`), `ian watchlist delete NAME [--yes] [--missing-ok] [--json]`:

1. If `--yes` is absent and stdin is not interactive: usage error (exit 2) naming `--yes`, before
   opening the database. Interactivity is checked through one small helper, so tests can control
   it instead of depending on the test runner's stdin.
2. If `--yes` is absent and stdin is interactive: look up the watchlist (applying the not-found
   rule below), show its name, ID, and entry count, and prompt. Declining exits 1 with nothing
   deleted.
3. Delete. Text output names the deleted watchlist and its ID and states that saved Analysis
   Runs are kept.
4. Not found: exit 1 via `_fail`, or with `--missing-ok`, exit 0 and a message that nothing was
   deleted.

`--json` output, one shape for all outcomes:

```text
{"requested_name": "Core Holdings", "deleted": true,  "watchlist": <the watchlist show --json document>}
{"requested_name": "Core Holdings", "deleted": false, "watchlist": null}
```

The second form appears only under `--missing-ok`. Without it, not-found is exit 1 on stderr, the
same as every other watchlist command.

Tests:

- Repository: returns the pre-delete aggregate; the watchlist and all its entries are gone;
  case-insensitive match; not-found raises; other watchlists untouched; a saved run carrying the
  deleted `watchlist_id` still loads and replays; the name can be reused and gets a new ID;
  deleting the parent row by raw SQL alone leaves no orphan entries.
- CLI: `--yes` success (text and `--json`); interactive confirm and decline; non-interactive without
  `--yes` is exit 2 and the database file is byte-for-byte unchanged; not-found is exit 1;
  `--missing-ok` not-found is exit 0 (text and `--json`); `--missing-ok` on an existing watchlist
  deletes normally; `watchlist list` no longer shows it.
- Docs: a "Deleting a watchlist" subsection in `WORKSPACE.md`, covering run retention, `--yes`,
  and `--missing-ok`.

### IR.6.3 — Rename

- Repository `rename(name: str, new_display_name: str) -> Watchlist` applies the same trim/blank
  validation as `create` and raises `WatchlistConflictError` if the new normalized name belongs to
  a *different* watchlist. Renaming to a different casing of its own name (`core holdings` →
  `Core Holdings`) is allowed and changes only `display_name`. Renaming to the identical display
  name is a no-op that does not bump `updated_at`. Any real change bumps `updated_at`.
  `watchlist_id` never changes.
- CLI `ian watchlist rename NAME NEW_NAME [--json]`: not destructive, so no confirmation. Not
  found is exit 1; conflict is exit 1; a blank new name is a usage error (exit 2). Output is the
  renamed watchlist, as `watchlist show` renders it.
- Docs: a "Renaming a watchlist" subsection, stating that saved runs keep the name the watchlist
  had when they ran, by design (§2 item 2), so `runs show` may display a name that no longer
  exists.
- Tests: success; case-only rename; identical-name no-op; conflict; blank; not found; a saved run's
  snapshot name is unchanged after rename; `updated_at` behavior.

## 6. Acceptance criteria

- No change to any analysis formula, classification, result, run envelope, persisted schema, or
  `--json` payload. No Alembic migration; the head revision is unchanged.
- Human-readable workspace text changes only as §5 IR.6.1 specifies, and the change is recorded in
  IR §4.
- The complete managed gate (`scripts/run-quality-gates.ps1` / `.sh`), ≥85% coverage, after each
  sub-slice.
- Step 3.4 §12's deferral note points here, so no document still describes watchlist rename,
  delete, or the alias/`method_id` inconsistency as open.
- A completion record appended to this document, analogous to IR.4's.
