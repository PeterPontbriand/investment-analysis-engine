# Slice I3 — Completion evidence (Amendment A1)

**Review disposition:** accepted (2026-09-20), carrying final Step 3.4
acceptance.
**Date:** 2026-09-20 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

Third and final slice of [Contract Amendment A1](STEP_3_4_CONTRACT_AND_SLICE_PLAN.md#12-contract-amendment-a1--watchlist-entry-model),
following [I1](SLICE_I1_COMPLETION_EVIDENCE.md)'s entry-model/repository/
migration checkpoint and [I2](SLICE_I2_COMPLETION_EVIDENCE.md)'s CLI surface.
This slice updates user documentation for the new model and commands,
revisits the one full-workflow integration test to drive it through those
real commands, and runs the full regression/managed gate ahead of final
Step 3.4 acceptance.

## Documentation

`docs/user/WORKSPACE.md`: the "Watchlists" section is rewritten around
[entries](GLOSSARY.md#entry) rather than a separate members list and
selections list — the retired default-selection-materialization example and
the file-based `--config PATH` example are both gone. It now documents
seeded creation (`create --analysis METHOD [flags] TICKER...`), the
`add-selection` fan-out, `remove-entry`'s 1-based `INDEX`, bulk removal via
`remove`/`disable`, and `show --group-by ticker|method` with its 1-based
JSON `index`. A new "Method-specific flags" table lists exactly which flags
each `--analysis` value accepts, cross-checked against `docs/user/USAGE.md`'s
own flag names for the direct commands so the two pages never disagree. The
refresh exit-code table's "no members or no selections to refresh" row is
corrected to "no entries to refresh".

`docs/user/GLOSSARY.md`: **Selection** no longer states a watchlist holds "at
most one selection per method" (the amendment's whole point is that it can
hold more than one, e.g. Graham Number via SEC EDGAR alongside Graham Number
via Massive). A new **Entry** term defines the ticker+selection pair and its
1-based display/addressing rule. **Watchlist** and **Refresh** are reworded
around the entry list rather than "tickers together with selections" and
"(ticker, selection) pair".

## Test revisit

`tests/test_workspace_integration.py`'s one scenario
(`test_full_offline_workflow_create_seed_refresh_and_browse`) now seeds its
three entries through the real CLI — `watchlist create --analysis momentum
--short-window 2 --long-window 3 SYNTH`, then two `watchlist add-selection`
calls for Graham Number and Graham Growth Value — instead of I1/I2's interim
direct-repository seeding (`SQLiteWatchlistRepository.add_entries`, used only
because I2's commands did not exist yet). The now-unused direct-repository
imports (`SQLiteDatabase`, `SQLiteWatchlistRepository`, `src.cli_workspace`,
and the four `AnalysisSelection` variants) are removed along with the
seeding code; the rest of the scenario (show, refresh, browse, replay in
every presentation mode) is unchanged, since it was already exercising the
CLI, not the repository.

## Full managed gate

Ruff, Ruff format, and strict mypy passed clean on every changed file. The
full pytest run: **3,086 passed**, combined coverage **91%** — identical to
I2's run, confirming the existing E1-E4/G1-G3 suites and every other
previously-accepted slice's tests are unaffected by this documentation-and-
test-only slice.

## Amendment A1 status

I1, I2, and I3 are now all accepted. Amendment A1's watchlist entry model
— the ordered list of (ticker, selection) entries, the 1-based user-facing
addressing rule, the same-method-more-than-once capability, the one-command
fan-out for creation and editing, and the retirement of file-based
`--config` — is complete end to end: model, repository, migration, CLI
surface, and documentation.

Per §9's slice table, I3 also carried explicit final Step 3.4 acceptance;
the project owner granted it on 2026-09-20, closing out Step 3.4 in full,
including the G3/H review outstanding since batch 4. Watchlist rename/delete
and the `--analysis`-alias-vs-canonical-`method_id` inconsistency remain the
two items §12 already flagged as deferred and out of scope for this
amendment. A short series of related, separately-authorized UX fixes not
part of Amendment A1's own slices was also made on this branch before final
acceptance; see the closing note in §12 of the plan document. Nothing was
committed, pushed, or opened as a PR as of this acceptance. Per §12,
P2-Profiles, ESC-D renewed acceptance, and Step 3.5 may now proceed.
