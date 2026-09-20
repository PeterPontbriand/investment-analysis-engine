# Slice I2 — Completion evidence (Amendment A1)

**Review disposition:** accepted (2026-09-19).
**Date:** 2026-09-19 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

Second slice of [Contract Amendment A1](STEP_3_4_CONTRACT_AND_SLICE_PLAN.md#12-contract-amendment-a1--watchlist-entry-model),
following [I1](SLICE_I1_COMPLETION_EVIDENCE.md)'s entry-model/repository/migration
checkpoint. This slice restores and expands the watchlist CLI surface that I1
removed, entirely within `src/cli_workspace.py`.

## Commands

`watchlist create NAME [--analysis METHOD [method flags] TICKER...]` — creation
is unchanged when `--analysis` is omitted (empty watchlist); when given, it
seeds one entry per listed ticker for that method in the same command, the
common single-method/multiple-ticker case (§12's "Creation"). Selection
construction and the created (empty) watchlist commit happen in that
order — the selection is fully validated before any row is written, so a
usage error never leaves a partially-seeded watchlist behind.

`watchlist add-selection NAME TICKER... --analysis METHOD [method flags]` —
the same one-command fan-out as `create`, for adding a method to a watchlist
that already exists (§12's "Editing"). Both commands accept identical
method-specific flags.

`watchlist remove-entry NAME INDEX` — removes exactly one entry by its
displayed 1-based index; `INDEX` is translated to the stored 0-based
`position` (`position = INDEX - 1`) before calling the repository, matching
the amendment's addressing rule exactly.

`watchlist remove NAME TICKER...` and `watchlist disable NAME --analysis
METHOD` are repurposed onto the new repository's bulk removal methods
(`remove_entries_for_ticker`/`remove_entries_for_method`), preserving the
superseded commands' own bulk, idempotent-on-a-miss convenience.

`watchlist show NAME [--group-by ticker|method] [--json]` — text output now
groups entries under their ticker (default) or method; `--json` emits the
flat, ordered entry list with an explicit 1-based `index` per entry (not the
internal 0-based `position`), so there is one number to learn across text,
JSON, and `remove-entry`'s own argument.

`configure` and its file-based `--config PATH` are not restored; no command
in this module accepts a `--config` flag (verified by a dedicated test
reading each command's own `--help` text).

## Method-specific flags

`_build_selection` in `src/cli_workspace.py` builds one validated
`AnalysisSelection` from CLI flags shared across `create`/`add-selection`,
mirroring each direct command's own flags and validation exactly:

- `momentum`: `--short-window`/`--long-window`/`--rsi-period`, defaulted from
  the same `MomentumConfig()` defaults the direct `momentum` command uses;
  invalid windows are rejected with the same messages the direct command
  produces.
- `graham-number`/`graham-growth`: `--as-of`, `--data-provider`, `--no-cache`,
  `--eps`, `--eps-basis`, `--current-price`, plus `--bvps` (graham-number
  only) and the required `--expected-growth`/`--aaa-yield` (graham-growth
  only); validation is delegated to the existing `GrahamNumberSelection`/
  `GrahamGrowthSelection` models through the existing `config_usage_errors()`
  translator (`src/cli_support.py`), so error text stays consistent with the
  direct commands without duplicating field-name-to-flag mapping.
- `fcf-growth`: `--growth-years`, `--forward-policy`, `--classification-basis`,
  `--currency`; always executes against SEC EDGAR regardless of
  `--data-provider`, exactly as the direct `fcf-growth` command's own
  persisted selection already does (`FCFGrowthSelection.provider_id` is a
  fixed `Literal["sec_edgar"]`) — the flag is still accepted and validated
  for a consistent experience, it simply has no effect for this method,
  matching the direct command's own existing behavior.

Only the flags relevant to the selected `--analysis` are consulted; the CLI
does not reject an irrelevant flag supplied alongside a different method (for
example `--bvps` with `--analysis momentum`), matching the merged-command
design the amendment calls for without adding a cross-flag validation matrix
the amendment does not ask for.

The `--analysis` alias vocabulary (`momentum`, `graham-number`,
`graham-growth`, `fcf-growth`) is unchanged from the superseded commands;
its inconsistency with `runs list --method`'s canonical `method_id` values
remains the separately flagged, out-of-scope item §12 already recorded.

## Tests

`tests/test_cli_workspace.py` gained 31 new tests (19 → 50) covering: seeded
creation (single and multi-ticker), the
creation-requires-both-or-neither-of `--analysis`/`TICKER` usage errors,
rejection of an unknown `--analysis` alias, graham-growth's required-flag
enforcement (both flags individually), a full fcf-growth seed exercising
every fcf-specific flag, rejection of each fcf-specific flag's invalid value
(`--growth-years`, `--forward-policy`, `--classification-basis`,
`--currency`) and of invalid momentum windows (all four branches),
`add-selection` appending and proving the amendment's headline capability
(the same method twice for one ticker, via two providers), `add-selection`
against a missing watchlist, `remove-entry`'s renumbering, its out-of-range
and missing-watchlist errors, `remove`/`disable`'s bulk removal and
missing-watchlist errors, a blank ticker being rejected by `create`,
`add-selection`, and `remove`, `show`'s ticker/method grouping and its
invalid-`--group-by` rejection, `show --json`'s 1-based `index` field, and
the no-`--config`-anywhere check. The existing `--help`
no-storage-side-effects test was extended to the four new commands.

## Full managed gate

Ruff, Ruff format, and strict mypy passed clean. `src/cli_workspace.py`
reaches 100% line/branch coverage across `test_cli_workspace.py` (50 tests),
`test_cli_refresh.py`, and `test_workspace_integration.py` (62 tests
combined). The full pytest run passed with **3,086 tests**, combined
coverage **91%**, matching I1's baseline.

## Boundaries

I3 (docs — `docs/user/WORKSPACE.md`/`GLOSSARY.md`; revisiting
`tests/test_workspace_integration.py` to drive entry creation through these
new commands instead of direct repository seeding; full regression; final
Step 3.4 acceptance) is the next and final slice of Amendment A1, not part
of this checkpoint. Nothing was committed, pushed, or opened as a PR.
