# Slices E3, E4, F1, F2 — Completion evidence (batch 1)

**Review disposition:** implemented; pending project owner review and acceptance.
**Date:** 2026-09-19 (America/Toronto).
**Branch:** `feat/step-3.4-local-research-workspace`.

The project owner authorized batching the remaining Step 3.4 slices into four
review checkpoints instead of one-at-a-time, given the contract's per-slice
granularity was calibrated for a local model, not for this session's direct
implementation. This is the first checkpoint: E3 (Growth replay), E4 (FCF
replay), F1 (Watchlist CLI), F2 (Run browsing CLI). Cline is not involved in
this batch; all of it was implemented and verified directly in this session.

## E3 — Graham Growth replay

### Audit required by §7

Read `src/cli.py`'s `_run_graham_growth` and `_growth_failure_output`, and
every render path in `src/reporting/graham.py` used for Growth. Two
substitution points were found — both already discovered and fixed for Number
in E2, and reproduced identically here because Growth shares the same
`cli.py` presentation pattern:

1. **Assumptions (`base_pe`/`growth_multiplier`/`baseline_aaa_yield`)** are
   *not* a hidden computation risk: the live command reads them from a fresh
   `_growth_assumptions()` settings call, but the analyzer is invoked with,
   and the native `GrahamGrowthAnalysis.policy` field retains, the exact same
   values used for that calculation. Replay reads `evidence.policy.*`
   directly — the stored assumptions, not a live settings re-read — so a
   future change to the project's default assumptions can never alter what
   an old run replays as. Verified with a dedicated test that patches
   `ProjectSettings.get_graham_value_analysis` to raise and confirms replay
   still renders the exact stored constants.
2. **Quote-reason normalization** (`growth_with_public_quote_reason`) is
   applied by the live command before rendering but never before persistence,
   identical to Number's E2 gap. Replay applies it here from the start.

### A second retroactive gap found, this time in the generic failure reason

Auditing `_growth_failure_output` alongside `_number_failure_output` (both
already read during E2, but not both fully cross-checked at the time)
surfaced that **both** functions apply a second, separate normalization —
`_friendly_graham_failure(ticker, status, reason)` — to a genuine failure's
`assembly.reason` before rendering, and this was **also never applied by
E2's accepted `_project_graham_number_v1`**. The live command only invokes
this for a real failure (anything except OK/NOT_APPLICABLE); a NOT_APPLICABLE
assembly's reason is already investor-facing at the source and is shown
verbatim. Since `execute_graham_number`/`execute_graham_growth` persist the
analyzer's raw, technical reason unmodified, a stored invalid-input or
provider-error run would have replayed with that raw text instead of the
live command's normalized sentence — the same class of bug as the
quote-reason gap, just on a different field, and equally undetected by E2's
own tests (its invalid-input fixture hardcoded the already-normalized
sentence directly into `reason`, with `quote_status=None`, so neither
transform was ever exercised for real).

**Fix, applied to both Number (retroactive) and Growth:** `_friendly_graham_failure`
was relocated from `cli.py` into `src/reporting/graham.py` as
`friendly_graham_failure` (mirroring E2's already-accepted relocation of the
quote-reason helpers, for the identical reason: reporting must not import
from `cli.py`), exported, and `cli.py` updated to import and call it instead
of a private copy — a pure relocation, no behavior change. A new private
helper in `analysis_runs.py`, `_friendly_graham_assembly(ticker, assembly)`,
applies it only for genuine failures (mirroring the exact live-command
branching) and is shared by both `_project_graham_number_v1` and
`_project_graham_growth_v1`, generic over both assembly types via a PEP 695
type parameter rather than duplicating the branch twice.

New regression tests prove this for both methods: a fixture stores a
deliberately raw, non-investor-facing reason string; the assertion checks
the normalized sentence renders **and** the raw string never appears
anywhere in the output — the same "prove substitution, not coincidence"
pattern used throughout this project's replay tests.

### Delivered scope

- `src/reporting/graham.py`: `friendly_graham_failure` (relocated, exported).
- `src/cli.py`: imports and calls the relocated function; the private copy
  is removed.
- `src/reporting/analysis_runs.py`: `_project_graham_growth_v1`,
  `_friendly_graham_assembly` (shared helper), the retroactive fix inside
  `_project_graham_number_v1`, and the dispatch entry for
  `("graham", "graham_growth_value")`.
- `tests/reporting/test_analysis_run_replay.py`: full Growth coverage —
  no-recalculation (mismatched stored `growth_value`), the settings-invariant
  test described above, negative growth (a valid completed calculation, not
  a failure), captured-profile-not-native-copy, comparison-unavailable,
  invalid-input reason normalization, ETF/NOT_APPLICABLE, quote-reason
  normalization, all-modes, JSON, and a live-analyzer/settings-forbidden
  test — plus the retroactive Number fix's own new test and a correction to
  Number's now-inaccurate "unimplemented method" fixture (it used to assert
  `graham_growth_value` was unsupported, which is no longer true after this
  slice; replaced with a genuinely unimplemented forward-looking pair).

## E4 — FCF/Earnings Growth replay

### Audit required by §7

`src/cli.py`'s `fcf-growth` command applies **no presentation-time
normalization at all** before calling `render_fcf_earnings_growth` — unlike
Graham, there is no intermediate "safe assembly" or friendly-failure step.
Reading every render helper in `src/reporting/fcf_earnings_growth.py`
line by line: every displayed number (CAGRs, FCF, FCF/share, FCF yield) is
read directly from an already-computed field on the stored
`FCFEarningsGrowthResult` or its `annual_observations`; the only
aggregations performed at render time (`_source_summary`'s provider-name
set and latest-evidence-date `max()`) are pure selections over already-known
provenance, not new financial derivations — the same category E1's audit
already established as safe to reuse. **No substitution point was needed.**

The one adapter-specific behavior preserved: `execute_fcf_growth` composes
the profile once and never reads `result.instrument_profile` back for
rendering (documented on the adapter itself), so replay uses the envelope's
own `run.instrument_profile`, exactly like Momentum and Number/Growth.

### Delivered scope

`_project_fcf_growth_v1` is three lines: decode, assert the type, call
`render_fcf_earnings_growth(evidence, options.mode,
instrument_profile=run.instrument_profile)`. Tests cover: no-recalculation
(a stored CAGR the identical-year-over-year fixture observations could not
themselves produce), captured-profile-not-native-copy, partial evidence /
missing forward context (the fixture's own forward evidence is naturally
unavailable — no consensus data — satisfying this criterion directly rather
than requiring a bespoke fixture), all-modes, JSON (including
`result_schema_version`), default-to-concise, and a live-analyzer-forbidden
test. "Old v1 output invariant under current-settings changes" is
structurally satisfied rather than separately tested: FCF's policy is
entirely request-scoped (built from CLI flags, never a `settings.get_*()`
default lookup the way Graham Growth's assumptions are), so there is no live
settings source for a future default change to diverge from.

## F1 — Watchlist CLI

New `src/cli_workspace.py`, registered in `src/cli.py` via
`register_workspace_commands(app)`. Implements the full approved command set
from contract §8: `watchlist create/list/add/remove/show/configure/disable`.

- `configure` reuses B1's existing `parse_selection(alias, config_json)`
  unchanged — it already enforces every requirement in §3 (unknown alias,
  extra/foreign fields, non-finite numbers, no identifier override in the
  body); this slice added no new validation logic for it.
- Each command opens its own short-lived, readiness-checked `SQLiteDatabase`
  via a local `_workspace_database()` context manager, mirroring
  `cli_support.py`'s existing `_production_historical_client`/
  `_production_financial_cache` pattern exactly — no side effects at import
  or `--help` time (both explicitly tested by patching `SQLiteDatabase.__init__`
  to raise and confirming `--help` and module reload still succeed).
- Exit codes follow contract §8 precisely: usage errors (unknown alias,
  malformed config, invalid ticker) exit 2; missing watchlist / readiness /
  storage errors exit 1 with a sanitized message; successful reads exit 0.

**Dead code found and removed:** an explicit `if not tickers: raise
typer.BadParameter(...)` guard was written for `add`/`remove`'s multi-value
TICKER argument, then found to be unreachable — Typer/Click's own required
multi-value argument parsing already rejects zero tickers with "Missing
argument 'tickers'" before the function body ever runs (confirmed directly:
invoking with zero tickers produces Click's own message, not ours). Both
guards were deleted rather than covered with a test for dead code; the
CLI-level "at least one ticker is required" contract behavior is still
verified end-to-end, now correctly attributed to Click's own parsing.

## F2 — Run browsing CLI

Same module, `runs list`/`runs show`. `runs show` dispatches to
`project_run` (E1–E4) for the rendered body; `runs list` reads only
`SQLiteAnalysisRunRepository.list()`'s indexed summary columns, never
decoding a full envelope, matching the repository's own documented
corruption-isolation guarantee.

**A real defect found and fixed during this slice's own development** (not
retroactive to already-accepted work): initial testing of a deliberately
corrupted stored row (a relational `method_version` column overwritten
directly, disagreeing with its own envelope) showed `runs show` propagating
a raw, uncaught `ValueError` — `SQLiteAnalysisRunRepository.get()`'s own
documented row-consistency check raises a plain `ValueError`, distinct from
the three typed codec errors (`UnsupportedProjectionError`,
`UnsupportedRunVersionError`, `InvalidStoredRunError`) `runs show` already
caught. Caught under `CliRunner`'s test harness this silently "passed" with
exit code 1 for the wrong reason (the harness's own exception-to-exit-code
handling, not a graceful command path); a real invocation would have printed
a Python traceback. Fixed by wrapping `repository.get()` itself in a
`try/except ValueError` inside `runs_show`. A dedicated test now asserts
`"Traceback" not in result.output` in addition to the exit code, so this
class of gap cannot silently re-pass in the future.

Exit-code note honored precisely: `runs show` exits **0** even when the
persisted run's own outcome is `failed` — verified with a genuine execution
run whose `ExecutionCapture.outcome` is deliberately `RunOutcome.FAILED`,
confirming a pure successful *read* is never conflated with the analysis
outcome it displays.

### Shared test infrastructure change

`tests/_cli_helpers.py`'s `isolated_cli_database` fixture previously patched
only `src.cli_support.settings`. Since `src/cli_workspace.py` holds its own
separate `from src.config import settings` module binding, the fixture was
extended to patch both — the same disposable, migrated-to-head database now
backs every CLI test module, old and new, with zero duplication.

## Contract proof (§7, §8, §9)

| Contract requirement | Evidence |
| :--- | :--- |
| Growth: all modes, assumptions, negative growth, unavailable comparison | `test_growth_project_run_*` — 12 tests covering each case individually. |
| Growth: no recalculation | Mismatched stored `growth_value`; settings-patch-to-raise test proves stored assumptions, not live settings, are shown. |
| FCF: all modes, partial evidence, missing forward context | `test_fcf_project_run_*`; forward evidence naturally unavailable in the fixture. |
| FCF: old v1 output invariant under settings changes | Structurally satisfied — no live settings source exists in FCF's render path; documented rather than redundantly tested. |
| F1: complete CRUD/config/disable workflow, usage validation, no provider calls, help side-effect freedom | 20 `test_watchlist_*` tests; `SQLiteDatabase.__init__` patched to raise across `--help` and module reload. |
| F2: listing/filtering, all show modes, unknown ID/version/corruption, no network/cache/clock enrichment | 14 `test_runs_*` tests, including the corrupted-envelope and unsupported-version cases; replay itself already proves no live calls (E1–E4). |

## Full managed gate

Ruff, Ruff format, and strict mypy passed clean. The full pytest run:
**3,020 passed** (52 new: 18 in the replay tests for E3/E4 plus the
retroactive Number fix, 34 in the new `tests/test_cli_workspace.py`),
combined coverage **91%**; `src/cli_workspace.py` and
`src/reporting/analysis_runs.py` both reach 100% line/branch coverage.

## Boundaries and review gate

F3 (direct-command `--save-run` wiring), G1–G3 (refresh/concurrency), and H
(final acceptance/docs) are the next batches and are not part of this
checkpoint. Nothing was committed, pushed, or opened as a PR.
