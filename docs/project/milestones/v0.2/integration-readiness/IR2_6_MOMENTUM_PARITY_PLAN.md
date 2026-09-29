# IR.2.6 — Momentum Parity: Implementation Plan

Revision 1 was approved for implementation on 2026-09-29.

Parent: [IR.2 detail plan, §6.12](IR2_ANALYZER_ENVELOPE_PLAN.md#612-ir2-slice-list--approved-revised-2026-09-25-graham-separation-inserted).
Scope origin: that plan's §2 item 4, §6.4, §6.5, §6.9 and §6.10. Where this plan disagrees with
them, this plan is based on the current code; the differences are listed in
[Appendix B](#appendix-b-decision-records).

## 1. At a glance

- **What IR.2.6 is:** the last IR.2 sub-slice. It makes Momentum's *caller-facing* surface match
  Graham Number, Graham Growth and FCF Growth: injected, required dependencies; the instrument
  profile embedded in every result; and real `--as-of`/`--no-cache` options, persisted on
  `MomentumSelection` and accepted by the orchestrator tool.
- **What it is not:** no formula, window, RSI or classification change; no new presentation field
  or JSON key; no change to the data-client cache mechanism IR.2.5 built; no Alembic migration.
- **Rules it follows:** `AGENTS.md` §0 (persisted shapes may change; version fields bump; no
  compatibility code for stored data), §9 (no generic framework), and line 58 (no AI/tool
  attribution). Every commit passes the full managed gate; the slice stops for review once, at the
  end.
- **When it lands, IR.2 is complete:** the last commit is IR.2's acceptance record, and the IR.2
  plan's rule that nothing merges to `main` before IR.2.6 is accepted no longer applies (merging
  still needs its own approval, `AGENTS.md` §11).
- **Decisions:** the project owner accepted the three choices in
  [B.1](#b1-decisions-flagged-for-the-project-owner) as drafted (2026-09-29).

## 2. Sequence and status

One gated slice delivered as six commits on `feat/ir-integration-readiness`, in this order. Each
commit passes the full managed gate on its own; the review stop is after commit 6.

| Commit | Scope | Status | Completed |
| :--- | :--- | :--- | :--- |
| 1 | [Required dependencies and the ticker default](#31-required-dependencies-and-the-ticker-default) | Complete | 2026-09-29 |
| 2 | [Delete `MomentumPolicy`](#32-delete-momentumpolicy) | Complete | 2026-09-29 |
| 3 | [Instrument profile embedded in `MomentumRun`](#33-instrument-profile-embedded-in-momentumrun) | Complete | 2026-09-29 |
| 4 | [`--as-of` and `--no-cache` on every caller surface](#34---as-of-and---no-cache-on-every-caller-surface) | Complete | 2026-09-29 |
| 5 | [Durable documentation](#35-durable-documentation) | Complete | 2026-09-29 |
| 6 | [IR.2 acceptance record](#36-ir2-acceptance-record) | Complete | 2026-09-29 |

## 3. The commits

### 3.1 Required dependencies and the ticker default

- **Problem:** `MomentumAnalyzer.__init__` defaults to constructing `YFinanceClient()`, reads
  `settings` twice (start date, default ticker), and accepts two overlapping data dependencies
  (`data_client`, `market_data_provider`) plus a private `_ClientProviderAdapter` to bridge them.
- **Decision:** one required dependency, `market_data_provider: MarketDataProvider`, plus a
  required `start_date: str`. `_ClientProviderAdapter` is deleted: `BaseDataClient` already
  satisfies `MarketDataProvider` structurally (confirmed with `mypy --strict` for `BaseDataClient`,
  `CachedHistoricalDataClient`, `YFinanceClient` and `FixtureDataClient`). The TOML default ticker
  moves to the `momentum` CLI command, normalized through `require_ticker`; `default_ticker`,
  `resolve_ticker` and the `data_client` attribute are deleted.
- **Scope:** the analyzer module, `run_momentum`, both CLI composition roots, the evaluation
  composition root, and their tests. No caller-visible output changes, including the "the
  configured default ticker" wording in error messages.
- **Branch:** `feat/ir-integration-readiness`.
- **Detail:** [A.1](#a1-commit-1-required-dependencies-and-the-ticker-default).

### 3.2 Delete `MomentumPolicy`

- **Problem:** `MomentumPolicy` duplicates `MomentumConfig`'s three fields and validation. Its only
  production use is sourcing `MomentumToolArguments`' field defaults.
- **Decision:** delete it; `_MOMENTUM_DEFAULTS = MomentumConfig()`, the same pattern
  `cli.py`/`cli_workspace.py` already use for `_MOMENTUM_CLI_DEFAULTS`.
- **Scope:** `momentum_analyzer.py`, `orchestrator/analysis_tools.py`, one test.
- **Branch:** `feat/ir-integration-readiness`.
- **Detail:** [A.2](#a2-commit-2-delete-momentumpolicy).

### 3.3 Instrument profile embedded in `MomentumRun`

- **Problem:** Momentum is the only analyzer whose result does not carry the profile it ran with.
  Every caller composes the profile *after* calculation, and the orchestrator attaches it with
  `dataclasses.replace`; the workspace carries it beside the result instead.
- **Decision:** every caller composes the profile *before* calculation and passes it in
  `AnalysisContext`, the order Graham and FCF already use. `run_analysis` sets
  `MomentumRun.instrument_profile = context.instrument_profile` on every path. The orchestrator's
  `replace()` and `MomentumCapture.profile` are deleted; the workspace reads the profile from the
  result. `result_schema_version` bumps 1 → 2, and the evidence codec's version check becomes a
  per-method table (it currently hard-codes `1` for every non-FCF method).
- **Scope:** analyzer, orchestrator handler, `run_momentum`/`capture_momentum`, both CLI roots,
  `execution.py`, `codecs.py`, their tests. Rendered output unchanged.
- **Branch:** `feat/ir-integration-readiness`.
- **Detail:** [A.3](#a3-commit-3-instrument-profile-embedded-in-momentumrun).

### 3.4 `--as-of` and `--no-cache` on every caller surface

- **Problem:** the analyzer and IR.2.5's data-client layer honor `as_of` and `use_cache`, but only
  the orchestrator passes `as_of`, and every caller hard-codes `use_cache=True`.
- **Decision:** `MomentumSelection` gains `as_of: AwareDatetime | None = None` and
  `use_cache: bool = True`, in the same shape as the other three selections, and
  `config_schema_version` bumps 1 → 2. The `momentum` command gains `--as-of` and `--no-cache`
  in the other commands' shape (`--no-cache`'s help text names the historical price cache instead
  of the resolved-input cache). `MomentumToolArguments` gains
  `use_cache: bool = True`. `--no-cache` bypasses the historical price cache only; the instrument
  profile cache is still used wherever a database is already open, exactly as for Graham.
- **Scope:** `requests.py`, `cli.py`, `cli_workspace.py`, `analysis_tools.py`, `codecs.py`, and
  their tests, plus new CLI tests for both options. Output of every existing invocation is unchanged.
- **Branch:** `feat/ir-integration-readiness`.
- **Detail:** [A.4](#a4-commit-4---as-of-and---no-cache-on-every-caller-surface).

### 3.5 Durable documentation

- **Problem:** user and architecture docs describe Momentum as having no `--as-of`, name the
  deleted adapter, and don't say what an `--as-of` result means for adjusted prices.
- **Decision:** document the two new options and the retroactive-revision caveat; correct
  `ARCHITECTURE.md`'s data-boundary paragraph. No planning labels in these files (`AGENTS.md` §4).
- **Scope:** `docs/user/strategies/MOMENTUM.md`, `docs/user/USAGE.md`, `docs/project/ARCHITECTURE.md`.
- **Branch:** `feat/ir-integration-readiness`.
- **Detail:** [A.5](#a5-commit-5-durable-documentation).

### 3.6 IR.2 acceptance record

- **Problem:** IR.2 is accepted only once all six sub-slices have landed and the conformance tests
  pass against the final state (IR.2 plan §6.12).
- **Decision:** one record, in the IR.2 plan, following IR.2.5's record format.
- **Scope:** the IR.2 plan's §6.12 row for IR.2.6 and a new acceptance-record section; this plan's
  §2 table.
- **Branch:** `feat/ir-integration-readiness`.
- **Detail:** [A.6](#a6-commit-6-ir2-acceptance-record).

## 4. Out of scope

- Any change to SMA, RSI or crossover calculation, windows, or classification.
- A presentation line or `--json` key for the requested `--as-of` boundary. The existing "Latest
  data observation" line and `--json`'s `as_of`/`data_as_of` keys already report the truncated
  series; typed `--json` envelopes belong to SWC ([B.1](#b1-decisions-flagged-for-the-project-owner), item 2).
- Changes to the historical cache mechanism, its keys, or `CachedHistoricalDataClient` (IR.2.5).
- Graham Number's pre-existing Config-path/Selection-path EPS-basis default divergence (IR.2 plan
  §6.1 item 13), which is still waiting for the project owner's decision.
- Converting `IR2_ANALYZER_ENVELOPE_PLAN.md` to the planning-document structure. Commit 6 touches
  it, which under `AGENTS.md`'s structure rule triggers a conversion; that is proposed as its own
  change rather than folded into this slice.
- Merging `feat/ir-integration-readiness` to `main`.

## 5. Acceptance criteria

- **Parity, checked by tests:** each `AnalysisContext` field reaches `MomentumAnalyzer.run_analysis`
  from every caller surface: the direct `momentum` command, `ian refresh`, and the orchestrator
  tool. `as_of` and `use_cache` are driven by a real option or argument on all three, and
  `instrument_profile` is present on the returned `MomentumRun` on all three.
- **No output change for existing invocations:** every existing `momentum` CLI test, the Golden
  suite's Momentum cases, and the existing-strategy output-contract tests pass unchanged, apart from
  tests that construct the deleted classes or parameters directly.
- **Storage:** `momentum --no-cache` without `--save-run` never creates the database file (same
  test shape as Graham's `test_no_cache_does_not_open_database`).
- **Versions:** `MomentumSelection.config_schema_version` is 2; Momentum's
  `(method_version, result_schema_version)` is `(1, 2)`; Graham's and FCF's versions are unchanged;
  runs and watchlist selections written by this build decode.
- **Structure:** `MomentumAnalyzer` has no default dependency, no `settings` read, and no ticker
  fallback; `MomentumPolicy`, `_ClientProviderAdapter`, `resolve_ticker` and the orchestrator's
  `replace()` no longer exist. The IR.2 conformance tests (IR.2 plan §6.6) pass.
- **Quality gate:** the full managed gate after every commit, ≥85% coverage, plus a live smoke of
  `momentum <ticker>`, `--as-of`, `--no-cache` and `--save-run` against a throwaway database.

## 6. Background: what IR.2.1–IR.2.5 already delivered

The IR.2 plan's row for IR.2.6 (written 2026-09-24) lists some work that earlier sub-slices have
since done. Checked against the code at `54fd46e`:

- **Already done (IR.2.3):** `compute_momentum_metrics` is a pure module-level function;
  `run_with_context` is gone; the resolver checks and publishes quality once and `run_analysis`
  re-checks without publishing.
- **Already done (IR.2.5):** `use_cache` is threaded, required and keyword-only, from
  `MomentumInputResolver.resolve` through `MarketDataProvider` to `CachedHistoricalDataClient`, and
  `_production_historical_client(use_cache=False)` never opens storage. Only the caller surface
  was left for IR.2.6.
- **Already done (IR.2.1):** `MomentumToolArguments` inherits `as_of`, and the orchestrator passes
  it to `run_analysis`.
- **Left for IR.2.6:** everything in §3.
- **No production orchestrator composition root exists yet:** `AnalysisToolDependencies` is
  constructed only by `src/evaluation/composition.py` and tests, so the orchestrator changes are
  exercised through the Golden suite and `tests/orchestrator/`.

---

## Appendix A: Implementation detail

Line numbers are as of `54fd46e` and will drift during implementation.

### A.1 Commit 1: required dependencies and the ticker default

`momentum_analyzer.py`:

```python
class MomentumAnalyzer(BaseAnalyzer[MomentumConfig, MomentumRun]):
    def __init__(self, *, market_data_provider: MarketDataProvider, start_date: str) -> None:
        self._market_data_provider: Final[MarketDataProvider] = market_data_provider
        self._start_date: Final[str] = start_date
```

- Delete `default_ticker`, `data_client`, the `data_client`/`market_data_provider` public
  attributes, `resolve_ticker` (lines 144–150), `_ClientProviderAdapter` (lines 421–438), and the
  `YFinanceClient` import. The module keeps its `settings` import: `MomentumConfig`'s window
  `default_factory` functions read it, which is config-default sourcing, not an analyzer read.
- `run_momentum(selection, ticker: str, market_data_provider: MarketDataProvider, *, start_date: str,
  executed_at: datetime)`. `ticker` stops being optional: nothing inside the workspace resolves a
  default any more.

Composition roots:

| Root | Change |
| :--- | :--- |
| `cli.py` `momentum` | After `_resolve_ticker(..., required=False)`, resolve `None` to the TOML default and normalize it with `require_ticker`. Keep `label` computed from the *unresolved* value, so error text is unchanged. Read `start_date` from settings once. |
| `cli_workspace.py` `_execute_momentum` | Read `start_date` from settings; pass the borrowed historical client as `market_data_provider`. |
| `evaluation/composition.py:155` | `MomentumAnalyzer(market_data_provider=FixtureMarketDataProvider(momentum_frame), start_date=<settings value>)`, reading the same setting production reads so fixture behavior is unchanged. `FixtureDataClient()` is no longer passed. |

Tests: `tests/analysis/momentum/test_momentum_analyzer.py` (five constructions, including three
bare `MomentumAnalyzer()` and one read of `analyzer.data_client`),
`tests/analysis/momentum/test_momentum_hardening.py`, `tests/analysis/test_base_analyzer_conformance.py`,
`tests/orchestrator/test_analysis_tools.py`, `tests/test_cli_historical_cache.py` (asserts
`analyzer.data_client is custom`; becomes an identity check on the provider handed to
`run_momentum`), `tests/workspace/test_momentum_execution.py`, and the `run_momentum` callers in
`tests/workspace/test_execution.py`, `test_refresh.py`, `tests/test_cli_workspace.py` and
`tests/reporting/test_analysis_run_replay.py`. New: the `momentum` command with no ticker resolves
the configured default, normalized.

### A.2 Commit 2: delete `MomentumPolicy`

- Delete `MomentumPolicy` (`momentum_analyzer.py:88–101`) and its export.
- `analysis_tools.py:73`: `_MOMENTUM_DEFAULTS = MomentumConfig()`. Evaluated once at import, like
  the class-level defaults it replaces, so tool-argument defaults don't change.
- `tests/analysis/momentum/test_momentum_hardening.py:15,68` constructs `MomentumConfig` instead.

### A.3 Commit 3: instrument profile embedded in `MomentumRun`

Order at every root becomes: normalize ticker → compose profile → build context → run.

| Site | Change |
| :--- | :--- |
| `momentum_analyzer.py` `run_analysis` | `MomentumRun(..., instrument_profile=context.instrument_profile)`. |
| `analysis_tools.py` `analyze_momentum` | `profile = self._resolve_profile(arguments.ticker)` before the run; `instrument_profile=profile` in the context; delete the `replace()` line and, if now unused, the `replace` import. |
| `run_momentum` | Gains `instrument_profile: InstrumentProfile | None`, passed to `selection.to_analysis_context`. |
| `capture_momentum(run)` | Loses its `profile` parameter; `MomentumCapture.profile` is deleted. |
| `execution.py` `from_momentum_capture` | `profile=capture.run.instrument_profile`. |
| `cli.py` `momentum`, both branches | Compose the profile (cache-backed on `--save-run`, live otherwise, as today) before `run_momentum`; the presenter reads `run.instrument_profile`. |
| `cli_workspace.py` `_execute_momentum` | Same reorder; `profile_cache` or live composition chosen exactly as today. |
| `execution.py:64` | `("momentum", "sma_crossover"): (1, 2)`. |
| `codecs.py` `decode_evidence` | Replace the `2 if fcf_pair else 1` / `3 if fcf_pair else 1` literals with one table of expected `(config_schema_version, method_version, result_schema_version)` per `(analysis_id, method_id)`, seeded so Graham and FCF are unchanged. Commit 4 bumps Momentum's config entry in the same table. |

The profile is composed from the normalized ticker every root already holds, so it still satisfies
`_MomentumEvidence`'s check that `profile.ticker == metrics.ticker`. Profile lookup fails open
(`ARCHITECTURE.md` §7), so composing it first adds no new failure; on the price-failure path it
adds one metadata lookup before the same error.

Tests: `tests/workspace/test_momentum_codec.py`, `test_momentum_execution.py`, `test_execution.py`
(capture shape, version tuple), `tests/orchestrator/test_analysis_tools.py` (profile present
without `replace`), `tests/reporting/test_analysis_run_replay.py`. New: a stored Momentum run with
`result_schema_version == 1` raises `UnsupportedRunVersionError`; Graham's and FCF's version checks
are unchanged.

### A.4 Commit 4: `--as-of` and `--no-cache` on every caller surface

`requests.py` `MomentumSelection`:

```python
class MomentumSelection(BaseModel):
    config_schema_version: Literal[2] = 2
    ...
    as_of: AwareDatetime | None = None
    use_cache: bool = Field(default=True, strict=True)

    def to_analysis_context(self, executed_at, instrument_profile=None) -> AnalysisContext:
        return AnalysisContext(
            as_of=self.as_of,
            executed_at=executed_at,
            use_cache=self.use_cache,
            instrument_profile=instrument_profile,
        )
```

Delete the class docstring's "Momentum accepts no `as_of` option" and the method docstring's
"not yet" note. `from_settings` needs no change: extra keyword arguments already pass through.

| Site | Change |
| :--- | :--- |
| `cli.py` `momentum` | Add `--as-of` (copied from `graham-number`, lines 336–340) and `--no-cache` (same shape, help text "Bypass historical price cache reads and writes"); `boundary = _parse_as_of(as_of)`; `MomentumSelection(..., as_of=boundary, use_cache=not no_cache)`; `_production_historical_client(..., use_cache=selection.use_cache)` in both branches. Delete the comment at line 269. |
| `cli_workspace.py` `_execute_momentum` | `_production_historical_client(..., use_cache=selection.use_cache)`. |
| `analysis_tools.py` | `MomentumToolArguments.use_cache: bool = True`; context `use_cache=arguments.use_cache`; delete the "not yet a real per-call toggle" comment. |
| `codecs.py` | Momentum's expected `config_schema_version` becomes 2 in the commit-3 table. |

`--save-run --no-cache` still checks run-storage readiness (saving needs the database) and still
uses the profile cache; only the historical price cache is bypassed.

Tests: `tests/workspace/test_requests.py` (new fields; v2 literal; round trip), `test_watchlists.py`,
`tests/test_cli_refresh.py`, `tests/test_cli_workspace.py`, `tests/evaluation/cases/test_momentum.py`,
`tests/evaluation/test_composition.py`, `tests/evaluation/test_runner.py`. New:
- `momentum --as-of <date>` reaches the resolver with that boundary (fixture frame; the latest
  observation after truncation is on or before it).
- `momentum --no-cache` never creates the database file; `momentum` without it still does.
- `momentum --save-run --as-of … --no-cache` persists a selection with both fields, and `ian refresh`
  of that entry reuses them.
- A stored watchlist entry with a Momentum `config_schema_version == 1` selection fails to decode
  with the existing "does not match its method/version columns" error, not silently
  ([B.1](#b1-decisions-flagged-for-the-project-owner), item 1).

### A.5 Commit 5: durable documentation

- `docs/user/strategies/MOMENTUM.md`: the `--as-of` and `--no-cache` options, and a note that
  provider-adjusted prices are revised retroactively (splits and dividends restate history), so an
  `--as-of` result is filtered to a date but reflects today's adjusted view of prices on that date.
- `docs/user/USAGE.md`: one `--as-of`/`--no-cache` example in the "Momentum analysis" section,
  next to the existing `--short-window` example.
- `docs/project/ARCHITECTURE.md` line 223: `MomentumAnalyzer` takes one `MarketDataProvider`, and
  `BaseDataClient` satisfies it directly; remove the `_ClientProviderAdapter` sentence.
- `src/workspace/momentum_execution.py`'s module docstring: drop "composed after calculation".
- Historical planning records that say Momentum has no `--as-of` (Step 3.4, ESC-D) are records of
  their time and stay unchanged.

### A.6 Commit 6: IR.2 acceptance record

In `IR2_ANALYZER_ENVELOPE_PLAN.md`: link the IR.2.6 row to this plan, set it Complete with its date,
and add an acceptance record covering the gate result, the live smoke, the conformance tests
(§6.6) against the final state, the version fields changed across IR.2 (from §6.10 and this plan),
and confirmation that no Alembic migration was added. The IR contract's own IR.2 row changes to
Complete only if the project owner accepts the record. The ESC re-run (IR contract §5) is not part
of this record: it runs once IR as a whole is complete, after IR.3 and IR.6.

---

## Appendix B: Decision records

### B.1 Decisions flagged for the project owner

`AGENTS.md` §0 requires decisions, not open items, so this plan decides each of these. They are
listed here because each is a behavior the project owner might have overruled. The project owner
accepted all three as drafted on 2026-09-29.

1. **Existing Momentum watchlist entries stop loading.** This is the first bump of a *selection*
   version; earlier bumps only touched result versions. Watchlist entries store the selection, and
   `decode_selection` validates it against `Literal[2]`, so an existing entry saved with version 1
   fails to decode on `ian refresh` and `watchlist show`. Per §0 this is accepted: no compatibility
   code, and the entry is re-added or the local database discarded. The alternative, reading a
   version-1 Momentum selection as version 2 with `as_of=None` and `use_cache=True` (which is
   exactly what it meant), is compatibility code §0 rules out.
2. **No presentation change for `--as-of`.** Graham's and FCF's presenters show the requested
   boundary; Momentum's will not in this slice. Its `--json` already emits `as_of` meaning the
   latest *observation* date, and adding or renaming keys is the typed-envelope work that moved to
   SWC. Consequence: an `--as-of` run shows the truncated observation date, not the requested date.
3. **The profile is composed before calculation.** This matches Graham and FCF and is required to
   embed it through `AnalysisContext`, but it reverses the order Step 3.4 chose ("retain the
   profile currently composed by its CLI after calculation"). The only observable effect is one
   extra metadata lookup when the price fetch then fails.

### B.2 Corrections to the IR.2 plan found while drafting

- **§6.10 missed the codec's `config_schema_version` check.** `decode_evidence` requires
  `config_schema_version == 1` for every method, not only `result_schema_version`. Bumping
  `MomentumSelection` to 2 as §6.10 planned would make every newly saved Momentum run fail to
  decode. Handled by the per-method table in A.3/A.4.
- **§6.5 said `run_momentum`'s `ticker: str | None` is unaffected.** It can't be: once the analyzer
  has no fallback, something must resolve `None` first. The CLI does (A.1); `run_momentum` takes
  `str`.
- **§6.5 planned to keep both `data_client` and `market_data_provider`.** One required
  `MarketDataProvider` is enough, since `BaseDataClient` already satisfies it; the adapter and the
  second parameter are deleted instead of made required (A.1).
- **The IR.2.6 row lists `compute_momentum_metrics` and the quality-check split implicitly as
  pending.** Both landed in IR.2.3 (§6).

### B.3 Found during implementation

Gaps the plan missed, fixed in the commit where each became visible. Items 3, 4 and the help text
in item 6 were corrected in a review-fix commit before the acceptance record.

1. **Commit 1: the A.4 snippet failed the repository's formatter check.** `ruff format --check .`
   formats Python code blocks in Markdown, and the indented `MomentumSelection` excerpt in A.4 was
   not formatter-clean, so the gate failed on this plan. The excerpt is now a formatted class
   excerpt with the same content.
2. **Commit 3: the `momentum_execution.py` module and `MomentumCapture` docstrings described the
   after-calculation profile order.** They became wrong in this commit, so both were corrected here
   rather than in commit 5 (A.5 keeps only the user and architecture documents).
3. **Commit 3, corrected in the review-fix commit: the `momentum` presenters read
   `run.instrument_profile`, as A.3 specifies.** Commit 3 first left them reading the locally composed
   profile, because the direct command's existing tests replace `run_analysis` with a canned run that
   carries no profile. That was a deviation, not an accepted one. The presenter now reads the profile
   from the run and treats a run without one as an invariant failure, and the tests that replace
   `run_analysis` return a run carrying the caller's profile (`carry_profile` in
   `tests/_cli_helpers.py`), as the real analyzer does. A test asserts the failure case.
4. **Commit 4, corrected in the review-fix commits: a stored version-1 Momentum watchlist selection
   failed with the selection's own validation error, not the "does not match its method/version
   columns" error A.4 names, and `watchlist show` and `ian refresh` printed a raw validation
   traceback.** `decode_selection` validates the stored JSON against `Literal[2]` before it compares
   identity columns. It now raises `StoredSelectionError` (still a `ValueError`) with a plain clause,
   and `SQLiteWatchlistRepository._decode_entry` adds which entry it was, so the CLI prints one line and
   exits 1:
   `Watchlist 'Mixed', entry 2 (MSFT, sma_crossover): saved by an earlier version (selection version 1)
   and can no longer be read. Remove it with: ian watchlist remove-entry "Mixed" 2`
   The line uses the canonical `method_id`; IR.6 switches it to the alias with the other human-readable
   text. The column-mismatch and malformed-JSON cases raise the same error type with their own clause.
   Neither path reads a version-1 entry as version 2, which is what B.1 item 1 decides. A
   watchlist holding an unreadable entry cannot be listed by `watchlist show`, which decodes every entry
   before printing, so the error is the only place the entry's number appears. Tests cover both commands,
   the exact line, the decode, and that the printed command restores the watchlist.
   **Decision (project owner) and fix: removal works one entry at a time, however many entries are
   unreadable.** `remove-entry`, `remove` (by ticker) and `disable` (by method) reloaded the surviving
   entries inside their transaction, so a second unreadable entry rolled the removal back and left the
   printed remedy unable to work. `SQLiteWatchlistRepository.remove_entry`, `remove_entries_for_ticker`
   and `remove_entries_for_method` now return `None` and decode nothing, so the removal commits. The three
   CLI commands read the watchlist back with `get()` only to display it; if that raises
   `StoredSelectionError`, they print a one-line confirmation (`Removed entry 2 from watchlist 'Mixed'.`),
   then the error line for the next unreadable entry, numbered from the renumbered list, and exit 1.
   `add-selection` is unchanged. Tests: three unreadable entries beside one valid entry, running the printed
   command repeatedly (each run removes exactly one and names the next; after the third, `watchlist show`
   lists only the valid entry), and `remove` and `disable` committing while another unreadable entry
   survives. A placeholder entry in `watchlist show` was proposed and not adopted.
5. **Commit 4: several existing test expectations encoded "Momentum has no `as_of`".** The foreign-field
   check in `test_requests.py` (`from_settings(as_of=None)`), the parser allowlist case
   `{"config": {"as_of": None}}`, and the version-2 probes in the identity-override, union-version and
   version-coercion tests all assumed version 1 was current. They now probe fields and versions that are
   still invalid (`use_cache: null`, version 99, `"2"`), and the alias test expects version 2 for Momentum.
6. **Commit 5: `watchlist create` and `watchlist add-selection` silently ignored `--as-of` and
   `--no-cache` for Momentum.** Both commands already declared the two options, and the selection
   builder discarded them for Momentum because Momentum's selection had nowhere to keep them. The
   plan's list of caller surfaces missed the watchlist commands; wiring them is within IR.2's acceptance
   line that every analyzer's real caller-facing surface exercises every `AnalysisContext` field. The
   builder now passes them through (`--as-of` parsed as for the other methods; `--no-cache` meaning the
   historical price cache). Both options' help text on both commands now names Momentum, and says that for
   Momentum `--no-cache` bypasses the historical price cache (review-fix commit). The workspace guide's
   flag table says the same. A test asserts the persisted selection.
7. **Commit 5: `watchlist show` output for Momentum entries gains `as_of` and `use_cache`.** Both the
   text detail and `--json` render the selection generically, so the new selection fields appear for
   Momentum exactly as they already do for the other three methods. `config_schema_version` (now 2)
   appears only in `--json`; the text view omits it. This follows from the selection shape A.4
   requires; no presentation code was changed. Recorded because it is a visible change to an existing
   command's output, and accepted by the project owner in review.
